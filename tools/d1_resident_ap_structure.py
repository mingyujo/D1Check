"""Opt-in, posthoc AP state-drive candidate. No energy, default, RL or device mutations."""
import argparse
import copy
import csv
import hashlib
import itertools
import json
import math
import shutil
from pathlib import Path

import numpy as np
from tools import d1_joint_model_refinement as j
from tools import d1_resident_identification_plan as roster

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'docs/results/resident_ap_structure_01'
INPUTS=ROOT/'docs/results/resident_identification_run_01/recorded_v3/inputs.json.gz'
STATES=tuple(j.m.base.STATES)
MODES=('RATIO_REFIT','STATE_DIRECT','STATE_DELAYED')
COLORS=dict(FROZEN='tab:orange',RATIO_REFIT='tab:green',STATE_DIRECT='tab:red',STATE_DELAYED='tab:purple')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p,v):
    Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')


def csv_write(p,rows):
    if not rows:return
    with Path(p).open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader();w.writerows(rows)


def design(c,original):
    """Targets/power are absent from basis construction. Reuse exact old clock/pre gates."""
    # Archived arrival ledgers use task:backend; new macro ledgers use task_backend.
    # Reuse the exact established parser, without collapsing different task pairs.
    if any(j.m.thermal.state_key(s['state']) not in ('resident_idle',)+STATES for s in c['actual']):raise ValueError('unsupported state; no mapping substitution')
    beta=float(original['ap']['beta']);parameters=copy.deepcopy(original['ap']['parameters'])
    initial,old_x,init=j.m.thermal.basis(j.m.case_input(c,c['actual']),parameters,beta)
    columns=[]
    for state in STATES:
        unit={k:float(k==state) for k in ('resident_idle',)+STATES}
        path=j.m.memory._propagate(c['actual'],c['q'],unit,beta,30.,0.,init)
        columns.append(np.array(path)-initial)
    direct=np.column_stack(columns)
    return initial,np.column_stack((direct,old_x[:,1])),old_x,init


def nnls(x,y):
    n=x.shape[1];solutions=[np.zeros(n)]
    for size in range(1,n+1):
        for columns in itertools.combinations(range(n),size):
            value=np.zeros(n);value[list(columns)]=np.linalg.lstsq(x[:,columns],y,rcond=None)[0]
            if np.all(value>=0):solutions.append(value)
    return min(solutions,key=lambda z:(float(np.sum((x@z-y)**2)),float(z[-1]),float(np.sum(z))))


def fit(cases,original,mode):
    if mode not in MODES:raise ValueError('unregistered mode')
    if len(cases)<3 or any(c['role']!='development' or c['policy'] not in ('DEV_A','DEV_B') for c in cases):
        raise ValueError('registered new development only; confirmation/archive fit forbidden')
    xs=[];ys=[]
    for c in cases:
        initial,full,old_x,_=design(c,original)
        x=old_x if mode=='RATIO_REFIT' else full[:,:4] if mode=='STATE_DIRECT' else full
        target=np.array(c['ap'],dtype=float)
        if target.shape!=initial.shape or not np.isfinite(target).all():raise ValueError('missing target')
        weight=1/math.sqrt(len(target)*len(cases));xs.append(x*weight);ys.append((target-initial)*weight)
    x=np.vstack(xs);y=np.concatenate(ys);norm=np.linalg.norm(x,axis=0)
    sv=np.linalg.svd(x/np.maximum(norm,1e-30),compute_uv=False)
    rank=np.linalg.matrix_rank(x)
    if rank!=x.shape[1]:raise ValueError('state/delayed coefficients unidentified')
    coefficients=nnls(x,y)
    return dict(version='resident-ap-state-drives-v1',mode=mode,coefficients=coefficients.tolist(),
                states=list(STATES),beta_fixed=original['ap']['beta'],tau_fixed_s=30.,
                development_ids=[c['id'] for c in cases],original_model_sha256=j.m.MODEL_SHA,
                numerical_rank=int(rank),scaled_singular_values=sv.tolist(),scaled_condition=float(sv[0]/sv[-1]),
                weighted_training_mse=float(np.sum((x@coefficients-y)**2)),
                practical_identification='not certified by rank; development session sensitivity required',
                accuracy_pass=None,default=False,strict_support=False,experiment_ready=False)


