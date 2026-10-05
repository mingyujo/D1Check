"""Masked constrained PPO in the existing event simulator, never a device runner.

Import with MKL_THREADING_LAYER=SEQUENTIAL on the current Windows conda host.
No KMP duplicate-runtime override, dependency upgrades, or machine settings.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import random
import time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from tools import d1_request_rl as old
from tools import d1_empirical_request_policy as p

VERSION='request-ppo-lagrange-v1'
CONTRACT=p.ROOT/'docs/results/request_ppo_01/contract.json'
ACTIONS=('CPU','GPU','WAIT')
BASELINES=('CPU_REFERENCE','SPLIT_REFERENCE','EFT_REFERENCE','ENERGY_AP_REQUEST_V1')
TOP=8
PHASES=('AVAILABLE',*old.engine.PHASES)


def settings():
    x=old.batch.defaults('explore')
    x.update(decision_ns=0,record_ns=0,dispatch_ns=0,interference=1.,predicted_interference=1.)
    return x


class ActorCritic(nn.Module):
    def __init__(self, dimension):
        super().__init__()
        self.body=nn.Sequential(nn.Linear(dimension,64),nn.Tanh(),nn.Linear(64,64),nn.Tanh())
        self.actor=nn.Linear(64,3);self.value=nn.Linear(64,4)
        for layer in self.modules():
            if isinstance(layer,nn.Linear):
                nn.init.orthogonal_(layer.weight,math.sqrt(2));nn.init.zeros_(layer.bias)
        nn.init.orthogonal_(self.actor.weight,.01);nn.init.orthogonal_(self.value.weight,1.)

    def forward(self, observation, mask):
        if not torch.all(mask.any(-1)): raise ValueError('empty action mask')
        h=self.body(observation)
        return torch.distributions.Categorical(logits=self.actor(h).masked_fill(~mask,-1e9)),self.value(h)


class Controller(p.Controller):
    def __init__(self,frozen,initial,network,deterministic):
        super().__init__(frozen,initial,p.profile(frozen),p.PPO_POLICY)
        self.network=network;self.deterministic=deterministic;self.rollout=[]
        self.seen={};self.action_counts=[0,0,0];self.choices=0

    def observation(self,ordered,lanes,now):
        for q in ordered:
            self.seen[q['id']]=q['arrival_ns']/1e9
        arrivals=sorted(set(self.seen.values()))[-9:]
        gaps=np.diff(arrivals)
        urgent=[q for q in ordered if q['priority']=='urgent']
        normal=[q for q in ordered if q['priority']=='normal']
        cpu_work=sum(sum(self.estimates[p.key(q,'CPU')])/1e9 for q in ordered)
        slack=[(q['arrival_ns']+q['deadline_offset_ns'])/1e9-now for q in ordered]
        features=[now/120,(120-now)/120,self.t/50,self.init['reference_c']/50,
            (self.t-self.init['reference_c'])/10,self.h/.1,
            len(urgent)/192,len(normal)/192,cpu_work/120,
            min(slack)/6,sum(slack)/len(slack)/6,
            float(np.mean(gaps)) if len(gaps) else 0.,float(np.std(gaps)) if len(gaps) else 0.]
        for backend in ('CPU','GPU'):
            lane=lanes[backend];q=lane['request']
            if q is None: features.extend([0.]*8);continue
            elapsed=now-lane['dispatch']/1e9
            residual=sum(self.estimates[p.key(q,backend)])/1e9-elapsed
            phase=lane['phase']
            ready=phase in (('OUTPUT_READY','PERSISTED','WORKER_RELEASED') if q['priority']=='urgent' else ('PERSISTED','WORKER_RELEASED'))
            features.extend([1.,float(q['task']=='classification'),elapsed/6,max(0.,residual)/6,
                             float(residual<=0),PHASES.index(phase)/5,
                             ((q['arrival_ns']+q['deadline_offset_ns'])/1e9-now)/6,float(ready)])
        for i in range(TOP):
            if i>=len(ordered): features.extend([0.]*7);continue
            q=ordered[i]
            features.extend([1.,float(q['task']=='classification'),
                ((q['arrival_ns']+q['deadline_offset_ns'])/1e9-now)/6,
                (now-q['arrival_ns']/1e9)/6,sum(self.estimates[p.key(q,'CPU')])/6e9,
                sum(self.estimates[p.key(q,'GPU')])/6e9 if q['task']=='classification' else 0.,
                q['deadline_offset_ns']/6e9])
        value=np.array(features,dtype=np.float32)
        if not np.isfinite(value).all():raise ValueError('nonfinite observation')
        return value

    def __call__(self,config,queue,lanes,now_ns,cfg,thermal_model,current_ap):
        if any(q['arrival_ns']>now_ns for q in queue):raise ValueError('future ticket')
        if any(set(x)!={'request','phase','since','dispatch'} for x in lanes.values()):raise ValueError('private lane data')
        now=now_ns/1e9
        out=dict(now_ns=now_ns,selected=None,reason='PPO_busy_event_wait')
        if not queue:return out
        ordered=sorted(queue,key=lambda q:(0 if now_ns-q['arrival_ns']>=cfg['aging_ns'] else
            1 if q['priority']=='urgent' else 2,q['arrival_ns']+q['deadline_offset_ns'],q['ordinal'],q['id']))
        active=self.active_jobs(lanes,now)
        if active is None:return dict(out,reason='PPO_unknown_overrun_event_wait')
        q=ordered[0];immediate={b:self.place(q,b,now,active) for b in p.backends(q)}
        immediate={b:j for b,j in immediate.items() if j['start']<=now+1e-9}
        if not immediate:return out
        delay=min(.25,max(0.,2.-(now-q['arrival_ns']/1e9)))
        mask=np.array([b in immediate for b in ('CPU','GPU')]+[
            delay>1e-9 and any(j['response']+delay<=j['deadline']+1e-9 for j in immediate.values())],dtype=bool)
        obs=self.observation(ordered,lanes,now)
        with torch.no_grad():
            distribution,values=self.network(torch.from_numpy(obs)[None],torch.from_numpy(mask)[None])
            action=distribution.probs.argmax(-1) if self.deterministic else distribution.sample()
            logprob=distribution.log_prob(action).item();a=action.item()
        self.rollout.append(dict(t=now,obs=obs,mask=mask,action=a,logprob=logprob,value=values[0].numpy()))
        self.action_counts[a]+=1;self.choices+=int(mask.sum()>1)
        out.update(reason='PPO_policy',action=ACTIONS[a],head_request_id=q['id'],valid_actions=mask.tolist(),modeled_ap_c=self.t)
        if a==2:out.update(wait_until_ns=now_ns+delay*1e9,chosen_explicit_delay_s=delay)
        else:out['selected']=dict(request_id=q['id'],backend=ACTIONS[a])
        return out


def sources():
    return [Path(__file__),Path(p.__file__),Path(old.__file__),Path(old.engine.__file__),CONTRACT,
            p.BUNDLE/'model.json',p.BUNDLE/'initial_inputs.json']


def seed_all(seed):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)


def model_hash(network):
    h=hashlib.sha256()
    for key,v in sorted(network.state_dict().items()):h.update(key.encode());h.update(v.detach().numpy().tobytes())
    return h.hexdigest()


def save_actor(path,network):
    p.write(path,dict(version=VERSION,dimension=85,sha256=model_hash(network),
        tensors={k:v.detach().tolist() for k,v in network.state_dict().items()}))


def load_actor(path):
    obj=json.loads(Path(path).read_text(encoding='utf8'));network=ActorCritic(obj['dimension'])
    network.load_state_dict({k:torch.tensor(v,dtype=torch.float32) for k,v in obj['tensors'].items()})
    if model_hash(network)!=obj['sha256']:raise ValueError('policy tensor hash')
    network.eval();return network


def outcome(result,initial,frozen,controller=None):
    ss,costs,end=p.account(result,initial,frozen)
    path=np.array(costs['ap_path'],dtype=float);grid=np.arange(35,end+1,dtype=float)
    init=p.memory.initialize(initial['preload'],frozen['ap']['beta'],30.)
    # Thermal burden = model AP degree-seconds above the same pre-load effective
    # idle reference, NOT ambient, skin, BAT, safety limit or a physical certificate.
    rise=np.maximum(0.,path-init['reference_c'])
    area=float(np.trapezoid(rise,grid))
    rows=result['ledger'];by={x:[r for r in rows if r['priority']==x] for x in ('urgent','normal')}
    misses={x:sum('response_ns' not in r or r['response_ns']>r['deadline_offset_ns'] for r in rs) for x,rs in by.items()}
    failed={x:sum(r['status']!='succeeded' or 'response_ns' not in r or r['response_ns']>r['deadline_offset_ns'] for r in rs)
            for x,rs in by.items()}
    row=dict(planned=len(rows),completed=sum(r['status']=='succeeded' for r in rows),
        urgent_n=len(by['urgent']),normal_n=len(by['normal']),urgent_miss=misses['urgent'],normal_miss=misses['normal'],
        urgent_service_failure=failed['urgent'],normal_service_failure=failed['normal'],
        deadline_met=len(rows)-sum(misses.values()),energy_j=costs['whole_120s_j'],
        thermal_degree_seconds=area if end==180 else None,peak_ap_c=float(max(path)) if end==180 else None,
        urgent_p95_ms=result['metrics']['urgent_p95_ms'],normal_mean_ms=result['metrics']['normal_mean_ms'],
        overlap_s=sum(s['end_s']-s['start_s'] for s in ss if '+' in s['state']),
        actions=controller.action_counts if controller else None,controllable_decisions=controller.choices if controller else None)
    return row,(ss,grid,rise,end)


def simulate(frozen,initial,tickets,scenario,network=None,policy=None,deterministic=True):
    if network is None:
        _,result,_=old.simulate(frozen,initial,tickets,scenario,policy,seed=201)
        row,_=outcome(result,initial,frozen);return row,result,None,None
    actual=p.profile(frozen,scenario);vectors=dict(cells={k:[dict(source_request_id='common_context_'+scenario,
        durations_ns=v) for _ in range(4)] for k,v in actual.items()})
    c=Controller(frozen,initial,network,deterministic)
    result=old.engine.simulate(dict(protocol=p.VERSION,cells=p.profile(frozen)),vectors,tickets,
        policy=p.PPO_POLICY,settings=settings(),seed=201,decision_provider=c)
    row,extra=outcome(result,initial,frozen,c)
    return row,result,c,extra


def rewards(controller,result,extra,initial,frozen):
    """Dense interval accounting; only training uses post-episode outcomes.

