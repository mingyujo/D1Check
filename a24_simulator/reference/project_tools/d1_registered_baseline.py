"""One fixed full-recovery CPU baseline candidate plus mean-only ablation. PC only."""
import argparse
import csv
import math
import time
import traceback
from pathlib import Path
import numpy as np
from tools import d1_cpu_prebaseline as old

ROOT=old.ROOT
BUNDLE=ROOT/'docs/results/registered_baseline_01'
METHODS=('FROZEN','ZERO','PRIOR_CPU','FULL_MEAN','FULL_CPU')


def median(values,weights):
    values=np.asarray(values,dtype=float);weights=np.asarray(weights,dtype=float)
    if len(values)!=len(weights) or len(values)<2 or not np.isfinite(values).all() or not np.isfinite(weights).all() or np.any(weights<=0):
        raise ValueError('invalid weighted median; no missing-value filling')
    ix=np.argsort(values,kind='stable');v=values[ix];w=weights[ix];cum=np.cumsum(w);half=w.sum()/2
    i=int(np.searchsorted(cum,half,side='left'))
    return float((v[i]+v[i+1])/2) if i+1<len(v) and abs(cum[i]-half)<1e-12 else float(v[i])


def features(rows):
    if len(rows)<15 or rows[0]['lo_s']>-45 or rows[-1]['hi_s']!=30.:
        raise ValueError('registered recovery coverage missing')
    if any(b['lo_s']!=a['hi_s'] for a,b in zip(rows,rows[1:])) or any(
            r['hi_s']-r['lo_s']!=5 or r['latest_power_event_s']>=35 or r['hi_s']>30 for r in rows):
        raise ValueError('gapped or future pre input')
    x=np.array([r['other_rate_core_s_per_s'] for r in rows]);y=np.array([r['mean_power_W'] for r in rows])
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(x<0) or np.any(x>8) or np.any(y<=0):
        raise ValueError('invalid pre CPU or power')
    return dict(pre_full_mean_W=float(y.mean()),pre_full_mean_other=float(x.mean()),
        persistent_other_proxy=median(x,np.full(len(x),5.)),
        duration_s=5*len(rows),pre_start_s=float(rows[0]['lo_s']),pre_end_s=30.,
        event_cutoff_s=30.,hypothetical_issue_s=35.,online_export_available=False,
        median_is_operational_proxy_not_physical_persistent_state=True)


def fit(rows,registered_ids):
    identities={r['session'] for r in rows}
    if len(identities)<3 or not identities<=set(registered_ids) or any(r['role']!='development' for r in rows):
        raise ValueError('registered development-only fit')
    X=[];Y=[];details=[]
    for identity in sorted(identities):
        use=[r for r in rows if r['session']==identity];features(use)
        x=np.array([r['other_rate_core_s_per_s'] for r in use]);y=np.array([r['mean_power_W'] for r in use])
        w=1/math.sqrt(len(use)*len(identities));X.extend((x-x.mean())*w);Y.extend((y-y.mean())*w)
        details.append(dict(session=identity,pre_bins=len(use)))
    x=np.asarray(X);y=np.asarray(Y);information=float(x@x)
    if information<=np.finfo(float).eps:raise ValueError('slope not identified; no invented coefficient')
    unconstrained=float(x@y/information);b=max(0.,unconstrained)
    return dict(version='registered-full-pre-CPU-baseline-v1',coefficient_count=1,slope_W_per_core_s_per_s=b,
        unconstrained_slope=unconstrained,information=information,pre_equal_session_RMSE_W=float(np.sqrt(np.sum((y-b*x)**2))),
        development_ids=sorted(identities),pre_bins_by_session=details,
        formula='P_full_mean + b*(time-weighted median other_CPU - P_full_mean other_CPU rate); fixed35..120 only',
        physical_CPU_power_identified=False,persistent_CPU_identified=False,
        future_observations_used_in_fit=False,default=False,strict_support=False,accuracy_pass=None,experiment_ready=False)


