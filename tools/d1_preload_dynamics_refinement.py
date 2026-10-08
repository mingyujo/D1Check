"""Two fixed preload-only estimator changes; no post-load fitting or defaults."""
import argparse
import copy
import math
from pathlib import Path
import numpy as np
from tools import d1_joint_model_refinement as j

BUNDLE=j.m.ROOT/'docs/results/preload_dynamics_refinement_01'
NAMES=('FROZEN','E_PRE_TRANSIENT','AP_FREE_INITIAL','COMBINED_DIAGNOSTIC')


def energy_initial(c):
    # Validate clipped coverage without using target observations outside this interval.
    j.m.integral(c,-20,30)
    use=[(t,w) for t,w in zip(c['power_t'],c['power_w']) if -20<=t<=30]
    t=np.array([z[0] for z in use]);y=np.array([z[1] for z in use],dtype=float)
    if len(t)<20 or t[-1]-t[0]<40 or not np.isfinite(y).all():raise ValueError('insufficient preload power')
    x=np.column_stack((np.ones(len(t)),np.exp(-(t+20)/30)));norm=np.linalg.norm(x,axis=0)
    scaled=x/norm;sv=np.linalg.svd(scaled,compute_uv=False)
    if sv[-1]<=sv[0]*1e-12:raise ValueError('preload power transient unidentifiable')
    b,z=np.linalg.lstsq(scaled,y,rcond=None)[0]/norm;p35=b+z*math.exp(-55/30)
    if not np.isfinite([b,z,p35]).all() or min(b,p35)<=0:raise ValueError('nonpositive baseline forecast; no clipping')
    return dict(reference_w=float(b),transient_at_minus20_w=float(z),predicted_35_w=float(p35),tau_s=30.,
                condition=float(sv[0]/sv[-1]),samples=len(t),input_start_s=float(t[0]),input_end_s=float(t[-1]),
                preload_rmse_w=float(np.sqrt(np.mean((x@np.array([b,z])-y)**2))),
                physical_equilibrium_identified=False)


def ap_initial(pre,model):
    beta=model['ap']['beta'];tau=30.
    j.h.memory.initialize(pre,beta,tau)  # Existing preload count/finite/gap/bracket checks.
    t0=pre[0]['t'];t=np.array([p['t']-t0 for p in pre]);y=np.array([p['ap'] for p in pre])
    x=np.array([[1.,math.exp(-beta*z),j.h.memory.convolution(beta,tau,z)] for z in t]);norm=np.linalg.norm(x,axis=0)
    scaled=x/norm;sv=np.linalg.svd(scaled,compute_uv=False)
    if sv[-1]<=sv[0]*1e-12:raise ValueError('free initial AP unidentifiable')
    r,a,h=np.linalg.lstsq(scaled,y,rcond=None)[0]/norm
    if not np.isfinite([r,a,h]).all():raise ValueError('nonfinite AP initial state')
    return dict(reference_c=float(r),estimated_first_ap_c=float(r+a),h_first_c_per_s=float(h),
                h_last_c_per_s=float(h*math.exp(-t[-1]/tau)),anchor_s=pre[-1]['t'],anchor_ap_c=pre[-1]['ap'],
                samples=len(t),input_end_s=pre[-1]['hi'],scaled_condition=float(sv[0]/sv[-1]),
                preload_rmse_c=float(np.sqrt(np.mean((x@np.array([r,a,h])-y)**2))),
                reference_is_ambient=False,latent_is_measured_internal_temperature=False)


def predict_ap(public,model,initial):
    j.m.thermal.basis(dict(inputs=public),model['ap']['parameters'],model['ap']['beta'])
    if model['ap']['g']!=0:raise ValueError('registered g0 only')
    slopes=model['ap']['parameters']['ap_slope_at_30_c_per_s'];beta=model['ap']['beta']
    zero={k:slopes['resident_idle'] for k in slopes}
    a=np.array(j.h.memory._propagate(public['segments'],public['query_s'],zero,beta,30.,0.,initial))
    b=np.array(j.h.memory._propagate(public['segments'],public['query_s'],slopes,beta,30.,0.,initial))
    pred=a+model['ap']['k']*(b-a)
    if not np.isfinite(pred).all():raise ValueError('nonfinite AP prediction')
    return pred.tolist()


