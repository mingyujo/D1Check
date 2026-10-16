"""Registered saved-data summary only; no fitting, policy simulation or fetch."""
import argparse
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from runtime_guard import operation, read, pin, canonical, write_new

p=argparse.ArgumentParser();p.add_argument('--operation',required=True)
args=p.parse_args()
with operation(args.operation,__file__) as (op,out):
    assert op['mode']=='MODEL_METADATA'
    data=read(pin(op['dataset_pin']))
    sessions=data['sessions']
    ids=[s['session_id'] for s in sessions]
    roster=[]
    for s in sessions:
        battery=s.get('battery',{})
        roster.append({k:s.get(k) for k in ('session_id','cohort_id','source_family','source_generation','bank','arm','protocol','target_eligibility','planned_windows','actual_recorded_window_s','continuous_response_tracking_verified')}|
                      {'requests':len(s.get('requests',[])),'observations':len(s.get('observations',[])),
                       'battery_summary':{k:v for k,v in battery.items() if k not in ('samples','raw_samples','rows')}})
    timing=read(pin(op['timing_cv_pin']))
    groups=defaultdict(list)
    for row in timing['rows']:
        groups[canonical(row['configuration'])].append(row)
    summaries=[]
    for config,rows in groups.items():
        errors=[r['prediction_error_ns'] for r in rows if r.get('prediction_error_ns') is not None]
        summaries.append({'configuration':json.loads(config),'rows':len(rows),
           'predicted':len(errors),'unknown':len(rows)-len(errors),'MAE_ms':statistics.mean(map(abs,errors))/1e6 if errors else None,
           'bias_ms':statistics.mean(errors)/1e6 if errors else None,'maximum_absolute_ms':max(map(abs,errors),default=0)/1e6 if errors else None,
           'sessions_with_predictions':len({r['session_id'] for r in rows if r.get('prediction_error_ns') is not None}),
           'unknown_reasons':dict(Counter(r.get('unknown_reason','UNKNOWN') for r in rows if r.get('prediction_error_ns') is None))})
    eligible=[s['session_id'] for s in sessions if s.get('source_family')=='m8' and s.get('target_eligibility',{}).get('timing_fit') is True]
    models=read(pin(op['thermal_models_pin']))
    result={'schema':'A24-saved-model-input-metadata-v1','dataset_sha256':op['dataset_pin']['sha256'],
       'session_roster_sha256':hashlib.sha256(canonical(ids).encode()).hexdigest(),'sessions':roster,
       'timing_qualified_M8_ids':eligible,'timing_qualified_count':len(eligible),'timing_models_built':timing['model_builds'],
       'timing_summaries':summaries,'thermal_model_hashes':{k:v.get('model_sha256') for k,v in models['final_models'].items()},
       'measured_J':None,'new_environment':0,'fit':0,'HTTP':0,'NN':0,'fresh_confirmation':False}
    write_new(out/'INPUT_METADATA.json',result)
    print(canonical({'sessions':len(sessions),'timing_qualified':len(eligible),'timing_summaries':summaries}))
