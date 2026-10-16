"""Recover recorded pre-load information, test one fixed initialization, PC only."""
import argparse
import copy
import json
import re
from pathlib import Path
import numpy as np
from tools import d1_session_contrast_cost as current

ROOT=current.ROOT
BUNDLE=ROOT/'docs/results/preboundary_evidence_01'


def write(path,value):current.prior.write(path,value)


def extract(external,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    all_cases=current.cases();cases={c['id']:c for c in all_cases if c.get('block')=='history'}
    expected=current.prior.old.analysis.j.m.read(ROOT/'docs/results/history_model_refinement_01/source_inventory.json')['raw_source_hashes']
    selected={}
    # Locate reused terminal records by frozen content hash, not by current folder age.
    for run in sorted(Path(external).glob('energy_ap_history_recovery_run_v*'),reverse=True):
        for path in sorted(run.rglob('thermal.jsonl')):
            folder=path.parent
            manifest=folder/'input_manifest.json'
            if not manifest.exists():continue
            m=json.loads(manifest.read_text(encoding='utf8'));identity=m.get('phase')
            if identity not in cases or identity in selected:continue
            if current.prior.old.scope_api.sha(path)==expected[identity+'/thermal.jsonl']:selected[identity]=folder
    if set(selected)!=set(cases):raise ValueError('frozen raw records unavailable: '+str(set(cases)-set(selected)))
    outputs=[];inventory={};audit=[]
    for identity,c in cases.items():
        folder=selected[identity];paths={'thermal.jsonl':folder/'thermal.jsonl',
            'history_boundary.json':folder/'artifacts/history_boundary.json',
            'conditioning_requests.json':folder/'artifacts/conditioning_requests.json'}
        for name,path in paths.items():
            actual=current.prior.old.scope_api.sha(path)
            if actual!=expected[identity+'/'+name]:raise ValueError('raw source hash mismatch')
            inventory[identity+'/'+name]=actual
        h=json.loads(paths['history_boundary.json'].read_text(encoding='utf8'))
        rows=json.loads(paths['conditioning_requests.json'].read_text(encoding='utf8'))
        if len(rows)!=96 or max(r['lane_available_ns'] for r in rows)>h['recovery_start_ns']:
            raise ValueError('registered recovery starts before conditioning lane release')
        raw=[json.loads(line) for line in paths['thermal.jsonl'].read_text(encoding='utf8').splitlines()]
        origin=h['target_start_ns'];start=h['recovery_start_ns'];unique={};HALmatches=cached_different=0
        for r in raw:
            if r.get('AP') in (None,''):continue
            text=r['raw'];current_section=text.split('Current temperatures from HAL:',1)[1].split('Current cooling devices from HAL:',1)[0]
            value=re.search(r'mValue=([-+0-9.eE]+),[^\n]*mName=AP,',current_section)
            if not value or float(value.group(1))!=float(r['AP']):raise ValueError('HAL_AP source differs from stored AP')
            HALmatches+=1
            cached=text.split('Cached temperatures:',1)[1].split('HAL Ready:',1)[0]
            v=re.search(r'mValue=([-+0-9.eE]+),[^\n]*mName=AP,',cached)
            cached_different+=int(v is not None and float(v.group(1))!=float(r['AP']))
            if start<=r['before_ns']<=r['mono_ns']<=r['after_ns']<origin+35e9:
                p=dict(t=(r['mono_ns']-origin)/1e9,lo=(r['before_ns']-origin)/1e9,hi=(r['after_ns']-origin)/1e9,ap=float(r['AP']))
                if p['t'] in unique and unique[p['t']]!=p:raise ValueError('duplicate AP clock conflict')
                unique[p['t']]=p
        pre=[unique[t] for t in sorted(unique)]
        if not pre or pre[-1]!=c['pre'][-1] or any(b['t']-a['t']>10 for a,b in zip(pre,pre[1:])):
            raise ValueError('changed anchor or incomplete registered idle coverage')
        outputs.append(dict(id=identity,role=c['role'],gap=c['gap'],policy=c['policy'],expanded_pre=pre,
            definition='all valid AP in registered post-conditioning resident recovery through pre-target cutoff35;no outcome-selected window',
            conditioning_calls=96,last_conditioning_lane_s=(max(r['lane_available_ns'] for r in rows)-origin)/1e9,
            recovery_start_s=(start-origin)/1e9,forecast_issue_s=35))
        audit.append(dict(session=identity,role=c['role'],gap=c['gap'],old_pre_samples=len(c['pre']),new_pre_samples=len(pre),
            old_pre_span_s=c['pre'][-1]['t']-c['pre'][0]['t'],new_pre_span_s=pre[-1]['t']-pre[0]['t'],
            same_last_initial_AP_and_time=True,all_pre_returned_before_issue=True,
            HAL_rows_verified=HALmatches,cached_AP_different_rows=cached_different,
            cached_AP_never_used=True,registered_idle_and_lane_release_checked=True))
    write(out/'expanded_pre.json',outputs)
    write(out/'source_inventory.json',dict(raw_files=inventory,source_locations={k:str(v.relative_to(Path(external))) for k,v in selected.items()},
        raw_unchanged=True,device_commands=0))
    current.prior.old.scope_api.tail.s.csv_write(out/'availability.csv',audit)
    return audit


def compare(c,pre,original,model):
    public=dict(pre=pre,actual=c['actual'],q=c['q'])
    prediction,parts=current.prior.old.scope_api.tail.predict(public,original,model)
    return prediction,parts


def evaluate(output):
    out=Path(output)
    if (out/'receipt.json').exists():raise ValueError('evaluation already completed')
    reg=current.prior.old.analysis.j.m.read(BUNDLE/'registration.json')
    for p,h in reg['sources'].items():
        if current.prior.old.scope_api.sha(ROOT/p)!=h:raise ValueError('registered source changed '+p)
    for name,h in reg['inputs'].items():
        if current.prior.old.scope_api.sha(out/name)!=h:raise ValueError('expanded pre input changed')
    original=current.prior.old.analysis.j.m.read(current.prior.old.analysis.j.m.MODEL)
    model=current.prior.old.scope_api.read_assets()[2]
    inputs=current.prior.old.analysis.j.m.read(out/'expanded_pre.json');lookup={c['id']:c for c in current.cases()}
    metrics=[];paths=[];initial=[]
    for row in inputs:
        c=lookup[row['id']]
        for name,pre in [('existing_short_pre',c['pre']),('registered_idle_pre',row['expanded_pre'])]:
            y,parts=compare(c,pre,original,model)
            init=current.prior.old.analysis.j.m.memory.initialize(pre,original['ap']['beta'],30.)
            score=current.prior.old.observed.phase_score(c,y,35.,c['actual'][-1]['end_s'])
            metrics.append(dict(session=c['id'],role=c['role'],gap=c['gap'],policy=c['policy'],variant=name,
                **score,initial_reference_c=init['reference_c'],initial_H_last=init['h_last_c_per_s'],pre_rmse_c=init['preload_rmse_c'],
                pre_samples=len(pre),pre_duration_s=init['duration_s'],future_observations_used_as_prediction_inputs=False))
            initial.append(dict(session=c['id'],variant=name,**init))
            paths.extend(dict(session=c['id'],role=c['role'],gap=c['gap'],variant=name,t_s=t,observed_c=obs,predicted_c=pred,residual_c=pred-obs) for t,obs,pred in zip(c['q'],c['ap'],y))
    for name,rows in [('AP_metrics',metrics),('AP_paths',paths),('initial_states',initial)]:
        current.prior.old.scope_api.tail.s.csv_write(out/(name+'.csv'),rows)
    summaries=[]
    for role in ('development','confirmation'):
        for gap in (30,180):
            for variant in ('existing_short_pre','registered_idle_pre'):
                use=[r for r in metrics if r['role']==role and r['gap']==gap and r['variant']==variant]
                summaries.append(dict(role=role,gap=gap,variant=variant,sessions=len(use),AP_mean_MAE_c=float(np.mean([r['mae_c'] for r in use])),
                    AP_mean_max_c=float(np.mean([r['max_absolute_error_c'] for r in use])),AP_peak_mean_abs_error_c=float(np.mean([abs(r['peak_signed_error_c']) for r in use]))))
    current.prior.old.scope_api.tail.s.csv_write(out/'summary.csv',summaries)
    # Attribution only: unchanged p4 cannot alter these recorded post-lane idle discrepancies.
    attribution=[]
    for r in current.prior.old.table(current.prior.BUNDLE/'run_v1/energy_errors.csv'):
        if r['phase'] not in ('post_lane_idle_covered_prefix','recovery_covered_prefix'):continue
        c=lookup[r['session']];lo,hi=float(r['lo_s']),float(r['hi_s'])
        if np.any(current.prior.old.analysis.j.m.base.exposure(c['actual'],lo,hi)>1e-9):continue
        obs=float(r['observed_j']) if r['observed_j'] else None
        attribution.append(dict(session=c['id'],phase=r['phase'],lo_s=lo,hi_s=hi,duration_s=hi-lo,
            pre50_W=c['pre_w'],observed_idle_mean_W=obs/(hi-lo) if obs is not None else None,
            signed_idle_J=c['pre_w']*(hi-lo)-obs if obs is not None else None,
            state_coefficient_contribution_J=0.,meaning='model-invariant idle discrepancy;not irreducible whole-window floor or causal hardware attribution'))
    current.prior.old.scope_api.tail.s.csv_write(out/'idle_energy_attribution.csv',attribution)
    write(out/'receipt.json',dict(status='one_fixed_initialization_and_error_attribution_evaluated',history_sessions=12,
        development_sessions=6,already_seen_confirmation_sessions=6,global_coefficient_fits=0,
        original_and_expanded_local_initializations=24,AP_path_replays=24,energy_coefficients_changed=False,
        default_changed=False,rl_changed=False,strict_support=False,experiment_ready=False,device_commands=0))
    return summaries


def main():
    p=argparse.ArgumentParser();p.add_argument('--action',choices=('extract','evaluate'),required=True);p.add_argument('--output',required=True);p.add_argument('--external-root');a=p.parse_args()
    value=extract(a.external_root,a.output) if a.action=='extract' else evaluate(a.output)
    print(current.prior.terminal_json(value))


if __name__=='__main__':main()
