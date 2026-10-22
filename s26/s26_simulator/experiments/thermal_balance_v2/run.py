"""Two passive thermal modes, registered all-seen measured-power replay only."""
import datetime,itertools,json,math,msvcrt,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'): os.environ[key]='1'
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'thermal_balance_v1'))
from calibrate import read,save,sha
from rc_model import features
import numpy as np
from scipy.optimize import minimize


def verify(op):
    for x in op['source']+list(op['inputs'].values()):
        assert sha(x['path'])==x['sha256'],'Changed pin '+x['path']


def design(ep,pair):
    f,s=pair
    age=ep['times']-ep['anchor_s'];ef=np.exp(-age/f);es=np.exp(-age/s)
    base=ep['skin']+(ep['anchor_AP']-ep['skin'])*es
    X=np.column_stack((1-es,(ep['anchor_AP']-ep['skin'])*(ef-es),-(ef-es),
                       ep['features'][f][1][:,1],ep['features'][s][1][:,1]))
    return base,X


def beta(theta):
    d,w,gf,gs=theta
    return np.array([d,w,d*w,gf,gs])


def fit(H,b,c,pair,w0):
    def fun(theta):
        d,w,gf,gs=theta;v=beta(theta);res=H@v-b
        J=np.array([[1,0,0,0],[0,1,0,0],[w,d,0,0],[0,0,1,0],[0,0,0,1]])
        return float(v@H@v-2*b@v+c),2*J.T@res
    result=minimize(fun,np.array([0.,w0,1.,1.]),jac=True,method='L-BFGS-B',
                    bounds=[(None,None),(0,1),(0,None),(0,None)],
                    options=dict(maxiter=1000,maxfun=6000,ftol=1e-12,gtol=1e-7))
    theta=result.x;loss,grad=fun(theta)
    residuals=[abs(grad[0])]
    for j in (1,2,3):
        lo=theta[j]<=1e-7;hi=j==1 and theta[j]>=1-1e-7
        residuals.append(max(0.,-grad[j]) if lo else max(0.,grad[j]) if hi else abs(grad[j]))
    kkt=max(residuals)
    assert np.isfinite(theta).all() and np.isfinite(loss),'Nonfinite optimizer'
    return dict(tau_fast_s=pair[0],tau_slow_s=pair[1],delta_C=float(theta[0]),w_fast=float(theta[1]),
                gain_fast=float(theta[2]),gain_slow=float(theta[3]),train_MSE=loss,KKT_residual=float(kkt),
                optimizer_success=bool(result.success),optimizer_message=str(result.message),iterations=int(result.nit),evaluations=int(result.nfev))


def summarize(rows,category,lo=0):
    picked=[r for r in rows if category=='ALL' or r['pool']==category or category=='R21' and r['group'].startswith('M8_R21_')]
    errors=[]
    for r in picked:
        mask=np.asarray(r['times'])>=lo
        if not any(mask):continue
        y=np.asarray(r['observed'])[mask]
        errors.append([float(np.mean(abs(np.asarray(r[k])[mask]-y))) for k in ('predicted','single_RC','parent_OOF','anchor_prediction')])
    return dict(category=category,from_s=lo,sessions=len(errors),**{key:float(np.mean([e[j] for e in errors])) if errors else None
                for j,key in enumerate(('two_RC_MAE_C','single_RC_MAE_C','parent_MAE_C','anchor_MAE_C'))})


