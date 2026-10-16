"""Same-learner32->512 PPO amount comparison; immutable input/budget lineage.

No policy, schema, PPO settings, objective, model or original checkpoint edits.
References/evaluation are native environments; cached actual rollouts cannot
become new training. The old checkpoint dependency manifest stays unchanged.
"""
import argparse, copy, gzip, json, os, subprocess, sys, time, traceback
from datetime import datetime, timezone
import numpy as np
import torch
from tools import d1_rolling_list_rl_run as x

r=x.r; h=x.h; ROOT=x.ROOT
LOCAL=ROOT/'output/overnight_rl_20261011_v1'
PUBLIC=ROOT/'docs/results/overnight_rl_20261011'
TASK='OVERNIGHT-RL-AMOUNT-09'
SEEDS=(11,23,37); TARGETS=(64,128,256,512)
TRAIN_SEEDS=tuple(range(827010001,827010121))
FINAL_SEEDS=(827020101,827020102,827020103,827020104)
sha=x.sha; read=x.read; serial=x.serial
ROLES=('L0','Band','Triton','Rule')

def write(path,value):
    # Windows readers/antivirus can momentarily block rename. This host-only
    # bounded retry never reruns a simulator, changes the ledger or resets time.
    for attempt in range(20):
        try:return x.write(path,value)
        except PermissionError:
            if attempt==19:raise
            time.sleep(.05)

def arithmetic():
    return dict(reference=480,train=1440,development=288,confirmation=336,no_wait=144,
                conditional_no_thermal=144,normal=2688,conditional_total=2832,cap=3072,
                learning=1440,learning_cap=1440,remaining=240)

def sources():
    old=x.check()['source_sha256']
    return dict(old,**{n:sha(ROOT/n) for n in ('tools/d1_overnight_rl_amount.py','tools/test_d1_overnight_rl_amount.py')})

def register():
    if LOCAL.exists():raise FileExistsError('same task and previous ledgers preserved; cannot reset')
    old=x.check(); state=read(x.LOCAL/'WORKING_STATE.json')
    if state['phase']!='completed' or state['consumption']['cumulative_native']!=10321 or state['consumption']['cumulative_learning']!=1549 or (x.LOCAL/'owner.lock').exists():raise ValueError('prior checkpoint/consumption lineage')
    seed_values=TRAIN_SEEDS+FINAL_SEEDS
    for path in (ROOT/'output').glob('*/registration*.json'):
        text=path.read_text(encoding='utf-8')
        if any(str(seed) in text for seed in seed_values):raise ValueError('new seeds already registered')
    data=read(x.LOCAL/'inputs.json');f,initial,m=h.load()
    inputs=dict(train=x.cases(TRAIN_SEEDS,True),development=data['development'],confirmation=x.cases(FINAL_SEEDS),initial=initial['initial'])
    checkpoints={str(seed):dict(path=(x.LOCAL/'checkpoints'/f'seed{seed}_ep32.pt').relative_to(ROOT).as_posix(),sha256=sha(x.LOCAL/'checkpoints'/f'seed{seed}_ep32.pt')) for seed in SEEDS}
    reg=dict(task=TASK,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),registered_utc=datetime.now(timezone.utc).isoformat(),
        authorization='user autonomously approved additional A24 work and substantially longer RL; this task is CPU/GPU PC-only same-learner extension',
        prior_native=10321,prior_learning=1549,native_cap=3072,learning_cap=1440,global_native_cap=20000,global_learning_cap=6144,
        phase_caps=dict(reference=480,train=1440,development=288,confirmation=336,no_wait=144,no_thermal=144),
        arithmetic=arithmetic(),closed_previous_budgets_reopened=False,learning_seeds=list(SEEDS),terminal_episode_counts=list(TARGETS),
        new_training_cases=480,common_training_order='120 unused arrival seeds x4 families; one cyclic context per trace, identical480 for all learners',
        training_seed_range=[TRAIN_SEEDS[0],TRAIN_SEEDS[-1]],development='existing24 conditions, explicitly already observed',
        confirmation='fresh4 arrival seeds x4 families x3 fixed sensitivity contexts =48; all terminal512 seeds, no best seed/checkpoint',
        confirmation_seeds=list(FINAL_SEEDS),checkpoints=checkpoints,original_contract_sha256=sha(x.LOCAL/'registration.json'),
        old_checkpoint_dependencies='unchanged original dependencies in restored learners; this new runner/input/ledger lineage is separately bound here',
        continuation_episodes_per_seed=480,training_settings=old['training_settings'],schema_id=r.SCHEMA,source_sha256=sources(),
        model_sha256=h.UPSTREAM_SHA,exported_model_sha256=sha(h.MODEL),initial_sha256=h.p.INITIAL_SHA,inputs_sha256=r.c.digest(inputs),
        common_settings=old['common_settings'],realization_seed=201,active_seconds=10800,save_reserve_seconds=600,
        objective=old['objective'],action_space=old['action_space'],wait_restrictions=old['wait_restrictions'],gamma=1,
        adoption_gate=old['adoption_gate'],final_epsilon=0,development_has24=True,confirmation_has48=True,
        ablations='terminal512 no_wait all3 seeds48; no_thermal_features only if at least one final terminal seed promising',
        thermal_to_service_feedback=False,NPU=False,device_commands=0,model_fit_calls=0,algorithm_changes=0,reward_tuning=0,seed_replacement=0,
        strict='unchanged',experiment_ready=False,automatic_adoption=False)
    LOCAL.mkdir(parents=True);PUBLIC.mkdir(parents=True,exist_ok=True)
    write(LOCAL/'registration.json',reg);write(LOCAL/'inputs.json',inputs)
    write(PUBLIC/'execution_contract.json',reg);write(PUBLIC/'cases.json',inputs)
    write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='registered',consumption=dict(native_starts=0,learning_starts=0,cumulative_native=10321,cumulative_learning=1549),next_action='common480L0 then preserved3 learners to64/128/256/512, final48 plus ablations'))
    return reg

