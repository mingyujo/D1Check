"""Existing-data-only capacity proxy calibration and conditional thermal replay."""
import datetime,json,math,msvcrt,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'thermal_balance_v1'))
from calibrate import read,save,sha
import numpy as np
import power as P


def verify(op):
    for x in op['source']+list(op['inputs'].values()):assert sha(x['path'])==x['sha256'],'Changed pin '+x['path']


def quad_test():
    from scipy.integrate import quad
    ints=[[] for _ in range(9)];ints[5]=[[0.,20.,3.]];ints[6]=[[0.,20.,3.]]
    ts=np.array([.25,.5,1.,10.,20.,21.,60.,300.]);m=dict(coef=[1.,0.]+[.1]*20,scale=[1.]*22)
    tm=dict(tau_fast_s=10,tau_slow_s=320,w_fast=.4,delta_C=0.,gain_fast=1.,gain_slow=2.)
    result=P.coupled(P.steps(ints),ts,.6,0.,31.,30.,m,tm);max_error=0.
    def pulse(t):
        box=min(1,max(0,t/.5))-min(1,max(0,(t-20)/.5))
        tails=[-math.expm1(-t/tau) if t<=20 else math.exp(-(t-20)/tau)-math.exp(-t/tau) for tau in (1,10,60)]
        return 1.+.2*(box+sum(tails))
    for j,t in enumerate(ts):
        hs=[]
        points=[x for x in (.5,20,20.5) if 0<x<t]
        for ht in (10,320):hs.append(quad(lambda u: math.exp(-(t-u)/ht)*(pulse(u)-.6)/ht,0,t,points=points,epsabs=1e-10,epsrel=1e-10)[0])
        expected=30.+(.4*math.exp(-t/10)+.6*math.exp(-t/320))+hs[0]+2*hs[1]
        energy=quad(pulse,0,t,points=points,epsabs=1e-10,epsrel=1e-10)[0]
        # Area includes 30s baseline history; subtract its exactly known constant area.
        max_error=max(max_error,abs(result[j,1]-expected),abs(result[j,2]-30.-energy),abs(result[j,0]-pulse(t)))
    assert max_error<1e-8
    return dict(status='PASS',checks=24,max_error=max_error,scope='Independent quadrature of box ramp/power tails/resonant two-mode cascade and energy')


