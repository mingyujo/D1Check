"""One additional finite tranche: matched current/tail PPO, no devices.

Old experiments and their unused budgets are never reset or reopened.
"""
from __future__ import annotations
import argparse
import ast
import copy
import gzip
import json
import os
import platform
import subprocess
import time
import traceback
from datetime import datetime,timezone
from pathlib import Path
import torch
from tools import d1_list_candidate_rl_run as r
from tools import d1_list_candidate_tail as tail
from tools import d1_list_candidate_rl_main_report as report

c=r.c
training=r.training
ROOT=r.ROOT
PRIOR=ROOT/'output/list_candidate_rl_develop_20261010_v1'
TASK='LIST-CANDIDATE-RL-TAIL-08'
VARIANTS=('current','tail')
CAP=1536
LEARNING_CAP=416
STAGE_CAPS={'gate':32,'resume':28,'references':64,'pilot':192,'pilot_development':240,
            'main':192,'main_development':144,'confirmation':480,'opportunity':32}


def sources():
    manifest=r.closure_sources()
    for name in ('tools/d1_list_candidate_tail.py','tools/d1_list_candidate_service_list.py',
                 'tools/d1_list_candidate_service_backlog.py','tools/d1_list_candidate_tail_run.py'):
        manifest[name]=r.sha(ROOT/name)
    manifest['tools/d1_list_candidate_rl_main_report.py']=r.sha(ROOT/'tools/d1_list_candidate_rl_main_report.py')
    return manifest


def gate_case(index):
    # All tickets really arrive together. No hidden future is supplied to a controller.
    patterns=('CDD','CCD','CDDD','CCCCDDDD')
    tasks=patterns[index%len(patterns)]
    requests=[dict(id=f'gate{index}_{i}',task='classification' if task=='C' else 'detection',
        priority='urgent' if task=='C' else 'normal',ordinal=i,arrival_ns=35_000_000_000,
        deadline_offset_ns=1_500_000_000 if task=='C' else 6_000_000_000)
        for i,task in enumerate(tasks)]
    return dict(seed=820000001+index,family='gate',context='mean',requests=requests)


