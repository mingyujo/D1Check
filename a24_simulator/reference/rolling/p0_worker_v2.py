"""Disposable registered A24 pretraining verification, not production data."""
from pathlib import Path
import sys,json,os
W=Path(__file__).parent;generation='A24INT_G002';sys.path.insert(0,str(W/'source_generations'/generation))
import registry,a24_engine,timing_bridge,a24_cost_adapter,learner,audit_a24
import torch,numpy as np
torch.set_num_threads(1)
B=registry.B;O=registry.O
EP000_SHA256='f233bc74cc2476637e2fd80dacf10bc2040e005cc47bafb2aa1de667b39c3988'
def auxwrite(identity,aux):
 p=O/'rollouts'/(identity+'.pt');p.parent.mkdir(exist_ok=True)
 if p.exists():raise RuntimeError('immutable rollout')
 temp=p.with_name(p.name+'.part');torch.save(aux,temp)
 with temp.open('r+b') as f:os.fsync(f.fileno())
 os.replace(temp,p)
 return {'rollout_path':str(p),'rollout_sha256':registry.sha(p)}
def main():
 operation=registry.read(O/'P0_FINISH_OPERATION_REGISTERED.json')
 if operation.get('allow_execution') is not True or operation.get('generation')!=generation:raise RuntimeError('P0 operation authorization/generation')
 if registry.sha(Path(__file__))!=operation['operator_source_sha256']:raise RuntimeError('P0 operator SHA')
 if operation['sample_seeds']!=list(range(799101,799109)):raise RuntimeError('new P0 sample seeds only')
 if (O/'P0_AUDIT.json').exists():raise RuntimeError('P0 already complete; read immutable audit')
 lock=registry.owner_lock();registry.guard(generation)
 numeric=registry.read(O/'NUMERIC_AUDIT.json')
 if numeric.get('status')!='PASS' or numeric.get('new_environment')!=0 or numeric.get('cost_only_model_wrapper_instances')!=6:raise RuntimeError('numeric6 pre-START PASS required')
 numeric_events=[x for x in registry.events(O/'cost_audit_receipts.jsonl') if x.get('identity')=='A24_FIXED_MODEL_NUMERIC_G002_001']
 if [x.get('event') for x in numeric_events]!=['START','COMPLETE'] or numeric_events[-1]['sha256']!=registry.sha(O/'NUMERIC_AUDIT.json'):raise RuntimeError('complete immutable numeric6 cost receipt chain required')
 numeric_op=registry.read(O/'NUMERIC_OPERATION_REGISTERED.json')
 if numeric_events[0]['operation_sha256']!=registry.sha(O/'NUMERIC_OPERATION_REGISTERED.json') or numeric_events[0]['operator_sha256']!=numeric_op['source_sha256'] or registry.sha(W/'numeric_audit.py')!=numeric_op['source_sha256']:raise RuntimeError('numeric operation/source binding')
 models=a24_cost_adapter.modelsload();profile=registry.read(O/'DEV_PROFILE_NORMALIZED.json')
 ctx=next(x for x in registry.read(O/'INITIAL_CONTEXTS.json')['contexts'] if x['context_id']=='M128_DEV_BASE')
 recipe=registry.read(O/'RECIPES.json')['M128'];j=registry.Journal(generation)
 cp=O/'checkpoints/P0_EP000.pt'
 if Path(operation['checkpoint_path']).resolve()!=cp.resolve() or operation['checkpoint_sha256']!=EP000_SHA256 or not cp.is_file() or registry.sha(cp)!=EP000_SHA256:raise RuntimeError('exact copied zero-episode checkpoint required; no regeneration')
 l=learner.Learner.load_snapshot(cp)
 if l.episodes!=0 or l.steps!=0 or l.updates!=0 or l.pending or l.pending_meta or l.logs or l.opt.state_dict()['state'] or l.seed!=46299 or l.family!='JOINT_ATC_RL':raise RuntimeError('fresh P0 state required')
 initial_sha=learner.network_digest(l.net)
 proof=[]
 for ep in range(1,9):
  sc=a24_engine.compile_scenario(recipe);sc['requests']=sc['requests'][:8];sc['scenario_id']=f'P0_{generation}_{ep}'
  c=l.controller(alpha=.95,collect=True)
  def cb(manifest):
   result,costs,frames=a24_engine.simulate(profile,sc,manifest,models,ctx,'MEASURED35',c,sample_seed=799100+ep,alpha=.95)
   return result,{'frames':frames,'costs':costs,'action_rng_after':l.action_rng.get_state().clone()}
  config={'stage':'P0','episode':ep,'scenario_sha256':registry.digest(a24_engine.wire(sc)),'sample_seed':799100+ep}
  registry.progress('P0',episode=ep)
  result,aux,row=j.run(f'P0_{generation}_EP{ep:03}',config,cb,auxwrite)
  counts={'urgent':sum(r['priority']=='U' for r in sc['requests']),'normal':sum(r['priority']=='N' for r in sc['requests'])}
  audit=audit_a24.inspect_result(result,profile,models)
  fa=audit_a24.verify_saved_frames(aux['frames'],l.net,decisions=result['decisions'],costs=aux['costs'],alpha=.95,counts=counts)
  meta=l.add_episode(aux['frames'],aux['costs'],.95,counts)
  proof.append({'identity':row['identity'],'trace_audit':audit,'frame_audit':fa,'labels':meta})
 after=learner.network_digest(l.net)
 if initial_sha==after or l.steps<1 or l.updates!=1:raise RuntimeError('Native PPO update not verified')
 if (O/'checkpoints/P0_EP008.pt').exists():raise RuntimeError('immutable P0 EP008 exists')
 l.save_snapshot(O/'checkpoints/P0_EP008.pt')
 registry.save(O/'P0_AUDIT.json',{'status':'PASS','generation':generation,'environment_starts':8,'native_updates':l.updates,'adam_steps':l.steps,
  'initial_network_sha256':initial_sha,'updated_network_sha256':after,'proof':proof,'new_physics_fit':0,'device':0,
  'initial_checkpoint_path':str(cp),'initial_checkpoint_sha256':registry.sha(cp),'operation_sha256':registry.sha(O/'P0_FINISH_OPERATION_REGISTERED.json'),
  'numeric_audit_sha256':registry.sha(O/'NUMERIC_AUDIT.json'),'sample_seeds':operation['sample_seeds'],'predecessor_failed_episode_retried':False})
 registry.progress('P0_PASS',adam_steps=l.steps)
 print(json.dumps({'status':'PASS','P0':8,'updates':l.updates,'adam_steps':l.steps}),flush=True)
if __name__=='__main__':main()
