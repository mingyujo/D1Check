"""Registered, bounded CPU/GPU PPO development and continuation. No devices."""
from __future__ import annotations
import argparse
import ast
import copy
import gzip
import hashlib
import json
import os
import platform
import subprocess
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import torch
from tools import d1_list_candidate_rl as c
from tools import d1_list_candidate_rl_engine as engine
from tools import d1_list_candidate_rl_training as training
from tools import d1_external_rules as external
from tools import d1_ie_dispatch as ie
from tools import d1_ie_candidates_v2 as previous
from tools import d1_triton_rules as triton

ROOT=c.ROOT
FAMILIES=('low','queue','burst','sustained')
CONTEXTS=('mean','short_context','long_context')
BASELINES=('L0','GREEDY','EDD','Band','Triton','ListV2')
SEEDS=(11,23,37)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def serial(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,torch.Tensor):return v.tolist()
    if isinstance(v,dict):return {str(k):serial(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,set)):return [serial(x) for x in v]
    return v
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(serial(value),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)

def cases(seeds,train=False):
    result=[]
    for seed in seeds:
        for family in FAMILIES:
            for context in ([CONTEXTS[len(result)%3]] if train else CONTEXTS):
                result.append(dict(seed=seed,family=family,context=context))
    return result

def closure_sources():
    todo=['d1_list_candidate_rl_run','d1_list_candidate_rl_training','d1_list_candidate_rl','d1_list_candidate_rl_engine',
          'd1_external_rules','d1_ie_dispatch','d1_ie_candidates_v2','d1_triton_rules','d1_list_candidate_rl_representation']
    found={}
    while todo:
        name=todo.pop();path=ROOT/'tools'/(name+'.py')
        if name in found or not path.exists():continue
        found[name]=path
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node,ast.ImportFrom):
                if node.module=='tools':todo.extend(a.name for a in node.names)
                elif node.module and node.module.startswith('tools.'):todo.append(node.module.split('.')[1])
            elif isinstance(node,ast.Import):
                todo.extend(a.name.split('.')[1] for a in node.names if a.name.startswith('tools.'))
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in found.values()}
    for name in ('docs/results/list_candidate_rl_design_01/design_contract.json',
                 'docs/results/list_candidate_rl_review_01/design_amendment_v4.json',
                 'docs/results/list_candidate_rl_prepilot_02/prepilot_contract.json'):
        sources[name]=sha(ROOT/name)
    return sources

def register(output):
    output.mkdir(parents=True,exist_ok=False)
    frozen,case=c.p.inputs(c.p.BUNDLE)
    contract=dict(task='LIST-CANDIDATE-RL-TRAIN-MAIN-05',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
      registered_utc=datetime.now(timezone.utc).isoformat(),active_seconds=7200,save_reserve_seconds=300,
      previous_environment_starts=6549,previous_learning_starts=641,implementation_gate_already_consumed=32,
      design_environment_cap=1536,design_learning_cap=416,global_environment_cap=20000,global_learning_cap=6144,
      stage_A_design_environment_cap=536,stage_A_learning_cap=224,learning_seeds=list(SEEDS),
      pilot_episodes_per_seed=64,main_additional_episodes_per_seed=64,resume_learning_fixture_expected=20,
      historical_no_arrival_training_reallocated_to_main=192,hyperparameters=training.Settings().__dict__,
      objective='v4 AP primary; signed energy, positive-part service costs; gamma1',schema='head2+C_next',
      train=cases(range(818010001,818010017),True),development=cases((818020101,818020102)),
      confirmation=cases((818030101,818030102,818030103,818030104)),
      fixture=cases((818001001,818001002),True),
      success_gate_unchanged=True,main_after_development_failure_explicitly_authorized=True,
      changes_after_pilot='expert discussion then validity repair only; no automatic reward/action/threshold tuning',
      reference='new L0; Band/Triton evaluation only',NPU_added=False,device_commands=0,
      frozen_model_sha256=c.p.MODEL_SHA,frozen_initial_sha256=c.p.INITIAL_SHA,
      source_sha256=closure_sources(),python_version=platform.python_version(),torch_version=str(torch.__version__),
      numpy_version=np.__version__,torch_threads=1,torch_deterministic=True,
      expected_design_environment_total_with_conditional_ablation=1372,expected_learning_total=404,
      heldout_policy='fixed terminal128 actors, never best seed or best validation checkpoint',
      initial_scope='existing validated fixed preload; same CPU/GPU profiles/inputs/deadlines/curves; model conditional PC only',
      original_experiment_ready=False)
    # Register actual inputs once; future requests are never passed to the actor.
    contract['input_sha256']={name:c.digest([dict(case=q,requests=external.old.workload(q['family'],q['seed'])) for q in contract[name]])
                              for name in ('train','development','confirmation','fixture')}
    write(output/'registration.json',contract)
    return contract

