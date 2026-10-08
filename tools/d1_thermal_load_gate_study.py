"""One development-driven admission repair; fresh final seeds, no extra RL."""
from __future__ import annotations
import argparse,gzip,json,os,subprocess,time
from datetime import datetime,timezone
from tools import d1_thermal_slack_v3_study as parent
from tools import d1_thermal_load_gate as x
from tools import d1_external_rules_study as audit
from tools.d1_edd_ect_residual_report import compare

ROOT=parent.ROOT;BUNDLE=ROOT/'docs/results/thermal_load_gate_01';LOCAL=ROOT/'output/thermal_load_gate_20261009_v1'
BAND=parent.BAND;TRITON=parent.TRITON;EDD=parent.EDD;LIST=parent.LIST
POLICIES=(BAND,TRITON,EDD,LIST,parent.x.SHORT,x.POLICY);NEW=(x.POLICY,)
read=parent.read;write=parent.write;sha=parent.sha;utc=parent.utc

def events():return parent.prior.prior.entries(LOCAL/'executions.jsonl')
def used():
    old=parent.used();assert old['cumulative_environment_starts']==5636 and old['cumulative_learning_starts']==641
    es=events();n=sum(r['event']=='start' for r in es)
    return dict(previous_environment_starts=5636,new_environment_starts=n,cumulative_environment_starts=5636+n,cumulative_learning_starts=641,new_learning_starts=0,failed=sum(r['event']=='failed' for r in es),device_commands=0)
