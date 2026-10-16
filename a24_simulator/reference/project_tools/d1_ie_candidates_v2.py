"""Four bounded CPU/GPU candidates; immutable plant and original adapters.

PPO and Double DQN share causal 109/68 candidate features and physical masks.
The CP-SAT planner schedules only arrived jobs; only its first action executes.
"""
from __future__ import annotations
import copy
import math
import time
import numpy as np
import torch
from torch import nn
from tools import d1_cpu_gpu_method_candidates as old

core=old.core
PPO='IE_PHYSICAL_MASK_UNBIASED_PPO_V2'
DQN='IE_PHYSICAL_MASK_DOUBLE_DQN_V2'
LIST='IE_ENERGY_AP_LIST_V2'
ROLL='IE_ROLLING_ENERGY_CPSAT_AP_FILTER_V2'


class UnbiasedPPO(old.current.ActorCritic):
    def forward(self,state,candidates,mask,base):
        if not torch.all(mask.any(-1)):raise ValueError('empty physical mask')
        h=self.state(state);ch=self.candidate(candidates)
        logits=self.actor(torch.cat((h[:,None,:].expand(-1,candidates.shape[1],-1),ch),-1)).squeeze(-1)
        return torch.distributions.Categorical(logits=logits.masked_fill(~mask,-1e9)),self.critic(h)


class DoubleQ(nn.Module):
    def __init__(self):
        super().__init__()
        self.state=nn.Sequential(nn.Linear(109,64),nn.Tanh(),nn.Linear(64,64),nn.Tanh())
        self.candidate=nn.Sequential(nn.Linear(68,64),nn.Tanh(),nn.Linear(64,64),nn.Tanh())
        self.q=nn.Sequential(nn.Linear(128,64),nn.Tanh(),nn.Linear(64,6))
        for layer in self.modules():
            if isinstance(layer,nn.Linear):nn.init.orthogonal_(layer.weight,math.sqrt(2));nn.init.zeros_(layer.bias)
        nn.init.zeros_(self.q[-1].weight);nn.init.zeros_(self.q[-1].bias)

    def forward(self,state,candidates):
        h=self.state(state);ch=self.candidate(candidates)
        return self.q(torch.cat((h[:,None,:].expand(-1,candidates.shape[1],-1),ch),-1))


def q_choice(q,mask,multipliers):
    values=q[:,:,0]-(q[:,:,1:]*torch.as_tensor(multipliers,dtype=q.dtype,device=q.device)).sum(-1)
    return values.masked_fill(~mask,-torch.inf).argmax(-1)


class DQNDistribution:
    def __init__(self,network,multipliers,epsilon=0.):
        self.network,self.multipliers,self.epsilon=network,multipliers,epsilon

    def __call__(self,state,candidates,mask,base):
        q=self.network(state,candidates);chosen=q_choice(q,mask,self.multipliers)
        probs=self.epsilon*mask/mask.sum(-1,keepdim=True)
        probs=probs.to(q.dtype);probs.scatter_add_(1,chosen[:,None],torch.full_like(chosen[:,None],1-self.epsilon,dtype=q.dtype))
        return torch.distributions.Categorical(probs=probs),q[torch.arange(len(q)),chosen]


def guarded(actions):
    """A local forecast filter, never a guarantee about future arrivals/SLA."""
    base=next(a for a in actions if a['base']);out=[]
    for a in actions:
        good=True
        for ctx in core.CONTEXTS:
            f,r=a['forecasts'][ctx],base['forecasts'][ctx]
            if not f['valid'] or not r['valid']:good=False;break
            if (f['deadline_misses']>r['deadline_misses'] or f['lane_end_s']>120+1e-9 or
                f['delta_ap']>1e-9 or f['delta_j']>1e-9):good=False;break
            fp,rp=f['urgent_p95_ms'],r['urgent_p95_ms']
            if fp is not None and rp is not None and fp>rp+1e-9:good=False;break
        if good:out.append(a)
    return out or [base]


def list_pick(actions):
    return min(guarded(actions),key=lambda a:(max(f.get('delta_ap',0.) for f in a['forecasts'].values()),
        max(f.get('delta_j',0.) for f in a['forecasts'].values()),not a['base'],core.signature(a)))


