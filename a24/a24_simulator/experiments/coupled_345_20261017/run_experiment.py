"""Registered finite closed-loop/learning experiment; no retry or old-op replay."""
from pathlib import Path
import copy
import dataclasses
import gc
import gzip
import io
import json
import os
import sys
import time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ENTRY=Path(__file__).resolve()
from bootstrap import L,G,registration,restore_old_ledger,public_input,save_binary,Nominal
sys.path.insert(0,str(HERE))
from dynamics import Config,Physics,NS
from controller import Controller
from engine import run as execute,metrics
from rewards import labels
from nn_train import Learner,digest
import torch
os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)
G.OWN_TOKENS+=('coupled_345_20261017','shared_cost_policy_20261017','shared_activation_20261017')


def save_pt(path,value):
    stream=io.BytesIO();torch.save(value,stream);save_binary(path,gzip.compress(stream.getvalue(),mtime=0))


def load_pt(path):return torch.load(io.BytesIO(gzip.decompress(path.read_bytes())),map_location='cpu',weights_only=False)


def raw_edf(state):
    free=[r for r in ('CPU','GPU') if r not in {o['route'] for o in state['owners']}]
    if not free or not state['queue']:return dict(kind='RESOURCE_WAIT')
    q=min(state['queue'],key=lambda q:(q['deadline_ns'],q['scheduled_arrival_ns'],q['ordinal'],q['request_id']))
    return dict(kind='DISPATCH',request_id=q['request_id'],route=free[0])


