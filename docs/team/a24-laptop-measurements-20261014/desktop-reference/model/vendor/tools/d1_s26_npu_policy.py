"""Causal full-waiting ranking, bounded union candidates, three-lane physical mask."""
import math
import time
import numpy as np
import torch
from tools import d1_s26_npu_engine as e

RULES=('FIFO','EFT','EDD','ATC','FIFO_HOL')
REQUEST_SLOTS=8
REQUEST_DIM=20
RESOURCE_DIM=8
GLOBAL_DIM=8
STATE_DIM=REQUEST_SLOTS*REQUEST_DIM+3*RESOURCE_DIM+GLOBAL_DIM
ACTION_DIM=32
SLOTS=64 # 3C+D+2CD+1 <=49 for C+D<=8; pad64, padding always mask0.
SCHEMA=e.digest(dict(version='s26-npu-atc-direct-v1',request=[8,20],resource=[3,8],global_dim=8,actions=[64,32],objective='SERVICE_ONLY_V1',w=[2,1],k=2,candidates='ATC top4 + oldest C/D + EDD fallback + fastest feasible; <=8',wait='physical allowed; operational only when no execution',costs=False))
def tie(q):return(q['arrival_ns'],q['ordinal'],q['id'])
def response(ds,q):return sum(ds[:2 if q['priority']=='urgent' else 3])
def representative(dev,q):
    return min((response(dev.estimate(q,b),q),sum(dev.estimate(q,b)),e.BACKENDS.index(b)) for b in e.routes(q,dev.npu))
def scores(dev,waiting):
    reps={q['id']:representative(dev,q) for q in waiting};mean=sum(v[1] for v in reps.values())/len(reps)
    return {q['id']:math.log(2 if q['priority']=='urgent' else 1)-math.log(reps[q['id']][1]/1e9)-max(q['arrival_ns']+q['deadline_offset_ns']-dev.now-reps[q['id']][0],0)/(2*mean) for q in waiting}
def rule_choice(dev,waiting,rule):
    if rule not in RULES:raise ValueError('unknown rule')
    legal=[(q,b) for q in waiting for b in e.routes(q,dev.npu) if dev.feasible([(q,b)])]
    if not legal:return None
    if rule=='FIFO_HOL':
        head=min(waiting,key=tie);legal=[(q,b) for q,b in legal if q['id']==head['id']]
        if not legal:return None
    sc=scores(dev,waiting) if rule=='ATC' else {}
    def key(job):
        q,b=job;path=(response(dev.estimate(q,b),q),sum(dev.estimate(q,b)),e.BACKENDS.index(b))
        if rule in ('FIFO','FIFO_HOL'):return (*tie(q),*path)
        if rule=='EFT':return (path[0],*tie(q),path[1],path[2])
        if rule=='EDD':return(q['arrival_ns']+q['deadline_offset_ns'],*tie(q),*path)
        return(-sc[q['id']],*tie(q),*path)
    return [min(legal,key=key)]

def candidates(dev,waiting):
    sc=scores(dev,waiting);atc=sorted(waiting,key=lambda q:(-sc[q['id']],*tie(q)));edd=sorted(waiting,key=lambda q:(q['arrival_ns']+q['deadline_offset_ns'],*tie(q)))
    chosen=atc[:4]
    for task in ('classification','detection'):
        xs=[q for q in waiting if q['task']==task]
        if xs:chosen.append(min(xs,key=tie))
    fallback=rule_choice(dev,waiting,'EDD');fast=rule_choice(dev,waiting,'EFT')
    for jobs in (fallback,fast):
        if jobs:chosen.extend(q for q,b in jobs)
    ids={q['id'] for q in chosen};slots=[q for q in atc if q['id'] in ids]
    if len(slots)>REQUEST_SLOTS:raise ValueError('candidate overflow; no silent truncation')
    return slots,sc,dict(atc_order=[q['id'] for q in atc],edd_order=[q['id'] for q in edd],top4_same={q['id'] for q in atc[:4]}=={q['id'] for q in edd[:4]})

def bank(dev,slots):
    actions=[[(q,b)] for q in slots for b in e.routes(q,dev.npu)]
    for c in slots:
        if c['task']!='classification':continue
        for d in slots:
            if d['task']!='detection':continue
            for b in ('GPU','NPU') if dev.npu else ('GPU',):actions.append([(c,b),(d,'CPU')])
    actions.append([])
    if len(actions)>49 or len(actions)>SLOTS:raise ValueError('derived action bound')
    physical=np.zeros(SLOTS,dtype=bool)
    for i,jobs in enumerate(actions):physical[i]=not jobs or dev.feasible(jobs)
    operational=physical.copy()
    # WAIT legality and work-conserving convention are different predicates.
    if physical[:len(actions)-1].any():operational[len(actions)-1]=False
    if not operational.any():raise ValueError('mask invariant')
    return actions,physical,operational