def cp_schedule(controller,queue,lanes,now_ns):
    """Joint assignment/start/order with integer-ms lane and response times.

Energy includes measured CG_DC overlap. AP is checked by the original exact
three-context forecast AFTER conversion to a physical first-action candidate.
This is an energy planner plus AP filter, not an exact thermal MILP.
"""
    from ortools.sat.python import cp_model
    now=now_ns/1e9;active=controller.active_jobs(lanes,now)
    if active is None:return None,dict(status='UNAVAILABLE_PUBLIC_RESIDUAL')
    tickets=sorted(queue,key=core.due)[:4]
    model=cp_model.CpModel();cpu=[];gpu=[];cc=[];cg=[];dc=[];starts=[];choices=[];misses=[];lateness=[]
    horizon=math.ceil((sum(max(sum(controller.estimates[core.p.key(q,b)]) for b in core.p.backends(q))/1e9 for q in tickets)+
        max([j['end']-now for j in active]+[0.])+.25)*1000)+1
    # Domains describe this finite plan, not a physical temperature/SLA limit.
    for j in active:
        end=math.ceil((j['end']-now)*1000-1e-8)
        iv=model.new_fixed_size_interval_var(0,end,'running_'+j['id'])
        (cpu if j['backend']=='CPU' else gpu).append(iv)
        if j['state']=='classification_CPU':cc.append(iv)
        if j['state']=='classification_GPU':cg.append((0,end,None))
        if j['state']=='detection_CPU':dc.append((0,end,None))
    hint_jobs=[dict(state=j['state'],backend=j['backend'],start=0,end=math.ceil((j['end']-now)*1000-1e-8)) for j in active]
    for i,q in enumerate(tickets):
        s=model.new_int_var(0,horizon,'s'+str(i));starts.append(s);options=[]
        response=model.new_int_var(0,horizon,'r'+str(i))
        for b in core.p.backends(q):
            ds=controller.estimates[core.p.key(q,b)]
            duration=math.ceil(sum(ds)/1e6-1e-8);resp=math.ceil(sum(ds[:2 if q['priority']=='urgent' else 3])/1e6-1e-8)
            present=model.new_bool_var(f'p{i}_{b}');end=model.new_int_var(0,horizon,f'e{i}_{b}')
            iv=model.new_optional_interval_var(s,duration,end,present,f'i{i}_{b}')
            model.add(response==s+resp).only_enforce_if(present)
            (cpu if b=='CPU' else gpu).append(iv)
            if q['task']=='classification' and b=='CPU':cc.append(iv)
            if q['task']=='classification' and b=='GPU':cg.append((s,end,present))
            if q['task']=='detection':dc.append((s,end,present))
            options.append((b,present,duration,end))
        model.add_exactly_one([x[1] for x in options]);choices.append(options)
        hint_options=[]
        for b,present,duration,end in options:
            label=q['task']+'_'+b;hs=0
            for _ in range(20):
                conflicts=[j for j in hint_jobs if hs<j['end'] and hs+duration>j['start'] and
                    (j['backend']==b or '+'.join(sorted((label,j['state']))) not in core.p.STATES)]
                if not conflicts:break
                hs=max(j['end'] for j in conflicts)
            hint_options.append((hs+duration,b,hs,duration))
        _,hb,hs,hd=min(hint_options,key=lambda z:(z[0],z[1]!='CPU'))
        model.add_hint(s,hs)
        for b,present,duration,end in options:
            model.add_hint(present,int(b==hb));model.add_hint(end,hs+duration if b==hb else 0)
        hint_jobs.append(dict(state=q['task']+'_'+hb,backend=hb,start=hs,end=hs+hd))
        response_hint=hs+math.ceil(sum(controller.estimates[core.p.key(q,hb)][:2 if q['priority']=='urgent' else 3])/1e6-1e-8)
        model.add_hint(response,response_hint)
        due_ms=math.floor(((q['arrival_ns']+q['deadline_offset_ns'])/1e9-now)*1000+1e-8)
        late=model.new_int_var(0,2*horizon+abs(due_ms),'late'+str(i));model.add_max_equality(late,[0,response-due_ms]);lateness.append(late)
        miss=model.new_bool_var('miss'+str(i));model.add(late==0).only_enforce_if(miss.Not());model.add(late>=1).only_enforce_if(miss);misses.append(miss)
        model.add_hint(late,max(0,response_hint-due_ms));model.add_hint(miss,int(response_hint>due_ms))
    model.add_no_overlap(cpu);model.add_no_overlap(gpu)
    model.add_no_overlap(cc+gpu) # no unmeasured classification CPU + GPU co-run
    first=model.new_int_var(0,horizon,'first');model.add_min_equality(first,starts)
    # If an immediate action exists, speculative idle delay uses cooling credit.
    model.add(first<=math.floor(controller.credit*1000+1e-8))
    watts=controller.frozen['energy_increment_w'];unit=1000000
    energy=sum(round(watts[q['task']+'_'+b]*unit)*duration*present for q,opts in zip(tickets,choices) for b,present,duration,end in opts)
    synergy=round((watts['classification_GPU']+watts['detection_CPU']-watts['classification_GPU+detection_CPU'])*unit)
    for k,(gs,ge,gp) in enumerate(cg):
        for l,(ds,de,dp) in enumerate(dc):
            lo=model.new_int_var(0,horizon,f'lo{k}_{l}');hi=model.new_int_var(0,horizon,f'hi{k}_{l}')
            model.add_max_equality(lo,[gs,ds]);model.add_min_equality(hi,[ge,de])
            raw=model.new_int_var(0,horizon,f'ov{k}_{l}');model.add_max_equality(raw,[0,hi-lo])
            overlap=model.new_int_var(0,horizon,f'used{k}_{l}')
            flags=[x for x in (gp,dp) if x is not None]
            if flags:
                model.add(overlap==raw).only_enforce_if(flags)
                for flag in flags:model.add(overlap==0).only_enforce_if(flag.Not())
            else:model.add(overlap==raw)
            energy-=synergy*overlap
    # Lexicographic bound: missing deadlines, total lateness, then energy.
    e_bound=max(1,round(max(watts.values())*unit)*horizon*len(tickets)*2)
    l_bound=sum(2*horizon+abs(math.floor(((q['arrival_ns']+q['deadline_offset_ns'])/1e9-now)*1000)) for q in tickets)+1
    model.minimize(sum(misses)*(l_bound*e_bound)+sum(lateness)*e_bound+energy)
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=1;solver.parameters.random_seed=0
    solver.parameters.max_deterministic_time=.05;solver.parameters.max_time_in_seconds=.25
    began=time.perf_counter();status=solver.solve(model)
    meta=dict(status=solver.status_name(status),response_stats=solver.response_stats(),wall_s=time.perf_counter()-began,window_jobs=len(tickets),integer_tick_ms=1,
        objective_kind='deadline count, lateness, measured overlap energy; exact AP first-action filter')
    if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):return None,meta
    plan=[dict(request_id=q['id'],backend=next(b for b,p,_,_ in opts if solver.value(p)),start_ms=solver.value(s)) for q,opts,s in zip(tickets,choices,starts)]
    plan.sort(key=lambda j:(j['start_ms'],core.due(next(q for q in tickets if q['id']==j['request_id']))))
    meta.update(plan=plan,proven_optimal=status==cp_model.OPTIMAL)
    return plan,meta


