"""Saved-only integration of audited A24 simulation and fixed-rule phone8.

SOURCE PREPARATION ONLY until a parent REPORT_OPERATION_REGISTERED.json pins
this source, both completed evidence lineages, and the exact finalizer HTML.
No environment, model/NN/CostState import, fit, reselection, or phone commands.
The integrator opens saved comparison reports, never measured request/AP ZIPs.

Operation schema A24-integrated-saved-report-operation-v1:
  operator_sha256, allow_execution=true, allow_replace_html=true,
  html_target, existing_html_sha256, pins={absolute_file_path:sha256},
  finalizer_operation_path (optional; default O/FINALIZER_OPERATION_REGISTERED),
  latest_live_metadata_path (required and pinned; exact historical snapshot).
Required pin paths are returned by --required-paths (stdlib, no output files).
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import hashlib
import html
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import time

B=Path('C:/Users/chomg/Documents/Codex/2026-10-11/dkfo')
W=B/'work/A24-INTEGRATED-SIM-20261016-G002'
O=B/'outputs/A24-INTEGRATED-SIM-20261016-G002'
PREDECESSOR_O=B/'outputs/A24-INTEGRATED-SIM-20261016'
PREDECESSOR_FAILURE_SOURCE=PREDECESSOR_O/'G001_FAILURE_FRONTIER_AND_RECOVERY_DECISION_20261016_0522.json'
PREDECESSOR_FAILED_IDENTITY='4d70abfdf8f0ede2496d7efbeab7'
PREDECESSOR_RECEIPTS_SHA256='47911bae289aaee5c8bc465f1877a4b5d715d4d131d0c1e67789c83bcb35a5cf'
P=O/'new_confirmation_predictions'
C=O/'new_confirmation_comparison'
R=O/'REPORT_SUPPLEMENT'
TARGET=Path('C:/Users/chomg/Documents/ChatGPT/산공회/A24_에너지열_시뮬레이터.html')
OLD_PLAN=B/'outputs/A24-DEV8-TIMING-20261015/CONFIRM_RECIPES.json'
SCHEMA='A24-integrated-saved-report-operation-v1'
P0_EP000_SHA256='f233bc74cc2476637e2fd80dacf10bc2040e005cc47bafb2aa1de667b39c3988'


def require(ok,message):
    if not ok:raise ValueError(message)


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):h.update(block)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def lines(path):return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]


def key(path):return str(Path(path).resolve()).casefold()


def write(path,value):
    path=Path(path);require(not path.exists(),'Immutable report artifact already exists: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    data=value if isinstance(value,bytes) else canonical(value)
    temp=path.with_name(path.name+'.part')
    with temp.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)


def required_paths(finalizer_operation=None,latest_live=None):
    fixed=[W/'finalize_a24.py',O/'FINAL_AUDIT.json',O/'COMPLETION_RECEIPT.json',
           O/'VIEW_DATA.json',O/'RESULTS_KO.json',O/'ALL_CASES.csv',O/'EFFECTS_AND_COMPARISONS.json',
           O/'REGISTRATION.json',O/'SEALED_PLAN.json',O/'DEV_SELECTION_FREEZE.json',
           O/'P0_INIT_COPY_REGISTERED.json',O/'PREDECESSOR_FAILURE_PROOF.json',
           PREDECESSOR_FAILURE_SOURCE,PREDECESSOR_O/'receipts.jsonl',PREDECESSOR_O/'checkpoints/P0_EP000.pt',
           W/'predict_confirmation.py',O/'NEW_CONFIRM_OPERATION_REGISTERED.json',
           P/'PREDICTIONS_FROZEN.json',P/'PREDICTION_EXECUTION_PLAN.json',
           W/'observed_comparison.py',O/'NEW_CONFIRM_COMPARISON_OPERATION_REGISTERED.json',
           C/'OBSERVED_COMPARISON.json',C/'OBSERVED_ACCESS_STARTED.json',C/'access_receipts.jsonl',
           C/'ALGORITHM_SPEC.json',OLD_PLAN]
    fixed.append(Path(finalizer_operation) if finalizer_operation else O/'FINALIZER_OPERATION_REGISTERED.json')
    if latest_live:fixed.append(Path(latest_live))
    return fixed


def validate_operation(path):
    op=read(path)
    require(op.get('schema')==SCHEMA and op.get('allow_execution') is True,'Saved report execution is not registered')
    require(op.get('operator_sha256')==sha(__file__),'Report source SHA not registered')
    require(op.get('allow_replace_html') is True,'Finalizer HTML replacement not registered')
    require(key(op['html_target'])==key(TARGET),'Unexpected report HTML target')
    require(op.get('latest_live_metadata_path'),'Exact latest LIVE metadata snapshot pin required')
    pins={key(p):h for p,h in op['pins'].items()}
    require(len(pins)==len(op['pins']),'Duplicate case-normalized report pin')
    for p in required_paths(op.get('finalizer_operation_path'),op['latest_live_metadata_path']):
        require(key(p) in pins,'Required source/artifact pin missing: '+str(p))
    for p,h in op['pins'].items():require(sha(p)==h,'Report source/evidence SHA changed: '+p)
    require(TARGET.exists() and sha(TARGET)==op['existing_html_sha256'],'Existing page is not the pinned finalizer-generated HTML')
    return op,pins


def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def fmt(value,digits=3):
    return format(value,'.'+str(digits)+'f') if finite(value) else '미판정'


def observed_csv(sessions):
    stream=io.StringIO(newline='')
    header=['session_id','label','forecast_identity','source_archive_sha256','planned','model',
            'response_residual_n','response_residual_bias_ms','response_residual_MAE_ms','response_residual_RMSE_ms',
            'AVAILABLE_residual_n','AVAILABLE_residual_bias_ms','AVAILABLE_residual_MAE_ms',
            'AP_window_qualified','AP_coverage_reasons','observed_AP35_180_reported_step_mean_c',
            'observed_AP35_180_reported_step_peak_c','observed_AP180_reported_c',
            'predicted_AP35_180_mean_c','prediction_minus_observed_APmean_c',
            'prediction_minus_observed_reported_peak_c','prediction_minus_observed_AP180_c',
            'predicted_J0_180_conditional','measured_J','energy_prediction_error']
    for co in ('ALL','U','N'):
        header.extend(co+'_'+f for f in ('planned','responded','available','deadline_met','service_success','failed','incomplete','missing_observed_records','invalid_records','response_p95_ns'))
    writer=csv.DictWriter(stream,fieldnames=header);writer.writeheader()
    for s in sessions:
        for model in ('TREND27','MEASURED35'):
            a=s['observed_AP'];m=s['models'][model];p=m['prediction'];d=m['prediction_minus_observed']
            row={k:s[k] for k in ('session_id','label','forecast_identity','source_archive_sha256','planned')}
            row.update(model=model,response_residual_n=s['response_latency_errors_ms']['n'],
                response_residual_bias_ms=s['response_latency_errors_ms']['bias'],response_residual_MAE_ms=s['response_latency_errors_ms']['MAE'],response_residual_RMSE_ms=s['response_latency_errors_ms']['RMSE'],
                AVAILABLE_residual_n=s['AVAILABLE_time_errors_ms']['n'],AVAILABLE_residual_bias_ms=s['AVAILABLE_time_errors_ms']['bias'],AVAILABLE_residual_MAE_ms=s['AVAILABLE_time_errors_ms']['MAE'],
                AP_window_qualified=a['qualified'],AP_coverage_reasons=json.dumps(a['reasons'],ensure_ascii=False),
                observed_AP35_180_reported_step_mean_c=a['AP35_180_reported_step_mean_c'],observed_AP35_180_reported_step_peak_c=a['AP35_180_reported_step_peak_c'],observed_AP180_reported_c=a['AP180_reported_c'],
                predicted_AP35_180_mean_c=p['AP35_180_mean_c'],prediction_minus_observed_APmean_c=d['mean_c'],
                prediction_minus_observed_reported_peak_c=d['reported_peak_vs_saved_model_grid_c'],prediction_minus_observed_AP180_c=d['AP180_c'],
                predicted_J0_180_conditional=p['J0_180_conditional'],measured_J=None,energy_prediction_error=None)
            for co in ('ALL','U','N'):
                row.update({co+'_'+f:s['observed_metrics']['by_cohort'][co].get(f) for f in ('planned','responded','available','deadline_met','service_success','failed','incomplete','missing_observed_records','invalid_records','response_p95_ns')})
            writer.writerow(row)
    return ('\ufeff'+stream.getvalue()).encode('utf-8')


def validate_predecessor_initial_copy(audit):
    """Bind unused EP000 initialization; never restore/promote failed EP001."""
    copied=read(O/'P0_INIT_COPY_REGISTERED.json');failure=read(O/'PREDECESSOR_FAILURE_PROOF.json')
    source_cp=PREDECESSOR_O/'checkpoints/P0_EP000.pt';target_cp=O/'checkpoints/P0_EP000.pt'
    receipts_path=PREDECESSOR_O/'receipts.jsonl'
    require(copied['generation']=='A24INT_G002','Initialization copy must name the successor generation')
    require(key(copied['source_checkpoint_path'])==key(source_cp) and key(copied['checkpoint_path'])==key(target_cp),'Exact predecessor/successor initialization paths')
    require(sha(source_cp)==P0_EP000_SHA256==copied['source_checkpoint_sha256']==copied['checkpoint_sha256']==sha(target_cp)==audit['checkpoint_states'][str(target_cp)]['sha256'],'Unused EP000 original/copy/audit byte SHA closure')
    require(key(copied['predecessor_receipts_path'])==key(receipts_path),'Exact predecessor consumed-ledger path')
    require(sha(receipts_path)==PREDECESSOR_RECEIPTS_SHA256==copied['predecessor_receipts_sha256']==failure['receipts_sha256'],'Predecessor START/FAIL receipt bytes unchanged')
    require(sha(O/'PREDECESSOR_FAILURE_PROOF.json')==sha(PREDECESSOR_FAILURE_SOURCE),'Parent failure proof must be an exact byte copy')
    require(copied['predecessor_START']==copied['predecessor_FAIL']==1 and copied['failed_identity']==PREDECESSOR_FAILED_IDENTITY and copied['failed_raw_present'] is False,'One failed consumption is preserved, not refunded or retried')
    require(failure['schema']=='A24_G001_P0_FAILURE_SAVED_FRONTIER_DECISION_V1' and failure['identity']==PREDECESSOR_FAILED_IDENTITY,'Original G001 failure identity proof')
    require(failure['old_START']==failure['old_FAIL']==1 and failure['old_COMPLETE']==failure['old_PREPARED']==0,'Original failure is not a successful saved result')
    frontier=failure['exact_saved_frontier']
    require(key(frontier['path'])==key(source_cp) and frontier['sha256']==P0_EP000_SHA256 and frontier['episode']==0 and frontier['raw_experience_for_failed_EP001'] is False,'Copy is unused initialization, not failed episode recovery')
    prior=lines(receipts_path)
    require(len(prior)==2 and [e['event'] for e in prior]==['START','FAIL'] and all(e['identity']==PREDECESSOR_FAILED_IDENTITY for e in prior),'Exactly one predecessor START and its FAIL remain visible')
    require(prior[0]['manifest']['generation']=='A24INT_G001' and prior[0]['manifest']['config']['episode']==1 and prior[0]['manifest']['config']['sample_seed']==799001,'Consumed predecessor identity/episode/seed remain unchanged')
    absent=[PREDECESSOR_O/'raw/A24INT_G001'/(PREDECESSOR_FAILED_IDENTITY+'.json.gz'),
            PREDECESSOR_O/'rollouts'/(PREDECESSOR_FAILED_IDENTITY+'.pt'),
            PREDECESSOR_O/'prepared'/(PREDECESSOR_FAILED_IDENTITY+'.json')]
    require(all(not p.exists() and not p.with_name(p.name+'.part').exists() for p in absent),'Failed predecessor has no recoverable raw/rollout/prepared result')
    return {'predecessor_output':str(PREDECESSOR_O),'failed_identity':PREDECESSOR_FAILED_IDENTITY,
            'predecessor_START':1,'predecessor_FAIL':1,'predecessor_COMPLETE':0,
            'predecessor_receipts_sha256':PREDECESSOR_RECEIPTS_SHA256,
            'failure_proof_sha256':sha(O/'PREDECESSOR_FAILURE_PROOF.json'),
            'initial_copy_registration_sha256':sha(O/'P0_INIT_COPY_REGISTERED.json'),
            'unused_initialization_checkpoint_sha256':P0_EP000_SHA256,
            'failed_episode_result_recovered':False,'failed_consumption_refunded':False}


def validate_completed_scopes(op,pins):
    completion=read(O/'COMPLETION_RECEIPT.json');audit=read(O/'FINAL_AUDIT.json')
    require(completion['status']=='A24_MODEL_TRAINING_EVAL_AND_SAVED_AUDIT_COMPLETE_PHYSICAL_CONFIRM_PENDING','Simulation artifact completion missing')
    require(audit['status']=='PASS' and audit['FAIL']==0 and audit['unresolved_START']==0,'Simulation FINAL_AUDIT not PASS')
    require(completion['project_complete'] is False and audit['project_complete'] is False,'Original scope overclaims project completion')
    reg=read(O/'REGISTRATION.json')
    require(sha(O/'REGISTRATION.json')==audit['registration_sha256'],'Original experiment registration SHA')
    for path,h in reg['protected'].items():require(sha(path)==h,'Protected original source/raw changed: '+path)
    for p,h in completion['artifacts'].items():require(sha(p)==h,'Finalized simulation artifact changed: '+p)
    require(completion['html']['sha256']==op['existing_html_sha256']==sha(TARGET),'Exact original finalizer HTML SHA')
    require(audit['finalizer_source_sha256']==sha(W/'finalize_a24.py'),'Original finalizer source drift')
    fop_path=Path(op.get('finalizer_operation_path',str(O/'FINALIZER_OPERATION_REGISTERED.json')));fop=read(fop_path)
    require(fop['source_sha256']==sha(W/'finalize_a24.py') and fop['allow_finalize'] is True,'Original finalizer operation/source binding')
    require(audit['html']['sha256']==completion['html']['sha256'],'Final audit rendered HTML/commitment mismatch')
    require(audit['new_NN_inference']==audit['new_optimizer_steps']==audit['new_CostState']==audit['new_environment']==0,'Finalizer must be saved-only')
    for p,meta in audit['checkpoint_states'].items():require(sha(p)==meta['sha256'],'Audited checkpoint bytes changed: '+p)
    predecessor=validate_predecessor_initial_copy(audit)
    trained=[m for p,m in audit['checkpoint_states'].items() if p.endswith('EP032.pt')]
    require(len(trained)==12 and all(m.get('actor_learning_proof',{}).get('changed_actor_tensor_count',0)>0 for m in trained),'Actual actor-learning proof not complete for twelve models')
    frozen=read(P/'PREDICTIONS_FROZEN.json');forecast_op=read(O/'NEW_CONFIRM_OPERATION_REGISTERED.json')
    observed=read(C/'OBSERVED_COMPARISON.json');observed_op=read(O/'NEW_CONFIRM_COMPARISON_OPERATION_REGISTERED.json')
    access=read(C/'OBSERVED_ACCESS_STARTED.json');algorithm=read(C/'ALGORITHM_SPEC.json')
    require(frozen['status']=='PREDICTIONS_FROZEN_BEFORE_NEW_OBSERVED_COMPARISON' and frozen['environment_starts']==8,'Eight fixed-rule prediction seal incomplete')
    require(frozen['observed_response_postcommon_AP_or_J_metrics_parsed']==0,'Forecast was not results-blind at its own boundary')
    require(frozen['operation_sha256']==sha(O/'NEW_CONFIRM_OPERATION_REGISTERED.json') and frozen['operator_sha256']==sha(W/'predict_confirmation.py'),'Forecast source/operation lineage')
    require(forecast_op['operator_sha256']==frozen['operator_sha256'] and forecast_op['allow_execution'] is True,'Forecast operation authorization')
    require(sha(O/'DEV_SELECTION_FREEZE.json')==read(O/'VIEW_DATA.json')['meta']['source_freeze']['selection_sha256'],'Original DEV-only selected checkpoint seal')
    require(observed['schema']=='A24-new8-sealed-forecast-observed-residuals-v1' and observed['status']=='DESCRIPTIVE_COMPARISON_COMPLETE','Observed descriptive comparison incomplete')
    require(observed['operator_sha256']==observed_op['operator_sha256']==sha(W/'observed_comparison.py'),'Observed source SHA lineage')
    require(observed['predictions_frozen_sha256']==observed_op['predictions_frozen_sha256']==access['predictions_frozen_sha256']==sha(P/'PREDICTIONS_FROZEN.json'),'Prediction seal before observed access linkage')
    require(observed_op['allow_observed_access'] is True and observed_op['max_sessions']==8 and observed_op['fit']==0,'Observed access operation scope')
    require(access['operation_sha256']==sha(O/'NEW_CONFIRM_COMPARISON_OPERATION_REGISTERED.json') and access['operator_sha256']==observed['operator_sha256'],'Observed access-start source/operation')
    require(sha(C/'ALGORITHM_SPEC.json')==digest(algorithm)==observed['algorithm_spec_sha256']==observed_op['algorithm_spec_sha256']==access['algorithm_spec_sha256'],'Observed algorithm predeclared SHA')
    require(observed_op['forecast_operation_sha256']==frozen['operation_sha256'],'Observed forecast operation binding')
    require(observed_op['execution_plan_sha256']==frozen['execution_plan_sha256']==sha(P/'PREDICTION_EXECUTION_PLAN.json'),'Prediction execution plan binding')
    require(observed['new_environment']==observed['NN']==observed['fit']==observed['optimizer']==0,'Observed comparator must not fit or execute models')
    require(observed['measured_J'] is None and observed['energy_prediction_error'] is None and observed['confidence_interval'] is None,'Unqualified measured energy/inference cannot be promoted')
    require(observed['physical_independent_accuracy_confirmed'] is False,'Fixed-rule residual report does not establish physical superiority')
    session_map={s['session_id']:s for s in observed['sessions']};prediction_map={p['session_id']:p for p in frozen['predictions']}
    require(len(session_map)==len(prediction_map)==observed['sessions_count']==8 and set(session_map)==set(prediction_map),'Same sealed eight forecast/observed sessions')
    old_ids={r['session_id'] for r in read(OLD_PLAN)}
    require(len(old_ids)==17 and not old_ids.intersection(session_map),'Previously seen17 and new normal-only8 must be distinct')
    access_rows=lines(C/'access_receipts.jsonl');access_by=collections.defaultdict(list)
    for event in access_rows:access_by[event['session_id']].append(event)
    require(set(access_by)==set(session_map) and len(access_rows)==16,'Exact eight observed access START/COMPLETE chains')
    for sid,item in session_map.items():
        chain=access_by[sid]
        require([e['event'] for e in chain]==['OBSERVED_SESSION_ACCESS_START','OBSERVED_SESSION_ACCESS_COMPLETE'],'Unfinished/duplicate observed access')
        require(access['unix']<=chain[0]['unix']<=chain[1]['unix'],'Observed access chronology')
        session_path=C/'sessions'/(sid+'.json')
        require(sha(session_path)==chain[1]['output_sha256'] and read(session_path)==item,'Per-session observed output immutable binding')
        pred=prediction_map[sid]
        require(item['forecast_identity']==pred['identity'] and item['forecast_raw_sha256']==pred['raw_sha256'],'Residual/forecast identity binding')
        require(len(item['requests'])==item['planned']==item['observed_metrics']['planned']==pred['primary_metrics']['planned'],'All planned requests retained')
        require(len({r['observed']['request_id'] for r in item['requests']})==item['planned'],'Unique request residual roster')
        require(item['measured_J'] is None and item['energy_prediction_error'] is None and item['confidence_interval'] is None and item['new_fit']==0,'Per-session energy/fit boundary')
        ap=item['observed_AP']
        require(ap['physical_interpolation'] is False and ap['sensor_update_time_known'] is False and ap['surface_temperature_verified'] is False,'Read-clock HAL AP is not physical interpolation/update/surface proof')
        for model in ('TREND27','MEASURED35'):
            m=item['models'][model]
            require(m['measured_J'] is None and m['energy_prediction_error'] is None,'No measured J from fixed model predictions')
            if not ap['qualified']:
                require(all(v is None for v in m['prediction_minus_observed'].values()),'Failed AP coverage residuals must remain null')
        if not ap['qualified']:
            require(all(ap[k] is None for k in ('AP35_180_reported_step_mean_c','AP35_180_reported_step_peak_c','AP180_reported_c','AP180_reported_residual_from_initial_c')),'Failed AP window must remain null')
    require(observed['planned_requests']==sum(s['planned'] for s in session_map.values())==1456,'Fixed normal8 full planned denominator')
    require(sha(observed['full_plan_denominator_path'])==observed['full_plan_denominator_sha256'] and read(observed['full_plan_denominator_path'])==observed['full_plan_denominators'],'Historical full-plan denominator bytes')
    rows=lines(O/'rows.jsonl');receipt_rows=lines(O/'receipts.jsonl');chains=collections.defaultdict(list)
    for e in receipt_rows:chains[e['identity']].append(e)
    original={e['identity'] for e in audit['per_run']};extra={e['identity'] for e in frozen['predictions']}
    require(len(rows)==len(chains)==1694 and {r['identity'] for r in rows}==original|extra,'Finalized base and new prediction durable roster, no silent extra identities')
    original_hash={e['identity']:e['raw_sha256'] for e in audit['per_run']}
    extra_hash={e['identity']:e['raw_sha256'] for e in frozen['predictions']}
    source_hashes={}
    for row in rows:
        identity=row['identity'];chain=chains[identity]
        require([e['event'] for e in chain]==['START','PREPARED','COMPLETE'],'Every saved environment terminal chain remains complete')
        require(sha(row['raw_path'])==row['raw_sha256']==original_hash.get(identity,extra_hash.get(identity))==chain[1]['raw_sha256']==chain[2]['raw_sha256'],'Existing raw/environment integrity')
        prep=O/'prepared'/(identity+'.json')
        require(read(prep)==row and sha(prep)==chain[1]['prepared_sha256'],'Existing prepared-row exact commit')
        manifest=row['manifest']
        require(manifest==chain[0]['manifest'] and manifest['identity']==identity,'Current START/row manifest binding')
        require(manifest['registration_sha256']==sha(O/'REGISTRATION.json'),'Current source registration binding')
        generation_path=W/'source_generations'/manifest['generation']/'GENERATION.json'
        require(sha(generation_path)==manifest['generation_sha256'],'Existing frozen generation SHA')
        for path,h in manifest['source_hashes'].items():
            if path not in source_hashes:require(sha(path)==h,'Frozen source changed after final audit: '+path);source_hashes[path]=h
            require(source_hashes[path]==h,'Conflicting saved source hash')
    for pred in frozen['predictions']:
        require(sha(pred['secondary_cost_path'])==pred['secondary_cost_sha256'] and sha(pred['trace_audit_path'])==pred['trace_audit_sha256'],'Fixed-trace secondary cost/audit bytes')
    observer_path=P/'cost_observer_receipts.jsonl'
    require(sha(observer_path)==frozen['cost_observer_receipts_sha256'] and frozen['cost_wrapper_instances']==16,'Prediction cost-only observer saved accounting')
    observer_events=lines(observer_path);os_=[e for e in observer_events if e['event']=='COST_START'];oc=[e for e in observer_events if e['event']=='COST_COMPLETE']
    require(len(os_)==len(oc)==16 and {e['wrapper_identity'] for e in os_}=={e['wrapper_identity'] for e in oc},'Exact16 prior cost-only observer terminal identities')
    live=read(op['latest_live_metadata_path'])
    require('live_counts' in live,'Pinned latest light metadata must contain progress counts')
    return completion,audit,frozen,observed,live,algorithm,predecessor


def report_document(simulation,observed,live,scope):
    lines_=['# A24 스케줄링 시뮬레이터 통합 결과','',
        '정해진 납기를 최대한 만족하면서 열·에너지를 줄이는 목표를 유지했다. 모형에서 학습·비교한 롤링＋ATC＋RL과 실기기 고정 규칙 8세션의 예측 잔차를 별도 증거로 연결했다.','',
        f'- 소프트웨어 구현·학습·봉인 평가·원감사 완료. DEV 선정 추천군: {simulation["recommended_family_from_DEV"]}. 실제 phone RL 정책 검증은 미실시다.',
        f'- 모형 내 E180≥10%·평균AP≥0.5℃ 공동목표 PASS 비교 수: {simulation["model_conditional_joint_goal_pass_count"]}. 실제 열·에너지 절감 목표는 미확인이다.',
        '- 새 실측 전류/전하량 단위가 해결되지 않아 measured J와 에너지 예측오차는 null이다. 모형 J를 실측 J로 대체하거나 1000배 보정하지 않았다.',
        '- 원 finalizer의 CONFIRM 접근0은 그 실행기의 범위다. 별도 승인된 observed_comparison 실행기가 봉인 후 정상 공개8세션을 읽었다. 프로젝트 수준 기존 관찰17＋새 정상8을 구분한다.',
        '- 새8은 이미 실측된 정상·공개 자료를 결과 열람 전에 offline 예측한 부분집합이다. 동시적 prospective 검증이나 전체40계획의 무편향 표본이 아니다. 실패·거절·미공개·보충군은 각각의 원분모에 남긴다.',
        '- AP는 HAL 읽기 완료 상한 시각을 기준으로 마지막 보고값을 유지하는 ZOH 통계다. 물리 센서 갱신시각·표면온도·온도 사이 실제 변화를 복원하지 않는다. 35/180 양측 및 중간gap5초 기준을 못 채우면 관련 요약·잔차를 null로 보존한다.',
        '- 모형 SIM_EVAL의 세 bank bootstrap2000/학습3seed 범위와 실측 fixed-rule8의 세션별 잔차는 합치지 않았다. 부호 차이는 모형/잠재시간표본의 합성 조건이며 순수계수 인과 효과가 아니다.',
        '- 최신 LIVE 진행보고와 d549 시점의 과거 분모 파일은 시점이 다르다. REBASE6/보충12/사후DEV를 기존40이나 이번8에 합산하지 않는다. 시작 AP가 같아도 열 이력·SOC·전체 상태가 같다는 뜻은 아니다.','',
        '- 실행 계보는 G002 성공1,694환경과 G001 실패소비1환경을 분리해 총 START1,695로 보존했다. EP000은 미사용 초기화 저장본을 정확 복사했으며 실패 EP001의 결과를 복구하거나 성공으로 재수집한 것이 아니다.','',
        '## 새 고정 규칙 실측8의 저장된 결과','',
        '| 세션 | 계획 | 긴급 납기/계획 | 일반 납기/계획 | 응답 잔차 MAE ms | AP창 | 관측 AP 평균 ℃ | TREND27 평균잔차 ℃ | MEASURED35 평균잔차 ℃ |',
        '|---|---:|---:|---:|---:|---|---:|---:|---:|']
    for s in observed['sessions']:
        co=s['observed_metrics']['by_cohort'];a=s['observed_AP']
        lines_.append('| '+s['label'].replace('|','/')+' | '+str(s['planned'])+' | '+str(co['U']['deadline_met'])+'/'+str(co['U']['planned'])+' | '+str(co['N']['deadline_met'])+'/'+str(co['N']['planned'])+' | '+fmt(s['response_latency_errors_ms']['MAE'])+' | '+('적격' if a['qualified'] else '미적격')+' | '+fmt(a['AP35_180_reported_step_mean_c'])+' | '+fmt(s['models']['TREND27']['prediction_minus_observed']['mean_c'])+' | '+fmt(s['models']['MEASURED35']['prediction_minus_observed']['mean_c'])+' |')
    lines_.extend(['','잔차 부호는 예측−관측이다. 완료 응답의 오차 표본 수와 전체 계획의 서비스 분모는 다르며, 세션별 원자료 누락/문제/기준미달을 보존했다.','',
        '## 자료 시점과 범위','',
        '- 최신 진행보고(부모가 핀한 메타데이터): `'+json.dumps(live['live_counts'],ensure_ascii=False)+'`',
        '- 비교기의 과거 전체계획 분모는 원 JSON을 그대로 연결했다. 최신 완료 현황으로 소급 수정하지 않았다.',
        '- 프로젝트 전체 완료: false. 소프트웨어 산출물/통합 보고 완료와 물리 에너지·정책 우위 검증 완료를 구분한다.',''])
    return '\n'.join(lines_).encode('utf-8')


def section_html(observed,live):
    esc=lambda v:html.escape(str(v),quote=True)
    parts=['<section id="a24-observed-supplement" aria-label="별도 실측 고정 규칙 검산" style="margin-top:34px;border-top:1px solid var(--a24-line);padding-top:24px">',
        '<h2>모형 학습과 실기기 검산을 구분합니다</h2>',
        '<p class="chart-explanation">위 곡선과 학습 정책은 SIM_EVAL 모형 실험입니다. 아래는 별도 고정 규칙으로 이미 실측된 정상 공개8세션의 예측−관측 잔차입니다. 휴대폰에서 RL을 실행한 검증이 아닙니다.</p>',
        '<div class="scope-note"><strong>소프트웨어 산출물 완료 · 실제 에너지 절감은 미확인.</strong> 새 실측 J와 에너지 오차는 미판정이며, 프로젝트 물리 목표 PASS로 표시하지 않습니다. 원 finalizer 접근0과 별도 비교기 관측8을 구분합니다.</div>',
        '<p class="table-note">G002 성공 실행1,694건과 원 G001 실패소비1건을 합쳐 전체 A24 계보 START1,695건을 보존했습니다. EP000은 미사용 초기화의 정확 복사이며 실패 EP001 결과 복구나 재수집이 아닙니다.</p>',
        '<div class="table-wrap"><table><thead><tr><th scope="col">실측 세션 / 고정 규칙</th><th scope="col">긴급 납기 / 계획</th><th scope="col">일반 납기 / 계획</th><th scope="col">전체 AVAILABLE / 계획</th><th scope="col">응답 잔차 MAE ms</th><th scope="col">AP 창</th><th scope="col">관측 AP 평균 ℃</th><th scope="col">TREND27 평균잔차 ℃</th><th scope="col">MEASURED35 평균잔차 ℃</th><th scope="col">실측 J</th></tr></thead><tbody>']
    for s in observed['sessions']:
        c=s['observed_metrics']['by_cohort'];ap=s['observed_AP']
        vals=[s['label'],str(c['U']['deadline_met'])+' / '+str(c['U']['planned']),str(c['N']['deadline_met'])+' / '+str(c['N']['planned']),
              str(c['ALL']['available'])+' / '+str(c['ALL']['planned']),fmt(s['response_latency_errors_ms']['MAE']),
              '적격' if ap['qualified'] else '기준 미달 · null 유지',fmt(ap['AP35_180_reported_step_mean_c']),
              fmt(s['models']['TREND27']['prediction_minus_observed']['mean_c']),fmt(s['models']['MEASURED35']['prediction_minus_observed']['mean_c']),'미판정']
        parts.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in vals)+'</tr>')
    parts.extend(['</tbody></table></div>',
        '<p class="table-note">전체 계획1,456요청을 분모에 유지했습니다. 응답 오차는 유효한 완료 응답에서만 정의되며, 실패·미완료가 없는 것으로 바꾸지 않습니다. AP 요약은 HAL 읽기 완료 시계의 ZOH 보고 통계이며 센서 갱신시각·실제 표면온도 검증이 아닙니다. 미래 표본 대입·공백 보간은 하지 않았습니다.</p>',
        '<details><summary>실측8의 선택 편향과 최신 진행보고</summary><div class="detail-body"><p>기존 관찰17과 겹치지 않는 정상·공개8만을 비교했습니다. 전체40의 실패·거절·미공개 슬롯을 대표하지 않으며, 실측 후 결과 미열람 offline 예측이므로 동시적 사전 예측도 아닙니다. REBASE6·보충군·사후DEV는 합치지 않았습니다. AP 시작값이 같아도 열 이력·SOC·전체 상태가 같은 증거가 아닙니다.</p><p>부모가 핀한 최신 LIVE 메타데이터: '+esc(json.dumps(live['live_counts'],ensure_ascii=False))+'</p><p>이 최신 보고와 비교기가 보존한 d549 시점의 전체계획 분모는 별도 시점입니다. 이전 파일을 최신값으로 소급 수정하지 않습니다.</p></div></details>',
        '</section>'])
    return ''.join(parts)


def execute(operation_path):
    op,pins=validate_operation(operation_path)
    require(not R.exists(),'REPORT_SUPPLEMENT lineage already exists; inspect it instead of overwriting')
    import msvcrt
    lock=(O/'worker.lock').open('a+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    require(shutil.disk_usage(O).free>=8*1024**3 and shutil.disk_usage(TARGET.parent).free>=8*1024**3,'Registered 8GiB storage reserve')
    completion,audit,frozen,observed,live,algorithm,predecessor=validate_completed_scopes(op,pins)
    source_results=read(O/'RESULTS_KO.json');source_view=read(O/'VIEW_DATA.json')
    require(source_results.get('new_CONFIRM_outcomes_opened')==0 and source_view['meta'].get('new_phone_CONFIRM_outcomes_opened')==0,'Preserve finalizer own-scope observed-access0')
    row_digest=digest(source_view['rows'])
    scopes={'finalizer':{'observed_CONFIRM_outcomes_opened':0,'meaning':'Only this operator scope, not the whole project'},
            'separate_observed_comparison':{'new_normal_fixed_rule_sessions_accessed':8,'planned_requests':observed['planned_requests'],
                'previously_observed_CONFIRM_sessions':17,'disjoint_normal_CONFIRM_seen_total':25,'phone_RL_policy_validation':False,
                'actual_delegate_or_decode_quality_independently_validated':False,
                'data_role':'Already measured normal/published subset; offline results-blind forecast, not contemporaneous prospective validation'},
            'project':{'software_artifact_complete':True,'integrated_report_complete':True,'project_complete':False,
                'physical_energy_goal_pass':False,'physical_policy_superiority_confirmed':False,'measured_J':None,
                'energy_prediction_error':None,'latest_progress_is_not_all_raw_audited':True,
                'base_model_environment_START':1686,'offline_fixed_rule_prediction_environment_START':8,
                'child_successful_environment_START':1694,'predecessor_failed_environment_START':1,'total_desktop_environment_START':1695,
                'predecessor_failure_and_initialization_copy':predecessor,
                'unique_measured_sessions_in_comparison':8,'two_model_observed_CSV_rows_not_sessions':16,
                'desktop_new_device_commands':0,'integrator_new_environment':0},
            'separation':['SIM_EVAL learned curves and model bootstrap are not phone measurements',
                'Normal-only8 residuals are not a confidence interval for all40 or phone RL superiority',
                'Historical d549 denominators and latest LIVE counts keep their own timestamps',
                'REBASE6/additional12/posthocDEV do not enter original40 or sealed8',
                'HAL AP read-completion ZOH is not physical sensor interpolation or surface temperature']}
    integrated={'schema':'A24-integrated-software-and-fixed-rule-evidence-report-v1','status':'SOFTWARE_AND_REPORT_COMPLETE_PHYSICAL_J_UNRESOLVED',
                'source_simulation_results':source_results,'separate_fixed_rule_observed_comparison':observed,
                'scope_correction':scopes,'latest_live_metadata':live,'historical_denominators':observed['full_plan_denominators'],
                'measured_J':None,'physical_goal_pass':False,'project_complete':False,
                'new_environment':0,'NN':0,'CostState':0,'fit':0,'selection':0,'optimizer':0,'raw_measurement_archives_opened_by_integrator':0}
    view=copy.deepcopy(source_view)
    view['meta']['scope_correction']=scopes
    view['meta']['primary_policy_status']='모형 학습·봉인 평가 완료 · 별도 고정 규칙 실측8 검산 · 실제 폰 RL 검증 미실시'
    view['meta']['project_observed_NORMAL_confirmation_sessions_opened_by_separate_operator']=8
    view['meta']['project_complete']=False
    view['meta']['physical_goal_pass']=False
    view['meta']['energy_status']='고정 모형의 조건부 J 예측. 별도 실측8도 measured J와 에너지오차 미판정. 폰 RL·물리 절감 미검증.'
    # Keep the original zero field unchanged; explicit source/project scopes above correct its interpretation.
    view['separate_fixed_rule_observed_comparison']=observed
    require(digest(view['rows'])==row_digest,'Learned SIM_EVAL values/curves must not be modified or mixed with phone8')
    old_html=TARGET.read_bytes();text_=old_html.decode('utf-8')
    pattern=re.compile(r'(<script\b[^>]*\bid=[\"\']a24-data[\"\'][^>]*>)(.*?)(</script>)',re.S)
    matches=list(pattern.finditer(text_));require(len(matches)==1,'Original finalized page must contain exactly one A24 data script')
    embedded=json.loads(matches[0].group(2))
    require(embedded==source_view,'Existing finalizer page embedded exact VIEW_DATA')
    require('a24-observed-supplement' not in text_,'Existing page already has a report supplement')
    text_=pattern.sub(lambda m:m.group(1)+canonical(view).decode().replace('<','\\u003c')+m.group(3),text_,count=1)
    require(text_.count('<footer>')==1,'Exact one root footer is required for supplement insertion')
    text_=text_.replace('<footer>',section_html(observed,live)+'<footer>',1)
    new_html=text_.encode('utf-8')
    # Recheck every parent pin immediately before writing; monitoring cannot silently change scope.
    for p,h in op['pins'].items():require(sha(p)==h,'Evidence changed during report assembly: '+p)
    require(sha(TARGET)==op['existing_html_sha256'],'Target changed during report assembly')
    write(R/'source/A24_finalized_before_report.html',old_html)
    for src,name in [(Path(operation_path),'REPORT_OPERATION_REGISTERED.json'),
                     (Path(op['latest_live_metadata_path']),'LATEST_LIVE_METADATA_PINNED.json')]:
        write(R/'source'/name,src.read_bytes())
    for src,name in [(O/'ALL_CASES.csv','SIMULATED_ALL_CASES.csv'),(O/'RESULTS_KO.json','SOURCE_SIMULATION_RESULTS.json'),
                     (O/'VIEW_DATA.json','SOURCE_SIMULATION_VIEW_DATA.json'),(O/'EFFECTS_AND_COMPARISONS.json','SOURCE_MODEL_EFFECTS.json'),
                     (C/'OBSERVED_COMPARISON.json','SOURCE_FIXED_RULE_OBSERVED_COMPARISON.json'),
                      (O/'P0_INIT_COPY_REGISTERED.json','SOURCE_P0_INIT_COPY_REGISTERED.json'),
                      (O/'PREDECESSOR_FAILURE_PROOF.json','SOURCE_PREDECESSOR_FAILURE_PROOF.json'),
                     (O/'FINAL_AUDIT.json','SOURCE_FINAL_AUDIT.json'),(O/'COMPLETION_RECEIPT.json','SOURCE_COMPLETION_RECEIPT.json')]:
        write(R/name,src.read_bytes());require(sha(R/name)==sha(src),'Archived source byte preservation')
    write(R/'SCOPED_RESULTS.json',integrated);write(R/'VIEW_DATA.json',view)
    write(R/'FIXED_RULE_OBSERVED_SESSIONS.csv',observed_csv(observed['sessions']))
    write(R/'통합_결과보고.md',report_document(source_results,observed,live,scopes))
    write(R/'A24_integrated_report.html',new_html)
    artifacts={str(p):sha(p) for p in sorted(R.rglob('*')) if p.is_file()}
    proof={'schema':'A24-integrated-report-saved-audit-v1','status':'PASS','operation_sha256':sha(operation_path),'source_sha256':sha(__file__),
           'parent_pins':op['pins'],'simulation_FINAL_AUDIT':'PASS','simulation_rows_digest_before':row_digest,'simulation_rows_digest_after':digest(view['rows']),
           'original_finalizer_SCOPE_CONFIRM_access':0,'separate_operator_observed_normal_sessions':8,'previously_seen17_separate':True,
           'all8_session_access_chains_complete':True,'all1694_child_environment_commit_chains_preserved':True,
           'child_successful_environment_START':1694,'predecessor_failed_consumption_preserved':1,'total_A24_lineage_START':1695,
           'P0_exact_unused_initialization_sha256':P0_EP000_SHA256,'P0_EP000_initialization_copy_and_predecessor_failure_bound':True,
           'failed_predecessor_episode_result_recovered':False,'predecessor_evidence':predecessor,
           'AP_read_clock_ZOH_scope_preserved':True,'actual_J_and_error_remain_null':True,'phone_RL_validation':False,
           'new_environment':0,'NN':0,'CostState':0,'fit':0,'selection':0,'optimizer':0,'raw_ZIP_open':0,
           'software_artifact_complete':True,'integrated_report_complete':True,'project_complete':False,'physical_goal_pass':False,
           'original_html_sha256':op['existing_html_sha256'],'new_html_sha256':hashlib.sha256(new_html).hexdigest(),'artifacts':artifacts,
           'publication_at_audit_boundary':'PENDING; report completion receipt must confirm exact HTML replacement','browser_QA':'PARENT_REQUIRED'}
    write(R/'INTEGRATED_REPORT_AUDIT.json',proof)
    # The previous page must be the exact finalizer artifact, and it is already archived above.
    require(sha(TARGET)==op['existing_html_sha256'] and sha(R/'source/A24_finalized_before_report.html')==op['existing_html_sha256'],'Preserved prior page before authorized replacement')
    temp=TARGET.with_name(TARGET.name+'.report.part')
    with temp.open('xb') as stream:stream.write(new_html);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,TARGET)
    require(sha(TARGET)==proof['new_html_sha256']==sha(R/'A24_integrated_report.html'),'Integrated HTML exact publication')
    receipt={'schema':'A24-integrated-report-completion-v1','status':'SOFTWARE_AND_INTEGRATED_REPORT_COMPLETE_PHYSICAL_J_UNRESOLVED',
             'audit_sha256':sha(R/'INTEGRATED_REPORT_AUDIT.json'),'operation_sha256':sha(operation_path),'source_sha256':sha(__file__),
             'html_target':str(TARGET),'html_sha256':sha(TARGET),'previous_html_archive':str(R/'source/A24_finalized_before_report.html'),
             'new_environment':0,'NN':0,'CostState':0,'fit':0,'selection':0,'optimizer':0,
             'software_artifact_complete':True,'integrated_report_complete':True,'project_complete':False,'physical_goal_pass':False,
              'child_successful_environment_START':1694,'predecessor_failed_consumption_preserved':1,'total_A24_lineage_START':1695,
             'automation_changed':False,'browser_QA':'PARENT_REQUIRED_NOT_CLAIMED'}
    write(R/'COMPLETION_RECEIPT.json',receipt);lock.close()
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--operation',type=Path,default=O/'REPORT_OPERATION_REGISTERED.json')
    parser.add_argument('--required-paths',action='store_true')
    args=parser.parse_args()
    if args.required_paths:
        print(json.dumps({'schema':SCHEMA,'required_paths':[str(p) for p in required_paths()],
            'also_required':'Pin latest_live_metadata_path exact snapshot and existing_html_sha256 from original finalizer receipt.'},ensure_ascii=False));return
    require(args.execute,'Source prepared only; pass --execute only after parent operation registration')
    print(json.dumps(execute(args.operation),ensure_ascii=False),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        # Never manufacture completion after missing/partial data. Preserve all source artifacts.
        failure=O/('REPORT_INTEGRATION_FAILURE_'+str(time.time_ns())+'.json')
        if O.exists():write(failure,{'status':'INTEGRATION_FAILED_NO_COMPLETION','error':str(error),'source_sha256':sha(__file__),
                                   'new_environment':0,'NN':0,'CostState':0,'fit':0,'project_complete':False})
        raise
