"""Derive the event study runner without modifying any parent runtime."""
from pathlib import Path
import ast
W=Path(__file__).resolve().parent.parent;P=W/'S26-D1Check/s26_simulator/experiments/route_energy_v1';H=P.parent/'route_event_learning_v1'
s=(P/'run.py').read_text(encoding='utf-8')
def replace(a,b):
    global s
    assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
start=s.index('def snapshot_resources(');end=s.index('def main(op,O):',start)
s=s[:start]+'''def snapshot_resources(min_MiB=1536):
    import psutil,gc
    end=time.monotonic()+3600;last=0
    while True:
        gc.collect();processes=[p.info for p in psutil.process_iter(['pid','name','cmdline']) if (p.info['name'] or '').lower() in ['python.exe','python3.exe']]
        free=psutil.virtual_memory().available
        if len(processes)<=3 and free>=min_MiB*1024**2 and all(shutil.disk_usage(p).free>=8*1024**3 for p in [W,Path('D:/')]):return dict(utc=now(),free_bytes=free,python=processes,min_free_MiB=min_MiB,real_host_inventory=True)
        if time.monotonic()>=end:raise RuntimeError('Finite resource wait elapsed before START')
        if time.monotonic()-last>=30:print('EVENT_RESOURCE_WAIT',len(processes),round(free/1048576),flush=True);last=time.monotonic()
        time.sleep(5)
'''+s[end:]
replace("from nn_train import Learner,digest", "from nn_train import Learner,digest\n    from bc import teacher,pretrain")
old="engine=subprocess.Popen(['node',str(H/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(O/'ENGINE_STDERR.txt').open('x'),text=True,encoding='utf-8',bufsize=1)"
new="""engine=None
    def reset_engine():
        nonlocal engine
        if engine is not None:
            engine.stdin.close()
            try:engine.wait(timeout=20)
            except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)
            engine=None
        append(O/'RESOURCE_CHECKS.jsonl',dict(count=count,**snapshot_resources(1536)))
        engine=subprocess.Popen(['node',str(H/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(O/'ENGINE_STDERR.txt').open('a'),text=True,encoding='utf-8',bufsize=1)
"""
replace(old,new)
replace("if count%8==0:append(O/'RESOURCE_CHECKS.jsonl',snapshot_resources())",'if count%8==0:reset_engine()')
replace("assert m['type']=='BANK' and learner is not None", "assert m['type']=='BANK' and (learner is not None or mode=='DEMO')")
old="index,f=learner.choose(bank,collect);f.update(time_ns=bank['time_ns'],action=bank['actions'][index],candidate_actions=bank['actions'],nominal_forecasts=bank['forecasts']);frames.append(f);send(dict(index=index))"
new="""if mode=='DEMO':
                    index=teacher(bank);f=dict(x=np.asarray(bank['x'],np.float32),mask=np.asarray(bank['mask'],bool),scores=bank['scores'],index=index,from_teacher=True,collect=False)
                else:index,f=learner.choose(bank,collect)
                f.update(time_ns=bank['time_ns'],action=bank['actions'][index],candidate_actions=bank['actions'],nominal_forecasts=bank['forecasts']);frames.append(f);send(dict(index=index))"""
