"""Independent bounded conservative IE comparison; no model/device/training edits."""
import argparse,copy,csv,gzip,hashlib,json,os,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_overnight_ie_policy as x
from tools import d1_rolling_list_rl_run as prior

ROOT=prior.ROOT;LOCAL=ROOT/'output/overnight_ie_20261011_v1';PUBLIC=ROOT/'docs/results/overnight_ie_20261011'
TASK='OVERNIGHT-IE-CONSERVATIVE-01';ROLES=('Band','Triton','L0','Rule','R1','R2')
IDS=dict(Band=x.r.h.prior.external.BAND,Triton=x.r.h.prior.triton.OFF,L0=x.r.L0,Rule=x.r.RULE,R1=x.R1,R2=x.R2)
sha=prior.sha;read=prior.read;write=prior.write;serial=prior.serial

def sources():
    names={Path(m.__file__).resolve() for n,m in sys.modules.copy().items() if n.startswith('tools.') and getattr(m,'__file__',None)}
    names|={ROOT/'tools/test_d1_overnight_ie_policy.py',ROOT/'tools/d1_overnight_ie_run.py'}
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(names) if p.suffix=='.py' and p.is_relative_to(ROOT)}

def representative():
    return [dict(id=f'overnight_96_{j:03d}',ordinal=j,task='classification' if j%2==0 else 'detection',priority='urgent' if j%2==0 else 'normal',arrival_ns=35_000_000_000+j*350_000_000,deadline_offset_ns=1_500_000_000 if j%2==0 else 6_000_000_000) for j in range(96)]

def register():
    if LOCAL.exists():raise FileExistsError('existing task preserved; no new clock/budget')
    dev=prior.cases((826020101,826020102));confirm=prior.cases((828110101,828110102,828110103,828110104))
    for path in (ROOT/'output').glob('*/registration*.json'):
        s=path.read_text(encoding='utf-8')
        if any(str(seed) in s for seed in (828110101,828110102,828110103,828110104)):raise ValueError('confirmation seed already used')
    fixtures=[dict(condition=j,seed=None,family='fixture',context='mean',tickets=t) for j,t in enumerate([
        [x.r.h.prior.ticket('D','detection')],
        [x.r.h.prior.ticket('D','detection'),x.r.h.prior.ticket('C','classification',35.1,1)]])]
    data=dict(development=dev,confirmation=confirm,fixtures=fixtures,representative=dict(condition=0,seed=None,family='device_fixed_96',context='mean',tickets=representative()))
    reg=dict(task=TASK,registered_utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        authorization='user overnight autonomous project development; root assigned separate768-env/90min conservative IE comparison',
        prior_native=10321,prior_learning=1549,concurrent_other_task_counters_not_included=True,native_cap=768,learning_cap=0,device_commands=0,model_fit_calls=0,
        expected_native=4+24*6+48*6+6,phase_caps=dict(gate=4,development=144,confirmation=288,representative=6),active_seconds=5400,save_reserve_seconds=600,
        roles=ROLES,policy_ids=IDS,model_sha256=x.r.h.UPSTREAM_SHA,exported_model_sha256=sha(x.r.h.MODEL),service_energy_sha256=x.r.h.p.MODEL_SHA,initial_sha256=x.r.h.p.INITIAL_SHA,
        source_sha256=sources(),inputs_sha256=x.r.c.digest(data),initial='unchanged measured idle preload',
        schema=x.r.SCHEMA,R1='same Rule bank; cooling rejected when last8 observed arrivals contain fewer than3 unique arrival times; old rho>=1/Dbacklog/request cap unchanged',
        R2='R1 plus response for every arrived queued request <= L0 reference in all3 contexts; no new time/miss tolerance',
        objective='old AP-primary Rule ranking; fixed energy/service coefficients; no tuning',common_settings=x.r.h.prior.external.settings(),realization_seed=201,
        verdict='all72 relevant current cases full completion and service/P95/J/AP nonworse vs both Band/Triton; low/sustained absolute deadlines; strict cost gain in same primary family',
        development_verdict='diagnosis only; R1/R2 both evaluated on confirmation without best-seed selection',representative='predeclared96 alternating C/D every350ms, mean context; export original online ledger then replay frozen dispatches on device, not online mobile effectiveness',
        limitations='fixed5phase, no cooling-to-speed recovery, AP model channel not surface/safety, PC callback not phone energy',NPU=False,experiment_ready=False,automatic_adoption=False)
    LOCAL.mkdir();write(LOCAL/'registration.json',reg);write(LOCAL/'inputs.json',data);write(PUBLIC/'execution_contract.json',reg);write(PUBLIC/'cases.json',data)
    write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='registered',native_starts=0,learning_starts=0,next_action='native gates then fixed development/confirmation and96 representative'))
    return reg