def predict_energy(pre_w,segments,model,initial,t):
    if not 0<=t<=120:raise ValueError('common energy window')
    if t<=35:base=pre_w*t
    else:
        dt=t-35;base=pre_w*35+initial['reference_w']*dt+(initial['predicted_35_w']-initial['reference_w'])*30*(-math.expm1(-dt/30))
    return float(base+j.m.base.exposure(segments,0,t)@np.array([model['energy_increment_w'][k] for k in j.m.base.STATES]))


def score(c,model,name,mode,initials):
    seg=c['actual'] if mode=='A_conditional' else c['forecast'];use_e=name in ('E_PRE_TRANSIENT','COMBINED_DIAGNOSTIC');use_ap=name in ('AP_FREE_INITIAL','COMBINED_DIAGNOSTIC')
    e=initials['energy'] if use_e else None;ap=initials['ap'] if use_ap else None
    ef=(lambda t:predict_energy(c['pre_w'],seg,model,e,t)) if not use_e or e is not None else None
    if not use_e:ef=lambda t:j.m.energy_prediction(c,seg,model,dict(name='FROZEN'),t)
    if use_ap and ap is None:pred=None
    elif use_ap:pred=predict_ap(j.m.case_input(c,seg)['inputs'],model,ap)
    else:pred=j.m.predict(c,seg,model,dict(name='FROZEN'))[0]
    observed=j.m.integral(c,0,120)
    result=dict(id=c['id'],block=c['evaluation_block'],fit_block=c['fit_block'],role=c['role'],policy=c['policy'],mode=mode,candidate=name,
                observed_j=observed,predicted_j=ef(120) if ef else None,signed_j=ef(120)-observed if ef else None,
                abs_j=abs(ef(120)-observed) if ef else None,relative_percent=100*abs(ef(120)-observed)/observed if ef else None,
                mae_c=None,max_absolute_error_c=None,peak_signed_error_c=None,delta_mae_c=None,
                ap_start_s=c['q'][0],ap_end_s=c['q'][-1],energy_available=ef is not None,ap_available=pred is not None)
    if pred is not None:
        result.update(j.m.base.common.score(c['ap'],pred))
        result['delta_mae_c']=float(np.mean(np.abs((np.array(pred)-pred[0])-(np.array(c['ap'])-c['ap'][0]))))
        if mode=='A_conditional':result.update(j.h.direction(c,pred))
    for label,a,b in [('pre',0,35),('load',35,c['last_lane_s']),('post',c['last_lane_s'],120)]:
        result[label+'_signed_j']=ef(b)-ef(a)-j.m.integral(c,a,b) if ef else None
        ix=[i for i,t in enumerate(c['q']) if a<=t<=b]
        result[label+'_ap_mae_c']=float(np.mean([abs(pred[i]-c['ap'][i]) for i in ix])) if pred is not None and ix else None
    if ef and abs(sum(result[k+'_signed_j'] for k in ('pre','load','post'))-result['signed_j'])>1e-8:raise ValueError('partition mismatch')
    windows=[]
    for t in range(0,120,5):
        states=sorted({s['state'] for s in seg if min(t+5,s['end_s'])>max(t,s['start_s'])})
        windows.append(dict(id=c['id'],mode=mode,candidate=name,start_s=t,end_s=t+5,states='|'.join(states),mixed=len(states)>1,
                            signed_j=ef(t+5)-ef(t)-j.m.integral(c,t,t+5) if ef else None))
    return result,pred,ef,windows


def summary(rows):
    result=[]
    for block,role,mode,name in sorted({(r['block'],r['role'],r['mode'],r['candidate']) for r in rows}):
        use=[r for r in rows if (r['block'],r['role'],r['mode'],r['candidate'])==(block,role,mode,name)]
        e=[r for r in use if r['energy_available']];a=[r for r in use if r['ap_available']]
        mean=lambda data,key:float(np.mean([r[key] for r in data])) if data else None
        result.append(dict(block=block,role=role,mode=mode,candidate=name,n=len(use),energy_n=len(e),ap_n=len(a),
                           energy_mae_j=mean(e,'abs_j'),energy_mape_percent=mean(e,'relative_percent'),energy_max_j=max((r['abs_j'] for r in e),default=None),
                           ap_mae_c=mean(a,'mae_c'),ap_max_c=max((r['max_absolute_error_c'] for r in a),default=None),
                           delta_mae_c=mean(a,'delta_mae_c'),absolute_peak_mae_c=mean([dict(r,peak_abs=abs(r['peak_signed_error_c'])) for r in a],'peak_abs'),
                           opposite_cooling=sum(r.get('cooling_opposite') is True for r in a)))
    return result


