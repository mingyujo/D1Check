"""One load-linked slow AP candidate and a clock-shift attribution control; PC only."""
import argparse
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
from tools import d1_resident_ap_structure as s

BUNDLE=s.ROOT/'docs/results/ap_tail_identification_01'
MODES=('LOAD_SLOW','CLOCK_SHIFT')


def bases(c,original,tau):
    if not math.isfinite(tau) or tau<=0:raise ValueError('invalid slow time')
    initial,full,_,init=s.design(c,original)
    zero=dict(init,reference_c=0.,anchor_ap_c=0.,h_last_c_per_s=0.)
    slopes=dict(resident_idle=0.,**original['energy_increment_w'])
    kernel=np.array(s.j.m.memory._propagate(c['actual'],c['q'],slopes,1/tau,30.,0.,zero))
    clock=-np.expm1(-(np.array(c['q'])-35.)/tau)
    return initial,full[:,:4],kernel,clock,init


def constrained(x,y,signed_last):
    if not signed_last:return s.nnls(x,y)
    candidates=[np.zeros(5)]
    for n in range(5):
        for active in itertools.combinations(range(4),n):
            columns=list(active)+[4];value=np.zeros(5)
            value[columns]=np.linalg.lstsq(x[:,columns],y,rcond=None)[0]
            if np.all(value[:4]>=0):candidates.append(value)
    return min(candidates,key=lambda z:(float(np.sum((x@z-y)**2)),abs(float(z[-1]))))


def predict(c,original,model):
    if model['original_model_sha256']!=s.j.m.MODEL_SHA or model['beta_fixed']!=original['ap']['beta']:
        raise ValueError('original family changed')
    initial,direct,kernel,clock,init=bases(c,original,model['tau_s'])
    mode=model['mode'];theta=np.array(model['coefficients'])
    if mode not in MODES or theta.shape!=(5,) or not np.isfinite(theta).all() or np.any(theta[:4]<0) or (mode=='LOAD_SLOW' and theta[4]<0):
        raise ValueError('invalid candidate')
    last=kernel if mode=='LOAD_SLOW' else clock
    fast=direct@theta[:4];slow=last*theta[4];y=initial+fast+slow
    if not np.isfinite(y).all():raise ValueError('nonfinite prediction')
    return y.tolist(),dict(initial_path_c=initial.tolist(),fast_path_c=fast.tolist(),slow_path_c=slow.tolist(),
                          effective_reference_c=init['reference_c'],reference_is_ambient=False,
                          slow_initial_zero_is_additional_change_not_measured_empty_state=True)


def fit(cases,original,mode,grid):
    if mode not in MODES or len(cases)<3 or any(c['role']!='development' or c['policy'] not in ('DEV_A','DEV_B') for c in cases):
        raise ValueError('new development-only fit; archive/confirmation forbidden')
    profile=[]
    for tau in grid:
        xs=[];ys=[]
        for c in cases:
            initial,direct,kernel,clock,_=bases(c,original,tau)
            target=np.array(c['ap']);last=kernel if mode=='LOAD_SLOW' else clock
            if target.shape!=initial.shape or not np.isfinite(target).all():raise ValueError('missing targets')
            weight=1/math.sqrt(len(target)*len(cases));xs.append(np.column_stack((direct,last))*weight);ys.append((target-initial)*weight)
        x=np.vstack(xs);y=np.concatenate(ys);norm=np.linalg.norm(x,axis=0)
        sv=np.linalg.svd(x/np.maximum(norm,1e-30),compute_uv=False);rank=np.linalg.matrix_rank(x)
        if rank!=5:raise ValueError('slow/direct coefficients unidentified')
        theta=constrained(x,y,mode=='CLOCK_SHIFT')
        profile.append(dict(mode=mode,tau_s=float(tau),coefficients=theta.tolist(),mse=float(np.sum((x@theta-y)**2)),
                            rank=int(rank),scaled_condition=float(sv[0]/sv[-1])))
    return model_from_profile(cases,original,mode,grid,profile),profile


