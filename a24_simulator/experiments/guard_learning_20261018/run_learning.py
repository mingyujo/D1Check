"""Finite paired fine-tuning and targeted repair, with final EP32 evaluation."""
from pathlib import Path
import ast,gc,gzip,importlib.util,io,json,os,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ENTRY=Path(__file__).resolve()
sys.path.insert(0,str(ROOT/'experiments/coupled_345_20261017'))
from bootstrap import L,G,registration,public_input,save_binary
from dynamics import Physics,Config,WEIGHTS
from engine import run as execute,metrics
from nn_train import Learner,digest
sys.path[:0]=[str(HERE),str(ROOT/'experiments/guard_ablation_20261018_v3')]
from guard_controller import GuardController
from bank_model import BankModel,SavedNominal
from repair_controller import RepairController
from paired_initialization import independently_restored
from repair_rewards import labels as repaired_labels,old as original_rewards
spec=importlib.util.spec_from_file_location('moderate_bank_builder',ROOT/'experiments/moderate_load_20261018/run_moderate.py')
_bank_directory=str(ROOT/'experiments/moderate_load_20261018');sys.path.insert(0,_bank_directory)
bank_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(bank_module)
sys.path.remove(_bank_directory)
import numpy as np
from resource_learning import wait_resources
import torch
torch.set_num_threads(1)
os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)
G.OWN_TOKENS+=('guard_learning_20261018','moderate_load_20261018','guard_ablation_20261018','coupled_345_20261017')

def read(p):
    p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)

def saved(p,x):save_binary(p,gzip.compress(G.canonical(x).encode(),mtime=0))

def pt(p,x):
    b=io.BytesIO();torch.save(x,b);save_binary(p,gzip.compress(b.getvalue(),mtime=0))

def loadpt(p):return torch.load(io.BytesIO(gzip.decompress(Path(p).read_bytes())),map_location='cpu',weights_only=False)

def replay_training(out,rows):
    total=0;records=[];replayed_updates=0
    for row in rows:
        if row['kind']!='TRAIN':continue
        before=loadpt(out/(row['label']+'.BEFORE.pt.gz'));after=loadpt(out/(row['label']+'.AFTER.pt.gz'));data=loadpt(out/(row['label']+'.frames.pt.gz'))
        learner=Learner(before['seed']);learner.restore(before)
        for f in data['frames']:
            idx,again=learner.choose({k:f[k] for k in ('x','mask','scores')},True)
            G.require(idx==f['index'] and again['old_logp']==f['old_logp'] and np.array_equal(again['value'],f['value']),'Exact stored stochastic RNG/input replay')
            total+=1
        G.require(torch.equal(learner.action_rng.get_state(),after['action_rng']),'All sampled actions account for action RNG')
        learner.add(data['frames'],data['costs'])
        def compare(a,b):
            if torch.is_tensor(a):G.require(torch.equal(a,b),'Exact saved optimizer/RNG/parameter tensor replay')
            elif isinstance(a,np.ndarray):G.require(np.array_equal(a,b),'Exact saved frame arithmetic replay')
            elif isinstance(a,dict):
                G.require(a.keys()==b.keys(),'Replay dictionary keys')
                for k in a:compare(a[k],b[k])
            elif isinstance(a,(list,tuple)):
                G.require(len(a)==len(b),'Replay sequence length')
                for x,y in zip(a,b):compare(x,y)
            else:G.require(a==b,'Exact saved scalar/Adam/log replay')
        compare(learner.snapshot(),after)
        replayed_updates+=int(after['updates']>before['updates'])
        G.require(np.max(abs(np.asarray(data['costs']).sum(0)-np.asarray(data['reward_audit']['cost_sum'])))<1e-6,'Saved label sum')
        records.append(dict(label=row['label'],frames=len(data['frames']),before_sha256=G.sha(out/(row['label']+'.BEFORE.pt.gz')),after_sha256=G.sha(out/(row['label']+'.AFTER.pt.gz'))))
    G.write_new(out/'STOCHASTIC_REPLAY.json',dict(status='PASS',episodes=len(records),frames=total,exact_saved_optimizer_update_replays=replayed_updates,records=records,new_environment_START=0,same_torch_saved_RNG_replay=True,not_independent_float64_training_replay=True))