def check():
    reg=read(LOCAL/'registration.json')
    for n,d in reg['source_sha256'].items():
        if sha(ROOT/n)!=d:raise ValueError('registered source changed '+n)
    if sha(x.r.h.MODEL)!=reg['exported_model_sha256'] or x.r.c.digest(read(LOCAL/'inputs.json'))!=reg['inputs_sha256']:raise ValueError('registered inputs/model changed')
    return reg

def agent(role):
    if role in ('R1','R2'):
        f,i,_=x.r.h.load();return x.Controller(f,i['initial'],{'R1':x.R1,'R2':x.R2}[role])
    return prior.agent(role)

class Budget:
    def __init__(self):
        self.reg=check();self.rows=[];self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+4800
        for line in (LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines() if (LOCAL/'executions.jsonl').exists() else []:
            v=json.loads(line)
            if v.get('event'):self.rows[v['number']-1].update(v)
            else:self.rows.append(v)
    def used(self):return dict(native_starts=len(self.rows),native_cap=768,learning_starts=0,failed=sum(v['status']=='failed' for v in self.rows),device_commands=0,model_fit_calls=0,task_only_cumulative_native=10321+len(self.rows),prior_learning=1549)
    def append(self,v):
        with (LOCAL/'executions.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(v,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def call(self,identity,phase,case,role):
        check();path=LOCAL/'items'/(identity+'.json.gz');found=next((v for v in self.rows if v['identity']==identity),None)
        if found:
            if found['status']!='completed' or found['case']!=case or sha(path)!=found['sha256']:raise ValueError('consumed failed/changed ID preserved')
            return json.loads(gzip.decompress(path.read_bytes()))
        if time.time()>=self.deadline or len(self.rows)>=768:raise TimeoutError('immutable time/cap')
        if sum(v['phase']==phase for v in self.rows)>=self.reg['phase_caps'][phase]:raise TimeoutError('phase cap')
        v=dict(number=len(self.rows)+1,identity=identity,phase=phase,case=case,role=role,status='started');self.rows.append(v);self.append(v)
        try:
            a=agent(role);frozen,initial,_=x.r.h.load();profile=x.r.h.p.profile(frozen,case['context']);vectors=dict(cells={k:[dict(source_request_id='common_'+case['context'],durations_ns=z) for _ in range(4)] for k,z in profile.items()})
            a.execution_deadline=time.monotonic()+max(0,self.deadline-time.time());began=time.perf_counter()
            with x.r.h.forecast_scope():result=x.r.h.prior.external.old.engine.simulate(dict(protocol=x.r.h.p.VERSION,cells=x.r.h.p.profile(frozen)),vectors,case['tickets'],policy=a.policy,settings=self.reg['common_settings'],seed=201,decision_provider=a)
            seconds=time.perf_counter()-began;prior.previous.audit(result,case['tickets']);ledger=result['ledger'];completed=sum(q['status']=='succeeded' for q in ledger)
            energy=peak=None;curve=[]
            if completed==len(ledger):
                _,costs,end=x.r.h.account(result,initial['initial'],frozen);energy=costs['whole_120s_j'];peak=max(costs['ap_path']);curve=list(zip(range(35,end+1),costs['ap_path']))
            row=dict(planned=len(ledger),completed=completed,incomplete=len(ledger)-completed,urgent_failure=sum(q['priority']=='urgent' and ('response_ns' not in q or q.get('late_success',True)) for q in ledger),normal_failure=sum(q['priority']=='normal' and ('response_ns' not in q or q.get('late_success',True)) for q in ledger),urgent_p95_ms=result['metrics']['urgent_p95_ms'],normal_mean_ms=result['metrics']['normal_mean_ms'],energy_j=energy,peak_ap_c=peak,native_seconds=seconds,surface_temperature=None,thermal_limit_exceed_seconds=None,phone_control_energy=None)
            snapshots=getattr(a,'snapshots',[])
            for s in snapshots:
                if not s['mask'][s['chosen']] or (s['mask'] & ~s['physical_mask']).any():raise ValueError('invalid chosen mask')
            raw=dict(row=row,result=result,curve=curve,snapshots=snapshots,callback_seconds=getattr(a,'callback_times',[]),total_extra_wait=getattr(a,'total_extra_wait',0.),request_wait=getattr(a,'request_wait',{}),cooling_count=getattr(a,'cooling_count',0),admission_rejections=getattr(a,'admission_rejections',{}))
            if raw['request_wait'] and max(raw['request_wait'].values())>.25+1e-8:raise ValueError('per-request wait cap')
            if phase=='gate':
                if completed!=len(case['tickets']) or row['urgent_failure'] or row['normal_failure']:raise ValueError('native fixture service')
                if not any('unknown_observed_CPU_load_no_cooling' in s['admissions'] for s in snapshots):raise ValueError('unknown load not tested by native fixture')
            path.parent.mkdir(exist_ok=True);path.write_bytes(gzip.compress(json.dumps(serial(raw),allow_nan=False).encode(),mtime=0));v.update(status='completed',sha256=sha(path));self.append(dict(event='completed',**v));write(LOCAL/'progress.json',self.used());return raw
        except BaseException as error:
            v.update(status='failed',error=repr(error));self.append(dict(event='failed',**v));write(LOCAL/'last_error.json',dict(error=repr(error),traceback=traceback.format_exc(),consumption=self.used()));raise

def row(raw,case,role):return dict(condition=case['condition'],arrival_seed=case['seed'],family=case['family'],context=case['context'],policy=role,policy_id=IDS[role],**raw['row'])

def verdict(rows,role,count):
    kpis=('incomplete','urgent_failure','normal_failure','urgent_p95_ms','energy_j','peak_ap_c');refs={(q['condition'],q['policy']):q for q in rows if q['policy'] in ('Band','Triton')};target=[q for q in rows if q['policy']==role]
    if len(target)!=count or len(refs)!=count*2:raise ValueError('missing/duplicate paired conditions')
    differences=[]
    for q in target:
        for refrole in ('Band','Triton'):
            ref=refs[q['condition'],refrole];d={k:(q[k]-ref[k] if q[k] is not None and ref[k] is not None else None) for k in kpis};full=q['completed']==q['planned']==ref['completed']==ref['planned'];primary=q['family'] in ('low','sustained')
            passed=full and all(z is not None and z<=0 for z in d.values()) and (not primary or q['urgent_failure']==q['normal_failure']==0)
            differences.append(dict(condition=q['condition'],family=q['family'],baseline=refrole,passed=passed,delta=d))
    maintained=all(d['passed'] for d in differences);promising=[]
    for family in ('low','sustained'):
        ds=[d for d in differences if d['family']==family]
        if maintained and ds and all(d['passed'] and (d['delta']['energy_j']<0 or d['delta']['peak_ap_c']<0) for d in ds):promising.append(family)
    return dict(maintenance_pass=maintained,promising=bool(promising),promising_families=promising,epsilon=0,differences=differences,automatic_adoption=False)

def export(raw,role):
    ledger=raw['result']['ledger'];requests=[]
    for q in sorted(ledger,key=lambda q:q['ordinal']):
        if q['status']!='succeeded':raise ValueError('cannot export incomplete replay')
        requests.append(dict(ordinal=q['ordinal'],source_request_id=q['id'],task_id=q['task'],priority=q['priority'],offset_ms=(q['arrival_ns']-35e9)/1e6,deadline_ms=q['deadline_offset_ns']/1e6,release_offset_ns=q['dispatch_ns']-35_000_000_000,recorded_backend=q['backend']))
    plan=dict(version='frozen-plan-v2',policy_id=IDS[role],model_sha256=x.r.h.UPSTREAM_SHA,trace_seed=None,source_sha256=read(LOCAL/'registration.json')['source_sha256'],requests=requests,online_mobile_policy=False,meaning='frozen dispatch plan from no-future online PC policy; actual lane re-use still guarded by device')
    write(LOCAL/f'device_plan_{role}.json',plan)

def run():
    budget=Budget();data=read(LOCAL/'inputs.json');lock=LOCAL/'owner.lock'
    with lock.open('x',encoding='utf-8') as f:f.write(str(os.getpid()))
    try:
        for role in ('R1','R2'):
            for case in data['fixtures']:budget.call(f'gate_{role}_{case["condition"]:02d}','gate',case,role)
        device_rows=[]
        for role in ROLES:
            raw=budget.call('representative_'+role,'representative',data['representative'],role);export(raw,role);device_rows.append(row(raw,data['representative'],role))
        write(LOCAL/'device_rows.json',device_rows);write(PUBLIC/'device_rows.json',device_rows)
        print(json.dumps(dict(event='DEVICE_PLANS_READY',path=str(LOCAL),rows=device_rows),ensure_ascii=False),flush=True)
        output={}
        for phase in ('development','confirmation'):
            rows=[]
            for case in data[phase]:
                for role in ROLES:
                    raw=budget.call(f'{phase}_{role}_{case["condition"]:02d}',phase,case,role);rows.append(row(raw,case,role));write(LOCAL/(phase+'_rows.json'),rows)
                print(json.dumps(dict(phase=phase,condition=case['condition'],consumption=budget.used()),ensure_ascii=False),flush=True)
            output[phase]={role:verdict(rows,role,len(data[phase])) for role in ('L0','Rule','R1','R2')};write(LOCAL/(phase+'_verdict.json'),output[phase]);write(PUBLIC/(phase+'_comparison.json'),rows);write(PUBLIC/(phase+'_verdict.json'),output[phase])
        write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='completed',consumption=budget.used(),verdict=output,next_action='root integrated report and device frozen-plan validation; no automatic adoption'))
        write(PUBLIC/'consumption.json',budget.used());return output
    finally:lock.unlink(missing_ok=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('register','check','run'));args=parser.parse_args();result=globals()[args.command]();print(json.dumps(serial(result),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
