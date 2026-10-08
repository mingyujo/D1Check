"""Bounded micro-calendar oracle and original-engine witness verification."""
from __future__ import annotations
import argparse,gzip,hashlib,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_micro_schedule_oracle as x
from tools import d1_external_rules_study as audit

ROOT=x.p.ROOT;BUNDLE=ROOT/'docs/results/micro_oracle_01';LOCAL=ROOT/'output/micro_oracle_20261009_v1'
BAND=x.external.BAND;TRITON='TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1';EDD='IE_EDD_ECT_LANE_PC_V1'
POLICIES=(BAND,TRITON,EDD,x.SLACK,x.FLEX);CONTEXTS=('mean','short_context','long_context')
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def entries(path):return [json.loads(s) for s in Path(path).read_text(encoding='utf8').splitlines()] if Path(path).exists() else []
def used():
    historical=('reserved_thermal_20261008_v1','ie_dispatch_20261008_v1','edd_ect_residual_prototype_20261008_v1',
        'edd_ect_residual_learning_20261008_v1','cpu_gpu_method_20261008_v1','ie_candidates_20261008_v2')
    counts=[sum(r['event']=='start' for r in entries(ROOT/'output'/name/'executions.jsonl')) for name in historical]
    if counts!=[2241,584,91,0,717,1422]:raise RuntimeError('historical budget changed; preserve and re-register')
    es=entries(LOCAL/'executions.jsonl');starts=[e for e in es if e['event']=='start']
    return dict(previous_environment_starts=5055,new_environment_starts=len(starts),cumulative_environment_starts=5055+len(starts),
        cumulative_learning_starts=641,new_learning_starts=0,failed=sum(e['event']=='failed' for e in es),device_commands=0)