def check():
    if (LOCAL/'storage_hold.json').exists():raise TimeoutError('explicit storage hold; original clock/caps remain unchanged')
    reg=read(LOCAL/'registration.json')
    amendment=read(LOCAL/'host_save_amendment.json') if (LOCAL/'host_save_amendment.json').exists() else None
    if amendment and (amendment['original_contract_sha256']!=sha(LOCAL/'registration.json') or amendment['old_driver_sha256']!=reg['source_sha256']['tools/d1_overnight_rl_amount.py']):raise ValueError('host amendment lineage')
    storage=read(LOCAL/'storage_hold_amendment.json') if (LOCAL/'storage_hold_amendment.json').exists() else None
    if storage and (storage['original_contract_sha256']!=sha(LOCAL/'registration.json') or storage['prior_host_amendment_sha256']!=sha(LOCAL/'host_save_amendment.json')):raise ValueError('storage hold lineage')
    for name,digest in reg['source_sha256'].items():
        if amendment and name=='tools/d1_overnight_rl_amount.py':digest=amendment['repaired_driver_sha256']
        if storage and name=='tools/d1_overnight_rl_amount.py':digest=storage['repaired_driver_sha256']
        if sha(ROOT/name)!=digest:raise ValueError('registered source changed '+name)
    if sha(h.MODEL)!=reg['exported_model_sha256'] or r.c.digest(read(LOCAL/'inputs.json'))!=reg['inputs_sha256']:raise ValueError('frozen input/model changed')
    for entry in reg['checkpoints'].values():
        if sha(ROOT/entry['path'])!=entry['sha256']:raise ValueError('original terminal32 changed')
    h.load();return reg

