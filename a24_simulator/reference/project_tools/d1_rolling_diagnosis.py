"""Frozen-action native replays and causal-prefix diagnostics, not a policy.

Stored actual arrivals are used for hindsight descriptions only. The forecast
auditor receives the same arrived queue and public lanes as the original policy.
"""
import argparse,copy,csv,gzip,json,math,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_rolling_joint_study as parent
x=parent.x;ROOT=parent.ROOT
BUNDLE=ROOT/'docs/results/rolling_diagnosis_01';LOCAL=ROOT/'output/rolling_diagnosis_20261009_v1'
read=parent.read;write=parent.write;sha=parent.sha;utc=parent.utc

def events():
    p=LOCAL/'executions.jsonl'
    return [json.loads(s) for s in p.read_text(encoding='utf8').splitlines()] if p.exists() else []
def consumption():
    assert parent.used()['cumulative_environment_starts']==6296
    es=events();n=sum(r['event']=='start' for r in es)
    return dict(previous_environment_starts=6296,new_environment_starts=n,cumulative_environment_starts=6296+n,
        cumulative_learning_starts=641,new_learning_starts=0,failed=sum(r['event']=='failed' for r in es),device_commands=0)
def append(event,**fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:
        f.write(json.dumps(dict(event=event,utc=utc(),**fields),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    parent.check();assert not (parent.LOCAL/'owner.json').exists()
    BUNDLE.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
    sources=dict(read(parent.BUNDLE/'registration.json')['sources']);sources['tools/d1_rolling_diagnosis.py']=sha(Path(__file__))
    reg=dict(task='IE-ROLLING-DIAGNOSIS-01',registered_utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        sources=sources,parent_registration_sha256=sha(parent.BUNDLE/'registration.json'),parent_artifact_manifest_sha256=sha(parent.BUNDLE/'artifact_manifest.json'),
        parent_receipts_sha256=sha(parent.LOCAL/'executions.jsonl'),prior=consumption(),environment_cap=32,expected_environment_starts=24,
        wall_seconds=1800,save_reserve_seconds=300,
        scope='both original joint policies, all six sustained contexts in development and previously consumed final; forced stored actions are hindsight replay, not an online scheduler or fresh validation',
        snapshot_selection='first four recorded planning callbacks per case with candidate_count>8; all valid mean-screen candidates get full arrived-queue three-context evaluation; max72 finite plans',
        prefix_audit='all selected recorded plans: compare full committed plan with first actually executed single/pair, first cooling or first resource wait plus Band suffix in all3 contexts',
        assertions='exact native ledger/transitions/decisions replay; recorded full metrics recovered; no new learning/device/coefficients or changes to old source/criteria',
        fresh_followup_seeds=[815030101,815030102],followup='No followup simulation here; a separate source/input/budget registration must be frozen after development diagnosis')
    write(BUNDLE/'registration.json',reg);return reg
def check():
    r=read(BUNDLE/'registration.json')
    for p,h in r['sources'].items():assert sha(ROOT/p)==h,p
    assert sha(parent.BUNDLE/'registration.json')==r['parent_registration_sha256']
    assert sha(parent.BUNDLE/'artifact_manifest.json')==r['parent_artifact_manifest_sha256']
    assert sha(parent.LOCAL/'executions.jsonl')==r['parent_receipts_sha256'];return r
def budget():
    r=check();elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(r['registered_utc'])).total_seconds()
    if elapsed>=r['wall_seconds']-r['save_reserve_seconds']:raise TimeoutError('diagnosis save boundary')
    return time.monotonic()+r['wall_seconds']-r['save_reserve_seconds']-elapsed
def metrics(f):
    keys=('valid','reason','peak_ap_c','global_peak_ap_c','remaining_increment_j','urgent_misses','normal_misses','urgent_p95_ms','normal_mean_ms','lane_end_s')
    return {k:f[k] for k in keys if k in f}
def key(forecasts,refs,index):
    if not all(x.acceptable(forecasts[c],refs[c]) for c in x.core.CONTEXTS):return None
    d=max(forecasts[c]['peak_ap_c']-refs[c]['peak_ap_c'] for c in x.core.CONTEXTS)
    j=max(forecasts[c]['remaining_increment_j']-refs[c]['remaining_increment_j'] for c in x.core.CONTEXTS)
    if d>=-x.EPS and j>=-x.EPS:return None
    return (d,j,max(f['normal_mean_ms'] or 0. for f in forecasts.values()),index)
def shortlist(screened):
    out=[];counts={}
    for score,first,i,plan in sorted(screened,key=lambda q:q[0]):
        if counts.get(first,0)>=2:continue
        counts[first]=counts.get(first,0)+1;out.append((i,plan))
        if len(out)==8:break
    return out
def immediate_plan(plan,decision,next_decision,now):
    # Match the original actually committed compatible same-time bundle only.
    n=1
    if decision.get('selected') and next_decision and next_decision['now_ns']==now and next_decision.get('action_kind')=='bundle_commit':n=2
    return copy.deepcopy(plan[:n])

class Replay(x.Controller):
    def __init__(self,frozen,initial,item):
        super().__init__(frozen,initial,item['row']['policy']);self.item=item;self.index=0;self.plan_index=0
        self.prefix_records=[];self.loss_records=[];self.captured=0;self.recovered_metrics=0;self.execution_deadline=budget()
    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now);d=copy.deepcopy(self.item['result']['decisions'][self.index]);self.index+=1
        assert d['now_ns']==now,'stored decision time differs'
        if 'expected_ns' in d:assert d['expected_ns']==self.band.expected,'EMA replay differs'
        records=self.item['plans'];record=records[self.plan_index] if self.plan_index<len(records) else None
        if record and record['now_ns']==now and d.get('action_kind')!='bundle_commit' and d['reason']!='rolling_hold_until_arrival_or_lane_release':
            window=x.window_requests(self,queue,lanes,now)
            if [q['id'] for q in window]==record['window_ids']:
                self.plan_index+=1;self.audit_plan(record,queue,lanes,now,d)
        if d.get('action_kind')=='cool_wait':self.cool_since=now
        return d
    def audit_plan(self,record,queue,lanes,now,d):
        if not record['selected_plan'] and not (record['candidate_count']>8 and self.captured<4):return
        refs={c:x.fast.forecast(self,queue,lanes,now,dict(jobs=[]),c) for c in x.core.CONTEXTS}
        if record['selected_plan']:
            plan=record['selected_plan'];full={c:x.forecast_plan(self,queue,lanes,now,plan,c) for c in x.core.CONTEXTS}
            for c in x.core.CONTEXTS:
                for k,v in record['forecast_metrics'][c].items():
                    actual=full[c][k]
                    assert actual==v if v is None else abs(actual-v)<=1e-9,(now,c,k,actual,v)
            self.recovered_metrics+=1
            next_d=self.item['result']['decisions'][self.index] if self.index<len(self.item['result']['decisions']) else None
            prefix=immediate_plan(plan,d,next_d,now);first={c:x.forecast_plan(self,queue,lanes,now,prefix,c) for c in x.core.CONTEXTS}
            violations={c:[k for k in ('urgent_misses','normal_misses','urgent_p95_ms','remaining_increment_j','global_peak_ap_c') if first[c].get('valid') and first[c].get(k) is not None and refs[c].get(k) is not None and first[c][k]>refs[c][k]+x.EPS] for c in x.core.CONTEXTS}
            self.prefix_records.append(dict(now_ns=now,queued_ids=[q['id'] for q in queue],original_action=d,
                plan=plan,actual_prefix=prefix,full_guard_pass=all(x.acceptable(full[c],refs[c]) for c in x.core.CONTEXTS),
                actual_prefix_guard_pass=all(x.acceptable(first[c],refs[c]) for c in x.core.CONTEXTS),violations=violations,
                references={c:metrics(f) for c,f in refs.items()},full={c:metrics(f) for c,f in full.items()},first={c:metrics(f) for c,f in first.items()}))
        if record['candidate_count']<=8 or self.captured>=4:return
        self.captured+=1;window=x.window_requests(self,queue,lanes,now);plans=x.candidate_plans(window,self.credit,self.allow_wait);assert len(plans)==record['candidate_count']
        screened=[]
        for i,plan in enumerate(plans):
            f=x.forecast_plan(self,window,lanes,now,plan,'mean')
            if f['valid']:screened.append(((f['urgent_misses'],f['normal_misses'],f['remaining_increment_j'],f['peak_ap_c'],f['urgent_p95_ms'] or 0.,i),(plan[0]['request_id'],plan[0]['backend'],plan[0]['delay_ns']),i,plan))
        short=shortlist(screened);assert len(short)==record['full_plan_count'];short_ids={i for i,p in short};evaluated=[]
        for score,signature,i,plan in screened:
            f={c:x.forecast_plan(self,queue,lanes,now,plan,c) for c in x.core.CONTEXTS};k=key(f,refs,i)
            evaluated.append(dict(index=i,in_shortlist=i in short_ids,plan=plan,score=list(k) if k else None,forecasts={c:metrics(v) for c,v in f.items()}))
        eligible=[r for r in evaluated if r['score'] is not None];short_ok=[r for r in eligible if r['in_shortlist']]
        best=min(eligible,key=lambda r:r['score']) if eligible else None;chosen=min(short_ok,key=lambda r:r['score']) if short_ok else None
        assert (chosen['plan'] if chosen else None)==record['selected_plan'],'original shortlist selection differs'
        self.loss_records.append(dict(now_ns=now,queued_ids=[q['id'] for q in queue],window_ids=record['window_ids'],candidate_count=len(plans),valid_mean_count=len(screened),
            shortlist_count=len(short),all_eligible_count=len(eligible),shortlist_eligible_count=len(short_ok),
            omitted_improving_plan=bool(best and (chosen is None or tuple(best['score'][:3])<tuple(chosen['score'][:3]))),
            shortlist_best=chosen,full_finite_best=best,evaluated=evaluated))

def execute(split,index,case,policy):
    identity=f'{split}/{index}/{policy}';target=LOCAL/'items'/(identity.replace('/','__')+'.json.gz');target.parent.mkdir(exist_ok=True)
    if target.exists():
        old=[e for e in events() if e['event']=='completed' and e['identity']==identity];assert len(old)==1 and sha(target)==old[0]['artifact_sha256']
        return json.loads(gzip.decompress(target.read_bytes()))
    budget();u=consumption();assert u['new_environment_starts']<32 and u['cumulative_environment_starts']<20000
    assert not any(e['event']=='start' and e['identity']==identity for e in events())
    receipt=next(e for e in parent.events() if e['event']=='completed' and e['identity']==identity)
    source=parent.LOCAL/'items'/(identity.replace('/','__')+'.json.gz');assert sha(source)==receipt['artifact_sha256']
    item=json.loads(gzip.decompress(source.read_bytes()));append('start',identity=identity,number=u['new_environment_starts']+1,source_sha256=sha(source));started=time.perf_counter()
    try:
        frozen,_=x.p.inputs(x.p.BUNDLE);initial=read(parent.BUNDLE/'inputs.json')['initial'];c=Replay(frozen,initial,item);profile=x.p.profile(frozen,case['context'])
        vectors=dict(cells={k:[dict(source_request_id='rolling_joint_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in profile.items()})
        result=x.fast.old.external.old.engine.simulate(dict(protocol=x.p.VERSION,cells=x.p.profile(frozen)),vectors,case['tickets'],policy=c.policy,settings=x.fast.old.external.settings(),seed=201,decision_provider=c)
        parent.audit.audit(result,case['tickets']);assert c.index==len(item['result']['decisions']) and c.plan_index==len(item['plans'])
        for k in ('ledger','transitions','decisions'):assert result[k]==item['result'][k],k
        out=dict(identity=identity,split=split,seed=case['seed'],context=case['context'],policy=policy,exact_replay=True,selected_metric_recoveries=c.recovered_metrics,
            prefixes=c.prefix_records,shortlist_snapshots=c.loss_records,host_wall_s=time.perf_counter()-started,source_sha256=sha(source))
        target.write_bytes(gzip.compress(json.dumps(out,allow_nan=False).encode(),mtime=0));append('completed',identity=identity,artifact_sha256=sha(target))
        return out
    except BaseException as e:append('failed',identity=identity,error=repr(e));raise
def run():
    prepare()
    if (BUNDLE/'completion.json').exists():return read(BUNDLE/'completion.json')
    owner=LOCAL/'owner.json';assert not owner.exists();write(owner,dict(pid=os.getpid(),utc=utc()));data=read(parent.BUNDLE/'inputs.json');out=[]
    try:
        for split in ('development','final'):
            for i,case in enumerate(data['cases'][split]):
                if case['family']!='sustained':continue
                for policy in parent.NEW:
                    out.append(execute(split,i,case,policy));print(json.dumps(dict(done=len(out),total=24,consumption=consumption())),flush=True)
        write(BUNDLE/'diagnosis.json',out);write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=consumption(),exact_replays=len(out)))
        return read(BUNDLE/'completion.json')
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','status']);a=p.parse_args()
    if a.command=='prepare':print(json.dumps(prepare(),indent=2))
    elif a.command=='run':print(json.dumps(run(),indent=2))
    else:print(json.dumps(consumption(),indent=2))
