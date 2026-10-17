"""Frozen A24 physics; new request-level RR runs with exact saved three-rule reuse, no NN import."""
from pathlib import Path
import copy,gc,gzip,json,math,os,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ENTRY=Path(__file__).resolve()
os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)
sys.path[:0]=[str(HERE),str(ROOT/'experiments/rules_no_rl_20261017'),str(ROOT/'src'),str(ROOT/'experiments/edf_cpu_first_20261016'),str(ROOT/'experiments/competition_cost_20261017')]
import lab_backend as L
from shared_exact import public_input,metrics,save_binary
from rr_policy import installed,SPEC
from policy import installed as install_edf
K=L.load_module('rules_long_kernel',ROOT/'experiments/long_scale_20261017/kernel_long.py')
G=L.runtime_guard;G.OWN_TOKENS+=('rr_20261017','rules_no_rl_20261017','long_scale_20261017','s26-state-aware-atc-','state_recovery_owner','s26-multiresource-','s26-integrated-model-')

def run(opfile):
    op=L.read(opfile);opsha=L.sha(opfile)
    L.need(op['schema']=='A24-RR-operation-v1' and op['maximum_requests']==3072,'Registered scope')
    for p in op['pins']:L.pin(p)
    reg=L.read(ROOT/'models/registration.json');G.process_guard(ENTRY,reg['known_PS_producer_paths']);L.free_guard([ROOT,'D:/'])
    out=ROOT/op['output_dir'];L.need(not out.exists(),'Operation consumed; automatic restart prohibited')
    import msvcrt
    lock=Path(reg['worker_lock_path']).open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0
    try:
        out.mkdir(parents=True,exist_ok=False);L.write_new(out/'START.json',dict(utc=L.now(),operation_sha256=opsha,process=G.process_guard(ENTRY,reg['known_PS_producer_paths'])))
        try:
            base,thermal,profile=L.initialize(reg);catalog=L.read(L.pin(reg['catalog_pin']));design=L.read(L.pin(op['inputs']));cost=L.read(L.pin(op['cost_model']));budget=L.read(L.pin(op['budget']))
            L.need([c['n'] for c in design['cases']]==[48,96,192,384,768,1536,3072],'Exact seven lengths; no higher count')
            prior=L.read(L.pin(op['saved_rules_report']));saved={c['n']:c['rows'] for c in prior['cases']}
            def simulate(case,policy,label):
                nonlocal count
                G.process_guard(ENTRY,reg['known_PS_producer_paths']);L.free_guard([ROOT,'D:/'])
                L.need(count<op['environment_cap'],'Own cap')
                previous=0
                for l in budget['global_ledgers']:
                    p=Path(l['path'])
                    if not p.exists():L.need(l['START']==0,'Missing nonzero ledger');continue
                    previous+=sum(json.loads(line).get('event')=='START' for line in p.read_text(encoding='utf-8-sig').splitlines() if line)
                L.need(previous+count<137712,'Global START cap')
                public,contexts=public_input(case,catalog);model=L.Model(base,contexts);identity=L.digest([opsha,label])
                start=dict(event='START',identity=identity,start_id=identity,registration_sha256=opsha,durable_START_consumed=True,n=case['n'],policy=policy,label=label,utc=L.now(),input_sha256=L.digest(case['input']))
                L.append(out/'receipts.jsonl',start);count+=1;print('START',label,flush=True);t=time.monotonic()
                try:
                    trace=[]
                    with install_edf(K,L),installed(K,trace):
                        pred=K.simulate_protocol(public,model,policy,execution_guard=start,
                            scenario_key=case.get('common_potential_key',design['common_potential_key']),
                            admission_protocol='SERIAL',redispatch_mode='ZERO_EXPLICIT_BASELINE',zero_baseline_id='COMMON_UNIDENTIFIED_CONTROLLER_IDEAL_ZERO',
                            pair_scope='READY_QUEUE',decision_cap=max(8192,case['n']*64),concurrency_mode='DATA_DERIVED_PROGRESS',unidentified_overlap='SERIAL_INDEPENDENT')
                    pred['rule_decision_audit']=trace
                    save_binary(out/(label+'.prepared_prediction.json.gz'),gzip.compress(L.canonical(pred).encode(),compresslevel=1,mtime=0))
                    activity=L.generated_activity(public,pred);end=public['observation_end_ns']/1e9
                    times=sorted(set([0.,35.,case['work_window'][1],end]+[float(i) for i in range(math.ceil(end))]))
                    ap=L.thermal_model.predict(thermal,activity,times=times,allow_extrapolation=True)
                    L.need(ap['status']=='CONDITIONAL_AP_PREDICTION','AP: '+str(ap.get('reason')))
                    summary=dict(policy=policy,requests=pred['requests'],gantt=activity['owner_intervals'],AP=dict(t_s=ap['t_s'],ap_c=ap['ap_c']))
                    audit=L.audit_result(dict(prediction=pred,summary={'measured_J':None}),None);m=metrics(summary,pred,case,cost)
                    raw=out/(label+'.raw.json.gz');save_binary(raw,gzip.compress(L.canonical(dict(prediction=pred,summary=summary)).encode(),compresslevel=1,mtime=0))
                    r=dict(label=label,n=case['n'],policy=policy,metrics=m,audit=audit,raw_sha256=L.sha(raw),NN=None,NN_execution=0,model_fitting=0,
                        AP_flags=ap['extrapolation_flags'],wall_seconds=time.monotonic()-t,measured_J=None,physical_goal_verified=False,
                        extended_duration_beyond_current_M8_210s=end>210,source_result_path=str((out/(label+'.json')).relative_to(ROOT)).replace('\\','/'))
                    L.write_new(out/(label+'.json'),r)
                    for e in ('PREPARED','COMPLETE'):L.append(out/'receipts.jsonl',{**start,'event':e,'result_sha256':L.sha(out/(label+'.json')),'raw_sha256':r['raw_sha256'],'utc':L.now()})
                    print('COMPLETE',label,'on_time',m['on_time'],'/',case['n'],'total_J*',round(m['total_J_proxy'],6),'AP',round(m['mean_AP_c'],6),'wall',round(r['wall_seconds'],1),flush=True)
                    return r,summary
                except BaseException as e:L.append(out/'receipts.jsonl',{**start,'event':'FAIL','error':str(e),'automatic_retry':False,'utc':L.now()});raise
            results=[]
            for case in design['cases']:
                rows=[{**r,'reused_saved_complete':True} for r in saved[case['n']]]
                for policy in ('RR_CPU_FIRST',):
                    r,summary=simulate(case,policy,'N%05d_%s'%(case['n'],policy));rows.append(r);del summary;gc.collect()
                results.append(dict(n=case['n'],window_s=case['work_window'],rows=rows))
                L.write_new(out/('PROGRESS_N%05d.json'%case['n']),dict(utc=L.now(),completed_levels=len(results),new_START=count,latest=rows))
            for p in op['pins']:L.pin(p)
            L.write_new(out/'RESULT.json',dict(schema='A24-RR-comparison-v1',cases=results,new_START=count,new_COMPLETE=count,new_FAIL=0,
                saved_rule_reuse=21,NN_execution=0,NN_training=0,model_fits=0,maximum_requests=3072,policy_spec=SPEC,
                event_reselection_common=True,multi_step_rolling_horizon_optimization=False,measured_J=None,physical_goal_verified=False,operation_sha256=opsha))
            L.write_new(out/'COMPLETE.json',dict(utc=L.now(),result_sha256=L.sha(out/'RESULT.json'),new_START=count,new_COMPLETE=count))
        except BaseException as e:L.write_new(out/'FAILURE.json',dict(error=str(e),utc=L.now(),automatic_retry=False));raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':run(sys.argv[1])