def register(output):
    canonical=ROOT/'output/list_candidate_tail_20261010_v1'
    if canonical.exists():
        raise FileExistsError('this task already registered; a new directory must not reset consumption')
    previous=r.read(PRIOR/'progress.json')['consumption']
    if (previous['cumulative_environment_starts'],previous['cumulative_learning_starts'])!=(7865,1045):
        raise ValueError('prior consumption changed; re-audit instead of resetting')
    for directory in (PRIOR,ROOT/'output/list_candidate_rl_train_main_20261010_v1'):
        if (directory/'owner.lock').exists():raise ValueError('another learning run is owned')
    output.mkdir(parents=True,exist_ok=False)
    frozen,initial,schema=r.inputs()
    new_schema=tail.TailController(frozen,initial,feature_variant='head2+C_next').schema_id
    reg=dict(task=TASK,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        registered_utc=datetime.now(timezone.utc).isoformat(),active_seconds=7200,save_reserve_seconds=300,
        authorization='user: 우선 토론해서 더 발전시켜봐 강화학습까지 알아서 해놔도 좋아',
        previous_cumulative_environment_starts=7865,previous_cumulative_learning_starts=1045,
        closed_previous_design=dict(spent_environments=1348,cap_environments=1536,spent_learning=404,cap_learning=416,
            unused_environment=188,unused_learning=12,reopened=False),
        new_tranche_environment_cap=CAP,new_tranche_learning_cap=LEARNING_CAP,
        cumulative_environment_cap=20000,cumulative_learning_cap=6144,
        expected_new_environment_starts=sum(v for k,v in STAGE_CAPS.items() if k!='opportunity'),expected_new_learning_starts=404,
        stage_caps={k:v for k,v in STAGE_CAPS.items() if k!='opportunity'},learning_seeds=list(r.SEEDS),variants=list(VARIANTS),
        pilot_episodes_per_seed_per_variant=32,terminal_episodes_per_seed_per_variant=64,
        hyperparameter_search_trials=0,candidate_specification_trials=1,
        train=r.cases(range(820010001,820010017),True),
        development=r.cases((820020101,820020102)),confirmation=r.cases((820030101,820030102,820030103,820030104)),
        fixture=r.cases((820001001,820001002),True),gate=[gate_case(i) for i in range(8)],
        objective='unchanged AP primary/signed J/positive-part F,U,N,P; gamma1; common L0 reference',
        schemas=dict(current=schema,tail=new_schema),hyperparameters=training.Settings().__dict__,
        gate_opportunity='native gate tail snapshots: >=1 admitted nonL0 with strict predicted AP or J benefit; no success guarantee',
        extension_rule='all six 32-episode learners valid; tail informative decisions>0 and sampled policy genuinely uses alternatives; extend all six equally to64, no seed selection; performance improvement not presumed',
        confirmation_rule='all fixed terminal64 actors plus same-candidate rule and L0/Band/Triton; diagnostic even if development unpromising, no adoption override',
        final_success_gate_unchanged=True,epsilon=0,reference_role='L0',
        representative=dict(condition=9,context='mean',family='sustained',learning_seed=23,window_s=[35,55]),
        original_actor_archives_reused_for_new_learning=False,physical_bank_unchanged=True,
        original_experiment_ready=False,NPU_added=False,device_commands=0,
        prediction_masks_are_physical_guarantees=False,phone_control_J_measured=False,
        frozen_model_sha256=c.p.MODEL_SHA,frozen_initial_sha256=c.p.INITIAL_SHA,
        source_sha256=sources(),prior_progress_sha256=r.sha(PRIOR/'progress.json'),
        python_version=platform.python_version(),torch_version=str(torch.__version__),
        semantic_changes=['arrived full queue L0 continuation','AP integer35..180 / J120',
            'current-queue service/J prediction admission distinct from physical mask','L0-relative new cost feature meanings','exact-tie rule reference'],
        improvement_scope='conditional measured-coefficient CPU/GPU simulation, AP not surface temperature')
    reg['input_sha256']={name:c.digest([dict(case=q,requests=q.get('requests',r.external.old.workload(q['family'],q['seed'])) if q['family']!='gate' else q['requests']) for q in reg[name]])
        for name in ('train','development','confirmation','fixture','gate')}
    r.write(output/'registration.json',reg)
    # Preserve the user-owned 14 lines and unrelated code by an initial audit receipt.
    r.write(output/'workspace_start.json',dict(head=reg['head'],branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
        status_sha256=r.sha(ROOT/'docs/PROJECT_STATUS.md'),tracked_diff=subprocess.check_output(['git','diff','--numstat'],text=True),
        protected_untracked={n:r.sha(ROOT/n) for n in ('tools/d1_registered_baseline.py','tools/test_d1_registered_baseline.py') if (ROOT/n).exists()}))
    return reg


def amend_opportunity(output):
    if (output/'registration_effective.json').exists():raise FileExistsError('amendment already frozen')
    original=r.read(output/'registration.json')
    gate_result=r.read(output/'gate_verification.json')
    if gate_result['status']!='PASS' or gate_result['learning_allowed']:
        raise ValueError('scope diagnostic only after small chronology gate has no opportunity')
    reg=copy.deepcopy(original)
    reg.update(source_sha256=sources(),stage_caps=STAGE_CAPS,
        opportunity=[dict(q) for q in original['development'] if q['context']=='mean'],
        expected_new_environment_starts=sum(STAGE_CAPS.values()),
        amendment=dict(registered_utc=datetime.now(timezone.utc).isoformat(),
            reason='small simultaneous-arrival gate has no strict beneficial alternatives; inspect already registered mixed-arrival conditions before interpreting absence',
            new_candidate_specifications=0,changed_success_criterion=False,original_gate_learning_allowed=False,
            additional_environment_cap=32,additional_learning=0,reserve_used=32,cap_and_clock_reset=False,
            original_source_preserved='source_versions/registered_gate_runner_'+original['source_sha256']['tools/d1_list_candidate_tail_run.py']+'.py'))
    r.write(output/'registration_effective.json',reg)
    return reg['amendment']


