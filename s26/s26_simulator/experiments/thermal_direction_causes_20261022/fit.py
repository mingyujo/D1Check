"""56 new pre-registered thermal margin fits; never rerun existing fits or policy environments."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from engine import *
import time,datetime,traceback,msvcrt,copy
from scipy import sparse
from sklearn.tree import DecisionTreeRegressor
O=H/'artifacts/G001';sys.stdout.reconfigure(encoding='utf-8')
def record(v):
    with (O/'FIT_RECEIPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(v)+'\n');f.flush();os.fsync(f.fileno())
def data(train,chain):
    X=[];previous=[];g=[];y=[];wl=[];ii=[];jj=[];vv=[];dy=[];labels=[];wa=[];wla=[];off=0;row=0;classes=['RISE','FALL','STEADY'];n={c:sum(any(w['direction']==c for w in e['windows']) for e in train) for c in classes};nl={c:sum(any(w['direction']==c and w['start']>=256 for w in e['windows']) for e in train) for c in classes}
    for e in train:
        xx,b,gate=design(e,chain);X.append(xx);previous.extend(b);g.extend(gate);y.extend(e['observed']);wl.extend([1/(len(train)*len(b))]*len(b));counts={c:sum(w['direction']==c for w in e['windows']) for c in classes};late={c:sum(w['direction']==c and w['start']>=256 for w in e['windows']) for c in classes}
        for w in e['windows']:
            for t,sign in [(w['start'],-1),(w['end'],1)]:
                for col,v in interpolate_coeff(e['times'],t,off):ii.append(row);jj.append(col);vv.append(sign*v)
            c=w['direction'];dy.append(w['observed_delta_C']);labels.append(1 if c=='RISE' else -1 if c=='FALL' else 0);wa.append(1/(3*n[c]*counts[c]));wla.append(1/(3*nl[c]*late[c]) if w['start']>=256 else 0.);row+=1
        off+=len(b)
    D=sparse.csr_matrix((vv,(ii,jj)),shape=(row,off));D.sum_duplicates();return np.vstack(X),np.array(previous),np.array(g),np.array(y),np.array(wl),D,np.array(dy),np.array(labels),np.array(wa),np.array(wla)
def hinge(delta,labels):
    target=np.where(labels==1,.22,np.where(labels==-1,-.22,np.where(delta>.16,.16,np.where(delta<-.16,-.16,delta))));active=np.where(labels==1,delta<.22,np.where(labels==-1,delta>-.22,abs(delta)>.16));return (delta-target)*active,active
def fit_one(d,cfg,p):
    X,previous,g,y,wl,D,dy,labels,wa,wla=d;wd=.25*wa+.5*wla;wh=(cfg['hinge_all']*wa+cfg['hinge_late']*wla)*np.where(labels==0,cfg['steady_multiplier'],1.);pred=previous.copy();trees=[];trace=[];steps=[];param=p['tree'];D2=D.power(2)
    def loss(pp):
        delta=D@pp;err,_=hinge(delta,labels);return float(wl@((pp-y)**2+4*(pp-previous)**2)+wd@((delta-dy)**2)+wh@(err*err))
    oldloss=loss(pred);initial=oldloss
    for stage in range(param['stages']):
        delta=D@pred;err,active=hinge(delta,labels);weights=wd+wh*active;grad=wl*((pred-y)+4*(pred-previous))+D.T@(wd*(delta-dy)+wh*err);hdiag=g*g*(5*wl+D2.T@weights);pseudo=-g*grad/hdiag
        tree=DecisionTreeRegressor(max_leaf_nodes=15,max_depth=5,min_samples_leaf=50,max_features=16,random_state=20261022+stage);tree.fit(X,pseudo,sample_weight=hdiag);leaf=tree.apply(X);nodes,index=np.unique(leaf,return_inverse=True);Z=np.zeros((len(X),len(nodes)));Z[np.arange(len(X)),index]=g;DZ=D@Z
        AA=np.diag(np.bincount(index,weights=5*wl*g*g,minlength=len(nodes)))+DZ.T@(weights[:,None]*DZ)+1e-4*np.eye(len(nodes));coef=np.linalg.solve(AA,-Z.T@grad);base_update=Z@coef;alpha=.1;accepted=False
        for line in range(10):
            candidate=pred+alpha*base_update;v=loss(candidate)
            if v<=oldloss+1e-11:accepted=True;break
            alpha*=.5
        if accepted:pred=candidate;oldloss=v
        else:alpha=0.
        steps.append(alpha);mapping=dict(zip(nodes,alpha*coef));tr=tree.tree_;export=[]
        for j in range(tr.node_count):export.append(dict(value=float(mapping.get(j,0.)),feature=int(tr.feature[j]),threshold=float(tr.threshold[j]),left=int(tr.children_left[j]),right=int(tr.children_right[j]),leaf=bool(tr.children_left[j]<0)))
        trees.append(export)
        if stage in [0,19,39,59,79]:trace.append(dict(stage=stage+1,objective=oldloss,alpha=alpha,active_hinges=int(sum(active))))
    model=dict(trees=trees,baseline_prediction=0.);ix=np.linspace(0,len(X)-1,60,dtype=int);assert max(abs(previous[ix]+g[ix]*tree_predict(X[ix],model)-pred[ix]))<1e-9
    return model,dict(initial_objective=initial,final_objective=oldloss,trace=trace,backtracked_stages=sum(0<a<.1 for a in steps),stalled_stages=sum(a==0 for a in steps))
def preflight():
    assert not (H/'PREFLIGHT.json').exists();entries=load_entries();by={r['id']:r for r in read(T/'artifacts/G001/OOF_ROWS.json.gz') if r['candidate']=='TREND_BALANCED'};error=0.;hist=[]
    for e in entries:
        _,b,_=design(e,frozen(e['group']));error=max(error,float(max(abs(b-by[e['id']]['predicted']))));ha=e['history_audit'];assert ha['maximum_available_s'] is None or ha['maximum_available_s']<=ha['anchor'];hist.append(dict(id=e['id'],features=e['history'].tolist(),**ha))
    assert error<1e-8,error
    raw=read(E/'multiresource_v1/calibration/MATERIALIZED_SESSIONS.json.gz');s=next(s for s in raw if s.get('session_uid',s['id'])==entries[0]['id']);altered=copy.deepcopy(s)
    for ob in altered['targets']['AP']['observations']:
        if ob['available_upper_s']>entries[0]['public']['anchor']:ob['AP']+=100;ob['SKIN']+=100;ob['BAT']+=100
    assert np.array_equal(initial_history(entries[0],s)[0],initial_history(entries[0],altered)[0])
    save(H/'INITIAL_HISTORY.json',hist)
    pins=read(T/'PREFLIGHT.json')['source'];paths=[H/'PROTOCOL.json',H/'DIAGNOSIS.json',H/'engine.py',Path(__file__),H/'INITIAL_HISTORY.json',T/'engine.py',T/'REPORT_KO.md',T/'artifacts/G001/OOF_ROWS.json.gz',E/'multiresource_v1/calibration/MATERIALIZED_SESSIONS.json.gz',*sorted((T/'artifacts/G001/models').glob('*.json.gz'))]
    for pin in pins:assert sha(R/pin['path'])==pin['sha256']
    save(H/'PREFLIGHT.json',dict(status='PASS_FROZEN_BALANCED_CHAIN_AND_AVAILABLE_HISTORY',max_frozen_reproduction_C=error,history_cutoff='available_upper_s<=anchor for every observation',future_measured_data_invariance=True,source=pins+[dict(path=p.relative_to(R).as_posix(),sha256=sha(p)) for p in paths],new_fit_START=0));print(json.dumps(dict(status='PREFLIGHT_PASS',max_error_C=error)),flush=True)
def fit():
    p=read(H/'PROTOCOL.json');pre=read(H/'PREFLIGHT.json');assert not O.exists()
    for pin in pre['source']:assert sha(R/pin['path'])==pin['sha256']
    res=P.helper().resource_guard(p);lock=Path(p['resource']['shared_mutex']).open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);begin=time.monotonic();started=complete=failed=0;rows=[]
    try:
        O.mkdir(parents=True);(O/'models').mkdir();save(O/'START.json',dict(UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol_sha256=sha(H/'PROTOCOL.json'),code_sha256=sha(__file__),resource=res));entries=load_entries();groups=read(E/'pipeline_thermal_v1/OPERATION.json')['groups']
        for group in groups+['FULL']:
            assert time.monotonic()-begin<1500;chain=frozen(group);train=[e for e in entries if group=='FULL' or e['group']!=group];test=[e for e in entries if e['group']==group]
            for e in test:assert group not in chain['train_groups'] and group not in chain['frozen_HGB']['train_groups'] and group not in chain['frozen_HGB']['base_power_model']['train_groups']
            d=data(train,chain)
            for cfg in p['candidates']:
                identity=group+'__'+cfg['id'];assert started<56;started+=1;record(dict(event='START',id=identity,sequence=started))
                try:
                    model,diag=fit_one(d,cfg,p);model.update(id=identity,candidate=cfg['id'],heldout_group=group,frozen_trend=chain,dimension=60,gate_feature_index=24,config=cfg,train_ids=[e['id'] for e in train],train_groups=sorted({e['group'] for e in train}),diagnostics=diag,adopted=False);path=O/'models'/(identity+'.json.gz');save(path,model)
                    for e in test:
                        X,b,g=design(e,chain);pred=b+g*tree_predict(X,model);rows.append(dict(id=e['id'],group=e['group'],pool=e['pool'],candidate=cfg['id'],model=identity,times=e['times'].tolist(),observed=e['observed'].tolist(),predicted=pred.tolist(),baseline=b.tolist()))
                    complete+=1;record(dict(event='COMPLETE',id=identity,model_sha256=sha(path),stages=80))
                except Exception as exc:failed+=1;save(O/'models'/(identity+'.failure.json'),dict(error=str(exc),traceback=traceback.format_exc(),automatic_retry=False));record(dict(event='FAIL',id=identity,error=str(exc)))
            print(json.dumps(dict(group=group,START=started,COMPLETE=complete,FAIL=failed,elapsed_s=round(time.monotonic()-begin,1))),flush=True)
        save(O/'OOF_ROWS.json.gz',rows)
        for pin in pre['source']:assert sha(R/pin['path'])==pin['sha256']
        save(O/'FIT_RESULT.json',dict(status='COMPLETE_NEW_MARGIN_FITS',fit_START=started,fit_COMPLETE=complete,fit_FAIL=failed,OOF_rows=len(rows),elapsed_s=time.monotonic()-begin,new_policy_environments=0,new_BC_RL_training=0,new_power_fits=0,new_measurements=0,original_models_and_previous_candidates_unchanged=True,adopted=False))
    except BaseException as exc:
        if O.exists():save(O/'OPERATION_FAILURE.json',dict(error=str(exc),traceback=traceback.format_exc(),START=started,COMPLETE=complete,FAIL=failed,automatic_retry=False))
        raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':
    if sys.argv[1:]==['--preflight']:preflight()
    elif sys.argv[1:]==['--fit']:fit()
    else:raise ValueError('Explicit mode required')