def model_from_profile(cases,original,mode,grid,profile):
    best=min(profile,key=lambda z:(z['mse'],z['tau_s']))
    model=dict(version='ap-load-linked-slow-memory-v1',mode=mode,coefficients=best['coefficients'],tau_s=best['tau_s'],
               beta_fixed=original['ap']['beta'],preparation_tau_s=30.,states=list(s.STATES),
               original_model_sha256=s.j.m.MODEL_SHA,development_ids=[c['id'] for c in cases],
               tau_boundary=best['tau_s'] in (float(grid[0]),float(grid[-1])),linear_rank=5,
               weighted_training_mse=best['mse'],profile_grid_s=list(grid),default=False,strict_support=False,
               accuracy_pass=None,independent_confirmation_sessions=0,experiment_ready=False)
    # Local prediction sensitivity for four fast gains, slow amplitude and tau.
    columns=[]
    baseline=[np.array(predict(c,original,model)[0]) for c in cases]
    for n in range(6):
        changed=copy.deepcopy(model)
        value=model['coefficients'][n] if n<5 else model['tau_s'];step=1e-4*max(abs(value),.1)
        if n<5:changed['coefficients'][n]+=step
        else:changed['tau_s']+=step
        columns.append(np.concatenate([(np.array(predict(c,original,changed)[0])-base)/step/math.sqrt(len(base)*len(cases)) for c,base in zip(cases,baseline)]))
    x=np.column_stack(columns);norm=np.linalg.norm(x,axis=0);sv=np.linalg.svd(x/np.maximum(norm,1e-30),compute_uv=False)
    model.update(jacobian_rank=int(np.linalg.matrix_rank(x)),jacobian_scaled_singular_values=sv.tolist(),
                 time_identified_within_grid=bool(not model['tau_boundary'] and int(np.linalg.matrix_rank(x))==6),
                 physical_cause_identified=False,application_allowed=False)
    return model


def ambiguity(cases,original,tau):
    xs=[]
    for c in cases:
        _,direct,kernel,clock,_=bases(c,original,tau);xs.append(np.column_stack((direct,kernel,clock))/math.sqrt(len(clock)*len(cases)))
    x=np.vstack(xs);direct=x[:,:4];last=x[:,4:]
    residual=last-direct@np.linalg.lstsq(direct,last,rcond=None)[0]
    norms=np.linalg.norm(residual,axis=0);cos=float(residual[:,0]@residual[:,1]/np.prod(norms)) if min(norms)>0 else None
    scale=np.linalg.norm(x,axis=0);sv=np.linalg.svd(x/np.maximum(scale,1e-30),compute_uv=False)
    return dict(tau_s=tau,load_vs_clock_cosine_after_fast_projection=cos,joint_rank=int(np.linalg.matrix_rank(x)),
                scaled_singular_values=sv.tolist(),scaled_condition=float(sv[0]/sv[-1]),
                causal_distinction_not_certified_by_rank=True)


def audit(cases,original):
    rows=[]
    for c in cases:
        initial,_,_,init=s.design(c,original)
        last=max(35.,c['last_lane_s']);cut=last+3/original['ap']['beta']
        indices=[i for i,t in enumerate(c['q']) if t>=cut]
        row=dict(session=c['id'],block=c.get('block','resident_new'),role=c['role'],policy=c['policy'],
                 no_load=not any(s.j.m.thermal.state_key(z['state'])!='resident_idle' for z in c['actual']),pre_last_ap_c=c['pre'][-1]['ap'],
                 effective_reference_c=init['reference_c'],end_ap_c=c['ap'][-1],end_initial_path_c=float(initial[-1]),
                 end_reference_offset_c=c['ap'][-1]-init['reference_c'],last_lane_s=c['last_lane_s'],
                 post_lane_observation_s=c['q'][-1]-last,late_cut_s=cut,late_samples=len(indices),
                 late_span_s=None,late_ap_slope_c_per_s=None,late_idle_power_w=None,late_power_change_w=None,
                 late_power_unavailable_reason=None)
        if len(indices)>=2:
            ts=np.array([c['q'][i] for i in indices]);ap=np.array([c['ap'][i] for i in indices]);row['late_span_s']=float(ts[-1]-ts[0])
            row['late_ap_slope_c_per_s']=float(np.linalg.lstsq(np.column_stack((np.ones(len(ts)),ts-ts[0])),ap,rcond=None)[0][1])
            try:
                value=s.j.m.integral(c,float(ts[0]),float(ts[-1]))/(ts[-1]-ts[0]);row['late_idle_power_w']=value;row['late_power_change_w']=value-c['pre_w']
            except ValueError as exc:row['late_power_unavailable_reason']=str(exc)
        rows.append(row)
    return rows


