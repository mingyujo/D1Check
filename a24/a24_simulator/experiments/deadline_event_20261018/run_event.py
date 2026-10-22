"""Privileged training expert; every deployed decision uses public inputs only."""
from pathlib import Path
import copy,gc,os,subprocess,sys,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'deep_repair_20261018'))
from common import B,ROOT,np,torch,read,saved,pt,loadpt
sys.path.insert(0,str(HERE.parent/'witness_gap_20261018_v3'))
from page_resources import wait_resources
sys.path.insert(0,str(HERE.parent/'density_headroom_20261018'))
from actors import Actor
from bounds import envelopes,build
sys.path.insert(0,str(HERE.parent/'packing_rl_20261018'))
sys.path.insert(0,str(HERE))
from packing_encoder import PackingEncoder
from packing_learner import Learner
from event_labels import labels
from nn_train import digest
ENTRY=Path(__file__).resolve();os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)
B.G.OWN_TOKENS+=('deadline_event_20261018',)

def equal(a,b):
    if torch.is_tensor(a):assert torch.equal(a,b),'Exact tensor replay'
    elif isinstance(a,np.ndarray):assert np.array_equal(a,b),'Exact array replay'
    elif isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:equal(a[k],b[k])
    elif isinstance(a,(tuple,list)):
        assert len(a)==len(b)
        for u,v in zip(a,b):equal(u,v)
    else:assert a==b,'Exact scalar replay'

def replay(out,rows):
    episodes=frames=updates=greedy=0
    for row in rows:
        source=out/(row['label']+'.BEFORE.pt.gz') if row['kind']=='TRAIN' else out/row['network_file'];learner=Learner(loadpt(source));data=loadpt(out/(row['label']+'.frames.pt.gz'))
        for f in data['frames']:
            i,again=learner.choose({k:f[k] for k in ('x','mask','scores')},row['kind']=='TRAIN');assert i==f['index'] and again['old_logp']==f['old_logp'] and np.array_equal(again['value'],f['value']);frames+=1
        if row['kind']=='TRAIN':
            before=learner.updates;learner.add(data['frames'],data['costs']);equal(learner.snapshot(),loadpt(out/(row['label']+'.AFTER.pt.gz')));updates+=learner.updates-before;episodes+=1
        else:greedy+=len(data['frames'])
    B.G.write_new(out/'STOCHASTIC_REPLAY.json',dict(status='PASS',BC_exact_optimizer_replay=False,reused_frozen_BC_warm=True,BC_epochs=0,reused_BC_epochs=64,exact_saved_greedy_replay=True,episodes=episodes,frames=frames,greedy_frames=greedy,exact_saved_optimizer_update_replays=updates,new_environment_START=0,new_training_data=0))

