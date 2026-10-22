"""Causal features, frozen model loading, exported tree replay. No fitting on import."""
from pathlib import Path
import sys,json,gzip,hashlib,importlib.util
import numpy as np
H=Path(__file__).resolve().parent;R=H.parents[2];E=H.parent;N=E/'thermal_decay_nonlinear_20261021'
sys.path.insert(0,str(N))
from features import design
from power import steps
def read(p):
    b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b.decode('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    b=json.dumps(x,ensure_ascii=False,allow_nan=False).encode('utf-8');b=gzip.compress(b,mtime=0) if str(p).endswith('.gz') else b
    with Path(p).open('xb') as f:f.write(b)
def tree_prediction(X,m):
    out=np.full(len(X),m.get('baseline_prediction',0.))
    for tree in m['trees']:
        ix=np.zeros(len(X),dtype=int);active=np.ones(len(X),dtype=bool)
        while active.any():
            rr=np.where(active)[0]
            for i in rr:
                node=tree[ix[i]]
                if node['leaf']:out[i]+=node['value'];active[i]=False
                else:ix[i]=node['left'] if X[i,node['feature']]<=node['threshold'] else node['right']
    return out
def signed_state_age(times,anchor,intervals):
    events=steps(intervals);last=np.full(5,anchor);v=np.zeros(5);out=[];j=0
    for t in times:
        while j<len(events) and events[j][0]<=t:
            when,nv=events[j];nv=np.asarray(nv);changed=nv!=v;last[changed]=max(when,anchor);v=nv;j+=1
        out.append((np.asarray(t)-last)*np.where(v>0,1.,-1.)/320.)
    return np.array(out)
def load_entries():
    meta=read(N/'input_cache/metadata.json');cache=np.load(N/'input_cache/arrays.npz');contexts={e['id']:e for e in read(N/'artifacts/G001/INDEPENDENT_REPLAY_INPUT.json.gz')['cases']};ws=read(E/'simulator_accuracy_rise_fall_20261021/artifacts/A001/WINDOWS.json.gz');wby={e['id']:[] for e in meta}
    for w in ws:wby[w['id']].append(w)
    out=[]
    for j,e in enumerate(meta):
        t=np.asarray(e['times']);pub={**e['public'],'times':t,**{k:cache[f'{j}_{k}'] for k in ['B','activity','drift']}};ctx=contexts[e['id']]
        extra=np.column_stack(((t-pub['anchor'])/320,signed_state_age(t,pub['anchor'],ctx['intervals'])))
        out.append({**e,'times':t,'observed':np.array(e['observed']),'public':pub,'extra':extra,'windows':wby[e['id']],'context':ctx})
    return out
def frozen(group):
    m=read(N/'artifacts/G001/models'/(group+'__HISTGB_RESIDUAL.json.gz'));return m
def make_X(e,m,fast_model=None):
    base,X=design(e['public'],m['base_power_model'],m['base_thermal_model']);xx=np.column_stack((X,base));raw=fast_model.predict(xx) if fast_model is not None else tree_prediction(xx,m)
    previous=base+X[:,24]*raw;out=np.column_stack((X,base,previous,e['extra']));assert out.shape[1]==47 and np.isfinite(out).all();return out,previous,X[:,24]
def helper():
    spec=importlib.util.spec_from_file_location('old_resource_only',E/'thermal_decay_refinement_20261021/fit.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
