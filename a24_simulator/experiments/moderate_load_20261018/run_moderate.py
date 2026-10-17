"""Finite moderate-load ablation; same physics and frozen neural checkpoint."""
from pathlib import Path
import ast,gc,gzip,io,json,os,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ENTRY=Path(__file__).resolve()
sys.path.insert(0,str(ROOT/'experiments/coupled_345_20261017'))
from bootstrap import L,G,registration,public_input,save_binary,Nominal
from dynamics import Config,Physics
from engine import run as execute,metrics
from nn_train import Learner,digest
sys.path.insert(0,str(ROOT/'experiments/guard_ablation_20261018_v2'))
from guard_controller import GuardController
from bank_model import BankModel,SavedNominal
import torch
torch.set_num_threads(1)
os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)
G.OWN_TOKENS+=('moderate_load_20261018','guard_ablation_20261018','coupled_345_20261017')

def read(p):
    p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)

def saved(p,x):save_binary(p,gzip.compress(G.canonical(x).encode(),mtime=0))

def pt(p,x):
    b=io.BytesIO();torch.save(x,b);save_binary(p,gzip.compress(b.getvalue(),mtime=0))

def bank(public,model,case):
    jobs=[];nominal=Nominal(model,public);vectors={}
    for q in public['requests']:
        context,_=model.request_context(public,q);potential=[case['common_potential_key'],q['ordinal'],q['request_id']]
        admission=model.admission(context,q['task'],potential,protocol='SERIAL')
        entry=q['scheduled_arrival_ns']+admission['scheduled_to_actual_ns']+admission['actual_to_queue_ns']
        job={k:q[k] for k in ('request_id','ordinal','task','priority','scheduled_arrival_ns','deadline_ns')}
        job.update(queue_entry_ns=entry,admission=admission,routes={})
        state=dict(now_ns=entry,queue=[{**q,'queue_entry_ns':entry}],owners=[],initial_ap_c=public['initial_ap_c'])
        for r in ('CPU','GPU'):
            vectors[q['request_id']+'|'+r]=nominal.vector(q,r,state)
            chosen=dict(request_id=q['request_id'],task=q['task'],route=r,context=L.context_for_route(context,q['task'],r))
            job['routes'][r]=model.draw_latent_serial(chosen,state,potential)
        jobs.append(job)
    return dict(jobs=jobs,nominal_vectors=vectors)