class Budget(r.Budget):
    def consumption(self):
        learning=sum(bool(row['learning']) for row in self.rows)
        return dict(new_environment_starts=len(self.rows),new_learning_starts=learning,
            cumulative_environment_starts=self.reg['previous_cumulative_environment_starts']+len(self.rows),
            cumulative_learning_starts=self.reg['previous_cumulative_learning_starts']+learning,
            failed=sum(row['status']=='failed' for row in self.rows),device_commands=0,
            prior_design_spent_environments=1348,prior_design_spent_learning=404,
            new_environment_cap=CAP,new_learning_cap=LEARNING_CAP)

    def guard(self,learning=False):
        self.work_guard()
        counts=self.consumption()
        if len(self.rows)>=CAP or counts['cumulative_environment_starts']>=20000:raise TimeoutError('additional environment cap')
        if learning and (counts['new_learning_starts']>=LEARNING_CAP or counts['cumulative_learning_starts']>=6144):raise TimeoutError('additional learning cap')
        if sum(row['phase']==self.phase for row in self.rows)>=STAGE_CAPS[self.phase]:raise TimeoutError('registered stage cap')

    def call(self,identity,controller,case,*,learning=False):
        artifact=self.output/'items'/(identity+'.json.gz');statefile=self.output/'items'/(identity+'.pt')
        actor_hash=r.network_hash(controller)
        old=next((row for row in self.rows if row['identity']==identity),None)
        if old:
            if old['case']!=case or bool(old['learning'])!=learning or old['network_before_sha256']!=actor_hash:
                raise ValueError('consumed cache input/role/actor mismatch')
            if old['status']!='completed' or r.sha(artifact)!=old['artifact_sha256']:raise ValueError('consumed/invalid run ID')
            item=json.loads(gzip.decompress(artifact.read_bytes()))
            if isinstance(controller,c.Controller):
                if old['schema_id']!=controller.schema_id or r.sha(statefile)!=old['controller_sha256']:raise ValueError('variant/schema/controller artifact mismatch')
                saved=torch.load(statefile,map_location='cpu',weights_only=False)
                c.restore_controller(controller,saved['controller']);training.restore_rng(saved['rng_after'])
            return item
        self.guard(learning)
        requests=case['requests'] if case['family']=='gate' else r.external.old.workload(case['family'],case['seed'])
        row=dict(number=len(self.rows)+1,identity=identity,phase=self.phase,status='started',learning=learning,
            case=case,planned=len(requests),network_before_sha256=actor_hash,schema_id=getattr(controller,'schema_id',None))
        self.rows.append(row);self.append(row)
        frozen,initial_case=c.p.inputs(c.p.BUNDLE);initial=initial_case['initial']
        actual=c.p.profile(frozen,case['context'])
        vectors=dict(cells={key:[dict(source_request_id='common_measured_context_'+case['context'],durations_ns=values) for _ in range(4)] for key,values in actual.items()})
        if isinstance(controller,tail.TailController):controller.forecast_deadline=self.deadline
        try:
            began=time.perf_counter()
            result=r.engine.simulate(dict(protocol=c.p.VERSION,cells=c.p.profile(frozen)),vectors,requests,
                policy=controller.policy,settings=r.external.settings(),seed=201,decision_provider=controller)
            elapsed=time.perf_counter()-began
            _,costs,end=c.p.account(result,initial,frozen)
            ledger=result['ledger'];completed=sum(q['status']=='succeeded' for q in ledger);full=completed==len(requests)
            metrics=dict(planned=len(requests),completed=completed,incomplete=len(requests)-completed,
                urgent_failure=sum(q['priority']=='urgent' and ('response_ns' not in q or q['late_success']) for q in ledger),
                normal_failure=sum(q['priority']=='normal' and ('response_ns' not in q or q['late_success']) for q in ledger),
                urgent_p95_ms=result['metrics']['urgent_p95_ms'],normal_mean_ms=result['metrics']['normal_mean_ms'],
                energy_j=costs['whole_120s_j'] if full else None,peak_ap_c=max(costs['ap_path']) if full else None,
                native_seconds=elapsed,scheduled_requests=len(requests),
                normal_scheduled=sum(q['priority']=='normal' for q in ledger),urgent_scheduled=sum(q['priority']=='urgent' for q in ledger))
            item=dict(case=case,row=metrics,result=result,curve=list(zip(range(35,end+1),costs['ap_path'])))
            if isinstance(controller,c.Controller):
                snaps=controller.snapshots
                item['control']=dict(defer_seconds=controller.deferred_seconds,holds=controller.hold_counter,
                    fallbacks=controller.fallbacks,forced_waits=controller.forced_waits,pair_cancelled=controller.pair_cancelled,
                    selection_opportunities=controller.selection_opportunities,
                    action_counts={kind:sum(s['kinds'][s['chosen']]==kind for s in snaps) for kind in sorted({s['kinds'][s['chosen']] for s in snaps})},
                    decision_seconds=[s['decision_seconds'] for s in snaps],
                    physical_multi_decisions=sum(int(s.get('physical_mask',s['mask']).sum())>1 for s in snaps),
                    effective_multi_decisions=sum(int(s['mask'].sum())>1 for s in snaps),
                    chosen_nonL0=sum(s['chosen']!=s['base'] for s in snaps),
                    chosen_nonrule=sum(s['chosen']!=s.get('rule_reference',s['base']) for s in snaps))
            artifact.parent.mkdir(parents=True,exist_ok=True)
            artifact.write_bytes(gzip.compress(json.dumps(r.serial(item),allow_nan=False).encode()))
            if isinstance(controller,c.Controller):
                torch.save(dict(controller=c.controller_state(controller),rng_after=training.rng_state()),statefile)
                row['controller_sha256']=r.sha(statefile)
            row.update(status='completed',completed=completed,artifact_sha256=r.sha(artifact),seconds=elapsed)
            self.append(dict(event='completion',**row))
            r.write(self.output/'progress.json',dict(phase=self.phase,last=identity,consumption=self.consumption()))
            return item
        except BaseException as error:
            row.update(status='failed',error=repr(error));self.append(dict(event='failure',**row))
            r.write(self.output/'failures'/(identity+'.json'),dict(row=row,traceback=traceback.format_exc(),events=getattr(controller,'events',[])))
            raise


