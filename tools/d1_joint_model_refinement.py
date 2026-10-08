"""One opt-in, development-only refit; archived evaluation and defaults stay immutable."""
import argparse
import copy
import csv
import datetime
import json
import math
import time
import traceback
from pathlib import Path

import numpy as np
from tools import d1_model_refinement as m
from tools import d1_history_model_refinement as h

BUNDLE = m.ROOT/'docs/results/joint_model_refinement_01'
SOURCES = [m.BUNDLE/'inputs.json.gz', h.BUNDLE/'inputs.json.gz', m.MODEL,
           m.ROOT/'docs/results/energy_memory30_01/session_errors.csv']
CORE = ('pre', 'pre_w', 'q', 'ap', 'actual', 'power_t', 'power_w', 'last_lane_s')
DEADLINE = None


def reserve():
    if DEADLINE is not None and time.monotonic() >= DEADLINE:
        raise TimeoutError('active budget reached; final 300 seconds reserved for receipt')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def panel():
    merged = {}; duplicates = []
    for source in SOURCES[:2]:
        for c in m.read(source):
            if c['id'] in merged:
                if any(c[k] != merged[c['id']][k] for k in CORE):
                    raise ValueError('duplicate source mismatch '+c['id'])
                duplicates.append(c['id']); continue
            merged[c['id']] = copy.deepcopy(c)
    cases = list(merged.values())
    if len(cases) != 29 or sum(c['role']=='development' for c in cases) != 9:
        raise ValueError('fixed 9 development / 20 evaluation denominator')
    for c in cases:
        c['fit_block'] = ('old_development' if c['block']=='development' else
                          'history_'+str(c['gap']) if c['block']=='history' else c['block'])
        c['evaluation_block'] = ('history_confirmation' if c['block']=='history' else c['block'])
        m.base.exposure(c['actual'], 0, 120)
        if abs(m.integral(c,-20,30)/50-c['pre_w']) > 1e-8:
            raise ValueError('baseline window mismatch')
    return cases, duplicates


def fit(cases, frozen):
    if not cases or any(c['role']!='development' for c in cases):
        raise ValueError('designated development only')
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('duplicate development')
    x=[]; y=[]
    for c in cases:
        weight=1/math.sqrt(17*len(cases))
        for a in range(35,120,5):
            x.append(m.base.exposure(c['actual'],a,a+5)*weight)
            y.append((m.integral(c,a,a+5)-5*c['pre_w'])*weight)
    x=np.array(x);y=np.array(y);norms=np.linalg.norm(x,axis=0)
    sv=np.linalg.svd(x/np.maximum(norms,1e-30),compute_uv=False)
    if np.linalg.matrix_rank(x)!=4:raise ValueError('state power unidentifiable')
    power=m.base.nnls(x,y)
    beta0=frozen['ap']['beta']; betas=beta0*np.geomspace(.2,5,61);betas[30]=beta0
    profile=[];params=frozen['ap']['parameters']
    for beta in betas:
        reserve()
        xs=[];ys=[]
        for c in cases:
            a,b,_=m.thermal.basis(m.case_input(c,c['actual']),params,float(beta))
            w=1/math.sqrt(len(a)*len(cases));xs.extend(b[:,0]*w);ys.extend((np.array(c['ap'])-a)*w)
        ax=np.array(xs);ay=np.array(ys);den=float(ax@ax)
        if den<=1e-12:raise ValueError('AP load gain unidentifiable')
        k=max(0.,float(ax@ay/den))
        profile.append(dict(beta=float(beta),k=k,mse=float(np.sum((ax*k-ay)**2))))
    best=min(profile,key=lambda r:(r['mse'],abs(math.log(r['beta']/beta0)),r['beta']))
    model=copy.deepcopy(frozen)
    model.update(version='joint-development-refit-v1', default=False, strict_support=False, experiment_ready=False)
    model['energy_increment_w']=dict(zip(m.base.STATES,map(float,power)))
    model['ap'].update(beta=best['beta'],k=best['k'],g=0.)
    columns=[]
    for field in ('beta','k'):
        delta=max(model['ap'][field],.001)*1e-4;other=copy.deepcopy(model);other['ap'][field]+=delta
        col=[]
        for c in cases:
            a=m.predict(c,c['actual'],model,dict(name='FROZEN'))[0]
            b=m.predict(c,c['actual'],other,dict(name='FROZEN'))[0]
            col.extend((np.array(b)-a)/delta/math.sqrt(len(a)*len(cases)))
        columns.append(col)
    jac=np.array(columns).T;jn=np.linalg.norm(jac,axis=0)
    js=np.linalg.svd(jac/np.maximum(jn,1e-30),compute_uv=False)
    rank=int(np.linalg.matrix_rank(jac))
    boundary=best['beta'] in (float(betas[0]),float(betas[-1]))
    return dict(model=model,development_ids=[c['id'] for c in cases],energy_scaled_singular_values=sv.tolist(),
                energy_design_rank=4,ap_scaled_singular_values=js.tolist(),ap_rank=rank,beta_boundary=boundary,
                eligible=rank==2 and not boundary,ap_profile=profile,
                practical_identification='not established by numerical rank; block-excluded coefficient variation retained')


