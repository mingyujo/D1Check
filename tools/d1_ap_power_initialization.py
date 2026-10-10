"""One pre-power-driven preparation-state initializer. No default/RL/device path."""
import argparse
import math
import time
import traceback
from pathlib import Path
import numpy as np
from tools import d1_ap_conditioned_power as previous
from tools import d1_ap_preparation_memory as memory
from tools import d1_energy_ap_zero_offset as energy
from tools import d1_session_contrast_cost as archive

ROOT=archive.ROOT
BUNDLE=ROOT/'docs/results/ap_power_initialization_01'
AP_VARIANTS=('registered_idle_control','pre_power_forcing')


def pre_power(c,pre):
    previous.validate_pre(pre);first,last=pre[0]['t'],pre[-1]['t']
    if last-first<55:raise ValueError('insufficient registered pre AP span')
    pairs=[(float(t),float(w)) for t,w in zip(c['power_t'],c['power_w']) if t<=last]
    if not pairs or any(not math.isfinite(t) or not math.isfinite(w) or w<=0 for t,w in pairs) or any(
            b[0]<=a[0] for a,b in zip(pairs,pairs[1:])):
        raise ValueError('invalid pre power clock/value')
    i=max((i for i,p in enumerate(pairs) if p[0]<=first),default=-1)
    if i<0 or first-pairs[i][0]>2.5:raise ValueError('initial pre power unavailable; no filling')
    pairs=pairs[i:];segments=[]
    for j,(event,w) in enumerate(pairs):
        lo=max(first,event);hi=min(last,pairs[j+1][0] if j+1<len(pairs) else last)
        if hi<=lo:continue
        if hi-event>2.5:raise ValueError('pre power gap/age>2.5s')
        segments.append(dict(lo_s=lo,hi_s=hi,power_W=w,source_event_s=event))
    if not segments or segments[0]['lo_s']!=first or segments[-1]['hi_s']!=last or any(
            a['hi_s']!=b['lo_s'] for a,b in zip(segments,segments[1:])):
        raise ValueError('incomplete causal pre power')
    mean=sum((r['hi_s']-r['lo_s'])*r['power_W'] for r in segments)/(last-first)
    return segments,mean


def advance_forcing(T,H,drive,beta,tau,dt):
    if not all(math.isfinite(v) for v in (T,H,drive,beta,tau,dt)) or min(beta,tau)<=0 or dt<0:
        raise ValueError('invalid fixed preparation response')
    eb=math.exp(-beta*dt);eh=math.exp(-dt/tau)
    return T*eb+drive*(1-eb)/beta+(H-drive)*memory.convolution(beta,tau,dt), drive+(H-drive)*eh


def forcing_response(p,beta,tau=30.):
    pre=p['pre_AP'];previous.validate_pre(pre);q=[r['t'] for r in pre];segments=p['pre_power_segments'];mean=p['pre_power_mean_W']
    if len(q)<15 or q[-1]-q[0]<55 or not math.isfinite(mean) or mean<=0:
        raise ValueError('insufficient/invalid pre information')
    if not segments or segments[0]['lo_s']!=q[0] or segments[-1]['hi_s']!=q[-1]:raise ValueError('pre power/AP span mismatch')
    for i,s in enumerate(segments):
        if not all(math.isfinite(s[k]) for k in ('lo_s','hi_s','power_W','source_event_s')) or not s['source_event_s']<=s['lo_s']<s['hi_s']<35 or s['power_W']<=0 or s['hi_s']-s['source_event_s']>2.5:
            raise ValueError('invalid/future held power')
        if i and segments[i-1]['hi_s']!=s['lo_s']:raise ValueError('pre power discontinuity')
    calculated=sum((s['hi_s']-s['lo_s'])*s['power_W'] for s in segments)/(q[-1]-q[0])
    if abs(calculated-mean)>1e-10:raise ValueError('pre reference mismatch')
    T=H=0.;pos=0;zt=[];zh=[]
    for s in segments:
        start,end=s['lo_s'],s['hi_s'];u=s['power_W']-mean
        while pos<len(q) and q[pos]<=end:
            a,b=advance_forcing(T,H,u,beta,tau,q[pos]-start);zt.append(a);zh.append(b);pos+=1
        T,H=advance_forcing(T,H,u,beta,tau,end-start)
    if pos!=len(q):raise ValueError('incomplete pre response')
    return np.array(zt),np.array(zh)


