"""Joint rolling-horizon pilot, finite search and preserved experiment budgets."""
import argparse,gzip,json,os,subprocess,time
from datetime import datetime,timezone
from tools import d1_future_thermal_v4_study as previous
from tools import d1_rolling_joint_thermal as x
from tools import d1_external_rules_study as audit
from tools.d1_edd_ect_residual_report import compare

ROOT=previous.ROOT;BUNDLE=ROOT/'docs/results/rolling_joint_01';LOCAL=ROOT/'output/rolling_joint_20261009_v1'
BAND=previous.BAND;TRITON=previous.TRITON;EDD=previous.EDD;FAST=previous.fast.FAST
CP='IE_ROLLING_ENERGY_CPSAT_AP_FILTER_V2';POLICIES=(BAND,TRITON,EDD,CP,FAST,x.NOWAIT,x.WAIT);NEW=(x.NOWAIT,x.WAIT)
read=previous.read;write=previous.write;sha=previous.sha;utc=previous.utc
def events():return previous.parent.parent.prior.prior.entries(LOCAL/'executions.jsonl')
def used():
    old=previous.used();assert old['cumulative_environment_starts']==6029 and old['cumulative_learning_starts']==641
    es=events();n=sum(r['event']=='start' for r in es)
    return dict(previous_environment_starts=6029,new_environment_starts=n,cumulative_environment_starts=6029+n,cumulative_learning_starts=641,new_learning_starts=0,failed=sum(r['event']=='failed' for r in es),device_commands=0)
