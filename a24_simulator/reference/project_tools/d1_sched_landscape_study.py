"""Separate, policy-neutral scheduling sensitivity experiment; fixed inference."""
import argparse
import collections
import copy
import csv
import gzip
import json
from pathlib import Path
import shutil
import time
import torch
from tools import d1_sched_dynamics_study as previous
from tools import d1_sched_dynamics_policy as policy
from tools import d1_sched_dynamics_ppo as rl
from tools import d1_sched_landscape_plant as plant
from tools import d1_sched_landscape_cases as cases

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT.parent.parent
TASK='D1-SCHED-LANDSCAPE-20'
WORK=BASE/'work'/TASK
OUT=BASE/'outputs'/TASK
SOURCE17=BASE/'work/D1-SCHED-DYNAMICS-17'
OUT17=BASE/'outputs/D1-SCHED-DYNAMICS-17'
ROLES=(*policy.RULES,'PPO_TRANSFER')
SHARDS=('A24','S26_seed0','S26_seed1')
WALL=1800
save=previous.save
read=previous.read
sha=previous.sha
digest=previous.digest
utc=previous.utc


def belongs(case,shard,seed_order):
    if shard=='A24':return case['device']=='A24'
    return case['device']=='S26' and case['arrival_seed']==seed_order[int(shard[-1])]


def register():
    if (WORK/'registration.json').exists():raise ValueError('already registered')
    # Generation APIs are filled in before registration; no environment runs here.
    bundle=cases.build(read(BASE/'work/D1-SCHED-CONTRAST-18/profiles.json'))
    profiles=bundle['profiles'];grid=bundle['cases']
    if len(grid)!=96 or len({c['identity'] for c in grid})!=96:raise ValueError('96 cases required')
    old=read(SOURCE17/'registration.json')
    sources=dict(old['sources'])
    for filename in ('d1_sched_landscape_plant.py','d1_sched_landscape_cases.py','d1_sched_landscape_study.py','d1_sched_landscape_cli.py','test_d1_sched_landscape_plant.py'):
        path=ROOT/'tools'/filename;sources[str(path)]=sha(path)
    parents=dict(old['parents'])
    for path in (BASE/'work/D1-SCHED-CONTRAST-18/profiles.json',OUT17/'selected_before_final.json',OUT17.parent/'D1-SCHED-DYNAMICS-17-contrast-runtime.zip'):
        parents[str(path)]=sha(path)
    selection=read(OUT17/'selected_before_final.json')
    selected=next(c for c in selection['selected'] if c['seed']==selection['representative'])
    parents[selected['path']]=selected['sha']
    save(WORK/'profiles.json',profiles);save(WORK/'inputs/cases.json',grid)
    save(OUT/'profiles.json',profiles);save(OUT/'inputs/cases.json',grid)
    save(OUT/'generation_metadata.json',bundle['metadata'])
    seeds=sorted({c['arrival_seed'] for c in grid})
    if len(seeds)!=2:raise ValueError('two arrival seeds required')
    reg=dict(task=TASK,created_utc=utc(),head='12d64923be824ce4c88fca074fbe38820f5a7d25',
             sources=sources,parents=parents,dependencies=old['dependencies'],
             inputs={str(p):sha(p) for p in (WORK/'profiles.json',WORK/'inputs/cases.json')},
             cases=96,roles=list(ROLES),environments=672,portable_environments_planned=2,environment_cap_all=674,shards=list(SHARDS),seed_order=seeds,
             shard_cap={s:sum(belongs(c,s,seeds) for c in grid)*len(ROLES) for s in SHARDS},
             wall_cap_per_worker_s=WALL,maximum_workers=3,torch_threads_per_worker=1,
             selected=selected,policy_training=0,fit=0,device=0,apk=0,external_messages=0,
             objective='increase scheduling-dependent energy, heat and service contrasts in declared hypothetical worlds',
             parameter_selection_from_this_run=False,policy_specific_environment_parameters=False,
             timings_scope='concurrent PC workers; do not compare with prior single-worker latency or phone cost')
    save(WORK/'registration.json',reg);save(OUT/'registration.json',reg)
    for path in sources:
        dst=OUT/'source'/Path(path).name;dst.parent.mkdir(exist_ok=True);shutil.copy2(path,dst)
    save(OUT/'PPO_TRANSFER_NOTICE.json',dict(selected=selected,weights_updated=False,
         training_environment='original17 neutral/mild/full',evaluated_environment=TASK,
         policy_schema=policy.SCHEMA,known_route_power_features_added=False,
         attribution='registered selected checkpoint loaded for every worker; each raw records checkpoint SHA'))
    print(json.dumps(dict(registered=TASK,cases=96,environments=672,shards=reg['shard_cap'],new_learning=0)))