def design(p,beta):
    pre=p['pre_AP'];zt,zh=forcing_response(p,beta);t0=pre[0]['t'];y0=pre[0]['ap']
    d=np.array([r['t']-t0 for r in pre]);eb=np.exp(-beta*d)
    x=np.column_stack((1-eb,[memory.convolution(beta,30.,float(dt)) for dt in d]))
    norm=np.linalg.norm(x,axis=0)
    if np.any(norm<=0):raise ValueError('pre initial-state rank')
    singular=np.linalg.svd(x/norm,compute_uv=False)
    if singular[-1]<=singular[0]*1e-12:raise ValueError('pre state unidentified')
    target=np.array([r['ap'] for r in pre])-y0*eb
    return x,target,zt,zh,eb,norm,singular


def solve(x,y,norm):
    return np.linalg.lstsq(x/norm,y,rcond=None)[0]/norm


def fit(cases,ids,beta):
    if len(cases)<3 or len({p['id'] for p in cases})!=len(cases) or any(p['role']!='development' or p['id'] not in ids for p in cases):
        raise ValueError('registered development sessions only')
    z=[];y=[];parts=[];conditions=[];full_information=0.
    for p in cases:
        x,target,zt,zh,eb,norm,singular=design(p,beta)
        zr=zt-x@solve(x,zt,norm);yr=target-x@solve(x,target,norm)
        w=1/math.sqrt(len(target)*len(cases));z.extend(zr*w);y.extend(yr*w)
        parts.append((zr,w,eb));full_information+=float(zt@zt)*w*w
        three=np.column_stack((x,zt));n=np.linalg.norm(three,axis=0)
        if n[-1]<=0:raise ValueError('no pre power variation; gain not identified')
        sv=np.linalg.svd(three/n,compute_uv=False)
        conditions.append(dict(session=p['id'],AP_samples=len(target),scaled3_condition=float(sv[0]/sv[-1]) if sv[-1]>0 else None))
    z=np.array(z);y=np.array(y);info=float(z@z)
    if info<=np.finfo(float).eps or info<=full_information*1e-24:
        raise ValueError('pre power gain not identified beyond R/H; no invented coefficient')
    unconstrained=float(z@y/info);gain=max(0.,unconstrained)
    sensitivity=0.
    for zr,w,eb in parts:
        a=zr*w*w/info;a=a.copy();a[0]-=float(a@eb)
        sensitivity+=.05*float(np.abs(a).sum())
    return dict(version='pre-power-preparation-initialization-v1',gain_C_per_J=gain,unconstrained_gain_C_per_J=unconstrained,
        residual_power_information=info,residual_fraction=info/full_information,development_ids=[p['id'] for p in cases],
        development_projection_bundles=len(cases),per_session_conditions=conditions,beta_fixed=beta,preparation_tau_s=30.,
        assumed_independent_pre_AP_half_step_c=.05,unconstrained_gain_worst_case_rounding_change=sensitivity,
        constrained_gain_rounding_interval=[max(0.,unconstrained-sensitivity),max(0.,unconstrained+sensitivity)],
        rounding_is_not_confidence_or_certified_sensor_accuracy=True,
        weighted_pre_residual_RMSE_c=float(np.sqrt(np.sum((gain*z-y)**2))),coefficient_count=1,
        future_targets_used=False,default=False,strict_support=False,accuracy_pass=None,experiment_ready=False)


def initialize(p,model):
    beta=model['beta_fixed'];gain=model['gain_C_per_J']
    if not math.isfinite(gain) or gain<0 or model['preparation_tau_s']!=30.:raise ValueError('fixed gain/family')
    x,target,zt,zh,eb,norm,singular=design(p,beta)
    ref,hfirst=map(float,solve(x,target-gain*zt,norm));pre=p['pre_AP'];span=pre[-1]['t']-pre[0]['t']
    hlast=hfirst*math.exp(-span/30.)+gain*float(zh[-1]);residual=x@np.array([ref,hfirst])+gain*zt-target
    return dict(reference_c=ref,h_first_c_per_s=hfirst,h_last_c_per_s=hlast,
        anchor_s=pre[-1]['t'],anchor_ap_c=pre[-1]['ap'],input_end_s=pre[-1]['hi'],
        beta_per_s=beta,tau_s=30.,samples=len(pre),duration_s=span,
        preload_RMSE_c=float(np.sqrt(np.mean(residual**2))),pre_power_reference_W=p['pre_power_mean_W'],
        unit_power_memory_at_anchor=float(zh[-1]),power_memory_contribution_C_per_s=gain*float(zh[-1]),
        reference_is_ambient=False,latent_is_measured=False,post_anchor_power_deviation_assumed_zero=True)


