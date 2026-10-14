"""Current observations only; actual ATC shortlist and shared physical actions."""
import math, time
import numpy as np
from common import H120, digest
BACKENDS=("CPU","GPU","NPU")
PHASES=("ASSIGNED","EXECUTING","OUTPUT_READY","PERSISTED","WORKER_RELEASED")
SPEC=dict(version="ratr37-v2-causal-24x24-resource3x12-global24-action80x16",
          candidates="ATC12 or EDD12 + same mandatory ready/cheap/oldest/minslack supplements <=24",
          physical="same-time single commit; max2 C_GPU/NPU+D_CPU; nonpreemptive actual AVAILABLE",
          wait="50/200/1000ms, actual total<=12s; per-request public slack guard; resource WAIT separate",
          state=[24,24,3,12,24],actions=[80,16],policy_inputs="observed only; nominal public cost proxy",
          atc="log(w/p_occ)-max(d-now-p_resp,0)/(k*mean_p_occ)",k=2.,weights=[2.,1.])
SPEC["causal_service_history"]=dict(global8="observed urgent misses / already arrived urgent",
    global19="observed normal misses / already arrived normal",
    replaced="oldest age is in mandatory request rows; remaining horizon is affine in global time",
    future_roster_denominator=False,fresh_main_weights=True)
SPEC["action9"]="0 no overlap; 1 current other owner; 2 compatible unstarted partner can co-start now; no future simulation"
SCHEMA=digest(SPEC)
def clip(x):
    return max(-10.,min(10.,float(x)))
def tie(q):
    return q["arrival_ns"],q["ordinal"],q["id"]
def response(ds,q):
    return sum(ds[:2 if q["priority"]=="urgent" else 3])
def weight(q):
    return 2. if q["priority"]=="urgent" else 1.
def slopes(history,now):
    rows=[h for h in history if now-5_000_000_000<=h["time_ns"]<=now]
    if len(rows)<2 or rows[-1]["time_ns"]==rows[0]["time_ns"]: return 0.,0.
    dt=(rows[-1]["time_ns"]-rows[0]["time_ns"])/1e9
    return (rows[-1]["ap_c"]-rows[0]["ap_c"])/dt,(rows[-1]["power_w"]-rows[0]["power_w"])/dt