def power_common_windows(cases,original):
    rows=[]
    for c in cases:
        cut=max(35.,c['last_lane_s'])+3/original['ap']['beta'];qs=[q for q in c['q'] if q>=cut]
        if len(qs)<2:continue
        lo=max(qs[0],c['power_t'][0]);hi=min(qs[-1],c['power_t'][-1])
        row=dict(session=c['id'],ap_interval_start_s=qs[0],ap_interval_end_s=qs[-1],power_common_start_s=lo,
                 power_common_end_s=hi,power_common_duration_s=max(0.,hi-lo),late_power_w=None,power_change_w=None,error=None)
        try:
            if hi<=lo:raise ValueError('no common observed window')
            value=s.j.m.integral(c,lo,hi)/(hi-lo);row.update(late_power_w=value,power_change_w=value-c['pre_w'])
        except ValueError as exc:row['error']=str(exc)
        rows.append(row)
    return rows


def upper_grid_sensitivity(cases,original,profiles):
    rows=[]
    for c in cases:
        grid=sorted({p['tau_s'] for p in profiles})
        for tau in grid[-2:]:
            p=next(p for p in profiles if p['excluded']==c['id'] and p['mode']=='LOAD_SLOW' and p['tau_s']==tau)
            model=dict(mode='LOAD_SLOW',tau_s=tau,coefficients=p['coefficients'],original_model_sha256=s.j.m.MODEL_SHA,beta_fixed=original['ap']['beta'])
            point,_=predict(dict(c,q=[120.]),original,model)
            rows.append(dict(session=c['id'],tau_s=tau,training_mse=p['mse'],predicted_ap_at120_c=point[0],
                             interpretation='adjacent upper grid sensitivity; not a confidence interval or new selection'))
    return rows