def main():
    op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir'];opsha=G.sha(HERE/'OPERATION.json')
    G.require('--published' in sys.argv,'Publish finite registration first')
    for p in [*op['sources'],*op['input_pins']]:G.pin(p)
    G.require(not out.exists(),'Consumed namespace; no retry')
    guard=wait_resources(ENTRY,1536*1024**2,time.monotonic()+1800);volumes=G.free_guard([ROOT,'D:/'])
    import msvcrt
    lockpath=ROOT/'runtime/a24_local_worker.lock'
    if not lockpath.exists():lockpath.write_bytes(b'0')
    lock=lockpath.open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0;rows=[];started=time.monotonic()
    try:
        out.mkdir();G.write_new(out/'START.json',dict(utc=G.now(),operation_sha256=opsha,guard=guard,volumes=volumes,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),uncommitted_changes=bool(subprocess.check_output(['git','status','--porcelain']))))
        try:
            base,_,_=L.initialize(registration(op));catalog=read(L.pin(registration(op)['catalog_pin']))
            physics=Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),Config(**op['physics']))
            inputs=read(op['inputs']['path']);train=inputs['training'];evaluation=inputs['evaluation'];banks={};refs={}
            public_nominals=read(HERE/'PUBLIC_NOMINAL_CATALOG.json.gz')
            for case in train:
                public,contexts=public_input(case,catalog);public['initial_ap_c']=case['temperature_c']
                b=bank_module.bank(public,L.Model(base,contexts),case);saved(out/(case['id']+'.BANK.json.gz'),b)
            initial=loadpt(op['checkpoint']['path']);arms={k:independently_restored(initial,op['learner_seed']) for k in op['arms']}
            for arm,learner in arms.items():pt(out/(arm+'.INITIAL.pt.gz'),learner.snapshot())
            initial_digest=digest(arms[op['arms'][0]].net);initial_counters=(initial['episodes'],initial['updates'],initial['steps'])
            G.require(all(digest(l.net)==initial_digest for l in arms.values()),'Identical initial NN/Adam/RNG')

            def getbank(case):
                cid=case['id'];public,contexts=public_input(case,catalog);public['initial_ap_c']=case['temperature_c']
                if cid.startswith('TRAINMID_'):b=read(out/(cid+'.BANK.json.gz'))
                elif cid.startswith('MID_'):b=read(ROOT/op['moderate_output']/(cid+'.BANK.json.gz'))
                else:
                    b=read(ROOT/op['headroom_output']/(cid+'.BANK.json.gz'))
                    b={**b,'nominal_vectors':public_nominals[cid]}
                return public,BankModel(b['jobs'],contexts),SavedNominal(public,[dict(nominal_vectors=b['nominal_vectors'])])

            def simulate(case,policy,kind,label,learner=None,reference=None):
                nonlocal count
                wait_resources(ENTRY,512*1024**2+case['n']*384*1024,started+op['wall_clock_limit_s'])
                G.free_guard([ROOT,'D:/']);G.require(count<op['environment_cap'] and time.monotonic()-started<op['wall_clock_limit_s'],'Finite learning cap')
                receipt=dict(event='START',label=label,case=case['id'],policy=policy,kind=kind,utc=G.now(),identity=L.digest([opsha,label]),start_id=L.digest([opsha,label]),durable_START_consumed=True,operation_sha256=opsha)
                G.append(out/'receipts.jsonl',receipt);count+=1;print('START',count,label,'n',case['n'],flush=True)
                try:
                    public,model,nominal=getbank(case);collect=kind=='TRAIN';neural=learner is not None
                    controller=RepairController if policy=='REPAIR_OFF_NN' else GuardController
                    actor=controller(nominal,physics,case,'RL' if neural else 'EDF',learner,collect,deadline_guard=policy not in ('FT_OFF_NN','REPAIR_OFF_NN'))
                    if collect:pt(out/(label+'.BEFORE.pt.gz'),learner.snapshot())
                    current_digest=digest(learner.net) if neural else None
                    calls=0
                    def progress(state):
                        nonlocal calls
                        calls+=1
                        if calls%256==0:
                            G.require(time.monotonic()-started<op['wall_clock_limit_s'],'Wall cap inside episode')
                            print('PROGRESS',label,calls,round(state['now_ns']/1e9-35,2),flush=True)
                        return actor(state)
                    result=execute(public,model,progress,physics,case['common_potential_key'],receipt);m=metrics(result,case,physics)
                    if neural:
                        neural_calls=[c for c in actor.calls if not c.get('common_coalescing')]
                        G.require(len(neural_calls)==len(actor.frames),'Every saved NN frame maps to actual decision')
                        for call,frame in zip(neural_calls,actor.frames):call.update(old_logp=frame['old_logp'],critic_value=frame['value'].tolist(),collect=collect)
                    raw=out/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,future_actual_work_used=False))
                    frames_sha=None;reward_audit=None
                    if neural:
                        if policy=='REPAIR_OFF_NN':costs,reward_audit=repaired_labels(result,actor.frames,case,physics,m,reference)
                        else:costs,reward_audit=original_rewards.labels(result,actor.frames,case,physics,m)
                        fp=out/(label+'.frames.pt.gz');pt(fp,dict(frames=actor.frames,costs=costs,reward_audit=reward_audit,collect=collect,network_sha256=current_digest));frames_sha=G.sha(fp)
                        if collect:learner.add(actor.frames,costs);pt(out/(label+'.AFTER.pt.gz'),learner.snapshot())
                    endpoint=max(q['available_ns'] for q in result['requests']) if all(q['available_ns'] is not None for q in result['requests']) else None
                    row=dict(label=label,case=case['id'],policy=policy,kind=kind,n=case['n'],condition=case['condition'],metrics=m,raw_sha256=G.sha(raw),frames_sha256=frames_sha,network_sha256=current_digest,reference_end_ns=reference if neural else endpoint,reward_audit=reward_audit,network_file=(label+'.BEFORE.pt.gz' if collect else policy+'.FINAL_EP032.pt.gz') if neural else None)
                    G.write_new(out/(label+'.json'),row);rows.append(row);G.append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','utc':G.now(),'raw_sha256':G.sha(raw)})
                    print('COMPLETE',label,'on',m['on_time'],'urgent',m['urgent_on_time'],'elapsed',round(time.monotonic()-started,1),flush=True)
                    del result,actor;gc.collect();return endpoint
                except BaseException as exc:
                    G.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','utc':G.now(),'error':str(exc),'automatic_retry':False});raise

            for case in train:
                endpoint=simulate(case,'EDF_TRAIN_REF','REFERENCE',case['id']+'_EDF_REF')
                G.require(endpoint is not None and endpoint<=round(case['drain_stop_s']*1e9),'Training EDF reference completed in registered drain');refs[case['id']]=endpoint
            G.write_new(out/'TRAINING_REFERENCE_ENDPOINTS.json',dict(endpoints=refs,trainer_labels_only=True,not_supplied_to_actor=True))
            for arm,learner in arms.items():
                for ep in range(32):
                    case=train[ep%8];simulate(case,arm,'TRAIN',arm+'_TRAIN_'+str(ep+1).zfill(3),learner,refs[case['id']])
                G.require(learner.episodes==initial_counters[0]+32 and learner.updates==initial_counters[1]+16 and learner.steps>initial_counters[2] and not learner.pending,'Exact equal fine-tuning budget')
                G.require(digest(learner.net)!=initial_digest,'Actual gradient weight updates')
                pt(out/(arm+'.FINAL_EP032.pt.gz'),learner.snapshot())
                G.write_new(out/(arm+'.LEARNING.json'),dict(arm=arm,initial_digest=initial_digest,final_digest=digest(learner.net),new_episodes=32,new_updates=16,new_Adam_steps=learner.steps-initial_counters[2],logs=learner.logs[-16:],final_checkpoint_fixed_before_evaluation=True))
            G.write_new(out/'SELECTION_FROZEN.json',dict(rule='Final new EP32, no evaluation selection',arms={k:digest(l.net) for k,l in arms.items()},new_training=96,reference_inputs=8,repeat_passes=4))
            evaluation_refs={}
            for src in op['evaluation_reference_metrics']:
                for row in read(src['path'])['rows']:
                    if row['policy']=='EDF':evaluation_refs[row['case']]=row['common']['end_ns']
            for case in evaluation:
                for arm,learner in arms.items():simulate(case,arm,'EVAL',case['id']+'_'+arm,learner,evaluation_refs[case['id']])
            G.require(count==194,'Exact finite native count')
            for arm,l in arms.items():G.require(digest(l.net)==read(out/(arm+'.LEARNING.json'))['final_digest'],'Evaluation changed no weights')
            for p in [*op['sources'],*op['input_pins']]:G.pin(p)
            G.write_new(out/'RESULT.json',dict(status='COMPLETED',rows=rows,new_START=count,new_COMPLETE=count,new_FAIL=0,new_training=96,new_updates=48,new_references=8,new_evaluations=90,new_physical_fit=0,frozen_bank_restores=1,initial_network_sha256=initial_digest,original_weights=list(WEIGHTS),operation_sha256=opsha))
            G.write_new(out/'COMPLETE.json',dict(utc=G.now(),result_sha256=G.sha(out/'RESULT.json'),elapsed_s=time.monotonic()-started))
            replay_training(out,rows)
            subprocess.run([op['node_executable'],str(HERE/'audit.cjs')],check=True)
            sys.path.insert(0,str(HERE));import learning_figures;learning_figures.main(out)
            subprocess.run([op['node_executable'],str(HERE/'report.cjs')],check=True)
        except BaseException as exc:
            G.write_new(out/('POSTPROCESS_FAILURE.json' if (out/'COMPLETE.json').exists() else 'FAILURE.json'),dict(utc=G.now(),error=str(exc),new_START=count,automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main()