def evaluate(c,model,mode='A_conditional'):
    seg=c['actual'] if mode=='A_conditional' else c['forecast']
    observed=m.integral(c,0,120)
    value=lambda t:m.energy_prediction(c,seg,model,dict(name='FROZEN'),t)
    pred,init=m.predict(c,seg,model,dict(name='FROZEN'))
    signed=value(120)-observed
    result=dict(observed_j=observed,predicted_j=value(120),signed_j=signed,abs_j=abs(signed),
                absolute_relative_percent=100*abs(signed)/observed,**m.base.common.score(c['ap'],pred),
                ap_start_s=c['q'][0],ap_end_s=c['q'][-1],ap_samples=len(c['q']))
    if mode=='A_conditional':result.update(h.direction(c,pred))
    boundaries=[('pre',0,35),('load',35,c['last_lane_s']),('post',c['last_lane_s'],120)]
    for label,a,b in boundaries:
        result[label+'_signed_j']=value(b)-value(a)-m.integral(c,a,b)
    if abs(sum(result[k+'_signed_j'] for k in ('pre','load','post'))-signed)>1e-8:
        raise ValueError('whole/partial energy mismatch')
    windows=[]
    for a in range(0,120,5):
        states=sorted({s['state'] for s in seg if min(a+5,s['end_s'])>max(a,s['start_s'])})
        windows.append(dict(start_s=a,end_s=a+5,states='|'.join(states),mixed=len(states)>1,
                            observed_j=m.integral(c,a,a+5),predicted_j=value(a+5)-value(a),
                            signed_j=value(a+5)-value(a)-m.integral(c,a,a+5)))
    return result,pred,init,windows,value


def group_scores(rows):
    out=[]
    for block,mode,name in sorted({(r['block'],r['mode'],r['model']) for r in rows}):
        use=[r for r in rows if (r['block'],r['mode'],r['model'])==(block,mode,name)]
        out.append(dict(block=block,mode=mode,model=name,n=len(use),energy_mae_j=float(np.mean([r['abs_j'] for r in use])),
                        energy_mape_percent=float(np.mean([r['absolute_relative_percent'] for r in use])),
                        energy_max_j=max(r['abs_j'] for r in use),ap_mae_c=float(np.mean([r['mae_c'] for r in use])),
                        ap_max_c=max(r['max_absolute_error_c'] for r in use),
                        peak_mae_c=float(np.mean([abs(r['peak_signed_error_c']) for r in use])),
                        opposite_cooling=sum(r.get('cooling_opposite') is True for r in use)))
    return out


