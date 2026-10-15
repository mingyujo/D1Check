"""Offline, aligned-interval battery readout forensics; no fitted correction.

The inventory contains local paths and stays private. Outputs retain file hashes
and logical dataset names only. Both gauge APIs are unvalidated, not ground truth.
"""
import argparse
import collections
import csv
from decimal import Decimal
import json
import math
from pathlib import Path
import statistics
from d1_a24_laptop_validator import load_json, sha256, NS
from d1_a24_measurement_analysis import integrate_window


def write_csv(path,rows):
    columns=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,columns);w.writeheader();w.writerows(rows)


def select_lossless_copies(items):
    """One longest stream only when every shorter recovery is its exact prefix.

    Outcome/measurement values never select the copy. Divergent bytes fail closed.
    Keep every input digest and byte count; no source file is changed or deleted.
    """
    grouped=collections.defaultdict(list)
    for item in items:grouped[item['session_id']].append(item)
    selected=[];audit=[]
    for sid,copies in grouped.items():
        ordered=sorted(copies,key=lambda x:Path(x['path']).stat().st_size,reverse=True)
        longest=Path(ordered[0]['path']).read_bytes();selected.append(ordered[0])
        for index,item in enumerate(ordered):
            data=Path(item['path']).read_bytes()
            assert longest.startswith(data),'divergent event copies; cannot silently choose a recovery'
            audit.append({'session_id':sid,'root_label':item['root_label'],'events_sha256':sha256(Path(item['path'])),
                'bytes':len(data),'selected':index==0,'selection_rule':'longest exact-prefix stream; no outcome selection',
                'selected_events_sha256':sha256(Path(ordered[0]['path'])),
                'relationship':'SELECTED' if index==0 else 'IDENTICAL' if data==longest else 'EXACT_SHORTER_PREFIX'})
    return selected,audit


def aligned_interval(samples, begin=None, end=None):
    selected=[s for s in samples if (begin is None or s['read_end_ns']>=begin) and (end is None or s['read_end_ns']<=end)]
    result={'samples':len(selected),'energy_J':None,'correction_applied':False,'independent_ground_truth':False}
    if len(selected)<2:return result|{'status':'INSUFFICIENT_SAMPLES'}
    assert all(type(s['read_end_ns']) is int and type(s['read_start_ns']) is int for s in selected)
    times=[s['read_end_ns'] for s in selected];gaps=[b-a for a,b in zip(times,times[1:])]
    result.update(first_ns=times[0],last_ns=times[-1],duration_s=(times[-1]-times[0])/NS,
        maximum_sample_gap_s=max(gaps)/NS,median_sample_gap_s=statistics.median(gaps)/NS,
        read_latency_p95_ms=sorted((s['read_end_ns']-s['read_start_ns'])/1e6 for s in selected)[math.ceil(.95*len(selected))-1],
        charging_or_unknown_samples=sum(s.get('plugged')!=0 for s in selected),
        invalid_samples=sum(type(s.get('current_raw')) is not int or type(s.get('charge_counter_raw')) is not int for s in selected))
    if result['invalid_samples']:return result|{'status':'NULL_OR_INVALID_RAW_SAMPLE'}
    currents=[s['current_raw'] for s in selected];charges=[s['charge_counter_raw'] for s in selected]
    changes=[(b['read_end_ns'],b['charge_counter_raw']-a['charge_counter_raw']) for a,b in zip(selected,selected[1:]) if b['charge_counter_raw']!=a['charge_counter_raw']]
    steps=[abs(d) for t,d in changes];change_gaps=[(b[0]-a[0])/NS for a,b in zip(changes,changes[1:])]
    gcd=0
    for step in steps:gcd=math.gcd(gcd,step)
    result.update(raw_current_median=statistics.median(currents),positive_current_samples=sum(i>0 for i in currents),
        raw_charge_first=charges[0],raw_charge_last=charges[-1],raw_charge_drop=charges[0]-charges[-1],
        charge_distinct_levels=len(set(charges)),charge_change_count=len(changes),charge_increase_count=sum(d>0 for t,d in changes),
        smallest_charge_step_raw=min(steps,default=None),largest_charge_step_raw=max(steps,default=None),charge_step_gcd_raw=gcd or None,
        observed_charge_change_gap_median_s=statistics.median(change_gaps) if change_gaps else None,
        observed_charge_change_gap_min_s=min(change_gaps,default=None),observed_charge_change_gap_max_s=max(change_gaps,default=None))
    if result['charging_or_unknown_samples']:return result|{'status':'CHARGING_OR_UNKNOWN_NOT_COMPARED'}
    if min(gaps)<=0 or max(gaps)>2_500_000_000:return result|{'status':'GAP_OR_NONMONOTONIC_NOT_FILLED'}
    # Independent decimal trapezoid on the EXACT SAME endpoint samples.
    q=sum((Decimal(-(a['current_raw']+b['current_raw']))*Decimal(b['read_end_ns']-a['read_end_ns'])/
           Decimal(2*NS*3600) for a,b in zip(selected,selected[1:])),Decimal(0))
    conventional=integrate_window([(s['read_end_ns'],-s['current_raw']) for s in selected],times[0],times[-1],2_500_000_000)['integral']/3600
    assert math.isclose(float(q),conventional,rel_tol=1e-12,abs_tol=1e-12),'independent numerical integration disagrees'
    result.update(status='DIAGNOSTIC_UNITS_UNVERIFIED',current_integral_declared_uAh=float(q),
        charge_drop_declared_uAh=charges[0]-charges[-1],
        required_scale_NOT_A_CALIBRATION=float(Decimal(charges[0]-charges[-1])/q) if q>0 else None,
        independent_decimal_integrator_agrees=True,current_units_claimed='uA_API_DEVICE_UNVERIFIED',charge_units_claimed='uAh_API_DEVICE_UNVERIFIED')
    return result