def build(view,waiting,kind="ATC",allow_wait=True,alpha=1.,heat_weight=.5):
    start=time.perf_counter_ns()
    if not waiting or len(waiting)>512 or len({q["id"] for q in waiting})!=len(waiting):
        raise ValueError("nonempty distinct queue<=512 required")
    pub=view.public();now=pub["now_ns"];ordered=sorted(waiting,key=tie)
    if any(q["arrival_ns"]>now for q in ordered): raise ValueError("future arrival")
    paths={(q["id"],b):view.estimate(q,b) for q in ordered for b in view.routes(q)}
    reps={}
    for q in ordered:
        b=min(view.routes(q),key=lambda b:(response(paths[q["id"],b],q),sum(paths[q["id"],b]),BACKENDS.index(b)))
        reps[q["id"]]=(sum(paths[q["id"],b])/1e9,response(paths[q["id"],b],q)/1e9,b)
    mean_p=sum(x[0] for x in reps.values())/len(reps)
    scores={q["id"]:math.log(weight(q)/max(reps[q["id"]][0],1e-9))
            -max((q["arrival_ns"]+q["deadline_offset_ns"]-now)/1e9-reps[q["id"]][1],0)/(2*mean_p)
            for q in ordered}
    sorts=dict(ATC=sorted(ordered,key=lambda q:(-scores[q["id"]],*tie(q))),
               EDD=sorted(ordered,key=lambda q:(q["arrival_ns"]+q["deadline_offset_ns"],*tie(q))),
               SPT=sorted(ordered,key=lambda q:(min(sum(paths[q["id"],b]) for b in view.routes(q)),*tie(q))))
    ranks={k:{q["id"]:i for i,q in enumerate(qs)} for k,qs in sorts.items()}
    atc_us=(time.perf_counter_ns()-start)/1000
    legal_all=[(q,b) for q in ordered for b in view.routes(q) if view.feasible(q,b)]
    nominal={(q["id"],b):view.local_proxy(q,b,paths[q["id"],b]) for q in ordered for b in view.routes(q)}
    supplemental=[]
    def add(q):
        if q["id"] not in {r["id"] for r in supplemental}: supplemental.append(q)
    for b in BACKENDS:
        qs=[q for q,r in legal_all if r==b]
        if qs:
            add(min(qs,key=lambda q:(-scores[q["id"]],*tie(q))))
            add(min(qs,key=lambda q:(nominal[q["id"],b][0],*tie(q))))
    for priority in ("urgent","normal"):
        qs=[q for q in ordered if q["priority"]==priority]
        if qs:add(qs[0])
    if legal_all:add(min(legal_all,key=lambda x:(ranks["EDD"][x[0]["id"]],response(paths[x[0]["id"],x[1]],x[0]),BACKENDS.index(x[1])))[0])
    add(min(ordered,key=lambda q:(q["arrival_ns"]+q["deadline_offset_ns"]-now-reps[q["id"]][1]*1e9,*tie(q))))
    if kind=="FULL":selected=ordered
    else:
        selected=list(supplemental)
        for q in sorts[kind][:12]:
            if q["id"] not in {r["id"] for r in selected}:selected.append(q)
        selected.sort(key=lambda q:(ranks[kind][q["id"]],*tie(q)))
        if len(selected)>24:raise ValueError("supplement bound")
    slots=max(24,len(selected)) if kind=="FULL" else 24
    req=np.zeros((slots,24),np.float32);rid_to_slot={}
    for j,q in enumerate(selected):
        rid_to_slot[q["id"]]=j
        row=[q["task"]=="classification",q["task"]=="detection",q["priority"]=="urgent",
             (now-q["arrival_ns"])/6e9,(q["arrival_ns"]+q["deadline_offset_ns"]-now)/6e9,
             (q["arrival_ns"]+(1.5e9 if q["priority"]=="urgent" else 6e9)-now)/6e9,
             q.get("work_units",1)/3,*[b in view.routes(q) for b in BACKENDS]]
        for b in BACKENDS:
            ds=paths.get((q["id"],b));row.extend([sum(ds)/6e9,response(ds,q)/6e9] if ds else [0,0])
        row += [scores[q["id"]]/10,*[ranks[k][q["id"]]/64 for k in ("EDD","ATC","SPT")],
                .05/6,weight(q)/4,q["priority"]=="normal",1.]
        req[j]=[clip(v) for v in row]
    res=np.zeros((3,12),np.float32)
    for j,b in enumerate(BACKENDS):
        supported=b!="NPU" or pub["npu_enabled"]
        lane=pub["lanes"].get(b)
        if not supported:continue
        if lane:
            q=lane["request"];ds=lane["estimate_ns"];elapsed=now-lane["dispatch"]
            res[j]=[1,1,q["task"]=="classification",q["task"]=="detection",q["priority"]=="urgent",
                    PHASES.index(lane["phase"])/5,clip(elapsed/6e9),clip(max(sum(ds)-elapsed,0)/6e9),
                    clip(max(response(ds,q)-elapsed,0)/6e9),0,pub["recent_activity"][b],1]
        else:
            res[j]=[1,0,0,0,0,0,0,0,0,clip((now-view.last_release[b])/6e9),pub["recent_activity"][b],1]
    su,sn=[],[]
    for q in ordered:
        (su if q["priority"]=="urgent" else sn).append((q["arrival_ns"]+q["deadline_offset_ns"]-now)/6e9)
    ap_slope,w_slope=slopes(pub["observed_history"],now)
    counts=[len(ordered),len(su),len(sn),sum(q["task"]=="classification" for q in ordered),sum(q["task"]=="detection" for q in ordered)]
    service_history=pub.get("observed_deadline_miss_fraction",{"urgent":0.,"normal":0.})
    glob=np.array([clip(v) for v in [now/120e9,*[n/64 for n in counts],
          min(su,default=0),min(sn,default=0),service_history["urgent"],
          (pub["ap_c"]-30)/10,pub["power_w"]/10,pub["thermal_observation_age_s"]/6,
          pub["power_observation_age_s"]/6,ap_slope,w_slope/10,
          *[pub["recent_activity"][b] for b in BACKENDS],view.wait_used/12e9,
          service_history["normal"],alpha,alpha,heat_weight,pub["device"]=="S26"]],np.float32)
    acts=[dict(request=q,backend=b,wait_ns=0) for q in selected for b in view.routes(q)]
    acts += [dict(request=None,backend=None,wait_ns=int(t*1e6)) for t in (50,200,1000)]
    acts += [dict(request=None,backend=None,wait_ns=0)]
    a_slots=max(80,len(acts)) if kind=="FULL" else 80
    feat=np.zeros((a_slots,16),np.float32);physical=np.zeros(a_slots,bool);mask=np.zeros(a_slots,bool)
    rqindex=np.zeros(a_slots,np.int64);bkindex=np.zeros(a_slots,np.int64)
    hasexec=bool(legal_all)
    # Same operational guard for every optional-WAIT policy. It is no guarantee.
    live_slacks=[(q["arrival_ns"]+q["deadline_offset_ns"]-now)-reps[q["id"]][1]*1e9-50_000_000
                 for q in ordered if q["arrival_ns"]+q["deadline_offset_ns"]>now]
    for j,a in enumerate(acts):
        q,b=a["request"],a["backend"]
        if q:
            ds=paths[q["id"],b];energy,power=nominal[q["id"],b]
            legal=view.feasible(q,b);physical[j]=mask[j]=legal
            rqindex[j]=rid_to_slot[q["id"]];bkindex[j]=BACKENDS.index(b)
            concurrency=float(any(pub["lanes"].values()))
            pair_check=getattr(view,"feasible_pair",None)
            if legal and pair_check and not any(pub["lanes"].values()):
                partner_routes=[(other,rb) for other in ordered if other["id"]!=q["id"] and other["task"]!=q["task"]
                                for rb in view.routes(other) if rb!=b]
                if any(pair_check(q,b,other,rb) for other,rb in partner_routes):concurrency=2.
            feat[j]=[clip(v) for v in [*[b==r for r in BACKENDS],0,sum(ds)/6e9,response(ds,q)/6e9,
                 (q["arrival_ns"]+q["deadline_offset_ns"]-now-response(ds,q))/6e9,energy,
                 power/10,concurrency,0,pub["power_observation_age_s"]/6,legal,.5,
                 ranks["ATC"][q["id"]]/64,1]]
        else:
            physical[j]=True;t=a["wait_ns"]
            guard=(t>0 and allow_wait and hasexec and view.wait_used+t<=12e9
                   and now+t<=H120 and (not live_slacks or min(live_slacks)>t))
            mask[j]=guard if t else not hasexec
            feat[j,3]=1;feat[j,10]=t/1e9;feat[j,12]=1;feat[j,15]=1
    if not mask.any():raise ValueError("candidate omissions or inconsistent wait mask")
    return dict(requests=req,resources=res,global_state=glob,features=feat,mask=mask,physical_mask=physical,
                request_index=rqindex,backend_index=bkindex,actions=acts,paths=paths,ranks=ranks,scores=scores,
                nominal=nominal,selected=selected,legal_all=legal_all,
                diagnostic=dict(time_ns=now,queue=len(ordered),candidate_count=len(selected),legal_count=int(mask.sum()),
                   selected_ids=[q["id"] for q in selected],atc_top12=[q["id"] for q in sorts["ATC"][:12]],
                   atc_edd_order_same=[q["id"] for q in sorts["ATC"]]==[q["id"] for q in sorts["EDD"]],
                   atc_us=atc_us,build_us=(time.perf_counter_ns()-start)/1000-atc_us,future_input=False))