def material_checks(reg):
    for kind in ('sources','parents','dependencies','inputs'):
        for path,expected in reg[kind].items():
            if sha(path)!=expected:raise ValueError('registered material changed:'+path)


class AuditedController(previous.AuditedController):
    def choose(self,dev,waiting):
        public=dev.public()
        result=super().choose(dev,waiting)
        item=self.audit[-1]
        item.pop('sensor_age_s',None)
        item.update(thermal_age_s=public['thermal_observation_age_s'],
                    power_age_s=public['power_observation_age_s'],
                    observed_ap_c=public['ap_c'],observed_power_w=public['power_w'])
        if not 0<=item['thermal_age_s']<=2.0000001 or not 0<=item['power_age_s']<=.9000001:
            raise ValueError('noncausal sensor timing')
        return result


def execute(shard):
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    reg=read(WORK/'registration.json');material_checks(reg)
    shardwork=WORK/'shards'/shard;shardwork.mkdir(parents=True,exist_ok=True)
    receiptpath=shardwork/'environment_receipts.jsonl'
    if receiptpath.exists():raise ValueError('shard already consumed; never repeat environments')
    original=read(SOURCE17/'registration.json')
    dependencies={Path(p).name:h for p,h in original['sources'].items() if p.endswith('.py')}
    dependencies.update(policy_schema=policy.SCHEMA,profiles=sha(SOURCE17/'profiles.json'))
    learner=rl.Learner.load(reg['selected']['path'],dependencies)
    snapshot=rl.canonical(learner.snapshot())
    profiles=read(WORK/'profiles.json');grid=read(WORK/'inputs/cases.json')
    rows=[];start=time.perf_counter();cap=reg['shard_cap'][shard]
    def receipt(**row):
        with receiptpath.open('a',encoding='utf-8') as f:f.write(json.dumps(dict(at_utc=utc(),**row))+'\n')
    for ci,case in enumerate(grid):
        if not belongs(case,shard,reg['seed_order']):continue
        profile=profiles[case['device']][case['profile']]
        for ri,role in enumerate(ROLES):
            if time.perf_counter()-start>WALL-60 or len(rows)>=cap:raise ValueError('worker finite budget before next environment')
            number=ci*len(ROLES)+ri+1;identity=f'{role}_{case["identity"]}';tick=time.perf_counter()
            receipt(number=number,identity=identity,status='started',training=False)
            try:
                inner=policy.Controller(role,previous.affinity(profile)) if role in policy.RULES else learner.controller(deterministic=True,collect=False)
                ctl=AuditedController(inner)
                envseed=948400000+case['arrival_seed']%100000
                raw=plant.simulate(profile,case['requests'],ctl,split='confirm',environment_seed=envseed)
                verification=previous.physical_audit(raw,case['requests'])
                cost=raw['cost_120']
                pieces=cost['activation_energy_j']+cost['parallel_extra_energy_j']+cost['idle_tail_energy_j']+cost['active_route_extra_energy_j']
                if abs(cost['additional_energy_j']-pieces)>1e-7:raise ValueError('additional energy decomposition')
                raw.update(identity=identity,case=case,role=role,phase='LANDSCAPE',
                           decisions=ctl.decisions,decision_audits=ctl.audit,verification=verification,
                           model_errors=ctl.errors,checkpoint_sha=reg['selected']['sha'] if role=='PPO_TRANSFER' else None,
                           policy_training=False,online_learning=False)
                path=OUT/'raw'/f'{number:04}_{role}.json.gz';path.parent.mkdir(exist_ok=True)
                with gzip.open(path,'wt',encoding='utf-8',compresslevel=4) as f:json.dump(raw,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
                row=dict(number=number,phase='LANDSCAPE',role=role,case=case['identity'],device=case['device'],profile=case['profile'],
                         family=case['family'],task_mix=case['task_mix'],deadline_mode=case['deadline_mode'],arrival_seed=case['arrival_seed'],
                         request_sha=case['request_sha256'],path=str(path.relative_to(OUT)),raw_sha=sha(path),ledger_sha=digest(raw['ledger']),events_sha=digest(raw['events']),**raw['metrics'])
                row.update(additional_energy_j=cost['additional_energy_j'],anchor_energy_j=cost['anchor_energy_j'],
                           active_route_extra_energy_j=cost['active_route_extra_energy_j'],
                           activation_energy_j=cost['activation_energy_j'],parallel_extra_energy_j=cost['parallel_extra_energy_j'],idle_tail_energy_j=cost['idle_tail_energy_j'],
                           decisions=len(ctl.decisions),mask_audits=len(ctl.audit),model_errors=len(ctl.errors),active_pc_s=time.perf_counter()-tick)
                table=OUT/f'rows_{shard}.csv';exists=table.exists()
                with table.open('a',encoding='utf-8' if exists else 'utf-8-sig',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=list(row))
                    if not exists:writer.writeheader()
                    writer.writerow(row)
                rows.append(row)
            except Exception as error:
                receipt(number=number,identity=identity,status='failed',error=repr(error));raise
            receipt(number=number,identity=identity,status='completed',training=False,path=row['path'],sha=row['raw_sha'],active_pc_s=time.perf_counter()-tick)
        if len(rows)%28==0:
            value=dict(task=TASK,shard=shard,completed=len(rows),planned=cap,elapsed_pc_s=time.perf_counter()-start,at_utc=utc())
            save(OUT/f'progress_{shard}.json',value);print(json.dumps(value),flush=True)
    if len(rows)!=cap or snapshot!=rl.canonical(learner.snapshot()):raise ValueError('shard count or frozen learner changed')
    save(OUT/f'consumption_{shard}.json',dict(environments_started=len(rows),environments_completed=len(rows),environments_failed=0,
         policy_training=0,native_updates=0,optimizer_steps=0,fit=0,device=0,apk=0,external_messages=0,
         elapsed_pc_s=time.perf_counter()-start,frozen_learner_snapshot_unchanged=True))
    print(json.dumps(dict(shard=shard,status='COMPLETE',environments=len(rows))),flush=True)


def collect():
    reg=read(WORK/'registration.json');material_checks(reg);rows=[];receipts=[];counts={}
    for shard in SHARDS:
        counts[shard]=read(OUT/f'consumption_{shard}.json')
        with (OUT/f'rows_{shard}.csv').open(encoding='utf-8-sig',newline='') as f:rows.extend(csv.DictReader(f))
        receipts.extend(json.loads(line) for line in (WORK/'shards'/shard/'environment_receipts.jsonl').read_text().splitlines())
    if len(rows)!=672 or {int(r['number']) for r in rows}!=set(range(1,673)):raise ValueError('672 distinct rows required')
    if collections.Counter(r['status'] for r in receipts)!=dict(started=672,completed=672):raise ValueError('receipt counts')
    rows.sort(key=lambda r:int(r['number']));previous.csvout(OUT/'all_rows.csv',rows)
    receipts.sort(key=lambda r:(r['number'],r['status']=='completed'))
    for path in (WORK/'environment_receipts.jsonl',OUT/'environment_receipts.jsonl'):
        path.write_text(''.join(json.dumps(r)+'\n' for r in receipts),encoding='utf-8')
    save(OUT/'consumption.json',dict(environments_started=672,environments_completed=672,environments_failed=0,
         policy_training=0,native_updates=0,optimizer_steps=0,fit=0,device=0,apk=0,external_messages=0,
         shards=counts,maximum_workers=3,worker_elapsed_sum_s=sum(r['elapsed_pc_s'] for r in counts.values())))
    print(json.dumps(dict(status='ALL_COMPLETE',environments=672,learning=0)))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('register','execute','collect'));parser.add_argument('--shard',choices=SHARDS)
    args=parser.parse_args()
    if args.stage=='register':register()
    elif args.stage=='collect':collect()
    elif not args.shard:parser.error('--shard is required')
    else:execute(args.shard)


if __name__=='__main__':main()
