"""Read-only decision on whether existing evidence certifies fixed-calendar gains.

Historical paired errors are descriptive and never imported as a universal
coefficient bound, noise model or significance threshold for a different input.
"""
import argparse
import csv
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
import subprocess
from tools import d1_joint_gain_sensitivity as sensitivity

P = sensitivity.P
ROOT = sensitivity.ROOT


def historical_pairs(rows):
    keys = [(r['index'], r['prediction']) for r in rows]
    layers = ('actual_schedule_conditional', 'arrival_forecast')
    if len(rows) != 16 or len(set(keys)) != 16 or {r['prediction'] for r in rows} != set(layers):
        raise ValueError('all eight sessions and both prediction layers required')
    result = []
    for layer in layers:
        for pair in range(4):
            members = [r for r in rows if r['prediction'] == layer and r['pair'] == pair]
            by_policy = {r['policy']: r for r in members}
            if len(members) != 2 or set(by_policy) != {'CPU_URGENT_ONLINE_V1', 'B2_PARALLEL_ONLINE_V1'}:
                raise ValueError('complete same-pair CPU/PAR denominator required')
            cpu, par = by_policy['CPU_URGENT_ONLINE_V1'], by_policy['B2_PARALLEL_ONLINE_V1']
            for row in members:
                if row['planned'] != 192 or row['actual_deadline_met'] != 192:
                    raise ValueError('historical complete service denominator changed')
                for field in ('observed_120s_j', 'predicted_120s_j', 'energy_signed_error_j',
                              'observed_peak_ap_c', 'predicted_peak_ap_c', 'preload_power_w', 'common_start_ap_c'):
                    if not math.isfinite(row[field]): raise ValueError('finite historical evidence required')
                if abs(row['predicted_120s_j']-row['observed_120s_j']-row['energy_signed_error_j']) > 1e-8:
                    raise ValueError('historical signed energy identity mismatch')
            observed = par['observed_120s_j']-cpu['observed_120s_j']
            predicted = par['predicted_120s_j']-cpu['predicted_120s_j']
            peak_observed = par['observed_peak_ap_c']-cpu['observed_peak_ap_c']
            peak_predicted = par['predicted_peak_ap_c']-cpu['predicted_peak_ap_c']
            result.append(dict(pair=pair, prediction=layer, requests_per_session=192,
                observed_par_minus_cpu_j=observed, predicted_par_minus_cpu_j=predicted,
                paired_signed_prediction_error_j=predicted-observed,
                observed_peak_difference_c=peak_observed, predicted_peak_difference_c=peak_predicted,
                paired_peak_prediction_error_c=peak_predicted-peak_observed,
                cpu_ap_observed_start_s=cpu['ap_window_start_s'], cpu_ap_observed_end_s=cpu['ap_window_end_s'],
                par_ap_observed_start_s=par['ap_window_start_s'], par_ap_observed_end_s=par['ap_window_end_s'],
                AP_peak_boundary='saved session-specific valid host AP sample windows, not uniform 35..180 grid',
                initial_ap_difference_c=par['common_start_ap_c']-cpu['common_start_ap_c'],
                modeled_preload_background_difference_j=120.*(par['preload_power_w']-cpu['preload_power_w']),
                universal_energy_error_bound_j=None, universal_coefficient_error_bound_w=None,
                error_transfer_to_48_requests_validated=False, independent_pairs=4,
                background_subtracted_from_observation=False))
    return result


