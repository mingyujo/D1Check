"""Evaluation-only selection of own current fresh CEM checkpoints; no new training or teacher."""
import copy,datetime,gzip,hashlib,io,json,msvcrt,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
H=Path(__file__).resolve().parent;R=H.parents[1];W=H.parents[3];O=H/'artifacts/G001';PRIMARY=H.parent/'episodic_policy_search_v1/artifacts/G001'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x):
    p=Path(p);b=json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    if p.suffix=='.gz':b=gzip.compress(b,compresslevel=3,mtime=0)
    with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def append(p,x):
    with Path(p).open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def pt(p,x):
    import torch
    b=io.BytesIO();torch.save(x,b)
    with Path(p).open('xb') as f:f.write(gzip.compress(b.getvalue(),compresslevel=3,mtime=0));f.flush();os.fsync(f.fileno())
def guard(deadline):
    import gc,psutil
    last=0
    while True:
        gc.collect();procs=[p.info for p in psutil.process_iter(['pid','name','cmdline']) if (p.info['name'] or '').lower() in ['python.exe','python3.exe']]
        free=psutil.virtual_memory().available;disks={str(p):shutil.disk_usage(p).free for p in [W,Path('D:/')]}
        if len(procs)<=3 and free>=1536*1024**2 and min(disks.values())>=8*1024**3:return dict(utc=now(),free_bytes=free,python=procs,disk_free=disks)
        if time.monotonic()>=deadline:raise RuntimeError('Finite resource wait before START elapsed')
        if time.monotonic()-last>=30:print('RESOURCE_WAIT',len(procs),round(free/1048576),flush=True);last=time.monotonic()
        time.sleep(5)

