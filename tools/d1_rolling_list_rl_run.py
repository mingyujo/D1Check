"""Bounded32-episode x3-seed development pilot; no final confirmation/devices."""
import argparse,copy,gzip,hashlib,json,os,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import torch
from tools import d1_rolling_list_rl as r
from tools import d1_rolling_hybrid_pilot as previous
from tools import d1_rolling_hybrid_model as h

ROOT=h.ROOT;LOCAL=ROOT/'output/rolling_list_rl_20261011_v1';PUBLIC=ROOT/'docs/results/rolling_list_rl_pilot_08'
TASK='ROLLING-LIST-RL-PILOT-08';SEEDS=(11,23,37);ROLES=('L0','Band','Triton','OriginalV2','Rule')
sha=previous.sha;read=previous.read;write=previous.write;serial=previous.serial


def cases(seeds,train=False):
    result=[]
    for seed in seeds:
        for family in ('low','queue','burst','sustained'):
            for context in ([r.selector.CONTEXTS[len(result)%3]] if train else r.selector.CONTEXTS):
                result.append(dict(condition=len(result),seed=seed,family=family,context=context,tickets=h.prior.external.old.workload(family,seed)))
    return result


def sources():
    names={Path(m.__file__).resolve() for name,m in sys.modules.copy().items() if name.startswith('tools.') and getattr(m,'__file__',None)}
    names|={ROOT/'tools'/n for n in ('d1_rolling_list_rl_run.py','test_d1_rolling_list_rl.py','test_d1_rolling_list_rl_run.py')}
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(names) if p.suffix=='.py' and p.is_relative_to(ROOT)}


