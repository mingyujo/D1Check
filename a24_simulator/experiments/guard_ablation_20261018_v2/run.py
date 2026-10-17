"""Frozen NN x urgent-WAIT mask 2x2 ablation; original penalty retained."""
from pathlib import Path
import ast,gc,gzip,io,json,os,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ENTRY=Path(__file__).resolve()
sys.path.insert(0,str(ROOT/'experiments/coupled_345_20261017'))
from bootstrap import L,G,public_input,save_binary
from dynamics import Config,Physics,WEIGHTS
from engine import run as execute,metrics
import importlib.util
_reward_spec=importlib.util.spec_from_file_location('coupled_reward_labels',ROOT/'experiments/coupled_345_20261017/rewards.py')
_reward_module=importlib.util.module_from_spec(_reward_spec);_reward_spec.loader.exec_module(_reward_module)
labels=_reward_module.labels
from nn_train import Learner,digest
sys.path.insert(0,str(HERE))
from guard_controller import GuardController
from bank_model import BankModel,SavedNominal
import torch
torch.set_num_threads(1)
os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)
G.OWN_TOKENS+=('guard_ablation_20261018_v2','density_headroom_20261018','density_headroom_coupling_20261018','load_density_20261017','coupled_345_20261017')


def read(p):
    p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)


def saved(p,x):save_binary(p,gzip.compress(G.canonical(x).encode(),mtime=0))


def pt(p,x):
    b=io.BytesIO();torch.save(x,b);save_binary(p,gzip.compress(b.getvalue(),mtime=0))


