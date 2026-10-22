"""Saved neural forward/RNG/update replay. Never sample a new environment."""
import gzip,io,json,os,copy
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
H=Path(__file__).resolve().parent
from run import read,save,sha,now
def main():
    import numpy as np,torch
    from nn_train import Learner,digest
    torch.set_num_threads(1);O=H/'artifacts/G001';result=read(O/'RESULT.json');op=read(H/'OPERATION.json');checks=frames_seen=updates=overdue_candidates=chosen_overdue=0;maxlog=maxvalue=0.;decision_diagnosis=[]
    save(H/'NN_AUDIT_OPERATION.json',dict(utc=now(),pins=[dict(path=str(p),sha256=sha(p)) for p in [Path(__file__),H/'nn_train.py',O/'RESULT.json']],new_environment=0,new_training=0))
    def load(p):return torch.load(io.BytesIO(gzip.decompress(Path(p).read_bytes())),map_location='cpu',weights_only=False)
    def need(b,m):
        nonlocal checks
        checks+=1
        if not b:raise ValueError(m)
    def equal(a,b):
        if torch.is_tensor(a):need(torch.equal(a,b),'Exact saved tensor')
        elif isinstance(a,np.ndarray):need(np.array_equal(a,b),'Exact saved array')
        elif isinstance(a,dict):
            need(a.keys()==b.keys(),'Mapping keys')
            for k in a:equal(a[k],b[k])
        elif isinstance(a,(tuple,list)):
            need(len(a)==len(b),'Sequence length')
            for x,y in zip(a,b):equal(x,y)
        else:need(a==b,'Exact scalar')
    def forward(frames,net,row):
        nonlocal frames_seen,maxlog,maxvalue,overdue_candidates,chosen_overdue
        w={k:v.detach().numpy() for k,v in net.state_dict().items()};raw=read(O/(row['label']+'.raw.json.gz'));need(len(frames)==len(raw['policy_decisions']),'Every decision has a frame')
        actual={q['ordinal']:q for q in raw['requests']};planned={q['ordinal']:q for q in raw['planned_requests']};dispatched=set();active={}
        for start in range(0,len(frames),128):
            ff=frames[start:start+128];x=np.stack([f['x'] for f in ff]);mask=np.stack([f['mask'] for f in ff]);e=np.tanh(x@w['encode.0.weight'].T+w['encode.0.bias']);context=np.concatenate([(e*mask[:,:,None]).sum(1)/mask.sum(1)[:,None],np.where(mask[:,:,None],e,-1e9).max(1)],-1)
            logits=(np.tanh(np.concatenate([e,np.broadcast_to(context[:,None,:],(len(ff),27,96))],-1)@w['actor.0.weight'].T+w['actor.0.bias'])@w['actor.2.weight'].T+w['actor.2.bias']).squeeze(-1);logits=logits/getattr(net,'temperature',1.);logits=np.where(mask,logits,-1e9);lp=logits-logits.max(-1)[:,None];lp-=np.log(np.exp(lp).sum(-1))[:,None]
            value=np.tanh(context@w['critic.0.weight'].T+w['critic.0.bias'])@w['critic.2.weight'].T+w['critic.2.bias']
            for i,f in enumerate(ff):
                err=abs(float(lp[i,f['index']])-f['old_logp']);ve=float(np.max(abs(value[i]-f['value'])));maxlog=max(maxlog,err);maxvalue=max(maxvalue,ve);need(err<2e-4 and ve<2e-4,'Independent NumPy forward');need(f['network_sha256']==digest(net),'Frame weight SHA')
                need(bool(mask[i,f['index']]),'Physical legal chosen index');need(all(bool(m)==(j<len(f['candidate_actions'])) for j,m in enumerate(mask[i])),'No hidden deadline mask')
                d=raw['policy_decisions'][start+i];need(abs(f['time_ns']-round(d['time']*1e9))<=1,'Actual decision time')
                t=d['time'];active={j:q for j,q in active.items() if q['available'] is None or q['available']>t+1e-9};slots={q['route'].rsplit('_',1)[1] for q in active.values()}
                for a in f['candidate_actions']:
                    q=planned[a['ordinal']];need(a['ordinal'] not in dispatched and q['readyAt']<=t+1e-9,'Candidate is causally ready')
                    if a['kind']=='DISPATCH':
                        need(a['route'].rsplit('_',1)[1] not in slots and len(active)<3,'Candidate physical slot');need(a['route'].startswith(q['task']+'_') and (q['task']!='detection' or a['route']=='detection_CPU'),'Candidate route support');overdue_candidates+=int(q['deadline']<t-1e-9)
                for k in ['kind','ordinal','route','wait_s']:need(f['action'].get(k)==d['action'].get(k),'No post-NN override')
                if f['action']['kind']=='DISPATCH':
                    ordinal=f['action']['ordinal'];dispatched.add(ordinal);active[ordinal]=actual[ordinal];chosen_overdue+=int(actual[ordinal]['deadline']<t-1e-9)
                if row['balanced']:
                    pref={p['ordinal']:p['route'] for p in raw['route_context_evidence']['preferences']}
                    for j,a in enumerate(f['candidate_actions']):
                        expected=-1 if a['kind']=='WAIT_EVENT' else int(a['kind']=='DISPATCH' and a.get('route')==pref[a['ordinal']]);need(float(f['x'][j,31])==expected,'Actual causal preference/event feature')
                if not f['collect']:need(int(logits[i].argmax())==f['index'],'Exact neural final choice')
                frames_seen+=1
        gaps=[f['scores'][f['index']]-min(v for v,m in zip(f['scores'],f['mask']) if m) for f in frames]
        decision_diagnosis.append(dict(label=row['label'],kind=row['kind'],model=row['model'],seed=row['seed'],load=row['load'],frames=len(frames),public_score_argmin_agreement=float(np.mean(np.array(gaps)<1e-8)),mean_public_score_gap=float(np.mean(gaps)),WAIT_actions=sum(f['action']['kind']=='WAIT' for f in frames),WAIT_EVENT_actions=sum(f['action']['kind']=='WAIT_EVENT' for f in frames),qualification='Diagnostic of imitation/optimization gap; nominal public score argmin is not proved optimal under actual future work.'))
    from bc import teacher,pretrain
    demonstrations=[]
    for row in [r for r in result['rows'] if r['kind']=='DEMO']:
        data=load(O/(row['label']+'.demonstrations.pt.gz'));demonstrations.append(data);raw=read(O/(row['label']+'.raw.json.gz'));need(len(raw['policy_decisions'])==len(data['frames']),'All teacher decisions recorded')
        pref={p['ordinal']:p for p in raw['route_context_evidence']['preferences']}
        for f,d in zip(data['frames'],raw['policy_decisions']):
            need(f['from_teacher'] and not f['collect'],'Declared demonstration, not PPO');need(teacher(dict(x=f['x'],mask=f['mask'],actions=f['candidate_actions']))==f['index'],'Reproducible public teacher')
            for j,a in enumerate(f['candidate_actions']):
                need(pref[a['ordinal']]['time']<=f['time_ns']/1e9+1e-8,'Preference known before demonstration')
                expected=-1 if a['kind']=='WAIT_EVENT' else int(a['kind']=='DISPATCH' and a.get('route')==pref[a['ordinal']]['route']);need(float(f['x'][j,31])==expected,'Actual demonstration preference/event feature')
            for k in ['kind','ordinal','route','wait_s']:need(f['action'].get(k)==d['action'].get(k),'Actual teacher action binding')
    parent=load(op['parent_checkpoint']);warm,bc_trace=pretrain(parent,demonstrations,op['BC_seed']);saved_trace=load(O/'BC_TRACE.pt.gz');equal(bc_trace,saved_trace);equal(warm.snapshot(),load(O/'BC_COMMON_FINAL.pt.gz')['learner']);bc_steps=bc_trace['steps'];del demonstrations
    for seed in op['seeds']:
        learner=Learner(seed);learner.restore(load(O/f'S{seed}_EP000.pt.gz'));need(learner.net.temperature==.35,'Sampling/PPO temperature recorded');order=read(O/f'S{seed}_ORDER.json');need(order['order']==np.random.default_rng(seed+50000).permutation(8).tolist(),'Fresh case RNG')
        for ep in range(1,9):
            prefix=f'S{seed}_EP{ep:03d}';before=load(O/(prefix+'_before.pt.gz'));after=load(O/(prefix+'_after.pt.gz'));equal(learner.snapshot(),before['learner']);learner.balance=copy.deepcopy(before['balance'])
            row=read(O/('TRAIN_'+prefix+'.json'));data=load(O/(row['label']+'.frames.pt.gz'));forward(data['frames'],learner.net,row)
            need(np.max(abs(data['physical_costs'].sum(0)-row['balanced_cost']))<1e-7,'Balanced reward telescope')
            expected=data['physical_costs'].copy();expected[:,0]/=data['balance']['scales'][0];expected[:,1]/=data['balance']['scales'][1];expected[:,2]*=data['balance']['classFactors'][0];expected[:,3]*=data['balance']['classFactors'][1];need(np.max(abs(expected-data['learning_costs']))<1e-12,'Declared objective normalization')
            for f in data['frames']:
                index,replay=learner.choose(dict(x=f['x'],mask=f['mask'],scores=f['scores']),True);need(index==f['index'] and abs(replay['old_logp']-f['old_logp'])<1e-7,'Exact temperature-scaled action RNG')
            old=learner.updates;learner.add(data['frames'],data['learning_costs']);equal(learner.snapshot(),after['learner']);updates+=learner.updates-old
        need(learner.updates==4,'Four PPO updates per seed');print('EVENT_SAVED_NN_REPLAY',seed,flush=True)
    nets={}
    for row in result['rows']:
        if row['seed'] is None or row['kind']=='TRAIN':continue
        key=(row['model'],row['seed'])
        if key not in nets:
            learner=Learner(row['seed']);s=load(op['parent_checkpoint']) if row['seed']==481083 else load(O/'BC_COMMON_FINAL.pt.gz')['learner'] if row['seed']==781000 else load(O/f'S{row["seed"]}_FINAL.pt.gz')['learner'];learner.restore(s);nets[key]=learner.net
        data=load(O/(row['label']+'.frames.pt.gz'));forward(data['frames'],nets[key],row)
    need(updates==12,'All12 PPO updates replayed')
    save(O/'NN_DECISION_DIAGNOSIS.json',dict(status='SAVED_PUBLIC_SCORE_AND_NN_CHOICE_DIAGNOSIS',rows=decision_diagnosis,new_environment=0,new_training=0))
    save(O/'NN_AUDIT.json',dict(status='PASS_NUMPY_FORWARD_EXACT_ACTION_RNG_AND_ADAM_REPLAY',utc=now(),checks=checks,frames=frames_seen,replayed_updates=updates,replayed_BC_steps=bc_steps,actual_overdue_DISPATCH_candidates=overdue_candidates,actual_chosen_overdue_requests=chosen_overdue,max_logprob_error=maxlog,max_value_error=maxvalue,new_environment=0,new_training=0,physical_validation=False))
    print('SAVED_NN_AUDIT_PASS',checks,frames_seen,updates,flush=True)
if __name__=='__main__':main()
