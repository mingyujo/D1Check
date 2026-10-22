"""Independent vectorized NumPy NN and exact saved RNG/Adam arithmetic replay."""
import gzip,hashlib,io,json,os,time
from pathlib import Path
for k in('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='1'
HERE=Path(__file__).resolve().parent
from run import read,save,sha,now
def main(op,out):
 import numpy as np,torch
 from nn_train import Learner,digest
 torch.set_num_threads(1);begin=time.monotonic();result=read(out/'RESULT.json');checks=frames_count=replayed_updates=actor_changes=nonfirst=eval_frames=wait_actions=0;maxlog=maxcritic=0.;decision_diagnostics=[];optimizer_diagnostics=[];public_samples=[]
 save(HERE/'NN_AUDIT_OPERATION.json',dict(utc=now(),new_environment=0,new_training=0,pins=[dict(path=str(p),sha256=sha(p))for p in(Path(__file__),HERE/'nn_train.py',HERE/'OPERATION.json',out/'RESULT.json')]))
 def load(p):return torch.load(io.BytesIO(gzip.decompress(Path(p).read_bytes())),map_location='cpu',weights_only=False)
 def need(ok,why):
  nonlocal checks
  checks+=1
  if not ok:raise ValueError(why)
 def same(a,b):
  if torch.is_tensor(a):need(torch.equal(a,b),'Saved tensor mismatch')
  elif isinstance(a,np.ndarray):need(np.array_equal(a,b),'Saved array mismatch')
  elif isinstance(a,dict):
   need(a.keys()==b.keys(),'Saved mapping keys')
   for k in a:same(a[k],b[k])
  elif isinstance(a,(list,tuple)):
   need(len(a)==len(b),'Saved sequence length')
   for x,y in zip(a,b):same(x,y)
  else:need(a==b,'Saved scalar mismatch')
 def manual(frames,net):
  nonlocal maxlog,maxcritic,frames_count,eval_frames,nonfirst,wait_actions
  w={k:v.detach().numpy()for k,v in net.state_dict().items()};network=digest(net)
  for offset in range(0,len(frames),128):
   ff=frames[offset:offset+128];x=np.stack([f['x']for f in ff]);mask=np.stack([f['mask']for f in ff]);e=np.tanh(x@w['encode.0.weight'].T+w['encode.0.bias']);mean=(e*mask[:,:,None]).sum(1)/mask.sum(1)[:,None];maximum=np.where(mask[:,:,None],e,-1e9).max(1);context=np.concatenate([mean,maximum],axis=-1)
   actor=np.tanh(np.concatenate([e,np.broadcast_to(context[:,None,:],(len(ff),27,96))],axis=-1)@w['actor.0.weight'].T+w['actor.0.bias']);logits=(actor@w['actor.2.weight'].T+w['actor.2.bias']).squeeze(-1);logits=np.where(mask,logits,-1e9);lp=logits-logits.max(-1)[:,None];lp-=np.log(np.exp(lp).sum(-1))[:,None];value=np.tanh(context@w['critic.0.weight'].T+w['critic.0.bias'])@w['critic.2.weight'].T+w['critic.2.bias']
   for i,f in enumerate(ff):
    err=abs(float(lp[i,f['index']])-f['old_logp']);v=float(np.max(abs(value[i]-f['value'])));maxlog=max(maxlog,err);maxcritic=max(maxcritic,v);need(err<2e-4 and v<2e-4,'Independent NumPy forward');need(bool(mask[i,f['index']]),'Actual chosen mask');need(f['network_sha256']==network,'Frame network provenance');frames_count+=1
    if not f['collect']:need(int(np.argmax(logits[i]))==f['index'],'Independent eval argmax');eval_frames+=1;nonfirst+=int(f['index']!=int(np.flatnonzero(mask[i])[0]));wait_actions+=int(f['action']['kind']=='WAIT')
 def bind(row,data):
  raw=read(out/(row['label']+'.raw.json.gz'));decisions=raw['policy_decisions'];need(len(decisions)==len(data['frames']),'Every NN action bound to environment')
  planned={q['ordinal']:q for q in raw['planned_requests']};actual={q['ordinal']:q for q in raw['requests']};active={};dispatched=set();wait_head={};wait_total=0.;coverage=[];actionable=hidden_potential=0
  public_ids=[i for i,d in enumerate(decisions)if d.get('public_observation')];sample_ids={public_ids[int(frac*len(public_ids))]for frac in(.1,.5,.9)}if public_ids and row['kind']!='TRAIN'else set()
  for fi,(f,d) in enumerate(zip(data['frames'],decisions)):
   t=d['time'];active={k:q for k,q in active.items()if q['available']is None or q['available']>t+1e-9};slots={q['route'].rsplit('_',1)[1]for q in active.values()};actions=f['candidate_actions'];need(len(actions)<=27 and len(f['mask'])==27,'NN bank bounds');need(all(bool(v)==(i<len(actions))for i,v in enumerate(f['mask'])),'Only physical candidate padding mask');need(f['decision_ready']<=8 and f['forecast_ready']<=(32 if row['variant']=='REPAIR'else 8),'Declared public lookahead bounds');need(t<f['forecast_horizon_s']<=raw['observation_horizon_s'],'Registered forecast horizon')
   for a in actions:
    q=planned[a['ordinal']];need(a['ordinal']not in dispatched and q['readyAt']<=t+1e-9,'No future/already-dispatched candidate')
    if a['kind']=='DISPATCH':
     route=a['route'];slot=route.rsplit('_',1)[1];need(len(active)<3 and slot not in slots,'Physical slot mask');need(route.startswith(q['task']+'_')and(q['task']!='detection'or route=='detection_CPU'),'Measured task support')
    else:need(a['kind']=='WAIT'and a['wait_s']in(.05,.2,.5),'Registered WAIT choices');need(wait_total+a['wait_s']<=12+1e-8 and wait_head.get(a['ordinal'],0)+a['wait_s']<=1.5+1e-8,'Only operational WAIT budget')
   coverage.append(f['forecast_ready']/max(1,f['ready_total']))
   if len(active)<3 and 'CPU'not in slots:
    ready_normal=[q for q in planned.values()if q['ordinal']not in dispatched and q['readyAt']<=t+1e-9 and q['priority']=='normal'and q['deadline']-t>.2264312379001616];candidate_ordinals={a['ordinal']for a in actions if a['kind']=='DISPATCH'};actionable+=int(bool(ready_normal));hidden_potential+=int(bool(ready_normal)and not any(q['ordinal']in candidate_ordinals for q in ready_normal))
   need(abs(f['time_ns']-round(d['time']*1e9))<=1,'Actual decision clock')
   for k in('kind','ordinal','route','wait_s'):need(f['action'].get(k)==d['action'].get(k),'Actual final NN decision binding')
   if fi in sample_ids:public_samples.append(dict(label=row['label'],decision_index=fi,x=f['x'].tolist(),mask=f['mask'].tolist(),scores=f['scores'],actions=f['candidate_actions']))
   chosen=f['action']
   if chosen['kind']=='DISPATCH':dispatched.add(chosen['ordinal']);active[chosen['ordinal']]=actual[chosen['ordinal']]
   else:wait_total+=chosen['wait_s'];wait_head[chosen['ordinal']]=wait_head.get(chosen['ordinal'],0)+chosen['wait_s']
  need(abs(wait_total-row['wait_s'])<1e-7,'Full actual WAIT accounting')
  score_gaps=[float(f['scores'][f['index']]-min(s for s,m in zip(f['scores'],f['mask'])if m))for f in data['frames']]
  decision_diagnostics.append(dict(label=row['label'],kind=row['kind'],variant=row['variant'],seed=row['seed'],load=row['nominal_load_ratio'],frames=len(data['frames']),mean_forecast_queue_coverage=float(np.mean(coverage)),CPU_free_with_potentially_timely_normal_frames=actionable,only_hidden_potentially_timely_normal_when_CPU_free=hidden_potential,nominal_score_argmin_agreement=float(np.mean(np.asarray(score_gaps)<1e-8)),mean_chosen_nominal_score_gap=float(np.mean(score_gaps)),qualification='CPU_free means the CPU route execution slot is unoccupied and owner count is below3. The separate shared CPU service queue may still be occupied. Potentially timely uses optimistic C0 isolated detection duration, not a feasibility guarantee. Queue prediction coverage is distinct from physical action availability. Nominal score disagreement is diagnostic, not proof that its argmin is better under actual future work.'))
  return raw
 for parent_seed,seed in zip(op['parent_seeds'],op['new_stage_seeds']):
  order=read(out/f'S{seed}_CASE_ORDER.json');rng=np.random.default_rng(seed+300000);need(order['order']==rng.permutation(32).tolist(),'Balanced paired case order');same(order['case_rng_after'],rng.bit_generator.state);a=load(out/f'BASE_S{seed}_EP000.pt.gz');b=load(out/f'REPAIR_S{seed}_EP000.pt.gz');parent=load(op['parent_checkpoints'][str(parent_seed)]);same(a,b);same(a['network'],parent['network']);need(not a['optimizer']['state']and not a['pending']and a['updates']==0,'New-stage optimizer and pending explicit reset')
  for variant in('BASE','REPAIR'):
   learner=Learner(seed);learner.restore(load(out/f'{variant}_S{seed}_EP000.pt.gz'))
   for ep in range(1,33):
    prefix=f'{variant}_S{seed}_EP{ep:03d}';row=read(out/f'TRAIN_{prefix}.json');before=load(out/(prefix+'_before.pt.gz'));after=load(out/(prefix+'_after.pt.gz'));same(learner.snapshot(),before);need(row['input']==order['case_ids'][ep-1],'Paired registered training input');data=load(out/(row['label']+'.frames.pt.gz'));bind(row,data);manual(data['frames'],learner.net)
    for f in data['frames']:
     index,replay=learner.choose(dict(x=f['x'],mask=f['mask'],scores=f['scores']),True);need(index==f['index']and abs(replay['old_logp']-f['old_logp'])<1e-7,'Exact action RNG draw');need(np.array_equal(replay['value'],f['value']),'Saved Torch critic');need(replay['network_sha256']==f['network_sha256'],'On-policy fixed weights')
    old=learner.updates;learner.add(data['frames'],data['costs']);same(learner.snapshot(),after)
    if learner.updates>old:replayed_updates+=1;changed=any(not torch.equal(before['network'][k],after['network'][k])for k in before['network']if k.startswith('actor.'));need(changed,'Actor weights changed');actor_changes+=int(changed)
   need(learner.updates==16 and learner.episodes==32,'Full paired finite training');optimizer_diagnostics.append(dict(variant=variant,seed=seed,updates=learner.updates,Adam_steps=learner.steps,max_reported_minibatch_KL=max(x['max_KL']for x in learner.logs),updates_with_reported_KL_above_epoch_stop=sum(x['max_KL']>.05 for x in learner.logs),aux_weight_first=learner.logs[0]['aux_weight'],aux_weight_last=learner.logs[-1]['aux_weight'],qualification='Saved training diagnostics only. KL is monitored after minibatches and stops later epochs, not a hard trust region or a causal explanation of seed differences.'));print('NN_EXACT_TRAIN_REPLAY',variant,seed,flush=True)
 nets={}
 for row in result['rows']:
  if not row['policy'].startswith('RL_')or row['kind']=='TRAIN':continue
  key=(row['variant'],row['seed'])
  if key not in nets:
   learner=Learner(row['seed']);snapshot=load(op['parent_checkpoints'][str(op['frozen_parent_seed'])])if row['variant']=='FROZEN'else load(out/f'{row["variant"]}_S{row["seed"]}_EP032.pt.gz');learner.restore(snapshot);nets[key]=learner.net
  data=load(out/(row['label']+'.frames.pt.gz'));bind(row,data);need(digest(nets[key])==row['network_sha256'],'Frozen evaluation weights');manual(data['frames'],nets[key])
 need(replayed_updates==96 and actor_changes==96,'All new96 updates independently replayed');need(result['START']==512,'Full new lineage')
 save(out/'NN_DECISION_DIAGNOSIS.json',dict(status='SAVED_ON_POLICY_ACTIONABILITY_DIAGNOSIS',rows=decision_diagnostics,optimizer=optimizer_diagnostics,new_environment=0,new_training=0,physical_validation=False))
 save(out/'PUBLIC_BANK_SAMPLES.json.gz',dict(status='SAVED_ACTUAL_NN_INPUT_SAMPLES',samples=public_samples,new_environment=0,new_training=0))
 audit=dict(status='PASS_INDEPENDENT_NUMPY_AND_PAIRED_RNG_ADAM_REPLAY',utc=now(),checks=checks,frames=frames_count,replayed_PPO_updates=replayed_updates,actor_weight_changes=actor_changes,evaluation_frames=eval_frames,evaluation_nonfirst_actions=nonfirst,evaluation_WAIT_actions=wait_actions,max_numpy_logprob_error=maxlog,max_numpy_critic_error=maxcritic,elapsed_s=time.monotonic()-begin,new_environment=0,new_training=0,physical_validation=False);save(out/'NN_AUDIT.json',audit);print(json.dumps(audit),flush=True)
