"""Heterogeneous declared work units, causal observed estimates, stricter request deadlines. Synthetic batch assumptions are not measured app support."""
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
STATE_DIM, ACTION_DIM, SLOTS = 218, 57, 32
KINDS = ("single", "bundle", "resource_wait")
POLICY = "ATC_COUPLING_DIRECT_PPO_V5"
RULE = "ATC_COUPLING_RULE_V5"
EPS = 1e-9  # event-time consistency only; never a final KPI tolerance


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
SCHEMA = native.digest(dict(version="atc-coupling-218x57-v5", state=STATE_DIM,
    candidate=ACTION_DIM, slots=SLOTS, kinds=KINDS, settings=asdict(DEFAULT),
    observation="public declared work_units1..3, request deadline <= original caps; public past requested/original miss rates4; actualRuleATC teacher flag/fallback/tie; no realized private residual, hidden H/slow",
    normalization="fixed units clip signed10; missing zero plus valid",
    candidate_meaning="whole arrived top4 plus coverage/fallback; request p uses declared execution-block units, normalized observed EMA; state218/action57, flag52 actual same-rule teacher",
    wait="resource only; arrivals/AVAILABLE cancel; observed release estimate timer; aliases deduplicated",
    coupling="JP09/JP05/JNONE jointphysical; ATC_ROUTE primaryrequest; ATC_SCORE_RESIDUAL currentATClogscore prior withNNresidual, Greedycomparisononly; operational selection mask separate from physical",
    action_extra="two job current ATC rankindex/(Q-1) and logscoregap tobest; no future queue simulation"))


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


PUBLIC_FIELDS={"id","task","priority","ordinal","arrival_ns","deadline_offset_ns","work_units"}
VERSION="atc-coupling-event-exploration-v1"

def phase_estimate(estimates,q,b):
    values=estimates.get(p.key(q,b))
    if values is None:return None
    values=list(values)
    values[1]*=q.get("work_units",1)
    return values

def durations(estimates,q,b):
    values=phase_estimate(estimates,q,b)
    if values is None or len(values)!=5 or any(not math.isfinite(v) or v<0 for v in values) or sum(values)<=0:return None
    response=sum(values[:2 if q["priority"]=="urgent" else 3])
    return (sum(values)/1e9,response/1e9) if response>0 else None

def validate_engine(config,vectors,requests,policy,settings,provider):
    if config.get("protocol")!=VERSION or getattr(provider,"protocol",None)!=VERSION or provider.policy!=p.PPO_POLICY:
        raise ValueError("separate heterogeneity opt-in contract")
    if settings["mode"]!="explore" or any(settings[k]!=0 for k in ("decision_ns","record_ns","dispatch_ns")):
        raise ValueError("zero incremental PC overhead contract")
    if any(settings[k]!=1 for k in ("interference","predicted_interference","estimate_factor","load_prepare_factor","load_callback_factor")):
        raise ValueError("unregistered rate or phase multiplier")
    if set(config["cells"])!=set(p.CELLS) or set(vectors["requests"])!={q["id"] for q in requests}:raise ValueError("realization coverage")
    for q in requests:
        cap=1.5e9 if q["priority"]=="urgent" else 6e9
        if set(q)!=PUBLIC_FIELDS or type(q["work_units"]) is not int or not 1<=q["work_units"]<=3 or not 35e9<=q["arrival_ns"]<120e9 or not 0<q["deadline_offset_ns"]<=cap:
            raise ValueError("public hint/deadline/arrival contract")
        if set(vectors["requests"][q["id"]])!=set(p.backends(q)):raise ValueError("unsupported/missing realized route")
        for b in p.backends(q):
            vv=vectors["requests"][q["id"]][b]
            if len(vv)!=4 or any(len(x["durations_ns"])!=5 or any(not math.isfinite(v) or v<0 for v in x["durations_ns"]) for x in vv):
                raise ValueError("invalid intact empirical realization")


ATC_REFERENCE_PATH={"classification":"CPU","detection":"CPU"}  # canonical ATC p/r reference, CPUclass n4 weak

def route_order(q,backend):return backend!="CPU"  # fixed canonical order; no Greedy or finish minimization

def representative(estimates,q):
    backend=ATC_REFERENCE_PATH[q["task"]]
    ds=durations(estimates,q,backend)
    return (ds,backend) if ds is not None else (None,None)


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
        job=min(options,key=lambda j:route_order(q,j["backend"]));jobs.append(job)
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


