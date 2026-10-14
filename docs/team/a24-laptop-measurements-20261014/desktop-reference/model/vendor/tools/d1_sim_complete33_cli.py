"""Same explicit CLI for A24/S26, measured/exploratory, active deadlines."""
import argparse,gzip,json
from pathlib import Path
import torch
from tools import d1_sim_complete33 as plant
from tools import d1_sched_dynamics_policy as policy
from tools import d1_sched_dynamics_ppo as rl
from tools import d1_sched_dynamics_study as helpers
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,required=True);p.add_argument('--requests',type=Path,required=True);p.add_argument('--policy',choices=(*plant.RULES,'PPO_TRANSFER'),default='ATC');p.add_argument('--checkpoint',type=Path);p.add_argument('--dependencies',type=Path);p.add_argument('--environment-seed',type=int,default=963330101);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('existing output preserved')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True);profile=read(a.profile);data=read(a.requests);qs=data if isinstance(data,list)else data['requests']
    if a.policy=='PPO_TRANSFER':
        if not a.checkpoint or not a.dependencies:p.error('fixed transfer needs checkpoint and dependencies')
        learner=rl.Learner.load(a.checkpoint,read(a.dependencies));before=rl.canonical(learner.snapshot());inner=learner.controller(deterministic=True,collect=False)
    elif a.policy in('ENERGY_EDD','THERMAL_EDD'):inner=plant.CostController(a.policy)
    else:inner=policy.Controller(a.policy,helpers.affinity(profile))
    ctrl=helpers.AuditedController(inner);r=plant.simulate(profile,qs,ctrl,environment_seed=a.environment_seed);assert not ctrl.errors;helpers.physical_audit(r,qs)
    if a.policy=='PPO_TRANSFER':assert before==rl.canonical(learner.snapshot())
    r.update(policy=a.policy,audit=ctrl.audit,decisions=ctrl.decisions,online_learning=False);a.out.parent.mkdir(parents=True,exist_ok=True)
    if a.out.suffix=='.gz':
        with gzip.open(a.out,'wt')as f:json.dump(r,f,allow_nan=False,separators=(',',':'))
    else:a.out.write_text(json.dumps(r,allow_nan=False),encoding='utf-8')
    print(json.dumps(r['metrics']))
if __name__=='__main__':main()
