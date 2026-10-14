"""Standalone same-case fixed-inference CLI; rejects overwrite, never trains."""
import os
for k in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"):os.environ[k]="1"
import argparse,json
from pathlib import Path
from common import VENDOR,read,gzsave
import cases,candidates,plant,audit,ppo
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--device",choices=("A24","S26"),required=True)
    p.add_argument("--layer",required=True)
    p.add_argument("--case",type=int,required=True)
    p.add_argument("--split",default="FINAL",choices=("FINAL","DEV","TRAIN"))
    p.add_argument("--replicate",type=int,default=0)
    p.add_argument("--policy",default="ATC",choices=("PPO",*("FIFO_READY","RR_READY","GREEDY_READY_V17","SPT","WSPT","EDD","LST","ATC","ENERGY_EDD","THERMAL_EDD")))
    p.add_argument("--checkpoint",type=Path)
    p.add_argument("--alpha",type=float,default=1.)
    p.add_argument("--wait-rule",action="store_true")
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError("output exists")
    profile=read(VENDOR/"profiles"/f"{a.device}_G36_{a.layer}.json")
    proxy=read(VENDOR/"profiles"/f"{a.device}_G36_M1_coupled.json")
    qs=cases.requests(profile,a.case,a.split,a.replicate)
    if a.policy=="PPO":
        if not a.checkpoint:raise ValueError("checkpoint required")
        learner=ppo.Learner.load(a.checkpoint)
        if learner.device!=a.device:raise ValueError("wrong-device weights")
        ctl=learner.controller(a.alpha)
    else:ctl=candidates.Rule(a.policy,a.wait_rule)
    raw=plant.simulate(profile,qs,ctl,proxy,cases.environment_seed(a.split,a.replicate))
    raw["physical_audit"]=audit.physical(raw,qs);gzsave(a.out,raw)
    print(json.dumps(raw["metrics"],ensure_ascii=False))
if __name__=="__main__":main()