def predict(public,model,fixed,lo,hi,method='FULL_CPU',*,opt_in=False):
    if not opt_in:raise ValueError('explicit offline diagnostic opt-in required')
    if method not in ('FULL_MEAN','FULL_CPU') or not 0<=lo<hi<=120:
        raise ValueError('unsupported method/horizon')
    f=public['full_pre_features']
    if not public['trace_complete'] or f['event_cutoff_s']!=30. or f['hypothetical_issue_s']!=35. or f['duration_s']<75:
        raise ValueError('pre feature unavailable')
    b=model['slope_W_per_core_s_per_s'] if method=='FULL_CPU' else 0.
    pre=f['pre_full_mean_W']+b*(f['persistent_other_proxy']-f['pre_full_mean_other'])
    if not all(math.isfinite(v) for v in (b,pre,public['pre_w'])) or b<0 or pre<=0:
        raise ValueError('invalid/nonpositive baseline; no clipping')
    base=old.prior.prior.energy(public,public['actual'],fixed,lo,hi)
    return base+(pre-public['pre_w'])*(max(0.,hi-35)-max(0.,lo-35))


def prepare(external,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    inventory=old.read(ROOT/'docs/results/cpu_prebaseline_01/run_v1/source_inventory.json')
    frozen=old.read(ROOT/'docs/results/preboundary_evidence_01/run_v1/source_inventory.json')
    rows=[];publics=[];availability=[]
    for c in old.history():
        folder=Path(external)/inventory['source_locations'][c['id']]
        path=folder/'artifacts/history_boundary.json'
        if old.sha(path)!=inventory['files'][c['id']+'/history_boundary.json']:raise ValueError('boundary source mismatch')
        h=old.read(path);trace=folder/'trace_export'
        for name in ('sched.csv','clock.csv','loss.csv','audit.json','cpu.csv','export_binding.json'):
            if old.sha(trace/name)!=inventory['files'][c['id']+'/trace_export/'+name]:raise ValueError('trace/export changed')
        release=folder/'artifacts/conditioning_requests.json'
        if old.sha(release)!=frozen['raw_files'][c['id']+'/conditioning_requests.json']:raise ValueError('conditioning source changed')
        conditioning=old.read(release)
        if len(conditioning)!=96 or max(r['lane_available_ns'] for r in conditioning)>h['recovery_start_ns']:
            raise ValueError('pre window contains conditioning work')
        origin=h['target_start_ns'];first=math.ceil((h['recovery_start_ns']-origin)/(5*10**9))*5
        lead=(origin+first*10**9-h['recovery_start_ns'])/1e9
        if not 0<=lead<5:raise ValueError('invalid fixed bin alignment')
        bins=old.pre_power_bins(c,old.cpu_bins(trace/'sched.csv',origin,left=first,right=30,width=5))
        f=features(bins)
        rows.extend(dict(session=c['id'],role=c['role'],gap=c['gap'],**b) for b in bins)
        publics.append(dict(id=c['id'],role=c['role'],gap=c['gap'],policy=c['policy'],pre_w=c['pre_w'],actual=c['actual'],
            trace_complete=True,full_pre_features=f))
        availability.append(dict(session=c['id'],role=c['role'],gap=c['gap'],policy=c['policy'],**f,
            discarded_leading_partial_s=lead,conditioning_calls=96,additional_inference=0,
            full_8_CPU_coverage=True,raw_hash_match=True))
        print(old.prior.prior.terminal_json(dict(stage='registered_pre_extract',session=c['id'],pre_seconds=f['duration_s'])),flush=True)
    old.write(out/'pre_inputs.json',publics)
    for name,value in [('pre_bins',rows),('availability',availability)]:old.prior.prior.old.scope_api.tail.s.csv_write(out/(name+'.csv'),value)
    sources=old.prior.prior.registration()['sources']
    sources={p:old.sha(ROOT/p) for p in sources}
    for p in ('tools/d1_registered_baseline.py','tools/d1_cpu_prebaseline.py',
              'docs/results/registered_baseline_01/analysis_contract.json','docs/results/energy_ap_zero_offset_01/run_v1/candidate.json',
              'docs/results/cpu_prebaseline_01/run_v1/candidate_final.json','docs/results/cpu_prebaseline_01/run_v1/candidate_30.json',
              'docs/results/cpu_prebaseline_01/run_v1/candidate_180.json','docs/results/cpu_prebaseline_01/run_v1/pre_inputs.json',
              'docs/results/cpu_prebaseline_01/run_v1/source_inventory.json'):
        sources[p]=old.sha(ROOT/p)
    old.write(out/'registration.json',dict(id='REGISTERED-BASELINE-PC-01',sources=sources,
        inputs={p:old.sha(out/p) for p in ('pre_inputs.json','pre_bins.csv','availability.csv')},
        development_ids=[c['id'] for c in old.history() if c['role']=='development'],
        evaluation_ids=[c['id'] for c in old.history() if c['role']=='confirmation'],
        contract=old.read(BUNDLE/'analysis_contract.json')))


def assets(out):
    reg=old.read(out/'registration.json')
    for p,h in reg['sources'].items():
        if old.sha(ROOT/p)!=h:raise ValueError('registered source changed '+p)
    for p,h in reg['inputs'].items():
        if old.sha(out/p)!=h:raise ValueError('registered pre input changed '+p)
    return reg


def run(output):
    out=Path(output)
    if (out/'started.json').exists():raise ValueError('analysis already consumed; no automatic restart')
    reg=assets(out);started=time.monotonic();calls=0
    old.write(out/'started.json',dict(id=reg['id'],status='PC analysis started',device_commands=0))
    try:
        data=old.prior.prior.old.table(out/'pre_bins.csv')
        for r in data:
            for k in ('lo_s','hi_s','other_rate_core_s_per_s','mean_power_W','latest_power_event_s'):r[k]=float(r[k])
            r['gap']=int(r['gap'])
        dev=[r for r in data if r['session'] in reg['development_ids']];models={};hashes={}
        for excluded in (30,180,None):
            calls+=1;key=str(excluded) if excluded else 'final'
            old.write(out/('fit_started_'+key+'.json'),dict(call=calls,max=3,excluded_gap=excluded))
            m=fit([r for r in dev if r['gap']!=excluded],reg['development_ids']);models[key]=m
            old.write(out/('candidate_'+key+'.json'),m);hashes[key]=old.sha(out/('candidate_'+key+'.json'))
        old.write(out/'fit_receipt.json',dict(status='frozen_before_future_evaluation',formal_fits=calls,
            model_hashes=hashes,registration_sha256=old.sha(out/'registration.json'),
            post_pre_or_confirmation_targets_used_in_fit=False,posthoc_family_choice=True))
        fixed,_=old.prior.prior.read_candidate(old.prior.prior.BUNDLE/'run_v1')
        original=old.read(old.prior.prior.old.analysis.j.m.MODEL);frozen=dict(idle_bias_w=0.,increments=original['energy_increment_w'])
        previous={p['id']:p for p in old.read(old.BUNDLE/'run_v1/pre_inputs.json')};cases={c['id']:c for c in old.history()}
        E=[];curves=[];summaries=[];range_rows=[]
        for public in old.read(out/'pre_inputs.json'):
            c=cases[public['id']];key=str(c['gap']) if c['role']=='development' else 'final';model=models[key]
            pm=old.read(old.BUNDLE/('run_v1/candidate_'+key+'.json'))
            last=max(35.,c['last_lane_s'] or 35.)
            windows=[('reference120',0.,120.),('future85',35.,120.),('post_lane_idle',last,120.)]
            if last>35:windows.append(('work_present',35.,last))
            def values(lo,hi):
                return dict(FROZEN=old.prior.prior.energy(public,public['actual'],frozen,lo,hi),
                    ZERO=old.prior.prior.energy(public,public['actual'],fixed,lo,hi),
                    PRIOR_CPU=old.predict(previous[c['id']],pm,fixed,lo,hi,opt_in=True),
                    **{name:predict(public,model,fixed,lo,hi,name,opt_in=True) for name in ('FULL_MEAN','FULL_CPU')})
            for phase,lo,hi in windows:
                cov=old.prior.prior.old.observed.measured_energy(c,lo,hi);obs=cov['full_energy_j']
                v=values(lo,hi)
                for name,y in v.items():
                    E.append(dict(session=c['id'],role=c['role'],gap=c['gap'],policy=c['policy'],phase=phase,method=name,
                        lo_s=lo,hi_s=hi,**cov,predicted_J=y,signed_J=y-obs if obs is not None else None,
                        absolute_J=abs(y-obs) if obs is not None else None,relative_signed=(y-obs)/obs if obs else None,
                        actual_schedule_conditional=True,future_observations_used_as_prediction_input=False))
            for t in range(1,121):
                cov=old.prior.prior.old.observed.measured_energy(c,0.,float(t))
                curves.append(dict(session=c['id'],role=c['role'],t_s=t,observed_J=cov['full_energy_j'],
                                   **{name+'_J':v for name,v in values(0.,float(t)).items()}))
            f=public['full_pre_features'];ids=model['development_ids']
            train=[p for p in old.read(out/'pre_inputs.json') if p['id'] in ids]
            fields=('pre_full_mean_W','pre_full_mean_other','persistent_other_proxy')
            reasons=[k for k in fields if not min(p['full_pre_features'][k] for p in train)<=f[k]<=max(p['full_pre_features'][k] for p in train)]
            range_rows.append(dict(session=c['id'],role=c['role'],outside_development_observed_features=';'.join(reasons),
                diagnostic_not_strict=True,excluded_from_evaluation=False))
        for role in ('development','confirmation'):
            for phase in ('reference120','future85','post_lane_idle','work_present'):
                for method in METHODS:
                    use=[r for r in E if r['role']==role and r['phase']==phase and r['method']==method and r['absolute_J'] is not None]
                    if not use:continue
                    baseline={r['session']:r for r in E if r['role']==role and r['phase']==phase and r['method']=='ZERO'}
                    summaries.append(dict(role=role,phase=phase,method=method,sessions=len(use),
                        mean_absolute_J=float(np.mean([r['absolute_J'] for r in use])),mean_signed_J=float(np.mean([r['signed_J'] for r in use])),
                        mean_absolute_relative_percent=float(np.mean([abs(r['relative_signed'])*100 for r in use])),
                        maximum_absolute_J=max(r['absolute_J'] for r in use),
                        improved_vs_zero=sum(r['absolute_J']<baseline[r['session']]['absolute_J']-1e-9 for r in use),
                        worsened_vs_zero=sum(r['absolute_J']>baseline[r['session']]['absolute_J']+1e-9 for r in use)))
        for name,rows in [('energy_errors',E),('energy_curves',curves),('summary',summaries),('feature_ranges',range_rows)]:
            old.prior.prior.old.scope_api.tail.s.csv_write(out/(name+'.csv'),rows)
        old.write(out/'receipt.json',dict(status='finite_recorded_full_pre_evaluation_complete',formal_fits=calls,
            new_structures=1,mean_only_ablation=True,AP_fits=0,sessions=12,development_sessions=6,already_seen_confirmation_sessions=6,
            elapsed_s=time.monotonic()-started,device_commands=0,new_plan=0,environment_simulations=0,
            default_changed=False,RL_changed=False,strict_support=False,experiment_ready=False,accuracy_pass=None,
            event_time_causal=True,online_CPU_feature_export_implemented=False,automatic_refit=False))
        print(old.prior.prior.terminal_json([r for r in summaries if r['phase']=='reference120']),flush=True)
    except BaseException:
        old.write(out/'FAIL.json',dict(original_stack=traceback.format_exc(),fits_started=calls,automatic_retry=False,device_commands=0));raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--action',choices=('prepare','run'),required=True);p.add_argument('--output',required=True);p.add_argument('--external-root');a=p.parse_args()
    if a.action=='prepare':prepare(a.external_root,a.output)
    else:run(a.output)


if __name__=='__main__':main()
