"""Separate constrained power candidate and fixed AP evaluation. No device/RL path."""
import argparse
import itertools
import json
import math
from pathlib import Path
import traceback

import numpy as np
from tools import d1_energy_ap_joint_followup as old
from tools import d1_model_accuracy_expert_diagnostics as review

ROOT=old.ROOT
BUNDLE=ROOT/'docs/results/energy_ap_zero_offset_01'
STATES=old.analysis.j.m.base.STATES


def write(path,value):
    with Path(path).open('x',encoding='utf8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n')


def registration():
    old.validate_sources()
    reg=old.analysis.j.m.read(BUNDLE/'registration.json')
    for path,expected in reg['sources'].items():
        if old.scope_api.sha(ROOT/path)!=expected:raise ValueError('registered source changed: '+path)
    return reg


def design(cases,registered_ids):
    if len(cases)<3 or len({c['id'] for c in cases})!=len(cases) or any(
            c['id'] not in registered_ids or c['role']!='development' or c['policy'] not in ('DEV_A','DEV_B') for c in cases):
        raise ValueError('registered development-only fit')
    x=[];y=[];detail=[]
    original=old.analysis.j.m.read(old.analysis.j.m.MODEL)
    for c in cases:
        if not math.isfinite(c['pre_w']) or c['pre_w']<=0:raise ValueError('invalid preload power')
        intervals=list(range(35,int(c['common_end_s'])-4,5))
        weight=1/math.sqrt(len(intervals)*len(cases))
        for lo in intervals:
            exposure=old.analysis.j.m.base.exposure(c['actual'],lo,lo+5)
            cov=old.observed.measured_energy(c,lo,lo+5)
            observed=cov['full_energy_j']
            if observed is None:raise ValueError('development interval not fully covered')
            target=observed-5*c['pre_w']
            x.append(exposure*weight);y.append(target*weight)
            baseline=5*c['pre_w']+sum(float(v)*original['energy_increment_w'][k] for k,v in zip(STATES,exposure))
            detail.append(dict(session=c['id'],profile=c['policy'],lo_s=lo,hi_s=lo+5,
                target_increment_j=target,original_signed_j=baseline-observed,
                **{'exposure_'+k:float(v) for k,v in zip(STATES,exposure)}))
    x=np.array(x);y=np.array(y)
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.linalg.matrix_rank(x)!=4:
        raise ValueError('four state powers not identified')
    return x,y,detail


def train(cases,registered_ids):
    x,y,_=design(cases,registered_ids)
    # The same nonnegative active-set least-squares rule as the previous candidate;
    # only the idle-offset column is removed, not a new hyperparameter search.
    solutions=[]
    for count in range(5):
        for active in itertools.combinations(range(4),count):
            value=np.zeros(4)
            if active:value[list(active)]=np.linalg.lstsq(x[:,list(active)],y,rcond=None)[0]
            if np.all(value>=0):solutions.append(value)
    value=min(solutions,key=lambda v:float(np.sum((x@v-y)**2)))
    norms=np.linalg.norm(x,axis=0)
    singular=np.linalg.svd(x/norms,compute_uv=False)
    return dict(version='resident-energy-zero-offset-p4-v1',idle_bias_w=0.,
        increments=dict(zip(STATES,map(float,value))),coefficient_count=4,
        development_ids=[c['id'] for c in cases],scaled_singular_values=singular.tolist(),
        scaled_condition_number=float(singular[0]/singular[-1]),
        weighted_squared_residual_J2=float(np.sum((x@value-y)**2)),
        default=False,strict_support=False,accuracy_pass=None,experiment_ready=False)


def fit(output):
    reg=registration();out=Path(output);out.mkdir(parents=True,exist_ok=False)
    cases=old.analysis.j.m.read(old.scope_api.tail.s.INPUTS)
    if [c['id'] for c in cases]!=reg['development_ids']:raise ValueError('development roster drift')
    _,_,detail=design(cases,reg['development_ids'])
    old.scope_api.tail.s.csv_write(out/'development_residual_preflight.csv',detail)
    calls=0
    try:
        for excluded in cases:
            calls+=1
            write(out/('fit_call_'+str(calls)+'.json'),dict(call=calls,excluded=excluded['id'],status='started',energy_fit_max=5))
            model=train([c for c in cases if c['id']!=excluded['id']],reg['development_ids'])
            write(out/('fold_'+excluded['id']+'.json'),dict(excluded=excluded['id'],model=model))
        calls+=1
        write(out/('fit_call_'+str(calls)+'.json'),dict(call=calls,excluded=None,status='started',energy_fit_max=5))
        model=train(cases,reg['development_ids']);write(out/'candidate.json',model)
        write(out/'fit_receipt.json',dict(status='frozen_for_posthoc_evaluation',energy_fit_calls=calls,energy_fit_max=5,AP_fit_calls=0,
            candidate_sha256=old.scope_api.sha(out/'candidate.json'),registration_sha256=old.scope_api.sha(BUNDLE/'registration.json'),
            validation_targets_seen_before_family_choice=True,default_changed=False,strict_support=False,experiment_ready=False))
    except Exception:
        write(out/'FAIL_fit.json',dict(energy_fit_calls_started=calls,original_stack=traceback.format_exc(),device_commands=0))
        raise
    return model


