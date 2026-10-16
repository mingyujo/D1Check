"""One minimally changed candidate, fixed development then fresh confirmation."""
import argparse,gzip,json,os,subprocess,time
from datetime import datetime,timezone
from tools import d1_rolling_diagnosis as diagnosis
from tools import d1_rolling_prefix_guard as x
parent=diagnosis.parent;ROOT=parent.ROOT
BUNDLE=ROOT/'docs/results/rolling_prefix_01';LOCAL=ROOT/'output/rolling_prefix_20261009_v1'
read=parent.read;write=parent.write;sha=parent.sha;utc=parent.utc
POLICIES=(parent.BAND,parent.TRITON,*parent.NEW,x.POLICY)
def events():
    p=LOCAL/'executions.jsonl'
    return [json.loads(s) for s in p.read_text(encoding='utf8').splitlines()] if p.exists() else []
def used():
    assert diagnosis.consumption()['cumulative_environment_starts']==6320
    es=events();n=sum(e['event']=='start' for e in es)
    return dict(previous_environment_starts=6320,new_environment_starts=n,cumulative_environment_starts=6320+n,
        cumulative_learning_starts=641,new_learning_starts=0,failed=sum(e['event']=='failed' for e in es),device_commands=0)
def append(event,**fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:f.write(json.dumps(dict(event=event,utc=utc(),**fields),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def seed_audit():
    wanted=('815030101','815030102');checked=0;declarations=[]
    for folder in (ROOT/'docs/results',ROOT/'output'):
        for p in folder.rglob('*'):
            if not p.is_file() or 'ie_scheduler_v2_deps' in p.parts or BUNDLE in p.parents or LOCAL in p.parents:continue
            if any(s in p.name for s in wanted):raise ValueError('consumed seed filename collision '+p.name)
            if p.suffix not in ('.json','.jsonl','.csv') or p.stat().st_size>20000000:continue
            if folder.name=='output' and p.name not in ('inputs.json','registration.json','contract.json','config.json','selection.json','executions.jsonl'):continue
            checked+=1;content=p.read_text(encoding='utf8',errors='replace')
            if any(s in content for s in wanted):
                if p==diagnosis.BUNDLE/'registration.json':declarations.append(p.relative_to(ROOT).as_posix());continue
                raise ValueError('consumed seed metadata collision '+p.relative_to(ROOT).as_posix())
    return dict(metadata_files=checked,prior_reserved_unconsumed_declarations=declarations,consumed_collisions=0,
        scope='shared JSON/CSV/local registered metadata and filenames, not unregistered external data')
def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    diagnosis.check();assert read(diagnosis.BUNDLE/'completion.json')['status']=='completed' and not (diagnosis.LOCAL/'owner.json').exists()
    inventory=seed_audit();BUNDLE.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
    old=read(parent.BUNDLE/'inputs.json');final=[dict(seed=seed,family=family,context=ctx,tickets=parent.x.fast.old.external.old.workload(family,seed)) for seed in (815030101,815030102) for family in ('low','queue','burst','sustained') for ctx in parent.x.core.CONTEXTS]
    write(BUNDLE/'inputs.json',dict(initial=old['initial'],cases=dict(development=old['cases']['development'],final=final)))
    sources=dict(read(diagnosis.BUNDLE/'registration.json')['sources'])
    for p in ('tools/d1_rolling_prefix_guard.py','tools/test_d1_rolling_prefix_guard.py','tools/d1_rolling_prefix_study.py'):sources[p]=sha(ROOT/p)
    reg=dict(task='IE-ROLLING-PREFIX-GUARD-02',registered_utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        sources=sources,inputs_sha256=sha(BUNDLE/'inputs.json'),diagnosis_sha256=sha(diagnosis.BUNDLE/'diagnosis.json'),seed_inventory=inventory,
        policies=list(POLICIES),development_conditions=24,final_conditions=24,environment_cap=160,expected_environment_starts=146,
        expected_breakdown=dict(fixtures=2,development_new=24,development_reused=96,final=120),wall_seconds=1800,save_reserve_seconds=300,prior=used(),
        change='exactly one extra full-arrived-queue3-context guard of actual first single/pair/cooling/resourcewait plus nativeBand suffix; cancel tentative hold/pending/cooling on failure and returnBand',
        preserved='old window4, mean shortlist8, per-task EDD, credit0.25, phase5 capacity, mean/short/long predictors, originalW/AP/preload/SLA/quality/default/strict',
        tuning_budget='one candidate, zero new fitted weights or thresholds; justified by development12/527 selected-plan prefix AP violations and zero lost best among24 selected shortlist snapshots',
        selection='all24 development service/J/AP nonworse vs bothBand/Triton and primary low/sustained heat gain in eachseed; freeze before final, never select from final',
        evaluation='all requests retained, common120sJ/AP35..180s1sgrid, absolute completion/deadlines plus paired service costs, host control time separate; unsupported surface/safety/controlJ null',
        representative=dict(seed=815030101,family='sustained',context='mean'),learning_starts=0,device_commands=0,NPU=False,experiment_ready=False)
    write(BUNDLE/'registration.json',reg);return reg
def check():
    reg=read(BUNDLE/'registration.json')
    for p,h in reg['sources'].items():assert sha(ROOT/p)==h,p
    assert sha(BUNDLE/'inputs.json')==reg['inputs_sha256'];assert sha(diagnosis.BUNDLE/'diagnosis.json')==reg['diagnosis_sha256'];return reg
def deadline():
    r=check();elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(r['registered_utc'])).total_seconds()
    if elapsed>=r['wall_seconds']-r['save_reserve_seconds']:raise TimeoutError('prefix study save boundary')
    return time.monotonic()+r['wall_seconds']-r['save_reserve_seconds']-elapsed
def simulate(frozen,initial,case,policy):
    if policy in (parent.BAND,parent.TRITON):return parent.previous.parent.parent.prior.x.micro.simulate(frozen,initial,case['tickets'],case['context'],policy)
    c=x.Controller(frozen,initial) if policy==x.POLICY else parent.x.Controller(frozen,initial,policy)
    c.execution_deadline=deadline();profile=parent.x.p.profile(frozen,case['context']);vectors=dict(cells={k:[dict(source_request_id='rolling_prefix_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in profile.items()})
    return parent.x.fast.old.external.old.engine.simulate(dict(protocol=parent.x.p.VERSION,cells=parent.x.p.profile(frozen)),vectors,case['tickets'],policy=c.policy,settings=parent.x.fast.old.external.settings(),seed=201,decision_provider=c),c
def execute(case,policy,identity):
    target=LOCAL/'items'/(identity.replace('/','__')+'.json.gz');target.parent.mkdir(exist_ok=True)
    if target.exists():
        done=[r for r in events() if r['event']=='completed' and r['identity']==identity];assert len(done)==1 and sha(target)==done[0]['artifact_sha256'];return json.loads(gzip.decompress(target.read_bytes()))
    deadline();u=used();assert u['new_environment_starts']<160 and u['cumulative_environment_starts']<20000
    assert not any(r['event']=='start' and r['identity']==identity for r in events());append('start',identity=identity,number=u['new_environment_starts']+1);began=time.perf_counter()
    try:
        frozen,_=parent.x.p.inputs(parent.x.p.BUNDLE);initial=read(BUNDLE/'inputs.json')['initial'];result,c=simulate(frozen,initial,case,policy)
        parent.audit.audit(result,case['tickets']);row,curves=parent.audit.metrics(result,c,initial,frozen)
        row.update(seed=case['seed'],family=case['family'],context=case['context'],policy=policy,identity=identity,host_wall_s=time.perf_counter()-began,
            prefix_checks=len(getattr(c,'prefix_guard_records',[])),prefix_blocked_calls=getattr(c,'prefix_blocked_calls',0))
        item=dict(row=row,result=result,curves=curves,plans=getattr(c,'plan_records',[]),prefix_guards=getattr(c,'prefix_guard_records',[]))
        target.write_bytes(gzip.compress(json.dumps(item,allow_nan=False).encode(),mtime=0));append('completed',identity=identity,artifact_sha256=sha(target));return item
    except BaseException as e:append('failed',identity=identity,error=repr(e));raise
def reuse(i,policy):
    row=next(r for r in read(parent.BUNDLE/'development_rows.json') if r['identity']==f'development/{i}/{policy}')
    if not any(r['event']=='reused' and r['identity']==row['identity'] for r in events()):append('reused',identity=row['identity'],source_shared_sha256=sha(parent.BUNDLE/'development_rows.json'))
    return row
def select(rows):
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};group=[r for r in rows if r['policy']==x.POLICY];good=0;seeds=set();pairs=[]
    for r in group:
        ps=[parent.compare(r,by[r['seed'],r['family'],r['context'],p]) for p in POLICIES[:2]];pairs+=ps;good+=all(p['nonworse'] for p in ps)
        if r['family'] in ('low','sustained') and all(p['heat_gain'] for p in ps):seeds.add(r['seed'])
    eligible=good==24 and seeds=={813010101,813010102}
    return dict(utc=utc(),chosen=x.POLICY if eligible else None,eligible=eligible,nonworse_conditions=good,primary_heat_gain_seeds=len(seeds),worst_AP_delta=max(p['delta_peak_ap_c'] for p in pairs),final_consumed=False)
def run():
    prepare()
    if (BUNDLE/'completion.json').exists():return read(BUNDLE/'completion.json')
    owner=LOCAL/'owner.json';assert not owner.exists();write(owner,dict(pid=os.getpid(),utc=utc()));data=read(BUNDLE/'inputs.json')
    try:
        from tools.test_d1_ie_dispatch import ticket
        case=dict(seed=0,family='fixture',context='mean',tickets=[ticket('c0',0),ticket('d0',1,'detection',35.,6.),ticket('c1',2),ticket('d1',3,'detection',35.,6.)])
        for p in (parent.BAND,x.POLICY):
            r=execute(case,p,'fixture/'+p)['row'];assert r['planned']==r['completed']==4 and r['urgent_service_failure']==r['normal_service_failure']==0
        write(BUNDLE/'fixture_verification.json',dict(status='PASS',native_starts=2,planned_completed=8))
        rows=[]
        for i,case in enumerate(data['cases']['development']):
            for p in POLICIES:rows.append(execute(case,p,f'development/{i}/{p}')['row'] if p==x.POLICY else reuse(i,p))
        write(BUNDLE/'development_rows.json',rows)
        if not (BUNDLE/'selection.json').exists():write(BUNDLE/'selection.json',select(rows))
        rows=[]
        for i,case in enumerate(data['cases']['final']):
            for p in POLICIES:rows.append(execute(case,p,f'final/{i}/{p}')['row'])
            print(json.dumps(dict(split='final',done=i+1,total=24,starts=used()['new_environment_starts'])),flush=True)
        write(BUNDLE/'final_rows.json',rows);write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=used(),development_reused_rows=96,final_rows=120))
        return read(BUNDLE/'completion.json')
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','status']);a=p.parse_args()
    if a.command=='prepare':print(json.dumps(prepare(),indent=2))
    elif a.command=='run':print(json.dumps(run(),indent=2))
    else:print(json.dumps(used(),indent=2))
