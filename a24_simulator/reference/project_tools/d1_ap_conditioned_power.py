"""Pre-only CPU/AP baseline association; fixed idle cooling, offline opt-in only."""
import argparse
import csv
import math
import time
import traceback
from pathlib import Path
import numpy as np
from tools import d1_registered_baseline as old

ROOT=old.ROOT
BUNDLE=ROOT/'docs/results/ap_conditioned_power_01'
FAMILIES=('MATCH_CPU','CPU_AP')
METHODS=('P50','PRIOR_FULL_CPU','MATCH_CPU','CPU_AP')


def table(path):
    with Path(path).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def validate_pre(pre):
    if len(pre)<15 or any(not all(math.isfinite(float(p[k])) for k in ('t','lo','hi','ap')) or
            not p['lo']<=p['t']<=p['hi']<35 for p in pre) or any(
            not 0<b['t']-a['t']<=10 for a,b in zip(pre,pre[1:])):
        raise ValueError('invalid/gapped/future pre AP; no filling')


def AP_bin_mean(pre,lo,hi):
    validate_pre(pre)
    if not pre[0]['t']<=lo<hi<=30 or hi>pre[-1]['t']:raise ValueError('unbracketed pre AP window')
    t=np.array([p['t'] for p in pre]);y=np.array([p['ap'] for p in pre])
    points=np.array([lo,*[float(v) for v in t if lo<v<hi],hi])
    values=np.interp(points,t,y)
    return float(np.sum(np.diff(points)*(values[:-1]+values[1:])/2)/(hi-lo))


def idle_terms(init):
    keys=('reference_c','h_last_c_per_s','anchor_s','anchor_ap_c','input_end_s','beta_per_s','tau_s')
    if not all(math.isfinite(init[k]) for k in keys) or not 30<=init['anchor_s']<=init['input_end_s']<35 or min(init['beta_per_s'],init['tau_s'])<=0:
        raise ValueError('pre AP initial-state clock/parameter')
    return init['reference_c'],init['anchor_ap_c']-init['reference_c'],init['h_last_c_per_s'],init['beta_per_s'],1/init['tau_s']


def idle_AP(init,t):
    R,A,H,b,r=idle_terms(init);d=t-init['anchor_s']
    if not 35<=t<=120:raise ValueError('idle forecast horizon')
    conv=d*math.exp(-b*d) if abs(b-r)<1e-10 else (math.exp(-r*d)-math.exp(-b*d))/(b-r)
    return R+A*math.exp(-b*d)+H*conv


def idle_integral(init,lo,hi):
    R,A,H,b,r=idle_terms(init)
    if not 35<=lo<hi<=120:raise ValueError('idle integration horizon')
    da,db=lo-init['anchor_s'],hi-init['anchor_s']
    eb=(math.exp(-b*da)-math.exp(-b*db))/b
    if abs(b-r)<1e-10:
        memory=((da+1/b)*math.exp(-b*da)-(db+1/b)*math.exp(-b*db))/b
    else:
        er=(math.exp(-r*da)-math.exp(-r*db))/r;memory=(er-eb)/(b-r)
    return R*(hi-lo)+A*eb+H*memory


def critical_times(init):
    _,A,H,b,r=idle_terms(init);values=[35.,120.]
    if abs(b-r)<1e-10:
        if H!=0:
            d=(H-b*A)/(b*H)
            t=init['anchor_s']+d
            if 35<t<120:values.append(t)
    else:
        Cb=A-H/(b-r);Cr=H/(b-r)
        ratio=-b*Cb/(r*Cr) if Cr!=0 else -1
        if ratio>0:
            t=init['anchor_s']+math.log(ratio)/(b-r)
            if 35<t<120:values.append(t)
    return sorted(values)