def analyze():
    # Reuse the authenticated fixed schedules, no new simulator/optimizer calls.
    precision = sensitivity.analyze()
    summary_path = P.BUNDLE/'summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf8'))
    if summary['model_sha256'] != P.MODEL_SHA or P.digest(P.BUNDLE/'model.json') != P.MODEL_SHA:
        raise ValueError('exact frozen model identity required')
    if summary['planned_sessions'] != 8 or summary['prediction_eligible_sessions'] != 8:
        raise ValueError('historical eight-session evidence changed')
    pairs = historical_pairs(summary['metrics'])
    # Preserve the old pair CSV's actual layer: it uses arrival forecast, not A.
    csv_path = P.BUNDLE/'pair_differences.csv'
    with csv_path.open(encoding='utf8', newline='') as file: previous = list(csv.DictReader(file))
    forecast = [r for r in pairs if r['prediction'] == 'arrival_forecast']
    if len(previous) != 4: raise ValueError('historical paired CSV denominator changed')
    for old, row in zip(previous, forecast):
        if int(old['pair']) != row['pair'] or old['complete'] != 'True': raise ValueError('pair CSV identity mismatch')
        for field in ('observed_par_minus_cpu_j', 'predicted_par_minus_cpu_j'):
            if abs(float(old[field])-row[field]) > 1e-8: raise ValueError('pair CSV numerical mismatch')
    requirements = []
    for row in precision['rows']:
        requirements.append(dict(envelope=row['envelope'], seed=row['seed'], context=row['context'],
            solver_status=row['status'], modeled_J_gain_j=row['modeled_J_gain_j'],
            exposure_l1_s=row['exposure_l1_s'],
            coefficient_error_break_even_w=row['uniform_increment_error_break_even_w'],
            coefficient_error_bound_observed_w=None, differential_controller_energy_observed_j=None,
            independent_AP_difference_accuracy_known=False, source_request_count=48,
            device_certification='not_computable' if row['modeled_J_gain_j'] is None else 'not_established',
            missing='integer incumbent' if row['modeled_J_gain_j'] is None else
                'same-input paired difference uncertainty; model route needs coefficient uncertainty and controller cost, direct pair route includes controller cost in whole-device J; AP difference accuracy',
            stopping_rule='no gain claim until whole-window same-input effect is distinguishable; data eligibility and accuracy remain separate'))
    paths = [summary_path, csv_path, P.BUNDLE/'model.json', P.BUNDLE/'initial_inputs.json']
    return dict(version='joint-evidence-requirements-v1', historical_pairs=pairs, requirements=requirements,
        energy_fit_rmse_j=json.loads((P.BUNDLE/'model.json').read_text(encoding='utf8'))['energy_fit_rmse_j'],
        fit_rmse_is_not_coefficient_bound=True, paired_errors_are_not_universal_bound=True,
        new_simulations=0, coefficient_refits=0, new_device_plan=False, device_commands=0,
        experiment_ready=False, goal_achieved=False,
        recommendation='EFT baseline and deadline-constrained objective-specific Pareto; physical joint advantage remains unproven',
        minimum_question='can the fixed same-input calendar improve both whole-window J and AP against EFT after actual controller cost, without violating all-arrival deadlines?',
        routes=dict(direct_pair='whole-device same-input paired J/AP includes actual controller cost; descriptive pair is not variance proof or dynamic-model validation',
                    model_based='bound incremental coefficient uncertainty plus differential controller cost and independently assess AP difference prediction',
                    online_policy='fixed future-known calendars never certify a causal online policy'),
        unknown_budget_items=['paired repetitions for precision', 'phone controller time/energy', 'coefficient uncertainty', '48-request AP prediction uncertainty'],
        do_not_create='new measurement claim, new APK, automatic retry or post-result accuracy margin',
        resources={**precision['resources'], **{p.relative_to(P.ROOT).as_posix():P.digest(p) for p in paths}})


def save(result, output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    P.write(out/'analysis_manifest.json', dict(utc_after_analysis=datetime.now(timezone.utc).isoformat(),
        base_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),source_dirty=True,
        retrospective_readout=True, source_sha256=P.digest(__file__), resources=result['resources']))
    P.write(out/'result.json', result)
    (out/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
    for filename, rows in [('historical_pairs.csv',result['historical_pairs']),('minimum_requirements.csv',result['requirements'])]:
        sensitivity.source.study.followup.x.old.csv_write(out/filename, rows)
    fields = ('pair','prediction','observed_par_minus_cpu_j','predicted_par_minus_cpu_j',
              'paired_signed_prediction_error_j','paired_peak_prediction_error_c','initial_ap_difference_c',
              'modeled_preload_background_difference_j')
    table = '<tr>'+''.join('<th>'+f+'</th>' for f in fields)+'</tr>'
    table += ''.join('<tr>'+''.join('<td>'+html.escape(str(row[f]))+'</td>' for f in fields)+'</tr>' for row in result['historical_pairs'])
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>공동 이득의 기존 근거와 최소 확인</title>'+
        '<style>body{font:16px/1.7 system-ui;margin:24px}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #aaa;padding:6px}.note{background:#fff2ca;padding:16px}.scroll{overflow:auto}</style>'+
        '<h1>기존 자료는 새 일정의 작은 공동 이득을 인증하지 못함</h1><p class="note">기존 192요청 8세션·4쌍의 사후 예측 차이와 관측 차이를 그대로 대조합니다. 새 48요청 일정의 보편적 오차 한도·계수 오차·정책 순위로 가져오지 않습니다. 같은 네 쌍의 조건부/종단간 두 판독은 독립 8쌍이 아닙니다.</p>'+
        '<p>background 항은 모형 입력의 기여이며 실제 관측에서 보정해 빼지 않았습니다. 현재 자료의 오차가 크다고 새 입력도 반드시 같은 오차라는 뜻은 아닙니다. 실제 계수 불확실성·제어비용·AP 차이 식별은 미확인이고 accuracy PASS/실제 우월성/목표 완료를 부여하지 않습니다.</p>'+
        '<div class="scroll"><table>'+table+'</table></div><p><a href="historical_pairs.csv">두 층의 기존 네 쌍</a> · <a href="minimum_requirements.csv">계산 6행/null 2행의 구체적 종료 조건</a> · <a href="result.json">미판정·정확한 해시·예산 미확정 항목</a> · <a href="../README.md">최종 해석·검증</a></p>',encoding='utf8')
    return out


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    save(analyze(),parser.parse_args().output)
