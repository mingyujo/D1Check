"""Add bank-overlay provenance and the third heldout AP curve to saved reports.

The frozen build_report_data.py is imported unchanged. This entry reads only
registered saved JSON/JSONL artifacts, performs no model or simulator execution,
and leaves original bank-null data and original CV summaries intact.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import build_report_data as base
from runtime_guard import operation, pin, read, sha, write_new

BASE_BUILDER_SHA256 = '4c34100f07dc1babf63a9006f6147c17049995115ebb4b80794a13ebdef30f09'
DATASET_SHA256 = 'f54df34fb498d235a97779aacf23e6a83cb1e4d71be807458d603face1254800'
OVERLAY_SCHEMA = 'A24_INITIAL_DEV8_TIMING_BANK_OVERLAY_V1'
def path_key(value):
    return os.path.normcase(os.path.abspath(value))
def registered_path(op, name):
    spec = op[name]
    allowed = {(path_key(p['path']), p['sha256']) for p in op['input_pins']}
    base.require((path_key(spec['path']), spec['sha256']) in allowed,
                 'Logical report input not registered: '+name)
    return pin(spec)
def input_artifact(op, name):
    return read(registered_path(op,name))
def overlay_facts(op, dataset):
    base.require(op['dataset_pin']['sha256'] == DATASET_SHA256, 'Original bank-null dataset pin differs')
    overlay = input_artifact(op, 'timing_bank_overlay_pin')
    proof = input_artifact(op, 'timing_bank_overlay_proof_pin')
    bindings_body = input_artifact(op, 'forecast_model_bindings_pin')
    bindings = bindings_body['model_bindings']
    base.require(overlay.get('schema') == OVERLAY_SCHEMA and
                 proof.get('schema') == OVERLAY_SCHEMA+'-APPLICATION-PROOF', 'Overlay proof schema differs')
    base.require(overlay.get('original_dataset_pin') == op['dataset_pin'] and
                 proof.get('original_dataset_pin') == op['dataset_pin'] and
                 proof.get('data_original_sha256') == DATASET_SHA256 and
                 proof.get('overlay_sha256') == op['timing_bank_overlay_pin']['sha256'],
                 'Overlay source dataset/proof binding differs')
    base.require(proof.get('all_nonbank_content_unchanged') is True and
                 proof.get('AP_inputs_targets_domains_and_roster_unchanged') is True and
                 proof.get('original_dataset_mutated') is False and
                 proof.get('new_AP_fit') == proof.get('NN_training') == proof.get('simulation_START_consumed') == 0,
                 'Overlay scientific boundary differs')
    for before, after in (('nonbank_dataset_before_sha256','nonbank_dataset_after_sha256'),
                          ('thermal_input_before_sha256','thermal_input_after_sha256')):
        base.require(isinstance(proof.get(before), str) and proof[before] == proof.get(after),
                     'Nonbank/AP projection changed')
    base.require(bindings.get('data_original_sha256') == DATASET_SHA256 and
                 bindings.get('timing_bank_overlay_sha256') == op['timing_bank_overlay_pin']['sha256'] and
                 bindings.get('timing_bank_overlay_proof_sha256') == op['timing_bank_overlay_proof_pin']['sha256'] and
                 bindings.get('effective_bank_map_sha256') == proof.get('effective_bank_map_sha256') and
                 bindings.get('thermal_input_projection_sha256') == proof.get('thermal_input_after_sha256'),
                 'Forecast model/overlay proof binding differs')
    sessions = dataset['sessions']
    by_id = {s['session_id']:(i,s) for i,s in enumerate(sessions)}
    records, changes = overlay.get('records'), proof.get('changes')
    base.require(isinstance(records,list) and isinstance(changes,list) and len(records) == len(changes) == 8
                 and proof.get('session_count') == len(sessions) == 115 and proof.get('amended_sessions') == 8,
                 'Exact115/8 overlay roster differs')
    record_by = {r['session_id']:r for r in records}
    change_by = {r['session_id']:r for r in changes}
    original_ids = {s['session_id'] for s in sessions if s.get('cohort_id') == 'INITIAL_DEV8:R02DEV01'}
    base.require(len(record_by) == len(change_by) == 8 and set(record_by) == set(change_by) == original_ids,
                 'Overlay whole-cohort roster differs')
    for sid, record in record_by.items():
        i, source = by_id[sid]
        change = change_by[sid]
        bank = record['bank']
        public, development = record['public_recipe'], record['development_proof']
        base.require(bank in ('C252','L64','M128') and 'bank' in source and source['bank'] is None
                     and record.get('old_bank') is None and source.get('source_family') == 'm8',
                     'Original null-bank session differs')
        base.require(record.get('dataset_pointer') == '/sessions/'+str(i) and
                     record.get('provenance_reference') == source.get('provenance',{}).get('saved_full_reference'),
                     'Exact original pointer/provenance differs')
        base.require(record['cohort_id'] == source['cohort_id'] == change.get('cohort_id') and
                     change.get('old_bank') is None and change.get('bank') == bank and
                     change.get('request_fields_changed') == 0,
                     'Saved overlay change does not match source')
        base.require(public.get('session_id') == development.get('session_id') == sid and
                     public.get('bank') == development.get('bank') == bank and
                     public.get('crc_verified') is True and development.get('role') == 'DEVELOPMENT' and
                     change.get('public_recipe_sha256') == base.identity(public) and
                     change.get('development_proof_sha256') == base.identity(development),
                     'Overlay public/DEV recipe proof differs')
        base.require(not any('bank' in q for q in source.get('requests',[])),
                     'Report contract expected no request-level bank fields in original DEV8')
    return {'overlay':overlay, 'proof':proof, 'model_bindings':bindings, 'records':record_by}
def timing_contexts(op, original, facts):
    contexts = [{'role':'ORIGINAL_NULL_BANK_GROUPED_CV', 'status':'SAVED_ORIGINAL_UNCHANGED',
                 'source_pin':op['timing_cv_pin'], 'dataset_sha256':DATASET_SHA256,
                 'summary':original,
                 'note':'Original context includes eight INITIAL_DEV8 bank-null sessions; unknowns retained.'}]
    if op.get('overlay_timing_cv_pin'):
        bindings = input_artifact(op, 'overlay_timing_cv_bindings_pin')
        result = input_artifact(op, 'overlay_timing_cv_result_pin')
        base.require(bindings.get('data_original_sha256') == DATASET_SHA256 and
                     bindings.get('timing_bank_overlay_sha256') == op['timing_bank_overlay_pin']['sha256'] and
                     bindings.get('effective_bank_map_sha256') == facts['proof']['effective_bank_map_sha256'] and
                     bindings.get('thermal_input_projection_sha256') == facts['proof']['thermal_input_after_sha256'] and
                     bindings.get('original_timing_cv_pin') == op['timing_cv_pin'],
                     'Corrected timing CV source/overlay context differs')
        base.require(result.get('result_sha256') == op['overlay_timing_cv_pin']['sha256'] and
                     result.get('bindings_sha256') == op['overlay_timing_cv_bindings_pin']['sha256'] and
                     result.get('original_result_sha256') == op['timing_cv_pin']['sha256'] and
                     result.get('original_timing_result_preserved') is True and
                     result.get('AP_fits') == result.get('NN') == result.get('simulation_START_consumed') == 0,
                     'Corrected timing CV receipt binding differs')
        summary = base.timing_summary(input_artifact(op, 'overlay_timing_cv_pin'))
        contexts.append({'role':'BANK_METADATA_OVERLAY_GROUPED_CV', 'status':'SAVED_SEPARATE_POSTHOC_CV',
                         'source_pin':op['overlay_timing_cv_pin'], 'bindings_pin':op['overlay_timing_cv_bindings_pin'],
                         'result_pin':op['overlay_timing_cv_result_pin'], 'summary':summary,
                         'note':'Same original candidate grid and whole cohorts; corrected bank metadata is a separate development context, not a fresh test.'})
    else:
        base.require(op.get('overlay_timing_cv_status') == 'PENDING_REGISTERED_TIMING_OVERLAY_CV',
                     'Explicit pending corrected timing CV contract required')
        contexts.append({'role':'BANK_METADATA_OVERLAY_GROUPED_CV',
                         'status':'PENDING_REGISTERED_TIMING_OVERLAY_CV','summary':None})
    return contexts
def augment_report(report, selected, facts, contexts, op):
    by_id = facts['records']
    for session in report['sessions']:
        sid = session['session_id']
        prediction = selected['m8-only']['predictions'].get(sid,{})
        session['m8_prediction'] = prediction.get('series',[])
        session['series_roles']['m8_prediction'] = 'SELECTED_M8_ONLY_WHOLE_COHORT_HELDOUT_CV'
        score = selected['m8-only']['rows'].get(sid,{})
        session['selected_CV']['m8-only'] = {'prediction':{k:v for k,v in prediction.items() if k != 'series'},
                                          'score':score}
        session['stats'].append({'label':'M8 자료만 적합한 CV MAE / 최대 오차',
            'value':base.fstr(score.get('mae_c'),3,'℃')+' / '+base.fstr(score.get('max_abs_error_c'),3,'℃')})
        session['original_observed_bank'] = session.get('bank')
        session['declared_public_bank'] = by_id[sid]['bank'] if sid in by_id else session.get('bank')
        session['forward_timing_bank'] = by_id[sid]['bank'] if sid in by_id else session.get('bank')
        if sid in by_id:
            record = by_id[sid]
            session['timing_bank_overlay'] = {'status':'PUBLIC_RECIPE_METADATA_REPAIR_FORWARD_TIMING_ONLY',
                'original_bank':None,'declared_public_bank':record['bank'],'forward_timing_bank':record['bank'],
                'preparation_pin':op['timing_bank_overlay_pin'],'application_proof_pin':op['timing_bank_overlay_proof_pin'],
                'source_record_session_id':sid,'public_recipe':record['public_recipe'],
                'development_proof':record['development_proof'],
                'original_thermal_CV_unchanged':True,'original_timing_CV_bank_context_unchanged':True}
            session['stats'].append({'label':'원 bank / 공개 recipe / 향후 시간 모형 bank',
                'value':'미확인(null) / '+record['bank']+' / '+record['bank']})
            session['note'] += ' 초기 DEV8 bank는 원자료의 null을 보존하고, 공개 recipe와 DEV 근거가 일치한 값만 별도 향후 시간 모형에 적용했습니다.'
        else:
            session['timing_bank_overlay'] = {'status':'NOT_AMENDED'}
    report['audit']['timing_bank_overlay'] = {'schema':OVERLAY_SCHEMA,
        'preparation_pin':op['timing_bank_overlay_pin'],'application_proof_pin':op['timing_bank_overlay_proof_pin'],
        'forecast_model_bindings_pin':op['forecast_model_bindings_pin'],
        'original_dataset_pin':op['dataset_pin'],'proof':facts['proof'],
        'changes':facts['proof']['changes'],'original_observed_bank_kept':True,
        'thermal_CV_and_final_models_kept':True,'original_timing_CV_kept':True,
        'actual_device_measurements_added':0,'new_AP_fits':0}
    report['audit']['timing_CV_contexts'] = contexts
    report['audit']['report_extension_source'] = {'original_builder_sha256':BASE_BUILDER_SHA256,
        'third_curve_role':'SELECTED_M8_ONLY_WHOLE_COHORT_HELDOUT_CV',
        'original_builder_modified':False}
    report['limitations'].append('초기 DEV8 8건의 원 bank null은 보존했습니다. 공개 recipe와 DEV 선언을 대조한 bank 보완은 별도 시간 모형 문맥이며, 원 timing CV와 보완 후 CV를 구분합니다. AP 적합·관측·묶음은 바꾸지 않았습니다.')
    return report
WAIT_UNQUALIFIED = 'RECORDED_GENERALIZED_SENTINEL_WAIT_UNQUALIFIED_NATIVE_DOMAIN'
WAIT_WARNING = '실측 WAIT 규칙 범위 밖 · 그룹 -1에 1회200ms를 둔 확장 진단'

def qualify_report(report, audit, contract, saved_rows):
    """Append saved contract qualifications without altering any forecast values."""
    base.require(audit.get('schema') == 'A24-SAVED-CONTRACT-SUPPLEMENT-v2' and
                 audit.get('status') == 'PASS_SAVED_CONTRACT_BINDINGS_WITH_UNQUALIFIED_WAIT_GENERALIZATIONS' and
                 audit.get('failed_checks') == 0 and audit.get('checks', 0) > 0,
                 'Completed V2 saved contract audit required')
    base.require(contract.get('schema') == 'A24-WAIT-DOMAIN-CORRECTION-CONTRACT-v1', 'Wrong WAIT qualification contract')
    expected = contract['expected_unqualified_cases']
    ids = [c['identity'] for c in expected]
    summary = audit['source_wait_domain_qualifications']
    base.require(len(ids) == len(set(ids)) == contract['expected_unqualified_count'] == 24 and
                 summary.get('unqualified_count') == summary.get('expected_unqualified_count') == 24 and
                 summary.get('unqualified_case_ids') == ids,
                 'Exact registered 24 unqualified case identities required')
    audit_cases = audit['cases']
    by_id = {c.get('identity'): c for c in audit_cases if c.get('identity') is not None}
    base.require(len(audit_cases) == 249 and audit.get('registered_case_roster') == 249 and
                 audit.get('heldout_roster') == 69 and audit.get('novel_roster') == 180 and
                 audit.get('all_249_cases_retained') is True, 'All249 V2 audit cases required')
    rows = [r for s in report['scenarios'] for r in s['rows']]
    heldout = report['audit']['forecast_validation_and_harms']['heldout_schedule_validation_rows']
    base.require(len(rows) == 180 and len(heldout) == 69, 'Preserve180 novel and69 heldout rows')
    source_hashes = {r['identity']: base.identity({k:v for k,v in r.items() if k != 'report_source_line'}) for r in saved_rows}
    base.require(len(source_hashes) == len(saved_rows), 'Duplicate saved source row identity')
    before = base.identity({'novel': rows, 'heldout': heldout})
    qualified = []
    seen = set()
    for row in rows + heldout:
        identity = row.get('identity')
        if identity is None:
            base.require(row.get('kind') == 'WHOLE_COHORT_HELDOUT_VALIDATION', 'Only no-START heldouts may lack identity')
            row['source_wait_domain_qualification'] = {'status': 'UNKNOWN_NO_SIMULATOR_START', 'native_group_domain_qualified': None,
                'message': '미실행 조건은 WAIT 규칙 검증이 미확인입니다.', 'forecast_row_identity': None, 'forecast_row_sha256': None}
            continue
        base.require(identity not in seen and identity in by_id, 'Report/V2 audit case identity differs')
        seen.add(identity)
        case = by_id[identity]
        base.require(all(row.get(k) == case.get(k) for k in ('kind','bank','policy','seed')), 'Report/V2 public case semantics differ')
        wait = case.get('WAIT')
        is_unqualified = identity in ids
        base.require((isinstance(wait, dict) and wait.get('status') == WAIT_UNQUALIFIED) == is_unqualified,
                     'Only registered24 may carry unqualified WAIT status')
        if is_unqualified:
            base.require(row['kind'] == 'PREDECLARED_NOVEL_GRID' and row['bank'] in ('C252','L64') and
                         row['policy'] == 'FIFO_WAIT_CG' and identity in source_hashes and wait.get('native_group_domain_qualified') is False and
                         wait.get('numeric_results_are_not_native_WAIT_validation') is True and
                         wait.get('full_scheduler_reproduction') is False and wait.get('installed_verified') is False,
                         'Unqualified WAIT must retain native-domain and installation limits')
            qualified.append(identity)
            status, native, message = WAIT_UNQUALIFIED, False, WAIT_WARNING
        elif row.get('policy') != 'FIFO_WAIT_CG':
            status, native, message = 'NOT_WAIT_POLICY', None, 'WAIT 정책 대상 아님'
        elif isinstance(wait, dict) and wait.get('status') == 'RECORDED_WAIT_CONSTRAINTS_CHECKED':
            status, native, message = 'NATIVE_WAIT_DOMAIN_RECORDED_CONSTRAINTS_CHECKED', True, '정수 그룹 0..15의 저장 WAIT 제약 확인 · 설치 검증 아님'
        else:
            status, native, message = 'UNKNOWN_NO_COMPLETE_WAIT_RECORD', None, '저장 WAIT 규칙 검증이 미확인입니다.'
        row['source_wait_domain_qualification'] = {'status':status, 'native_group_domain_qualified':native,
            'message':message, 'audit_WAIT':wait, 'forecast_row_identity':identity,
            'forecast_row_sha256':source_hashes.get(identity), 'numeric_values_changed':False,
            'installed_verified':False, 'full_scheduler_reproduction':False}
    base.require(set(qualified) == set(ids) and len(qualified) == 24, 'Do not omit any unqualified case')
    stripped = lambda rr: [{k:v for k,v in r.items() if k != 'source_wait_domain_qualification'} for r in rr]
    after = base.identity({'novel':stripped(rows), 'heldout':stripped(heldout)})
    base.require(before == after, 'Qualification must not alter any preexisting forecast field')
    report['audit']['source_wait_domain_qualifications'] = {**summary,
        'contract_expected_case_ids':ids, 'all249_annotation_value_sha256_before':before,
        'all249_annotation_value_sha256_after_stripping_qualifications':after,
        'all_preexisting_forecast_fields_unchanged':True,
        'saved_forecast_row_sha256_by_identity':source_hashes,
        'message':WAIT_WARNING, 'native_WAIT_validation_claim_for_these24':False,
        'new_simulations':0, 'new_fits':0}
    scope_note = 'C252·L64의 WAIT 24행은 검증 지원범위 밖 그룹 -1을 일반화 엔진이 한 그룹으로 취급한 확장 진단입니다. 이 행을 포함한 WAIT 평균·정책효과·승자 비교는 실측 WAIT 재현·검증으로 해석할 수 없습니다. 조건부 J 차이 약 5.68e-14J는 부동소수점 잔차이며 실제 에너지 손해의 근거가 아닙니다.'
    report['audit']['forecast_validation_and_harms']['source_wait_domain_qualification'] = {
        'unqualified_case_ids':ids, 'unqualified_count':24, 'message':scope_note,
        'applies_to':['WAIT 전체 평균','정책 효과','승자 요약','EFFECTS_AND_HARMS'],
        'original_effect_values_changed':False, 'native_WAIT_policy_validation_for_all180':False,
        'measured_J':None, 'physical_goal_pass':False}
    for scenario in report['scenarios']:
        if any(r['identity'] in ids for r in scenario['rows']):
            scenario['source_wait_domain_qualification'] = {'unqualified_case_ids':[r['identity'] for r in scenario['rows'] if r['identity'] in ids], 'message':scope_note}
            scenario['limits'] = scenario.get('limits','') + ' ' + scope_note
    report['limitations'].append('C252·L64 WAIT 24행은 '+WAIT_WARNING+'입니다. 수치는 원 예측 그대로이며 실측 소스 WAIT 정책의 검증 결과로 사용하지 않습니다. M128의 정수 그룹 0..15 WAIT와 관측 일정 검증은 별도로 보존합니다.')
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation',required=True)
    args = parser.parse_args()
    with operation(args.operation,__file__) as (op,out):
        base.require(op.get('mode') == 'REPORT_DATA','Wrong saved report mode')
        for field in base.ZERO_FIELDS:
            base.require(type(op.get(field)) is int and op[field] == 0,'Saved-only zero boundary differs: '+field)
        base.require(op.get('automation_status') == 'PAUSED','Automation boundary differs')
        source = next((p for p in op['source_pins'] if path_key(p['path']) == path_key(base.__file__)),None)
        base.require(source is not None and source['sha256'] == BASE_BUILDER_SHA256,
                     'Exact unchanged base builder source pin required')
        dataset = input_artifact(op,'dataset_pin')
        facts = overlay_facts(op,dataset)
        sessions = base.thin_sessions(dataset)
        base.require(len(sessions) == op['expected_sessions'] and
                     base.identity([s['session_id'] for s in sessions]) == op['session_roster_sha256'],
                     'Exact all-session report roster differs')
        del dataset
        cv = input_artifact(op,'thermal_cv_pin')
        selection = input_artifact(op,'thermal_selection_pin')
        base.require(selection.get('dataset_sha256') == op['dataset_pin']['sha256'],'Selection dataset differs')
        selected, fold_info = base.selected_cv(cv,selection,[s['session_id'] for s in sessions])
        del cv
        observers = base.observer_summary(input_artifact(op,'historical_observer_pin'))
        base.require(set(observers) == {s['session_id'] for s in sessions},'Historical observer roster differs')
        timing = base.timing_summary(input_artifact(op,'timing_cv_pin'))
        contexts = timing_contexts(op,timing,facts)
        coverage = input_artifact(op,'coverage_review_pin')
        base.require(coverage.get('artifact_bindings',{}).get('model_inputs_sha256') == DATASET_SHA256,
                     'Coverage review/model inputs binding differs')
        final_models = input_artifact(op,'final_models_pin')
        base.require(final_models.get('CV_selection_sha256') == base.identity(selection['selection']) and
                     final_models.get('fresh_confirmation') is False and final_models.get('physical_goal_pass') is False,
                     'Final model selection/role differs')
        base.require(op.get('forecast_format') == 'A24_COUNTERFACTUAL_ROWS_JSONL_V1',
                     'Registered native forecast format required for overlay report')
        registered_path(op,'forecast_pin')
        registered_path(op,'forecast_receipts_pin')
        rows = base.saved_forecast_rows(op['forecast_pin'])
        receipt_summary = base.forecast_receipt_summary(op['forecast_receipts_pin'])
        cases = base.join_forecast_case_roster(input_artifact(op,'case_status_pin'),rows,receipt_summary)
        forecasts, validations = base.native_forecast_adapter(cases)
        base.require(len(cases) == op['expected_total_forecast_cases'] and
                     sum(r['kind'] == 'PREDECLARED_NOVEL_GRID' for r in cases) == op['expected_novel_rows'] and
                     len(validations) == op['expected_validation_rows'] and
                     sum(r['kind'] == 'REGISTERED_CUSTOM' for r in cases) == op.get('expected_custom_rows',0),
                     'All-case role denominator differs')
        forecast_audit = {'heldout_schedule_validation_rows':validations,
            'all_planned_forecast_cases':len(cases),'successful_saved_forecast_rows':len(rows),
            'novel_grid_rows':sum(r['kind'] == 'PREDECLARED_NOVEL_GRID' for r in cases),
            'registered_custom_rows':sum(r['kind'] == 'REGISTERED_CUSTOM' for r in cases),
            'heldout_validation_rows':len(validations),'receipt_accounting':receipt_summary,
            'explicitly_failed_rows':sum('FAIL' in str(r.get('status','')).upper() or 'ERROR' in str(r.get('status','')).upper() for r in cases),
            'unknown_AP_mean_rows':sum(r.get('AP_mean_c') is None for r in cases),
            'status_counts':dict(base.Counter(str(r.get('status')) for r in cases)),
            'AP_status_counts':dict(base.Counter(str(r.get('AP_status')) for r in cases))}
        del rows
        for name in ('forecast_result_pin','forecast_complete_pin','effects_harms_pin','heldout_validation_pin'):
            forecast_audit[name[:-4]] = input_artifact(op,name)
        base.require(forecast_audit['forecast_result'].get('simulation_START_consumed') == receipt_summary['simulator_STARTs'],
                     'Forecast result/START receipt count differs')
        artifact_pins = {k:v for k,v in op.items() if k.endswith('_pin')}
        report = base.assemble(sessions,selected,fold_info,observers,timing,coverage,forecasts,artifact_pins,final_models,forecast_audit)
        report = augment_report(report,selected,facts,contexts,op)
        qualification_audit = input_artifact(op,'audit_contract_supplement_result_pin')
        base.require(qualification_audit['source_wait_domain_qualifications'].get('correction_contract_sha256') == op['wait_domain_correction_pin']['sha256'], 'WAIT correction artifact SHA differs')
        report = qualify_report(report, qualification_audit, input_artifact(op,'wait_domain_correction_pin'), base.saved_forecast_rows(op['forecast_pin']))
        report['audit']['wait_domain_correction_pin'] = op['wait_domain_correction_pin']
        report['audit']['contract_audit_v2_pin'] = op['audit_contract_supplement_result_pin']
        write_new(out/'REPORT_DATA.json',report)
        write_new(out/'REPORT_REQUEST_METRICS.json',[{'session_id':s['session_id'],**s['request_metrics_report']} for s in report['sessions']])
        write_new(out/'REPORT_DATA_RESULT.json',{'status':'SOURCE_BOUND_REPORT_DATA_READY_PENDING_RENDER_AND_UI_QA',
            'sessions':len(report['sessions']),'scenarios':len(report['scenarios']),
            'report_data_sha256':sha(out/'REPORT_DATA.json'),'report_value_sha256':base.identity(report),
            'source_dataset_sha256':DATASET_SHA256,'report_ROSTER_sha256':op['session_roster_sha256'],
            'timing_bank_overlay_sha256':op['timing_bank_overlay_pin']['sha256'],
            'overlay_timing_CV_present':bool(op.get('overlay_timing_cv_pin')),
            'unqualified_source_WAIT_rows':24,'all_preexisting_forecast_values_unchanged':True,'third_AP_CV_curve':'M8_ONLY','new_environment':0,'HTTP':0,'fits':0,
            'measured_J':None,'fresh_confirmation':False,'physical_goal_pass':False,
            'original_results_or_HTML_overwritten':False})
    print(base.canonical({'status':'COMPLETE','output':str(out)}))
if __name__ == '__main__':
    main()

