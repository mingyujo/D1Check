"""Reproducible PC-only completion from published inputs; never calls a device."""
import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path

from tools import d1_ap_workload_lag as lag
from tools.d1_ap_idle_response import preload_reference
from tools.d1_arrival_recorded_replay_analysis import state_key

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT/'docs/results/ap_model_completion_pc_01'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def write_csv(path, data):
    with path.open('w', encoding='utf-8', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)


def inputs():
    sources = {}
    def use(relative):
        p=ROOT/relative; sources[relative]=digest(p); return p
    old=read(use('docs/results/energy_ap_idle_response_01/low_temperature_scope_v1/inputs.json'))
    cases=[]
    for c in old['cases']:
        p=c['prediction_inputs']
        ref=preload_reference([(s['t'],s['ap']) for s in p['preload_ap']],old['parameters']['ap_cooling_rate_per_s'])
        if abs(ref['effective_idle_reference_c']-c['saved_reference_c'])>1e-9:
            raise ValueError('preload reference changed')
        cases.append(dict(id='idle_'+c['role'], original_role=c['original_data_role'],
            protocol='747_APK', saved_mae_c=c['saved_mae_c'],
            inputs=dict(initial_ap_c=p['initial_ap_c'], reference_c=c['saved_reference_c'],
                        segments=p['segments'], query_s=p['query_s'],
                        information_cutoff_s=p['prediction_information_cutoff_s']),
            observed_ap_c=c['observed_ap_c']))
    for name, folder, protocol in [
        ('cgdc_transfer','energy_ap_cgdc_transfer_01/run01/data','747_APK'),
        ('one_pulse','ap_bundle_confirmation_01/run02/confirmation_one_pulse','3d8_APK'),
        ('two_pulses','ap_bundle_confirmation_01/run02/confirmation_two_pulses','3d8_APK')]:
        base='docs/results/'+folder+'/'
        s=read(use(base+'summary.json')); states=rows(use(base+'actual_states.csv')); ap=rows(use(base+'ap_paths.csv'))
        segments=[dict(start_s=float(r['start_s']),end_s=float(r['end_s']),state=r['state']) for r in states]
        segments.append(dict(start_s=120.,end_s=s['ap_comparison_end_s'],state='idle'))
        cases.append(dict(id=name,original_role='prospective_protocol_transfer_diagnostic',protocol=protocol,
            saved_mae_c=s['ap_scores']['candidate']['mae_c'],
            inputs=dict(initial_ap_c=s['initial_ap_c'],reference_c=s['preload']['effective_idle_reference_c'],
                segments=segments,query_s=[float(r['elapsed_s']) for r in ap],
                information_cutoff_s=s['preload']['last_s']),
            observed_ap_c=[float(r['observed_ap_c']) for r in ap]))
    history=read(use('docs/results/resident_history_01/inputs.json'))
    group={c['case']:c['protocol_group'] for c in history['cases']}
    stress=[]
    for r in rows(use('docs/results/resident_history_01/readout/fixed_windows.csv')):
        if r['window']=='late_common' and r['mean_w'] and r['state_eligible']=='True':
            stress.append(dict(case=r['case'],protocol=group[r['case']],start_s=float(r['start_s']),
                end_s=float(r['end_s']),residual_w=float(r['mean_w'])-history['original_power_w']['resident_idle']))
    representative=read(use('docs/results/arrival_service_choice_01/readout/representative.json'))
    schedules={}
    for r in rows(use('docs/results/arrival_policy_screen_01/repro_bundle/occupancy_segments.csv')):
        if r['scenario']=='queue' and r['seed']=='201' and float(r['realized'])==1.5:
            schedules.setdefault(r['policy'],[]).append(dict(start_s=float(r['start_s']),end_s=float(r['end_s']),state=r['state']))
    policies={p:schedules[p] for p in ('CPU_URGENT','B2_PC','B3_SOLO_EFT_PC')}
    return dict(parameters=old['parameters'],cases=cases,power_w=history['original_power_w'],
        policy_schedules=policies,service=representative['representative_service'],idle_stress=stress,source_sha256=sources)