def main():
    op_path=HERE/'OPERATION.json';op=L.read(op_path);opsha=L.sha(op_path)
    L.need('--published' in sys.argv,'Publish source/inputs/new finite reservation first')
    for p in [*op['sources'],*op['input_pins']]:L.pin(p)
    G.process_guard(ENTRY);G.free_guard([ROOT,'D:/'])
    out=ROOT/op['output_dir'];L.need(not out.exists(),'Consumed operation; no automatic restart')
    restore_old_ledger()
    import msvcrt
    lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0;allrows=[];started=time.monotonic()
    try:
        out.mkdir();L.write_new(out/'START.json',dict(utc=L.now(),operation_sha256=opsha,process=G.process_guard(ENTRY)))
        try:
            base,_,_=L.initialize(registration(op));catalog=L.read(L.pin(registration(op)['catalog_pin']))
            L.need(base.feature_mode=='exact_public','Nominal cache requires frozen exact-public timing strata')
            cost=L.read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')
            design=L.read(L.pin(op['inputs']));config=Config(**op['physics']);selection_sha=None
            public_check,contexts_check=public_input(design['p0'][0],catalog)
            nominal_check=Nominal(L.Model(base,contexts_check),public_check)
            nominal_cells=[]
            for task in ('C','D'):
                q=next(q for q in public_check['requests'] if q['task']==task)
                for route in ('CPU','GPU'):
                    v=nominal_check.vector(q,route,dict(queue_count=0,initial_ap_c=26.))
                    L.need(len(v)==5 and min(v)>=0 and sum(v)>0,'Public nominal five-phase estimate')
                    nominal_cells.append(dict(task=task,route=route,vector_s=v))
            L.write_new(out/'NOMINAL_PREFLIGHT.json',dict(status='PASS',cells=nominal_cells,new_environment_START=0))

            def start(case,name,mode,kind):
                nonlocal count
                G.process_guard(ENTRY)
                if count%8==0:G.free_guard([ROOT,'D:/'])
                L.need(count<op['environment_cap'] and time.monotonic()-started<op['wall_clock_limit_s'],'Finite budget/time cap')
                receipt=dict(event='START',label=name,identity=L.digest([opsha,name]),start_id=L.digest([opsha,name]),
                    registration_sha256=opsha,durable_START_consumed=True,kind=kind,policy=mode,case=case['id'],
                    selection_sha256=selection_sha,utc=L.now())
                L.append(out/'receipts.jsonl',receipt);count+=1;print('START',count,name,flush=True)
                return receipt

            def simulate(case,mode,name,kind,learner=None,collect=False,strength=None,tick=None):
                receipt=start(case,name,mode,kind)
                try:
                    public,contexts=public_input(case,catalog);public['initial_ap_c']=case['temperature_c']
                    model=L.Model(base,contexts)
                    conf=dataclasses.replace(config,**({} if strength is None else dict(strength=strength)),**({} if tick is None else dict(tick_s=tick)))
                    physics=Physics(cost,conf);nominal=Nominal(model,public)
                    actor=Controller(nominal,physics,case,mode,learner,collect)
                    action_rng_before=learner.action_rng.get_state().clone() if learner else None
                    result=execute(public,model,actor,physics,case['common_potential_key'],receipt)
                    prepared=out/(name+'.prepared.json.gz');save_binary(prepared,gzip.compress(L.canonical(result).encode(),mtime=0))
                    m=metrics(result,case,physics);reward=None;reward_audit=None
                    if learner:
                        reward,reward_audit=labels(result,actor.frames,case,physics,m)
                        save_pt(out/(name+'.frames.pt.gz'),dict(frames=actor.frames,costs=reward,
                            action_rng_before=action_rng_before,action_rng_after=learner.action_rng.get_state().clone(),reward_audit=reward_audit))
                    raw=out/(name+'.raw.json.gz')
                    save_binary(raw,gzip.compress(L.canonical(dict(result=result,calls=actor.calls)).encode(),mtime=0))
                    row=dict(label=name,case=case['id'],kind=kind,policy=mode,condition=case['condition'],n=case['n'],
                        metrics=m,raw_sha256=L.sha(raw),prepared_sha256=L.sha(prepared),
                        network_sha256=digest(learner.net) if learner else None,reward_audit=reward_audit,
                        strength=conf.strength,tick_s=conf.tick_s,measured_J=None)
                    L.write_new(out/(name+'.json'),row);allrows.append(row)
                    for event in ('PREPARED','COMPLETE'):L.append(out/'receipts.jsonl',{**receipt,'event':event,'raw_sha256':L.sha(raw),'result_sha256':L.sha(out/(name+'.json')),'utc':L.now()})
                    print('COMPLETE',name,'on',m['on_time'],'/',m['planned'],'J*',round(m['total_J_proxy'],5),'AP',round(m['mean_AP_c'],4),flush=True)
                    frames=actor.frames
                    del model,actor,result,nominal;gc.collect()
                    return row,frames,reward
                except BaseException as exc:
                    L.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','error':str(exc),'automatic_retry':False,'utc':L.now()});raise

            # P0 reproduces two new recipes in the old independent-progress
            # event engine and in the new engine with feedback strength0.
            oldkernel=L.load_module('coupled345_old_reference',ROOT/'experiments/long_scale_20261017/kernel_long.py')
            p0=[]
            for case in design['p0']:
                pair=[]
                for which in ('OLD','NEW'):
                    name=case['id']+'_'+which;receipt=start(case,name,'RAW_EDF','P0')
                    try:
                        public,contexts=public_input(case,catalog);public['initial_ap_c']=case['temperature_c'];model=L.Model(base,contexts)
                        if which=='OLD':
                            result=oldkernel.simulate_protocol(public,model,'FROZEN_RL_REPLAY',execution_guard=receipt,
                                scenario_key=case['common_potential_key'],admission_protocol='SERIAL',redispatch_mode='ZERO_EXPLICIT_BASELINE',
                                zero_baseline_id='COMMON_UNIDENTIFIED_CONTROLLER_IDEAL_ZERO',pair_scope='READY_QUEUE',
                                concurrency_mode='SERIAL_INDEPENDENT',unidentified_overlap='SERIAL_INDEPENDENT',frozen_policy=raw_edf,
                                frozen_policy_binding=dict(replay_only=True,checkpoint_sha256='NO_NN_P0',input_contract_sha256=opsha))
                        else:result=execute(public,model,raw_edf,Physics(cost,dataclasses.replace(config,strength=0)),case['common_potential_key'],receipt)
                        path=out/(name+'.json.gz');save_binary(path,gzip.compress(L.canonical(result).encode(),mtime=0));pair.append(result)
                        L.append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','raw_sha256':L.sha(path),'utc':L.now()})
                    except BaseException as exc:
                        L.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','error':str(exc),'automatic_retry':False});raise
                worst=0
                for a,b in zip(pair[0]['requests'],pair[1]['requests']):
                    L.need(a['request_id']==b['request_id'] and a['route']==b['route'],'P0 action mismatch')
                    for key in ('queue_entry_ns','dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','available_ns','response_ns'):
                        worst=max(worst,abs(a[key]-b[key]))
                L.need(worst<=10,'P0 clocks differ beyond event rounding')
                p0.append(dict(case=case['id'],max_clock_difference_ns=worst))
            L.write_new(out/'P0.json',dict(status='PASS',pairs=p0,new_START=4,scope='same serial latent work and cold independent progress, not physical accuracy'))

            checkpoints=[]
            for seed in op['learner_seeds']:
                learner=Learner(seed);save_pt(out/('SEED_%d_EP000.pt.gz'%seed),learner.snapshot())
                for episode,case in enumerate(design['train'],1):
                    name='TRAIN_S%d_EP%03d'%(seed,episode)
                    row,frames,reward=simulate(case,'RL',name,'TRAIN',learner,True)
                    learner.add(frames,reward)
                    if episode%16==0 or episode==2:
                        path=out/('SEED_%d_EP%03d.pt.gz'%(seed,episode));save_pt(path,learner.snapshot())
                        if episode in op['checkpoint_episodes']:checkpoints.append(dict(seed=seed,episode=episode,path=path.name,sha256=L.sha(path)))
                    if episode%2==0:L.write_new(out/('UPDATE_S%d_%03d.json'%(seed,learner.updates)),learner.logs[-1])
                L.write_new(out/('TRAINING_S%d.json'%seed),dict(episodes=learner.episodes,updates=learner.updates,Adam_steps=learner.steps,logs=learner.logs))
                del learner;gc.collect()
            dev_baseline=[simulate(c,'EDF','DEV_EDF_%02d'%i,'DEV')[0] for i,c in enumerate(design['dev'])]
            rankings=[]
            for cp in checkpoints:
                learner=Learner(cp['seed']);learner.restore(load_pt(out/cp['path']))
                rows=[simulate(c,'RL','DEV_S%d_EP%03d_%02d'%(cp['seed'],cp['episode'],i),'DEV',learner)[0] for i,c in enumerate(design['dev'])]
                missing=sum(r['metrics']['response_missing'] for r in rows)
                harm=sum(max(0,b['metrics']['on_time']-r['metrics']['on_time']) for r,b in zip(rows,dev_baseline))
                score=[missing,harm,sum(r['metrics']['objective'] for r in rows)/len(rows)]
                rankings.append(dict(**cp,score=score,qualification=missing==0 and harm==0))
            selected_by_seed=[min((r for r in rankings if r['seed']==seed),key=lambda r:(r['score'],r['episode'])) for seed in op['learner_seeds']]
            selected=min(selected_by_seed,key=lambda r:(r['score'],r['seed'],r['episode']))
            L.write_new(out/'SELECTION_FROZEN.json',dict(selected=selected,by_seed=selected_by_seed,rankings=rankings,selection='DEV_ONLY',fresh_outcomes_opened=0))
            selection_sha=L.sha(out/'SELECTION_FROZEN.json')
            models={}
            for cp in selected_by_seed:
                models[cp['seed']]=Learner(cp['seed']);models[cp['seed']].restore(load_pt(out/cp['path']))
            for i,case in enumerate(design['fresh']):
                for mode in ('EDF','FIFO','RR','ATC','EXACT'):simulate(case,mode,'FRESH_%02d_%s'%(i,mode),'FRESH')
                for seed in op['learner_seeds']:simulate(case,'RL','FRESH_%02d_RL_S%d'%(i,seed),'FRESH',models[seed])
            best=models[selected['seed']]
            for i,case in enumerate(design['fresh']):
                for mode in ('EDF','EXACT','RL'):simulate(case,mode,'OFF_%02d_%s'%(i,mode),'FEEDBACK_OFF',best if mode=='RL' else None,strength=0.)
                simulate(case,'APPROX','APPROX_%02d'%i,'COST_MISMATCH')
                for strength in (.5,1.5):simulate(case,'RL','STRENGTH_%s_%02d'%(str(strength).replace('.',''),i),'STRENGTH',best,strength=strength)
            for i in (0,9):
                for mode in ('EXACT','RL'):simulate(design['fresh'][i],mode,'DT_%02d_%s'%(i,mode),'TIMESTEP',best if mode=='RL' else None,tick=.05)
            L.need(count==op['planned_START'],'Exact registered count')
            for p in [*op['sources'],*op['input_pins']]:L.pin(p)
            L.write_new(out/'RESULT.json',dict(status='COMPLETED_RESEARCH_HYPOTHESIS',rows=allrows,selected=selected,selected_by_seed=selected_by_seed,
                new_START=count,new_COMPLETE=count,new_FAIL=0,source_operation_sha256=opsha,physical_energy_accuracy_verified=False,
                new_physical_fit=0,new_device_measurements=0,measured_J=None))
            L.write_new(out/'COMPLETE.json',dict(utc=L.now(),result_sha256=L.sha(out/'RESULT.json'),new_START=count,new_COMPLETE=count,
                elapsed_s=time.monotonic()-started))
        except BaseException as exc:
            L.write_new(out/'FAILURE.json',dict(utc=L.now(),error=str(exc),new_START=count,automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