def predict(c,original,model):
    """Diagnostic equation evaluation. This is not an empirical support grant."""
    if model['original_model_sha256']!=j.m.MODEL_SHA or model['beta_fixed']!=original['ap']['beta'] or model['tau_fixed_s']!=30.:
        raise ValueError('fixed family mismatch')
    initial,full,old_x,init=design(c,original);mode=model['mode'];theta=np.array(model['coefficients'])
    x=old_x if mode=='RATIO_REFIT' else full[:,:4] if mode=='STATE_DIRECT' else full
    if theta.shape!=(x.shape[1],) or not np.isfinite(theta).all() or np.any(theta<0):raise ValueError('coefficient mismatch')
    if mode=='RATIO_REFIT':direct=old_x[:,0]*theta[0];delayed=old_x[:,1]*theta[1]
    else:
        direct=full[:,:4]@theta[:4];delayed=full[:,4]*theta[4] if mode=='STATE_DELAYED' else np.zeros(len(initial))
    y=initial+direct+delayed
    if not np.isfinite(y).all():raise ValueError('nonfinite prediction')
    return y.tolist(),dict(initial_path_c=initial.tolist(),direct_path_c=direct.tolist(),delayed_path_c=delayed.tolist(),
                          initial=init,reference_is_ambient=False,latent_is_measured=False)


