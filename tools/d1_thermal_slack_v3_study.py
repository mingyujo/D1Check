"""Finite development/final experiment; immutable old model and budget ledger."""
from __future__ import annotations
import argparse,gzip,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_thermal_slack_v3 as x
from tools import d1_busy_oracle_study as prior
from tools import d1_external_rules_study as audit
from tools.d1_edd_ect_residual_report import compare

ROOT=x.p.ROOT;BUNDLE=ROOT/'docs/results/thermal_slack_v3';LOCAL=ROOT/'output/thermal_slack_20261009_v3'
BAND=prior.BAND;TRITON=prior.TRITON;EDD=prior.EDD;LIST='IE_ENERGY_AP_LIST_V2'
POLICIES=(BAND,TRITON,EDD,LIST,x.SHORT,x.LONG,x.NOWAIT);NEW=(x.SHORT,x.LONG,x.NOWAIT)
read=prior.read;write=prior.write;sha=prior.sha;utc=prior.utc

def events():return prior.prior.entries(LOCAL/'executions.jsonl')
def used():
    old=prior.used();assert old['cumulative_environment_starts']==5298 and old['cumulative_learning_starts']==641
    es=events();n=sum(e['event']=='start' for e in es)
    return dict(previous_environment_starts=5298,new_environment_starts=n,cumulative_environment_starts=5298+n,cumulative_learning_starts=641,new_learning_starts=0,failed=sum(e['event']=='failed' for e in es),device_commands=0)
