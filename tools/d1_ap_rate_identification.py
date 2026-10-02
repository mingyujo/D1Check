"""Posthoc fixed-rate identifiability analysis; archive-only, no device API."""
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from tools import d1_ap_preparation_memory as memory
from tools import d1_ap_model_completion as common
from tools.d1_arrival_recorded_replay_analysis import state_key

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT/'docs/results/ap_rate_identification_01'
CONTRACT = BUNDLE/'contract.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs():
    sources = {}
    def used(name):
        f = ROOT/name; sources[name] = digest(f); return common.read(f)
    old = used('docs/results/ap_preparation_memory_01/inputs.json')
    candidate = used('docs/results/ap_preparation_memory_01/final/candidate.json')
    cases = copy.deepcopy(old['cases'])
    for c in cases:
        c['role'] = 'posthoc_development' if c['id']=='idle_development' else 'previously_seen_fit_excluded'
    folder = 'docs/results/ap_memory_confirmation_01/run01'
    latest = used(folder+'/summary.json')
    for saved in latest['sessions']:
        name = saved['role']; d = used(folder+'/'+name+'/prediction_inputs.json')
        f = ROOT/folder/name/'ap_paths.csv'; sources[f.relative_to(ROOT).as_posix()] = digest(f)
        with f.open(encoding='utf-8') as stream: rows = list(csv.DictReader(stream))
        cases.append(dict(id=name,role='previously_seen_new_confirmation_fit_excluded',
            protocol='74e APK',inputs=d['case'],observed_ap_c=[float(r['observed_ap_c']) for r in rows]))
    history = used('docs/results/resident_history_01/inputs.json')
    controls = []
    for c in history['cases'][-2:]:
        ap = [dict(t=p['relative_ns']/1e9,ap=p['ap_c'],
                   lo=(p['relative_ns']-p['read_bracket_ns']/2)/1e9,
                   hi=(p['relative_ns']+p['read_bracket_ns']/2)/1e9) for p in c['ap_samples']]
        ap = [p for p in ap if p['lo']>=c['baseline_start_ns']/1e9 and p['hi']<=180]
        controls.append(dict(id=c['case'],ap=ap,states=c['states'],context=c['source_context'],
                             work_requests=c['work_requests'],baseline_start_s=c['baseline_start_ns']/1e9))
    control = controls[0]
    pre = [p for p in control['ap'] if p['hi']<35]
    post = [p for p in control['ap'] if p['lo']>=35]
    cases.append(dict(id='resident_no_load_C',role='unmatched_control_not_fit',protocol='3d8 APK',
        no_load=True,inputs=dict(preload=pre,query_s=[p['t'] for p in post],
        segments=[dict(start_s=0,end_s=180,state='idle')]),observed_ap_c=[p['ap'] for p in post]))
    return dict(cases=cases,controls=controls,parameters=old['parameters'],candidate=candidate,source_sha256=sources)


def parameters(base,beta,gain):
    if not math.isfinite(beta) or not math.isfinite(gain) or beta<=0 or gain<0:
        raise ValueError('invalid rate/gain')
    result=copy.deepcopy(base); result['ap_cooling_rate_per_s']=beta
    idle=base['ap_slope_at_30_c_per_s']['resident_idle']
    result['ap_slope_at_30_c_per_s']={k:idle+gain*(v-idle) for k,v in base['ap_slope_at_30_c_per_s'].items()}
    return result


def predict(case,base,beta,gain):
    p=parameters(base,beta,gain)
    if not case.get('no_load'):
        return memory.predict(case,p,30.,0.)
    if any(s['state']!='idle' for s in case['inputs']['segments']):
        raise ValueError('control has load')
    q=case['inputs']['query_s'];pre=case['inputs']['preload']
    if not q or any(not math.isfinite(t) for t in q) or any(b<=a or b-a>10 for a,b in zip(q,q[1:])):
        raise ValueError('invalid control targets')
    if pre[-1]['hi']>=q[0] or q[-1]>case['inputs']['segments'][-1]['end_s']:
        raise ValueError('control input/target boundary')
    init=memory.initialize(pre,beta,30.)
    ys=[memory.advance(init['anchor_ap_c'],init['h_last_c_per_s'],0,init['reference_c'],beta,30.,0.,t-init['anchor_s'])[0] for t in q]
    return ys,init


def profile(case,base,betas):
    y=np.array(case['observed_ap_c'],dtype=float); result=[]
    if not len(y) or not np.all(np.isfinite(y)): raise ValueError('invalid targets')
    for beta in betas:
        a,init=predict(case,base,float(beta),0);b,_=predict(case,base,float(beta),1)
        a=np.array(a);basis=np.array(b)-a
        if len(a)!=len(y):raise ValueError('target denominator')
        information=float(basis@basis)
        unconstrained=float(basis@(y-a)/information) if information>1e-12 else None
        gain=max(0.,unconstrained) if unconstrained is not None else None
        predicted=a if gain is None else a+gain*basis
        result.append(dict(beta_per_s=float(beta),gain=gain,unconstrained_gain=unconstrained,
            rmse_c=float(np.sqrt(np.mean((predicted-y)**2))),gain_information=information,
            reference_c=init['reference_c'],initial_condition=init['scaled_condition']))
    return result


