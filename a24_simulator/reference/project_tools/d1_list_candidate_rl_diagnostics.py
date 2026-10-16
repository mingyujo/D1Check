"""Read completed snapshots/logs; no forward, optimizer, or environment calls."""
import argparse,json,math,statistics
from pathlib import Path
import torch

def run(path):
    path=Path(path);rows=[]
    for episodes,label in ((64,'development'),(128,'main_development')):
        for seed in (11,23,37):
            extras=[];chosen=[];decisions=0
            for i in range(24):
                f=path/'items'/f'{label}_PPO{episodes}_s{seed}_{i:03d}.pt'
                if not f.exists():continue
                state=torch.load(f,map_location='cpu',weights_only=False)['controller']
                if not state['deterministic']:raise ValueError('max-probability inference requires deterministic evaluation')
                for step in state['snapshots']:
                    count=int(step['mask'].sum());decisions+=1
                    if count<=1:continue
                    p=math.exp(step['logprob']);extras.append(p-1/count)
                    chosen.append(step['action']['wait']>0)
            rows.append(dict(seed=seed,episodes=episodes,decisions=decisions,informative_decisions=len(extras),
                argmax_probability_excess_over_uniform_mean=statistics.mean(extras) if extras else None,
                argmax_probability_excess_over_uniform_max=max(extras) if extras else None,
                selected_wait_fraction_informative=statistics.mean(chosen) if chosen else None))
    result=dict(status='PASS',read_only=True,rows=rows,
      interpretation='Selected max probability is exp(saved logprob); observed maximum near uniform supports small-score argmax repetition, not a mode-only causal proof',
      new_environment_starts=0,new_learning_starts=0,optimizer_steps=0,network_forward_calls=0,device_commands=0)
    (path/'argmax_diagnostics.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    print(json.dumps(run(args.run),indent=2))