def read_candidate(folder):
    registration()
    folder=Path(folder);receipt=old.analysis.j.m.read(folder/'fit_receipt.json')
    if old.scope_api.sha(folder/'candidate.json')!=receipt['candidate_sha256'] or old.scope_api.sha(BUNDLE/'registration.json')!=receipt['registration_sha256']:
        raise ValueError('frozen candidate/registration hash changed')
    model=old.analysis.j.m.read(folder/'candidate.json')
    if model['idle_bias_w']!=0 or model['coefficient_count']!=4:raise ValueError('zero-offset protocol changed')
    return model,receipt


def windows(c,stage):
    end=c['actual'][-1]['end_s'];covered=min(end,c['power_t'][-1]);last=c.get('last_lane_s')
    result=[('reference120',0.,120.),('future85',35.,120.)]
    if stage!='archive_posthoc':
        result += [('registered600',35.,635.),('recovery_full',635.,end),
                   ('recovery_covered_prefix',635.,covered),('registered_and_recovery_prefix',35.,covered)]
    if last is not None and last>35:result.append(('work_present',35.,last))
    result += [('post_lane_idle_full',max(35.,last or 35.),end),
               ('post_lane_idle_covered_prefix',max(35.,last or 35.),covered),
               ('matched_AP_power',max(35.,c['q'][0],c['power_t'][0]),min(c['q'][-1],covered))]
    return [(name,a,b) for name,a,b in result if b>a]


def energy(c,segments,model,lo,hi):
    return old.prediction(dict(pre_w=c['pre_w'],actual=segments),model,lo,hi)