def append(event,**fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:f.write(json.dumps(dict(event=event,utc=utc(),**fields),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    assert not (parent.LOCAL/'owner.json').exists(),'finish source experiment; preserve its running files'
    assert read(parent.BUNDLE/'completion.json')['status']=='completed';parent.check()
    fresh=(813030101,813030102)
    # Reuse the parent's audited metadata traversal with no mutations to its globals.
    inventory=parent.seed_audit(fresh)
    BUNDLE.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
    old=read(parent.BUNDLE/'inputs.json');final=[dict(seed=seed,family=family,context=context,tickets=parent.x.external.old.workload(family,seed)) for seed in fresh for family in ('low','queue','burst','sustained') for context in parent.x.core.CONTEXTS]
    write(BUNDLE/'inputs.json',dict(initial=old['initial'],cases=dict(development=old['cases']['development'],final=final)))
    sources=dict(read(parent.BUNDLE/'registration.json')['sources'])
    for rel in ('tools/d1_thermal_load_gate.py','tools/d1_thermal_load_gate_study.py','tools/test_d1_thermal_load_gate.py'):sources[rel]=sha(ROOT/rel)
    reg=dict(task='IE-THERMAL-LOAD-GATE-01',registered_utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,sources=sources,inputs_sha256=sha(BUNDLE/'inputs.json'),seed_inventory=inventory,
        development_conditions=24,final_conditions=24,policies=list(POLICIES),environment_cap=192,expected_environment_starts=168,learning_starts=0,wall_seconds=1800,save_reserve_seconds=300,prior=used(),whole_environment_cap=20000,
        design_trigger='source development:0.25s cooling helped sparse traces but worsened deadlines/heat under queue/burst/sustained; no use of its final outcomes to fit this gate',
        design='one fixed workload admission gate: >=3 observed requests; min last8 observed interarrival gaps minus elapsed since last arrival must cover queued CPU-only worst-context full lane work PLUS remaining cooling credit; both baseline/candidate current-work forecasts absolutely feasible. No workload-family/next-arrival/SLA/temperature threshold input',
        scope='known-history risk screen only, not guaranteed next arrival or deadline; same old EDD/slack/Band forecast and0.25s credit; no fitted threshold/grid search',
        development_reuse='all source development baseline rows sealed/hashed reused,24 new gate environments; old final seeds deliberately not reused for new final',
        selection='same all24 service/J/AP nonworse versus both references and primary heat gain in both development seeds; freeze before fresh final. never choose from final',
        representative=dict(seed=813030101,family='low',context='mean'),device_commands=0,NPU=False,experiment_ready=False,no_new_model_or_coefficients=True)
    write(BUNDLE/'registration.json',reg);write(LOCAL/'registration.json',reg);return reg

def check():
    reg=read(BUNDLE/'registration.json');assert reg==read(LOCAL/'registration.json')
    for path,h in reg['sources'].items():assert sha(ROOT/path)==h,path
    assert sha(BUNDLE/'inputs.json')==reg['inputs_sha256'];return reg
def deadline():
    reg=check();elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(reg['registered_utc'])).total_seconds()
    if elapsed>=reg['wall_seconds']-300 or (LOCAL/'STOP_REQUEST.json').exists():raise TimeoutError('save/stop boundary')
    return time.monotonic()+reg['wall_seconds']-300-elapsed

def simulate(frozen,initial,case,policy):
    if policy not in (x.POLICY,parent.x.SHORT,LIST):return parent.prior.x.micro.simulate(frozen,initial,case['tickets'],case['context'],policy)
    if policy==x.POLICY:c=x.Controller(frozen,initial)
    elif policy==parent.x.SHORT:c=parent.x.Controller(frozen,initial,policy)
    else:
        from tools import d1_ie_candidates_v2 as v2
        c=v2.Controller(frozen,initial,policy)
    c.execution_deadline=deadline();actual=parent.x.p.profile(frozen,case['context']);vectors=dict(cells={k:[dict(source_request_id='thermal_load_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in actual.items()})
    return parent.x.external.old.engine.simulate(dict(protocol=parent.x.p.VERSION,cells=parent.x.p.profile(frozen)),vectors,case['tickets'],policy=c.policy,settings=parent.x.external.settings(),seed=201,decision_provider=c),c

def execute(case,policy,identity):
    path=LOCAL/'items'/(identity.replace('/','__')+'.json.gz');path.parent.mkdir(exist_ok=True)
    if path.exists():
        item=json.loads(gzip.decompress(path.read_bytes()));receipt=[r for r in events() if r['event']=='completed' and r['identity']==identity];assert len(receipt)==1 and sha(path)==receipt[0]['artifact_sha256'];return item
    deadline();u=used();assert u['new_environment_starts']<192 and u['cumulative_environment_starts']<20000
    assert not any(r['event']=='start' and r['identity']==identity for r in events()),'charged identity must be investigated, no silent retry'
    n=u['new_environment_starts']+1;append('start',number=n,identity=identity,kind='evaluation');began=time.perf_counter()
    try:
        frozen,_=parent.x.p.inputs(parent.x.p.BUNDLE);initial=read(BUNDLE/'inputs.json')['initial'];result,c=simulate(frozen,initial,case,policy)
        audit.audit(result,case['tickets']);row,curves=audit.metrics(result,c,initial,frozen);choices=getattr(c,'choice_records',[]);gate=getattr(c,'gate_records',[])
        row.update(seed=case['seed'],family=case['family'],context=case['context'],policy=policy,identity=identity,host_wall_s=time.perf_counter()-began,discretionary_decisions=sum(not d.get('chosen_base',True) for d in choices),cool_wait_choices=sum(d.get('kind')=='cool_wait' for d in choices),gate_allowed=sum(d['allowed'] for d in gate),gate_blocked=sum(not d['allowed'] for d in gate))
        item=dict(row=row,result=result,curves=curves,choices=choices,gates=gate);path.write_bytes(gzip.compress(json.dumps(item,allow_nan=False).encode(),mtime=0));append('completed',number=n,identity=identity,artifact_sha256=sha(path));return item
    except BaseException as e:append('failed',number=n,identity=identity,error=repr(e));raise

def reuse(index,policy):
    identity=f'development/{index}/{policy}';path=parent.LOCAL/'items'/(identity.replace('/','__')+'.json.gz')
    item=json.loads(gzip.decompress(path.read_bytes()));receipt=[r for r in parent.events() if r['event']=='completed' and r['identity']==identity];assert len(receipt)==1 and receipt[0]['artifact_sha256']==sha(path)
    if not any(r['event']=='reused' and r['identity']==identity for r in events()):append('reused',identity=identity,source_sha256=sha(path),source_parent_task='IE-THERMAL-SLACK-03')
    return item['row']

def select(rows):
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};pairs=[];seeds=set()
    for row in (r for r in rows if r['policy']==x.POLICY):
        ps=[compare(row,by[row['seed'],row['family'],row['context'],p]) for p in (BAND,TRITON)];pairs.append(ps)
        if row['family'] in ('low','sustained') and all(p['heat_gain'] for p in ps):seeds.add(row['seed'])
    eligible=all(all(p['nonworse'] for p in ps) for ps in pairs) and seeds=={813010101,813010102}
    return dict(utc=utc(),chosen=x.POLICY if eligible else None,development_nonworse_conditions=sum(all(p['nonworse'] for p in ps) for ps in pairs),heat_gain_seed_count=len(seeds),final_consumed=False)

def run():
    prepare();owner=LOCAL/'owner.json';assert not owner.exists();write(owner,dict(pid=os.getpid(),utc=utc()));data=read(BUNDLE/'inputs.json')
    try:
        rows=[]
        for i,case in enumerate(data['cases']['development']):
            for policy in POLICIES:rows.append(execute(case,policy,f'development/{i}/{policy}')['row'] if policy==x.POLICY else reuse(i,policy))
        write(BUNDLE/'development_rows.json',rows)
        if not (BUNDLE/'selection.json').exists():write(BUNDLE/'selection.json',select(rows))
        rows=[]
        for i,case in enumerate(data['cases']['final']):
            for policy in POLICIES:rows.append(execute(case,policy,f'final/{i}/{policy}')['row'])
            print(json.dumps(dict(split='fresh_final',done=i+1,total=24,environment_starts=used()['new_environment_starts'])),flush=True)
        write(BUNDLE/'final_rows.json',rows);write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=used(),development_rows=144,development_reused_rows=120,final_rows=144))
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run','status']);a=parser.parse_args()
    if a.command=='prepare':prepare();print(json.dumps(used()))
    elif a.command=='run':run()
    else:print(json.dumps(used(),indent=2))