def clip(x):return float(np.clip(x,-10,10))
def encode(dev,waiting,slots,sc,actions,mask):
    req=[]
    for q in slots:
        ds=[dev.estimate(q,b) if b in e.routes(q,dev.npu) else [0]*5 for b in e.BACKENDS]
        row=[float(q['task']=='classification'),float(q['task']=='detection'),float(q['priority']=='urgent'),clip((dev.now-q['arrival_ns'])/6e9),clip((q['arrival_ns']+q['deadline_offset_ns']-dev.now)/6e9),clip((q['arrival_ns']+(1.5e9 if q['priority']=='urgent' else 6e9)-dev.now)/6e9),q['deadline_offset_ns']/6e9]
        row.extend(v for vds in ds for v in (sum(vds)/6e9,response(vds,q)/6e9))
        row.extend(float(b in e.routes(q,dev.npu)) for b in e.BACKENDS)
        row.extend([clip(sc[q['id']]/10),q['arrival_ns']/120e9,q['ordinal']/512,1.])
        if len(row)!=REQUEST_DIM:raise ValueError('request dimension derivation')
        req.extend(row)
    req.extend([0.]*(REQUEST_DIM*(REQUEST_SLOTS-len(slots))))
    public=dev.public();resource=[]
    for b in e.BACKENDS:
        owner=public['lanes'][b]
        if owner:
            q=owner['request'];elapsed=dev.now-owner['dispatch'];ds=owner['estimate_ns']
            resource.extend([1.,float(q['task']=='classification'),float(q['task']=='detection'),float(q['priority']=='urgent'),(['ASSIGNED']+list(e.PHASES)).index(owner['phase'])/5,clip(elapsed/6e9),max(sum(ds)-elapsed,0)/6e9,max(response(ds,q)-elapsed,0)/6e9])
        else:resource.extend([0.]*RESOURCE_DIM)
    n=len(waiting);globalf=[dev.now/120e9,n/512,sum(q['priority']=='urgent' for q in waiting)/n,sum(q['task']=='classification' for q in waiting)/n,len(slots)/8,sum(bool(v) for v in public['lanes'].values())/2,public['observed_responses']/512,float(dev.npu)]
    state=np.array(req+resource+globalf,dtype=np.float32)
    vectors=np.zeros((SLOTS,ACTION_DIM),dtype=np.float32);idx={q['id']:i for i,q in enumerate(slots)}
    fallback=rule_choice(dev,waiting,'EDD');fid={(q['id'],b) for q,b in fallback or []}
    for i,jobs in enumerate(actions):
        vectors[i,0]=float(not jobs);vectors[i,1]=float(len(jobs)==2)
        for j,(q,b) in enumerate(jobs):vectors[i,2+j*8+idx[q['id']]]=1;vectors[i,18+j*3+e.BACKENDS.index(b)]=1
        if jobs:
            ds=[dev.estimate(q,b,jobs) for q,b in jobs]
            vectors[i,24:]=[sum(q['priority']=='urgent' for q,b in jobs)/2,sum(q['priority']=='normal' for q,b in jobs)/2,max(sum(x) for x in ds)/6e9,max(response(x,q) for x,(q,b) in zip(ds,jobs))/6e9,clip(min(q['arrival_ns']+q['deadline_offset_ns']-dev.now-response(x,q) for x,(q,b) in zip(ds,jobs))/6e9),clip(max(sc[q['id']] for q,b in jobs)/10),len(jobs)/2,float(any((q['id'],b) in fid for q,b in jobs))]
    if state.shape!=(STATE_DIM,) or not np.isfinite(state).all() or not np.isfinite(vectors).all():raise ValueError('encoding ABI')
    return state,vectors

class Controller:
    def __init__(self,rule='ATC',network=None,generator=None,deterministic=True,collect=False):
        self.rule=rule;self.network=network;self.generator=generator;self.deterministic=deterministic;self.collect=collect
        self.frames=[];self.decisions=[];self.errors=[]
    def choose(self,dev,waiting):
        begin=time.perf_counter_ns()
        if self.network is None:
            jobs=rule_choice(dev,waiting,self.rule)
            self.decisions.append(dict(now_ns=dev.now,queue=len(waiting),total_us=(time.perf_counter_ns()-begin)/1e3,chosen=[(q['id'],b) for q,b in jobs or []]))
            return jobs
        t=begin;slots,sc,diag=candidates(dev,waiting);atc_us=(time.perf_counter_ns()-t)/1e3
        t=time.perf_counter_ns();actions,physical,mask=bank(dev,slots);state,vec=encode(dev,waiting,slots,sc,actions,mask);build_us=(time.perf_counter_ns()-t)/1e3
        infer_us=0.;logprob=None;value=None
        try:
            if int(mask.sum())==1:chosen=int(np.flatnonzero(mask)[0])
            else:
                t=time.perf_counter_ns()
                with torch.no_grad():
                    dist,val=self.network(torch.from_numpy(state)[None],torch.from_numpy(vec)[None],torch.from_numpy(mask)[None])
                    probs=dist.probs[0]
                    if not torch.isfinite(probs).all() or not torch.isfinite(val).all():raise ValueError('nonfinite model')
                    chosen=int(torch.argmax(probs)) if self.deterministic else int(torch.multinomial(probs,1,generator=self.generator))
                    logprob=float(dist.log_prob(torch.tensor([chosen])));value=float(val[0,0])
                infer_us=(time.perf_counter_ns()-t)/1e3
            if chosen>=len(actions) or not mask[chosen]:raise ValueError('bad selected action')
        except (ValueError,RuntimeError) as error:
            fallback=rule_choice(dev,waiting,'EDD');self.errors.append(repr(error))
            self.decisions.append(dict(now_ns=dev.now,queue=len(waiting),model_error=repr(error),total_us=(time.perf_counter_ns()-begin)/1e3,chosen=[(q['id'],b) for q,b in fallback or []]))
            return fallback
        decision=dict(now_ns=dev.now,queue=len(waiting),candidates=len(slots),actions=len(actions),physical_legal=int(physical.sum()),legal=int(mask.sum()),atc_us=atc_us,build_us=build_us,infer_us=infer_us,total_us=(time.perf_counter_ns()-begin)/1e3,chosen=[(q['id'],b) for q,b in actions[chosen]],**diag)
        self.decisions.append(decision)
        if self.collect:self.frames.append(dict(now_ns=dev.now,state=state,candidates=vec,mask=mask,action=chosen,informative=mask.sum()>1,logprob=logprob,old_value=value))
        return actions[chosen] or None