def append(event,**fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:f.write(json.dumps(dict(event=event,utc=utc(),**fields),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

def seed_audit(seeds):
    # Full shared metadata and local registered JSON inputs; raw filename
    # metadata included. No claim about unregistered external datasets.
    wanted={str(s) for s in seeds};count=0;raw_names=0
    for folder in (ROOT/'docs/results',ROOT/'output'):
        for path in folder.rglob('*'):
            if not path.is_file() or BUNDLE in path.parents or LOCAL in path.parents or 'ie_scheduler_v2_deps' in path.parts:continue
            if any(s in path.name for s in wanted):raise ValueError('seed filename collision '+path.name)
            raw_names+=1
            if path.suffix not in ('.json','.jsonl','.csv'):continue
            if folder.name=='output' and path.name not in ('inputs.json','registration.json','contract.json','config.json','selection.json','executions.jsonl'):continue
            if path.stat().st_size>20000000:continue
            text=path.read_text(encoding='utf8',errors='replace');count+=1
            if any(s in text for s in wanted):raise ValueError('seed metadata collision '+path.relative_to(ROOT).as_posix())
    return dict(metadata_files=count,local_and_shared_filenames=raw_names,collisions=0,scope='shared JSON/CSV and local registered inputs/receipts plus filenames; not full raw gzip/external history audit')

def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    for directory in ('ie_candidates_20261008_v2','cpu_gpu_method_20261008_v1','busy_oracle_20261009_v1'):
        if (ROOT/'output'/directory/'owner.json').exists():raise RuntimeError('preserve active owner '+directory)
    seeds=(813010101,813010102,813020101,813020102);inventory=seed_audit(seeds)
    BUNDLE.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
    cases={split:[dict(seed=seed,family=family,context=context) for seed in ss for family in ('low','queue','burst','sustained') for context in x.core.CONTEXTS] for split,ss in (('development',seeds[:2]),('final',seeds[2:]))}
    for group in cases.values():
        for c in group:c['tickets']=x.external.old.workload(c['family'],c['seed'])
    initial=read(ROOT/'docs/results/external_rules_02/inputs.json')['initial'];write(BUNDLE/'inputs.json',dict(initial=initial,cases=cases))
    sources=dict(read(ROOT/'docs/results/busy_oracle_01/registration.json')['sources']);sources.update(read(ROOT/'docs/results/busy_oracle_01/repair.json')['source_overrides'])
    for rel in ('tools/d1_thermal_slack_v3.py','tools/d1_thermal_slack_v3_study.py','tools/test_d1_thermal_slack_v3.py'):sources[rel]=sha(ROOT/rel)
    reg=dict(task='IE-THERMAL-SLACK-03',registered_utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,sources=sources,inputs_sha256=sha(BUNDLE/'inputs.json'),seed_inventory=inventory,
        development_conditions=24,final_conditions=24,policies=list(POLICIES),environment_cap=384,expected_environment_starts=338,learning_starts=0,wall_seconds=3600,save_reserve_seconds=300,prior=used(),whole_environment_cap=20000,
        objective_version='AP_FIRST_SERVICE_ENERGY_NONWORSE_V3; old joint-improvement and C/E objectives unchanged; strict joint gains still reported separately',
        selection='development all24 service/J/AP nonworse versus BOTH Band/Triton, and heat gain in primary low/sustained in each of the two seeds; minimize worst paired AP change then mean J then shorter credit; freeze before final. all7 final roles diagnostic, never reselect from final',
        tuning_budget='exactly two predeclared cumulative wait credits0.25s and1.0s; no fitted weights/temperature limit/SLA or post-result grid expansion; no-wait ablation0',
        candidate_rule='Band fallback, EDD first4 plus least-response-slack CPU-only job; legal single and CG_DC bundle; idle cooling only all lanes empty/no urgent arrived, bounded by credit since dispatch; native arrivals/phase events replan',
        predictor='three pinned phase contexts, original linear AP/energy, Band-adapted suffix with hypothesis-only EMA, no future arrivals/actual remaining service/true plant context',
        local_guard='arrived-work urgent/normal misses and urgent P95, whole remaining J/global AP nonworse vs local Band in all3contexts; strict improvement of worst future AP. Not a future SLA guarantee',
        evaluation='same full arrival traces,120s device J,AP35..180s original1s grid, exact completion boundaries, normal mean reported; unsupported thermal safety limit/control J null',
        fixtures='one4-job Band environment + matching pure Band projection, one forced normal idle then urgent-arrival interruption fixture; synthetic hand fixtures, not policy performance',
        representative=dict(seed=813020101,family='sustained',context='mean'),device_commands=0,NPU=False,experiment_ready=False,no_new_model_or_coefficients=True)
    write(BUNDLE/'registration.json',reg);write(LOCAL/'registration.json',reg);return reg

def check():
    reg=read(BUNDLE/'registration.json');assert reg==read(LOCAL/'registration.json')
    sources=dict(reg['sources'])
    if (BUNDLE/'repair.json').exists():sources.update(read(BUNDLE/'repair.json')['source_overrides'])
    for p,h in sources.items():assert sha(ROOT/p)==h,p
    assert sha(BUNDLE/'inputs.json')==reg['inputs_sha256'];return reg
def deadline():
    reg=check();elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(reg['registered_utc'])).total_seconds()
    if elapsed>=reg['wall_seconds']-300 or (LOCAL/'STOP_REQUEST.json').exists():raise TimeoutError('save/stop boundary')
    return time.monotonic()+reg['wall_seconds']-300-elapsed

def simulate(frozen,initial,case,policy,force_wait=False):
    if policy not in NEW:return prior.x.micro.simulate(frozen,initial,case['tickets'],case['context'],policy) if policy!=LIST else list_simulate(frozen,initial,case)
    c=x.Controller(frozen,initial,policy);c.execution_deadline=deadline()
    if force_wait:
        c.select=lambda actions:next((a for a in actions if a['kind']=='cool_wait'),next(a for a in actions if a['base']))
    actual=x.p.profile(frozen,case['context']);vectors=dict(cells={k:[dict(source_request_id='thermal_slack_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in actual.items()})
    result=x.external.old.engine.simulate(dict(protocol=x.p.VERSION,cells=x.p.profile(frozen)),vectors,case['tickets'],policy=c.policy,settings=x.external.settings(),seed=201,decision_provider=c)
    return result,c
def list_simulate(frozen,initial,case):
    from tools import d1_ie_candidates_v2 as v2
    c=v2.Controller(frozen,initial,LIST);c.execution_deadline=deadline();actual=x.p.profile(frozen,case['context'])
    vectors=dict(cells={k:[dict(source_request_id='thermal_slack_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in actual.items()})
    return x.external.old.engine.simulate(dict(protocol=x.p.VERSION,cells=x.p.profile(frozen)),vectors,case['tickets'],policy=c.policy,settings=x.external.settings(),seed=201,decision_provider=c),c

def execute(case,policy,identity,force_wait=False):
    path=LOCAL/'items'/(identity.replace('/','__')+'.json.gz');path.parent.mkdir(exist_ok=True)
    if path.exists():
        item=json.loads(gzip.decompress(path.read_bytes()));receipt=[e for e in events() if e['event']=='completed' and e['identity']==item['row']['identity']];assert len(receipt)==1 and sha(path)==receipt[0]['artifact_sha256'];return item
    deadline();u=used();assert u['new_environment_starts']<384 and u['cumulative_environment_starts']<20000
    original=identity;attempt=0
    while any(e['event']=='start' and e['identity']==identity for e in events()):
        assert any(e['event']=='failed' and e['identity']==identity for e in events()),'unsealed started execution'
        attempt+=1;identity=original+f'/retry_{attempt}'
    n=u['new_environment_starts']+1;append('start',number=n,identity=identity,kind='fixture' if identity.startswith('fixture') else 'evaluation')
    began=time.perf_counter()
    try:
        frozen,_=x.p.inputs(x.p.BUNDLE);initial=read(BUNDLE/'inputs.json')['initial'];result,c=simulate(frozen,initial,case,policy,force_wait)
        audit.audit(result,case['tickets']);row,curves=audit.metrics(result,c,initial,frozen)
        choices=getattr(c,'choice_records',[])
        row.update(seed=case['seed'],family=case['family'],context=case['context'],policy=policy,identity=identity,host_wall_s=time.perf_counter()-began,
            discretionary_decisions=sum(not d.get('chosen_base',True) for d in choices),cool_wait_choices=sum(d.get('kind')=='cool_wait' for d in choices),projection_calls=getattr(c,'projection_calls',0))
        item=dict(row=row,result=result,curves=curves,choices=choices);path.write_bytes(gzip.compress(json.dumps(item,allow_nan=False).encode(),mtime=0));append('completed',number=n,identity=identity,artifact_sha256=sha(path));return item
    except BaseException as e:append('failed',number=n,identity=identity,error=repr(e));raise

def fixtures(data):
    from tools.test_d1_ie_dispatch import ticket
    frozen,_=x.p.inputs(x.p.BUNDLE);initial=data['initial'];qs=[ticket('d0',0,'detection',35.,6.),ticket('c0',1),ticket('d1',2,'detection',35.,6.),ticket('c1',3)]
    case=dict(seed=0,family='fixture',context='mean',tickets=qs);item=execute(case,BAND,'fixture/Band_projection')
    c=x.Controller(frozen,initial,x.LONG);lanes=x.core.empty_lanes(35e9);c.observe(35e9,lanes);action=dict(jobs=[],base=True)
    projection=x.project_band(c.estimates,c.profiles,qs,lanes,35e9,action,'mean',c.band)
    calendar=prior.x.micro.extract_calendar(item['result']);assert projection['dispatches']==[dict(request_id=j['request_id'],backend=j['backend'],at_ns=round(j['start_ns'])) for j in calendar]
    f=c.forecast(qs,lanes,35e9,action,'mean');assert f['valid']
    assert abs(f['remaining_increment_j']+initial['preload_power_w']*120-item['row']['energy_j'])<1e-8
    assert abs(f['global_peak_ap_c']-item['row']['peak_ap_c'])<1e-8
    qs=[ticket('normal',0,'detection',35.,6.),ticket('urgent',1,arrival=35.1)];case=dict(seed=0,family='fixture',context='mean',tickets=qs)
    item=execute(case,x.LONG,'fixture/urgent_interrupt',True);assert min(r['dispatch_ns'] for r in item['result']['ledger'])==35100000000
    write(BUNDLE/'fixture_verification.json',dict(status='PASS',Band_projection_calendar_and_cost_parity=True,urgent_interrupt_ns=35100000000,environment_starts=2,learning_starts=0,device_commands=0))

def select(rows):
    grouped={(r['seed'],r['family'],r['context'],r['policy']):r for r in rows};eligibility={};eligible=[]
    for policy in (x.SHORT,x.LONG):
        pairs=[];seed_gains=set()
        for row in (r for r in rows if r['policy']==policy):
            refs=[grouped[row['seed'],row['family'],row['context'],p] for p in (BAND,TRITON)];ps=[compare(row,r) for r in refs]
            pairs.append((row,ps))
            if row['family'] in ('low','sustained') and all(p['heat_gain'] for p in ps):seed_gains.add(row['seed'])
        good=all(all(p['nonworse'] for p in ps) for _,ps in pairs) and seed_gains=={813010101,813010102}
        key=(max(p['delta_peak_ap_c'] for _,ps in pairs for p in ps),sum(r['energy_j'] for r,_ in pairs)/24,x.LIMITS[policy])
        eligibility[policy]=dict(eligible=good,nonworse_conditions=sum(all(p['nonworse'] for p in ps) for _,ps in pairs),heat_gain_seed_count=len(seed_gains),ranking=list(key))
        if good:eligible.append((key,policy))
    return dict(utc=utc(),chosen=min(eligible)[1] if eligible else None,development_eligibility=eligibility,final_consumed=False,criterion='predeclared all24 paired nonworse and primary heat gain both seeds; final cannot select winner')

def run():
    prepare();owner=LOCAL/'owner.json';assert not owner.exists(),'preserve owner';write(owner,dict(pid=os.getpid(),utc=utc()))
    data=read(BUNDLE/'inputs.json')
    try:
        fixtures(data)
        for split in ('development','final'):
            if split=='final':assert (BUNDLE/'selection.json').exists()
            rows=[]
            for i,case in enumerate(data['cases'][split]):
                for policy in POLICIES:rows.append(execute(case,policy,f'{split}/{i}/{policy}')['row'])
                print(json.dumps(dict(split=split,conditions_done=i+1,total=24,environment_starts=used()['new_environment_starts'])),flush=True)
            write(BUNDLE/f'{split}_rows.json',rows)
            if split=='development':
                selection=select(rows)
                if (BUNDLE/'selection.json').exists():assert read(BUNDLE/'selection.json')['chosen']==selection['chosen']
                else:write(BUNDLE/'selection.json',selection)
        write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=used(),development_rows=168,final_rows=168))
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run','status']);a=parser.parse_args()
    if a.command=='prepare':prepare();print(json.dumps(used()))
    elif a.command=='run':run()
    else:print(json.dumps(used(),indent=2))
