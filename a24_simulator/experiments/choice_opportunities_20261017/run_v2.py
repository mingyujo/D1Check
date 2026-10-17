"""New, preregistered coalescing generation; the failed v1 is never rerun."""
from pathlib import Path
import gc,gzip,json,math,os,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
os.environ['A24_LAB_GUARD_ENTRY']=str(Path(__file__).resolve())
import run as V1
from run import L,G,K,registration,restore_old_ledger,public_input,metrics,save_binary,FastThermal
from observer_v2 import CoalescingObserver
from shared_exact import Cost,exclusive

def main():
    opfile=HERE/'OPERATION_V2.json';op=L.read(opfile);opsha=L.sha(opfile)
    for p in [*op['sources'],op['inputs'],op['budget'],op['cost_model']]:L.pin(p)
    G.process_guard(Path(__file__).resolve());G.free_guard([ROOT,'D:/'])
    L.need('--published' in sys.argv,'Publish V2 registration first')
    out=ROOT/op['output_dir'];L.need(not out.exists(),'Consumed V2; no restart')
    restore_old_ledger()
    import msvcrt
    lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0
    try:
        reg=registration(op);base,thermal,profile=L.initialize(reg)
        catalog=L.read(L.pin(reg['catalog_pin']));cost=L.read(L.pin(op['cost_model']))
        design=L.read(L.pin(op['inputs']));budget=L.read(L.pin(op['budget']))
        L.need(budget['parent_consumed']+budget['transferred']+budget['parent_unallocated_after']==28,'Child allocation conservation')
        out.mkdir();L.write_new(out/'START.json',dict(operation_sha256=opsha,utc=L.now(),process=G.process_guard(Path(__file__).resolve())))
        rows=[]
        for case in design['cases']:
            for mode in op['policies']:
                G.process_guard(Path(__file__).resolve());G.free_guard([ROOT,'D:/'])
                L.need(count<12,'V2 cap')
                label=case['id']+'_'+mode
                start=dict(event='START',label=label,identity=L.digest([opsha,label]),start_id=L.digest([opsha,label]),registration_sha256=opsha,durable_START_consumed=True,utc=L.now())
                L.append(out/'receipts.jsonl',start);count+=1;print('START',label,flush=True)
                try:
                    public,contexts=public_input(case,catalog);model=L.Model(base,contexts)
                    actor=CoalescingObserver(model,public,thermal,profile,mode)
                    original=L.thermal_model.predict;fast=FastThermal(L.thermal_model,original,public,thermal)
                    L.thermal_model.predict=fast.predict
                    try:
                        pred=K.simulate_protocol(public,model,'FROZEN_RL_REPLAY',execution_guard=start,
                            scenario_key=case['common_potential_key'],admission_protocol='SERIAL',redispatch_mode='ZERO_EXPLICIT_BASELINE',
                            zero_baseline_id='COMMON_UNIDENTIFIED_CONTROLLER_IDEAL_ZERO',pair_scope='READY_QUEUE',decision_cap=8192,
                            concurrency_mode='DATA_DERIVED_PROGRESS',unidentified_overlap='SERIAL_INDEPENDENT',frozen_policy=actor,
                            frozen_policy_binding=dict(replay_only=True,checkpoint_sha256='NO_NN_'+mode,input_contract_sha256=opsha))
                    finally:L.thermal_model.predict=original
                    save_binary(out/(label+'.prepared_prediction.json.gz'),gzip.compress(L.canonical(pred).encode(),mtime=0))
                    activity=L.generated_activity(public,pred);end=public['observation_end_ns']/1e9
                    times=sorted({0.,35.,case['work_window'][1],end,*map(float,range(math.ceil(end)))})
                    ap=original(thermal,activity,times=times,allow_extrapolation=True)
                    L.write_new(out/(label+'.AP.json'),ap)
                    summary=dict(requests=pred['requests'],gantt=activity['owner_intervals'],AP=dict(t_s=ap['t_s'],ap_c=ap['ap_c']))
                    audit=L.audit_result(dict(prediction=pred,summary={'measured_J':None}),None)
                    if ap['status']=='CONDITIONAL_AP_PREDICTION':m=metrics(summary,pred,case,cost)
                    else:
                        q=pred['requests'];answered=[r for r in q if r['response_ns'] is not None];hi=case['work_window'][1]
                        m={**Cost.observe(exclusive(summary['gantt'],0.,end),*case['work_window'],cost),
                            'planned':48,'responded':len(answered),'response_missing':48-len(answered),
                            'on_time':sum(r['response_ns']<=r['deadline_ns'] for r in answered),
                            'urgent_planned':sum(r['priority']=='U' for r in q),
                            'urgent_on_time':sum(r['priority']=='U' and r['response_ns'] is not None and r['response_ns']<=r['deadline_ns'] for r in q),
                            'incomplete':sum(r['available_ns'] is None for r in q),
                            'AVAILABLE_by_window_end':sum(r['available_ns'] is not None and r['available_ns']/1e9<=hi for r in q),
                            'mean_AP_c':None,'peak_AP_c':None,'duration_s':hi-35,'window_s':case['work_window'],'measured_J':None}
                    o=actor.summary();L.need(o['decision_opportunities']==48,'WAIT excluded from dispatch denominator')
                    raw=out/(label+'.raw.json.gz')
                    save_binary(raw,gzip.compress(L.canonical(dict(prediction=pred,summary=summary,AP=ap,opportunities=actor.opportunities,
                        actor_calls=actor.bank_audits,coalescing_events=actor.coalescing_events)).encode(),mtime=0))
                    row=dict(case=case['id'],pair=case['pair'],arm=case['arm'],policy=mode,n=48,metrics=m,opportunities=o,
                        audit=audit,raw_sha256=L.sha(raw),AP_status=ap['status'],AP_reason=ap.get('reason'),NN_execution=0,
                        EDF_protection_census_is_shadow=mode=='EDF',measured_J=None)
                    L.write_new(out/(label+'.json'),row);rows.append(row)
                    for event in ('PREPARED','COMPLETE'):L.append(out/'receipts.jsonl',{**start,'event':event,'result_sha256':L.sha(out/(label+'.json')),'raw_sha256':L.sha(raw),'utc':L.now()})
                    print('COMPLETE',label,'multi',o['multiple_requests_after'],'twofree',o['two_free_routes'],'wait',o['coalescing_WAIT_calls'],'ontime',m['on_time'],'AP',ap['status'],flush=True)
                    del actor,model,pred,summary;gc.collect()
                except BaseException as exc:
                    L.append(out/'receipts.jsonl',{**start,'event':'FAIL','error':str(exc),'automatic_retry':False});raise
        for p in op['sources']:L.pin(p)
        L.need(count==12,'Exact V2 consumption')
        L.write_new(out/'RESULT.json',dict(schema='A24-choice-coalescing-result-v2',rows=rows,new_START=count,new_COMPLETE=count,new_FAIL=0,
                 NN_training=0,new_fit=0,measured_J=None,operation_sha256=opsha,protection_changed=False,development_only=True))
        L.write_new(out/'COMPLETE.json',dict(utc=L.now(),result_sha256=L.sha(out/'RESULT.json'),new_START=count,new_COMPLETE=count))
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main()