def score(observed,predicted):
    e=[p-y for p,y in zip(predicted,observed)]
    return dict(mae_c=sum(map(abs,e))/len(e),max_absolute_error_c=max(map(abs,e)),
        signed_mean_c=sum(e)/len(e),peak_signed_error_c=max(predicted)-max(observed))


def interpolate(ts, ys, q):
    for i in range(1,len(ts)):
        if ts[i-1]<=q<=ts[i] and ts[i]-ts[i-1]<=10:
            return ys[i-1]+(ys[i]-ys[i-1])*(q-ts[i-1])/(ts[i]-ts[i-1])
    return None


def sensitivity(data):
    costs=[]
    for p, segments in data['policy_schedules'].items():
        cursor=0.;energy=idle=0.
        for s in segments:
            if abs(s['start_s']-cursor)>1e-6 or s['end_s']<cursor:
                raise ValueError('policy state coverage')
            duration=s['end_s']-cursor; key=state_key(s['state'])
            energy+=duration*data['power_w'][key]
            if key=='resident_idle': idle+=duration
            cursor=s['end_s']
        if abs(cursor-120)>1e-6: raise ValueError('partial policy horizon')
        costs.append(dict(policy=p,diagnostic_state_w_j=energy,idle_s=idle,
            whole_window_supported_energy_j=None,strict_support=False))
    comparisons=[]
    for a,b in itertools.combinations(costs,2):
        for group in sorted({r['protocol'] for r in data['idle_stress']}):
            residuals=[r['residual_w'] for r in data['idle_stress'] if r['protocol']==group]
            interval=lag.idle_difference_interval(a['diagnostic_state_w_j'],b['diagnostic_state_w_j'],a['idle_s'],b['idle_s'],min(residuals),max(residuals))
            comparisons.append(dict(first=a['policy'],second=b['policy'],stress_protocol=group,
                observed_residual_low_w=min(residuals),observed_residual_high_w=max(residuals),
                **interval,stress_crosses_zero=interval['stress_low_j']<=0<=interval['stress_high_j'],
                policy_rank=None))
    return costs,comparisons


