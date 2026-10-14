"""Explicit S26 M6 development profiles, isolated runtime and frozen inference."""
import argparse,gzip,json
from pathlib import Path
import torch
from tools import d1_sched_dynamics_plant as original
from tools import d1_sched_dynamics_policy as policy
from tools import d1_sched_dynamics_ppo as rl
from tools import d1_sched_dynamics_study as helpers
from tools import d1_s26_m6_plant as candidate

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,required=True);p.add_argument('--requests',type=Path,required=True)
    p.add_argument('--policy',choices=(*policy.RULES,'PPO'),default='ATC');p.add_argument('--checkpoint',type=Path);p.add_argument('--dependencies',type=Path)
    p.add_argument('--environment-seed',type=int,default=963230101);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    if a.out.exists():raise ValueError('existing output preserved; choose a fresh path')
    profile=read(a.profile);data=read(a.requests);requests=data if isinstance(data,list) else data['requests']
    if a.policy=='PPO':
        if not a.checkpoint or not a.dependencies:p.error('fixed PPO requires checkpoint/dependencies')
        learner=rl.Learner.load(a.checkpoint,read(a.dependencies));before=rl.canonical(learner.snapshot());inner=learner.controller(deterministic=True,collect=False)
    else:inner=policy.Controller(a.policy,helpers.affinity(profile))
    controller=helpers.AuditedController(inner);plant=candidate if profile['cost_anchor']['abi']==candidate.COST_ABI else original
    result=plant.simulate(profile,requests,controller,environment_seed=a.environment_seed)
    if controller.errors:raise ValueError('policy errors/fallback')
    if a.policy=='PPO' and before!=rl.canonical(learner.snapshot()):raise ValueError('frozen PPO changed')
    result.update(policy=a.policy,audit=controller.audit,decisions=controller.decisions,online_learning=False,independent_confirmation=False,development_only=True,model_errors=controller.errors)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    if a.out.suffix=='.gz':
        with gzip.open(a.out,'wt',encoding='utf-8') as f:json.dump(result,f,allow_nan=False,separators=(',',':'))
    else:a.out.write_text(json.dumps(result,allow_nan=False),encoding='utf-8')
    print(json.dumps(result['metrics']))

if __name__=='__main__':main()
