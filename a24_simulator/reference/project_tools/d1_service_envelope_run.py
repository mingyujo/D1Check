"""Predeclared bounded development24/fresh confirmation48, no learning."""
import argparse,json,os,sys,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_overnight_ie_run as native
from tools import d1_service_envelope_policy as x
ROOT=native.ROOT;LOCAL=ROOT/'output/service_envelope_20261011_v1';PUBLIC=ROOT/'docs/results/service_envelope_20261011'
TASK='IE-SERVICE-ENVELOPE-01';ROLES=('Band','Triton','JointList','CostList')
IDS=dict(native.IDS,JointList=x.JOINT,CostList=x.COST)
read=native.read;sha=native.sha;serial=native.serial;_write=native.write;_agent=native.agent
def write(p,v):
    for i in range(21):
        try:return _write(p,v)
        except PermissionError:
            if i==20:raise
            time.sleep(.05)
def sources():
    files={Path(m.__file__).resolve() for n,m in sys.modules.copy().items() if n.startswith('tools.') and getattr(m,'__file__',None)}
    files|={ROOT/'tools/test_d1_service_envelope_policy.py',ROOT/'tools/d1_service_envelope_run.py'}
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files) if p.suffix=='.py'}
def register():
    if LOCAL.exists():raise FileExistsError('registered task/clock preserved')
    seeds=(833110101,833110102,833110103,833110104)
    parallel=ROOT/'output/service_joint_rl_20261011_v1/registration.json'
    parallel_note=None
    for p in (ROOT/'output').glob('*/registration*.json'):
        if any(str(s) in p.read_text(encoding='utf-8') for s in seeds):
            if p.resolve()==parallel.resolve():
                if list(p.parent.glob('items/confirmation*')):raise ValueError('parallel confirmation already consumed before registration')
                parallel_note=dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),meaning='same root-approved new paired confirmation reservation; no prior result inspected or tuning')
            else:raise ValueError('confirmation seed already registered')
    dev=native.prior.cases((826020101,826020102));confirm=native.prior.cases(seeds)
    parent=read(ROOT/'output/overnight_ie_20261011_v1/inputs.json')
    data=dict(development=dev,confirmation=confirm,fixtures=parent['fixtures'],representative=parent['representative'])
    reg=dict(task=TASK,registered_utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        authorization='user explicitly requests final heat-energy methodology; root bounded384 PC comparison, no learning',native_cap=384,learning_cap=0,
        active_seconds=1200,save_reserve_seconds=180,phase_caps=dict(gate=4,development=48,confirmation=192,representative=4),expected_native=248,
        source_sha256=sources(),inputs_sha256=x.r.c.digest(data),exported_model_sha256=sha(x.r.h.MODEL),model_sha256=x.r.h.UPSTREAM_SHA,
        common_settings=x.r.h.prior.external.settings(),realization_seed=201,roles=ROLES,policy_ids=IDS,schema=x.SCHEMA,
        service_rank='worst3contexts urgent misses,normal misses,urgent total lateness,normal total lateness; current whole queue drain;AP;J',
        suffix='shared Joint current-queue compatible EDD dispatcher: at most4 CPU-prefix/GPU maps; same actual fallback and forecast continuation; bounded approximation, no future arrivals',
        Cost_envelope='all3context Joint miss/lateness equality; current predicted urgentP95 nonworse; CPU-only queued response nonworse; no drain-end equality; AP/J both nonworse Joint then AP/J lex',
        preserved='original physical support,phase/response/AVAILABLE,modeled coefficients,engineering deadlines,request wait025,R1unknown cooling guard,original8slot bank',
        forecast_is_real_service_guarantee=False,final_gate='original strict epsilon0 full completion/service/P95/J/AP nonworse vsBand/Triton,low/sustained absolute deadlines,primary family strict one-axis gain',
        development='24 already-used development conditions; candidate2 only, former baselines explicitly reused for diagnosis',
        confirmation='fresh seeds833110101..104 x4families x3contexts48,4roles each; settings fixed before results',
        parallel_new_confirmation_reservation=parallel_note,
        representative='same fixed96 alternating35s+350ms trace, mean; plan export is not online mobile effect',new_learning=0,device_commands=0,model_fit_calls=0,automatic_adoption=False,experiment_ready=False)
    LOCAL.mkdir();write(LOCAL/'registration.json',reg);write(LOCAL/'inputs.json',data);write(PUBLIC/'execution_contract.json',reg);write(PUBLIC/'cases.json',data);write(LOCAL/'WORKING_STATE.json',dict(phase='registered'));return reg