def AP_predict(p,init,original,ap_model,queries,actual,*,opt_in=False):
    if not opt_in:raise ValueError('explicit offline diagnostic opt-in required')
    if not queries or any(not math.isfinite(t) or t<35 or t>180 for t in queries) or any(b<=a for a,b in zip(queries,queries[1:])):
        raise ValueError('query/horizon35..180')
    if init['anchor_s']!=p['pre_AP'][-1]['t'] or init['anchor_ap_c']!=p['pre_AP'][-1]['ap'] or init['input_end_s']>=35 or init['beta_per_s']!=original['ap']['beta'] or init['tau_s']!=30.:
        raise ValueError('pre anchor/fixed family mismatch')
    cursor=0.;states=('resident_idle',)+energy.STATES
    for s in actual:
        if abs(s['start_s']-cursor)>1e-6 or not math.isfinite(s['end_s']) or s['end_s']<=cursor or memory.state_key(s['state']) not in states:
            raise ValueError('unsupported/noncontiguous actual schedule')
        cursor=s['end_s']
    if queries[-1]>cursor:raise ValueError('query exceeds actual schedule')
    if ap_model['mode']!='LOAD_SLOW' or ap_model['beta_fixed']!=original['ap']['beta'] or ap_model['preparation_tau_s']!=30. or ap_model['tau_s']!=1920.:
        raise ValueError('frozen workload model changed')
    theta=np.array(ap_model['coefficients'])
    if theta.shape!=(5,) or not np.isfinite(theta).all() or np.any(theta<0):raise ValueError('fixed AP coefficients')
    zero=dict(init,reference_c=0.,anchor_ap_c=0.,h_last_c_per_s=0.)
    fast=dict(resident_idle=0.,**dict(zip(energy.STATES,map(float,theta[:4]))))
    direct=np.array(memory._propagate(actual,queries,fast,init['beta_per_s'],30.,0.,zero))
    proxy=dict(resident_idle=0.,**original['energy_increment_w'])
    slow=np.array(memory._propagate(actual,queries,proxy,1/1920.,30.,0.,zero))*theta[4]
    initial=np.array([memory.advance(init['anchor_ap_c'],init['h_last_c_per_s'],0.,init['reference_c'],init['beta_per_s'],30.,0.,t-init['anchor_s'])[0] for t in queries])
    y=initial+direct+slow
    if not np.isfinite(y).all():raise ValueError('nonfinite AP output')
    return y.tolist()


