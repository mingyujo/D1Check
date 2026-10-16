"""Registered full-queue PC-only study, frozen paired references and final data."""
import argparse, copy, gzip, hashlib, json, math, os, platform, subprocess, time
from dataclasses import asdict,is_dataclass
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_atc_coupling_policy as a
from tools import d1_atc_coupling_ppo as learning
from tools import d1_atc_coupling_budget as budget
from tools import d1_atc_coupling_controls as mobile
from tools import d1_desktop_seed_registry as registry
from tools import d1_atc_coupling_engine as engine
from tools import d1_list_candidate_rl_training as native
ROOT=Path(__file__).resolve().parents[1]
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

SEEDS=(601,607,613);ARMS=a.ARMS;STAGES=(64,128,256)
FAMILIES=("low","variable","paired","sustained")
FACTORS=("single_fixed","single_due","uniform2","variable123")
TRAIN=tuple(range(888110101,888110117));DEV=(888210101,888210102)
CONFIRM=(888310101,888310102,888310103,888310104)
REALIZATION=888000201;HINT_SEED=888000301
BASES=(*mobile.ROLES,"RuleEDD","RuleATC")
CSV=oldstudy.CSV;POOL=oldstudy.POOL

def keyed(*values):return oldstudy.keyed(*values)

def requests(family,seed,factor):
    import random
    rng=random.Random(keyed(seed,family,"arrivals"));points=[]
    if family=="low":points=[(35+i*1.8,i%2) for i in range(24)]
    elif family=="variable":
        now=35.
        for i in range(48):points.append((now,i%2));now+=rng.uniform(.65,1.05)
    elif family=="paired":
        for i in range(24):
            kinds=(0,1) if i%2==0 else (1,0)
            points.extend((35+i*2.6,kind) for kind in kinds)
    elif family=="sustained":points=[(35+i*.85,i%2) for i in range(96)]
    else:raise ValueError("unregistered family")
    qs=[dict(id=f"C08_{i:03d}",ordinal=i,task="classification" if kind==0 else "detection",priority="urgent" if kind==0 else "normal",
             arrival_ns=round(at*1e9),deadline_offset_ns=round((1.5 if kind==0 else 6)*1e9),work_units=1) for i,(at,kind) in enumerate(points)]
    for task in ("classification","detection"):
        members=[q for q in qs if q["task"]==task]
        if len(members)%3:raise ValueError("exact units require triplets")
        units=[1,2,3]*(len(members)//3)
        random.Random(keyed(HINT_SEED,seed,family,task,"units")).shuffle(units)
        deltas=([.75,1.,1.5] if task=="classification" else [3.,4.5,6.])*(len(members)//3)
        random.Random(keyed(HINT_SEED,seed,family,task,"due")).shuffle(deltas)
        for i,q in enumerate(members):
            if factor!="single_fixed":q["deadline_offset_ns"]=round(deltas[i]*1e9)
            q["work_units"]=2 if factor=="uniform2" else units[i] if factor=="variable123" else 1
    return qs

def cases(seeds):
    return [dict(arrival_seed=seed,family=family,factor=factor,context="new888_ABBA_empirical_n1_and_synthetic_batch",condition=i,requests=requests(family,seed,factor))
            for i,(seed,family,factor) in enumerate((seed,family,factor) for seed in seeds for family in FAMILIES for factor in FACTORS)]

def realizations(qs,arrival_seed):
    out={}
    for q in qs:
        out[q["id"]]={}
        for backend in a.p.backends(q):
            donors=POOL[a.p.key(q,backend)];vv=[]
            for j in range(4):
                donor=donors[keyed(REALIZATION,arrival_seed,q["id"],backend,j)%len(donors)]
                ds=list(donor["durations_ns"]);ds[1]*=q["work_units"]
                vv.append(dict(source_request_id=donor["source_request_id"],durations_ns=ds))
            out[q["id"]][backend]=vv
    return dict(requests=out)

def sources():
    import sys
    paths={Path(v.__file__).resolve() for k,v in sys.modules.copy().items() if k.startswith("tools.") and getattr(v,"__file__",None)}
    paths|={Path(__file__).resolve(),ROOT/"tools/test_d1_atc_coupling.py",ROOT/"tools/d1_atc_repair_targets.py",CSV,a.hybrid.MODEL,a.p.BUNDLE/"model.json",a.p.BUNDLE/"initial_inputs.json",ROOT/"docs/results/list_candidate_rl_review_01/design_amendment_v4.json"}
    return {p.relative_to(ROOT).as_posix():budget.digest(p) for p in sorted(paths) if p.is_relative_to(ROOT)}

def register(folder):
    if folder.exists():raise FileExistsError("never reset task")
    reserved=registry.collect();new=set(TRAIN+DEV+CONFIRM+(REALIZATION,HINT_SEED))
    if new&set(reserved["seeds"]) or any(lo<=seed<=hi for seed in new for lo,hi in reserved["ranges"]):raise ValueError("seed collision")
    for path in folder.parent.glob("*/inputs.json"):
        if any(str(v) in path.read_text("utf8") for v in new):raise ValueError("local namespace collision")
    oldstudy.check(ROOT.parent/"ATC-RESIDUAL-REPAIR-05")
    oldmodels={}  # old callbacks may include EFT; history kept, no replay in08
    inputs=dict(train=cases(TRAIN),development=cases(DEV),confirmation=cases(CONFIRM))
    assert [len(inputs[k]) for k in inputs]==[256,32,64]
    folder.mkdir(parents=True)
    reg=dict(task=budget.TASK,aggregate=budget.AGGREGATE,profiles=budget.PROFILES,head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),sources=sources(),input_sha=a.native.digest(inputs),old_models=oldmodels,
        arms=ARMS,seeds=SEEDS,stages=STAGES,schema=a.SCHEMA,state=218,action=57,padding=32,priors=a.PRIORS,
        expected=dict(train=3840,development=1440,control_development=192,confirmation=1344,initialproof=20,total=6836),
        coupling="physicalmask separately saved; effectiveintersection for sampling/logprob; actualATC teacher canonicalCPUfirst frozen beforeenvelope; Greedycomparisononly; route prior0; score-residual beta1, logscoregap currentonly; duplicatescollapsed; stagecost same acrossfivearms",
        initialization="pairedsame601/607/613 fresh weights acrossarms, not sharedlearnedweights; environmentkeyed888000201; permodelactionseed+10000/shuffle+20000 independentfromenvironment",
        objective="sameCAUSAL10future suffix from05: AVAILABLEunit-credit - unrespondedunitseconds/units/85; E120increment100J/AP120growth1C; orig/requestU/N rates10, Iunit/Irequest10, urgentholding1/1.5s; no rewardretune within experiment",
        zero_information="dedupforcedsteps retained; anallforcedeight-episodebatch performscritic-only withactor/candidategradNone,sharedstateencoderstillupdates; actor/critic-only countsreported separately",
        selection="perarm/seed minimumlex devprimary singlefixed+single_due incomplete/units/Ucap/Ureq/Ncap/Nreq/P95 thenJ/AP, tieearliercheckpoint; choose TRAINED64/128/256 only for experiment, allservicefailures retained; CP0 separateRule reference andsafe deploymentfallback, not hiddenlearnedgain",
        pilot="actual59pausefirstmodelworker5partial/RNG/Adam snapshots saved; stage64 actualnativefinitegradient/source/physicalmechanics mustpass; critic-only notactorfailure; nonzeroactorchoice required atleastonce permodel beforeexpansion",
        final="no final env untilall3 seedworkersfreeze ondev;64*21roles=1344; inferargmaxonly, allweights/source/input frozen; no postfinaltraining/reselection",
        data="new888 workload and requested due(.75/1/1.5;3/4.5/6), originalcapsU1.5/N6 retained; different from05 .5/1/1.5;2/4/6 so no olddeclaredSLAfixed or oldoverloadsolved claim; n2/n123synthetic executionblock scaling notactualmobilebatchsupport",
        workload="balanced C/D, low24gap1.8/variable48gap.65..1.05/paired48group2.6CfirstDfirstbalanced/sustained96gap.85;D48 n2minimum57.86<85 doesnotguarantee due orcomplete",
        adoption="08strict reference amendment after userEFTban: FIFO_FIXED/RR_READY/GREEDY_RESOURCE_FIFO/RuleATC; retained completion/request+originaldue/units/P95/J/AP epsilon0 percondition, readyFIFO/EDD pairlosses; historicalclosedstrictFAIL preserved, no claimidentical oldreferencecontract; supportedn1/full separated; noautomaticadoption",
        physical="sameC_CPU/C_GPU/D_CPU/CG_DCmax2,actualAVAILABLE,response distinct,nonpreemptive/resourceWAITonly,noNPU/cooling/preemption",
        EFT="userban: no EFT comparison/dispatch/arbiter/oldmodelreplay; legacycallback/EFT/queueforecast trapped; ATC route canonicalCPU-first and p representative fixedCPUreference, no dynamic minimumfinish; Greedybenchmark never called from proposal",
        operation="arrival/AVAILABLE/timer rerank unstarted,event-basedonline,noformalrollinghorizon; weightsfixed, futurequeue rollout/place/J/AP forecasts runtime trapped",
        parallel="three seedworkers eachcap2300env1280learn +controlworker600env0=7500/3840, disjointidentities/clock/ledger; active3600/model and1200/control savingreserves; sharedPC timings notphoneenergy",
        fit=0,S26=0,device=0,APK=0,experiment_ready=False,automatic_adoption=False,python=platform.python_version(),torch=torch.__version__,numpy=np.__version__)
    write(folder/"registration.json",reg);write(folder/"inputs.json",inputs)
    budget.Budget.register(folder/"controls","control",dict(parent_sha=budget.digest(folder/"registration.json"),expected=576))
    write(folder/"controls/cursor.json",dict(completed=False))
    for seed in SEEDS:
        child=folder/f"seed{seed}"
        budget.Budget.register(child,"model",dict(parent_sha=budget.digest(folder/"registration.json"),seed=seed,expected=2100 if seed==SEEDS[0] else 2080))
        write(child/"cursor.json",dict(completed=False,stage="train"))
    return dict(registered=True,expected6836=True,caps=budget.AGGREGATE,schema=a.SCHEMA)

def check(folder):
    reg=budget.read(folder/"registration.json")
    if reg["aggregate"]!=budget.AGGREGATE or reg["profiles"]!=budget.PROFILES or reg["schema"]!=a.SCHEMA:raise ValueError("immutabletaskcontract")
    for path,sha in reg["sources"].items():
        if budget.digest(ROOT/path)!=sha:raise ValueError("fixedsource changed "+path)
    for model in reg["old_models"].values():
        if budget.digest(model["path"])!=model["sha256"]:raise ValueError("fixedreferenceweight")
    if a.native.digest(budget.read(folder/"inputs.json"))!=reg["input_sha"]:raise ValueError("fixedinputs")
    return reg

def deps(reg,arm):return dict(schema=a.SCHEMA,arm=arm,sequencing="ATC",objective=learning.OBJECTIVES[arm],sources=reg["sources"],input_sha=reg["input_sha"])
def rows(folder,prefix):return [budget.read(p)["row"] for p in sorted((folder/"rows").glob(prefix+"*.json"))]
def learner_path(child,arm,seed,ep=None):return child/"checkpoints"/f"{arm}_{seed}_{'latest' if ep is None else 'ep'+str(ep)}.pt"
def primary(rr):return [r for r in rr if r["factor"] in ("single_fixed","single_due")]
def key(rr):
    q=primary(rr)
    mean=lambda k:float(np.mean([r[k] if r[k] is not None else float("inf") for r in q]))
    return (sum(r["incomplete"] for r in q),sum(r["planned_work_units"]-r["completed_work_units"] for r in q),sum(r["urgent_original_cap_failure"] for r in q),sum(r["urgent_failure"] for r in q),sum(r["normal_original_cap_failure"] for r in q),sum(r["normal_failure"] for r in q),mean("urgent_p95_ms"),mean("energy_j"),mean("peak_ap_c"))

def controller(role,f,initial,learners=None,legacy=None):
    if role in mobile.ROLES:return mobile.Controller(f,initial,role)
    if role in ("RuleEDD","RuleATC"):return a.Controller(f,initial,mode=a.RULE,sequencing=role[4:])
    arm,seed=role.rsplit("_",1);return learners[arm,int(seed)].controller(f,initial,True)


def evaluate(child,b,cases_,roles,learners,phase,legacy=None):
    f,init,_=a.hybrid.load()
    for case in cases_:
        for role in roles:
            identity=f"{phase}_{case['condition']:02d}_{role}";path=child/"rows"/(identity+".json")
            if path.exists():
                if budget.digest(child/"items"/(identity+".json.gz"))!=budget.read(path)["raw_sha256"]:raise ValueError("savedraw changed")
                continue
            collect(b,child,identity,phase,dict(case,role=role),controller(role,f,init["initial"],learners,legacy))
    return rows(child,phase+"_")

def controls(folder,phase):
    reg=check(folder);child=folder/"controls";b=budget.Budget(child);inputs=budget.read(folder/"inputs.json")
    if phase=="confirmation":
        if not (folder/"freeze.json").exists():raise ValueError("parentdevelopmentfreeze mustprecedefinal")
        for seed in SEEDS:
            if not (folder/f"seed{seed}/freeze.json").exists():raise ValueError("allmodelselections mustprecedefinal")
    with b.session():
        rr=evaluate(child,b,inputs["development" if phase=="development" else "confirmation"],BASES,{},phase)
        write(child/"cursor.json",dict(completed=phase=="confirmation",stage=phase,rows=len(rr)))
    return dict(completed=True,phase=phase,rows=len(rr),consumption=b.used())

def initial_proof(folder,child,b,learners):
    path=child/"initial_teacher_proof.json"
    if path.exists():return
    if child.name!=f"seed{SEEDS[0]}":return
    f,init,_=a.hybrid.load();inputs=budget.read(folder/"inputs.json")["development"];proofs=[]
    for arm in ARMS:
        for index in (0,1,10,15):
            case=inputs[index];role=f"{arm}_{SEEDS[0]}";identity=f"initialproof_{index:02d}_{role}"
            raw=collect(b,child,identity,"initialproof",dict(case,role=role),learners[arm].controller(f,init["initial"],True))
            refpath=folder/"controls/items"/f"development_{index:02d}_RuleATC.json.gz"
            if not refpath.exists():raise ValueError("controlreference must finishbeforeproof")
            reference=json.loads(gzip.decompress(refpath.read_bytes()))
            if raw["result"]["ledger"]!=reference["result"]["ledger"] or raw["result"]["transitions"]!=reference["result"]["transitions"]:raise ValueError("initialteacher trace mismatch")
            proofs.append(dict(arm=arm,condition=index,ledger_and_transitions_exact=True))
    write(path,dict(status="PASS20_native_CP0_exactRuleATC",proofs=proofs,new_environments=20,learning=0))

def train(folder,seed,stop_after=None):
    if seed not in SEEDS:raise ValueError("unregistered seed")
    reg=check(folder);child=folder/f"seed{seed}";b=budget.Budget(child);inputs=budget.read(folder/"inputs.json")
    if (child/"freeze.json").exists():return dict(alreadyfrozen=True,consumption=b.used())
    f,init,_=a.hybrid.load();learners={}
    for arm in ARMS:
        path=learner_path(child,arm,seed)
        l=learning.Learner.load(path,deps(reg,arm)) if path.exists() else learning.Learner(seed,deps(reg,arm));learners[arm]=l
        if not learner_path(child,arm,seed,0).exists():l.save(learner_path(child,arm,seed,0))
    accepted=0
    with b.session():
        initial_proof(folder,child,b,learners)
        for stage in STAGES:
            if (child/f"stage{stage}.json").exists():continue
            for n in range(stage):
                for arm,l in learners.items():
                    if l.episodes>n:continue
                    if l.episodes!=n:raise ValueError("learnercursor")
                    identity=f"train_{arm}_{seed}_{n:03d}"
                    if (child/"rows"/(identity+".json")).exists():raise ValueError("unadoptedrollout needsaudit")
                    agent=l.controller(f,init["initial"],False)
                    raw=collect(b,child,identity,"train",dict(inputs["train"][n],role=f"{arm}_{seed}"),agent,True)
                    frames,costs,valid,_=learning.targets(agent,raw,init["initial"]["preload_power_w"]*120,arm)
                    l.add(frames,costs,valid,raw["row"]);l.cursor=dict(episode=l.episodes);l.consumption=b.used();l.save(learner_path(child,arm,seed))
                    accepted+=1;write(child/"cursor.json",dict(completed=False,stage="train",learning_accepted=sum(v.episodes for v in learners.values())))
                    if stop_after and accepted>=stop_after:
                        for aa,ll in learners.items():ll.save(child/"paused_checkpoints"/f"{aa}_{seed}.pt")
                        write(child/"pause_receipt.json",dict(digests={aa:payload_digest(l.snapshot()) for aa,l in learners.items()},partial={aa:len(l.pending) for aa,l in learners.items()},learning_accepted=sum(v.episodes for v in learners.values())))
                        return dict(paused=True,consumption=b.used())
            for arm,l in learners.items():l.save(learner_path(child,arm,seed,stage))
            roles=[f"{arm}_{seed}" for arm in ARMS]
            rr=evaluate(child,b,inputs["development"],roles,{(arm,seed):l for arm,l in learners.items()},f"dev{stage}")
            mechanics=all(l.logs and any(x["sampled_choices"]>0 for x in l.logs) and all(np.isfinite(x["actor_gradient_max"]) and (x["critic_only"] or (x["actor_gradient_max"]>0 and x["actor_changed"])) for x in l.logs) and all(e["row"]["fallbacks"]==0 for e in l.episode_logs) for l in learners.values())
            diagnostics={}
            for arm in ARMS:
                snapshots=[]
                for case in inputs["development"]:
                    snapshots.extend(json.loads(gzip.decompress((child/"items"/f"dev{stage}_{case['condition']:02d}_{arm}_{seed}.json.gz").read_bytes()))["snapshots"])
                diagnostics[arm]=dict(snapshots=len(snapshots),multiple_selection=sum(sum(s["mask"])>1 for s in snapshots),multiple_physical=sum(sum(s["physical_mask"])>1 for s in snapshots),teacher_overrides=sum(s["chosen"]!=s["base"] for s in snapshots),critic_only_updates=sum(x["critic_only"] for x in learners[arm].logs),actor_updates=sum(not x["critic_only"] for x in learners[arm].logs))
            write(child/f"stage{stage}.json",dict(mechanics_pass=mechanics,keys={role:key([r for r in rr if r["policy"]==role]) for role in roles},diagnostics=diagnostics))
            if not mechanics:raise ValueError("nativelearning mechanicsfailure; no automaticexpansion")
        if any((child/"rows").glob("confirmation_*.json")):raise ValueError("selectioncannotfollowfinal")
        selections={}
        for arm in ARMS:
            role=f"{arm}_{seed}"
            ep=min(STAGES,key=lambda ep:(key([r for r in rows(child,f"dev{ep}_") if r["policy"]==role]),ep))
            path=learner_path(child,arm,seed,ep)
            selections[role]=dict(episodes=ep,sha256=budget.digest(path),development_key=key([r for r in rows(child,f"dev{ep}_") if r["policy"]==role]),trained_candidate=True,adoption_pending=True)
        write(child/"freeze.json",dict(selections=selections,registration_sha=budget.digest(folder/"registration.json"),confirmation_not_read=True,CP0_not_hidden_as_learning=True))
        write(child/"cursor.json",dict(completed=False,stage="frozen",learning_accepted=1280))
    return dict(frozen=True,seed=seed,selections=selections,consumption=b.used())

def confirm(folder,seed):
    reg=check(folder)
    if not (folder/"freeze.json").exists():raise ValueError("parentdevelopmentfreeze mustprecedefinal")
    for ss in SEEDS:
        if not (folder/f"seed{ss}/freeze.json").exists():raise ValueError("allworkers mustfreeze beforefinal")
    child=folder/f"seed{seed}";b=budget.Budget(child);frozen=budget.read(child/"freeze.json");models={}
    for role,meta in frozen["selections"].items():
        arm,ss=role.rsplit("_",1);path=learner_path(child,arm,int(ss),meta["episodes"])
        if budget.digest(path)!=meta["sha256"]:raise ValueError("frozenweightchanged")
        models[arm,int(ss)]=learning.Learner.load(path,deps(reg,arm))
    with b.session():
        rr=evaluate(child,b,budget.read(folder/"inputs.json")["confirmation"],list(frozen["selections"]),models,"confirmation")
        write(child/"cursor.json",dict(completed=True,stage="completed",rows=len(rr)))
    return dict(completed=True,seed=seed,rows=len(rr),consumption=b.used())

def merge(folder):
    reg=check(folder);children=[folder/"controls"]+[folder/f"seed{s}" for s in SEEDS]
    if not all(budget.read(p/"cursor.json")["completed"] for p in children):raise ValueError("incompleteworker")
    rr=[r for child in children for r in rows(child,"confirmation_")]
    roles=(*BASES,*(f"{arm}_{seed}" for arm in ARMS for seed in SEEDS))
    expected={(i,role) for i in range(64) for role in roles}
    if len(rr)!=1344 or {(r["condition"],r["policy"]) for r in rr}!=expected:raise ValueError("finalmatrix")
    used=[budget.Budget(p).used() for p in children]
    consumption=dict(environments=sum(v["environments"] for v in used),learning=sum(v["learning"] for v in used),failed=sum(v["failed"] for v in used),worker_active_seconds_sum=sum(v["active_seconds"] for v in used),caps=budget.AGGREGATE,workers=used,device=0,S26=0)
    if consumption["environments"]>7500 or consumption["learning"]>3840:raise ValueError("aggregatecap")
    write(folder/"consumption.json",consumption);write(folder/"final_rows.json",rr)
    selections={r:m for seed in SEEDS for r,m in budget.read(folder/f"seed{seed}/freeze.json")["selections"].items()}
    frozen=budget.read(folder/"freeze.json")
    if selections!=frozen["selections"]:raise ValueError("childselections changedafterparentfreeze")
    representative=frozen["selected"]
    write(folder/"development_selection_summary.json",dict(selected=representative,selections=selections,criterion="development-only, no finalmetric",automatic_adoption=False))
    return dict(completed=True,rows=1344,selected=representative,consumption=consumption)

def freeze(folder):
    check(folder)
    if (folder/"freeze.json").exists():raise FileExistsError("parentalreadyfrozen")
    if any(folder.glob("**/rows/confirmation_*.json")):raise ValueError("freezecannotfollowconfirmation")
    selections={}
    for seed in SEEDS:
        child=folder/f"seed{seed}";meta=budget.read(child/"freeze.json")
        for role,item in meta["selections"].items():
            arm,_=role.rsplit("_",1)
            if budget.digest(learner_path(child,arm,seed,item["episodes"]))!=item["sha256"]:raise ValueError("selectedweightchanged")
            selections[role]=item
    def selection_key(role):
        item=selections[role]
        numbers=[float("inf") if v=="UNAVAILABLE" else v for v in item["development_key"]]
        return numbers,item["episodes"],role
    representative=min(selections,key=selection_key)
    write(folder/"freeze.json",dict(selected=representative,selections=selections,registration_sha=budget.digest(folder/"registration.json"),confirmation_not_read=True,all15trained=True))
    return dict(frozen=True,selected=representative,models=len(selections))

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=("register","check","controls","train","freeze","confirm","merge"));p.add_argument("--run-root",type=Path,required=True);p.add_argument("--seed",type=int);p.add_argument("--phase",choices=("development","confirmation"));p.add_argument("--stop-after",type=int);x=p.parse_args()
    result=register(x.run_root) if x.command=="register" else check(x.run_root) if x.command=="check" else controls(x.run_root,x.phase) if x.command=="controls" else train(x.run_root,x.seed,x.stop_after) if x.command=="train" else freeze(x.run_root) if x.command=="freeze" else confirm(x.run_root,x.seed) if x.command=="confirm" else merge(x.run_root)
    print(json.dumps(serial(result),ensure_ascii=False),flush=True)

if __name__=="__main__":main()