def fit(rows,ids,family):
    identities={r['session'] for r in rows}
    if family not in FAMILIES or len(identities)<3 or not identities<=set(ids) or any(r['role']!='development' for r in rows):
        raise ValueError('registered development-only family')
    xs=[];ys=[]
    for identity in sorted(identities):
        use=[r for r in rows if r['session']==identity]
        old.features(use)
        X=np.array([[r['other_rate_core_s_per_s'],r['pre_AP_mean_c']] for r in use]);y=np.array([r['mean_power_W'] for r in use])
        if not np.isfinite(X).all() or not np.isfinite(y).all():raise ValueError('missing pre fit data')
        X=X-X.mean(axis=0);y=y-y.mean();w=1/math.sqrt(len(use)*len(identities))
        xs.extend(X*w);ys.extend(y*w)
    x=np.array(xs);y=np.array(ys);n=1 if family=='MATCH_CPU' else 2
    use=x[:,:n];norm=np.linalg.norm(use,axis=0)
    if np.any(norm<=0):raise ValueError('unidentified pre covariate')
    scaled=use/norm;singular=np.linalg.svd(scaled,compute_uv=False)
    if singular[-1]<=singular[0]*1e-12:raise ValueError('rank deficient pre CPU/AP; no invented coefficients')
    theta=np.linalg.lstsq(scaled,y,rcond=None)[0]/norm
    if theta[0]<0:
        theta[0]=0.
        if n==2:theta[1]=float(use[:,1]@y/(use[:,1]@use[:,1]))
    return dict(version='pre-AP-preparatory-cooling-power-v1',family=family,
        CPU_slope_W_per_core_s_per_s=float(theta[0]),AP_slope_W_per_C=float(theta[1]) if n==2 else 0.,
        coefficient_count=n,development_ids=sorted(identities),scaled_singular_values=singular.tolist(),
        scaled_condition=float(singular[0]/singular[-1]),pre_equal_session_RMSE_W=float(np.sqrt(np.sum((use@theta-y)**2))),
        AP_slope_is_observational_not_physical=True,CPU_nonnegative=True,AP_slope_signed=True,
        AP_beta_and_preparation_tau_fixed=True,future_targets_used=False,
        default=False,strict_support=False,accuracy_pass=None,experiment_ready=False)


def baseline(public,model,t):
    f=public['features'];a=public['pre_init'];idle_terms(a)
    keys=('pre_full_mean_W','pre_full_mean_other','persistent_other_proxy','pre_mean_AP_c','duration_s')
    if not all(math.isfinite(f[k]) for k in keys) or f['duration_s']<75 or not public['pre_before35'] or not public['trace_complete']:
        raise ValueError('invalid pre-only information')
    b,g=model['CPU_slope_W_per_core_s_per_s'],model['AP_slope_W_per_C']
    if not math.isfinite(b) or b<0 or not math.isfinite(g):raise ValueError('invalid power coefficients')
    return f['pre_full_mean_W']+b*(f['persistent_other_proxy']-f['pre_full_mean_other'])+g*(idle_AP(a,t)-f['pre_mean_AP_c'])


def prediction(public,model,power,lo,hi,*,opt_in=False):
    if not opt_in:raise ValueError('explicit offline diagnostic opt-in required')
    if not 0<=lo<hi<=120:raise ValueError('supported recorded horizon0..120 only')
    if min(baseline(public,model,t) for t in critical_times(public['pre_init']))<=0:
        raise ValueError('nonpositive baseline within horizon; no clipping')
    base=old.old.prior.prior.energy(public,public['actual'],power,lo,hi)
    left=max(35.,lo)
    if hi<=left:return base
    f=public['features'];b,g=model['CPU_slope_W_per_core_s_per_s'],model['AP_slope_W_per_C'];dt=hi-left
    const=f['pre_full_mean_W']+b*(f['persistent_other_proxy']-f['pre_full_mean_other'])-public['pre_w']
    return base+dt*const+g*(idle_integral(public['pre_init'],left,hi)-dt*f['pre_mean_AP_c'])


