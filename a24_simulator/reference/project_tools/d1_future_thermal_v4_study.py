"""Bounded exact-speed preservation and causal future-scenario comparison."""
import argparse,gzip,json,os,subprocess,time
from datetime import datetime,timezone
from tools import d1_thermal_load_gate_study as parent
from tools import d1_fast_thermal_forecast as fast
from tools import d1_future_thermal_v4 as x
from tools import d1_external_rules_study as audit
from tools.d1_edd_ect_residual_report import compare

ROOT=parent.ROOT;BUNDLE=ROOT/'docs/results/future_thermal_v4';LOCAL=ROOT/'output/future_thermal_20261009_v4'
BAND=parent.BAND;TRITON=parent.TRITON;EDD=parent.EDD;OLD=parent.x.POLICY
POLICIES=(BAND,TRITON,EDD,OLD,fast.FAST,x.ROBUST,x.EMPIRICAL);DEV=tuple(p for p in POLICIES if p!=fast.FAST);CANDIDATES=(x.ROBUST,x.EMPIRICAL)
read=parent.read;write=parent.write;sha=parent.sha;utc=parent.utc
def events():return parent.parent.prior.prior.entries(LOCAL/'executions.jsonl')
def used():
    old=parent.used();assert old['cumulative_environment_starts']==5804 and old['cumulative_learning_starts']==641
    es=events();n=sum(r['event']=='start' for r in es)
    return dict(previous_environment_starts=5804,new_environment_starts=n,cumulative_environment_starts=5804+n,cumulative_learning_starts=641,new_learning_starts=0,failed=sum(r['event']=='failed' for r in es),device_commands=0)
