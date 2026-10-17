"""Finite offline headroom diagnosis; original results and physics are read-only."""
from pathlib import Path
import copy
import dataclasses
import gc
import gzip
import hashlib
import json
import math
import os
import subprocess
import sys
import time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];COUPLED=ROOT/'experiments/coupled_345_20261017'
sys.path.insert(0,str(COUPLED))
from bootstrap import L,G,registration,public_input,save_binary,Nominal
from dynamics import Physics,Config
from controller import Controller
from engine import run as execute,metrics
sys.path.insert(0,str(HERE))
from math_bounds import coefficients,work_energy,passive_mean,relaxation,observed_vector,feasibility,solve
from actors import TruthNominal,EnergyRouteActor,ListActor,list_plans
import numpy as np
import scipy
import torch
torch.set_num_threads(1)
G.OWN_TOKENS+=('savings_limit_20261017','coupled_345_20261017','shared_cost_policy_20261017')
os.environ['A24_LAB_GUARD_ENTRY']=str(Path(__file__).resolve())


def read(p):
    p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)


def saved(path,value):save_binary(path,gzip.compress(L.canonical(value).encode('utf-8'),mtime=0))


def extract_bank(public,model,key):
    jobs=[]
    for q in public['requests']:
        context,_=model.request_context(public,q);potential=[key,q['ordinal'],q['request_id']]
        admission=model.admission(context,q['task'],potential,protocol='SERIAL')
        entry=q['scheduled_arrival_ns']+admission['scheduled_to_actual_ns']+admission['actual_to_queue_ns']
        job={k:q[k] for k in ('request_id','ordinal','task','priority','scheduled_arrival_ns','deadline_ns')}
        job.update(queue_entry_ns=entry,admission=admission,routes={})
        state=dict(now_ns=entry,queue=[{**q,'queue_entry_ns':entry}],owners=[],initial_ap_c=public['initial_ap_c'])
        for route in ('CPU','GPU'):
            action=dict(request_id=q['request_id'],task=q['task'],route=route,context=L.context_for_route(context,q['task'],route))
            job['routes'][route]=model.draw_latent_serial(action,state,potential)
        jobs.append(job)
    return jobs


def eligible(m,ref):return m['response_missing']==m['incomplete']==0 and m['on_time']>=ref['on_time'] and m['urgent_on_time']>=ref['urgent_on_time']


