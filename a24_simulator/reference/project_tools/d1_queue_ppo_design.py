"""PC-only feasibility certificates and immutable v1 readout; no simulation.

A violated mandatory detector CPU demand bound proves infeasibility only in
the frozen deterministic context. Passing it is not a feasibility certificate.
An independent fixed-split construction supplies the positive witness.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import html
import json
import math
from pathlib import Path
import statistics

from tools import d1_empirical_request_policy as p
from tools import d1_request_rl as workload

VERSION = 'request-ppo-feasibility-design-v2'
BUNDLE = p.ROOT / 'docs/results/request_ppo_01/queue_design_v2'
PLAN = BUNDLE / 'training_plan.json'
BASELINES = ['CPU_REFERENCE', 'SPLIT_REFERENCE', 'EFT_REFERENCE', 'SHARED_EDF', 'SHARED_EFT']
EPS = 1e-9  # numeric equality, never an accuracy/physical margin


def specification():
    learners, updates, batch = 6, 128, 8
    train, validation, test = 1024, 24, 192
    counts = dict(training=learners*updates*batch, validation=learners*5*validation,
                  test=(learners+len(BASELINES)-1)*test, reference=train+validation+test, smoke=0)
    return dict(version=VERSION, status='PC_READY_NOT_RUN', source_head='435aa2533fc2704eb6a3c014f400a12afcffeea8',
        experiment_ready=False, device_commands=0, independent_device_validation=False,
        retrospective_design=True, algorithm='masked_PPO_Lagrange', variants=['HEAD','QUEUE'], learning_seeds=[11,23,37],
        deadlines_ns=dict(classification_output_ready=1500000000,detection_persist_complete=6000000000),
        windows_s=dict(energy=[0,120],ap=[35,180],all_lane_release_by=120),
        support=dict(cells=list(p.CELLS),pair='classification_GPU+detection_CPU',preemption=False,
            precision_change=False,thermal_latency_feedback=False,controller_device_energy_unknown=True),
        actions=dict(request_slots=8,outputs=17,max_wait_s=.25,
            guard='v1_aging_WAIT_plus_same_request_known_late_backend_when_immediate_on_time_alternative_exists'),
        network=dict(observations=85,hidden=[64,64],actor_outputs=17,value_outputs=5),
        objective=dict(energy_reward='-whole_0_120s_J/10',
            costs=['urgent_absolute_failure_fraction','normal_absolute_failure_fraction',
                   'positive_part(AP_area-shared_EFT_area)/100','positive_part(AP_peak-shared_EFT_peak)'],
            targets=[0,0,0,0],thermal_attribution='terminal_positive_violation_no_cross_case_cancellation',
            multipliers_initial=[10,10,1,1],multiplier_step=5.,multiplier_bounds=[0,100],
            claim='expected_nonnegative_zero_cost_is_not_finite_training_or_unseen_case_guarantee'),
        numeric_equality_tolerance=dict(J=EPS,C=EPS,Cs=EPS,accuracy_margin=False),
        optimizer=dict(name='Adam',lr=.0003,epsilon=1e-5,epochs=4,minibatch=256,clip=.2,entropy=.01,
            value_coefficient=.5,gradient_clip=.5,target_kl=.03,gamma=1.,gae_lambda=.95),
        data=dict(train_seed_range=[610700000,610700511],validation_seed_range=[610710001,610710004],
            test_seed_range=[610720001,610720016],primary_families=['low','sustained'],stress_families=['queue','burst'],
            contexts=list(workload.SCENARIOS),train_order='seed=start+i//2; family=i%2; context=(i//2+i%2)%3',
            witness='fixed_split_FIFO_GPU_classification_CPU_detection_using_frozen_context',
            main_admission='all_train_and_validation_cases_require_feasible_witness',
            stress_use='final_test_only_not_training_or_selection',unknown_use='block_main_and_record_separately',
            input_choice='existing_generator_and_capacity_rule_not_policy_J_AP_results',
            old_seen_test='v1_is_retrospective_development_evidence_never_v2_holdout',
            initial_conditions='one_unchanged_preload_history',new_physical_holdout=False),
        baselines=BASELINES,thermal_reference='SHARED_EFT',
        selection=dict(order=['incomplete','absolute_service_violation_cases','service_fraction_sum',
            'positive_thermal_violation_cases','positive_scaled_thermal_sum','mean_J','urgent_P95','normal_mean','earlier_update'],
            validation='primary_only_per_case_nonworsening',freeze_all_six_before_test=True,
            test_action='deterministic_masked_argmax',best_test_seed_selection=False,
            ineligible_actor='diagnostic_only_never_adoption',
            joint_nonworsening='J_peak_area_all_nonworse_and_one_lower_full_work_zero_service_failures',
            strict_joint='J_peak_area_all_lower_full_work_zero_service_failures',
            accuracy_pass=None,policy_winner=None,automatic_default_promotion=False),
        budget=dict(updates_per_learner=updates,batch=batch,validation_updates=[0,32,64,96,128],
            counts=counts,formal_simulations=sum(counts.values()),test_table_rows=test*(learners+len(BASELINES)),
            primary_test_cases=96,stress_test_cases=96,preflight_witnesses=train+validation+test,
            active_limit_s=5400,receipt_reserve_s=120,checkpoint='every_completed_durable_unit',
            fixture_simulations_max=40,retries=0,additional_training=0,additional_algorithm=0,
            fixture_budget_scope='each_frozen_verification_pass_not_policy_search',
            expected_time_note='v1_active5770.077s*10024/17936_linear_reference_not_guarantee'),
        frozen_files={str(x.relative_to(p.ROOT)).replace('\\','/'):sha for x,sha in
            [(p.BUNDLE/'model.json',p.MODEL_SHA),(p.BUNDLE/'initial_inputs.json',p.INITIAL_SHA)]},
        run_output='output/queue_ppo_feasible_v2',
        limitations=['conditional_current_model_only','same_workload_family_confounds_count_mix_interval',
            'three_service_contexts_not_three_independent_phone_sessions','no_policy_device_overhead_measurement',
            'finite_AP_window_not_total_physical_heat','no_thermal_service_feedback'])


def cases(plan):
    data=plan['data']; families=data['primary_families']; contexts=data['contexts']
    start,end=data['train_seed_range']; train=[]
    for i in range((end-start+1)*len(families)):
        train.append((start+i//len(families),families[i%len(families)],contexts[(i//len(families)+i%len(families))%len(contexts)]))
    def cross(key,fams):
        a,b=data[key]
        return [(s,f,c) for s in range(a,b+1) for f in fams for c in contexts]
    return train,cross('validation_seed_range',families),cross('test_seed_range',list(workload.FAMILIES))


def validate_tickets(tickets):
    if not tickets or len({q['id'] for q in tickets})!=len(tickets): raise ValueError('empty/duplicate requests')
    for q in tickets:
        p.backends(q)
        if type(q['arrival_ns']) is not int or not 35e9<=q['arrival_ns']<120e9:
            raise ValueError('invalid arrival boundary')
        expected=1500000000 if q['priority']=='urgent' else 6000000000
        if q['deadline_offset_ns']!=expected: raise ValueError('deadline contract')


def validate_witness(tickets, jobs):
    """Validate all service and actual lane endpoints, not response alone."""
    by={q['id']:q for q in tickets}
    if len(jobs)!=len(tickets) or {j['id'] for j in jobs}!=set(by): raise ValueError('witness denominator')
    misses=0; minimum=math.inf
    for j in jobs:
        q=by[j['id']]; p.backends(q)
        if j['backend'] not in p.backends(q) or not q['arrival_ns']<=j['dispatch_ns']<=j['response_ns']<=j['lane_available_ns']:
            raise ValueError('unsupported path/time order')
        if not all(math.isfinite(j[k]) for k in ('dispatch_ns','response_ns','lane_available_ns')):
            raise ValueError('nonfinite witness')
        slack=(q['arrival_ns']+q['deadline_offset_ns']-j['response_ns'])/1e9
        misses+=slack < -EPS; minimum=min(minimum,slack)
    events=[]
    for j in jobs:
        events.extend([(j['dispatch_ns'],1,j),(j['lane_available_ns'],0,j)])
    active={}
    for _,kind,j in sorted(events,key=lambda x:(x[0],x[1])):
        if kind==0: active.pop(j['backend'],None)
        else:
            if j['backend'] in active: raise ValueError('lane overlap before release')
            active[j['backend']]=by[j['id']]['task']+'_'+j['backend']
            p.state(list(active.values()))
    return dict(service_misses=int(misses),minimum_slack_s=minimum,
                all_lane_release_by_120=all(j['lane_available_ns']<=120e9 for j in jobs))


def classify(tickets, frozen, context):
    validate_tickets(tickets); profile=p.profile(frozen,context)
    normal=[q for q in tickets if q['task']=='detection']
    # Conservative necessary bound: omit classification CPU work and lane tail.
    demand=len(normal)*sum(profile['detection_CPU_normal'][:3])/1e9
    width=(max(q['arrival_ns']+q['deadline_offset_ns'] for q in normal)-min(q['arrival_ns'] for q in normal))/1e9 if normal else 0.
    base=dict(cpu_response_demand_s=demand,cpu_deadline_window_s=width,context=context,
              physical_capacity_certified=False,bound_scope='all_detector_release_deadline_span_no_tail')
    if demand>width+EPS:
        return dict(base,status='overload_proved',reason='mandatory_detector_CPU_demand_exceeds_window',witness=None)
    ready={'CPU':0.,'GPU':0.}; jobs=[]
    for q in sorted(tickets,key=lambda x:(x['arrival_ns'],x['ordinal'])):
        backend='GPU' if q['task']=='classification' else 'CPU'
        d=profile[p.key(q,backend)]; start=max(q['arrival_ns'],ready[backend])
        end=start+sum(d); response=start+sum(d[:2 if q['priority']=='urgent' else 3])
        jobs.append(dict(id=q['id'],backend=backend,dispatch_ns=start,response_ns=response,lane_available_ns=end))
        ready[backend]=end
    witness=validate_witness(tickets,jobs)
    feasible=witness['service_misses']==0 and witness['all_lane_release_by_120']
    return dict(base,status='feasible_witness' if feasible else 'unknown',
        reason='fixed_split_witness_valid' if feasible else 'bound_pass_but_constructed_witness_fails',
        witness=witness,witness_sha256=digest_value(jobs))


def digest_value(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def preflight(plan, frozen):
    groups=cases(plan); records=[]; split_hashes=[]
    for split,group in zip(('train','validation','test'),groups):
        traces={}
        for seed,family,context in group:
            if (seed,family) not in traces:
                tickets=workload.workload(family,seed)
                # Exclude request IDs/seed: detect equivalent physical inputs too.
                sha=digest_value([{k:q[k] for k in ('task','priority','arrival_ns','deadline_offset_ns')} for q in tickets])
                traces[(seed,family)]=(tickets,sha)
            tickets,sha=traces[(seed,family)]; cert=classify(tickets,frozen,context)
            if split!='test' and cert['status']!='feasible_witness':
                raise ValueError(f'primary admission blocked: {split}/{seed}/{family}/{context}/{cert["status"]}')
            if split=='test' and family in plan['data']['primary_families'] and cert['status']!='feasible_witness':
                raise ValueError('primary test input lacks feasible witness')
            if split=='test' and family in plan['data']['stress_families'] and cert['status']!='overload_proved':
                raise ValueError('registered stress class changed; do not silently replace')
            records.append(dict(split=split,seed=seed,family=family,input_sha256=sha,**cert))
        split_hashes.append({sha for _,sha in traces.values()})
    if any(split_hashes[i]&split_hashes[j] for i in range(3) for j in range(i)):
        raise ValueError('same physical trace across splits')
    return dict(version=VERSION,input_and_certificate_sha256=digest_value(records),
        counts={s:{v:sum(r['split']==s and r['status']==v for r in records)
                   for v in ('feasible_witness','overload_proved','unknown')} for s in ('train','validation','test')},
        minimum_primary_witness_slack_s=min(r['witness']['minimum_slack_s'] for r in records if r['status']=='feasible_witness'),
        device_commands=0,policy_simulations=0,records=records)


def idle_with_backlog(ledger):
    """Observed interval, not a reconstructed WAIT decision or causal effect."""
    cuts=sorted({r[k]/1e9 for r in ledger for k in ('arrival_ns','dispatch_ns','lane_available_ns')})
    intervals=[]
    for a,b in zip(cuts,cuts[1:]):
        mid=(a+b)/2
        queued=[r for r in ledger if r['arrival_ns']/1e9<=mid<r['dispatch_ns']/1e9]
        active=[r for r in ledger if r['dispatch_ns']/1e9<=mid<r['lane_available_ns']/1e9]
        if queued and not active:
            item=dict(start_s=a,end_s=b,queued=len(queued),observed='all_lanes_idle_with_arrived_pending_work',
                      decision_reason=None,causal_WAIT_effect=None)
            if intervals and intervals[-1]['end_s']==a and intervals[-1]['queued']==len(queued): intervals[-1]['end_s']=b
            else: intervals.append(item)
    return intervals


def legacy_readout(root):
    root=Path(root); paths=[root/n for n in ('test.csv','paired_differences.csv','freeze_before_test.json','test_ledgers.jsonl','summary.json','progress.json')]
    latest=json.loads((root/'LATEST_RECEIPT.json').read_text(encoding='utf8')); receipt_path=root/latest['file']
    receipt=json.loads(receipt_path.read_text(encoding='utf8')); paths.extend([root/'LATEST_RECEIPT.json',receipt_path])
    if receipt['status']!='completed': raise ValueError('legacy run not complete')
    with (root/'test.csv').open(encoding='utf8',newline='') as f: rows=list(csv.DictReader(f))
    if len(rows)!=2112: raise ValueError('legacy full denominator')
    references={(r['trace_seed'],r['family'],r['context']):r for r in rows if r['policy']=='SHARED_EFT'}
    aggregates=[]
    for policy in sorted({r['policy'] for r in rows}):
        for family in workload.FAMILIES:
            group=[r for r in rows if r['policy']==policy and r['family']==family]
            full=[r for r in group if r['equal_work']=='True' and int(r['urgent_service_failure'])==int(r['normal_service_failure'])==0]
            deltas=[]; strict=joint=0
            for r in full:
                ref=references[(r['trace_seed'],r['family'],r['context'])]
                if int(ref['urgent_service_failure'])+int(ref['normal_service_failure']): continue
                ds=[float(r[k])-float(ref[k]) for k in ('energy_j','peak_ap_c','thermal_degree_seconds')]
                deltas.append(ds); strict+=all(d < -EPS for d in ds)
                joint+=all(d <= EPS for d in ds) and any(d < -EPS for d in ds)
            waits=sum(json.loads(r['actions'])[16] for r in group if r['actions'])
            aggregates.append(dict(policy=policy,family=family,cases=len(group),service_success_cases=len(full),
                planned_requests=sum(int(r['planned']) for r in group),completed_requests=sum(int(r['completed']) for r in group),
                urgent_failures=sum(int(r['urgent_service_failure']) for r in group),normal_failures=sum(int(r['normal_service_failure']) for r in group),
                WAIT_actions=waits,eligible_paired_cases=len(deltas),strict_joint=strict,joint_nonworsening=int(joint),
                mean_delta_J=statistics.mean(d[0] for d in deltas) if deltas else None,
                mean_delta_peak_C=statistics.mean(d[1] for d in deltas) if deltas else None,
                mean_delta_area_Cs=statistics.mean(d[2] for d in deltas) if deltas else None,
                mean_scope='policy_specific_eligible_subset_not_global_ranking'))
    representatives=[]; idle=[]; chosen=set()
    for line in (root/'test_ledgers.jsonl').open(encoding='utf8'):
        item=json.loads(line); seed,family,context=item['case']; policy=item['policy']
        if not policy.startswith(('HEAD_','QUEUE_')): continue
        ledger=item['ledger']; failures=[r for r in ledger if r['response_ns']>r['deadline_offset_ns'] or r['status']!='succeeded']
        key=(policy,family)
        if not failures or key in chosen: continue
        chosen.add(key); first=min(failures,key=lambda r:r['arrival_ns']+r['deadline_offset_ns']); gaps=idle_with_backlog(ledger)
        representatives.append(dict(policy=policy,trace_seed=seed,family=family,context=context,
            first_failure_ordinal=first['ordinal'],task=first['task'],arrival_s=first['arrival_ns']/1e9,
            deadline_s=(first['arrival_ns']+first['deadline_offset_ns'])/1e9,dispatch_s=first['dispatch_ns']/1e9,
            response_s=(first['arrival_ns']+first['response_ns'])/1e9,lateness_s=(first['response_ns']-first['deadline_offset_ns'])/1e9,
            idle_backlog_s=sum(g['end_s']-g['start_s'] for g in gaps),
            decision_snapshot_available=False,selection_rule='first_stored_failure_per_actor_family',cause='unidentified_no_decision_journal'))
        idle.extend(dict(policy=policy,trace_seed=seed,family=family,context=context,**g) for g in gaps)
    # Verify witness/capacity classification on existing inputs, no engine replay.
    frozen=json.loads((p.BUNDLE/'model.json').read_text()); bounds=[]
    for seed,family,context in references:
        cert=classify(workload.workload(family,int(seed)),frozen,context)
        bounds.append(dict(trace_seed=int(seed),family=family,**cert))
    return dict(version=VERSION,retrospective=True,original_result_relabelled=False,
        receipt=receipt,source_sha256={x.name:p.digest(x) for x in paths},
        selected=json.loads((root/'freeze_before_test.json').read_text())['selected'],
        aggregates=aggregates,representatives=representatives,idle_intervals=idle,bounds=bounds,
        interpretation='WAIT counts and idle backlog are descriptive; decision-time queues/guard reasons were not saved',
        device_commands=0,new_policy_simulations=0)


def save_csv(path, rows):
    if not rows: raise ValueError('empty table is not successful evidence')
    with Path(path).open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def render_readout(evidence):
    rows=evidence['aggregates']; esc=html.escape
    table=''.join('<tr>'+''.join(f'<td>{esc(str(r[k]))}</td>' for k in ('policy','family','cases','service_success_cases','WAIT_actions','joint_nonworsening'))+'</tr>' for r in rows)
    return '<!doctype html><meta charset="utf-8"><title>PPO v1 판독 / v2 준비</title><style>body{font:16px sans-serif;max-width:1100px;margin:30px auto}td,th{border:1px solid #ccc;padding:7px}table{border-collapse:collapse}</style><h1>완료된 PPO v1 판독과 v2 준비</h1><p>사후 분석. 새 학습·실측 결과 아님. 기존6actor 채택 부적격 보존. WAIT 원인 snapshot 부재로 인과 미확정.</p><p>주 평가: feasible low/sustained. queue/burst: 과부하 스트레스. 기한1.5/6초·J0–120초·AP35–180초 유지. 모형 내부 비교이며 실기기 절감·strict 확대 아님.</p><table><tr><th>정책</th><th>입력</th><th>조건</th><th>전량 기한 성공</th><th>WAIT 횟수</th><th>공동 비악화</th></tr>'+table+'</table><p>48조건=16합성도착×3동결문맥, 독립실기기48회 아님. 부분 적격 평균으로 전체 정책 순위를 정하지 않음.</p><p><a href="README.md">계약·예산·실행 안내</a> · <a href="legacy_policy_family.csv">전체 분모 CSV</a> · <a href="legacy_first_failures.csv">첫 실패</a> · <a href="legacy_idle_backlog.csv">관측 대기·유휴 구간</a></p>'


def prepare(root):
    BUNDLE.mkdir(parents=True,exist_ok=True)
    for name in ('training_plan.json','preflight.json','legacy_readout.json'):
        if (BUNDLE/name).exists(): raise ValueError('existing design evidence; no overwrite: '+name)
    plan=specification(); frozen,_=p.inputs(p.BUNDLE)
    manifest=preflight(plan,frozen); evidence=legacy_readout(root)
    p.write(PLAN,plan); p.write(BUNDLE/'preflight.json',manifest)
    p.write(BUNDLE/'legacy_readout.json',{k:v for k,v in evidence.items() if k not in ('idle_intervals','bounds')})
    save_csv(BUNDLE/'legacy_policy_family.csv',evidence['aggregates'])
    save_csv(BUNDLE/'legacy_first_failures.csv',evidence['representatives'])
    save_csv(BUNDLE/'legacy_idle_backlog.csv',evidence['idle_intervals'])
    save_csv(BUNDLE/'legacy_capacity.csv',[{k:v for k,v in r.items() if k!='witness'} for r in evidence['bounds']])
    (BUNDLE/'index.html').write_text(render_readout(evidence),encoding='utf8')
    print(json.dumps(dict(plan_sha256=p.digest(PLAN),preflight_counts=manifest['counts'],budget=plan['budget'],
                         legacy_aggregates=len(evidence['aggregates']),device_commands=0),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-root',required=True)
    args=parser.parse_args(); prepare(args.legacy_root)