def main():
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir'];parent=ROOT/op['potential_output'];opsha=G.sha(HERE/'OPERATION.json')
    G.require('--published' in sys.argv,'Publish this new finite registration first')
    for p in [*op['sources'],*op['input_pins']]:G.pin(p)
    G.require(not out.exists(),'Consumed namespace; preserve failure, no retry')
    guard=G.process_guard(ENTRY);volumes=G.free_guard([ROOT,'D:/'])
    import msvcrt
    lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0;rows=[];started=time.monotonic()
    try:
        out.mkdir();G.write_new(out/'START.json',dict(utc=G.now(),operation_sha256=opsha,guard=guard,volumes=volumes,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),uncommitted_changes=bool(subprocess.check_output(['git','status','--porcelain']))))
        try:
            catalog=read(op['catalog']['path']);physics=Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),Config(**op['physics']))
            snap=torch.load(io.BytesIO(gzip.decompress(Path(op['checkpoint']['path']).read_bytes())),map_location='cpu',weights_only=False)
            learned=Learner(op['learner_seed']);learned.restore(snap)
            zero=Learner(op['learner_seed']);zero.restore(snap)
            with torch.no_grad():zero.net.actor[-1].weight.zero_();zero.net.actor[-1].bias.zero_()
            models={'NN':learned,'ZERO':zero};before={k:digest(v.net) for k,v in models.items()}
            rng={k:(v.action_rng.get_state().clone(),v.shuffle_rng.get_state().clone(),v.episodes,v.updates,v.steps) for k,v in models.items()}
            pt(out/'ZERO_SNAPSHOT.pt.gz',zero.snapshot())
            G.write_new(out/'NETWORKS.json',dict(learned=before['NN'],zero=before['ZERO'],zero_only_final_actor_layer=True,deadline_cost_weights=list(WEIGHTS[2:]),original_weights=list(WEIGHTS),new_training=0))
            for case in read(op['inputs']['path'])['cases']:
                cid=case['id'];original=read(ROOT/(op['original_output']+'/'+cid+'_RL.raw.json.gz'))
                public,contexts=public_input(case,catalog);public['initial_ap_c']=case['temperature_c']
                jobs=read(parent/(cid+'.BANK.json.gz'))['jobs'];model=BankModel(jobs,contexts);nominal=SavedNominal(public,original['calls'])
                for mask_on,which in [(True,'NN'),(False,'NN'),(True,'ZERO'),(False,'ZERO')]:
                    began=time.monotonic()
                    while True:
                        try:G.process_guard(ENTRY);break
                        except RuntimeError as exc:
                            if not any(s in str(exc) for s in ('Global Python leaf limit','Other own Python producer alive')) or time.monotonic()-began>=30:raise
                            print('PRE_START_SLOT_WAIT',str(exc),flush=True);time.sleep(5)
                    G.free_guard([ROOT,'D:/']);G.require(count<op['environment_cap'] and time.monotonic()-started<op['wall_clock_limit_s'],'Finite ablation cap')
                    policy=('GUARD_ON_' if mask_on else 'GUARD_OFF_')+which;name=cid+'_'+policy
                    receipt=dict(event='START',label=name,case=cid,policy=policy,utc=G.now(),identity=L.digest([opsha,name]),start_id=L.digest([opsha,name]),durable_START_consumed=True,operation_sha256=opsha)
                    G.append(out/'receipts.jsonl',receipt);count+=1;print('START',count,name,'n',case['n'],flush=True)
                    try:
                        learner=models[which];actor=GuardController(nominal,physics,case,'RL',learner,False,deadline_guard=mask_on);calls=0
                        def progress(state):
                            nonlocal calls
                            calls+=1
                            if calls%256==0:
                                G.require(time.monotonic()-started<op['wall_clock_limit_s'],'Wall cap inside episode')
                                print('PROGRESS',name,'calls',calls,'sim_s',round(state['now_ns']/1e9-35,2),flush=True)
                            return actor(state)
                        result=execute(public,model,progress,physics,case['common_potential_key'],receipt);m=metrics(result,case,physics)
                        cost,ra=labels(result,actor.frames,case,physics,m)
                        raw=out/(name+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,future_actual_work_used=False))
                        frames=out/(name+'.frames.pt.gz');pt(frames,dict(frames=actor.frames,costs=cost,reward_audit=ra,network_sha256=before[which],collect=False))
                        exact_checks=0
                        if mask_on and which=='NN':
                            G.require(result['trace']==original['result']['trace'],'Cached-bank guard-on every physical trace term')
                            for a,b in zip(result['requests'],original['result']['requests']):
                                for key in ('request_id','route','queue_entry_ns','dispatch_ns','response_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','available_ns'):
                                    G.require(a.get(key)==b.get(key),'Exact guard-on reproduction '+key);exact_checks+=1
                            G.require(len(actor.calls)==len(original['calls']),'Exact baseline decision count')
                            for a,b in zip(actor.calls,original['calls']):
                                for key in ('time_ns','action','chosen','actions','x','mask','forecast_scores','forecasts','common_coalescing'):
                                    G.require(a.get(key)==b.get(key),'Exact original neural public bank '+key);exact_checks+=1
                        row=dict(label=name,case=cid,policy=policy,kind='GUARD_ABLATION',n=case['n'],condition=case['condition'],guard_enabled=mask_on,neural_head=which,
                                 metrics=m,raw_sha256=G.sha(raw),frames_sha256=G.sha(frames),network_sha256=before[which],reward_audit=ra,exact_original_checks=exact_checks)
                        G.write_new(out/(name+'.json'),row);rows.append(row);G.append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','utc':G.now(),'raw_sha256':G.sha(raw),'result_sha256':G.sha(out/(name+'.json'))})
                        print('COMPLETE',name,'on',m['on_time'],'urgent',m['urgent_on_time'],'wait',round(m['wait_s'],3),'elapsed',round(time.monotonic()-started,1),flush=True)
                        del result,actor;gc.collect()
                    except BaseException as exc:
                        G.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','utc':G.now(),'error':str(exc),'automatic_retry':False});raise
                del original,jobs,model,nominal;gc.collect()
            G.require(count==op['planned_START'],'Exact finite episode count')
            for k,v in models.items():
                state=rng[k];G.require(digest(v.net)==before[k] and (v.episodes,v.updates,v.steps)==tuple(state[2:]),'No weight/optimizer updates')
                G.require(torch.equal(state[0],v.action_rng.get_state()) and torch.equal(state[1],v.shuffle_rng.get_state()),'No training RNG consumed')
            for p in [*op['sources'],*op['input_pins']]:G.pin(p)
            G.write_new(out/'RESULT.json',dict(status='FROZEN_GUARD_ABLATION_COMPLETED',rows=rows,new_START=count,new_COMPLETE=count,new_FAIL=0,operation_sha256=opsha,
                        new_training=0,new_physical_fit=0,original_timing_model_restores=0,latent_replay_banks=10,original_guard_on_exact_cases=10,networks=before,deadline_cost_weights=list(WEIGHTS[2:])))
            G.write_new(out/'COMPLETE.json',dict(utc=G.now(),result_sha256=G.sha(out/'RESULT.json'),elapsed_s=time.monotonic()-started))
            subprocess.run([op['node_executable'],str(HERE/'audit.cjs')],check=True)
            import figures
            figures.main(out)
            subprocess.run([op['node_executable'],str(HERE/'report.cjs')],check=True)
        except BaseException as exc:
            G.write_new(out/('POSTPROCESS_FAILURE.json' if (out/'COMPLETE.json').exists() else 'FAILURE.json'),dict(utc=G.now(),error=str(exc),new_START=count,automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
