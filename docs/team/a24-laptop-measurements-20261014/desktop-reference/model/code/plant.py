"""Frozen 35/36 physics; private engine behind a narrow observation interface."""
import copy, math, sys, time
import numpy as np
from common import VENDOR,H120,H180
sys.path.insert(0,str(VENDOR))
from tools import d1_grounded36 as g
from tools import d1_measured35 as measured
from tools import d1_sim_complete33 as contract
from tools import d1_sched_dynamics_plant as base
from candidates import BACKENDS

class PublicView:
    __slots__=("_engine","_proxy","wait_used","last_release","_cached","_cache_key","_arrived")
    def __init__(self,engine,proxy):
        self._engine=engine;self._proxy=proxy;self.wait_used=0;self.last_release={b:0 for b in BACKENDS};self._cached=None;self._cache_key=None;self._arrived={}
    @property
    def now(self):return self._engine.now
    def public(self):
        key=(self._engine.now,self._engine.decision_revision,len(self._arrived))
        if key!=self._cache_key:
            self._cached=self._engine.public();self._cache_key=key
            counts={p:0 for p in ("urgent","normal")};miss={p:0 for p in counts}
            for q in self._arrived.values():
                p=q["priority"];counts[p]+=1
                r=self._engine.records.get(q["id"],{});response=r.get("response_ns")
                if q["arrival_ns"]+q["deadline_offset_ns"]<=self.now and (response is None or response>q["deadline_offset_ns"]):
                    miss[p]+=1
            self._cached["known_arrival_counts"]=counts
            self._cached["observed_deadline_miss_fraction"]={p:miss[p]/max(counts[p],1) for p in counts}
        return self._cached
    def arrived(self,q):
        if q["arrival_ns"]>self.now or q["id"] in self._arrived:raise ValueError("future/duplicate arrival counter")
        self._arrived[q["id"]]=q
    def routes(self,q):return self._engine.routes(q)
    def estimate(self,q,b):
        ds=self._engine.estimate(q,b,[(q,b)])
        if len(ds)!=5 or any(not math.isfinite(v) or v<0 for v in ds) or sum(ds)<=0:raise ValueError("public estimate")
        return ds
    def feasible(self,q,b):return self._engine.feasible([(q,b)])
    def feasible_pair(self,q,b,partner,route):
        return self._engine.feasible([(q,b),(partner,route)])
    def local_proxy(self,q,b,ds):
        pub=self.public()
        if pub["device"]=="A24":
            w=self._proxy["cost_anchor"]["energy_increment_w"][q["task"]+"_"+b]
        else:
            coeff=self._proxy["grounded36"]["power_coefficients"]
            i={("classification","CPU"):4,("detection","CPU"):5,("classification","GPU"):6,("classification","NPU"):7}[q["task"],b]
            cpu=pub["recent_activity"]["CPU"]
            w=max(0.,coeff[i])/(1+4*cpu) + max(0.,coeff[10])
        return max(0.,pub["power_w"])*sum(ds)/1e9+max(0.,w)*ds[1]/1e9,max(0.,w)

