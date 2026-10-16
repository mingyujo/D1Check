"""V21 arrival-only relative-load comparison; immutable V20 engine and policy."""
import argparse
import collections
import csv
import json
from pathlib import Path
import shutil
from tools import d1_sched_landscape_study as parent
from tools import d1_sched_relative_load_cases as inputs

ROOT=parent.ROOT;BASE=parent.BASE
TASK='D1-SCHED-RELLOAD-21'
WORK=BASE/'work'/TASK;OUT=BASE/'outputs'/TASK
WORK20=BASE/'work/D1-SCHED-LANDSCAPE-20'
OUT20=BASE/'outputs/D1-SCHED-LANDSCAPE-20'
SHARDS=('S26_seed0','S26_seed1')
save=parent.save;read=parent.read;sha=parent.sha;digest=parent.digest;utc=parent.utc


def register():
    if (WORK/'registration.json').exists():raise ValueError('already registered')
    old=read(WORK20/'registration.json');parent.material_checks(old)
    bundle=inputs.build(read(WORK20/'inputs/cases.json'))
    new=bundle['new_cases'];after=bundle['after_cases']
    if len(new)!=30 or len(after)!=96:raise ValueError('expected30 changed S26 and96 after cases')
    save(WORK/'inputs/cases.json',new);save(WORK/'inputs/after_cases.json',after)
    save(OUT/'inputs/cases.json',new);save(OUT/'inputs/after_cases.json',after)
    save(OUT/'input_transformations.json',bundle['transformations']);save(OUT/'generation_metadata.json',bundle['metadata'])
    shutil.copy2(WORK20/'profiles.json',WORK/'profiles.json');shutil.copy2(WORK20/'profiles.json',OUT/'profiles.json')
    sources=dict(old['sources'])
    for name in ('d1_sched_relative_load_study.py','d1_sched_relative_load_cases.py'):
        path=ROOT/'tools'/name;sources[str(path)]=sha(path)
    parents=dict(old['parents'])
    for path in (WORK20/'registration.json',WORK20/'inputs/cases.json',WORK20/'profiles.json',OUT20/'all_rows.csv',OUT20/'manifest.json',OUT20.parent/'D1-SCHED-LANDSCAPE-20-runtime.zip'):
        parents[str(path)]=sha(path)
    seeds=old['seed_order'];caps={shard:sum(parent.belongs(c,shard,seeds) for c in new)*7 for shard in SHARDS}
    reg=dict(task=TASK,created_utc=utc(),head=old['head'],sources=sources,parents=parents,dependencies=old['dependencies'],
             inputs={str(p):sha(p) for p in (WORK/'inputs/cases.json',WORK/'inputs/after_cases.json',WORK/'profiles.json')},
             cases=30,after_view_cases=96,roles=old['roles'],environments=210,portable_environments_planned=2,environment_cap_all=212,
             seed_order=seeds,shard_cap=caps,selected=old['selected'],shards=list(SHARDS),wall_cap_per_worker_s=1200,
             unique_reused_environments=672,after_view_reused_environments=462,policy_training=0,native_updates=0,optimizer_steps=0,
             profile_or_policy_change=False,physical_environment_seed_formula_unchanged=True,
             purpose='isolate S26 arrival-span floor effects by matching the corresponding A24 nominal load',
             target_definition='current-neutral public nominal lane capacity / declared activity span; not actual hot-stage utilization',
             execution_reuse='unchanged raw byte hashes reused; no A24 or unchanged S26 rerun',
             fit=0,device=0,apk=0,external_messages=0,parameter_tuning_from_results=False)
    save(WORK/'registration.json',reg);save(OUT/'registration.json',reg)
    save(OUT/'PPO_TRANSFER_NOTICE.json',dict(selected=reg['selected'],weights_updated=False,trained_on_relative_load21=False,
         policy_schema=parent.policy.SCHEMA,training_dependencies_source='original17',original20_control_preserved=True))
    for path in sources:
        target=OUT/'source'/Path(path).name;target.parent.mkdir(exist_ok=True);shutil.copy2(path,target)
    print(dict(task=TASK,new_cases=30,new_environments=210,reused_raw=672,shards=caps,new_learning=0))


