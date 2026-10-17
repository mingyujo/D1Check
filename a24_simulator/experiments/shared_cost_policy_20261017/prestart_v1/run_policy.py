"""Finite8 policy development runs funded from the remaining original envelope."""
from pathlib import Path
import gc
import gzip
import math
import os
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'experiments/choice_opportunities_20261017'))
from run import L,G,K,registration,restore_old_ledger,public_input,metrics,save_binary,FastThermal
from shared_policy import SharedCostPolicy
os.environ['A24_LAB_GUARD_ENTRY']=str(Path(__file__).resolve())
G.OWN_TOKENS+=('shared_cost_policy_20261017','shared_activation_20261017')


def main():
    opfile=HERE/'OPERATION.json';op=L.read(opfile);opsha=L.sha(opfile)
    for p in [*op['sources'],op['inputs'],op['budget'],op['cost_model']]:L.pin(p)
    G.process_guard(Path(__file__).resolve());G.free_guard([ROOT,'D:/'])
    L.need('--published' in sys.argv,'Publish registration first')
    out=ROOT/op['output_dir'];L.need(not out.exists(),'Consumed generation; no restart')
    budget=L.read(L.pin(op['budget']))
    L.need(budget['old_consumed']+budget['transferred']==256 and budget['transferred']==8,'Exact remaining allocation')
    restore_old_ledger()
    import msvcrt
    lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0
    try:
        base,thermal,profile=L.initialize(registration(op))
        reg=registration(op);catalog=L.read(L.pin(reg['catalog_pin']));oldcost=L.read(L.pin(op['cost_model']))
        design=L.read(L.pin(op['inputs']));rows=[]
        out.mkdir();L.write_new(out/'START.json',dict(operation_sha256=opsha,utc=L.now(),process=G.process_guard(Path(__file__).resolve())))
        for case in design['cases']:
            for mode in op['policies']:
                G.process_guard(Path(__file__).resolve());G.free_guard([ROOT,'D:/'])
                L.need(count<8,'Cap8')
                name=case['id']+'_'+mode
                start=dict(event='START',label=name,identity=L.digest([opsha,name]),start_id=L.digest([opsha,name]),
                    registration_sha256=opsha,durable_START_consumed=True,utc=L.now())
                L.append(out/'receipts.jsonl',start);count+=1;print('START',name,flush=True)
                try:
                    public,contexts=public_input(case,catalog);model=L.Model(base,contexts)
                    actor=SharedCostPolicy(model,public,thermal,profile,mode)
                    original=L.thermal_model.predict;fast=FastThermal(L.thermal_model,original,public,thermal)
                    L.thermal_model.predict=fast.predict
                    try:
                        pred=K.simulate_protocol(public,model,'FROZEN_RL_REPLAY',execution_guard=start,
                            scenario_key=case['common_potential_key'],admission_protocol='SERIAL',redispatch_mode='ZERO_EXPLICIT_BASELINE',
                            zero_baseline_id='COMMON_UNIDENTIFIED_CONTROLLER_IDEAL_ZERO',pair_scope='READY_QUEUE',decision_cap=8192,
                            concurrency_mode='DATA_DERIVED_PROGRESS',unidentified_overlap='SERIAL_INDEPENDENT',frozen_policy=actor,
                            frozen_policy_binding=dict(replay_only=True,checkpoint_sha256='NO_NN_'+mode,input_contract_sha256=opsha))
                    finally:L.thermal_model.predict=original
                    save_binary(out/(name+'.prepared_prediction.json.gz'),gzip.compress(L.canonical(pred).encode(),mtime=0))
                    activity=L.generated_activity(public,pred);end=public['observation_end_ns']/1e9
                    times=sorted({0.,35.,case['work_window'][1],end,*map(float,range(math.ceil(end)))})
                    ap=original(thermal,activity,times=times,allow_extrapolation=True)
                    L.write_new(out/(name+'.AP.json'),ap)
                    summary=dict(requests=pred['requests'],gantt=activity['owner_intervals'],AP=dict(t_s=ap['t_s'],ap_c=ap['ap_c']))
                    audit=L.audit_result(dict(prediction=pred,summary={'measured_J':None}),None)
                    if ap['status']=='CONDITIONAL_AP_PREDICTION':oldmetrics=metrics(summary,pred,case,oldcost)
                    else:
                        q=pred['requests'];answered=[r for r in q if r['response_ns'] is not None]
                        oldmetrics=dict(planned=48,responded=len(answered),response_missing=48-len(answered),
                            on_time=sum(r['response_ns']<=r['deadline_ns'] for r in answered),
                            urgent_on_time=sum(r['priority']=='U' and r['response_ns'] is not None and r['response_ns']<=r['deadline_ns'] for r in q),
                            incomplete=sum(r['available_ns'] is None for r in q),mean_AP_c=None,measured_J=None)
                    cost=actor.new_cost.observe(summary['gantt'],*case['work_window'])
                    cost.update(actor.new_cost.episode(summary['gantt']))
                    o=actor.summary();L.need(o['decision_opportunities']==48,'Dispatch-only denominator')
                    raw=out/(name+'.raw.json.gz')
                    save_binary(raw,gzip.compress(L.canonical(dict(prediction=pred,summary=summary,AP=ap,actor_calls=actor.bank_audits,
                        opportunities=actor.opportunities,coalescing_events=actor.coalescing_events,marginal_audits=actor.marginal_audits)).encode(),mtime=0))
                    row=dict(case=case['id'],arm=case['arm'],packet=case['packet'],policy=mode,n=48,metrics=oldmetrics,
                        new_cost=cost,opportunities=o,audit=audit,raw_sha256=L.sha(raw),AP_status=ap['status'],AP_reason=ap.get('reason'),
                        NN_execution=0,measured_J=None)
                    L.write_new(out/(name+'.json'),row);rows.append(row)
                    for event in ('PREPARED','COMPLETE'):
                        L.append(out/'receipts.jsonl',{**start,'event':event,'result_sha256':L.sha(out/(name+'.json')),'raw_sha256':L.sha(raw),'utc':L.now()})
                    print('COMPLETE',name,'ontime',oldmetrics['on_time'],'cost',cost['total_J_proxy'],'AP',ap['status'],flush=True)
                    del actor,model,pred,summary;gc.collect()
                except BaseException as error:
                    L.append(out/'receipts.jsonl',{**start,'event':'FAIL','error':str(error),'automatic_retry':False});raise
        for p in op['sources']:L.pin(p)
        L.need(count==8,'Exactly8 consumed')
        L.write_new(out/'RESULT.json',dict(schema='A24-shared-cost-policy-result-v1',rows=rows,new_START=count,new_COMPLETE=count,new_FAIL=0,
            operation_sha256=opsha,new_fit=0,NN_training=0,physical_energy_verified=False,development_only=True,measured_J=None))
        L.write_new(out/'COMPLETE.json',dict(utc=L.now(),result_sha256=L.sha(out/'RESULT.json'),new_START=count,new_COMPLETE=count))
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
