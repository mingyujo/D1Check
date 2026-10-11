"""Whole three-learner session archive for the original shared RNG semantics.

This module never starts an environment, teacher rollout or optimizer step.
Terminal64 sequential archives must be loaded11->23->37; the last37 RNG is
the completed round-robin session RNG. A new independent-stream experiment
would be a different design, not an extension of this run.
"""
import copy,os,time,json,hashlib
from pathlib import Path
from tools import d1_service_joint_rl as n
r=n.r
FIELDS=('multipliers','pending_episodes','logs','episode_logs','failed_updates','accepted_episodes','update_count','optimizer_steps','cursor','consumption','last_controller_state','extra_rng_states')
def digest(value):
    def canonical(v):
        if isinstance(v,(r.torch.Tensor,r.np.ndarray,r.np.generic)):return r.training._canonical(v)
        if isinstance(v,dict):return {str(k):canonical(z) for k,z in v.items()}
        if isinstance(v,(tuple,list)):return [canonical(z) for z in v]
        if isinstance(v,set):return sorted((canonical(z) for z in v),key=lambda z:json.dumps(z,sort_keys=True))
        if v is None or isinstance(v,(str,int,float,bool)):return v
        if hasattr(v,'__dict__'):return dict(object_class=type(v).__module__+'.'+type(v).__qualname__,attributes=canonical(vars(v)))
        raise TypeError('unsupported saved state '+str(type(v)))
    return hashlib.sha256(json.dumps(canonical(value),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def initial(paths,expected_dependencies=None):
    learners={}
    for seed in (11,23,37):
        p=r.torch.load(paths[seed],map_location='cpu',weights_only=False)
        if p['schema_id']!=n.SCHEMA or p['seed']!=seed or p['accepted_episodes']!=64 or p['version']!=r.training.VERSION or p['settings']!=r.training.Settings().__dict__:raise ValueError('requires exact V1 three terminal64 archives/settings')
        if expected_dependencies is not None and p['dependencies']!=expected_dependencies:raise ValueError('original caller dependency contract changed')
        learner=n.Learner(seed,n.SCHEMA,p['dependencies']);learner.network.load_state_dict(p['network']);learner.optimizer.load_state_dict(p['optimizer'])
        for field in FIELDS:setattr(learner,field,copy.deepcopy(p[field]))
        r.training.restore_rng(p['rng']);learners[seed]=learner
    return learners
def snapshot(learners,cursor,consumption):
    return dict(version='joint64_shared_session_v1',schema_id=n.SCHEMA,objective=n.objective.OBJECTIVE,
        learners={str(seed):learners[seed].snapshot() for seed in (11,23,37)},
        session_rng=r.training.rng_state(),cursor=copy.deepcopy(cursor),consumption=copy.deepcopy(consumption),
        scope='complete episode boundaries, same shared global RNG and case/next-seed order; no live engine restore')
def restore(payload):
    if payload['version']!='joint64_shared_session_v1' or payload['schema_id']!=n.SCHEMA or payload['objective']!=n.objective.OBJECTIVE:raise ValueError('session policy/objective schema mismatch, V2 reuse forbidden')
    learners={}
    for seed in (11,23,37):
        p=payload['learners'][str(seed)]
        if p['settings']!=r.training.Settings().__dict__ or p['schema_id']!=n.SCHEMA or p['version']!=r.training.VERSION:raise ValueError('learner ABI/settings changed')
        learner=n.Learner(seed,n.SCHEMA,p['dependencies']);learner.network.load_state_dict(p['network']);learner.optimizer.load_state_dict(p['optimizer'])
        for field in FIELDS:setattr(learner,field,copy.deepcopy(p[field]))
        learners[seed]=learner
    r.training.restore_rng(payload['session_rng']);return learners,copy.deepcopy(payload['cursor']),copy.deepcopy(payload['consumption'])
def save(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    with tmp.open('wb') as f:r.torch.save(payload,f);f.flush();os.fsync(f.fileno())
    for attempt in range(20):
        try:os.replace(tmp,path);return
        except PermissionError:
            if attempt==19:raise
            time.sleep(.05)
