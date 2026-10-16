"""Registered full-queue PC-only study, frozen paired references and final data."""
import argparse, copy, gzip, hashlib, json, os, platform, subprocess, time
from dataclasses import asdict,is_dataclass
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_common_compare_policy as a
from tools import d1_common_compare_ppo as learning
from tools import d1_common_compare_budget as budget

from tools import d1_desktop_seed_registry as registry
from tools import d1_common_compare_engine as engine
from tools import d1_list_candidate_rl_training as native
ROOT=Path(__file__).resolve().parents[1]
SEEDS=(211,223,239)
FAMILIES=("low","queue","burst","sustained")
CONTEXTS=("mean","short_context","long_context")
BASES=("FIFO_READY","SPT","EDD","ATC")
MODES=("ORDER","JOINT")
TRAIN=tuple(range(891110101,891110229))
DEV=(891210101,891210102)
CONFIRM=(891310101,891310102,891310103,891310104)
REALIZATION=891000201
FACTORS=("measured_fixed","measured_variable","io_fixed","io_variable")
RESIDUAL=(.8,.9,1.1,1.2)
STAGES=(128,256)
def serial(x):
    if isinstance(x,dict):return {str(k):serial(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [serial(v) for v in x]
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    return x


def write(path,x):budget.write(path,serial(x))


def payload_digest(value):
    """Lossless dataclass metadata normalization for archive checks, not policy input."""
    def normalize(v):
        if is_dataclass(v):
            return dict(dataclass_type=type(v).__module__+"."+type(v).__qualname__,fields=normalize(asdict(v)))
        if isinstance(v,dict):return {k:normalize(x) for k,x in v.items()}
        if isinstance(v,(tuple,list)):return [normalize(x) for x in v]
        return v
    return native.state_digest(normalize(value))


def cases(seeds):
    return [dict(arrival_seed=s,family=f,factor=v,context="per_request_frozen_context",condition=i)
            for i,(s,f,v) in enumerate((s,f,v) for s in seeds for f in FAMILIES for v in FACTORS)]

def hashed(seed,rid,label):
    return int.from_bytes(hashlib.sha256(f"{seed}/{rid}/{label}".encode()).digest()[:8],"big")

def tickets(case):
    qs=copy.deepcopy(a.external.old.workload(case['family'],case['arrival_seed']))
    for q in qs:
        q['service_class']=hashed(case['arrival_seed'],q['id'],'public-io-class')%3 if case['factor'].startswith('io_') else 0
        if case['factor'].endswith('_variable'):
            q['deadline_offset_ns']=a.DEADLINES_NS[q['priority']][hashed(case['arrival_seed'],q['id'],'public-deadline')%3]
    return qs

def realized_vectors(f,qs,realization,arrival_seed):
    out={}
    for q in qs:
        noise=RESIDUAL[hashed(realization+arrival_seed,q['id'],'private-io-residual')%4]
        routes={}
        for b in a.p.backends(q):
            samples=a.measured.POOL[a.p.key(q,b)];cell=[]
            for index in range(4):
                sample=samples[hashed(realization+arrival_seed,q['id'],b+str(index)+'private-raw')%len(samples)]
                ds=list(sample['durations_ns']);ds[1]+=a.IO_EXTRA_NS[q['service_class']]*noise
                cell.append(dict(source_request_id=sample['source_request_id'],durations_ns=ds))
            routes[b]=cell
        out[q['id']]=routes
    return dict(per_request=out)

def response_metrics(rows,horizon=120e9):
    out={};denom=sum(2 if r['priority']=='urgent' else 1 for r in rows)
    for priority,cap in (('urgent',1.5e9),('normal',6e9)):
        out[priority+'_failure']=sum(r['priority']==priority and ('response_ns' not in r or r['response_ns']>r['deadline_offset_ns']) for r in rows)
        out['original_'+priority+'_failure']=sum(r['priority']==priority and ('response_ns' not in r or r['response_ns']>cap) for r in rows)
    out['weighted_miss_rate']=(2*out['urgent_failure']+out['normal_failure'])/denom
    out['weighted_normalized_tardiness']=sum((2 if r['priority']=='urgent' else 1)*max((r.get('response_ns',horizon-r['arrival_ns'])/r['deadline_offset_ns'])-1,0) for r in rows)/denom
    out['tardiness_is_lower_bound']=not all('response_ns' in r for r in rows)
    vals=[r['response_ns']/r['deadline_offset_ns'] for r in rows if 'response_ns' in r]
    out['normalized_response_p95']=a.native.rank95(vals) if vals else None
    return out


class Proxy:
    def __init__(self,controller):
        self.controller=controller;self.callbacks=[];self.observation_seconds=0.;self.event_seconds=0.;self.pending_event_seconds=0.
    def __getattr__(self,key):return getattr(self.controller,key)
    def __call__(self,*args):
        t=time.perf_counter()
        try:return self.controller(*args)
        finally:
            elapsed=time.perf_counter()-t
            self.callbacks.append(dict(seconds=elapsed,event_to_dispatch_seconds=elapsed+self.pending_event_seconds,queue=len(args[1])))
            self.pending_event_seconds=0.
    def observe(self,*args):
        t=time.perf_counter()
        try:return self.controller.observe(*args)
        finally:
            elapsed=time.perf_counter()-t;self.observation_seconds+=elapsed;self.pending_event_seconds+=elapsed
    def on_public_event(self,event):
        t=time.perf_counter()
        try:return self.controller.on_public_event(event)
        finally:
            elapsed=time.perf_counter()-t;self.event_seconds+=elapsed;self.pending_event_seconds+=elapsed


def audit_ledger(result):
    seen=set()
    for r in result["ledger"]:
        if r["id"] in seen:raise ValueError("duplicate planned ledger")
        seen.add(r["id"])
        if "backend" not in r:continue
        if r["backend"] not in a.p.backends(r):raise ValueError("unsupported actual backend")
        fields=["dispatch_ns",*a.FIELDS]
        available=[r[k] for k in fields if k in r]
        if any(y<x for x,y in zip(available,available[1:])):raise ValueError("phase order")
        if "response_ns" in r:
            boundary="output_ready_ns" if r["priority"]=="urgent" else "persist_complete_ns"
            if abs((r[boundary]-r["arrival_ns"])-r["response_ns"])>1:raise ValueError("response boundary")
    spans=[r for r in result["ledger"] if "dispatch_ns" in r]
    for i,r in enumerate(spans):
        for s in spans[i+1:]:
            if max(r["dispatch_ns"],s["dispatch_ns"])<min(r.get("lane_available_ns",120e9),s.get("lane_available_ns",120e9)):
                a.p.state([r["task"]+"_"+r["backend"],s["task"]+"_"+s["backend"]])
    return dict(planned=len(seen),no_duplicate=True,phase_and_response_available_checked=True)


def collect(b,folder,identity,phase,case,agent,learning_episode=False,zero=False):
    f,init,_=a.hybrid.load();initial=init["initial"]
    qs=case.get("requests") or tickets(case)
    realization=REALIZATION+(2 if phase.startswith('confirmation') else 1 if phase.startswith('dev') else 0)
    vectors=realized_vectors(f,qs,realization,case["arrival_seed"])
    if zero:
        for routes in vectors['per_request'].values():
            for rows in routes.values():
                for r in rows:r['durations_ns']=[0.]*5
    proxy=Proxy(agent);t=time.perf_counter();cpu=time.process_time()
    with b.environment(identity,phase,learning_episode):
        if isinstance(agent,a.Controller):
            # Any queue-drain/placement or future-cost call during policy selection is a contract failure.
            with patch.object(a.p.Controller,"rollout",side_effect=AssertionError("online queue-drain forecast")), \
                 patch.object(a.p.Controller,"place",side_effect=AssertionError("online virtual placement")), \
                 patch.object(a.hybrid,"costs",side_effect=AssertionError("online future AP/J")):
                result=engine.simulate(dict(protocol=a.VERSION,cells=a.measured.MEANS),vectors,qs,
                    policy=agent.policy,settings=a.external.settings(),seed=realization,decision_provider=proxy)
        else:
            result=engine.simulate(dict(protocol=a.VERSION,cells=a.measured.MEANS),vectors,qs,
                policy=agent.policy,settings=a.external.settings(),seed=realization,decision_provider=proxy)
        audit=audit_ledger(result)
        segments,costs,end=a.hybrid.account(result,initial,f)
        rows=result["ledger"];full=all(r["status"]=="succeeded" for r in rows)
        row=dict(identity=identity,phase=phase,policy=case.get("role") or getattr(agent,"public_policy",getattr(agent,"policy","unknown")),
            **{k:v for k,v in case.items() if k!="requests" and k!="role"},planned=len(qs),
            completed=sum(r["status"]=="succeeded" for r in rows),
            incomplete=sum(r["status"]!="succeeded" for r in rows),
            urgent_planned=sum(r["priority"]=="urgent" for r in rows),
            normal_planned=sum(r["priority"]=="normal" for r in rows),
            urgent_failure=sum(r["priority"]=="urgent" and ("response_ns" not in r or r["response_ns"]>r["deadline_offset_ns"]) for r in rows),
            normal_failure=sum(r["priority"]=="normal" and ("response_ns" not in r or r["response_ns"]>r["deadline_offset_ns"]) for r in rows),
            urgent_p95_ms=result["metrics"]["urgent_p95_ms"],normal_mean_ms=result["metrics"]["normal_mean_ms"],
            energy_j=costs["whole_120s_j"] if full else None,
            peak_ap_c=max(costs["ap_path"]) if full else None,
            native_seconds=time.perf_counter()-t,cpu_seconds=time.process_time()-cpu,
            callbacks=len(proxy.callbacks),controller_observation_seconds=proxy.observation_seconds,controller_event_seconds=proxy.event_seconds,
            modeled_temperature_channel="AP model-plant observation; not surface",experiment_ready=False)
        row['declared_urgent_failure']=sum(r['priority']=='urgent' and ('response_ns' not in r or r['response_ns']>r['deadline_offset_ns']) for r in rows)
        row['declared_normal_failure']=sum(r['priority']=='normal' and ('response_ns' not in r or r['response_ns']>r['deadline_offset_ns']) for r in rows)
        row.update(response_metrics(rows))
        row['realization_seed']=realization
        row['assumption']='A24 ABBA4 intact bootstrap; io_* adds unmeasured public I/O sensitivity only; declared deadlines are engineering requirements within original caps'
        row["normal_p95_ms"]=a.native.rank95([r["response_ns"]/1e6 for r in rows if r["priority"]=="normal" and "response_ns" in r]) if any(r["priority"]=="normal" and "response_ns" in r for r in rows) else None
        row["max_wait_ms"]=max([(r["dispatch_ns"]-r["arrival_ns"])/1e6 for r in rows if "dispatch_ns" in r] or [0.])
        row["fallbacks"]=getattr(agent,"stats",{}).get("fallback",0)
        row["nonhead_decisions"]=sum(s.get("nonhead_selected",False) for s in getattr(agent,"snapshots",[]))
        ticket_by={q['id']:q for q in qs}
        def template(action):
            if action['kind']=='resource_wait':return ('resource_wait',)
            return action['kind'],tuple(sorted((ticket_by[j['request_id']]['task'],j['backend']) for j in action['jobs']))
        row['physical_choice_decisions']=sum(len({template(ac) for ac,m in zip(sn['actions'],sn['mask']) if m})>1 for sn in getattr(agent,'snapshots',[]))
        curve=list(zip(range(35,end+1),costs["ap_path"]))
        raw=dict(row=row,result=result,curve=curve,segments=segments,
            snapshots=getattr(agent,"snapshots",[]),events=getattr(agent,"events",[]),
            stats=getattr(agent,"stats",{}),stage_times=getattr(agent,"times",[]),
            callbacks=proxy.callbacks,audit=audit)
        path=folder/"items"/(identity+".json.gz");path.parent.mkdir(exist_ok=True)
        if path.exists():raise FileExistsError("raw item already exists")
        path.write_bytes(gzip.compress(json.dumps(serial(raw),ensure_ascii=False,allow_nan=False).encode("utf8")))
        write(folder/"rows"/(identity+".json"),dict(row=row,raw_sha256=budget.digest(path)))
    return raw

def sources():
    import sys
    paths={Path(v.__file__).resolve() for k,v in sys.modules.copy().items() if k.startswith('tools.') and getattr(v,'__file__',None)}
    paths|={Path(__file__).resolve(),ROOT/'tools/test_d1_common_compare.py',a.measured.CSV,a.hybrid.MODEL,a.p.BUNDLE/'model.json',a.p.BUNDLE/'initial_inputs.json',ROOT/'docs/results/list_candidate_rl_review_01/design_amendment_v4.json'}
    return {p.relative_to(ROOT).as_posix():budget.digest(p) for p in sorted(paths) if p.is_relative_to(ROOT)}

def register(folder):
    reserved=registry.collect();new=set(TRAIN+DEV+CONFIRM)
    if new & set(reserved['seeds']) or any(lo<=s<=hi for s in new for lo,hi in reserved['ranges']):raise ValueError('seed reservation collision')
    inputs=dict(train=[dict(arrival_seed=TRAIN[i//4],family=FAMILIES[i%4],context="per_request_frozen_context",factor=FACTORS[(i//4)%4],condition=i) for i in range(256)],development=cases(DEV),confirmation=cases(CONFIRM))
    b=budget.Budget.register(folder,dict(user_authorized='full queue, three expert reviews, implement/train/compare on PC',device='A24 fixed measured plant',preflight_tests=6))
    reg=dict(task=budget.TASK,caps=budget.CAPS,head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),schema=a.SCHEMA,settings=asdict(a.DEFAULT),objective=learning.OBJECTIVE,sources=sources(),input_sha=a.native.digest(inputs),seeds=SEEDS,stages=STAGES,io_extra_ns=a.IO_EXTRA_NS,io_residual=RESIDUAL,declared_deadlines_ns=a.DEADLINES_NS,factors=FACTORS,modes=MODES,
        candidate='ALL arrived/unstarted requests; no topK; request cap24 or error, never silently truncate',actions='single request commit, immediate same-time redecision; K=2C+D+blocked wait<=49; dynamic actiondim42; batch false-padding only',state_dim=510,action_dim=42,
        baselines=BASES,primary='one declared deadline per request for training/dev/final: weighted response-miss rate; normalized weighted tardiness; completion and original caps guard separately',importance='urgent2/normal1 policy input, not monetary delay cost',
        ready_contract='all primary FIFO_READY/SPT/EDD/ATC/ORDER share one currently legal shortest AVAILABLE-finish route per request; WAIT false whenever any runnable action; separate from physical impossibility',joint_control='JOINT same work-conserving physical support, all CPU/GPU paths to separate routing effect; no bundle action',
        reference_version='COMMON_DECLARED_DEADLINE_STRICT_V4',strict='same primary case-by-case incomplete/U/N/P95/weighted_miss/tardiness/J/AP epsilon0 nonworse vs FIFO_READY/SPT/EDD/ATC; original1.5/6 guard preserved; full completion, low/sustained absolute service0; J/AP strict gain only after service protection',physical='C_CPU/C_GPU/D_CPU/CG_DC only; max2/nonpreemptive/actualAVAILABLE; response separate; resource wait only, no NPU/cooling',
        selection='dev32 lexicographic incomplete, weightedmiss, weightedtardiness, urgentP95, J, AP then earliest checkpoint; one representative per ORDER/JOINT and every seed reported; freeze before confirm64',
        learning='reward=-weighted declared miss-.2weighted normalized tardiness; J residual/10 cost weight.05; incomplete cost initial100 dual eta.01 cap100; gamma1/noGAE',
        rng='fresh 3 base seeds paired across ORDER/JOINT, independent learner states/action seed+10000/shuffle+20000; hidden realization keyed arrival/request/backend',realization_seeds=dict(train=REALIZATION,development=REALIZATION+1,confirmation=REALIZATION+2),final_action='fixed masked argmax, fallback tie then canonical slot',
        service_data=dict(path=a.measured.CSV.relative_to(ROOT).as_posix(),sha256=a.measured.FULL_SHA,cell_counts={k:len(v) for k,v in a.measured.POOL.items()},scope='existing ABBA4 samples, CPU n4; not independent new device validation; no synthetic batch multiplier'),
        io_scope='measured_* primary excludes synthetic I/O; io_* sensitivity adds0/25/75ms within S->O; predictable class assumption',new_model_fit=0,new_device_runs=0,S26='not used; pinned P1l service exploratory/thermal not reproduced/J not validated; other concurrent work kept separate',no_future_queue_prediction=True,experiment_ready=False,automatic_adoption=False,python=platform.python_version(),torch=torch.__version__,numpy=np.__version__,registry_sha=a.native.digest(reserved))
    write(folder/'registration.json',reg);write(folder/'inputs.json',inputs)
    write(folder/'cursor.json',dict(completed=False,stage='development_controls'))
    return dict(status='registered',task=budget.TASK,caps=budget.CAPS,schema=a.SCHEMA)

def check(folder):
    r=budget.read(folder/'registration.json')
    if r['schema']!=a.SCHEMA or r['caps']!=budget.CAPS:raise ValueError('immutable ABI/budget changed')
    for name,sha in r['sources'].items():
        if budget.digest(ROOT/name)!=sha:raise ValueError('frozen source changed: '+name)
    if a.native.digest(budget.read(folder/'inputs.json'))!=r['input_sha']:raise ValueError('inputs changed')
    return r

def deps(reg,bank):return dict(schema=a.SCHEMA,objective=learning.OBJECTIVE,sources=reg['sources'],input_sha=reg['input_sha'],sequencing=bank)

def rows(folder,prefix):return [budget.read(p)['row'] for p in sorted((folder/'rows').glob(prefix+'*.json'))]

def controller(role,f,initial,learners=None):
    if role in BASES:return a.Controller(f,initial,mode=a.RULE,sequencing=role)
    mode,seed=role.split('_');return learners[mode,int(seed)].controller(f,initial,True)

def collected(folder,b,identity,stage,case,agent,train=False,zero=False):
    path=folder/'rows'/(identity+'.json')
    if path.exists():
        receipt=budget.read(path);rawpath=folder/'items'/(identity+'.json.gz')
        if budget.digest(rawpath)!=receipt['raw_sha256']:raise ValueError('stored raw mutated')
        if train:raise ValueError('unadopted episode requires explicit boundary audit')
        return json.loads(gzip.decompress(rawpath.read_bytes()))
    failures=sum(r['event']=='failure' and r['identity'].startswith(identity) for r in b.rows)
    return collect(b,folder,identity+(f'_retry{failures}' if failures else ''),stage,case,agent,train,zero)

def evaluate(folder,b,cases_,roles,learners,stage):
    f,i,_=a.hybrid.load();initial=i['initial']
    for case in cases_:
        for role in roles:
            identity=f'{stage}_{case["condition"]:02d}_{role}'
            collected(folder,b,identity,stage,dict(case,role=role),controller(role,f,initial,learners))
    return rows(folder,stage+'_')

def key(rr):
    mean=lambda k:np.mean([q[k] if q[k] is not None else float('inf') for q in rr])
    return (sum(q['incomplete'] for q in rr),mean('weighted_miss_rate'),mean('weighted_normalized_tardiness'),mean('urgent_p95_ms'),mean('energy_j'),mean('peak_ap_c'))

def gate(rr,role):
    by={(q['condition'],q['policy']):q for q in rr};differences=[];maintain=True
    for condition in sorted({q['condition'] for q in rr}):
        q=by[condition,role]
        for baseline in BASES:
            r=by[condition,baseline]
            delta={k:q[k]-r[k] if q[k] is not None and r[k] is not None else None for k in ('incomplete','urgent_failure','normal_failure','weighted_miss_rate','weighted_normalized_tardiness','urgent_p95_ms','original_urgent_failure','original_normal_failure','energy_j','peak_ap_c')}
            absolute=q['family'] not in ('low','sustained') or q['incomplete']==q['urgent_failure']==q['normal_failure']==0
            passed=q['completed']==q['planned']==r['planned']==r['completed'] and absolute and all(v is not None and v<=0 for v in delta.values())
            maintain &= passed;differences.append(dict(condition=condition,factor=q['factor'],family=q['family'],baseline=baseline,passed=passed,delta=delta))
    gains=[]
    for family in ('low','sustained'):
        dd=[d for d in differences if d['family']==family]
        if maintain and all(d['delta']['energy_j']<0 or d['delta']['peak_ap_c']<0 for d in dd):gains.append(family)
    return dict(maintenance_pass=maintain,promising=maintain and bool(gains),promising_families=gains,epsilon=0,differences=differences,automatic_adoption=False)

def learner_path(folder,bank,seed,ep=None):return folder/'checkpoints'/f'{bank}_{seed}_{"latest" if ep is None else "ep"+str(ep)}.pt'

def run(folder,stop_after=None):
    reg=check(folder);b=budget.Budget(folder);inputs=budget.read(folder/'inputs.json');cursor=budget.read(folder/'cursor.json')
    if cursor['completed']:return dict(status='already_completed',consumption=b.used())
    f,i,_=a.hybrid.load();initial=i['initial'];accepted=0
    with b.session():
        controls=evaluate(folder,b,inputs['development'],BASES,{},'dev_controls')
        banks=MODES
        learners={}
        for bank in banks:
            for seed in SEEDS:
                path=learner_path(folder,bank,seed)
                learners[bank,seed]=learning.Learner.load(path,deps(reg,bank)) if path.exists() else learning.Learner(seed,deps(reg,bank))
        roles=[f'{bank}_{s}' for bank in banks for s in SEEDS]
        stages_done=[];reason='maximum256'
        for stage in STAGES:
            expandfile=folder/f'expand{stage}.json'
            if expandfile.exists():
                stages_done.append(stage)
                if not budget.read(expandfile)['expand']:reason=budget.read(expandfile)['reason'];break
                continue
            for n in range(stage):
                for bank in banks:
                    for seed in SEEDS:
                        l=learners[bank,seed]
                        if l.episodes>n:continue
                        if l.episodes!=n:raise ValueError('learner cursor changed')
                        identity=f'train_{bank}_{seed}_{n:03d}'
                        agent=l.controller(f,initial,False)
                        raw=collected(folder,b,identity,'train',dict(inputs['train'][n],role=f'{bank}_{seed}'),agent,True)
                        frames,costs,valid,_=learning.targets(agent,raw['row'],raw['curve'],initial['preload_power_w']*120)
                        l.add(frames,costs,valid,raw['row'])
                        l.cursor=dict(stage='train',episode=l.episodes);l.consumption=b.used();l.save(learner_path(folder,bank,seed))
                        cursor.update(stage='train',learning_accepted=sum(x.episodes for x in learners.values()))
                        write(folder/'cursor.json',cursor);accepted+=1
                        if stop_after and accepted>=stop_after:
                            write(folder/'pause_receipt.json',dict(cursor=cursor,digests={f'{bb}_{ss}':payload_digest(ll.snapshot()) for (bb,ss),ll in learners.items()},partial={f'{bb}_{ss}':len(ll.pending) for (bb,ss),ll in learners.items()}))
                            return dict(status='paused',consumption=b.used())
            for (bank,seed),l in learners.items():l.save(learner_path(folder,bank,seed,stage))
            dev=evaluate(folder,b,inputs['development'],roles,learners,f'dev{stage}')
            ok=all(l.logs and all(np.isfinite(q['actor_gradient_max']) and q['actor_gradient_max']>0 and q['actor_changed'] for q in l.logs) and all(q['row']['fallbacks']==0 for q in l.episode_logs) and any(q['row']['physical_choice_decisions']>0 for q in l.episode_logs) for l in learners.values())
            improvement=None
            expand=ok and stage!=256
            reason='maximum256' if stage==256 else ('mechanics_failure' if not ok else 'mechanics_pass_fixed_budget_extension')
            write(expandfile,dict(expand=expand,reason=reason,mechanics_pass=ok,development_improvement=None,development_improvement_checked=False,learning_accepted=sum(l.episodes for l in learners.values()),development_keys={r:key([q for q in dev if q['policy']==r]) for r in roles}))
            stages_done.append(stage)
            print(json.dumps(dict(stage=stage,expand=expand,reason=reason,consumption=b.used()),ensure_ascii=False),flush=True)
            if not expand:break
        if not (folder/'freeze.json').exists():
            selections={}
            for role in roles:
                ep=min(stages_done,key=lambda n:(key([q for q in rows(folder,f'dev{n}_') if q['policy']==role]),n))
                bank,seed=role.split('_');path=learner_path(folder,bank,int(seed),ep)
                selections[role]=dict(episodes=ep,sha256=budget.digest(path),development_key=key([q for q in rows(folder,f'dev{ep}_') if q['policy']==role]))
            representatives={mode:min([r for r in roles if r.startswith(mode+'_')],key=lambda r:(selections[r]['development_key'],r)) for mode in MODES}
            selected=representatives['ORDER']
            write(folder/'freeze.json',dict(selected=selected,representatives=representatives,selections=selections,stages_done=stages_done,stop_reason=reason,all_seeds_reported=True,confirmation_not_read=True,registration_sha256=budget.digest(folder/'registration.json')))
        freeze=budget.read(folder/'freeze.json');frozen={}
        for role,s in freeze['selections'].items():
            bank,seed=role.split('_');path=learner_path(folder,bank,int(seed),s['episodes'])
            if budget.digest(path)!=s['sha256']:raise ValueError('frozen model changed')
            frozen[bank,int(seed)]=learning.Learner.load(path,deps(reg,bank))
        final=evaluate(folder,b,inputs['confirmation'],[*BASES,*roles],frozen,'confirmation')
        expected={(q['condition'],r) for q in inputs['confirmation'] for r in [*BASES,*roles]}
        if {(q['condition'],q['policy']) for q in final}!=expected or len(final)!=len(expected):raise ValueError('incomplete/duplicate final paired matrix')
        verdict={r:gate(final,r) for r in roles};write(folder/'verdict.json',verdict)
        cursor.update(completed=True,stage='completed',learning_accepted=sum(l.episodes for l in learners.values()));write(folder/'cursor.json',cursor)
    return dict(status='completed',freeze=freeze,consumption=b.used(),verdicts={r:v['promising'] for r,v in verdict.items()})

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','check','run'));p.add_argument('--run-root',type=Path,required=True);p.add_argument('--stop-after',type=int)
    x=p.parse_args();r=register(x.run_root) if x.command=='register' else check(x.run_root) if x.command=='check' else run(x.run_root,x.stop_after)
    print(json.dumps(serial(r),ensure_ascii=False),flush=True)
if __name__=='__main__':main()


