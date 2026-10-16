"""Two registered posthoc candidates, offline only; defaults/RL are never changed."""
import argparse
import copy
import csv
import gzip
import json
import math
import time
from pathlib import Path
import numpy as np
from tools import d1_model_refinement as m
from tools import d1_ap_preparation_memory as memory
from tools.d1_arrival_recorded_replay_analysis import state_key

BUNDLE = m.ROOT/'docs/results/history_model_refinement_01'
FIXED_G = .16229091917947994


def inputs(c):
    # The predictor receives neither post-load temperatures nor electrical targets.
    return dict(preload=copy.deepcopy(c['pre']), query_s=list(c['q']), segments=copy.deepcopy(c['actual']))


def features(c):
    # Both windows end before the 35s first allowed work boundary.
    return dict(pre_w=float(c['pre_w']), trend_w=m.integral(c,10,30)/20-m.integral(c,-20,0)/20)


def initialization(pre, beta, strength):
    base = memory.initialize(pre,beta,30.)
    if not math.isfinite(strength) or strength<0:
        raise ValueError('invalid ridge strength')
    if strength==0:
        return base
    t0,y0=pre[0]['t'],pre[0]['ap']
    design=np.array([[1-math.exp(-beta*(p['t']-t0)),memory.convolution(beta,30.,p['t']-t0)] for p in pre])
    target=np.array([p['ap']-y0*math.exp(-beta*(p['t']-t0)) for p in pre])
    norms=np.linalg.norm(design,axis=0);scaled=design/norms
    # Penalty is dimensionless after column normalization, on H only.
    fitted=np.linalg.lstsq(np.vstack((scaled,[0.,math.sqrt(strength)])),np.r_[target,0.],rcond=None)[0]/norms
    ref,h0=map(float,fitted)
    return dict(base,reference_c=ref,h_first_c_per_s=h0,h_last_c_per_s=h0*math.exp(-(pre[-1]['t']-t0)/30),
                ridge_lambda=strength,preload_rmse_c=float(np.sqrt(np.mean((design@fitted-target)**2))))


def ap_prediction(public,frozen,strength=0.,fixed_g=0.):
    case=dict(inputs=public)
    # Existing boundary/support/coverage validation, including the C0 idle path.
    m.thermal.basis(case,frozen['ap']['parameters'],frozen['ap']['beta'])
    ap=frozen['ap'];beta=ap['beta'];slopes=ap['parameters']['ap_slope_at_30_c_per_s']
    init=initialization(public['preload'],beta,strength)
    zero={k:slopes['resident_idle'] for k in slopes}
    a=np.array(memory._propagate(public['segments'],public['query_s'],zero,beta,30.,0.,init))
    b=np.array(memory._propagate(public['segments'],public['query_s'],slopes,beta,30.,0.,init))
    if fixed_g:
        d=np.array(memory._propagate(public['segments'],public['query_s'],slopes,beta,30.,1.,init))
    else:
        d=b
    prediction=a+ap['k']*(b-a)+fixed_g*(d-b)
    if not np.isfinite(prediction).all():raise ValueError('nonfinite AP prediction')
    return prediction.tolist(),init


def transient_basis(d,t):
    return d*30*(-math.expm1(-max(0.,float(t)-35)/30))


def load_basis(seg,frozen,t):
    return float(m.base.exposure(seg,0,t)@np.array([frozen['energy_increment_w'][k] for k in m.base.STATES]))


def energy_prediction(public,seg,frozen,coef,t):
    if not 0<=t<=120:raise ValueError('energy window')
    alpha,gain=coef['alpha'],coef['gain']
    if not all(math.isfinite(x) for x in (alpha,gain,public['pre_w'],public['trend_w'])) or gain<0:
        raise ValueError('invalid energy coefficient')
    if min(public['pre_w'],public['pre_w']+alpha*public['trend_w'])<=0:
        raise ValueError('nonpositive idle power; no clipping')
    return public['pre_w']*t+alpha*transient_basis(public['trend_w'],t)+gain*load_basis(seg,frozen,t)


