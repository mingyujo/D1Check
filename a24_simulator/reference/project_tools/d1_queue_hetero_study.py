"""Registered full-queue PC-only study, frozen paired references and final data."""
import argparse, copy, gzip, hashlib, json, math, os, platform, subprocess, time
from dataclasses import asdict,is_dataclass
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_queue_hetero_policy as a
from tools import d1_queue_hetero_ppo as learning
from tools import d1_queue_hetero_budget as budget
from tools import d1_queue_hetero_mobile as mobile
from tools import d1_desktop_seed_registry as registry
from tools import d1_queue_hetero_engine as engine
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
        if isinstance(agent,a.Controller):
            # Any queue-drain/placement or future-cost call during policy selection is a contract failure.
            with patch.object(a.p.Controller,"rollout",side_effect=AssertionError("online queue-drain forecast")), \
                 patch.object(a.p.Controller,"place",side_effect=AssertionError("online virtual placement")), \
                 patch.object(a.hybrid,"costs",side_effect=AssertionError("online future AP/J")):
                result=engine.simulate(dict(protocol=a.VERSION,cells=a.p.profile(f)),vectors,qs,
                    policy=agent.policy,settings=a.external.settings(),seed=REALIZATION,decision_provider=proxy)
        else:
            result=engine.simulate(dict(protocol=a.VERSION,cells=a.p.profile(f)),vectors,qs,
                policy=agent.policy,settings=a.external.settings(),seed=REALIZATION,decision_provider=proxy)
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


SEEDS=(101,113,127)
FAMILIES=("low","queue","burst","sustained")
FACTORS=("single_fixed","single_deadlines","batch_uniform2","batch_variable")
BASES=(*mobile.ROLES,"RuleEDD","RuleATC")
TRAIN=tuple(range(873110101,873110117));DEV=(873210101,873210102)
CONFIRM=(873310101,873310102,873310103)
REALIZATION=873000201;HINT_SEED=873000301
STAGES=(128,256)
CSV=ROOT/"docs/results/overnight_device_20261011/requests.csv"

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
    # Imported transitive files plus the actual executed driver, even under __main__.
    import sys
    paths={Path(v.__file__).resolve() for k,v in sys.modules.copy().items() if k.startswith("tools.") and getattr(v,"__file__",None)}
    paths|={Path(__file__).resolve(),CSV,ROOT/"tools/test_d1_queue_hetero.py",a.hybrid.MODEL,a.p.BUNDLE/"model.json",a.p.BUNDLE/"initial_inputs.json",ROOT/"docs/results/list_candidate_rl_review_01/design_amendment_v4.json"}
    return {p.relative_to(ROOT).as_posix():budget.digest(p) for p in sorted(paths) if p.is_relative_to(ROOT)}