def register():
    if LOCAL.exists():raise FileExistsError('same task directory preserved; no budget reset')
    prior=read(previous.LOCAL/'WORKING_STATE.json')
    if prior['phase']!='completed' or prior['consumption']['cumulative_policy_environment_starts']!=9849 or (previous.LOCAL/'owner.lock').exists():raise ValueError('previous completion/consumption changed')
    train=cases(range(826010001,826010009),True);dev=cases((826020101,826020102))
    for p in (ROOT/'output').glob('*/registration*.json'):
        text=p.read_text(encoding='utf-8')
        if any(str(s) in text for s in list(range(826010001,826010009))+[826020101,826020102]):raise ValueError('seed already declared')
    f,i,m=h.load();ticket=h.prior.ticket
    fixtures=[dict(mode='one_D_cooling',context='mean',tickets=[ticket('D','detection')]),
        dict(mode='D_backlog',context='mean',tickets=[ticket('D','detection'),ticket('D2','detection',ordinal=1),ticket('C','classification',35.1,2)]),
        dict(mode='urgent_arrival',context='mean',tickets=[ticket('D','detection'),ticket('C','classification',35.1,1)]),
        dict(mode='owned_lane_release',context='mean',tickets=[ticket('D','detection'),ticket('C','classification',35.05,1)])]
    inputs=dict(train=train,development=dev,fixtures=fixtures,initial=i['initial'])
    reg=dict(task=TASK,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),registered_utc=datetime.now(timezone.utc).isoformat(),
        authorization='user proceed to one minimal public-risk repair and same-bank3-seed small RL pilot; not large main training',
        prior_native=9849,prior_learning=1449,previous_closed_budgets_reopened=False,native_cap=572,learning_cap=104,global_native_cap=20000,global_learning_cap=6144,
        phase_caps=dict(gate=4,reference=32,train=96,replay=4,development=264,no_wait=72,no_thermal=72),
        expected_native=472,conditional_no_thermal_native=72,expected_learning=100,pilot_episodes_per_seed=32,learning_seeds=list(SEEDS),
        checkpoint_evaluation_episodes=[16,32],checkpoint_selection='all3 terminal32, no best seed/checkpoint',
        training_settings=r.training.Settings().__dict__,initial_multipliers=[1.,10.,1.,1.,1.],gamma=1.,
        objective='unchanged AP-primary telescoping reward, signed J and positive service-cost dual channels, L0 episode reference',
        model_sha256=h.UPSTREAM_SHA,exported_model_sha256=sha(h.MODEL),original_service_energy_sha256=h.p.MODEL_SHA,initial_sha256=h.p.INITIAL_SHA,
        inputs_sha256=r.c.digest(inputs),schema_id=r.SCHEMA,state_names=r.STATE_NAMES,candidate_names=r.CANDIDATE_NAMES,
        action_space='slot0 physical service-first L0, up to7 unique executable prefixes from unchanged rolling window4/mean-shortlist8',
        fallback_reference='L0 service-first list, not Band',forecast_suffix='same L0 service-first with causal EMA estimate update',
        prediction_admission='arrived-request response/lateness and J nonworse in3 contexts; finite drain120; not future SLA guarantee',
        wait_restrictions='request cumulative extra cooling<=0.25; D backlog<2; last8 observed arrivals CPU-D rho<1 when >=3 unique times',
        normalization='fixed named scales, unused slots/reserved features zero, known flags explicit',
        development_scope='same24 development cases for16/32 and non-learning baselines; no untouched final confirmation',
        ablations='no_wait terminal32 all3 seeds/all24; no_thermal_features only if at least one seed promising',
        adoption_gate='same all24 nonworse vs Band/Triton and same-bank Rule, low/sustained absolute service; one primary family strict AP or J',
        final_epsilon=0,hypothesis='learn when not to wait from public backlog/arrival history; no success presumed',
        active_seconds=3600,save_reserve_seconds=300,clock_starts='registration before first native environment, immutable across resume',
        common_settings=h.prior.external.settings(),realization_seed=201,device_commands=0,NPU=False,model_fit_calls=0,
        preemption=False,thermal_service_feedback=False,default_changed=False,experiment_ready=False,source_sha256=sources())
    LOCAL.mkdir();PUBLIC.mkdir(parents=True,exist_ok=True);write(LOCAL/'registration.json',reg);write(PUBLIC/'execution_contract.json',reg)
    write(LOCAL/'inputs.json',inputs);write(PUBLIC/'cases.json',dict(train=train,development=dev,fixtures=fixtures))
    foreign=subprocess.check_output(['git','diff','--name-only','-z']).decode().strip('\0').split('\0')
    write(LOCAL/'preserved_foreign.json',{n:sha(ROOT/n) for n in foreign if n and n not in ('docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md')})
    write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='registered',next_action='4 native fixtures then same-bank development/3seed32, no automatic main training',consumption=dict(native_starts=0,learning_starts=0,cumulative_native=9849,cumulative_learning=1449)))
    return reg


