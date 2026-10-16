"""Bounded loaded-snapshot diagnosis, retaining immutable old experiment paths."""
from __future__ import annotations
import argparse,gzip,hashlib,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_busy_schedule_oracle as x
from tools import d1_micro_oracle_study as prior
from tools import d1_external_rules_study as audit

ROOT=x.p.ROOT;BUNDLE=ROOT/'docs/results/busy_oracle_01';LOCAL=ROOT/'output/busy_oracle_20261009_v1'
BAND=prior.BAND;TRITON=prior.TRITON;EDD=prior.EDD
POLICIES=(BAND,TRITON,EDD,x.micro.SLACK,x.micro.FLEX,'IE_ENERGY_AP_LIST_V2','IE_ROLLING_ENERGY_CPSAT_AP_FILTER_V2')
read=prior.read;write=prior.write;sha=prior.sha;utc=prior.utc


def entries():return prior.entries(LOCAL/'executions.jsonl')
def used():
    old=prior.used();assert old['cumulative_environment_starts']==5255 and old['cumulative_learning_starts']==641
    es=entries();n=sum(e['event']=='start' for e in es)
    return dict(previous_environment_starts=5255,new_environment_starts=n,cumulative_environment_starts=5255+n,new_learning_starts=0,cumulative_learning_starts=641,failed=sum(e['event']=='failed' for e in es),device_commands=0)
