"""Matched-data energy/AP contrasts; fixed time constants, no device/default/RL path."""
import argparse
import json
import math
from pathlib import Path
import traceback

import numpy as np
from tools import d1_energy_ap_zero_offset as prior

ROOT=prior.ROOT
BUNDLE=ROOT/'docs/results/session_contrast_cost_01'
METHODS=('UNCENTERED','CENTERED')
GROUPS=('old','history30','history180','macro')


def group(c):
    if c['id'].startswith('session_'):return 'macro'
    if '_30_' in c['id']:return 'history30'
    if '_180_' in c['id']:return 'history180'
    return 'old'


def cases():
    macro=prior.old.analysis.j.m.read(prior.old.scope_api.tail.s.INPUTS)
    archive,_=prior.old.analysis.j.panel()
    long=prior.old.analysis.j.m.read(ROOT/'docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz')
    return macro+archive+long


def read_registration():
    prior.registration()
    r=prior.old.analysis.j.m.read(BUNDLE/'registration.json')
    for p,h in r['sources'].items():
        if prior.old.scope_api.sha(ROOT/p)!=h:raise ValueError('registered source changed: '+p)
    audit=prior.old.analysis.j.m.read(BUNDLE/'native13_contract_audit.json')
    if not audit['core_execution_equal'] or audit['manifest_count']!=13 or not audit['device_identity_equal'] or not audit['cpu_threads_equal'] or not audit['resident_keys_equal']:
        raise ValueError('core model/runtime/resident contract mismatch')
    if {c['case_id'] for c in audit['cases']}!=set(r['development_ids']) or not all(c['source_inventory_hash_match'] for c in audit['cases']):
        raise ValueError('native development roster/source mismatch')
    return r


def design(c,head,original):
    if head=='energy':
        end=635 if group(c)=='macro' else 120
        X=[];target=[]
        for lo in range(35,end,5):
            obs=prior.old.observed.measured_energy(c,lo,lo+5)['full_energy_j']
            if obs is None:raise ValueError('missing training energy')
            X.append(prior.old.analysis.j.m.base.exposure(c['actual'],lo,lo+5))
            target.append(obs-5*c['pre_w'])
        return np.asarray(X),np.asarray(target)
    if head=='AP':
        initial,fast,slow,_,_=prior.old.scope_api.tail.bases(c,original,1920.)
        return np.column_stack((fast,slow)),np.asarray(c['ap'])-initial
    raise ValueError('unregistered head')


def centered_design(X,y,method):
    if method=='CENTERED':return X-X.mean(axis=0),y-y.mean()
    if method=='UNCENTERED':return X,y
    raise ValueError('unregistered method')


def estimate(data,head,method,original,development_ids):
    if not data or any(c['id'] not in development_ids or c['role']!='development' for c in data):
        raise ValueError('designated development only')
    n=4 if head=='energy' else 5;xs=[];ys=[];raw=[]
    for c in data:
        X,y=design(c,head,original)
        if not np.isfinite(X).all() or not np.isfinite(y).all():raise ValueError('nonfinite design or target')
        raw.append((c,X,y));x,z=centered_design(X,y,method);weight=1/math.sqrt(len(y)*len(data))
        xs.append(x*weight);ys.append(z*weight)
    x=np.vstack(xs);y=np.concatenate(ys)
    if np.linalg.matrix_rank(x)!=n:raise ValueError('head coefficients numerically unidentified')
    theta=prior.old.scope_api.tail.s.nnls(x,y)
    norm=np.linalg.norm(x,axis=0);singular=np.linalg.svd(x/norm,compute_uv=False)
    nuisance=[dict(session=c['id'],mean_residual=float(np.mean(z-X@theta)),
        unit='J_per_5_second_bin' if head=='energy' else 'degree_C',training_only=True) for c,X,z in raw]
    common=dict(method=method,development_ids=[c['id'] for c in data],numerical_rank=n,
        scaled_condition=float(singular[0]/singular[-1]),weighted_training_MSE=float(np.sum((x@theta-y)**2)),
        training_nuisance_levels_used=len(data) if method=='CENTERED' else 0,
        nuisance_not_used_in_prediction=nuisance,default=False,strict_support=False,accuracy_pass=None,experiment_ready=False)
    if head=='energy':return dict(common,version='session-contrast-energy-v1',coefficient_count=4,idle_bias_w=0.,increments=dict(zip(prior.STATES,map(float,theta))))
    return dict(common,version='session-contrast-AP-v1',mode='LOAD_SLOW',coefficients=theta.tolist(),tau_s=1920.,
        beta_fixed=original['ap']['beta'],preparation_tau_s=30.,original_model_sha256=prior.old.analysis.j.m.MODEL_SHA,
        application_allowed=False,physical_cause_identified=False,time_identified=False,
        tau_is_inherited_posthoc_prior_not_fresh_identified=True)