class RuleNetwork:
    def __init__(self,owner):self.owner=owner
    def __call__(self,state,candidates,mask,base):
        owner=self.owner;actions=owner.live_actions;chosen=list_pick(actions)
        if owner.public_policy==ROLL and len(actions)>1 and any(a['jobs'] for a in actions):
            plan,meta=cp_schedule(owner,*owner.live_public);owner.plans.append(meta)
            if plan:
                first=plan[0]['start_ms'];signature=tuple((j['request_id'],j['backend']) for j in plan if j['start_ms']==first)
                if first==0:
                    match=next((a for a in guarded(actions) if tuple((j['request_id'],j['backend']) for j in a['jobs'])==signature),None)
                else:
                    match=next((a for a in guarded(actions) if a['kind']=='cool_wait' and abs(a['wait_until_ns']-owner.live_public[2]-first*1e6)<=1e6),None)
                if match is not None:chosen=match;meta['first_action_accepted']=True
                else:meta['first_action_accepted']=False
        index=actions.index(chosen);probs=torch.zeros_like(mask,dtype=torch.float32);probs[:,index]=1.
        return torch.distributions.Categorical(probs=probs),torch.zeros((len(state),6))


class Controller(old.Controller):
    def __init__(self,frozen,initial,policy,network=None,*,deterministic=False,multipliers=None,epsilon=0.,no_wait=False,no_heat=False):
        if policy==DQN:network=DQNDistribution(network,multipliers,epsilon)
        if policy in (LIST,ROLL):network=RuleNetwork(self)
        super().__init__(frozen,initial,network,deterministic,no_wait=no_wait,no_heat=no_heat)
        self.public_policy=policy;self.plans=[];self.choice_records=[]

    def feature_vectors(self,queue,lanes,now_ns,actions):
        self.live_actions=actions;self.live_public=(queue,lanes,now_ns)
        return super().feature_vectors(queue,lanes,now_ns,actions)

    def decide(self,*args):
        n=len(self.trajectory);out=super().decide(*args)
        if len(self.trajectory)>n:
            step=self.trajectory[-1]
            self.choice_records.append(dict(t_s=step['t_s'],valid_actions=int(step['mask'].sum()),chosen_base=bool(step['base'][step['action']]),action=int(step['action'])))
        return out


