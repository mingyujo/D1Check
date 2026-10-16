"""Causal full arrived queue ATC bank and native PPO execution, no queue-drain forecasts."""
import copy
import math
import time
from dataclasses import asdict, dataclass

import numpy as np
import torch

from tools import d1_external_rules as external
from tools import d1_rolling_hybrid_model as hybrid
from tools import d1_list_candidate_rl as native

p = external.p
PHASES = native.PHASES
FIELDS = native.PUBLIC_PHASE_EVENTS
REQUEST_SLOTS = 8
STATE_DIM, ACTION_DIM, SLOTS = 206, 49, 32
KINDS = ("single", "bundle", "resource_wait")
POLICY = "HETERO_QUEUE8_PHYSICAL_DIRECT_NATIVE_PPO_V3"
RULE = "HETERO_QUEUE8_SAME_BANK_DIRECT_RULE_V3"
EPS = 1e-9  # event-time consistency only; never a final KPI tolerance
VERSION = "heterogeneous-input-io-exploration-v1"
TICKET_FIELDS = {"id","task","priority","ordinal","arrival_ns","deadline_offset_ns","service_class"}
IO_EXTRA_NS = (0,25_000_000,75_000_000)
DEADLINES_NS = dict(urgent=(750_000_000,1_500_000_000,3_000_000_000),normal=(3_000_000_000,6_000_000_000,9_000_000_000))

def estimate_key(q,b):
    return p.key(q,b)+"@io"+str(q.get("service_class",0))

def public_estimates(frozen):
    out={}
    for key,values in p.profile(frozen).items():
        for c,extra in enumerate(IO_EXTRA_NS):
            ds=list(values);ds[1]+=extra # S->O contains input read/decode/tensor and inference in the A24 executor.
            out[key+"@io"+str(c)]=ds
    return out

def validate_engine(config,vectors,requests,policy,settings,provider):
    if config.get("protocol")!=VERSION or provider.protocol!=VERSION or policy!=p.PPO_POLICY or settings['mode']!='explore':
        raise ValueError("explicit heterogeneous opt-in transport")
    if set(config['cells'])!=set(p.CELLS) or not callable(provider) or not callable(provider.observe):
        raise ValueError("service contract")
    if any(settings[k]!=1 for k in ('interference','predicted_interference','estimate_factor','load_prepare_factor','load_callback_factor')) or any(settings[k]!=0 for k in ('decision_ns','record_ns','dispatch_ns')):
        raise ValueError("frozen support and zero plant control overhead")
    if set(vectors['per_request'])!={q['id'] for q in requests}:raise ValueError("realization roster")
    for q in requests:
        p.backends(q)
        if set(q)!=TICKET_FIELDS or not 35e9<=q['arrival_ns']<120e9 or type(q['service_class']) is not int or q['service_class'] not in range(3) or q['deadline_offset_ns'] not in DEADLINES_NS[q['priority']]:
            raise ValueError("public request schema/range")
        if set(vectors['per_request'][q['id']])!=set(p.backends(q)):raise ValueError("realization routes")
        for cell in vectors['per_request'][q['id']].values():
            if len(cell)!=4 or any(len(v['durations_ns'])!=5 or any(not math.isfinite(x) or x<0 for x in v['durations_ns']) for v in cell):
                raise ValueError("invalid private realization")



@dataclass(frozen=True)
class Settings:
    k: float = 2.
    urgent_weight: float = 2.
    normal_weight: float = 1.
    top_k: int = 4
    ema: float = .1

    def __post_init__(self):
        if self.k <= 0 or min(self.urgent_weight, self.normal_weight) <= 0 or self.top_k != 4 or not 0 < self.ema <= 1:
            raise ValueError("invalid registered ATC configuration")


DEFAULT = Settings()
SCHEMA = native.digest(dict(version="public-io-deadline-queue8-direct-v3", state=STATE_DIM,
    candidate=ACTION_DIM, slots=SLOTS, kinds=KINDS, settings=asdict(DEFAULT), io_extra=IO_EXTRA_NS, deadlines=DEADLINES_NS, state_extension="candidate declared deadline/6s x8",
    observation="public tails and current modeled AP only; no hidden H/slow",
    normalization="fixed units clip signed10; missing zero plus valid",
    candidate_meaning="all arrived top4 union oldest C/D union current fullqueue L0; max8 canonical slots; request-bound actions",
    wait="resource only; arrivals/AVAILABLE cancel; observed release estimate timer; aliases deduplicated"))


