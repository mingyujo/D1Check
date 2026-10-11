"""Bounded fresh3seed32->64 pilot, new objective, shared unchanged PPO core."""
import argparse,gzip,json,os,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from tools import d1_overnight_rl_amount as old
from tools import d1_service_joint_rl as n

r=n.r;e=n.e;h=old.h;ROOT=old.ROOT
LOCAL=ROOT/'output/service_joint_rl_20261011_v1';PUBLIC=ROOT/'docs/results/service_joint_rl_20261011'
TASK='SERVICE-JOINT-FRESH-RL-02';SEEDS=(11,23,37)
sha=old.sha;read=old.read;write=old.write;serial=old.serial
TRAIN_SEEDS=tuple(range(834010001,834010017));FINAL_SEEDS=(833110101,833110102,833110103,833110104)

def sources():
    files={Path(m.__file__).resolve() for name,m in sys.modules.items() if name.startswith('tools.') and getattr(m,'__file__',None)}
    files.add(ROOT/'tools/test_d1_service_joint_rl_cost.py')
    return {p.relative_to(ROOT).as_posix():sha(p) for p in files if p.suffix=='.py' and p.is_relative_to(ROOT)}

def register():
    if LOCAL.exists():raise FileExistsError('fresh task cannot reset')
    old.check();data=read(old.LOCAL/'inputs.json');train=old.x.cases(TRAIN_SEEDS,True);dev=data['development'];final=old.x.cases(FINAL_SEEDS)
    for p in (ROOT/'output').glob('*/registration*.json'):
        text=p.read_text(encoding='utf-8')
        if any(str(seed) in text for seed in TRAIN_SEEDS):raise ValueError('fresh train seed reused')
    inputs=dict(train=train,development=dev,development_mean=[q for q in dev if q['context']=='mean'],confirmation=final,initial=data['initial'])
    reg=dict(task=TASK,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),registered_utc=datetime.now(timezone.utc).isoformat(),
        authorization='latest user final methodology continuation, root bounded512native/192learning/20min with3min save reserve',
        native_cap=512,learning_cap=192,active_seconds=1200,save_reserve_seconds=180,phase_caps=dict(gate=4,reference=64,train=192,development=96,confirmation=144),
        normal_native=500,budget_formula='gate4+reference64+train192+32 mean8x3=24+64 full24x3=72+confirm48x3=144=500',
        prior_closed_RL_native=2688,prior_closed_RL_learning=1440,old32_512_reused=False,learning_seeds=list(SEEDS),episodes=[32,64],
        training_seed_range=[TRAIN_SEEDS[0],TRAIN_SEEDS[-1]],confirmation_seeds=list(FINAL_SEEDS),development_previously_observed=True,
        schema_id=n.SCHEMA,parent_policy_schema=e.SCHEMA,objective=n.objective.OBJECTIVE,cost_channels=n.objective.COST_CHANNELS,
        service_cost='absolute raw incomplete/urgent failure/normal failure counts; excess vsJointList diagnostic only, no doublecount',
        AP='same telescoping AP-primary signed reward againstJointList',J='signed whole120s J difference vsJointList',
        P95='positive full-episode P95 difference vsJointList/1500ms, not an invented newSLA',initial_multipliers=[1.,10.,1.,1.,1.],gamma=1,
        training_settings=r.training.Settings().__dict__,algorithm_architecture_unchanged=True,new_design_total_effect_not_algorithm_superiority=True,
        fallback_base_reference='new JointList service dispatcher, no Band fallback',model_sha256=h.UPSTREAM_SHA,exported_model_sha256=sha(h.MODEL),
        inputs_sha256=r.c.digest(inputs),source_sha256=sources(),common_settings=old.check()['common_settings'],device_commands=0,NPU=False,model_fit=0,
        strict='unchanged',experiment_ready=False,final_gate='original service/AP/J allconditions gate preserved; independent adoption requires full references, no automatic promotion',
        time_fallback='if insufficient before64 for all3, finish32 for all3 equal budget; keep all saved state, no bestseed choice')
    LOCAL.mkdir();PUBLIC.mkdir(parents=True,exist_ok=True);write(LOCAL/'registration.json',reg);write(LOCAL/'inputs.json',inputs);write(PUBLIC/'execution_contract.json',reg)
    write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='registered',native=0,learning=0,next_action='4 model/action gates then shared refs then3fresh learners; no teacher baseline availability proof means no training'))
    return reg