def main(op):
    import numpy as np,torch
    from nn_train import Learner,digest
    from selection_rules import rolling_atc
    torch.set_num_threads(1)
    parent_root=H.parent/'episodic_policy_search_v1';parent_proof=read(parent_root/'FINAL_PROOF.json');assert parent_proof['status']=='PASS_COMPLETE_AND_HASH_VERIFIED'
    source_manifest=read(parent_root/'MANIFEST.json');source_pins={(R/e['path']).resolve():e['sha256'] for e in source_manifest['files']}
    original_load=torch.load
    def own_load(p):
        p=Path(p).resolve();assert p.is_relative_to(PRIMARY.resolve()) and p in source_pins and sha(p)==source_pins[p],'Only current fresh CEM source checkpoints'
        return original_load(io.BytesIO(gzip.decompress(p.read_bytes())),map_location='cpu',weights_only=False)
    def forbidden(*args,**kwargs):raise RuntimeError('Unvetted checkpoint load forbidden; no old project weights')
    torch.load=forbidden
    started=time.monotonic();rows=[];count=0;reused=0;selection=None;engine=None;checkpoint_files={}
    cases=read(H/'INPUTS.json')['cases'];phase={p:[c for c in cases if c['phase']==p] for p in ['DEV','EVAL']}
    def verify():
        for pin in op['pins']:assert sha(pin['path'])==pin['sha256'],'Changed pinned source '+pin['path']
        assert sha(parent_root/'MANIFEST.json')==parent_proof['manifest_sha256']
    save(O/'SOURCE_PROVENANCE_FROZEN.json',dict(parent_FINAL_PROOF_sha256=sha(parent_root/'FINAL_PROOF.json'),parent_MANIFEST_sha256=sha(parent_root/'MANIFEST.json'),parent_TRAIN=432,new_training=0,old_project_weights=0,BC=0,selection_EVAL_used=0))
    def reuse(c,source_label,method,label,checkpoint=None):
        nonlocal reused
        verify();source=read(PRIMARY/(source_label+'.json'));assert source['input']==c['id'] and source['stream']==c['stream']
        for suffix,key in [('.raw.json.gz','raw_sha256'),('.banks.jsonl.gz','banks_sha256')]:
            p=PRIMARY/(source_label+suffix);assert sha(p)==source[key];shutil.copyfile(p,O/(label+suffix))
        row={**source,'method':method,'label':label,'checkpoint_file':checkpoint,'reused_environment':True,'source_namespace':'episodic_policy_search_v1','source_label':source_label}
        save(O/(label+'.json'),row);rows.append(row);reused+=1;append(O/'receipts.jsonl',dict(event='REUSE',utc=now(),label=label,source_label=source_label,source_namespace='episodic_policy_search_v1',new_environment=0,raw_sha256=row['raw_sha256']))
        return row
    def simulate(c,method,label,kind,scales,learner=None,collect=False,epoch=None):
        nonlocal count,engine
        verify();assert count<op['environment_cap'] and time.monotonic()-started<op['wall_cap_s']
        resource=guard(started+op['wall_cap_s']);count+=1;frames=[];pre=digest(learner.net) if learner else None
        if learner and collect:
            crn=int(hashlib.sha256(f'{learner.seed}|{c["stream"]}|CEM_TRAIN_CRN_V1'.encode()).hexdigest()[:16],16)%(2**63);learner.action_rng.manual_seed(crn)
        else:crn=None
        eval_rng_seed=int(hashlib.sha256(f'{learner.seed}|{c["stream"]}|DEPLOY_SAMPLE_V1'.encode()).hexdigest()[:16],16)%(2**63) if learner and not collect else None
        eval_rng=torch.Generator().manual_seed(eval_rng_seed) if eval_rng_seed is not None else None
        train_rng_before=learner.action_rng.get_state().clone() if learner and not collect else None
        identity=hashlib.sha256((sha(H/'OPERATION.json')+'|'+label).encode()).hexdigest()
        rec=dict(event='START',utc=now(),count=count,label=label,identity=identity,kind=kind,input=c['id'],stream=c['stream'],method=method,seed=learner.seed if learner else None,epoch=epoch,selection_sha256=selection,resource=resource)
        append(O/'receipts.jsonl',rec);begin=time.monotonic();decisions=0
        bank_partial=O/(label+'.banks.jsonl.gz.partial');bank_final=O/(label+'.banks.jsonl.gz');bf=bank_partial.open('xb');bz=gzip.GzipFile(filename='',mode='wb',fileobj=bf,compresslevel=3,mtime=0)
        err=(O/'ENGINE_STDERR.txt').open('a');engine=subprocess.Popen(['node',str(H/'server_optimized.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8',bufsize=1)
        def send(x):engine.stdin.write(json.dumps(x,separators=(',',':'))+'\n');engine.stdin.flush()
        try:
            send(dict(input=c['id'],scales=scales))
            while True:
                line=engine.stdout.readline();assert line,'Engine closed'
                m=json.loads(line)
                if m['type']=='FAIL':save(O/(label+'.failed.json.gz'),m);raise RuntimeError(m['error'])
                if m['type']=='DONE':raw=m['result'];break
                bank=m['bank'];assert bank['constraints']==dict(physical_slots_only=True,deadline_action_mask=False,critical_request_override=False,fixed_ATC_prior=False,post_NN_override=False)
                if learner and collect:
                    index,f=learner.choose(bank,True);f.update(time_ns=bank['time_ns'],action=bank['actions'][index]);frames.append(f)
                elif learner:
                    with torch.no_grad():
                        logits,_=learner.net(torch.from_numpy(np.asarray(bank['x'],np.float32))[None],torch.from_numpy(np.asarray(bank['mask'],bool))[None])
                        index=int(torch.multinomial(logits.log_softmax(-1).exp()[0],1,generator=eval_rng))
                else:index=rolling_atc(bank)
                assert bank['mask'][index];bz.write((json.dumps(dict(bank=bank,index=index),separators=(',',':'))+'\n').encode());decisions+=1;send(dict(index=index))
            bz.close();bf.flush();os.fsync(bf.fileno());bf.close();assert not bank_final.exists();os.replace(bank_partial,bank_final)
            save(O/(label+'.raw.json.gz'),raw)
            n=c['n'];skin=c['context']['initial_context']['targets']['AP']['anchor']['SKIN'];span=raw['observation_end_s']-35
            responded=[q for q in raw['requests'] if q['response'] is not None]
            physical=[max(0,raw['api_energy']-raw['baseline_API_J'])/n,max(0,(raw['AP_mean']-skin)/10),0.,0.,(n-len(responded))/n]
            for q in raw['requests']:
                response=q['response'];j=2 if q['priority']=='urgent' else 3
                late=response is None or response>q['deadline']+1e-9
                latency=(response if response is not None else raw['observation_end_s'])-q['arrival']
                physical[j]+=(float(late)+.2*min(5,max(0,latency)/(q['deadline']-q['arrival'])))/n
            factors=[n/raw['service'][k]['planned'] for k in ['urgent','normal']]
            normalized=[physical[0]/scales[0],physical[1]/scales[1],physical[2]*factors[0],physical[3]*factors[1],physical[4]]
            row=dict(label=label,kind=kind,input=c['id'],stream=c['stream'],method=method,seed=learner.seed if learner else None,epoch=epoch,n=n,mix=c['mix'],replicate=c['replicate'],load=.85,
                service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],incremental_J=raw['api_energy']-raw['baseline_API_J'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],
                baseline_J=raw['baseline_API_W']*raw['observation_end_s'],observation_s=raw['observation_end_s'],work_s=raw['actual_work_span_s'],routes=raw['policy_route_counts'],wait_s=raw['wait_s'],shared_cpu_wait_s=raw['shared_cpu_wait_s'],extra_cpu_core_s=raw['extra_cpu_core_s'],
                decisions=decisions,neural_calls=decisions if learner else 0,network_sha256=pre,deployment='training_sample' if collect else 'PPO_sample' if learner else 'deterministic_rule',train_rng_seed=crn,eval_rng_seed=eval_rng_seed,eval_rng_after_sha256=hashlib.sha256(eval_rng.get_state().numpy().tobytes()).hexdigest() if eval_rng else None,reused_environment=False,physical_cost=physical,normalized_cost=normalized,soft_objective=sum(v*w for v,w in zip(normalized,[1,1,1,1,3])),scales=scales,
                raw_sha256=sha(O/(label+'.raw.json.gz')),banks_sha256=sha(bank_final),physical_validation=False,wall_s=time.monotonic()-begin)
            if learner and collect:
                times=np.array([f['time_ns'] for f in frames],np.int64);cost=np.zeros((len(frames),5));assert len(times)>0
                def idx(t):return max(0,min(len(times)-1,int(np.searchsorted(times,round(t*1e9),side='right'))-1))
                for t0,t1,J,heat in raw['integrals']:
                    cost[idx(t0),0]+=(J-raw['baseline_API_W']*(t1-t0))/n
                    if physical[1]>0:cost[idx(t0),1]+=(heat-skin*(t1-t0))/(span*10)
                for q in raw['requests']:
                    response=q['response'];late=response is None or response>q['deadline']+1e-9
                    latency=(response if response is not None else raw['observation_end_s'])-q['arrival']
                    cost[idx(response) if response is not None else -1,2 if q['priority']=='urgent' else 3]+=(float(late)+.2*min(5,max(0,latency)/(q['deadline']-q['arrival'])))/n
                cost[-1,4]=physical[4];error=float(np.max(abs(cost.sum(0)-physical)));assert error<1e-7
                learning=cost.copy();learning[:,0]/=scales[0];learning[:,1]/=scales[1];learning[:,2]*=factors[0];learning[:,3]*=factors[1]
                pt(O/(label+'.frames.pt.gz'),dict(frames=frames,physical_costs=cost,learning_costs=learning,telescope_error=error,after_collect=learner.snapshot(),new_BC=0))
                learner.add(frames,learning)
            if learner and not collect:assert torch.equal(learner.action_rng.get_state(),train_rng_before),'DEV/EVAL cannot advance training RNG'
            save(O/(label+'.json'),row);rows.append(row);append(O/'receipts.jsonl',{**rec,'event':'COMPLETE','utc':now(),'raw_sha256':row['raw_sha256']})
            save(O/f'PROGRESS_{count:03d}.json',dict(START=count,COMPLETE=len(rows),FAIL=0,last=row))
            print('PURE_COMPLETE',count,label,'J',round(row['J'],3),'on',row['service']['all']['on_time'],'/',n,'AP',round(row['AP_mean'],3),'wall',round(row['wall_s'],1),flush=True)
            return row
        except BaseException as error:
            if frames:pt(O/(label+'.partial_frames.pt.gz'),dict(frames=frames,learner=learner.snapshot() if learner else None))
            append(O/'receipts.jsonl',{**rec,'event':'FAIL','utc':now(),'error':str(error),'automatic_retry':False});raise
        finally:
            if not bf.closed:bz.close();bf.flush();os.fsync(bf.fileno());bf.close()
            engine.stdin.close()
            try:engine.wait(timeout=20)
            except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)
            err.close();engine=None

    scales=read(H/'CALIBRATION_REFERENCE.json')['scales'];save(O/'SCALES_FROZEN.json',dict(scales=scales,reused_units_only=True))
    nets={};choices=[];selection_details=[]
    for seed in op['seeds']:
        # Read only TRAIN parameters and DEV/selection metadata before freezing this selection.
        gen=read(PRIMARY/f'S{seed}_G06_UPDATE.json');k=min(range(12),key=lambda i:(gen['scores'][i],i));assert k==gen['elite'][0]
        source_candidate=PRIMARY/f'TRAIN_S{seed}_G06_P{k:02d}_C0.75_after.pt.gz';source_mean=PRIMARY/f'S{seed}_SELECTED.pt.gz';source_initial=PRIMARY/f'S{seed}_EP000.pt.gz'
        candidate_state=own_load(source_candidate);mean_state=own_load(source_mean);initial_state=own_load(source_initial)
        fresh=Learner(seed);assert digest(fresh.net)==initial_state['network_sha256'],'Same fresh initial policy lineage'
        for source,name in [(source_candidate,f'S{seed}_CANDIDATE.pt.gz'),(source_mean,f'S{seed}_MEAN.pt.gz'),(source_initial,f'S{seed}_INITIAL.pt.gz')]:shutil.copyfile(source,O/name)
        checkpoint_files[f'CANDIDATE{seed}']=f'S{seed}_CANDIDATE.pt.gz';checkpoint_files[f'MEAN{seed}']=f'S{seed}_MEAN.pt.gz';checkpoint_files[f'RL{seed}']=f'S{seed}_SELECTED.pt.gz'
        mean_epoch=next(s['epoch'] for s in read(PRIMARY/'SELECTION_FROZEN.json')['selection'] if s['seed']==seed)
        rrmean=[reuse(c,f'{c["id"]}__RL{seed}_EP{mean_epoch:03d}',f'MEAN{seed}',f'{c["id"]}__MEAN{seed}',f'S{seed}_MEAN.pt.gz') for c in phase['DEV']]
        learner=Learner(seed);learner.restore(candidate_state)
        if candidate_state['network_sha256']==mean_state['network_sha256']:
            rrcandidate=[reuse(c,f'{c["id"]}__RL{seed}_EP{mean_epoch:03d}',f'CANDIDATE{seed}',f'{c["id"]}__CANDIDATE{seed}',f'S{seed}_CANDIDATE.pt.gz') for c in phase['DEV']]
        else:rrcandidate=[simulate(c,f'CANDIDATE{seed}',f'{c["id"]}__CANDIDATE{seed}','DEV',scales,learner,False,6) for c in phase['DEV']]
        mean_score=float(np.mean([r['soft_objective'] for r in rrmean]));candidate_score=float(np.mean([r['soft_objective'] for r in rrcandidate]));which='CANDIDATE' if candidate_score<mean_score-1e-12 else 'MEAN';state=candidate_state if which=='CANDIDATE' else mean_state
        source_file=O/f'S{seed}_{which}.pt.gz';shutil.copyfile(source_file,O/f'S{seed}_SELECTED.pt.gz');learner.restore(state);nets[seed]=learner
        detail=dict(seed=seed,which=which,candidate_generation=6,candidate_index=k,candidate_source=source_candidate.name,candidate_source_sha256=sha(source_candidate),candidate_network_sha256=candidate_state['network_sha256'],mean_epoch=mean_epoch,mean_source_sha256=sha(source_mean),mean_network_sha256=mean_state['network_sha256'],mean_score=mean_score,candidate_score=candidate_score,selected_score=min(mean_score,candidate_score) if which=='CANDIDATE' else mean_score,network_sha256=digest(learner.net),old_project_weights=0,new_training=0,DEV_mean_labels=[r['label'] for r in rrmean],DEV_candidate_labels=[r['label'] for r in rrcandidate])
        selection_details.append(detail);choices.append(dict(seed=seed,which=which,epoch=6 if which=='CANDIDATE' else mean_epoch,score=detail['selected_score'],network_sha256=digest(learner.net)))
    save(O/'SELECTION_FROZEN.json',dict(utc=now(),selection=choices,details=selection_details,source='DEV fixed soft objective only',fixed_runtime_seed=1181083,EVAL_used=0,new_training=0));selection=sha(O/'SELECTION_FROZEN.json')
    for c in phase['EVAL']:
        reuse(c,c['id']+'__ROLLING_ATC','ROLLING_ATC',c['id']+'__ROLLING_ATC')
        for seed in op['seeds']:
            reuse(c,f'{c["id"]}__INITIAL_RL{seed}',f'INITIAL_RL{seed}',f'{c["id"]}__INITIAL_RL{seed}',f'S{seed}_INITIAL.pt.gz')
            detail=next(d for d in selection_details if d['seed']==seed)
            if detail['which']=='MEAN' or detail['network_sha256']==detail['mean_network_sha256']:reuse(c,f'{c["id"]}__RL{seed}',f'RL{seed}',f'{c["id"]}__RL{seed}',f'S{seed}_SELECTED.pt.gz')
            else:simulate(c,f'RL{seed}',f'{c["id"]}__RL{seed}','EVAL',scales,nets[seed],False,6)
    verify();assert count<=36 and len(rows)==80 and count+reused==80
    save(O/'RESULT.json',dict(status='COMPLETE_SAME_FRESH_CEM_CANDIDATE_SELECTION',START=count,COMPLETE=count,REUSE=reused,logical_records=len(rows),FAIL=0,rows=rows,scales=scales,selection=choices,selection_details=selection_details,new_TRAIN=0,new_training=0,parent_TRAIN=432,CEM_parent_updates=18,new_PPO_updates=0,new_BC=0,earlier_weights=0,physical_validation=False,elapsed_s=time.monotonic()-started))
    save(O/'COMPLETE.json',dict(utc=now(),START=count,COMPLETE=count,REUSE=reused,result_sha256=sha(O/'RESULT.json')));print('CANDIDATE_SELECTION_COMPLETE',count,reused,flush=True)
if __name__=='__main__':
    op=read(H/'OPERATION.json');assert not O.exists(),'Consumed namespace; no automatic retry';assert read(H/'PREFLIGHT.json')['status']=='PASS'
    for pin in op['pins']:assert sha(pin['path'])==pin['sha256']
    lock=Path(op['shared_mutex']).open('r+b');locked=False
    try:
        deadline=time.monotonic()+3600
        while not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:
                if time.monotonic()>=deadline:raise
                time.sleep(5)
        resource=guard(time.monotonic()+3600);O.mkdir(parents=True);save(O/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(H/'OPERATION.json'),resource=resource))
        try:main(op)
        except BaseException as error:save(O/'FAILURE.json',dict(utc=now(),error=str(error),traceback=traceback.format_exc(),automatic_retry=False));raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
