"""Terminal-only v3 confirmation report; immutable candidates, no fit/device API."""
from __future__ import annotations
import argparse
import copy
import csv
import html
import json
import math
from pathlib import Path
import statistics

from tools import d1_arrival_plan as p
from tools import d1_simulation_model_v2 as v2
from tools import d1_simulation_model_v2_report as old_report
from tools import d1_simulation_model_v3 as model
from tools import d1_simulation_model_v3_inputs as inputs
from tools import d1_simulation_model_v3_prediction as blind

MODELS = ('original', 'v2', 'v3')
MODES = ('A_actual_schedule', 'B_fixed_original_service')
POLICIES = ('CPU_URGENT_ONLINE_V1', 'B2_PARALLEL_ONLINE_V1',
            'B2_PARALLEL_ONLINE_V1', 'CPU_URGENT_ONLINE_V1')
V2_FILE = model.ROOT / 'docs/results/simulation_model_v2_01/run_v1/model.json'
CORE_FILES = ('validated.json', 'input_manifest.json', 'thermal.jsonl', 'host_cleanup.json',
              'artifacts/manifest.json', 'artifacts/progress.jsonl', 'artifacts/requests.json',
              'artifacts/common_boundary.json', 'artifacts/cleanup.json', 'artifacts/summary.json',
              'artifacts/warmup.json', 'artifacts/start_ap.accepted.json',
              'artifacts/start_ap.ready.json', 'artifacts/baseline.ready.json')
LIMITATIONS = [
    '개발 source 제외/중첩 검증은 고정 원모형·서비스 조건부이며 전체 가족의 완전 독립 OOF가 아니다.',
    '원모형/v2/v3를 동일 사전입력·실측·원서비스 예측일정에서 비교한다. A와 B 평균은 합치지 않는다.',
    '새 APK와 배터리 6% 허용 조건의 확인이다. 이전 APK/20% 이상 환경의 엄격 재현으로 해석하지 않는다.',
    '각 정책 2회이며 통계 유의성·타기기 일반화·실제 정책 효과는 판정하지 않는다.',
    '전류 mA 해석의 기기 전체 에너지이며 절대 전류 교정과 정책 우월성은 별도 검증이다.',
    '서비스는 원모형에 고정해 v3의 처리시간/P95 예측 개선을 주장하지 않는다.',
    '열→속도 동적 연결·확률적 실패 모형은 미검증이며 기본/RL/strict/experiment_ready=false를 유지한다.',
]


def _write(folder, name, value):
    model.write(Path(folder) / name, value)


