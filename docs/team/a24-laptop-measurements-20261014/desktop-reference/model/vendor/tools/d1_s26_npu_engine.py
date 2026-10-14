"""S26 short service plant. Six measured contexts; no energy/thermal/learning."""
from __future__ import annotations
import copy
import csv
import hashlib
import heapq
import json
import math
from pathlib import Path

VERSION = 's26-short-npu-service-v1'
BACKENDS = ('CPU', 'GPU', 'NPU')
PHASES = ('EXECUTING', 'OUTPUT_READY', 'PERSISTED', 'WORKER_RELEASED', 'AVAILABLE')
FIELDS = ('execution_start_ns', 'output_ready_ns', 'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')
PHASE_NAMES = ('dispatch_to_execution_start', 'execution_start_to_output_ready', 'output_ready_to_persist_complete', 'persist_complete_to_worker_release', 'worker_release_to_lane_available')
CELLS = ('CPU_URGENT|classification|CPU', 'CPU_URGENT|detection|CPU', 'B2_PARALLEL|classification|GPU', 'B2_PARALLEL|detection|CPU', 'NPU_PARALLEL|classification|NPU', 'NPU_PARALLEL|detection|CPU')
SPLITS = dict(train=[0,1,2,3,8,9,10,11], dev=[4,5,12,13], confirm=[6,7,14,15])
REQUEST_FIELDS = {'id','task','priority','ordinal','arrival_ns','deadline_offset_ns'}
HORIZON = 120_000_000_000

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
def write(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    tmp.replace(path)
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def routes(q, npu=True):
    if q['task']=='classification': return BACKENDS if npu else BACKENDS[:2]
    if q['task']=='detection': return ('CPU',)
    raise ValueError('unsupported task')

def profile(source):
    root=Path(source); mp=root/'d1sim/a24fmt_v1/out/s26_a24fmt_model.json'
    rp=root/'d1sim/parsim_v1/data/r3_requests.csv'; sp=root/'d1sim/parsim_v1/data/r3_sessions.csv'
    raw=read(mp)
    if tuple(raw['phases'])!=PHASE_NAMES: raise ValueError('phase ABI mismatch')
    sessions={int(r['index']):r for r in csv.DictReader(sp.open(encoding='utf-8',newline=''))}
    pools={s:{k:[] for k in CELLS} for s in SPLITS}
    allrows={k:[] for k in CELLS}; groups={}
    context={'CPU_URGENT_ONLINE_V1':'CPU_URGENT','B2_PARALLEL_ONLINE_V1':'B2_PARALLEL','S26_NPU_PARALLEL_V1':'NPU_PARALLEL'}
    for r in csv.DictReader(rp.open(encoding='utf-8',newline='')):
        index=int(r['index']); session=sessions[index]
        if session['eligible']!='True' or session['valid_log']!='True' or r['terminal_status']!='succeeded': raise ValueError('ineligible R3 row')
        key=f"{context[session['policy']]}|{r['task_id']}|{r['selected_backend']}"
        times=[int(r['dispatch_ns'])]+[int(r[f]) for f in FIELDS]
        ds=[times[i+1]-times[i] for i in range(5)]
        if key not in CELLS or min(ds)<0 or sum(ds)<=0: raise ValueError('invalid intact vector')
        row=dict(session_index=index,session_id=session['session_id'],request_id=r['request_id'],durations_ns=ds)
        allrows[key].append(row)
        for split, indices in SPLITS.items():
            if index in indices:pools[split][key].append(row)
        groups.setdefault(index,[]).append(r)
    audit={}
    for key, rows in allrows.items():
        means=[sum(r['durations_ns'][j] for r in rows)/len(rows) for j in range(5)]
        delta=max(abs(x-y) for x,y in zip(means,raw['service'][key]['phase_means_ns']))
        if len(rows)!=raw['service'][key]['n'] or delta>1e-6: raise ValueError('S0/raw mismatch')
        audit[key]=dict(n=len(rows),max_mean_delta_ns=delta,source_mean_occupancy_ms=sum(means)/1e6)
    # Means are recomputed on training sessions only. Confirmation vectors are not policy estimates.
    means={k:[sum(r['durations_ns'][j] for r in pools['train'][k])/len(pools['train'][k]) for j in range(5)] for k in CELLS}
    if any(not pools[s][k] for s in SPLITS for k in CELLS):raise ValueError('empty split cell')
    return dict(schema=VERSION,phases=list(PHASE_NAMES),means=means,pools=pools,splits=SPLITS,
        session_ids={s:[sessions[i]['session_id'] for i in ids] for s,ids in SPLITS.items()},
        sources={str(p.relative_to(root)).replace('\\','/'):sha(p) for p in (mp,rp,sp)},audit=audit,
        energy_j=None,peak_ap_c=None,quality_status='exploratory; request-runner/GPU precision/NPU FP16 acceptance unconfirmed',
        assumptions=['whole-session context transported to instantaneous dispatch; solo accelerator/partial overlap not independently validated','intact per-request bootstrap; cross-request session dependence not reconstructed','CPU1 no long-load slowdown; no power/thermal'],horizon_cap_ns=HORIZON)

class Device:
    def __init__(self, model, split='train', environment_seed=0, npu=True, deterministic=False):
        if model['schema']!=VERSION or tuple(model['phases'])!=PHASE_NAMES or model.get('energy_j') is not None or model.get('peak_ap_c') is not None:raise ValueError('service ABI/cost mismatch')
        if set(model['means'])!=set(CELLS) or model['horizon_cap_ns']!=HORIZON:raise ValueError('cell/horizon mismatch')
        for ds in model['means'].values():
            if len(ds)!=5 or any(not math.isfinite(x) or x<0 for x in ds) or sum(ds)<=0:raise ValueError('bad means')
        self.model=model; self.split=split; self.seed=int(environment_seed); self.npu=npu; self.deterministic=deterministic
        self.now=0; self._owners={b:None for b in BACKENDS}; self._events=[]; self.records={};self.events=[]
    def key(self,q,b,jobs=()):
        if b not in routes(q,self.npu):raise ValueError('unsupported backend')
        active=[(v['request']['task'], bb) for bb,v in self._owners.items() if v]+[(r['task'],bb) for r,bb in jobs]
        if b=='GPU' or q['task']=='detection' and ('classification','GPU') in active: ctx='B2_PARALLEL'
        elif b=='NPU' or q['task']=='detection' and ('classification','NPU') in active:ctx='NPU_PARALLEL'
        else:ctx='CPU_URGENT'
        return f"{ctx}|{q['task']}|{b}"
    def estimate(self,q,b,jobs=()):return list(self.model['means'][self.key(q,b,jobs)])
    def feasible(self,jobs):
        if not 1<=len(jobs)<=2 or len({q['id'] for q,b in jobs})!=len(jobs) or len({b for q,b in jobs})!=len(jobs):return False
        labels=[(v['request']['task'],b) for b,v in self._owners.items() if v]
        for q,b in jobs:
            if b not in self._owners or self._owners[b] or b not in routes(q,self.npu) or q['id'] in self.records or q['arrival_ns']>self.now:return False
            labels.append((q['task'],b))
        return len(labels)==1 or len(labels)==2 and set(labels) in ({('classification','GPU'),('detection','CPU')},{('classification','NPU'),('detection','CPU')})
    def public(self):
        return dict(now_ns=self.now,lanes=copy.deepcopy(self._owners),npu_enabled=self.npu,observed_responses=sum('response_ns' in r for r in self.records.values()))
    def _sample(self,q,key):
        if self.deterministic:return [round(x) for x in self.model['means'][key]],None
        pool=self.model['pools'][self.split][key]
        # Same request/context outcomes for every policy, irrespective of dispatch order/action RNG.
        h=int(digest([self.seed,q['id'],key]),16); row=pool[h%len(pool)]
        return list(row['durations_ns']),row
    def dispatch(self,jobs):
        if not self.feasible(jobs):raise ValueError('infeasible/duplicate bundle')
        prepared=[]
        for q,b in jobs:
            if set(q)!=REQUEST_FIELDS or q['priority'] not in ('urgent','normal'):raise ValueError('request ABI')
            key=self.key(q,b,jobs); ds,origin=self._sample(q,key);t=self.now;bounds=[]
            for d in ds:t+=d;bounds.append(t)
            prepared.append((q,b,key,ds,bounds,origin))
        for q,b,key,ds,bounds,origin in prepared:
            self.records[q['id']]=dict(q,backend=b,context=key,dispatch_ns=self.now,status='running',realized_durations_ns=ds,sample_origin=origin)
            self._owners[b]=dict(request=copy.deepcopy(q),phase='ASSIGNED',since=self.now,dispatch=self.now,estimate_ns=list(self.model['means'][key]))
            self.events.append(dict(time_ns=self.now,id=q['id'],backend=b,phase='ASSIGNED'))
            for i,t in enumerate(bounds):heapq.heappush(self._events,(t,BACKENDS.index(b),i,q['id'],b))
    def advance(self,to):
        if to<self.now or to>HORIZON:raise ValueError('time range')
        while self._events and self._events[0][0]<=to:
            at,_,i,rid,b=heapq.heappop(self._events);r=self.records[rid];r[FIELDS[i]]=at
            if i==(1 if r['priority']=='urgent' else 2):r['response_ns']=at-r['arrival_ns'];r['response_at_ns']=at
            if i==4:self._owners[b]=None;r['status']='succeeded'
            else:self._owners[b].update(phase=PHASES[i],since=at)
            self.events.append(dict(time_ns=at,id=rid,backend=b,phase=PHASES[i]))
        self.now=to
    def next_event(self):return self._events[0][0] if self._events else None

def percentile(xs,p=.95):
    return sorted(xs)[max(0,math.ceil(len(xs)*p)-1)] if xs else None
def metrics(ledger):
    m=dict(planned=len(ledger),completed=sum(r['status']=='succeeded' for r in ledger),energy_j=None,peak_ap_c=None,experiment_ready=False)
    m['incomplete']=m['planned']-m['completed']; weighted=0.; tardiness=0.
    for pr,cap in [('urgent',1_500_000_000),('normal',6_000_000_000)]:
        rows=[r for r in ledger if r['priority']==pr]; responses=[r['response_ns']/1e6 for r in rows if 'response_ns' in r]
        m[pr+'_planned']=len(rows);m[pr+'_p95_ms']=percentile(responses);m[pr+'_mean_ms']=sum(responses)/len(responses) if responses else None
        for name,original in [('failure',True),('declared_failure',False)]:
            failures=sum('response_ns' not in r or r['response_ns']>(cap if original else r['deadline_offset_ns']) for r in rows)
            m[pr+'_'+name]=failures
        for r in rows:
            w=2 if pr=='urgent' else 1;d=r['deadline_offset_ns'];resp=r.get('response_ns',HORIZON-r['arrival_ns'])
            weighted+=w*('response_ns' not in r or resp>d);tardiness+=w*max(resp-d,0)/1e9
    m['weighted_declared_misses']=weighted;m['weighted_tardiness_s']=tardiness
    m['backend_counts']={b:sum(r.get('backend')==b for r in ledger) for b in BACKENDS}
    m['service_cost']=service_cost(ledger)
    return m

def request_cost(r,n,nu,nn):
    pr=r['priority'];den=max(nu if pr=='urgent' else nn,1);d=r['deadline_offset_ns']; cap=1_500_000_000 if pr=='urgent' else 6_000_000_000
    resp=r.get('response_ns',HORIZON-r['arrival_ns']);missing='response_ns' not in r
    weight=20. if pr=='urgent' else 5.
    return weight*((missing or resp>d)+(missing or resp>cap))/den + (0.2 if pr=='urgent' else 0.1)*resp/cap/den + (2 if pr=='urgent' else 1)*max(resp-d,0)/d/max(n,1) + 50*(r['status']!='succeeded')/max(n,1)
def service_cost(ledger):
    n=len(ledger);nu=sum(r['priority']=='urgent' for r in ledger);nn=n-nu
    return sum(request_cost(r,n,nu,nn) for r in ledger)

def simulate(model,requests,controller,split='train',environment_seed=0,npu=True,deterministic=False):
    if not requests or len({q['id'] for q in requests})!=len(requests):raise ValueError('empty/duplicate roster')
    for q in requests:
        if set(q)!=REQUEST_FIELDS or not 0<=q['arrival_ns']<HORIZON or q['deadline_offset_ns']<=0 or q['priority'] not in ('urgent','normal'):raise ValueError('request range/ABI')
        routes(q,npu)
    pending=sorted(copy.deepcopy(requests),key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']));dev=Device(model,split,environment_seed,npu,deterministic);waiting=[];cursor=0
    while dev.now<HORIZON:
        dev.advance(dev.now)
        while cursor<len(pending) and pending[cursor]['arrival_ns']<=dev.now:waiting.append(pending[cursor]);cursor+=1
        if waiting:
            jobs=controller.choose(dev,waiting)
            if jobs:
                dev.dispatch(jobs);ids={q['id'] for q,b in jobs};waiting=[q for q in waiting if q['id'] not in ids];continue
        if cursor==len(pending) and not waiting and dev.next_event() is None:break
        future=[HORIZON]
        if cursor<len(pending):future.append(pending[cursor]['arrival_ns'])
        if dev.next_event() is not None:future.append(dev.next_event())
        nxt=min(t for t in future if t>dev.now);dev.advance(nxt)
    ledger=[]
    for q in requests:
        r=copy.deepcopy(dev.records.get(q['id'],dict(q,status='unfinished')))
        if r['status']=='running':r['status']='unfinished'
        ledger.append(r)
    return dict(metrics=metrics(ledger),ledger=ledger,events=dev.events,end_ns=dev.now,split=split,environment_seed=environment_seed,npu=npu,quality_status=model['quality_status'])