def main(op):
    out=Path(op['output']);verify(op)
    entries=read(op['inputs']['prepared']['path']);single={r['id']:r for r in read(op['inputs']['single_OOF']['path'])}
    for ep in entries:
        for key in ('times','observed','parent_OOF','power_times','power_values'):ep[key]=np.asarray(ep[key])
        ep['features']={tau:features(ep,tau) for tau in op['tau_grid_s']}
    pairs=list(itertools.combinations(op['tau_grid_s'],2));assert len(pairs)==21
    for ep in entries:
        ep['suff']={}
        for pair in pairs:
            base,X=design(ep,pair);y=ep['observed']-base;n=len(y)
            ep['suff'][pair]=(X.T@X/n,X.T@y/n,float(y@y/n))
    rows,profiles,train_folds=[],[],[];models={};started=complete=failed=0;begin=time.monotonic()
    with (out/'FIT_RECEIPTS.jsonl').open('x',encoding='utf-8') as receipts:
        def record(x):receipts.write(json.dumps(x)+'\n');receipts.flush();os.fsync(receipts.fileno())
        for group in op['groups']+[None]:
            verify(op);assert shutil.disk_usage(HERE).free>=8*1024**3
            train=[e for e in entries if e['group']!=group] if group else entries
            test=[e for e in entries if e['group']==group] if group else []
            train_folds.append(dict(group=group,train_ids=[e['id'] for e in train],train_groups=sorted({e['group'] for e in train})))
            counts={}
            for e in train:counts[e['cohort']]=counts.get(e['cohort'],0)+1
            eligible=[]
            for pair in pairs:
                H=np.zeros((5,5));b=np.zeros(5);c=0.
                for e in train:
                    w=1/(len(counts)*counts[e['cohort']]);h,bb,cc=e['suff'][pair];H+=w*h;b+=w*bb;c+=w*cc
                for start,w0 in enumerate((.1,.9)):
                    assert started<op['fit_cap'] and time.monotonic()-begin<op['wall_cap_s'],'Finite cap'
                    identity=(group or 'FULL')+f'_f{pair[0]}_s{pair[1]}_i{start}'
                    started+=1;record(dict(event='START',id=identity,sequence=started))
                    try:
                        m=fit(H,b,c,pair,w0);m.update(id=identity,heldout_group=group,start_w=w0)
                        assert m['KKT_residual']<=1e-5,'KKT nonconvergence preserved'
                        save(out/'models'/(identity+'.json'),m);models[identity]=m;eligible.append(m);complete+=1
                        record(dict(event='COMPLETE',id=identity,model_sha256=sha(out/'models'/(identity+'.json'))))
                    except (AssertionError,ValueError) as exc:
                        failed+=1;record(dict(event='FAIL',id=identity,reason=str(exc),automatic_retry=False))
            assert eligible,'No converged fit in fold; preserve all consumed identities'
            chosen=min(eligible,key=lambda m:(m['train_MSE'],m['tau_fast_s'],m['tau_slow_s'],m['start_w']))
            profiles.append(dict(group=group,selected=chosen['id'],fits=eligible))
            theta=[chosen[k] for k in ('delta_C','w_fast','gain_fast','gain_slow')]
            for ep in test:
                base,X=design(ep,(chosen['tau_fast_s'],chosen['tau_slow_s']));pred=base+X@beta(theta)
                rows.append(dict(id=ep['id'],group=ep['group'],pool=ep['pool'],model=chosen['id'],
                    times=ep['times'].tolist(),observed=ep['observed'].tolist(),predicted=pred.tolist(),
                    single_RC=single[ep['id']]['predicted'],parent_OOF=ep['parent_OOF'].tolist(),anchor_prediction=[ep['anchor_AP']]*len(pred)))
            if group is None:full=chosen
            print(json.dumps(dict(status='FOLD',group=group,started=started,complete=complete,failed=failed,
                                  selected_taus=[chosen['tau_fast_s'],chosen['tau_slow_s']])),flush=True)
    assert started==op['planned_fit_START']
    save(out/'TRAIN_FOLDS.json',train_folds);save(out/'PROFILES.json',profiles);save(out/'MODEL.json',{**full,'adopted':False})
    save(out/'OOF_ROWS.json.gz',rows)
    summaries=[summarize(rows,c) for c in ('ALL','OLD','M8','R21')]+[summarize(rows,'ALL',256)]
    accuracy=all(s['two_RC_MAE_C']<=min(s['single_RC_MAE_C'],s['parent_MAE_C']) for s in summaries)
    result=dict(status='ALL_SEEN_TWO_MODE_REPLAY_COMPLETED',fit_START=started,fit_COMPLETE=complete,fit_FAIL=failed,
        sessions=len(entries),summary=summaries,accuracy_gate_pass=bool(accuracy),adopted=False,deployment_gate_pass=False,
        new_policy_environments=0,new_RL=0,new_measurements=0,observed_future_power_input=True,
        optimizer_global_minimum_proven=False,elapsed_s=time.monotonic()-begin)
    save(out/'RESULT.json',result)
    # Independent saved-only JS recurrence replay, plus group/receipt and passive response checks.
    cases=[];folds={f['group']:f for f in train_folds};checks=0
    for ep in entries:
        r=next(r for r in rows if r['id']==ep['id']);assert ep['id'] not in folds[ep['group']]['train_ids']
        assert ep['group'] not in folds[ep['group']]['train_groups'];checks+=2
        case={k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in ep.items() if k not in ('features','suff')};case['model']=r['model'];cases.append(case)
    replay=subprocess.run(['node',str(HERE/'replay.cjs')],input=json.dumps(dict(cases=cases,models=models)),capture_output=True,text=True,encoding='utf-8',check=True)
    saved={r['id']:r for r in rows};err=0.
    for r in json.loads(replay.stdout):
        delta=abs(np.asarray(r['predicted'])-np.asarray(saved[r['id']]['predicted']));err=max(err,float(max(delta)));checks+=len(delta)
    assert err<1e-8
    receipts=[json.loads(l) for l in (out/'FIT_RECEIPTS.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len({r['id'] for r in receipts if r['event']=='START'})==started
    for r in receipts:
        if r['event']=='COMPLETE':assert sha(out/'models'/(r['id']+'.json'))==r['model_sha256'];checks+=1
    for p in profiles:assert min(p['fits'],key=lambda m:(m['train_MSE'],m['tau_fast_s'],m['tau_slow_s'],m['start_w']))['id']==p['selected'];checks+=1
    pure=json.loads(subprocess.check_output(['node',str(HERE/'replay.cjs'),'test'],text=True));assert pure['status']=='PASS'
    verify(op)
    audit=dict(status='PASS_SAVED_REPLAY_AND_MATH_ONLY',checks=checks+pure['checks'],points=sum(len(r['times']) for r in rows),
               max_JS_python_error_C=err,fit_START=started,fit_COMPLETE=complete,fit_FAIL=failed,physical_validation=False)
    save(out/'AUDIT.json',audit)
    lines=['# 두 시간상수 열응답 후보의 개발 검증','',
      '실측 전력 입력의 두 수동 열응답 mode다. 기존 단일 RC의 긴 구간 악화 후 별도 등록했다. 온도 clamp는 없다. 이미 본 자료의 그룹 OOF이며 미래 전력/속도/기기열완화 검증을 대신하지 않는다.','',
      f"FULL fast/slow tau={full['tau_fast_s']}/{full['tau_slow_s']}초, 초기 fast비중={full['w_fast']:.6f}, Gf/Gs={full['gain_fast']:.6f}/{full['gain_slow']:.6f}, delta={full['delta_C']:.6f}℃.",'',
      '|자료/시간|세션|두 RC MAE℃|단일 RC MAE℃|원 AP MAE℃|초기 AP MAE℃|','|---|---:|---:|---:|---:|---:|']
    for s in summaries:lines.append(f"|{s['category']} / {s['from_s']}초 이후|{s['sessions']}|{s['two_RC_MAE_C']:.4f}|{s['single_RC_MAE_C']:.4f}|{s['parent_MAE_C']:.4f}|{s['anchor_MAE_C']:.4f}|")
    lines+=['',f"fit START{started}/완료{complete}/보존실패{failed}. 정확도 screen {'PASS' if accuracy else 'FAIL'}. 정책환경 채택 **0**. JS/Python독립 replay {audit['points']}점 최대차{err:.3g}℃. optimizer의 전역최솟값 또는 실기기 독립 정확도를 주장하지 않는다.",'',
      '수동 열모형만으로 CPU대기를 분리한 미래 전력과 기기별 thermal severity/속도 변화를 검증할 수 없다. 온도 marginal 범위 또는 수학적 안정성만으로 합성 triple/지속부하를 지원한다고 판정하지 않는다. 새 정책환경/RL/기기측정/환경예약0.','',
      '[작업량 확대/원인/단일 RC 결과](../../../../THERMAL_REPAIR_REPORT_KO.md). 이 두 RC 후보도 기본 엔진에 연결하지 않았다.','']
    with (out/'REPORT_KO.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines))
    save(out/'FINAL_PROOF.json',dict(status='TWO_MODE_CANDIDATE_EVALUATED_NOT_ADOPTED',operation_sha256=sha(HERE/'OPERATION.json'),
        artifacts={name:sha(out/name) for name in ['RESULT.json','MODEL.json','AUDIT.json','REPORT_KO.md','TRAIN_FOLDS.json','PROFILES.json','OOF_ROWS.json.gz']},
        new_fit=started,new_policy_environments=0,new_RL=0,failed_identity_retry=False))
    print(json.dumps(dict(status='FINISHED',fit_START=started,fit_COMPLETE=complete,fit_FAIL=failed,accuracy_screen=accuracy,adopted=False)),flush=True)


if __name__=='__main__':
    op=read(HERE/'OPERATION.json');verify(op);out=Path(op['output']);assert not out.exists(),'Consumed namespace'
    lock=Path(op['shared_byte_mutex']).open('r+b');locked=False
    try:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
        assert shutil.disk_usage(HERE).free>=8*1024**3
        raw=subprocess.check_output(['powershell','-NoProfile','-Command',
          '[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-CimInstance Win32_Process -Filter "Name = \'python.exe\' OR Name = \'python3.exe\'" | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress'],text=True,encoding='utf-8')
        processes=json.loads(raw or '[]');processes=[processes] if isinstance(processes,dict) else processes
        assert len({p['ProcessId'] for p in processes}-{p['ParentProcessId'] for p in processes})<=2,'Global Python leaf cap'
        assert not any(p['ProcessId']!=os.getpid() and any(t in (p.get('CommandLine') or '') for t in ('a24_simulator','s26_simulator')) for p in processes),'Other simulator owner'
        out.mkdir(parents=True);(out/'models').mkdir();save(out/'START.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=os.getpid(),operation_sha256=sha(HERE/'OPERATION.json')))
        main(op)
    except BaseException:
        if out.exists() and not (out/'FAILURE.json').exists():save(out/'FAILURE.json',dict(traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