def forecast_candidate(c,original,model,context):
    """Explicit opt-in context guard. Does not enter any default/strict/RL path."""
    scope=j.m.read(BUNDLE/'application_scope.json');reasons=[]
    digest=hashlib.sha256(json.dumps(model,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if digest!=scope['candidate_payload_sha256']:reasons.append('candidate payload mismatch')
    for k,v in scope['expected_context'].items():
        if context.get(k)!=v:reasons.append('context mismatch: '+k)
    if c.get('policy') not in scope['profiles'] or c.get('common_end_s')!=scope['common_end_s']:
        reasons.append('unsupported short/arrival/profile window')
    elif not registered_schedule(c):reasons.append('actual schedule outside registered macro blocks')
    if c.get('q') and c['q'][-1]>scope['common_end_s']+180.:
        reasons.append('query outside registered candidate observation horizon')
    pre=c.get('pre',[]);lo,hi=scope['observed_pre_last_ap_range_c']
    ap=pre[-1].get('ap') if pre else None
    if not isinstance(ap,(int,float)) or not math.isfinite(ap) or not lo<=ap<=hi:
        reasons.append('initial AP missing/nonfinite/outside observed candidate context')
    result=dict(status='unsupported_candidate_context' if reasons else 'diagnostic_candidate_only',reasons=reasons,
                prediction_ap_c=None,independent_confirmation_sessions=0,accuracy_pass=None,
                strict_support=False,default_changed=False,experiment_ready=False)
    if reasons:return result
    try:pred,parts=predict(c,original,model)
    except (ValueError,TypeError,KeyError) as error:
        result.update(status='invalid_candidate_inputs',reasons=[str(error)]);return result
    result.update(prediction_ap_c=pred,initialization=parts['initial'])
    return result


def registered_schedule(c):
    """Keep real occupancy/one-sided pair intervals; no fictitious full-time overlap."""
    windows=[];cursor=35.
    for block in roster.blocks(c['policy']):
        keys={roster.old.KEYS[n] for n in block['lane_indices']};end=cursor+block['seconds']
        if keys:
            allowed=keys|{'+'.join(sorted(keys))}
            windows.append((cursor,end,keys,allowed))
        cursor=end
    segments=c.get('actual',[]);occupancy={key:[] for key in STATES[:3]}
    for seg in segments:
        state=j.m.thermal.state_key(seg['state'])
        if state=='resident_idle':continue
        if state not in STATES:return False
        for key in state.split('+'):
            intervals=occupancy[key]
            if intervals and abs(intervals[-1][1]-seg['start_s'])<=1e-6:
                intervals[-1][1]=seg['end_s']
            else:intervals.append([seg['start_s'],seg['end_s']])
    for key,intervals in occupancy.items():
        for start,end in intervals:
            # A pair->solo label change is continuous occupancy, not a new dispatch.
            if not any(key in keys and left<=start<right and end<=right+30.
                       for left,right,keys,allowed in windows):return False
    for left,right,keys,allowed in windows:
        for key in keys:
            if not any(start<right and end>left for start,end in occupancy[key]):
                return False
    return True


def score(c,pred,stage,model):
    result=dict(session=c['id'],block=c.get('block','resident_new'),policy=c['policy'],role=c['role'],stage=stage,model=model,
                **j.m.base.common.score(c['ap'],pred),**j.h.direction(c,pred),ap_start_s=c['q'][0],ap_end_s=c['q'][-1])
    ef=j.m.energy_prediction(c,c['actual'],j.m.read(j.m.MODEL),dict(name='FROZEN'),120)
    observed=j.m.integral(c,0,120)
    result.update(energy_observed_120_j=observed,energy_predicted_120_j=ef,energy_signed_120_j=ef-observed,
                  energy_model_changed=False,accuracy_pass=None)
    return result


def phase_scores(c,pred,stage,model):
    if c['policy'] not in ('DEV_A','DEV_B'):return []
    result=[];offset=35.
    specs=roster.blocks(c['policy'])+[dict(id='tail',lane_indices=[],seconds=90),dict(id='cooling',lane_indices=[],seconds=180)]
    for spec in specs:
        end=offset+spec['seconds'];indices=[i for i,t in enumerate(c['q']) if offset<=t<end]
        if len(indices)>=2:
            obs=[c['ap'][i] for i in indices];p=[pred[i] for i in indices]
            do=obs[-1]-obs[0];dp=p[-1]-p[0]
            result.append(dict(session=c['id'],profile=c['policy'],stage=stage,model=model,phase=spec['id'],
                               nominal_start_s=offset,nominal_end_s=end,sampled_start_s=c['q'][indices[0]],sampled_end_s=c['q'][indices[-1]],
                               samples=len(indices),observed_change_c=do,predicted_change_c=dp,
                               opposite=bool(abs(do)>.100000001 and do*dp< -1e-12),**j.m.base.common.score(obs,p)))
        offset=end
    return result


def csv_read(p):
    rows=[]
    for row in csv.DictReader(Path(p).open(encoding='utf8')):
        converted={}
        for k,v in row.items():
            if v=='':converted[k]=None
            elif v in ('True','False'):converted[k]=v=='True'
            else:
                try:converted[k]=float(v)
                except ValueError:converted[k]=v
        rows.append(converted)
    return rows


def render_diagnostics(out,rows,curves,worsening):
    import matplotlib.pyplot as plt
    blocks=('development','confirmation','sustained','history')
    fig,axes=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
    for ax,metric,title in [(axes[0],'mae_c','Archived AP MAE'),(axes[1],'max_absolute_error_c','Archived mean maximum absolute error')]:
        for i,name in enumerate(('FROZEN','STATE_DELAYED')):
            values=[np.mean([r[metric] for r in rows if r['stage']=='archive_posthoc_transfer' and r['block']==b and r['model']==name]) for b in blocks]
            ax.bar(np.arange(4)+(i-.5)*.35,values,width=.35,label=name,color=COLORS[name])
        ax.set_xticks(np.arange(4),['old dev (3)','old confirm (6)','sustained (8)','history (12)'])
        ax.set(title=title,ylabel='C');ax.legend();ax.grid(axis='y',alpha=.2)
    fig.suptitle('Previously seen 29 sessions; transfer diagnosis, not independent confirmation')
    fig.savefig(out/'archive_groups.png',dpi=140);plt.close(fig)
    candidates=[r for r in worsening if r['stage']=='archive_posthoc_transfer']
    if candidates:
        sid=max(candidates,key=lambda r:r['mae_change_c'])['session']
        fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True,constrained_layout=True)
        for name in ('FROZEN','STATE_DELAYED'):
            use=[r for r in curves if r['session']==sid and r['model']==name and r['stage']=='archive_posthoc_transfer']
            q=[r['t_s'] for r in use]
            if name=='FROZEN':axes[0].plot(q,[r['observed_c'] for r in use],label='Observed')
            axes[0].plot(q,[r['predicted_c'] for r in use],label=name,color=COLORS[name]);axes[1].plot(q,[r['residual_c'] for r in use],label=name,color=COLORS[name])
        axes[0].set_ylabel('AP (C)');axes[0].legend();axes[1].set(xlabel='Reference time (s)',ylabel='Prediction - observed (C)')
        axes[1].axhline(0,c='black',lw=.5)
        for ax in axes:ax.grid(alpha=.2)
        fig.suptitle(sid+' | largest archived MAE worsening; display choice only')
        fig.savefig(out/'archive_worst.png',dpi=140);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4),constrained_layout=True)
    for name in ('FROZEN','STATE_DELAYED'):
        use=[r for r in curves if r['session']=='session_00' and r['model']==name and r['stage']=='development_loso']
        q=[r['t_s'] for r in use]
        if name=='FROZEN':ax.plot(q,[r['observed_c'] for r in use],label='Observed')
        ax.plot(q,[r['predicted_c'] for r in use],label=name,color=COLORS[name])
    ax.set_xlim(540,815);ax.set(xlabel='Reference time: first DEV_A, late idle/cooling',ylabel='AP (C)');ax.grid(alpha=.2);ax.legend()
    fig.suptitle('Fixed pre-only reference + 30 s term misses persistent late offset')
    fig.savefig(out/'late_idle_offset.png',dpi=140);plt.close(fig)


