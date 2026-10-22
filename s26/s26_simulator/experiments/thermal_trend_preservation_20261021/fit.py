"""84 newly registered coupled-loss thermal fits. Old models are loaded, never fitted."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from engine import *
import time,datetime,pickle,traceback,msvcrt
from scipy import sparse
from sklearn.tree import DecisionTreeRegressor
O=H/'artifacts/G001'
sys.stdout.reconfigure(encoding='utf-8')
def record(x):
    with (O/'FIT_RECEIPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(x)+'\n');f.flush();os.fsync(f.fileno())
def interpolate_coeff(t,q,offset):
    j=int(np.searchsorted(t,q));
    if j<len(t) and abs(t[j]-q)<1e-10:return [(offset+j,1.)]
    assert 0<j<len(t);a=(q-t[j-1])/(t[j]-t[j-1]);return [(offset+j-1,1-a),(offset+j,a)]
def training_data(train,m,fast):
    X=[];prev=[];g=[];y=[];wl=[];ii=[];jj=[];vv=[];deltas=[];wall=[];wlate=[];offset=0;row=0
    classes=['RISE','FALL','STEADY'];ns={c:sum(any(w['direction']==c for w in e['windows']) for e in train) for c in classes};nl={c:sum(any(w['direction']==c and w['start']>=256 for w in e['windows']) for e in train) for c in classes}
    for e in train:
        x,b,gate=make_X(e,m,fast);X.append(x);prev.extend(b);g.extend(gate);y.extend(e['observed']);wl.extend([1/(len(train)*len(b))]*len(b));counts={c:sum(w['direction']==c for w in e['windows']) for c in classes};latecounts={c:sum(w['direction']==c and w['start']>=256 for w in e['windows']) for c in classes}
        for w in e['windows']:
            for q,sign in [(w['start'],-1),(w['end'],1)]:
                for col,value in interpolate_coeff(e['times'],q,offset):ii.append(row);jj.append(col);vv.append(sign*value)
            c=w['direction'];deltas.append(w['observed_delta_C']);wall.append(1/(3*ns[c]*counts[c]));wlate.append(1/(3*nl[c]*latecounts[c]) if w['start']>=256 else 0.);row+=1
        offset+=len(b)
    D=sparse.csr_matrix((vv,(ii,jj)),shape=(row,offset));D.sum_duplicates();return np.vstack(X),np.array(prev),np.array(g),np.array(y),np.array(wl),D,np.array(deltas),np.array(wall),np.array(wlate)
def fit_one(data,cfg,p):
    X,previous,g,y,wl,D,dy,wa,wla=data;wd=cfg['lambda_all']*wa+cfg['lambda_late']*wla;pred=previous.copy();trees=[];trace=[];params=p['tree'];hdiag=g*g*(3*wl+D.power(2).T@wd);assert np.all(hdiag>0)
    def loss(pp):return float(wl@((pp-y)**2+2*(pp-previous)**2)+wd@((D@pp-dy)**2))
    oldloss=loss(pred);initial=oldloss
    for stage in range(params['stages']):
        grad=wl*((pred-y)+2*(pred-previous))+D.T@(wd*(D@pred-dy));pseudo=-g*grad/hdiag
        dt=DecisionTreeRegressor(max_leaf_nodes=params['max_leaf_nodes'],max_depth=params['max_depth'],min_samples_leaf=params['min_samples_leaf'],max_features=params['max_features'],random_state=20261021+stage)
        dt.fit(X,pseudo,sample_weight=hdiag);leaf=dt.apply(X);nodes,index=np.unique(leaf,return_inverse=True);Z=np.zeros((len(X),len(nodes)));Z[np.arange(len(X)),index]=g;DZ=D@Z
        A=np.diag(np.bincount(index,weights=3*wl*g*g,minlength=len(nodes)))+DZ.T@(wd[:,None]*DZ)+params['leaf_ridge']*np.eye(len(nodes));rhs=-Z.T@grad;coef=np.linalg.solve(A,rhs);update=params['learning_rate']*(Z@coef);pred+=update
        current=loss(pred);assert current<=oldloss+1e-10,(current,oldloss);oldloss=current
        tree=dt.tree_;mapping=dict(zip(nodes,params['learning_rate']*coef));export=[]
        for n in range(tree.node_count):
            isleaf=tree.children_left[n]<0;export.append(dict(value=float(mapping.get(n,0.)),feature=int(tree.feature[n]),threshold=float(tree.threshold[n]),left=int(tree.children_left[n]),right=int(tree.children_right[n]),leaf=bool(isleaf)))
        trees.append(export)
        if stage in [0,19,39,59,79]:trace.append(dict(stage=stage+1,train_objective=current))
    # Exported leaf traversal must exactly reproduce learned train corrections.
    model=dict(trees=trees,baseline_prediction=0.);ix=np.linspace(0,len(X)-1,60,dtype=int);check=previous[ix]+g[ix]*tree_prediction(X[ix],model);assert max(abs(check-pred[ix]))<1e-9
    return model,dict(initial_train_objective=initial,final_train_objective=oldloss,trace=trace)
def preflight():
    assert not (H/'PREFLIGHT.json').exists();entries=load_entries();by={r['id']:r for r in read(N/'artifacts/G001/OOF_ROWS.json.gz')};err=0.
    for e in entries:
        _,b,_=make_X(e,frozen(e['group']));err=max(err,float(max(abs(b-by[e['id']]['predicted']))))
    assert err<1e-8
    # Future state changes cannot affect earlier phase-age features.
    t=np.array([0.,2.,10.,20.]);iv=[[] for _ in range(9)];a=signed_state_age(t,0.,iv);iv[0]=[[30.,40.,1.]];assert np.array_equal(a,signed_state_age(t,0.,iv))
    paths=[H/'PROTOCOL.json',H/'engine.py',Path(__file__),N/'input_cache/arrays.npz',N/'input_cache/metadata.json',N/'features.py',N/'artifacts/G001/OOF_ROWS.json.gz',N/'REPORT_KO.md',E/'simulator_accuracy_rise_fall_20261021/artifacts/A001/WINDOWS.json.gz',*sorted((N/'artifacts/G001/models').glob('*'))]
    oldpins=read(N/'PREFLIGHT.json')['source']+read(E/'thermal_decay_refinement_20261021/PREFLIGHT.json')['source']
    for z in oldpins:assert sha(R/z['path'])==z['sha256']
    save(H/'PREFLIGHT.json',dict(status='PASS_FROZEN_CHAIN_AND_CAUSAL_INPUTS',sessions=208,points=25975,max_frozen_HGB_reproduction_C=err,future_activity_invariance=True,source=[dict(path=x.relative_to(R).as_posix(),sha256=sha(x)) for x in paths]+oldpins,new_fit_START=0));print(json.dumps(dict(status='PREFLIGHT_PASS',max_error_C=err)),flush=True)
def fit():
    protocol=read(H/'PROTOCOL.json');pre=read(H/'PREFLIGHT.json');assert not O.exists()
    for z in pre['source']:assert sha(R/z['path'])==z['sha256']
    resource=helper().resource_guard(protocol);lock=Path(protocol['resource']['shared_mutex']).open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);begin=time.monotonic();started=complete=failed=0;rows=[]
    try:
        O.mkdir(parents=True);(O/'models').mkdir();save(O/'START.json',dict(UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol_sha256=sha(H/'PROTOCOL.json'),code_sha256=sha(__file__),resource=resource))
        entries=load_entries();groups=read(E/'pipeline_thermal_v1/OPERATION.json')['groups']
        for group in groups+['FULL']:
            assert time.monotonic()-begin<protocol['fits']['wall_cap_s'];train=[e for e in entries if group=='FULL' or e['group']!=group];test=[e for e in entries if e['group']==group];m=frozen(group)
            with gzip.open(N/'artifacts/G001/models'/(group+'__HISTGB_RESIDUAL.pkl.gz'),'rb') as f:fast=pickle.load(f)
            for e in test:assert e['id'] not in m['train_ids'] and group not in m['train_groups'] and group not in m['base_power_model']['train_groups']
            data=training_data(train,m,fast)
            for cfg in protocol['candidates']:
                identity=group+'__'+cfg['id'];assert started<84;started+=1;record(dict(event='START',id=identity,sequence=started))
                try:
                    model,diag=fit_one(data,cfg,protocol);model.update(id=identity,candidate=cfg['id'],heldout_group=group,gate_feature_index=24,dimension=47,frozen_HGB=m,train_ids=[e['id'] for e in train],train_groups=sorted({e['group'] for e in train}),config=cfg,diagnostics=diag,adopted=False);path=O/'models'/(identity+'.json.gz');save(path,model)
                    for e in test:
                        X,b,g=make_X(e,m,fast);pred=b+g*tree_prediction(X,model);rows.append(dict(id=e['id'],group=e['group'],pool=e['pool'],candidate=cfg['id'],model=identity,times=e['times'].tolist(),observed=e['observed'].tolist(),predicted=pred.tolist(),baseline=b.tolist()))
                    complete+=1;record(dict(event='COMPLETE',id=identity,model_sha256=sha(path),stages=80))
                except Exception as exc:
                    failed+=1;save(O/'models'/(identity+'.failure.json'),dict(error=str(exc),traceback=traceback.format_exc(),automatic_retry=False));record(dict(event='FAIL',id=identity,error=str(exc)))
            print(json.dumps(dict(status='FOLD_COMPLETE',group=group,START=started,COMPLETE=complete,FAIL=failed,elapsed_s=round(time.monotonic()-begin,2))),flush=True)
        save(O/'OOF_ROWS.json.gz',rows)
        for z in pre['source']:assert sha(R/z['path'])==z['sha256']
        save(O/'FIT_RESULT.json',dict(status='COMPLETE_NEW_TREND_FITS',fit_START=started,fit_COMPLETE=complete,fit_FAIL=failed,OOF_rows=len(rows),elapsed_s=time.monotonic()-begin,old_models_policy_unchanged=True,new_policy_environments=0,new_BC_RL_training=0,new_power_fits=0,new_measurements=0,adopted=False))
    except BaseException as exc:
        if O.exists():save(O/'OPERATION_FAILURE.json',dict(error=str(exc),traceback=traceback.format_exc(),fit_START=started,fit_COMPLETE=complete,fit_FAIL=failed,automatic_retry=False))
        raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':
    if sys.argv[1:]==['--preflight']:preflight()
    elif sys.argv[1:]==['--fit']:fit()
    else:raise ValueError('Explicit mode required')
