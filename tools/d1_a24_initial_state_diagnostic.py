"""PC-only supplementary baseline normalization of the 17 already closed runs.

No device API, fitting, new thresholds or changes to confirmation eligibility.
Private roots are command arguments; none are emitted into shared artifacts.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from d1_a24_laptop_validator import load_json,sha256
from d1_a24_measurement_analysis import integrate_window,NS
from d1_a24_measurement_share_bundle import encode,csv_bytes


def run(spec,output):
    contract_path=Path(spec['contract']);contract=load_json(contract_path)
    assert contract['primary_acceptance_or_execution_gate_changed'] is False
    assert contract['baseline_interval_seconds_relative_to_common_origin']==[0,35]
    assert contract['maximum_gap_seconds_unchanged']==10
    assert load_json(Path(spec['ledger']))['new_confirm_completed_execution']==17
    records=load_json(Path(spec['ledger']))['records'][:17]
    assert len(records)==17 and all(r['APP_launches']==1 and r['outcome']=='COMPLETE_TRACE_RECOVERED' for r in records)
    rows=[];sources=[];fingerprints=[]
    for record in records:
        sid=record['session_id']
        hits=[Path(p)/'raw'/sid for p in spec['closed_raw_roots'] if (Path(p)/'raw'/sid/'events.jsonl').exists()]
        assert len(hits)==1,(sid,'raw count');raw=hits[0]
        assert sha256(raw/'events.jsonl')==record['events_sha256']
        assert sha256(raw/'journal_closed.json')==record['closed_sha256']
        assert load_json(raw/'journal_closed.json')['status']=='SYNCED_AND_CLOSED'
        hits=[Path(p)/(sid+'.analysis.json') for p in spec['analysis_directories'] if (Path(p)/(sid+'.analysis.json')).exists()]
        assert len(hits)==1,(sid,'analysis count');analysis=load_json(hits[0])
        assert analysis['session_id']==sid
        origin=analysis['trace']['common_origin_ns']
        requests=load_json(raw/'requests.json')
        assert min(r['scheduled_arrival_ns'] for r in requests)==origin+35*NS
        hal=[json.loads(line) for line in (raw/'host_hal_raw.jsonl').read_bytes().splitlines()]
        samples=[]
        for x in hal:
            values=[s['value_c'] for s in x['sensors'] if s['sensor_name']=='AP' and s['sensor_type']==0]
            if len(values)==1:samples.append(((x['device_elapsed_before_ns']+x['device_elapsed_after_ns'])//2,values[0]))
        before=integrate_window(samples,origin,origin+35*NS,10*NS)
        primary=analysis['thermal'];baseline=before['integral']/35 if before['integral'] is not None else None
        eligible=before['status']==primary['status']=='READOUT_WINDOW_COVERED'
        rawmean=primary['mean_reported_AP_c'];rawpeak=primary['highest_observed_AP_c']
        row={k:record[k] for k in ['session_id','plan_ordinal','block','recipe','arm','request_count']}
        row.update(completed_MAIN_requests=analysis['trace']['completed_in_service'],
            pre_request_AP_window_status=before['status'],pre_request_AP_mean_c=baseline,
            original_AP_window_status=primary['status'],original_AP_mean_c=rawmean,original_observed_AP_peak_c=rawpeak,
            relative_diagnostic_eligible=eligible,
            delta_AP_mean_c=rawmean-baseline if eligible else None,
            delta_observed_AP_peak_c=rawpeak-baseline if eligible else None,validated_J=None)
        rows.append(row)
        files={'events':raw/'events.jsonl','closure':raw/'journal_closed.json','HAL':raw/'host_hal_raw.jsonl',
               'requests':raw/'requests.json','original_analysis':hits[0]}
        sources.append({'session_id':sid,'sha256':{k:sha256(p) for k,p in files.items()}})
        fingerprints.extend((p,sha256(p)) for p in files.values())
    assert sum(r['completed_MAIN_requests'] for r in rows)==2352
    pairs=[]
    for row in rows:
        control='GPU' if row['recipe']=='C252' else 'BASE'
        if row['arm']==control:continue
        baselines=[r for r in rows if (r['block'],r['recipe'],r['arm'])==(row['block'],row['recipe'],control)]
        if not baselines:continue
        b=baselines[0];eligible=row['relative_diagnostic_eligible'] and b['relative_diagnostic_eligible']
        absolute_eligible=row['original_AP_window_status']==b['original_AP_window_status']=='READOUT_WINDOW_COVERED'
        pairs.append({'block':row['block'],'recipe':row['recipe'],'candidate':row['arm'],'baseline':control,
            'both_original_AP_windows_eligible':absolute_eligible,'both_relative_windows_eligible':eligible,
            'pre_request_AP_difference_c':row['pre_request_AP_mean_c']-b['pre_request_AP_mean_c'] if row['pre_request_AP_mean_c'] is not None and b['pre_request_AP_mean_c'] is not None else None,
            'absolute_AP_mean_difference_c':row['original_AP_mean_c']-b['original_AP_mean_c'] if absolute_eligible else None,
            'absolute_AP_peak_difference_c':row['original_observed_AP_peak_c']-b['original_observed_AP_peak_c'] if absolute_eligible else None,
            'relative_AP_mean_difference_c':row['delta_AP_mean_c']-b['delta_AP_mean_c'] if eligible else None,
            'relative_AP_peak_difference_c':row['delta_observed_AP_peak_c']-b['delta_observed_AP_peak_c'] if eligible else None,
            'new_policy_or_temperature_gate_acceptance':False})
    assert all(sha256(p)==digest for p,digest in fingerprints),'original bytes changed during PC calculation'
    assert not output.exists();output.mkdir(parents=True)
    (output/'all17_sessions.csv').write_bytes(csv_bytes(rows));(output/'paired_differences.csv').write_bytes(csv_bytes(pairs))
    (output/'SOURCE_SHA256.json').write_bytes(encode({'contract_sha256':sha256(contract_path),
        'diagnostic_code_sha256':sha256(Path(__file__)),'records':sources,'raw_bytes_changed':False}))
    eligible=[r for r in rows if r['relative_diagnostic_eligible']]
    report={'status':'EXPLORATORY_PC_ONLY','sessions':len(rows),'completed_MAIN_requests':2352,
        'relative_diagnostic_eligible':len(eligible),'pre_request_AP_range_c':[min(r['pre_request_AP_mean_c'] for r in eligible),max(r['pre_request_AP_mean_c'] for r in eligible)],
        'paired_differences':pairs,'linear_thermal_response_validated':False,'internal_equilibrium_validated':False,
        'new_start_temperature_gate_accepted':False,'primary_acceptance_changed':False,
        'energy_J':None,'surface_temperature_verified':False,'device_commands':0,'new_APP_MAIN_sessions':0,
        'calculated_UTC':dt.datetime.now(dt.timezone.utc).isoformat()}
    (output/'summary.json').write_bytes(encode(report))
    print(json.dumps({'sessions':len(rows),'relative_eligible':len(eligible),'pre_request_AP_range_c':report['pre_request_AP_range_c']}))
    for p in pairs:
        if p['recipe']=='M128' and p['candidate']=='PAIR_G':print(json.dumps(p))
    return rows,report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('private_spec',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();run(load_json(args.private_spec),args.output)