def deps(reg,variant):
    return training.dependency_manifest(dict(source_sha256=reg['source_sha256'],input_sha256=reg['input_sha256'],
        registration_sha256=c.digest(reg),variant=variant,reference_role='L0',schema=reg['schemas'][variant]))


def learner_type(variant):return tail.TailLearner if variant=='tail' else training.Learner


def gate(budget):
    frozen,initial,_=r.inputs();checks=[];opportunities=0;effective=0
    for i,case in enumerate(budget.reg['gate']):
        base=r.base_controller('L0',frozen,initial)
        baseline=budget.call(f'gate_L0_{i:02d}',base,case)
        for suffix in (0,1):
            controller=tail.TailController(frozen,initial,feature_variant='head2+C_next',forced_first=suffix,fixture_suffix=True)
            item=budget.call(f'gate_suffix_{suffix}_{i:02d}',controller,case)
            first=controller.snapshots[0];prediction=first['tail_forecasts'][first['chosen']]
            if not prediction['known']:raise ValueError('bounded gate forecast must be known')
            errors=[]
            for q in item['result']['ledger']:
                p=prediction['prediction'][q['id']]
                for key,actual in (('start',q['dispatch_ns']/1e9),('end',q['lane_available_ns']/1e9),
                                  ('response',(q['arrival_ns']+q['response_ns'])/1e9)):
                    errors.append(abs(p[key]-actual))
                if p['backend']!=q['backend']:raise ValueError('forecast backend differs from actualL0 suffix')
            if max(errors)>1.1e-9:raise ValueError('forecast dispatch/response/lane chronology differs')
            expected_J=initial['preload_power_w']*35+prediction['energy']
            if abs(expected_J-item['row']['energy_j'])>1e-8 or abs(prediction['peak_ap']-item['row']['peak_ap_c'])>1e-8:
                raise ValueError('forecast common-window cost differs from native mean accounting')
            checks.append(dict(case=i,first_variant=suffix,max_timing_error_s=max(errors),J_error=expected_J-item['row']['energy_j'],
                AP_error=prediction['peak_ap']-item['row']['peak_ap_c']))
        controller=tail.TailController(frozen,initial,feature_variant='head2+C_next')
        budget.call(f'gate_rule_{i:02d}',controller,case)
        for step in controller.snapshots:
            effective+=int(step['mask'].sum())>1
            b=step['tail_forecasts'][step['base']]
            opportunities+=sum(bool(step['mask'][j]) and j!=step['base'] and f['known'] and b['known']
                and (f['peak_ap']<b['peak_ap'] or f['energy']<b['energy']) for j,f in enumerate(step['tail_forecasts']))
        # Native L0 results are independent of the new forecasting implementation.
        if baseline['row']['completed']!=len(case['requests']):raise ValueError('baseline request loss')
    evidence=dict(status='PASS',chronology_checks=checks,effective_multi_decisions=effective,
        strict_predicted_opportunities=opportunities,learning_allowed=opportunities>0,
        scope='these declared gate states, not all schedules or actual improvement',consumption=budget.consumption())
    r.write(budget.output/'gate_verification.json',evidence);return evidence