def prepare(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    prior=old.BUNDLE/'run_v1';old.assets(prior)
    prebase=ROOT/'docs/results/preboundary_evidence_01/run_v1'
    v=old.old.read(prebase.parent/'verification.json')['artifact_sha256']
    for name in ('expanded_pre.json','initial_states.csv'):
        key=str((prebase/name).relative_to(ROOT)).replace('\\','/')
        if key in v and old.old.sha(prebase/name)!=v[key]:raise ValueError('frozen AP information changed')
    all_pre={r['id']:r['expanded_pre'] for r in old.old.read(prebase/'expanded_pre.json')}
    inits={r['session']:r for r in table(prebase/'initial_states.csv') if r['variant']=='registered_idle_pre'}
    raw=table(prior/'pre_bins.csv');publics=[];rows=[];availability=[]
    original=old.old.read(old.old.prior.prior.old.analysis.j.m.MODEL);beta=original['ap']['beta']
    for previous in old.old.read(prior/'pre_inputs.json'):
        identity=previous['id'];pre=all_pre[identity];validate_pre(pre)
        use=[];discard=0
        for r in [r for r in raw if r['session']==identity]:
            r=dict(r)
            for k in ('lo_s','hi_s','other_rate_core_s_per_s','mean_power_W','latest_power_event_s'):r[k]=float(r[k])
            if r['lo_s']<pre[0]['t']:discard+=1;continue
            r['gap']=int(r['gap']);r['pre_AP_mean_c']=AP_bin_mean(pre,r['lo_s'],r['hi_s']);use.append(r)
        f=old.features(use);f['pre_mean_AP_c']=float(np.mean([r['pre_AP_mean_c'] for r in use]))
        init={k:float(inits[identity][k]) for k in ('reference_c','h_last_c_per_s','anchor_s','anchor_ap_c','input_end_s')}
        init.update(beta_per_s=beta,tau_s=30.,initial_state_reused_not_refit=True,reference_is_ambient=False)
        idle_terms(init)
        if init['anchor_s']!=pre[-1]['t'] or init['anchor_ap_c']!=pre[-1]['ap'] or init['input_end_s']!=pre[-1]['hi']:
            raise ValueError('AP initial information identity mismatch')
        rows.extend(use)
        publics.append(dict(id=identity,role=previous['role'],gap=previous['gap'],policy=previous['policy'],pre_w=previous['pre_w'],
            features=f,pre_init=init,trace_complete=True,pre_before35=True,source_actual_schedule='registered_baseline_01/run_v1/pre_inputs.json'))
        availability.append(dict(session=identity,role=previous['role'],gap=previous['gap'],pre_bins=len(use),pre_duration_s=f['duration_s'],
            excluded_unbracketed_initial_bins=discard,pre_mean_AP_c=f['pre_mean_AP_c'],AP_input_end_s=init['input_end_s'],
            pre_AP_observed_change_c=pre[-1]['ap']-pre[0]['ap'],reference_c=init['reference_c'],idle_AP_at35_c=idle_AP(init,35.),
            idle_AP_at120_c=idle_AP(init,120.),initial_state_reused=True,future_AP_used=False,live_export_available=False))
    old.old.write(out/'pre_features.json',publics)
    for name,data in [('pre_bins',rows),('availability',availability)]:old.old.prior.prior.old.scope_api.tail.s.csv_write(out/(name+'.csv'),data)
    sources=dict(old.assets(prior)['sources'])
    for p in ('tools/d1_ap_conditioned_power.py','tools/d1_ap_preparation_memory.py',
              'docs/results/ap_conditioned_power_01/analysis_contract.json','docs/results/registered_baseline_01/run_v1/pre_bins.csv',
              'docs/results/registered_baseline_01/run_v1/pre_inputs.json','docs/results/registered_baseline_01/run_v1/candidate_30.json',
              'docs/results/registered_baseline_01/run_v1/candidate_180.json','docs/results/registered_baseline_01/run_v1/candidate_final.json',
              'docs/results/preboundary_evidence_01/run_v1/expanded_pre.json','docs/results/preboundary_evidence_01/run_v1/initial_states.csv'):
        sources[p]=old.old.sha(ROOT/p)
    old.old.write(out/'registration.json',dict(id='AP-CONDITIONED-POWER-PC-01',sources=sources,
        inputs={p:old.old.sha(out/p) for p in ('pre_features.json','pre_bins.csv','availability.csv')},
        development_ids=[p['id'] for p in publics if p['role']=='development'],
        evaluation_ids=[p['id'] for p in publics if p['role']=='confirmation'],contract=old.old.read(BUNDLE/'analysis_contract.json')))


def assets(out):
    r=old.old.read(out/'registration.json')
    for p,h in r['sources'].items():
        if old.old.sha(ROOT/p)!=h:raise ValueError('registered source changed '+p)
    for p,h in r['inputs'].items():
        if old.old.sha(out/p)!=h:raise ValueError('registered pre information changed '+p)
    return r


def public_cases(out):
    previous={p['id']:p for p in old.old.read(old.BUNDLE/'run_v1/pre_inputs.json')}
    return [dict(p,actual=previous[p['id']]['actual']) for p in old.old.read(out/'pre_features.json')]


def run(output):
    out=Path(output)
    if (out/'started.json').exists():raise ValueError('PC analysis consumed; no automatic restart')
    reg=assets(out);start=time.monotonic();calls=0
    old.old.write(out/'started.json',dict(id=reg['id'],device_commands=0,status='PC analysis started'))
    try:
        data=table(out/'pre_bins.csv')
        for r in data:
            for k in ('lo_s','hi_s','other_rate_core_s_per_s','mean_power_W','latest_power_event_s','pre_AP_mean_c'):r[k]=float(r[k])
            r['gap']=int(r['gap'])
        dev=[r for r in data if r['session'] in reg['development_ids']];models={};hashes={}
        for family in FAMILIES:
            for gap in (30,180,None):
                calls+=1;key=family+'_'+(str(gap) if gap else 'final')
                old.old.write(out/('fit_started_'+key+'.json'),dict(call=calls,max=6,excluded_gap=gap,family=family))
                model=fit([r for r in dev if r['gap']!=gap],reg['development_ids'],family);models[key]=model
                old.old.write(out/('candidate_'+key+'.json'),model);hashes[key]=old.old.sha(out/('candidate_'+key+'.json'))
        old.old.write(out/'fit_receipt.json',dict(status='fixed_before_future_evaluation',formal_fits=calls,model_hashes=hashes,
            registration_sha256=old.old.sha(out/'registration.json'),AP_fits=0,new_local_AP_initializations=0,posthoc_family_choice=True))
        cases={c['id']:c for c in old.old.history()};previous={p['id']:p for p in old.old.read(old.BUNDLE/'run_v1/pre_inputs.json')}
        original=old.old.read(old.old.prior.prior.old.analysis.j.m.MODEL);fixed,_=old.old.prior.prior.read_candidate(old.old.prior.prior.BUNDLE/'run_v1')
        heads=dict(original_frozen=dict(idle_bias_w=0.,increments=original['energy_increment_w']),zero_offset=fixed)
        errors=[];curves=[];baseline_paths=[];pairs=[];summary=[]
        for p in public_cases(out):
            c=cases[p['id']];key=str(p['gap']) if p['role']=='development' else 'final'
            new={family:models[family+'_'+key] for family in FAMILIES}
            prior=old.old.read(old.BUNDLE/('run_v1/candidate_'+key+'.json'))
            last=max(35.,c['last_lane_s'] or 35.)
            windows=[('reference120',0.,120.),('future85',35.,120.),('post_lane_idle',last,120.)]
            if last>35:windows.append(('work_present',35.,last))
            for head,power in heads.items():
                def predictions(lo,hi):
                    values=dict(P50=old.old.prior.prior.energy(p,p['actual'],power,lo,hi),
                        PRIOR_FULL_CPU=old.predict(previous[p['id']],prior,power,lo,hi,opt_in=True));reasons={}
                    for family in FAMILIES:
                        try:values[family]=prediction(p,new[family],power,lo,hi,opt_in=True)
                        except ValueError as error:values[family]=None;reasons[family]=str(error)
                    return values,reasons
                for phase,lo,hi in windows:
                    cov=old.old.prior.prior.old.observed.measured_energy(c,lo,hi);obs=cov['full_energy_j'];values,reasons=predictions(lo,hi)
                    for method,y in values.items():
                        errors.append(dict(session=p['id'],role=p['role'],gap=p['gap'],policy=p['policy'],head=head,method=method,
                            phase=phase,lo_s=lo,hi_s=hi,**cov,predicted_J=y,signed_J=y-obs if y is not None and obs is not None else None,
                            absolute_J=abs(y-obs) if y is not None and obs is not None else None,
                            relative_signed=(y-obs)/obs if y is not None and obs else None,
                            unsupported_reason=reasons.get(method,''),future_AP_or_power_used_as_inputs=False))
                for t in range(1,121):
                    values,_=predictions(0.,float(t));obs=old.old.prior.prior.old.observed.measured_energy(c,0.,float(t))['full_energy_j']
                    curves.append(dict(session=p['id'],role=p['role'],head=head,t_s=t,observed_J=obs,**{k+'_J':v for k,v in values.items()}))
            for t in range(35,121):
                baseline_paths.append(dict(session=p['id'],role=p['role'],t_s=t,idle_AP_counterfactual_c=idle_AP(p['pre_init'],float(t)),
                    pre_matched_mean_AP_c=p['features']['pre_mean_AP_c'],P50_W=p['pre_w'],
                    MATCH_CPU_W=baseline(p,new['MATCH_CPU'],float(t)),CPU_AP_W=baseline(p,new['CPU_AP'],float(t)),
                    actual_target_heating_in_baseline=False,future_AP_used=False))
        for role in ('development','confirmation'):
            for head in heads:
                for phase in ('reference120','future85','post_lane_idle','work_present'):
                    for method in METHODS:
                        allrows=[r for r in errors if r['role']==role and r['head']==head and r['phase']==phase and r['method']==method]
                        use=[r for r in allrows if r['absolute_J'] is not None]
                        if not allrows:continue
                        base={r['session']:r for r in errors if r['role']==role and r['head']==head and r['phase']==phase and r['method']=='P50'}
                        summary.append(dict(role=role,head=head,phase=phase,method=method,planned_sessions=len(allrows),eligible_sessions=len(use),
                            mean_absolute_J=float(np.mean([r['absolute_J'] for r in use])) if use else None,
                            mean_signed_J=float(np.mean([r['signed_J'] for r in use])) if use else None,
                            maximum_absolute_J=max((r['absolute_J'] for r in use),default=None),
                            improved_vs_P50=sum(r['absolute_J']<base[r['session']]['absolute_J']-1e-9 for r in use),
                            worsened_vs_P50=sum(r['absolute_J']>base[r['session']]['absolute_J']+1e-9 for r in use)))
                        if phase=='reference120':
                            for gap in (30,180):
                                group=[r for r in allrows if r['gap']==gap and not r['session'].endswith('_C0')]
                                cpu=next(r for r in group if r['session'].endswith('_CPU'));par=next(r for r in group if r['session'].endswith('_PAR'))
                                err=cpu['signed_J']-par['signed_J'] if cpu['signed_J'] is not None and par['signed_J'] is not None else None
                                pairs.append(dict(role=role,gap=gap,head=head,method=method,signed_difference_error_J=err,
                                    absolute_difference_error_J=abs(err) if err is not None else None,causal_policy_effect=False))
        for name,rows in [('energy_errors',errors),('energy_curves',curves),('baseline_paths',baseline_paths),('summary',summary),('policy_difference_errors',pairs)]:
            old.old.prior.prior.old.scope_api.tail.s.csv_write(out/(name+'.csv'),rows)
        old.old.write(out/'receipt.json',dict(status='bounded_AP_power_association_evaluation_complete',formal_fits=calls,
            new_family=1,matched_pre_CPU_ablation=True,sessions=12,development=6,already_seen_confirmation=6,
            AP_fits=0,new_AP_initializations=0,device_commands=0,new_plan=0,environment_simulations=0,
            elapsed_s=time.monotonic()-start,posthoc=True,default_changed=False,RL_changed=False,strict_support=False,
            experiment_ready=False,accuracy_pass=None,automatic_refit=False,live_feature_delivery_implemented=False))
        print(old.old.prior.prior.terminal_json([r for r in summary if r['role']=='confirmation' and r['phase']=='reference120']))
    except BaseException:
        old.old.write(out/'FAIL.json',dict(original_stack=traceback.format_exc(),fits_started=calls,automatic_retry=False,device_commands=0));raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--action',choices=('prepare','run'),required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if a.action=='prepare':prepare(a.output)
    else:run(a.output)


if __name__=='__main__':main()