def tie(q):
    return q["arrival_ns"], q["ordinal"], q["id"]


def heads(queue):
    return {task: min((q for q in queue if q["task"] == task), key=tie, default=None)
            for task in ("classification", "detection")}


def due(q):
    return q["arrival_ns"] + q["deadline_offset_ns"]


def members(lanes):
    return [l["request"]["task"] + "_" + b for b, l in lanes.items() if l["request"] is not None]


def legal(job, queue, lanes, by_id=None):
    q = by_id.get(job["request_id"]) if by_id is not None else next((q for q in queue if q["id"] == job["request_id"]), None)
    if q is None or job["backend"] not in p.backends(q) or lanes[job["backend"]]["request"] is not None:
        return False
    try:
        p.state(members(lanes) + [q["task"] + "_" + job["backend"]])
    except ValueError:
        return False
    return True


def physical(action, queue, lanes, by_id=None):
    by_id=by_id if by_id is not None else {q["id"]:q for q in queue}
    if action is None:
        return False
    if action["kind"] == "resource_wait":
        target = action["target"]
        q = by_id.get(target["request_id"])
        return bool(q is not None and
                    target["backend"] in p.backends(q) and any(l["request"] for l in lanes.values()) and
                    not legal(target, queue, lanes, by_id))
    jobs = action.get("jobs", [])
    if action["kind"] not in ("single", "bundle") or len(jobs) != (1 if action["kind"] == "single" else 2):
        return False
    if len({j["request_id"] for j in jobs}) != len(jobs) or len({j["backend"] for j in jobs}) != len(jobs):
        return False
    virtual = {b: dict(l) for b, l in lanes.items()}
    for job in jobs:
        if not legal(job, queue, virtual, by_id):
            return False
        virtual[job["backend"]]["request"] = by_id[job["request_id"]]
    return True


def durations(estimates, q, b):
    values = estimates.get(estimate_key(q, b))
    if values is None or len(values) != 5 or any(not math.isfinite(v) or v < 0 for v in values) or sum(values) <= 0:
        return None
    response = sum(values[:2 if q["priority"] == "urgent" else 3])
    return (sum(values) / 1e9, response / 1e9) if response > 0 else None


def representative(estimates, q):
    opts = [(durations(estimates, q, b), b) for b in p.backends(q)]
    opts = [(d, b) for d, b in opts if d is not None]
    return min(opts, key=lambda v: (v[0][0], v[1] != "CPU")) if opts else (None, None)


def atc_scores(waiting, estimates, now, settings=DEFAULT):
    reps = {q["id"]: representative(estimates, q)[0] for q in waiting}
    known = [v[0] for v in reps.values() if v is not None]
    mean = sum(known) / len(known) if known else None
    values = {}
    for q in waiting:
        rep = reps[q["id"]]
        w = settings.urgent_weight if q["priority"] == "urgent" else settings.normal_weight
        values[q["id"]] = (math.log(rep[0]) - math.log(w) +
            max(0., (due(q)-now)/1e9-rep[1])/(settings.k*mean)) if rep is not None else None
    return values


def head_l0(queue, lanes, estimates):
    by_id={q["id"]:q for q in queue}
    virtual = {b: dict(l) for b, l in lanes.items()}; jobs = []
    for q in sorted(queue, key=lambda q: (due(q), *tie(q))):
        options = [dict(request_id=q["id"], backend=b) for b in p.backends(q)]
        options = [j for j in options if legal(j, queue, virtual, by_id)]
        if not options:
            continue
        def key(j):
            d = durations(estimates, q, j["backend"])
            return (d is None, d[0] if d else 0., j["backend"] != "CPU")
        job = min(options, key=key); jobs.append(job)
        virtual[job["backend"]]["request"] = q
        if len(jobs)==2:break
    jobs.sort(key=lambda j: j["backend"] != "GPU")
    return dict(kind="bundle" if len(jobs)==2 else "single", jobs=jobs) if jobs else None