def actual_rule(e,queue,estimates):
    by={q["id"]:q for q in queue}
    for rid in e["ranked_ids"]:
        options=[i for i,a in enumerate(e["actions"]) if e["mask"][i] and a["kind"]=="single" and a["jobs"][0]["request_id"]==rid]
        if not options:continue
        i=min(options,key=lambda i:route_order(by[rid],e["actions"][i]["jobs"][0]["backend"]));chosen=e["actions"][i]["jobs"][0]
        if chosen["backend"]=="GPU":
            pairs=[j for j,a in enumerate(e["actions"]) if e["mask"][j] and a["kind"]=="bundle" and a["jobs"][0]==chosen]
            if pairs:
                order={r:k for k,r in enumerate(e["ranked_ids"])}
                return min(pairs,key=lambda j:order[e["actions"][j]["jobs"][1]["request_id"]])
        return i
    return e["base"]


_full_candidate_bank=bank

def bank(queue,lanes,now,estimates,settings=DEFAULT,sequencing="ATC"):
    e=_full_candidate_bank(queue,lanes,now,estimates,settings,sequencing)
    # Physical masks/actions/request freedom are unchanged. Only the actual
    # same-rule teacher and its semantic flag/fallback replace full-EDD L0.
    if e["mask"].any():
        e["base"]=actual_rule(e,queue,estimates)
        if not e["mask"][e["base"]]:raise ValueError("illegal ATC teacher")
    return e

ARMS=("JP09","JP05","JNONE","ATC_ROUTE","ATC_SCORE_RESIDUAL")
PRIORS={"JP09":.9,"JP05":.5,"JNONE":None,"ATC_ROUTE":None,"ATC_SCORE_RESIDUAL":None}

def restrict(e,queue,lanes,estimates,coupling):
    if coupling not in ARMS:raise ValueError("unregistered coupling")
    e["physical_mask"]=e["mask"].copy()
    if coupling in ("JP09","JP05","JNONE","ATC_SCORE_RESIDUAL") or not e["mask"].any():return e
    allowed=np.zeros(SLOTS,dtype=bool)
    teacher=e["actions"][e["base"]]
    allowed[e["base"]]=True
    if coupling=="ATC_ROUTE" and teacher["kind"]!="resource_wait":
        primary=teacher["jobs"][0]["request_id"]
        for i,action in enumerate(e["actions"]):
            if action and e["physical_mask"][i] and action["kind"] in ("single","bundle") and any(j["request_id"]==primary for j in action["jobs"]):allowed[i]=True
    e["mask"] &= allowed
    if not e["mask"][e["base"]] or np.any(e["mask"] & ~e["physical_mask"]):raise ValueError("coupling added illegal action")
    return e

_joint_bank=bank
def bank(queue,lanes,now,estimates,settings=DEFAULT,sequencing="ATC",coupling="JP09"):
    return restrict(_joint_bank(queue,lanes,now,estimates,settings,sequencing),queue,lanes,estimates,coupling)

