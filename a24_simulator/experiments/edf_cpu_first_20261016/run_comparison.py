"""Registered 14 new EDF environments; reuse immutable selected-RL results."""
from pathlib import Path
import argparse, copy, csv, gzip, json, os, sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
os.environ['A24_LAB_GUARD_ENTRY']=str(Path(__file__).resolve())
import lab_backend as L
import interactive_kernel as kernel
from policy import POLICY, SPEC, installed, metrics, select

ENTRY=Path(__file__).resolve()

def check_pins(op):
    for s in op['source_pins']+op['input_pins']: L.pin(s)

def aggregate(cases, policy):
    rows=[next(r for r in c['metrics'] if r['policy']==policy) for c in cases]
    means=('baseline_J_proxy','total_J_proxy','increment_J_proxy','mean_AP_c','peak_AP_c','end_AP_c')
    out={'policy':policy,'conditions':len(rows),**{k:sum(r[k] for r in rows)/len(rows) for k in means}}
    for k in ('planned','on_time','responded','response_missing','responded_by_window_end','AVAILABLE_by_window_end'):
        out[k]=sum(r[k] for r in rows)
    out['on_time_percent']=100*out['on_time']/out['planned']
    out['total_tardiness_s']=sum(r['total_tardiness_s'] for r in rows) if all(r['total_tardiness_s'] is not None for r in rows) else None
    out['maximum_peak_AP_c']=max(r['peak_AP_c'] for r in rows)
    out['route_counts']={k:sum(r['route_counts'][k] for r in rows) for k in rows[0]['route_counts']}
    return out

