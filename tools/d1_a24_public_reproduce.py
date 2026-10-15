"""Recompute service/AP/output checks from committed public ZIPs, on PC only.

The public replay headers are explicitly not original device identity manifests.
This repeats event/capacity/clock/KPI math, not private identity authorization or
sensor calibration. No ADB, inference, fitting, or alteration of source archives.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path,PurePosixPath
import zipfile

from d1_a24_laptop_validator import load_json,validate_events
from d1_a24_measurement_analysis import decoded_match,integrate_window,NS
from d1_a24_measurement_report import save_csv
from d1_a24_revision02_suite import require

ROOT=Path(__file__).resolve().parents[1]


def verified_members(path,expected_sha):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==expected_sha,'public archive SHA differs')
    with zipfile.ZipFile(path) as z:
        names=z.namelist();require(len(names)==len(set(names)),'duplicate ZIP member')
        require(all(not n.startswith('/') and '..' not in PurePosixPath(n).parts and '\\' not in n for n in names),'unsafe ZIP path')
        require(sum(i.file_size for i in z.infolist())<=256*1024*1024,'public block exceeds bounded raw size')
        index=json.loads(z.read('FILE_SHA256.json'))['members']
        require(isinstance(index,list),'not a measurement block ZIP')
        require(set(names)=={r['path'] for r in index}|{'FILE_SHA256.json'},'unindexed archive member')
        values={}
        for item in index:
            b=z.read(item['path']);require(len(b)==item['bytes'] and hashlib.sha256(b).hexdigest()==item['sha256'],'member SHA differs')
            values[item['path']]=b
    return values


def metrics(manifest,files,quality_refs):
    sid=manifest['session_id'];prefix='raw/'+sid+'/'
    events=[json.loads(s) for s in files[prefix+'events.jsonl'].splitlines()]
    requests=json.loads(files[prefix+'requests.json']);trace=validate_events(manifest,events,requests)['metrics'];origin=trace['common_origin_ns']
    require(json.loads(files[prefix+'journal_closed.json'])['status']=='SYNCED_AND_CLOSED','public normal app journal not closed')
    hal=[json.loads(s) for s in files[prefix+'host_hal_raw.jsonl'].splitlines()];points=[]
    for r in hal:
        values=[x['value_c'] for x in r['sensors'] if (x['sensor_name'],x['sensor_type'])==('AP',0)]
        if len(values)==1:points.append(((r['device_elapsed_before_ns']+r['device_elapsed_after_ns'])//2,values[0]))
    thermal=integrate_window(points,origin+35*NS,origin+180*NS,10*NS)
    result={'planned':len(manifest['requests']),'completed':trace['completed_in_service'],'failed':trace['failed'],'unfinished':trace['unfinished'],
        'mean_AP_c':thermal['integral']/145 if thermal['integral'] is not None else None,
        'observed_peak_AP_c':max((v for t,v in points if origin+35*NS<=t<=origin+180*NS),default=None),
        'thermal_window_status':thermal['status'],'actual_overlap_s':trace['actual_pair_overlap_ns']/NS,
        'actual_WAIT_s':trace['wait_actual_ns']/NS,'energy_J':None}
    for task in ['C','D']:
        ids={r['request_id'] for r in manifest['requests'] if r['task']==task};selected=[r for r in requests if r['request_id'] in ids]
        complete=[r for r in selected if r['terminal_status']=='COMPLETED' and r.get('response_in_service_window') is True]
        response=sorted(r['response_complete_ns']-r['scheduled_arrival_ns'] for r in complete)
        ontime=sum(r['response_complete_ns']<=r['deadline_ns'] for r in complete);n=len(selected)
        result.update({task+'_planned':n,task+'_on_time':ontime,task+'_on_time_rate_all_planned':ontime/n if n else None,
            task+'_response_P95_ms_service_successes':response[math.ceil(.95*len(response))-1]/1e6 if response else None})
    quality=[]
    for name,b in files.items():
        if name.startswith(prefix) and name.endswith('.result.json'):
            r=json.loads(b);q=quality_refs['classification_CPU' if r['task_id']=='classification' else 'detection_CPU'];quality.append(decoded_match(r,q))
    require(len(quality)==len(manifest['requests']),'public normal result files missing')
    result.update(decoded_quality_failures=sum(q['status']!='DECODED_OUTPUT_MATCH' for q in quality),
        decoded_result_count=len(quality),event_capacity_clock_and_boundaries_replayed=True)
    return result


def run(contractfile,out,repo_root=ROOT):
    cfg=load_json(contractfile);require(cfg['schema']=='a24-public-replay-contract-v1','wrong public replay contract')
    require(cfg['private_device_identity_authorization_reproduced'] is False and cfg['energy_J'] is None,'do not claim private identity or J calibration')
    require(not out.exists(),'fresh public reproduction output required');files={};zipchecks=[]
    for archive in cfg['archives']:
        path=(repo_root/archive['repo_relative_path']).resolve();require(path.is_relative_to(repo_root.resolve()),'archive outside repository')
        part=verified_members(path,archive['sha256'])
        for name,b in part.items():
            if name.startswith(('raw/','public_manifests/','supplemental_same_run_raw/')):
                require(name not in files or files[name]==b,'different original bytes for repeated public member');files[name]=b
        zipchecks.append({'repo_relative_path':archive['repo_relative_path'],'sha256':archive['sha256'],'members_verified':len(part)})
    rows=[]
    for item in cfg['sessions']:
        manifest=item['public_event_replay_manifest'];sid=manifest['session_id'];status=item['original_status']
        row={k:manifest.get(k) for k in ['session_id','stage','block','recipe','arm','policy_id']}
        row.update(family=item['family'],analysis_role=item['analysis_role'],status=status,planned=len(manifest['requests']),completed=0,
            normal_comparison_eligible=status=='COMPLETE_TRACE_RECOVERED',energy_J=None)
        if status=='COMPLETE_TRACE_RECOVERED':
            # The public projection and the replay header must agree wherever
            # both carry a field. Missing private fields are never invented.
            projection=json.loads(files['public_manifests/'+sid+'.json'])
            require(all(projection[k]==v for k,v in manifest.items() if k in projection),'header/projection mismatch')
            row.update(metrics(manifest,files,cfg['quality_references']))
        rows.append(row)
    out.mkdir(parents=True);save_csv(out/'reproduced_sessions.csv',rows)
    summary={'status':'PUBLIC_ZIP_KPI_REPRODUCED_NO_DEVICE_IDENTITY_OR_J_CALIBRATION',
        'sessions':len(rows),'normal':sum(r['normal_comparison_eligible'] for r in rows),'all_planned_requests':sum(r['planned'] for r in rows),
        'normal_completed_requests':sum(r['completed'] for r in rows),'decoded_quality_failures':sum(r.get('decoded_quality_failures',0) for r in rows),
        'archives':zipchecks,'contract_sha256':hashlib.sha256(contractfile.read_bytes()).hexdigest(),
        'reproducer_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'event_validator_sha256':hashlib.sha256((ROOT/'tools/d1_a24_laptop_validator.py').read_bytes()).hexdigest(),
        'analysis_code_sha256':hashlib.sha256((ROOT/'tools/d1_a24_measurement_analysis.py').read_bytes()).hexdigest(),
        'private_device_identity_authorization_reproduced':False,'J_calibrated':False,'surface_temperature_verified':False,'device_commands':0}
    (out/'VERIFICATION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary))
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('public_contract',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--repo-root',type=Path,default=ROOT);a=p.parse_args();run(a.public_contract,a.output,a.repo_root)
