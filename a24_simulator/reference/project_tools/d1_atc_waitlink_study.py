"""Registered full-queue PC-only study, frozen paired references and final data."""
import argparse, copy, gzip, hashlib, json, math, os, platform, subprocess, time
from dataclasses import asdict,is_dataclass
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_atc_waitlink_policy as a
from tools import d1_atc_waitlink_ppo as learning
from tools import d1_atc_waitlink_budget as budget
from tools import d1_atc_waitlink_controls as mobile
from tools import d1_desktop_seed_registry as registry
from tools import d1_atc_waitlink_engine as engine
from tools import d1_list_candidate_rl_training as native
ROOT=Path(__file__).resolve().parents[1]
from tools import d1_atc_wait_study as parent
def serial(x):
    if isinstance(x,float) and not math.isfinite(x):return "UNAVAILABLE"
    if isinstance(x,dict):return {str(k):serial(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [serial(v) for v in x]
    if isinstance(x,np.ndarray):return serial(x.tolist())
    if isinstance(x,np.generic):return serial(x.item())
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


class Proxy:
    protocol=a.VERSION
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
    qs=case["requests"]
    vectors=realizations(qs,case["arrival_seed"])
    proxy=Proxy(agent);t=time.perf_counter();cpu=time.process_time()
    with b.environment(identity,phase,learning_episode):
        with patch.object(engine,"choose",side_effect=AssertionError("legacyenginechoose forbidden")),patch.object(a.p.Controller,"__call__",side_effect=AssertionError("legacy/EFT decision forbidden")),patch.object(oldstudy.mobile,"eft",side_effect=AssertionError("EFT forbidden")),patch.object(a.p.Controller,"rollout",side_effect=AssertionError("online queue forecast")),patch.object(a.p.Controller,"place",side_effect=AssertionError("online placement")),patch.object(a.hybrid,"costs",side_effect=AssertionError("online AP/J forecast")):
            result=engine.simulate(dict(protocol=a.VERSION,cells=a.p.profile(f)),vectors,qs,policy=agent.policy,settings=a.external.settings(),seed=REALIZATION,decision_provider=proxy)
        audit=audit_ledger(result)
        segments,costs,end=a.hybrid.account(result,initial,f)
        rows=result["ledger"];full=all(r["status"]=="succeeded" for r in rows)
        row=dict(identity=identity,phase=phase,policy=case.get("role") or getattr(agent,"public_policy",getattr(agent,"policy","unknown")),
            **{k:v for k,v in case.items() if k!="requests" and k!="role"},planned=len(qs),
            completed=sum(r["status"]=="succeeded" for r in rows),
            incomplete=sum(r["status"]!="succeeded" for r in rows),
            urgent_planned=sum(r["priority"]=="urgent" for r in rows),
            normal_planned=sum(r["priority"]=="normal" for r in rows),
            urgent_failure=sum(r["priority"]=="urgent" and ("response_ns" not in r or r.get("late_success",False)) for r in rows),
            normal_failure=sum(r["priority"]=="normal" and ("response_ns" not in r or r.get("late_success",False)) for r in rows),
            urgent_p95_ms=result["metrics"]["urgent_p95_ms"],normal_mean_ms=result["metrics"]["normal_mean_ms"],
            energy_j=costs["whole_120s_j"] if full else None,
            peak_ap_c=max(costs["ap_path"]) if full else None,
            native_seconds=time.perf_counter()-t,cpu_seconds=time.process_time()-cpu,
            callbacks=len(proxy.callbacks),controller_observation_seconds=proxy.observation_seconds,controller_event_seconds=proxy.event_seconds,
            modeled_temperature_channel="AP model-plant observation; not surface",experiment_ready=False)
        row["normal_p95_ms"]=a.native.rank95([r["response_ns"]/1e6 for r in rows if r["priority"]=="normal" and "response_ns" in r]) if any(r["priority"]=="normal" and "response_ns" in r for r in rows) else None
        row["max_wait_ms"]=max([(r["dispatch_ns"]-r["arrival_ns"])/1e6 for r in rows if "dispatch_ns" in r] or [0.])
        row["fallbacks"]=getattr(agent,"stats",{}).get("fallback",0)
        row["nonhead_decisions"]=sum(s.get("nonhead_selected",False) for s in getattr(agent,"snapshots",[]))
        row["planned_work_units"]=sum(q["work_units"] for q in qs)
        row["completed_work_units"]=sum(q["work_units"] for q in rows if q["status"]=="succeeded")
        for priority,cap in (("urgent",1.5e9),("normal",6e9)):
            row[priority+"_original_cap_failure"]=sum(q["priority"]==priority and ("response_ns" not in q or q["response_ns"]>cap) for q in rows)
        row["rank_different"]=sum(not x["raw_rank_same"] for x in agent.snapshots)
        row["bank_different"]=sum(not x["ATC_EDD_same"] for x in agent.snapshots)
        row["legal_different"]=sum(not x["ATC_EDD_legal_actions_same"] for x in agent.snapshots)
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



from tools import d1_atc_repair_study as oldstudy

SEEDS=(1013,1019,1021);ARMS=a.ARMS
FAMILIES=("idle","steady","release_015","release_035","release_050","release_058","release_065","burst2","burst4","mix4","boundary6")
FACTORS=("fixed","declared")
TRAIN=tuple(range(923110101,923110165));DEV=tuple(range(923210101,923210105))
CONFIRM=tuple(range(923410101,923410109))
REALIZATION=923000201;HINT_SEED=923000301
BASES=(*mobile.ROLES,"RuleEDD","RuleATC")
CSV=oldstudy.CSV;POOL=oldstudy.POOL

def keyed(*values):return oldstudy.keyed(*values)

def requests(family,seed,factor):
    import random
    rng=random.Random(keyed(seed,family,"arrivals"));points=[]
    if family=="idle":points=[(35+i*1.8,i%2) for i in range(24)]
    elif family=="steady":points=[(35+i*.6,i%2) for i in range(96)]
    elif family.startswith("release_"):
        offset=int(family[-3:])/100
        for i in range(18):
            begin=35+i*3
            points.extend(((begin,1),(begin+offset+rng.uniform(-.01,.01),0)))
    elif family in ("burst2","burst4","mix4","boundary6"):
        burst=2 if family=="burst2" else 6 if family=="boundary6" else 4
        cycles=18 if family in ("burst2","burst4") else 24
        period=3. if family in ("burst2","burst4") else 1.5 if family=="mix4" else 1.3
        offset=.55 if family in ("burst2","burst4") else .15
        for i in range(cycles):
            begin=35+i*period;points.append((begin,1))
            points.extend((begin+offset+j*.06+rng.uniform(-.008,.008),0) for j in range(burst))
    else:raise ValueError("unregistered family")
    points.sort(key=lambda v:(v[0],v[1]))
    qs=[dict(id=f"W10_{i:03d}",ordinal=i,task="classification" if kind==0 else "detection",priority="urgent" if kind==0 else "normal",
        arrival_ns=round(at*1e9),deadline_offset_ns=round((1.5 if kind==0 else 6)*1e9),work_units=1) for i,(at,kind) in enumerate(points)]
    if factor=="declared":
        for task in ("classification","detection"):
            group=[q for q in qs if q['task']==task]
            if len(group)%3:raise ValueError('balanced deadline triplets')
            values=([.75,1.,1.5] if task=='classification' else [3.,4.5,6.])*(len(group)//3)
            random.Random(keyed(HINT_SEED,seed,family,task,'due')).shuffle(values)
            for q,v in zip(group,values):q['deadline_offset_ns']=round(v*1e9)
    if any(not 35e9<=q['arrival_ns']<120e9 for q in qs):raise ValueError('arrival horizon')
    return qs

def cases(seeds):
    return [dict(arrival_seed=seed,family=family,factor=factor,context="new923_n1_fixedoffset_currentowner_WAIT_hypothesis",condition=i,
        primary=family!='boundary6',release_domain=family.startswith('release_'),requests=requests(family,seed,factor))
        for i,(seed,family,factor) in enumerate((seed,family,factor) for seed in seeds for family in FAMILIES for factor in FACTORS)]

def realizations(qs,arrival_seed):
    out={}
    for q in qs:
        out[q['id']]={}
        for backend in a.p.backends(q):
            donors=POOL[a.p.key(q,backend)]
            out[q['id']][backend]=[dict(source_request_id=d['source_request_id'],durations_ns=list(d['durations_ns']))
                for d in (donors[keyed(REALIZATION,arrival_seed,q['id'],backend,j)%len(donors)] for j in range(4))]
    return dict(requests=out)

def sources():
    import sys
    paths={Path(v.__file__).resolve() for k,v in sys.modules.copy().items() if k.startswith('tools.') and getattr(v,'__file__',None)}
    paths|={Path(__file__).resolve(),ROOT/'tools/test_d1_atc_wait.py',ROOT/'tools/d1_atc_waitlink_targets.py',ROOT/'tools/d1_atc_waitlink_orchestrator.py',ROOT/'tools/d1_atc_waitlink_report.py',CSV,a.hybrid.MODEL,a.p.BUNDLE/'model.json',a.p.BUNDLE/'initial_inputs.json',ROOT/'docs/results/list_candidate_rl_review_01/design_amendment_v4.json'}
    return {p.relative_to(ROOT).as_posix():budget.digest(p) for p in sorted(paths) if p.is_relative_to(ROOT)}

def register(folder):
    if folder.exists():raise FileExistsError('never reset task')
    parentroot=ROOT.parent/'ATC-WAIT-EXPAND-10';parentreg=parent.check(parentroot)
    reserved=registry.collect();new=set(CONFIRM)
    if new&set(reserved['seeds']) or any(lo<=v<=hi for v in new for lo,hi in reserved['ranges']):raise ValueError('new final seed collision')
    for path in folder.parent.glob('*/inputs.json'):
        if any(str(v) in path.read_text('utf8') for v in new):raise ValueError('local final namespace collision')
    previous=budget.read(parentroot/'inputs.json')
    inputs=dict(train=previous['train'],development=previous['development'],confirmation=cases(CONFIRM))
    bindings=[]
    for p in sorted((parentroot/'controls/rows').glob('*.json')):
        if not p.name.startswith(('teacher_train_','development_')):continue
        receipt=budget.read(p);raw=parentroot/'controls/items'/(p.stem+'.json.gz')
        if budget.digest(raw)!=receipt['raw_sha256']:raise ValueError('parent reference raw changed')
        bindings.append(dict(identity=p.stem,row_sha=budget.digest(p),raw_sha=receipt['raw_sha256']))
    if len(bindings)!=1936:raise ValueError('all parent teacher/control dev references must be complete')
    folder.mkdir(parents=True)
    reg=dict(task=budget.TASK,aggregate=budget.AGGREGATE,profiles=budget.PROFILES,head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        sources=sources(),input_sha=a.native.digest(inputs),seeds=SEEDS,arms=ARMS,state=226,action=57,padding=32,schema=a.SCHEMA,old_models={},objectives=learning.OBJECTIVES,
        counts=dict(train_cases=1408,dev_cases=88,confirm_cases=176,reused_reference_environments=1936,new_teacher_environment_count=0),
        parent=dict(path=str(parentroot),registration_sha=budget.digest(parentroot/'registration.json'),input_sha=parentreg['input_sha'],reference_bindings_sha=a.native.digest(bindings),stage512_development_observed=True,parent_confirmation_not_used=True),
        initialization='samefresh1013/1019/1021 parameters as10 for pairedcouplingablation; action+10000/shuffle+20000; no10learnedweights reused',
        coupling='KEEP_FLAG_WAIT0:hintpresent Waitgap0; DROP_FLAG_WAIT1:NNcolumn52zero Waitmaxlegalstartgap+1; DROP_FLAG_WAIT0:NNcolumn52zero Waitgap0. single/pair ATCgapbeta1, raw52/uniquelegal/fallback/tie preserved. all physical masks same',
        objective='all three identical10 URGENT_HOLD: Rdelta-absoluteurgent suffixarea/NU1.5s; E10J/AP.1C, services100x6, pairedrunningP95potentialfuture/100ms20; no newfutureinput. same separateencoder/criticzero/native loss. couplingfactor effects do not include different reward',
        data='10 train/dev reused deliberately for development, parentteacher/control raw SHAbound, do not call independent newdataset; new176final923410101..108 and all15roles beforefinalfreeze. original10 final923310xxx remains separate and cannot guide11selection',
        selection='developmentonly primary boundary6 excluded preregistered, percondition service/P95 RuleATC guard thenmeanJ/AP/P95; allactualtrained checkpoints, noCP0replacement; fullnegative/anchor/boundary andallseedreported; parentfreeze before onefinalbatch',
        final='176newcases15roles=2640, frozenmaskedargmax, no finalguidedtraining/reselection; oldstrict full/primary epsilon0 + separatelypreregistered release400ms conditionalSLO',
        operation='wholecurrentQ ATCscan boundedbank8/action29 pad32; currentphaseETA150ms/knownoverrun; no wholefuturequeue rollout/place/J/AP orprivatearrivals/durations. teacher onlypostlabels',
        physical='sameC_CPU/C_GPU/D_CPU/CG_DCmax2,actualAVAILABLE/nonpreemptive/response split/resourceWAIT only/noNPUcooling',
        baseline='EFT0,Greedy/RR/FIFO independentcontrolonly,no benchmarkarbiter oroldEFTPPOreplay',
        resources='episode/environment numericalcapsNone, 512powers2 milestones, sharedovernighttimewith10, sixseedprocesseson6core12threadhost/disk8GiB preservationreserve; timingnotphone',
        created_utc=budget.datetime.now(budget.timezone.utc).isoformat(),fit=0,device=0,APK=0,S26=0,NPU=0,experiment_ready=False,automatic_adoption=False)
    write(folder/'registration.json',reg);write(folder/'inputs.json',inputs);write(folder/'reused_reference_bindings.json',bindings)
    budget.Budget.register(folder/'controls','control',dict(parent_sha=budget.digest(folder/'registration.json'),reused_reference_count=1936))
    (folder/'controls/rows').mkdir();(folder/'controls/items').mkdir()
    import shutil
    for binding in bindings:
        for sub,suffix in (('rows','.json'),('items','.json.gz')):
            src=parentroot/'controls'/sub/(binding['identity']+suffix);dst=folder/'controls'/sub/src.name
            shutil.copy2(src,dst)
            if budget.digest(src)!=budget.digest(dst):raise ValueError('copy binding failed')
    write(folder/'controls/cursor.json',dict(completed=False))
    for seed in SEEDS:
        child=folder/f'seed{seed}';budget.Budget.register(child,'model',dict(parent_sha=budget.digest(folder/'registration.json'),seed=seed))
        write(child/'cursor.json',dict(completed=False,stage='train',learning_accepted=0))
    io=budget.read(parentroot/'io_transport_resume_receipt.json')
    write(folder/'io_transport_binding.json',dict(supplement=io['supplement'],parent_receipt_sha=budget.digest(parentroot/'io_transport_resume_receipt.json'),new_operational_failure_count=0))
    deadline=budget.read(parentroot/'orchestration.json')['deadline_unix']
    write(folder/'orchestration.json',dict(status='prepared',phase='prepared',deadline_unix=deadline,learning_episode_count_cap=None))
    return dict(registered=True,schema=a.SCHEMA,reused_reference_count=1936,new_final_seeds=CONFIRM,no_episode_count_cap=True)

def check(folder):
    reg=budget.read(folder/'registration.json')
    if reg['aggregate']!=budget.AGGREGATE or reg['profiles']!=budget.PROFILES or reg['schema']!=a.SCHEMA:raise ValueError('immutable contract')
    for path,sha in reg['sources'].items():
        if budget.digest(ROOT/path)!=sha:raise ValueError('registered source changed '+path)
    if a.native.digest(budget.read(folder/'inputs.json'))!=reg['input_sha']:raise ValueError('input changed')
    return reg

def deps(reg,arm):return dict(schema=a.SCHEMA,arm=arm,sequencing='ATC',objective=learning.OBJECTIVES[arm],sources=reg['sources'],input_sha=reg['input_sha'])
def rows(folder,prefix):return [budget.read(p)['row'] for p in sorted((folder/'rows').glob(prefix+'*.json'))]
def learner_path(child,arm,seed,ep=None):return child/'checkpoints'/f"{arm}_{seed}_{'latest' if ep is None else 'ep'+str(ep)}.pt"
def primary(rr):return [r for r in rr if r['primary']]
def key(rr):
    q=primary(rr);mean=lambda k:float(np.mean([r[k] if r[k] is not None else float('inf') for r in q]))
    return (sum(r['incomplete'] for r in q),sum(r['planned_work_units']-r['completed_work_units'] for r in q),sum(r['urgent_original_cap_failure'] for r in q),sum(r['urgent_failure'] for r in q),sum(r['normal_original_cap_failure'] for r in q),sum(r['normal_failure'] for r in q),mean('urgent_p95_ms'),mean('energy_j'),mean('peak_ap_c'))
def eligible(rr,reference):
    by={r['condition']:r for r in reference};rr=primary(rr)
    if len(rr)!=len(primary(reference)):return False
    for r in rr:
        ref=by[r['condition']]
        if r['completed']!=r['planned'] or r['completed_work_units']!=r['planned_work_units']:return False
        for k in ('incomplete','urgent_failure','urgent_original_cap_failure','normal_failure','normal_original_cap_failure','urgent_p95_ms'):
            if r[k] is None or ref[k] is None or r[k]>ref[k]:return False
    return True
def cost_key(rr):return tuple(float(np.mean([r[k] if r[k] is not None else float('inf') for r in primary(rr)])) for k in ('energy_j','peak_ap_c','urgent_p95_ms'))
def controller(role,f,initial,learners=None):
    if role in mobile.ROLES:return mobile.Controller(f,initial,role)
    if role in ('RuleEDD','RuleATC'):return a.Controller(f,initial,mode=a.RULE,sequencing=role[4:])
    arm,seed=role.rsplit('_',1);return learners[arm,int(seed)].controller(f,initial,True)

def evaluate(child,b,cases_,roles,learners,phase):
    f,init,_=a.hybrid.load()
    for case in cases_:
        for role in roles:
            identity=f"{phase}_{case['condition']:02d}_{role}";path=child/'rows'/(identity+'.json')
            if path.exists():
                if budget.digest(child/'items'/(identity+'.json.gz'))!=budget.read(path)['raw_sha256']:raise ValueError('savedraw changed')
                continue
            collect(b,child,identity,phase,dict(case,role=role),controller(role,f,init['initial'],learners))
        if case['condition']%32==0:print(json.dumps(dict(phase=phase,through_case=case['condition'],worker=child.name)),flush=True)
    return rows(child,phase+'_')

def controls(folder,phase):
    check(folder);child=folder/'controls';b=budget.Budget(child);inputs=budget.read(folder/'inputs.json')
    if phase=='confirmation' and not (folder/'freeze.json').exists():raise ValueError('parentfreeze before confirmation')
    with b.session():
        if phase=='development':evaluate(child,b,inputs['train'],['RuleATC'],{},'teacher_train')
        rr=evaluate(child,b,inputs['development' if phase=='development' else 'confirmation'],BASES,{},phase)
        write(child/'cursor.json',dict(completed=phase=='confirmation',stage=phase,rows=len(rr)))
    return dict(completed=True,phase=phase,rows=len(rr),consumption=b.used())

def initial_proof(folder,child,b,learners):
    path=child/'initial_teacher_proof.json'
    if path.exists() or child.name!=f'seed{SEEDS[0]}':return
    inputs=budget.read(folder/'inputs.json')['development'];proofs=[]
    for arm in ARMS:
        for index in (0,2,12,17):
            case=inputs[index];role=f'{arm}_{SEEDS[0]}';identity=f'initialproof_{index:02d}_{role}'
            raw=collect(b,child,identity,'initialproof',dict(case,role=role),learners[arm].controller(*_initial(),True))
            ref=json.loads(gzip.decompress((folder/'controls/items'/f'development_{index:02d}_RuleATC.json.gz').read_bytes()))
            if raw['result']['ledger']!=ref['result']['ledger'] or raw['result']['transitions']!=ref['result']['transitions']:raise ValueError('CP0 teacher mismatch')
            proofs.append(dict(arm=arm,condition=index,exact=True))
    write(path,dict(status='PASS12_native_teacher_exact',proofs=proofs,new_environments=12,learning=0))
def _initial():
    f,init,_=a.hybrid.load();return f,init['initial']
def stages(through):
    if through<512 or through&(through-1):raise ValueError('power2 checkpoint at least512')
    values=[];x=512
    while x<=through:values.append(x);x*=2
    return values

def train(folder,seed,through,stop_after=None):
    if seed not in SEEDS:raise ValueError('seed')
    if (folder/'freeze.json').exists():raise ValueError('never train after parent final freeze')
    reg=check(folder);child=folder/f'seed{seed}';b=budget.Budget(child);inputs=budget.read(folder/'inputs.json');f,init,_=a.hybrid.load();learners={}
    for arm in ARMS:
        path=learner_path(child,arm,seed)
        learners[arm]=learning.Learner.load(path,deps(reg,arm)) if path.exists() else learning.Learner(seed,deps(reg,arm))
        if not learner_path(child,arm,seed,0).exists():learners[arm].save(learner_path(child,arm,seed,0))
    accepted=0
    with b.session():
        initial_proof(folder,child,b,learners)
        for stage in stages(through):
            if (child/f'stage{stage}.json').exists():continue
            for n in range(stage):
                for arm,l in learners.items():
                    if l.episodes>n:continue
                    if l.episodes!=n:raise ValueError('learner cursor')
                    case=inputs['train'][n%len(inputs['train'])]
                    identity=f'train_{arm}_{seed}_{n:06d}'
                    if (child/'rows'/(identity+'.json')).exists():raise ValueError('unadopted rollout must be audited')
                    agent=l.controller(f,init['initial'],False)
                    raw=collect(b,child,identity,'train',dict(case,role=f'{arm}_{seed}'),agent,True)
                    refpath=folder/'controls/items'/f"teacher_train_{case['condition']:02d}_RuleATC.json.gz"
                    receipt=budget.read(folder/'controls/rows'/(refpath.name[:-8]+'.json'))
                    if budget.digest(refpath)!=receipt['raw_sha256']:raise ValueError('reference changed')
                    ref=json.loads(gzip.decompress(refpath.read_bytes()))
                    frames,costs,valid,_=learning.targets(agent,raw,init['initial']['preload_power_w']*120,arm,ref)
                    l.add(frames,costs,valid,raw['row']);l.cursor=dict(episode=l.episodes);l.consumption=b.used();l.save(learner_path(child,arm,seed))
                    accepted+=1;write(child/'cursor.json',dict(completed=False,stage='train',through=through,learning_accepted=sum(v.episodes for v in learners.values()),episodes={aa:ll.episodes for aa,ll in learners.items()}))
                    if stop_after and accepted>=stop_after:
                        for aa,ll in learners.items():ll.save(child/'paused_checkpoints'/f'{aa}_{seed}.pt')
                        write(child/'pause_receipt.json',dict(digests={aa:payload_digest(ll.snapshot()) for aa,ll in learners.items()},partial={aa:len(ll.pending) for aa,ll in learners.items()},learning_accepted=sum(v.episodes for v in learners.values())))
                        return dict(paused=True,consumption=b.used())
                if (n+1)%32==0:print(json.dumps(dict(worker=seed,episode_per_arm=n+1,through=through,accepted=accepted)),flush=True)
            for arm,l in learners.items():l.save(learner_path(child,arm,seed,stage))
            roles=[f'{arm}_{seed}' for arm in ARMS]
            rr=evaluate(child,b,inputs['development'],roles,{(arm,seed):l for arm,l in learners.items()},f'dev{stage}')
            mechanics=all(l.logs and any(x['sampled_choices']>0 for x in l.logs) and all(np.isfinite(x['actor_gradient_max']) and (x['critic_only'] or x['actor_gradient_max']>0) for x in l.logs) and all(e['row']['fallbacks']==0 for e in l.episode_logs) for l in learners.values())
            diagnostics={}
            for arm in ARMS:
                snaps=[]
                for case in inputs['development']:snaps.extend(json.loads(gzip.decompress((child/'items'/f"dev{stage}_{case['condition']:02d}_{arm}_{seed}.json.gz").read_bytes()))['snapshots'])
                diagnostics[arm]=dict(snapshots=len(snaps),choices=sum(sum(s['mask'])>1 for s in snaps),teacher_overrides=sum(s['chosen']!=s['base'] for s in snaps),resource_wait=sum(s['actions'][s['chosen']]['kind']=='resource_wait' for s in snaps),wait_with_legal_start=sum(s['actions'][s['chosen']]['kind']=='resource_wait' and any(m and ac and ac['kind']!='resource_wait' for m,ac in zip(s['mask'],s['actions'])) for s in snaps))
            ref=[r for r in rows(folder/'controls','development_') if r['policy']=='RuleATC']
            write(child/f'stage{stage}.json',dict(mechanics_pass=mechanics,keys={role:key([r for r in rr if r['policy']==role]) for role in roles},guard={role:eligible([r for r in rr if r['policy']==role],ref) for role in roles},cost_keys={role:cost_key([r for r in rr if r['policy']==role]) for role in roles},diagnostics=diagnostics))
            if not mechanics:raise ValueError('native learning failed; stop rather than fake expansion')
        write(child/'cursor.json',dict(completed=False,stage='development_completed',through=through,learning_accepted=sum(l.episodes for l in learners.values()),episodes={arm:l.episodes for arm,l in learners.items()}))
    return dict(stage_completed=through,seed=seed,consumption=b.used())

def select(folder,seed):
    reg=check(folder)
    if (folder/'freeze.json').exists():raise ValueError('cannot reselect after parent freeze')
    child=folder/f'seed{seed}';available=sorted(int(p.stem[5:]) for p in child.glob('stage*.json'))
    if not available or any(child.glob('rows/confirmation_*.json')):raise ValueError('invalid selection phase')
    teacher=[r for r in rows(folder/'controls','development_') if r['policy']=='RuleATC'];selections={}
    for arm in ARMS:
        role=f'{arm}_{seed}';candidates=[ep for ep in available if eligible([r for r in rows(child,f'dev{ep}_') if r['policy']==role],teacher)]
        def ck(ep):
            rr=[r for r in rows(child,f'dev{ep}_') if r['policy']==role];return cost_key(rr) if candidates else key(rr)
        ep=min(candidates or available,key=lambda ep:(ck(ep),ep));rr=[r for r in rows(child,f'dev{ep}_') if r['policy']==role]
        selections[role]=dict(episodes=ep,sha256=budget.digest(learner_path(child,arm,seed,ep)),development_key=key(rr),development_cost_key=cost_key(rr),development_guard_pass=bool(candidates),eligible_checkpoints=candidates,trained_candidate=True)
    write(child/'freeze.json',dict(selections=selections,registration_sha=budget.digest(folder/'registration.json'),confirmation_not_read=True))
    return dict(selected=True,seed=seed,selections=selections)

def freeze(folder):
    check(folder)
    if (folder/'freeze.json').exists() or any(folder.glob('**/rows/confirmation_*.json')):raise ValueError('final freeze once before confirmation')
    selections={}
    for seed in SEEDS:
        for role,item in budget.read(folder/f'seed{seed}/freeze.json')['selections'].items():
            arm,_=role.rsplit('_',1)
            if budget.digest(learner_path(folder/f'seed{seed}',arm,seed,item['episodes']))!=item['sha256']:raise ValueError('selected weights changed')
            selections[role]=item
    def sk(role):
        it=selections[role];ks=it['development_cost_key'] if it['development_guard_pass'] else it['development_key']
        return not it['development_guard_pass'],[float('inf') if x=='UNAVAILABLE' else x for x in ks],it['episodes'],role
    representative=min(selections,key=sk)
    write(folder/'freeze.json',dict(selected=representative,selections=selections,registration_sha=budget.digest(folder/'registration.json'),confirmation_not_read=True,all9trained=True))
    return dict(frozen=True,selected=representative,models=len(selections))

def confirm(folder,seed):
    reg=check(folder)
    if not (folder/'freeze.json').exists():raise ValueError('parent freeze required')
    child=folder/f'seed{seed}';models={};frozen=budget.read(child/'freeze.json')
    for role,it in frozen['selections'].items():
        arm,ss=role.rsplit('_',1);path=learner_path(child,arm,int(ss),it['episodes'])
        if budget.digest(path)!=it['sha256']:raise ValueError('frozen weights changed')
        models[arm,int(ss)]=learning.Learner.load(path,deps(reg,arm))
    b=budget.Budget(child)
    with b.session():
        rr=evaluate(child,b,budget.read(folder/'inputs.json')['confirmation'],list(frozen['selections']),models,'confirmation')
        write(child/'cursor.json',dict(completed=True,stage='completed',rows=len(rr)))
    return dict(completed=True,seed=seed,rows=len(rr),consumption=b.used())

def merge(folder):
    reg=check(folder);children=[folder/'controls']+[folder/f'seed{seed}' for seed in SEEDS]
    if not all(budget.read(p/'cursor.json')['completed'] for p in children):raise ValueError('workers incomplete')
    rr=[r for child in children for r in rows(child,'confirmation_')]
    n=len(budget.read(folder/'inputs.json')['confirmation']);roles=(*BASES,*(f'{arm}_{seed}' for arm in ARMS for seed in SEEDS))
    if len(rr)!=n*len(roles) or {(r['condition'],r['policy']) for r in rr}!={(i,role) for i in range(n) for role in roles}:raise ValueError('final matrix')
    used=[budget.Budget(p).used() for p in children]
    consumption=dict(environments=sum(v['environments'] for v in used),learning=sum(v['learning'] for v in used),failed=sum(v['failed'] for v in used),worker_active_seconds_sum=sum(v['active_seconds'] for v in used),caps=budget.AGGREGATE,workers=used,device=0,S26=0)
    write(folder/'consumption.json',consumption);write(folder/'final_rows.json',rr)
    write(folder/'development_selection_summary.json',dict(**budget.read(folder/'freeze.json'),automatic_adoption=False))
    return dict(completed=True,rows=len(rr),consumption=consumption)

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','check','controls','train','select','freeze','confirm','merge'))
    p.add_argument('--run-root',type=Path,required=True);p.add_argument('--seed',type=int);p.add_argument('--phase',choices=('development','confirmation'));p.add_argument('--stop-after',type=int);p.add_argument('--through',type=int,default=1024);x=p.parse_args()
    result=register(x.run_root) if x.command=='register' else check(x.run_root) if x.command=='check' else controls(x.run_root,x.phase) if x.command=='controls' else train(x.run_root,x.seed,x.through,x.stop_after) if x.command=='train' else select(x.run_root,x.seed) if x.command=='select' else freeze(x.run_root) if x.command=='freeze' else confirm(x.run_root,x.seed) if x.command=='confirm' else merge(x.run_root)
    print(json.dumps(serial(result),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