def main():
    op=read(HERE/'OPERATION.json');opsha=B.G.sha(HERE/'OPERATION.json');out=ROOT/op['output_dir'];assert '--published' in sys.argv
    assert subprocess.check_output(['git','show','HEAD:'+str((HERE/'OPERATION.json').relative_to(ROOT.parent)).replace('\\','/')])==(HERE/'OPERATION.json').read_bytes()
    for p in op['sources']+op['input_pins']:B.G.pin(p)
    assert not out.exists(),'Consumed operation'
    guard=wait_resources(ENTRY,1536*1024**2,time.monotonic()+1800);B.G.free_guard([ROOT,'D:/'])
    import msvcrt
    lock=(ROOT/'runtime/a24_local_worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);begin=time.monotonic();count=0;rows=[];solves=0
    try:
        out.mkdir();B.G.write_new(out/'START.json',dict(utc=B.G.now(),operation_sha256=opsha,guard=guard,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))
        try:
            inputs=read(op['inputs']['path']);training=inputs['training'];evaluation=inputs['evaluation'];catalog=read(B.L.pin(B.registration(op)['catalog_pin']));nominals=read(op['public_nominals']['path']);physics=B.Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),B.Config(**op['physics']));references=op['reward_references']
            B.G.write_new(out/'GRADIENT_PROBES.json',dict(records=[]))
            def getbank(case):
                public,contexts=B.public_input(case,catalog);public['initial_ap_c']=case['temperature_c'];bank=read(op['bank_map'][case['id']]['path']);vectors=nominals[case['id']] if case['id'].startswith('DENSITY_') else bank['nominal_vectors']
                return public,B.BankModel(bank['jobs'],contexts),B.SavedNominal(public,[dict(nominal_vectors=vectors)]),bank['jobs']
            def slot(case):
                assert time.monotonic()-begin<op['wall_clock_limit_s'];return wait_resources(ENTRY,768*1024**2+case['n']*128*1024,begin+op['wall_clock_limit_s'])
            def simulate(case,policy,kind,learner=None,expert=None):
                nonlocal count
                resource=slot(case);B.G.free_guard([ROOT,'D:/']);assert count<op['environment_cap'];label=case['id']+'_'+policy if kind!='TRAIN' else policy
                receipt=dict(event='START',label=label,case=case['id'],policy=policy.split('_TRAIN_')[0],kind=kind,utc=B.G.now(),identity=B.L.digest([opsha,label]),start_id=B.L.digest([opsha,label]),durable_START_consumed=True,operation_sha256=opsha)
                B.G.append(out/'receipts.jsonl',receipt);count+=1;print('START',count,label,flush=True)
                try:
                    public,model,nominal,jobs=getbank(case);collect=kind=='TRAIN';neural=learner is not None;actor=PackingEncoder(nominal,physics,case,learner,collect,expert)
                    if collect:pt(out/(label+'.BEFORE.pt.gz'),learner.snapshot())
                    network=digest(learner.net) if neural else None
                    result=B.execute(public,model,actor,physics,case['common_potential_key'],receipt);metrics=B.metrics(result,case,physics);calls=[c for c in actor.calls if not c.get('common_coalescing')]
                    if neural:
                        assert len(calls)==len(actor.frames)
                        for call,f in zip(calls,actor.frames):call.update(old_logp=f['old_logp'],critic_value=f['value'].tolist(),collect=collect)
                    file=out/(label+'.raw.json.gz');saved(file,dict(result=result,calls=actor.calls,future_actual_work_used=expert is not None,privileged_training_expert=expert is not None));costs=audit=None;frames_sha=None
                    if neural:
                        joint=not policy.startswith('EVENT_ENERGY');ref=references[case['id']];costs,audit=labels(result,actor.frames,case,physics,metrics,ref['reference_end_ns'],ref,joint)
                        p=out/(label+'.frames.pt.gz');pt(p,dict(frames=actor.frames,costs=costs,reward_audit=audit,collect=collect,network_sha256=network));frames_sha=B.G.sha(p)
                        if collect:learner.add(actor.frames,costs);pt(out/(label+'.AFTER.pt.gz'),learner.snapshot())
                    if expert is not None:pt(out/(label+'.expert_frames.pt.gz'),dict(frames=actor.frames,semantic_labels_only=True,future_information_in_training_labels_only=True))
                    arm=policy.split('_TRAIN_')[0];network_file=label+'.BEFORE.pt.gz' if collect else ('PACKING_BC_ONLY.FINAL_WARM.pt.gz' if arm=='PACKING_BC_ONLY' else arm+'.FINAL_EP032.pt.gz')
                    row=dict(label=label,case=case['id'],policy=receipt['policy'],kind=kind,n=case['n'],condition=case['condition'],metrics=metrics,raw_sha256=B.G.sha(file),frames_sha256=frames_sha,network_sha256=network,network_file=network_file if neural else None,network_temperature=learner.temperature if neural else None,selector_kind=None,reward_kind=audit['reward_kind'] if audit else 'EXPERT' if expert else 'PUBLIC_PACKING',reference_end_ns=references[case['id']]['reference_end_ns'],reward_audit=audit,selected_NN_WAIT_s=sum(c['action'].get('wait_ns',0)/1e9 for c in calls) if neural else None,resource_guard=resource)
                    B.G.write_new(out/(label+'.json'),row);rows.append(row);B.G.append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','utc':B.G.now(),'raw_sha256':row['raw_sha256']});print('COMPLETE',label,metrics['on_time'],metrics['urgent_on_time'],'elapsed',round(time.monotonic()-begin,1),flush=True)
                    del result,actor;gc.collect();return row
                except BaseException as exc:B.G.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','error':str(exc),'utc':B.G.now(),'automatic_retry':False});raise
            warm=loadpt(op['warm_checkpoint']['path']);equal(warm,loadpt(op['paired_initial_snapshot']['path']));pt(out/'REUSED_BC_WARM.pt.gz',warm)
            B.G.write_new(out/'WARM_EXACT.json',dict(status='PASS',full_actor_critic_two_Adam_and_RNG_exact=True,new_BC_epochs=0,reused_BC_epochs=64))
            for arm in op['arms']:
                learner=Learner(copy.deepcopy(warm));initial_digest=digest(learner.net)
                for ep in range(32):
                    row=simulate(training[ep%8],arm+f'_TRAIN_{ep+1:03d}','TRAIN',learner)
                    if ep<2:
                        expected=read(Path(op['parent_output'])/(op['parent_arm_map'][arm]+f'_TRAIN_{ep+1:03d}.raw.json.gz'))['result'];actual=read(out/(row['label']+'.raw.json.gz'))['result']
                        for key in ('requests','trace','decisions'):assert B.G.canonical(expected[key])==B.G.canonical(actual[key]),'Exact matched parent before first reward-dependent update'
                        del expected,actual;gc.collect()
                        if ep==1:B.G.write_new(out/(arm+'.PAIRED_PARENT_PREFIX_PASS.json'),dict(status='PASS',episodes=[1,2],parent_arm=op['parent_arm_map'][arm]))
                    if arm==op['arms'][1] and ep<2:
                        parent=read(out/(op['arms'][0]+f'_TRAIN_{ep+1:03d}.raw.json.gz'))['result'];actual=read(out/(row['label']+'.raw.json.gz'))['result']
                        for key in ('requests','trace','decisions'):assert B.G.canonical(parent[key])==B.G.canonical(actual[key]),'Paired physical trajectory before first objective-dependent update'
                        del parent,actual;gc.collect()
                assert learner.episodes==32 and learner.updates==16 and digest(learner.net)!=initial_digest and not learner.pending
                pt(out/(arm+'.FINAL_EP032.pt.gz'),learner.snapshot());B.G.write_new(out/(arm+'.LEARNING.json'),dict(new_episodes=32,new_updates=16,new_Adam_steps=2*learner.steps,initial_digest=initial_digest,final_digest=digest(learner.net),logs=learner.logs));del learner;gc.collect()
            B.G.write_new(out/'SELECTION_FROZEN.json',dict(rule='Fixed final EP32 of both event-timed arms in all30; parent BC/rule results retained',evaluation_checkpoint_selection=False))
            for case in evaluation:
                for arm in op['arms']:
                    learner=Learner(loadpt(out/('PACKING_BC_ONLY.FINAL_WARM.pt.gz' if arm=='PACKING_BC_ONLY' else arm+'.FINAL_EP032.pt.gz')));simulate(case,arm,'EVAL',learner);del learner;gc.collect()
            assert count==124 and solves==0
            for p in op['sources']+op['input_pins']:B.G.pin(p)
            B.G.write_new(out/'RESULT.json',dict(status='COMPLETED',rows=rows,new_START=count,new_COMPLETE=count,new_FAIL=0,new_training=64,new_updates=32,new_experts=0,new_evaluations=60,new_LP_solves=solves,BC_epochs=0,reused_BC_epochs=64,new_physical_fit=0,operation_sha256=opsha));B.G.write_new(out/'COMPLETE.json',dict(utc=B.G.now(),elapsed_s=time.monotonic()-begin,result_sha256=B.G.sha(out/'RESULT.json')))
            replay(out,rows);subprocess.run([op['node_executable'],str(HERE/'audit.cjs')],check=True);subprocess.run([op['node_executable'],str(HERE/'report.cjs')],check=True)
        except BaseException as exc:B.G.write_new(out/('POSTPROCESS_FAILURE.json' if (out/'COMPLETE.json').exists() else 'FAILURE.json'),dict(utc=B.G.now(),error=str(exc),new_START=count,new_LP_solves=solves,automatic_retry=False));raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
