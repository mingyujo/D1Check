"""Offline A24 service, decoded-output and reported-sensor analysis; never executes ADB."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
from d1_a24_laptop_validator import load_json, sha256, validate_events

NS=1_000_000_000


def integrate_window(samples: list[tuple[int,float]], start: int, end: int, max_gap: int) -> dict:
    """Linear boundary interpolation, trapezoids; no missing-data fill or tail extrapolation."""
    values=sorted(samples)
    if len(values)<2 or not any(t<=start for t,v in values) or not any(t>=end for t,v in values):
        return {'status':'BOUNDARY_NOT_BRACKETED','integral':None}
    left=max(i for i,(t,v) in enumerate(values) if t<=start)
    right=next(i for i,(t,v) in enumerate(values) if t>=end)
    chosen=values[left:right+1]
    if any(b[0]<=a[0] or b[0]-a[0]>max_gap for a,b in zip(chosen,chosen[1:])):
        return {'status':'GAP_OR_DUPLICATE_TIMESTAMP','integral':None}
    total=0.0
    for (t,a),(u,b) in zip(chosen,chosen[1:]):
        lo,hi=max(t,start),min(u,end)
        if hi<=lo:continue
        x=a+(b-a)*(lo-t)/(u-t);y=a+(b-a)*(hi-t)/(u-t)
        total+=(x+y)*0.5*(hi-lo)/NS
    return {'status':'READOUT_WINDOW_COVERED','integral':total,'sample_count':len(chosen),
            'maximum_observed_gap_ns':max(b[0]-a[0] for a,b in zip(chosen,chosen[1:]))}


def decoded_match(result: dict, reference: dict) -> dict:
    fields=('task_id','model_id','model_sha256','image_sha256','input_tensor_sha256','adapter_contract','canonical_input_contract')
    if any(result.get(k)!=reference.get(k) for k in fields):return {'status':'BINDING_MISMATCH'}
    a,b=result.get('results',[]),reference.get('results',[])
    if not a or len(a)!=len(b):return {'status':'OUTPUT_COUNT_MISMATCH'}
    score_errors=[];box_errors=[]
    for x,y in zip(a,b):
        if x.get('label')!=y.get('label') or x.get('class_index')!=y.get('class_index'):return {'status':'LABEL_OR_ORDER_MISMATCH'}
        if not all(isinstance(v,(float,int)) and math.isfinite(v) for v in (x.get('score'),y.get('score'))):return {'status':'INVALID_SCORE'}
        score_errors.append(abs(x['score']-y['score']))
        if len(x.get('box',[]))!=len(y.get('box',[])):return {'status':'BOX_SHAPE_MISMATCH'}
        box_errors.extend(abs(v-w) for v,w in zip(x.get('box',[]),y.get('box',[])))
    # Original combined-tolerance-v1 decoded contract; not a new accuracy bound.
    good=max(score_errors)<=1e-3 and max(box_errors,default=0)<=2.0
    return {'status':'DECODED_OUTPUT_MATCH' if good else 'DECODED_TOLERANCE_FAILED',
            'maximum_score_difference':max(score_errors),'maximum_box_difference_px':max(box_errors,default=0),
            'raw_output_sha_equal':result.get('raw_output_sha256')==reference.get('raw_output_sha256'),
            'full_tensor_equivalence_tested':False}


def analyze(raw: Path, contract: dict, references: dict, logcat: str) -> dict:
    manifest=load_json(raw/'session_manifest.json');rows=load_json(raw/'requests.json')
    events=[json.loads(s) for s in (raw/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    trace=validate_events(manifest,events,rows);m=trace['metrics'];origin=m['common_origin_ns']
    transport=load_json(raw/'transport_manifest.json')
    for item in transport['files']:
        p=raw/item['path'];assert p.stat().st_size==item['bytes'] and sha256(p)==item['sha256'],'recovered file hash mismatch'
    samples=[e for e in events if e['kind']=='sensor_sample']
    hal=[json.loads(s) for s in (raw/'host_hal_raw.jsonl').read_text(encoding='utf-8').splitlines()]
    ap=[]
    for record in hal:
        readings=[s for s in record['sensors'] if s['sensor_name']==contract['AP_name'] and s['sensor_type']==contract['AP_type']]
        if len(readings)==1:ap.append(((record['device_elapsed_before_ns']+record['device_elapsed_after_ns'])//2,readings[0]['value_c']))
    thermal=integrate_window(ap,origin+35*NS,origin+180*NS,contract['AP_max_gap_ns'])
    ap_values=[v for t,v in ap if origin+35*NS<=t<=origin+180*NS]
    thermal.update(mean_reported_AP_c=thermal['integral']/145 if thermal['integral'] is not None else None,
                   highest_observed_AP_c=max(ap_values,default=None),HAL_cache_age_ns=None,
                   meaning='HAL readout at host device-clock brackets; sensor refresh age and calibration unverified')
    quality=[]
    for p in sorted(raw.glob('*.result.json')):
        result=load_json(p);ref=references['classification_CPU' if result['task_id']=='classification' else 'detection_CPU']
        quality.append(decoded_match(result,ref))
    # API-declared uA is retained as a diagnostic hypothesis, never promoted to calibrated J.
    powers=[(e['read_end_ns'],-e['current_raw']*e['voltage_raw']/1e9) for e in samples
            if isinstance(e.get('current_raw'),(int,float)) and e['current_raw']<0 and isinstance(e.get('voltage_raw'),(int,float)) and e['voltage_raw']>0 and e.get('plugged')==0]
    energy=integrate_window(powers,origin,origin+180*NS,contract['power_max_gap_ns'])
    energy.update(energy_J=None,status='CURRENT_SCALE_UNRESOLVED_ENERGY_NOT_VALIDATED',
                  API_uA_hypothesis_J=energy.pop('integral'),
                  current_scale_correction_applied=False,external_meter=False,
                  meaning='API readings conflict with charge-counter scale; no mA substitution or calibrated saving claim')
    service={}
    for task in ('C','D'):
        selected=[r for r in rows if r['request_id'] in {q['request_id'] for q in manifest['requests'] if q['task']==task}]
        successful=[r for r in selected if r['terminal_status']=='COMPLETED' and r.get('response_in_service_window') is True]
        times=sorted(r['response_complete_ns']-r['scheduled_arrival_ns'] for r in successful)
        on_time=sum(r['response_complete_ns']<=r['deadline_ns'] for r in successful)
        n=len(selected)
        service[task]={'planned':n,'completed_in_service':len(successful),'on_time':on_time,
                       'on_time_rate_all_planned':on_time/n if n else None,
                       'response_P95_ms_service_successes':times[math.ceil(.95*len(times))-1]/1e6 if times else None,
                       'not_on_time_all_planned':n-on_time}
    return {'schema':'a24-offline-measurement-analysis-v1','session_id':manifest['session_id'],'stage':manifest['stage'],
            'arm':manifest['arm'],'recipe':manifest['recipe'],'service':service,'trace':m,
            'decoded_quality':{'result_count':len(quality),'failures':sum(q['status']!='DECODED_OUTPUT_MATCH' for q in quality),
                               'maximum_score_difference':max((q.get('maximum_score_difference',0) for q in quality),default=None)},
            'GPU_delegation':{'C_full_log_observed':'Replacing 62 out of 62 node(s) with delegate (TfLiteGpuDelegateV2)' in logcat,
                              'D_full_resident_only_log_observed':'Replacing 263 out of 263 node(s) with delegate (TfLiteGpuDelegateV2)' in logcat,
                              'precision':'UNKNOWN_GPU_INTERNAL_PRECISION'},
            'thermal':thermal,'energy':energy,'calibrated_energy_or_model_accuracy_PASS':False,
            'actual_control_cost_J':None,'AP_exceedance_time_s':None,'threshold_was_not_invented':True}


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('raw',type=Path);p.add_argument('contract',type=Path)
    p.add_argument('references',type=Path);p.add_argument('logcat',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    refs={k:load_json(Path(v['path'])) for k,v in load_json(a.references).items()}
    result=analyze(a.raw,load_json(a.contract),refs,a.logcat.read_text(encoding='utf-8',errors='replace'))
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'session_id':result['session_id'],'service':result['service'],'thermal':result['thermal'],'energy':result['energy']},ensure_ascii=False))

if __name__=='__main__':main()