def render_reused_macro(out,cases,curves):
    import matplotlib.pyplot as plt
    for i,c in enumerate(cases):
        fig,axes=plt.subplots(2,1,figsize=(10,6.5),sharex=True,constrained_layout=True)
        axes[0].plot(c['q'],c['ap'],label='Observed',lw=2,color='tab:blue')
        for name in ('FROZEN',)+MODES:
            use=[r for r in curves if r['session']==c['id'] and r['stage']=='development_loso' and r['model']==name]
            q=[r['t_s'] for r in use]
            axes[0].plot(q,[r['predicted_c'] for r in use],label=name,lw=1.2,color=COLORS[name])
            axes[1].plot(q,[r['residual_c'] for r in use],label=name,color=COLORS[name])
        base=[r['predicted_c'] for r in curves if r['session']==c['id'] and r['stage']=='development_loso' and r['model']=='FROZEN']
        for ax in axes:
            for spec in phase_scores(c,base,'development_loso','FROZEN'):
                if spec['phase'].startswith('state_'):ax.axvspan(spec['nominal_start_s'],spec['nominal_end_s'],color='gray',alpha=.08)
            ax.grid(alpha=.2)
        axes[0].set_ylabel('AP (C)');axes[0].legend(ncol=2);axes[1].set_ylabel('Prediction - observed (C)')
        axes[1].set_xlabel('Reference seconds; load at 35 s');axes[1].axhline(0,c='black',lw=.5)
        fig.suptitle(c['id']+' '+c['policy']+' | posthoc development LOSO, no independent confirmation')
        fig.savefig(out/f'macro_{i}.png',dpi=140);plt.close(fig)


