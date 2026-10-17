"""One registered cost-aware PPO generation; no retries or old ledger reuse."""
from pathlib import Path
import copy,gc,gzip,json,math,os,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ENTRY=Path(__file__).resolve()
os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)
sys.path[:0]=[str(HERE),str(ROOT/'src'),str(ROOT/'experiments/rules_no_rl_20261017'),
             str(ROOT/'experiments/long_scale_20261017'),
             str(ROOT/'experiments/competition_cost_20261017'),str(ROOT/'experiments/rr_20261017'),
             str(ROOT/'experiments/edf_cpu_first_20261016')]
import lab_backend as L
from shared_exact import public_input,metrics,save_binary
from rr_policy import installed as install_rr
from rules import installed as install_rules
from policy import installed as install_edf
from rl_policy import ProtectedPolicy,CONFIG,FAMILY
from rewards import make_costs,SPEC
from fast_thermal import FastThermal
from snapshots import save_torch,save_snapshot,load_snapshot
import numpy as np,torch
torch.set_num_threads(1)
K=L.load_module('cost_rl_long_kernel',ROOT/'experiments/long_scale_20261017/kernel_long.py')
G=L.runtime_guard
G.OWN_TOKENS+=('rr_20261017','rl_cost_20261017','s26-multiresource-','s26-state-aware-atc-',
               'state_recovery_owner','long_scale_20261017','rules_no_rl_20261017')
NEW='ROLLING_ATC_RL_COST';CONTROL='ATC_COST_NO_NN'


def dev_score(rows,baseline):
    """Predeclared deadline tolerance then heat/energy score; DEV only."""
    def average(values):return sum(values)/len(values)
    return [sum(r['response_missing'] for r in rows),
            max(max(0,(b['on_time']-r['on_time'])/r['planned']-.01) for r,b in zip(rows,baseline)),
            max(max(0,.95-r['on_time']/r['planned']) for r in rows),
            max(max(0,.95-r['urgent_on_time']/max(1,r['urgent_planned'])) for r in rows),
            average([.5*(r['increment_J_proxy']/max(.01,b['increment_J_proxy'])-1)+
                     .5*(r['mean_AP_c']-b['mean_AP_c'])/.5 for r,b in zip(rows,baseline)]),
            average([r['total_J_proxy']/b['total_J_proxy']-1 for r,b in zip(rows,baseline)])]