def main():
    op=read(HERE/'OPERATION.json');opsha=L.sha(HERE/'OPERATION.json');out=ROOT/op['output_dir'];parent=ROOT/op['parent_output']
    L.need('--published' in sys.argv,'Publish this separate bound/search registration first')
    for pin in [*op['sources'],*op['input_pins']]:L.pin(pin)
    L.need(not out.exists(),'Consumed diagnosis cannot be restarted')
    guard=G.process_guard(Path(__file__).resolve());volumes=G.free_guard([ROOT,'D:/'])
    import msvcrt
    lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    started=time.monotonic();count=0;rows=[]
    try:
        out.mkdir();L.write_new(out/'START.json',dict(utc=L.now(),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            uncommitted_changes=bool(subprocess.check_output(['git','status','--porcelain'])),command=sys.argv,
            operation_sha256=opsha,guard=guard,volumes=volumes))
        try:
            base,_,_=L.initialize(registration(op));L.need(base.feature_mode=='exact_public','State-independent potential bank requires exact_public')
            catalog=read(L.pin(registration(op)['catalog_pin']));cost=read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')
            physics=Physics(cost,Config(**op['physics']));design=read(op['inputs']['path']);reference_result=read(parent/'RESULT.json')
            cases=design['fresh'];references={r['case']:r for r in reference_result['rows'] if r['kind']=='FRESH' and r['policy']=='EDF'}
            publics={};models={};banks={};all_bounds=[];binding_checks=0;constraint_checks=0
            for case in cases:
                public,contexts=public_input(case,catalog);public['initial_ap_c']=case['temperature_c'];model=L.Model(base,contexts)
                jobs=extract_bank(public,model,case['common_potential_key']);publics[case['id']]=public;models[case['id']]=model;banks[case['id']]=jobs
                for row in (r for r in reference_result['rows'] if r['kind']=='FRESH' and r['case']==case['id']):
                    raw=read(parent/(row['label']+'.raw.json.gz'));L.need(L.sha(parent/(row['label']+'.raw.json.gz'))==row['raw_sha256'],'Saved reference SHA')
                    observed={q['request_id']:q for q in raw['result']['requests']}
                    for job in jobs:
                        q=observed[job['request_id']];v=job['routes'][q['route']]
                        L.need(q['queue_entry_ns']==job['queue_entry_ns'] and q['timing']['stages_ns']==v['stages_ns'] and q['timing']['sample_id']==v['sample_id'],'Exact original potential binding')
                        binding_checks+=1
                saved(out/(case['id']+'.BANK.json.gz'),dict(case=case,jobs=jobs,feature_mode='exact_public',future_truth_offline_only=True))
                coef=coefficients(physics,case['temperature_c'],op['temperature_interval_step_c']);ref=references[case['id']]['metrics']
                simple=sum(min(work_energy(j,r,coef) for r in ('CPU','GPU')) for j in jobs)
                free=sum(min(work_energy(j,r,coef,free=True) for r in ('CPU','GPU')) for j in jobs)
                problem=relaxation(jobs,case,ref,physics,coef);observed_heat_floor=passive_mean(case,physics)
                for row in (r for r in reference_result['rows'] if r['kind']=='FRESH' and r['case']==case['id']):
                    result=read(parent/(row['label']+'.raw.json.gz'))['result'];v=observed_vector(jobs,result['requests'],case['drain_stop_s'])
                    include=eligible(row['metrics'],ref);error=feasibility(problem,v,include_counts=include)
                    L.need(error<=2e-7,'Necessary interval constraints exclude a saved schedule: '+str(error));constraint_checks+=problem['rows']
                    L.need(float(problem['energy']@v)<=row['metrics']['increment_J_proxy']+2e-7,'Work-energy bound exceeds observed energy')
                    L.need(observed_heat_floor+float(problem['heat']@v)<=row['metrics']['mean_AP_c']+2e-7,'RC deadline-prefix bound exceeds observed heat')
                    L.need(max(t['state']['temperature_c'] for t in result['trace'])<=coef['temperature_upper']+1e-8,'Universal temperature upper bound')
                energy=solve(problem,'energy',op['MILP_seconds_per_solve']);heat=solve(problem,'heat',op['MILP_seconds_per_solve'])
                work_lower=max(simple-1e-6,energy['conservative_lower_bound']);base_energy=physics.c.baseline*(case['drain_stop_s']-35)
                total_lower=base_energy+work_lower;heat_lower=observed_heat_floor+heat['conservative_lower_bound']
                L.need(total_lower<=ref['total_J_proxy']+1e-6 and heat_lower<=ref['mean_AP_c']+1e-6,'Certified lower bound exceeds feasible EDF')
                result=dict(case=case['id'],n=case['n'],reference=ref,coefficients=coef,unlinked_work_lower=free,
                    independent_thermal_linked_work_lower=simple,energy_MILP=energy,heat_MILP=heat,
                    baseline=base_energy,total_energy_lower=total_lower,mean_temperature_lower=heat_lower,
                    maximum_total_saving_percent=100*(1-total_lower/ref['total_J_proxy']),maximum_AP_reduction_c=ref['mean_AP_c']-heat_lower,
                    constraint_sha256=problem['fingerprint'],constraint_rows=problem['rows'],variables=problem['variables'],
                    relaxation='full future work; independent optimal thermal states; perfect half-shared cost; necessary-only interval capacity; EDF count SLA')
                L.write_new(out/(case['id']+'.BOUND.json'),result);all_bounds.append(result)
                print('BOUND',case['id'],'saving at most',round(result['maximum_total_saving_percent'],5),'percent; AP at most',round(result['maximum_AP_reduction_c'],5),flush=True)
            L.write_new(out/'BOUNDS.json',dict(cases=all_bounds,potential_bindings_checked=binding_checks,necessary_constraints_checked=constraint_checks,
                original_sources_unchanged=True,new_environment_START=0,restored_frozen_timing_bank=1,new_physical_fit=0,
                versions=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,torch=torch.__version__)))

            def native(case,public,model,actor,name,kind,extra=None):
                nonlocal count
                L.need(count<op['environment_cap'] and time.monotonic()-started<op['wall_clock_limit_s'],'Registered finite cap')
                if count%8==0:G.process_guard(Path(__file__).resolve());G.free_guard([ROOT,'D:/'])
                receipt=dict(event='START',label=name,kind=kind,case=case['id'],identity=L.digest([opsha,name]),start_id=L.digest([opsha,name]),
                    durable_START_consumed=True,operation_sha256=opsha,utc=L.now())
                L.append(out/'receipts.jsonl',receipt);count+=1;print('START',count,name,flush=True)
                try:
                    result=execute(public,model,actor,physics,case['common_potential_key'],receipt);m=metrics(result,case,physics)
                    raw=out/(name+'.raw.json.gz');saved(raw,dict(result=result,offline_information='both latent route vectors; no online-performance claim',
                        actor_calls=getattr(actor,'calls',None),extra=extra))
                    row=dict(label=name,case=case['id'],kind=kind,metrics=m,raw_sha256=L.sha(raw),extra=extra,
                        list_plan_eligible=getattr(actor,'feasible',True),list_violations=getattr(actor,'violations',None))
                    L.write_new(out/(name+'.json'),row);rows.append(row)
                    L.append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','raw_sha256':L.sha(raw),'result_sha256':L.sha(out/(name+'.json')),'utc':L.now()})
                    return row,result
                except BaseException as exc:
                    L.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','error':str(exc),'automatic_retry':False,'utc':L.now()});raise

            p0=[]
            for i in op['P0_indices']:
                case=cases[i];public=publics[case['id']];model=models[case['id']]
                row,result=native(case,public,model,Controller(Nominal(model,public),physics,case,'EDF'),'P0_'+case['id'],'P0')
                old=read(parent/(references[case['id']]['label']+'.raw.json.gz'))['result'];difference=0
                for q,o in zip(result['requests'],old['requests']):
                    for k in ('dispatch_ns','response_ns','available_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns'):
                        L.need((q.get(k) is None)==(o.get(k) is None),'P0 missing mismatch')
                        if q.get(k) is not None:difference=max(difference,abs(q[k]-o[k]))
                L.need(difference==0,'Original EDF replay differs');p0.append(dict(case=case['id'],max_clock_difference_ns=difference))
            L.write_new(out/'P0.json',dict(status='PASS',pairs=p0,new_START=len(p0)))
            for case in cases:
                jobs=banks[case['id']];public=publics[case['id']];model=models[case['id']];truth=TruthNominal(jobs)
                coef=next(x['coefficients'] for x in all_bounds if x['case']==case['id'])
                actors=[('TRUTH_EXACT',Controller(truth,physics,case,'EXACT')),('TRUTH_ATC',Controller(truth,physics,case,'ATC')),
                        ('ENERGY_ROUTE',EnergyRouteActor(jobs,truth,physics,coef))]
                for mode,actor in actors:native(case,public,model,actor,case['id']+'_'+mode,'FULL_WITNESS',dict(mode=mode,global_optimality_claim=False))
                gc.collect()
            for i in op['micro_indices']:
                original=cases[i];alljobs=banks[original['id']]
                ids=[j['request_id'] for task in ('C','D') for j in [x for x in alljobs if x['task']==task][:2]]
                L.need(len(ids)==4 and len(set(ids))==4,'Preselected mixed4 subset')
                public=copy.deepcopy(publics[original['id']]);public['requests']=[q for q in public['requests'] if q['request_id'] in ids]
                case=copy.deepcopy(original);case.update(id='MICRO_'+original['id'],n=4)
                case['input']['requests']=[q for q in case['input']['requests'] if 'user-'+str(q['ordinal']).zfill(5) in ids]
                model=models[original['id']];nominal=Nominal(model,public)
                ref,_=native(case,public,model,Controller(nominal,physics,case,'EDF'),case['id']+'_EDF','MICRO_REFERENCE',dict(selected_ids=ids))
                plans=list(list_plans(ids));L.need(len(plans)==120,'All120 lists required')
                for j,plan in enumerate(plans):
                    actor=ListActor(plan,nominal,physics)
                    native(case,public,model,actor,case['id']+'_LIST_'+str(j).zfill(3),'MICRO_LIST',dict(plan=plan,selected_ids=ids,
                        class_scope='all lane assignments and per-lane lists; specified earliest dispatch/50ms legal-wait implementation; not all continuous schedules'))
                    if j%30==29:print('MICRO_PROGRESS',case['id'],j+1,'/120',flush=True)
            L.need(count==op['planned_START']==280,'Exact registered execution count')
            for p in [*op['sources'],*op['input_pins']]:L.pin(p)
            L.write_new(out/'RESULT.json',dict(status='COMPLETED_OFFLINE_HEADROOM_DIAGNOSIS',rows=rows,bound_cases=all_bounds,
                new_START=count,new_COMPLETE=count,new_FAIL=0,operation_sha256=opsha,elapsed_s=time.monotonic()-started,
                new_physical_fit=0,new_training=0,measured_J=None,physical_accuracy_verified=False))
            L.write_new(out/'COMPLETE.json',dict(utc=L.now(),new_START=count,new_COMPLETE=count,new_FAIL=0,
                result_sha256=L.sha(out/'RESULT.json'),elapsed_s=time.monotonic()-started))
        except BaseException as exc:
            L.write_new(out/'FAILURE.json',dict(utc=L.now(),error=str(exc),new_START=count,automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
