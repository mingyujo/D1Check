"""Dual device trend simulation with supplied frozen profile and fixed inference."""
import argparse,gzip,json
from pathlib import Path
import torch
from tools import d1_dual_trend27_runtime as plant
from tools import d1_sched_dynamics_policy as policy
from tools import d1_sched_dynamics_ppo as rl
from tools import d1_sched_dynamics_study as helpers
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,required=True);p.add_argument('--requests',type=Path,required=True);p.add_argument('--policy',choices=(*policy.RULES,'PPO'),default='ATC');p.add_argument('--checkpoint',type=Path);p.add_argument('--dependencies',type=Path);p.add_argument('--environment-seed',type=int,default=963270101);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('existing output preserved')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True);profile=read(a.profile);data=read(a.requests);requests=data if isinstance(data,list)else data['requests']
    if a.policy=='PPO':
        if not a.checkpoint or not a.dependencies:p.error('fixed PPO needs checkpoint and dependencies')
        learner=rl.Learner.load(a.checkpoint,read(a.dependencies));before=rl.canonical(learner.snapshot());inner=learner.controller(deterministic=True,collect=False)
    else:inner=policy.Controller(a.policy,helpers.affinity(profile))
    ctrl=helpers.AuditedController(inner);result=plant.simulate(profile,requests,ctrl,environment_seed=a.environment_seed)
    if ctrl.errors:raise ValueError('controller model error')
    if a.policy=='PPO':assert before==rl.canonical(learner.snapshot())
    result.update(policy=a.policy,audit=ctrl.audit,decisions=ctrl.decisions,model_errors=ctrl.errors,online_learning=False)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    if a.out.suffix=='.gz':
        with gzip.open(a.out,'wt',encoding='utf-8')as f:json.dump(result,f,allow_nan=False,separators=(',',':'))
    else:a.out.write_text(json.dumps(result,allow_nan=False),encoding='utf-8')
    print(json.dumps(result['metrics']))
if __name__=='__main__':main()