def register(folder):
    reserved=registry.collect();new=set(TRAIN+DEV+CONFIRM+(REALIZATION,HINT_SEED))
    if new & set(reserved["seeds"]) or any(lo<=s<=hi for s in new for lo,hi in reserved["ranges"]):raise ValueError("seed reservation collision")
    # Also inspect sibling local task registrations; the public registry is not live.
    for path in folder.parent.glob("*/inputs.json"):
        old=budget.read(path)
        for phase in ("train","development","confirmation"):
            if any(x.get("arrival_seed") in new for x in old.get(phase,[])):raise ValueError("local sibling seed collision")
    inputs=dict(train=cases(TRAIN),development=cases(DEV),confirmation=cases(CONFIRM))
    if len(inputs["train"])!=256 or len(inputs["development"])!=32 or len(inputs["confirmation"])!=48:raise ValueError("paired count")
    b=budget.Budget.register(folder,dict(user_authorized="realistic heterogeneous processing/deadline EDD ATC PPO repeat + new S26 handoff audit",device="A24 residual empirical bootstrap + declared synthetic batch sensitivity",S26_learning=0))
    reg=dict(task=budget.TASK,caps=budget.CAPS,head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),schema=a.SCHEMA,state=214,action=53,padding=32,sources=sources(),input_sha=a.native.digest(inputs),settings=asdict(a.DEFAULT),objective=learning.OBJECTIVE,stages=STAGES,seeds=SEEDS,preflight_tests=8,
        factors=FACTORS,baselines=BASES,deadline="urgent .5/1/1.5 seconds, normal2/4/6; no relaxation of original caps",processing="intact real ABBA4 fivephase bootstrap hidden draw; batch n1/2/3 publicly declared execution_start->OUTPUT_READY block scale, other4 stages fixed, not pure invoke",matched_load="batch_uniform2 and batch_variable equal total work units per task/trace; fixed arrival in all paired factors",pool_counts={k:len(v) for k,v in POOL.items()},pool_sha256=budget.digest(CSV),CPU_sample_warning="4 total; no robust CPU distribution/generalization claim",model_fit=0,
        train_arrival_seeds=TRAIN,development_arrival_seeds=DEV,confirmation_arrival_seeds=CONFIRM,realization_seed=REALIZATION,hint_seed=HINT_SEED,physics="C_CPU/C_GPU/D_CPU/CG_DC only, no preemption/migration, actualAVAILABLE, response independent; no cooling/NPU",reference_version="HETERO_FIFO_EFT_QUEUE_STRICT_V3",strict="all paired conditions completion/U/N/P95/J/AP epsilon0 nonworse vsFIFO_FIXED/FIFO_EFT/same-bankRule, low/sustained absolute failures0, low or sustained every condition J orAP strict gain; stricter requested deadlines kept",objective_units="APinterval/1C, Jminusbaseline/100J weight1 (relative energy emphasis changed vsV2), I/U/N rate initial10 dual, urgentP95/1500ms weight1",bank_gate="dev32 exact rawrank, bank/legal and encoder input equivalence; train separate6 only if bank/input difference",selection="dev32 lex I/U/N/urgentP95/J/AP then earliestcheckpoint; selected bank/seed frozen before newfinal48; all3 seeds per distinct bank reported",final_action="masked argmax tie fallback then canonical",budget_expected_if_two_banks=2768,preflight_environment_reserve=16,
        S26="pinned5bdc13c1 handoff: service exploration only, thermal not reproduced, no energy calibration; adapter replay separate environment count not policytraining",experiment_ready=False,automatic_adoption=False,python=platform.python_version(),torch=torch.__version__,numpy=np.__version__)
    write(folder/"registration.json",reg);write(folder/"inputs.json",inputs);write(folder/"cursor.json",dict(completed=False,stage="controls"))
    return dict(status="registered",task=budget.TASK,schema=a.SCHEMA,expected_max=2768,caps=budget.CAPS)

def check(folder):
    reg=budget.read(folder/"registration.json")
    if reg["schema"]!=a.SCHEMA or reg["caps"]!=budget.CAPS or reg["objective"]!=learning.OBJECTIVE:raise ValueError("immutable contract changed")
    repair=budget.read(folder/"source_repair.json") if (folder/"source_repair.json").exists() else None
    if repair and (repair["registration_sha256"]!=budget.digest(folder/"registration.json") or repair["scope"]!="json_unavailable_output_only"):
        raise ValueError("repair lineage or scope changed")
    for path,sha in reg["sources"].items():
        if repair and path in repair["effective_sources"]:
            item=repair["effective_sources"][path]
            if path!="tools/d1_queue_hetero_study.py" or item["original_sha256"]!=sha or budget.digest(folder/"source_archive/original_d1_queue_hetero_study.py")!=sha:
                raise ValueError("driver-only repair identity changed")
            sha=item["effective_sha256"]
        if budget.digest(ROOT/path)!=sha:raise ValueError("frozen source changed "+path)
    if a.native.digest(budget.read(folder/"inputs.json"))!=reg["input_sha"]:raise ValueError("frozen inputs changed")
    return reg

def deps(reg,bank):return dict(schema=a.SCHEMA,objective=learning.OBJECTIVE,sources=reg["sources"],input_sha=reg["input_sha"],sequencing=bank)
def rows(folder,prefix):return [budget.read(p)["row"] for p in sorted((folder/"rows").glob(prefix+"*.json"))]
def learner_path(folder,bank,seed,ep=None):return folder/"checkpoints"/f"{bank}_{seed}_{'latest' if ep is None else 'ep'+str(ep)}.pt"
def key(rr):
    return (sum(q["incomplete"] for q in rr),sum(q["urgent_failure"] for q in rr),sum(q["normal_failure"] for q in rr),np.mean([q["urgent_p95_ms"] if q["urgent_p95_ms"] is not None else float("inf") for q in rr]),np.mean([q["energy_j"] if q["energy_j"] is not None else float("inf") for q in rr]),np.mean([q["peak_ap_c"] if q["peak_ap_c"] is not None else float("inf") for q in rr]))