def evaluate(output):
    out=Path(output);candidate,fit_receipt=read_candidate(out)
    if (out/'receipt.json').exists() or (out/'energy_errors.csv').exists():raise ValueError('evaluation output already consumed')
    original=old.analysis.j.m.read(old.analysis.j.m.MODEL)
    _,_,ap_model=old.scope_api.read_assets()
    macro=old.analysis.j.m.read(old.scope_api.tail.s.INPUTS)
    archive,_=old.analysis.j.panel()
    long=old.analysis.j.m.read(ROOT/'docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz')
    cases=[(c,'development_loso') for c in macro]+[(c,'archive_posthoc') for c in archive]+[(c,'seen_long_posthoc') for c in long]
    E=[];AP=[];curves=[];bins=[];stored_B=[]
    for c,stage in cases:
        m=old.analysis.j.m.read(out/('fold_'+c['id']+'.json'))['model'] if stage=='development_loso' else candidate
        previous=old.analysis.j.m.read(old.BUNDLE/'run_v1'/('fold_'+c['id']+'.json'))['model'] if stage=='development_loso' else old.analysis.j.m.read(old.BUNDLE/'run_v1/candidate.json')
        ablated=dict(previous,idle_bias_w=0.)
        original_ap=old.analysis.j.m.predict(c,c['actual'],original,dict(name='FROZEN'))[0]
        fixed_ap,_=old.scope_api.tail.predict(c,original,ap_model)
        support_reasons=old.scope_api.schedule_reasons(c,old.scope_api.read_assets()[0])
        for phase,lo,hi in windows(c,stage):
            cov=old.observed.measured_energy(c,lo,hi);observed=cov['full_energy_j']
            f=old.analysis.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),hi)-old.analysis.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),lo)
            n=energy(c,c['actual'],m,lo,hi);prior=energy(c,c['actual'],previous,lo,hi);abl=energy(c,c['actual'],ablated,lo,hi)
            E.append(dict(session=c['id'],stage=stage,policy=c['policy'],phase=phase,lo_s=lo,hi_s=hi,**cov,
                observed_j=observed,frozen_j=f,previous_offset_j=prior,fixed_p4_ablation_j=abl,candidate_j=n,
                frozen_signed_j=f-observed if observed is not None else None,candidate_signed_j=n-observed if observed is not None else None,
                frozen_absolute_j=abs(f-observed) if observed is not None else None,candidate_absolute_j=abs(n-observed) if observed is not None else None,
                candidate_relative_error=(n-observed)/observed if observed else None,
                energy_worse=abs(n-observed)>abs(f-observed)+1e-9 if observed is not None else None))
            for name,pred in [('FROZEN',original_ap),('fixed_LOAD_SLOW',fixed_ap)]:
                AP.append(dict(session=c['id'],stage=stage,policy=c['policy'],phase=phase,model=name,lo_s=lo,hi_s=hi,
                    **old.observed.phase_score(c,pred,lo,hi),diagnostic_scope_matches=not support_reasons,
                    support_reasons=';'.join(support_reasons),AP_fit_calls=0))
        hi=min(c['actual'][-1]['end_s'],c['power_t'][-1]);query=sorted(set([35.,120.,hi]+[float(v) for v in np.linspace(0,hi,161)[1:]]))
        for t in query:
            if t<=hi:
                cov=old.observed.measured_energy(c,0.,t)
                curves.append(dict(session=c['id'],stage=stage,t_s=t,observed_j=cov['full_energy_j'],
                    frozen_j=old.analysis.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),t),
                    previous_offset_j=energy(c,c['actual'],previous,0.,t),candidate_j=energy(c,c['actual'],m,0.,t)))
        for width in (5,10):
            for lo in np.arange(35.,hi,width):
                end=min(float(lo)+width,hi);cov=old.observed.measured_energy(c,float(lo),end)
                observed=cov['full_energy_j'];n=energy(c,c['actual'],m,float(lo),end)
                f=old.analysis.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),end)-old.analysis.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),float(lo))
                exposure=old.analysis.j.m.base.exposure(c['actual'],float(lo),end)
                occupied=float(exposure.sum());label='resident_idle' if occupied<1e-9 else ('mixed_bin' if np.count_nonzero(exposure>1e-9)>1 or occupied<end-lo-1e-6 else STATES[int(np.argmax(exposure))])
                bins.append(dict(session=c['id'],stage=stage,width_s=width,lo_s=float(lo),hi_s=end,bin_state=label,observed_j=observed,
                    frozen_signed_j=f-observed if observed is not None else None,candidate_signed_j=n-observed if observed is not None else None))
        if c.get('forecast'):
            segments=c['forecast']
            for phase,lo,hi in [('reference120',0.,120.),('future85',35.,120.)]:
                observed=old.observed.measured_energy(c,lo,hi)['full_energy_j']
                f=old.analysis.j.m.energy_prediction(c,segments,original,dict(name='FROZEN'),hi)-old.analysis.j.m.energy_prediction(c,segments,original,dict(name='FROZEN'),lo)
                n=energy(c,segments,m,lo,hi)
                stored_B.append(dict(session=c['id'],stage=stage,policy=c['policy'],phase=phase,lo_s=lo,hi_s=hi,
                    observed_j=observed,frozen_j=f,candidate_j=n,frozen_signed_j=f-observed if observed is not None else None,
                    candidate_signed_j=n-observed if observed is not None else None,
                    prediction_layer='stored_forecast_schedule_cost_projection_only',new_schedule_generation=False,
                    new_response_evaluation=False,AP_strict_supported=False))
    old.scope_api.tail.s.csv_write(out/'energy_errors.csv',E)
    old.scope_api.tail.s.csv_write(out/'AP_errors.csv',AP)
    old.scope_api.tail.s.csv_write(out/'energy_curves.csv',curves)
    old.scope_api.tail.s.csv_write(out/'sensor_resolution_bins.csv',bins)
    old.scope_api.tail.s.csv_write(out/'stored_B_energy_errors.csv',stored_B)
    pairs=[]
    for n in range(4):
        for mode,table in [('A_conditional',E),('B_stored_schedule_cost',stored_B)]:
            lookup={r['session']:r for r in table if r['phase']=='reference120'}
            a,b=review.orient_policy_pair(lookup['sustained_'+str(2*n)],lookup['sustained_'+str(2*n+1)])
            obs=lookup[b]['observed_j']-lookup[a]['observed_j'];f=lookup[b]['frozen_j']-lookup[a]['frozen_j'];c=lookup[b]['candidate_j']-lookup[a]['candidate_j']
            pairs.append(dict(pair=n,mode=mode,baseline_session=a,parallel_session=b,observed_delta_j=obs,frozen_predicted_delta_j=f,
                candidate_predicted_delta_j=c,frozen_delta_error_j=f-obs,candidate_delta_error_j=c-obs,
                frozen_sign_wrong=f*obs<0,candidate_sign_wrong=c*obs<0,causal_policy_effect=False))
    old.scope_api.tail.s.csv_write(out/'paired_errors.csv',pairs)
    summary=[]
    for stage in ('development_loso','archive_posthoc','seen_long_posthoc'):
        for phase in dict.fromkeys(r['phase'] for r in E):
            use=[r for r in E if r['stage']==stage and r['phase']==phase and r['observed_j'] is not None]
            if use:summary.append(dict(stage=stage,phase=phase,sessions=len(use),
                frozen_mean_absolute_j=float(np.mean([r['frozen_absolute_j'] for r in use])),candidate_mean_absolute_j=float(np.mean([r['candidate_absolute_j'] for r in use])),
                energy_worse=sum(r['energy_worse'] for r in use)))
    old.scope_api.tail.s.csv_write(out/'summary.csv',summary)
    receipt=dict(status='posthoc_constrained_energy_and_fixed_AP_evaluated',sessions=len(cases),family_count=1,
        energy_fit_calls=fit_receipt['energy_fit_calls'],AP_fit_calls=0,new_policy_simulator_runs=0,device_commands=0,
        candidate_sha256=fit_receipt['candidate_sha256'],AP_candidate_sha256=old.scope_api.sha(ROOT/'docs/results/ap_tail_identification_01/run_v2/candidates.json'),
        prediction_layer='A_actual_schedule_conditional',B_is_saved_schedule_cost_only=True,
        no_load_baseline_drift_solved=False,independent_new_confirmation=False,
        default_changed=False,rl_changed=False,strict_support=False,accuracy_pass=None,experiment_ready=False)
    write(out/'receipt.json',receipt)
    return summary