def score_development(c,model,head,original):
    if head=='energy':
        hi=635 if group(c)=='macro' else 120
        obs=prior.old.observed.measured_energy(c,35.,hi)['full_energy_j']
        y=prior.energy(c,c['actual'],model,35.,hi)
        return dict(primary_abs_mean_power_W=abs(y-obs)/(hi-35),abs_J=abs(y-obs),window_s=[35.,hi])
    pred,_=prior.old.scope_api.tail.predict(c,original,model)
    return prior.old.observed.phase_score(c,pred,35.,c['actual'][-1]['end_s'])


def fit(output):
    reg=read_registration();out=Path(output);out.mkdir(parents=True,exist_ok=False)
    all_cases=cases();data=[c for c in all_cases if c['id'] in reg['development_ids']]
    if sorted(c['id'] for c in data)!=sorted(reg['development_ids']):raise ValueError('development roster drift')
    original=prior.old.analysis.j.m.read(prior.old.analysis.j.m.MODEL)
    scores=[];count=0;hashes={}
    try:
        for method in METHODS:
            for excluded in GROUPS+(None,):
                train=[c for c in data if group(c)!=excluded]
                for head in ('energy','AP'):
                    count+=1
                    prior.write(out/('fit_call_'+str(count)+'.json'),dict(call=count,max_calls=20,head=head,method=method,excluded=excluded))
                    model=estimate(train,head,method,original,reg['development_ids'])
                    name=method+'_'+head+'_'+(excluded or 'final')+'.json';prior.write(out/name,model)
                    hashes[name]=prior.old.scope_api.sha(out/name)
                    if excluded:
                        for c in data:
                            if group(c)==excluded:scores.append(dict(session=c['id'],source_group=excluded,method=method,head=head,**score_development(c,model,head,original)))
        prior.old.scope_api.tail.s.csv_write(out/'development_source_excluded.csv',scores)
        selection={};keys={}
        for head in ('energy','AP'):
            metric='primary_abs_mean_power_W' if head=='energy' else 'mae_c'
            for method in METHODS:
                use=[r for r in scores if r['head']==head and r['method']==method]
                per_group=[np.mean([r[metric] for r in use if r['source_group']==g]) for g in GROUPS]
                keys[(head,method)]=(float(np.mean(per_group)),max(float(r[metric]) for r in use))
            selection[head]=min(METHODS,key=lambda method:(keys[(head,method)],METHODS.index(method)))
        prior.write(out/'selection.json',dict(selected_heads=selection,
            development_only_keys={h:{m:keys[(h,m)] for m in METHODS} for h in ('energy','AP')},
            energy_objective='source-equal mean absolute J/duration,then worst session same-unit error',
            AP_objective='source-equal mean absolute path MAE,then worst session MAE',
            evaluation_targets_used_in_selection=False,accuracy_pass=None))
        prior.write(out/'fit_receipt.json',dict(status='models_and_head_selection_frozen_before_evaluation',fit_calls=count,energy_fit_calls=10,AP_fit_calls=10,
            model_hashes=hashes,selection_sha256=prior.old.scope_api.sha(out/'selection.json'),
            registration_sha256=prior.old.scope_api.sha(BUNDLE/'registration.json'),default_changed=False,device_commands=0))
    except Exception:
        prior.write(out/'FAIL_fit.json',dict(fit_calls_started=count,original_stack=traceback.format_exc(),automatic_retry=False));raise
    return selection


def assets(output):
    read_registration();out=Path(output);receipt=prior.old.analysis.j.m.read(out/'fit_receipt.json')
    if receipt['registration_sha256']!=prior.old.scope_api.sha(BUNDLE/'registration.json'):raise ValueError('registration changed')
    for name,h in receipt['model_hashes'].items():
        if prior.old.scope_api.sha(out/name)!=h:raise ValueError('model bytes changed')
    if receipt['selection_sha256']!=prior.old.scope_api.sha(out/'selection.json'):raise ValueError('selection changed')
    return receipt,prior.old.analysis.j.m.read(out/'selection.json')['selected_heads']