def append(event,**fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:f.write(json.dumps(dict(event=event,utc=utc(),**fields),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    assert not (parent.LOCAL/'owner.json').exists();assert read(parent.BUNDLE/'completion.json')['status']=='completed';parent.check()
    inventory=parent.parent.seed_audit((814020101,814020102));old=read(parent.BUNDLE/'inputs.json')
    BUNDLE.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
    final=[dict(seed=seed,family=family,context=ctx,tickets=fast.old.external.old.workload(family,seed)) for seed in (814020101,814020102) for family in ('low','queue','burst','sustained') for ctx in fast.old.core.CONTEXTS]
    preservation=[c for c in old['cases']['final'] if c['context']=='mean'];assert len(preservation)==8
    write(BUNDLE/'inputs.json',dict(initial=old['initial'],cases=dict(development=old['cases']['development'],final=final,preservation=preservation)))
    sources=dict(read(parent.BUNDLE/'registration.json')['sources'])
    for rel in ('tools/d1_fast_thermal_forecast.py','tools/d1_future_thermal_v4.py','tools/d1_future_thermal_v4_study.py','tools/test_d1_fast_future_thermal.py'):sources[rel]=sha(ROOT/rel)
    reg=dict(task='IE-FUTURE-THERMAL-04',registered_utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,sources=sources,inputs_sha256=sha(BUNDLE/'inputs.json'),seed_inventory=inventory,
        development_conditions=24,final_conditions=24,development_policies=list(DEV),final_policies=list(POLICIES),environment_cap=256,expected_environment_starts=225,learning_starts=0,wall_seconds=3600,save_reserve_seconds=300,prior=used(),whole_environment_cap=20000,
        speed_preservation='8 original mean-context cases2seeds4families; exact physical ledger parity vs original gated policy; fresh final also pairs old vs fast all24. No changed cost coefficients',
        synthetic_scenarios='prediction only: no-arrival plus one next classification or detection at each distinct min/max of last8 observed gaps, measured phase contexts3; static original1.5s/6s task contracts; never real future trace',
        empirical_weights='task counts last8+one pseudocount per supported task, equal weights across distinct gap endpoints; heuristic scenario weights, not calibrated probabilities; no-arrival used as guard with score weight0',
        service_guard='all scenarios known urgent/normal misses and known-only P95 nonworse, each virtual urgent response individually nonworse, all planned work feasible; virtual jobs excluded from known P95 denominator; J nonworse paired same hypothetical workload',
        heat_objectives='ROBUST: paired worst future AP decrease and global AP nonworse every scenario. EMPIRICAL: weighted paired future AP decrease in all phase contexts, actual-known/no-arrival AP nonworse; permits modeled future AP tradeoffs, no real guarantee',
        action_space='fast preservation retains full old physical pool; future policies intentionally restrict to native Band first action vs same admissible normal0.25s cooling. Width effect separated from forecast/algorithm effects',
        selection='development all24 service/J/AP nonworse vs BOTH original Band/Triton and primary low/sustained heat gain in both seeds; worst paired AP thenmean J then ROBUST tie; freeze before final, never select from final',
        expected_breakdown=dict(preservation=8,native_virtual_isolation_fixture=1,development_new=48,development_reused=96,final=168),
        representative=dict(seed=814020101,family='low',context='mean'),device_commands=0,NPU=False,experiment_ready=False,no_new_model_or_coefficients=True)
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
    if policy in (BAND,TRITON,EDD):return parent.parent.prior.x.micro.simulate(frozen,initial,case['tickets'],case['context'],policy)
    if policy==OLD:c=parent.x.Controller(frozen,initial)
    elif policy==fast.FAST:c=fast.Controller(frozen,initial)
    else:c=x.Controller(frozen,initial,policy)
    c.execution_deadline=deadline();actual=fast.p.profile(frozen,case['context']);vectors=dict(cells={k:[dict(source_request_id='future_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in actual.items()})
    return fast.old.external.old.engine.simulate(dict(protocol=fast.p.VERSION,cells=fast.p.profile(frozen)),vectors,case['tickets'],policy=c.policy,settings=fast.old.external.settings(),seed=201,decision_provider=c),c
def execute(case,policy,identity):
    path=LOCAL/'items'/(identity.replace('/','__')+'.json.gz');path.parent.mkdir(exist_ok=True)
    if path.exists():
        item=json.loads(gzip.decompress(path.read_bytes()));receipt=[r for r in events() if r['event']=='completed' and r['identity']==identity];assert len(receipt)==1 and sha(path)==receipt[0]['artifact_sha256'];return item
    deadline();u=used();assert u['new_environment_starts']<256 and u['cumulative_environment_starts']<20000
    assert not any(r['event']=='start' and r['identity']==identity for r in events()),'preserve unsealed started identity'
    n=u['new_environment_starts']+1;append('start',number=n,identity=identity,kind='fixture' if identity.startswith('fixture') else 'evaluation');began=time.perf_counter()
    try:
        frozen,_=fast.p.inputs(fast.p.BUNDLE);initial=read(BUNDLE/'inputs.json')['initial'];result,c=simulate(frozen,initial,case,policy);audit.audit(result,case['tickets']);row,curves=audit.metrics(result,c,initial,frozen)
        choices=getattr(c,'choice_records',[]);probes=getattr(c,'probe_records',[])
        row.update(seed=case['seed'],family=case['family'],context=case['context'],policy=policy,identity=identity,host_wall_s=time.perf_counter()-began,discretionary_decisions=sum(not q.get('chosen_base',True) for q in choices),cool_wait_choices=sum(q.get('kind')=='cool_wait' for q in choices),projection_calls=getattr(c,'projection_calls',0),future_scenario_batches=len(probes))
        item=dict(row=row,result=result,curves=curves,choices=choices,probes=probes);path.write_bytes(gzip.compress(json.dumps(item,allow_nan=False).encode(),mtime=0));append('completed',number=n,identity=identity,artifact_sha256=sha(path));return item
    except BaseException as e:append('failed',number=n,identity=identity,error=repr(e));raise
def physical(result):return [{k:v for k,v in row.items() if k!='source_request_id'} for row in result['ledger']]
def preservation(data):
    proofs=[];oldcases=read(parent.BUNDLE/'inputs.json')['cases']['final']
    for i,case in enumerate(data['cases']['preservation']):
        original_index=oldcases.index(case);identity=f'final/{original_index}/{OLD}';path=parent.LOCAL/'items'/(identity.replace('/','__')+'.json.gz');original=json.loads(gzip.decompress(path.read_bytes()))
        assert any(r['event']=='completed' and r['identity']==identity and r['artifact_sha256']==sha(path) for r in parent.events())
        new=execute(case,fast.FAST,f'preservation/{i}');assert physical(new['result'])==physical(original['result']),'fast semantic drift'
        proofs.append(dict(seed=case['seed'],family=case['family'],context='mean',original_identity=identity,original_sha256=sha(path),old_host_s=original['row']['decision_host_total_s'],fast_host_s=new['row']['decision_host_total_s'],ledger_equal=True))
    write(BUNDLE/'preservation.json',proofs)
    from tools.test_d1_ie_dispatch import ticket
    qs=[ticket(str(i),i,'detection' if i in (3,5) else 'classification',35.+1.2*i,6. if i in (3,5) else 1.5) for i in range(6)]
    item=execute(dict(seed=0,family='fixture',context='mean',tickets=qs),x.ROBUST,'fixture/virtual_isolation')
    assert {r['id'] for r in item['result']['ledger']}=={q['id'] for q in qs} and item['row']['future_scenario_batches']>0
    write(BUNDLE/'fixture_verification.json',dict(status='PASS',real_requests=6,virtual_scenario_batches=item['row']['future_scenario_batches'],no_virtual_admission=True,environment_starts=1,device_commands=0))
def reuse(i,policy):
    rows=read(parent.BUNDLE/'development_rows.json');row=next(r for r in rows if r['identity']==f'development/{i}/{policy}')
    if policy==OLD:source=parent
    else:source=parent.parent
    path=source.LOCAL/'items'/(row['identity'].replace('/','__')+'.json.gz');assert any(r['event']=='completed' and r['identity']==row['identity'] and r['artifact_sha256']==sha(path) for r in source.events())
    if not any(r['event']=='reused' and r['identity']==row['identity'] for r in events()):append('reused',identity=row['identity'],source_sha256=sha(path))
    return row
def select(rows):
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};eligible=[];details={}
    for policy in CANDIDATES:
        pairs=[];gain_seeds=set()
        for row in (r for r in rows if r['policy']==policy):
            ps=[compare(row,by[row['seed'],row['family'],row['context'],p]) for p in (BAND,TRITON)];pairs.append((row,ps))
            if row['family'] in ('low','sustained') and all(p['heat_gain'] for p in ps):gain_seeds.add(row['seed'])
        good=all(all(p['nonworse'] for p in ps) for _,ps in pairs) and gain_seeds=={813010101,813010102}
        key=(max(p['delta_peak_ap_c'] for _,ps in pairs for p in ps),sum(row['energy_j'] for row,_ in pairs)/24,policy!=x.ROBUST)
        details[policy]=dict(eligible=good,nonworse_conditions=sum(all(p['nonworse'] for p in ps) for _,ps in pairs),heat_gain_seed_count=len(gain_seeds),ranking=list(key))
        if good:eligible.append((key,policy))
    return dict(utc=utc(),chosen=min(eligible)[1] if eligible else None,development_eligibility=details,final_consumed=False)
def run():
    prepare();owner=LOCAL/'owner.json';assert not owner.exists();write(owner,dict(pid=os.getpid(),utc=utc()));data=read(BUNDLE/'inputs.json')
    try:
        preservation(data);rows=[]
        for i,case in enumerate(data['cases']['development']):
            for policy in DEV:rows.append(execute(case,policy,f'development/{i}/{policy}')['row'] if policy in CANDIDATES else reuse(i,policy))
        write(BUNDLE/'development_rows.json',rows)
        if not (BUNDLE/'selection.json').exists():write(BUNDLE/'selection.json',select(rows))
        rows=[]
        for i,case in enumerate(data['cases']['final']):
            for policy in POLICIES:rows.append(execute(case,policy,f'final/{i}/{policy}')['row'])
            print(json.dumps(dict(split='final',done=i+1,total=24,environment_starts=used()['new_environment_starts'])),flush=True)
        write(BUNDLE/'final_rows.json',rows);write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=used(),development_rows=144,development_reused_rows=96,final_rows=168))
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run','status']);args=parser.parse_args()
    if args.command=='prepare':prepare();print(json.dumps(used()))
    elif args.command=='run':run()
    else:print(json.dumps(used(),indent=2))
