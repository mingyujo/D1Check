"""Post-episode labels only. Failed service gate removes negative interval costs."""
import numpy as np
from tools import d1_atc_waitlink_targets as base

ARMS=("CONTROL","COST5","GATED_COST5")
SERVICE=("incomplete","urgent_failure","urgent_original_cap_failure",
         "normal_failure","normal_original_cap_failure","urgent_p95_ms")


def service_gate(actual,reference):
    for row in (actual,reference):
        for key in ("completed","planned","completed_work_units","planned_work_units",*SERVICE):
            if key not in row or row[key] is None or not np.isfinite(float(row[key])):
                raise ValueError("invalid service gate value "+key)
    return (actual["completed"]==actual["planned"] and actual["completed_work_units"]==actual["planned_work_units"]
            and all(actual[key]==0 for key in SERVICE if key!="urgent_p95_ms")
            and actual["urgent_p95_ms"]<=reference["urgent_p95_ms"])


def remove_negative_intervals(suffix):
    suffix=np.asarray(suffix,dtype=np.float64)
    intervals=np.concatenate((suffix[:-1]-suffix[1:],suffix[-1:]))
    intervals=np.maximum(intervals,0.)
    return np.cumsum(intervals[::-1])[::-1]


def canonical_energy(actual,reference,frozen,t):
    def segments(raw):
        values=raw["segments"]
        if not values:raise ValueError("missing physical energy segments")
        end=0.
        for item in values:
            if not np.isfinite([item["start_s"],item["end_s"]]).all() or abs(item["start_s"]-end)>1e-8 or item["end_s"]<=end:
                raise ValueError("physical segment coverage/order")
            if item["state"]!="idle" and item["state"] not in frozen["energy_increment_w"]:raise ValueError("unknown physical power state")
            end=item["end_s"]
        if end<120.:raise ValueError("physical energy horizon missing")
        return values
    a,r=segments(actual),segments(reference)
    points=sorted({0.,120.,*(min(120.,max(0.,v[k])) for values in (a,r) for v in values for k in ("start_s","end_s"))})
    def power(state):
        value=0. if state=="idle" else frozen["energy_increment_w"][state]
        if not np.isfinite(value):raise ValueError("nonfinite physical power")
        return value
    ia=ir=0;total=0.
    for lo,hi in zip(points,points[1:]):
        mid=(lo+hi)/2
        while a[ia]["end_s"]<=mid:ia+=1
        while r[ir]["end_s"]<=mid:ir+=1
        total+=max(0.,hi-max(lo,t/1e9))*max(0.,power(a[ia]["state"])-power(r[ir]["state"]))
    return total/10.


def canonical_ap(actual,reference,t):
    def peaks(raw):
        values=[(at,value) for at,value in raw["curve"] if 35<=at<=120]
        if [at for at,_ in values]!=list(range(35,121)) or not np.isfinite([v for _,v in values]).all():
            raise ValueError("AP canonical1s grid missing/nonfinite")
        return np.maximum.accumulate([v for _,v in values])
    difference=(peaks(actual)-peaks(reference))/.1
    if difference[0]!=0.:raise ValueError("AP initial difference must be0")
    increments=np.maximum(np.diff(difference),0.)
    return float(sum(value for at,value in zip(range(36,121),increments) if at*1e9>t))


def targets(controller,raw,resident_baseline_j,reward_arm,reference):
    if reward_arm not in ARMS:raise ValueError("unregistered reward arm")
    if raw["row"]["arrival_seed"]!=reference["row"]["arrival_seed"] or raw["row"]["condition"]!=reference["row"]["condition"]:
        raise ValueError("teacher exogenous case/realization differs")
    frames,costs,valid,reward=base.targets(controller,raw,resident_baseline_j,"DROP_FLAG_WAIT1",reference)
    passed=service_gate(raw["row"],reference["row"])
    raw_costs=[float(frames[0]["target"][1]),float(frames[0]["target"][2])]
    if reward_arm=="GATED_COST5" and not passed:
        steps=[step for step in controller.snapshots if "model_error" not in step]
        for frame,step in zip(frames,steps):
            frame["target"][1]=canonical_energy(raw,reference,controller.frozen,step["now_ns"])
            frame["target"][2]=canonical_ap(raw,reference,step["now_ns"])
        costs=costs.copy();costs[0]=frames[0]["target"][1];costs[1]=frames[0]["target"][2]
    for frame in frames:frame["post_episode_service_gate"]=passed
    reasons=[key for key in SERVICE if key!="urgent_p95_ms" and raw["row"][key]!=0]
    if raw["row"]["completed"]!=raw["row"]["planned"] or raw["row"]["completed_work_units"]!=raw["row"]["planned_work_units"]:reasons.append("full_or_units_incomplete")
    if raw["row"]["urgent_p95_ms"]>reference["row"]["urgent_p95_ms"]:reasons.append("urgent_p95_ms")
    frames[0]["costguard_diagnostics"]=dict(reward_arm=reward_arm,gate_pass=passed,failure_reasons=reasons,
        raw_E10_cost=raw_costs[0],raw_AP01_cost=raw_costs[1],gated_E10_cost=float(frames[0]["target"][1]),gated_AP01_cost=float(frames[0]["target"][2]),
        gate_applied=reward_arm=="GATED_COST5" and not passed,proxy="E physical-rate positive difference0..120; AP runningpeak-difference positive1s increments35..120; postlabel only")
    return frames,costs,valid,reward