def fit_energy(cases,frozen):
    if not cases or any(c['role']!='development' or c['block']!='history' for c in cases):
        raise ValueError('designated history development only')
    controls=[c for c in cases if c['policy']=='C0']
    loaded=[c for c in cases if c['policy']!='C0']
    if not controls or not loaded:raise ValueError('C0 and load required')
    def solve(use,kind,alpha=0.):
        x=[];y=[]
        for c in use:
            f=features(c);weight=1/math.sqrt(17*len(use))
            for a in range(35,120,5):
                b=a+5;obs=m.integral(c,a,b)
                if kind=='idle':
                    basis=transient_basis(f['trend_w'],b)-transient_basis(f['trend_w'],a)
                    target=obs-f['pre_w']*5
                else:
                    basis=load_basis(c['actual'],frozen,b)-load_basis(c['actual'],frozen,a)
                    target=obs-f['pre_w']*5-alpha*(transient_basis(f['trend_w'],b)-transient_basis(f['trend_w'],a))
                x.append(basis*weight);y.append(target*weight)
        x=np.array(x);y=np.array(y);information=float(x@x)
        if information<=1e-12:raise ValueError(kind+' coefficient unidentified')
        estimate=float(x@y/information)
        return (max(0.,estimate) if kind=='load' else estimate),information,estimate
    alpha,ai,au=solve(controls,'idle')
    gain,gi,gu=solve(loaded,'load',alpha)
    coef=dict(id='CONTROL_IDLE_LOAD_V1',alpha=alpha,gain=gain,idle_information=ai,load_information=gi,
              unconstrained_gain=gu,controls=[c['id'] for c in controls],load_fit=[c['id'] for c in loaded],
              practical_identification='not certified by finite numerical information; two C0 sessions only')
    for c in cases:energy_prediction(features(c),c['actual'],frozen,coef,120)
    return coef


def direction(c,pred):
    result={}
    for name,left,right in [('load',35,c['last_lane_s']),('cooling',c['last_lane_s'],c['q'][-1])]:
        indices=[i for i,t in enumerate(c['q']) if left<=t<=right]
        if len(indices)<2:
            result.update({name+'_opposite':None,name+'_observed_change_c':None,name+'_predicted_change_c':None})
            continue
        a,b=indices[0],indices[-1];change=c['ap'][b]-c['ap'][a];predchange=pred[b]-pred[a]
        result.update({name+'_opposite':bool(abs(change)>.100000001 and change*predchange < -1e-12),
                       name+'_observed_change_c':change,name+'_predicted_change_c':predchange})
    return result


def evaluate(c,frozen,energy_coef=None,strength=0.,fixed_g=0.):
    pred,init=ap_prediction(inputs(c),frozen,strength,fixed_g)
    energy_coef=energy_coef or dict(alpha=0.,gain=1.)
    public=features(c);ef=lambda t:energy_prediction(public,c['actual'],frozen,energy_coef,t)
    observed=m.integral(c,0,120);predj=ef(120);signed=predj-observed
    result=dict(observed_j=observed,predicted_j=predj,signed_j=signed,abs_j=abs(signed),relative_j=signed/observed,
                **m.base.common.score(c['ap'],pred),**direction(c,pred))
    result['delta_mae_c']=float(np.mean(np.abs((np.array(pred)-pred[0])-(np.array(c['ap'])-c['ap'][0]))))
    errors=[];windows=[]
    for a in range(0,120,5):
        err=ef(a+5)-ef(a)-m.integral(c,a,a+5);errors.append(err)
        used=sorted({s['state'] for s in c['actual'] if min(a+5,s['end_s'])>max(a,s['start_s'])})
        windows.append(dict(start_s=a,end_s=a+5,states='|'.join(used),mixed=len(used)>1,signed_j=err))
    result.update(positive_bins_j=sum(max(0,x) for x in errors),negative_bins_j=sum(min(0,x) for x in errors))
    for label,a,b in [('pre',0,35),('load',35,c['last_lane_s']),('post',c['last_lane_s'],120)]:
        result[label+'_signed_j']=ef(b)-ef(a)-m.integral(c,a,b)
        ix=[i for i,t in enumerate(c['q']) if a<=t<=b]
        result[label+'_ap_mae_c']=float(np.mean([abs(pred[i]-c['ap'][i]) for i in ix])) if ix else None
    if abs(sum(result[k+'_signed_j'] for k in ('pre','load','post'))-signed)>1e-8:
        raise ValueError('energy partition mismatch')
    return result,pred,init,windows


