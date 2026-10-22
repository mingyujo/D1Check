"""Registered input-opportunity development. Frozen physics/protection; no NN."""
from pathlib import Path
import copy,gc,gzip,json,math,os,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
os.environ['A24_LAB_GUARD_ENTRY']=str(Path(__file__).resolve())
sys.path[:0]=[str(HERE),str(ROOT/'src'),str(ROOT/'experiments/rl_cost_20261017'),
 str(ROOT/'experiments/long_scale_20261017'),str(ROOT/'experiments/rules_no_rl_20261017'),
 str(ROOT/'experiments/edf_cpu_first_20261016'),str(ROOT/'experiments/competition_cost_20261017')]
import lab_backend as L
from shared_exact import public_input,metrics,save_binary
from observer import Observer
from fast_thermal import FastThermal
K=L.load_module('choice_frozen_kernel',ROOT/'experiments/long_scale_20261017/kernel_long.py')
G=L.runtime_guard;G.OWN_TOKENS+=('choice_opportunities_20261017','rl_cost_20261017','s26-multiresource-','s26-state-aware-atc-')

def registration(op):
    r=L.read(L.pin(op['registration']));prefix=r['package_root_at_publication'].replace('\\','/')
    def move(x):
        if isinstance(x,dict):return {k:move(v) for k,v in x.items()}
        if isinstance(x,list):return [move(v) for v in x]
        if isinstance(x,str) and x.replace('\\','/').startswith(prefix+'/'):return str(ROOT/x.replace('\\','/')[len(prefix)+1:])
        return x
    return move(r)

def restore_old_ledger():
    # Same exact forward-only restoration, with the canonical own/global worker
    # guard instead of excluding an unrelated Python web server on this host.
    folder=ROOT/'results/COMPETITION_WITNESS_AUDIT_20261017_01'
    source=folder/'SAVED_SHARED_RECEIPTS.jsonl';proof=L.read(folder/'AUDIT.json')
    L.need(L.sha(source)==proof['portable_receipts_sha256'],'Historical ledger SHA')
    target=ROOT/'runtime/receipts.jsonl';b=source.read_bytes();old=target.read_bytes() if target.exists() else b''
    L.need(b.startswith(old) and (not old or old.endswith(b'\n')),'Newer/divergent ledger preserved')
    target.parent.mkdir(exist_ok=True)
    if old!=b:
        with target.open('ab') as f:f.write(b[len(old):]);f.flush();os.fsync(f.fileno())
    L.need(L.sha(target)==L.sha(source),'Exact forward-only old ledger restoration')

