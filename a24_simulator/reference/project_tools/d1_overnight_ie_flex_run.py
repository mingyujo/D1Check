"""Separate bounded P95-flex experiment, after conservative batch completion.

Reuses the tested native/archive/audit runner through process-local routing;
no old source/checkpoint/output is edited. Existing development baselines are
explicitly reused, not rerun or counted as independent observations.
"""
import argparse,copy,gzip,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_overnight_ie_run as native
from tools import d1_overnight_ie_flex_policy as x

ROOT=native.ROOT;PARENT_LOCAL=native.LOCAL
LOCAL=ROOT/'output/overnight_ie_flex_20261011_v1';PUBLIC=ROOT/'docs/results/overnight_ie_flex_20261011'
TASK='OVERNIGHT-IE-P95-FLEX-02';ROLES=('Band','Triton','L0','Rule','Flex')
IDS=dict(native.IDS,Flex=x.FLEX);read=native.read;sha=native.sha;serial=native.serial
_write=native.write;_agent=native.agent

def write(path,obj):
    # Windows readers can briefly hold a destination during atomic replace.
    # Same bytes and fixed budget; no policy/criterion change or new run.
    for j in range(21):
        try:return _write(path,obj)
        except PermissionError:
            if j==20:raise
            time.sleep(.05)

def sources():
    names={Path(m.__file__).resolve() for n,m in sys.modules.copy().items() if n.startswith('tools.') and getattr(m,'__file__',None)}
    names|={ROOT/'tools/d1_overnight_ie_flex_run.py',ROOT/'tools/test_d1_overnight_ie_flex_policy.py'}
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(names) if p.suffix=='.py' and p.is_relative_to(ROOT)}

def register():
    if LOCAL.exists():raise FileExistsError('same task preserved; no reset')
    closed=read(PARENT_LOCAL/'WORKING_STATE.json')
    if closed['phase']!='completed' or closed['consumption']['native_starts']!=442 or (PARENT_LOCAL/'owner.lock').exists():raise ValueError('original conservative task must complete first')
    seeds=(828120201,828120202,828120203,828120204)
    for path in (ROOT/'output').glob('*/registration*.json'):
        if any(str(s) in path.read_text(encoding='utf-8') for s in seeds):raise ValueError('seed already registered')
    parent_inputs=read(PARENT_LOCAL/'inputs.json');dev=parent_inputs['development'];confirm=native.prior.cases(seeds)
    inputs=dict(development=dev,confirmation=confirm,fixtures=parent_inputs['fixtures'])
    reg=dict(task=TASK,registered_utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        authorization='root recorded additional candidate under user overnight full development authorization; final KPI unchanged',
        parent_task=native.TASK,parent_registration_sha256=sha(PARENT_LOCAL/'registration.json'),parent_closed_native=442,
        prior_native_task_only=10763,prior_learning_before_parallel_extension=1549,other_concurrent_task_consumption_excluded=True,
        native_cap=512,learning_cap=0,expected_native=266,phase_caps=dict(gate=2,development=24,confirmation=240),active_seconds=3600,save_reserve_seconds=600,
        roles=ROLES,policy_ids={r:IDS[r] for r in ROLES},schema=x.SCHEMA,features_parent_schema=x.r.SCHEMA,
        feature_ABI='same56 state/8x28 candidates/physical mask; prediction admission mask changed and separately identified; no actor transferred',
        source_sha256=sources(),model_sha256=x.r.h.UPSTREAM_SHA,exported_model_sha256=sha(x.r.h.MODEL),service_energy_sha256=x.r.h.p.MODEL_SHA,initial_sha256=x.r.h.p.INITIAL_SHA,
        inputs_sha256=x.r.c.digest(inputs),common_settings=x.r.h.prior.external.settings(),realization_seed=201,
        changed='replace per-current-urgent exact response guard with observed+arrived+owned unanswered urgent P95/miss nonworse; every current queued individual lateness nonworse',
        preserved='physical support, actual AVAILABLE, unknown fallback,L0 suffix, unknown-cooling rejection,D backlog/observed rho/request0.25wait cap,3context J/drain guard,AP-primary ranking,final service/J/AP criteria',
        no_future_guarantee='P95 contains past observed and current arrived/owned unanswered; actual future arrivals excluded',
        archived_witness='development seed826020101 sustained at63.072586416s: resource_wait blocked per request but3context current P95/miss/J/AP nonworse, one state across3 sensitivity contexts',
        development_baselines_reused=True,reused_development_rows_sha256=sha(PARENT_LOCAL/'development_rows.json'),reused_development_raw_sha256={p.name:sha(p) for p in sorted((PARENT_LOCAL/'items').glob('development_*.gz'))},
        confirmation='fresh4arrival seeds x4families x3contexts; candidate and4baselines same48; settings frozen before any fresh confirmation result',
        final_gate='identical full completion; all48 service/P95/J/AP nonworse vs Band/Triton; low/sustained absolute deadlines; one primary family strict AP orJ improvement',
        representative='existing first4device Band/Rule replay unchanged; no new representative trace or physical plan automatic replacement',
        tuning_calls=0,learning_starts=0,device_commands=0,model_fit_calls=0,NPU=False,experiment_ready=False,automatic_adoption=False)
    LOCAL.mkdir();write(LOCAL/'registration.json',reg);write(LOCAL/'inputs.json',inputs);write(PUBLIC/'execution_contract.json',reg);write(PUBLIC/'cases.json',inputs)
    write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='registered',consumption=dict(native_starts=0),next_action='2 native fixtures then24 development candidate and fixed48x5 confirmation'))
    return reg

