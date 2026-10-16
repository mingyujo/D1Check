"""Development-only gate: forced prefix replays, not fresh policy evaluation."""
import argparse,copy,gzip,json,os,subprocess,time
from datetime import datetime,timezone
from tools import d1_rolling_terminal as x
from tools import d1_rolling_prefix_study as parent
ROOT=parent.ROOT;BUNDLE=ROOT/'docs/results/rolling_terminal_01';LOCAL=ROOT/'output/rolling_terminal_20261009_v1'
read=parent.read;write=parent.write;sha=parent.sha;utc=parent.utc
def events():
    p=LOCAL/'executions.jsonl';return [json.loads(s) for s in p.read_text(encoding='utf8').splitlines()] if p.exists() else []
def used():
    assert parent.used()['cumulative_environment_starts']==6466
    es=events();n=sum(r['event']=='start' for r in es)
    return dict(previous_environment_starts=6466,new_environment_starts=n,cumulative_environment_starts=6466+n,cumulative_learning_starts=641,
        new_learning_starts=0,failed=sum(r['event']=='failed' for r in es),device_commands=0)
def append(event,**fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:f.write(json.dumps(dict(event=event,utc=utc(),**fields),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    parent.check();assert read(parent.BUNDLE/'completion.json')['status']=='completed' and not (parent.LOCAL/'owner.json').exists()
    BUNDLE.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
    sources=dict(read(parent.BUNDLE/'registration.json')['sources'])
    for p in ('tools/d1_rolling_terminal.py','tools/test_d1_rolling_terminal.py','tools/d1_rolling_terminal_study.py'):sources[p]=sha(ROOT/p)
    write(BUNDLE/'inputs.json',dict(initial=read(parent.BUNDLE/'inputs.json')['initial'],development=read(parent.BUNDLE/'inputs.json')['cases']['development']))
    r=dict(task='IE-ROLLING-TERMINAL-03',registered_utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        sources=sources,inputs_sha256=sha(BUNDLE/'inputs.json'),parent_manifest_sha256=sha(parent.BUNDLE/'artifact_manifest.json'),parent_receipts_sha256=sha(parent.LOCAL/'executions.jsonl'),
        prior=used(),environment_cap=32,expected_environment_starts=24,wall_seconds=1800,save_reserve_seconds=300,
        scope='development24 traces only, force saved prefix-guard actions and verify exact native ledger/transitions/decisions. Neither new online terminal-policy performance nor independent validation.',
        terminal='actual first prefix + Band suffix versus Band full known-queue forecast; commonH=max(both lane ends) separately within each of three pinned contexts; T(H) and h(H) both nonworse, no fake heat limit',
        model='original g=0, so h is autonomous and terminal h adds no independent workload information; no new thermal coefficient or model change',
        useful_gate='previous first guard passed AND common terminal condition all3 passed AND strict worst first-prefix futureAP orJ decrease vs localBand. Identical first action/forecast never counted as a useful improvement.',
        followup='If useful_gate count is zero stop without new-policy pilot/final/training. Otherwise separately register exactly one terminal candidate and small development/fresh confirmation batch before evaluation.',
        conditional_proof='If T/h are nonworse at commonH, identical future thermal input under the same linear model preserves thermal order. Actual future arrivals/routing differ, so not a future SLA or physical guarantee.',
        representative='first development seed sustained mean, plus earliest common-terminal failure with old first guard pass',new_learning=0,device_commands=0,experiment_ready=False)
    write(BUNDLE/'registration.json',r);return r
def check():
    r=read(BUNDLE/'registration.json')
    sources=dict(r['sources'])
    if (BUNDLE/'repair.json').exists():sources.update(read(BUNDLE/'repair.json')['source_overrides'])
    for p,h in sources.items():assert sha(ROOT/p)==h,p
    assert sha(BUNDLE/'inputs.json')==r['inputs_sha256'] and sha(parent.BUNDLE/'artifact_manifest.json')==r['parent_manifest_sha256']
    assert sha(parent.LOCAL/'executions.jsonl')==r['parent_receipts_sha256'];return r
def deadline():
    r=check();elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(r['registered_utc'])).total_seconds()
    if elapsed>=r['wall_seconds']-r['save_reserve_seconds']:raise TimeoutError('terminal probe save boundary')
    return time.monotonic()+r['wall_seconds']-r['save_reserve_seconds']-elapsed
def matches_plan(record,now,window_ids,reply):
    return bool(record and record['now_ns']==now and record['window_ids']==window_ids and
        reply.get('action_kind')!='bundle_commit' and reply['reason']!='rolling_hold_until_arrival_or_lane_release')
class Replay(parent.x.Controller):
    def __init__(self,frozen,initial,item):
        super().__init__(frozen,initial);self.item=item;self.index=0;self.guard_index=0;self.plan_index=0;self.records=[];self.recovered=0;self.execution_deadline=deadline()
    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        d=copy.deepcopy(self.item['result']['decisions'][self.index]);self.index+=1;assert d['now_ns']==now
        self.validate_public(queue,lanes,now)
        if 'expected_ns' in d:assert d['expected_ns']==self.band.expected
        plans=self.item['plans'];record=plans[self.plan_index] if self.plan_index<len(plans) else None
        matched=matches_plan(record,now,[q['id'] for q in x.old.window_requests(self,queue,lanes,now)],d)
        if matched:self.plan_index+=1
        source=self.item['prefix_guards'];g=source[self.guard_index] if self.guard_index<len(source) else None
        if matched and record['selected_plan'] is not None:
            assert g and g['now_ns']==now,'guard must belong to the matched selected plan'
            self.guard_index+=1;plan=g['actual_prefix']
            first={c:x.old.forecast_plan(self,queue,lanes,now,plan,c) for c in x.CONTEXTS}
            refs={c:x.old.fast.forecast(self,queue,lanes,now,dict(jobs=[]),c) for c in x.CONTEXTS}
            for ctx in x.CONTEXTS:
                for kind,value in (('first',first[ctx]),('references',refs[ctx])):
                    for k,v in g[kind][ctx].items():
                        actual=value[k];assert actual==v if not isinstance(v,(int,float)) else abs(actual-v)<=1e-9,(now,ctx,kind,k,actual,v)
            self.recovered+=1
            result=x.assess(self,queue,lanes,now,plan,first,refs,g['passed'])
            self.records.append(dict(now_ns=now,queue_ids=[q['id'] for q in queue],actual_prefix=plan,action_kind=d.get('action_kind','band_fallback' if d.get('prefix_guard_blocked') else 'resource_wait' if d['reason']=='rolling_selected_resource_wait' else 'single'),
                references={c:{k:v for k,v in f.items() if k in ('valid','reason','peak_ap_c','remaining_increment_j')} for c,f in refs.items()},
                first={c:{k:v for k,v in f.items() if k in ('valid','reason','peak_ap_c','remaining_increment_j')} for c,f in first.items()},**result))
        if d.get('action_kind')=='cool_wait':self.cool_since=now
        return d
def execute(index,case):
    source_identity=f'development/{index}/{parent.x.POLICY}';mapping=read(BUNDLE/'repair.json').get('retry_identity_map',{}) if (BUNDLE/'repair.json').exists() else {}
    identity=mapping.get(source_identity,source_identity);target=LOCAL/'items'/(f'development_{index}_repair1.json.gz' if identity!=source_identity else f'development_{index}.json.gz');target.parent.mkdir(exist_ok=True)
    if target.exists():
        es=[e for e in events() if e['event']=='completed' and e['identity']==identity];assert len(es)==1 and sha(target)==es[0]['artifact_sha256'];return json.loads(gzip.decompress(target.read_bytes()))
    deadline();u=used();assert u['new_environment_starts']<32 and u['cumulative_environment_starts']<20000
    assert not any(e['event']=='start' and e['identity']==identity for e in events())
    source=parent.LOCAL/'items'/(source_identity.replace('/','__')+'.json.gz');receipt=next(e for e in parent.events() if e['event']=='completed' and e['identity']==source_identity);assert sha(source)==receipt['artifact_sha256']
    item=json.loads(gzip.decompress(source.read_bytes()));append('start',identity=identity,number=u['new_environment_starts']+1,source_sha256=sha(source),adapter_sha256=sha(__file__));began=time.perf_counter()
    try:
        frozen,_=x.p.inputs(x.p.BUNDLE);initial=read(BUNDLE/'inputs.json')['initial'];c=Replay(frozen,initial,item);profile=x.p.profile(frozen,case['context'])
        vectors=dict(cells={k:[dict(source_request_id='rolling_prefix_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in profile.items()})
        result=x.old.fast.old.external.old.engine.simulate(dict(protocol=x.p.VERSION,cells=x.p.profile(frozen)),vectors,case['tickets'],policy=c.policy,settings=x.old.fast.old.external.settings(),seed=201,decision_provider=c)
        parent.parent.audit.audit(result,case['tickets']);assert c.index==len(item['result']['decisions']) and c.guard_index==len(item['prefix_guards']) and c.plan_index==len(item['plans'])
        for k in ('ledger','transitions','decisions'):assert result[k]==item['result'][k],k
        out=dict(identity=identity,seed=case['seed'],family=case['family'],context=case['context'],exact_replay=True,planned= len(case['tickets']),completed=sum(r['status']=='succeeded' for r in result['ledger']),
            recovered_first_forecasts=c.recovered,records=c.records,host_wall_s=time.perf_counter()-began,source_sha256=sha(source))
        target.write_bytes(gzip.compress(json.dumps(out,allow_nan=False).encode(),mtime=0));append('completed',identity=identity,artifact_sha256=sha(target));return out
    except BaseException as e:append('failed',identity=identity,error=repr(e));raise
def run():
    prepare()
    if (BUNDLE/'completion.json').exists():return read(BUNDLE/'completion.json')
    owner=LOCAL/'owner.json';assert not owner.exists();write(owner,dict(pid=os.getpid(),utc=utc()));out=[]
    try:
        for i,case in enumerate(read(BUNDLE/'inputs.json')['development']):
            out.append(execute(i,case));print(json.dumps(dict(done=i+1,total=24,starts=used()['new_environment_starts'])),flush=True)
        (BUNDLE/'probe_records.json.gz').write_bytes(gzip.compress(json.dumps(out,separators=(',',':'),allow_nan=False).encode(),mtime=0))
        useful=sum(r['useful'] for item in out for r in item['records'])
        write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=used(),exact_replays=len(out),planned_completed=sum(r['planned'] for r in out),
            first_forecast_recoveries=sum(r['recovered_first_forecasts'] for r in out),useful_count=useful,followup_allowed=useful>0))
        return read(BUNDLE/'completion.json')
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','status']);a=p.parse_args()
    if a.command=='prepare':print(json.dumps(prepare(),indent=2))
    elif a.command=='run':print(json.dumps(run(),indent=2))
    else:print(json.dumps(used(),indent=2))