def run(output):
    reg=s.j.m.read(BUNDLE/'registration.json')
    for path,digest in reg['sources'].items():
        if s.sha(s.ROOT/path)!=digest:raise ValueError('registered source changed '+path)
    out=Path(output);out.mkdir(parents=True,exist_ok=False);original=s.j.m.read(s.j.m.MODEL)
    new=s.j.m.read(s.INPUTS);archive,_=s.j.panel();grid=reg['tau_grid_s'];prior=s.j.m.read(s.BUNDLE/'run_v2/candidate.json')
    metrics=[];curves=[];profiles=[];models=[];folds=[]
    def record(c,pred,name,stage,parts=None):
        metrics.append(s.score(c,pred,stage,name))
        for i,(t,obs,p) in enumerate(zip(c['q'],c['ap'],pred)):
            row=dict(session=c['id'],stage=stage,model=name,t_s=t,observed_c=obs,predicted_c=p,residual_c=p-obs)
            if parts:row.update(initial_path_c=parts['initial_path_c'][i],fast_path_c=parts['fast_path_c'][i],slow_path_c=parts['slow_path_c'][i])
            curves.append(row)
    for i,c in enumerate(new):
        train=[a for n,a in enumerate(new) if i!=n];record(c,s.j.m.predict(c,c['actual'],original,dict(name='FROZEN'))[0],'FROZEN','development_loso')
        old=[m for m in s.j.m.read(s.BUNDLE/'run_v2/fold_models.json') if m['excluded']==c['id'] and m['mode']=='STATE_DELAYED'][0]
        record(c,s.predict(c,original,old)[0],'PRIOR30','development_loso')
        for mode in MODES:
            fitted,profile=fit(train,original,mode,grid);pred,parts=predict(c,original,fitted)
            record(c,pred,mode,'development_loso',parts);models.append(dict(excluded=c['id'],**fitted))
            profiles.extend(dict(excluded=c['id'],**p) for p in profile)
            folds.append(dict(excluded=c['id'],mode=mode,tau_s=fitted['tau_s'],tau_boundary=fitted['tau_boundary'],
                              jacobian_rank=fitted['jacobian_rank'],time_identified_within_grid=fitted['time_identified_within_grid']))
        print(json.dumps(dict(stage='fold_complete',excluded=c['id'])),flush=True)
    final={}
    for mode in MODES:
        final[mode],profile=fit(new,original,mode,grid);profiles.extend(dict(excluded='full_development',**p) for p in profile)
    for c in archive:
        record(c,s.j.m.predict(c,c['actual'],original,dict(name='FROZEN'))[0],'FROZEN','archive_posthoc')
        record(c,s.predict(c,original,prior)[0],'PRIOR30','archive_posthoc')
        for mode in MODES:
            pred,parts=predict(c,original,final[mode]);record(c,pred,mode,'archive_posthoc',parts)
    summaries=[]
    for stage in ('development_loso','archive_posthoc'):
        blocks=dict.fromkeys(r['block'] for r in metrics if r['stage']==stage)
        for block in blocks:
            for mode in ('FROZEN','PRIOR30')+MODES:
                use=[r for r in metrics if r['stage']==stage and r['block']==block and r['model']==mode]
                summaries.append(dict(stage=stage,block=block,model=mode,sessions=len(use),
                     mean_mae_c=float(np.mean([r['mae_c'] for r in use])),mean_max_c=float(np.mean([r['max_absolute_error_c'] for r in use])),
                     mean_peak_abs_c=float(np.mean([abs(r['peak_signed_error_c']) for r in use]))))
    return publish(out,new,archive,original,metrics,curves,profiles,models,folds,final,summaries)


def publish(out,new,archive,original,metrics,curves,profiles,models,folds,final,summaries,recovery_source=None):
    reg=s.j.m.read(BUNDLE/'registration.json');grid=reg['tau_grid_s']
    s.csv_write(out/'tail_audit.csv',audit(new+archive,original));s.csv_write(out/'metrics.csv',metrics)
    s.csv_write(out/'curves.csv',curves);s.csv_write(out/'tau_profiles.csv',profiles);s.csv_write(out/'summary.csv',summaries)
    s.csv_write(out/'tail_power_common_window.csv',power_common_windows(new+archive,original))
    s.csv_write(out/'upper_grid_sensitivity.csv',upper_grid_sensitivity(new,original,profiles))
    s.write(out/'fold_models.json',models);s.write(out/'fold_identification.json',folds);s.write(out/'candidates.json',final)
    s.write(out/'ambiguity.json',ambiguity(new,original,final['LOAD_SLOW']['tau_s']))
    render(out,new,metrics,curves,profiles)
    result=dict(status='posthoc_tail_identification_completed',sessions=33,development=4,archive=29,
                primary_fits=5,control_fits=5,profile_points=len(profiles),tau_grid_s=grid,
                tau_s=final['LOAD_SLOW']['tau_s'],tau_boundary=final['LOAD_SLOW']['tau_boundary'],
                time_identified_within_grid=final['LOAD_SLOW']['time_identified_within_grid'],
                physical_cause_identified=False,matched_long_no_load_controls=0,independent_confirmation_sessions=0,
                physical_commands=0,new_plans=0,default_changed=False,energy_changed=False,experiment_ready=False,
                accuracy_pass=None,registration_sha256=s.sha(BUNDLE/'registration.json'),source_sha256=s.sha(__file__),
                recovered_from_profile=str(recovery_source) if recovery_source else None,new_fit_count=0 if recovery_source else 10,
                original_model_sha256=s.sha(s.j.m.MODEL))
    s.write(out/'receipt.json',result);return dict(receipt=result,summary=summaries)


