"""Registered full-queue PC-only study, frozen paired references and final data."""
import argparse, copy, gzip, hashlib, json, math, os, platform, subprocess, time
from dataclasses import asdict,is_dataclass
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_atc_repair_policy as a
from tools import d1_atc_repair_ppo as learning
from tools import d1_atc_repair_budget as budget
from tools import d1_atc_repair_mobile as mobile
from tools import d1_desktop_seed_registry as registry
from tools import d1_atc_repair_engine as engine
from tools import d1_list_candidate_rl_training as native
ROOT=Path(__file__).resolve().parents[1]
from tools import d1_queue_hetero_policy as legacy_policy
from tools import d1_queue_hetero_ppo as legacy_learning
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
        with patch.object(a.p.Controller,"rollout",side_effect=AssertionError("online queue forecast")),patch.object(a.p.Controller,"place",side_effect=AssertionError("online placement")),patch.object(a.hybrid,"costs",side_effect=AssertionError("online AP/J forecast")):
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



SEEDS=(211,223,227);ARMS=("ANCHOR","CAUSAL")
FAMILIES=("low","queue","burst","sustained")
FACTORS=("single_fixed","single_deadlines","batch_uniform2","batch_variable")
BASES=(*mobile.ROLES,"RuleEDD","RuleATC")
TRAIN=tuple(range(886110101,886110109));DEV=(886210101,886210102)
CONFIRM=(886310101,886310102,886310103,886310104)
REALIZATION=886000201;HINT_SEED=886000301;STAGES=(64,128)
CSV=ROOT/"docs/results/overnight_device_20261011/requests.csv"
OLD=ROOT.parent/"QUEUE-HETERO-PPO-03"

def pool():
    import csv
    groups={k:[] for k in a.p.CELLS}
    for i,row in enumerate(csv.DictReader(CSV.open(encoding="utf-8-sig",newline=""))):
        if row["terminal_status"]!="succeeded":raise ValueError("missing empirical denominator")
        q=dict(task=row["task_id"],priority=row["priority"])
        points=[float(row[k])*1e6 for k in ("dispatch_ms","execution_start_ms","output_ready_ms","persist_complete_ms","worker_release_ms","lane_available_ms")]
        ds=[round(y-x) for x,y in zip(points,points[1:])]
        if any(v<0 for v in ds):raise ValueError("empirical stage inversion")
        groups[a.p.key(q,row["backend"])].append(dict(source_request_id=f"ABBA{row['index']}/row{i}",durations_ns=ds))
    if [len(groups[k]) for k in a.p.CELLS]!=[4,188,192]:raise ValueError("source evidence counts changed")
    return groups

POOL=pool()

def keyed(*values):
    return int.from_bytes(hashlib.sha256("/".join(map(str,values)).encode()).digest()[:8],"big")

