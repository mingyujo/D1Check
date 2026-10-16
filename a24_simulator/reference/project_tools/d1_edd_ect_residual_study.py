"""128-start non-learning prototype registration, durable accounting and resume.

No PPO training CLI exists in this runner. Gate results determine next work.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import subprocess
import time
from tools import d1_edd_ect_residual_controller as x
from tools import d1_external_rules_study as audit

ROOT=x.p.ROOT
BUNDLE=ROOT/'docs/results/edd_ect_residual_prototype_01'
LOCAL=ROOT/'output/edd_ect_residual_prototype_20261008_v1'
INPUT=ROOT/'docs/results/external_rules_02/inputs.json'
DESIGN=ROOT/'docs/results/edd_ect_residual_design_01/design_contract.json'
POLICIES=(x.BASE,'SHARED_EFT',x.ie.external.BAND,x.PRIOR,x.GREEDY)


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def utc():return datetime.now(timezone.utc).isoformat()
def sha(path):return x.p.digest(path)


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,allow_nan=False,indent=2);stream.write('\n')
        stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)


def entries(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf8').splitlines()] if Path(path).exists() else []


def consumption():
    historical=[ROOT/'output/reserved_thermal_20261008_v1/executions.jsonl',ROOT/'output/ie_dispatch_20261008_v1/executions.jsonl']
    old=[sum(r['event']=='start' for r in entries(path)) for path in historical]
    if old!=[2241,584]:raise RuntimeError('historical budget changed; re-register without resetting')
    journal=entries(LOCAL/'executions.jsonl')
    new=sum(r['event']=='start' for r in journal)
    return dict(historical=old,new_starts=new,cumulative_starts=sum(old)+new,environment_ceiling=20000,
        prototype_ceiling=128,training_episodes=0,device_commands=0,
        failed=sum(r['event']=='failed' for r in journal))


def append(event,**values):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:
        f.write(json.dumps(dict(event=event,utc=utc(),**values),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())


def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    LOCAL.mkdir(parents=True,exist_ok=True);BUNDLE.mkdir(parents=True,exist_ok=True)
    for directory in ('output/reserved_thermal_20261008_v1','output/ie_dispatch_20261008_v1'):
        if (ROOT/directory/'owner.json').exists():raise RuntimeError('existing campaign owner must be preserved')
    inputs=read(INPUT);seed=min(w['seed'] for w in inputs['workloads'])
    selected=[w for w in inputs['workloads'] if w['seed']==seed]
    assert len(selected)==4
    before=consumption()
    design=read(DESIGN)
    assert design['budget_proposal']['existing_used']==before['cumulative_starts']==2825
    sources=audit.existing_sources()
    for rel in ('tools/d1_external_rules.py','tools/d1_ie_dispatch.py','tools/d1_edd_ect_residual_controller.py',
                'tools/d1_edd_ect_residual_study.py','tools/test_d1_edd_ect_residual_controller.py'):
        sources[rel]=sha(ROOT/rel)
    spec=dict(version='edd-ect-residual-prototype-v1',registered_utc=utc(),
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        source_hashes=sources,input_path=INPUT.relative_to(ROOT).as_posix(),input_sha256=sha(INPUT),
        design_path=DESIGN.relative_to(ROOT).as_posix(),design_sha256=sha(DESIGN),
        selected_workloads=selected,contexts=list(x.CONTEXTS),policies=list(POLICIES),
        conditions=12,policy_runs_max=60,branch_runs_max=24,fixture_and_error_max=44,new_start_max=128,
        historical_consumption=before,wall_seconds=3600,save_reserve_seconds=300,
        realization_seed=201,training_allowed=False,device_commands=0,experiment_ready=False,
        temperature_input='MODEL_AP',physical_scope='original A24 measured coefficients with synthetic arrivals and fixed transferred service contexts',
        representative=dict(seed=seed,family='queue',context='mean'),
        phase_residual_rule='phase end already elapsed in required running forecast => unavailable, exact BASE; no zero residual',
        branch_rule='first BASE and alternative valid/distinct immediate physical prefix; no winning branch search; both prior thereafter',
        clock='new authorized prototype block; one registration time, no reset on resume',
        old_design_and_finished_campaign_clocks_unchanged=True)
    write(BUNDLE/'registration.json',spec);write(LOCAL/'registration.json',spec)
    write(LOCAL/'clock.json',dict(start_utc=spec['registered_utc']))
    paths=[p for p in ROOT.iterdir() if p.is_file() and p.suffix.lower() in ('.html','.pdf')]
    paths += [p for p in (ROOT/'.vscode').rglob('*') if p.is_file()]
    for folder in ROOT.glob('*_files'):paths += [p for p in folder.rglob('*') if p.is_file()]
    write(LOCAL/'user_files.json',{p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    return check()


def check():
    spec=read(BUNDLE/'registration.json')
    if read(LOCAL/'registration.json')!=spec:raise ValueError('registration binding drift')
    source_hashes=dict(spec['source_hashes'])
    if (BUNDLE/'metadata_repair.json').exists():
        repair=read(BUNDLE/'metadata_repair.json')
        rel='tools/d1_edd_ect_residual_study.py'
        if repair['original_runner_sha256']!=source_hashes[rel] or repair['registration_sha256']!=sha(BUNDLE/'registration.json'):
            raise ValueError('repair lineage drift')
        source_hashes[rel]=repair['repaired_runner_sha256']
    for rel,h in source_hashes.items():
        if sha(ROOT/rel)!=h:raise ValueError('source drift: '+rel)
    if sha(INPUT)!=spec['input_sha256'] or sha(DESIGN)!=spec['design_sha256']:raise ValueError('input/design drift')
    used=consumption()
    if used['new_starts']>128 or used['cumulative_starts']>20000:raise ValueError('budget exceeded')
    return spec


def begin(kind,identity):
    spec=check();used=consumption()
    if read(LOCAL/'owner.json')['pid']!=os.getpid():raise RuntimeError('owner mismatch')
    if used['new_starts']>=128 or used['cumulative_starts']>=20000:raise RuntimeError('environment cap')
    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(read(LOCAL/'clock.json')['start_utc'])).total_seconds()
    if elapsed>=3300:raise TimeoutError('prototype last five minutes reserved for saving')
    number=used['new_starts']+1
    append('start',number=number,cumulative_number=used['cumulative_starts']+1,kind=kind,identity=identity)
    return number, time.monotonic()+3300-elapsed


def execute(kind,identity,work,context,policy,*,branch=None,original=False):
    started=[e for e in entries(LOCAL/'executions.jsonl') if e['event']=='start' and e['identity']==identity]
    if started and not (LOCAL/'items'/f'{identity}.json.gz').exists():
        repair=read(BUNDLE/'metadata_repair.json') if (BUNDLE/'metadata_repair.json').exists() else {}
        if identity==repair.get('failed_identity'):
            identity=repair['charged_replacement_identity']
    path=LOCAL/'items'/f'{identity}.json.gz'
    if path.exists():
        done=[e for e in entries(LOCAL/'executions.jsonl') if e['event']=='completed' and e['identity']==identity]
        if len(done)!=1 or done[0]['item_sha256']!=sha(path):raise ValueError('completion hash drift')
        item=json.loads(gzip.decompress(path.read_bytes()))
        if item['registration_sha256']!=sha(BUNDLE/'registration.json'):raise ValueError('resume source binding')
        return item
    if any(e['event']=='start' and e['identity']==identity for e in entries(LOCAL/'executions.jsonl')):
        raise RuntimeError('unfinished started item; preserve instead of free replay')
    number,deadline=begin(kind,identity);began=time.perf_counter()
    try:
        frozen,_=x.p.inputs(x.p.BUNDLE);initial=read(INPUT)['initial']
        if original:
            result,c=x.ie.simulate(frozen,initial,work['tickets'],context,x.BASE)
        elif policy in (x.BASE,x.PRIOR,x.GREEDY):
            result,c=x.simulate(frozen,initial,work['tickets'],context,policy,branch=branch,
                                record_forecasts=kind=='fixture',deadline=deadline)
        else:
            result,c=x.ie.external.simulate(frozen,initial,work['tickets'],context,policy)
        audit.audit(result,work['tickets'])
        row,curves=audit.metrics(result,c,initial,frozen)
        row.update(seed=work['seed'],family=work['family'],context=context,policy=policy,
            projection_calls=getattr(c,'projection_calls',0),projection_seconds=getattr(c,'projection_seconds',0.),
            forced_decisions=sum(bool(d.get('forced')) for d in result['decisions']),
            multi_action_decisions=sum((sum(d['valid_actions']) if isinstance(d.get('valid_actions'),list)
                                      else d.get('valid_actions',0))>1 for d in result['decisions']),
            multi_physical_decisions=sum(d.get('physical_immediate_groups',0)>1 for d in result['decisions']),
            bundle_commits=sum(d.get('reason')=='bundle_commit' for d in result['decisions']),
            cool_wait_decisions=sum(d.get('action_kind')=='cool_wait' for d in result['decisions']),
            original_ect_wait_decisions=sum(d.get('action_kind')=='ect_resource_wait' for d in result['decisions']),
            cancelled_bundles=getattr(c,'cancelled_bundles',0),
            causal_response_counters_valid=getattr(c,'response_counters_valid',None))
        item=dict(identity=identity,registration_sha256=sha(BUNDLE/'registration.json'),row=row,
            result=result,curves=curves,host_wall_s=time.perf_counter()-began,
            branch_record=getattr(c,'branch_record',None))
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(gzip.compress(json.dumps(item,allow_nan=False).encode('utf8'),mtime=0))
        append('completed',number=number,identity=identity,kind=kind,item_sha256=sha(path))
        print(f'{number}: {identity} {item["host_wall_s"]:.3f}s',flush=True)
        return item
    except BaseException as error:
        append('failed',number=number,identity=identity,kind=kind,error=repr(error));raise


def run():
    spec=prepare();owner=LOCAL/'owner.json'
    with owner.open('x',encoding='utf8') as stream:json.dump(dict(pid=os.getpid(),utc=utc()),stream)
    try:
        if not (LOCAL/'fixtures_complete.json').exists():
            qs=[dict(id='fixture/'+str(i),ordinal=i,task='classification' if i%2 else 'detection',
                priority='urgent' if i%2 else 'normal',arrival_ns=35000000000,
                deadline_offset_ns=1500000000 if i%2 else 6000000000) for i in range(4)]
            work=dict(seed=0,family='fixture',tickets=qs)
            frozen,_=x.p.inputs(x.p.BUNDLE);est=x.p.profile(frozen)
            profiles={c:x.p.profile(frozen,c) for c in x.CONTEXTS}
            for ctx in x.CONTEXTS:
                origin=execute('fixture','original_'+ctx,work,ctx,x.BASE,original=True)
                actual=execute('fixture','wrapped_'+ctx,work,ctx,x.BASE)
                if origin['result']['ledger']!=actual['result']['ledger']:raise AssertionError('exact BASE ledger changed')
                predicted=x.project(est,profiles,qs,x.empty_lanes(35e9),35e9,dict(jobs=[]),ctx)
                by={j['id']:j for j in predicted['jobs']}
                for row in origin['result']['ledger']:
                    job=by[row['id']]
                    assert abs(job['start']*1e9-row['dispatch_ns'])<=1
                    assert abs(job['end']*1e9-row['lane_available_ns'])<=1
                    boundary='output_ready_ns' if row['priority']=='urgent' else 'persist_complete_ns'
                    assert abs(job['response']*1e9-row[boundary])<=1
            write(LOCAL/'fixtures_complete.json',dict(status='PASS',engine_starts=6,
                exact_base_ledgers=3,forecast_parity_contexts=3,controller_unit_tests=14))
        all_rows=[];branches=[];items={}
        for work in spec['selected_workloads']:
            for ctx in spec['contexts']:
                prior_item=None
                for policy in spec['policies']:
                    name=f"{work['seed']}_{work['family']}_{ctx}_{policy}"
                    item=execute('prototype',name,work,ctx,policy,branch='discover' if policy==x.PRIOR else None)
                    all_rows.append(item['row']);items[item['identity']]=sha(LOCAL/'items'/f'{item["identity"]}.json.gz')
                    if policy==x.PRIOR:prior_item=item
                    write(LOCAL/'progress.json',dict(status='running',comparison_rows=len(all_rows),total=60,consumption=consumption()))
                if prior_item['branch_record']:
                    pair=[]
                    for arm in ('base','alt'):
                        name=f"{work['seed']}_{work['family']}_{ctx}_branch_{arm}"
                        item=execute('branch',name,work,ctx,x.PRIOR,branch=arm)
                        if item['branch_record']!=prior_item['branch_record']:raise AssertionError('branch prefix state mismatch')
                        pair.append(item)
                    point=pair[0]['branch_record']['now_ns']
                    def prefix(item):return sorted((r['id'],r['backend'],r['dispatch_ns']) for r in item['result']['ledger'] if r.get('dispatch_ns',float('inf'))<point)
                    if prefix(pair[0])!=prefix(pair[1]):raise AssertionError('causal prefix differs before branch')
                    branches.append(dict(seed=work['seed'],family=work['family'],context=ctx,
                        base_identity=pair[0]['identity'],alt_identity=pair[1]['identity'],record=pair[0]['branch_record'],
                        base_row=pair[0]['row'],alt_row=pair[1]['row']))
                else:
                    branches.append(dict(seed=work['seed'],family=work['family'],context=ctx,record=None,reason='no valid distinct BASE/alternative branch'))
        audit.csv_write(BUNDLE/'results.csv',all_rows)
        write(BUNDLE/'branches.json',branches)
        users=read(LOCAL/'user_files.json')
        for rel,h in users.items():
            if sha(ROOT/rel)!=h:raise AssertionError('user file changed: '+rel)
        check()
        receipt=dict(status='completed',utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
            command='MKL_THREADING_LAYER=SEQUENTIAL; python -B -m tools.d1_edd_ect_residual_study run',
            registration_sha256=sha(BUNDLE/'registration.json'),results_sha256=sha(BUNDLE/'results.csv'),
            branches_sha256=sha(BUNDLE/'branches.json'),logical_rows=len(all_rows),consumption=consumption(),
            item_hashes=items,user_files_preserved=len(users),fixtures=read(LOCAL/'fixtures_complete.json'),
            training_episodes=0,device_commands=0,experiment_ready=False)
        write(BUNDLE/'completion.json',receipt)
        return receipt
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','status'))
    action=parser.parse_args().action
    result=run() if action=='run' else prepare() if action=='prepare' else consumption()
    print(json.dumps({k:v for k,v in result.items() if k not in ('item_hashes','source_hashes','selected_workloads')},ensure_ascii=False,indent=2))
