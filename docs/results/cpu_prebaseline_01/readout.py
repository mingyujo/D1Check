"""Read frozen fits; verify arithmetic and raw provenance without re-fitting."""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_cpu_prebaseline as m


def table(path):
    with Path(path).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def readout(output,external=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    source=m.BUNDLE/'run_v1';errors=table(source/'energy_errors.csv');bins=table(source/'pre_bins.csv');features=table(source/'pre_features.csv')
    development=[r for r in features if r['role']=='development'];cols=('pre50_other_rate','late20_other_rate','contrast_core_s_per_s')
    ranges={k:[min(float(r[k]) for r in development),max(float(r[k]) for r in development)] for k in cols}
    diagnostics=[];pairs=[];raw_RMSE={}
    for key in ('30','180','final'):
        model=m.read(source/('candidate_'+key+'.json'));residual=[]
        for identity in model['development_ids']:
            use=[r for r in bins if r['session']==identity]
            x=np.array([float(r['other_rate_core_s_per_s']) for r in use]);y=np.array([float(r['mean_power_W']) for r in use])
            residual.extend(y-y.mean()-model['slope_W_per_core_s_per_s']*(x-x.mean()))
        value=float(np.sqrt(np.mean(np.square(residual))));raw_RMSE[key]=value
        assert abs(value-model['within_session_pre_RMSE_W']*np.sqrt(10))<1e-12
    for f in features:
        identity=f['session'];reasons=[k for k in cols if not ranges[k][0]<=float(f[k])<=ranges[k][1]]
        idle=[r for r in errors if r['session']==identity and r['phase']=='post_lane_idle' and r['variant']=='fixed_zero_offset'][0]
        candidate=[r for r in errors if r['session']==identity and r['phase']=='post_lane_idle' and r['variant']=='CPU_prebaseline'][0]
        dt=float(idle['hi_s'])-float(idle['lo_s'])
        diagnostics.append(dict(session=identity,role=f['role'],development_feature_range='outside' if reasons else 'within',
            outside_fields=';'.join(reasons),past_feature_cutoff_s=30.,hypothetical_issue_s=35.,
            pre50_other_rate=float(f['pre50_other_rate']),late20_other_rate=float(f['late20_other_rate']),
            proposed_baseline_correction_W=float(candidate['baseline_correction_W']),
            observed_idle_minus_P50_W=-float(idle['signed_J'])/dt,
            observed_idle_field_is_evaluation_target_not_input=True))
        for phase in ('reference120','future85','post_lane_idle','work_present'):
            use={r['variant']:r for r in errors if r['session']==identity and r['phase']==phase}
            if not use:continue
            base,new,original=use['fixed_zero_offset'],use['CPU_prebaseline'],use['original_frozen']
            pairs.append(dict(session=identity,role=f['role'],gap=f['gap'],policy=f['policy'],phase=phase,
                observed_J=float(base['full_energy_j']),original_abs_J=float(original['absolute_J']),
                fixed_abs_J=float(base['absolute_J']),new_abs_J=float(new['absolute_J']),
                signed_J=float(new['signed_J']),relative_signed=float(new['relative_signed']),
                change_abs_J=float(new['absolute_J'])-float(base['absolute_J']),
                worse_than_fixed=float(new['absolute_J'])>float(base['absolute_J'])+1e-9,
                development_feature_range='outside' if reasons else 'within'))
    for identity in [r['session'] for r in features]:
        for variant in ('original_frozen','fixed_zero_offset','CPU_prebaseline'):
            rows={r['phase']:r for r in errors if r['session']==identity and r['variant']==variant}
            a=float(rows['future85']['signed_J']);b=float(rows['post_lane_idle']['signed_J'])
            if 'work_present' in rows:b+=float(rows['work_present']['signed_J'])
            assert abs(a-b)<1e-9, 'error partition lost energy'
    fixed,_=m.prior.prior.read_candidate(m.prior.prior.BUNDLE/'run_v1')
    publics=m.read(source/'pre_inputs.json');curve_errors=[]
    for r in table(source/'energy_curves.csv'):
        p=next(p for p in publics if p['id']==r['session'])
        key=str(p['gap']) if p['role']=='development' else 'final';model=m.read(source/('candidate_'+key+'.json'))
        curve_errors.append(abs(m.predict(p,model,fixed,0,float(r['t_s']),opt_in=True)-float(r['CPU_prebaseline_J'])))
    assert max(curve_errors)<1e-12
    checked=0
    if external:
        inventory=m.read(source/'source_inventory.json');prior=m.read(ROOT/'docs/results/preboundary_evidence_01/run_v1/source_inventory.json')
        for relative,h in dict(prior['raw_files'],**inventory['files']).items():
            identity,name=relative.split('/',1);folder=Path(external)/inventory['source_locations'][identity]
            p=folder/name if '/' in name or name=='thermal.jsonl' else folder/'artifacts'/name
            if m.sha(p)!=h:raise ValueError('raw/export changed '+relative)
            checked+=1
        for identity,location in inventory['source_locations'].items():
            folder=Path(external)/location;binding=m.read(folder/'trace_export/export_binding.json')
            if m.sha(folder/'system_activity.pftrace')!=binding['trace_sha256']:raise ValueError('raw trace changed')
            checked+=1
            for key,h in binding['queries'].items():
                if m.sha(ROOT/('tools/perfetto/background_'+key+'.sql'))!=h:raise ValueError('trace query changed')
    summary=[]
    for role in ('development','confirmation'):
        for phase in ('reference120','future85','post_lane_idle','work_present'):
            use=[r for r in pairs if r['role']==role and r['phase']==phase]
            if use:summary.append(dict(role=role,phase=phase,sessions=len(use),
                mean_original_abs_J=float(np.mean([r['original_abs_J'] for r in use])),
                mean_fixed_abs_J=float(np.mean([r['fixed_abs_J'] for r in use])),
                mean_new_abs_J=float(np.mean([r['new_abs_J'] for r in use])),
                mean_new_abs_relative_percent=float(np.mean([100*abs(r['relative_signed']) for r in use])),
                improved_vs_fixed=sum(r['change_abs_J'] < -1e-9 for r in use),
                worsened_vs_fixed=sum(r['worse_than_fixed'] for r in use)))
    for name,rows in [('feature_and_idle_readout',diagnostics),('paired_errors',pairs),('role_summary',summary)]:
        m.prior.prior.old.scope_api.tail.s.csv_write(out/(name+'.csv'),rows)
    m.write(out/'readout.json',dict(status='candidate_not_adopted',diagnostic_only=True,
        slope_W_per_core_s_per_s=m.read(source/'candidate_final.json')['slope_W_per_core_s_per_s'],
        actual_pre_fit_RMSE_W=raw_RMSE,stored_RMSE_reporting_error_corrected_without_refit=True,
        coefficient_and_prediction_bytes_unchanged=True,development_feature_ranges=ranges,
        confirmation_outside_pre_feature_ranges=sum(r['role']=='confirmation' and r['development_feature_range']=='outside' for r in diagnostics),
        verification_raw_and_export_files=checked,energy_partition_max_error_lt_J=1e-9,
        shared_curve_replay_max_error_J=max(curve_errors),shared_curve_points=len(curve_errors),
        formal_fits_repeated=0,default_changed=False,RL_changed=False,AP_changed=False,strict_support=False,experiment_ready=False,
        device_commands=0,future_CPU_or_power_used_in_prediction=False,
        root_cause='Late pre CPU is neither a guaranteed future background level nor an energy cause identifier; recorded C0 counterexamples show unchanged/rising pre activity followed by reduced future activity.'))
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--external-root');a=p.parse_args();readout(a.output,a.external_root)