def append(event,**fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:
        f.write(json.dumps(dict(event=event,utc=utc(),**fields),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())


def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    BUNDLE.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
    cases=[];screen=[];artifacts={}
    for i in range(48):
        path=ROOT/'output/ie_candidates_20261008_v2/items'/f'final__{BAND}__{i}.json.gz'
        item=json.loads(gzip.decompress(path.read_bytes()));row=item['row'];tickets=x.external.old.workload(row['family'],row['seed'])
        receipts=prior.entries(ROOT/'output/ie_candidates_20261008_v2/executions.jsonl')
        assert any(e['event']=='completed' and e['identity']==row['identity'] and e['artifact_sha256']==sha(path) for e in receipts)
        snap=x.snapshot(tickets,item['ledger']);artifacts[path.relative_to(ROOT).as_posix()]=sha(path)
        screen.append(dict(source_index=i,seed=row['seed'],family=row['family'],context=row['context'],eligible=snap is not None,reason='first qualifying busy snapshot' if snap else 'no instant with active job and two queued requests of each task'))
        if snap:cases.append(dict(seed=row['seed'],family=row['family'],context=row['context'],source_index=i,source_prefix_ledger=[r for r in item['ledger'] if r['id'] in {j['request_id'] for j in snap['prefix_calendar']}],**snap))
    assert len(cases)==4,'structural inventory changed; do not silently alter selection'
    initial=read(ROOT/'docs/results/external_rules_02/inputs.json')['initial'];write(BUNDLE/'inputs.json',dict(initial=initial,cases=cases,screening=screen))
    sources=dict(read(ROOT/'docs/results/micro_oracle_01/registration.json')['sources'])
    for rel in ('tools/d1_busy_schedule_oracle.py','tools/d1_busy_oracle_study.py','tools/test_d1_busy_schedule_oracle.py'):sources[rel]=sha(ROOT/rel)
    reg=dict(task='IE-BUSY-ORACLE-01',registered_utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,sources=sources,consumed_source_artifacts=artifacts,inputs_sha256=sha(BUNDLE/'inputs.json'),cases=4,baselines=list(POLICIES),
        selection='screen all prior 48 final Band ledgers; earliest arrival/dispatch/release boundary BEFORE same-time dispatch with active job and >=2 queued per task; first2 EDD within each task; no performance-based selection',
        scope='conditional microproblem: retain every already-dispatched prefix job and four selected queued jobs; omit other waiting/future jobs explicitly; do not claim full-arrival throughput improvement or independent holdout',
        prefix='replay all native prefix dispatches; feed public history to each tail; original measured preload/energy/AP state from time0, no reset at snapshot; true running jobs remain nonpreemptive',
        domain='snapshot+k*100ms k0..30, plus each job native Band AND Triton start; four legal backend assignments; exhaustive finite space only',
        reference_contract='complete retained requests, failures/P95/J/AP nonworse versus BOTH conditional Band/Triton; strict joint gain requires both J/AP strict; normal mean extra diagnostic only',
        raw_calendar_cap_per_case=20000000,raw_calendar_cap_total=80000000,environment_cap=80,wall_seconds=3600,save_reserve_seconds=300,expected_environment_max=54,learning_starts=0,prior=used(),whole_environment_cap=20000,
        robustness='same mean prefix and mean optimized tail under short/long vectors; original capacity guard may delay starts; fixed-plan stress, no new coefficients or independent repeats',
        representative_source_index=6,current_RL_credit_s=.25,oracle_wait_relaxation_s=3,model_sha256=x.p.MODEL_SHA,initial_source_sha256=x.p.INITIAL_SHA,device_commands=0,NPU=False,experiment_ready=False)
    write(BUNDLE/'registration.json',reg);write(LOCAL/'registration.json',reg);return reg


def check():
    reg=read(BUNDLE/'registration.json');assert reg==read(LOCAL/'registration.json')
    sources=dict(reg['sources'])
    if (BUNDLE/'repair.json').exists():sources.update(read(BUNDLE/'repair.json')['source_overrides'])
    for rel,digest in sources.items():assert sha(ROOT/rel)==digest,rel
    assert sha(BUNDLE/'inputs.json')==reg['inputs_sha256'];return reg
def deadline():
    reg=check();elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(reg['registered_utc'])).total_seconds()
    if elapsed>=reg['wall_seconds']-300 or (LOCAL/'STOP_REQUEST.json').exists():raise TimeoutError('save boundary')
    return time.monotonic()+reg['wall_seconds']-300-elapsed


def execute(case,policy,identity,calendar=None):
    path=LOCAL/'items'/(identity.replace('/','__')+'.json.gz');path.parent.mkdir(exist_ok=True)
    if path.exists():
        item=json.loads(gzip.decompress(path.read_bytes()));receipt=[e for e in entries() if e['event']=='completed' and e['identity']==item['row']['identity']];assert len(receipt)==1 and sha(path)==receipt[0]['artifact_sha256']
        return item
    deadline();u=used();assert u['new_environment_starts']<80 and u['cumulative_environment_starts']<20000
    original=identity;attempt=0
    while any(e['event']=='start' and e['identity']==identity for e in entries()):
        assert any(e['event']=='failed' and e['identity']==identity for e in entries()),'unsealed started execution'
        attempt+=1;identity=original+f'/retry_{attempt}'
    n=u['new_environment_starts']+1;append('start',number=n,identity=identity,kind='oracle_replay' if calendar else 'conditional_baseline')
    began=time.perf_counter()
    try:
        frozen,_=x.p.inputs(x.p.BUNDLE);initial=read(BUNDLE/'inputs.json')['initial'];result,c=x.simulate(frozen,initial,case,policy,calendar)
        audit.audit(result,case['tickets']);row,curves=audit.metrics(result,c,initial,frozen)
        row.update(seed=case['seed'],family=case['family'],context=case['context'],source_index=case['source_index'],policy=policy,identity=identity,host_wall_s=time.perf_counter()-began)
        item=dict(row=row,result=result,curves=curves,planned_calendar=calendar);path.write_bytes(gzip.compress(json.dumps(item,allow_nan=False).encode(),mtime=0))
        append('completed',number=n,identity=identity,artifact_sha256=sha(path));return item
    except BaseException as e:append('failed',number=n,identity=identity,error=repr(e));raise


def run():
    prepare();owner=LOCAL/'owner.json';assert not owner.exists(),'preserve existing owner';write(owner,dict(pid=os.getpid(),utc=utc()))
    data=read(BUNDLE/'inputs.json');frozen,_=x.p.inputs(x.p.BUNDLE);model=x.micro.PulseModel(frozen,data['initial']);records=[];raw_total=0
    try:
        for i,case in enumerate(data['cases']):
            baselines={policy:execute(case,policy,f'base/{i}/{policy}') for policy in POLICIES}
            source={r['id']:r for r in case['source_prefix_ledger']}
            for item in baselines.values():
                for r in item['result']['ledger']:
                    if r['id'] not in source:continue
                    assert {k:v for k,v in r.items() if k!='source_request_id'}=={k:v for k,v in source[r['id']].items() if k!='source_request_id'},'prefix ledger mismatch'
            calendars=[x.micro.extract_calendar(baselines[p]['result']) for p in (BAND,TRITON)]
            tail=[j for j in calendars[0] if j['request_id'] in case['variable_ids']]
            repeat=execute(case,x.ORACLE,f'band_repeat/{i}',tail)
            assert repeat['result']['ledger']==baselines[BAND]['result']['ledger'],'Band calendar parity'
            path=LOCAL/f'oracle_{i}.json'
            answer=read(path) if path.exists() else x.enumerate_calendars(case,x.p.profile(frozen,case['context']),model,[baselines[p]['row'] for p in (BAND,TRITON)],calendars,deadline=deadline())
            write(path,answer);raw_total+=answer['counts']['raw'];assert raw_total<=80000000
            verified={};known={}
            for role,w in answer['witnesses'].items():
                if w is None:continue
                fingerprint=hashlib.sha256(json.dumps(w['calendar'],sort_keys=True).encode()).hexdigest()
                if fingerprint not in known:known[fingerprint]=execute(case,x.ORACLE,f'witness/{i}/{role}',w['calendar'])
                verified[role]=known[fingerprint]['row']
                for k in ('energy_j','peak_ap_c','urgent_p95_ms','normal_mean_ms'):assert abs(w[k]-verified[role][k])<1e-8,(k,w[k],verified[role][k])
            record=dict(case=case,baselines={k:v['row'] for k,v in baselines.items()},oracle=answer,verified=verified);write(BUNDLE/f'case_{i:02d}.json',record);records.append(record)
            print(json.dumps(dict(case=i+1,total=4,counts=answer['counts'],environment_starts=used()['new_environment_starts'])),flush=True)
        robust=[]
        for i,r in enumerate(records):
            if r['case']['context']!='mean':continue
            for role in ('min_J','min_AP'):
                w=r['oracle']['witnesses'][role]
                if w is None:continue
                for context in ('short_context','long_context'):
                    case=dict(r['case'],context=context);item=execute(case,x.ORACLE,f'robust/{i}/{role}/{context}',w['calendar'])
                    # Shared history and same request set must also be used by the actual-context reference.
                    ref=execute(case,BAND,f'robust_ref/{i}/{context}')
                    robust.append(dict(nominal_case=i,role=role,actual_context=context,row=item['row'],reference=ref['row']))
        write(BUNDLE/'robustness.json',robust);write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=used(),cases=4,raw_calendars=raw_total))
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run','status']);a=parser.parse_args()
    if a.command=='prepare':prepare();print(json.dumps(used()))
    elif a.command=='run':run()
    else:print(json.dumps(used(),indent=2))
