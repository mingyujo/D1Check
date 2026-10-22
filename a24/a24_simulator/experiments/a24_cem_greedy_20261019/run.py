"""144 frozen-actor argmax diagnostics, using existing banks; no training."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,time,hashlib,subprocess,msvcrt,shutil,gc,datetime,traceback,importlib.util
from pathlib import Path
import psutil
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent;PORT=A/'experiments/a24_s26_method_20261019';CEM=A/'experiments/a24_cem_identification_20261019'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def new(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def main():
    op=json.loads((H/'OPERATION.json').read_text(encoding='utf-8'));O=A/op['output_dir'];assert '--published' in sys.argv and not O.exists()
    assert subprocess.check_output(['git','show','HEAD:a24_simulator/experiments/a24_cem_greedy_20261019/OPERATION.json'])==(H/'OPERATION.json').read_bytes()
    for p in op['pins']:assert sha(p['path'])==p['sha256'],p['path']
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False;deadline=time.monotonic()+3600
    while True:
        if not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:pass
        processes=[p.info for p in psutil.process_iter(['pid','name','cmdline']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')]
        if locked and len(processes)<=3 and psutil.virtual_memory().available>=1024*1048576 and shutil.disk_usage(R).free>=8*1024**3:break
        assert time.monotonic()<deadline,'Finite resource wait';time.sleep(5)
    try:
        sys.path.insert(0,str(A/'experiments/public_transfer_20261018'))
        from common_transfer import B,read,saved,loadpt,pt,np,torch
        sys.path.insert(0,str(A/'experiments/a24_parallel_20261018'));sys.path.insert(0,str(A/'experiments/a24_candidate_repair_20261018'));sys.path.insert(0,str(PORT))
        def module(name,path):
            spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
        Physics=module('greedy_port_physics',PORT/'physics.py').Physics;engine=module('greedy_port_engine',PORT/'engine.py');Policy=module('greedy_port_policy',PORT/'policy.py').Policy
        LM=module('greedy_matched_learner',CEM/'learner.py');outcome=module('greedy_objective',CEM/'objective.py').outcome
        class Greedy(LM.Learner):
            def choose(self,bank,collect):
                assert not collect;x=np.asarray(bank['x'],np.float32);mask=np.asarray(bank['mask'],bool)
                with torch.no_grad():logits=self.net(torch.tensor(x),torch.tensor(mask));lp=logits.log_softmax(-1);i=int(logits.argmax())
                return i,dict(x=x.copy(),mask=mask.copy(),scores=bank['scores'].copy(),index=i,old_logp=float(lp[i]),collect=False,learn_actor=int(mask.sum())>1,network_sha256=LM.digest(self.net))
        parent=read(op['parent']['path']);catalog=read(B.L.pin(B.registration(parent)['catalog_pin']));power=read(A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json');shape=read(PORT/'SHAPE.json');design=read(CEM/'POLICY_INPUTS.json')['evaluation'];P=A/'results/A24_CEM_MATCHED_20261019_01';begun=time.monotonic();O.mkdir();rows=[];count=0;opsha=sha(H/'OPERATION.json');new(O/'START.json',dict(utc=stamp(),pid=os.getpid(),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),operation_sha256=opsha,processes=processes,posthoc_same_inputs=True))
        def receipt(x):
            with (O/'receipts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(x)+'\n');f.flush();os.fsync(f.fileno())
        for profile in op['profiles']:
            for case in design:
                public,contexts=B.public_input(case,catalog);public['initial_ap_c']=26;bankfile=P/(case['id']+'.BANK.json.gz');bank=read(bankfile)
                for policy in op['policies']:
                    assert count<144 and time.monotonic()-begun<14400 and shutil.disk_usage(R).free>=4*1024**3
                    physics=Physics(power,B.Config(**parent['physics']),profile,shape);model=B.BankModel(bank['jobs'],contexts);nominal=B.SavedNominal(public,[dict(nominal_vectors=bank['nominal_vectors'])]);label=profile+'__GREEDY__'+case['id']+'__'+policy;algorithm,idx=policy.rsplit('_S',1);si=int(idx);seed=op['seeds'][si];file=op['checkpoints'][policy]['path'];state=loadpt(file);l=Greedy(seed);l.restore(state);actor=Policy(nominal,physics,case,policy,l,False)
                    rec=dict(event='START',label=label,kind='EVAL',utc=stamp(),durable_START_consumed=True,start_id=hashlib.sha256((opsha+label).encode()).hexdigest());receipt(rec);count+=1;episode_begun=time.monotonic();print('START_A24_GREEDY',count,label,flush=True)
                    try:
                        def guarded(s):
                            assert time.monotonic()-begun<14400
                            if len(actor.calls)>=max(1024,4*case['n']):raise ValueError('Frozen policy call cap')
                            if time.monotonic()-episode_begun>30:raise ValueError('Frozen policy wall cap')
                            return actor(s)
                        result=engine.run(public,model,guarded,physics,case['common_potential_key'],rec);m=engine.metrics(result,case,physics);score=outcome(result,case,physics);raw=O/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,profile=dict(id=profile,slots=3,beta=.25)));row=dict(label=label,kind='EVAL',case=case['id'],profile=dict(id=profile,slots=3,beta=.25),policy=policy,n=case['n'],metrics=m,score=score,raw_sha256=sha(raw),bank_path=str(bankfile),bank_sha256=sha(bankfile),network_sha256=state['network_sha256'],network_file=file,network_file_sha256=sha(file),argmax=True,posthoc_same_inputs=True);new(O/(label+'.json'),row);rows.append(row);receipt({**rec,'event':'COMPLETE','utc':stamp(),'raw_sha256':sha(raw)});print('COMPLETE_A24_GREEDY',count,label,m['on_time'],m['urgent_on_time'],'elapsed',round(time.monotonic()-begun,1),flush=True);del actor,l,result;gc.collect()
                    except ValueError as e:
                        receipt({**rec,'event':'FAIL','utc':stamp(),'error':str(e),'automatic_retry':False})
                        if str(e) not in ('Decision cap','Integration cap','Frozen policy call cap','Frozen policy wall cap'):raise
                        # A deterministic actor can repeatedly choose WAIT. Keep
                        # the finite engine failure; never override it or retry.
                        raw=O/(label+'.FAILED.json.gz');saved(raw,dict(calls=actor.calls,case=case,error=str(e),last_public_state=locals().get('s'),partial_not_complete_trace=True));row=dict(label=label,kind='EVAL',case=case['id'],profile=dict(id=profile,slots=3,beta=.25),policy=policy,n=case['n'],status='FAIL',failure=str(e),metrics=None,score=None,raw_sha256=sha(raw),failed_file=str(raw),bank_path=str(bankfile),bank_sha256=sha(bankfile),network_sha256=state['network_sha256'],network_file=file,network_file_sha256=sha(file),argmax=True,posthoc_same_inputs=True);new(O/(label+'.json'),row);rows.append(row);print('CONTROLLED_POLICY_FAIL',count,label,str(e),flush=True);del actor,l;gc.collect()
        assert count==144
        for p in op['pins']:assert sha(p['path'])==p['sha256']
        failed=sum(r.get('status')=='FAIL' for r in rows);new(O/'RESULT.json',dict(status='BATCH_COMPLETE',START=count,COMPLETE=count-failed,FAIL=failed,rows=rows,elapsed_s=time.monotonic()-begun,new_training=0,new_physical_fit=0,new_device=0,posthoc_same_inputs=True));print('A24_GREEDY_ALL_COMPLETE',count,'failed',failed,flush=True)
    except BaseException as e:
        if O.exists():new(O/'FAILURE.json',dict(utc=stamp(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