def main():
    opfile=HERE/'OPERATION.json';op=L.read(opfile);opsha=L.sha(opfile)
    for p in [*op['sources'],op['inputs'],op['budget'],op['cost_model']]:L.pin(p)
    G.process_guard(Path(__file__).resolve());G.free_guard([ROOT,'D:/'])
    reg=registration(op)
    if '--preflight' in sys.argv:
        L.initialize(reg)
        print('PREFLIGHT_PASS: frozen timing/AP digest and all runtime pins, no environment',flush=True);return
    L.need('--published' in sys.argv,'Publish reservation/source before execution')
    out=ROOT/op['output_dir'];L.need(not out.exists(),'Consumed operation; no automatic retry')
    restore_old_ledger()
    import msvcrt
    lockpath=ROOT/'runtime/worker.lock'
    if not lockpath.exists():lockpath.write_bytes(b'0')
    lock=lockpath.open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0
    try:
        base,thermal,profile=L.initialize(reg);catalog=L.read(L.pin(reg['catalog_pin']))
        cost=L.read(L.pin(op['cost_model']));design=L.read(L.pin(op['inputs']));budget=L.read(L.pin(op['budget']))
        L.need(budget['old_consumed']+budget['transferred']+budget['old_unused_after']==256,'Allocation conservation')
        L.need(budget['transferred']==op['environment_cap'] and budget['global_reservation_increment']==0,'No added global reservation')
        out.mkdir();L.write_new(out/'START.json',dict(operation_sha256=opsha,utc=L.now(),process=G.process_guard(Path(__file__).resolve())))
        results=[]
        for case in design['cases']:
            for mode in op['policies']:
                G.process_guard(Path(__file__).resolve());G.free_guard([ROOT,'D:/'])
                L.need(count<op['environment_cap'],'Transferred allocation cap')
                label=case['id']+'_'+mode;start=dict(event='START',label=label,identity=L.digest([opsha,label]),
                    start_id=L.digest([opsha,label]),registration_sha256=opsha,durable_START_consumed=True,utc=L.now())
                L.append(out/'receipts.jsonl',start);count+=1;print('START',label,flush=True)
                try:
                    public,contexts=public_input(case,catalog);model=L.Model(base,contexts)
                    actor=Observer(model,public,thermal,profile,mode)
                    original=L.thermal_model.predict
                    fast=FastThermal(L.thermal_model,original,public,thermal);L.thermal_model.predict=fast.predict
                    try:
                        pred=K.simulate_protocol(public,model,'FROZEN_RL_REPLAY',execution_guard=start,
                            scenario_key=case['common_potential_key'],admission_protocol='SERIAL',
                            redispatch_mode='ZERO_EXPLICIT_BASELINE',zero_baseline_id='COMMON_UNIDENTIFIED_CONTROLLER_IDEAL_ZERO',
                            pair_scope='READY_QUEUE',decision_cap=8192,concurrency_mode='DATA_DERIVED_PROGRESS',
                            unidentified_overlap='SERIAL_INDEPENDENT',frozen_policy=actor,
                            frozen_policy_binding=dict(replay_only=True,checkpoint_sha256='NO_NN_OBSERVER_'+mode,input_contract_sha256=opsha))
                    finally:L.thermal_model.predict=original
                    activity=L.generated_activity(public,pred);end=case['observation_end_s']
                    times=sorted({0.,35.,case['work_window'][1],end,*map(float,range(math.ceil(end)))})
                    ap=original(thermal,activity,times=times,allow_extrapolation=True)
                    L.need(ap['status']=='CONDITIONAL_AP_PREDICTION','AP coverage')
                    summary=dict(requests=pred['requests'],gantt=activity['owner_intervals'],AP=dict(t_s=ap['t_s'],ap_c=ap['ap_c']))
                    audit=L.audit_result(dict(prediction=pred,summary={'measured_J':None}),None)
                    m=metrics(summary,pred,case,cost);opportunity=actor.summary()
                    L.need(opportunity['decision_opportunities']==48,'One opportunity census per actual dispatch')
                    raw=out/(label+'.raw.json.gz');save_binary(raw,gzip.compress(L.canonical(dict(prediction=pred,summary=summary,opportunities=actor.opportunities)).encode(),mtime=0))
                    row=dict(case=case['id'],pair=case['pair'],arm=case['arm'],policy=mode,n=48,metrics=m,
                        opportunities=opportunity,audit=audit,raw_sha256=L.sha(raw),NN_execution=0,
                        EDF_protection_census_is_shadow=mode=='EDF',measured_J=None)
                    L.write_new(out/(label+'.json'),row);results.append(row)
                    for event in ('PREPARED','COMPLETE'):L.append(out/'receipts.jsonl',{**start,'event':event,'result_sha256':L.sha(out/(label+'.json')),'raw_sha256':L.sha(raw),'utc':L.now()})
                    print('COMPLETE',label,'requests',opportunity['multiple_requests_after'],'twofree',opportunity['two_free_routes'],'ontime',m['on_time'],flush=True)
                    del actor,model,pred,summary;gc.collect()
                except BaseException as exc:
                    L.append(out/'receipts.jsonl',{**start,'event':'FAIL','error':str(exc),'automatic_retry':False});raise
        for p in op['sources']:L.pin(p)
        L.need(count==24,'Exact planned consumption')
        L.write_new(out/'RESULT.json',dict(schema='A24-choice-opportunity-result-v1',rows=results,
            new_START=count,new_COMPLETE=count,new_FAIL=0,NN_training=0,new_fit=0,measured_J=None,
            operation_sha256=opsha,protection_changed=False,development_only=True))
        L.write_new(out/'COMPLETE.json',dict(utc=L.now(),result_sha256=L.sha(out/'RESULT.json'),new_START=count,new_COMPLETE=count))
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main()
