"""Prepared full-trace pilot: four native gates then24 cases x four policies.

prepare/check never start a native environment. run starts the immutable clock
only when explicitly invoked; completed/cached runs never acquire fresh budget.
"""
import argparse,copy,gzip,hashlib,json,os,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_rolling_execution_prefix as new
from tools import d1_rolling_prefix_guard as original
from tools import d1_external_rules as external
from tools import d1_triton_rules as triton
from tools import d1_rolling_hybrid_model as hybrid
from tools import d1_rolling_execution_pilot as prepared
ROOT=new.p.ROOT;LOCAL=ROOT/'output/rolling_hybrid_pilot_20261011_v1'
PUBLIC=ROOT/'docs/results/rolling_hybrid_pilot_07'
TASK='ROLLING-HYBRID-PILOT-07'
ROLES=('Band','Triton','OriginalV2','ExecutionPrefix')
SEEDS=(825060101,825060102)
POLICY_IDS=dict(Band=external.BAND,Triton=triton.OFF,OriginalV2=original.POLICY,ExecutionPrefix=new.POLICY)
MODEL_CONTEXT='A24_V3_THERMAL_ONLY_HYBRID_FROZEN_V1'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def serial(v):
    if isinstance(v,dict):return {str(k):serial(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [serial(x) for x in v]
    if hasattr(v,'tolist'):return v.tolist()
    return v
def write(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as f:json.dump(serial(obj),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def sources():
    result={}
    for name,module in sys.modules.copy().items():
        path=getattr(module,'__file__',None)
        if name.startswith('tools.') and path:
            path=Path(path).resolve()
            if path.suffix=='.py' and path.is_relative_to(ROOT):result[path.relative_to(ROOT).as_posix()]=sha(path)
    for path in ['tools/d1_rolling_hybrid_pilot.py','tools/d1_rolling_hybrid_model.py','tools/test_d1_rolling_hybrid_model.py','tools/test_d1_rolling_hybrid_pilot.py']:
        result[path]=sha(ROOT/path)
    return result
def ticket(name,task,at=35.,ordinal=0):return dict(id=name,ordinal=ordinal,task=task,priority='urgent' if task=='classification' else 'normal',
    arrival_ns=round(at*1e9),deadline_offset_ns=1_500_000_000 if task=='classification' else 6_000_000_000)
def fixtures():
    return [dict(mode='arrival_interrupt',tickets=[ticket('D','detection'),ticket('C','classification',35.1,1)]),
        dict(mode='resource_release',tickets=[ticket('D','detection'),ticket('C','classification',35.05,1)]),
        dict(mode='pair',tickets=[ticket('C','classification'),ticket('D','detection',ordinal=1)]),
        dict(mode='cancel_pair',tickets=[ticket('C','classification'),ticket('D','detection',ordinal=1)])]
def prepare():
    if (LOCAL/'registration.json').exists():return check()
    if LOCAL.exists():raise FileExistsError('existing task directory preserved; no fresh budget')
    prepared.check(require_local=True)
    if (prepared.LOCAL/'execution_registration.json').exists() or (prepared.LOCAL/'executions.jsonl').exists() or (prepared.LOCAL/'owner.lock').exists():raise ValueError('original pilot already activated; cannot transfer unused budget')
    reg=copy.deepcopy(read(prepared.LOCAL/'registration.json'));data=read(prepared.LOCAL/'inputs.json')
    reg.update(task=TASK,status='prepared_not_run',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        authorization='latest user instruction: execute rolling pilot using the new simulator; same unused112 cap, not additional112',
        parent_task=prepared.TASK,parent_contract_sha256=sha(prepared.LOCAL/'registration.json'),
        old_model_pilot_status='preserved unexecuted, superseded for this authorization',
        prepared_utc=datetime.now(timezone.utc).isoformat(),execution_started_utc=None,run_requires_subsequent_user_execution_instruction=False,
        model_context=MODEL_CONTEXT,upstream_hybrid_sha256=hybrid.UPSTREAM_SHA,exported_hybrid_sha256=sha(hybrid.MODEL),
        model_sha256=hybrid.UPSTREAM_SHA,original_service_energy_sha256=new.p.MODEL_SHA,
        source_sha256=sources(),forecast_thermal='same frozen v3 head for online screening, prefix guard, final AP path',
        initial_thermal='same measured preload, v3 alpha0.5 initial-state estimator, no workload prehistory',
        thermal_to_service_feedback=False,thermal_to_energy_feedback=False,model_fit_calls=0,
        limitation='v3 AP validated on CPU/PAR n1 each; peak error worsened in CPU. Other traces are bounded model exploration, no strict/safety claim')
    LOCAL.mkdir(parents=True)
    write(LOCAL/'registration.json',reg);write(LOCAL/'inputs.json',data)
    write(PUBLIC/'execution_contract.json',reg);write(PUBLIC/'cases.json',dict(cases=data['cases'],fixtures=data['fixtures']))
    write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='prepared_not_run',consumption=dict(native_environment_starts=0,learning_starts=0,device_commands=0,cumulative_policy_environment_starts=9749,cumulative_policy_learning_starts=1449),next_action='gates4 then fixed96; no learning/device'))
    return check()

def check(require_local=False):
    local=(LOCAL/'registration.json').exists() and (LOCAL/'inputs.json').exists()
    if require_local and not local:raise ValueError('native run requires original local prepared registration and consumption lineage')
    reg=read(LOCAL/'registration.json' if local else PUBLIC/'execution_contract.json')
    for name,h in reg['source_sha256'].items():
        if sha(ROOT/name)!=h:raise ValueError('prepared execution source changed: '+name)
    new.p.inputs(new.p.BUNDLE)
    hybrid.load()
    if sha(hybrid.MODEL)!=reg['exported_hybrid_sha256']:raise ValueError('frozen hybrid changed')
    if (prepared.LOCAL/'execution_registration.json').exists():raise ValueError('old pilot activated after transfer')
    inputs=read(LOCAL/'inputs.json' if local else PUBLIC/'cases.json')
    h=hashlib.sha256(json.dumps(inputs['cases'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if h!=reg['inputs_sha256'] or len(inputs['cases'])!=24:raise ValueError('prepared workload changed')
    return dict(status='PASS_prepared_sources_and_inputs',scope='local_prepared' if local else 'shared_read_only',execution_started=(LOCAL/'execution_registration.json').exists(),
        conditions=24,policies=4,expected_native_starts=100,cap=112,prepared_environment_learning_device_starts=0)

FixtureController=hybrid.FixtureController
controller=hybrid.controller

def audit(result,tickets):
    ledger=result['ledger'];assert {q['id'] for q in ledger}=={q['id'] for q in tickets} and len(ledger)==len(tickets)
    lanes={'CPU':[],'GPU':[]}
    for q in ledger:
        if 'dispatch_ns' not in q:continue
        assert q['backend'] in new.p.backends(q)
        phases=[q[k] for k in ('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns') if k in q]
        assert phases==sorted(phases) and q['dispatch_ns']>=q['arrival_ns']
        if q['status']=='succeeded':
            assert len(phases)==6
            response=q['output_ready_ns'] if q['task']=='classification' else q['persist_complete_ns']
            assert abs(q['response_ns']-(response-q['arrival_ns']))<=1
            assert q['late_success']==(q['response_ns']>q['deadline_offset_ns'])
        lanes[q['backend']].append(q)
    for jobs in lanes.values():
        jobs.sort(key=lambda q:q['dispatch_ns'])
        assert all(a.get('lane_available_ns',120e9)<=b['dispatch_ns'] for a,b in zip(jobs,jobs[1:]))
    for a in lanes['CPU']:
        for b in lanes['GPU']:
            if min(a.get('lane_available_ns',120e9),b.get('lane_available_ns',120e9))>max(a['dispatch_ns'],b['dispatch_ns']):
                assert a['task']=='detection' and b['task']=='classification'
def gate_rows(rows,policy='ExecutionPrefix'):
    expected={(i,role) for i in range(24) for role in ('Band','Triton',policy)}
    relevant=[r for r in rows if r['policy'] in ('Band','Triton',policy)]
    if len(relevant)!=72 or {(r['condition'],r['policy']) for r in relevant}!=expected:
        raise ValueError('missing/duplicate policy-condition rows; no aggregate verdict')
    bases={(r['condition'],r['policy']):r for r in rows if r['policy'] in ('Band','Triton')}
    targets=[r for r in rows if r['policy']==policy];differences=[];maintenance=True
    kpis=('incomplete','urgent_failure','normal_failure','urgent_p95_ms','energy_j','peak_ap_c')
    for row in targets:
        for role in ('Band','Triton'):
            baseline=bases[(row['condition'],role)];delta={k:row[k]-baseline[k] if row[k] is not None and baseline[k] is not None else None for k in kpis}
            full=row['completed']==row['planned']==baseline['completed']==baseline['planned']
            nonworse=full and all(v is not None and v<=0 for v in delta.values())
            primary=row['family'] in ('low','sustained');absolute=not primary or all(row[k]==0 for k in ('incomplete','urgent_failure','normal_failure'))
            passed=nonworse and absolute;maintenance &= passed
            differences.append(dict(condition=row['condition'],family=row['family'],baseline=role,passed=passed,delta=delta))
    promising=[]
    for family in ('low','sustained'):
        subset=[d for d in differences if d['family']==family]
        if maintenance and subset and all(d['passed'] and (d['delta']['energy_j']<0 or d['delta']['peak_ap_c']<0) for d in subset):promising.append(family)
    return dict(maintenance_pass=maintenance,promising=maintenance and bool(promising),promising_families=promising,
        comparisons=len(differences),epsilon=0,learners=0,differences=differences,automatic_adoption=False)

class Budget:
    def __init__(self):
        check(require_local=True);self.reg=read(LOCAL/'registration.json');self.rows=[]
        for line in (LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines() if (LOCAL/'executions.jsonl').exists() else []:
            row=json.loads(line)
            if row.get('event'):self.rows[row['number']-1].update(row)
            else:self.rows.append(row)
        activation=LOCAL/'execution_registration.json'
        if not activation.exists():write(activation,dict(started_utc=datetime.now(timezone.utc).isoformat(),prepared_contract_sha256=sha(LOCAL/'registration.json')))
        self.activation=read(activation)
        assert self.activation['prepared_contract_sha256']==sha(LOCAL/'registration.json')
        self.deadline=datetime.fromisoformat(self.activation['started_utc']).timestamp()+3300
    def used(self):return dict(native_environment_starts=len(self.rows),native_cap=112,learning_starts=0,device_commands=0,
        failed=sum(r['status']=='failed' for r in self.rows),cumulative_policy_environment_starts=9749+len(self.rows),cumulative_policy_learning_starts=1449)
    def append(self,row):
        with (LOCAL/'executions.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(row,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def call(self,identity,phase,case,agent):
        check(require_local=True);path=LOCAL/'items'/(identity+'.json.gz');old=next((r for r in self.rows if r['identity']==identity),None)
        if old:
            if old['status']!='completed' or old['case']!=case or sha(path)!=old['sha256']:raise ValueError('failed/changed consumed run ID')
            return json.loads(gzip.decompress(path.read_bytes()))
        if time.time()>=self.deadline or len(self.rows)>=112 or 9749+len(self.rows)>=20000:raise TimeoutError('original clock/global cap reached')
        if sum(r['phase']==phase for r in self.rows)>=self.reg['phase_caps'][phase]:raise TimeoutError('phase cap')
        start=dict(number=len(self.rows)+1,identity=identity,phase=phase,case=case,status='started',planned=len(case['tickets']))
        self.rows.append(start);self.append(start)
        try:
            frozen,initial=new.p.inputs(new.p.BUNDLE);profile=new.p.profile(frozen,case['context'])
            vectors=dict(cells={k:[dict(source_request_id='common_pilot_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in profile.items()})
            agent.execution_deadline=time.monotonic()+max(0,self.deadline-time.time());began=time.perf_counter()
            result=external.old.engine.simulate(dict(protocol=new.p.VERSION,cells=new.p.profile(frozen)),vectors,case['tickets'],
                policy=agent.policy,settings=self.reg['common_settings'],seed=201,decision_provider=agent)
            seconds=time.perf_counter()-began;audit(result,case['tickets']);ledger=result['ledger'];complete=sum(q['status']=='succeeded' for q in ledger)
            energy=peak=None;curve=[]
            if complete==len(ledger):
                _,costs,end=hybrid.account(result,initial['initial'],frozen);energy=costs['whole_120s_j'];peak=max(costs['ap_path']);curve=list(zip(range(35,end+1),costs['ap_path']))
            segments=new.p.segments([dict(state=q['task']+'_'+q['backend'],start=q['dispatch_ns']/1e9,end=q.get('lane_available_ns',120e9)/1e9) for q in ledger if 'dispatch_ns' in q],0,120)
            row=dict(overlap_s=sum(z['end_s']-z['start_s'] for z in segments if '+' in z['state']),classification_cpu=sum(q['task']=='classification' and q.get('backend')=='CPU' for q in ledger),planned=len(ledger),completed=complete,incomplete=len(ledger)-complete,
                urgent_failure=sum(q['priority']=='urgent' and ('response_ns' not in q or q.get('late_success',True)) for q in ledger),
                normal_failure=sum(q['priority']=='normal' and ('response_ns' not in q or q.get('late_success',True)) for q in ledger),
                urgent_p95_ms=result['metrics']['urgent_p95_ms'],normal_mean_ms=result['metrics']['normal_mean_ms'],
                energy_j=energy,peak_ap_c=peak,surface_temperature=None,thermal_limit_exceed_seconds=None,phone_control_energy=None,native_seconds=seconds)
            item=dict(row=row,result=result,curve=curve,callback_seconds=getattr(agent,'callback_times',[]),model_context=MODEL_CONTEXT,model_sha256=hybrid.UPSTREAM_SHA,
                projection_calls=getattr(agent,'projection_calls',0),projection_seconds=getattr(agent,'projection_seconds',0.),prefix_projection_calls=getattr(agent,'execution_prefix_projection_calls',0),prefix_projection_seconds=getattr(agent,'execution_prefix_projection_seconds',0.),
                prefix_choices=getattr(agent,'prefix_choices',[]),plan_records=getattr(agent,'plan_records',[]),
                prefix_guard_records=getattr(agent,'prefix_guard_records',[]),cancelled_bundles=getattr(agent,'cancelled_bundles',0),interrupted_holds=getattr(agent,'interrupted_holds',0))
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(gzip.compress(json.dumps(serial(item),allow_nan=False).encode(),mtime=0))
            start.update(status='completed',sha256=sha(path),completed=complete);self.append(dict(event='completion',**start));write(LOCAL/'progress.json',self.used());return item
        except BaseException as error:
            start.update(status='failed',error=repr(error));self.append(dict(event='failure',**start));write(LOCAL/'progress.json',self.used())
            write(LOCAL/'last_error.json',dict(error=repr(error),traceback=traceback.format_exc(),consumption=self.used()));raise
def _run():
    check(require_local=True)
    if (LOCAL/'completion.json').exists():raise FileExistsError('completed pilot preserved')
    owner=LOCAL/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    try:
        budget=Budget();data=read(LOCAL/'inputs.json');frozen,_=new.p.inputs(new.p.BUNDLE);initial=data['initial']
        gates=[]
        for i,case in enumerate(data['fixtures']):
            item=budget.call(f'gate_{i}','gate',dict(case,context='mean'),FixtureController(frozen,initial,case['mode']));result=item['result'];by={q['id']:q for q in result['ledger']}
            assert item['row']['completed']==item['row']['planned']==2 and item['row']['urgent_failure']==item['row']['normal_failure']==0
            if case['mode']=='arrival_interrupt':assert by['C']['dispatch_ns']<35_250_000_000
            if case['mode']=='resource_release':assert by['C']['dispatch_ns']>=by['D']['lane_available_ns']
            if case['mode']=='pair':assert by['C']['dispatch_ns']==by['D']['dispatch_ns']
            if case['mode']=='cancel_pair':assert item['cancelled_bundles']>=1
            gates.append(dict(fixture=i,mode=case['mode'],status='PASS'))
        write(LOCAL/'gate_verification.json',dict(status='PASS',fixtures=gates,consumption=budget.used()))
        rows=[]
        for case in data['cases']:
            for role in ROLES:
                item=budget.call(f"pilot_{role}_{case['condition']:03d}",'pilot',case,controller(role,frozen,initial))
                rows.append(dict(condition=case['condition'],seed=case['seed'],family=case['family'],context=case['context'],policy=role,policy_id=POLICY_IDS[role],**item['row']))
            print(json.dumps(dict(done=case['condition']+1,total=24,consumption=budget.used())),flush=True)
        result=dict(status='completed',rows=rows,gates={role:gate_rows(rows,role) for role in ('OriginalV2','ExecutionPrefix')},consumption=budget.used(),independent_final_confirmation=0,automatic_adoption=False)
        write(LOCAL/'completion.json',result);write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='completed',consumption=budget.used(),next_action='report full rows and per-condition gates, no automatic learning/devices'))
    finally:
        if owner.exists() and owner.read_text()==str(os.getpid()):owner.unlink()
def run():
    with hybrid.forecast_scope():return _run()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','check','run']);args=parser.parse_args()
    if args.command=='prepare':print(json.dumps(prepare(),indent=2))
    elif args.command=='check':print(json.dumps(check(),indent=2))
    else:run()