def forecast(case,context,folder,*,opt_in=False,lo_s=35.,hi_s=635.):
    """Explicit registered-macro cost diagnostic; never replace the base simulator."""
    model,_=read_candidate(folder)
    result=dict(status='blocked',reasons=[],energy_prediction_j=None,prediction_ap_c=None,
        prediction_layer='actual_schedule_conditional',strict_support=False,accuracy_pass=None,
        default_changed=False,rl_changed=False,experiment_ready=False)
    if context.get('requested_usage')!='diagnostic_energy_AP_only':
        result['reasons'].append('explicit_joint_diagnostic_usage_required');return result
    ap_context=dict(context,requested_usage='diagnostic_AP_only')
    ap=old.scope_api.forecast(case,ap_context,opt_in=opt_in)
    if ap['status']!='diagnostic_AP_only':result['reasons']=ap['reasons'];return result
    if not math.isfinite(case.get('pre_w',float('nan'))) or case['pre_w']<=0:
        result['reasons']=['invalid_preload_power'];return result
    if context.get('power_pre_window_s')!=[-20,30] or context.get('power_initialization_clock')!='canonical_common_start_seconds':
        result['reasons']=['preload_power_information_contract_mismatch'];return result
    if not old.scope_api.finite(context.get('power_pre_ready_s')) or not 30<=context['power_pre_ready_s']<35:
        result['reasons']=['future_or_unrecorded_preload_power_availability'];return result
    try:
        value=energy(dict(pre_w=case['pre_w']),case['actual'],model,lo_s,hi_s)
    except (ValueError,KeyError,TypeError):
        result.update(status='calculation_failed',reasons=['energy_predictor_rejected_input'],original_stack=traceback.format_exc());return result
    result.update(status='diagnostic_energy_AP_only',energy_prediction_j=value,energy_window_s=[lo_s,hi_s],
        prediction_ap_c=ap['prediction_ap_c'],query_window_s=ap['query_window_s'],
        no_load_baseline_drift_solved=False,independent_accuracy_pass=False)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--action',choices=('fit','evaluate'),required=True);p.add_argument('--output',required=True);a=p.parse_args()
    try:
        result=fit(a.output) if a.action=='fit' else evaluate(a.output)
    except Exception:
        folder=Path(a.output)
        if folder.exists() and not (folder/('FAIL_'+a.action+'.json')).exists():
            write(folder/('FAIL_'+a.action+'.json'),dict(original_stack=traceback.format_exc(),device_commands=0,automatic_retry=False))
        raise
    print(json.dumps(result,allow_nan=False))


if __name__=='__main__':main()
