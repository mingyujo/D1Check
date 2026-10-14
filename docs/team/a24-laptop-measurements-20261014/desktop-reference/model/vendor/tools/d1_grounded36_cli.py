"""Frozen range36 simulation; named parameters carry explicit evidence grades."""
import argparse,json,gzip,hashlib
from pathlib import Path
import torch
from tools import d1_grounded36 as g
from tools import d1_sim_complete33 as rules
from tools import d1_sched_dynamics_policy as policy
from tools import d1_sched_dynamics_ppo as rl
from tools import d1_sched_dynamics_study as helper
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,required=True);p.add_argument('--requests',type=Path,required=True);p.add_argument('--policy',choices=(*rules.RULES,'PPO_TRANSFER','ATC_WAIT_SHORT','ATC_WAIT_LONG'),default='ATC');p.add_argument('--seed',type=int,default=963360101);p.add_argument('--checkpoint',type=Path);p.add_argument('--dependencies',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise ValueError('existing output preserved')
 manifest=read(Path(__file__).resolve().parents[1]/'GRID_FREEZE.json');known=set(manifest['profile_sha'].values())
 if hashlib.sha256(a.profile.read_bytes()).hexdigest()not in known:raise ValueError('frozen exploration profile only')
 profile=read(a.profile);qs=read(a.requests)
 if any(q.get('work_units',1)!=1 for q in qs):raise ValueError('unit1 only')
 torch.set_num_threads(1);torch.use_deterministic_algorithms(True);name='ATC'if a.policy.startswith('ATC_WAIT_')else a.policy
 if name=='PPO_TRANSFER':
  if not a.checkpoint or not a.dependencies:p.error('fixed checkpoint/dependencies required')
  learner=rl.Learner.load(a.checkpoint,read(a.dependencies));before=rl.canonical(learner.snapshot());inner=learner.controller(deterministic=True,collect=False)
 elif name in ('ENERGY_EDD','THERMAL_EDD'):inner=rules.CostController(name)
 else:inner=policy.Controller(name,helper.affinity(profile))
 wait='short'if a.policy=='ATC_WAIT_SHORT'else'long'if a.policy=='ATC_WAIT_LONG'else None;c=g.Controller(inner,wait);r=g.simulate(profile,qs,c,environment_seed=a.seed);helper.physical_audit(r,qs)
 if name=='PPO_TRANSFER':assert before==rl.canonical(learner.snapshot())
 a.out.parent.mkdir(parents=True,exist_ok=True)
 with gzip.open(a.out,'wt')as f:json.dump(r,f,allow_nan=False)
 print(json.dumps(r['metrics']))
if __name__=='__main__':main()
