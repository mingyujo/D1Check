"""Explicit bounded register/gate/train/evaluate; fixed public A24 plant, no phone."""
import argparse
import copy
import gzip
import hashlib
import json
import os
import platform
import subprocess
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch

from tools import d1_atc_direct_policy as a
from tools import d1_atc_direct_ppo as learning
from tools import d1_atc_pilot_budget as budget
from tools import d1_desktop_seed_registry as registry
from tools import d1_ie_dispatch as ie
from tools import d1_list_candidate_rl_engine as engine
from tools import d1_list_candidate_rl_training as native

ROOT=Path(__file__).resolve().parents[1]
SEEDS=(11,23,37)
FAMILIES=("low","queue","burst","sustained")
CONTEXTS=("mean","short_context","long_context")
ROLES=("Band","Triton","EDD","Rule","PPO11","PPO23","PPO37")
TRAIN=tuple(range(861110101,861110117))
DEV=(861210101,861210102)
CONFIRM=(861310101,861310102,861310103,861310104)
REALIZATION=861000201
OBJECTIVE=learning.OBJECTIVE


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
    return [dict(arrival_seed=s,family=f,context=c,condition=i)
            for i,(s,f,c) in enumerate((s,f,c) for s in seeds for f in FAMILIES for c in CONTEXTS)]


def source_manifest():
    import sys
    paths={Path(v.__file__).resolve() for k,v in sys.modules.copy().items()
           if k.startswith("tools.") and getattr(v,"__file__",None)}
    paths|={Path(__file__).resolve(),ROOT/"tools/test_d1_atc_direct.py",ROOT/"tools/test_d1_s26_mixed_audit.py"}
    paths|={a.hybrid.MODEL,a.p.BUNDLE/"model.json",a.p.BUNDLE/"initial_inputs.json",
            ROOT/"docs/results/list_candidate_rl_review_01/design_amendment_v4.json"}
    return {p.relative_to(ROOT).as_posix():budget.digest(p) for p in sorted(paths) if p.is_relative_to(ROOT)}