def prepare(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    prior=previous.BUNDLE/'run_v1';previous.assets(prior)
    all_cases={c['id']:c for c in previous.old.old.history()}
    prefile=ROOT/'docs/results/preboundary_evidence_01/run_v1/expanded_pre.json'
    records=previous.old.old.read(prefile);data=[];availability=[]
    for row in records:
        c=all_cases[row['id']];segments,mean=pre_power(c,row['expanded_pre'])
        data.append(dict(id=c['id'],role=c['role'],gap=c['gap'],policy=c['policy'],pre_AP=row['expanded_pre'],
            pre_power_segments=segments,pre_power_mean_W=mean))
        availability.append(dict(session=c['id'],role=c['role'],gap=c['gap'],AP_samples=len(row['expanded_pre']),power_segments=len(segments),
            pre_start_s=segments[0]['lo_s'],pre_end_s=segments[-1]['hi_s'],last_power_event_s=segments[-1]['source_event_s'],
            power_ZOH_mean_W=mean,power_events_before_AP_anchor=True,AP_return_before35=True,new_measurement=False))
    previous.old.old.write(out/'pre_inputs.json',data);energy.old.scope_api.tail.s.csv_write(out/'availability.csv',availability)
    sources=dict(previous.assets(prior)['sources'])
    for path in ('tools/d1_ap_power_initialization.py','tools/d1_ap_preparation_memory.py',
        'docs/results/ap_power_initialization_01/analysis_contract.json',
        'docs/results/preboundary_evidence_01/run_v1/expanded_pre.json','docs/results/preboundary_evidence_01/run_v1/initial_states.csv',
        'docs/results/preboundary_evidence_01/run_v1/AP_paths.csv','docs/results/ap_conditioned_power_01/run_v1/pre_features.json'):
        sources[path]=previous.old.old.sha(ROOT/path)
    for key in ('30','180','final'):
        path='docs/results/ap_conditioned_power_01/run_v1/candidate_CPU_AP_'+key+'.json';sources[path]=previous.old.old.sha(ROOT/path)
    previous.old.old.write(out/'registration.json',dict(id='AP-POWER-INITIALIZATION-PC-01',sources=sources,
        inputs={name:previous.old.old.sha(out/name) for name in ('pre_inputs.json','availability.csv')},
        development_ids=[p['id'] for p in data if p['role']=='development'],evaluation_ids=[p['id'] for p in data if p['role']=='confirmation'],
        contract=previous.old.old.read(BUNDLE/'analysis_contract.json')))


def assets(out):
    reg=previous.old.old.read(out/'registration.json')
    for path,h in reg['sources'].items():
        if previous.old.old.sha(ROOT/path)!=h:raise ValueError('registered source changed '+path)
    for path,h in reg['inputs'].items():
        if previous.old.old.sha(out/path)!=h:raise ValueError('registered pre input changed '+path)
    return reg


def run(output):
    out=Path(output)
    if (out/'started.json').exists():raise ValueError('analysis consumed; no automatic restart')
    reg=assets(out);started=time.monotonic();count=0
    previous.old.old.write(out/'started.json',dict(id=reg['id'],status='PC analysis started',device_commands=0))
    try:
        data=previous.old.old.read(out/'pre_inputs.json');dev=[p for p in data if p['id'] in reg['development_ids']]
        original=previous.old.old.read(energy.old.analysis.j.m.MODEL);ap=previous.old.old.read(ROOT/'docs/results/ap_tail_identification_01/run_v2/candidates.json')['LOAD_SLOW']
        models={};hashes={}
        for gap in (30,180,None):
            count+=1;key=str(gap) if gap else 'final'
            previous.old.old.write(out/('fit_started_'+key+'.json'),dict(call=count,max=3,excluded_gap=gap))
            model=fit([p for p in dev if p['gap']!=gap],reg['development_ids'],original['ap']['beta']);models[key]=model
            previous.old.old.write(out/('candidate_'+key+'.json'),model);hashes[key]=previous.old.old.sha(out/('candidate_'+key+'.json'))
        previous.old.old.write(out/'fit_receipt.json',dict(status='gain_frozen_before_future_evaluation',global_gain_fits=count,
            development_projection_bundles=12,model_hashes=hashes,registration_sha256=previous.old.old.sha(out/'registration.json'),
            future_targets_used=False,posthoc_family_choice=True))
        lookup={c['id']:c for c in previous.old.old.history()};old_init={r['session']:r for r in previous.table(ROOT/'docs/results/preboundary_evidence_01/run_v1/initial_states.csv') if r['variant']=='registered_idle_pre'}
        public_power={p['id']:p for p in previous.public_cases(previous.BUNDLE/'run_v1')}
        power_zero,_=energy.read_candidate(energy.BUNDLE/'run_v1');powerheads=dict(original_frozen=dict(idle_bias_w=0.,increments=original['energy_increment_w']),zero_offset=power_zero)
        metrics=[];paths=[];states=[];J=[];Jcurves=[]
        for p in data:
            c=lookup[p['id']];key=str(p['gap']) if p['role']=='development' else 'final';init=initialize(p,models[key]);states.append(dict(session=p['id'],role=p['role'],**init))
            old=old_init[p['id']];control={k:float(old[k]) for k in ('reference_c','h_last_c_per_s','anchor_s','anchor_ap_c','input_end_s')};control.update(beta_per_s=original['ap']['beta'],tau_s=30.)
            query=[float(q) for q in c['q'] if 35<=q<=180];observed=[float(y) for q,y in zip(c['q'],c['ap']) if 35<=q<=180]
            predictions={name:AP_predict(p,state,original,ap,query,c['actual'],opt_in=True) for name,state in zip(AP_VARIANTS,(control,init))}
            last=max(35.,c['last_lane_s'] or 35.)
            for name,y in predictions.items():
                windows=[('common85',35.,120.),('full_AP',35.,180.),('post_lane_idle',last,180.)]
                if last>35:windows.append(('work_present',35.,last))
                for phase,lo,hi in windows:
                    use=[i for i,q in enumerate(query) if lo<=q<=hi]
                    if len(use)<2:continue
                    obs=np.array([observed[i] for i in use]);pred=np.array([y[i] for i in use]);err=pred-obs
                    metrics.append(dict(session=p['id'],role=p['role'],gap=p['gap'],policy=p['policy'],variant=name,phase=phase,
                        requested_lo_s=lo,requested_hi_s=hi,first_sample_s=query[use[0]],last_sample_s=query[use[-1]],samples=len(use),
                        MAE_c=float(np.mean(np.abs(err))),max_absolute_c=float(np.max(np.abs(err))),peak_signed_c=float(pred.max()-obs.max()),
                        observed_change_c=float(obs[-1]-obs[0]),predicted_change_c=float(pred[-1]-pred[0]),direction_match=bool(np.sign(obs[-1]-obs[0])==np.sign(pred[-1]-pred[0]))))
                paths.extend(dict(session=p['id'],role=p['role'],t_s=q,variant=name,observed_c=obs,predicted_c=pred,residual_c=pred-obs) for q,obs,pred in zip(query,observed,y))
            ep=public_power[p['id']];relation=previous.old.old.read(previous.BUNDLE/('run_v1/candidate_CPU_AP_'+key+'.json'))
            for head,fixed in powerheads.items():
                for name,state in zip(AP_VARIANTS,(control,init)):
                    pub=dict(ep,pre_init=state)
                    for phase,lo,hi in [('reference120',0.,120.),('future85',35.,120.),('post_lane_idle',last,120.)]:
                        cov=energy.old.observed.measured_energy(c,lo,hi);obs=cov['full_energy_j'];reason=''
                        try:y=previous.prediction(pub,relation,fixed,lo,hi,opt_in=True)
                        except ValueError as error:y=None;reason=str(error)
                        J.append(dict(session=p['id'],role=p['role'],head=head,variant=name,phase=phase,lo_s=lo,hi_s=hi,
                            observed_J=obs,predicted_J=y,signed_J=y-obs if y is not None and obs is not None else None,
                            absolute_J=abs(y-obs) if y is not None and obs is not None else None,
                            unsupported_reason=reason,energy_relation_is_previous_rejected_candidate=True,energy_fits=0))
                    for t in range(1,121):
                        obs=energy.old.observed.measured_energy(c,0.,float(t))['full_energy_j']
                        try:y=previous.prediction(pub,relation,fixed,0.,float(t),opt_in=True)
                        except ValueError:y=None
                        Jcurves.append(dict(session=p['id'],role=p['role'],head=head,variant=name,t_s=t,observed_J=obs,predicted_J=y,signed_J=y-obs if y is not None and obs is not None else None))
        for name,rows in [('AP_errors',metrics),('AP_paths',paths),('initial_states',states),('energy_link_errors',J),('energy_link_curves',Jcurves)]:energy.old.scope_api.tail.s.csv_write(out/(name+'.csv'),rows)
        summary=[]
        for role in ('development','confirmation'):
            for phase in ('common85','full_AP','post_lane_idle','work_present'):
                for name in AP_VARIANTS:
                    use=[r for r in metrics if r['role']==role and r['phase']==phase and r['variant']==name]
                    if use:summary.append(dict(role=role,phase=phase,variant=name,sessions=len(use),AP_mean_MAE_c=float(np.mean([r['MAE_c'] for r in use])),
                        AP_mean_max_c=float(np.mean([r['max_absolute_c'] for r in use])),AP_mean_abs_peak_c=float(np.mean([abs(r['peak_signed_c']) for r in use])),direction_matches=sum(r['direction_match'] for r in use)))
        energy.old.scope_api.tail.s.csv_write(out/'summary.csv',summary)
        previous.old.old.write(out/'receipt.json',dict(status='bounded_pre_power_initialization_evaluated',global_gain_fits=count,development_projection_bundles=12,
            evaluated_local_pre_state_estimates=12,AP_path_replays=24,energy_fits=0,energy_link_is_rejected_relation_diagnostic=True,
            sessions=12,development=6,already_seen_confirmation=6,elapsed_s=time.monotonic()-started,
            device_commands=0,new_plan=0,environment_simulations=0,default_changed=False,RL_changed=False,strict_support=False,experiment_ready=False,accuracy_pass=None,automatic_refit=False))
        print(energy.terminal_json(summary))
    except BaseException:
        previous.old.old.write(out/'FAIL.json',dict(original_stack=traceback.format_exc(),global_fits_started=count,automatic_retry=False,device_commands=0));raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--action',choices=('prepare','run'),required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if a.action=='prepare':prepare(a.output)
    else:run(a.output)


if __name__=='__main__':main()