def freeze(development,frozen,contract):
    expected={(gap,policy) for gap in (30,180) for policy in ('C0','CPU_URGENT_ONLINE_V1','B2_PARALLEL_ONLINE_V1')}
    if (len(development)!=6 or len({c['id'] for c in development})!=6 or
        {(c['gap'],c['policy']) for c in development}!=expected or
        any(c['role']!='development' or c['block']!='history' for c in development)):
        raise ValueError('six history development only')
    rows=[];energy_fit=None;energy_folds=[]
    try:
        energy_fit=fit_energy(development,frozen)
        for gap in (30,180):
            train=[c for c in development if c['gap']!=gap]
            local=fit_energy(train,frozen);selected=[c for c in development if c['gap']==gap]
            baseline=[evaluate(c,frozen)[0]['abs_j'] for c in selected]
            new=[evaluate(c,frozen,local)[0]['abs_j'] for c in selected]
            energy_folds.append(dict(held_out_gap=gap,coefficient=local,baseline_mae_j=float(np.mean(baseline)),candidate_mae_j=float(np.mean(new))))
    except ValueError as exc:
        energy_failure=str(exc)
    else:
        energy_failure=None
    energy_selected=energy_failure is None and all(x['candidate_mae_j']<=x['baseline_mae_j']+1e-12 for x in energy_folds) and any(x['candidate_mae_j']<x['baseline_mae_j']-1e-12 for x in energy_folds)
    for strength in contract['ap_candidate']['lambdas']:
        for c in development:
            score,_,_,_=evaluate(c,frozen,strength=strength)
            rows.append(dict(id=c['id'],gap=c['gap'],ridge_lambda=strength,mae_c=score['mae_c'],max_absolute_error_c=score['max_absolute_error_c'],cooling_opposite=score['cooling_opposite'],load_opposite=score['load_opposite']))
    eligible=[]
    for strength in contract['ap_candidate']['lambdas']:
        passed=True
        for gap in (30,180):
            group=[x for x in rows if x['ridge_lambda']==strength and x['gap']==gap]
            baseline=[x for x in rows if x['ridge_lambda']==0 and x['gap']==gap]
            passed=passed and np.mean([x['mae_c'] for x in group])<=np.mean([x['mae_c'] for x in baseline])+1e-12
            for key in ('load_opposite','cooling_opposite'):
                passed=passed and sum(x[key] is True for x in group)<=sum(x[key] is True for x in baseline)
        if passed:eligible.append(strength)
    selected=min(eligible,key=lambda strength:(np.mean([x['mae_c'] for x in rows if x['ridge_lambda']==strength]),strength))
    nonzero=[s for s in contract['ap_candidate']['lambdas'] if s>0]
    diagnostic=selected if selected>0 else min(nonzero,key=lambda s:(np.mean([x['mae_c'] for x in rows if x['ridge_lambda']==s]),s))
    return dict(energy_candidate=energy_fit,energy_failure=energy_failure,energy_folds=energy_folds,energy_selected=bool(energy_selected),
                ap_selected_lambda=float(selected),ap_diagnostic_lambda=float(diagnostic),ap_selection_rows=rows,development_ids=[c['id'] for c in development],
                confirmation_used_for_fit=False,posthoc=True,accuracy_pass=None,strict_support=False,default=False,experiment_ready=False)


