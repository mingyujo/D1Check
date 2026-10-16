"""Offline fixed-window AP objectives; deadline-only arms contain no time reward."""
import numpy as np
from tools import d1_atc_costguard_targets as current
from tools import d1_atc_repair_targets as service
from tools import d1_atc_delta_targets as paired

ARMS=("CURRENT_COST5","DEADLINE_PEAK120","DEADLINE_MEAN120","DEADLINE_MEAN180")


def ap_mean_suffix(raw,t,end=180):
    if end not in (120,180) or not np.isfinite(t):raise ValueError("fixed AP window/cut nonfinite or unknown")
    points=[(at,value) for at,value in raw["curve"] if 35<=at<=end]
    if [at for at,_ in points]!=list(range(35,end+1)) or not np.isfinite([value for _,value in points]).all():
        raise ValueError("fixed AP grid missing/nonfinite")
    cut=max(35.,t/1e9);area=0.
    for (lo,ylo),(hi,yhi) in zip(points,points[1:]):
        begin=max(cut,lo)
        if begin>=hi:continue
        ybegin=ylo+(yhi-ylo)*(begin-lo)/(hi-lo)
        area+=(ybegin+yhi)*(hi-begin)/2
    return area/(end-35)


def targets(controller,raw,resident_baseline_j,arm,reference):
    if arm not in ARMS:raise ValueError("unregistered14 arm")
    if arm=="CURRENT_COST5":return current.targets(controller,raw,resident_baseline_j,"COST5",reference)
    for row in (raw['row'],reference['row']):
        for key in ('completed','planned','completed_work_units','planned_work_units'):
            if key not in row or row[key] is None or not np.isfinite(float(row[key])):raise ValueError('equal-work completion unknown '+key)
    if paired.signature(raw)!=paired.signature(reference) or raw["row"]["arrival_seed"]!=reference["row"]["arrival_seed"] or raw["row"]["condition"]!=reference["row"]["condition"]:
        raise ValueError("teacher case/realization differs")
    frames,costs,valid,_=service.targets(controller,raw,resident_baseline_j,"CAUSAL")
    steps=[step for step in controller.snapshots if "model_error" not in step]
    for frame,step in zip(frames,steps):
        t=step["now_ns"]
        _,ae,aa=paired.trajectory_suffix(raw,t,controller.frozen)
        _,re,ra=paired.trajectory_suffix(reference,t,controller.frozen)
        frame["target"][0]=0.;frame["target"][1]=(ae-re)/10.
        frame["target"][2]=((aa-ra)/.1 if arm=="DEADLINE_PEAK120" else
            (ap_mean_suffix(raw,t,120 if arm=="DEADLINE_MEAN120" else 180)-ap_mean_suffix(reference,t,120 if arm=="DEADLINE_MEAN120" else 180))/.1)
        frame["target"][9]=0.;frame["valid"][[0,9]]=False
        if not np.isfinite(frame["target"]).all():raise ValueError("nonfinite deadline target")
    costs=costs.copy();costs[0]=frames[0]["target"][1];costs[1]=frames[0]["target"][2];costs[8]=0.
    valid=valid.copy();valid[[0,9]]=False
    equalwork=all(row["completed"]==row["planned"] and row["completed_work_units"]==row["planned_work_units"] for row in (raw["row"],reference["row"]))
    if not equalwork:
        valid[[1,2]]=False
        for frame in frames:frame["valid"][[1,2]]=False
    frames[0]["deadline_diagnostics"]=dict(arm=arm,time_reward_valid=False,p95_valid=False,
        completion_holding_urgentarea_teacherreturn_p95_reward=0,
        mean_window=(120 if arm=="DEADLINE_MEAN120" else 180 if arm=="DEADLINE_MEAN180" else None),
        duplicate_declared_original_costs_preserved=True)
    frames[0]["deadline_diagnostics"]["equal_work_costs_valid"]=equalwork
    return frames,costs,valid,np.zeros(len(frames),dtype=np.float32)