def network_hash(controller):
    network=getattr(controller,'network',None)
    return training.state_digest(network.state_dict()) if isinstance(network,torch.nn.Module) else None

class Budget:
    def __init__(self,output,phase):
        self.output=Path(output)
        effective=self.output/'registration_effective.json'
        self.reg=read(effective if effective.exists() else self.output/'registration.json');self.phase=phase
        self.path=self.output/'execution.jsonl';self.rows=[]
        for line in self.path.read_text(encoding='utf-8').splitlines() if self.path.exists() else []:
            row=json.loads(line)
            if 'event' not in row:self.rows.append(row)
            else:self.rows[row['number']-1].update(row)
        self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+self.reg['active_seconds']-self.reg['save_reserve_seconds']
        for name,h in self.reg['source_sha256'].items():
            if sha(ROOT/name)!=h:raise ValueError('registered source changed: '+name)
        c.p.inputs(c.p.BUNDLE)
    def consumption(self):
        learning=sum(bool(r['learning']) for r in self.rows)
        return dict(new_environment_starts=len(self.rows),design_environment_starts=32+len(self.rows),
          cumulative_environment_starts=6549+len(self.rows),new_learning_starts=learning,
          cumulative_learning_starts=641+learning,failed=sum(r['status']=='failed' for r in self.rows),device_commands=0)
    def append(self,value):
        with self.path.open('a',encoding='utf-8') as f:
            f.write(json.dumps(serial(value),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def work_guard(self):
        if time.time()>=self.deadline:raise TimeoutError('registered 2h clock with 5min save reserve')
        for name,h in self.reg['source_sha256'].items():
            if sha(ROOT/name)!=h:raise ValueError('registered source changed during run: '+name)
        c.p.inputs(c.p.BUNDLE)
    def guard(self,learning=False):
        self.work_guard()
        counts=self.consumption()
        if counts['design_environment_starts']>=1536 or counts['cumulative_environment_starts']>=20000:raise TimeoutError('environment cap')
        if learning and (counts['new_learning_starts']>=416 or counts['cumulative_learning_starts']>=6144):raise TimeoutError('learning cap')
        if self.phase in ('gate','pilot') and counts['design_environment_starts']>=536:raise TimeoutError('stage A environment cap')
    def call(self,identity,controller,case,*,learning=False):
        artifact=self.output/'items'/(identity+'.json.gz');statefile=self.output/'items'/(identity+'.pt')
        actor_hash=network_hash(controller)
        old=next((r for r in self.rows if r['identity']==identity),None)
        if old:
            if old['case']!=case or bool(old['learning'])!=learning:raise ValueError('consumed ID input/role mismatch')
            if old['network_before_sha256']!=actor_hash:raise ValueError('completed rollout belongs to different actor/critic weights')
            if old['status']!='completed' or sha(artifact)!=old['artifact_sha256']:raise ValueError('consumed/invalid run ID '+identity)
            item=json.loads(gzip.decompress(artifact.read_bytes()))
            if isinstance(controller,c.Controller):
                if sha(statefile)!=old['controller_sha256']:raise ValueError('changed completed controller artifact')
                saved=torch.load(statefile,map_location='cpu',weights_only=False)
                c.restore_controller(controller,saved['controller']);training.restore_rng(saved['rng_after'])
            return item
        self.guard(learning)
        requests=external.old.workload(case['family'],case['seed'])
        row=dict(number=len(self.rows)+1,identity=identity,phase=self.phase,status='started',learning=learning,case=case,planned=len(requests),network_before_sha256=actor_hash)
        self.rows.append(row);self.append(row)
        frozen,initial_case=c.p.inputs(c.p.BUNDLE);initial=initial_case['initial']
        actual=c.p.profile(frozen,case['context'])
        vectors=dict(cells={key:[dict(source_request_id='common_measured_context_'+case['context'],durations_ns=values) for _ in range(4)] for key,values in actual.items()})
        try:
            began=time.perf_counter()
            result=engine.simulate(dict(protocol=c.p.VERSION,cells=c.p.profile(frozen)),vectors,requests,
              policy=controller.policy,settings=external.settings(),seed=201,decision_provider=controller)
            elapsed=time.perf_counter()-began
            _,costs,end=c.p.account(result,initial,frozen)
            ledger=result['ledger'];completed=sum(q['status']=='succeeded' for q in ledger);full=completed==len(requests)
            metrics=dict(planned=len(requests),completed=completed,incomplete=len(requests)-completed,
              urgent_failure=sum(q['priority']=='urgent' and ('response_ns' not in q or q['late_success']) for q in ledger),
              normal_failure=sum(q['priority']=='normal' and ('response_ns' not in q or q['late_success']) for q in ledger),
              urgent_p95_ms=result['metrics']['urgent_p95_ms'],normal_mean_ms=result['metrics']['normal_mean_ms'],
              energy_j=costs['whole_120s_j'] if full else None,peak_ap_c=max(costs['ap_path']) if full else None,native_seconds=elapsed,
              scheduled_requests=len(requests),normal_scheduled=sum(q['priority']=='normal' for q in ledger),
              urgent_scheduled=sum(q['priority']=='urgent' for q in ledger))
            item=dict(case=case,row=metrics,result=result,curve=list(zip(range(35,end+1),costs['ap_path'])))
            if isinstance(controller,c.Controller):
                item['control']=dict(defer_seconds=controller.deferred_seconds,holds=controller.hold_counter,
                  fallbacks=controller.fallbacks,forced_waits=controller.forced_waits,pair_cancelled=controller.pair_cancelled,
                  selection_opportunities=controller.selection_opportunities,
                  action_counts={kind:sum(s['kinds'][s['chosen']]==kind for s in controller.snapshots) for kind in sorted({s['kinds'][s['chosen']] for s in controller.snapshots})},
                  decision_seconds=[s['decision_seconds'] for s in controller.snapshots])
            artifact.parent.mkdir(parents=True,exist_ok=True)
            artifact.write_bytes(gzip.compress(json.dumps(serial(item),allow_nan=False).encode()))
            if isinstance(controller,c.Controller):
                torch.save(dict(controller=c.controller_state(controller),rng_after=training.rng_state()),statefile)
                row['controller_sha256']=sha(statefile)
            row.update(status='completed',completed=completed,artifact_sha256=sha(artifact),seconds=elapsed)
            self.append(dict(event='completion',**row));write(self.output/'progress.json',dict(phase=self.phase,last=identity,consumption=self.consumption()))
            return item
        except BaseException as error:
            row.update(status='failed',error=repr(error));self.append(dict(event='failure',**row))
            write(self.output/'failures'/(identity+'.json'),dict(row=row,traceback=traceback.format_exc(),events=getattr(controller,'events',[])))
            raise

def dependencies(reg):
    return training.dependency_manifest(dict(source_sha256=reg['source_sha256'],input_sha256=reg['input_sha256'],
      registration_sha256=c.digest(reg),reference_role='L0',schema='head2+C_next'))
def base_controller(name,frozen,initial):
    if name in ('L0','GREEDY'):return c.Controller(frozen,initial,c.L0 if name=='L0' else c.GREEDY,feature_variant='head2+C_next')
    if name=='EDD':return ie.Controller(frozen,initial,'IE_EDD_ECT_LANE_PC_V1')
    if name=='Band':return external.BandController(frozen,initial)
    if name=='Triton':return triton.Controller(frozen,initial,triton.OFF)
    if name=='ListV2':return previous.Controller(frozen,initial,previous.LIST)
    raise ValueError(name)
def inputs():
    frozen,case=c.p.inputs(c.p.BUNDLE);initial=case['initial']
    schema=c.Controller(frozen,initial,feature_variant='head2+C_next').schema_id
    return frozen,initial,schema
def reference(budget,label,index,case):
    frozen,initial,_=inputs()
    identity=f'{label}_L0_{index:03d}'
    item=budget.call(identity,base_controller('L0',frozen,initial),case)
    return item,sha(budget.output/'items'/(identity+'.json.gz'))
def observe(budget,learner,identity,case,ref,refhash,cursor):
    frozen,initial,_=inputs();controller=learner.fresh_controller(frozen,initial)
    item=budget.call(identity,controller,case,learning=True)
    learner.observe_episode(controller,item['row'],item['curve'],ref['row'],cursor=cursor,
      consumption=budget.consumption(),reference_hash=refhash,metadata=case)
    return item
def update(budget,learner):
    if len(learner.pending_episodes)>=learner.settings.episodes_per_update:
        budget.work_guard()
        return learner.update_if_ready()
    return None
def stable(value):
    if isinstance(value,dict):return {k:stable(v) for k,v in value.items() if k not in ('native_seconds','decision_seconds','seconds','consumption')}
    if isinstance(value,list):return [stable(v) for v in value]
    if isinstance(value,tuple):return tuple(stable(v) for v in value)
    return value

def resume_gate(budget):
    _,_,schema=inputs();deps=dependencies(budget.reg);refs=[]
    for i,q in enumerate(budget.reg['fixture']):refs.append(reference(budget,'fixture_ref',i,q))
    learner=training.Learner(97,schema,deps)
    for i in range(12):
        ref,h=refs[i%8];observe(budget,learner,f'fixture_A_{i:02d}',budget.reg['fixture'][i%8],ref,h,dict(fixture_next=i+1))
        update(budget,learner)
    if not learner.optimizer.state or len(learner.pending_episodes)!=4:raise ValueError('fixture needs nonempty Adam and partial batch')
    archive=budget.output/'checkpoints/resume_fixture_partial.pt';learner.save(archive)
    branch_A=[]
    for i in range(12,16):
        ref,h=refs[i%8];branch_A.append(observe(budget,learner,f'fixture_A_{i:02d}',budget.reg['fixture'][i%8],ref,h,dict(fixture_next=i+1)))
        update(budget,learner)
    expected=copy.deepcopy(learner.snapshot())
    resumed=training.Learner.load(archive,expected_schema_id=schema,expected_dependencies=deps)
    branch_B=[]
    for i in range(12,16):
        ref,h=refs[i%8];branch_B.append(observe(budget,resumed,f'fixture_B_{i:02d}',budget.reg['fixture'][i%8],ref,h,dict(fixture_next=i+1)))
        update(budget,resumed)
    actual=resumed.snapshot()
    if training.state_digest(stable(expected))!=training.state_digest(stable(actual)):raise ValueError('actual additional-update resume mismatch')
    if training.state_digest(stable(branch_A))!=training.state_digest(stable(branch_B)):raise ValueError('actual subsequent on-policy episodes differ after resume')
    bad=copy.deepcopy(deps);bad['caller_contracts']['schema']='changed'
    try:training.Learner.load(archive,expected_schema_id=schema,expected_dependencies=bad)
    except ValueError:rejected=True
    else:raise ValueError('dependency mismatch accepted')
    evidence=dict(status='PASS',actual_learning_environment_starts=20,L0_references=8,Adam_nonempty=True,
      partial_batch_episodes=4,additional_on_policy_episodes_exact=True,network_Adam_lambda_RNG_losses_gradients_cursor_exact=True,
      logical_accepted_episodes=16,source_mismatch_rejected=rejected,optimizer_steps_original=expected['optimizer_steps'],
      actual_optimizer_steps_both_branches=expected['optimizer_steps']+actual['optimizer_steps']-read_optimizer_count(archive),
      excludes='host timings and actual outer global starts differ by replay4; global budget was never restored',
      scope='episode/update boundary continuation, not live engine or mid-minibatch resume',consumption=budget.consumption())
    write(budget.output/'resume_verification.json',evidence);return evidence
def read_optimizer_count(path):return torch.load(path,map_location='cpu',weights_only=False)['optimizer_steps']

def train_to(budget,target):
    if target not in (64,128):raise ValueError('unregistered training extension')
    if target==128:
        decision=read(budget.output/'expert_main_decision.json')
        if not decision.get('review_complete') or not decision.get('main_allowed'):raise ValueError('missing main-stage review decision')
    _,_,schema=inputs();deps=dependencies(budget.reg)
    refs=[reference(budget,'train_ref',i,q) for i,q in enumerate(budget.reg['train'])]
    for seed in SEEDS:
        checkpoint=budget.output/f'checkpoints/seed{seed}_last.pt'
        learner=training.Learner.load(checkpoint,expected_schema_id=schema,expected_dependencies=deps) if checkpoint.exists() else training.Learner(seed,schema,deps)
        if learner.accepted_episodes>target:raise ValueError('cannot overwrite an earlier terminal checkpoint with later weights')
        if learner.accepted_episodes and learner.cursor!=dict(seed=seed,next_episode=learner.accepted_episodes):raise ValueError('learner cursor mismatch')
        update(budget,learner)
        while learner.accepted_episodes<target:
            i=learner.accepted_episodes;q=budget.reg['train'][i%64];ref,h=refs[i%64]
            observe(budget,learner,f'train_s{seed}_{i:03d}',q,ref,h,dict(seed=seed,next_episode=i+1))
            learner.save(checkpoint) # Valid partial batch boundary before any update.
            update(budget,learner);learner.save(checkpoint)
            if (i+1)%8==0:write(budget.output/f'learner_seed{seed}.json',dict(seed=seed,episodes=learner.accepted_episodes,
              updates=learner.update_count,optimizer_steps=learner.optimizer_steps,logs=learner.logs,episode_logs=learner.episode_logs))
        learner.save(budget.output/f'checkpoints/seed{seed}_terminal{target}.pt')
    return dict(status='completed',episodes_per_seed=target,consumption=budget.consumption())

class NoWaitController(c.Controller):
    def bank(self,queue,lanes,now):
        return [a for a in super().bank(queue,lanes,now) if a['wait']==0.]

def evaluate(budget,label,target,baseline=True,no_wait=False):
    frozen,initial,schema=inputs();deps=dependencies(budget.reg)
    qlist=budget.reg['confirmation' if label in ('confirmation','ablation') else 'development'];rows=[]
    if baseline:
        for role in BASELINES:
            for i,q in enumerate(qlist):
                item=budget.call(f'{label}_{role}_{i:03d}',base_controller(role,frozen,initial),q)
                rows.append(dict(condition=i,case=q,policy=role,seed=None,training_episodes=0,**item['row'],control=item.get('control')))
    for seed in SEEDS:
        learner=training.Learner.load(budget.output/f'checkpoints/seed{seed}_terminal{target}.pt',expected_schema_id=schema,expected_dependencies=deps)
        for i,q in enumerate(qlist):
            controller=(NoWaitController if no_wait else c.Controller)(frozen,initial,c.PPO,network=learner.network,deterministic=True,feature_variant='head2+C_next')
            item=budget.call(f'{label}_PPO{target}_s{seed}_{i:03d}',controller,q)
            rows.append(dict(condition=i,case=q,policy=f'PPO{target}',seed=seed,training_episodes=target,**item['row'],control=item.get('control')))
    write(budget.output/f'evaluation_{label}_{target}.json',dict(status='completed',rows=rows,consumption=budget.consumption()))
    return dict(status='completed',evaluations=len(rows),consumption=budget.consumption())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--phase',required=True,choices=('register','gate','pilot','main','confirmation','ablation'))
    args=parser.parse_args();torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    if args.phase=='register':print(json.dumps(register(args.output),ensure_ascii=False,indent=2));return
    owner=args.output/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    budget=None
    try:
        budget=Budget(args.output,args.phase)
        if args.phase=='gate':result=resume_gate(budget)
        elif args.phase=='pilot':
            if read(args.output/'resume_verification.json')['status']!='PASS':raise ValueError('resume gate not passed')
            train_to(budget,64);result=evaluate(budget,'development',64)
        elif args.phase=='main':
            train_to(budget,128);result=evaluate(budget,'main_development',128,baseline=False)
        elif args.phase=='ablation':result=evaluate(budget,'ablation',128,baseline=False,no_wait=True)
        else:result=evaluate(budget,'confirmation',128)
        write(args.output/(args.phase+'_completion.json'),result)
        print(json.dumps(serial(result),ensure_ascii=False,indent=2))
    except BaseException as error:
        write(args.output/(args.phase+'_error.json'),dict(status='stopped_error',error=repr(error),traceback=traceback.format_exc(),
          consumption=budget.consumption() if budget else None))
        raise
    finally:
        if owner.exists() and owner.read_text(encoding='ascii')==str(os.getpid()):owner.unlink()

if __name__=='__main__':main()
