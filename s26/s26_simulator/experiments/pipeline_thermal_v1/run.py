"""Fixed held-group power -> passive thermal calibration, existing data only."""
import datetime,importlib.util,json,math,msvcrt,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'thermal_balance_v1'));sys.path.insert(0,str(HERE.parent/'capacity_power_v1'))
from calibrate import read,save,sha
import power as P
from basis import thermal_basis,design
import numpy as np
spec=importlib.util.spec_from_file_location('frozen_two_mode_solver',HERE.parent/'thermal_balance_v2/run.py');solver=importlib.util.module_from_spec(spec);spec.loader.exec_module(solver)


def verify(op):
    for x in op['source']+list(op['inputs'].values())+list(op['power_models'].values()):assert sha(x['path'])==x['sha256'],'Changed pin '+x['path']


def pure_test():
    ints=[[] for _ in range(9)];ints[5]=[[0.,20.,3.]];ints[6]=[[0.,20.,3.]];ts=np.array([.25,.5,1.,10.,20.,21.,60.,300.])
    pm=dict(coef=[1.,0.]+[.1]*20,scale=[1.]*22);tm=dict(tau_fast_s=10,tau_slow_s=320,w_fast=.4,delta_C=0.,gain_fast=1.,gain_slow=2.)
    step=P.steps(ints);B=thermal_basis(step,ts,.6,0.,[10,160,320]);ep=dict(times=ts,anchor_s=0.,anchor_AP=31.,skin=30.,baseline=.6,B=B)
    base,X=design(ep,[10,320],pm,{10:0,160:1,320:2});pred=base+X@solver.beta([0.,.4,1.,2.]);reference=P.coupled(step,ts,.6,0.,31.,30.,pm,tm)
    err=float(max(abs(pred-reference[:,1])));assert err<1e-8
    return dict(status='PASS',checks=8,max_basis_scalar_cascade_error=err)


def summarize(rows,category,lo=0):
    errors=[]
    for r in rows:
        if category!='ALL' and r['pool']!=category and not(category=='R21' and r['group'].startswith('M8_R21_')):continue
        mask=np.asarray(r['times'])>=lo
        if any(mask):errors.append([float(np.mean(abs(np.asarray(r[k])[mask]-np.asarray(r['observed'])[mask]))) for k in ('predicted','parent','previous_conditional','oracle')])
    return dict(category=category,from_s=lo,sessions=len(errors),**{k:float(np.mean([e[j] for e in errors])) for j,k in enumerate(('pipeline_MAE_C','parent_MAE_C','previous_conditional_MAE_C','measured_power_oracle_MAE_C'))})


