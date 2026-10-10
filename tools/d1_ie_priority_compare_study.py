"""One bounded, preregistered nine-policy comparison; no training/devices."""
from __future__ import annotations
import argparse,copy,gzip,hashlib,json,os,platform,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
import torch
from tools import d1_ie_priority_compare as rules
from tools import d1_ie_dispatch as original
from tools import d1_list_candidate_rl as core
from tools import d1_list_candidate_tail as tail
from tools import d1_triton_rules as triton
from tools import d1_list_candidate_rl_engine as engine
from tools import d1_list_candidate_rl_main_report as gate_report

external=rules.external;p=rules.p;ROOT=p.ROOT
TASK='IE-PRIORITY-COMPARE-02'
CANONICAL=ROOT/'output/ie_priority_compare_20261010_v1'
ROLES=('EDD','MST','CR','ATC','PROTECT','L0','Band','Triton','TailRule')
FAMILIES=('low','queue','burst','sustained')
CONTEXTS=('mean','short_context','long_context')
CAP=480
STAGE_CAPS={'gate':16,'development':216,'confirmation':216}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def serial(v):
    if isinstance(v,dict):return {str(k):serial(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [serial(x) for x in v]
    if hasattr(v,'tolist'):return v.tolist()
    return v
def write(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(serial(obj),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def sources():
    result={}
    for name,module in list(sys.modules.items()):
        if name.startswith('tools.') and getattr(module,'__file__',None):
            path=Path(module.__file__).resolve()
            if path.suffix=='.py' and path.is_relative_to(ROOT):result[path.relative_to(ROOT).as_posix()]=sha(path)
    result['tools/d1_ie_priority_compare_study.py']=sha(Path(__file__))
    result['docs/results/list_candidate_rl_review_01/design_amendment_v4.json']=sha(ROOT/'docs/results/list_candidate_rl_review_01/design_amendment_v4.json')
    return result

def cases(seeds):return [dict(seed=s,family=f,context=c) for s in seeds for f in FAMILIES for c in CONTEXTS]
def fixture(index):
    tasks=('C','D','CD','CCDD')[index]
    return dict(seed=822001001+index,family='fixture',context='mean',requests=[dict(id=f'fixture{index}/{i}',
        task='classification' if task=='C' else 'detection',priority='urgent' if task=='C' else 'normal',ordinal=i,
        arrival_ns=35_000_000_000+(i//2)*200_000_000,deadline_offset_ns=1_500_000_000 if task=='C' else 6_000_000_000)
        for i,task in enumerate(tasks)])

def register(output):
    if CANONICAL.exists():raise FileExistsError('same task cannot acquire a fresh budget in another directory')
    prior=ROOT/'output/list_candidate_tail_20261010_v1'
    previous=read(prior/'WORKING_STATE.json')
    if previous['phase']!='completed' or previous['consumption']['cumulative_environment_starts']!=9269:
        raise ValueError('prior policy consumption changed; audit instead of resetting')
    if (prior/'owner.lock').exists():raise ValueError('prior run owned')
    output.mkdir(parents=True,exist_ok=False)
    reg=dict(task=TASK,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        registered_utc=datetime.now(timezone.utc).isoformat(),active_seconds=2700,save_reserve_seconds=300,
        authorization='user: 비교한번해봐; PC rules only, no new RL or devices',
        previous_cumulative_environment_starts=9269,previous_cumulative_learning_starts=1449,
        previous_tail_tranche_spent=1404,previous_tail_unused_environments=132,previous_tail_unused_learning=12,
        previous_tranches_reopened=False,new_environment_cap=CAP,new_learning_cap=0,expected_new_environments=sum(STAGE_CAPS.values()),
        cumulative_environment_cap=20000,stage_caps=STAGE_CAPS,policies=list(ROLES),
        development=cases((822020101,822020102)),confirmation=cases((822030101,822030102)),
        fixtures=[fixture(i) for i in range(4)],actual_realization_seed=201,
        tuning_trials=0,ATC_k=2.,ATC_wj=1.,ATC_config_is_universal_default=False,
        routing='all priority rules use existing minimum whole5phase lane ECT, CPU tie; PROTECT explicit routing exception',
        priority=dict(EDD='absolute existing response deadline',MST='due minus predicted response of ECT route',
            CR='(due-now)/(predicted response-now), resource wait included; adapted lead-time ratio',
            ATC='min log(lane5 service)+max(0,due-predicted response)/(2*mean lane5 service), all weights1',
            PROTECT='same MST order; route first C to GPU only if C meets due and same arrived D-only projected miss count strictly falls'),
        deadline_conversion='source manufacturing completion becomes existing response2/3; lane release remains5',
        supported={'classification':['CPU','GPU'],'detection':['CPU']},maximum_concurrent=2,
        allowed_parallel='classification_GPU+detection_CPU only',cooling_wait_added=False,preemption=False,NPU_added=False,
        changes_to_existing_models_defaults_RL_strict=False,experiment_ready=False,phone_overhead_measured=False,
        energy_window_s=[0,120],AP_grid=list(range(35,181)),surface_temperature_available=False,AP_limit_c=None,
        final_gate='existing full-completion/urgent-normal/P95/J/AP per condition versus L0/Band/Triton; no epsilon relaxation',
        declared_scope='small measured-coefficient model comparison; 2 development and 2 fresh confirmation arrival seeds, not physical superiority',
        representative={'condition':9,'family':'sustained','context':'mean','window_s':[35,55]},
        frozen_model_sha256=p.MODEL_SHA,frozen_initial_sha256=p.INITIAL_SHA,
        source_sha256=sources(),python=platform.python_version())
    for old in (ROOT/'output').glob('*/registration*.json'):
        if old.parent==output:continue
        contents=old.read_text(encoding='utf-8')
        if any(str(s) in contents for s in (822020101,822020102,822030101,822030102)):
            raise ValueError('new arrival seed already declared elsewhere: '+old.parent.name)
    reg['input_sha256']={stage:core.digest([dict(case=c,requests=external.old.workload(c['family'],c['seed'])) for c in reg[stage]])
        for stage in ('development','confirmation')}
    reg['source_urls']={
        'MS_CR':'https://www.mdpi.com/2073-431X/5/1/3',
        'ATC':'https://pubsonline.informs.org/doi/abs/10.1287/mnsc.33.8.1035',
        'eligibility_concept_only':'https://www.sciencedirect.com/science/article/abs/pii/S016763771300120X'}
    write(output/'registration.json',reg)
    write(output/'workspace_start.json',dict(head=reg['head'],tracked_diff=subprocess.check_output(['git','diff','--numstat'],text=True),
        protected_files={path:sha(ROOT/path) for path in ['benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/EnergyResidentIdentification.kt',
            'benchmark-runner/src/testModelProbe/java/com/example/d1check/benchmarkrunner/EnergyResidentIdentificationTest.kt',
            'tools/d1_energy_collection_device.py','tools/d1_resident_identification_plan.py'] if (ROOT/path).exists()}))
    return reg

class Budget:
    def __init__(self,output,phase):
        self.output=Path(output);self.reg=read(self.output/'registration.json');self.phase=phase
        self.path=self.output/'executions.jsonl';self.rows=[]
        for line in self.path.read_text(encoding='utf-8').splitlines() if self.path.exists() else []:
            row=json.loads(line)
            if 'event' not in row:self.rows.append(row)
            else:self.rows[row['number']-1].update(row)
        self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+self.reg['active_seconds']-300
        self.guard(False)
    def consumption(self):return dict(new_environment_starts=len(self.rows),new_learning_starts=0,
        cumulative_environment_starts=9269+len(self.rows),cumulative_learning_starts=1449,
        native_failed=sum(r['status']=='failed' for r in self.rows),device_commands=0,new_cap=CAP)
    def guard(self,starting=True):
        if time.time()>=self.deadline:raise TimeoutError('45minute clock with last5minutes for saving')
        for name,h in self.reg['source_sha256'].items():
            if sha(ROOT/name)!=h:raise ValueError('registered execution source changed: '+name)
        p.inputs(p.BUNDLE)
        if starting and (len(self.rows)>=CAP or 9269+len(self.rows)>=20000):raise TimeoutError('additional/environment global cap')
        if starting and sum(r['phase']==self.phase for r in self.rows)>=STAGE_CAPS[self.phase]:raise TimeoutError('stage cap')
    def append(self,row):
        with self.path.open('a',encoding='utf-8',newline='\n') as f:
            f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def call(self,identity,controller,case):
        artifact=self.output/'items'/(identity+'.json.gz')
        cached=next((r for r in self.rows if r['identity']==identity),None)
        if cached:
            if cached['status']!='completed' or cached['case']!=case or sha(artifact)!=cached['sha256']:raise ValueError('consumed/changed run ID')
            return json.loads(gzip.decompress(artifact.read_bytes()))
        self.guard()
        requests=case['requests'] if case['family']=='fixture' else external.old.workload(case['family'],case['seed'])
        start=dict(number=len(self.rows)+1,identity=identity,phase=self.phase,status='started',case=case,planned=len(requests))
        self.rows.append(start);self.append(start)
        frozen,initial_case=p.inputs(p.BUNDLE);initial=initial_case['initial'];actual=p.profile(frozen,case['context'])
        vectors=dict(cells={k:[dict(source_request_id='common_measured_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in actual.items()})
        if isinstance(controller,tail.TailController):controller.forecast_deadline=self.deadline
        try:
            began=time.perf_counter()
            result=engine.simulate(dict(protocol=p.VERSION,cells=p.profile(frozen)),vectors,requests,
                policy=controller.policy,settings=external.settings(),seed=201,decision_provider=controller)
            seconds=time.perf_counter()-began
            _,costs,end=p.account(result,initial,frozen);ledger=result['ledger'];completed=sum(q['status']=='succeeded' for q in ledger)
            row=dict(planned=len(requests),completed=completed,incomplete=len(requests)-completed,
                urgent_failure=sum(q['priority']=='urgent' and ('response_ns' not in q or q.get('late_success',True)) for q in ledger),
                normal_failure=sum(q['priority']=='normal' and ('response_ns' not in q or q.get('late_success',True)) for q in ledger),
                urgent_scheduled=sum(q['priority']=='urgent' for q in ledger),normal_scheduled=sum(q['priority']=='normal' for q in ledger),
                urgent_p95_ms=result['metrics']['urgent_p95_ms'],normal_mean_ms=result['metrics']['normal_mean_ms'],
                energy_j=costs['whole_120s_j'] if completed==len(requests) else None,
                peak_ap_c=max(costs['ap_path']) if completed==len(requests) else None,native_seconds=seconds)
            times=getattr(controller,'callback_times',[s['decision_seconds'] for s in getattr(controller,'snapshots',[])])
            item=dict(case=case,row=row,result=result,curve=list(zip(range(35,end+1),costs['ap_path'])),
                controller=dict(decision_seconds=times,CPU_protect_decisions=getattr(controller,'protect_count',0),
                    voluntary_wait_s=getattr(controller,'deferred_seconds',0.),fallbacks=getattr(controller,'fallbacks',0)))
            artifact.parent.mkdir(parents=True,exist_ok=True);artifact.write_bytes(gzip.compress(json.dumps(serial(item),allow_nan=False).encode()))
            start.update(status='completed',sha256=sha(artifact),completed=completed,native_seconds=seconds)
            self.append(dict(event='completion',**start));write(self.output/'progress.json',dict(phase=self.phase,last=identity,consumption=self.consumption()))
            return item
        except BaseException as error:
            start.update(status='failed',error=repr(error));self.append(dict(event='failure',**start))
            write(self.output/'failures'/(identity+'.json'),dict(error=repr(error),traceback=traceback.format_exc(),consumption=self.consumption()))
            raise

def controller(role,frozen,initial):
    if role in rules.POLICIES:return rules.Controller(frozen,initial,role)
    if role=='LegacyEDD':return original.Controller(frozen,initial,'IE_EDD_ECT_LANE_PC_V1')
    if role=='L0':return core.Controller(frozen,initial,core.L0,feature_variant='head2+C_next')
    if role=='Band':return external.BandController(frozen,initial)
    if role=='Triton':return triton.Controller(frozen,initial,triton.OFF)
    if role=='TailRule':return tail.TailController(frozen,initial,feature_variant='head2+C_next')
    raise ValueError('unknown comparison role')

def gate(budget):
    frozen,case=p.inputs(p.BUNDLE);initial=case['initial'];comparisons=[]
    for i,q in enumerate(budget.reg['fixtures']):
        runs={role:budget.call(f'gate_{role}_{i}',controller(role,frozen,initial),q) for role in ('LegacyEDD','EDD','MST','PROTECT')}
        old,new=runs['LegacyEDD']['result'],runs['EDD']['result']
        same=all(old[k]==new[k] for k in ('ledger','transitions','metrics'))
        if not same:raise ValueError('EDD routing/priority wrapper regression')
        comparisons.append(dict(fixture=i,ledger_transitions_metrics_exact=True,planned=len(q['requests'])))
    evidence=dict(status='PASS',EDD_existing_preserved=comparisons,new_environment_starts=16,new_learning=0,
        rule_definition_tests='nine pure tests, including EDD/MS/CR differing states and CPU guard trigger',
        manual_states_are_performance_evidence=False,consumption=budget.consumption())
    write(budget.output/'gate_verification.json',evidence);return evidence

def evaluate(budget):
    if read(budget.output/'gate_verification.json')['status']!='PASS':raise ValueError('gate incomplete')
    frozen,case=p.inputs(p.BUNDLE);initial=case['initial'];rows=[]
    for role in ROLES:
        for i,q in enumerate(budget.reg[budget.phase]):
            identity=f'{budget.phase}_{role}_{i:03d}';item=budget.call(identity,controller(role,frozen,initial),q)
            rows.append(dict(identity=identity,condition=i,case=q,policy=role,seed=None,training_episodes=0,
                **item['row'],controller=item['controller']))
        print(json.dumps(dict(stage=budget.phase,completed_role=role,consumption=budget.consumption())),flush=True)
    decisions={role:gate_report.gate(rows,role,len(budget.reg[budget.phase])) for role in ('EDD','MST','CR','ATC','PROTECT','TailRule')}
    for d in decisions.values():d['learners']=0
    result=dict(status='completed',rows=rows,gates=decisions,consumption=budget.consumption(),tuning=0,learning=0)
    write(budget.output/(budget.phase+'_results.json'),result)
    return dict(status='completed',rows=len(rows),gates={role:{k:v for k,v in d.items() if k!='differences'} for role,d in decisions.items()},consumption=budget.consumption())

def main():
    a=argparse.ArgumentParser();a.add_argument('--output',required=True,type=Path);a.add_argument('--phase',required=True,choices=('register',*STAGE_CAPS));args=a.parse_args()
    torch.set_num_threads(1)
    if args.phase=='register':
        reg=register(args.output);print(json.dumps(dict(status='registered',task=TASK,expected=reg['expected_new_environments'],cap=CAP,learning=0)));return
    done=args.output/(args.phase+'_completion.json')
    if done.exists():raise FileExistsError('completed stage preserved')
    owner=args.output/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    budget=None
    try:
        budget=Budget(args.output,args.phase);result=gate(budget) if args.phase=='gate' else evaluate(budget)
        write(done,result);print(json.dumps(result,ensure_ascii=False,indent=2))
    except BaseException as error:
        write(args.output/(args.phase+'_error.json'),dict(error=repr(error),consumption=budget.consumption() if budget else None));raise
    finally:
        if owner.exists() and owner.read_text(encoding='ascii')==str(os.getpid()):owner.unlink()

if __name__=='__main__':main()
