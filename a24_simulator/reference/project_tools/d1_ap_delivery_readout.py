"""Read original timing evidence; no ADB, APK or device operation."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from tools import d1_ap_observation_bridge as bridge
from tools import d1_rolling_forecast as rolling

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def check_shared():
    root=rolling.h.m.ROOT/'docs/results/ap_observation_path_01'
    summary=read(root/'summary.json')
    with (root/'query_timings.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
    if len(rows)!=summary['matched_observations']:raise ValueError('timing denominator')
    for field in ('device_bracket_s','query_client_s','three_client_wait_s','triple_host_span_s','host_record_after_last_client_s'):
        values=[float(x[field]) for x in rows];expected=summary[field]
        if max(abs(float(np.median(values))-expected['median']),abs(float(np.quantile(values,.95))-expected['p95']),abs(max(values)-expected['maximum']))>1e-9:
            raise ValueError('saved timing statistics')
    cases={x['id']:x for x in rolling.h.m.read(rolling.BUNDLE/'inputs.json.gz')};frozen=rolling.h.m.read(rolling.h.m.MODEL)
    if rolling.h.m.sha(rolling.h.m.MODEL)!=rolling.h.m.MODEL_SHA:raise ValueError('frozen model')
    fixture=read(root/'forecast_fixtures.json');count=0
    for row in fixture:
        receiver=bridge.ObservationBuffer(row['session_alias'],row['manifest_sha256'],row['host_clock_id'])
        reading=bridge.from_host_record(row['record'],session_id=row['session_alias'],manifest_sha256=row['manifest_sha256'],host_clock_id=row['host_clock_id'])
        receiver.offer(reading);issue=(reading.after_ns-row['origin_ns'])/1e9;times=[issue+1,issue+5,issue+10]
        result=bridge.host_ap_forecast(cases[row['id']],frozen,receiver,origin_ns=row['origin_ns'],device_decision_ns=reading.after_ns,
                                      host_now_mono=reading.host_received_mono,host_clock_id=row['host_clock_id'],times=times)
        if result['status']!='calculated_host_diagnostic' or result['app_ready']:raise ValueError('fixture integration status')
        if receiver.app_status()['status']!='unavailable':raise ValueError('unverified app route promoted')
        count+=1
    if count!=20:raise ValueError('fixture denominator')
    print(json.dumps(dict(status='PASS',timing_rows=len(rows),sanitized_fixture_forecasts=count,new_device_commands=0,new_queries=0,android_app_ready=False)))


def analyze(external,output):
    output=Path(output)
    if output.exists():raise FileExistsError('new output required')
    output.mkdir(parents=True)
    external=Path(external);pool={};source_hashes={};scanned=0
    def load(path):
        blob=path.read_bytes();source_hashes[str(path.relative_to(external)).replace('\\','/')]=hashlib.sha256(blob).hexdigest()
        return json.loads(blob)
    roots=[external/f'energy_ap_history_recovery_run_v{i}'/'primary' for i in range(2,8)]+[external/'sustained_confirmation_run_v1']
    for root in roots:
        receipt=load(root/'FINAL_RECEIPT.json')
        for i in range(receipt['adb_commands']):
            folder=root/'host_commands'/f'{i:04d}'
            p=folder/'client/result.json'
            if not p.exists():continue
            result=read(p);scanned+=1
            if result['command'][3:]!=['shell','dumpsys','thermalservice'] or result['status']!='returned' or result['returncode']!=0:continue
            before=root/'host_commands'/f'{i-1:04d}'/'client';after=root/'host_commands'/f'{i+1:04d}'/'client'
            if not (before/'result.json').exists() or not (after/'result.json').exists():continue
            left,right=read(before/'result.json'),read(after/'result.json')
            if any(x['command'][3:]!=['exec-out','cat','/proc/uptime'] or x['status']!='returned' or x['returncode']!=0 for x in (left,right)):continue
            a=bridge.parser.parse_uptime((before/'stdout.bin').read_bytes().decode('utf-8'))
            b=bridge.parser.parse_uptime((after/'stdout.bin').read_bytes().decode('utf-8'))
            raw=(folder/'client/stdout.bin').read_bytes().decode('utf-8')
            key=(a,b,hashlib.sha256(raw.encode()).hexdigest())
            pool.setdefault(key,[]).append(dict(query_client_s=result['elapsed_seconds'],three_client_wait_s=left['elapsed_seconds']+result['elapsed_seconds']+right['elapsed_seconds'],
                triple_host_span_s=right['monotonic_end']-left['monotonic_start'],after_host_end=right['monotonic_end'],
                context_alias=root.parent.name if root.name=='primary' else root.name))
    cases=rolling.h.m.read(rolling.BUNDLE/'inputs.json.gz');rows=[];unmatched=[];gate_counts={'available':0,'unavailable':0}
    for c in cases:
        root=external/('energy_ap_history_recovery_run_v7/primary' if c['block']=='history' else 'sustained_confirmation_run_v1')
        plan=load(root/'frozen_collection_plan.json')
        entry=next(e for e in plan['entries'] if (e['phase']==c['id'] if c['block']=='history' else e['index']==int(c['id'].split('_')[-1])))
        folder=root/f"{entry['index']:02d}_{entry['session_id']}"
        boundary=load(folder/'artifacts'/('history_boundary.json' if c['block']=='history' else 'common_boundary.json'))
        origin=boundary['target_start_ns'] if c['block']=='history' else boundary['start_ns']
        p=folder/'thermal.jsonl';blob=p.read_bytes();source_hashes[c['id']+'/thermal.jsonl']=hashlib.sha256(blob).hexdigest()
        records=[json.loads(s) for s in blob.decode('utf-8').splitlines() if s]
        wanted={round(x['t'],7) for x in c['ap_observations']}
        manifest_sha=rolling.h.m.sha(folder/'input_manifest.json')
        if manifest_sha!=entry['manifest_sha256']:raise ValueError('original manifest byte identity')
        receiver=bridge.ObservationBuffer(entry['session_id'],manifest_sha,'recorded-host-scope')
        for record in records:
            if round((record['mono_ns']-origin)/1e9,7) not in wanted:continue
            sample=bridge.from_host_record(record,session_id=entry['session_id'],manifest_sha256=manifest_sha,host_clock_id='recorded-host-scope')
            accepted=receiver.offer(sample)
            gate=receiver.at(device_decision_ns=record['after_ns'],host_now_mono=record['host_monotonic'],host_clock_id='recorded-host-scope')
            gate_counts['available' if gate['status']=='available_host_diagnostic' else 'unavailable']+=1
            key=(record['before_ns'],record['after_ns'],hashlib.sha256(record['raw'].encode()).hexdigest())
            matches=pool.get(key,[])
            matches=[x for x in matches if 0<=record['host_monotonic']-x['after_host_end']<5]
            if len(matches)!=1:
                unmatched.append(dict(id=c['id'],query_index=record['index'],candidates=len(matches)));continue
            x=matches[0]
            rows.append(dict(id=c['id'],block=c['block'],role=c['role'],query_index=record['index'],t_s=(record['mono_ns']-origin)/1e9,
                             device_bracket_s=(record['after_ns']-record['before_ns'])/1e9,query_client_s=x['query_client_s'],
                             three_client_wait_s=x['three_client_wait_s'],triple_host_span_s=x['triple_host_span_s'],
                             host_record_after_last_client_s=record['host_monotonic']-x['after_host_end'],
                             receiver_offer=accepted,host_gate=gate['status'],app_received=False,app_delivery_delay_s=None))
    rolling.h.m.table(output/'query_timings.csv',rows)
    summary=dict(scanned_client_results=scanned,matched_observations=len(rows),unmatched_observations=unmatched,receiver_gate_counts=gate_counts,
                 app_delivery_delay_s=None,app_continuous_numeric_ap=False,live_host_route_attached=False,device_commands=0,android_changed=False,apk_built=False)
    for field in ('device_bracket_s','query_client_s','three_client_wait_s','triple_host_span_s','host_record_after_last_client_s'):
        values=[x[field] for x in rows]
        summary[field]=dict(median=float(np.median(values)),p95=float(np.quantile(values,.95)),maximum=max(values)) if values else None
    rolling.h.m.write(output/'summary.json',summary)
    rolling.h.m.write(output/'source_hashes.json',source_hashes)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--external');p.add_argument('--output');p.add_argument('--check-shared',action='store_true')
    args=p.parse_args()
    if args.check_shared:check_shared()
    elif args.external and args.output:analyze(args.external,args.output)
    else:p.error('supply --check-shared or --external and --output')