def check():
    reg=read(LOCAL/'registration.json')
    for name,digest in reg['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('registered source changed '+name)
    if x.r.c.digest(read(LOCAL/'inputs.json'))!=reg['inputs_sha256'] or sha(x.r.h.MODEL)!=reg['exported_model_sha256']:raise ValueError('model/input changed')
    if sha(PARENT_LOCAL/'development_rows.json')!=reg['reused_development_rows_sha256']:raise ValueError('reused reference changed')
    return reg

def agent(role):
    if role=='Flex':
        f,i,_=x.r.h.load();return x.Controller(f,i['initial'])
    return _agent(role)

# All module routing is within this independent Python process only.
native.LOCAL=LOCAL;native.PUBLIC=PUBLIC;native.agent=agent;native.check=check;native.write=write

class Budget(native.Budget):
    def __init__(self):
        super().__init__();self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+3000
    def used(self):return dict(native_starts=len(self.rows),native_cap=512,learning_starts=0,failed=sum(v['status']=='failed' for v in self.rows),device_commands=0,model_fit_calls=0,task_only_cumulative_native=10763+len(self.rows),other_parallel_consumption_excluded=True)
    def call(self,*args,**kwargs):
        if len(self.rows)>=512 and not any(v['identity']==args[0] for v in self.rows):raise TimeoutError('separate512 cap')
        return super().call(*args,**kwargs)

def row(raw,case,role):return dict(condition=case['condition'],arrival_seed=case['seed'],family=case['family'],context=case['context'],policy=role,policy_id=IDS[role],**raw['row'])

def run():
    budget=Budget();inputs=read(LOCAL/'inputs.json');lock=LOCAL/'owner.lock'
    with lock.open('x',encoding='utf-8') as f:f.write(str(os.getpid()))
    try:
        for case in inputs['fixtures']:budget.call(f'gate_Flex_{case["condition"]:02d}','gate',case,'Flex')
        reused=[dict(q,reference_origin='parent completed same development input/model/source, native starts counted there only') for q in read(PARENT_LOCAL/'development_rows.json') if q['policy'] in ROLES]
        dev=list(reused)
        for case in inputs['development']:
            raw=budget.call(f'development_Flex_{case["condition"]:02d}','development',case,'Flex');dev.append(row(raw,case,'Flex'))
            write(LOCAL/'development_rows.json',dev);print(json.dumps(dict(phase='development',condition=case['condition'],consumption=budget.used())),flush=True)
        write(LOCAL/'development_verdict.json',native.verdict(dev,'Flex',24));write(PUBLIC/'development_comparison.json',dev)
        confirmation=[]
        for case in inputs['confirmation']:
            for role in ROLES:
                raw=budget.call(f'confirmation_{role}_{case["condition"]:02d}','confirmation',case,role);confirmation.append(row(raw,case,role));write(LOCAL/'confirmation_rows.json',confirmation)
            print(json.dumps(dict(phase='confirmation',condition=case['condition'],consumption=budget.used())),flush=True)
        final=native.verdict(confirmation,'Flex',48);write(LOCAL/'confirmation_verdict.json',final);write(PUBLIC/'confirmation_verdict.json',final);write(PUBLIC/'confirmation_comparison.json',confirmation)
        write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='completed',consumption=budget.used(),verdict=final,next_action='report and preserve firstdevice plan; no automatic adoption'));write(PUBLIC/'consumption.json',budget.used());return final
    finally:lock.unlink(missing_ok=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('register','check','run'));args=parser.parse_args();print(json.dumps(serial(globals()[args.command]()),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
