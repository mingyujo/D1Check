"""One-shot saved forecast audit; never imports or invokes a policy simulator.

Ledger/SHA/phase/capacity/denominator/energy arithmetic is independently
reconstructed here. AP curves are replayed with the exact frozen AP function;
that part is a saved numerical replay, not a second independent AP algorithm.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import math
from pathlib import Path
import statistics
from runtime_guard import canonical, operation, pin, read, require, sha, write_new

NS = 1_000_000_000
BOUNDARIES = ('execution_start','output_ready','persist_complete','worker_release','lane_available')
STATES = ('classification_CPU','detection_CPU','classification_GPU','classification_GPU+detection_CPU')
CHECKS = 0

def check(ok, reason):
    global CHECKS
    CHECKS += 1
    require(bool(ok), reason)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def tree_equal(a,b,label):
    if isinstance(a,dict) and isinstance(b,dict):
        check(set(a)==set(b),label+': keys')
        for k in a: tree_equal(a[k],b[k],label+'/'+str(k))
    elif isinstance(a,list) and isinstance(b,list):
        check(len(a)==len(b),label+': length')
        for i,(x,y) in enumerate(zip(a,b)): tree_equal(x,y,label+'/'+str(i))
    elif type(a) in (int,float) and type(b) in (int,float):
        check(math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8),label+': numeric')
    else:
        check(type(a) is type(b) and a==b,label+': value')

def jsonl(path):
    with Path(path).open(encoding='utf-8-sig') as f:
        return [__import__('json').loads(line) for line in f if line.strip()]

def terminal_bijection(starts,terminals):
    check(len({r['identity'] for r in starts})==len(starts),'Duplicate START')
    check(Counter(r['identity'] for r in terminals)==Counter(r['identity'] for r in starts),'Exactly one terminal per START identity')

def unavailable_ap_guard(ap,row):
    check(ap.get('status')=='UNKNOWN' and ap.get('reason')=='model unavailable or solver did not converge','Unavailable AP model evidence')
    check(all(c is None for c in ap.get('ap_c',[])) and len(ap.get('ap_c',[]))==len(ap.get('t_s',[])),'Unavailable AP remains a null curve')
    check(all(row.get(k) is None for k in ('AP_mean_c','AP_peak_c','AP_endpoint_c','AP_residual_c')),'Unavailable AP cannot have numeric summaries')

def quantile(values):
    ordered=sorted(values)
    return ordered[math.ceil(.95*len(ordered))-1] if ordered else None

def summary(rows,drain):
    done=[q for q in rows if q.get('response_ns') is not None and q['response_ns']<=drain]
    ontime=sum(q['response_ns']<=q['deadline_ns'] for q in done)
    bounds=[max(0,(q['response_ns'] if q in done else drain)-q['scheduled_arrival_ns'])/NS for q in rows]
    tardy=[max(0,(q['response_ns'] if q in done else drain)-q['deadline_ns'])/NS for q in rows]
    missing=[q for q in rows if q not in done]
    return {'planned':len(rows),'response_completed_by_drain':len(done),'uncompleted':len(missing),
            'on_time':ontime,'on_time_rate_planned':ontime/len(rows) if rows else None,
            'P95_all_requested_response_s':quantile(bounds) if not missing else None,
            'P95_all_requested_response_lower_bound_s':quantile(bounds),
            'P95_completed_response_s':quantile([(q['response_ns']-q['scheduled_arrival_ns'])/NS for q in done]),
            'P95_all_requested_tardiness_s':quantile(tardy) if not missing else None,
            'P95_all_requested_tardiness_lower_bound_s':quantile(tardy),
            'total_tardiness_s':sum(tardy) if not missing else None,
            'total_tardiness_lower_bound_s':sum(tardy),
            'service_threshold_flags':{str(p):ontime/len(rows)>=p/100 if rows else None for p in (70,80,90,95,100)}}

def check_deadlines(rows,saved,drain):
    values=summary(rows,drain)
    for k,v in values.items(): tree_equal(v,saved[k],'deadline/'+k)
    groups={'U':lambda q:q.get('priority')=='U','N':lambda q:q.get('priority')=='N',
            'C':lambda q:q['task']=='C','D':lambda q:q['task']=='D'}
    for task in ('C','D'):
        for priority in ('U','N'): groups[task+priority]=lambda q,t=task,p=priority:q['task']==t and q.get('priority')==p
    for k,f in groups.items():
        for field,value in summary([q for q in rows if f(q)],drain).items():
            tree_equal(value,saved['by_cohort'][k][field],'cohort/'+k+'/'+field)
    check(saved['missing_response_imputed'] is False,'Incomplete responses must not be imputed')
    return values

def expected_owners(public,rows):
    end=public['observation_end_ns']/NS
    out=[]
    for q in rows:
        if q.get('dispatch_ns') is None: continue
        a=q['dispatch_ns']/NS
        b=min(end,q['available_ns']/NS) if q.get('available_ns') is not None else end
        if a<b: out.append({'start_s':a,'end_s':b,'request_id':q['request_id'],'task':q['task'],'route':q['route'],
                            'end_is_censored_forecast_window':q.get('available_ns') is None or q['available_ns']/NS>end})
    return out

def check_owners(owners):
    marks=sorted({float(x[k]) for x in owners for k in ('start_s','end_s')})
    overlap=0.
    for a,b in zip(marks,marks[1:]):
        active=[x for x in owners if x['start_s']<b and x['end_s']>a]
        check(len(active)<=2,'More than two owners')
        check(len({x['route'] for x in active})==len(active),'Resource overlap/nonpreemption violation')
        labels={(x['task'],x['route']) for x in active}
        check(labels<={('C','CPU'),('C','GPU'),('D','CPU')},'Illegal resource/task')
        if len(active)==2:
            check(labels=={('C','GPU'),('D','CPU')},'Unqualified pair')
            overlap+=b-a
    return overlap

def energy(activity,profile,window):
    a,b=window
    coverage=activity.get('activity_coverage_s')
    observed=activity.get('observation_window_s')
    if not coverage or not observed or max(coverage[0],observed[0])>a or min(coverage[1],observed[1])<b:
        return None
    owners=activity['owner_intervals']
    marks=sorted({a,b,*[max(a,min(b,float(x[k]))) for x in owners for k in ('start_s','end_s')]})
    occupancy={k:0. for k in (*STATES,'resident_idle')}
    for lo,hi in zip(marks,marks[1:]):
        labels={(x['task'],x['route']) for x in owners if x['start_s']<hi and x['end_s']>lo}
        state='resident_idle' if not labels else 'classification_GPU+detection_CPU' if len(labels)==2 else (
              ('classification_' if next(iter(labels))[0]=='C' else 'detection_')+next(iter(labels))[1])
        check(state in occupancy,'Unknown energy state')
        occupancy[state]+=hi-lo
    return profile['measured35']['baseline_w']*(b-a)+sum(occupancy[k]*profile['cost_anchor']['energy_increment_w'][k] for k in STATES)

def model_index(value,models):
    if isinstance(value,dict):
        if isinstance(value.get('model_sha256'),str) and 'coefficients' in value and 'feature_names' in value:
            check(digest({k:v for k,v in value.items() if k!='model_sha256'})==value['model_sha256'],'AP model internal hash')
            models[value['model_sha256']]=value
        else:
            for child in value.values(): model_index(child,models)
    elif isinstance(value,list):
        for child in value: model_index(child,models)

def audit(op,out):
    import thermal_model
    require(op['mode']=='AUDIT_FORECAST_SAVED','Wrong audit mode')
    require(op.get('AP_replay_cap')==256 and op.get('new_policy_simulations')==0,'Saved-only replay budget')
    allowed={(str(Path(x['path']).resolve()),x['sha256']) for x in op['input_pins']}
    def artifact(k):
        spec=op[k];check((str(Path(spec['path']).resolve()),spec['sha256']) in allowed,'Unregistered logical input '+k)
        return read(pin(spec))
    result,complete,cases=artifact('forecast_result_pin'),artifact('forecast_complete_pin'),artifact('case_status_pin')
    forecast_operation=artifact('forecast_operation_pin')
    check(forecast_operation.get('energy_start_s')==0 and forecast_operation.get('energy_end_s')==180,'Registered audit energy window')
    rowfile=pin(op['forecast_rows_pin']); receiptfile=pin(op['forecast_receipts_pin'])
    check((str(rowfile.resolve()),op['forecast_rows_pin']['sha256']) in allowed,'Rows not input pinned')
    check((str(receiptfile.resolve()),op['forecast_receipts_pin']['sha256']) in allowed,'Receipts not input pinned')
    rows,receipts=jsonl(rowfile),jsonl(receiptfile)
    starts=[r for r in receipts if r['event']=='START']
    terminal=[r for r in receipts if r['event'] in ('FAIL','COMPLETE')]
    counts=Counter(r['event'] for r in receipts)
    check(len(starts)==len(terminal)==result['simulation_START_consumed']==complete['simulation_START_consumed'],'START conservation')
    terminal_bijection(starts,terminal)
    check(len({r['logical_case_sha256'] for r in starts})==len(starts),'Duplicate logical case')
    prior_global=sum(p.get('START',0) for p in forecast_operation.get('prior_forecast_ledger_pins',[]))
    external_global=sum(p.get('START',0) for p in forecast_operation.get('extra_consumption_ledgers',[]))
    for i,start in enumerate(starts):
        check(start['manifest']['operation_sha256']==op['forecast_operation_pin']['sha256'],'START operation SHA')
        check(start['guards']['arithmetic']['this_forecast_START_before']==i,'Durable START ordinal')
        check(start['guards']['arithmetic']['this_forecast_START_after']==i+1,'Durable START charge')
        check(26454+external_global+prior_global+i+1<=137712,'Global START cap')
        check(1695+prior_global+i+1<=2048 and prior_global+i+1<=256,'A24 shared START caps')
    check(result['global_START_after']==26454+external_global+prior_global+len(starts),'Reported global consumption')
    check(len(cases['cases'])==cases['registered_case_roster']==249,'All249 planned cases retained')
    check(Counter(c['kind'] for c in cases['cases'])=={'PREDECLARED_NOVEL_GRID':180,'WHOLE_COHORT_HELDOUT_VALIDATION':69},'Case roles')
    check(sum(c['simulation_START_consumed'] for c in cases['cases'])==len(starts),'Case START count')
    check(Counter(c['identity'] for c in cases['cases'] if c['identity'])==Counter(r['identity'] for r in starts),'Case identity links')
    check(len(rows)==counts['COMPLETE']==result['COMPLETE'] and counts['FAIL']==result['FAIL'],'Success/failure denominator')
    check(Counter(r['identity'] for r in rows)==Counter(r['identity'] for r in terminal if r['event']=='COMPLETE'),'Exactly one row per COMPLETE identity')
    check(result['measured_J'] is None and result['physical_goal_pass'] is False and result['RL_connected'] is False,'Scientific boundaries')
    check(result['all_failed_STARTs_remain_consumed'] is True and result['automatic_retry'] is False,'Failure consumption')
    profile=artifact('historical_profile_pin')
    models={}; model_index(artifact('thermal_models_pin'),models); model_index(artifact('thermal_cv_pin'),models)
    terminal_by={r['identity']:r for r in terminal}
    start_by={r['identity']:r for r in starts}
    report=[]; ap_queries=0; unavailable_AP_models=0
    for row in rows:
        identity=row['identity'];term=terminal_by[identity]
        check(term['event']=='COMPLETE','Saved row without COMPLETE')
        check(term['row_sha256']==digest(row),'Canonical row SHA')
        for field in ('raw','prepared','terminal'):
            spec={'path':term[field+'_path'],'sha256':term[field+'_sha256']}
            pin(spec)
        terminal_body=read(term['terminal_path']);tree_equal(terminal_body['row_sha256'],digest(row),'terminal row SHA')
        check(terminal_body.get('identity')==identity and terminal_body.get('event')=='COMPLETE' and
              terminal_body.get('operation_sha256')==op['forecast_operation_pin']['sha256'],'COMPLETE terminal body identity/operation/event')
        prepared=read(term['prepared_path'])
        check(prepared['manifest']==row['manifest']==start_by[identity]['manifest'],'Manifest chain')
        # The row adds its own prepared pointer after the prepared file exists.
        check(all(row[k]==v for k,v in prepared['row'].items()),'Prepared-to-row binding')
        raw=__import__('json').loads(gzip.decompress(Path(term['raw_path']).read_bytes()))
        public,simulation,activity,ap=raw['public_input'],raw['simulation'],raw['simulated_activity'],raw['AP_prediction']
        check(raw['forecast_manifest']==row['manifest'],'Raw manifest link')
        check(public['public_scenario_sha256']==row['public_scenario_sha256'],'Public scenario binding')
        check(all(x.get('hi_s',math.inf)<=0 for x in public.get('observations',[])),'Future measured AP leakage')
        check('owner_intervals' not in public and 'state_intervals' not in public,'Future owner leakage')
        forbidden={'response_ns','dispatch_ns','available_ns','execution_start_ns','output_ready_ns','persist_complete_ns'}
        check(all(not(forbidden & set(q)) for q in public['requests']),'Future measured request leakage')
        predicted=simulation['requests']; planned={q['request_id']:q for q in public['requests']}
        check(len(predicted)==len(planned) and {q['request_id'] for q in predicted}==set(planned),'All-request roster')
        for q in predicted:
            source=planned[q['request_id']]
            for k in ('ordinal','task','priority','group','scheduled_arrival_ns','deadline_ns'):tree_equal(q[k],source[k],'public request '+k)
            dispatch=q.get('dispatch_ns')
            if dispatch is None:check(q.get('response_ns') is None and q.get('available_ns') is None,'Undispatched request completed');continue
            check(q['scheduled_arrival_ns']<=q['actual_arrival_ns']<=q['queue_entry_ns']<=dispatch,'Arrival/queue/dispatch chronology')
            previous=dispatch
            for k in BOUNDARIES:
                value=q.get(k+'_ns')
                if value is not None:check(value>=previous,'Phase order '+k);previous=value
            response=q.get('output_ready_ns' if q['task']=='C' else 'persist_complete_ns')
            tree_equal(q.get('response_ns'),response,'C output / D persist response')
            # Frozen atomic mode records AVAILABLE separately; rolling also
            # exposes lane_available_ns. Neither schema is retroactively edited.
            if 'lane_available_ns' in q:
                tree_equal(q.get('available_ns'),q['lane_available_ns'],'AVAILABLE boundary')
            if q.get('available_ns') is not None:
                check(q['available_ns']>=previous,'AVAILABLE after completed phases')
        owners=expected_owners(public,predicted);tree_equal(activity['owner_intervals'],owners,'Generated activity')
        overlap=check_owners(owners)
        ds=check_deadlines(predicted,row['deadline_summary'],public['drain_stop_ns'])
        check(simulation['metrics']['planned']==ds['planned'] and simulation['metrics']['on_time']==ds['on_time'],'Simulator metrics')
        check(simulation['new_environment_STARTs']==row['new_simulator_environments_consumed']==1,'Per-case environment consumption')
        for energy_key,raw_key,window in (('historical_conditional_J','historical_conditional_energy',[0.,180.]),
            ('historical_conditional_J_full_forecast_window','historical_conditional_energy_full_forecast_window',[0.,public['observation_end_ns']/NS])):
            expected=energy(activity,profile,window)
            tree_equal(expected,row.get(energy_key),'Independent conditional energy')
            tree_equal(expected,raw[raw_key].get('historical_conditional_J'),'Raw conditional energy')
            check(raw[raw_key]['measured_J'] is None,'Conditional energy is not device J')
        if ap.get('model_sha256') is None:
            unavailable_AP_models+=1
            unavailable_ap_guard(ap,row)
        else:
            ap_queries+=1;check(ap_queries<=op['AP_replay_cap'],'AP replay budget')
            check(ap['model_sha256'] in models,'AP hash outside registered models')
            model=models[ap['model_sha256']]
            replay=thermal_model.predict(model,activity,times=ap['t_s'],reference_domain=forecast_operation.get('AP_reference_domain'),allow_extrapolation=True)
            tree_equal(replay,ap,'Frozen AP saved replay')
        check(row['AP_model_sha256']==ap['model_sha256'] and row['AP_status']==ap['status'],'AP row binding')
        if row.get('AP_mean_c') is not None:
            a,b=row['AP_summary_window_s'];points=[(t,c) for t,c in zip(ap['t_s'],ap['ap_c']) if a<=t<=b]
            check(points[0][0]==a and points[-1][0]==b,'Exact AP summary coverage')
            mean=sum((y[0]-x[0])*(x[1]+y[1])/2 for x,y in zip(points,points[1:]))/(b-a)
            tree_equal(mean,row['AP_mean_c'],'Independent AP mean');tree_equal(max(c for _,c in points),row['AP_peak_c'],'AP peak')
            tree_equal(points[-1][1],row['AP_endpoint_c'],'AP endpoint')
        check(row['measured_J'] is None and row['physical_goal_pass'] is False,'Per-row physical boundary')
        def active(at):
            return [q['request_id'] for q in predicted if q.get('dispatch_ns') is not None and q['dispatch_ns']<=at
                    and (q.get('available_ns') is None or q['available_ns']>at)]
        end=public['observation_end_ns'];drain=public['drain_stop_ns'];cutoff=180*NS
        expected_work={'planned':len(predicted),
            'responded_by_drain':sum(q.get('response_ns') is not None and q['response_ns']<=drain for q in predicted),
            'AVAILABLE_by_drain':sum(q.get('available_ns') is not None and q['available_ns']<=drain for q in predicted),
            'unfinished_by_drain':sum(q.get('available_ns') is None or q['available_ns']>drain for q in predicted),
            'energy_window_s':[0.,180.],
            'responded_by_energy_end':sum(q.get('response_ns') is not None and q['response_ns']<=cutoff for q in predicted),
            'AVAILABLE_by_energy_end':sum(q.get('available_ns') is not None and q['available_ns']<=cutoff for q in predicted),
            'owners_at_service_cutoff':active(public['service_stop_ns']),'owners_at_drain_cutoff':active(drain),
            'owners_at_energy_cutoff':active(cutoff),
            'modeled_owner_seconds_after_energy_window':sum(max(0,min(q['available_ns'] if q.get('available_ns') is not None else end,end)-max(q['dispatch_ns'],cutoff))/NS for q in predicted if q.get('dispatch_ns') is not None),
            'right_censored_owner_hold_is_assumption':any(q.get('dispatch_ns') is not None and q.get('available_ns') is None for q in predicted),
            'energy_decrease_is_efficiency_or_goal_PASS':False}
        tree_equal(expected_work,row['work_scope'],'Full work and residual scope')
        report.append({'identity':identity,'label':row['label'],'status':row['status'],'planned':len(predicted),
                       'on_time':ds['on_time'],'incomplete':row['work_scope']['unfinished_by_drain'],'overlap_s':overlap,
                       'AP_status':ap['status'],'uncertainty_flags':row['uncertainty_flags']})
    for term in terminal:
        if term['event']=='FAIL':
            pin({'path':term['terminal_path'],'sha256':term['terminal_sha256']})
            body=read(term['terminal_path'])
            check(body.get('event')=='FAIL' and body.get('identity')==term['identity'] and
                  body.get('operation_sha256')==op['forecast_operation_pin']['sha256'],'Failed terminal SHA/event/identity/operation')
    write_new(out/'AUDIT_RESULT.json',{'schema':'A24-SAVED-FORECAST-RESULT-AUDIT-v1','status':'PASS_SAVED_ARTIFACT_ARITHMETIC_ONLY',
        'checks':CHECKS,'planned_cases':249,'case_statuses':dict(Counter(c['status'] for c in cases['cases'])),
        'receipt_counts':dict(counts),'rows':len(rows),'AP_saved_replay_queries':ap_queries,'AP_replay_cap':op['AP_replay_cap'],
        'unavailable_AP_models_preserved_without_numeric_replay':unavailable_AP_models,
        'AP_replay_uses_same_frozen_function':True,'AP_independent_feature_math_prior_Node_audit_separate':True,
        'new_policy_simulations':0,'new_fit':0,'NN':0,'HTTP':0,'device_commands':0,'measured_J':None,
        'physical_goal_pass':False,'fresh_confirmation':False,'policy_winner_selected':False,'cases':report,
        'limits':['No policy simulation or parameter fitting rerun.','AP replay shares the frozen Python function; independent model arithmetic is in the preceding Node audit.',
                  'Timing latent selection and installed scheduler/APK/assets are not independently established by this saved arithmetic audit.']})

def main():
    p=argparse.ArgumentParser();p.add_argument('--operation',required=True);args=p.parse_args()
    with operation(args.operation,__file__) as (op,out):
        if op['mode']=='AUDIT_FORECAST_TEST':
            import io,unittest
            suite=unittest.TestLoader().discover(str(Path(__file__).resolve().parent),pattern='test_audit_forecast_results.py')
            stream=io.StringIO();test=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            write_new(out/'TEST_RESULT.json',{'status':'PASS' if test.wasSuccessful() else 'FAIL','testsRun':test.testsRun,
                'output':stream.getvalue(),'new_fit':0,'new_policy_simulations':0,'AP_replay_queries':0})
            require(test.wasSuccessful(),'Saved audit fixtures failed; preserve consumed output')
        else:audit(op,out)
    print(canonical({'status':'COMPLETE','output':str(out)}))

if __name__=='__main__':main()
