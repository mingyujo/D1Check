"""Finite 724-episode A24 matched CEM/PPO study, no restarts or retries."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,time,hashlib,subprocess,msvcrt,shutil,gc,datetime,traceback,copy,importlib.util
from pathlib import Path
import psutil
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent;PORT=A/'experiments/a24_s26_method_20261019'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def new(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def main():
    op=json.loads((H/'POLICY_OPERATION.json').read_text(encoding='utf-8'));O=A/op['output_dir'];assert '--published' in sys.argv and not O.exists()
    assert subprocess.check_output(['git','show','HEAD:a24_simulator/experiments/a24_cem_identification_20261019/POLICY_OPERATION.json'])==(H/'POLICY_OPERATION.json').read_bytes()
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
        from common_transfer import B,read,saved,loadpt,pt,np,equal
        from transfer_learner import Learner as OldLearner
        sys.path.insert(0,str(A/'experiments/a24_parallel_20261018'));sys.path.insert(0,str(A/'experiments/a24_candidate_repair_20261018'));sys.path.insert(0,str(PORT))
        def module(name,path):
            spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
        Physics=module('cem_port_physics',PORT/'physics.py').Physics;engine=module('cem_port_engine',PORT/'engine.py');Policy=module('cem_port_policy',PORT/'policy.py').Policy
        learner_module=module('a24_matched_learner',H/'learner.py');Learner=learner_module.Learner;cem_update=learner_module.cem_update;outcome=module('a24_cem_objective',H/'objective.py').outcome
        parent=read(op['parent']['path']);base,_,_=B.L.initialize(B.registration(parent));catalog=read(B.L.pin(B.registration(parent)['catalog_pin']));power=read(A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json');shape=read(PORT/'SHAPE.json');design=read(H/'POLICY_INPUTS.json');begin=time.monotonic();rows=[];count=0;O.mkdir();opsha=sha(H/'POLICY_OPERATION.json')
        new(O/'START.json',dict(utc=stamp(),pid=os.getpid(),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),operation_sha256=opsha,processes=processes))
        new(O/'PHYSICAL_ADOPTION.json',dict(adopted=False,extra_environment_12_skipped=True,reason='All conditional thermal fits fail preregistered session-bias gate; absolute W and hardware R/C unidentified',result_sha256=sha(A/'results/A24_IDENTIFICATION_20261019_01/RESULT.json')))
        def receipt(x):
            with (O/'receipts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(x)+'\n');f.flush();os.fsync(f.fileno())
        banks={}
        for case in design['training']+design['development']+design['evaluation']:
            public,contexts=B.public_input(case,catalog);public['initial_ap_c']=26;bank=B.bank_module.bank(public,B.L.Model(base,contexts),case);file=O/(case['id']+'.BANK.json.gz');saved(file,bank);banks[case['id']]=(public,contexts,bank,file)
            print('BANK',len(banks),case['id'],flush=True)
        def simulate(case,profile,policy,kind,tag,learner=None,action_seed=None,collect=False):
            nonlocal count
            assert count<724 and time.monotonic()-begin<14400 and shutil.disk_usage(R).free>=4*1024**3
            physics=Physics(power,B.Config(**parent['physics']),profile,shape);public,contexts,bank,bankfile=banks[case['id']];model=B.BankModel(bank['jobs'],contexts);nominal=B.SavedNominal(public,[dict(nominal_vectors=bank['nominal_vectors'])]);label=profile+'__'+tag+'__'+case['id']+'__'+policy
            rec=dict(event='START',label=label,kind=kind,utc=stamp(),durable_START_consumed=True,start_id=hashlib.sha256((opsha+label).encode()).hexdigest());receipt(rec);count+=1;print('START_CEM_MATCHED',count,label,flush=True)
            try:
                if action_seed is not None:learner.reseed(action_seed)
                actor=Policy(nominal,physics,case,policy,learner,collect);before=learner.snapshot() if learner else None
                def guarded(s):
                    assert time.monotonic()-begin<14400,'Finite in-episode wall cap'
                    return actor(s)
                result=engine.run(public,model,guarded,physics,case['common_potential_key'],rec);m=engine.metrics(result,case,physics);score=outcome(result,case,physics);raw=O/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,case=case,profile=dict(id=profile,slots=3,beta=.25)))
                if learner:
                    pt(O/(label+'.FRAMES.pt.gz'),dict(frames=actor.frames,action_seed=action_seed,network=before['network'],network_sha256=before['network_sha256'],action_rng_before=before['action_rng'],action_rng_after=learner.snapshot()['action_rng'],old_learner=policy=='OLD_PPO',score=score))
                row=dict(label=label,kind=kind,case=case['id'],profile=dict(id=profile,slots=3,beta=.25),policy=policy,n=case['n'],metrics=m,score=score,raw_sha256=sha(raw),bank_path=str(bankfile),bank_sha256=sha(bankfile),network_sha256=before['network_sha256'] if before else None)
                new(O/(label+'.json'),row);rows.append(row);receipt({**rec,'event':'COMPLETE','utc':stamp(),'raw_sha256':sha(raw)});print('COMPLETE_CEM_MATCHED',count,label,m['on_time'],m['urgent_on_time'],'cost',round(score['scalar'],6),'elapsed',round(time.monotonic()-begin,1),flush=True)
                frames=actor.frames;del result,actor;gc.collect();return row,frames
            except BaseException as e:receipt({**rec,'event':'FAIL','utc':stamp(),'error':str(e),'automatic_retry':False});raise
        # References are diagnostics only: no objective coefficient is calibrated.
        for case in design['development']:simulate(case,'ORIGINAL','EDF_CPU','REFERENCE','REF')
        selected={};initial={}
        for si,seed in enumerate(op['seeds']):
            init=Learner(seed);initial[seed]=init.snapshot();pt(O/f'S{si}.INITIAL.pt.gz',initial[seed]);del init
            for algorithm in ('CEM','PPO48'):
                learner=Learner(seed);mu=learner.net.weight.detach().numpy().astype(float).copy();sigma=np.full(48,.5);rng=np.random.default_rng(seed+20000);dev=[]
                for g in range(1,7):
                    cases=[c for c in design['training'] if c['condition']['learner_index']==si and c['condition']['generation']==g];assert len(cases)==2
                    prefix=f'S{si}.{algorithm}.G{g}';pt(O/(prefix+'.BEFORE.pt.gz'),learner.snapshot())
                    if algorithm=='CEM':
                        rng_before=copy.deepcopy(rng.bit_generator.state);z=rng.normal(size=(4,48));candidates=mu+sigma*np.r_[z,-z];scores=[];labels=[];oldmu=mu.copy();oldsigma=sigma.copy()
                        for k,w in enumerate(candidates):
                            candidate=Learner(seed,w);ss=[];ll=[]
                            for ci,case in enumerate(cases):
                                row,_=simulate(case,'ORIGINAL',f'CEM_S{si}','TRAIN',f'{prefix}.C{k}',candidate,seed+g*100+ci,True);ss.append(row['score']['scalar']);ll.append(row['label'])
                            scores.append(float(np.mean(ss)));labels.append(ll);del candidate
                        mu,sigma,order=cem_update(mu,sigma,candidates,np.asarray(scores));learner=Learner(seed,mu)
                        new(O/(prefix+'.UPDATE.json'),dict(mu_before=oldmu.tolist(),sigma_before=oldsigma.tolist(),parameter_rng_before=rng_before,z=z.tolist(),candidates=candidates.tolist(),scores=scores,labels=labels,elite_indices=order.tolist(),mu_after=mu.tolist(),sigma_after=sigma.tolist(),parameter_rng_after=copy.deepcopy(rng.bit_generator.state)))
                    else:
                        for k in range(8):
                            for ci,case in enumerate(cases):
                                row,frames=simulate(case,'ORIGINAL',f'PPO48_S{si}','TRAIN',f'{prefix}.R{k}',learner,seed+g*100+ci+k*100000,True);learner.add(frames,row['score']['scalar'],ci,row['label'])
                        log=learner.update();new(O/(prefix+'.UPDATE.json'),log)
                    state=learner.snapshot();pt(O/(prefix+'.AFTER.pt.gz'),state)
                    if g in (2,4,6):
                        costs=[]
                        for ci,case in enumerate(design['development']):
                            l=Learner(seed);l.restore(state);row,_=simulate(case,'ORIGINAL',f'{algorithm}_S{si}','DEV',prefix,l,seed+50000+ci);costs.append(row['score']['scalar'])
                        dev.append(dict(generation=g,costs=costs,mean=float(np.mean(costs)),checkpoint=prefix+'.AFTER.pt.gz',network_sha256=state['network_sha256']))
                winner=min(dev,key=lambda x:(x['mean'],x['generation']));selected[algorithm,seed]=loadpt(O/winner['checkpoint']);new(O/f'S{si}.{algorithm}.SELECTION.json',dict(rule='Minimum fixed actual episode cost on four DEV cases; earlier checkpoint breaks exact ties; no EVAL selection',all_candidates=dev,selected=winner));del learner;gc.collect()
        new(O/'SELECTION_FROZEN.json',dict(utc=stamp(),completed_START=count,selection_before_any_EVAL=True,all_seed_indices=[0,1]))
        for profile in op['profiles']:
            oldstate=loadpt(A/'results/A24_S26_METHOD_20261019_01'/(profile+'.PPO.FINAL.pt.gz'))
            for ci,case in enumerate(design['evaluation']):
                for policy in op['policies']:
                    l=None;seed_action=None
                    if policy=='OLD_PPO':l=OldLearner(state=oldstate)
                    elif policy.startswith(('INITIAL_','CEM_','PPO48_')):
                        algorithm,idx=policy.rsplit('_S',1);si=int(idx);seed=op['seeds'][si];l=Learner(seed);l.restore(initial[seed] if algorithm=='INITIAL' else selected[algorithm,seed]);seed_action=seed+90000+ci
                    simulate(case,profile,policy,'EVAL','EVAL',l,seed_action);del l;gc.collect()
        assert count==724
        for p in op['pins']:assert sha(p['path'])==p['sha256'],p['path']
        new(O/'RESULT.json',dict(status='COMPLETE',START=count,COMPLETE=count,FAIL=0,rows=rows,elapsed_s=time.monotonic()-begin,new_CEM_environments=192,new_PPO48_environments=192,DEV=48,EVAL=288,references=4,physical_fits_in_policy_run=0,new_device=0));print('A24_CEM_ALL_COMPLETE',count,flush=True)
    except BaseException as e:
        if O.exists():new(O/'FAILURE.json',dict(utc=stamp(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
