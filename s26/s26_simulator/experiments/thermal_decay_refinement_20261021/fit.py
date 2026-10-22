"""Registered56 residual-model fits only. Original simulations/training never invoked."""
from pathlib import Path
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import sys,json,gzip,hashlib,datetime,time,math,collections,msvcrt,ctypes,shutil,subprocess,traceback
import numpy as np
from features import prepare_input,design,predict,interpolate,activity_filters
H=Path(__file__).resolve().parent;R=H.parents[2];E=H.parent;O=H/'artifacts/G001'
sys.stdout.reconfigure(encoding='utf-8')
def read(p):
    b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b.decode('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x):
    b=json.dumps(x,ensure_ascii=False,allow_nan=False).encode('utf-8')
    if str(p).endswith('.gz'):b=gzip.compress(b,mtime=0)
    with Path(p).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def append(p,x):
    with Path(p).open('a',encoding='utf-8') as f:f.write(json.dumps(x,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
def load_models():
    groups=read(E/'pipeline_thermal_v1/OPERATION.json')['groups'];pm={};tm={};pins=[]
    for group in groups+['FULL']:
        p=E/'capacity_power_v1/artifacts/G001/models'/(group+'.json');pm[group]=read(p);pins.append(p)
        paths=[E/'pipeline_thermal_v1/artifacts/G001/models'/(group+f'_i{i}.json') for i in [0,1]]
        fits=[read(p) for p in paths];tm[group]=min(fits,key=lambda m:(m['train_MSE'],m['start_w']));pins.extend(paths)
    return groups,pm,tm,pins

def prepare():
    raw=read(E/'thermal_balance_v1/artifacts/G001/PREPARED.json.gz');sessions=read(E/'multiresource_v1/calibration/MATERIALIZED_SESSIONS.json.gz');by={s.get('session_uid',s['id']):s for s in sessions}
    old=read(E/'pipeline_thermal_v1/artifacts/G001/OOF_ROWS.json.gz');oldby={r['id']:r for r in old};wins=read(E/'simulator_accuracy_rise_fall_20261021/artifacts/A001/WINDOWS.json.gz');wby=collections.defaultdict(list)
    for w in wins:wby[w['id']].append(w)
    entries=[]
    for ep in raw:
        if ep['id'] not in oldby:continue
        identity=ep['id'];s=by[identity];a=s['targets']['AP']['anchor'];t=np.asarray(ep['times']);obs=np.asarray(ep['observed'])
        assert np.array_equal(t,np.asarray(oldby[identity]['times'])) and np.array_equal(obs,np.asarray(oldby[identity]['observed']))
        context=dict(times=t,anchor=ep['anchor_s'],AP0=ep['anchor_AP'],skin=ep['skin'],BAT=a['BAT'],slope=a['pre20_AP_slope_c_s'],baseline=ep['baseline'],intervals=s['activity9']['intervals'])
        public=prepare_input(**context)
        entries.append(dict(id=identity,group=ep['group'],pool=ep['pool'],cohort=ep['cohort'],times=t,observed=obs,public=public,windows=wby[identity],old=oldby[identity]['predicted'],context=context,measured_power_times=ep['power_times'],measured_power_values=ep['power_values']))
    assert len(entries)==208
    return entries

def resource_guard(protocol):
    res=protocol['resource'];mem=ctypes.c_ulonglong
    class Memory(ctypes.Structure):_fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,mem) for k in ['physical','available','page','freepage','virtual','freevirtual','extended']]
    m=Memory();m.length=ctypes.sizeof(m);assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    assert m.available>=res['minimum_free_memory_bytes'] and shutil.disk_usage(R).free>=res['disk_min_free_bytes']
    cmd="[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' OR Name = 'python3.exe'\" | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"
    q=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',cmd],text=True,encoding='utf-8') or '[]');q=[q] if isinstance(q,dict) else q
    assert len({p['ProcessId'] for p in q}-{p['ParentProcessId'] for p in q})<=res['global_Python_limit'],'Python leaf cap'
    assert not any(p['ProcessId']!=os.getpid() and any(t in(p.get('CommandLine')or'') for t in ['a24_simulator','s26_simulator/experiments','s26_simulator\\experiments']) for p in q),'Other research heavy worker'
    return dict(free_memory=m.available,free_disk=shutil.disk_usage(R).free,python_leaves=len({p['ProcessId'] for p in q}-{p['ParentProcessId'] for p in q}))

def preflight():
    p=read(H/'PROTOCOL.json');groups,pm,tm,modelpaths=load_models();start=time.monotonic();entries=prepare();maxerr=0.
    for e in entries:
        g=e['group'];base,X=design(e['public'],pm[g],tm[g]);maxerr=max(maxerr,float(max(abs(base-e['old']))))
        assert e['id'] not in pm[g]['train_ids'] and g not in pm[g]['train_groups']
    assert maxerr<1e-7,maxerr
    # Causality: future phase changes cannot affect earlier features; anchor correction starts at zero.
    ctx=dict(times=np.array([0.,2.,10.,20.]),anchor=0.,AP0=31.,skin=30.,BAT=29.,slope=.01,baseline=.6,intervals=[[] for _ in range(9)])
    a=prepare_input(**ctx);c=ctx.copy();c['intervals']=[[list(v) for v in xs] for xs in ctx['intervals']];c['intervals'][0]=[[30.,40.,1.]];b=prepare_input(**c)
    for key in ['B','activity','drift']:assert np.array_equal(a[key],b[key])
    base,X=design(a,pm['FULL'],tm['FULL']);assert max(abs(X[0]))<1e-12 and abs(base[0]-31)<1e-12
    sources=[H/'PROTOCOL.json',H/'features.py',Path(__file__),E/'thermal_balance_v1/artifacts/G001/PREPARED.json.gz',E/'multiresource_v1/calibration/MATERIALIZED_SESSIONS.json.gz',E/'pipeline_thermal_v1/artifacts/G001/OOF_ROWS.json.gz',E/'pipeline_thermal_v1/OPERATION.json',E/'pipeline_thermal_v1/basis.py',E/'capacity_power_v1/power.py',E/'simulator_accuracy_rise_fall_20261021/artifacts/A001/WINDOWS.json.gz',R/'s26_simulator/FINAL_POLICY.json',E/'route_group_learning_v1/artifacts/G001/BC_COMMON_FINAL.pt.gz',E/'route_group_learning_v1/artifacts/G001/S881087_FINAL.pt.gz',*modelpaths]
    pins=[dict(path=x.relative_to(R).as_posix(),sha256=sha(x)) for x in sources]
    save(H/'PREFLIGHT.json',dict(status='PASS_NO_NEW_FITS',UTC=utc(),sessions=len(entries),points=sum(len(e['times']) for e in entries),max_frozen_baseline_reconstruction_C=maxerr,anchor_zero_correction=True,future_activity_invariance=True,post_anchor_observed_AP_or_power_features=False,source=pins,elapsed_s=time.monotonic()-start))
    print(json.dumps(dict(status='PREFLIGHT_PASS',sessions=len(entries),max_baseline_error_C=maxerr,elapsed_s=time.monotonic()-start),ensure_ascii=False),flush=True)

def sufficient(train,pm,tm):
    D=39;Hl=np.zeros((D,D));bl=np.zeros(D);cl=0.;Hlate=np.zeros_like(Hl);blate=np.zeros(D);Hd=np.zeros_like(Hl);bd=np.zeros(D)
    nlate=sum(np.any(e['times']>=256) for e in train);class_sessions={c:sum(any(w['direction']==c for w in e['windows']) for e in train) for c in ['RISE','FALL','STEADY']}
    for e in train:
        base,X=design(e['public'],pm,tm);y=e['observed']-base;w=1/(len(train)*len(y));Hl+=w*X.T@X;bl+=w*X.T@y;cl+=w*float(y@y)
        m=e['times']>=256
        if any(m):w=1/(nlate*sum(m));Hlate+=w*X[m].T@X[m];blate+=w*X[m].T@y[m]
        for c in class_sessions:
            ws=[z for z in e['windows'] if z['direction']==c]
            if not ws:continue
            end=np.array([z['end'] for z in ws]);start=np.array([z['start'] for z in ws]);dx=interpolate(e['times'],X,end)-interpolate(e['times'],X,start);dy=np.array([z['observed_delta_C'] for z in ws])-(interpolate(e['times'],base,end)-interpolate(e['times'],base,start));w=1/(len(class_sessions)*class_sessions[c]*len(ws));Hd+=w*dx.T@dx;bd+=w*dx.T@dy
    scale=np.maximum(np.sqrt(np.diag(Hl)),1e-6)
    return Hl,bl,cl,Hlate,blate,Hd,bd,scale

def fit_model(stats,kind,group,train):
    Hl,bl,cl,Hlate,blate,Hd,bd,scale=stats;HH=Hl if kind=='LEVEL_RESIDUAL' else Hl+Hlate+Hd;bb=bl if kind=='LEVEL_RESIDUAL' else bl+blate+bd
    A=HH/(scale[:,None]*scale[None,:])+np.eye(39)/39;b=bb/scale;coef=np.linalg.solve(A,b);grad=A@coef-b;kkt=float(max(abs(grad)));assert kkt<1e-7 and np.isfinite(coef).all()
    return dict(id=f'{group}__{kind}',kind=kind,heldout_group=group,coef=coef.tolist(),scale=scale.tolist(),ridge=1/39,KKT_residual=kkt,condition_number=float(np.linalg.cond(A)),train_ids=[e['id'] for e in train],train_groups=sorted({e['group'] for e in train}),physical_constants_identified=False,adopted=False)

def fit():
    p=read(H/'PROTOCOL.json');pre=read(H/'PREFLIGHT.json');assert pre['status']=='PASS_NO_NEW_FITS' and not O.exists()
    for x in pre['source']:assert sha(R/x['path'])==x['sha256'],x['path']
    resource=resource_guard(p);lockpath=Path(p['resource']['shared_mutex']);assert lockpath.exists();lock=lockpath.open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    began=time.monotonic();started=complete=failed=0;rows=[];folds=[]
    try:
        O.mkdir(parents=True);(O/'models').mkdir();save(O/'START.json',dict(UTC=utc(),PID=os.getpid(),protocol_sha256=sha(H/'PROTOCOL.json'),source_sha256=sha(__file__),resource=resource))
        groups,pm,tm,_=load_models();entries=prepare()
        for group in groups+['FULL']:
            assert time.monotonic()-began<p['fits']['wall_cap_s'];train=[e for e in entries if group=='FULL' or e['group']!=group];test=[e for e in entries if e['group']==group]
            if group!='FULL':assert all(e['group'] not in pm[group]['train_groups'] and e['id'] not in pm[group]['train_ids'] for e in test)
            stats=sufficient(train,pm[group],tm[group]);folds.append(dict(group=group,train_ids=[e['id'] for e in train],test_ids=[e['id'] for e in test],power_train_groups=pm[group]['train_groups'],thermal_base_id=tm[group]['id']))
            for candidate in p['candidates']:
                kind=candidate['id'];identity=f'{group}__{kind}';assert started<p['fits']['cap'];started+=1;append(O/'FIT_RECEIPTS.jsonl',dict(event='START',id=identity,UTC=utc(),sequence=started))
                try:
                    model=fit_model(stats,kind,group,train);model['base_power_model']=pm[group];model['base_thermal_model']=tm[group];model['feature_names']=p['features'];model['prediction_input']='Initial context and observed/planned activity only; no post-anchor measured AP/power.'
                    path=O/'models'/(identity+'.json');save(path,model);complete+=1;append(O/'FIT_RECEIPTS.jsonl',dict(event='COMPLETE',id=identity,UTC=utc(),model_sha256=sha(path)))
                    for e in test:
                        assert e['id'] not in model['train_ids'] and e['group'] not in model['train_groups']
                        pred=predict(e['public'],pm[group],tm[group],model)
                        rows.append(dict(id=e['id'],group=e['group'],pool=e['pool'],candidate=kind,model=identity,times=e['times'].tolist(),observed=e['observed'].tolist(),predicted=pred.tolist(),baseline=e['old']))
                except Exception as error:
                    failed+=1;save(O/'models'/(identity+'.failure.json'),dict(id=identity,error=str(error),traceback=traceback.format_exc(),automatic_retry=False));append(O/'FIT_RECEIPTS.jsonl',dict(event='FAIL',id=identity,UTC=utc(),reason=str(error),automatic_retry=False))
            print(json.dumps(dict(status='FOLD_COMPLETE',group=group,START=started,COMPLETE=complete,FAIL=failed),ensure_ascii=False),flush=True)
        assert started==56
        save(O/'OOF_ROWS.json.gz',rows);save(O/'TRAIN_FOLDS.json',folds)
        for x in pre['source']:assert sha(R/x['path'])==x['sha256'],'Original source changed '+x['path']
        save(O/'FIT_RESULT.json',dict(status='COMPLETE_NEW_RESIDUAL_FITS',UTC=utc(),fit_START=started,fit_COMPLETE=complete,fit_FAIL=failed,OOF_rows=len(rows),elapsed_s=time.monotonic()-began,source_files_unchanged=True,original_policy_models_unchanged=True,new_policy_environments=0,new_NN_training=0,new_power_fits=0,new_measurements=0,adopted=False))
    except BaseException as e:
        if O.exists():save(O/'OPERATION_FAILURE.json',dict(UTC=utc(),error=str(e),traceback=traceback.format_exc(),START=started,COMPLETE=complete,FAIL=failed,automatic_retry=False))
        raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':
    if sys.argv[1:]==['--preflight']:preflight()
    elif sys.argv[1:]==['--fit']:fit()
    else:raise ValueError('Explicit --preflight or --fit required; no automatic run')