class Rule:
    def __init__(self,name="ATC",wait=False):
        self.name=name;self.wait=wait;self.cursor=0;self.errors=[];self.frames=[];self.audit=[];self.decisions=[]
    def index(self,bank):
        legal=[i for i in np.flatnonzero(bank["mask"]) if bank["actions"][i]["request"] is not None]
        if not legal:return int(np.flatnonzero(bank["mask"])[0])
        def key(i):
            q=bank["actions"][i]["request"];b=bank["actions"][i]["backend"];ds=bank["paths"][q["id"],b]
            path=(response(ds,q),sum(ds),BACKENDS.index(b));rid=q["id"];name=self.name
            if name=="FIFO_READY":return (*tie(q),*path)
            if name=="RR_READY":return (*tie(q),(BACKENDS.index(b)-self.cursor)%3)
            if name=="GREEDY_READY_V17":
                pref=min([r for r in BACKENDS if (rid,r) in bank["paths"]],key=lambda r:(sum(bank["paths"][rid,r]),BACKENDS.index(r)))
                return (*tie(q),b!=pref,*path)
            if name in ("SPT","WSPT","LST"):
                supported=[r for r in BACKENDS if (rid,r) in bank["paths"]]
                representative=min(supported,key=lambda r:(response(bank["paths"][rid,r],q),
                    sum(bank["paths"][rid,r]),BACKENDS.index(r)))
                representative_ds=bank["paths"][rid,representative]
                if name=="SPT":priority=sum(representative_ds)
                elif name=="WSPT":priority=sum(representative_ds)/weight(q)
                else:priority=q["arrival_ns"]+q["deadline_offset_ns"]-response(representative_ds,q)
                return (priority,*tie(q),*path)
            if name in ("EDD","ENERGY_EDD","THERMAL_EDD"):
                return (bank["ranks"]["EDD"][rid],*path)
            return(-bank["scores"][rid],*tie(q),*path)
        idx=min(legal,key=key)
        if self.name in ("ENERGY_EDD","THERMAL_EDD"):
            q=bank["actions"][idx]["request"];same=[i for i in legal if bank["actions"][i]["request"]["id"]==q["id"]]
            safe=[i for i in same if bank["diagnostic"]["time_ns"]+response(bank["paths"][q["id"],bank["actions"][i]["backend"]],q)<=q["arrival_ns"]+q["deadline_offset_ns"]]
            if safe:
                def costkey(i):
                    e,w=bank["nominal"][q["id"],bank["actions"][i]["backend"]]
                    return (e,w,i) if self.name=="ENERGY_EDD" else (w,e,i)
                idx=min(safe,key=costkey)
        return idx
    def choose(self,view,waiting):
        bank=build(view,waiting,"FULL",self.wait);i=self.index(bank)
        if self.wait and view.public()["ap_c"]>=view.public()["reference_ap_c"]+2:
            waits=[j for j in np.flatnonzero(bank["mask"]) if bank["actions"][j]["wait_ns"]==200_000_000]
            if waits:i=waits[0]
        a=bank["actions"][i]
        if a["request"] and self.name=="RR_READY":self.cursor=(BACKENDS.index(a["backend"])+1)%3
        self.decisions.append({**bank["diagnostic"],"chosen_index":int(i),"chosen":([a["request"]["id"],a["backend"]] if a["request"] else None),"wait_ns":a["wait_ns"]})
        self.audit.append(dict(time_ns=view.now,physical=bool(bank["physical_mask"][i]),future_input=False))
        return a
