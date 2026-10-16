"""Run a declared V20 hypothetical landscape with rules or a frozen PPO."""
import argparse
import gzip
import json
from pathlib import Path
import torch
from tools import d1_sched_landscape_plant as plant
from tools import d1_sched_dynamics_policy as policy
from tools import d1_sched_dynamics_ppo as rl
from tools import d1_sched_dynamics_study as helpers


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--requests',type=Path,required=True)
    parser.add_argument('--policy',choices=(*policy.RULES,'PPO'),default='ATC')
    parser.add_argument('--checkpoint',type=Path)
    parser.add_argument('--dependencies',type=Path)
    parser.add_argument('--environment-seed',type=int,default=948400101)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise ValueError('existing output preserved; choose a new filename')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    profile=read(args.profile);data=read(args.requests)
    requests=data if isinstance(data,list) else data['requests']
    if args.policy=='PPO':
        if not args.checkpoint or not args.dependencies:parser.error('PPO requires fixed checkpoint and training dependencies')
        learner=rl.Learner.load(args.checkpoint,read(args.dependencies));before=rl.canonical(learner.snapshot())
        ctl=learner.controller(deterministic=True,collect=False)
    else:ctl=policy.Controller(args.policy,helpers.affinity(profile))
    result=plant.simulate(profile,requests,ctl,environment_seed=args.environment_seed)
    if ctl.errors:raise ValueError('model error or fallback:'+str(ctl.errors))
    if args.policy=='PPO' and before!=rl.canonical(learner.snapshot()):raise ValueError('frozen learner changed')
    result.update(policy=args.policy,decisions=ctl.decisions,model_errors=ctl.errors,online_learning=False,
                  checkpoint_sha=helpers.sha(args.checkpoint) if args.policy=='PPO' else None)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.suffix=='.gz':
        with gzip.open(args.out,'wt',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    else:args.out.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(metrics=result['metrics'],hypothetical=True,model_errors=0,online_learning=False),ensure_ascii=False))


if __name__=='__main__':main()