def analyze(data,contract,output):
    output=Path(output)
    if output.exists(): raise FileExistsError(output)
    cases,parameters=data['cases'],data['parameters']
    g=contract['tau_grid_seconds']; grid=[g['min']+i*g['step'] for i in range(round((g['max']-g['min'])/g['step'])+1)]
    training=[c for c in cases if c['id']==contract['primary_fit_session']]
    if len(training)!=1: raise ValueError('primary fit must have exactly one specified session')
    tau,profile=lag.fit(training,parameters,grid)
    scores=[]; paths=[]; directions=[]; loo=[]
    for c in cases:
        p=c['inputs']; observed=c['observed_ap_c']; queries=p['query_s']
        if queries[0]<p['information_cutoff_s'] or any(not 0<b-a<=10 for a,b in zip(queries,queries[1:])):
            raise ValueError('target precedes preload cutoff or AP gap')
        original=lag.path(c,parameters,0); candidate=lag.path(c,parameters,tau)
        if abs(score(observed,original)['mae_c']-c['saved_mae_c'])>1e-8: raise ValueError('saved candidate score mismatch')
        for name,prediction in [('existing_preload',original),('workload_lag',candidate)]:
            scores.append(dict(case=c['id'],model=name,role='posthoc_fit' if c in training else 'posthoc_held_out',
                protocol=c['protocol'],tau_s=0 if name=='existing_preload' else tau,
                first_sample_s=queries[0],last_sample_s=queries[-1],samples=len(queries),**score(observed,prediction)))
            for lo,hi in [(90,115),(120,145),(150,175)]:
                ov=[interpolate(queries,observed,q) for q in (lo,hi)]
                pv=[interpolate(queries,prediction,q) for q in (lo,hi)]
                directions.append(dict(case=c['id'],model=name,start_s=lo,end_s=hi,
                    observed_change_c=None if None in ov else ov[1]-ov[0],
                    predicted_change_c=None if None in pv else pv[1]-pv[0]))
        for t,y,o,n in zip(queries,observed,original,candidate):
            paths.append(dict(case=c['id'],t_s=t,observed_c=y,existing_c=o,candidate_c=n,
                candidate_residual_c=n-y,observed_change_c=y-p['initial_ap_c'],candidate_change_c=n-p['initial_ap_c']))
        held_tau,_=lag.fit([x for x in cases if x['id']!=c['id']],parameters,grid)
        loo.append(dict(held_out=c['id'],tau_s=held_tau,**score(observed,lag.path(c,parameters,held_tau))))
    costs,comparisons=sensitivity(data)
    output.mkdir(parents=True)
    for name,table in [('scores',scores),('paths',paths),('directions',directions),('fit_profile',profile),('leave_session_out',loo),('policy_cost_diagnostic',costs),('policy_sensitivity',comparisons),('idle_stress_observations',data['idle_stress'])]:
        write_csv(output/(name+'.csv'),table)
    summary=dict(version=lag.VERSION,primary_tau_s=tau,primary_boundary_optimum=tau in (grid[0],grid[-1]),
        primary_training_sessions=[c['id'] for c in training],previously_seen_sessions=len(cases),
        fresh_independent_validation_sessions=0,leave_session_out_tau_s=[r['tau_s'] for r in loo],
        scores=scores,sensitivity=comparisons,strict_support=False,policy_rank=None,accuracy_pass=None,experiment_ready=False,
        adopted_as_default=False,physical_delay_identified=False,device_commands=0,
        inputs_sha256=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest())
    write_json(output/'summary.json',summary)
    write_json(output/'candidate.json',dict(version=lag.VERSION,tau_s=tau,fixed_parameters=parameters,
        preload_reference='existing procedure, per-session pre-load only',initial_h=0,
        role='posthoc candidate; not independently validated',strict_support=False,default=False))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(cases),2,figsize=(12,14),layout='constrained')
    for c,ax in zip(cases,axes):
        rr=[r for r in paths if r['case']==c['id']];ts=[r['t_s'] for r in rr]
        for field,label in [('observed_c','Observed'),('existing_c','Preload fixed'),('candidate_c',f'Lag {tau:g}s posthoc')]:
            ax[0].plot(ts,[r[field] for r in rr],label=label)
        ax[0].set_title(c['id']+' / '+c['protocol']);ax[0].set_ylabel('AP (C)');ax[0].legend(fontsize=8)
        ax[1].plot(ts,[r['candidate_residual_c'] for r in rr],label='Lag - observed')
        ax[1].plot(ts,[r['existing_c']-r['observed_c'] for r in rr],label='Preload - observed')
        ax[1].axhline(0,color='black',linewidth=.5);ax[1].set_ylabel('Residual (C)');ax[1].legend(fontsize=8)
        for s in c['inputs']['segments']:
            if s['state']!='idle':
                for a in ax:a.axvspan(s['start_s'],s['end_s'],color='grey',alpha=.12)
        for a in ax:a.set_xlabel('Seconds from common-window start');a.grid(alpha=.2)
    fig.savefig(output/'ap_comparison.png',dpi=140);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4),layout='constrained')
    for i,r in enumerate(comparisons):
        ax.plot([r['stress_low_j'],r['stress_high_j']],[i,i],marker='|')
        ax.plot(r['diagnostic_difference_j'],i,'ko')
    ax.set_yticks(range(len(comparisons)),[r['first']+' - '+r['second']+' / '+('747' if 'previous' in r['stress_protocol'] else '3d8') for r in comparisons],fontsize=8)
    ax.axvline(0,color='red');ax.set_xlabel('Diagnostic J difference; finite idle stress, NOT confidence bounds')
    fig.savefig(output/'policy_sensitivity.png',dpi=150);plt.close(fig)
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    contract=read(RESULT/'contract.json');data=inputs()
    result=analyze(data,contract,args.output)
    write_json(args.output/'provenance.json',dict(source_sha256=data['source_sha256'],contract_sha256=digest(RESULT/'contract.json'),
        code_sha256={x:digest(ROOT/x) for x in ['tools/d1_ap_workload_lag.py','tools/d1_ap_model_completion.py']}))
    print(json.dumps({'tau_s':result['primary_tau_s'],'loo_tau':result['leave_session_out_tau_s'],'output':str(args.output)}))


if __name__=='__main__': main()