def fit(development,base,betas):
    if development['id']!='idle_development':raise ValueError('development role required')
    rows=profile(development,base,betas)
    if not rows or any(r['gain'] is None for r in rows):raise ValueError('unidentified load gain')
    return min(rows,key=lambda r:(r['rmse_c'],r['beta_per_s'])),rows


def jacobian(case,base,beta,gain):
    eps=1e-4; columns=[]
    if gain<=0:return dict(status='gain_boundary',singular_values=None)
    for b0,k0,b1,k1 in [(beta*math.exp(-eps),gain,beta*math.exp(eps),gain),
                          (beta,gain*math.exp(-eps),beta,gain*math.exp(eps))]:
        a,_=predict(case,base,b0,k0);b,_=predict(case,base,b1,k1)
        columns.append((np.array(b)-a)/(2*eps))
    matrix=np.array(columns).T;norm=np.linalg.norm(matrix,axis=0)
    if min(norm)<1e-12:return dict(status='rank_deficient',singular_values=None)
    scaled=matrix/norm;sv=np.linalg.svd(scaled,compute_uv=False)
    return dict(status='numerical_only',singular_values=sv.tolist(),scaled_condition=float(sv[0]/sv[-1]),
                column_cosine=float(scaled[:,0]@scaled[:,1]),column_norms=norm.tolist())


def state_information(case,base):
    if case.get('no_load'):return dict(states=[],rank=0,meaning='no load coefficient information')
    p=parameters(base,base['ap_cooling_rate_per_s'],0);zero,_=memory.predict(case,p,30,0)
    states=sorted({state_key(s['state']) for s in case['inputs']['segments'] if s['state']!='idle'})
    cols=[]
    for key in states:
        changed=copy.deepcopy(p);changed['ap_slope_at_30_c_per_s'][key]+=1
        values,_=memory.predict(case,changed,30,0);cols.append(np.array(values)-zero)
    x=np.array(cols).T;norm=np.linalg.norm(x,axis=0)
    sv=np.linalg.svd(x/np.maximum(norm,1e-30),compute_uv=False)
    return dict(states=states,column_norms=norm.tolist(),singular_values=sv.tolist(),
                rank=int(np.sum(sv>sv[0]*1e-12)),scaled_condition=None if sv[-1]<=1e-12 else float(sv[0]/sv[-1]),
                meaning='numerical independent shapes only; no state coefficient fit or precision guarantee')


def window_delta(ts,values,start,end):
    a=common.interpolate(ts,values,start);b=common.interpolate(ts,values,end)
    return None if a is None or b is None else b-a