def main(op):
    verify(op);out=Path(op['output']);begin=time.monotonic();save(out/'PURE_TEST.json',pure_test())
    entries=read(op['inputs']['prepared']['path']);sessions=read(op['inputs']['sessions']['path']);by={s.get('session_uid',s['id']):s for s in sessions}
    power={g:read(p['path']) for g,p in op['power_models'].items()};indices={tau:j for j,tau in enumerate(op['basis_taus'])}
    priorprofiles=read(op['inputs']['prior_profiles']['path']);prior={p['group'] or 'FULL':next(m for m in p['fits'] if m['id']==p['selected']) for p in priorprofiles}
    previous={r['id']:r for r in read(op['inputs']['previous_conditional']['path'])};oracle={r['id']:r for r in read(op['inputs']['oracle']['path'])}
    max_basis_error=0.
    for j,e in enumerate(entries):
        for key in ('times','observed','parent_OOF'):e[key]=np.asarray(e[key])
        e['B']=thermal_basis(P.steps(by[e['id']]['activity9']['intervals']),e['times'],e['baseline'],e['anchor_s'],op['basis_taus'])
        tm=prior[e['group']];base,X=design(e,op['pairs'][e['group']],power[e['group']],indices)
        theta=[tm[k] for k in ('delta_C','w_fast','gain_fast','gain_slow')]
        max_basis_error=max(max_basis_error,float(max(abs(base+X@solver.beta(theta)-np.asarray(previous[e['id']]['predicted'])))))
        if (j+1)%40==0:print(json.dumps(dict(status='BASIS',sessions=j+1)),flush=True)
    assert max_basis_error<1e-7;save(out/'BASIS_AUDIT.json',dict(status='PASS',points=sum(len(e['times']) for e in entries),max_basis_vs_exact_scalar_error_C=max_basis_error))
    rows=[];models={};started=complete=failed=0;folds=[]
    with (out/'FIT_RECEIPTS.jsonl').open('x',encoding='utf-8') as receipts:
        def record(x):receipts.write(json.dumps(x)+'\n');receipts.flush();os.fsync(receipts.fileno())
        for group in op['groups']+['FULL']:
            verify(op);train=[e for e in entries if e['group']!=group] if group!='FULL' else entries;tests=[e for e in entries if e['group']==group]
            pm=power[group];pair=op['pairs'][group];counts={};fold=dict(group=group,train_ids=[e['id'] for e in train],train_groups=sorted({e['group'] for e in train}))
            folds.append(fold)
            for e in train:counts[e['cohort']]=counts.get(e['cohort'],0)+1
            H=np.zeros((5,5));b=np.zeros(5);c=0.
            for e in train:
                base,X=design(e,pair,pm,indices);y=e['observed']-base;w=1/(len(counts)*counts[e['cohort']]*len(y));H+=w*X.T@X;b+=w*X.T@y;c+=w*float(y@y)
            fits=[]
            for i,w0 in enumerate((.1,.9)):
                assert started<op['fit_cap'] and time.monotonic()-begin<op['wall_cap_s'],'Finite cap'
                identity=group+'_i'+str(i);record(dict(event='START',id=identity));started+=1;m=None
                try:
                    m=solver.fit(H,b,c,pair,w0);m.update(id=identity,heldout_group=group,power_model_sha256=op['power_models'][group]['sha256'],start_w=w0,
                        mode='PREDICTED_CAPACITY_POWER_DRIVEN_PASSIVE_THERMAL',physical_constants_identified=False)
                    assert m['KKT_residual']<=1e-5,'KKT nonconvergence preserved'
                    save(out/'models'/(identity+'.json'),m);fits.append(m);complete+=1;record(dict(event='COMPLETE',id=identity,sha256=sha(out/'models'/(identity+'.json'))))
                except (AssertionError,ValueError) as exc:
                    if m is not None:save(out/'models'/(identity+'.failed_candidate.json'),m)
                    failed+=1;record(dict(event='FAIL',id=identity,reason=str(exc),automatic_retry=False))
            assert fits,'No converged fit; preserve consumed namespace'
            chosen=min(fits,key=lambda m:(m['train_MSE'],m['start_w']));models[group]=chosen
            for e in tests:
                assert e['id'] not in pm['train_ids'] and e['group'] not in pm['train_groups']
                assert e['id'] not in fold['train_ids'] and e['group'] not in fold['train_groups']
                base,X=design(e,pair,pm,indices);theta=[chosen[k] for k in ('delta_C','w_fast','gain_fast','gain_slow')]
                rows.append(dict(id=e['id'],group=group,pool=e['pool'],times=e['times'].tolist(),observed=e['observed'].tolist(),predicted=(base+X@solver.beta(theta)).tolist(),
                    parent=e['parent_OOF'].tolist(),previous_conditional=previous[e['id']]['predicted'],oracle=oracle[e['id']]['predicted']))
            print(json.dumps(dict(status='PIPELINE_FOLD',group=group,started=started,complete=complete,failed=failed)),flush=True)
    assert started==op['planned_fit_START'];save(out/'TRAIN_FOLDS.json',folds);save(out/'MODEL.json',{**models['FULL'],'adopted':False});save(out/'OOF_ROWS.json.gz',rows)
    summaries=[summarize(rows,c) for c in ('ALL','OLD','M8','R21')]+[summarize(rows,'ALL',256)]
    accuracy=all(s['pipeline_MAE_C']<=min(s['parent_MAE_C'],s['previous_conditional_MAE_C']) for s in summaries)
    # Reconstruct every saved OOF from the basis/selected model; the basis itself was cross-checked against the independently quadrature-tested scalar cascade.
    checks=0;max_saved_error=0.;saved={r['id']:r for r in rows}
    for e in entries:
        m=models[e['group']];base,X=design(e,op['pairs'][e['group']],power[e['group']],indices);theta=[m[k] for k in ('delta_C','w_fast','gain_fast','gain_slow')]
        err=abs(base+X@solver.beta(theta)-np.asarray(saved[e['id']]['predicted']));max_saved_error=max(max_saved_error,float(max(err)));checks+=len(err)
    for r in [json.loads(l) for l in (out/'FIT_RECEIPTS.jsonl').read_text(encoding='utf-8').splitlines()]:
        if r['event']=='COMPLETE':assert sha(out/'models'/(r['id']+'.json'))==r['sha256'];checks+=1
    verify(op);assert max_saved_error<1e-10
    audit=dict(status='PASS_SAVED_BASIS_CASCADE_AND_LINEAGE',checks=checks,points=sum(len(r['times']) for r in rows),max_saved_reconstruction_error_C=max_saved_error,
               max_basis_vs_prior_independently_tested_cascade_error_C=max_basis_error,power_and_thermal_held_groups_both_excluded=True,physical_validation=False)
    save(out/'AUDIT.json',audit)
    result=dict(status='EXISTING_DATA_PREDICTED_POWER_THERMAL_COMPLETED',fit_START=started,fit_COMPLETE=complete,fit_FAIL=failed,sessions=len(entries),summary=summaries,
        accuracy_gate_pass=bool(accuracy),adopted=False,new_policy_environments=0,new_RL=0,new_measurements=0,observed_future_power_input=False,observed_activity_timing_input=True,
        power_energy_errors_unchanged=True,physical_constants_identified=False,elapsed_s=time.monotonic()-begin)
    save(out/'RESULT.json',result);save(out/'FINAL_PROOF.json',dict(status='PIPELINE_CANDIDATE_EVALUATED_NOT_ADOPTED',operation_sha256=sha(HERE/'OPERATION.json'),
        artifacts={n:sha(out/n) for n in ['RESULT.json','MODEL.json','AUDIT.json','OOF_ROWS.json.gz','TRAIN_FOLDS.json','BASIS_AUDIT.json','PURE_TEST.json']},new_fit=started,new_policy_environments=0,new_RL=0))
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    op=read(HERE/'OPERATION.json');verify(op);out=Path(op['output']);assert not out.exists(),'Consumed namespace'
    lock=Path(op['shared_byte_mutex']).open('r+b');locked=False
    try:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True;assert shutil.disk_usage(HERE).free>=8*1024**3
        raw=subprocess.check_output(['powershell','-NoProfile','-Command','[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-CimInstance Win32_Process -Filter "Name = \'python.exe\' OR Name = \'python3.exe\'" | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress'],text=True,encoding='utf-8')
        procs=json.loads(raw or '[]');procs=[procs] if isinstance(procs,dict) else procs
        assert len({p['ProcessId'] for p in procs}-{p['ParentProcessId'] for p in procs})<=2,'Global Python leaf cap'
        assert not any(p['ProcessId']!=os.getpid() and any(t in(p.get('CommandLine')or'') for t in('a24_simulator','s26_simulator')) for p in procs),'Other simulator owner'
        out.mkdir(parents=True);(out/'models').mkdir();save(out/'START.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=os.getpid(),operation_sha256=sha(HERE/'OPERATION.json')))
        main(op)
    except BaseException:
        if out.exists() and not(out/'FAILURE.json').exists():save(out/'FAILURE.json',dict(traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
