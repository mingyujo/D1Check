"""One posthoc robust gain candidate; never changes the frozen/default model."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import numpy as np
from tools import d1_model_refinement as m

NAME = 'ROBUST_LOAD_GAIN_V1'


def fit(cases, frozen, allowed_ids):
    if not cases or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('empty/duplicate training sessions')
    if any(c['id'] not in allowed_ids or c['block']=='sustained' for c in cases):
        raise ValueError('evaluation session cannot fit')
    gains=[]
    for c in cases:
        end=c['last_lane_s']
        exposure=m.base.exposure(c['actual'],35,end)
        extra=float(exposure @ np.array([frozen['energy_increment_w'][k] for k in m.base.STATES]))
        if extra<=1e-9:raise ValueError('unidentified energy gain')
        # Only registered load-envelope energy; late background spikes do not fit gain.
        energy=(m.integral(c,35,end)-c['pre_w']*(end-35))/extra
        a,x,_=m.thermal.basis(m.case_input(c,c['actual']),frozen['ap']['parameters'],frozen['ap']['beta'])
        use=np.array(c['q'])<=end
        u=x[use,0]; target=np.array(c['ap'])[use]-a[use]-frozen['ap']['g']*x[use,1]
        if len(u)<2 or float(u@u)<1e-9:raise ValueError('unidentified AP gain')
        k=float(u@target/(u@u))
        gains.append(dict(id=c['id'],energy_gain=energy,k=k))
    energy=float(np.median([r['energy_gain'] for r in gains]));k=float(np.median([r['k'] for r in gains]))
    if not np.isfinite([energy,k]).all() or min(energy,k)<0:raise ValueError('invalid fitted gain; not clipped')
    return dict(name=NAME,energy_gain=energy,k=k,session_gains=gains,default=False,posthoc=True)


def model(frozen,candidate):
    out=copy.deepcopy(frozen)
    out['ap']['k']=candidate['k']
    out['energy_increment_w']={k:v*candidate['energy_gain'] for k,v in frozen['energy_increment_w'].items()}
    return out


def features(c):
    t=np.array([p['t'] for p in c['pre']]);ap=np.array([p['ap'] for p in c['pre']])
    return dict(id=c['id'],block=c['block'],policy=c['policy'],pre_w=c['pre_w'],
        ap_last=float(ap[-1]),ap_slope=float(np.polyfit(t,ap,1)[0]),
        power_trend_w=m.integral(c,10,30)/20-m.integral(c,-20,0)/20,
        pre_span_s=float(t[-1]-t[0]))


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    contract=m.read('docs/results/model_refinement_02/contract.json')
    inputs=m.BUNDLE/'inputs.json.gz';frozen=m.read(m.MODEL);cases=m.read(inputs)
    if m.sha(m.MODEL)!=m.MODEL_SHA or m.sha(inputs)!=contract['inputs_sha256']:raise ValueError('source hash')
    train=[c for c in cases if c['block']!='sustained'];test=[c for c in cases if c['block']=='sustained']
    if len(train)!=9 or len(test)!=8:raise ValueError('session denominator')
    ids={c['id'] for c in train};candidate=fit(train,frozen,ids)
    folds=[]
    for c in train:
        local=fit([d for d in train if d['id']!=c['id']],frozen,ids)
        for label,mod in [('FROZEN',frozen),(NAME,model(frozen,local))]:
            score,_,_=m.metrics(c,c['actual'],mod,dict(name='FROZEN'))
            folds.append(dict(id=c['id'],candidate=label,**score))
    # Diagnostic candidate, no deployment selected using later evaluation.
    m.write(out/'candidate.json',dict(**candidate,training_ids=sorted(ids),evaluation_ids=[c['id'] for c in test],
        contract_sha256=m.sha('docs/results/model_refinement_02/contract.json'),frozen_sha256=m.MODEL_SHA))
    m.table(out/'development_loso.csv',folds)
    rows=[];paths=[];windows=[]
    for c in cases:
        for mode,key in [('A_conditional','actual'),('B_arrival','forecast')]:
            for label,mod in [('FROZEN',frozen),(NAME,model(frozen,candidate))]:
                info=dict(id=c['id'],block=c['block'],policy=c['policy'],mode=mode,candidate=label,
                          role='posthoc_evaluation' if c in test else 'posthoc_development')
                score,ap,_=m.metrics(c,c[key],mod,dict(name='FROZEN'));rows.append(dict(**info,**score))
                for t,y,p in zip(c['q'],c['ap'],ap):paths.append(dict(**info,kind='AP',t=t,observed=y,predicted=p))
                for t in range(121):paths.append(dict(**info,kind='J',t=t,observed=m.integral(c,0,t),
                    predicted=m.energy_prediction(c,c[key],mod,dict(name='FROZEN'),t)))
                for t in range(0,120,5):
                    pred=m.energy_prediction(c,c[key],mod,dict(name='FROZEN'),t+5)-m.energy_prediction(c,c[key],mod,dict(name='FROZEN'),t)
                    states=sorted({s['state'] for s in c['actual'] if min(t+5,s['end_s'])>max(t,s['start_s'])})
                    windows.append(dict(**info,start_s=t,end_s=t+5,states='|'.join(states),mixed=len(states)>1,
                                        signed_j=pred-m.integral(c,t,t+5)))
    summary=[]
    for mode in ('A_conditional','B_arrival'):
        for block in ('development','confirmation','sustained'):
            refs={r['id']:r for r in rows if r['block']==block and r['mode']==mode and r['candidate']=='FROZEN'}
            for name in ('FROZEN',NAME):
                use=[r for r in rows if r['block']==block and r['mode']==mode and r['candidate']==name]
                summary.append(dict(mode=mode,block=block,candidate=name,n=len(use),
                    j_mae=float(np.mean([r['abs_j'] for r in use])),ap_mae=float(np.mean([r['mae_c'] for r in use])),
                    max_ap_error=max(r['max_absolute_error_c'] for r in use),
                    j_worse=sum(r['abs_j']>refs[r['id']]['abs_j']+1e-10 for r in use),
                    ap_worse=sum(r['mae_c']>refs[r['id']]['mae_c']+1e-10 for r in use)))
    pairs=[]
    for p in range(4):
        pairids={c['policy']:c['id'] for c in test if c['index']//2==p}
        for mode in ('A_conditional','B_arrival'):
            for name in ('FROZEN',NAME):
                r={x['id']:x for x in rows if x['candidate']==name and x['mode']==mode}
                a,b=[r[pairids[k]] for k in ('CPU_URGENT_ONLINE_V1','B2_PARALLEL_ONLINE_V1')]
                pairs.append(dict(pair=p,mode=mode,candidate=name,difference_error_j=b['signed_j']-a['signed_j'],
                    peak_difference_error_c=b['peak_signed_error_c']-a['peak_signed_error_c']))
    ff=[features(c) for c in cases]
    # Fixed pre-only nearest-neighbour diagnostic, leave whole session out.
    # Predict signed energy residual; no gating/exclusion or fitting after seeing held-out residual.
    keys=['pre_w','ap_last','ap_slope','power_trend_w']
    for c,f in zip(cases,ff):
        pool=[d for d in train if d['id']!=c['id']]
        x=np.array([[features(d)[k] for k in keys] for d in pool]);scale=np.std(x,axis=0)
        if np.any(scale<1e-12):raise ValueError('unidentified pre-feature scale')
        distance=np.linalg.norm((x-np.array([f[k] for k in keys]))/scale,axis=1)
        near=pool[int(np.argmin(distance))]
        err=lambda id:next(r['signed_j'] for r in rows if r['id']==id and r['mode']=='A_conditional' and r['candidate']=='FROZEN')
        f.update(nearest_training_id=near['id'],distance=float(min(distance)),observed_signed_j=err(c['id']),
                 nearest_residual_j=err(near['id']),residual_prediction_abs_error_j=abs(err(c['id'])-err(near['id'])))
    for filename,data in [('session_errors',rows),('comparison',summary),('paired_errors',pairs),('pre_features',ff),('windows',windows)]:m.table(out/(filename+'.csv'),data)
    m.table(out/'paths.csv',paths)
    (out/'paths.csv.gz').write_bytes(gzip.compress((out/'paths.csv').read_bytes(),mtime=0))
    m.write(out/'summary.json',dict(comparison=summary,candidate=candidate,device_commands=0,posthoc=True,
        independent_blind_validation=False,default_changed=False,experiment_ready=False))
    plot(out,rows,paths)
    return summary


def plot(out,rows,paths):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ids=list(dict.fromkeys(r['id'] for r in rows if r['block']=='sustained'))
    fig,ax=plt.subplots(2,1,figsize=(12,7))
    for axis,field,label in [(ax[0],'abs_j','Absolute energy error (J), 0-120s'),(ax[1],'mae_c','AP MAE (C), post-load onset through cooling')]:
        for name in ('FROZEN',NAME):
            axis.plot(range(8),[next(r[field] for r in rows if r['id']==id and r['mode']=='A_conditional' and r['candidate']==name) for id in ids],marker='o',label=name)
        axis.set_xticks(range(8),ids);axis.set_ylabel(label);axis.legend();axis.grid(alpha=.3)
    fig.suptitle('Previously seen sustained sessions: posthoc evaluation, no adoption');fig.tight_layout();fig.savefig(out/'comparison.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(8,2,figsize=(13,22))
    for i,id in enumerate(ids):
        for j,kind in enumerate(('J','AP')):
            for name in ('FROZEN',NAME):
                use=[r for r in paths if r['id']==id and r['kind']==kind and r['candidate']==name and r['mode']=='A_conditional']
                if name=='FROZEN':axes[i,j].plot([r['t'] for r in use],[r['observed'] for r in use],color='black',label='Observed')
                axes[i,j].plot([r['t'] for r in use],[r['predicted'] for r in use],label=name)
            axes[i,j].set_title(id+' '+kind);axes[i,j].set_xlabel('Android relative seconds');axes[i,j].legend(fontsize=7)
    fig.tight_layout();fig.savefig(out/'paths.png',dpi=120);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    print(json.dumps(run(p.parse_args().output),indent=2))
