"""PC-only research design check. No Run, ADB, claim or candidate fitting."""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = Path(__file__).resolve().parent
load = lambda p: json.loads(p.read_text(encoding='utf-8'))
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def check(plan_file):
    study = load(BUNDLE/'completion_study.json')
    plan_file = Path(plan_file); plan = load(plan_file)
    assert digest(plan_file) == study['existing_collection_plan_sha256']
    assert not Path(plan['registry']).exists() and not Path(plan['output_root']).exists()
    assert all(digest(ROOT/k) == v for k,v in plan['source_code'].items())
    assert digest(Path(plan['apk_path'])) == study['apk_sha256']
    assert digest(Path(plan['memory_candidate']['path'])) == study['existing_candidate_sha256']
    source = load(plan_file.parent/plan['entries'][1]['manifest'])['requests']
    assert len(source) == 24
    b = study['budget']; per = plan['budget']
    assert b['sessions'] == b['blocks']*b['sessions_per_block'] == 12
    assert b['requests'] == 8*24 and b['warmup'] == 12*8
    assert b['explicit_inference'] == b['requests']+b['warmup'] == 288
    assert b['runtime_creations'] == 12*4 and b['staging_files'] == 12*7
    assert b['device_block_limit_seconds'] == 600+6*(120+485+50+45)+5*90 == per['total_seconds']
    assert b['device_total_limit_seconds'] == 2*per['total_seconds'] == 10500
    assert b['active_work_limit_seconds'] == b['device_total_limit_seconds']+b['pc_freeze_limit_seconds']
    assert b['adb_commands'] == 2*(6*3200+200) == 38800
    assert b['fixed_observation_seconds'] == 12*(30+120+60)
    assert b['intersession_idle_seconds'] == 2*5*90
    assert all(b[k]==0 for k in ['apk_transfers','installs','retry','replacement','additional'])
    schedules={}
    for condition in ['C','L35','L65','L50','SPLIT_DELAY30']:
        rows=[] if condition=='C' else copy.deepcopy(source)
        for row in rows:
            shift=30 if condition=='L65' or condition=='SPLIT_DELAY30' and row['ordinal']>=12 else 15 if condition=='L50' else 0
            row['release_offset_ns']+=shift*1_000_000_000
            assert row['offset_ms']*1_000_000 <= row['release_offset_ns'] < 120_000_000_000
            original=source[row['ordinal']]
            for key in ['offset_ms','task_id','priority','recorded_backend','deadline_ms']:
                assert row[key]==original[key]
        schedules[condition]=rows
    design=[]
    for phase in ['development','confirmation']:
        order=study[phase+'_order']
        assert len(order)==6
        for condition in set(order):
            assert sum(i+1 for i,c in enumerate(order) if c==condition)/2 == 3.5
        for i,condition in enumerate(order):
            rows=schedules[condition];times=[r['release_offset_ns']/1e9 for r in rows]
            design.append(dict(phase=phase,ordinal=i+1,condition=condition,work=len(rows),warmup=8,
                first_release_s=min(times) if times else None,last_release_s=max(times) if times else None,
                initialization_cutoff_s=35,fixed_observation_s=210))
    assert sum(r['work'] for r in design)==b['requests']
    assert schedules['L50'] not in [schedules['L35'],schedules['L65']]
    assert schedules['SPLIT_DELAY30'] not in [schedules['L35'],schedules['L65'],schedules['L50']]
    for condition,rows in schedules.items():
        assert not rows or min(r['release_offset_ns'] for r in rows)>35_000_000_000
    return dict(study_sha256=digest(BUNDLE/'completion_study.json'),plan_sha256=digest(plan_file),
        base_head='1f828ae07160cd8edf60ef0d101fb72291637046',uncommitted_documents=True,
        checks=['budget arithmetic','frozen plan and sources unchanged','frozen APK/candidate unchanged',
        'production output and registry absent','same arrivals, backend, priority, deadlines',
        'release offsets within fixed common window','same pre35 initialization','condition order balance',
        'heldout releases differ from development'],device_commands=0,fit_count=0,
        execution_ready=False,meaning='Design checks, not runtime/Android/identifiability or prediction validation',
        budget=b,design=design)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=check(a.plan)
    if a.output.exists():raise FileExistsError('fresh PC design output required')
    a.output.mkdir(parents=True)
    (a.output/'design_check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    with (a.output/'session_design.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(result['design'][0]));w.writeheader();w.writerows(result['design'])
    print(json.dumps({k:result[k] for k in ['study_sha256','device_commands','fit_count','execution_ready']}))