def _csv(folder, name, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (Path(folder) / name).open('x', encoding='utf8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader(); writer.writerows(rows)


def _hash(path, hashes, expected=None):
    path = Path(path)
    digest = p.digest(path)
    if expected is not None and digest != expected:
        raise ValueError('frozen source hash drift: ' + str(path))
    hashes[str(path.resolve())] = digest
    return digest


def _model_guard(plan, run, hashes, allow_missing_local=False):
    prior = plan['prior_freeze']
    source = Path(prior['path'])
    _hash(source, hashes, prior['sha256'])
    local = Path(run) / 'development_freeze.json'
    if local.is_file():
        _hash(local, hashes, prior['sha256'])
        receipt_path = Path(run) / 'freeze_receipt.json'
        _hash(receipt_path, hashes)
        if p.read(receipt_path)['sha256'] != prior['sha256']:
            raise ValueError('local freeze receipt mismatch')
    elif allow_missing_local:
        local = source  # A preflight failure can occur before any local copy.
    else:
        raise ValueError('local frozen model is missing')
    frozen = p.read(local)
    if not frozen.get('confirmation_fit_forbidden'):
        raise ValueError('confirmation refitting was not prohibited')
    candidate = frozen['model']
    if candidate['version'] != model.VERSION or candidate.get('experiment_ready') is not False:
        raise ValueError('candidate identity/readiness drift')
    if len(candidate['development_ids']) != 17 or any(n.startswith(('confirmation_', 'blind_confirmation_', 'sustained_')) for n in candidate['development_ids']):
        raise ValueError('development roster contains confirmation')
    for name, expected in frozen['source_code'].items():
        _hash(model.ROOT / name, hashes, expected)
    for name, expected in frozen['source_inventory']['files'].items():
        _hash(name, hashes, expected)
    for name, expected in plan['source_code'].items():
        _hash(model.ROOT / name, hashes, expected)
    original_spec = plan['original_model']
    _hash(original_spec['path'], hashes, original_spec['sha256'])
    if original_spec['sha256'] != v2.prior.MODEL_SHA or candidate['original_model']['sha256'] != original_spec['sha256']:
        raise ValueError('original model identity drift')
    if candidate['service'] != dict(mode='frozen_original_forecast', sha256=v2.prior.MODEL_SHA):
        raise ValueError('service was changed after development')
    development_receipt = source.parent / 'freeze_receipt.json'
    _hash(development_receipt, hashes)
    if p.read(development_receipt)['sha256'] != prior['sha256']:
        raise ValueError('development freeze receipt mismatch')
    development_model = source.parent / 'model.json'
    _hash(development_model, hashes)
    if p.read(development_model) != candidate:
        raise ValueError('exported numerical model differs from freeze')
    registration_path = source.parent / 'registration.json'
    _hash(registration_path, hashes)
    registration = p.read(registration_path)
    _hash(V2_FILE, hashes, registration['reference_v2_sha256'])
    for key in ('analysis_contract', 'measurement_amendment', 'observation_repair_contract'):
        if plan.get(key):
            _hash(plan[key]['path'], hashes, plan[key]['sha256'])
    if frozen['plan_sha256'] != plan['analysis_contract']['sha256']:
        raise ValueError('registered development contract differs')
    return frozen, p.read(original_spec['path']), p.read(V2_FILE)


def forecast_service(legacy):
    result = {}
    for priority in ('urgent', 'normal'):
        rows = [r for r in legacy['ledger'] if r['priority'] == priority]
        values = sorted(r['response_ns']/1e6 for r in rows
                        if r['status'] == 'succeeded' and r.get('response_ns') is not None)
        completed = sum(r['status'] == 'succeeded' for r in rows)
        timely = sum(r['status'] == 'succeeded' and r.get('response_ns', math.inf) <= r['deadline_offset_ns'] for r in rows)
        n = len(rows)
        result[priority] = dict(planned=n, completed=completed, timely=timely,
            response_P95_ms=values[math.ceil(.95*len(values))-1] if values else None,
            completion_success_rate=completed/n if n else None,
            timely_success_rate=timely/n if n else None,
            service_success_rate=timely/n if n else None,
            terminal_counts={s: sum(r['status'] == s for r in rows)
                             for s in ('succeeded', 'failed', 'rejected', 'expired', 'unfinished', 'not_arrived')})
    return result


def _score(c, values, predicted_j):
    row = v2.prior.base.common.score(c['ap'], values)
    observed_j = v2.prior.integral(c, 0, 120)
    signed = predicted_j-observed_j
    return dict(row, peak_abs_error_c=abs(row['peak_signed_error_c']),
                observed_J120_j=observed_j, predicted_J120_j=predicted_j,
                J120_signed_j=signed, J120_abs_j=abs(signed))


def evaluate_case(c, manifest, candidate, original, previous):
    """Targets score predictions; only the public whitelist reaches B forecast."""
    if c['role'] != 'confirmation' or c['manifest_requests'] != manifest['requests']:
        raise ValueError('exact confirmation role/planned requests mismatch')
    policy = manifest['policy']
    public = inputs.public_input(c)
    prediction = blind.forecast(public, manifest['requests'], policy, candidate, original)
    actual_scoped = dict(public, actual=c['actual'])
    first = model.cost_assessment(c, candidate, original, actual_scoped)
    second = v2.assess(c, previous, original)
    original_ap = v2.prior.thermal.predict(v2.prior.case_input(c, c['actual']), original['ap'])[0]
    actual_ap = dict(original=original_ap, v2=second['predicted_AP_c'], v3=first['predicted_AP_c'])
    actual_j = dict(original=v2.energy_at(c, original, 120), v2=v2.energy_at(c, previous, 120),
                   v3=first['scores']['120s_energy_signed_j']+v2.prior.integral(c, 0, 120))
    shared = dict(public, actual=prediction['segments'])
    middle_ap = v2.ap_prediction(shared, previous)[0]
    predicted_ap = dict(original=prediction['original_AP_c'], v2=middle_ap,
                        v3=prediction['predicted_AP_c'])
    predicted_j = dict(original=prediction['original_J120'],
                       v2=v2.energy_at(shared, previous, 120), v3=prediction['predicted_J120'])
    scores, curves = [], []
    for mode, paths, joules in ((MODES[0], actual_ap, actual_j), (MODES[1], predicted_ap, predicted_j)):
        for name in MODELS:
            scores.append(dict(session=c['id'], policy=policy, mode=mode, model=name,
                               **_score(c, paths[name], joules[name])))
        for index, t in enumerate(c['q']):
            curves.append(dict(session=c['id'], policy=policy, mode=mode, time_s=t,
                observed_AP_c=c['ap'][index], original_AP_c=paths['original'][index],
                v2_AP_c=paths['v2'][index], v3_AP_c=paths['v3'][index]))
    observed = old_report.actual_service(c)
    predicted = forecast_service(prediction['legacy'])
    service_rows = []
    for priority in ('urgent', 'normal'):
        a, b = observed[priority], predicted[priority]
        service_rows.append(dict(session=c['id'], policy=policy, priority=priority, planned=a['planned'],
            observed_completed=a['completed'], observed_timely=a['timely'],
            observed_completion_rate=a['completion_success_rate'], observed_timely_rate=a['timely_success_rate'],
            observed_P95_ms=a['response_P95_ms'], original_and_v3_P95_ms=b['response_P95_ms'],
            P95_abs_error_ms=abs(b['response_P95_ms']-a['response_P95_ms']) if a['response_P95_ms'] is not None and b['response_P95_ms'] is not None else None,
            predicted_completed=b['completed'], predicted_timely=b['timely'],
            predicted_completion_rate=b['completion_success_rate'], predicted_timely_rate=b['timely_success_rate'],
            service_scope='frozen original service; v3 and v2 cost-control use exactly the same ledger'))
    auxiliary = old_report.arrival_assessment(c, previous, original)
    return dict(scores=scores, curves=curves, forecast=prediction,
                observed_service=observed, forecast_service=predicted, service_rows=service_rows,
                v2_own_service_auxiliary=auxiliary,
                auxiliary_scope='v2 own five-phase service schedule: supplementary; excluded from primary same-service comparison')


def aggregate_scores(rows, roster):
    planned = len(roster)
    validated = sum(r['status'] == 'validated' for r in roster)
    out = dict(planned_sessions=planned, validated_sessions=validated,
               missing_sessions=planned-validated, all_four_validated=planned == 4 and validated == 4,
               missing_measurements_are_not_zero=True, joint_cost_error_decrease_pass=None,
               primary_mode=MODES[1], modes={})
    def summarize(use):
        if len({r['session'] for r in use}) != len(use):
            raise ValueError('duplicate model/session score rows')
        return dict(evaluated_sessions=len(use),
            mean_AP_MAE_c=statistics.mean(r['mae_c'] for r in use),
            mean_J120_abs_j=statistics.mean(r['J120_abs_j'] for r in use),
            mean_J120_signed_j=statistics.mean(r['J120_signed_j'] for r in use),
            worst_AP_MAE_c=max(r['mae_c'] for r in use),
            worst_AP_max_error_c=max(r['max_absolute_error_c'] for r in use),
            worst_J120_abs_j=max(r['J120_abs_j'] for r in use))
    for mode in MODES:
        data = [r for r in rows if r['mode'] == mode]
        total = {name: summarize([r for r in data if r['model'] == name]) for name in MODELS if any(r['model'] == name for r in data)}
        by_policy = {}
        for policy in sorted(set(POLICIES)):
            by_policy[policy] = {name: summarize([r for r in data if r['model'] == name and r['policy'] == policy])
                                for name in MODELS if any(r['model'] == name and r['policy'] == policy for r in data)}
        out['modes'][mode] = dict(overall=total, by_policy=by_policy)
    if out['all_four_validated']:
        primary = out['modes'][MODES[1]]['overall']
        if any(primary.get(name, {}).get('evaluated_sessions') != 4 for name in MODELS):
            raise ValueError('four valid sessions require every fixed candidate score')
        ap = primary['v3']['mean_AP_MAE_c'] < primary['original']['mean_AP_MAE_c']
        joules = primary['v3']['mean_J120_abs_j'] < primary['original']['mean_J120_abs_j']
        out.update(AP_mean_improved=ap, J120_mean_improved=joules,
                   joint_cost_error_decrease_pass=ap and joules)
    out['comparison_rule'] = 'four valid new sessions; session equal B AP MAE and absolute J120 must BOTH strictly decrease versus original; A and B never pooled'
    return out


def development_readout(frozen):
    rows = []
    for fold in frozen['nested']:
        for name, key in (('nested_v3', 'held_rows'), ('original_prior', 'baseline_rows')):
            for r in fold[key]:
                rows.append(dict(session=r['id'], source=r['group'], mode=r['mode'], head=fold['head'],
                    model=name, error=r['error'], unit='degree_C_path_MAE' if fold['head'] == 'thermal' else 'J120_absolute',
                    selected_parameters=json.dumps(fold['inner_selected']['choice'], sort_keys=True)))
    summary = []
    for head in ('thermal', 'energy'):
        for name in ('original_prior', 'nested_v3'):
            for mode in ('A', 'B'):
                use = [r for r in rows if (r['head'], r['model'], r['mode']) == (head, name, mode)]
                if not use:
                    continue
                per = {g: statistics.mean(r['error'] for r in use if r['source'] == g) for g in sorted({r['source'] for r in use})}
                summary.append(dict(head=head, model=name, mode=mode, session_count=len(use),
                    source_equal_mean=statistics.mean(per.values()), worst_source=max(per.values()),
                    worst_session=max(r['error'] for r in use), per_source=per))
    return dict(scope='fixed historical prior/service conditional nested development evaluation; not full-family/service independent OOF',
                rows=rows, summaries=summary, fit_calls=frozen['fit_calls'],
                final_choices={k: r['selected']['choice'] for k, r in frozen['selection'].items()},
                confirmation_used_for_selection=False)


def _appendix(plan, hashes):
    if not plan.get('prior_failure_receipt'):
        return []
    spec = plan['prior_failure_receipt']
    _hash(spec['path'], hashes, spec['sha256'])
    receipt = p.read(spec['path'])
    folder = Path(spec['path']).parent
    evidence = {}
    for pattern in ('*/attempt.json', '*/launch_attempt.json', '*/partial_progress.json',
                    '*/recovery_prefix/*.json', '*/recovery_prefix/progress.jsonl',
                    '*/artifacts/*failure.json', '*/host_cleanup.json'):
        for path in sorted(folder.glob(pattern)):
            evidence[str(path)] = _hash(path, hashes)
    return [dict(kind='preserved_premeasurement_wireless_thermal_2s_timeout',
                 source=spec['path'], sha256=spec['sha256'], receipt=receipt, evidence_sha256=evidence,
                 measured_sessions_reused=0, failed_attempt_is_not_completed_confirmation=True)]


def report(run, output):
    run, output = Path(run).resolve(), Path(output).resolve()
    terminal = run / 'FINAL_RECEIPT.json'
    if not terminal.is_file():
        raise ValueError('active run: FINAL_RECEIPT.json required before reporting')
    if output.exists():
        raise ValueError('new report output required; original report is immutable')
    hashes = {}; _hash(terminal, hashes)
    receipt = p.read(terminal)
    if receipt.get('status') not in ('completed_regimen_diagnostic_only', 'stopped_no_resume'):
        raise ValueError('unsupported terminal receipt')
    plan_file = run.parent / 'plan/collection_plan.json'
    _hash(plan_file, hashes); plan = p.read(plan_file)
    if not plan.get('simulation_model_v3') or len(plan['entries']) != 4 or len({e['session_id'] for e in plan['entries']}) != 4:
        raise ValueError('registered four new confirmation roster required')
    frozen, original, previous = _model_guard(plan, run, hashes,
        allow_missing_local=receipt['status']=='stopped_no_resume' and receipt.get('completed_sessions')==0)
    candidate = frozen['model']
    if receipt.get('post_confirmation_fit_calls', 0) != 0:
        raise ValueError('post-confirmation fitting forbidden')
    if receipt.get('preserved_freeze_sha256', plan['prior_freeze']['sha256']) != plan['prior_freeze']['sha256']:
        raise ValueError('terminal numerical freeze mismatch')
    sessions, metrics, curves, services, forecasts = [], [], [], [], []
    core_inventory = {}
    for e, policy in zip(plan['entries'], POLICIES):
        if e['index'] != len(sessions) or e['role'] != 'confirmation' or e.get('completed_reuse'):
            raise ValueError('fixed fresh confirmation index/role')
        manifest_path = plan_file.parent / e['manifest']
        _hash(manifest_path, hashes, e['manifest_sha256']); manifest = p.read(manifest_path)
        if (manifest['policy'] != policy or manifest['session_id'] != e['session_id']
                or manifest['apk_sha256'] != plan['apk_sha256'] or len(manifest['requests']) != 96):
            raise ValueError('fixed policy/planned request denominator')
        from tools import d1_separated_power_protocol as separated
        separated.validate('confirmation', manifest['requests'])
        folder = run / f"{e['index']:02d}_{e['session_id']}"
        row = dict(index=e['index'], session=manifest['phase'], session_id=e['session_id'],
                   policy=policy, planned_requests=len(manifest['requests']), role=e['role'],
                   status='not_validated', observed_completed=None, observed_timely=None,
                   battery_scope=None, APK=manifest['apk_sha256'])
        core = {name: _hash(folder/name, hashes) if (folder/name).is_file() else None for name in CORE_FILES}
        for path in sorted(folder.glob('artifacts/*failure.json')):
            core[str(path.relative_to(folder))] = _hash(path, hashes)
        core_inventory[manifest['phase']] = core
        if (folder/'validated.json').is_file():
            required = ('input_manifest.json', 'thermal.jsonl', 'host_cleanup.json',
                        'artifacts/manifest.json', 'artifacts/progress.jsonl', 'artifacts/requests.json',
                        'artifacts/common_boundary.json', 'artifacts/cleanup.json')
            if any(core[name] is None for name in required):
                raise ValueError('validated session missing core raw source')
            _hash(folder/'input_manifest.json', hashes, e['manifest_sha256'])
            _hash(folder/'artifacts/manifest.json', hashes, e['manifest_sha256'])
            stats = p.read(folder/'validated.json'); c = stats['analysis_case']
            if c['id'] != manifest['phase'] or c['role'] != 'confirmation' or c['manifest_requests'] != manifest['requests']:
                raise ValueError('derived case/manifest role mismatch')
            if p.read(folder/'artifacts/requests.json') != c['actual_requests'] or len(c['actual_requests']) != 96:
                raise ValueError('raw request/analysis full denominator mismatch')
            if {r['request_id'] for r in c['actual_requests']} != {r['request_id'] for r in manifest['requests']}:
                raise ValueError('native completed request IDs differ from planned tickets')
            if (stats['work_calls'], stats['warmup_calls'], stats['eligibility_calls']) != (96, 8, 0):
                raise ValueError('native work/warmup/eligibility denominator drift')
            events = [json.loads(line) for line in (folder/'artifacts/progress.jsonl').read_text(encoding='utf8').splitlines()]
            if not events or any(event['session_id'] != e['session_id'] for event in events):
                raise ValueError('native journal session ownership mismatch')
            if p.read(folder/'artifacts/common_boundary.json')['start_ns'] != c['origin_ns']:
                raise ValueError('analysis clock differs from raw common origin')
            from tools import d1_resident_identification_analysis as raw_reader
            reconstructed = raw_reader.arrival_case(folder/'artifacts', manifest)
            fields = ('pre', 'pre_w', 'q', 'ap', 'actual', 'power_t', 'power_w', 'common_end_s')
            if any(c[k] != reconstructed[k] for k in fields):
                raise ValueError('derived AP/power/schedule differs from native raw source')
            if p.read(folder/'artifacts/cleanup.json')['status'] != 'completed':
                raise ValueError('validated session has incomplete native cleanup')
            if any(folder.glob('artifacts/*failure.json')):
                raise ValueError('new validated session contains app failure evidence')
            evaluated = evaluate_case(c, manifest, candidate, original, previous)
            metrics.extend(evaluated['scores']); curves.extend(evaluated['curves']); services.extend(evaluated['service_rows'])
            forecasts.append(dict(session=c['id'], policy=policy, **evaluated))
            row.update(status='validated', observed_completed=sum(v['completed'] for v in evaluated['observed_service'].values()),
                observed_timely=sum(v['timely'] for v in evaluated['observed_service'].values()),
                battery_scope=stats.get('battery_scope'), initial_AP_c=c['pre'][-1]['ap'],
                initial_power_w=c['pre_w'], initial_late_power_w=inputs.public_input(c).get('initial_power_late_w'),
                application_lifecycle_pass=stats.get('application_lifecycle_pass'),
                native_cleanup_status='completed', raw_requests=stats['work_calls'], warmup=stats['warmup_calls'])
        elif folder.exists():
            row['status'] = 'attempted_not_validated'
        sessions.append(row)
    declared = receipt.get('sessions', receipt.get('completed_sessions'))
    validated = sum(r['status'] == 'validated' for r in sessions)
    if declared != validated or (receipt['status'].startswith('completed_') and validated != 4):
        raise ValueError('terminal receipt/validated roster disagree')
    aggregate = aggregate_scores(metrics, sessions)
    development = development_readout(frozen)
    appendix = _appendix(plan, hashes)
    _hash(Path(__file__), hashes)
    _hash(Path(old_report.__file__), hashes)
    planned_requests = sum(r['planned_requests'] for r in sessions)
    confirmed = sum(r['observed_completed'] for r in sessions if r['observed_completed'] is not None)
    timely = sum(r['observed_timely'] for r in sessions if r['observed_timely'] is not None)
    battery = [r['battery_scope'] for r in sessions if r['battery_scope'] is not None]
    environment = dict(native_APK_sha256=plan['apk_sha256'], admitted_minimum_percent=plan.get('battery_min_percent', 20),
        minimum_observed_percent=min(r['minimum_observed_percent'] for r in battery) if battery else None,
        any_below20=any(r['any_below20'] for r in battery) if battery else None,
        power_save_mode_observed=any(r['power_save_mode_observed'] for r in battery) if battery else None,
        scope='new low-battery diagnostic APK/opt-in6%; not same-APK strict replication of original20% environment')
    summary = dict(version=model.VERSION, terminal_receipt=receipt, session_roster=sessions,
        comparison=aggregate, metrics=metrics, service_rows=services, forecasts=forecasts,
        planned_requests=planned_requests, confirmed_completed_requests=confirmed, confirmed_timely_requests=timely,
        unvalidated_planned_requests=sum(r['planned_requests'] for r in sessions if r['status'] != 'validated'),
        confirmed_completion_lower_bound_rate=confirmed/planned_requests,
        confirmed_timely_lower_bound_rate=timely/planned_requests,
        missing_raw_completions_are_unknown_not_failures=True, environment=environment,
        development_nested=development, failure_appendix=appendix,
        frozen_model_sha256=plan['prior_freeze']['sha256'], source_hashes=hashes,
        core_raw_sha256=core_inventory, post_confirmation_fit_calls=0,
        independent_new_measurement=validated>0, planned_independent_confirmations=4,
        local_freeze_was_copied=(run/'development_freeze.json').is_file(),
        default=False, strict_support=False, experiment_ready=False,
        accuracy_pass=None, limitations=LIMITATIONS,
        model_sha256=p.digest(Path(plan['prior_freeze']['path']).parent/'model.json'),
        primary_v2_control='v2 cost coefficients on original fixed service schedule; own v2 service is auxiliary only')
    summary['measurement_contract'] = {key: copy.deepcopy(plan[key]) for key in (
        'experiment_id', 'budget', 'original_deadline_monotonic', 'cumulative_amendment',
        'measurement_protocol_change', 'thermal_timeout_seconds') if key in plan}
    summary['source_document_paths'] = {name: str(model.ROOT/'docs'/name) for name in (
        'SIMULATION_MODEL_V3_PLAN_20261010.md', 'SIMULATION_MODEL_V3_EXPERT_MEETING_20261010.md',
        'SIMULATION_MODEL_V3_LOW_BATTERY_20261010.md', 'SIMULATION_MODEL_V3_OBSERVATION_REPAIR_20261010.md')}
    output.mkdir(parents=True)
    for name, rows in (('sessions.csv', sessions), ('cost_scores.csv', metrics), ('AP_curves.csv', curves),
                       ('service_scores.csv', services), ('development_nested_scores.csv', development['rows'])):
        _csv(output, name, rows)
    _write(output, 'summary.json', summary); _write(output, 'model.json', candidate)
    freeze_export_source = run/'development_freeze.json' if (run/'development_freeze.json').is_file() else Path(plan['prior_freeze']['path'])
    with (output/'development_freeze.json').open('xb') as handle:
        handle.write(freeze_export_source.read_bytes())
    if p.read(output/'model.json') != candidate or p.digest(output/'development_freeze.json') != plan['prior_freeze']['sha256']:
        raise ValueError('report numerical model export changed')
    _write(output, 'export_receipt.json', dict(model_sha256=p.digest(output/'model.json'),
        development_freeze_sha256=p.digest(output/'development_freeze.json'), numerical_dictionary_equal=True,
        fit_calls=0, device_commands=0, source_hashes=hashes))
    figures = plots(output, sessions, curves, metrics, services)
    (output/'index.html').write_text(page(summary, figures), encoding='utf8')
    return dict(status=receipt['status'], planned=4, validated=validated,
                joint_cost_error_decrease_pass=aggregate['joint_cost_error_decrease_pass'],
                model_sha256=p.digest(output/'model.json'), report=str(output/'index.html'), fit_calls=0, device_commands=0)


def plots(folder, sessions, curves, metrics, services):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'Malgun Gothic', 'axes.unicode_minus': False})
    colors = dict(original='#a16207', v2='#64748b', v3='#0e7490')
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, session in zip(axes.flat, sessions):
        rows = [r for r in curves if r['session'] == session['session'] and r['mode'] == MODES[1]]
        if rows:
            times = [r['time_s'] for r in rows]
            ax.plot(times, [r['observed_AP_c'] for r in rows], color='black', label='관측', lw=1.8)
            for name in MODELS:
                ax.plot(times, [r[name+'_AP_c'] for r in rows], label=name, color=colors[name], lw=1.2)
            ax.legend()
        else:
            ax.text(.5, .5, '검증된 계측 없음', transform=ax.transAxes, ha='center')
        ax.set_title(f"{session['index']+1}: {'CPU' if session['policy']==POLICIES[0] else 'PAR'}")
        ax.set_xlabel('공통 원점 이후 초'); ax.set_ylabel('HAL AP °C')
    fig.suptitle('새 확인4 · 예정 도착 B · 세 모형 동일 원서비스 일정'); fig.tight_layout()
    fig.savefig(folder/'AP_paths.png', dpi=140); plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 4))
    for j, name in enumerate(MODELS):
        xs, ys = [], []
        for session in sessions:
            row = next((r for r in metrics if r['session']==session['session'] and r['mode']==MODES[1] and r['model']==name), None)
            if row is not None:
                xs.append(session['index']+(j-1)*.24); ys.append(row['J120_abs_j'])
        ax.bar(xs, ys, width=.23, label=name, color=colors[name])
    ax.set_xticks(range(4), [f"{r['index']+1} {'CPU' if r['policy']==POLICIES[0] else 'PAR'}" for r in sessions])
    ax.set_ylabel('|예측-관측| J / 0..120초'); ax.set_title('B 에너지 절대오차 · 결측은 막대를 만들지 않음'); ax.legend()
    fig.tight_layout(); fig.savefig(folder/'energy_error.png', dpi=140); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, priority in zip(axes, ('urgent', 'normal')):
        use = [r for r in services if r['priority']==priority]
        for name, key, shift, color in (('실측', 'observed_P95_ms', -.14, '#111827'),
                ('원서비스 = v3', 'original_and_v3_P95_ms', .14, '#0e7490')):
            ax.bar([next(s['index'] for s in sessions if s['session']==r['session'])+shift for r in use],
                   [r[key] for r in use], width=.28, label=name, color=color)
        ax.set_xticks(range(4), [str(r['index']+1) for r in sessions]); ax.set_title('긴급 분류' if priority=='urgent' else '일반 탐지')
        ax.set_ylabel('완료 응답 P95 ms'); ax.set_xlabel('예정 확인 세션'); ax.legend()
    fig.suptitle('서비스는 동결 원모형 그대로 · 비용 보정으로 처리시간 개선 주장 없음')
    fig.tight_layout(); fig.savefig(folder/'service_P95.png', dpi=140); plt.close(fig)
    return ['AP_paths.png', 'energy_error.png', 'service_P95.png']