def check():
    reg=read(LOCAL/'registration.json')
    for p,s in reg['source_sha256'].items():
        if sha(ROOT/p)!=s:raise ValueError('source changed '+p)
    if x.r.c.digest(read(LOCAL/'inputs.json'))!=reg['inputs_sha256'] or sha(x.r.h.MODEL)!=reg['exported_model_sha256']:raise ValueError('model/input changed')
    return reg
def agent(role):
    if role in ('JointList','CostList'):
        f,i,_=x.r.h.load();return x.Controller(f,i['initial'],x.JOINT if role=='JointList' else x.COST)
    return _agent(role)
native.LOCAL=LOCAL;native.PUBLIC=PUBLIC;native.agent=agent;native.check=check;native.write=write
class Budget(native.Budget):
    def __init__(self):super().__init__();self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+1020
    def used(self):return dict(native_starts=len(self.rows),native_cap=384,new_learning=0,failed=sum(q['status']=='failed' for q in self.rows),device_commands=0,model_fit_calls=0)
    def call(self,*args,**kwargs):
        if len(self.rows)>=384 and not any(q['identity']==args[0] for q in self.rows):raise TimeoutError('new384 cap')
        return super().call(*args,**kwargs)
def row(raw,case,role):return dict(condition=case['condition'],arrival_seed=case['seed'],family=case['family'],context=case['context'],policy=role,policy_id=IDS[role],**raw['row'])
def run():
    budget=Budget();data=read(LOCAL/'inputs.json');lock=LOCAL/'owner.lock';rows=[]
    with lock.open('x',encoding='utf-8') as f:f.write(str(os.getpid()))
    try:
        for role in ('JointList','CostList'):
            for q in data['fixtures']:budget.call(f'gate_{role}_{q["condition"]}','gate',q,role)
        dev=[]
        for case in data['development']:
            for role in ('JointList','CostList'):dev.append(row(budget.call(f'development_{role}_{case["condition"]:02d}','development',case,role),case,role))
            write(LOCAL/'development_rows.json',dev);print(json.dumps(dict(phase='development',condition=case['condition'],used=budget.used())),flush=True)
        write(PUBLIC/'development_comparison.json',dev)
        for case in data['confirmation']:
            for role in ROLES:rows.append(row(budget.call(f'confirmation_{role}_{case["condition"]:02d}','confirmation',case,role),case,role))
            write(LOCAL/'confirmation_rows.json',rows);print(json.dumps(dict(phase='confirmation',condition=case['condition'],used=budget.used())),flush=True)
        verdict={role:native.verdict(rows,role,48) for role in ('JointList','CostList')};write(PUBLIC/'confirmation_comparison.json',rows);write(PUBLIC/'confirmation_verdict.json',verdict)
        rep=[]
        for role in ROLES:rep.append(row(budget.call('representative_'+role,'representative',data['representative'],role),data['representative'],role))
        write(PUBLIC/'representative_rows.json',rep);write(PUBLIC/'consumption.json',budget.used());write(LOCAL/'WORKING_STATE.json',dict(phase='completed',consumption=budget.used(),verdict=verdict));return verdict
    except BaseException:
        write(LOCAL/'WORKING_STATE.json',dict(phase='failed_or_budget_stopped',consumption=budget.used()));raise
    finally:lock.unlink(missing_ok=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','check','run'));a=p.parse_args();print(json.dumps(serial(globals()[a.command]()),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