replace(old,new)
replace("if learner:\n                times=", "if mode=='DEMO':pt(O/(label+'.demonstrations.pt.gz'),dict(frames=frames,from_teacher=True,new_PPO_updates=0,balance=balance))\n            if learner:\n                times=")
start=s.index('        # Four counted numerical environments');end=s.index("    finally:\n        engine.stdin.close()",start)
body="""        c=phase['P0'][0]
        a,ra=simulate(c,'EDF_GPU_FIRST','P0_PARENT','P0','CPU3',parent=True)
        b,rb=simulate(c,'EDF_GPU_FIRST','P0_EVENT_ENGINE','P0','CPU3')
        assert abs(a['J']-b['J'])<1e-7 and abs(a['AP_mean']-b['AP_mean'])<1e-8
        assert all(abs(x['available']-y['available'])<1e-8 for x,y in zip(ra['requests'],rb['requests']))
        save(O/'P0_PROOF.json',dict(parent_CPU3_exact=True,max_J_error=abs(a['J']-b['J']),new_environments=2))
        parent=load(op['parent_checkpoint']);frozen=Learner(481083);frozen.restore(parent);frozen_sha=digest(frozen.net);references={};reference_rows=[]
        for i,c in enumerate(phase['TRAIN']):
            row,_=simulate(c,'RL',f'REFERENCE_{i}','TRAIN_REFERENCE','CPU3',frozen,parent=True);references[c['id']]=row;reference_rows.append(row)
        scales=[max(.05,float(np.median([r['cost'][j] for r in reference_rows]))) for j in [0,1]]
        demos=[]
        for i,c in enumerate([c for c in phase['TRAIN'] if c['nominal_load_ratio']==.85]):
            balance=dict(scales=scales,dual=[1.,1.],classFactors=[1/c['mix'],1/(1-c['mix'])],tail=.02)
            row,_=simulate(c,'DEMO',f'DEMO_{i}','DEMO','CPU3',balance=balance)
            data=load(O/(row['label']+'.demonstrations.pt.gz'));demos.append(data)
        warm,bc_trace=pretrain(parent,demos,op['BC_seed']);warm.balance=dict(scales=scales,dual=[1.,1.],classFactors=[1,1],tail=.02)
        pt(O/'BC_TRACE.pt.gz',bc_trace);pt(O/'BC_COMMON_FINAL.pt.gz',dict(learner=warm.snapshot(),balance=warm.balance));save(O/'BC_TRAINING.json',dict(logs=bc_trace['logs'],steps=bc_trace['steps'],frames=bc_trace['frames'],not_RL=True,new_PPO_updates=0,weight_sha256=digest(warm.net)));warm_sha=digest(warm.net)
        del demos
        nets={};dual_history=[]
        for seed in op['seeds']:
            learner=Learner(seed);learner.net.load_state_dict(warm.net.state_dict());learner.net.temperature=.35;learner.optimizer.param_groups[0]['lr']=1e-4;dual=np.ones(2);order=np.random.default_rng(seed+50000).permutation(8).tolist()
            save(O/f'S{seed}_ORDER.json',dict(order=order,case_ids=[phase['TRAIN'][j]['id'] for j in order],scales=scales,common_BC_sha256=warm_sha));pt(O/f'S{seed}_EP000.pt.gz',learner.snapshot())
            for ep,j in enumerate(order,1):
                c=phase['TRAIN'][j];ref=references[c['id']];balance=dict(scales=scales,dual=dual.tolist(),classFactors=[c['n']/ref['service'][k]['planned'] for k in ['urgent','normal']],tail=.02);learner.balance=copy.deepcopy(balance)
                pt(O/f'S{seed}_EP{ep:03d}_before.pt.gz',dict(learner=learner.snapshot(),balance=balance));row,_=simulate(c,'RL',f'TRAIN_S{seed}_EP{ep:03d}','TRAIN','CPU3',learner,True,balance=balance)
                deficits=np.array([(ref['service'][k]['on_time']-row['service'][k]['on_time'])/ref['service'][k]['planned']-.005 for k in ['urgent','normal']]);old=dual.copy();dual=np.clip(dual+4*deficits,.25,8.);dual_history.append(dict(seed=seed,ep=ep,before=old.tolist(),after=dual.tolist(),deficits=deficits.tolist()))
                pt(O/f'S{seed}_EP{ep:03d}_after.pt.gz',dict(learner=learner.snapshot(),dual=dual.tolist(),balance=balance))
            assert learner.episodes==8 and learner.updates==4 and not learner.pending
            learner.balance=dict(scales=scales,dual=dual.tolist(),classFactors=[1,1],tail=.02);nets[seed]=learner;pt(O/f'S{seed}_FINAL.pt.gz',dict(learner=learner.snapshot(),balance=learner.balance))
        save(O/'TRAINING_COMPLETE.json',dict(scales=scales,TRAIN_REFERENCE=8,DEMO=4,TRAIN=24,PPO_updates=12,dual_history=dual_history,updates={str(s):l.logs for s,l in nets.items()},BC_source_sha256=sha(O/'BC_COMMON_FINAL.pt.gz')))
        def evaluate(c,phase,i):
            for mode in ['EDF_GPU_FIRST','ATC','ATC_SALVAGE']:simulate(c,mode,f'{phase}_{i}_{mode}',phase,'CPU3',parent=True)
            simulate(c,'RL',f'{phase}_{i}_FROZEN',phase,'CPU3',frozen,parent=True)
            for label,learner in [('WARM_FROZEN',warm),*[(f'RL_S{s}',l) for s,l in nets.items()]]:
                balance=copy.deepcopy(learner.balance);balance['classFactors']=[1/c['mix'],1/(1-c['mix'])];simulate(c,'RL',f'{phase}_{i}_{label}',phase,'CPU3',learner,balance=balance)
        for i,c in enumerate(phase['DEV']):evaluate(c,'DEV',i)
        dev=[r for r in rows if r['kind']=='DEV'];ref={r['input']:r for r in dev if r['seed']==481083};scores=[]
        for seed in op['seeds']:
            rr=[r for r in dev if r['seed']==seed];assert len(rr)==4
            harm=sum(max(0,(ref[r['input']]['service'][k]['on_time']-r['service'][k]['on_time'])/r['service'][k]['planned']-.005)**2 for r in rr for k in ['urgent','normal'])
            energyheat=sum(r['incremental_J']/ref[r['input']]['incremental_J']+r['cost'][1]/max(.05,ref[r['input']]['cost'][1]) for r in rr)/len(rr);key=(sum(r['unfinished'] for r in rr),harm,energyheat,seed);scores.append(dict(seed=seed,key=key))
        selected=min(scores,key=lambda x:x['key'])['seed'];save(O/'SELECTION_FROZEN.json',dict(utc=now(),selected=selected,scores=scores,rule='DEV only; missing, class deficits beyond0.5pp, energy+heat, seed'));selection=sha(O/'SELECTION_FROZEN.json')
        for i,c in enumerate(phase['EVAL']):evaluate(c,'EVAL',i)
        assert count==134 and len(rows)==134 and digest(frozen.net)==frozen_sha and digest(warm.net)==warm_sha
        verify();save(O/'RESULT.json',dict(status='EVENT_ROUTE_BALANCED_PPO_COMPUTATION_COMPLETE',START=count,COMPLETE=count,FAIL=0,rows=rows,selected=selected,PPO_updates=12,BC_steps=bc_trace['steps'],scales=scales,physical_validation=False,elapsed_s=time.monotonic()-started));save(O/'COMPLETE.json',dict(utc=now(),START=count,sha256=sha(O/'RESULT.json')))
        print('EVENT_ROUTE_LEARNING_COMPLETE',count,flush=True)
"""
s=s[:start]+body+s[end:]
replace("        engine.stdin.close()\n        try:engine.wait(timeout=15)\n        except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)", "        if engine is not None:\n            engine.stdin.close()\n            try:engine.wait(timeout=15)\n            except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)")
replace('resource=snapshot_resources(2048);O.mkdir(parents=True)', 'resource=snapshot_resources(1536);O.mkdir(parents=True)')
compile(s,str(H/'run.py'),'exec');(H/'run.py').write_text(s,encoding='utf-8');print('EVENT_RUNNER134_READY')
