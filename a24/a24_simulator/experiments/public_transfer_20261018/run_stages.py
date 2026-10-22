"""Finite, preregistered staged public-policy transfer; no automatic retries."""
from pathlib import Path
import sys,os,copy,gc,time,subprocess
from common_transfer import *
from transfer_learner import Learner,digest
from transfer_policy import Policy
from transfer_rewards import labels
from controller import Controller
ENTRY=Path(__file__).resolve();os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY);B.G.OWN_TOKENS+=('public_transfer_20261018',)
def main():
    op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir'];opsha=B.G.sha(HERE/'OPERATION.json')
    assert '--published' in sys.argv and not out.exists()
    assert subprocess.check_output(['git','show','HEAD:a24_simulator/experiments/public_transfer_20261018/OPERATION.json'])==(HERE/'OPERATION.json').read_bytes()
    for p in op['sources']+op['input_pins']:B.G.pin(p)
    guard=wait_resources(ENTRY,1536*1024**2,time.monotonic()+1800);B.G.free_guard([ROOT,'D:/'])
    import msvcrt
    lock=(ROOT/'runtime/a24_local_worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);begin=time.monotonic();rows=[];count=0;demos=[];replay_frames=0;replay_updates=0
    try:
        out.mkdir();B.G.write_new(out/'START.json',dict(utc=B.G.now(),operation_sha256=opsha,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),resource_guard=guard))
        try:
            design=read(op['inputs']['path']);train=design['training'];evaluation=design['evaluation'];cases={c['id']:c for c in [*train,*evaluation]};catalog=read(B.L.pin(B.registration(op)['catalog_pin']));nominals=read(op['public_nominals']['path']);physics=B.Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),B.Config(**op['physics']));refs=op['reward_references'];scales=np.ones(2)
            def get(case):
                public,contexts=B.public_input(case,catalog);public['initial_ap_c']=case['temperature_c'];bank=read(op['bank_map'][case['id']]['path']);vectors=nominals[case['id']] if case['id'].startswith('DENSITY_') else bank['nominal_vectors'];return public,B.BankModel(bank['jobs'],contexts),B.SavedNominal(public,[dict(nominal_vectors=vectors)])
            def simulate(case,policy,kind,stage=1,learner=None,label=None,p0=None,event_probe=False):
                nonlocal count,replay_frames,replay_updates
                assert count<op['environment_cap'] and time.monotonic()-begin<op['wall_clock_limit_s']
                resource=wait_resources(ENTRY,768*1024**2+case['n']*128*1024,begin+op['wall_clock_limit_s']);B.G.free_guard([ROOT,'D:/']);label=label or case['id']+'__'+policy;receipt=dict(event='START',label=label,case=case['id'],policy=policy,kind=kind,stage=stage,seed=learner.seed if learner else None,identity=B.L.digest([opsha,label]),start_id=B.L.digest([opsha,label]),durable_START_consumed=True,utc=B.G.now(),operation_sha256=opsha)
                B.G.append(out/'receipts.jsonl',receipt);count+=1;print('START',count,label,flush=True)
                try:
                    public,model,nominal=get(case);actor=Controller(nominal,physics,case,policy) if policy in ('FIFO','EDF') else Policy(nominal,physics,case,learner,kind=='TRAIN',stage,demo=kind=='DEMO')
                    if event_probe:
                        old=actor;fired=[False]
                        def probe(state):
                            if state['owners'] and state['queue'] and not fired[0]:fired[0]=True;return dict(kind='WAIT_EVENT',max_wait_ns=1_500_000_000)
                            return old(state)
                        actor=probe
                    before=learner.snapshot() if learner else None
                    if learner:pt(out/(label+'.BEFORE.pt.gz'),before)
                    result=execute(public,model,actor,physics,case['common_potential_key'],receipt);m=B.metrics(result,case,physics)
                    calls=[] if event_probe else actor.calls;frames=[] if event_probe else getattr(actor,'frames',[]);reward=None;cost=None
                    if learner:
                        selected_calls=[c for c in calls if not c.get('common_coalescing')];assert len(selected_calls)==len(frames)
                        for call,f in zip(selected_calls,frames):call['old_logp']=f['old_logp']
                    if event_probe:
                        waits=[d for d in result['decisions'] if d['action']['kind']=='WAIT_EVENT'];assert len(waits)==1 and waits[0]['event_wait_end_ns']>waits[0]['time_ns'];assert waits[0]['event_wait_elapsed_ns']<=1_500_000_000
                    if kind=='DEMO':
                        # Store the actual public states, so later representations can be reencoded without new environments.
                        states=[d['public_state'] for c,d in zip(calls,result['decisions']) if not c.get('common_coalescing')];assert len(states)==len(frames);pt(out/(label+'.DEMO.pt.gz'),dict(frames=frames,states=states,case=case['id']));demos.append(label)
                    if learner:
                        cost,reward=labels(result,frames,case,physics,refs[case['id']],learner.balanced,scales);pt(out/(label+'.frames.pt.gz'),dict(frames=frames,costs=cost,reward_audit=reward))
                        # Exact action replay starts before stochastic draws, then exact optimizer/RNG replay after update.
                        replica=Learner(state=before)
                        for f in frames:
                            idx,again=replica.choose({k:f[k] for k in ('x','mask','scores')},kind=='TRAIN');assert idx==f['index'] and again['old_logp']==f['old_logp'] and np.array_equal(again['value'],f['value']);replay_frames+=1
                        if kind=='TRAIN':
                            old_updates=learner.updates;learner.add(frames,cost);replica.add(frames,cost)
                            if learner.balanced:
                                deficits=np.array([(refs[case['id']]['urgent_on_time']-m['urgent_on_time'])/max(1,m['urgent_planned'])-.005,((refs[case['id']]['on_time']-refs[case['id']]['urgent_on_time'])-(m['on_time']-m['urgent_on_time']))/max(1,case['n']-m['urgent_planned'])-.005]);learner.dual=np.clip(learner.dual+4*deficits,.25,8.);replica.dual=learner.dual.copy()
                            replay_updates+=learner.updates-old_updates
                        equal(learner.snapshot(),replica.snapshot());pt(out/(label+'.AFTER.pt.gz'),learner.snapshot());del replica
                    if p0:
                        expected=read(p0)['result']
                        for k in ('requests','trace','decisions'):assert B.G.canonical(result[k])==B.G.canonical(expected[k]),'Event-disabled physical exact '+k
                    raw=out/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=calls,future_actual_work_used=False,future_arrivals_used=False,event_probe=event_probe));row=dict(label=label,case=case['id'],policy=policy,kind=kind,stage=stage,seed=learner.seed if learner else None,n=case['n'],condition=case['condition'],metrics=m,raw_sha256=B.G.sha(raw),network_sha256=digest(learner.net) if learner else None,decision_network_sha256=before['network_sha256'] if before else None,network_file=label+'.BEFORE.pt.gz' if before else None,reward_audit=reward,resource_guard=resource,event_probe=event_probe,p0_parent=p0)
                    B.G.write_new(out/(label+'.json'),row);rows.append(row);B.G.append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','utc':B.G.now(),'raw_sha256':row['raw_sha256']});print('COMPLETE',label,m['on_time'],m['urgent_on_time'],'elapsed',round(time.monotonic()-begin,1),flush=True);del result,actor,model;gc.collect();return row
                except BaseException as e:B.G.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','utc':B.G.now(),'error':str(e),'automatic_retry':False});raise
            for cid in op['P0_cases']:
                for p in ('EDF','FIFO','PACKING_PUBLIC'):simulate(cases[cid],p,'P0',label='P0__'+cid+'__'+p,p0=op['reuse'][cid][p]['path'])
                simulate(cases[cid],'EDF','EVENT_CONTRACT',label='EVENT_CONTRACT__'+cid,event_probe=True)
            B.G.write_new(out/'P0_EXACT.json',dict(status='PASS',rows=6,fields=['requests','trace','decisions'],event_wake_contracts=2))
            for case in train:simulate(case,'PUBLIC_TEACHER','DEMO',label='DEMO__'+case['id'])
            warm_by_stage={};BC=[]
            for stage in (1,3,4):
                allframes=[]
                for name in demos:
                    data=loadpt(out/(name+'.DEMO.pt.gz'));case=cases[data['case']];public,model,nominal=get(case);encoder=Policy(nominal,physics,case,stage=stage)
                    for original,state in zip(data['frames'],data['states']):
                        # Restore public fixed-WAIT dose for identical legal fixed actions; teachers never select policy WAIT.
                        bank,actions,*_=encoder.encode(state);assert actions[original['index']]['kind']=='DISPATCH'
                        allframes.append(dict(**bank,index=original['index'],teacher_mask=np.pad(original['teacher_mask'][:original['mask'].sum()],(0,ACTIONS-int(original['mask'].sum())),constant_values=False),group=original['group']))
                    del data,model;gc.collect()
                learner=Learner(op['BC_seed']);initial=learner.snapshot();trace=learner.distill(allframes);pt(out/f'BC_S{stage}.TRACE.pt.gz',dict(initial=initial,trace=trace));pt(out/f'BC_S{stage}.FRAMES.pt.gz',allframes);pt(out/f'BC_S{stage}.FINAL.pt.gz',learner.snapshot());warm_by_stage[stage]=learner.snapshot();BC.append(dict(stage=stage,epochs=len(trace['logs']),steps=learner.bc_steps,final=trace['logs'][-1],network_sha256=digest(learner.net)))
                # Exact replay of actual BC optimizer updates from identical init and shuffle RNG.
                check=Learner(state=initial);again=check.distill(allframes);equal(check.snapshot(),learner.snapshot());equal(again,trace);del check,learner,allframes;gc.collect()
            B.G.write_new(out/'BC_EXACT.json',dict(status='PASS',fits=3,rows=BC,new_environment_START=0,public_teacher=True))
            # TRAIN-only reference scaling, unchanged among all balanced stages.
            scales=np.array([1.,1.]);B.G.write_new(out/'TRAIN_SCALES.json',dict(scales=scales.tolist(),meaning='Already dimensionless total-E/reference-E and heat/reference-heat; component advantage RMS supplies variance scaling',evaluation_used=False))
            for stage in (1,3,4):
                learner=Learner(state=warm_by_stage[stage])
                for case in evaluation:simulate(case,f'BC_S{stage}','BC_EVAL',stage,learner)
                del learner;gc.collect()
            for stage in (1,2,3,4):
                for seed in op['seeds']:
                    learner=Learner(seed,stage>=2);learner.net.load_state_dict(warm_by_stage[1 if stage<=2 else stage]['network']);learner.scales=scales.copy();pt(out/f'S{stage}_SEED{seed}.INITIAL.pt.gz',learner.snapshot())
                    for ep,case in enumerate(train):simulate(case,f'S{stage}_SEED{seed}','TRAIN',stage,learner,label=f'TRAIN__S{stage}__SEED{seed}__EP{ep+1:03d}')
                    assert learner.episodes==8 and learner.updates==4 and not learner.pending;pt(out/f'S{stage}_SEED{seed}.FINAL.pt.gz',learner.snapshot())
                    B.G.write_new(out/f'S{stage}_SEED{seed}.SELECTION_FROZEN.json',dict(rule='Fixed final EP8, no evaluation selection',stage=stage,seed=seed,digest=digest(learner.net)))
                    for case in evaluation:simulate(case,f'S{stage}_SEED{seed}','EVAL',stage,learner)
                    del learner;gc.collect()
            assert count==562 and len(rows)==562 and replay_updates==48
            for p in op['sources']+op['input_pins']:B.G.pin(p)
            B.G.write_new(out/'REPLAY.json',dict(status='PASS',all_saved_actions=replay_frames,exact_PPO_updates=replay_updates,exact_BC_fits=3,network_two_Adam_RNG=True,new_environment_START=0))
            B.G.write_new(out/'RESULT.json',dict(status='COMPLETED',rows=rows,new_START=count,new_COMPLETE=count,new_FAIL=0,TRAIN=96,PPO_updates=48,BC_fits=3,new_LP=0,new_fit=0,new_device=0,new_latent_draws=0,operation_sha256=opsha));B.G.write_new(out/'COMPLETE.json',dict(utc=B.G.now(),elapsed_s=time.monotonic()-begin))
            subprocess.run([op['node_executable'],str(HERE/'audit.cjs')],check=True)
            subprocess.run([op['python_executable'],'-B',str(HERE/'report_transfer.py')],check=True)
        except BaseException as e:B.G.write_new(out/('POSTPROCESS_FAILURE.json' if (out/'COMPLETE.json').exists() else 'FAILURE.json'),dict(utc=B.G.now(),error=str(e),new_START=count,automatic_retry=False));raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