Channels are reward -J/10 and three costs: urgent/normal missed fraction,
thermal area/100. Sum matches the whole episode, with fixed prefix assigned to
the first action and post-last-action cooling to the last. No reward for fewer
decisions, early stops or uncompleted requests.
"""
    ss,grid,rise,end=extra;tr=controller.rollout
    if not tr:raise ValueError('no training decisions')
    cuts=np.array([0.]+[x['t'] for x in tr[1:]]+[180.])
    cum=[0.]
    for a,b in zip(grid,grid[1:]):cum.append(cum[-1]+(rise[int(a-35)]+rise[int(b-35)])*.5*(b-a))
    thermal=np.interp(cuts,grid,np.array(cum),left=0.,right=cum[-1])
    reward=np.zeros((len(tr),4),dtype=np.float32)
    for i,(a,b) in enumerate(zip(cuts,cuts[1:])):
        energy=initial['preload_power_w']*max(0.,min(b,120)-a)
        for s in ss:
            energy+=max(0.,min(b,120,s['end_s'])-max(a,s['start_s']))*frozen['energy_increment_w'].get(s['state'],0.)
        reward[i,0]=-energy/10
        reward[i,3]=(thermal[i+1]-thermal[i])/100
    counts={x:sum(r['priority']==x for r in result['ledger']) for x in ('urgent','normal')}
    for r in result['ledger']:
        if r['status']!='succeeded' or 'response_ns' not in r or r['response_ns']>r['deadline_offset_ns']:
            deadline=(r['arrival_ns']+r['deadline_offset_ns'])/1e9
            i=max(0,min(len(tr)-1,int(np.searchsorted(cuts,deadline,side='right')-1)))
            reward[i,1 if r['priority']=='urgent' else 2]+=1/counts[r['priority']]
    if end!=180:reward[-1,3]+=10. # invalid completion bookkeeping; reported thermal stays null
    return reward


def gae(reward,values,lam=.95):
    """Undiscounted finite episode; no future episode bootstrap."""
    advantage=np.zeros_like(reward);carry=np.zeros(4,dtype=np.float32)
    for t in reversed(range(len(reward))):
        nxt=values[t+1] if t+1<len(values) else np.zeros(4,dtype=np.float32)
        carry=reward[t]+nxt-values[t]+lam*carry
        advantage[t]=carry
    return advantage,advantage+values


def pack(episodes):
    observations=[];masks=[];actions=[];logprobs=[];advantages=[];returns=[]
    for c,reward in episodes:
        values=np.stack([x['value'] for x in c.rollout]);a,v=gae(reward,values)
        observations.extend(x['obs'] for x in c.rollout);masks.extend(x['mask'] for x in c.rollout)
        actions.extend(x['action'] for x in c.rollout);logprobs.extend(x['logprob'] for x in c.rollout)
        advantages.extend(a);returns.extend(v)
    return dict(obs=torch.tensor(np.array(observations)),mask=torch.tensor(np.array(masks)),
        actions=torch.tensor(actions),old_logprob=torch.tensor(logprobs),
        advantages=torch.tensor(np.array(advantages)),returns=torch.tensor(np.array(returns)))


def optimize(network,optimizer,data,multipliers):
    a=data['advantages'];adv=a[:,0]-(a[:,1:]*torch.tensor(multipliers,dtype=torch.float32)).sum(-1)
    adv=(adv-adv.mean())/(adv.std(unbiased=False)+1e-8)
    losses=[];kls=[];entropies=[];clipped=[];n=len(adv);early=False
    for epoch in range(4):
        for idx in torch.randperm(n).split(256):
            dist,values=network(data['obs'][idx],data['mask'][idx])
            logprob=dist.log_prob(data['actions'][idx]);logratio=logprob-data['old_logprob'][idx]
            ratio=logratio.exp();approx_kl=((ratio-1)-logratio).mean()
            if approx_kl.item()>.03:early=True;break
            policy=-torch.minimum(ratio*adv[idx],ratio.clamp(.8,1.2)*adv[idx]).mean()
            value=.5*(values-data['returns'][idx]).square().mean()
            entropy=dist.entropy().mean();loss=policy+.5*value-.01*entropy
            if not torch.isfinite(loss):raise ValueError('nonfinite PPO loss')
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(network.parameters(),.5);optimizer.step()
            losses.append(loss.item());kls.append(approx_kl.item());entropies.append(entropy.item())
            clipped.append(((ratio-1).abs()>.2).float().mean().item())
        if early:break
    return dict(loss=float(np.mean(losses)) if losses else None,kl=float(np.mean(kls)) if kls else None,
        entropy=float(np.mean(entropies)) if entropies else None,clip_fraction=float(np.mean(clipped)) if clipped else None,
        minibatch_updates=len(losses),kl_stopped=early)


def violation(row,reference):
    return np.array([row['urgent_service_failure']/row['urgent_n']-reference['urgent_service_failure']/reference['urgent_n'],
        row['normal_service_failure']/row['normal_n']-reference['normal_service_failure']/reference['normal_n'],
        (row['thermal_degree_seconds']-reference['thermal_degree_seconds'])/100
        if row['thermal_degree_seconds'] is not None and reference['thermal_degree_seconds'] is not None else 10.],dtype=float)


def validation_key(rows,refs):
    violations=[violation(r,b) for r,b in zip(rows,refs)]
    return (sum(r['completed']<r['planned'] for r in rows),
        sum(bool(v[0]>1e-9 or v[1]>1e-9) for v in violations),
        float(sum(max(0.,v[0])+max(0.,v[1]) for v in violations)),
        sum(bool(v[2]>1e-9) for v in violations),float(sum(max(0.,v[2]) for v in violations)),
        float(np.mean([r['energy_j'] for r in rows])),
        float(np.mean([r['urgent_p95_ms'] or 120000. for r in rows])))


def specification():
    return dict(version=VERSION,algorithm='masked PPO clipped surrogate + 4 value heads + projected Lagrange ascent',
        seeds=[11,23,37],updates_per_seed=256,episodes_per_update=8,total_training_episodes=6144,
        train_trace_seeds=[30000,30511],validation_trace_seeds=[40001,40002,40003,40004],
        test_trace_seeds=list(range(50001,50009)),families=list(old.FAMILIES),scenarios=list(old.SCENARIOS),
        validation_updates=[0,64,128,192,256],validation_cases=48,test_cases=96,
        test_policies=[*BASELINES,'MC_RL_01','PPO_seed11','PPO_seed23','PPO_seed37'],
        test_runs=768,architecture='85 continuous features -> tanh64 -> tanh64 -> logits3 + values4',
        optimizer='Adam lr=0.0003 eps=1e-5',epochs=4,minibatch=256,clip=.2,entropy_coefficient=.01,
        value_coefficient=.5,gradient_clip=.5,target_kl=.03,gamma=1.,gae_lambda=.95,
        objective='minimize whole120s J/10; keep expected priority-specific deadline-or-incomplete fractions and AP degree-seconds/100 <= paired EFT',
        thermal_definition='35-180s trapezoidal model AP area above pre-load effective idle reference; not ambient/safety',
        multiplier_initial=[10.,10.,1.],multiplier_lr=5.,multiplier_bounds=[0.,100.],
        action_mask='supported immediate CPU/GPU; wait<=250ms, arrival-age<=2s, estimated head deadline guard only',
        validation_selection='lexicographic incomplete cases, worse service cases, positive service excess, worse thermal cases, positive thermal excess, mean J, P95; report all 3 seeds, no best-test-seed selection',
        freeze='all three validation-selected actors before any test result; no test-based retraining',
        training_data='new synthetic arrival seeds; previously seen measured model and fixed initial input; no new independent device data',
        max_wall_seconds=7200,checkpoint_every_updates=16,early_success_stop=False,
        sources=dict(model=p.MODEL_SHA,initial=p.INITIAL_SHA),device_commands=0,experiment_ready=False)


def run(output):
    spec=specification()
    if json.loads(CONTRACT.read_text(encoding='utf8'))!=spec:raise ValueError('contract changed')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    began=time.monotonic();hashes={str(x.relative_to(p.ROOT)):p.digest(x) for x in sources()}
    p.write(output/'preregistered.json',dict(contract=spec,hashes=hashes,utc=datetime.now(timezone.utc).isoformat(),
        torch=torch.__version__,numpy=np.__version__,mkl_threading_layer='SEQUENTIAL',threads=1))
    frozen,case=p.inputs(p.BUNDLE);initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
    val_cases=[(s,f,c) for s in spec['validation_trace_seeds'] for f in old.FAMILIES for c in old.SCENARIOS]
    references={};validation=[];training=[];selected=[];total_steps=0
    def check_time():
        if time.monotonic()-began>spec['max_wall_seconds']:raise TimeoutError('PC 2h bound; checkpoints preserved')
    def reference(seed,family,scenario):
        key=(seed,family,scenario)
        if key not in references:
            references[key]=simulate(frozen,initial,old.workload(family,seed),scenario,policy='EFT_REFERENCE')[0]
        return references[key]
    def validate(network,learnseed,update):
        rows=[];refs=[];before=model_hash(network)
        for s,f,c in val_cases:
            check_time();row,*_=simulate(frozen,initial,old.workload(f,s),c,network)
            rows.append(row);refs.append(reference(s,f,c))
            validation.append(dict(learn_seed=learnseed,update=update,trace_seed=s,family=f,scenario=c,**row))
        if before!=model_hash(network):raise ValueError('validation mutated network')
        return validation_key(rows,refs)
    for learnseed in spec['seeds']:
        seed_all(learnseed);network=ActorCritic(85);optimizer=torch.optim.Adam(network.parameters(),lr=3e-4,eps=1e-5)
        multipliers=np.array(spec['multiplier_initial'],dtype=float)
        best=None;best_update=None;seed_dir=output/f'seed{learnseed}';seed_dir.mkdir()
        # Untrained diagnostic is logged but never selected as a learned candidate.
        initial_key=validate(network,learnseed,0)
        print(f'seed={learnseed} untrained validation={initial_key}',flush=True)
        for update in range(1,spec['updates_per_seed']+1):
            check_time();episodes=[];violations=[];metrics=[]
            for offset in range(8):
                i=(update-1)*8+offset;family=old.FAMILIES[i%4];trace_seed=30000+i//4
                scenario=old.SCENARIOS[(i//4+old.FAMILIES.index(family))%3]
                row,result,c,extra=simulate(frozen,initial,old.workload(family,trace_seed),scenario,network,deterministic=False)
                reward=rewards(c,result,extra,initial,frozen)
                episodes.append((c,reward));metrics.append(row)
                violations.append(violation(row,reference(trace_seed,family,scenario)))
                total_steps+=len(c.rollout)
            data=pack(episodes);stats=optimize(network,optimizer,data,multipliers)
            violation_mean=np.mean(violations,axis=0)
            multipliers=np.clip(multipliers+5*violation_mean,0.,100.)
            log=dict(learn_seed=learnseed,update=update,episodes=update*8,total_steps=total_steps,
                batch_steps=len(data['actions']),elapsed_s=time.monotonic()-began,
                mean_energy_j=float(np.mean([m['energy_j'] for m in metrics])),
                mean_urgent_miss=float(np.mean([m['urgent_miss']/m['urgent_n'] for m in metrics])),
                mean_normal_miss=float(np.mean([m['normal_miss']/m['normal_n'] for m in metrics])),
                violation=violation_mean.tolist(),multipliers=multipliers.tolist(),**stats)
            training.append(log)
            if update%16==0:
                torch.save(dict(network=network.state_dict(),optimizer=optimizer.state_dict(),update=update,
                    multipliers=multipliers,torch_rng=torch.get_rng_state()),seed_dir/'checkpoint.pt')
                old.csv_write(output/'training.csv',training)
                p.write(output/'progress.json',dict(seed=learnseed,update=update,total_steps=total_steps,
                    elapsed_s=time.monotonic()-began,stage='training',test_started=False))
                print(f'seed={learnseed} update={update}/256 steps={total_steps} miss={log["mean_urgent_miss"]:.3f}/{log["mean_normal_miss"]:.3f} dual={multipliers.round(2)}',flush=True)
            if update in spec['validation_updates']:
                key=validate(network,learnseed,update)
                save_actor(seed_dir/f'actor_update{update}.json',network)
                if best is None or key<best:
                    best=key;best_update=update;save_actor(seed_dir/'selected_actor.json',network)
                print(f'seed={learnseed} validation@{update}={key}; selected={best_update}',flush=True)
                old.csv_write(output/'validation.csv',validation)
        selected.append(dict(seed=learnseed,update=best_update,key=best,
            actor_sha256=p.digest(seed_dir/'selected_actor.json')))
    if hashes!={str(x.relative_to(p.ROOT)):p.digest(x) for x in sources()}:raise ValueError('source drift')
    p.write(output/'freeze_before_test.json',dict(selected=selected,total_training_steps=total_steps,
        utc=datetime.now(timezone.utc).isoformat(),test_started=False))
    print('all three policies frozen; opening final test once',flush=True)
    models={s['seed']:load_actor(output/f'seed{s["seed"]}'/'selected_actor.json') for s in selected}
    mc=json.loads((p.ROOT/'docs/results/request_rl_01/run_v1/learned_table.json').read_text(encoding='utf8'))['table']
    tests=[];details_path=output/'local_test_ledgers.jsonl'
    with details_path.open('w',encoding='utf8') as details:
        for trace_seed in spec['test_trace_seeds']:
            for family in old.FAMILIES:
                tickets=old.workload(family,trace_seed)
                for scenario in old.SCENARIOS:
                    for policy in spec['test_policies']:
                        check_time()
                        if policy.startswith('PPO_seed'):
                            network=models[int(policy.split('seed')[1])]
                            row,result,c,_=simulate(frozen,initial,tickets,scenario,network)
                        elif policy=='MC_RL_01':
                            _,result,_=old.simulate(frozen,initial,tickets,scenario,p.RL_POLICY,mc,0,201)
                            row,_=outcome(result,initial,frozen)
                        else:row,result,_,_=simulate(frozen,initial,tickets,scenario,policy=policy)
                        tests.append(dict(trace_seed=trace_seed,family=family,scenario=scenario,policy=policy,**row))
                        details.write(json.dumps(dict(trace_seed=trace_seed,family=family,scenario=scenario,policy=policy,
                            ledger=result['ledger']),ensure_ascii=False)+'\n')
                print(f'test trace={trace_seed} family={family} {len(tests)}/768',flush=True)
                old.csv_write(output/'test.csv',tests)
    for selected_row in selected:
        path=output/f'seed{selected_row["seed"]}'/'selected_actor.json'
        if p.digest(path)!=selected_row['actor_sha256'] or model_hash(models[selected_row['seed']])!=json.loads(path.read_text())['sha256']:
            raise ValueError('test updated policy')
    if hashes!={str(x.relative_to(p.ROOT)):p.digest(x) for x in sources()}:raise ValueError('source drift')
    p.write(output/'summary.json',dict(version=VERSION,training_episodes=6144,training_steps=total_steps,
        test_runs=len(tests),validation_runs=len(validation),selected=selected,
        elapsed_s=time.monotonic()-began,device_commands=0,independent_device_validation=False,
        convergence_proven=False,policy_winner=None,experiment_ready=False))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args();print(run(args.output))