def main(operation):
    op_path=Path(operation);op=L.read(op_path);op_sha=L.sha(op_path)
    L.need(op['schema']=='A24-EDF-CPU-first-comparison-operation-v1','Operation schema')
    L.need(op['policy_spec']==SPEC and op['new_environment_cap']==14,'Policy or cap changed')
    check_pins(op)
    reg=L.read(ROOT/'models/registration.json')
    state=L.runtime_guard.process_guard(ENTRY, reg['known_PS_producer_paths'])
    space=L.free_guard([ROOT,ROOT/op['output_dir'],reg['worker_lock_path'],'D:/'])
    out=ROOT/op['output_dir']
    L.need(not out.exists(),'Consumed namespace; no automatic retry')
    ledger=ROOT/'runtime/receipts.jsonl'
    lines=[json.loads(s) for s in ledger.read_text().splitlines() if s]
    L.need(sum(r['event']=='START' for r in lines)==op['expected_child_START_before'],'Budget snapshot differs')
    L.need(op['parent_START']+op['expected_child_START_before']+14 <= op['shared_cap'],'Shared budget exceeded')
    import msvcrt
    lock=Path(reg['worker_lock_path']).open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        out.mkdir(parents=True,exist_ok=False)
        L.write_new(out/'OPERATION_START.json',dict(operation_sha256=op_sha,utc=L.now(),process=state,space=space))
        try:
            old=L.read(ROOT/'results/FOUR_ROUTE_V2_EVAL.json')
            L.need(len(old['cases'])==14,'Expected frozen fourteen cases')
            model,thermal,profile=L.initialize(reg)
            L.need(thermal['model_sha256']==reg['expected_four_route_AP_sha256'],'AP freeze differs')
            catalog=L.read(L.pin(reg['catalog_pin']))
            cases=[]
            for i,c in enumerate(old['cases']):
                L.runtime_guard.process_guard(ENTRY,reg['known_PS_producer_paths']);L.free_guard([ROOT,'D:/'])
                check_pins(op)
                value=L.validate_input(copy.deepcopy(c['input']),catalog['profiles'])
                public,contexts=L.prepare_public(value,catalog['templates'],catalog['profiles'])
                m=L.Model(model,contexts)
                L.need(m.metadata['model_digest']==reg['expected_four_route_timing_digest'],'Timing freeze differs')
                rl=next(r for r in c['rows'] if r['policy']=='ROLLING_ATC_RL')
                L.need(rl['network_sha256']==op['selected_network_sha256'],'Saved RL actor differs')
                identity=L.digest(['EDF_CPU_FIRST_20261016_01',i,L.digest(value),op_sha])
                L.need(not any(r.get('identity')==identity for r in lines),'Identity previously consumed')
                start=dict(event='START',identity=identity,start_id=identity,policy=POLICY,
                           operation_sha256=op_sha,registration_sha256=op_sha,durable_START_consumed=True,
                           utc=L.now(),new_environment=1,case_index=i,input_sha256=L.digest(value))
                L.append(ledger,start);L.append(out/'receipts.jsonl',start)
                try:
                    with installed(kernel,L): result,actor=L.policy_result(POLICY,public,m,thermal,profile,value,start,reg)
                    audit=L.audit_result(result,actor)
                    decision_checks=0
                    for d in result['prediction']['decisions']:
                        L.need(d['action']==select(d['public_state']),'Actual action not pure EDF/CPU-first')
                        decision_checks+=1
                    raw=out/('EDF_%02d.raw.json.gz'%i)
                    with gzip.open(raw,'xt',encoding='utf-8') as f:f.write(L.canonical(result))
                    s=result['summary'];L.write_new(out/('EDF_%02d.summary.json'%i),s)
                    lo,hi=rl['diagnostics']['common_work_window_s']
                    pair=[metrics(rl,lo,hi),metrics(s,lo,hi)]
                    L.need(abs(pair[0]['baseline_J_proxy']-pair[1]['baseline_J_proxy'])<1e-8,'Unequal common baseline')
                    row=dict(index=i,label=c['label'],input=value,common_work_window_s=[lo,hi],
                             metrics=pair,rows=[rl,s],RL_summary_sha256=L.digest(rl),
                             audit=audit,EDF_actual_dispatch_checks=decision_checks)
                    L.write_new(out/('CASE_%02d.json'%i),row)
                    prepared={**start,'event':'PREPARED','raw_sha256':L.sha(raw),'summary_sha256':L.digest(s),
                              'case_sha256':L.sha(out/('CASE_%02d.json'%i)),'audit':audit,'EDF_dispatch_checks':decision_checks}
                    L.append(ledger,prepared);L.append(out/'receipts.jsonl',prepared)
                    terminal={**start,'event':'COMPLETE','utc':L.now(),'raw_sha256':L.sha(raw)}
                    L.append(ledger,terminal);L.append(out/'receipts.jsonl',terminal)
                    cases.append(row);print('EDF saved',i+1,'/14',flush=True)
                except BaseException as e:
                    failure={**start,'event':'FAIL','utc':L.now(),'error':str(e),'automatic_retry':False}
                    L.append(ledger,failure);L.append(out/'receipts.jsonl',failure);raise
            report=dict(schema='A24-same-window-EDF-versus-selected-RL-v1',operation_sha256=op_sha,
                        policy_spec=SPEC,cases=cases,aggregate=[aggregate(cases,p) for p in ('ROLLING_ATC_RL',POLICY)],
                        window_rule='input earliest arrival to latest arrival +15s; identical between policies',
                        AP_window_method='linear interpolation and trapezoid time mean with exact endpoints',
                        saved_RL_source_sha256=L.sha(ROOT/'results/FOUR_ROUTE_V2_EVAL.json'),
                        new_environment_START=14,NN_training=0,model_fit=0,HTTP=0,device_commands=0,
                        measured_J=None,fresh_confirmation=False,energy_CI=None,
                        budget=dict(parent_START=op['parent_START'],child_START_before=op['expected_child_START_before'],
                                    child_START_after=op['expected_child_START_before']+14,
                                    total_START=op['parent_START']+op['expected_child_START_before']+14,
                                    shared_cap=op['shared_cap'],remaining=op['shared_cap']-op['parent_START']-op['expected_child_START_before']-14))
            L.write_new(out/'RESULT.json',report)
            fields=list(cases[0]['metrics'][0]);
            with (out/'METRICS.csv').open('x',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['case_index','case_label']+fields);writer.writeheader()
                for c in cases:
                    for r in c['metrics']:writer.writerow(dict(case_index=c['index'],case_label=c['label'],**r))
            check_pins(op);L.need(L.sha(op_path)==op_sha,'Operation changed')
            L.write_new(out/'COMPLETE.json',dict(status='COMPLETE_14_EDF_WITH_SAVED_RL_REFERENCE',utc=L.now(),
                operation_sha256=op_sha,result_sha256=L.sha(out/'RESULT.json'),new_START=14,
                policy_selection_cost_lookups=0,budget=report['budget'],NN_training=0,model_fit=0))
            print(json.dumps(report['aggregate'],ensure_ascii=False),flush=True)
        except BaseException as e:
            L.write_new(out/'FAILURE.json',dict(utc=L.now(),type=type(e).__name__,error=str(e),automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--operation',required=True);main(ap.parse_args().operation)
