"""Conditional small development pilot; no fresh evaluation unless eligible."""
import argparse,gzip,json,os,subprocess,time
from datetime import datetime,timezone
from tools import d1_rolling_terminal_study as probe
x=probe.x;parent=probe.parent;ROOT=parent.ROOT
BUNDLE=ROOT/'docs/results/rolling_terminal_01/pilot';LOCAL=ROOT/'output/rolling_terminal_pilot_20261009_v1'
read=parent.read;write=parent.write;sha=parent.sha;utc=parent.utc
POLICIES=(parent.parent.BAND,parent.parent.TRITON,parent.x.POLICY,x.POLICY)
def events():
    p=LOCAL/'executions.jsonl';return [json.loads(s) for s in p.read_text(encoding='utf8').splitlines()] if p.exists() else []
def used():
    assert probe.used()['cumulative_environment_starts']==6491
    es=events();n=sum(e['event']=='start' for e in es)
    return dict(previous_environment_starts=6491,new_environment_starts=n,cumulative_environment_starts=6491+n,cumulative_learning_starts=641,new_learning_starts=0,
        failed=sum(e['event']=='failed' for e in es),device_commands=0)
def append(event,**fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:f.write(json.dumps(dict(event=event,utc=utc(),**fields),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    probe.check();done=read(probe.BUNDLE/'completion.json');assert done['status']=='completed' and done['followup_allowed'] and not (probe.LOCAL/'owner.json').exists()
    BUNDLE.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
    sources=dict(read(probe.BUNDLE/'registration.json')['sources']);sources.update(read(probe.BUNDLE/'repair.json')['source_overrides']);sources['tools/d1_rolling_terminal_pilot.py']=sha(__file__)
    r=dict(task='IE-ROLLING-TERMINAL-03-PILOT',registered_utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,sources=sources,
        input_sha256=sha(probe.BUNDLE/'inputs.json'),probe_sha256=sha(probe.BUNDLE/'probe_records.json.gz'),probe_completion_sha256=sha(probe.BUNDLE/'completion.json'),
        policies=list(POLICIES),prior=used(),expected_environment_starts=26,environment_cap=40,wall_seconds=1800,save_reserve_seconds=300,
        scope='one terminal-guard candidate on the same development24 conditions; 72 parent rows reused, new26=24candidate+2four-request fixtures; not independent validation',
        one_change='first-prefix service/J/AP guard unchanged; add common-time T/h constraint all3contexts. Original g=0 and all inputs/profile/window/credit/coefficients unchanged.',
        selection='all24 service/J/AP nonworse vs bothBand/Triton and low/sustained heat gain each developmentseed; freeze. If ineligible or allBand ledger equality, stop with no fresh final or training. Eligible candidate may receive a separately registered small fresh confirmation.',
        no_new_weights_limits_or_tuning=True,device_commands=0,new_learning=0,experiment_ready=False)
    write(BUNDLE/'registration.json',r);return r
def check():
    r=read(BUNDLE/'registration.json')
    for p,h in r['sources'].items():assert sha(ROOT/p)==h,p
    assert sha(probe.BUNDLE/'inputs.json')==r['input_sha256'] and sha(probe.BUNDLE/'probe_records.json.gz')==r['probe_sha256']
    assert sha(probe.BUNDLE/'completion.json')==r['probe_completion_sha256'];return r
def deadline():
    r=check();elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(r['registered_utc'])).total_seconds()
    if elapsed>=r['wall_seconds']-r['save_reserve_seconds']:raise TimeoutError('terminal pilot save boundary')
    return time.monotonic()+r['wall_seconds']-r['save_reserve_seconds']-elapsed
def execute(case,policy,identity):
    target=LOCAL/'items'/(identity.replace('/','__')+'.json.gz');target.parent.mkdir(exist_ok=True)
    if target.exists():
        es=[e for e in events() if e['event']=='completed' and e['identity']==identity];assert len(es)==1 and sha(target)==es[0]['artifact_sha256'];return json.loads(gzip.decompress(target.read_bytes()))
    deadline();u=used();assert u['new_environment_starts']<40 and u['cumulative_environment_starts']<20000
    assert not any(e['event']=='start' and e['identity']==identity for e in events());append('start',identity=identity,number=u['new_environment_starts']+1);began=time.perf_counter()
    try:
        frozen,_=x.p.inputs(x.p.BUNDLE);initial=read(probe.BUNDLE/'inputs.json')['initial']
        if policy==POLICIES[0]:result,c=parent.parent.previous.parent.parent.prior.x.micro.simulate(frozen,initial,case['tickets'],case['context'],policy)
        else:
            c=x.Controller(frozen,initial);c.execution_deadline=deadline();profile=x.p.profile(frozen,case['context'])
            vectors=dict(cells={k:[dict(source_request_id='terminal_pilot_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in profile.items()})
            result=x.old.fast.old.external.old.engine.simulate(dict(protocol=x.p.VERSION,cells=x.p.profile(frozen)),vectors,case['tickets'],policy=c.policy,settings=x.old.fast.old.external.settings(),seed=201,decision_provider=c)
        parent.parent.audit.audit(result,case['tickets']);row,curves=parent.parent.audit.metrics(result,c,initial,frozen)
        row.update(seed=case['seed'],family=case['family'],context=case['context'],policy=policy,identity=identity,host_wall_s=time.perf_counter()-began,
            first_guard_checks=len(getattr(c,'prefix_guard_records',[])),first_guard_blocks=getattr(c,'prefix_blocked_calls',0),terminal_checks=len(getattr(c,'terminal_records',[])),terminal_blocks=getattr(c,'terminal_blocks',0))
        item=dict(row=row,result=result,curves=curves,terminal_records=getattr(c,'terminal_records',[]))
        target.write_bytes(gzip.compress(json.dumps(item,allow_nan=False).encode(),mtime=0));append('completed',identity=identity,artifact_sha256=sha(target));return item
    except BaseException as e:append('failed',identity=identity,error=repr(e));raise
def reuse(index,policy):
    row=next(r for r in read(parent.BUNDLE/'development_rows.json') if r['identity']==f'development/{index}/{policy}')
    if not any(e['event']=='reused' and e['identity']==row['identity'] for e in events()):append('reused',identity=row['identity'],source_shared_sha256=sha(parent.BUNDLE/'development_rows.json'))
    return row
def select(rows):
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};good=0;heat=set()
    for r in rows:
        if r['policy']!=x.POLICY:continue
        ps=[parent.parent.compare(r,by[r['seed'],r['family'],r['context'],p]) for p in POLICIES[:2]];good+=all(p['nonworse'] for p in ps)
        if r['family'] in ('low','sustained') and all(p['heat_gain'] for p in ps):heat.add(r['seed'])
    eligible=good==24 and heat=={813010101,813010102}
    return dict(utc=utc(),chosen=x.POLICY if eligible else None,nonworse_conditions=good,primary_heat_gain_seeds=len(heat),eligible=eligible,independent_final_not_consumed=True)
def run():
    prepare()
    if (BUNDLE/'completion.json').exists():return read(BUNDLE/'completion.json')
    owner=LOCAL/'owner.json';assert not owner.exists();write(owner,dict(pid=os.getpid(),utc=utc()));rows=[]
    try:
        from tools.test_d1_ie_dispatch import ticket
        case=dict(seed=0,family='fixture',context='mean',tickets=[ticket('c0',0),ticket('d0',1,'detection',35.,6.),ticket('c1',2),ticket('d1',3,'detection',35.,6.)])
        for policy in (POLICIES[0],x.POLICY):
            r=execute(case,policy,'fixture/'+policy)['row'];assert r['completed']==r['planned']==4 and r['urgent_service_failure']==r['normal_service_failure']==0
        write(BUNDLE/'fixture_verification.json',dict(status='PASS',native_starts=2,planned_completed=8))
        for i,case in enumerate(read(probe.BUNDLE/'inputs.json')['development']):
            for p in POLICIES:rows.append(execute(case,p,f'development/{i}/{p}')['row'] if p==x.POLICY else reuse(i,p))
            print(json.dumps(dict(done=i+1,total=24,starts=used()['new_environment_starts'])),flush=True)
        write(BUNDLE/'development_rows.json',rows);write(BUNDLE/'selection.json',select(rows));write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=used(),new_candidate_conditions=24,reused_rows=72,independent_final_started=0,new_learning=0))
        return read(BUNDLE/'completion.json')
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','status']);a=p.parse_args()
    if a.command=='prepare':print(json.dumps(prepare(),indent=2))
    elif a.command=='run':print(json.dumps(run(),indent=2))
    else:print(json.dumps(used(),indent=2))