def targets(controller,row,refs):
    if len(refs)!=2:raise ValueError('independent Band/Triton references required')
    full=row['completed']==row['planned'] and all(r['completed']==r['planned'] for r in refs)
    valid=np.ones(6,dtype=bool);valid[0]=valid[1]=full
    gain=refs[0]['energy_j']-row['energy_j'] if full else 0.
    costs=np.zeros(5);costs[1]=row['planned']-row['completed']
    for i,key,scale in [(0,'peak_ap_c',1.),(2,'urgent_service_failure',1.),(3,'normal_service_failure',1.),(4,'urgent_p95_ms',1500.)]:
        if row.get(key) is None or any(r.get(key) is None for r in refs):valid[i+1]=False;continue
        costs[i]=max(0.,*(row[key]-r[key]-(1e-9 if key in ('peak_ap_c','urgent_p95_ms') else 0.) for r in refs))/scale
    data=[dict(step,target=np.asarray([gain,*costs],dtype=np.float32),valid=valid.copy()) for step in controller.trajectory]
    return data,costs,valid


def double_targets(online,target,next_state,next_candidates,next_mask,multipliers,terminal,done):
    with torch.no_grad():
        selected=q_choice(online(next_state,next_candidates),next_mask,multipliers)
        evaluation=target(next_state,next_candidates)[torch.arange(len(selected)),selected]
        return terminal+(~done)[:,None]*evaluation # gamma=1, terminal whole-window cost includes WAIT


def dqn_update(network,target,optimizer,replay,fresh_count,multipliers,gradient_steps):
    entries=[(episode,i) for episode in replay for i in range(len(episode['data']))]
    steps=4*math.ceil(fresh_count/256);loss_value=0.
    for _ in range(steps):
        picked=[entries[int(i)] for i in torch.randint(len(entries),(min(256,len(entries)),))]
        frames=[e['data'][i] for e,i in picked]
        done=torch.tensor([i==len(e['data'])-1 for e,i in picked])
        following=[e['data'][min(i+1,len(e['data'])-1)] for e,i in picked]
        def tensor(rows,key):return torch.from_numpy(np.stack([r[key] for r in rows]))
        state=tensor(frames,'state');cand=tensor(frames,'candidates');action=torch.tensor([r['action'] for r in frames])
        terminal=torch.from_numpy(np.stack([r['target'] if d else np.zeros(6,dtype=np.float32) for r,d in zip(frames,done)]))
        expected=double_targets(network,target,tensor(following,'state'),tensor(following,'candidates'),tensor(following,'mask'),multipliers,terminal,done)
        actual=network(state,cand)[torch.arange(len(frames)),action];valid=tensor(frames,'valid')
        loss=(torch.nn.functional.smooth_l1_loss(actual,expected,reduction='none')*valid).sum()/valid.sum().clamp(min=1)
        optimizer.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(network.parameters(),.5);optimizer.step()
        gradient_steps+=1;loss_value=float(loss.detach())
        if gradient_steps%32==0:target.load_state_dict(network.state_dict())
    return dict(optimizer_steps=steps,loss=loss_value,gradient_steps=gradient_steps,replay_transitions=len(entries))
