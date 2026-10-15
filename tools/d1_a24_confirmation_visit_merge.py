"""Build a new private, read-only analysis snapshot of closed CONFIRM visits.

No experiment execution, source changes, replay or raw edits. Copies retain bytes.
An active visit must finish before this tool can create a combined final snapshot.
"""
import argparse
import json
from pathlib import Path
import shutil
from d1_a24_laptop_validator import load_json, sha256
from d1_a24_laptop_control import atomic_json


def copy_exact(source, target):
    if source.is_symlink():
        raise ValueError('symlink source not accepted')
    if target.exists():
        if source.read_bytes()!=target.read_bytes():
            raise ValueError('different bytes at shared analysis path: '+target.name)
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
    if sha256(source)!=sha256(target):raise ValueError('copy verification failed')


def merge(job_paths, out):
    if out.exists():raise FileExistsError('new snapshot required')
    jobs=[load_json(p) for p in job_paths]
    first=jobs[0];plan=load_json(Path(first['plan']))
    if plan['stage']!='CONFIRM' or len(plan['sessions'])!=40:raise ValueError('original CONFIRM40 required')
    expected={r['session_id']:r for r in plan['sessions']}
    visits=[];seen=set();records=[]
    same=['plan','budget_file','confirm_freeze','analysis_contract','pre_measurement_predictions',
          'source_manifest','apk_identity','quality_references']
    for job_path,job in zip(job_paths,jobs):
        for key in same:
            if sha256(Path(job[key]))!=sha256(Path(first[key])):raise ValueError('visit contract mismatch: '+key)
        root=Path(job['run_root'])
        if not (root/'WINDOW_STOPPED.json').is_file():raise ValueError('active/unclosed visit; no final snapshot')
        outcomes=[(p,load_json(p)) for p in sorted(root.glob('*.outcome.json'))]
        for p,row in outcomes:
            sid=row['session_id']
            if sid in seen or sid not in expected:raise ValueError('duplicate/foreign attempted identity')
            seen.add(sid)
            if row['status']=='COMPLETE_TRACE_RECOVERED' and not (root/'raw'/sid/'journal_closed.json').is_file():
                raise ValueError('complete outcome lacks raw closure')
            records.append(dict(session_id=sid,visit=root.name,status=row['status'],outcome_sha256=sha256(p)))
        visits.append((root,outcomes))
    # Validate all source contracts/identities before writing anything.
    out.mkdir(parents=True,exist_ok=False)
    raw_root=out/'combined';raw_root.mkdir()
    provenance=[];audit=[]
    for root,outcomes in visits:
        for p,row in outcomes:
            sid=row['session_id'];copy_exact(p,raw_root/p.name)
            for name in ['raw','registry']:
                source=root/name
                if source.exists():
                    for item in source.rglob('*'):
                        if item.is_file() and (name=='registry' or item.relative_to(source).parts[0]==sid):
                            copy_exact(item,raw_root/name/item.relative_to(source))
            log=root/'logcat'/(sid+'.txt')
            if log.exists():copy_exact(log,raw_root/'logcat'/log.name)
        for name in ['references','pre_app_cooldown_v2']:
            source=root/name
            if source.exists():
                for item in source.rglob('*'):
                    if item.is_file():copy_exact(item,raw_root/name/item.relative_to(source))
        p=root/'adb_commands.jsonl'
        if p.exists():audit.extend(p.read_bytes().splitlines())
        provenance.append(dict(visit=root.name,stop_sha256=sha256(root/'WINDOW_STOPPED.json')))
    (raw_root/'adb_commands.jsonl').write_bytes(b'\n'.join(audit)+b'\n')
    job=first|dict(run_root=str(raw_root.resolve()),read_only_analysis_snapshot=True)
    atomic_json(out/'job.json',job)
    atomic_json(out/'provenance.json',dict(plan_sha256=sha256(Path(first['plan'])),visits=provenance,
        records=records,attempted_outcomes=len(records),full_plan=40,raw_modified=False,device_commands=0))
    print(json.dumps({'status':'PRIVATE_ANALYSIS_SNAPSHOT','attempted_outcomes':len(records),'device_commands':0}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    parser.add_argument('jobs',type=Path,nargs='+');args=parser.parse_args();merge(args.jobs,args.output)