def controller(role,f,initial,learners=None):
    if role in mobile.ROLES:return mobile.Controller(f,initial,role)
    if role in ("RuleEDD","RuleATC"):return a.Controller(f,initial,mode=a.RULE,sequencing=role[4:])
    bank,seed=role.split("_");return learners[bank,int(seed)].controller(f,initial,True)

def evaluate(folder,b,cases_,roles,learners,stage):
    f,i,_=a.hybrid.load()
    for case in cases_:
        for role in roles:
            identity=f"{stage}_{case['condition']:02d}_{role}"
            path=folder/"rows"/(identity+".json")
            if path.exists():
                receipt=budget.read(path)
                if budget.digest(folder/"items"/(identity+".json.gz"))!=receipt["raw_sha256"]:raise ValueError("saved raw changed")
                continue
            collect(b,folder,identity,stage,dict(case,role=role),controller(role,f,i["initial"],learners))
    return rows(folder,stage+"_")

def strict(rr,role):
    by={(r["condition"],r["policy"]):r for r in rr};bank=role.split("_")[0];deltas=[];maintained=True
    for condition in sorted({q["condition"] for q in rr}):
        q=by[condition,role]
        for ref in ("FIFO_FIXED","FIFO_EFT","Rule"+bank):
            r=by[condition,ref];delta={k:q[k]-r[k] if q[k] is not None and r[k] is not None else None for k in ("incomplete","urgent_failure","normal_failure","urgent_p95_ms","energy_j","peak_ap_c")}
            absolute=q["family"] not in ("low","sustained") or q["incomplete"]==q["urgent_failure"]==q["normal_failure"]==0
            passed=q["planned"]==q["completed"]==r["planned"]==r["completed"] and absolute and all(v is not None and v<=0 for v in delta.values())
            maintained &= passed;deltas.append(dict(condition=condition,factor=q["factor"],family=q["family"],reference=ref,passed=passed,delta=delta))
    gains=[]
    for family in ("low","sustained"):
        dd=[q for q in deltas if q["family"]==family and q["reference"] in ("FIFO_FIXED","FIFO_EFT")]
        if maintained and all(q["delta"]["energy_j"]<0 or q["delta"]["peak_ap_c"]<0 for q in dd):gains.append(family)
    return dict(promising=maintained and bool(gains),maintenance_pass=maintained,epsilon=0,gain_families=gains,differences=deltas,automatic_adoption=False)