def run(opfile):
    op=L.read(opfile);opsha=L.sha(opfile)
    L.need(op['schema']=='A24-cost-RL-operation-v1' and op['policy_config']==CONFIG and op['reward_spec']==SPEC,'Frozen design')
    for p in op['pins']:L.pin(p)
    reg=L.read(ROOT/'models/registration.json');G.process_guard(ENTRY,reg['known_PS_producer_paths']);L.free_guard([ROOT,'D:/'])
    out=ROOT/op['output_dir'];L.need(not out.exists(),'Consumed operation namespace; no restart')
    import msvcrt
    lock=Path(reg['worker_lock_path']).open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0
    try:
        out.mkdir(parents=True,exist_ok=False)
        L.write_new(out/'START.json',dict(utc=L.now(),operation_sha256=opsha,process=G.process_guard(ENTRY,reg['known_PS_producer_paths'])))
        try:
            base,thermal,profile=L.initialize(reg);catalog=L.read(L.pin(reg['catalog_pin']))
            cost=L.read(L.pin(op['cost_model']));design=L.read(L.pin(op['inputs']));budget=L.read(L.pin(op['budget']))
            learn=L.load_module('cost_rl_native_learner',ROOT/'reference/rolling/learner.py')
            learner=learn.Learner(op['learner_seed'],FAMILY,learn.Settings(**op['learner_settings']))
            warm=torch.load(L.pin(op['warm_start']),map_location='cpu',weights_only=False)
            learner.net.load_state_dict(warm['network'])
            L.write_new(out/'INITIALIZATION.json',dict(network_sha256=learn.network_digest(learner.net),
                optimizer_restarted=True,warm_start_network_only=True,physical_model_unchanged=True))

            def simulate(case,policy,label,live=None,collect=False):
                nonlocal count
                G.process_guard(ENTRY,reg['known_PS_producer_paths']);L.free_guard([ROOT,'D:/'])
                L.need(count<op['environment_cap'],'Own environment cap')
                previous=0
                for spec in budget['global_ledgers']:
                    path=Path(spec['path'])
                    if not path.exists():L.need(spec['START']==0,'Missing nonzero global ledger');continue
                    previous+=sum(json.loads(s).get('event')=='START' for s in path.read_text(encoding='utf-8-sig').splitlines() if s)
                L.need(previous+count<137712,'Global START cap')
                public,contexts=public_input(case,catalog);model=L.Model(base,contexts)
                start=dict(event='START',identity=L.digest([opsha,label]),start_id=L.digest([opsha,label]),
                    registration_sha256=opsha,durable_START_consumed=True,label=label,policy=policy,
                    input_sha256=L.digest(case['input']),n=case['n'],utc=L.now())
                L.append(out/'receipts.jsonl',start);count+=1;print('START',label,flush=True)
                try:
                    actor=None;before=None;trace=[]
                    if policy in (NEW,CONTROL):
                        before=out/(label+'.before.pt.gz')
                        if collect:save_snapshot(live,before)
                        actor=ProtectedPolicy(model,public,thermal,profile,live,learn,collect,policy==CONTROL)
                    original_predict=L.thermal_model.predict
                    if actor:
                        streaming=FastThermal(L.thermal_model,original_predict,public,thermal)
                        L.thermal_model.predict=streaming.predict
                    try:
                        with install_edf(K,L),install_rules(K,trace),install_rr(K,trace):
                            pred=K.simulate_protocol(public,model,'FROZEN_RL_REPLAY' if actor else policy,
                                execution_guard=start,scenario_key=case['common_potential_key'],admission_protocol='SERIAL',
                                redispatch_mode='ZERO_EXPLICIT_BASELINE',zero_baseline_id='COMMON_UNIDENTIFIED_CONTROLLER_IDEAL_ZERO',
                                pair_scope='READY_QUEUE',decision_cap=max(8192,case['n']*64),
                                concurrency_mode='DATA_DERIVED_PROGRESS',unidentified_overlap='SERIAL_INDEPENDENT',
                                frozen_policy=actor,frozen_policy_binding=dict(replay_only=True,
                                    checkpoint_sha256=actor.network_sha,input_contract_sha256=opsha) if actor else None)
                    finally:L.thermal_model.predict=original_predict
                    pred['rule_decision_audit']=trace
                    # Preserve completed dynamics before all postprocessing/update checks.
                    save_binary(out/(label+'.prepared_prediction.json.gz'),gzip.compress(L.canonical(pred).encode(),compresslevel=1,mtime=0))
                    if actor:
                        save_torch(out/(label+'.frames.pt.gz'),actor.controller.frames)
                        save_binary(out/(label+'.actor_calls.json.gz'),gzip.compress(L.canonical(actor.bank_audits).encode(),compresslevel=1,mtime=0))
                    activity=L.generated_activity(public,pred);end=public['observation_end_ns']/1e9
                    times=sorted(set([0.,35.,case['work_window'][1],end]+[float(i) for i in range(math.ceil(end))]))
                    ap=original_predict(thermal,activity,times=times,allow_extrapolation=True)
                    L.need(ap['status']=='CONDITIONAL_AP_PREDICTION','AP prediction status')
                    summary=dict(policy=policy,requests=pred['requests'],gantt=activity['owner_intervals'],AP=dict(t_s=ap['t_s'],ap_c=ap['ap_c']))
                    m=metrics(summary,pred,case,cost)
                    raw=out/(label+'.raw.json.gz');save_binary(raw,gzip.compress(L.canonical(dict(prediction=pred,summary=summary)).encode(),compresslevel=1,mtime=0))
                    if collect:
                        for f in actor.controller.frames:
                            rp=learn.replay_frame(live.net,f)
                            L.need(abs(rp['logprob']-f['old_logp'])<1e-6 and np.allclose(rp['critic'],f['value'],atol=1e-6,rtol=1e-5),'Input/logprob/critic replay')
                        costs,counts,proof=make_costs(summary,actor.controller.frames,case,cost,public['initial_ap_c'])
                        exp=out/(label+'.experience.pt.gz')
                        save_torch(exp,dict(frames=actor.controller.frames,costs=costs,role_counts=counts,alpha=.95,proof=proof))
                        live.add_episode(actor.controller.frames,costs,.95,counts)
                        after=out/(label+'.after.pt.gz');save_snapshot(live,after)
                        L.write_new(out/(label+'.learning.json'),dict(before=dict(path=str(before),sha256=L.sha(before)),
                            after=dict(path=str(after),sha256=L.sha(after)),experience=dict(path=str(exp),sha256=L.sha(exp)),
                            before_network=actor.network_sha,after_network=learn.network_digest(live.net),
                            updates=live.updates,Adam_steps=live.steps,reward=proof))
                    row=dict(label=label,n=case['n'],policy=policy,metrics=m,raw_sha256=L.sha(raw),
                             source_result_path=str((out/(label+'.json')).relative_to(ROOT)).replace('\\','/'),
                             network_sha256=actor.network_sha if actor else None,NN_training=bool(collect),
                             measured_J=None,physical_goal_verified=False)
                    L.write_new(out/(label+'.json'),row)
                    for event in ('PREPARED','COMPLETE'):L.append(out/'receipts.jsonl',{**start,'event':event,'result_sha256':L.sha(out/(label+'.json')),'raw_sha256':row['raw_sha256'],'utc':L.now()})
                    print('COMPLETE',label,count,'on_time',m['on_time'],'/',case['n'],flush=True)
                    return row
                except BaseException as e:
                    L.append(out/'receipts.jsonl',{**start,'event':'FAIL','error':str(e),'automatic_retry':False,'utc':L.now()});raise

            checkpoints={}
            for i,case in enumerate(design['train'],1):
                simulate(case,NEW,'TRAIN_%03d'%i,learner,True)
                if i in op['checkpoint_episodes']:
                    path=out/('PPO_COST_EP%03d.pt.gz'%i);save_snapshot(learner,path)
                    checkpoints[i]=dict(path=str(path),sha256=L.sha(path),bytes=path.stat().st_size)
            dev_edf=[simulate(c,'EDF_CPU_FIRST','DEV_EDF_%02d'%i)['metrics'] for i,c in enumerate(design['dev'])]
            rankings=[]
            for episode,cp in checkpoints.items():
                frozen=load_snapshot(learn,cp['path'])
                rows=[simulate(c,NEW,'DEV_EP%03d_%02d'%(episode,i),frozen)['metrics'] for i,c in enumerate(design['dev'])]
                rankings.append(dict(episode=episode,checkpoint=cp,score=dev_score(rows,dev_edf)))
            selected=min(rankings,key=lambda r:(r['score'],r['episode']))
            L.write_new(out/'SELECTION_FROZEN.json',dict(selected=selected,rankings=rankings,evaluation_outcomes_opened=0,selection='DEV_ONLY_FIXED_SCORE'))
            frozen=load_snapshot(learn,selected['checkpoint']['path'])
            fresh=[]
            for i,case in enumerate(design['fresh_eval']):
                rows=[simulate(case,p,'FRESH_%02d_%s'%(i,p),frozen if p==NEW else None)
                      for p in ('EDF_CPU_FIRST','FIFO_CPU_FIRST','RR_CPU_FIRST','ROLLING_ATC',NEW)]
                fresh.append(dict(case=case,rows=rows))
            historical=[];saved=L.read(L.pin(op['saved_RR_comparison']))
            for i,case in enumerate(design['historical']):
                old=next(c for c in saved['cases'] if c['n']==case['n'])
                new=simulate(case,NEW,'HISTORICAL_%05d'%case['n'],frozen)
                historical.append(dict(case=case,rows=[*old['rows'],new]))
            controls=[dict(case=c,rows=[simulate(c,CONTROL,'CONTROL_%02d'%i,frozen)]) for i,c in enumerate(design['fresh_eval'])]
            for p in op['pins']:L.pin(p)
            L.write_new(out/'RESULT.json',dict(schema='A24-cost-RL-result-v1',selected=selected,rankings=rankings,
                fresh=fresh,historical=historical,controls=controls,new_START=count,new_COMPLETE=count,new_FAIL=0,
                updates=learner.updates,Adam_steps=learner.steps,new_fit=0,measured_J=None,
                physical_goal_verified=False,fresh_device_confirmation=False,operation_sha256=opsha))
            L.need(count==op['planned_STARTs'],'Exact planned START count')
            L.write_new(out/'COMPLETE.json',dict(utc=L.now(),result_sha256=L.sha(out/'RESULT.json'),new_START=count,new_COMPLETE=count))
        except BaseException as e:
            L.write_new(out/'FAILURE.json',dict(utc=L.now(),error=str(e),automatic_retry=False));raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':run(sys.argv[1])