def signature(action):
    if action is None:
        return None
    if action["kind"]=="resource_wait":
        # All current waits wake on the same first AVAILABLE/arrival/min-owner timer.
        # The target is a reason, not a reservation or a different physical action.
        return ("resource_wait",(),())
    return (action["kind"], tuple(sorted((j["request_id"], j["backend"]) for j in action.get("jobs", []))),
            tuple(sorted(action.get("target", {}).items())))


def bank(queue, lanes, now, estimates, settings=DEFAULT, sequencing="ATC"):
    start=time.perf_counter()
    by_id={q["id"]:q for q in queue}
    waiting=list(queue)  # public arrived, unstarted tickets only
    scores=atc_scores(waiting,estimates,now,settings)
    after_atc=time.perf_counter()
    ranked=sorted(waiting,key=lambda q: ((scores[q["id"]] is None,
        scores[q["id"]] if scores[q["id"]] is not None else due(q),*tie(q))
        if sequencing=="ATC" else (False,due(q),*tie(q))))
    base=head_l0(queue,lanes,estimates)  # current physical placements, at most two; no queue rollout
    coverage=[q for q in heads(queue).values() if q]
    ids={q["id"] for q in ranked[:settings.top_k]+coverage}
    if base: ids.update(j["request_id"] for j in base["jobs"])
    slots=sorted([q for q in waiting if q["id"] in ids],key=tie)
    if len(slots)>REQUEST_SLOTS: raise ValueError("reserved request bank exceeded")
    c=[q for q in slots if q["task"]=="classification"]
    d=[q for q in slots if q["task"]=="detection"]
    job=lambda q,b:dict(request_id=q["id"],backend=b)
    actions=[dict(kind="single",jobs=[job(q,b)]) for q in slots for b in p.backends(q)]
    actions += [dict(kind="bundle",jobs=[job(x,"GPU"),job(y,"CPU")]) for x in c for y in d]
    blocked=[job(q,b) for q in slots for b in p.backends(q) if not legal(job(q,b),queue,lanes,by_id)]
    if blocked and any(l["request"] for l in lanes.values()):
        actions.append(dict(kind="resource_wait",target=blocked[0]))
    if len(actions)>29:raise ValueError("supported actions exceeded derived bound29")
    slots += [None]*(REQUEST_SLOTS-len(slots))
    actions += [None]*(SLOTS-len(actions))
    after_candidates=time.perf_counter()
    mask=np.asarray([physical(a,queue,lanes,by_id) for a in actions],dtype=bool)
    base_slot=next((i for i,a in enumerate(actions) if mask[i] and signature(a)==signature(base)),None)
    if base_slot is None and mask.any():base_slot=int(np.flatnonzero(mask)[0])
    return dict(slots=slots,actions=actions,mask=mask,base=base_slot,scores=scores,
        ranked_ids=[q["id"] for q in ranked],coverage_ids=[q["id"] for q in coverage],
        timings=dict(atc_seconds=after_atc-start,candidates_seconds=after_candidates-after_atc,
            mask_seconds=time.perf_counter()-after_candidates))