def run(folder,stop_after=None,controls_only=False):
    reg=check(folder);b=budget.Budget(folder);inputs=budget.read(folder/"inputs.json");cursor=budget.read(folder/"cursor.json")
    if cursor["completed"]:return dict(status="already_completed",consumption=b.used())
    f,i,_=a.hybrid.load();initial=i["initial"];accepted=0
    with b.session():
        evaluate(folder,b,inputs["development"],BASES,{},"controls")
        if not (folder/"bank_gate.json").exists():
            ss=[]
            for p in (folder/"items").glob("controls_*_RuleATC.json.gz"):ss+=json.loads(gzip.decompress(p.read_bytes()))["snapshots"]
            different=sum(not q["ATC_EDD_same"] or not q["ATC_EDD_legal_actions_same"] for q in ss)
            write(folder/"bank_gate.json",dict(banks=["EDD","ATC"] if different else ["EDD"],decisions=len(ss),bank_different=different,raw_rank_different=sum(not q["raw_rank_same"] for q in ss),legal_different=sum(not q["ATC_EDD_legal_actions_same"] for q in ss),atc_duplicate_learning_stopped=not bool(different)))
        if controls_only:return dict(status="controls_complete",gate=budget.read(folder/"bank_gate.json"),consumption=b.used())
        banks=budget.read(folder/"bank_gate.json")["banks"];roles=[f"{bank}_{seed}" for bank in banks for seed in SEEDS]
        learners={}
        for bank in banks:
            for seed in SEEDS:
                path=learner_path(folder,bank,seed)
                learners[bank,seed]=learning.Learner.load(path,deps(reg,bank)) if path.exists() else learning.Learner(seed,deps(reg,bank))
        stop_reason="maximum256"
        for stage in STAGES:
            if (folder/f"stage{stage}.json").exists():
                if not budget.read(folder/f"stage{stage}.json")["mechanics_pass"]:stop_reason="mechanics_failure";break
                continue
            for n in range(stage):
                for bank in banks:
                    for seed in SEEDS:
                        l=learners[bank,seed]
                        if l.episodes>n:continue
                        if l.episodes!=n:raise ValueError("learner cursor changed")
                        identity=f"train_{bank}_{seed}_{n:03d}"
                        if (folder/"rows"/(identity+".json")).exists():raise ValueError("unadopted episode requires explicit audit")
                        agent=l.controller(f,initial,False)
                        raw=collect(b,folder,identity,"train",dict(inputs["train"][n],role=f"{bank}_{seed}"),agent,True)
                        frames,costs,valid,_=learning.targets(agent,raw["row"],raw["curve"],initial["preload_power_w"]*120)
                        l.add(frames,costs,valid,raw["row"]);l.cursor=dict(episode=l.episodes);l.consumption=b.used();l.save(learner_path(folder,bank,seed))
                        write(folder/"cursor.json",dict(completed=False,stage="train",learning_accepted=sum(x.episodes for x in learners.values())))
                        accepted+=1
                        if stop_after and accepted>=stop_after:
                            write(folder/"pause_receipt.json",dict(digests={f"{bb}_{ss}":payload_digest(ll.snapshot()) for (bb,ss),ll in learners.items()},partial={f"{bb}_{ss}":len(ll.pending) for (bb,ss),ll in learners.items()},learning_accepted=sum(x.episodes for x in learners.values())))
                            return dict(status="paused",consumption=b.used())
            for (bank,seed),l in learners.items():l.save(learner_path(folder,bank,seed,stage))
            dev=evaluate(folder,b,inputs["development"],roles,learners,f"dev{stage}")
            mechanics=all(l.logs and all(np.isfinite(x["actor_gradient_max"]) and x["actor_gradient_max"]>0 and x["actor_changed"] for x in l.logs) and all(x["row"]["fallbacks"]==0 for x in l.episode_logs) for l in learners.values())
            write(folder/f"stage{stage}.json",dict(mechanics_pass=mechanics,learning_accepted=sum(l.episodes for l in learners.values()),development_keys={role:key([q for q in dev if q["policy"]==role]) for role in roles}))
            if not mechanics:stop_reason="mechanics_failure";break
        if not (folder/"freeze.json").exists():
            selections={}
            for role in roles:
                bank,seed=role.split("_")
                stages=[x for x in STAGES if (folder/f"stage{x}.json").exists()]
                ep=min(stages,key=lambda x:(key([q for q in rows(folder,f"dev{x}_") if q["policy"]==role]),x))
                selections[role]=dict(episodes=ep,sha256=budget.digest(learner_path(folder,bank,int(seed),ep)),development_key=key([q for q in rows(folder,f"dev{ep}_") if q["policy"]==role]))
            selected=min(roles,key=lambda r:(selections[r]["development_key"],r))
            if any((folder/"rows").glob("confirmation_*.json")):raise ValueError("cannot select after confirmation")
            write(folder/"freeze.json",dict(selected=selected,selections=selections,stop_reason=stop_reason,confirmation_not_read=True,registration_sha256=budget.digest(folder/"registration.json")))
        freeze=budget.read(folder/"freeze.json");final={}
        for role,selection in freeze["selections"].items():
            bank,seed=role.split("_");path=learner_path(folder,bank,int(seed),selection["episodes"])
            if budget.digest(path)!=selection["sha256"]:raise ValueError("frozen model changed")
            final[bank,int(seed)]=learning.Learner.load(path,deps(reg,bank))
        rr=evaluate(folder,b,inputs["confirmation"],(*BASES,*roles),final,"confirmation")
        write(folder/"verdict.json",{role:strict(rr,role) for role in roles})
        write(folder/"cursor.json",dict(completed=True,stage="completed",confirmation_rows=len(rr),selected=freeze["selected"]))
    return dict(status="completed",selected=freeze["selected"],consumption=b.used())

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=("register","check","run"));p.add_argument("--run-root",type=Path,required=True);p.add_argument("--stop-after",type=int);p.add_argument("--controls-only",action="store_true");x=p.parse_args()
    r=register(x.run_root) if x.command=="register" else check(x.run_root) if x.command=="check" else run(x.run_root,x.stop_after,x.controls_only)
    print(json.dumps(serial(r),ensure_ascii=False),flush=True)
if __name__=="__main__":main()