def export(inventory,out,reference_csv):
    input_items=load_json(inventory);items,copy_audit=select_lossless_copies(input_items)
    out.mkdir(parents=True,exist_ok=False)
    all_rows=[];changes=[];sources=[];seen={};raw_by_session={};duplicates=[]
    for item in items:
        path=Path(item['path']);digest=sha256(path);sid=item['session_id'];key=(sid,digest)
        if key in seen:
            duplicates.append({'session_id':sid,'events_sha256':digest,'same_bytes_as_existing':True});continue
        seen[key]=True
        events=[json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
        samples=[s for s in events if s['kind']=='sensor_sample']
        raw_by_session.setdefault(sid,[]).append(samples)
        head={k:item[k] for k in ['root_label','session_id','recipe','arm','stage','resident_mode','APK_sha256','sensor_period_ms']}
        sources.append(head|{'events_sha256':digest,'manifest_sha256':sha256(Path(item['manifest'])),'sensor_samples':len(samples)})
        bounds=[('FULL_RECORDED',None,None)]
        ready=path.parent/'ready.json';starts=[e['mono_ns'] for e in events if e['kind']=='common_start']
        origin=load_json(path.parent/'summary.json').get('common_start_ns') if (path.parent/'summary.json').exists() else None
        if origin is None and starts:origin=starts[0]
        if ready.exists():
            rn=load_json(ready)['ready_ns'];bounds.append(('POST_READY_APP_NO_INFERENCE',rn,origin))
        if origin is not None:
            bounds.extend([('COMMON_0_180',origin,origin+180*NS),('COMMON_PREFIX_APP_IDLE_0_35',origin,origin+35*NS)])
            ends=[e.get('lane_available_ns',e['mono_ns']) for e in events if e['kind']=='lane_available']
            if ends:
                bounds.extend([('REGISTERED_REQUEST_FLOW',origin+35*NS,max(ends)),('POST_REQUEST_APP_IDLE',max(ends),None)])
        for label,begin,end in bounds:
            all_rows.append(head|{'events_sha256':digest,'segment':label}|aligned_interval(samples,begin,end))
        for a,b in zip(samples,samples[1:]):
            if type(a.get('charge_counter_raw')) is int and type(b.get('charge_counter_raw')) is int and a['charge_counter_raw']!=b['charge_counter_raw']:
                changes.append(head|{'events_sha256':digest,'read_end_ns':b['read_end_ns'],'elapsed_from_first_sample_s':(b['read_end_ns']-samples[0]['read_end_ns'])/NS,'previous_raw':a['charge_counter_raw'],'current_raw':b['charge_counter_raw'],'delta_raw':b['charge_counter_raw']-a['charge_counter_raw'],'battery_current_raw':b.get('current_raw'),'plugged':b.get('plugged')})
    reference=[]
    if reference_csv:
        with reference_csv.open(encoding='utf-8-sig',newline='') as f:csv_rows=list(csv.DictReader(f))
        grouped=collections.defaultdict(list)
        for row in csv_rows:grouped[row['session_id']].append(row)
        fields=['read_start_ns','read_end_ns','current_raw','voltage_raw','charge_counter_raw','plugged']
        for sid,csv_samples in grouped.items():
            candidates=raw_by_session.get(sid,[])
            matched=[]
            for raw_samples in candidates:
                by_time={str(s['read_end_ns']):s for s in raw_samples};good=True
                for row in csv_samples:
                    src=by_time.get(row['read_end_ns'])
                    if src is None or any(str(src.get(k))!=row[k] for k in fields):good=False;break
                if good:matched.append(raw_samples)
            assert len(matched)==1,'published CSV does not uniquely match raw integers'
            normalized=[{k:int(r[k]) for k in fields} for r in csv_samples]
            reference.append({'session_id':sid,'CSV_rows':len(csv_samples),'CSV_to_events_integer_fields_exact':True,
                'CSV_sha256':sha256(reference_csv)}|aligned_interval(normalized))
    write_csv(out/'intervals.csv',all_rows);write_csv(out/'counter_changes.csv',changes)
    write_csv(out/'source_inventory.csv',sources);write_csv(out/'duplicate_copies.csv',duplicates);write_csv(out/'published_CSV_recalculation.csv',reference)
    write_csv(out/'lossless_copy_selection.csv',copy_audit)
    (out/'verification.json').write_text(json.dumps({'status':'OFFLINE_DIAGNOSTIC_NOT_ENERGY_CALIBRATION','script_sha256':sha256(Path(__file__)),
        'input_event_files':len(input_items),'selected_lossless_streams':len(items),
        'excluded_identical_or_prefix_copies':len(input_items)-len(items),
        'unique_session_event_versions':len(sources),'unique_session_ids':len({s['session_id'] for s in sources}),
        'identical_duplicate_copies':len(duplicates),'diagnostic_intervals':len(all_rows),'published_CSV_exact_verified':bool(reference),
        'arithmetic_tolerance':'1e-12 relative/absolute for independent floating/decimal integrator agreement only; not sensor error tolerance',
        'device_commands':0,'calibrated_energy_J':None,'scale_correction_applied':False,
        'actual_hardware_sensor_age_verified':False,'new_independent_model_validation':False,
        'no_inference_segments':'app has no model invocation; does not imply entire phone is electrically idle'},indent=2),encoding='utf-8')
    print(json.dumps({'event_versions':len(sources),'intervals':len(all_rows),'published_CSV':reference,'device_commands':0},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('inventory',type=Path);p.add_argument('output',type=Path);p.add_argument('--reference-csv',type=Path);a=p.parse_args();export(a.inventory,a.output,a.reference_csv)