def configure():
    # Reuse unchanged executable code, while isolating paths/budget in memory.
    parent.TASK=TASK;parent.WORK=WORK;parent.OUT=OUT;parent.SHARDS=SHARDS;parent.WALL=1200


def collect():
    reg=read(WORK/'registration.json');parent.material_checks(reg);rows=[];receipts=[];cons={}
    for shard in SHARDS:
        cons[shard]=read(OUT/f'consumption_{shard}.json')
        with (OUT/f'rows_{shard}.csv').open(encoding='utf-8-sig',newline='') as f:rows.extend(csv.DictReader(f))
        receipts.extend(json.loads(line) for line in (WORK/'shards'/shard/'environment_receipts.jsonl').read_text().splitlines())
    if len(rows)!=210 or {int(r['number']) for r in rows}!=set(range(1,211)):raise ValueError('210 new rows required')
    if collections.Counter(r['status'] for r in receipts)!=dict(started=210,completed=210):raise ValueError('new receipt counts')
    rows.sort(key=lambda r:int(r['number']));parent.previous.csvout(OUT/'all_rows.csv',rows)
    receipts.sort(key=lambda r:(r['number'],r['status']=='completed'))
    for path in (WORK/'environment_receipts.jsonl',OUT/'environment_receipts.jsonl'):
        path.write_text(''.join(json.dumps(r)+'\n' for r in receipts),encoding='utf-8')
    save(OUT/'consumption.json',dict(environments_started=210,environments_completed=210,environments_failed=0,
         policy_training=0,native_updates=0,optimizer_steps=0,fit=0,device=0,apk=0,external_messages=0,
         shards=cons,maximum_workers=2,unique_reused_environments=672,after_view_reused=462))
    with (OUT20/'all_rows.csv').open(encoding='utf-8-sig',newline='') as f:prior=list(csv.DictReader(f))
    expected=read(OUT20/'manifest.json')['files'];reference=OUT/'reference'
    before=[]
    for old in prior:
        origin=OUT20/old['path']
        if sha(origin)!=old['raw_sha'] or old['raw_sha']!=expected[old['path'].replace('\\','/')]['sha256']:raise ValueError('parent raw changed')
        target=reference/old['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(origin,target)
        before.append(dict(old,path=str(target.relative_to(OUT)),source_task='D1-SCHED-LANDSCAPE-20',environment_number=old['number'],reused='True'))
    old_by_case={(r['case'],r['role']):r for r in before};new_by_case={(r['case'],r['role']):r for r in rows}
    after=[];aliases=[]
    for ci,case in enumerate(read(WORK/'inputs/after_cases.json')):
        changed=case['identity'].endswith('_RELLOAD21')
        for ri,role in enumerate(reg['roles']):
            source=new_by_case[case['identity'],role] if changed else old_by_case[case['identity'],role]
            value=dict(source,number=str(ci*7+ri+1),source_task=TASK if changed else 'D1-SCHED-LANDSCAPE-20',environment_number=source['number'],reused=str(not changed))
            after.append(value);aliases.append(dict(evaluation_number=value['number'],case=case['identity'],role=role,source_task=value['source_task'],source_environment_number=value['environment_number'],raw_sha=value['raw_sha'],reused=not changed))
    if len(before)!=672 or len(after)!=672 or sum(r['reused']=='True' for r in after)!=462:raise ValueError('paired view counts')
    parent.previous.csvout(OUT/'before_rows.csv',before);parent.previous.csvout(OUT/'after_rows.csv',after)
    save(OUT/'view_lineage.json',dict(unique_new=210,unique_reused=672,before_views=672,after_views=672,after_new=210,after_reused=462,aliases=aliases))
    print(dict(status='ALL_COMPLETE',new_environments=210,reused_unique=672,after_views=672,new_learning=0))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('register','execute','collect'));parser.add_argument('--shard',choices=SHARDS)
    args=parser.parse_args()
    if args.stage=='register':register()
    elif args.stage=='collect':collect()
    elif not args.shard:parser.error('--shard required')
    else:
        configure();parent.execute(args.shard)


if __name__=='__main__':main()