class Budget:
    def __init__(self):
        self.reg=check();self.rows=[];self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+10200
        for line in (LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines() if (LOCAL/'executions.jsonl').exists() else []:
            v=json.loads(line)
            if v.get('event'):self.rows[v['number']-1].update(v)
            else:self.rows.append(v)
    def used(self):
        learning=sum(v['learning'] for v in self.rows)
        return dict(native_starts=len(self.rows),learning_starts=learning,native_cap=3072,learning_cap=1440,
            failed=sum(v['status']=='failed' for v in self.rows),host_save_failures_preserved=sum(bool(v.get('host_save_failure_preserved')) for v in self.rows),cumulative_native=10321+len(self.rows),cumulative_learning=1549+learning,device_commands=0,model_fit_calls=0)
    def append(self,v):
        with (LOCAL/'executions.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(v,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def call(self,identity,phase,case,agent,learning=False):
        check();path=LOCAL/'items'/(identity+'.json.gz');existing=next((v for v in self.rows if v['identity']==identity),None)
        if existing:
            if learning:raise ValueError('consumed actual training requires saved learner cursor; cached rollout is not retraining')
            if existing['status']!='completed' or existing['case']!=case or sha(path)!=existing['sha256']:raise ValueError('consumed failed/changed ID preserved')
            return json.loads(gzip.decompress(path.read_bytes()))
        if time.time()>=self.deadline or len(self.rows)>=3072 or 10321+len(self.rows)>=20000:raise TimeoutError('immutable clock/native cap')
        if sum(v['phase']==phase for v in self.rows)>=self.reg['phase_caps'][phase]:raise TimeoutError('phase cap')
        if learning and self.used()['learning_starts']>=1440:raise TimeoutError('learning cap')
        v=dict(number=len(self.rows)+1,identity=identity,phase=phase,case=case,learning=learning,status='started');self.rows.append(v);self.append(v)
        try:
            frozen,initial,_=h.load();profile=h.p.profile(frozen,case['context']);vectors=dict(cells={k:[dict(source_request_id='same_overnight_'+case['context'],durations_ns=z) for _ in range(4)] for k,z in profile.items()})
            agent.execution_deadline=time.monotonic()+max(0,self.deadline-time.time());began=time.perf_counter()
            with h.forecast_scope():result=h.prior.external.old.engine.simulate(dict(protocol=h.p.VERSION,cells=h.p.profile(frozen)),vectors,case['tickets'],policy=agent.policy,settings=self.reg['common_settings'],seed=201,decision_provider=agent)
            seconds=time.perf_counter()-began;x.previous.audit(result,case['tickets']);ledger=result['ledger'];completed=sum(q['status']=='succeeded' for q in ledger);energy=peak=None;curve=[]
            if completed==len(ledger):
                _,costs,end=h.account(result,initial['initial'],frozen);energy=costs['whole_120s_j'];peak=max(costs['ap_path']);curve=list(zip(range(35,end+1),costs['ap_path']))
            row=dict(planned=len(ledger),completed=completed,incomplete=len(ledger)-completed,
                urgent_failure=sum(q['priority']=='urgent' and ('response_ns' not in q or q.get('late_success',True)) for q in ledger),normal_failure=sum(q['priority']=='normal' and ('response_ns' not in q or q.get('late_success',True)) for q in ledger),
                urgent_p95_ms=result['metrics']['urgent_p95_ms'],normal_mean_ms=result['metrics']['normal_mean_ms'],energy_j=energy,peak_ap_c=peak,native_seconds=seconds,
                urgent_planned=sum(q['priority']=='urgent' for q in ledger),normal_planned=sum(q['priority']=='normal' for q in ledger),surface_temperature=None,thermal_limit_exceed_seconds=None,phone_control_energy=None)
            snapshots=getattr(agent,'snapshots',[])
            for s in snapshots:
                assert s['mask'][s['chosen']] and not (s['mask'] & ~s['physical_mask']).any()
                assert np.isfinite(s['state']).all() and np.isfinite(s['candidates']).all()
            item=dict(row=row,result=result,curve=curve,snapshots=snapshots,callback_seconds=getattr(agent,'callback_times',[]),
                projection_calls=getattr(agent,'projection_calls',0),projection_seconds=getattr(agent,'projection_seconds',0),total_extra_wait=getattr(agent,'total_extra_wait',0),request_wait=getattr(agent,'request_wait',{}),cooling_count=getattr(agent,'cooling_count',0),admission_rejections=getattr(agent,'admission_rejections',{}))
            if item['request_wait'] and max(item['request_wait'].values())>.25+1e-8:raise ValueError('actual request cooling cap')
            path.parent.mkdir(exist_ok=True);path.write_bytes(gzip.compress(json.dumps(serial(item),allow_nan=False).encode(),mtime=0))
            v.update(status='completed',sha256=sha(path));self.append(dict(event='completed',**v));write(LOCAL/'progress.json',self.used());return item
        except BaseException as error:
            v.update(status='failed',error=repr(error));self.append(dict(event='failed',**v));write(LOCAL/'last_error.json',dict(error=repr(error),traceback=traceback.format_exc(),consumption=self.used()));raise

def read_raw(identity):return json.loads(gzip.decompress((LOCAL/'items'/(identity+'.json.gz')).read_bytes()))

def gate_rows(rows,policy,conditions):
    roles=('Band','Triton','Rule',policy);by={(q['condition'],q['policy']):q for q in rows if q['policy'] in roles}
    relevant=[q for q in rows if q['policy'] in roles]
    if len(relevant)!=len(by) or set(by)!={(i,role) for i in range(conditions) for role in roles}:raise ValueError('missing/duplicate common-condition rows')
    kpis=('incomplete','urgent_failure','normal_failure','urgent_p95_ms','energy_j','peak_ap_c');diffs=[];maintenance=True
    for i in range(conditions):
        q=by[i,policy]
        for role in ('Band','Triton','Rule'):
            b=by[i,role];delta={k:q[k]-b[k] if q[k] is not None and b[k] is not None else None for k in kpis}
            absolute=q['family'] not in ('low','sustained') or q['incomplete']==q['urgent_failure']==q['normal_failure']==0
            passed=q['planned']==q['completed']==b['completed']==b['planned'] and absolute and all(v is not None and v<=0 for v in delta.values())
            maintenance &= passed;diffs.append(dict(condition=i,family=q['family'],baseline=role,passed=passed,delta=delta))
    primary=[]
    for family in ('low','sustained'):
        relevant=[d for d in diffs if d['family']==family and d['baseline'] in ('Band','Triton')]
        if maintenance and relevant and all(d['delta']['energy_j']<0 or d['delta']['peak_ap_c']<0 for d in relevant):primary.append(family)
    return dict(maintenance_pass=maintenance,promising=maintenance and bool(primary),promising_families=primary,epsilon=0,differences=diffs,automatic_adoption=False)

def dependencies():return dict(contract_sha256=sha(x.LOCAL/'registration.json'),model_sha256=h.UPSTREAM_SHA,sources=x.check()['source_sha256'])

def load_learner(seed,path=None):
    return r.Learner.load(path or x.LOCAL/'checkpoints'/f'seed{seed}_ep32.pt',expected_schema_id=r.SCHEMA,expected_dependencies=dependencies())

def train_episode(budget,learner,case,index,reference):
    f,i,_=h.load();a=learner.fresh_controller(f,i['initial']);identity=f'train_{learner.seed}_{index:03d}'
    raw=budget.call(identity,'train',case,a,True);target=r.c.episode_targets(a,raw['row'],raw['curve'],reference['row'])
    learner.add_episode(target[0],raw['row'],target[2],target[3],controller=a,cursor=dict(next_extension_episode=index+1,total_episode=index+33),consumption=budget.used(),reference_hash=reference['sha256'],metadata=dict(extension_case=index,arrival_seed=case['seed'],new_run_contract_sha256=sha(LOCAL/'registration.json')))
    learner.update_if_ready();latest=LOCAL/'checkpoints'/f'seed{learner.seed}_latest.pt';learner.save(latest)
    if learner.accepted_episodes in TARGETS:learner.save(LOCAL/'checkpoints'/f'seed{learner.seed}_ep{learner.accepted_episodes}.pt')
    return raw

def eval_rows(budget,cases,phase,role,network=None,seed=None,episodes=None,ablation=None):
    rows=[]
    for case in cases:
        identity=f'{phase}_{role}_{case["condition"]:02d}';mode='PPO' if network is not None else role
        raw=budget.call(identity,phase,case,x.agent(mode,network,ablation));rows.append(dict(scope=phase,identity=identity,condition=case['condition'],arrival_seed=case['seed'],family=case['family'],context=case['context'],policy=role,learning_seed=seed,episodes=episodes,**raw['row']))
    return rows

def run():
    if (LOCAL/'completion.json').exists():raise FileExistsError('completed experiment cannot reset')
    owner=LOCAL/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    budget=None
    try:
        budget=Budget();data=read(LOCAL/'inputs.json');references=[];rows=[];lineage=[]
        for seed in SEEDS:
            original=torch.load(x.LOCAL/'checkpoints'/f'seed{seed}_ep32.pt',map_location='cpu',weights_only=False);learner=load_learner(seed);restored=learner.snapshot()
            equality={k:r.training.state_digest(original[k])==r.training.state_digest(restored[k]) for k in ('network','optimizer','multipliers','pending_episodes','accepted_episodes','update_count','optimizer_steps','rng','dependencies')}
            if not all(equality.values()) or learner.accepted_episodes!=32 or learner.update_count!=4:raise ValueError('original full-state restoration mismatch')
            lineage.append(dict(seed=seed,status='PASS',restored_terminal_episodes=32,exact=equality))
        write(LOCAL/'lineage_verification.json',dict(status='PASS',learners=lineage,new_learning=0,algorithm_change=0))
        for index,case in enumerate(data['train']):
            raw=budget.call(f'reference_{index:03d}','reference',case,x.agent('L0'));references.append(dict(row=raw['row'],sha256=sha(LOCAL/'items'/f'reference_{index:03d}.json.gz')))
            if (index+1)%40==0:print(json.dumps(dict(phase='reference',done=index+1,total=480,consumption=budget.used())),flush=True)
        write(LOCAL/'reference_rows.json',references)
        # Development controls are the earlier same input/model completed runs.
        old=read(x.LOCAL/'completion.json')['rows']
        controls=[dict(q,scope='development',identity=f'dev_{q["policy"]}_{q["condition"]:02d}',reused_completed=True) for q in old if q['policy'] in ROLES]
        rows=read(LOCAL/'rows_partial.json') if (LOCAL/'rows_partial.json').exists() else controls
        if not all(any(q['condition']==v['condition'] and q['policy']==v['policy'] and q['scope']=='development' for q in rows) for v in controls):raise ValueError('saved common development controls lost')
        for seed in SEEDS:
            latest=LOCAL/'checkpoints'/f'seed{seed}_latest.pt';learner=load_learner(seed,latest if latest.exists() else None)
            start=learner.accepted_episodes-32
            consumed=sum(v['learning'] and v['identity'].startswith(f'train_{seed}_') for v in budget.rows)
            if consumed!=start:raise ValueError('consumed training cursor cannot replay or lose an actual episode')
            # Restore incomplete evaluation at an already archived checkpoint;
            # preserve live training RNG after deterministic evaluation loads.
            saved_rng=r.training.rng_state()
            for ep in TARGETS:
                path=LOCAL/'checkpoints'/f'seed{seed}_ep{ep}.pt'
                if ep>learner.accepted_episodes or not path.exists():continue
                role=f'PPO{seed}_{ep}'
                if sum(q['scope']=='development' and q['policy']==role for q in rows)==24:continue
                archived=load_learner(seed,path)
                rows=[q for q in rows if not (q['scope']=='development' and q['policy']==role)]
                rows.extend(eval_rows(budget,data['development'],'development',role,archived.network,seed,ep))
                write(LOCAL/'rows_partial.json',rows)
            r.training.restore_rng(saved_rng)
            for index in range(start,480):
                train_episode(budget,learner,data['train'][index],index,references[index])
                if learner.accepted_episodes in TARGETS:
                    role=f'PPO{seed}_{learner.accepted_episodes}'
                    rows.extend(eval_rows(budget,data['development'],'development',role,learner.network,seed,learner.accepted_episodes))
                    write(LOCAL/'rows_partial.json',rows);write(LOCAL/f'learning_{seed}.json',dict(updates=learner.logs,episodes=learner.episode_logs,accepted_episodes=learner.accepted_episodes,optimizer_steps=learner.optimizer_steps))
                    print(json.dumps(dict(phase='checkpoint',seed=seed,episodes=learner.accepted_episodes,updates=learner.update_count,optimizer_steps=learner.optimizer_steps,consumption=budget.used())),flush=True)
            write(LOCAL/f'learning_{seed}.json',dict(updates=learner.logs,episodes=learner.episode_logs,accepted_episodes=learner.accepted_episodes,optimizer_steps=learner.optimizer_steps))
        dev_gates={f'PPO{s}_{ep}':gate_rows([q for q in rows if q['scope']=='development'],f'PPO{s}_{ep}',24) for s in SEEDS for ep in TARGETS}
        for role in ROLES:rows.extend(eval_rows(budget,data['confirmation'],'confirmation',role))
        for seed in SEEDS:
            learner=load_learner(seed,LOCAL/'checkpoints'/f'seed{seed}_ep512.pt')
            rows.extend(eval_rows(budget,data['confirmation'],'confirmation',f'PPO{seed}_512',learner.network,seed,512))
        final=[q for q in rows if q['scope']=='confirmation'];gates={f'PPO{s}_512':gate_rows(final,f'PPO{s}_512',48) for s in SEEDS}
        write(LOCAL/'confirmation_rows_before_ablations.json',rows)
        for seed in SEEDS:
            learner=load_learner(seed,LOCAL/'checkpoints'/f'seed{seed}_ep512.pt');rows.extend(eval_rows(budget,data['confirmation'],'no_wait',f'NoWait{seed}',learner.network,seed,512,'no_wait'))
        if any(q['promising'] for q in gates.values()):
            for seed in SEEDS:
                learner=load_learner(seed,LOCAL/'checkpoints'/f'seed{seed}_ep512.pt');rows.extend(eval_rows(budget,data['confirmation'],'no_thermal',f'NoThermal{seed}',learner.network,seed,512,'no_thermal_features'))
        inventory=[]
        for seed in SEEDS:
            for ep in TARGETS:
                path=LOCAL/'checkpoints'/f'seed{seed}_ep{ep}.pt';z=torch.load(path,map_location='cpu',weights_only=False)
                if z['accepted_episodes']!=ep or z['schema_id']!=r.SCHEMA or len(z['pending_episodes']):raise ValueError('terminal checkpoint inventory')
                inventory.append(dict(seed=seed,episodes=ep,updates=z['update_count'],optimizer_steps=z['optimizer_steps'],sha256=sha(path),has_final_network_critic_Adam_RNG=True,dependency_manifest_unchanged=z['dependencies']==dependencies()))
        write(LOCAL/'checkpoint_inventory.json',dict(status='PASS',checkpoints=inventory))
        result=dict(task=TASK,status='completed',rows=rows,development_gates=dev_gates,confirmation_gates=gates,consumption=budget.used(),automatic_adoption=False,device_commands=0)
        write(LOCAL/'completion.json',result);write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='completed',budget_closed=True,consumption=budget.used(),next_action='analyze full learning curves and48 untouched confirmation; no automatic adoption'))
    except BaseException as error:
        write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='stopped_preserve',error=repr(error),consumption=budget.used() if budget else None,next_action='preserve checkpoint/source/actual consumption; no reset, diagnose bounded repair'))
        raise
    finally:
        if owner.exists() and owner.read_text()==str(os.getpid()):owner.unlink()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('register','check','run'));args=parser.parse_args()
    if args.command=='register':print(json.dumps(dict(status='registered',task=register()['task'])))
    elif args.command=='check':print(json.dumps(dict(status='PASS',task=check()['task'])))
    else:run()