def main(op):
    verify(op);out=Path(op['output']);begin=time.monotonic()
    save(out/'CASCADE_TEST.json',quad_test())
    old=read(op['inputs']['old_OOF']['path']);sessions=read(op['inputs']['sessions']['path']);by={s.get('session_uid',s['id']):s for s in sessions}
    entries=[]
    for r in old:
        if r['target']!='POWER_API':continue
        s=by[r['id']];baseline=s['targets']['POWER_API']['baseline']['median_api_w'];st=P.steps(s['activity9']['intervals'])
        entries.append(dict(id=r['id'],group=r['group'],pool=r['pool'],cohort=s['cohort'],baseline=baseline,step=st,
             times=np.asarray(r['times']),observed=np.asarray(r['observed']),parent=np.asarray(r['predicted']),
             X=P.features(st,r['times'],baseline),intervals=s['activity9']['intervals']))
    assert len(entries)==209 and sorted({e['group'] for e in entries})==op['groups']
    models={};rows=[];started=0
    with (out/'FIT_RECEIPTS.jsonl').open('x',encoding='utf-8') as receipts:
        def record(x):receipts.write(json.dumps(x)+'\n');receipts.flush();os.fsync(receipts.fileno())
        for group in op['groups']+[None]:
            verify(op);assert started<op['fit_cap'] and time.monotonic()-begin<op['wall_cap_s']
            train=[e for e in entries if e['group']!=group] if group else entries;tests=[e for e in entries if e['group']==group] if group else []
            identity=group or 'FULL';record(dict(event='START',id=identity));started+=1
            counts={}
            for e in train:counts[e['cohort']]=counts.get(e['cohort'],0)+1
            X=np.vstack([e['X'] for e in train]);y=np.concatenate([e['observed'] for e in train])
            w=np.concatenate([np.full(len(e['times']),1/(len(counts)*counts[e['cohort']]*len(e['times']))) for e in train])
            m=P.fit(X,y,w);m.update(id=identity,heldout_group=group,train_ids=[e['id'] for e in train],train_groups=sorted({e['group'] for e in train}))
            save(out/'models'/(identity+'.json'),m);models[identity]=m;record(dict(event='COMPLETE',id=identity,sha256=sha(out/'models'/(identity+'.json'))))
            for e in tests:
                pred=P.predict(e['X'],m);obs=e['observed'];area=float(np.trapezoid(obs,e['times']));assert min(pred)>0 and area>0
                rows.append(dict(id=e['id'],group=group,pool=e['pool'],model=identity,times=e['times'].tolist(),observed=obs.tolist(),predicted=pred.tolist(),parent=e['parent'].tolist(),
                    MAE_API_W=float(np.mean(abs(pred-obs))),parent_MAE_API_W=float(np.mean(abs(e['parent']-obs))),
                    relative_J_error=float((np.trapezoid(pred,e['times'])-area)/area),parent_relative_J_error=float((np.trapezoid(e['parent'],e['times'])-area)/area)))
            print(json.dumps(dict(status='POWER_FOLD',group=group,fits=started)),flush=True)
    assert started==op['planned_fit_START'];save(out/'MODEL.json',models['FULL']);save(out/'OOF_ROWS.json.gz',rows)
    summary=[]
    for category in ('ALL','OLD','M8','R21'):
        rs=[r for r in rows if category=='ALL' or r['pool']==category or category=='R21' and r['group'].startswith('M8_R21_')]
        summary.append(dict(category=category,sessions=len(rs),MAE_API_W=float(np.mean([r['MAE_API_W'] for r in rs])),parent_MAE_API_W=float(np.mean([r['parent_MAE_API_W'] for r in rs])),
            median_abs_relative_J_error=float(np.median([abs(r['relative_J_error']) for r in rs])),parent_median_abs_relative_J_error=float(np.median([abs(r['parent_relative_J_error']) for r in rs]))))
    # Exact coupled replay uses held-group power and held-group thermal coefficients.
    eps=read(op['inputs']['thermal_prepared']['path']);profiles=read(op['inputs']['two_RC_profiles']['path']);thermal={p['group']:next(m for m in p['fits'] if m['id']==p['selected']) for p in profiles}
    oracle={r['id']:r for r in read(op['inputs']['two_RC_OOF']['path'])};eby={e['id']:e for e in entries};conditional=[];max_cascade_power_error=0.
    for ep in eps:
        e=eby[ep['id']];m=models[ep['group']];tm=thermal[ep['group']]
        assert ep['id'] not in m['train_ids'] and ep['group'] not in m['train_groups']
        pred=P.coupled(e['step'],ep['times'],ep['baseline'],ep['anchor_s'],ep['anchor_AP'],ep['skin'],m,tm)
        check=P.predict(P.features(e['step'],ep['times'],ep['baseline']),m);max_cascade_power_error=max(max_cascade_power_error,float(max(abs(check-pred[:,0]))))
        conditional.append(dict(id=ep['id'],group=ep['group'],pool=ep['pool'],times=ep['times'],observed=ep['observed'],predicted=pred[:,1].tolist(),parent=ep['parent_OOF'],oracle=oracle[ep['id']]['predicted']))
    assert max_cascade_power_error<1e-7;save(out/'CONDITIONAL_AP_ROWS.json.gz',conditional)
    apsummary=[]
    for category,lo in [('ALL',0),('OLD',0),('M8',0),('R21',0),('ALL',256)]:
        errs=[]
        for r in conditional:
            if category!='ALL' and r['pool']!=category and not(category=='R21' and r['group'].startswith('M8_R21_')):continue
            mask=np.asarray(r['times'])>=lo
            if any(mask):errs.append([float(np.mean(abs(np.asarray(r[k])[mask]-np.asarray(r['observed'])[mask]))) for k in ('predicted','parent','oracle')])
        apsummary.append(dict(category=category,from_s=lo,sessions=len(errs),conditional_MAE_C=float(np.mean([x[0] for x in errs])),parent_MAE_C=float(np.mean([x[1] for x in errs])),measured_power_oracle_MAE_C=float(np.mean([x[2] for x in errs]))))
    # Independent JS implementation of source unions, box, tails and prediction.
    payload=dict(cases=[dict(id=e['id'],model=e['group'],intervals=e['intervals'],times=e['times'].tolist(),baseline=e['baseline']) for e in entries],models=models)
    replay=subprocess.run(['node',str(HERE/'replay.cjs')],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',check=True)
    saved={r['id']:r for r in rows};max_error=0.;points=0;max_proxy=0.
    for r in json.loads(replay.stdout):
        diff=abs(np.asarray(r['predicted'])-np.asarray(saved[r['id']]['predicted']));max_error=max(max_error,float(max(diff)));points+=len(diff);max_proxy=max(max_proxy,r['max_proxy'])
    assert max_error<1e-7 and max_proxy<=1+1e-8
    pure=json.loads(subprocess.check_output(['node',str(HERE/'replay.cjs'),'test'],text=True));assert pure['status']=='PASS'
    verify(op)
    audit=dict(status='PASS_SAVED_AND_MATH_ONLY',points=points,max_JS_python_API_W_error=max_error,max_proxy=max_proxy,max_cascade_vs_power_API_W_error=max_cascade_power_error,pure=pure,physical_validation=False)
    save(out/'AUDIT.json',audit)
    full=models['FULL'];upper=float((np.asarray(full['coef'])/np.asarray(full['scale']))@np.r_[1.,.5764,np.ones(20)])
    result=dict(status='EXISTING_DATA_CAPACITY_POWER_COMPLETED',fit_START=started,fit_COMPLETE=started,fit_FAIL=0,power_sessions=len(entries),power_summary=summary,conditional_AP_summary=apsummary,
        maximal_proxy_power_at_context0_API_W=upper,upper_is_not_measured_physical_limit=True,new_policy_environments=0,new_RL=0,new_measurements=0,adopted=False,
        condition='Actual measured activity timing supplied; no independent workload-timing/triple/thermal-mitigation validation',elapsed_s=time.monotonic()-begin)
    save(out/'RESULT.json',result);save(out/'FINAL_PROOF.json',dict(status='CAPACITY_POWER_CALIBRATED_NOT_ADOPTED',operation_sha256=sha(HERE/'OPERATION.json'),
        artifacts={name:sha(out/name) for name in ['RESULT.json','MODEL.json','AUDIT.json','OOF_ROWS.json.gz','CONDITIONAL_AP_ROWS.json.gz','CASCADE_TEST.json']},new_fit=started,new_policy_environments=0,new_RL=0))
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
        out.mkdir(parents=True);(out/'models').mkdir();save(out/'START.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=os.getpid(),python=sys.version,numpy=np.__version__,operation_sha256=sha(HERE/'OPERATION.json')))
        main(op)
    except BaseException:
        if out.exists() and not(out/'FAILURE.json').exists():save(out/'FAILURE.json',dict(traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
