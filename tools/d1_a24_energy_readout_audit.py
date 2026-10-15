"""Offline consistency diagnostic, never a calibrated power/energy estimate.

Both BatteryManager properties can share one gauge. Agreement is not independent
validation. No scale correction, phone command, or change to measurement sources.
"""
import argparse
import csv
import json
import statistics
from pathlib import Path
from d1_a24_laptop_validator import load_json, sha256, NS
from d1_a24_measurement_analysis import integrate_window


def audit_events(events, origin):
    samples=[e for e in events if e['kind']=='sensor_sample']
    valid=[e for e in samples if type(e.get('current_raw')) is int and type(e.get('charge_counter_raw')) is int]
    left=[e for e in valid if e['read_end_ns']<=origin]
    right=[e for e in valid if e['read_end_ns']>=origin+180*NS]
    common={'calibrated_energy_J':None,'unit_scale_correction_applied':False,
            'independent_power_ground_truth':False,'reported_sensor_cache_age_verified':False}
    if not left or not right:
        return common|{'status':'COUNTER_ENDPOINTS_NOT_BRACKETED'}
    first=max(left,key=lambda e:e['read_end_ns']);last=min(right,key=lambda e:e['read_end_ns'])
    selected=[e for e in samples if first['read_end_ns']<=e['read_end_ns']<=last['read_end_ns']]
    if any(type(e.get('current_raw')) is not int or type(e.get('charge_counter_raw')) is not int or e.get('plugged')!=0 for e in selected):
        return common|{'status':'MISSING_OR_CHARGING_SAMPLE'}
    integral=integrate_window([(e['read_end_ns'],-e['current_raw']) for e in selected],first['read_end_ns'],last['read_end_ns'],2_500_000_000)
    declared_current_uAh=integral['integral']/3600 if integral['integral'] is not None else None
    counter_drop=first['charge_counter_raw']-last['charge_counter_raw']
    steps=[abs(b['charge_counter_raw']-a['charge_counter_raw']) for a,b in zip(selected,selected[1:]) if b['charge_counter_raw']!=a['charge_counter_raw']]
    return common|{'status':'DIAGNOSTIC_ONLY_NO_UNIT_VALIDATION',
        'start_relative_s':(first['read_end_ns']-origin)/NS,'end_relative_s':(last['read_end_ns']-origin)/NS,
        'duration_s':(last['read_end_ns']-first['read_end_ns'])/NS,'samples':len(selected),
        'raw_current_median':statistics.median(e['current_raw'] for e in selected),
        'raw_counter_first':first['charge_counter_raw'],'raw_counter_last':last['charge_counter_raw'],
        'declared_uA_integral_in_uAh_hypothesis':declared_current_uAh,
        'declared_uAh_counter_drop_hypothesis':counter_drop,
        'counter_drop_to_current_integral_ratio':counter_drop/declared_current_uAh if declared_current_uAh and declared_current_uAh>0 else None,
        'counter_distinct_levels':len({e['charge_counter_raw'] for e in selected}),
        'counter_change_events':len(steps),'counter_smallest_nonzero_step_raw':min(steps,default=None),
        'counter_largest_nonzero_step_raw':max(steps,default=None),
        'current_integration_status':integral['status']}


def export(job_path, out):
    job=load_json(job_path);root=Path(job['run_root']);plan=load_json(Path(job['plan']))
    rows=[]
    for row in plan['sessions']:
        outcome=root/(row['session_id']+'.outcome.json')
        if not outcome.exists() or load_json(outcome)['status']!='COMPLETE_TRACE_RECOVERED':continue
        raw=root/'raw'/row['session_id'];load_json(raw/'journal_closed.json')
        events=[json.loads(s) for s in (raw/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        origin=load_json(raw/'summary.json')['common_start_ns']
        rows.append({k:row[k] for k in ['session_id','recipe','arm']}|audit_events(events,origin))
    out.mkdir(parents=True,exist_ok=False)
    names=list(dict.fromkeys(k for r in rows for k in r))
    with (out/'energy_readout_unit_diagnostic.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,names);writer.writeheader();writer.writerows(rows)
    (out/'provenance.json').write_text(json.dumps({'analysis_source_sha256':sha256(Path(__file__)),
        'job_sha256':sha256(job_path),'complete_sessions':len(rows),'device_commands':0,
        'energy_unit_verified':False,'calibrated_energy_J':None,
        'warning':'same-gauge consistency only; neither independent calibration nor a justified fixed correction factor'},indent=2),encoding='utf-8')
    print(json.dumps({'status':'DIAGNOSTIC_ONLY','sessions':len(rows),'device_commands':0,'calibrated_energy_J':None}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('output',type=Path);a=p.parse_args();export(a.job,a.output)
