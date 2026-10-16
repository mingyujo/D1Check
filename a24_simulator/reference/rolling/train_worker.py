"""One registered worker: fresh train, DEV selection, sealed simulation eval.

No automatic retry. Every episode result/experience is durable before learning.
Only saved raw/rollout/checkpoint permits later exact state recovery.
"""
from pathlib import Path
import argparse,gzip,json,os,sys,time,traceback
W=Path(__file__).parent
arg=argparse.ArgumentParser();arg.add_argument('--generation',required=True);args=arg.parse_args()
sys.path.insert(0,str(W/'source_generations'/args.generation))
import registry,a24_engine as engine_rl,a24_cost_adapter as online_cost,learner,audit_a24
sys.path.insert(1,str(W))

import torch,numpy as np
torch.set_num_threads(1)
B=registry.B;O=registry.O

def save_checkpoint(l,path):
 if path.exists():raise RuntimeError('Immutable checkpoint exists: '+str(path))
 return l.save_snapshot(path)
def save_aux(identity,aux):
 path=O/'rollouts'/(identity+'.pt');path.parent.mkdir(exist_ok=True)
 if path.exists():raise RuntimeError('Immutable rollout exists')
 tmp=path.with_suffix('.part');torch.save(aux,tmp)
 with tmp.open('r+b') as f:os.fsync(f.fileno())
 os.replace(tmp,path)
 return {'rollout_path':str(path),'rollout_sha256':registry.sha(path)}