def paired_rows(rows,cases):
    result=[]
    for pair in range(4):
        ids={c['policy']:c['id'] for c in cases if c['block']=='sustained' and c['index']//2==pair}
        for name in dict.fromkeys(x['candidate'] for x in rows):
            lookup={x['id']:x for x in rows if x['candidate']==name and x['status']!='unavailable'}
            cpu=lookup.get(ids['CPU_URGENT_ONLINE_V1']);par=lookup.get(ids['B2_PARALLEL_ONLINE_V1'])
            if cpu and par:
                result.append(dict(pair=pair,candidate=name,observed_par_minus_cpu_j=par['observed_j']-cpu['observed_j'],
                                   predicted_par_minus_cpu_j=par['predicted_j']-cpu['predicted_j'],
                                   signed_difference_error_j=par['signed_j']-cpu['signed_j'],
                                   peak_difference_error_c=par['peak_signed_error_c']-cpu['peak_signed_error_c'],
                                   causal_policy_effect=False))
    return result


def run(output):
    start=time.monotonic();output=Path(output)
    if output.exists():raise FileExistsError('new output required')
    contract=m.read(BUNDLE/'contract.json');cases=m.read(BUNDLE/'inputs.json.gz');frozen=m.read(m.MODEL)
    if m.sha(m.MODEL)!=m.MODEL_SHA:raise ValueError('model identity')
    if len(cases)!=20 or len({c['id'] for c in cases})!=20:raise ValueError('input denominator')
    output.mkdir(parents=True)
    result=freeze([c for c in cases if c['role']=='development'],frozen,contract)
    # Durable fit/selection record precedes any evaluation target scoring.
    m.write(output/'candidate_freeze.json',dict(result,input_sha256=m.sha(BUNDLE/'inputs.json.gz'),contract_sha256=m.sha(BUNDLE/'contract.json')))
    frozen_sha=m.sha(output/'candidate_freeze.json')
    m.write(output/'freeze_receipt.json',dict(sha256=frozen_sha,evaluation_scored=False))
    rows=[];paths=[];windows=[];initials=[];unavailable=[]
    for c in cases:
        if time.monotonic()-start>contract['budget']['active_seconds']-contract['budget']['reserve_seconds']:
            m.write(output/'partial.json',dict(reason='time_budget',finished_rows=len(rows)));break
        models=[('FROZEN',None,0.,0.),('AP_RIDGE',None,result['ap_diagnostic_lambda'],0.),('FIXED_G_SAME_INPUT',None,0.,FIXED_G)]
        if result['energy_candidate'] is not None:
            models.extend([('E_CONTROL',result['energy_candidate'],0.,0.),('COMBINED_DIAGNOSTIC',result['energy_candidate'],result['ap_diagnostic_lambda'],0.)])
        for name,coef,strength,g in models:
            common=dict(id=c['id'],role=c['role'],block=c['block'],gap=c.get('gap'),policy=c['policy'],mode='A_conditional',candidate=name)
            try:score,pred,init,w=evaluate(c,frozen,coef,strength,g)
            except ValueError as exc:
                unavailable.append(dict(**common,error=str(exc)));rows.append(dict(**common,status='unavailable'));continue
            rows.append(dict(**common,status='posthoc_evaluation',**score));initials.append(dict(**common,**init))
            windows.extend(dict(**common,**x) for x in w)
            for t,y,p in zip(c['q'],c['ap'],pred):
                paths.append(dict(**common,kind='AP',t_s=t,observed=y,predicted=p,residual=p-y))
            for t in range(121):
                y=m.integral(c,0,t);p=energy_prediction(features(c),c['actual'],frozen,coef or dict(alpha=0.,gain=1.),t)
                paths.append(dict(**common,kind='J',t_s=t,observed=y,predicted=p,residual=p-y))
    m.table(output/'session_errors.csv',rows);m.table(output/'windows.csv',windows);m.table(output/'initial_states.csv',initials)
    data=json.dumps(paths,separators=(',',':'),allow_nan=False).encode()
    (output/'paths.json.gz').write_bytes(gzip.compress(data,mtime=0))
    m.write(output/'unavailable.json',unavailable)
    aggregate=[]
    for block,role in [('history','development'),('history','confirmation'),('sustained','evaluation')]:
        ref={x['id']:x for x in rows if x['block']==block and x['role']==role and x['candidate']=='FROZEN' and x['status']!='unavailable'}
        for name in dict.fromkeys(x['candidate'] for x in rows):
            use=[x for x in rows if x['block']==block and x['role']==role and x['candidate']==name and x['status']!='unavailable']
            aggregate.append(dict(block=block,role=role,candidate=name,n=len(use),energy_mae_j=float(np.mean([x['abs_j'] for x in use])) if use else None,
                                  ap_mae_c=float(np.mean([x['mae_c'] for x in use])) if use else None,
                                  ap_max_absolute_c=max((x['max_absolute_error_c'] for x in use),default=None),
                                  peak_max_absolute_c=max((abs(x['peak_signed_error_c']) for x in use),default=None),
                                  energy_worse_sessions=sum(x['abs_j']>ref[x['id']]['abs_j']+1e-10 for x in use),
                                  ap_worse_sessions=sum(x['mae_c']>ref[x['id']]['mae_c']+1e-10 for x in use),
                                  cooling_opposite=sum(x['cooling_opposite'] is True for x in use)))
    m.table(output/'comparison.csv',aggregate)
    # Nominal sequential contrasts, not causal policy pairs.
    pairs=[]
    for role in ('development','confirmation'):
        for gap in (30,180):
            for name in dict.fromkeys(x['candidate'] for x in rows):
                group={x['policy']:x for x in rows if x['block']=='history' and x['role']==role and x['gap']==gap and x['candidate']==name and x['status']!='unavailable'}
                cpu,par=group.get('CPU_URGENT_ONLINE_V1'),group.get('B2_PARALLEL_ONLINE_V1')
                if cpu and par:pairs.append(dict(role=role,gap=gap,candidate=name,energy_difference_error_j=par['signed_j']-cpu['signed_j'],peak_difference_error_c=par['peak_signed_error_c']-cpu['peak_signed_error_c'],causal_policy_effect=False))
    m.table(output/'nominal_contrasts.csv',pairs)
    m.table(output/'sustained_pairs.csv',paired_rows(rows,cases))
    summary=dict(energy_selected=result['energy_selected'],ap_selected_lambda=result['ap_selected_lambda'],ap_diagnostic_lambda=result['ap_diagnostic_lambda'],energy_failure=result['energy_failure'],
                 rows=len(rows),unavailable=len(unavailable),active_seconds=time.monotonic()-start,device_commands=0,training=0,policy_simulations=0,
                 candidate_structures=2,posthoc=True,freeze_sha256=frozen_sha,input_sha256=m.sha(BUNDLE/'inputs.json.gz'),model_sha256=m.sha(m.MODEL),
                 accuracy_pass=None,policy_winner=None,experiment_ready=False)
    m.write(output/'summary.json',summary)
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);run(p.parse_args().output)