def opportunity(budget):
    frozen,initial,_=r.inputs();strict=0;multi=0;examples=[]
    for i,case in enumerate(budget.reg['opportunity']):
        for role in ('L0','TailRule','suffix0','suffix1'):
            if role=='L0':controller=r.base_controller('L0',frozen,initial)
            else:controller=tail.TailController(frozen,initial,feature_variant='head2+C_next',
                forced_first=int(role[-1]) if role.startswith('suffix') else None,fixture_suffix=role.startswith('suffix'))
            budget.call(f'opportunity_{role}_{i:02d}',controller,case)
            if role=='L0':continue
            for step in controller.snapshots:
                multi+=int(step['mask'].sum())>1
                base=step['tail_forecasts'][step['base']]
                for j,f in enumerate(step['tail_forecasts']):
                    if (step['mask'][j] and j!=step['base'] and f['known'] and base['known']
                        and (f['peak_ap']<base['peak_ap'] or f['energy']<base['energy'])):
                        strict+=1
                        if len(examples)<8:examples.append(dict(case=case,role=role,at_ns=step['now_ns'],
                            action=step['kinds'][j],AP_difference=f['peak_ap']-base['peak_ap'],J_difference=f['energy']-base['energy']))
    result=dict(status='PASS',criterion_unchanged=True,strict_predicted_opportunities=strict,
        effective_multi_decisions=multi,learning_allowed=strict>0,examples=examples,
        scope='registered mixed-arrival development diagnostic; no independent confirmation or actual advantage',consumption=budget.consumption())
    r.write(budget.output/'opportunity_verification.json',result);return result


def reference(budget,label,index,case):
    frozen,initial,_=r.inputs();identity=f'{label}_L0_{index:03d}'
    item=budget.call(identity,r.base_controller('L0',frozen,initial),case)
    return item,r.sha(budget.output/'items'/(identity+'.json.gz'))


def observe(budget,learner,identity,case,ref,h,cursor):
    frozen,initial,_=r.inputs();controller=learner.fresh_controller(frozen,initial)
    item=budget.call(identity,controller,case,learning=True)
    learner.observe_episode(controller,item['row'],item['curve'],ref['row'],cursor=cursor,
        consumption=budget.consumption(),reference_hash=h,metadata=case)
    return item


def resume(budget):
    gate_record=budget.output/('opportunity_verification.json' if (budget.output/'opportunity_verification.json').exists() else 'gate_verification.json')
    if not r.read(gate_record)['learning_allowed']:raise ValueError('no demonstrated candidate opportunity')
    schema=budget.reg['schemas']['tail'];dependencies=deps(budget.reg,'tail')
    refs=[reference(budget,'fixture_ref',i,q) for i,q in enumerate(budget.reg['fixture'])]
    learner=tail.TailLearner(97,schema,dependencies)
    for i in range(12):
        ref,h=refs[i%8];observe(budget,learner,f'fixture_A_{i:02d}',budget.reg['fixture'][i%8],ref,h,dict(fixture_next=i+1));r.update(budget,learner)
    if not learner.optimizer.state or len(learner.pending_episodes)!=4:raise ValueError('nonempty Adam/partial4 required')
    archive=budget.output/'checkpoints/resume_fixture_partial.pt';learner.save(archive)
    branchA=[]
    for i in range(12,16):
        ref,h=refs[i%8];branchA.append(observe(budget,learner,f'fixture_A_{i:02d}',budget.reg['fixture'][i%8],ref,h,dict(fixture_next=i+1)));r.update(budget,learner)
    expected=copy.deepcopy(learner.snapshot())
    restored=tail.TailLearner.load(archive,expected_schema_id=schema,expected_dependencies=dependencies)
    branchB=[]
    for i in range(12,16):
        ref,h=refs[i%8];branchB.append(observe(budget,restored,f'fixture_B_{i:02d}',budget.reg['fixture'][i%8],ref,h,dict(fixture_next=i+1)));r.update(budget,restored)
    if training.state_digest(r.stable(expected))!=training.state_digest(r.stable(restored.snapshot())):
        raise ValueError('tail learner additional-update resume mismatch')
    if training.state_digest(r.stable(branchA))!=training.state_digest(r.stable(branchB)):raise ValueError('resumed native trajectories differ')
    evidence=dict(status='PASS',learning=20,environments=28,partial_episodes=4,Adam_nonempty=True,
        exact=['network','Adam','multipliers','RNG','pending','cursor','losses','gradients','public-controller-state','next-rollouts'],
        actual_optimizer_steps=expected['optimizer_steps']+restored.optimizer_steps-r.read_optimizer_count(archive),
        global_budget_restored=False,scope='completed episode/update boundary; host time/outer budget excluded',consumption=budget.consumption())
    r.write(budget.output/'resume_verification.json',evidence);return evidence


