"""Frozen-head ablation, original-error reproduction and provenance checks; no fit."""
import argparse
import csv
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_registered_baseline as m


def table(path):
    with Path(path).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def readout(output,external=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);source=m.BUNDLE/'run_v1';reg=m.assets(source)
    contract=m.old.read(m.BUNDLE/'secondary_readout_contract.json')
    fitted=m.old.read(source/'fit_receipt.json')
    for key,h in fitted['model_hashes'].items():
        if m.old.sha(source/('candidate_'+key+'.json'))!=h:raise ValueError('frozen candidate changed')
    original=m.old.read(m.old.prior.prior.old.analysis.j.m.MODEL)
    fixed,_=m.old.prior.prior.read_candidate(m.old.prior.prior.BUNDLE/'run_v1')
    heads=dict(original_frozen=dict(idle_bias_w=0.,increments=original['energy_increment_w']),existing_zero_offset=fixed)
    lookup={c['id']:c for c in m.old.history()};errors=[];curves=[];summaries=[]
    primary=table(source/'energy_errors.csv');original_stored=table(m.old.BUNDLE/'run_v1/energy_errors.csv')
    for p in m.old.read(source/'pre_inputs.json'):
        c=lookup[p['id']];key=str(c['gap']) if c['role']=='development' else 'final';model=m.old.read(source/('candidate_'+key+'.json'))
        for oldname,newname in [('original_frozen','FROZEN'),('fixed_zero_offset','ZERO'),('CPU_prebaseline','PRIOR_CPU')]:
            for r in primary:
                if r['session']!=c['id'] or r['method']!=newname:continue
                z=next(z for z in original_stored if z['session']==c['id'] and z['variant']==oldname and z['phase']==r['phase'])
                assert abs(float(z['predicted_J'])-float(r['predicted_J']))<1e-12
                assert abs(float(z['signed_J'])-float(r['signed_J']))<1e-12
        windows=[r for r in primary if r['session']==c['id'] and r['method']=='ZERO']
        for name,head in heads.items():
            for base in ('P50','FULL_MEAN','FULL_CPU'):
                def y(lo,hi):
                    return m.old.prior.prior.energy(p,p['actual'],head,lo,hi) if base=='P50' else m.predict(p,model,head,lo,hi,base,opt_in=True)
                for r in windows:
                    lo,hi=float(r['lo_s']),float(r['hi_s']);obs=float(r['full_energy_j']) if r['full_energy_j'] else None;pred=y(lo,hi)
                    errors.append(dict(session=c['id'],role=c['role'],gap=c['gap'],policy=c['policy'],phase=r['phase'],
                        head=name,initializer=base,lo_s=lo,hi_s=hi,observed_J=obs,predicted_J=pred,
                        signed_J=pred-obs if obs is not None else None,absolute_J=abs(pred-obs) if obs is not None else None,
                        relative_signed=(pred-obs)/obs if obs else None,posthoc_secondary=True,
                        actual_schedule_conditional=True,future_observations_used_as_inputs=False))
                for t in range(1,121):
                    obs=m.old.prior.prior.old.observed.measured_energy(c,0.,float(t))['full_energy_j']
                    curves.append(dict(session=c['id'],role=c['role'],head=name,initializer=base,t_s=t,
                        observed_J=obs,predicted_J=y(0.,float(t)),signed_J=y(0.,float(t))-obs if obs is not None else None))
    paired=[]
    for role in ('development','confirmation'):
        for phase in ('reference120','future85','post_lane_idle','work_present'):
            for head in heads:
                for base in ('P50','FULL_MEAN','FULL_CPU'):
                    use=[r for r in errors if r['role']==role and r['phase']==phase and r['head']==head and r['initializer']==base and r['absolute_J'] is not None]
                    baseline={r['session']:r for r in errors if r['role']==role and r['phase']==phase and r['head']==head and r['initializer']=='P50'}
                    if not use:continue
                    summaries.append(dict(role=role,phase=phase,head=head,initializer=base,sessions=len(use),
                        mean_absolute_J=float(np.mean([r['absolute_J'] for r in use])),mean_signed_J=float(np.mean([r['signed_J'] for r in use])),
                        maximum_absolute_J=max(r['absolute_J'] for r in use),
                        improved_vs_same_head=sum(r['absolute_J']<baseline[r['session']]['absolute_J']-1e-9 for r in use),
                        worsened_vs_same_head=sum(r['absolute_J']>baseline[r['session']]['absolute_J']+1e-9 for r in use)))
                    if phase=='reference120':
                        for gap in (30,180):
                            u=[r for r in use if r['gap']==gap and not r['session'].endswith('_C0')]
                            cpu=next(r for r in u if r['session'].endswith('_CPU'));par=next(r for r in u if r['session'].endswith('_PAR'))
                            observed=cpu['observed_J']-par['observed_J'];pred=cpu['predicted_J']-par['predicted_J']
                            paired.append(dict(role=role,gap=gap,head=head,initializer=base,
                                CPU_minus_PAR_observed_J=observed,CPU_minus_PAR_predicted_J=pred,
                                signed_difference_error_J=pred-observed,absolute_difference_error_J=abs(pred-observed),
                                matched_initial_condition=False,causal_policy_effect_identified=False,posthoc=True))
    for identity in lookup:
        for head in heads:
            for base in ('P50','FULL_MEAN','FULL_CPU'):
                use={r['phase']:r for r in errors if r['session']==identity and r['head']==head and r['initializer']==base}
                parts=use['post_lane_idle']['signed_J']+use.get('work_present',{'signed_J':0.})['signed_J']
                assert abs(use['future85']['signed_J']-parts)<1e-9
    checked=0
    if external:
        inv=m.old.read(ROOT/'docs/results/cpu_prebaseline_01/run_v1/source_inventory.json')
        previous=m.old.read(ROOT/'docs/results/preboundary_evidence_01/run_v1/source_inventory.json')
        for relative,h in dict(previous['raw_files'],**inv['files']).items():
            identity,name=relative.split('/',1);folder=Path(external)/inv['source_locations'][identity]
            path=folder/name if '/' in name or name=='thermal.jsonl' else folder/'artifacts'/name
            if m.old.sha(path)!=h:raise ValueError('raw/export changed '+relative)
            checked+=1
        for identity,location in inv['source_locations'].items():
            folder=Path(external)/location;binding=m.old.read(folder/'trace_export/export_binding.json')
            if m.old.sha(folder/'system_activity.pftrace')!=binding['trace_sha256']:raise ValueError('raw trace changed')
            checked+=1
    for name,rows in [('fixed_head_errors',errors),('fixed_head_curves',curves),('fixed_head_summary',summaries),('policy_difference_errors',paired)]:
        m.old.prior.prior.old.scope_api.tail.s.csv_write(out/(name+'.csv'),rows)
    m.old.write(out/'receipt.json',dict(status='secondary_fixed_head_readout_complete',contract_sha256=m.old.sha(m.BUNDLE/'secondary_readout_contract.json'),
        secondary_posthoc=True,no_head_selection=True,additional_fits=0,AP_fits=0,device_commands=0,
        original_three_method_values_reproduced=True,full_energy_partition_tolerance_J=1e-9,raw_and_export_files_unchanged=checked,
        original_and_candidate_heads=2,initializers=3,sessions=12,default_changed=False,RL_changed=False,strict_support=False,experiment_ready=False))
    print(m.old.prior.prior.terminal_json([r for r in summaries if r['role']=='confirmation' and r['phase']=='reference120']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--external-root');a=p.parse_args();readout(a.output,a.external_root)