def append(event,**fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:f.write(json.dumps(dict(event=event,utc=utc(),**fields),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    assert not (previous.LOCAL/'owner.json').exists();previous.check()
    inventory=previous.parent.parent.seed_audit((815020101,815020102));old=read(previous.BUNDLE/'inputs.json')
    BUNDLE.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
    final=[dict(seed=seed,family=family,context=ctx,tickets=x.fast.old.external.old.workload(family,seed)) for seed in (815020101,815020102) for family in ('low','queue','burst','sustained') for ctx in x.core.CONTEXTS]
    write(BUNDLE/'inputs.json',dict(initial=old['initial'],cases=dict(development=old['cases']['development'],final=final)))
    sources=dict(read(previous.BUNDLE/'registration.json')['sources'])
    for path in ('tools/d1_rolling_joint_thermal.py','tools/d1_rolling_joint_study.py','tools/test_d1_rolling_joint_thermal.py'):sources[path]=sha(ROOT/path)
    reg=dict(task='IE-ROLLING-JOINT-01',registered_utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,sources=sources,inputs_sha256=sha(BUNDLE/'inputs.json'),seed_inventory=inventory,
        development_conditions=24,final_conditions=24,policies=list(POLICIES),environment_cap=320,expected_environment_starts=267,learning_starts=0,wall_seconds=3600,save_reserve_seconds=300,prior=used(),whole_environment_cap=20000,
        design='EDD within each task,window first4EDD with replacement by least-response-slack CPU-only job; enumerate compatible routing/interleaving and at most one normal0.25s idle slot; no synthetic arrivals',
        computation='max72finite prefix plans; mean-only window ranking urgency misses,normal misses,J,AP,P95; first8 with at most2 per first-action signature receive full known-queue/Band-suffix evaluation in all3phase contexts',
        forecast_guard='full arrived queue and owned jobs retained; urgent/normal misses,P95,J/globalAP nonworse vs hypothetical Band in all3contexts; finish<=120; select worst futureAP change thenJ thennormal mean; strict AP orJ decrease required',
        waiting='credit0.25 cumulative between actual dispatches; initial delay<=remaining credit,internal planned gap only when both lanes free/no queued urgent; resource ownership remains through5phase release; first simultaneous legal pair only committed',
        decisions='new arrivals/ownership changes/cooling timer; phase-only updates observers but selected resource-wait/cooling continuation is held; no preemption/frequency/NPU',
        selection='development all24 service/J/AP nonworse vs BOTH Band/Triton and primary low/sustained heat gain each seed, worstAP thenmeanJ thenNOWAIT tie; freeze before final; final never reselects',
        scope='bounded list-restricted rolling heuristic, beam8 not exhaustive/global/continuous optimum; window-only cost used only for shortlist, never outcome or full completion claim',
        expected_breakdown=dict(fixtures=3,development_new=96,development_reused=72,final=168),representative=dict(seed=815020101,family='burst',context='mean'),device_commands=0,NPU=False,experiment_ready=False,no_new_model_or_coefficients=True)
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
    if policy in (BAND,TRITON,EDD):return previous.parent.parent.prior.x.micro.simulate(frozen,initial,case['tickets'],case['context'],policy)
    if policy==FAST:c=x.fast.Controller(frozen,initial)
    elif policy==CP:
        from tools import d1_ie_candidates_v2 as legacy
        c=legacy.Controller(frozen,initial,CP)
    else:c=x.Controller(frozen,initial,policy)
    c.execution_deadline=deadline();profile=x.p.profile(frozen,case['context']);vectors=dict(cells={k:[dict(source_request_id='rolling_joint_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in profile.items()})
    return x.fast.old.external.old.engine.simulate(dict(protocol=x.p.VERSION,cells=x.p.profile(frozen)),vectors,case['tickets'],policy=c.policy,settings=x.fast.old.external.settings(),seed=201,decision_provider=c),c
def execute(case,policy,identity):
    path=LOCAL/'items'/(identity.replace('/','__')+'.json.gz');path.parent.mkdir(exist_ok=True)
    if path.exists():
        item=json.loads(gzip.decompress(path.read_bytes()));es=[r for r in events() if r['event']=='completed' and r['identity']==identity];assert len(es)==1 and sha(path)==es[0]['artifact_sha256'];return item
    deadline();u=used();assert u['new_environment_starts']<320 and u['cumulative_environment_starts']<20000
    assert not any(r['event']=='start' and r['identity']==identity for r in events()),'preserve started identity'
    n=u['new_environment_starts']+1;append('start',number=n,identity=identity,kind='fixture' if identity.startswith('fixture') else 'evaluation');started=time.perf_counter()
    try:
        frozen,_=x.p.inputs(x.p.BUNDLE);initial=read(BUNDLE/'inputs.json')['initial'];result,c=simulate(frozen,initial,case,policy)
        audit.audit(result,case['tickets']);row,curves=audit.metrics(result,c,initial,frozen);records=getattr(c,'plan_records',[])
        row.update(seed=case['seed'],family=case['family'],context=case['context'],policy=policy,identity=identity,host_wall_s=time.perf_counter()-started,planning_calls=len(records),nonbase_plans=sum(r['selected_plan'] is not None for r in records),
            mean_screen_plan_evaluations=sum(r['candidate_count'] for r in records),full_three_context_plans=sum(r['full_plan_count'] for r in records),projection_calls=getattr(c,'projection_calls',0))
        item=dict(row=row,result=result,curves=curves,plans=records);path.write_bytes(gzip.compress(json.dumps(item,allow_nan=False).encode(),mtime=0));append('completed',number=n,identity=identity,artifact_sha256=sha(path));return item
    except BaseException as e:append('failed',number=n,identity=identity,error=repr(e));raise
def reuse(i,policy):
    rows=read(previous.BUNDLE/'development_rows.json');row=next(r for r in rows if r['identity']==f'development/{i}/{policy}')
    if not any(r['event']=='reused' and r['identity']==row['identity'] for r in events()):append('reused',identity=row['identity'],source_shared_sha256=sha(previous.BUNDLE/'development_rows.json'))
    return row
def fixtures():
    from tools.test_d1_ie_dispatch import ticket
    qs=[ticket('c0',0),ticket('d0',1,'detection',35.,6.),ticket('c1',2),ticket('d1',3,'detection',35.,6.)];case=dict(seed=0,family='fixture',context='mean',tickets=qs)
    items={p:execute(case,p,f'fixture/{p}') for p in (BAND,x.NOWAIT,x.WAIT)}
    for item in items.values():assert item['row']['planned']==item['row']['completed']==4 and item['row']['urgent_service_failure']==item['row']['normal_service_failure']==0
    write(BUNDLE/'fixture_verification.json',dict(status='PASS',native_environment_starts=3,planned_completed=12,original_engine_capacity_boundary_audit=True,device_commands=0))
def select(rows):
    by={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};eligible=[];details={}
    for policy in NEW:
        pairs=[];seeds=set()
        for r in (r for r in rows if r['policy']==policy):
            ps=[compare(r,by[r['seed'],r['family'],r['context'],p]) for p in (BAND,TRITON)];pairs.append((r,ps))
            if r['family'] in ('low','sustained') and all(p['heat_gain'] for p in ps):seeds.add(r['seed'])
        good=all(all(p['nonworse'] for p in ps) for _,ps in pairs) and seeds=={813010101,813010102}
        key=(max(p['delta_peak_ap_c'] for _,ps in pairs for p in ps),sum(r['energy_j'] for r,_ in pairs)/24,policy!=x.NOWAIT)
        details[policy]=dict(eligible=good,nonworse_conditions=sum(all(p['nonworse'] for p in ps) for _,ps in pairs),primary_heat_gain_seeds=len(seeds),ranking=list(key))
        if good:eligible.append((key,policy))
    return dict(utc=utc(),chosen=min(eligible)[1] if eligible else None,eligibility=details,final_consumed=False)
def run():
    prepare();owner=LOCAL/'owner.json';assert not owner.exists();write(owner,dict(pid=os.getpid(),utc=utc()));data=read(BUNDLE/'inputs.json')
    try:
        fixtures();rows=[]
        for i,case in enumerate(data['cases']['development']):
            for policy in POLICIES:rows.append(reuse(i,policy) if policy in (BAND,TRITON,EDD) else execute(case,policy,f'development/{i}/{policy}')['row'])
            print(json.dumps(dict(split='development',done=i+1,total=24,starts=used()['new_environment_starts'])),flush=True)
        write(BUNDLE/'development_rows.json',rows)
        if not (BUNDLE/'selection.json').exists():write(BUNDLE/'selection.json',select(rows))
        rows=[]
        for i,case in enumerate(data['cases']['final']):
            for policy in POLICIES:rows.append(execute(case,policy,f'final/{i}/{policy}')['row'])
            print(json.dumps(dict(split='final',done=i+1,total=24,starts=used()['new_environment_starts'])),flush=True)
        write(BUNDLE/'final_rows.json',rows);write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=used(),development_rows=168,development_reused_rows=72,final_rows=168))
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','status']);args=p.parse_args()
    if args.command=='prepare':prepare();print(json.dumps(used()))
    elif args.command=='run':run()
    else:print(json.dumps(used(),indent=2))