def train(budget,target):
    if not r.read(budget.output/'resume_verification.json')['status']=='PASS':raise ValueError('resume gate incomplete')
    if target==64 and not r.read(budget.output/'extension_decision.json')['extend_all_six']:raise ValueError('extension blocked')
    # References were completed in their own bounded stage.
    refs=[]
    for i,q in enumerate(budget.reg['train']):
        p=budget.output/'items'/f'train_ref_L0_{i:03d}.json.gz'
        refs.append((json.loads(gzip.decompress(p.read_bytes())),r.sha(p)))
    for variant in VARIANTS:
        dependencies=deps(budget.reg,variant);schema=budget.reg['schemas'][variant];cls=learner_type(variant)
        for seed in r.SEEDS:
            checkpoint=budget.output/f'checkpoints/{variant}_seed{seed}_last.pt'
            learner=cls.load(checkpoint,expected_schema_id=schema,expected_dependencies=dependencies) if checkpoint.exists() else cls(seed,schema,dependencies)
            if learner.accepted_episodes>target:raise ValueError('cannot overwrite previous terminal')
            if learner.accepted_episodes and learner.cursor!=dict(variant=variant,seed=seed,next_episode=learner.accepted_episodes):raise ValueError('learner cursor changed')
            r.update(budget,learner)
            while learner.accepted_episodes<target:
                i=learner.accepted_episodes;q=budget.reg['train'][i%64];ref,h=refs[i%64]
                observe(budget,learner,f'train_{variant}_s{seed}_{i:03d}',q,ref,h,dict(variant=variant,seed=seed,next_episode=i+1))
                learner.save(checkpoint);r.update(budget,learner);learner.save(checkpoint)
                if (i+1)%8==0:
                    r.write(budget.output/f'learner_{variant}_seed{seed}.json',dict(variant=variant,seed=seed,episodes=learner.accepted_episodes,
                        updates=learner.update_count,optimizer_steps=learner.optimizer_steps,logs=learner.logs,episode_logs=learner.episode_logs))
                    print(json.dumps(dict(stage=budget.phase,variant=variant,seed=seed,episodes=learner.accepted_episodes,consumption=budget.consumption())),flush=True)
            learner.save(budget.output/f'checkpoints/{variant}_seed{seed}_terminal{target}.pt')
    return dict(status='completed',episodes_per_learner=target,learners=6,consumption=budget.consumption())