def main():
    op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir'];opsha=G.sha(HERE/'OPERATION.json')
    G.require('--published' in sys.argv,'Publish finite registration first')
    for p in [*op['sources'],*op['input_pins']]:G.pin(p)
    G.require(not out.exists(),'Consumed namespace; preserve failure, no retry')
    guard=G.process_guard(ENTRY);volumes=G.free_guard([ROOT,'D:/'])
    import msvcrt
    lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0;rows=[];started=time.monotonic()
    try:
        out.mkdir();G.write_new(out/'START.json',dict(utc=G.now(),operation_sha256=opsha,guard=guard,volumes=volumes,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),uncommitted_changes=bool(subprocess.check_output(['git','status','--porcelain']))))
        try:
            base,_,_=L.initialize(registration(op));catalog=read(L.pin(registration(op)['catalog_pin']))
            G.require(base.feature_mode=='exact_public','Frozen public strata')
            physics=Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),Config(**op['physics']))
            snap=torch.load(io.BytesIO(gzip.decompress(Path(op['checkpoint']['path']).read_bytes())),map_location='cpu',weights_only=False)
            learner=Learner(op['learner_seed']);learner.restore(snap);before=digest(learner.net)
            rng=(learner.action_rng.get_state().clone(),learner.shuffle_rng.get_state().clone(),learner.episodes,learner.updates,learner.steps)
            for case in read(op['inputs']['path'])['cases']:
                public,contexts=public_input(case,catalog);public['initial_ap_c']=case['temperature_c']
                b=bank(public,L.Model(base,contexts),case);saved(out/(case['id']+'.BANK.json.gz'),b)
                model=BankModel(b['jobs'],contexts);nominal=SavedNominal(public,[dict(nominal_vectors=b['nominal_vectors'])])
                for policy in op['policies']:
                    wait_start=time.monotonic()
                    while True:
                        try:G.process_guard(ENTRY);break
                        except RuntimeError as exc:
                            if not any(x in str(exc) for x in ('Global Python leaf limit','Other own Python producer alive')) or time.monotonic()-wait_start>=30:raise
                            print('PRE_START_SLOT_WAIT',str(exc),flush=True);time.sleep(5)
                    G.free_guard([ROOT,'D:/'])
                    G.require(count<op['environment_cap'] and time.monotonic()-started<op['wall_clock_limit_s'],'Finite cap')
                    name=case['id']+'_'+policy;receipt=dict(event='START',label=name,case=case['id'],policy=policy,utc=G.now(),identity=L.digest([opsha,name]),start_id=L.digest([opsha,name]),durable_START_consumed=True,operation_sha256=opsha)
                    G.append(out/'receipts.jsonl',receipt);count+=1;print('START',count,name,'n',case['n'],flush=True)
                    try:
                        neural=policy.endswith('_NN');mode='RL' if neural else policy
                        actor=GuardController(nominal,physics,case,mode,learner if neural else None,False,deadline_guard=policy!='GUARD_OFF_NN')
                        calls=0
                        def progress(state):
                            nonlocal calls
                            calls+=1
                            if calls%256==0:
                                G.require(time.monotonic()-started<op['wall_clock_limit_s'],'Wall cap inside episode')
                                print('PROGRESS',name,calls,round(state['now_ns']/1e9-35,2),flush=True)
                            return actor(state)
                        result=execute(public,model,progress,physics,case['common_potential_key'],receipt);m=metrics(result,case,physics)
                        raw=out/(name+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,future_actual_work_used=False))
                        frames_sha=None
                        if neural:
                            frames=out/(name+'.frames.pt.gz');pt(frames,dict(frames=actor.frames,network_sha256=before,collect=False));frames_sha=G.sha(frames)
                        row=dict(label=name,case=case['id'],policy=policy,kind='DENSITY',n=case['n'],condition=case['condition'],metrics=m,raw_sha256=G.sha(raw),frames_sha256=frames_sha,network_sha256=before if neural else None)
                        G.write_new(out/(name+'.json'),row);rows.append(row);G.append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','utc':G.now(),'raw_sha256':G.sha(raw)})
                        print('COMPLETE',name,'on',m['on_time'],'urgent',m['urgent_on_time'],'wait',round(m['wait_s'],3),'elapsed',round(time.monotonic()-started,1),flush=True)
                        del result,actor;gc.collect()
                    except BaseException as exc:
                        G.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','utc':G.now(),'error':str(exc),'automatic_retry':False});raise
                del b,model,nominal;gc.collect()
            G.require(count==80 and digest(learner.net)==before,'Finite count and frozen network')
            G.require(torch.equal(rng[0],learner.action_rng.get_state()) and torch.equal(rng[1],learner.shuffle_rng.get_state()) and tuple(rng[2:])==(learner.episodes,learner.updates,learner.steps),'No training or RNG update')
            for p in [*op['sources'],*op['input_pins']]:G.pin(p)
            G.write_new(out/'RESULT.json',dict(status='COMPLETED',rows=rows,new_START=count,new_COMPLETE=count,new_FAIL=0,network_sha256=before,network_and_training_RNG_unchanged=True,operation_sha256=opsha,new_training=0,new_physical_fit=0,frozen_bank_restores=1))
            G.write_new(out/'COMPLETE.json',dict(utc=G.now(),result_sha256=G.sha(out/'RESULT.json'),elapsed_s=time.monotonic()-started))
            subprocess.run([op['node_executable'],str(HERE/'audit.cjs')],check=True)
            sys.path.insert(0,str(HERE));import moderate_figures;moderate_figures.main(out)
            subprocess.run([op['node_executable'],str(HERE/'report.cjs')],check=True)
        except BaseException as exc:
            G.write_new(out/('POSTPROCESS_FAILURE.json' if (out/'COMPLETE.json').exists() else 'FAILURE.json'),dict(utc=G.now(),error=str(exc),new_START=count,automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main()