def page(summary, figures):
    e = html.escape
    comparison = summary['comparison']
    outcome = comparison['joint_cost_error_decrease_pass']
    title = '새4 확인의 두 비용 평균 감소' if outcome is True else '새4 확인에서 두 비용 평균 감소 불충족' if outcome is False else '확인4 미완료 · 개선 판정 보류'
    def table(rows, keys):
        return '<table><tr>'+''.join('<th>'+e(k)+'</th>' for k in keys)+'</tr>'+''.join('<tr>'+''.join('<td>'+e(str(round(r[k],5) if isinstance(r.get(k), float) else r.get(k, '')) )+'</td>' for k in keys)+'</tr>' for r in rows)+'</table>'
    score_rows = []
    for mode in MODES:
        for name, row in comparison['modes'][mode]['overall'].items():
            score_rows.append(dict(mode=mode, model=name, **row))
    docs = [('사전 모형 계획', '../../../SIMULATION_MODEL_V3_PLAN_20261010.md'),
            ('전문가 토론', '../../../SIMULATION_MODEL_V3_EXPERT_MEETING_20261010.md'),
            ('배터리 환경 개정', '../../../SIMULATION_MODEL_V3_LOW_BATTERY_20261010.md'),
            ('관측 timeout 수정', '../../../SIMULATION_MODEL_V3_OBSERVATION_REPAIR_20261010.md')]
    links = [('전체 수치·근거', 'summary.json'), ('동결 새 모형', 'model.json'), ('동결 증거', 'development_freeze.json'),
             ('전체4 세션', 'sessions.csv'), ('A/B 비용 오차', 'cost_scores.csv'), ('서비스·전체 도착 분모', 'service_scores.csv'),
             ('조건부 중첩 개발 평가', 'development_nested_scores.csv')]
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><title>D1Check 시뮬레이션 v3 확인</title><style>body{font:16px system-ui;margin:28px;max-width:1250px;color:#17212c}table{border-collapse:collapse;margin:16px 0}th,td{border:1px solid #ccc;padding:7px;text-align:right}img{max-width:100%}.scroll{overflow:auto}.note{background:#eef2ff;padding:14px}</style><h1>새 시뮬레이션 v3 확인</h1><h2>'+e(title)+'</h2><p class="note">계수·선택·원서비스는 새 계측 전에 동결했습니다. 기본 모형 채택·정책 효과·절대 에너지 교정은 별도입니다. 새 APK와 배터리6% 허용 조건을 기록하며 이전20% 이상 환경의 엄격 재현으로 표시하지 않습니다.</p><p>'+ ' · '.join('<a href="'+e(url)+'">'+e(text)+'</a>' for text,url in links)+'</p><p>'+ ' · '.join('<a href="'+e(url)+'">'+e(text)+'</a>' for text,url in docs)+'</p><h2>전체 예정4 · 검증'+str(comparison['validated_sessions'])+'</h2>'+table(summary['session_roster'], ('index','policy','status','planned_requests','observed_completed','observed_timely'))+'<h2>A와 B의 평균 · 세션마다 같은 비중</h2><p>A는 실제 일정 입력의 조건부 오차입니다. B는 예정 도착부터의 예측이며 세 모형 모두 동일한 원서비스 일정을 씁니다. 두 범위 평균을 합치지 않습니다. v2 자체서비스 예측은 summary의 보조 결과로만 제공합니다.</p><div class="scroll">'+table(score_rows, ('mode','model','evaluated_sessions','mean_AP_MAE_c','mean_J120_abs_j','worst_AP_MAE_c','worst_J120_abs_j'))+'</div><p>정책별2·최악 세션·잔차는 summary.json 및 CSV에 모두 남깁니다. 검증되지 않은 계측의 오차를0으로 채우지 않습니다.</p><h2>배터리·절전·실패 기록</h2><pre>'+e(json.dumps(summary['environment'],ensure_ascii=False,indent=2))+'</pre><p>원2초 thermal timeout 시도는 '+str(len(summary['failure_appendix']))+'건의 별도 부록으로 보존했습니다. 실패 시도를 완료 확인으로 합치지 않습니다.</p>'+''.join('<img src="'+e(f)+'" alt="'+e(f)+'">' for f in figures)+'<h2>검증 한계</h2><ul>'+''.join('<li>'+e(v)+'</li>' for v in LIMITATIONS)+'</ul></html>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(report(args.run, args.output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