def evaluate(budget,label,target):
    frozen,initial,_=r.inputs();cases=budget.reg['confirmation' if label=='confirmation' else 'development'];rows=[]
    if label!='main_development':
        for role in ('L0','Band','Triton','TailRule'):
            for i,q in enumerate(cases):
                controller=tail.TailController(frozen,initial,feature_variant='head2+C_next') if role=='TailRule' else r.base_controller(role,frozen,initial)
                identity=f'{label}_{role}_{i:03d}';item=budget.call(identity,controller,q)
                rows.append(dict(identity=identity,condition=i,case=q,policy=role,seed=None,training_episodes=0,**item['row'],control=item.get('control')))
    else:rows=[copy.deepcopy(q) for q in r.read(budget.output/'pilot_development_results.json')['rows'] if q['seed'] is None]
    for variant in VARIANTS:
        cls=learner_type(variant)
        for seed in r.SEEDS:
            archive=budget.output/f'checkpoints/{variant}_seed{seed}_terminal{target}.pt'
            learner=cls.load(archive,expected_schema_id=budget.reg['schemas'][variant],expected_dependencies=deps(budget.reg,variant))
            before=training.state_digest(learner.network.state_dict())
            for i,q in enumerate(cases):
                controller=learner.fresh_controller(frozen,initial);controller.deterministic=True
                identity=f'{label}_{variant}_s{seed}_{i:03d}';item=budget.call(identity,controller,q)
                rows.append(dict(identity=identity,condition=i,case=q,policy=variant+'PPO',seed=seed,training_episodes=target,**item['row'],control=item.get('control')))
            if training.state_digest(learner.network.state_dict())!=before:raise ValueError('evaluation updated actor')
    gates={policy:report.gate(rows,policy,len(cases)) for policy in ('TailRule','currentPPO','tailPPO')}
    for policy,g in gates.items():g['learners']=1 if policy=='TailRule' else 3
    result=dict(status='completed',rows=rows,gates=gates,consumption=budget.consumption(),fixed_terminal_episodes=target)
    r.write(budget.output/(label+'_results.json'),result)
    if label=='pilot_development':
        logs=[r.read(budget.output/f'learner_{v}_seed{s}.json') for v in VARIANTS for s in r.SEEDS]
        tail_rows=[row for row in rows if row['policy']=='tailPPO']
        valid=all(log['episodes']==32 and log['updates']==4 for log in logs)
        meaningful=sum((row.get('control') or {}).get('effective_multi_decisions',0) for row in tail_rows)>0
        sampled_nonbase=sum(log['sampled_choices'] for summary in logs if summary['variant']=='tail' for log in summary['episode_logs'])>0
        decision=dict(review_complete=True,extend_all_six=valid and meaningful and sampled_nonbase,
            exact_rule=budget.reg['extension_rule'],valid_all_six=valid,tail_multi_decisions=meaningful,
            tail_on_policy_actor_samples=sampled_nonbase,development_promising=gates['tailPPO']['promising'],
            improvement_assumed=False,best_seed_selection=False,success_gate_relaxed=False)
        r.write(budget.output/'extension_decision.json',decision)
    return dict(status='completed',rows=len(rows),gates={k:{a:v for a,v in g.items() if a!='differences'} for k,g in gates.items()},consumption=budget.consumption())


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    p.add_argument('--phase',required=True,choices=('register','amend_opportunity',*STAGE_CAPS));a=p.parse_args()
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    if a.phase=='register':
        reg=register(a.output);print(json.dumps({k:v for k,v in reg.items() if k not in ('source_sha256','input_sha256','train','development','confirmation','fixture','gate')},ensure_ascii=False,indent=2));return
    if a.phase=='amend_opportunity':print(json.dumps(amend_opportunity(a.output),ensure_ascii=False,indent=2));return
    completed=a.output/(a.phase+'_completion.json')
    if completed.exists():raise FileExistsError('completed stage is immutable; no reset/rerun')
    owner=a.output/'owner.lock'
    with owner.open('x',encoding='ascii') as stream:stream.write(str(os.getpid()))
    budget=None
    try:
        budget=Budget(a.output,a.phase)
        if a.phase=='gate':result=gate(budget)
        elif a.phase=='opportunity':result=opportunity(budget)
        elif a.phase=='resume':result=resume(budget)
        elif a.phase=='references':
            if not r.read(a.output/'resume_verification.json')['status']=='PASS':raise ValueError('resume gate missing')
            for i,q in enumerate(budget.reg['train']):reference(budget,'train_ref',i,q)
            result=dict(status='completed',consumption=budget.consumption())
        elif a.phase in ('pilot','main'):result=train(budget,32 if a.phase=='pilot' else 64)
        else:result=evaluate(budget,a.phase,32 if a.phase=='pilot_development' else 64)
        r.write(completed,result);print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    except BaseException as error:
        r.write(a.output/(a.phase+'_error.json'),dict(status='stopped_error',error=repr(error),
            consumption=budget.consumption() if budget else None));raise
    finally:
        if owner.exists() and owner.read_text(encoding='ascii')==str(os.getpid()):owner.unlink()

if __name__=='__main__':main()