def check():
    reg=read(LOCAL/'registration.json')
    for name,digest in reg['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('fresh registered source changed '+name)
    if sha(h.MODEL)!=reg['exported_model_sha256'] or r.c.digest(read(LOCAL/'inputs.json'))!=reg['inputs_sha256']:raise ValueError('fixedmodel/input')
    return reg

class Budget(old.Budget):
    def __init__(self):
        self.reg=check();self.rows=[];self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+1020
        for line in (LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines() if (LOCAL/'executions.jsonl').exists() else []:
            v=json.loads(line)
            if v.get('event'):self.rows[v['number']-1].update(v)
            else:self.rows.append(v)
    def used(self):return dict(native_starts=len(self.rows),learning_starts=sum(v['learning'] for v in self.rows),native_cap=512,learning_cap=192,failed=sum(v['status']=='failed' for v in self.rows),device_commands=0,old_closed_budget_reopened=False)
    def append(self,v):
        with (LOCAL/'executions.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(v,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def call(self,identity,phase,case,agent,learning=False):
        if not any(v['identity']==identity for v in self.rows):
            if len(self.rows)>=512 or learning and self.used()['learning_starts']>=192:raise TimeoutError('new task tighter cap')
        # Reuse only the unchanged native/archive implementation. Scope changes
        # are process-local runner globals; files, old policy code and budgets
        # are never changed. Tighter512/192 caps above and own phase caps apply.
        previous_local,previous_check=old.LOCAL,old.check
        old.LOCAL,old.check=LOCAL,check
        try:return old.Budget.call(self,identity,phase,case,agent,learning)
        finally:old.LOCAL,old.check=previous_local,previous_check

def teacher(case):
    f,i,_=h.load();return e.Controller(f,i['initial'],e.JOINT)
def actor(network,deterministic=True):
    f,i,_=h.load();return n.Controller(f,i['initial'],network,deterministic)
def row(raw,case,role,seed=None,episodes=None):return dict(condition=case['condition'],arrival_seed=case['seed'],family=case['family'],context=case['context'],policy=role,learning_seed=seed,episodes=episodes,**raw['row'])

def run():
    if (LOCAL/'completion.json').exists():raise FileExistsError('completed freshpilot')
    owner=LOCAL/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    budget=None
    try:
        budget=Budget();data=read(LOCAL/'inputs.json');refs=[];rows=[];models=[]
        for case in data['development_mean'][:4]:
            raw=budget.call(f'gate_{case["condition"]}','gate',case,teacher(case));models.append(dict(condition=case['condition'],full=raw['row']['planned']==raw['row']['completed'],opportunities=sum(sum(s['mask'])>1 for s in raw['snapshots'])))
        if not all(v['full'] for v in models):raise ValueError('model/action availability failed')
        write(LOCAL/'model_gate.json',dict(status='PASS',cases=models,warning='existence of choices is not a performance guarantee'))
        for j,case in enumerate(data['train']):
            raw=budget.call(f'reference_{j:02d}','reference',case,teacher(case));refs.append(dict(row=raw['row'],sha256=sha(LOCAL/'items'/f'reference_{j:02d}.json.gz')))
        write(LOCAL/'reference_rows.json',refs)
        dependencies=dict(contract_sha256=sha(LOCAL/'registration.json'),model=h.UPSTREAM_SHA,sources=budget.reg['source_sha256'],objective=n.objective.OBJECTIVE)
        learners={seed:n.Learner(seed,n.SCHEMA,dependencies) for seed in SEEDS}
        # Round-robin ensures all three receive an equal completed stage.
        for target in (32,64):
            if target==64 and time.time()+330>budget.deadline:break
            start=0 if target==32 else 32
            for index in range(start,target):
                for seed in SEEDS:
                    learner=learners[seed];case=data['train'][index];f,i,_=h.load();controller=learner.fresh_controller(f,i['initial'])
                    raw=budget.call(f'train_{seed}_{index:02d}','train',case,controller,True)
                    frames,rewards,costs,valid,diag=n.objective.episode_targets(controller,raw['row'],raw['curve'],refs[index]['row'])
                    learner.add_episode(frames,raw['row'],costs,valid,controller=controller,cursor=dict(next_episode=index+1),consumption=budget.used(),reference_hash=refs[index]['sha256'],metadata=dict(case=index,objective_diag=diag))
                    learner.update_if_ready();learner.save(LOCAL/'checkpoints'/f'seed{seed}_latest.pt')
                    if index+1 in (32,64):learner.save(LOCAL/'checkpoints'/f'seed{seed}_ep{index+1}.pt')
            dev=data['development_mean'] if target==32 else data['development']
            for seed in SEEDS:
                for case in dev:
                    role=f'FreshPPO{seed}_{target}';raw=budget.call(f'dev_{role}_{case["condition"]:02d}','development',case,actor(learners[seed].network));rows.append(row(raw,case,role,seed,target))
            write(LOCAL/'rows_partial.json',rows);print(json.dumps(dict(stage=target,consumption=budget.used())),flush=True)
        terminal={seed:learners[seed].accepted_episodes for seed in SEEDS}
        if len(set(terminal.values()))!=1 or next(iter(terminal.values())) not in (32,64):raise ValueError('unequal stage budget; no terminal result')
        for seed in SEEDS:
            learner=learners[seed]
            for case in data['confirmation']:
                role=f'FreshPPO{seed}_{learner.accepted_episodes}';raw=budget.call(f'final_{role}_{case["condition"]:02d}','confirmation',case,actor(learner.network));rows.append(dict(scope='confirmation',**row(raw,case,role,seed,learner.accepted_episodes)))
            write(LOCAL/f'learning_{seed}.json',dict(updates=learner.logs,episodes=learner.episode_logs,accepted_episodes=learner.accepted_episodes,optimizer_steps=learner.optimizer_steps,terminal_sha256=sha(LOCAL/'checkpoints'/f'seed{seed}_ep{learner.accepted_episodes}.pt')))
        result=dict(status='completed',task=TASK,rows=rows,terminal_episodes=terminal,consumption=budget.used(),original_gate_changed=False,automatic_adoption=False,design_not_algorithm_comparison=True)
        write(LOCAL/'completion.json',result);write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='completed',consumption=budget.used(),terminal=terminal,budget_closed=True,next_action='report actualfreshobjective/sameJointList semantics, alignshared48references beforejudgment'))
    except BaseException as error:
        write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='stopped_preserve',error=repr(error),consumption=budget.used() if budget else None,next_action='preserve source/checkpoints/consumed starts; no retry/reset without bounded record'));raise
    finally:
        if owner.exists() and owner.read_text()==str(os.getpid()):owner.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','check','run'));a=p.parse_args()
    if a.command=='register':print(json.dumps(dict(status='registered',task=register()['task'])))
    elif a.command=='check':print(json.dumps(dict(status='PASS',task=check()['task'])))
    else:run()