def requests(family,seed,factor):
    import random
    qs=a.external.old.workload(family,seed)
    for task in ("classification","detection"):
        members=[q for q in qs if q["task"]==task]
        rng=random.Random(keyed(HINT_SEED,seed,task,"deadlines"))
        deadlines=([.5,1.,1.5] if task=="classification" else [2.,4.,6.])
        ds=(deadlines*((len(members)+2)//3))[:len(members)];rng.shuffle(ds)
        ns=([1,2,3]*((len(members)+2)//3))[:len(members)]
        random.Random(keyed(HINT_SEED,seed,task,"work_units")).shuffle(ns)
        if len(members)%3:raise ValueError("exact matched batch work-unit design requires triplets")
        for j,q in enumerate(members):
            q["deadline_offset_ns"]=round((1.5 if task=="classification" else 6.)*1e9) if factor=="single_fixed" else round(ds[j]*1e9)
            q["work_units"]=2 if factor=="batch_uniform2" else ns[j] if factor=="batch_variable" else 1
    return qs

def cases(seeds):
    return [dict(arrival_seed=seed,family=family,factor=factor,context="empirical_ABBA4_bootstrap",condition=i,requests=requests(family,seed,factor))
        for i,(seed,family,factor) in enumerate((seed,family,factor) for seed in seeds for family in FAMILIES for factor in FACTORS)]

def realizations(qs,arrival_seed):
    # Engine-only realized vectors. Buckets/counts never encode the selected residual.
    vv={}
    for q in qs:
        vv[q["id"]]={}
        for b in a.p.backends(q):
            available=POOL[a.p.key(q,b)];vectors=[]
            for j in range(4):
                source=available[keyed(REALIZATION,arrival_seed,q["id"],b,j)%len(available)]
                ds=list(source["durations_ns"]);ds[1]*=q["work_units"]
                vectors.append(dict(source_request_id=source["source_request_id"],durations_ns=ds))
            vv[q["id"]][b]=vectors
    return dict(requests=vv)


def sources():
    import sys
    paths={Path(v.__file__).resolve() for k,v in sys.modules.copy().items() if k.startswith("tools.") and getattr(v,"__file__",None)}
    paths|={Path(__file__).resolve(),ROOT/"tools/d1_atc_repair_targets.py",ROOT/"tools/test_d1_atc_repair.py",CSV,a.hybrid.MODEL,a.p.BUNDLE/"model.json",a.p.BUNDLE/"initial_inputs.json",ROOT/"docs/results/list_candidate_rl_review_01/design_amendment_v4.json"}
    return {p.relative_to(ROOT).as_posix():budget.digest(p) for p in sorted(paths) if p.is_relative_to(ROOT)}

def register(folder):
    reserved=registry.collect();new=set(TRAIN+DEV+CONFIRM+(REALIZATION,HINT_SEED))
    if new&set(reserved["seeds"]) or any(lo<=seed<=hi for seed in new for lo,hi in reserved["ranges"]):raise ValueError("seed collision")
    for path in folder.parent.glob("*/inputs.json"):
        old=budget.read(path)
        for phase in ("train","development","confirmation"):
            if any(x.get("arrival_seed") in new for x in old.get(phase,[])):raise ValueError("local sibling collision")
    oldfreeze=budget.read(OLD/"freeze.json");legacy={}
    for seed in (101,113,127):
        selection=oldfreeze["selections"][f"ATC_{seed}"];path=OLD/"checkpoints"/f"ATC_{seed}_ep{selection['episodes']}.pt"
        if budget.digest(path)!=selection["sha256"]:raise ValueError("old fixed reference changed")
        legacy[f"LEGACY_{seed}"]=dict(path=path.resolve().as_posix(),sha256=selection["sha256"],episodes=selection["episodes"],schema=legacy_policy.SCHEMA)
    inputs=dict(train=cases(TRAIN),development=cases(DEV),confirmation=cases(CONFIRM))
    assert len(inputs["train"])==128 and len(inputs["development"])==32 and len(inputs["confirmation"])==64
    budget.Budget.register(folder,dict(user_authorized="three-expert discussion and implementation/finite verification of ATC PPO repair",experiment_scope="A24 PC; old stages unchanged"))
    reg=dict(task=budget.TASK,caps=budget.CAPS,head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),schema=a.SCHEMA,state=218,action=53,padding=32,sources=sources(),input_sha=a.native.digest(inputs),settings=asdict(a.DEFAULT),arms=ARMS,seeds=SEEDS,stages=STAGES,legacy_models=legacy,
        changes="actual same-bank RuleATC flag52/fallback/tie; forward log[9*(Mlegal-1)] prior90%; public past requested/original miss4 state; fullK8/request choice/physical WAIT unchanged",objectives=learning.OBJECTIVES,
        anchor="same V3 reward/dual6 targets padded10invalid4; new teacher/state; no old actor reuse",causal="10channel post-episode future suffix only; AVAILABLE workcredit - unit unresponded holding/units/85s; E120increment/100J, APobservedprefix35..120growth/1C, Ureq/Ucap/Nreq/Ncap missonce rates, terminalIunits/Ireq, Uunrespondedseconds/NU/1.5s; fixed service weights10, no tolerance relaxation",prior="sampler and PPO logprob use same biased Categorical, initial maskedargmax exactRuleATC; not external epsilon greedy",input="observed arrived requests/phases/AP, public work_units and remaining due only; no future draws/outcomes/plans",physical="C_CPU/C_GPU/D_CPU/CG_DC max2, actualAVAILABLE/nonpreemptive/response distinct, resourceWAIT only, no cooling/NPU",deadline="old urgent1.5/normal6 unchanged caps, same requested .5/1/1.5 and2/4/6; no dropping old overloaded cases",
        primary="single_fixed+single_deadlines, final32 for supported one-image service diagnosis",stress="batch_uniform2+batch_variable final32; synthetic assumptions and intrinsic DCPU capacity impossible",selection="perarm/seed checkpoint0 teacher is eligible reference;64/128 trained candidate only if devprimary16 I, unitI, U/N orig/req andP95 percondition<=RuleATC; then lexical primaryservice/J/AP andearliesttie; no trainedcandidate ->0 andreport learnedgain0; representativechosen ondev beforefinal; not proof of final nondegradation",final="64cases*16roles=1024; all6 new+3 old frozen+7 rules; weights frozen argmax; no postfinalretune",adoption="report historical full-domain strict; both requested andoriginal cap andworkunits/P95/J/AP nonworse vsFIFO_FIXED/FIFO_EFT/RuleATC epsilon0; low/sustained absolute0; strictJorAPgain allprimary low/sustained pairedconditions, fullstress failure kept; primary-only is diagnostic not originalglobalPASS",expected=2400,model_fit=0,S26_learning=0,S26_environments=0,device_runs=0,experiment_ready=False,automatic_adoption=False,python=platform.python_version(),torch=torch.__version__,numpy=np.__version__)
    write(folder/"registration.json",reg);write(folder/"inputs.json",inputs);write(folder/"cursor.json",dict(completed=False,stage="controls"))
    return dict(status="registered",task=budget.TASK,schema=a.SCHEMA,caps=budget.CAPS,expected=2400)

def check(folder):
    reg=budget.read(folder/"registration.json")
    if reg["schema"]!=a.SCHEMA or reg["caps"]!=budget.CAPS:raise ValueError("immutable contract")
    for path,sha in reg["sources"].items():
        if budget.digest(ROOT/path)!=sha:raise ValueError("source changed "+path)
    for role,model in reg["legacy_models"].items():
        if budget.digest(model["path"])!=model["sha256"]:raise ValueError("fixed legacy model changed")
    if a.native.digest(budget.read(folder/"inputs.json"))!=reg["input_sha"]:raise ValueError("inputs changed")
    return reg

def deps(reg,arm):return dict(schema=a.SCHEMA,arm=arm,sequencing="ATC",objective=learning.OBJECTIVES[arm],sources=reg["sources"],input_sha=reg["input_sha"])
def rows(folder,prefix):return [budget.read(p)["row"] for p in sorted((folder/"rows").glob(prefix+"*.json"))]
def learner_path(folder,arm,seed,ep=None):return folder/"checkpoints"/f"{arm}_{seed}_{'latest' if ep is None else 'ep'+str(ep)}.pt"
def primary(rr):return [r for r in rr if r['factor'] in ('single_fixed','single_deadlines')]
def key(rr):
    q=primary(rr)
    return (sum(r["incomplete"] for r in q),sum(r["planned_work_units"]-r["completed_work_units"] for r in q),sum(r["urgent_original_cap_failure"] for r in q),sum(r["urgent_failure"] for r in q),sum(r["normal_original_cap_failure"] for r in q),sum(r["normal_failure"] for r in q),np.mean([r["urgent_p95_ms"] if r["urgent_p95_ms"] is not None else float("inf") for r in q]),np.mean([r["energy_j"] if r["energy_j"] is not None else float("inf") for r in q]),np.mean([r["peak_ap_c"] if r["peak_ap_c"] is not None else float("inf") for r in q]))
def eligible(q,reference):
    by={r['condition']:r for r in primary(reference)}
    for r in primary(q):
        b=by[r['condition']]
        fields=('incomplete','urgent_original_cap_failure','urgent_failure','normal_original_cap_failure','normal_failure','urgent_p95_ms')
        if r['planned']!=r['completed'] or r['planned_work_units']!=r['completed_work_units'] or any(r[k] is None or r[k]>b[k] for k in fields):return False
    return True

def controller(role,f,initial,learners=None,legacy=None):
    if role in mobile.ROLES:return mobile.Controller(f,initial,role)
    if role in ('RuleEDD','RuleATC'):return a.Controller(f,initial,mode=a.RULE,sequencing=role[4:])
    if role.startswith('LEGACY_'):return legacy_policy.Controller(f,initial,legacy[role],True,sequencing='ATC')
    arm,seed=role.split('_');return learners[arm,int(seed)].controller(f,initial,True)

def evaluate(folder,b,cases_,roles,learners,stage,legacy=None):
    f,i,_=a.hybrid.load()
    for case in cases_:
        for role in roles:
            identity=f"{stage}_{case['condition']:02d}_{role}";path=folder/'rows'/(identity+'.json')
            if path.exists():
                receipt=budget.read(path)
                if budget.digest(folder/'items'/(identity+'.json.gz'))!=receipt['raw_sha256']:raise ValueError('saved raw changed')
                continue
            collect(b,folder,identity,stage,dict(case,role=role),controller(role,f,i['initial'],learners,legacy))
    return rows(folder,stage+'_')

def verdict(rr,role,scope):
    cases=sorted({r['condition'] for r in rr if scope=='full' or r['factor'] in ('single_fixed','single_deadlines')});by={(r['condition'],r['policy']):r for r in rr};maintained=True;deltas=[]
    for case in cases:
        q=by[case,role]
        for ref in ('FIFO_FIXED','FIFO_EFT','RuleATC'):
            b=by[case,ref];d={k:q[k]-b[k] if q[k] is not None and b[k] is not None else None for k in ('incomplete','urgent_failure','urgent_original_cap_failure','normal_failure','normal_original_cap_failure','urgent_p95_ms','energy_j','peak_ap_c')}
            d['unfinished_units']=(q['planned_work_units']-q['completed_work_units'])-(b['planned_work_units']-b['completed_work_units'])
            absolute=q['family'] not in ('low','sustained') or q['incomplete']==q['urgent_failure']==q['normal_failure']==q['urgent_original_cap_failure']==q['normal_original_cap_failure']==0
            passed=absolute and q['completed']==q['planned']==b['planned']==b['completed'] and all(v is not None and v<=0 for v in d.values())
            maintained &= passed;deltas.append(dict(condition=case,factor=q['factor'],family=q['family'],reference=ref,passed=passed,delta=d))
    gains=[]
    for family in ('low','sustained'):
        dd=[r for r in deltas if r['family']==family and r['reference'] in ('FIFO_FIXED','FIFO_EFT')]
        if maintained and dd and all(r['delta']['energy_j']<0 or r['delta']['peak_ap_c']<0 for r in dd):gains.append(family)
    return dict(scope=scope,promising=maintained and bool(gains),maintenance_pass=maintained,gain_families=gains,differences=deltas,epsilon=0,automatic_adoption=False,primary_only_not_original_global_pass=scope!='full')

def run(folder,stop_after=None):
    reg=check(folder);b=budget.Budget(folder);inputs=budget.read(folder/'inputs.json');cursor=budget.read(folder/'cursor.json')
    if cursor['completed']:return dict(status='already_completed',consumption=b.used())
    f,i,_=a.hybrid.load();initial=i['initial'];accepted=0;roles=[f'{arm}_{seed}' for arm in ARMS for seed in SEEDS]
    with b.session():
        controls=evaluate(folder,b,inputs['development'],BASES,{},'controls')
        teacher=[r for r in controls if r['policy']=='RuleATC'];learners={}
        for arm in ARMS:
            for seed in SEEDS:
                path=learner_path(folder,arm,seed)
                l=learning.Learner.load(path,deps(reg,arm)) if path.exists() else learning.Learner(seed,deps(reg,arm));learners[arm,seed]=l
                if not learner_path(folder,arm,seed,0).exists():l.save(learner_path(folder,arm,seed,0))
        if not (folder/'initial_teacher_proof.json').exists():
            proofs=[]
            for index in (0,1,2,15):
                case=inputs['development'][index];role=f'ANCHOR_{SEEDS[0]}'
                identity=f'initialproof_{index:02d}_{role}'
                path=folder/'items'/(identity+'.json.gz')
                raw=json.loads(gzip.decompress(path.read_bytes())) if path.exists() else collect(b,folder,identity,'initialproof',dict(case,role=role),learners['ANCHOR',SEEDS[0]].controller(f,initial,True))
                reference=json.loads(gzip.decompress((folder/'items'/f"controls_{index:02d}_RuleATC.json.gz").read_bytes()))
                if raw['result']['ledger']!=reference['result']['ledger'] or raw['result']['transitions']!=reference['result']['transitions']:
                    raise ValueError('initial greedy teacher trace mismatch')
                proofs.append(dict(condition=index,factor=case['factor'],family=case['family'],ledger_and_transitions_exact=True))
            write(folder/'initial_teacher_proof.json',dict(status='PASS_initial_softanchor_greedy_exactRuleATC',native_environments=4,learning=0,proofs=proofs,all_seeds_initial_actor_lastzero=True))
        for stage in STAGES:
            if (folder/f'stage{stage}.json').exists():continue
            for n in range(stage):
                for arm in ARMS:
                    for seed in SEEDS:
                        l=learners[arm,seed]
                        if l.episodes>n:continue
                        if l.episodes!=n:raise ValueError('learner cursor')
                        identity=f'train_{arm}_{seed}_{n:03d}'
                        if (folder/'rows'/(identity+'.json')).exists():raise ValueError('unadopted episode requires audit')
                        agent=l.controller(f,initial,False);raw=collect(b,folder,identity,'train',dict(inputs['train'][n],role=f'{arm}_{seed}'),agent,True)
                        frames,costs,valid,_=learning.targets(agent,raw,initial['preload_power_w']*120,arm)
                        l.add(frames,costs,valid,raw['row']);l.cursor=dict(episode=l.episodes);l.consumption=b.used();l.save(learner_path(folder,arm,seed))
                        write(folder/'cursor.json',dict(completed=False,stage='train',learning_accepted=sum(ll.episodes for ll in learners.values())));accepted+=1
                        if stop_after and accepted>=stop_after:
                            for (aa,ss),ll in learners.items():ll.save(folder/'paused_checkpoints'/f'{aa}_{ss}.pt')
                            write(folder/'pause_receipt.json',dict(digests={f'{aa}_{ss}':payload_digest(ll.snapshot()) for (aa,ss),ll in learners.items()},partial={f'{aa}_{ss}':len(ll.pending) for (aa,ss),ll in learners.items()},learning_accepted=sum(ll.episodes for ll in learners.values())))
                            return dict(status='paused',consumption=b.used())
            for (arm,seed),l in learners.items():l.save(learner_path(folder,arm,seed,stage))
            dev=evaluate(folder,b,inputs['development'],roles,learners,f'dev{stage}')
            mechanics=all(l.logs and all(np.isfinite(x['actor_gradient_max']) and x['actor_gradient_max']>0 and x['actor_changed'] for x in l.logs) and all(e['row']['fallbacks']==0 for e in l.episode_logs) for l in learners.values())
            write(folder/f'stage{stage}.json',dict(mechanics_pass=mechanics,eligible={r:eligible([q for q in dev if q['policy']==r],teacher) for r in roles},keys={r:key([q for q in dev if q['policy']==r]) for r in roles}))
            if not mechanics:raise ValueError('mechanics failure; no automatic expansion')
        if not (folder/'freeze.json').exists():
            if any((folder/'rows').glob('confirmation_*.json')):raise ValueError('selection cannot follow confirmation')
            selections={}
            for role in roles:
                arm,seed=role.split('_');candidates=[0]+[ep for ep in STAGES if eligible([q for q in rows(folder,f'dev{ep}_') if q['policy']==role],teacher)]
                def objective(ep):return key(teacher if ep==0 else [q for q in rows(folder,f'dev{ep}_') if q['policy']==role])
                ep=min(candidates,key=lambda e:(objective(e),e));path=learner_path(folder,arm,int(seed),ep)
                selections[role]=dict(episodes=ep,sha256=budget.digest(path),development_key=objective(ep),eligible_checkpoints=candidates,learned_gain_demonstrated=ep>0)
            selected=min(roles,key=lambda r:(selections[r]['development_key'],selections[r]['episodes'],r))
            write(folder/'freeze.json',dict(selected=selected,selections=selections,registration_sha256=budget.digest(folder/'registration.json'),confirmation_not_read=True,checkpoint0='exactRuleATC policy by actualteacher/prior proof; devreferencecontrols reused, no learninggainclaim'))
        freeze=budget.read(folder/'freeze.json');final={}
        for role,selection in freeze['selections'].items():
            arm,seed=role.split('_');path=learner_path(folder,arm,int(seed),selection['episodes'])
            if budget.digest(path)!=selection['sha256']:raise ValueError('frozen weights changed')
            final[arm,int(seed)]=learning.Learner.load(path,deps(reg,arm))
        legacy={}
        for role,meta in reg['legacy_models'].items():
            d=torch.load(meta['path'],map_location='cpu',weights_only=False);net=legacy_learning.ActorCritic();net.load_state_dict(d['network']);net.eval();legacy[role]=net
        rr=evaluate(folder,b,inputs['confirmation'],(*BASES,*reg['legacy_models'],*roles),final,'confirmation',legacy)
        expected={(case['condition'],role) for case in inputs['confirmation'] for role in (*BASES,*reg['legacy_models'],*roles)}
        if len(rr)!=len(expected) or {(r['condition'],r['policy']) for r in rr}!=expected:raise ValueError('final matrix')
        write(folder/'verdict.json',{r:dict(full=verdict(rr,r,'full'),primary=verdict(rr,r,'primary')) for r in roles})
        write(folder/'cursor.json',dict(completed=True,stage='completed',rows=len(rr),selected=freeze['selected']))
    return dict(status='completed',selected=freeze['selected'],consumption=b.used())

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','check','run'));p.add_argument('--run-root',type=Path,required=True);p.add_argument('--stop-after',type=int);x=p.parse_args()
    r=register(x.run_root) if x.command=='register' else check(x.run_root) if x.command=='check' else run(x.run_root,x.stop_after)
    print(json.dumps(serial(r),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