def register(folder):
    path=folder/"registration.json"
    if path.exists():raise FileExistsError("contract exists; inspect/resume, no re-register")
    b=budget.Budget(folder)
    if not budget.read(folder/"portable_suite.json")["status"]=="PASS" or not budget.read(folder/"frozen_demo.json")["status"]=="PASS":
        raise ValueError("raw-free preflight first")
    seeds=registry.collect()
    new=set(TRAIN+DEV+CONFIRM)
    if new & set(seeds["seeds"]) or any(lo<=s<=hi for s in new for lo,hi in seeds["ranges"]):
        raise ValueError("arrival seed reservation collision")
    train=[dict(arrival_seed=TRAIN[i//4],family=FAMILIES[i%4],context=CONTEXTS[(i//4)%3],condition=i) for i in range(64)]
    inputs=dict(train=train,development=cases(DEV),confirmation=cases(CONFIRM))
    f,i,m=a.hybrid.load()
    reg=dict(task=budget.TASK,base_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        schema=a.SCHEMA,settings=asdict(a.DEFAULT),objective=OBJECTIVE,
        PPO_settings=asdict(native.Settings()),learning_seeds=SEEDS,
        independent_action_and_shuffle_generators=True,gamma=1,GAE=False,
        normalization="native full8episode advantage normalization; fixed input units and clip10",
        costs=["J120 minus observed resident baseline120 /1J","absolute incomplete rate",
               "absolute urgent failure rate","absolute normal failure rate","absolute urgent P95/1500ms"],
        AP_reward="negative running-peak increments /1C, gamma1; full35..180 telescope; no baseline teacher",
        energy_reward="whole common120 including waiting; known constant resident baseline removed only in learning target",
        dual="I/U/N only, zero failure-rate target, eta.01 cap100; E/Q fixed weight1",
        initial_multipliers=[1,10,10,10,1],inputs_sha256=a.native.digest(inputs),
        input_sources="arrived tickets/public phases/current model-plant AP; hidden H/slow and future events excluded",
        physical_mask_only=True,resource_wait_only=True,wait_aliases_deduplicated=True,
        no_queue_drain_forecast=True,actual_realization_seed=REALIZATION,
        initialization="same validated measured idle preload,26 samples; no new thermal initial state",
        model_sources=source_manifest(),original_energy_service_preserved=True,
        temperature_service_feedback=False,model_refit=0,
        expected=dict(preflight=14,gate=8,train=192,dev32=168,dev64_new_PPO_only=72,
                      confirmation=336,total=790,learning=192),
        caps=budget.CAPS,development_role="fresh arrival seeds, selection allowed",
        confirmation_role="fresh disjoint seeds; freeze/checkpoint choice before reading",
        final_gate="original epsilon0 per-condition full completion/service/P95/J/AP plus primary low/sustained strict one-axis gain",
        required_baselines=["Band","Triton","Rule"],all_three_seeds_reported=True,
        S26="held on mixed quality/precision/time/energy/profile gates; static adapter only",
        old_amount512_reopened=False,experiment_ready=False,automatic_adoption=False,
        source_registry_sha256=a.native.digest(seeds),python=platform.python_version(),
        torch=torch.__version__,numpy=np.__version__,CPU_threads=1)
    reg["validation_checkpoint_selection"]="each seed chooses32 or64 on development only; terminal64 preserved; all3 selected models confirmed"
    write(folder/"registration.json",reg);write(folder/"inputs.json",inputs)
    deps=dict(schema=a.SCHEMA,objective=OBJECTIVE,sources=reg["model_sources"],input_sha=reg["inputs_sha256"])
    for seed in SEEDS:learning.Learner(seed,deps).save(folder/"checkpoints"/f"seed{seed}_latest.pt")
    write(folder/"cursor.json",dict(stage="gate",gate=0,train=0,dev32=0,dev64=0,confirmation=0,completed=False))
    return reg


def check(folder):
    reg=budget.read(folder/"registration.json")
    if reg["caps"]!=budget.CAPS or reg["schema"]!=a.SCHEMA:raise ValueError("frozen contract/caps")
    repairs=budget.read(folder/"source_repairs.json") if (folder/"source_repairs.json").exists() else {}
    if repairs:
        if repairs["registration_sha256"]!=budget.digest(folder/"registration.json") or repairs["scope"] not in ("driver_archive_digest_only","driver_metadata_and_stage_resume_only"):
            raise ValueError("source repair identity/scope mismatch")
        if set(repairs["effective_sources"])!={"tools/d1_atc_direct_study.py"}:
            raise ValueError("policy/learner source change is not an archive serializer repair")
    for name,expected in reg["model_sources"].items():
        if name in repairs.get("effective_sources",{}):
            repair=repairs["effective_sources"][name]
            if repair["original_sha256"]!=expected:raise ValueError("repair original identity mismatch")
            expected=repair["effective_sha256"]
        if budget.digest(ROOT/name)!=expected:raise ValueError("source/model changed after registration: "+name)
    if a.native.digest(budget.read(folder/"inputs.json"))!=reg["inputs_sha256"]:raise ValueError("input changes")
    return reg


class Proxy:
    def __init__(self,controller):
        self.controller=controller;self.callbacks=[];self.observation_seconds=0.
    def __getattr__(self,key):return getattr(self.controller,key)
    def __call__(self,*args):
        t=time.perf_counter()
        try:return self.controller(*args)
        finally:self.callbacks.append(dict(seconds=time.perf_counter()-t,queue=len(args[1])))
    def observe(self,*args):
        t=time.perf_counter()
        try:return self.controller.observe(*args)
        finally:self.observation_seconds+=time.perf_counter()-t


class Fixed(torch.nn.Module):
    schema_id=a.SCHEMA
    def __init__(self,slot):super().__init__();self.slot=slot
    def forward(self,state,vectors,mask):
        logits=torch.zeros((len(state),7));logits[:,self.slot]=100
        return torch.distributions.Categorical(logits=logits.masked_fill(~mask,-torch.inf)),torch.zeros((len(state),6))


def controller(role,f,initial,learners=None):
    if role=="Band":return a.hybrid.BandController(f,initial)
    if role=="Triton":return a.hybrid.TritonController(f,initial,a.hybrid.prior.triton.OFF)
    if role=="EDD":
        cls=type("HybridEDD",(a.hybrid.ThermalMixin,ie.Controller),{})
        return cls(f,initial,"IE_EDD_ECT_LANE_PC_V1")
    if role=="Rule":return a.Controller(f,initial,mode=a.RULE)
    if role.startswith("PPO"):
        return learners[int(role[3:])].controller(f,initial,True)
    if role=="ForcePair":return a.Controller(f,initial,network=Fixed(3))
    if role=="ForceWait":return a.Controller(f,initial,network=Fixed(4))
    raise ValueError("unknown registered role")


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
    qs=case.get("requests") or a.external.old.workload(case["family"],case["arrival_seed"])
    actual=a.p.profile(f,case["context"])
    vectors=dict(cells={k:[dict(source_request_id="frozen_"+case["context"],durations_ns=([0.]*5 if zero else v)) for _ in range(4)] for k,v in actual.items()})
    proxy=Proxy(agent);t=time.perf_counter();cpu=time.process_time()
    with b.environment(identity,phase,learning_episode):
        if isinstance(agent,a.Controller):
            # Any queue-drain/placement or future-cost call during policy selection is a contract failure.
            with patch.object(a.p.Controller,"rollout",side_effect=AssertionError("online queue-drain forecast")), \
                 patch.object(a.p.Controller,"place",side_effect=AssertionError("online virtual placement")), \
                 patch.object(a.hybrid,"costs",side_effect=AssertionError("online future AP/J")):
                result=engine.simulate(dict(protocol=a.p.VERSION,cells=a.p.profile(f)),vectors,qs,
                    policy=agent.policy,settings=a.external.settings(),seed=REALIZATION,decision_provider=proxy)
        else:
            result=engine.simulate(dict(protocol=a.p.VERSION,cells=a.p.profile(f)),vectors,qs,
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
            callbacks=len(proxy.callbacks),controller_observation_seconds=proxy.observation_seconds,
            modeled_temperature_channel="AP model-plant observation; not surface",experiment_ready=False)
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


def fixture(i):
    ticket=lambda n,t,at=35.,o=0:dict(id=n,task=t,priority="urgent" if t=="classification" else "normal",
        ordinal=o,arrival_ns=round(at*1e9),deadline_offset_ns=1500000000 if t=="classification" else 6000000000)
    pair=[ticket("C","classification"),ticket("D","detection",o=1)]
    cases_=[("EDD",pair),("Rule",pair),("PPO11",pair),("ForcePair",pair),
        ("ForceWait",[ticket("D","detection"),ticket("C","classification",35.05,1)]),
        ("ForceWait",[ticket("D","detection"),ticket("C","classification",35.05,1),ticket("C2","classification",35.15,2)]),
        ("Rule",pair),("Rule",[ticket("C","classification"),ticket("laterD","detection",35.8,1)])]
    role,qs=cases_[i]
    return dict(condition=i,arrival_seed=861001000+i,family="fixture",context="mean",role=role,requests=qs)


def schedule(raw):
    return [(r["id"],r.get("backend"),r.get("dispatch_ns"),r.get("response_ns"),r.get("lane_available_ns")) for r in raw["result"]["ledger"]]


def loaders(folder,reg):
    deps=dict(schema=a.SCHEMA,objective=OBJECTIVE,sources=reg["model_sources"],input_sha=reg["inputs_sha256"])
    if (folder/"session_latest.pt").exists():
        session=torch.load(folder/"session_latest.pt",map_location="cpu",weights_only=False)
        return {s:learning.Learner.from_snapshot(session["learners"][s],deps) for s in SEEDS}
    return {s:learning.Learner.load(folder/"checkpoints"/f"seed{s}_latest.pt",deps) for s in SEEDS}


def gate_rows(rows,policy,conditions):
    by={(q["condition"],q["policy"]):q for q in rows}
    if len(by)!=len(rows) or set(by)!={(i,r) for i in range(conditions) for r in ROLES}:
        raise ValueError("missing/duplicate complete paired evaluation rows")
    diffs=[];maintenance=True
    for i in range(conditions):
        q=by[i,policy]
        for ref in ("Band","Triton","Rule"):
            r=by[i,ref];delta={k:q[k]-r[k] if q[k] is not None and r[k] is not None else None
                for k in ("incomplete","urgent_failure","normal_failure","urgent_p95_ms","energy_j","peak_ap_c")}
            absolute=q["family"] not in ("low","sustained") or q["incomplete"]==q["urgent_failure"]==q["normal_failure"]==0
            passed=q["planned"]==q["completed"]==r["completed"]==r["planned"] and absolute and all(v is not None and v<=0 for v in delta.values())
            maintenance &= passed
            diffs.append(dict(condition=i,family=q["family"],baseline=ref,passed=passed,delta=delta))
    primary=[]
    for family in ("low","sustained"):
        subset=[x for x in diffs if x["family"]==family and x["baseline"] in ("Band","Triton")]
        if maintenance and subset and all(x["delta"]["energy_j"]<0 or x["delta"]["peak_ap_c"]<0 for x in subset):primary.append(family)
    return dict(maintenance_pass=maintenance,promising=maintenance and bool(primary),
                promising_families=primary,epsilon=0,differences=diffs,automatic_adoption=False)


def read_rows(folder,prefix):
    return [budget.read(p)["row"] for p in sorted((folder/"rows").glob(prefix+"*.json"))]


def run(folder,stop_after=None):
    reg=check(folder);b=budget.Budget(folder);cursor=budget.read(folder/"cursor.json")
    if cursor["completed"]:return dict(status="already_completed",consumption=b.used())
    inputs=budget.read(folder/"inputs.json");learners=loaders(folder,reg)
    if (folder/"session_latest.pt").exists():
        cursor=torch.load(folder/"session_latest.pt",map_location="cpu",weights_only=False)["cursor"]
    if (folder/"pause_receipt.json").exists() and not (folder/"resume_receipt.json").exists():
        paused=budget.read(folder/"pause_receipt.json")
        current={str(s):payload_digest(l.snapshot()) for s,l in learners.items()}
        if current!=paused["learner_digests"]:raise ValueError("process-boundary resume mismatch")
        write(folder/"resume_receipt.json",dict(status="PASS",all3learner_payloads_exact=True,
            cursor=cursor,partial=[len(learners[s].pending) for s in SEEDS],
            nonempty_Adam=[bool(learners[s].optimizer.state) for s in SEEDS],
            independent_action_shuffle_RNG_restored=True,old_budget_clock_not_reset=True))
    f,init,_=a.hybrid.load();initial=init["initial"];collected=0
    with b.session():
        while cursor["gate"]<8:
            i=cursor["gate"];case=fixture(i);role=case["role"]
            collect(b,folder,f"gate_{i:02d}","gate",case,controller(role,f,initial,learners),zero=i==6)
            cursor["gate"]+=1;write(folder/"cursor.json",cursor)
        first=[json.loads(gzip.decompress((folder/"items"/f"gate_{i:02d}.json.gz").read_bytes())) for i in range(3)]
        if not schedule(first[0])==schedule(first[1])==schedule(first[2]):raise ValueError("initial fallback/baseline gate mismatch")
        if cursor["train"]>=96 and cursor["dev32"]<168:
            # Resume the unfinished evaluation with frozen ep32 actors, not newer weights.
            at32={s:learning.Learner.load(folder/"checkpoints"/f"seed{s}_ep32.pt",learners[s].dependencies) for s in SEEDS}
            evaluate(folder,b,at32,inputs["development"],"dev32",ROLES,cursor,session_learners=learners)
        while cursor["train"]<192:
            number=cursor["train"];seed=SEEDS[number%3];index=number//3
            case=dict(inputs["train"][index],role="PPO"+str(seed))
            agent=learners[seed].controller(f,initial,False)
            raw=collect(b,folder,f"train_{seed}_{index:02d}","train",case,agent,True)
            frames,costs,valid,rewards=learning.targets(agent,raw["row"],raw["curve"],initial["preload_power_w"]*120)
            learners[seed].add(frames,costs,valid,raw["row"],agent)
            cursor["train"]+=1;cursor["stage"]="train";learners[seed].cursor=copy.deepcopy(cursor);learners[seed].consumption=b.used()
            # Single session bundle is the authoritative atomic resume point.
            save_session(folder,learners,cursor,b.used())
            write(folder/"cursor.json",cursor);collected+=1
            if learners[seed].episodes in (32,64):
                learners[seed].save(folder/"checkpoints"/f"seed{seed}_ep{learners[seed].episodes}.pt")
            if cursor["train"]==96:evaluate(folder,b,learners,inputs["development"],"dev32",ROLES,cursor)
            if stop_after and collected>=stop_after:
                write(folder/"pause_receipt.json",dict(cursor=cursor,consumption=b.used(),
                    learner_digests={str(s):payload_digest(l.snapshot()) for s,l in learners.items()},
                    reason="registered functional process-boundary pause, not new budget",
                    partial=[len(learners[s].pending) for s in SEEDS]))
                return dict(status="paused",cursor=cursor,consumption=b.used())
        if cursor["dev64"]<72:evaluate(folder,b,learners,inputs["development"],"dev64",ROLES[4:],cursor)
        development=read_rows(folder,"dev64_")+[dict(q,phase="dev64") for q in read_rows(folder,"dev32_") if q["policy"] in ROLES[:4]]
        if not (folder/"freeze.json").exists():
            development32=read_rows(folder,"dev32_")
            gates={s:gate_rows(development,"PPO"+str(s),24) for s in SEEDS}
            # Selection uses development only; retain every learner outcome.
            def key(seed,rr):
                rr=[q for q in rr if q["policy"]=="PPO"+str(seed)]
                return (sum(q["incomplete"] for q in rr),sum(q["urgent_failure"] for q in rr),
                    sum(q["normal_failure"] for q in rr),np.mean([q["urgent_p95_ms"] for q in rr]),
                    np.mean([q["energy_j"] if q["energy_j"] is not None else float("inf") for q in rr]),seed)
            checkpoints={s:32 if key(s,development32)<key(s,development) else 64 for s in SEEDS}
            selected=min(SEEDS,key=lambda s:key(s,development32 if checkpoints[s]==32 else development))
            write(folder/"freeze.json",dict(selected_seed=selected,checkpoint_episodes=checkpoints[selected],terminal_episodes=64,
                selected_by="development only: incomplete/urgent/normal/P95/J then seed",
                best_validation_epochs=checkpoints,
                best_validation_sha={str(s):budget.digest(folder/"checkpoints"/f"seed{s}_ep{checkpoints[s]}.pt") for s in SEEDS},
                terminal_sha={str(s):budget.digest(folder/"checkpoints"/f"seed{s}_latest.pt") for s in SEEDS},
                development_gates=gates,configuration_sha=a.native.digest(reg),
                no_confirmation_results_read=True))
        freeze=budget.read(folder/"freeze.json")
        deps=learners[11].dependencies
        chosen={s:learning.Learner.load(folder/"checkpoints"/f"seed{s}_ep{freeze['best_validation_epochs'][str(s)]}.pt",deps) for s in SEEDS}
        evaluate(folder,b,chosen,inputs["confirmation"],"confirmation",ROLES,cursor,session_learners=learners)
        final=read_rows(folder,"confirmation_")
        verdict={str(s):gate_rows(final,"PPO"+str(s),48) for s in SEEDS}
        write(folder/"verdict.json",verdict)
        cursor.update(completed=True,stage="completed");write(folder/"cursor.json",cursor)
        save_session(folder,learners,cursor,b.used())
    return dict(status="completed",consumption=b.used(),verdicts={s:v["promising"] for s,v in verdict.items()})


def save_session(folder,learners,cursor,consumption):
    payload=dict(version="atc-independent-session-v1",cursor=copy.deepcopy(cursor),
        consumption=copy.deepcopy(consumption),learners={s:l.snapshot() for s,l in learners.items()})
    path=folder/"session_latest.pt";tmp=path.with_suffix(".tmp")
    with tmp.open("wb") as f:torch.save(payload,f);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    for s,l in learners.items():l.save(folder/"checkpoints"/f"seed{s}_latest.pt")


def evaluate(folder,b,learners,cases_,stage,roles,cursor,session_learners=None):
    plan=[(case,role) for case in cases_ for role in roles]
    f,init,_=a.hybrid.load();initial=init["initial"]
    while cursor[stage]<len(plan):
        i=cursor[stage];case,role=plan[i]
        identity=f"{stage}_{case['condition']:02d}_{role}"
        failed=[r for r in b.rows if r["event"]=="failure" and
                (r["identity"]==identity or r["identity"].startswith(identity+"_retry"))]
        if failed:
            # A metadata-only failed invocation stays charged; collect a new retry identity.
            identity+=f"_retry{len(failed)}"
        collect(b,folder,identity,stage,dict(case,role=role),controller(role,f,initial,learners))
        cursor[stage]+=1;cursor["stage"]=stage;write(folder/"cursor.json",cursor)
        save_session(folder,session_learners if session_learners is not None else learners,cursor,b.used())


def main():
    p=argparse.ArgumentParser();p.add_argument("--run-root",required=True,type=Path)
    p.add_argument("--stop-after",type=int);p.add_argument("command",choices=("register","run","check"))
    x=p.parse_args()
    if x.command=="register":r=register(x.run_root)
    elif x.command=="check":r=check(x.run_root)
    else:
        try:r=run(x.run_root,x.stop_after)
        except InterruptedError:
            r=dict(status="REQUEST_STOP_saved_at_boundary",consumption=budget.Budget(x.run_root).used())
    print(json.dumps(serial(r),ensure_ascii=False))


if __name__=="__main__":main()
