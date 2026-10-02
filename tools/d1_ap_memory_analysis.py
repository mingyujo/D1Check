"""Archive-only AP memory fit and temperature/service association. No device API."""
import argparse
import bisect
import copy
import json
import math
from pathlib import Path
import numpy as np
from tools import d1_ap_model_completion as old
from tools import d1_ap_preparation_memory as model

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'docs/results/ap_preparation_memory_01'


def lines(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]


def prepare(raw_root, output):
    if output.exists():raise FileExistsError(output)
    data=old.inputs();cases=data['cases'];sources=dict(data['source_sha256'])
    original=old.read(ROOT/'docs/results/energy_ap_idle_response_01/low_temperature_scope_v1/inputs.json')
    for c,src in zip(cases[:2],original['cases']):
        c['inputs']['preload']=src['prediction_inputs']['preload_ap']
    locations=[('cgdc_transfer','energy_ap_cgdc_transfer_run_v2',0),
               ('one_pulse','energy_ap_bundle_confirm_run_v2',0),
               ('two_pulses','energy_ap_bundle_confirm_run_v2',1)]
    def used(path):
        sources[path.relative_to(raw_root).as_posix()]=old.digest(path)
        return path
    for name,run,index in locations:
        matches=list((raw_root/run).glob(f'{index:02d}_*'))
        if len(matches)!=1:raise ValueError('missing/ambiguous session '+name)
        folder=matches[0];art=folder/'artifacts'
        boundary=old.read(used(art/'common_boundary.json'));origin=boundary['start_ns']
        requests=old.read(used(art/'requests.json'));first=min(r['dispatch_ns'] for r in requests)
        progress=lines(used(art/'progress.jsonl'))
        baseline=[r['mono_ns'] for r in progress if (r.get('kind'),r.get('phase'))==('phase_start','resident_baseline')]
        if len(baseline)!=1:raise ValueError('baseline boundary')
        pre=[dict(t=(r['mono_ns']-origin)/1e9,ap=float(r['AP']),lo=(r['before_ns']-origin)/1e9,hi=(r['after_ns']-origin)/1e9)
             for r in lines(used(folder/'thermal.jsonl')) if r.get('AP') not in (None,'') and r['thermal_status']=='0'
             and baseline[0]<=r['before_ns']<=r['after_ns']<first]
        c=next(c for c in cases if c['id']==name);c['inputs']['preload']=pre
        checked=old.preload_reference([(r['t'],r['ap']) for r in pre],data['parameters']['ap_cooling_rate_per_s'])
        if abs(checked['effective_idle_reference_c']-c['inputs']['reference_c'])>1e-9:
            raise ValueError('archived pre-load reproduction differs')
    service=[];coverage=[]
    for index in range(4):
        folder=next((raw_root/'energy_ap_state_run_v5').glob(f'{index:02d}_*'))
        v=old.read(used(folder/'validated.json'))
        events=lines(used(folder/'artifacts/progress.jsonl'))
        requests=[r for r in events if r.get('phase')=='load' and r.get('kind')=='lane_available']
        if len({r['id'] for r in requests})!=len(requests) or len(requests)!=v['work_calls']:
            raise ValueError('work request denominator')
        thermal=lines(used(folder/'thermal.jsonl'))
        thermal=sorted([r for r in thermal if r.get('AP') not in (None,'')],key=lambda r:r['after_ns'])
        ends=[r['after_ns'] for r in thermal];origin=v['common_start_ns'];matched=0
        for r in requests:
            start,end=r['invocation_start_ns'],r['invocation_end_ns']
            if r['terminal_status']!='succeeded' or end<=start:raise ValueError('request boundary/status')
            j=bisect.bisect_right(ends,start)-1
            sample=thermal[j] if j>=0 and start-ends[j]<=10_000_000_000 else None
            overlap=sum(max(0,min(end,q['invocation_end_ns'])-max(start,q['invocation_start_ns']))
                        for q in requests if q['id']!=r['id'])/(end-start)
            if overlap>1+1e-6:raise ValueError('unsupported >2 inference overlap')
            row=dict(session=index,role=v['phase'],condition=v['condition'],block=r['block'],key=r['key'],
                elapsed_s=(start-origin)/1e9,inference_ms=(end-start)/1e6,
                dispatch_to_lane_ms=(r['lane_available_ns']-r['dispatch_ns'])/1e6,
                overlap_fraction=overlap,ap_before_c=float(sample['AP']) if sample else None,
                sample_age_s=(start-sample['after_ns'])/1e9 if sample else None,
                thermal_status=sample['thermal_status'] if sample else None)
            matched+=sample is not None;service.append(row)
        coverage.append(dict(session=index,role=v['phase'],condition=v['condition'],planned_recorded=len(requests),matched_ap=matched,missing_ap=len(requests)-matched))
    out=dict(version=model.VERSION,parameters=data['parameters'],cases=cases,
             service_requests=service,service_coverage=coverage,source_sha256=sources,
             experiment_ready=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
    return out


def service_associations(records):
    groups={}
    for r in records:
        if r['ap_before_c'] is None:continue
        key=(r['session'],r['block'],r['key'],r['overlap_fraction']>0)
        groups.setdefault(key,[]).append(r)
    result=[]
    for key,rr in sorted(groups.items()):
        ap=np.array([r['ap_before_c'] for r in rr]);y=np.array([r['inference_ms'] for r in rr]);elapsed=np.array([r['elapsed_s'] for r in rr])
        def corr(a,b):
            return float(np.corrcoef(a,b)[0,1]) if len(a)>2 and np.std(a)>1e-12 and np.std(b)>1e-12 else None
        overlap=np.array([r['overlap_fraction'] for r in rr]);cols=[ap-ap.mean(),elapsed-elapsed.mean()]
        if np.std(overlap)>1e-12:cols.append(overlap-overlap.mean())
        x=np.array(cols).T;norm=np.linalg.norm(x,axis=0);adjusted=None;cond=None
        if min(norm)>1e-12 and len(rr)>len(cols)+1:
            scaled=x/norm;sv=np.linalg.svd(scaled,compute_uv=False)
            if sv[-1]>sv[0]*1e-12:
                adjusted=float(np.linalg.lstsq(scaled,y-y.mean(),rcond=None)[0][0]/norm[0]);cond=float(sv[0]/sv[-1])
        result.append(dict(session=key[0],block=key[1],key=key[2],inference_overlap=key[3],requests=len(rr),
            ap_min_c=float(min(ap)),ap_max_c=float(max(ap)),inference_median_ms=float(np.median(y)),
            inference_min_ms=float(min(y)),inference_max_ms=float(max(y)),
            ap_inference_correlation=corr(ap,y),ap_elapsed_correlation=corr(ap,elapsed),
            adjusted_association_ms_per_c=adjusted,scaled_condition=cond,
            thermal_statuses='|'.join(sorted({str(r['thermal_status']) for r in rr})),
            fitted_throttle_coefficient=None))
    return result


def analyze(data, contract, output):
    if output.exists():raise FileExistsError(output)
    if contract['id']!=model.VERSION or contract['global_fit']['primary_session']!='idle_development':
        raise ValueError('wrong candidate contract')
    cases=data['cases'];parameters=data['parameters']
    if [c['id'] for c in cases]!=['idle_development',*contract['evaluation']]:raise ValueError('case roles/order')
    for c in cases:
        ts=c['inputs']['query_s'];values=c['observed_ap_c']
        if (not ts or len(ts)!=len(values) or any(not math.isfinite(v) for v in values) or
            any(not 0<b-a<=10 for a,b in zip(ts,ts[1:]))):
            raise ValueError('missing target or AP time gap')
    fit,profile=model.fit(cases[0],parameters,contract['global_fit']['tau_seconds'])
    scores=[];paths=[];initial=[];directions=[];sensitivity=[];decomposition=[];phase_scores=[]
    for c in cases:
        predicted,init=model.predict(c,parameters,fit['tau_s'],fit['gamma'])
        initial.append(dict(case=c['id'],**init))
        stress=model.preload_sensitivity(c,parameters,fit['tau_s'],fit['gamma']);sensitivity.append(dict(case=c['id'],**{k:v for k,v in stress.items() if k!='pointwise_change_bounds_c'}))
        baseline=old.lag.path(c,parameters,0);previous=old.lag.path(c,parameters,4)
        if abs(old.score(c['observed_ap_c'],baseline)['mae_c']-c['saved_mae_c'])>1e-8:
            raise ValueError('old model reproduction')
        ts=c['inputs']['query_s'];y=c['observed_ap_c']
        last=max(s['end_s'] for s in c['inputs']['segments'] if s['state']!='idle')
        parts=model.decompose(c,parameters,fit['tau_s'],fit['gamma'],baseline)
        for phase,indices in [('work_span',[i for i,t in enumerate(ts) if t<=last]),
                              ('post_work_idle',[i for i,t in enumerate(ts) if t>last])]:
            if not indices:continue
            for name,pred in [('existing_preload',baseline),('preparation_memory',predicted)]:
                phase_scores.append(dict(case=c['id'],phase=phase,model=name,samples=len(indices),
                    **old.score([y[i] for i in indices],[pred[i] for i in indices])))
        for t,part in zip(ts,parts):
            if abs(sum(part[k] for k in ('anchor_change_c','reference_change_c','preparation_state_change_c','work_memory_change_c'))-part['total_change_c'])>1e-9:
                raise ValueError('AP decomposition conservation')
            decomposition.append(dict(case=c['id'],time_s=t,**part))
        for name,pred in [('existing_preload',baseline),('rejected_lag4',previous),('preparation_memory',predicted)]:
            scores.append(dict(case=c['id'],model=name,role='posthoc_development' if c['id']=='idle_development' else 'posthoc_fit_excluded',
                protocol=c['protocol'],first_sample_s=ts[0],last_sample_s=ts[-1],samples=len(ts),**old.score(y,pred)))
            for lo,hi in contract['directions_windows_seconds']:
                ov=[old.interpolate(ts,y,t) for t in (lo,hi)];pv=[old.interpolate(ts,pred,t) for t in (lo,hi)]
                directions.append(dict(case=c['id'],model=name,start_s=lo,end_s=hi,
                    observed_change_c=None if None in ov else ov[1]-ov[0],
                    predicted_change_c=None if None in pv else pv[1]-pv[0]))
        for i,t in enumerate(ts):
            paths.append(dict(case=c['id'],time_s=t,phase='work_span' if t<=last else 'post_work_idle',observed_c=y[i],
                existing_c=baseline[i],previous_lag_c=previous[i],memory_c=predicted[i],memory_residual_c=predicted[i]-y[i],
                observed_change_from_initial_c=y[i]-c['inputs']['initial_ap_c'],
                memory_change_from_initial_c=predicted[i]-c['inputs']['initial_ap_c'],
                preload_rounding_sensitivity_c=stress['pointwise_change_bounds_c'][i]))
    association=service_associations(data['service_requests'])
    near=[r for r in profile if r['rmse_c']<=fit['rmse_c']+.05]
    summary=dict(version=model.VERSION,fit=fit,primary_fit_sessions=1,posthoc_fit_excluded_sessions=4,
        fresh_independent_confirmation_sessions=0,boundary_optimum=fit['tau_s'] in (profile[0]['tau_s'],profile[-1]['tau_s']),
        rmse_plus_005_sensitivity_tau_s=[r['tau_s'] for r in near],
        profile_sensitivity_is_confidence=False,scores=scores,initial_states=initial,
        preload_sensitivity=sensitivity,service_coverage=data['service_coverage'],
        adjusted_association_positive=sum(r['adjusted_association_ms_per_c'] is not None and r['adjusted_association_ms_per_c']>0 for r in association),
        adjusted_association_negative=sum(r['adjusted_association_ms_per_c'] is not None and r['adjusted_association_ms_per_c']<0 for r in association),
        throttle_model_identified=False,physical_heat_state_identified=False,
        accuracy_pass=None,adopted_as_default=False,strict_support=False,experiment_ready=False,device_commands=0)
    output.mkdir(parents=True)
    for name,table in [('scores',scores),('paths',paths),('directions',directions),('fit_profile',profile),
                       ('initial_states',initial),('preload_sensitivity',sensitivity),('temperature_service',association),
                       ('decomposition',decomposition),('phase_scores',phase_scores)]:
        old.write_csv(output/(name+'.csv'),table)
    old.write_json(output/'summary.json',summary)
    old.write_json(output/'candidate.json',dict(version=model.VERSION,tau_s=fit['tau_s'],gamma=fit['gamma'],
        fixed_parameters=parameters,role='posthoc_diagnostic_only',initialization='pre-load AP only; E and H not physical measurements',
        strict_support=False,default=False,adoption='not_automatic'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(5,2,figsize=(12,15),layout='constrained')
    for c,ax in zip(cases,axes):
        pp=[r for r in paths if r['case']==c['id']];ts=[r['time_s'] for r in pp]
        for field,label in [('observed_c','Observed'),('existing_c','Existing preload'),('memory_c','Preparation memory')]:
            ax[0].plot(ts,[r[field] for r in pp],label=label)
        ax[1].plot(ts,[r['memory_residual_c'] for r in pp],label='Memory - observed')
        ax[1].plot(ts,[r['existing_c']-r['observed_c'] for r in pp],label='Existing - observed')
        ax[1].axhline(0,color='black',lw=.5);ax[0].set_title(c['id']+' / '+c['protocol'])
        for a in ax:
            a.set_xlabel('Seconds from common start');a.set_ylabel('AP / residual (C)');a.grid(alpha=.2);a.legend(fontsize=8)
            for s in c['inputs']['segments']:
                if s['state']!='idle':a.axvspan(s['start_s'],s['end_s'],alpha=.12,color='grey')
    fig.savefig(output/'comparison.png',dpi=135);plt.close(fig)
    return summary


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--prepare-inputs',type=Path);cli.add_argument('--raw-root',type=Path)
    cli.add_argument('--inputs',type=Path,default=BUNDLE/'inputs.json');cli.add_argument('--output',type=Path)
    args=cli.parse_args()
    if args.prepare_inputs:
        if not args.raw_root:cli.error('--raw-root required for archive extraction')
        data=prepare(args.raw_root,args.prepare_inputs)
        print(json.dumps(dict(cases=len(data['cases']),requests=len(data['service_requests']),device_commands=0)))
    else:
        if not args.output:cli.error('--output required')
        result=analyze(old.read(args.inputs),old.read(BUNDLE/'contract.json'),args.output)
        old.write_json(args.output/'provenance.json',dict(inputs_sha256=old.digest(args.inputs),
            contract_sha256=old.digest(BUNDLE/'contract.json'),code_sha256={p:old.digest(ROOT/p) for p in
            ('tools/d1_ap_memory_analysis.py','tools/d1_ap_preparation_memory.py')}))
        print(json.dumps(dict(fit=result['fit'],positive=result['adjusted_association_positive'],negative=result['adjusted_association_negative'])))


if __name__=='__main__':main()