def freeze(output):
    if output.exists():raise FileExistsError('new output required')
    contract=m.read(BUNDLE/'contract.json')
    for path,digest in contract['input_hashes'].items():
        if m.sha(m.ROOT/path)!=digest:raise ValueError('input identity')
    cases,duplicates=panel();dev=[c for c in cases if c['role']=='development'];frozen=m.read(m.MODEL)
    output.mkdir(parents=True);start=time.monotonic();folds=[]
    for block in sorted({c['fit_block'] for c in dev}):
        reserve()
        fitted=fit([c for c in dev if c['fit_block']!=block],frozen);rows=[]
        for c in dev:
            if c['fit_block']!=block:continue
            for name,model in [('FROZEN',frozen),('JOINT',fitted['model'])]:
                score=evaluate(c,model)[0];rows.append(dict(id=c['id'],block=block,mode='A_conditional',model=name,**score))
        folds.append(dict(block=block,fit=fitted,scores=rows))
    final=fit(dev,frozen)
    def gate(metrics):
        ok=[]
        for fold in folds:
            old=[r for r in fold['scores'] if r['model']=='FROZEN'];new=[r for r in fold['scores'] if r['model']=='JOINT']
            ok.extend(float(np.mean([r[k] for r in new]))<=float(np.mean([r[k] for r in old]))+1e-10 for k in metrics)
        return final['eligible'] and all(f['fit']['eligible'] for f in folds) and all(ok)
    result=dict(id='JOINT-REFIT-01',utc=now(),input_hashes=contract['input_hashes'],contract_sha256=m.sha(BUNDLE/'contract.json'),
                final=final,folds=folds,energy_development_gate=gate(['abs_j']),
                ap_development_gate=gate(['mae_c','max_absolute_error_c']),
                candidates=1,fit_calls=4,beta_profiles=244,development_sessions=9,evaluation_sessions=20,
                duplicates_removed=duplicates,fit_seconds=time.monotonic()-start,accuracy_pass=None,default=False)
    m.write(output/'candidate_freeze.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('final','folds','input_hashes','duplicates_removed')}))


def paired(rows):
    out=[]
    # Index pairs were fixed in the existing sustained protocol; history gap pairs are nominal only.
    groups=[('sustained_'+str(i),'sustained_'+str(i+1)) for i in range(0,8,2)]
    groups += [(f'confirmation_{g}_CPU',f'confirmation_{g}_PAR') for g in (30,180)]
    for cpu,par in groups:
        first=next(r for r in rows if r['id']==cpu)
        if first['policy']=='B2_PARALLEL_ONLINE_V1':cpu,par=par,cpu
        for mode in ('A_conditional','B_arrival'):
            for model in ('FROZEN','JOINT'):
                a=next((r for r in rows if (r['id'],r['mode'],r['model'])==(cpu,mode,model)),None)
                b=next((r for r in rows if (r['id'],r['mode'],r['model'])==(par,mode,model)),None)
                if a is None or b is None:continue
                observed=b['observed_j']-a['observed_j'];pred=b['predicted_j']-a['predicted_j']
                out.append(dict(cpu=cpu,par=par,block=a['block'],mode=mode,model=model,
                                observed_difference_j=observed,predicted_difference_j=pred,
                                signed_difference_error_j=pred-observed,abs_difference_error_j=abs(pred-observed),
                                peak_difference_error_c=b['peak_signed_error_c']-a['peak_signed_error_c']))
    return out


def memory_pairs():
    with SOURCES[3].open(encoding='utf8') as f:rows=list(csv.DictReader(f))
    out=[]
    for cpu,par in [(f'sustained_{i}',f'sustained_{i+1}') for i in range(0,8,2)]+[(f'confirmation_{g}_CPU',f'confirmation_{g}_PAR') for g in (30,180)]:
        if next(r for r in rows if r['id']==cpu)['policy']=='B2_PARALLEL_ONLINE_V1':cpu,par=par,cpu
        for method in ('FROZEN','MEMORY30'):
            a=next(r for r in rows if r['id']==cpu and r['method']==method);b=next(r for r in rows if r['id']==par and r['method']==method)
            obs=float(b['observed_80s_j'])-float(a['observed_80s_j']);pred=float(b['predicted_80s_j'])-float(a['predicted_80s_j'])
            out.append(dict(cpu=cpu,par=par,method=method,window='35..115 s / sequential observations',observed_difference_j=obs,
                            predicted_difference_j=pred,abs_difference_error_j=abs(pred-obs),full120_error=None,policy_counterfactual=False))
    return out


def score(output):
    frozen_result=m.read(output/'candidate_freeze.json');contract=m.read(BUNDLE/'contract.json')
    for path,digest in contract['input_hashes'].items():
        if m.sha(m.ROOT/path)!=digest:raise ValueError('input changed after freeze')
    if frozen_result['contract_sha256']!=m.sha(BUNDLE/'contract.json'):raise ValueError('contract changed')
    if (output/'summary.json').exists():raise FileExistsError('evaluation already completed')
    cases,_=panel();original=m.read(m.MODEL);candidate=frozen_result['final']['model'];rows=[];paths=[];windows=[]
    m.write(output/'evaluation_started.json',dict(utc=now(),freeze_sha256=m.sha(output/'candidate_freeze.json')))
    for c in cases:
        reserve()
        if c['role']=='development':continue
        for mode in ['A_conditional']+(['B_arrival'] if 'forecast' in c else []):
            for name,model in [('FROZEN',original),('JOINT',candidate)]:
                metrics,pred,init,bins,value=evaluate(c,model,mode)
                row=dict(id=c['id'],block=c['evaluation_block'],policy=c['policy'],mode=mode,model=name,**metrics);rows.append(row)
                windows.extend(dict(id=c['id'],mode=mode,model=name,**w) for w in bins)
                paths.extend(dict(id=c['id'],mode=mode,model=name,t_s=t,observed_ap_c=obs,predicted_ap_c=p,
                                  signed_ap_c=p-obs) for t,obs,p in zip(c['q'],c['ap'],pred))
                # Energy path uses registered 0..120 boundaries, not AP sensor queries.
                for t in range(0,121):
                    paths.append(dict(id=c['id'],mode=mode,model=name,t_s=t,observed_energy_j=m.integral(c,0,t),predicted_energy_j=value(t)))
    comparison=group_scores(rows);pairs=paired(rows);rolling=memory_pairs()
    for name,data in [('session_errors.csv',rows),('comparison.csv',comparison),('paths.csv',paths),('windows.csv',windows),
                      ('paired_errors.csv',pairs),('memory30_paired_errors.csv',rolling),
                      ('development_folds.csv',[r for f in frozen_result['folds'] for r in f['scores']])]:m.table(output/name,data)
    m.write(output/'candidate_model.json',candidate)
    checks=[]
    for block in ('confirmation','history_confirmation','sustained'):
        a=next(r for r in comparison if (r['block'],r['mode'],r['model'])==(block,'A_conditional','FROZEN'))
        b=next(r for r in comparison if (r['block'],r['mode'],r['model'])==(block,'A_conditional','JOINT'))
        checks.append(dict(block=block,energy_nonworse=b['energy_mae_j']<=a['energy_mae_j']+1e-10 and b['energy_max_j']<=a['energy_max_j']+1e-10,
                           ap_nonworse=b['ap_mae_c']<=a['ap_mae_c']+1e-10 and b['ap_max_c']<=a['ap_max_c']+1e-10 and b['opposite_cooling']<=a['opposite_cooling']))
    ps={name:float(np.mean([r['abs_difference_error_j'] for r in pairs if r['model']==name and r['block']=='sustained' and r['mode']=='A_conditional'])) for name in ('FROZEN','JOINT')}
    summary=dict(id='JOINT-REFIT-01',utc=now(),evaluation_rows=len(rows),evaluated_sessions=20,comparison=comparison,checks=checks,
                 policy_pair_mae_j=ps,energy_development_gate=frozen_result['energy_development_gate'],ap_development_gate=frozen_result['ap_development_gate'],
                 joint_general_adoption=frozen_result['energy_development_gate'] and frozen_result['ap_development_gate'] and all(c['energy_nonworse'] and c['ap_nonworse'] for c in checks) and ps['JOINT']<=ps['FROZEN'],
                 freeze_sha256=m.sha(output/'candidate_freeze.json'),model_sha256=m.sha(m.MODEL),
                 posthoc=True,accuracy_pass=None,experiment_ready=False,default_replaced=False,device_commands=0,policy_simulations=0,rl_training=0)
    m.write(output/'summary.json',summary);print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['freeze','evaluate']);p.add_argument('--output',required=True)
    args=p.parse_args();destination=Path(args.output)
    DEADLINE=time.monotonic()+14400-300
    try:
        (freeze if args.action=='freeze' else score)(destination)
    except BaseException as exc:
        if destination.exists():
            stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')
            m.write(destination/('failure_'+stamp+'.json'),dict(utc=now(),action=args.action,
                    original_error=dict(type=type(exc).__name__,message=str(exc),stack=traceback.format_exc()),device_commands=0))
        raise