def evaluate(output):
    out=Path(output);receipt,choice=assets(out)
    if (out/'receipt.json').exists():raise ValueError('evaluation output already completed')
    reg=read_registration();all_cases=cases();lookup={c['id']:c for c in all_cases};original=prior.old.analysis.j.m.read(prior.old.analysis.j.m.MODEL)
    E=[];AP=[];curves=[];B=[];pairs=[]
    source=prior.BUNDLE/'run_v1'
    stored_energy=prior.old.table(source/'energy_errors.csv')
    stored_AP={(r['session'],r['phase'],r['model']):r for r in prior.old.table(source/'AP_errors.csv')}
    stored_B=prior.old.table(source/'stored_B_energy_errors.csv')
    def model(c,method,head):
        excluded=group(c) if c['id'] in reg['development_ids'] else 'final'
        return prior.old.analysis.j.m.read(out/(method+'_'+head+'_'+excluded+'.json'))
    def role(c):return 'development_source_excluded' if c['id'] in reg['development_ids'] else ('seen_long_evaluation' if c['policy'] in ('C0_LONG','LOAD_A_LONG') else 'seen_archival_evaluation')
    for c in all_cases:
        print(prior.terminal_json(dict(stage='evaluate',session=c['id'],role=role(c))),flush=True)
        for method in METHODS:
            em=model(c,method,'energy');am=model(c,method,'AP')
            ap_pred,_=prior.old.scope_api.tail.predict(c,original,am)
            for r in stored_energy:
                if r['session']!=c['id']:continue
                lo,hi=float(r['lo_s']),float(r['hi_s']);n=prior.energy(c,c['actual'],em,lo,hi)
                obs=float(r['observed_j']) if r['observed_j'] else None
                E.append(dict(session=c['id'],role=role(c),source_group=group(c) if c['id'] in reg['development_ids'] else c.get('block','long'),method=method,phase=r['phase'],lo_s=lo,hi_s=hi,
                    observed_j=obs,original_j=float(r['frozen_j']),prior_zero_offset_j=float(r['candidate_j']),candidate_j=n,
                    candidate_signed_j=n-obs if obs is not None else None,candidate_abs_j=abs(n-obs) if obs is not None else None,
                    original_abs_j=float(r['frozen_absolute_j']) if r['frozen_absolute_j'] else None,
                    prior_abs_j=float(r['candidate_absolute_j']) if r['candidate_absolute_j'] else None,
                    candidate_relative=(n-obs)/obs if obs else None,selected_head=method==choice['energy'],
                    learned_nuisance_not_in_forecast=True))
                score=prior.old.observed.phase_score(c,ap_pred,lo,hi)
                oldAP=stored_AP[(c['id'],r['phase'],'FROZEN')]
                prevAP=stored_AP[(c['id'],r['phase'],'fixed_LOAD_SLOW')]
                AP.append(dict(session=c['id'],role=role(c),method=method,phase=r['phase'],lo_s=lo,hi_s=hi,
                    **score,original_MAE_c=float(oldAP['mae_c']) if oldAP['mae_c'] else None,prior_AP_MAE_c=float(prevAP['mae_c']) if prevAP['mae_c'] else None,
                    selected_head=method==choice['AP'],prior_AP_reference_macro_development_in_sample=c['id'].startswith('session_')))
            for i,t in enumerate(c['q']):
                curves.append(dict(session=c['id'],role=role(c),method=method,t_s=t,observed_ap_c=c['ap'][i],predicted_ap_c=ap_pred[i]))
            for r in stored_B:
                if r['session']!=c['id']:continue
                lo,hi=float(r['lo_s']),float(r['hi_s']);n=prior.energy(c,c['forecast'],em,lo,hi)
                obs=float(r['observed_j']) if r['observed_j'] else None
                B.append(dict(session=c['id'],role=role(c),method=method,phase=r['phase'],observed_j=obs,candidate_j=n,prior_j=float(r['candidate_j']),original_j=float(r['frozen_j']),
                    candidate_signed_j=n-obs if obs is not None else None,selected_head=method==choice['energy'],new_schedule_or_response_validation=False))
    for method in METHODS:
        for i in range(4):
            for mode,table in [('A',E),('B_saved_cost',B)]:
                rows={r['session']:r for r in table if r['method']==method and r['phase']=='reference120'}
                meta={c['id']:dict(session=c['id'],policy=c['policy']) for c in all_cases}
                a,b=prior.review.orient_policy_pair(meta['sustained_'+str(2*i)],meta['sustained_'+str(2*i+1)])
                obs=rows[b]['observed_j']-rows[a]['observed_j'];n=rows[b]['candidate_j']-rows[a]['candidate_j']
                pairs.append(dict(pair=i,method=method,mode=mode,baseline_session=a,parallel_session=b,observed_delta_j=obs,predicted_delta_j=n,delta_error_j=n-obs,sign_wrong=n*obs<0,selected_head=method==choice['energy']))
    for name,rows in [('energy_errors',E),('AP_errors',AP),('AP_curves',curves),('B_saved_cost',B),('paired_errors',pairs)]:
        prior.old.scope_api.tail.s.csv_write(out/(name+'.csv'),rows)
    summary=[]
    for method in METHODS:
        for status in ('development_source_excluded','seen_archival_evaluation','seen_long_evaluation'):
            for phase in ('reference120','future85','registered600','matched_AP_power'):
                use=[r for r in E if r['method']==method and r['role']==status and r['phase']==phase and r['observed_j'] is not None]
                if use:
                    summary.append(dict(role=status,method=method,phase=phase,sessions=len(use),original_mean_abs_J=float(np.mean([r['original_abs_j'] for r in use])),prior_mean_abs_J=float(np.mean([r['prior_abs_j'] for r in use])),candidate_mean_abs_J=float(np.mean([r['candidate_abs_j'] for r in use])),
                        worse_than_prior=sum(r['candidate_abs_j']>r['prior_abs_j']+1e-9 for r in use)))
    prior.old.scope_api.tail.s.csv_write(out/'summary.csv',summary)
    prior.write(out/'receipt.json',dict(status='two_preregistered_methods_evaluated_no_reselection',fit_calls=20,selected_heads=choice,energy_development_sessions=13,energy_held_from_fit_sessions=22,
        AP_development_sessions=13,AP_held_from_fit_sessions=22,already_viewed_posthoc=True,coefficient_source_exclusion_not_full_family_OOF=True,
        default_changed=False,rl_changed=False,strict_support=False,experiment_ready=False,device_commands=0,new_measurement_plans=0))
    return summary