def recover_profiles(source,output):
    """Finish a serialization failure using saved numeric profiles; never rerun NNLS."""
    source=Path(source);out=Path(output);reg=s.j.m.read(BUNDLE/'registration.json')
    for path,digest in reg['sources'].items():
        if s.sha(s.ROOT/path)!=digest:raise ValueError('registered source changed')
    new=s.j.m.read(s.INPUTS);archive,_=s.j.panel();original=s.j.m.read(s.j.m.MODEL);grid=reg['tau_grid_s']
    profiles=s.csv_read(source/'tau_profiles.csv')
    for p in profiles:p['coefficients']=json.loads(p['coefficients'])
    if len(profiles)!=70:raise ValueError('complete saved70 profiles required')
    metrics=s.csv_read(source/'metrics.csv');curves=s.csv_read(source/'curves.csv');summaries=s.csv_read(source/'summary.csv')
    if len(metrics)!=132:raise ValueError('complete numeric evaluation required')
    models=[];folds=[];final={}
    for i,c in enumerate(new):
        train=[v for j,v in enumerate(new) if i!=j]
        for mode in MODES:
            use=[p for p in profiles if p['excluded']==c['id'] and p['mode']==mode]
            if [p['tau_s'] for p in use]!=grid:raise ValueError('profile grid changed')
            m=model_from_profile(train,original,mode,grid,use);models.append(dict(excluded=c['id'],**m))
            folds.append(dict(excluded=c['id'],mode=mode,tau_s=m['tau_s'],tau_boundary=m['tau_boundary'],
                              jacobian_rank=m['jacobian_rank'],time_identified_within_grid=m['time_identified_within_grid']))
    for mode in MODES:
        use=[p for p in profiles if p['excluded']=='full_development' and p['mode']==mode]
        if [p['tau_s'] for p in use]!=grid:raise ValueError('final profile grid changed')
        final[mode]=model_from_profile(new,original,mode,grid,use)
    for c in new+archive:
        stage='development_loso' if c in new else 'archive_posthoc'
        for mode in MODES:
            model=next(m for m in models if m['excluded']==c['id'] and m['mode']==mode) if stage=='development_loso' else final[mode]
            pred,_=predict(c,original,model)
            stored=[r['predicted_c'] for r in curves if r['session']==c['id'] and r['stage']==stage and r['model']==mode]
            if not np.allclose(pred,stored,atol=1e-12,rtol=0):raise ValueError('saved predictions changed; no recovery publication')
    out.mkdir(parents=True,exist_ok=False)
    return publish(out,new,archive,original,metrics,curves,profiles,models,folds,final,summaries,source)


