"""One registered 48-request fine-tune, DEV selection, and fresh-seed evaluation.
No automatic retry or expansion. Frozen physical model and old results survive.
"""
from pathlib import Path
import argparse,copy,gzip,json,os,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'experiments/edf_cpu_first_20261016'))
os.environ['A24_LAB_GUARD_ENTRY']=str(Path(__file__).resolve())
import lab_backend as L
import interactive_kernel as kernel
from policy import installed as edf_installed,metrics
from protected_policy import ProtectedPolicy,CONFIG,FAMILY
from dense_rewards import make_costs,SPEC as REWARD_SPEC
import numpy as np,torch
torch.set_num_threads(1)
ENTRY=Path(__file__).resolve()
L.runtime_guard.OWN_TOKENS+=('protected48_20261016','edf_cpu_first_20261016')
NEW='ROLLING_ATC_RL_PROTECTED48'
CONTROL='PROTECTION_ATC_COST_NO_RL'
OLD='ROLLING_ATC_RL'
EDF='EDF_CPU_FIRST'

def pins(op):
    for s in op['source_pins']+op['input_pins']:L.pin(s)

def aggregate(cases,policy):
    rows=[next(r for r in c['metrics'] if r['policy']==policy) for c in cases]
    out={'policy':policy,'conditions':len(rows)}
    for k in ('baseline_J_proxy','total_J_proxy','increment_J_proxy','mean_AP_c','peak_AP_c','end_AP_c'):
        out[k]=sum(r[k] for r in rows)/len(rows)
    for k in ('planned','on_time','responded','response_missing','responded_by_window_end','AVAILABLE_by_window_end'):
        out[k]=sum(r[k] for r in rows)
    out['on_time_percent']=100*out['on_time']/out['planned']
    out['total_tardiness_s']=sum(r['total_tardiness_s'] for r in rows) if all(r['total_tardiness_s'] is not None for r in rows) else None
    out['by_priority']={p:{k:sum(c['rows'][[r['policy'] for r in c['rows']].index(policy)]['by_priority'][p][k] for c in cases) for k in ('planned','on_time','missing')} for p in ('U','N')}
    return out

def selection_score(rows,baselines):
    m=[metrics(r,*r['diagnostics']['common_work_window_s']) for r in rows]
    b=[metrics(r,*r['diagnostics']['common_work_window_s']) for r in baselines]
    urgent=sum(r['by_priority']['U']['planned']-r['by_priority']['U']['on_time'] for r in rows)
    normal=sum(r['by_priority']['N']['planned']-r['by_priority']['N']['on_time'] for r in rows)
    harms=sum(x['total_J_proxy']>y['total_J_proxy']+1e-8 for x,y in zip(m,b))+sum(x['mean_AP_c']>y['mean_AP_c']+1e-6 for x,y in zip(m,b))
    short=np.mean([max(0,(x['total_J_proxy']/y['total_J_proxy']-.9)/.1)+max(0,(x['mean_AP_c']-y['mean_AP_c']+.5)/.5) for x,y in zip(m,b)])
    return [sum(r['metrics']['response_missing'] for r in rows),urgent,normal,int(harms),float(short),
            float(np.mean([x['total_J_proxy'] for x in m])),float(np.mean([x['mean_AP_c'] for x in m]))]