def run(output):
    if output.exists():raise FileExistsError('new output required')
    contract=j.m.read(BUNDLE/'contract.json')
    for p,digest in contract['input_hashes'].items():
        if j.m.sha(j.m.ROOT/p)!=digest:raise ValueError('input identity')
    output.mkdir(parents=True);cases,_=j.panel();model=j.m.read(j.m.MODEL);initials={};initial_rows=[]
    # Both initializers only consume pre35 observations; no target score has been read here.
    for c in cases:
        initials[c['id']]={}
        for component,func in [('energy',lambda:energy_initial(c)),('ap',lambda:ap_initial(c['pre'],model))]:
            try:value=func();error=None
            except ValueError as exc:value=None;error=str(exc)
            initials[c['id']][component]=value
            initial_rows.append(dict(id=c['id'],role=c['role'],component=component,available=value is not None,error=error,**(value or {})))
    dev=[];windows=[];paths=[]
    for c in cases:
        if c['role']!='development':continue
        for name in NAMES:
            row,*_=score(c,model,name,'A_conditional',initials[c['id']]);dev.append(row)
    gates={}
    for name,metrics,available in [('E_PRE_TRANSIENT',('abs_j',),'energy_available'),('AP_FREE_INITIAL',('mae_c','max_absolute_error_c'),'ap_available')]:
        checks=[]
        for block in sorted({c['fit_block'] for c in cases if c['role']=='development'}):
            original=[r for r in dev if r['fit_block']==block and r['candidate']=='FROZEN'];candidate=[r for r in dev if r['fit_block']==block and r['candidate']==name]
            checks.append(dict(block=block,available=all(r[available] for r in candidate),
                               **{metric:dict(original=float(np.mean([r[metric] for r in original])),candidate=float(np.mean([r[metric] for r in candidate])) if all(r[available] for r in candidate) else None) for metric in metrics}))
        nonworse=all(x['available'] and all(x[k]['candidate']<=x[k]['original']+1e-10 for k in metrics) for x in checks)
        gates[name]=dict(selected=nonworse and any(x[k]['candidate']<x[k]['original']-1e-10 for x in checks for k in metrics),checks=checks)
    freeze=dict(id=contract['id'],utc=j.now(),contract_sha256=j.m.sha(BUNDLE/'contract.json'),development_ids=[c['id'] for c in cases if c['role']=='development'],
                gates=gates,initializers_fixed=True,no_population_fit=True,physical_coefficients_changed=False,default=False)
    j.m.write(output/'development_freeze.json',freeze)
    # Diagnostics fixed before evaluation. Rejected components are retained, not adopted on target results.
    rows=dev[:]
    for c in cases:
        if c['role']=='development':continue
        for mode in ['A_conditional']+(['B_arrival'] if 'forecast' in c else []):
            for name in NAMES:
                row,pred,ef,bins=score(c,model,name,mode,initials[c['id']]);rows.append(row);windows.extend(bins)
                if mode=='A_conditional':
                    if pred is not None:paths.extend(dict(id=c['id'],candidate=name,t_s=t,observed_ap_c=o,predicted_ap_c=p,signed_ap_c=p-o) for t,o,p in zip(c['q'],c['ap'],pred))
                    if ef:paths.extend(dict(id=c['id'],candidate=name,t_s=t,observed_j=j.m.integral(c,0,t),predicted_j=ef(t),signed_j=ef(t)-j.m.integral(c,0,t)) for t in range(121))
    compare=summary(rows)
    for name,data in [('session_errors.csv',rows),('comparison.csv',compare),('initial_states.csv',initial_rows),('windows.csv',windows),('paths.csv',paths)]:j.m.table(output/name,data)
    j.m.write(output/'summary.json',dict(id=contract['id'],utc=j.now(),component_structures=2,combined_new_fit=False,population_fit_calls=0,preload_initializations=58,
                                        development_gate=gates,evaluation_sessions=20,development_sessions=9,rows=len(rows),comparison=compare,
                                        freeze_sha256=j.m.sha(output/'development_freeze.json'),model_sha256=j.m.sha(j.m.MODEL),
                                        default_changed=False,posthoc=True,device_commands=0,policy_simulations=0,rl_training=0,accuracy_pass=None,experiment_ready=False))
    print(__import__('json').dumps(dict(gates=gates,rows=len(rows),model_unchanged=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);run(Path(p.parse_args().output))