def render(out,new,metrics,curves,profiles):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=dict(FROZEN='tab:orange',PRIOR30='tab:purple',LOAD_SLOW='tab:green',CLOCK_SHIFT='tab:red')
    for i,c in enumerate(new):
        fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True,constrained_layout=True)
        axes[0].plot(c['q'],c['ap'],label='Observed',color='tab:blue')
        for name in colors:
            use=[r for r in curves if r['session']==c['id'] and r['stage']=='development_loso' and r['model']==name];q=[r['t_s'] for r in use]
            axes[0].plot(q,[r['predicted_c'] for r in use],label=name,color=colors[name]);axes[1].plot(q,[r['residual_c'] for r in use],color=colors[name])
        axes[0].legend(ncol=2);axes[0].set_ylabel('AP (C)');axes[1].set(xlabel='Reference seconds',ylabel='Prediction - observed (C)');axes[1].axhline(0,c='black',lw=.5)
        for ax in axes:ax.grid(alpha=.2)
        fig.suptitle(c['id']+' | posthoc development LOSO; no independent confirmation');fig.savefig(out/f'macro_{i}.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    for ax,mode in zip(axes,MODES):
        for excluded in dict.fromkeys(p['excluded'] for p in profiles):
            use=[p for p in profiles if p['excluded']==excluded and p['mode']==mode]
            ax.plot([p['tau_s'] for p in use],[p['mse'] for p in use],label=excluded)
        ax.set(xscale='log',xlabel='tau (s)',ylabel='Equal-session training MSE',title=mode);ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Fixed profile: endpoints are not an identified physical time constant');fig.savefig(out/'tau_profiles.png',dpi=140);plt.close(fig)
    c0=[r for r in metrics if r['stage']=='archive_posthoc' and r['policy']=='C0']
    fig,ax=plt.subplots(figsize=(9,4),constrained_layout=True)
    for i,name in enumerate(colors):
        use=[r for r in c0 if r['model']==name];ax.bar(np.arange(len(use))+(i-1.5)*.2,[r['mae_c'] for r in use],width=.2,label=name,color=colors[name])
    names=[r['session'] for r in c0 if r['model']=='FROZEN'];ax.set_xticks(np.arange(len(names)),names,rotation=12);ax.set_ylabel('AP MAE (C)');ax.legend();ax.grid(axis='y',alpha=.2)
    fig.suptitle('Historical short C0; no matched long no-load counterfactual');fig.savefig(out/'c0_controls.png',dpi=140);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4),constrained_layout=True);blocks=('development','confirmation','sustained','history')
    for i,name in enumerate(colors):
        values=[np.mean([r['mae_c'] for r in metrics if r['stage']=='archive_posthoc' and r['block']==block and r['model']==name]) for block in blocks]
        ax.bar(np.arange(4)+(i-1.5)*.2,values,width=.2,label=name,color=colors[name])
    ax.set_xticks(np.arange(4),['old dev3','old confirm6','sustained8','history12']);ax.set_ylabel('AP MAE (C)');ax.legend();ax.grid(axis='y',alpha=.2)
    fig.suptitle('All previously seen groups: worsening remains; no new independent confirmation')
    fig.savefig(out/'archive_groups.png',dpi=140);plt.close(fig)
    body=''.join('<img src="macro_'+str(i)+'.png" style="max-width:100%">' for i in range(4))
    d=[r['mae_c'] for r in metrics if r['stage']=='development_loso' and r['model']=='LOAD_SLOW']
    archived=[r for r in metrics if r['stage']=='archive_posthoc' and r['model']=='LOAD_SLOW'];bad=0
    for r in archived:
        base=next(a for a in metrics if a['session']==r['session'] and a['stage']==r['stage'] and a['model']=='FROZEN')
        bad+=r['mae_c']>base['mae_c']+1e-9
    model=s.j.m.read(out/'candidates.json')['LOAD_SLOW']
    note=f'<aside style="padding:15px;background:#fff1d6"><b>오차는 일부 감소·원인/시간상수는 미확정</b><p>새개발4 제외평가 MAE {np.mean(d):.3f}°C. 선택τ {model["tau_s"]:.0f}초·경계값 {model["tau_boundary"]}; 물리적시간상수 식별/정확도PASS/기본교체 아님. 과거29 중 {bad}세션은 원모형보다 악화했습니다. Clock 대조를 사후 주후보로 바꾸지 않습니다.</p></aside>'
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>AP 꼬리 식별 PC 분석</title><style>body{max-width:1100px;margin:30px auto;font:16px/1.7 sans-serif}</style><h1>느린 부하 이력과 유휴 기준 변화</h1>'+note+'<p>사후 개발4 제외평가+이전열람29 전이. 시간상수/물리원인/독립확인과 오차 산출을 구분합니다. 장구간 동일프로토콜 C0 없음·기기0·기본/RL/strict 유지.</p><a href="metrics.csv">전체 오차</a> · <a href="tail_audit.csv">33세션 꼬리/전력 관측</a> · <a href="tail_power_common_window.csv">전력 공통구간</a> · <a href="tau_profiles.csv">전체 시간상수 profile</a>'+body+'<img src="tau_profiles.png" style="max-width:100%"><img src="c0_controls.png" style="max-width:100%"><img src="archive_groups.png" style="max-width:100%">',encoding='utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--recover-profiles');args=p.parse_args()
    print(json.dumps(recover_profiles(args.recover_profiles,args.output) if args.recover_profiles else run(args.output),ensure_ascii=False,indent=2))