def run(data,contract,output):
    output=Path(output)
    if output.exists():raise FileExistsError('fresh PC output required')
    if contract['id']!='ap-fixed-rate-identification-v1':raise ValueError('contract')
    cases=data['cases'];base=data['parameters'];beta0=base['ap_cooling_rate_per_s']
    expected=['idle_development',*contract['evaluation'],'resident_no_load_C']
    if [c['id'] for c in cases]!=expected:raise ValueError('roles/order')
    for c in cases:
        ts=c['inputs']['query_s'];y=c['observed_ap_c']
        if len(ts)!=len(y) or any(not math.isfinite(v) for v in y) or any(not 0<b-a<=10 for a,b in zip(ts,ts[1:])):
            raise ValueError('missing target or timing gap')
    betas=beta0*np.geomspace(.2,5,61);betas[30]=beta0
    best,grid=fit(cases[0],base,betas)
    near=[r for r in grid if r['rmse_c']<=best['rmse_c']+.05]
    table=[];paths=[];directions=[];info=[]
    for c in cases:
        ts=c['inputs']['query_s'];y=c['observed_ap_c'];last=max((s['end_s'] for s in c['inputs']['segments'] if s['state']!='idle'),default=None)
        original,_=predict(c,base,beta0,1)
        changed,init=predict(c,base,best['beta_per_s'],best['gain'])
        for name,values in [('frozen_memory',original),('rate_gain_diagnostic',changed)]:
            table.append(dict(case=c['id'],role=c['role'],protocol=c['protocol'],model=name,
                first_s=ts[0],last_s=ts[-1],samples=len(y),**common.score(y,values)))
            for lo,hi in contract['observational_windows']:
                directions.append(dict(case=c['id'],model=name,start_s=lo,end_s=hi,
                    observed_change_c=window_delta(ts,y,lo,hi),predicted_change_c=window_delta(ts,values,lo,hi)))
        for t,obs,a,b in zip(ts,y,original,changed):
            paths.append(dict(case=c['id'],common_s=t,since_last_lane_s=None if last is None else t-last,
                observed_c=obs,frozen_memory_c=a,diagnostic_c=b,frozen_residual_c=a-obs,diagnostic_residual_c=b-obs))
        info.append(dict(case=c['id'],last_lane_s=last,initialization=init,
                         state_information=state_information(c,base),local_rate_gain=jacobian(c,base,best['beta_per_s'],best['gain'])))
    observation=[];observed_paths=[]
    for c in cases[:-1]:
        p=c['inputs'];ts=[v['t'] for v in p['preload']]+p['query_s'];y=[v['ap'] for v in p['preload']]+c['observed_ap_c']
        last=max(s['end_s'] for s in p['segments'] if s['state']!='idle')
        for lo,hi in contract['observational_windows']:
            observation.append(dict(case=c['id'],work_requests=24,start_s=lo,end_s=hi,change_c=window_delta(ts,y,lo,hi),causal=False))
        observed_paths.extend(dict(case=c['id'],common_s=t,since_last_lane_s=t-last,ap_c=v) for t,v in zip(ts,y))
    for c in data['controls']:
        ts=[v['t'] for v in c['ap']];y=[v['ap'] for v in c['ap']]
        last=max((s['end_s'] for s in c['states'] if s['state']!='idle'),default=None)
        for lo,hi in contract['observational_windows']:
            observation.append(dict(case=c['id'],work_requests=c['work_requests'],start_s=lo,end_s=hi,change_c=window_delta(ts,y,lo,hi),causal=False))
        observed_paths.extend(dict(case=c['id'],common_s=t,since_last_lane_s=None if last is None else t-last,ap_c=v) for t,v in zip(ts,y))
    control_grid=profile(cases[-1],base,betas)
    summary=dict(id=contract['id'],best_development=best,profile_near_best=dict(
        criterion='RMSE <= best+0.05C; sensitivity only, NOT CI or PASS',
        beta_min=min(r['beta_per_s'] for r in near),beta_max=max(r['beta_per_s'] for r in near),
        gain_min=min(r['gain'] for r in near),gain_max=max(r['gain'] for r in near),points=len(near)),
        boundary_optimum=best['beta_per_s'] in (float(betas[0]),float(betas[-1])),
        cases=info,source_sha256=data['source_sha256'],contract_sha256=digest(CONTRACT),
        family_count=1,fresh_independent_confirmation=0,accuracy_pass=None,strict_support=False,
        experiment_ready=False,default_changed=False,device_commands=0,new_measurement_plan=False)
    candidate=dict(id='ap-rate-gain-diagnostic-v1',beta_per_s=best['beta_per_s'],gain=best['gain'],
        tau_s=30,gamma=0,base_parameters=base,role='posthoc_development_only_unadopted',
        fitted_sessions=['idle_development'],fit_excluded_but_already_seen=contract['evaluation'],
        strict_support=False,default=False,accuracy_pass=None)
    output.mkdir(parents=True)
    for name,rr in [('profile',grid),('control_profile',control_grid),('scores',table),('paths',paths),
                    ('directions',directions),('observed_windows',observation),('observed_paths',observed_paths)]:
        common.write_csv(output/(name+'.csv'),rr)
    common.write_json(output/'summary.json',summary);common.write_json(output/'candidate.json',candidate)
    common.write_json(output/'inputs.json',data)
    plot(output,table,paths,grid,beta0,observed_paths)
    return summary


def plot(output,scores,paths,grid,beta0,observed):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,3,figsize=(14,10),constrained_layout=True)
    for ax,name in zip(axes.flat,dict.fromkeys(p['case'] for p in observed)):
        rows=[p for p in observed if p['case']==name]
        ax.plot([r['common_s'] for r in rows],[r['ap_c'] for r in rows],color='#111827',label='Observed')
        rows=[p for p in paths if p['case']==name or name=='control03_C_seen' and p['case']=='resident_no_load_C']
        for key,label,col in [('frozen_memory_c','Frozen memory','#047857'),('diagnostic_c','Rate/gain posthoc','#c2410c')]:
            if rows:ax.plot([r['common_s'] for r in rows],[r[key] for r in rows],label=label,color=col)
        ax.set_title(name);ax.set_xlabel('Common-origin seconds');ax.set_ylabel('AP C');ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8);fig.suptitle('Observed histories / one posthoc rate-gain diagnostic; no causal control subtraction')
    save(fig,output/'paths');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
    axes[0].semilogx([r['beta_per_s'] for r in grid],[r['rmse_c'] for r in grid]);axes[0].axvline(beta0,color='#64748b',ls=':')
    axes[0].set_xlabel('beta /s');axes[0].set_ylabel('Development RMSE C')
    axes[1].semilogx([r['beta_per_s'] for r in grid],[r['gain'] for r in grid]);axes[1].axvline(beta0,color='#64748b',ls=':')
    axes[1].set_xlabel('beta /s');axes[1].set_ylabel('Conditional load gain k')
    fig.suptitle('One prespecified family; profile is not a confidence interval')
    save(fig,output/'profile');plt.close(fig)


def save(fig,path):
    fig.savefig(path.with_suffix('.png'),dpi=130)
    fig.savefig(path.with_suffix('.svg'))
    p=path.with_suffix('.svg');p.write_text('\n'.join(l.rstrip() for l in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=run(inputs(),common.read(CONTRACT),a.output)
    print(json.dumps({k:result[k] for k in ('best_development','profile_near_best','boundary_optimum','device_commands')}))


if __name__=='__main__':main()
