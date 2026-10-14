"""Physical/event/reward invariants; no fabricated unsupported-path passes."""
import math, copy
import numpy as np
from common import H120,H180
def physical(raw,requests):
    events=raw["events"];owners={};seen=set();last=-1;phase={};avail={};responses={}
    for e in events:
        t=e["time_ns"];rid=e["id"];b=e["backend"];p=e["phase"]
        if t<last:raise ValueError("nonmonotonic event clock")
        last=t
        if p=="ASSIGNED":
            if rid in seen or b in owners:raise ValueError("duplicate request/lane")
            seen.add(rid);owners[b]=rid
        elif owners.get(b)!=rid:raise ValueError("owner lost before AVAILABLE")
        phase[rid]=p
        if p=="AVAILABLE":avail[rid]=t;del owners[b]
        if len(owners)>2:raise ValueError("three lanes")
        if len(owners)==2:
            rows={r["id"]:r for r in raw["ledger"]}
            labels={(rows[r]["task"],bk) for bk,r in owners.items()}
            legal=[{("classification","GPU"),("detection","CPU")}]
            if raw["device"]=="S26":legal.append({("classification","NPU"),("detection","CPU")})
            if labels not in legal:raise ValueError("unsupported parallel pair")
    for q,r in zip(requests,raw["ledger"]):
        if q["id"]!=r["id"]:raise ValueError("ledger identity")
        if r["status"]=="succeeded":
            if avail.get(r["id"])!=r["lane_available_ns"] or avail[r["id"]]>H120:raise ValueError("missing actual AVAILABLE")
            if not r["dispatch_ns"]<=r["response_at_ns"]<=avail[r["id"]]:raise ValueError("response/ownership contract")
            if r["backend"] in ("GPU","NPU") and r["task"]=="detection":raise ValueError("unsupported detection")
        if q["arrival_ns"]>r.get("dispatch_ns",H120):raise ValueError("future dispatch")
    if not all(x["physical"] and x["future_input"] is False for x in raw["audit"]):raise ValueError("physical mask audit")
    if raw["wait_used_ns"]>12e9:raise ValueError("WAIT cap")
    for c in (raw["cost_120"],raw.get("cooling_180") or {}):
        for k in ("thermal_energy_balance_error_j","energy_component_sum_error_j"):
            if abs(c.get(k,0))>1e-6:raise ValueError("power/heat balance")
    if raw["metrics"]["incomplete"]==0:
        samples=raw["cost_samples"]
        if samples[-1]["time_ns"]!=H180:raise ValueError("tail omitted")
        if abs(samples[-1]["ap_area"]/145-raw["metrics"]["mean_ap_c"])>1e-7:raise ValueError("meanAP window")
    return dict(legal_events=True,AVAILABLE=True,response_separate=True,no_future_input=True,
                max2=True,energy_heat_balance=True,total_requests=len(requests))

def compare_metrics(a,b):
    for k in ("energy_prefix_j","energy_180_j","mean_ap_c"):
        va,vb=a["metrics"].get(k),b["metrics"].get(k)
        if va is None or vb is None:
            if va!=vb:raise ValueError("null mismatch")
        elif abs(va-vb)>1e-6:raise ValueError("metric mismatch: "+k)
    for k in ("ledger","events"):
        if a[k]!=b[k]:raise ValueError("event contract changed: "+k)
    return True