def check():
    reg=read(LOCAL/'registration.json')
    for name,digest in reg['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('registered source changed '+name)
    if sha(h.MODEL)!=reg['exported_model_sha256'] or r.c.digest(read(LOCAL/'inputs.json'))!=reg['inputs_sha256']:raise ValueError('model/input changed')
    h.load();return reg


class Budget:
    def __init__(self):
        self.reg=check();self.rows=[];self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+3300
        if (LOCAL/'executions.jsonl').exists():
            for line in (LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines():
                v=json.loads(line)
                if v.get('event'):self.rows[v['number']-1].update(v)
                else:self.rows.append(v)
    def used(self):
        learning=sum(v['learning'] for v in self.rows)
        return dict(native_starts=len(self.rows),learning_starts=learning,native_cap=572,learning_cap=104,failed=sum(v['status']=='failed' for v in self.rows),
            cumulative_native=9849+len(self.rows),cumulative_learning=1449+learning,device_commands=0,model_fit_calls=0)
    def append(self,v):
        with (LOCAL/'executions.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(v,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def call(self,identity,phase,case,agent,learning=False):
        check();path=LOCAL/'items'/(identity+'.json.gz');existing=next((v for v in self.rows if v['identity']==identity),None)
        if existing:
            if existing['status']!='completed' or existing['case']!=case or sha(path)!=existing['sha256']:raise ValueError('consumed failed/changed ID preserved')
            return json.loads(gzip.decompress(path.read_bytes()))
        if time.time()>=self.deadline or len(self.rows)>=572 or 9849+len(self.rows)>=20000:raise TimeoutError('immutable clock/native cap')
        if sum(v['phase']==phase for v in self.rows)>=self.reg['phase_caps'][phase]:raise TimeoutError('phase cap')
        if learning and self.used()['learning_starts']>=104:raise TimeoutError('learning cap')
        v=dict(number=len(self.rows)+1,identity=identity,phase=phase,case=case,learning=learning,status='started');self.rows.append(v);self.append(v)
        try:
            frozen,initial,_=h.load();profile=h.p.profile(frozen,case['context']);vectors=dict(cells={k:[dict(source_request_id='common_'+case['context'],durations_ns=z) for _ in range(4)] for k,z in profile.items()})
            agent.execution_deadline=time.monotonic()+max(0,self.deadline-time.time());began=time.perf_counter()
            with h.forecast_scope():
                result=h.prior.external.old.engine.simulate(dict(protocol=h.p.VERSION,cells=h.p.profile(frozen)),vectors,case['tickets'],policy=agent.policy,settings=self.reg['common_settings'],seed=201,decision_provider=agent)
            seconds=time.perf_counter()-began;previous.audit(result,case['tickets']);ledger=result['ledger'];completed=sum(q['status']=='succeeded' for q in ledger);energy=peak=None;curve=[]
            if completed==len(ledger):
                _,costs,end=h.account(result,initial['initial'],frozen);energy=costs['whole_120s_j'];peak=max(costs['ap_path']);curve=list(zip(range(35,end+1),costs['ap_path']))
            row=dict(planned=len(ledger),completed=completed,incomplete=len(ledger)-completed,
                urgent_failure=sum(q['priority']=='urgent' and ('response_ns' not in q or q.get('late_success',True)) for q in ledger),normal_failure=sum(q['priority']=='normal' and ('response_ns' not in q or q.get('late_success',True)) for q in ledger),
                urgent_p95_ms=result['metrics']['urgent_p95_ms'],normal_mean_ms=result['metrics']['normal_mean_ms'],energy_j=energy,peak_ap_c=peak,native_seconds=seconds,
                surface_temperature=None,thermal_limit_exceed_seconds=None,phone_control_energy=None)
            snapshots=getattr(agent,'snapshots',[])
            for s in snapshots:
                assert s['mask'][s['chosen']] and not (s['mask'] & ~s['physical_mask']).any()
                assert np.isfinite(s['state']).all() and np.isfinite(s['candidates']).all()
            item=dict(row=row,result=result,curve=curve,snapshots=snapshots,callback_seconds=getattr(agent,'callback_times',[]),
                projection_calls=getattr(agent,'projection_calls',0),projection_seconds=getattr(agent,'projection_seconds',0),
                total_extra_wait=getattr(agent,'total_extra_wait',0),request_wait=getattr(agent,'request_wait',{}),cooling_count=getattr(agent,'cooling_count',0),admission_rejections=getattr(agent,'admission_rejections',{}))
            if item['request_wait'] and max(item['request_wait'].values())>.25+1e-8:raise ValueError('actual request cooling allowance exceeded')
            path.parent.mkdir(exist_ok=True);path.write_bytes(gzip.compress(json.dumps(serial(item),allow_nan=False).encode(),mtime=0))
            v.update(status='completed',sha256=sha(path));self.append(dict(event='completed',**v));write(LOCAL/'progress.json',self.used());return item
        except BaseException as error:
            v.update(status='failed',error=repr(error));self.append(dict(event='failed',**v));write(LOCAL/'last_error.json',dict(error=repr(error),traceback=traceback.format_exc(),consumption=self.used()));raise


def agent(role,network=None,ablation=None,deterministic=True):
    f,i,_=h.load()
    if role in ('L0','Rule','PPO'):return r.Controller(f,i['initial'],{'L0':r.L0,'Rule':r.RULE,'PPO':r.PPO}[role],network,deterministic,ablation)
    return h.controller(role,f,i['initial'])


def row(item,case,role,seed=None,episodes=None):
    return dict(condition=case['condition'],arrival_seed=case['seed'],family=case['family'],context=case['context'],policy=role,learning_seed=seed,episodes=episodes,**item['row'])


def gate_rows(rows,policy):
    renamed=[dict(q,seed=q['arrival_seed']) for q in rows if q['policy'] in (policy,'Band','Triton')]
    verdict=previous.gate_rows(renamed,policy)
    rule={(q['condition']):q for q in rows if q['policy']=='Rule'}
    additional=[]
    for q in rows:
        if q['policy']!=policy:continue
        base=rule[q['condition']];delta={k:q[k]-base[k] if q[k] is not None and base[k] is not None else None for k in ('incomplete','urgent_failure','normal_failure','urgent_p95_ms','energy_j','peak_ap_c')}
        additional.append(dict(condition=q['condition'],passed=q['completed']==q['planned']==base['completed']==base['planned'] and all(v is not None and v<=0 for v in delta.values()),delta=delta))
    verdict['same_bank_Rule_comparisons']=additional;verdict['same_bank_Rule_maintenance']=all(v['passed'] for v in additional)
    verdict['promising']=verdict['promising'] and verdict['same_bank_Rule_maintenance'];return verdict


def restore_frames(raw):
    # JSON caches never replace an actual training rollout/controller.
    raise ValueError('cached rollout cannot silently resume a consumed learning episode')


def train_episode(budget,learner,case,index,phase='train'):
    a=learner.fresh_controller(*((lambda f,i,m:(f,i['initial']))(*h.load())))
    identity=f'{phase}_{learner.seed}_{index:02d}'
    if any(v['identity']==identity for v in budget.rows):raise ValueError('training resume requires matching saved learner cursor, not cached replay')
    raw=budget.call(identity,phase,case,a,True);reference=read(LOCAL/'reference_rows.json')[index]
    target=r.c.episode_targets(a,raw['row'],raw['curve'],reference['row'])
    learner.add_episode(target[0],raw['row'],target[2],target[3],controller=a,cursor=dict(next_episode=index+1),consumption=budget.used(),reference_hash=reference['sha256'],metadata=dict(case=index))
    learner.update_if_ready();prefix='' if phase=='train' else phase+'_'
    learner.save(LOCAL/'checkpoints'/f'{prefix}seed{learner.seed}_ep{index+1:02d}.pt')
    return raw


def run():
    if (LOCAL/'completion.json').exists():raise FileExistsError('completed pilot preserved')
    owner=LOCAL/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    try:
        budget=Budget();data=read(LOCAL/'inputs.json');f,initial,_=h.load();dependencies=dict(contract_sha256=sha(LOCAL/'registration.json'),model_sha256=h.UPSTREAM_SHA,sources=budget.reg['source_sha256'])
        for index,case in enumerate(data['fixtures']):
            raw=budget.call('gate_'+str(index),'gate',case,agent('Rule'))
            assert raw['row']['completed']==len(case['tickets']) and raw['snapshots']
        write(LOCAL/'gate.json',dict(status='PASS',native=4,consumption=budget.used()))
        references=[]
        for index,case in enumerate(data['train']):
            raw=budget.call('reference_'+str(index),'reference',case,agent('L0'))
            references.append(dict(row=raw['row'],sha256=sha(LOCAL/'items'/('reference_'+str(index)+'.json.gz'))))
        write(LOCAL/'reference_rows.json',references)
        rows=[]
        for case in data['development']:
            for role in ROLES:rows.append(row(budget.call(f'dev_{role}_{case["condition"]:02d}','development',case,agent(role)),case,role))
        opportunities=sum(sum(int(sum(s['mask'])>1) for s in read_raw(f'dev_Rule_{case["condition"]:02d}')['snapshots']) for case in data['development'])
        write(LOCAL/'opportunities.json',dict(multiple_admitted_choices=opportunities,development_only=True,policy_success_claim=False))
        if not opportunities:raise ValueError('no same-bank improvement choices; do not run critic-only learning')
        for seed in SEEDS:
            learner=r.Learner(seed,r.SCHEMA,dependencies)
            for index,case in enumerate(data['train']):
                train_episode(budget,learner,case,index)
                if index+1 in (16,32):
                    for dev in data['development']:
                        role=f'PPO{seed}_{index+1}';rows.append(row(budget.call(f'dev_{role}_{dev["condition"]:02d}','development',dev,agent('PPO',learner.network)),dev,role,seed,index+1))
                    write(LOCAL/'rows_partial.json',rows)
                    print(json.dumps(dict(seed=seed,episodes=index+1,updates=learner.update_count,consumption=budget.used())),flush=True)
            write(LOCAL/f'learning_{seed}.json',dict(updates=learner.logs,episodes=learner.episode_logs,terminal_sha256=sha(LOCAL/'checkpoints'/f'seed{seed}_ep32.pt'),optimizer_steps=learner.optimizer_steps))
        # Resume from nonempty Adam plus four pending episodes, compare actual4 additional episodes.
        replay=r.Learner.load(LOCAL/'checkpoints/seed11_ep12.pt',expected_schema_id=r.SCHEMA,expected_dependencies=dependencies)
        for index in range(12,16):train_episode(budget,replay,data['train'][index],index,'replay')
        expected=torch.load(LOCAL/'checkpoints/seed11_ep16.pt',map_location='cpu',weights_only=False);actual=replay.snapshot()
        keys=('network','optimizer','multipliers','pending_episodes','accepted_episodes','update_count','optimizer_steps','rng')
        same={k:r.training.state_digest(expected[k])==r.training.state_digest(actual[k]) for k in keys}
        if not all(same.values()):raise ValueError('actual resumed learning differs '+repr(same))
        write(LOCAL/'resume_verification.json',dict(status='PASS',nonempty_Adam=True,pending_episodes_at_resume=4,actual_extra_learning=4,equality=same,consumption=budget.used()))
        gates={f'PPO{seed}_{ep}':gate_rows(rows,f'PPO{seed}_{ep}') for seed in SEEDS for ep in (16,32)}
        for seed in SEEDS:
            learner=r.Learner.load(LOCAL/'checkpoints'/f'seed{seed}_ep32.pt',expected_schema_id=r.SCHEMA,expected_dependencies=dependencies)
            for dev in data['development']:
                role=f'NoWait{seed}';rows.append(row(budget.call(f'nowait_{seed}_{dev["condition"]:02d}','no_wait',dev,agent('PPO',learner.network,'no_wait')),dev,role,seed,32))
        if any(gates[f'PPO{seed}_32']['promising'] for seed in SEEDS):
            for seed in SEEDS:
                learner=r.Learner.load(LOCAL/'checkpoints'/f'seed{seed}_ep32.pt',expected_schema_id=r.SCHEMA,expected_dependencies=dependencies)
                for dev in data['development']:
                    role=f'NoThermal{seed}';rows.append(row(budget.call(f'nothermal_{seed}_{dev["condition"]:02d}','no_thermal',dev,agent('PPO',learner.network,'no_thermal_features')),dev,role,seed,32))
        result=dict(status='completed',task=TASK,rows=rows,gates=gates,consumption=budget.used(),final_confirmation=0,automatic_adoption=False)
        write(LOCAL/'completion.json',result);write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='completed',budget_closed=True,consumption=budget.used(),next_action='report every seed/condition; no automatic main learning/confirmation/device'))
    except BaseException as error:
        write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='stopped_preserve',error=repr(error),consumption=budget.used() if 'budget' in locals() else None,next_action='preserve source/checkpoints/ledger; diagnose without resetting original cap/clock'));raise
    finally:
        if owner.exists() and owner.read_text()==str(os.getpid()):owner.unlink()


def read_raw(identity):return json.loads(gzip.decompress((LOCAL/'items'/(identity+'.json.gz')).read_bytes()))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('register','check','run'));args=parser.parse_args()
    if args.command=='register':print(json.dumps(dict(task=register()['task'],status='registered')))
    elif args.command=='check':print(json.dumps(dict(status='PASS',task=check()['task'])))
    else:run()