def main(operation):
    op_path=Path(operation);op=L.read(op_path);op_sha=L.sha(op_path)
    L.need(op['schema']=='A24-protected48-training-operation-v1','Operation schema')
    L.need(op['protection_config']==CONFIG and op['reward_spec']==REWARD_SPEC,'Policy/reward freeze')
    pins(op)
    reg=L.read(ROOT/'models/registration.json')
    L.runtime_guard.process_guard(ENTRY,reg['known_PS_producer_paths'])
    L.free_guard([ROOT,'D:/',reg['worker_lock_path']])
    out=ROOT/op['output_dir'];runtime=ROOT/op['runtime_dir'];ledger=ROOT/'runtime/receipts.jsonl'
    events=[json.loads(s) for s in ledger.read_text().splitlines() if s]
    L.need(sum(r['event']=='START' for r in events)==op['expected_child_START_before'],'Shared budget snapshot changed')
    L.need(op['expected_child_START_before']+op['new_environment_cap']<=reg['environment_cap'],'Shared child budget exceeded')
    L.need(not out.exists() and not runtime.exists(),'Consumed output; no automatic restart')
    import msvcrt
    lock=Path(reg['worker_lock_path']).open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0
    try:
        out.mkdir(parents=True,exist_ok=False);runtime.mkdir(parents=True,exist_ok=False)
        L.write_new(out/'OPERATION_START.json',dict(operation_sha256=op_sha,utc=L.now(),process=L.runtime_guard.process_guard(ENTRY,reg['known_PS_producer_paths'])))
        try:
            base_model,thermal,profile=L.initialize(reg)
            L.need(thermal['model_sha256']==reg['expected_four_route_AP_sha256'],'Frozen AP differs')
            catalog=L.read(L.pin(reg['catalog_pin']))
            learn=L.load_module('protected48_native_learner',ROOT/'reference/rolling/learner.py')
            settings=learn.Settings(**op['learner_settings'])
            learner=learn.Learner(op['learner_seed'],FAMILY,settings)
            warm=torch.load(L.pin(reg['checkpoints']['20261028']),map_location='cpu',weights_only=False)
            learner.net.load_state_dict(warm['network'])
            initial_network=learn.network_digest(learner.net)
            L.need(initial_network==op['warm_start_network_sha256'],'Warm-start policy differs')
            L.write_new(out/'INITIALIZATION.json',dict(network_sha256=initial_network,
                actor_initialized_from='original selected EP032 network only',optimizer_restarted=True,
                RNG_seed=op['learner_seed'],new_family=FAMILY,new_reward=True,physical_model_unchanged=True))

            def consume(label,case,policy,live=None,cp=None,collect=False,train_episode=None):
                nonlocal count
                L.runtime_guard.process_guard(ENTRY,reg['known_PS_producer_paths']);L.free_guard([ROOT,'D:/'])
                L.need(count<op['new_environment_cap'],'Registered operation budget exhausted')
                used=sum(json.loads(s)['event']=='START' for s in ledger.read_text().splitlines() if s)
                L.need(used==op['expected_child_START_before']+count and used<reg['environment_cap'],'Unregistered/shared consumption changed')
                value=L.validate_input(copy.deepcopy(case['input']),catalog['profiles'])
                if policy==OLD:value['alpha']=.95
                else:value['alpha']=1.
                public,contexts=L.prepare_public(value,catalog['templates'],catalog['profiles'])
                model=L.Model(base_model,contexts)
                L.need(model.metadata['model_digest']==reg['expected_four_route_timing_digest'],'Frozen timing differs')
                identity=L.digest(['PROTECTED48_20261016_V1',label,op_sha])
                L.need(not any(r.get('identity')==identity for r in events),'Already consumed identity')
                start=dict(event='START',identity=identity,start_id=identity,registration_sha256=op_sha,
                    operation_sha256=op_sha,durable_START_consumed=True,label=label,policy=policy,
                    input_sha256=L.digest(value),utc=L.now(),new_environment=1)
                L.append(ledger,start);L.append(out/'receipts.jsonl',start);count+=1
                try:
                    before=None
                    if collect:
                        before=runtime/(label+'.before.pt');live.save_snapshot(before)
                        cp={'path':str(before),'sha256':L.sha(before),'bytes':before.stat().st_size}
                    if policy==EDF:
                        with edf_installed(kernel,L):result,actor=L.policy_result(EDF,public,model,thermal,profile,value,start,reg)
                    elif policy==OLD:
                        result,actor=L.policy_result(OLD,public,model,thermal,profile,value,start,reg)
                    else:
                        rr=copy.deepcopy(reg);rr['checkpoints']['20261028']=cp
                        rr['adapter_contract_sha256']=L.sha(Path(__file__).with_name('protected_policy.py'))
                        original=L.RLPolicy
                        def factory(*args,**kwargs):return ProtectedPolicy(model,public,thermal,profile,live,learn,collect,policy==CONTROL)
                        L.RLPolicy=factory
                        try:result,actor=L.policy_result(OLD,public,model,thermal,profile,value,start,rr)
                        finally:L.RLPolicy=original
                        result['summary'].update(policy=policy,label=policy,
                            RL_status='TRAINED_PROTECTED48' if policy==NEW else 'PROTECTED_ATC_MARGINAL_COST_RULE_WITHOUT_NEURAL_SELECTION',
                            protection_config=CONFIG,protection_decisions=actor.bank_audits,
                            NN_training_in_this_environment=bool(collect))
                        if policy==CONTROL:result['summary']['D_GPU_legal_action_slots']=None
                    audit=L.audit_result(result,None if collect or policy==CONTROL else actor)
                    if collect:
                        replay_checks=0
                        for f in actor.controller.frames:
                            rp=learn.replay_frame(live.net,f)
                            L.need(abs(rp['logprob']-f['old_logp'])<1e-6,'Collected logprob does not replay')
                            L.need(np.allclose(rp['critic'],f['value'],rtol=1e-5,atol=1e-6),'Collected critic does not replay');replay_checks+=1
                        costs,roles,proof=make_costs(result,actor.controller.frames,public,profile)
                        experience=runtime/(label+'.experience.pt')
                        torch.save({'frames':actor.controller.frames,'costs':costs,'role_counts':roles,
                                    'alpha':1.,'proof':proof,'protection':actor.bank_audits},experience)
                        meta=live.add_episode(actor.controller.frames,costs,1.,roles)
                        after=runtime/(label+'.after.pt');live.save_snapshot(after)
                        L.write_new(out/(label+'.learning.json'),dict(meta=meta,reward=proof,
                            replay_frames=replay_checks,before={'path':str(before),'sha256':L.sha(before)},
                            after={'path':str(after),'sha256':L.sha(after)},experience={'path':str(experience),'sha256':L.sha(experience)},
                            before_network=actor.network_sha,after_network=learn.network_digest(live.net),
                            optimizer_steps=live.steps,updates=live.updates))
                    elif actor and policy!=CONTROL:
                        frames=runtime/(label+'.frames.pt');torch.save(actor.controller.frames,frames)
                        result['summary']['saved_frames']={'path':str(frames),'sha256':L.sha(frames)}
                    raw=out/(label+'.raw.json.gz')
                    with gzip.open(raw,'xt',encoding='utf-8') as f:f.write(L.canonical(result))
                    L.write_new(out/(label+'.summary.json'),result['summary'])
                    prep={**start,'event':'PREPARED','raw_sha256':L.sha(raw),'summary_sha256':L.digest(result['summary']),'audit':audit}
                    L.append(ledger,prep);L.append(out/'receipts.jsonl',prep)
                    end={**start,'event':'COMPLETE','raw_sha256':L.sha(raw),'utc':L.now()}
                    L.append(ledger,end);L.append(out/'receipts.jsonl',end)
                    print(label,'COMPLETE',count,'/',op['new_environment_cap'],flush=True)
                    return result['summary']
                except BaseException as e:
                    fail={**start,'event':'FAIL','utc':L.now(),'error':str(e),'automatic_retry':False}
                    L.append(ledger,fail);L.append(out/'receipts.jsonl',fail);raise

            checkpoints={}
            for episode,c in enumerate(op['cases']['train'],1):
                consume('TRAIN_%03d'%episode,c,NEW,learner,collect=True,train_episode=episode)
                if episode in op['checkpoint_episodes']:
                    path=out/('PPO_PROTECTED48_EP%03d.pt'%episode);learner.save_snapshot(path)
                    checkpoints[episode]={'path':str(path),'sha256':L.sha(path),'bytes':path.stat().st_size}
            dev_edf=[consume('DEV_EDF_%02d'%i,c,EDF) for i,c in enumerate(op['cases']['dev'])]
            rankings=[]
            for ep,cp in checkpoints.items():
                frozen=learn.Learner.load_snapshot(cp['path'])
                rows=[consume('DEV_EP%03d_%02d'%(ep,i),c,NEW,frozen,cp) for i,c in enumerate(op['cases']['dev'])]
                rankings.append(dict(episode=ep,checkpoint=cp,score=selection_score(rows,dev_edf)))
            selected=min(rankings,key=lambda r:(r['score'],r['episode']))
            L.write_new(out/'SELECTION_FROZEN.json',dict(rankings=rankings,selected=selected,
                evaluation_outcomes_opened=0,NN_training=64,selection='DEV_ONLY_PREDECLARED_LEXICOGRAPHIC'))
            cp=selected['checkpoint'];frozen=learn.Learner.load_snapshot(cp['path'])
            def case_result(i,c,rows):
                lo=min(q['arrival_s'] for q in c['input']['requests']);hi=min(180,max(q['arrival_s'] for q in c['input']['requests'])+15)
                return dict(index=i,label=c['label'],input=c['input'],common_work_window_s=[lo,hi],
                            rows=rows,metrics=[metrics(r,lo,hi) for r in rows])
            fresh=[];controls=[]
            for i,c in enumerate(op['cases']['fresh_eval']):
                rows=[consume('FRESH_%02d_%s'%(i,p),c,p,frozen if p==NEW else None,cp if p==NEW else None) for p in (EDF,OLD,NEW)]
                fresh.append(case_result(i,c,rows))
                if i<op['mechanism_control_conditions']:
                    control=consume('CONTROL_%02d'%i,c,CONTROL,frozen,cp)
                    controls.append(case_result(i,c,[rows[-1],control]))
            historical=[];saved=L.read(ROOT/'results/EDF_CPU_FIRST_20261016_01/RESULT.json')
            for i,c in enumerate(saved['cases']):
                new=consume('HISTORICAL_%02d'%i,c,NEW,frozen,cp)
                historical.append(case_result(i,c,[*c['rows'],new]))
            aggregates={name:[aggregate(cases,p) for p in policies] for name,cases,policies in (
                ('fresh',fresh,(EDF,OLD,NEW)),('historical',historical,(OLD,EDF,NEW)),('mechanism',controls,(NEW,CONTROL)))}
            targets=[]
            for c in fresh:
                a=next(r for r in c['metrics'] if r['policy']==NEW);b=next(r for r in c['metrics'] if r['policy']==EDF)
                service=a['on_time']>=b['on_time'] and a['response_missing']==0 and a['AVAILABLE_by_window_end']==a['planned']
                targets.append(dict(case_index=c['index'],no_service_harm=service,
                    both_heat_and_total_lower=service and a['total_J_proxy']<b['total_J_proxy']-1e-8 and a['mean_AP_c']<b['mean_AP_c']-1e-6,
                    target_total_10pct_AP_0_5=service and a['total_J_proxy']<=.9*b['total_J_proxy'] and a['mean_AP_c']<=b['mean_AP_c']-.5))
            summary=dict(schema='A24-protected48-training-comparison-v1',operation_sha256=op_sha,
                selected=selected,rankings=rankings,initial_network_sha256=initial_network,
                final_training_network_sha256=learn.network_digest(learner.net),training_episodes=64,
                optimizer_steps=learner.steps,updates=learner.updates,fresh_cases=fresh,historical_cases=historical,
                mechanism_cases=controls,aggregate=aggregates,targets=targets,
                budget=dict(new_START=count,previous_shared_START=306,current_shared_START=306+count,
                            shared_cap=512,remaining=512-306-count,new_global_reservation=0),
                measured_J=None,energy_CI=None,fresh_device_confirmation=False,model_fit=0,
                method='Same frozen physics, same input-derived work window; fresh fixed-model simulation seeds vs posthoc historical cases separated')
            L.need(count==op['new_environment_cap'],'Registered exact count not completed')
            L.write_new(out/'RESULT.json',summary)
            pins(op);L.need(L.sha(op_path)==op_sha,'Operation mutated')
            L.write_new(out/'COMPLETE.json',dict(status='COMPLETE_TRAIN_DEV_FRESH_EVAL_AND_HISTORICAL',utc=L.now(),
                operation_sha256=op_sha,result_sha256=L.sha(out/'RESULT.json'),budget=summary['budget'],
                selected_episode=selected['episode'],physical_model_unchanged=True,measured_J=None))
            print(json.dumps(aggregates,ensure_ascii=False),flush=True)
        except BaseException as e:
            L.write_new(out/'FAILURE.json',dict(utc=L.now(),error=str(e),type=type(e).__name__,automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--operation',required=True);main(a.parse_args().operation)