def run(output,reuse_development=None):
    reg=j.m.read(BUNDLE/'registration.json')
    if sha(INPUTS)!=reg['inputs_sha256'] or sha(j.m.MODEL)!=reg['original_model_sha256']:raise ValueError('registered sources changed')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    cases=j.m.read(INPUTS);original=j.m.read(j.m.MODEL)
    if len(cases)!=4 or [c['policy'] for c in cases]!=['DEV_A','DEV_B','DEV_B','DEV_A']:raise ValueError('roster')
    rows=[];phases=[];curves=[];coeffs=[];models=[];unsupported=[];pictures=[]
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    if reuse_development is not None:
        source=Path(reuse_development);previous=j.m.read(source/'receipt.json')
        if any(previous[k]!=sha(p) for k,p in [('registration_sha256',BUNDLE/'registration.json'),
                                               ('original_model_sha256',j.m.MODEL),('inputs_sha256',INPUTS)]):
            raise ValueError('reuse source identity mismatch')
        rows=[r for r in csv_read(source/'metrics.csv') if r['stage']=='development_loso']
        phases=[r for r in csv_read(source/'phase_errors.csv') if r['stage']=='development_loso']
        curves=[r for r in csv_read(source/'curves.csv') if r['stage']=='development_loso']
        if len(rows)!=16:raise ValueError('complete registered development results required')
        models=j.m.read(source/'fold_models.json');coeffs=csv_read(source/'coefficient_sensitivity.csv')
        for file in sorted(source.glob('macro_*.png')):shutil.copyfile(file,out/file.name);pictures.append(file.name)
    def record(c,pred,stage,name,parts=None):
        rows.append(score(c,pred,stage,name));phases.extend(phase_scores(c,pred,stage,name))
        for i,(t,y,p) in enumerate(zip(c['q'],c['ap'],pred)):
            r=dict(session=c['id'],stage=stage,model=name,t_s=t,observed_c=y,predicted_c=p,residual_c=p-y)
            if parts:r.update(initial_path_c=parts['initial_path_c'][i],direct_path_c=parts['direct_path_c'][i],delayed_path_c=parts['delayed_path_c'][i])
            curves.append(r)
    for i,c in enumerate(cases if reuse_development is None else []):
        train=[x for n,x in enumerate(cases) if n!=i];baseline=j.m.predict(c,c['actual'],original,dict(name='FROZEN'))[0]
        record(c,baseline,'development_loso','FROZEN');predictions={'FROZEN':baseline}
        for mode in MODES:
            model=fit(train,original,mode);pred,parts=predict(c,original,model);record(c,pred,'development_loso',mode,parts)
            predictions[mode]=pred;models.append(dict(excluded=c['id'],stage='development_loso',**model))
            coeffs.extend(dict(excluded=c['id'],mode=mode,coefficient_index=n,value=v) for n,v in enumerate(model['coefficients']))
        fig,axes=plt.subplots(2,1,figsize=(10,6.5),sharex=True,constrained_layout=True)
        axes[0].plot(c['q'],c['ap'],label='Observed',lw=2)
        for name,pred in predictions.items():
            axes[0].plot(c['q'],pred,label=name,lw=1.2,color=COLORS[name]);axes[1].plot(c['q'],np.array(pred)-c['ap'],label=name,color=COLORS[name])
        for ax in axes:
            for spec in phase_scores(c,baseline,'development_loso','FROZEN'):
                if spec['phase'].startswith('state_'):ax.axvspan(spec['nominal_start_s'],spec['nominal_end_s'],color='gray',alpha=.08)
            ax.grid(alpha=.2)
        axes[0].set_ylabel('AP (C)');axes[0].legend(ncol=2);axes[1].set_ylabel('Prediction - observed (C)');axes[1].set_xlabel('Reference seconds; load at 35 s');axes[1].axhline(0,c='black',lw=.5)
        fig.suptitle(c['id']+' '+c['policy']+' | posthoc development LOSO, no independent confirmation')
        name=f'macro_{i}.png';fig.savefig(out/name,dpi=140);plt.close(fig);pictures.append(name)
        print(json.dumps(dict(stage='fold_complete',excluded=c['id']),ensure_ascii=False),flush=True)
    final=fit(cases,original,'STATE_DELAYED') if reuse_development is None else j.m.read(Path(reuse_development)/'candidate.json')
    write(out/'candidate.json',final)
    if reuse_development is not None and sha(out/'candidate.json')!=sha(Path(reuse_development)/'candidate.json'):
        raise ValueError('reused coefficients changed')
    archive,_=j.panel()
    for c in archive:
        try:pred,parts=predict(c,original,final)
        except ValueError as exc:
            unsupported.append(dict(session=c['id'],reason=str(exc)));continue
        baseline=j.m.predict(c,c['actual'],original,dict(name='FROZEN'))[0]
        record(c,baseline,'archive_posthoc_transfer','FROZEN');record(c,pred,'archive_posthoc_transfer','STATE_DELAYED',parts)
    summaries=[]
    for stage in dict.fromkeys(r['stage'] for r in rows):
        for block in dict.fromkeys(r['block'] for r in rows if r['stage']==stage):
            for name in ('FROZEN','STATE_DELAYED'):
                use=[r for r in rows if r['stage']==stage and r['block']==block and r['model']==name]
                if use:summaries.append(dict(stage=stage,block=block,model=name,sessions=len(use),mean_mae_c=float(np.mean([r['mae_c'] for r in use])),
                                             mean_max_c=float(np.mean([r['max_absolute_error_c'] for r in use])),worst_max_c=max(r['max_absolute_error_c'] for r in use)))
    gates=[]
    for profile in ('DEV_A','DEV_B'):
        use=[r for r in rows if r['stage']=='development_loso' and r['policy']==profile]
        for metric in ('mae_c','max_absolute_error_c'):
            values={name:float(np.mean([r[metric] for r in use if r['model']==name])) for name in ('FROZEN','STATE_DELAYED')}
            gates.append(dict(profile=profile,metric=metric,**values,nonworse=values['STATE_DELAYED']<=values['FROZEN']+1e-9))
    worsening=[]
    for stage in ('development_loso','archive_posthoc_transfer'):
        ids=dict.fromkeys(r['session'] for r in rows if r['stage']==stage)
        for sid in ids:
            pair={r['model']:r for r in rows if r['session']==sid and r['stage']==stage}
            if all(n in pair for n in ('FROZEN','STATE_DELAYED')):
                worsening.append(dict(stage=stage,session=sid,policy=pair['FROZEN']['policy'],block=pair['FROZEN']['block'],
                                      mae_change_c=pair['STATE_DELAYED']['mae_c']-pair['FROZEN']['mae_c'],
                                      max_change_c=pair['STATE_DELAYED']['max_absolute_error_c']-pair['FROZEN']['max_absolute_error_c']))
    csv_write(out/'metrics.csv',rows);csv_write(out/'phase_errors.csv',phases);csv_write(out/'curves.csv',curves)
    csv_write(out/'coefficient_sensitivity.csv',coeffs);csv_write(out/'summary.csv',summaries);csv_write(out/'worsening.csv',worsening)
    write(out/'fold_models.json',models);write(out/'gates.json',gates);write(out/'unsupported.json',unsupported)
    write(out/'receipt.json',dict(status='pc_posthoc_completed',candidate_development_gate=all(g['nonworse'] for g in gates),
          development_sessions=4,archived_evaluation_sessions=len(archive)-len(unsupported),unsupported=unsupported,
          candidate_families=1,fit_count=len(models)+1,independent_confirmation_sessions=0,physical_commands=0,
          new_fit_count=len(models)+1 if reuse_development is None else 0,
          development_reused_from=str(reuse_development) if reuse_development is not None else None,
          energy_changed=False,default_changed=False,experiment_ready=False,accuracy_pass=None,
          registration_sha256=sha(BUNDLE/'registration.json'),original_model_sha256=sha(j.m.MODEL),inputs_sha256=sha(INPUTS),
          source_sha256=sha(__file__)))
    if reuse_development is not None:render_reused_macro(out,cases,curves)
    render_diagnostics(out,rows,curves,worsening)
    body=''.join('<img src="'+p+'" style="max-width:100%">' for p in pictures)
    def mean_metric(stage,name,key):
        values=[r[key] for r in rows if r['stage']==stage and r['model']==name]
        return float(np.mean(values)) if values else None
    d0,d1=[mean_metric('development_loso',n,'mae_c') for n in ('FROZEN','STATE_DELAYED')]
    a0,a1=[mean_metric('archive_posthoc_transfer',n,'mae_c') for n in ('FROZEN','STATE_DELAYED')]
    bad=sum(r['stage']=='archive_posthoc_transfer' and r['mae_change_c']>1e-9 for r in worsening)
    note=f'<aside style="padding:15px;background:#fff1d6"><b>특정 조건에서만 개선</b><p>새 개발4 제외평가 MAE {d0:.3f}→{d1:.3f}°C. 과거 자료 전이 MAE {a0:.3f}→{a1:.3f}°C·{bad}세션 악화. 평균 최고온도 오차도 별도로 공개합니다. 짧은 Arrival은 후보 API에서 차단하며 기본/RL/strict는 유지합니다.</p></aside>'
    diagnostic='<h2>과거 자료 악화와 남은 유휴 편차</h2><img src="archive_groups.png" style="max-width:100%"><img src="archive_worst.png" style="max-width:100%"><img src="late_idle_offset.png" style="max-width:100%">'
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>AP 구조 보완 PC 평가</title><style>body{max-width:1100px;margin:30px auto;font:16px/1.7 sans-serif}</style><h1>AP 상태별 가열·30초 잔열 분해</h1>'+note+'<p>개발4 세션 제외평가·사후 분석. 기존29 이전 열람 자료는 전이 진단이며 독립 확인이 아닙니다. 고정 beta/tau·초기화, 에너지/기본/RL/strict 유지·기기0.</p><p><a href="metrics.csv">전체 오차</a> · <a href="worsening.csv">조건별 악화</a> · <a href="phase_errors.csv">등록 구간/방향</a> · <a href="candidate.json">별도 후보</a></p>'+body+diagnostic,encoding='utf8')
    return dict(status='pc_posthoc_completed',gates=gates,summaries=summaries,output=str(out))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reuse-development');args=p.parse_args()
    print(json.dumps(run(args.output,args.reuse_development),ensure_ascii=False,indent=2))