class Controller(hybrid.ThermalMixin, external.Timed):
    protocol = VERSION

    def __init__(self, frozen, initial, network=None, deterministic=True, generator=None, mode=POLICY, settings=DEFAULT, sequencing="ATC"):
        super().__init__(frozen, initial)
        self.estimates=public_estimates(frozen)
        self.policy = p.PPO_POLICY  # unchanged legacy opt-in transport; new public/schema ID
        self.public_policy = mode; self.schema_id = SCHEMA
        self.sequencing=sequencing
        self.settings = settings; self.network = network; self.deterministic = deterministic
        self.generator = generator; self.events=[]; self.snapshots=[]; self.tickets={}; self.responses={}
        self.receipts={}; self.phase_cursors={}; self.pending=None; self.hold=None
        self.event_seq=0; self.stats=dict(fallback=0, pair_cancelled=0, wait_selected=0, wait_cancelled=0,
                                       duplicate_callbacks=0, ATC_EDD_bank_same=0, ATC_EDD_bank_different=0)
        self.times=[]; self.grid={}; self.online_forecast_calls=0
        self.observations={}; self.last_key=None; self.model_errors=0; self.model_disabled=False

    def on_public_event(self, event):
        if set(event) - {"at_ns","event_seq","request_id","backend","event","ticket"}:
            raise ValueError("private public-event fields")
        if event["event_seq"] != self.event_seq+1:
            raise ValueError("missing/duplicate/out-of-order public event")
        self.event_seq += 1; self.events.append(copy.deepcopy(event))
        rid, kind, now = event["request_id"], event["event"], event["at_ns"]
        if kind == "arrived":
            q = copy.deepcopy(event["ticket"])
            if rid in self.tickets or set(q) != TICKET_FIELDS or q["arrival_ns"] > now:
                raise ValueError("duplicate/private/future ticket")
            p.backends(q); self.tickets[rid]=q
            if self.hold: self.stats["wait_cancelled"]+=1
            self.hold=None
        elif kind == "dispatch_ns":
            if rid not in self.tickets or rid in self.receipts:
                raise ValueError("duplicate/unknown actual dispatch")
            if event["backend"] not in p.backends(self.tickets[rid]):
                raise ValueError("unsupported actual dispatch")
            self.receipts[rid]=dict(backend=event["backend"], at_ns=now, points=[now])
            self.phase_cursors[rid]=-1
        elif kind in FIELDS:
            if rid not in self.receipts:
                raise ValueError("phase before dispatch")
            cursor=self.phase_cursors[rid]+1
            if cursor >= 5 or FIELDS[cursor]!=kind or event["backend"]!=self.receipts[rid]["backend"]:
                raise ValueError("public phase order/owner mismatch")
            receipt=self.receipts[rid]; receipt["points"].append(now); self.phase_cursors[rid]=cursor
            q=self.tickets[rid]
            if kind==("output_ready_ns" if q["priority"]=="urgent" else "persist_complete_ns"):
                if rid in self.responses: raise ValueError("duplicate response")
                self.responses[rid]=dict(priority=q["priority"], response_ms=round(now-q["arrival_ns"])/1e6)
            if kind=="lane_available_ns":
                ds=[b-a for a,b in zip(receipt["points"],receipt["points"][1:])]
                if any(v<0 for v in ds) or len(ds)!=5: raise ValueError("invalid observed intervals")
                cell=estimate_key(q,receipt["backend"]); alpha=self.settings.ema
                self.estimates[cell]=[(1-alpha)*a+alpha*b for a,b in zip(self.estimates[cell],ds)]
                n=self.observations.get(cell,dict(n=0))["n"]+1
                self.observations[cell]=dict(n=n, at_ns=now)
                if self.hold:self.stats["wait_cancelled"]+=1
                self.hold=None
        else:
            raise ValueError("unknown public event")

    def encode(self, queue, lanes, now, e):
        state=np.zeros(STATE_DIM,dtype=np.float32); vectors=np.zeros((SLOTS,ACTION_DIM),dtype=np.float32)
        groups={task: sorted([q for q in queue if q["task"]==task],key=tie) for task in heads(queue)}
        counts=[len(groups[t]) for t in groups]
        state[:3]=[now/120e9,*[math.log1p(n)/math.log(97) for n in counts]]
        for j,(task,scale) in enumerate((("classification",1.5),("detection",6.))):
            qs=groups[task]
            if qs: state[3+j]=(now-qs[0]["arrival_ns"])/1e9/scale
            if len(qs)>1: state[5+j]=(due(qs[1])-now)/1e9/scale
        for j,(task,b) in enumerate((("classification","CPU"),("classification","GPU"),("detection","CPU"))):
            ds=[durations(self.estimates,q,b) for q in groups[task]]
            state[7+j]=sum(d[0] for d in ds if d is not None)/6
        recent=sorted(self.tickets.values(),key=tie)[-8:]
        ts=sorted({q["arrival_ns"]/1e9 for q in recent})
        if len(ts)>1: state[10:12]=[(ts[-1]-ts[-2])/6,1]
        if len(ts)>=3 and ts[-1]>ts[0]:
            work=sum((durations(self.estimates,q,"CPU") or (0,0))[0] for q in recent if q["task"]=="detection")
            state[12:14]=[work/(ts[-1]-ts[0]),1]
        state[14:17]=[(self.t-30)/10,1,0]  # current model-plant AP, explicitly tagged by runner
        points=sorted((t,v) for t,v in self.grid.items() if t<=now/1e9)
        if len(points)>=2:
            (t0,v0),(t1,v1)=points[-2:]
            state[17:19]=[(v1-v0)/(t1-t0)/.1,1]
        state[19]=(max(self.grid.values(),default=self.t)-30)/10
        urg=[v["response_ms"] for v in self.responses.values() if v["priority"]=="urgent"]
        if urg:state[20:22]=[native.rank95(urg)/1500,1]
        state[22:24]=[len(urg)/96,(len(self.responses)-len(urg))/96]
        for slot,q in enumerate(e["slots"]):
            if q is None:continue
            scale=q["deadline_offset_ns"]/1e9; offset=24+18*slot
            values=[1.,float(q["task"]=="classification"),float(q["task"]=="detection"),float(q["priority"]=="urgent"),float(q["priority"]=="normal"),
                (now-q["arrival_ns"])/1e9/scale,(due(q)-now)/1e9/scale,
                (self.settings.urgent_weight if q["priority"]=="urgent" else self.settings.normal_weight)/2,
                float("CPU" in p.backends(q)),float("GPU" in p.backends(q))]
            for b in ("CPU","GPU"):
                ds=durations(self.estimates,q,b) if b in p.backends(q) else None
                values += [ds[0]/6,ds[1]/scale,1.] if ds else [0.,0.,0.]
            _,b=representative(self.estimates,q); obs=self.observations.get(estimate_key(q,b),{}) if b else {}
            values += [math.log1p(obs.get("n",0))/math.log(97),(now-obs["at_ns"])/6e9 if "at_ns" in obs else 0.]
            state[offset:offset+18]=values
        for j,b in enumerate(("CPU","GPU")):
            l=lanes[b]; q=l["request"]; o=24+18*REQUEST_SLOTS+15*j
            state[o]=float(q is not None)
            phase=PHASES.index(l["phase"]) if q else 5
            state[o+4+phase]=1.
            if q:
                state[o+1:o+4]=[float(q["task"]=="classification"),float(q["task"]=="detection"),float(q["id"] in self.responses)]
                state[o+10:o+12]=[(now-l["dispatch"])/6e9,(now-l["since"])/6e9]
                ds=self.estimates[estimate_key(q,b)]; end=l["dispatch"]+sum(ds)
                known=end>now and l["dispatch"]+sum(ds[:phase+1])>now
                state[o+12:o+15]=[(end-now)/6e9 if known else 0.,float(known),float(not known)]
        by={q["id"]:q for q in queue}
        slot_by={q["id"]:j for j,q in enumerate(e["slots"]) if q}
        for i,a in enumerate(e["actions"]):
            if a is None:continue
            v=vectors[i];v[0]=1.;v[1+("single","bundle","resource_wait").index(a["kind"])]=1.
            jobs=a.get("jobs",[a.get("target")])
            for j,job in enumerate(jobs):
                q=by[job["request_id"]];b=job["backend"];scale=q["deadline_offset_ns"]/1e9
                vals=[1.,float(q["task"]=="classification"),float(q["task"]=="detection"),
                    float(q["priority"]=="urgent"),float(q["priority"]=="normal"),float(b=="CPU"),float(b=="GPU")]
                vals += [float(k==slot_by[q["id"]]) for k in range(REQUEST_SLOTS)]
                vals += [(now-q["arrival_ns"])/1e9/scale,(due(q)-now)/1e9/scale,scale/6,
                    (self.settings.urgent_weight if q["priority"]=="urgent" else self.settings.normal_weight)/2]
                ds=durations(self.estimates,q,b)
                vals += [ds[0]/6,ds[1]/scale,1.] if ds else [0.,0.,0.]
                assert len(vals)==22
                v[4+22*j:26+22*j]=vals
            v[48]=float(i==e["base"])
        state=np.clip(state,-10,10); vectors=np.clip(vectors,-10,10)
        if not np.isfinite(state).all() or not np.isfinite(vectors).all():raise ValueError("nonfinite encoder")
        for i,q in enumerate(e['slots']):
            if q:state[198+i]=np.clip(q['deadline_offset_ns']/6e9,-10,10)
        return dict(state=state,candidates=vectors,mask=e["mask"].copy(),schema_id=self.schema_id)

    def rule(self,e,queue,lanes):
        by={q["id"]:q for q in queue}
        for rid in e["ranked_ids"]:
            options=[i for i,a in enumerate(e["actions"]) if e["mask"][i] and a["kind"]=="single" and a["jobs"][0]["request_id"]==rid]
            if not options:continue
            def key(i):
                ds=durations(self.estimates,by[rid],e["actions"][i]["jobs"][0]["backend"])
                return ds is None,ds[0] if ds else 0.,i
            i=min(options,key=key);chosen=e["actions"][i]["jobs"][0]
            if chosen["backend"]=="GPU":
                pairs=[j for j,a in enumerate(e["actions"]) if e["mask"][j] and a["kind"]=="bundle" and a["jobs"][0]==chosen]
                if pairs:
                    order={r:k for k,r in enumerate(e["ranked_ids"])}
                    return min(pairs,key=lambda j:order[e["actions"][j]["jobs"][1]["request_id"]])
            return i
        return e["base"]

    def __call__(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        started=time.perf_counter(); self.validate_public(queue,lanes,now)
        if any(set(q)!=TICKET_FIELDS for q in queue):
            raise ValueError("private ticket fields")
        out=dict(now_ns=now,selected=None,reason="resource_event_wait",public_policy=self.public_policy)
        if self.pending:
            pending,self.pending=self.pending,None
            first=pending["first"]; receipt=self.receipts.get(first["request_id"]); owner=lanes[first["backend"]]["request"]
            if (receipt and receipt["at_ns"]==now==pending["at_ns"] and owner and owner["id"]==first["request_id"] and legal(pending["second"],queue,lanes)):
                return dict(out,selected=pending["second"],reason="guarded_pair_second_commit")
            self.stats["pair_cancelled"]+=1
        if not queue:return dict(out,reason="empty")
        hold_sig=(tuple(sorted(q["id"] for q in queue)),tuple((b,l["request"]["id"] if l["request"] else None) for b,l in lanes.items()))
        if self.hold:
            if self.hold["signature"]==hold_sig and (self.hold["until"] is None or now<self.hold["until"]):
                return dict(out,reason="resource_hold",**({"wait_until_ns":self.hold["until"]} if self.hold["until"] is not None else {}))
            self.stats["wait_cancelled"]+=1;self.hold=None
        key=(now,self.event_seq,hold_sig)
        if key==self.last_key:
            self.stats["duplicate_callbacks"]+=1
            return dict(out,reason="duplicate_decision_revision")
        self.last_key=key
        e=bank(queue,lanes,now,self.estimates,self.settings,self.sequencing)
        after_bank=time.perf_counter()
        other=bank(queue,lanes,now,self.estimates,self.settings,"EDD" if self.sequencing=="ATC" else "ATC")
        diagnostic_seconds=time.perf_counter()-after_bank
        same=[signature(a) for a in e["actions"]]==[signature(a) for a in other["actions"]] and np.array_equal(e["mask"],other["mask"])
        same_legal={signature(a) for a,m in zip(e["actions"],e["mask"]) if m}=={signature(a) for a,m in zip(other["actions"],other["mask"]) if m}
        self.stats["ATC_EDD_bank_same" if same else "ATC_EDD_bank_different"]+=1
        if not e["mask"].any():return dict(out,reason="no_legal_progress_contract_error")
        encoded=self.encode(queue,lanes,now,e); after_encode=time.perf_counter()
        chosen=self.rule(e,queue,lanes); info=False; forward_seconds=0.
        if e["mask"].sum()==1:
            chosen=int(np.flatnonzero(e["mask"])[0])
        elif self.public_policy==POLICY and self.network is not None and not self.model_disabled:
            try:
                if getattr(self.network,"schema_id",None)!=SCHEMA:raise ValueError("model schema mismatch")
                forward_started=time.perf_counter()
                with torch.no_grad():
                    dist,value=self.network(torch.from_numpy(encoded["state"])[None],torch.from_numpy(encoded["candidates"])[None],torch.from_numpy(encoded["mask"])[None])
                forward_seconds=time.perf_counter()-forward_started
                logits=dist.logits[0]
                if not torch.isfinite(logits[encoded["mask"]]).all() or not torch.isfinite(value).all():raise ValueError("nonfinite logits/value")
                if self.deterministic:
                    chosen=e["base"] if logits[e["base"]]==logits.max() else int(logits.argmax())
                else:
                    if self.generator is None:raise ValueError("independent sampling generator required")
                    chosen=int(torch.multinomial(dist.probs[0],1,generator=self.generator).item())
                    info=int(e["mask"].sum())>1
                encoded.update(old_value=value[0].numpy().copy(),logprob=float(dist.log_prob(torch.tensor([chosen])).item()))
                if not 0<=chosen<SLOTS or not e["mask"][chosen]:raise ValueError("invalid model action")
                self.model_errors=0
            except Exception as error:
                chosen=e["base"];self.stats["fallback"]+=1;self.model_errors+=1
                self.model_disabled=self.model_errors>=3;encoded["model_error"]=repr(error);info=False
                encoded.pop("old_value",None);encoded.pop("logprob",None)
        elif self.public_policy==POLICY:
            chosen=e["base"];self.stats["fallback"]+=1
        action=e["actions"][chosen]
        if not physical(action,queue,lanes):raise ValueError("stale physical action")
        encoded.update(chosen=chosen,informative=info,actor_eligible=info,actions=copy.deepcopy(e["actions"]),base=e["base"],now_ns=now,
            scores=e["scores"],ranked_ids=e["ranked_ids"],request_ids=[q["id"] if q else None for q in e["slots"]],queue_size=len(queue),
            nonhead_selected=any(j["request_id"]!=heads(queue)[next(q["task"] for q in queue if q["id"]==j["request_id"])]["id"] for j in action.get("jobs",[])),ATC_EDD_same=same,ATC_EDD_legal_actions_same=same_legal,
            raw_rank_same=e["ranked_ids"]==other["ranked_ids"],raw_top_same=e["ranked_ids"][:self.settings.top_k]==other["ranked_ids"][:self.settings.top_k],
            same_bank_rule_choice_same=signature(e["actions"][self.rule(e,queue,lanes)])==signature(other["actions"][self.rule(other,queue,lanes)]),online_forecast_calls=0)
        self.snapshots.append(encoded)
        if action["kind"]=="resource_wait":
            ends=[]
            for b,l in lanes.items():
                if l["request"]:
                    ds=self.estimates[estimate_key(l["request"],b)];end=l["dispatch"]+sum(ds)
                    if end>now:ends.append(end)
            until=min(ends) if ends else None
            self.hold=dict(signature=hold_sig,until=until);self.stats["wait_selected"]+=1
            out.update(action_kind="resource_wait",**({"wait_until_ns":until} if until is not None else {}))
        else:
            out.update(selected=copy.deepcopy(action["jobs"][0]),action_kind=action["kind"])
            if len(action["jobs"])==2:
                self.pending=dict(first=copy.deepcopy(action["jobs"][0]),second=copy.deepcopy(action["jobs"][1]),at_ns=now)
        self.times.append(dict(**e["timings"],bank_seconds=after_bank-started,encode_seconds=after_encode-after_bank-diagnostic_seconds,diagnostic_seconds=diagnostic_seconds,
                               inference_seconds=forward_seconds,selection_record_seconds=time.perf_counter()-after_encode-forward_seconds,
                               actual_total_seconds=time.perf_counter()-started,total_seconds=time.perf_counter()-started-diagnostic_seconds,
                               queue=len(queue)))
        return out