class Controller(hybrid.ThermalMixin, p.Controller):
    protocol=VERSION
    def __init__(self, frozen, initial, network=None, deterministic=True, generator=None, mode=POLICY, settings=DEFAULT, sequencing="ATC", coupling="JP09"):
        super().__init__(frozen,initial,p.profile(frozen),p.PPO_POLICY)
        self.policy = p.PPO_POLICY  # unchanged legacy opt-in transport; new public/schema ID
        self.public_policy = mode; self.schema_id = SCHEMA
        self.sequencing=sequencing
        if coupling not in ARMS:raise ValueError("unknown coupling")
        self.coupling=coupling
        self.settings = settings; self.network = network; self.deterministic = deterministic
        self.generator = generator; self.events=[]; self.snapshots=[]; self.tickets={}; self.responses={}
        self.receipts={}; self.phase_cursors={}; self.pending=None; self.hold=None
        self.event_seq=0; self.stats=dict(fallback=0, pair_cancelled=0, wait_selected=0, wait_cancelled=0,
                                       duplicate_callbacks=0, ATC_EDD_bank_same=0, ATC_EDD_bank_different=0)
        self.times=[]; self.grid={}; self.online_forecast_calls=0
        self.observations={}; self.last_key=None; self.model_errors=0; self.model_disabled=False

    def validate_public(self,queue,lanes,now):
        if any(q["arrival_ns"]>now for q in queue):raise ValueError("future ticket")
        if any(set(l)!={"request","phase","since","dispatch"} for l in lanes.values()):raise ValueError("private lane data")
        for q in queue:p.backends(q)

    def on_public_event(self, event):
        if set(event) - {"at_ns","event_seq","request_id","backend","event","ticket"}:
            raise ValueError("private public-event fields")
        if event["event_seq"] != self.event_seq+1:
            raise ValueError("missing/duplicate/out-of-order public event")
        self.event_seq += 1; self.events.append(copy.deepcopy(event))
        rid, kind, now = event["request_id"], event["event"], event["at_ns"]
        if kind == "arrived":
            q = copy.deepcopy(event["ticket"])
            if rid in self.tickets or set(q) != PUBLIC_FIELDS or q["arrival_ns"] > now:
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
                ds[1]/=q["work_units"]  # normalize observed execution block before shared-base EMA
                cell=p.key(q,receipt["backend"]); alpha=self.settings.ema
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
            q=dict(task=task,priority="urgent" if task=="classification" else "normal")
            ds=durations(self.estimates,q,b)
            state[7+j]=sum((durations(self.estimates,x,b) or (0,0))[0] for x in groups[task])/6
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
        for j,(priority,kind) in enumerate((("urgent","request"),("urgent","original"),("normal","request"),("normal","original"))):
            arrived=[q for q in self.tickets.values() if q["priority"]==priority]
            misses=0
            for q in arrived:
                delta=q["deadline_offset_ns"] if kind=="request" else (1.5e9 if priority=="urgent" else 6e9)
                response=self.responses.get(q["id"])
                misses += (round(response["response_ms"]*1e6)>delta if response else now>q["arrival_ns"]+delta)
            state[24+j]=misses/max(len(arrived),1)
        for slot,q in enumerate(e["slots"]):
            if q is None:continue
            scale=q["deadline_offset_ns"]/1e9; offset=28+20*slot
            values=[1.,float(q["task"]=="classification"),float(q["task"]=="detection"),float(q["priority"]=="urgent"),float(q["priority"]=="normal"),
                (now-q["arrival_ns"])/1e9/scale,(due(q)-now)/1e9/scale,
                (self.settings.urgent_weight if q["priority"]=="urgent" else self.settings.normal_weight)/2,
                float("CPU" in p.backends(q)),float("GPU" in p.backends(q))]
            for b in ("CPU","GPU"):
                ds=durations(self.estimates,q,b) if b in p.backends(q) else None
                values += [ds[0]/6,ds[1]/scale,1.] if ds else [0.,0.,0.]
            _,b=representative(self.estimates,q); obs=self.observations.get(p.key(q,b),{}) if b else {}
            values += [math.log1p(obs.get("n",0))/math.log(97),(now-obs["at_ns"])/6e9 if "at_ns" in obs else 0.]
            values += [q["work_units"]/3,1.]
            state[offset:offset+20]=values
        for j,b in enumerate(("CPU","GPU")):
            l=lanes[b]; q=l["request"]; o=28+20*REQUEST_SLOTS+15*j
            state[o]=float(q is not None)
            phase=PHASES.index(l["phase"]) if q else 5
            state[o+4+phase]=1.
            if q:
                state[o+1:o+4]=[float(q["task"]=="classification"),float(q["task"]=="detection"),float(q["id"] in self.responses)]
                state[o+10:o+12]=[(now-l["dispatch"])/6e9,(now-l["since"])/6e9]
                ds=phase_estimate(self.estimates,q,b); end=l["dispatch"]+sum(ds)
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
                vals += [q["work_units"]/3,1.]
                assert len(vals)==24
                v[4+24*j:28+24*j]=vals
            v[52]=float(i==e["base"])
        ranks={rid:i for i,rid in enumerate(e["ranked_ids"])}
        known=[v for v in e["scores"].values() if v is not None]
        best=min(known) if known else 0.
        for i,action in enumerate(e["actions"]):
            if action is None:continue
            for j,job in enumerate(action.get("jobs",[action.get("target")])):
                rid=job["request_id"];score=e["scores"][rid]
                vectors[i,53+2*j]=ranks[rid]/max(len(queue)-1,1)
                vectors[i,54+2*j]=score-best if score is not None else 10.
        state=np.clip(state,-10,10); vectors=np.clip(vectors,-10,10)
        if not np.isfinite(state).all() or not np.isfinite(vectors).all():raise ValueError("nonfinite encoder")
        return dict(state=state,candidates=vectors,mask=e["mask"].copy(),physical_mask=e["physical_mask"].copy(),schema_id=self.schema_id,coupling=self.coupling)

    def rule(self,e,queue,lanes):
        return e["base"]  # teacher fixed before applying the coupling envelope

    def __call__(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        started=time.perf_counter(); self.validate_public(queue,lanes,now)
        if any(set(q)!=PUBLIC_FIELDS for q in queue):
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
        e=bank(queue,lanes,now,self.estimates,self.settings,self.sequencing,self.coupling)
        after_bank=time.perf_counter()
        other=bank(queue,lanes,now,self.estimates,self.settings,"EDD" if self.sequencing=="ATC" else "ATC",self.coupling)
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
                if getattr(self.network,"schema_id",None)!=SCHEMA or getattr(self.network,"coupling",None)!=self.coupling:raise ValueError("model schema/coupling mismatch")
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
                    ds=phase_estimate(self.estimates,l["request"],b);end=l["dispatch"]+sum(ds)
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