def simulate(profile,requests,controller,proxy,seed=0,split="confirm",step_s=None):
    if len(requests)>1200 or len({q["id"] for q in requests})!=len(requests):raise ValueError("roster")
    for q in requests:
        contract.validate(q)
        if q.get("work_units",1)!=1:raise ValueError("unit1 support")
    cls=g.Device if "grounded36" in profile else measured.A24Device if profile["device"]=="A24" else measured.S26Device
    dev=cls(profile,split=split,environment_seed=seed,npu=True,step_s=step_s)
    view=PublicView(dev,proxy);pending=sorted(requests,key=lambda q:(q["arrival_ns"],q["ordinal"],q["id"]))
    cursor=0;waiting=[];revision=-1;timer=None;wait_start=None;wait_events=[];samples=[];previous=dict(time_ns=0,energy_j=0.,ap_area=0.)
    def sample(reason="integration"):
        nonlocal previous
        c=dev.current_cost();now=dev.now;area=dev._ap_area
        active_area=area-dev._area_at35 if dev._area_at35 is not None and now>=35e9 else 0.
        row=dict(time_ns=now,energy_j=c["energy_window_j"],ap_area=active_area,reason=reason)
        if reason=="dispatch":row["decision_index"]=len(controller.frames)-1 if controller.frames else None
        if samples and samples[-1]["time_ns"]==now and samples[-1]["energy_j"]==row["energy_j"] and samples[-1]["ap_area"]==row["ap_area"]:return
        samples.append(row)
    sample()
    def stop_wait(reason):
        nonlocal timer,wait_start
        if timer is not None:
            elapsed=dev.now-wait_start;view.wait_used+=elapsed
            wait_events.append(dict(time_ns=dev.now,event="WAIT_END",elapsed_ns=elapsed,reason=reason))
            timer=wait_start=None
    while dev.now<H120:
        dev.advance(dev.now);arrived=False
        while cursor<len(pending) and pending[cursor]["arrival_ns"]<=dev.now:
            waiting.append(pending[cursor]);view.arrived(pending[cursor]);cursor+=1;arrived=True
        changed=revision!=dev.decision_revision or any(q["arrival_ns"]+q["deadline_offset_ns"]==dev.now for q in waiting)
        if timer is not None and (arrived or changed or dev.now>=timer):
            stop_wait("timer" if dev.now>=timer and not arrived and not changed else "event")
            changed=True  # Timer expiry itself is a decision event, even with no lane/sensor update.
        if waiting and timer is None and (arrived or changed):
            revision=dev.decision_revision;tick=time.perf_counter_ns()
            action=controller.choose(view,waiting)
            controller.decisions[-1]["total_decision_us"]=(time.perf_counter_ns()-tick)/1000
            q,b,t=action["request"],action["backend"],action["wait_ns"]
            if q:
                if not view.feasible(q,b):raise ValueError("stale/illegal dispatch")
                dev.dispatch([(q,b)]);waiting=[r for r in waiting if r["id"]!=q["id"]];sample("dispatch");continue
            if t:
                if t<=0 or view.wait_used+t>12e9:raise ValueError("WAIT cap")
                timer=dev.now+t;wait_start=dev.now
                wait_events.append(dict(time_ns=dev.now,event="WAIT_START",quantum_ns=t))
        if cursor==len(pending) and not waiting and not dev._work:break
        targets=[H120]
        if cursor<len(pending):targets.append(pending[cursor]["arrival_ns"])
        event=dev.next_event()
        if event is not None:targets.append(event)
        if timer is not None:targets.extend([timer,dev._next_thermal_ns,dev._next_power_ns])
        targets += [q["arrival_ns"]+q["deadline_offset_ns"] for q in waiting if q["arrival_ns"]+q["deadline_offset_ns"]>dev.now]
        to=min(t for t in targets if t>dev.now);owners={b:(v["request"]["id"] if v else None) for b,v in dev._owners.items()}
        dev.advance(to);sample()
        for b in BACKENDS:
            if owners[b] and not dev._owners[b]:view.last_release[b]=dev.now
    service_end=dev.now;dev.advance(H120);sample();stop_wait("horizon")
    ledger=[]
    for q in requests:
        r=copy.deepcopy(dev.records.get(q["id"],dict(q,status="unfinished")))
        if r["status"]=="running":r["status"]="unfinished"
        ledger.append(r)
    m=contract.active_metrics(ledger,base.old.metrics(ledger),H120)
    c120=copy.deepcopy(dev.current_cost());complete=m["incomplete"]==0
    if not any(dev._owners.values()):
        cooling=copy.deepcopy(dev.observe_cooling());sample()
    else:cooling=None
    m.update(energy_prefix_j=c120["energy_window_j"],energy_180_j=cooling["energy_window_j"] if complete and cooling else None,
             energy_j=c120["energy_window_j"] if complete else None,mean_ap_c=cooling["mean_after35_c"] if complete and cooling else None,
             peak_ap_c=cooling["peak_after35_c"] if complete and cooling else None,
             mean_ap_0_120_c=c120["mean_ap_c"],peak_ap_0_120_c=c120["peak_ap_c"],
             completed_work_units=sum(r.get("work_units",1) for r in ledger if r["status"]=="succeeded"),
             planned_work_units=sum(r.get("work_units",1) for r in ledger))
    return dict(schema="ratr37-v2",profile=profile["name"],device=dev.device,split=split,environment_seed=seed,
                metrics=m,ledger=ledger,events=dev.events,service_end_ns=service_end,cost_120=c120,cooling_180=cooling,
                cost_samples=samples,cost_trace=dev.cost_trace,wait_events=wait_events,wait_used_ns=view.wait_used,
                audit=controller.audit,decisions=controller.decisions,hardware_validated=False,strict_eligible=False,
                online_learning=False,physical_evidence="M0/M1/M2 frozen evidence grade")