def forecast(c,context,output,*,opt_in=False,lo_s=35.,hi_s=635.):
    receipt,choice=assets(output)
    prior_result=prior.forecast(c,context,prior.BUNDLE/'run_v1',opt_in=opt_in,lo_s=lo_s,hi_s=hi_s)
    if prior_result['status']!='diagnostic_energy_AP_only':return prior_result
    out=Path(output);em=prior.old.analysis.j.m.read(out/(choice['energy']+'_energy_final.json'))
    am=prior.old.analysis.j.m.read(out/(choice['AP']+'_AP_final.json'))
    original=prior.old.analysis.j.m.read(prior.old.analysis.j.m.MODEL)
    # Preserve old metadata guard, but load new heads explicitly from a different bundle.
    predictor_input=dict(pre=c['pre'],actual=c['actual'],q=c['q'])
    y,_=prior.old.scope_api.tail.predict(predictor_input,original,am)
    value=prior.energy(dict(pre_w=c['pre_w']),c['actual'],em,lo_s,hi_s)
    return dict(prior_result,energy_prediction_j=value,prediction_ap_c=y,selected_heads=choice,
        model_bundle='session_contrast_cost_01',source_model_hashes=receipt['model_hashes'],
        learned_session_nuisance_used_at_prediction=False,already_seen_posthoc_candidate=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--action',choices=('fit','evaluate'),required=True);p.add_argument('--output',required=True);a=p.parse_args()
    try:result=fit(a.output) if a.action=='fit' else evaluate(a.output)
    except Exception:
        out=Path(a.output)
        if out.exists() and not (out/('FAIL_'+a.action+'.json')).exists():prior.write(out/('FAIL_'+a.action+'.json'),dict(original_stack=traceback.format_exc(),automatic_retry=False))
        raise
    print(prior.terminal_json(result))


if __name__=='__main__':main()