def append(event,**fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as f:
        f.write(json.dumps(dict(event=event,utc=utc(),**fields),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())


def prepare():
    if (BUNDLE/'registration.json').exists():return check()
    BUNDLE.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
    for name in ('ie_candidates_20261008_v2','cpu_gpu_method_20261008_v1'):
        if (ROOT/'output'/name/'owner.json').exists():raise RuntimeError('preserve existing owner')
    frozen,_=x.p.inputs(x.p.BUNDLE);initial=read(ROOT/'docs/results/external_rules_02/inputs.json')['initial']
    cases=[]
    for seed in (812000001,812000002):
        for family in ('low','queue','burst','sustained'):
            full=x.external.old.workload(family,seed)
            ids={q['id'] for task in ('classification','detection') for q in [r for r in full if r['task']==task][:2]}
            tickets=[q for q in full if q['id'] in ids]
            assert len(tickets)==4 and len({q['id'] for q in tickets})==4
            for context in CONTEXTS:cases.append(dict(seed=seed,family=family,context=context,tickets=tickets))
    write(BUNDLE/'inputs.json',dict(initial=initial,cases=cases))
    sources=dict(read(ROOT/'docs/results/ie_candidates_v2/registration.json')['sources'])
    for rel in ('tools/d1_micro_schedule_oracle.py','tools/d1_micro_oracle_study.py','tools/test_d1_micro_schedule_oracle.py'):
        sources[rel]=sha(ROOT/rel)
    reg=dict(task='IE-MICRO-ORACLE-01',registered_utc=utc(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        sources=sources,inputs_sha256=sha(BUNDLE/'inputs.json'),cases=24,requests_per_case=4,baselines=list(POLICIES),
        source_data_role='first two requests per task in two already consumed training traces, eight workload-derived microcases; NOT new independent holdout',
        grid_ns=100000000,per_job_delay_ns=3000000000,domain='arrival + k*100ms for k0..30, plus that request native Band start',
        raw_calendar_cap_per_case=20000000,raw_calendar_cap_total=110000000,environment_cap=320,learning_starts=0,wall_seconds=3600,save_reserve_seconds=300,
        prior=used(),whole_environment_cap=20000,reference_contract='complete work, failures/P95/J/AP nonworse versus BOTH original Band/Triton; strict joint/heat/energy gains separately',
        secondary_contract='add normal mean completion nonworsening; diagnostic, not retroactive change to original gate',
        oracle='future arrivals and realized context known OFFLINE; full 120s J, AP35..180 original 1s grid; exhaustive finite calendars, no continuous/global online optimum claim',
        current_RL_action_space='oracle 3s delay domain is an explicit relaxation; current 0.25s cooling credit is NOT silently widened',
        robustness='replay same mean-selected calendar under short/long whole-phase context vectors, true lane ownership rechecked; no invented thermal slowdown',
        expected_engine_max=272,engine_error_and_fixture_margin=48,model_sha256=x.p.MODEL_SHA,initial_source_sha256=x.p.INITIAL_SHA,
        device_commands=0,NPU=False,experiment_ready=False,no_new_model_or_coefficients=True,representative=dict(seed=812000001,family='queue',context='mean'))
    write(BUNDLE/'registration.json',reg);write(LOCAL/'registration.json',reg);return reg


def check():
    reg=read(BUNDLE/'registration.json');assert reg==read(LOCAL/'registration.json')
    sources=dict(reg['sources'])
    if (BUNDLE/'repair.json').exists():sources.update(read(BUNDLE/'repair.json')['source_overrides'])
    for path,digest in sources.items():
        if sha(ROOT/path)!=digest:raise ValueError('source drift '+path)
    if sha(BUNDLE/'inputs.json')!=reg['inputs_sha256']:raise ValueError('input drift')
    return reg


def time_left():
    reg=check();elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(reg['registered_utc'])).total_seconds()
    if elapsed>=reg['wall_seconds']-300 or (LOCAL/'STOP_REQUEST.json').exists():raise TimeoutError('save/stop boundary')
    return time.monotonic()+reg['wall_seconds']-300-elapsed


def execute(case,policy,identity,calendar=None):
    path=LOCAL/'items'/(identity.replace('/','__')+'.json.gz');path.parent.mkdir(exist_ok=True)
    if path.exists():
        es=[e for e in entries(LOCAL/'executions.jsonl') if e['event']=='completed' and e['identity']==identity]
        if len(es)!=1 or sha(path)!=es[0]['artifact_sha256']:raise ValueError('unsealed item '+identity)
        return json.loads(gzip.decompress(path.read_bytes()))
    time_left();u=used()
    if u['new_environment_starts']>=320 or u['cumulative_environment_starts']>=20000:raise RuntimeError('environment ceiling')
    if any(e['event']=='start' and e['identity']==identity for e in entries(LOCAL/'executions.jsonl')):raise RuntimeError('charged identity already started')
    n=u['new_environment_starts']+1;append('start',number=n,identity=identity,kind='calendar_replay' if calendar else 'baseline')
    frozen,_=x.p.inputs(x.p.BUNDLE);initial=read(BUNDLE/'inputs.json')['initial'];began=time.perf_counter()
    try:
        result,c=x.simulate(frozen,initial,case['tickets'],case['context'],policy,calendar)
        audit.audit(result,case['tickets']);row,curves=audit.metrics(result,c,initial,frozen)
        row.update(seed=case['seed'],family=case['family'],context=case['context'],policy=policy,identity=identity,host_wall_s=time.perf_counter()-began)
        item=dict(row=row,result=result,curves=curves,planned_calendar=calendar)
        path.write_bytes(gzip.compress(json.dumps(item,allow_nan=False).encode(),mtime=0))
        append('completed',number=n,identity=identity,row=row,artifact_sha256=sha(path))
        return item
    except BaseException as e:append('failed',number=n,identity=identity,error=repr(e));raise


def run():
    prepare();owner=LOCAL/'owner.json'
    if owner.exists():raise RuntimeError('owner exists; inspect without terminating it')
    write(owner,dict(pid=os.getpid(),utc=utc()))
    frozen,_=x.p.inputs(x.p.BUNDLE);data=read(BUNDLE/'inputs.json');model=x.PulseModel(frozen,data['initial']);results=[];raw_total=0
    try:
        for index,case in enumerate(data['cases']):
            baselines={p:execute(case,p,f'base/{index}/{p}') for p in POLICIES}
            calendar=x.extract_calendar(baselines[BAND]['result'])
            replay=execute(case,x.ORACLE,f'band_repeat/{index}',calendar)
            assert [{k:v for k,v in r.items() if k!='source_request_id'} for r in replay['result']['ledger']]==[{k:v for k,v in r.items() if k!='source_request_id'} for r in baselines[BAND]['result']['ledger']], 'native Band calendar repeat differs'
            profile=x.p.profile(frozen,case['context']);path=LOCAL/f'oracle_{index:02d}.json'
            if path.exists():answer=read(path)
            else:
                answer=x.enumerate_calendars(case['tickets'],profile,model,[baselines[BAND]['row'],baselines[TRITON]['row']],calendar,
                    deadline=time_left(),stop=lambda:(LOCAL/'STOP_REQUEST.json').exists())
                write(path,answer)
            raw_total+=answer['counts']['raw']
            if raw_total>110000000:raise RuntimeError('registered oracle calculation ceiling')
            verified={};known={}
            for role,key in [('min_J','energy_min_ap_cap'),('min_AP','ap_min_energy_cap'),('joint','joint_witness'),('normal_guard','normal_mean_guard_witness')]:
                w=answer[key]
                if w is None:continue
                fingerprint=hashlib.sha256(json.dumps(w['calendar'],sort_keys=True).encode()).hexdigest()
                if fingerprint not in known:known[fingerprint]=execute(case,x.ORACLE,f'witness/{index}/{role}',w['calendar'])
                verified[role]=known[fingerprint]
                for metric in ('energy_j','peak_ap_c'):
                    if abs(w[metric]-verified[role]['row'][metric])>1e-8:raise AssertionError('pulse/engine '+metric+' parity')
            record=dict(case=case,baselines={k:v['row'] for k,v in baselines.items()},band_calendar=calendar,oracle=answer,verified={k:v['row'] for k,v in verified.items()})
            write(BUNDLE/f'case_{index:02d}.json',record);results.append(record)
            print(json.dumps(dict(case=index+1,total=24,visited=answer['counts']['visited'],raw=answer['counts']['raw'],joint=answer['counts']['joint_gain'],engine_starts=used()['new_environment_starts'])),flush=True)
        # Mean-derived OFFLINE calendars stay fixed under two alternative costs.
        robustness=[]
        for index,record in enumerate(results):
            if record['case']['context']!='mean':continue
            for role,key in [('min_J','energy_min_ap_cap'),('min_AP','ap_min_energy_cap')]:
                w=record['oracle'][key]
                if w is None:continue
                for context in ('short_context','long_context'):
                    case=dict(record['case'],context=context);item=execute(case,x.ORACLE,f'robust/{index}/{role}/{context}',w['calendar'])
                    robustness.append(dict(nominal_case=index,role=role,actual_context=context,row=item['row']))
        write(BUNDLE/'robustness.json',robustness)
        write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),consumption=used(),cases=24,raw_calendars=raw_total,oracle_evaluations=sum(r['oracle']['counts']['visited'] for r in results)))
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid():owner.unlink()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','status']);a=p.parse_args()
    if a.command=='prepare':prepare();print(json.dumps(used()))
    elif a.command=='run':run()
    else:print(json.dumps(used(),indent=2))