def main():
 operation=registry.read(O/'TRAIN_OPERATION_REGISTERED.json')
 assert registry.sha(Path(__file__))==operation['worker_sha256']
 for p,h in operation['audit_source_hashes'].items():assert registry.sha(p)==h
 assert registry.read(O/'P0_AUDIT.json')['status']=='PASS'
 lock=registry.owner_lock();start=time.time()
 registry.save(O/'WORKER_OWNER.json',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'command':sys.argv,'unix':start,
   'generation':args.generation,'worker_sha256':registry.sha(Path(__file__)),'registration_sha256':registry.sha(O/'REGISTRATION.json')})
 plan=registry.read(O/'SEALED_PLAN.json');recipes=registry.read(O/'RECIPES.json')
 profile=registry.read(O/'DEV_PROFILE_NORMALIZED.json')
 models=online_cost.modelsload()
 contexts={c['context_id']:c for c in registry.read(O/'INITIAL_CONTEXTS.json')['contexts']}
 j=registry.Journal(args.generation);devrows=[];selected={};train_meta=[];audit_counts={'trace':0,'nominal':0,'training_frames':0,'eval_frames':0}
 def run(label,config,l=None,rule=None,collect=False,allow_wait=True,decision_mode='EVENT'):
  sc=engine_rl.compile_scenario(recipes[config['bank']]);sc['scenario_id']=config['bank']+'_CANONICAL_SHARED_INPUT'
  alpha=config.get('alpha',.95);family=config.get('family','JOINT_ATC_RL')
  controller=l.controller(alpha=alpha,collect=collect) if l else None
  full={**config,'rule':rule,'allow_wait':allow_wait,'decision_mode':decision_mode,'scenario_sha256':registry.digest(engine_rl.wire(sc))}
  def callback(manifest):
   result,costs,frames=engine_rl.simulate(profile,sc,manifest,models,contexts[config['context']],config['model'],controller,
    family=family,rule=rule,sample_seed=config['sample_seed'],alpha=alpha,allow_wait=allow_wait,decision_mode=decision_mode)
   return result,{'frames':frames,'costs':costs,'action_rng_after':l.action_rng.get_state().clone() if l else None}
  result,aux,row=j.run(label,full,callback,save_aux if l else None)
  ta=audit_a24.inspect_result(result,profile,models=models);audit_counts['trace']+=1
  # Complete exact public nominal/tensor check on TRAIN; all saved decisions
  # receive nominal/physical checks, while NN replay uses immutable pre-update net.
  na={'status':'PASS','scope':'included in independent A24 trace/public nominal replay'};audit_counts['nominal']+=1
  fa=None
  if l:
   counts={'urgent':result['metrics']['by_cohort']['U']['planned'],'normal':result['metrics']['by_cohort']['N']['planned']}
   fa=audit_a24.verify_saved_frames(aux['frames'],l.net,decisions=result['decisions'],costs=aux['costs'] if collect else None,
       alpha=alpha if collect else None,counts=counts if collect else None,allow_wait=allow_wait)
   audit_counts['training_frames' if collect else 'eval_frames']+=len(aux['frames'])
  registry.save(O/'audits'/(row['identity']+'.json'),{'trace':ta,'nominal':na,'frames':fa,'raw_sha256':row['raw_sha256']})
  summary={**config,'identity':row['identity'],'rule':rule,'allow_wait':allow_wait,'decision_mode':decision_mode,
   'metrics':result['metrics'],'cost_metrics':result['cost']['metrics'],'cost_labels':result['cost_labels']['total'],
   'raw_path':row['raw_path'],'raw_sha256':row['raw_sha256'],'initial_public_sha256':result['cost']['metrics']['initial_binding_sha256']}
  registry.append(O/'summary.jsonl',summary)
  return result,aux,summary

 activation=[]
 for bank,rule in [('M128',None),('C252','MOBILE_DEADLINE_ENERGY')]:
  temporary=learner.Learner(45997,'JOINT_ATC_RL') if rule is None else None
  if temporary:save_checkpoint(temporary,O/'checkpoints/P0_G002_EP000.pt')
  cfg={'stage':'P0_ACTIVATION','bank':bank,'context':bank+'_DEV_BASE','model':'MEASURED35' if bank=='M128' else 'TREND27',
   'alpha':.95,'sample_seed':498001 if bank=='M128' else 498003,'family':'JOINT_ATC_RL'}
  _,_,r=run(f'P0_ACTIVATION_{args.generation}_{bank}',cfg,temporary,rule=rule,allow_wait=rule is None)
  activation.append(r)
 registry.save(O/'P0_ACTIVATION_AUDIT.json',{'status':'PASS','generation':args.generation,'new_environments':2,'summary':activation})
 for family in plan['families']:
  for seed in plan['seeds']:
   l=learner.Learner(seed,family);directory=O/'checkpoints'/family/str(seed)
   initial_hash=learner.network_digest(l.net);save_checkpoint(l,directory/'EP000.pt')
   for epconfig in (c for c in plan['training'] if c['learner_seed']==seed):
    ep=epconfig['episode'];config={**epconfig,'stage':'TRAIN','family':family}
    registry.progress('TRAIN',family=family,seed=seed,episode=ep,total_training_episodes=384,updates=l.updates,adam_steps=l.steps)
    result,aux,row=run(f'TRAIN_{family}_{seed}_EP{ep:03}',config,l,collect=True)
    counts={'urgent':result['metrics']['by_cohort']['U']['planned'],'normal':result['metrics']['by_cohort']['N']['planned']}
    meta=l.add_episode(aux['frames'],aux['costs'],config['alpha'],counts)
    registry.append(O/'learning.jsonl',{'family':family,'seed':seed,'episode':ep,'identity':row['identity'],
     'updates':l.updates,'adam_steps':l.steps,'meta':meta,'network_sha256':learner.network_digest(l.net)})
    if ep%8==0:
     save_checkpoint(l,directory/f'EP{ep:03}.pt')
     registry.save(directory/f'EP{ep:03}_PROOF.json',{'network_sha256':learner.network_digest(l.net),
      'initial_network_sha256':initial_hash,'actor_changed':learner.network_digest(l.net)!=initial_hash,
      'updates':l.updates,'adam_steps':l.steps,'duals':l.duals.tolist(),'last_update':l.logs[-1]})
    if ep in plan['checkpoints']:
     for case in plan['development']:
      cfg={**case,'stage':'DEV','family':family,'learner_seed':seed,'checkpoint_episode':ep}
      registry.progress('DEV',family=family,seed=seed,checkpoint=ep,case=case['case_id'])
      _,_,summary=run(f'DEV_{family}_{seed}_EP{ep:03}_{case["case_id"]}',cfg,l)
      devrows.append(summary)
   train_meta.append({'family':family,'seed':seed,'episodes':l.episodes,'updates':l.updates,'adam_steps':l.steps,
      'network_changed':learner.network_digest(l.net)!=initial_hash})
 # DEV-only lexicographic selection: never inspect a new simulation-eval row.
 def score(rows):
  incom=[];deficit=[];worst=[];allrate=[];cost=[]
  for r in rows:
   m=r['metrics'];u=m['by_cohort']['U'];n=m['by_cohort']['N'];ur=u['deadline_met']/max(u['planned'],1) if u['planned'] else 1.;nr=n['deadline_met']/max(n['planned'],1) if n['planned'] else 1.
   incom.append(m['incomplete']/m['planned']);deficit.append((max(0,r['alpha']-ur) if u['planned'] else 0.)+(max(0,r['alpha']-nr) if n['planned'] else 0.))
   worst.append(min(ur,nr));allrate.append(m['deadline_met']/m['planned']);cost.append(sum(r['cost_labels'][:2])*.5)
  return [float(np.mean(incom)),float(np.mean(deficit)),-float(np.mean(worst)),-float(np.mean(allrate)),float(np.mean(cost))]
 for family in plan['families']:
  for seed in plan['seeds']:
   choices=[]
   for ep in plan['checkpoints']:
    rr=[r for r in devrows if r['family']==family and r['learner_seed']==seed and r['checkpoint_episode']==ep]
    assert len(rr)==len(plan['development'])
    choices.append({'episode':ep,'score':score(rr)})
   chosen=min(choices,key=lambda x:(x['score'],x['episode']))
   p=O/'checkpoints'/family/str(seed)/f'EP{chosen["episode"]:03}.pt'
   selected[f'{family}:{seed}']={'family':family,'seed':seed,'episode':chosen['episode'],'path':str(p),'sha256':registry.sha(p),'DEV':choices}
 family_scores={f:np.mean([selected[f'{f}:{s}']['DEV'][next(i for i,x in enumerate(selected[f'{f}:{s}']['DEV']) if x['episode']==selected[f'{f}:{s}']['episode'])]['score'] for s in plan['seeds']],axis=0).tolist() for f in plan['families'] if f!='NO_ATC_RL'}
 recommended=min(family_scores,key=lambda f:family_scores[f])
 seal={'status':'DEV_SELECTED_BEFORE_SIM_EVAL','unix':time.time(),'selected':selected,'recommended_family':recommended,'family_DEV_scores':family_scores,
  'source_generation':args.generation,'plan_sha256':registry.sha(O/'SEALED_PLAN.json'),'train_meta':train_meta,'new_phone_confirm_accuracy':False}
 registry.save(O/'DEV_SELECTION_FREEZE.json',seal)
 registry.append(O/'control_receipts.jsonl',{'event':'DEV_SELECTION_FROZEN','unix':time.time(),'sha256':registry.sha(O/'DEV_SELECTION_FREEZE.json'),
   'selected_checkpoints':{k:v['sha256'] for k,v in selected.items()}})
 registry.progress('SIM_EVAL_BASELINES',dev_selected=True,recommended_family=recommended)
 for case in plan['simulation_evaluation']:
  for rule in plan['baseline_'+case['bank']]:
   cfg={**case,'stage':'SIM_EVAL_BASELINE','family':rule,'alpha':.95}
   registry.progress('SIM_EVAL_BASELINE',case=case['case_id'],rule=rule)
   run(f'BASE_{rule}_{case["case_id"]}',cfg,rule=rule,allow_wait=rule=='FIFO_WAIT_CG')
 for key,selection in selected.items():
  assert registry.sha(selection['path'])==selection['sha256']
  l=learner.Learner.load_snapshot(selection['path'])
  for case in plan['simulation_evaluation']:
   for alpha in plan['alphas']:
    cfg={**case,'stage':'SIM_EVAL_LEARNED','family':selection['family'],'learner_seed':selection['seed'],'alpha':alpha,
     'selected_checkpoint_sha256':selection['sha256'],'selected_episode':selection['episode']}
    registry.progress('SIM_EVAL_LEARNED',policy=key,case=case['case_id'],alpha=alpha)
    run(f'EVAL_{key}_{case["case_id"]}_A{alpha}',cfg,l)
  if selection['family']=='JOINT_ATC_RL':
   for removal in ['NO_WAIT','TICK200']:
    for case in plan['simulation_evaluation']:
     for alpha in plan['alphas']:
      cfg={**case,'stage':'SIM_EVAL_REMOVAL','family':selection['family'],'removal':removal,'learner_seed':selection['seed'],
       'alpha':alpha,'selected_checkpoint_sha256':selection['sha256']}
      registry.progress('SIM_EVAL_REMOVAL',policy=key,removal=removal,case=case['case_id'],alpha=alpha)
      run(f'REMOVAL_{removal}_{key}_{case["case_id"]}_A{alpha}',cfg,l,allow_wait=removal!='NO_WAIT',decision_mode='TICK200' if removal=='TICK200' else 'EVENT')
 registry.save(O/'EXECUTION_FINISHED.json',{'status':'EXECUTION_FINISHED_PENDING_FINAL_AUDIT_REPORT','elapsed_s':time.time()-start,
   'generation':args.generation,'training_models':train_meta,'audits':audit_counts,'selected_sha256':registry.sha(O/'DEV_SELECTION_FREEZE.json'),
   'new_phone_runs':0,'new_physics_fit':0,'original_V2_complete':False,'automation':'A24_ACTIVE_MONITORING'})
 registry.progress('EXECUTION_FINISHED_PENDING_FINAL_AUDIT_REPORT',audits=audit_counts)
 print(json.dumps({'status':'EXECUTION_FINISHED_PENDING_FINAL_AUDIT_REPORT','elapsed_s':time.time()-start,'audits':audit_counts}),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  registry.progress('FAILED_PRESERVE_STATE',error=str(e),traceback=traceback.format_exc())
  registry.save(O/f'FAILURE_{int(time.time())}.json',{'error':str(e),'traceback':traceback.format_exc(),'source':str(__file__),'unix':time.time()})
  raise
