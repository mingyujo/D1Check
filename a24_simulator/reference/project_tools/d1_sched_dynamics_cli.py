"""Explicit hypothesis-only runtime; optional fixed PPO inference, no learning."""
import argparse
import gzip
import json
from pathlib import Path
import numpy as np
import torch
from tools import d1_sched_dynamics_plant as plant
from tools import d1_sched_dynamics_policy as policy
from tools import d1_sched_dynamics_ppo as rl

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,required=True);p.add_argument('--requests',type=Path,required=True)
    p.add_argument('--policy',choices=(*policy.RULES,'PPO'),default='ATC');p.add_argument('--checkpoint',type=Path);p.add_argument('--dependencies',type=Path)
    p.add_argument('--initial',type=Path);p.add_argument('--no-npu',action='store_true');p.add_argument('--environment-seed',type=int,default=947300101);p.add_argument('--out',type=Path,required=True);p.add_argument('--capture',type=Path)
    a=p.parse_args()
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    if a.out.exists():raise ValueError('existing result never overwritten')
    if a.capture and (a.capture.exists() or a.capture.with_suffix('.sensors.json').exists()):raise ValueError('existing capture never overwritten')
    profile=read(a.profile);data=read(a.requests);requests=data if isinstance(data,list) else data['requests']
    captured=[];sensors=[]
    if a.policy=='PPO':
        if not a.checkpoint or not a.dependencies:raise ValueError('fixed PPO requires checkpoint/dependencies')
        learner=rl.Learner.load(a.checkpoint,read(a.dependencies))
        def builder(dev,waiting):
            pack=policy.build(dev,waiting)
            if a.capture:
                captured.append({k:pack[k].copy() for k in ('state','candidates','mask','physical_mask')})
                pub=dev.public();sensors.append(dict(time_ns=dev.now,thermal_age_s=pub['thermal_observation_age_s'],power_age_s=pub['power_observation_age_s'],ap_c=pub['ap_c'],power_w=pub['power_w']))
            return pack
        ctl=rl.Controller(learner.network,deterministic=True,collect=False,builder=builder)
    else:
        means=profile['service_anchor']['means'];paths={key.split('|')[-1]:v for key,v in means.items() if key.split('|')[-2]=='classification'}
        preferred=min(paths,key=lambda b:(sum(paths[b]),plant.BACKENDS.index(b)));ctl=policy.Controller(a.policy,dict(classification=preferred,detection='CPU'))
    result=plant.simulate(profile,requests,ctl,environment_seed=a.environment_seed,npu=not a.no_npu,initial=read(a.initial) if a.initial else None)
    result.update(policy=a.policy,decisions=ctl.decisions,policy_errors=ctl.errors,online_learning=False,checkpoint_objective=rl.OBJECTIVE if a.policy=='PPO' else None)
    if a.capture:
        if a.policy!='PPO' or not captured:raise ValueError('capture requires nonempty fixed PPO inference')
        state=np.stack([r['state'] for r in captured]);vectors=np.stack([r['candidates'] for r in captured]);mask=np.stack([r['mask'] for r in captured]);physical=np.stack([r['physical_mask'] for r in captured])
        with torch.no_grad():
            choices=np.asarray([int(learner.network(torch.from_numpy(state[i:i+1]),torch.from_numpy(vectors[i:i+1]),torch.from_numpy(mask[i:i+1]))[0].probs.argmax(-1)) for i in range(len(state))])
        expected=np.asarray([d['chosen_index'] for d in ctl.decisions])
        if not np.array_equal(choices,expected) or (mask&~physical).any():raise ValueError('captured forward/mask differs')
        if any(not 0<=r['thermal_age_s']<=2.0000001 or not 0<=r['power_age_s']<=.9000001 for r in sensors):raise ValueError('causal sensor age')
        a.capture.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(a.capture,state=state,candidates=vectors,mask=mask,physical_mask=physical,choices=choices)
        a.capture.with_suffix('.sensors.json').write_text(json.dumps(sensors,allow_nan=False),encoding='utf-8');result['captured_forward_exact']=True
    a.out.parent.mkdir(parents=True,exist_ok=True)
    if a.out.suffix=='.gz':
        with gzip.open(a.out,'wt',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    else:a.out.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(metrics=result['metrics'],profile=profile['name'],hypothesis_only=True,online_learning=False,model_errors=len(ctl.errors)),ensure_ascii=False))
if __name__=='__main__':main()
