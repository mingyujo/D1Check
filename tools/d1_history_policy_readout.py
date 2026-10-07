"""Read saved comparisons and contextual errors; never launch an engine or a device."""
import argparse
import csv
import hashlib
import html
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
BASE = 'docs/results/reserved_thermal_01/final_rule_only/'
HISTORY = 'docs/results/history_control_plan_01/run_v7/'
MODEL = 'docs/results/online_policy_study_01/overnight_sustained_run01/model.json'
MODEL_SHA = '5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2'
SOURCES = [BASE+'pairs.csv', BASE+'results.csv', BASE+'registration.json',
           HISTORY+'metrics.csv', HISTORY+'contrast_diagnostic.csv', MODEL]


def number(row, key):
    value = float(row[key])
    if not math.isfinite(value):
        raise ValueError(f'non-finite {key}')
    return value


def boolean(row, key):
    if row[key] not in ('True', 'False'):
        raise ValueError(f'missing boolean {key}')
    return row[key] == 'True'


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def classify(row):
    # A numerical mask is never an independent prediction/physical gain claim.
    if not boolean(row, 'cost_eligible'):
        return 'cost_or_full_work_ineligible'
    if not boolean(row, 'service_preserved'):
        return 'service_not_preserved'
    j, ap = number(row, 'delta_energy_j'), number(row, 'delta_peak_ap_c')
    if j < -1e-9 and ap < -1e-9:
        return 'model_joint_gain_only'
    if j > 1e-9 and ap < -1e-9:
        return 'model_heat_energy_tradeoff'
    return 'model_no_joint_gain'


def contrasts(metrics, recorded):
    rows = []
    for role in ('development', 'confirmation'):
        for gap in (30, 180):
            pair = {x['policy']: x for x in metrics
                    if x['model'] == 'frozen' and x['role'] == role and int(x['gap']) == gap}
            cpu, par = pair['CPU_URGENT_ONLINE_V1'], pair['B2_PARALLEL_ONLINE_V1']
            observed = number(par, 'observed_j') - number(cpu, 'observed_j')
            predicted = number(par, 'predicted_j') - number(cpu, 'predicted_j')
            err = number(par, 'signed_j') - number(cpu, 'signed_j')
            if not math.isclose(predicted-observed, err, abs_tol=1e-9):
                raise ValueError('contrast sign mismatch')
            old = next(x for x in recorded if x['role'] == role and int(x['gap_s']) == gap)
            if not math.isclose(err, number(old, 'signed_contrast_error_j'), abs_tol=1e-9):
                raise ValueError('saved contrast mismatch')
            rows.append(dict(role=role, gap_s=gap, observed_par_minus_cpu_j=observed,
                             predicted_par_minus_cpu_j=predicted, signed_contrast_error_j=err,
                             observed_peak_par_minus_cpu_c=number(par, 'observed_peak_ap_c')-number(cpu, 'observed_peak_ap_c'),
                             signed_peak_contrast_error_c=number(par, 'peak_signed_error_c')-number(cpu, 'peak_signed_error_c'),
                             energy_window_s='0..120', ap_window='actual post35 samples, session-specific end',
                             causal_effect=False, transferable_error_bound='',
                             limitation='sequential nominal conditions; different initial states; protocol transition'))
    return rows


def analyze(root=ROOT):
    hashes = {f: hashlib.sha256((root/f).read_bytes()).hexdigest() for f in SOURCES}
    if hashes[MODEL] != MODEL_SHA:
        raise ValueError('frozen model changed')
    registration = json.loads((root/(BASE+'registration.json')).read_text(encoding='utf-8'))
    if registration['source_hashes'][MODEL] != MODEL_SHA:
        raise ValueError('policy and history model identity mismatch')
    pairs = csv_rows(root/(BASE+'pairs.csv'))
    results = csv_rows(root/(BASE+'results.csv'))
    metrics = csv_rows(root/(HISTORY+'metrics.csv'))
    if len(pairs) != 1920 or len(results) != 2112:
        raise ValueError('incomplete saved comparison')
    keys = [(x['seed'], x['family'], x['context'], x['baseline']) for x in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate comparison')
    by_key = {(x['seed'], x['family'], x['context'], x['policy']):x for x in results}
    if len(by_key) != len(results):
        raise ValueError('duplicate policy result')
    annotated = []
    for x in pairs:
        key = (x['seed'], x['family'], x['context'])
        candidate = by_key[key+('RESERVED_THERMAL_REQUEST_V1_NUMERIC_R2',)]
        baseline = by_key[key+(x['baseline'],)]
        for delta, metric in (('delta_energy_j','energy_j'), ('delta_peak_ap_c','peak_ap_c'),
                              ('delta_urgent_p95_ms','urgent_p95_ms')):
            if candidate[metric] and baseline[metric]:
                if not math.isclose(number(x,delta), number(candidate,metric)-number(baseline,metric), abs_tol=1e-8):
                    raise ValueError(f'saved pair/result mismatch {delta}')
        cf = int(candidate['planned'])-int(candidate['deadline_met'])
        bf = int(baseline['planned'])-int(baseline['deadline_met'])
        annotated.append(dict(x, readout=classify(x), candidate_deadline_failures=cf,
                              baseline_deadline_failures=bf, both_all_deadlines=(cf==0 and bf==0),
                              independent_phone_policy_gain='unverified', universal_accuracy_threshold='', device='A24',
                              mode='B_synthetic_arrival_exploration', energy_window_s='0..120',
                              ap_window_s='35..180 model grid'))
    summaries = []
    for baseline in sorted({x['baseline'] for x in pairs}):
        for scope in ('primary_low_sustained', 'all_conditions'):
            selected = [x for x in annotated if x['baseline'] == baseline and
                        (scope == 'all_conditions' or x['family'] in ('low', 'sustained'))]
            eligible = [x for x in selected if boolean(x, 'service_preserved') and boolean(x, 'cost_eligible')]
            j = [number(x, 'delta_energy_j') for x in eligible]
            ap = [number(x, 'delta_peak_ap_c') for x in eligible]
            summaries.append(dict(baseline=baseline, scope=scope, comparisons=len(selected),
                                 eligible_pairs=len(eligible),
                                 ineligible_pairs=len(selected)-len(eligible),
                                 joint_model_gain_pairs=sum(x['readout']=='model_joint_gain_only' for x in eligible),
                                 both_all_deadlines_pairs=sum(x['both_all_deadlines'] for x in eligible),
                                 joint_gain_both_all_deadlines=sum(x['both_all_deadlines'] and x['readout']=='model_joint_gain_only' for x in eligible),
                                 delta_energy_mean_j=mean(j) if j else None,
                                 delta_energy_min_j=min(j) if j else None,
                                 delta_energy_max_j=max(j) if j else None,
                                 delta_peak_mean_c=mean(ap) if ap else None,
                                 delta_peak_min_c=min(ap) if ap else None,
                                 delta_peak_max_c=max(ap) if ap else None,
                                 physical_joint_gain='unverified'))
    errors = contrasts(metrics, csv_rows(root/(HISTORY+'contrast_diagnostic.csv')))
    confirmed = [x for x in metrics if x['model']=='frozen' and x['role']=='confirmation']
    if len(confirmed) != 6:
        raise ValueError('all six confirmation sessions required')
    summary = dict(model_sha256=MODEL_SHA, policy_rows_reused=len(results), pair_rows_reused=len(pairs),
                   confirmation_sessions=6, new_simulations=0, training=0, device_commands=0,
                   energy_mae_j=mean(number(x, 'absolute_j') for x in confirmed),
                   ap_mae_c=mean(number(x, 'mae_c') for x in confirmed),
                   ap_peak_max_absolute_c=max(abs(number(x, 'peak_signed_error_c')) for x in confirmed),
                   confirmation_energy_contrast_errors_j=[x['signed_contrast_error_j'] for x in errors if x['role']=='confirmation'],
                   confirmation_peak_contrast_errors_c=[x['signed_peak_contrast_error_c'] for x in errors if x['role']=='confirmation'],
                   physical_policy_winner=None, large_effect_threshold=None, confidence_interval=None,
                   forecast_A_vs_B='history costs conditional on actual schedule; saved policy engine generates schedule',
                   limitation='same coefficients and units, but workload/history/protocol and AP sampling differ; no residual transfer or universal PASS',
                   source_hashes=hashes)
    return annotated, summaries, errors, summary


def figures(output, summaries, errors):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    selected = [x for x in summaries if x['scope']=='primary_low_sustained' and x['baseline'] in (
        'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1', 'BAND_HEFT_WHOLE_REQUEST_ADAPT_V1', 'SHARED_EFT', 'EFT_REFERENCE')]
    names = {'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1':'Triton 대응', 'BAND_HEFT_WHOLE_REQUEST_ADAPT_V1':'Band 대응',
             'SHARED_EFT':'공유 EFT', 'EFT_REFERENCE':'내부 EFT'}
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, key, error_key, unit in zip(axs, ('delta_energy_mean_j','delta_peak_mean_c'),
                                      ('signed_contrast_error_j','signed_peak_contrast_error_c'), ('J', '°C')):
        labels = [names[x['baseline']]+'\n모형 차이 평균' for x in selected]+['회복30초\n확인 대조잔차', '회복180초\n확인 대조잔차']
        values = [x[key] for x in selected]+[x[error_key] for x in errors if x['role']=='confirmation']
        ax.bar(range(6), values, color=['#16728c']*4+['#b66630']*2)
        ax.axhline(0, color='black', lw=.7)
        ax.set_xticks(range(6), labels, fontsize=8)
        ax.set_ylabel(unit)
        ax.set_title('정책 모형 차이와 별도 이력 대조 잔차')
        ax.margins(y=.18)
        for i, value in enumerate(values):
            ax.annotate(f'{value:+.3f}', (i,value), xytext=(0,5 if value>=0 else -13), textcoords='offset points', ha='center', fontsize=8)
    fig.suptitle('같은 단위의 규모 비교 · 잔차 전용/오차 한도/정책 확인이 아님', fontsize=12)
    fig.tight_layout()
    fig.savefig(output/'context_comparison.png', dpi=150)
    fig.savefig(output/'context_comparison.svg')
    svg = output/'context_comparison.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('use a new output directory; saved results are immutable')
    pairs, summaries, errors, summary = analyze()
    args.output.mkdir(parents=True)
    write_csv(args.output/'policy_context.csv', pairs)
    write_csv(args.output/'policy_summary.csv', summaries)
    write_csv(args.output/'history_contrasts.csv', errors)
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    figures(args.output, summaries, errors)
    table = ''.join('<tr>'+''.join('<td>'+html.escape(str(x[k]))+'</td>' for k in
                    ('baseline','scope','eligible_pairs','joint_model_gain_pairs','delta_energy_mean_j','delta_peak_mean_c'))+'</tr>' for x in summaries)
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>정책 차이와 실측 잔차</title>
    <style>body{font:16px sans-serif;max-width:1200px;margin:30px auto;padding:20px}td,th{padding:8px;border:1px solid #ccc}table{border-collapse:collapse}img{max-width:100%}</style>
    <h1>정책 차이와 실측 잔차</h1><p>저장된 192조건·2,112행 재사용. 새 시뮬레이션·학습·기기 명령 0.</p>
    <p>실측 잔차는 실제 일정에 조건부인 A, 정책 비교는 합성 도착부터 일정을 만드는 B다.
    같은 계수라도 다른 부하·이력·관측 프로토콜의 잔차를 정책 오차 한도나 신뢰구간으로 전용하지 않는다.</p>
    <p>모형의 작은 공동 감소는 일부 있으나 Band 대비 주평가 공동 감소 0. 실제 열·에너지 우월성은 미확인.
    기존 실측에서 확인된 CPU/PAR 응답 차이는 별도 근거로 유지한다. strict/default/experiment_ready=false 불변.</p>
    <img src="context_comparison.png" alt="정책 모형 차이와 별도 관측 대조 잔차 규모">
    <p><a href="README.md">판독·범위·재현</a> · <a href="policy_context.csv">전체1,920쌍</a> · <a href="history_contrasts.csv">이력 대조잔차</a></p>
    <table><thead><tr><th>기준정책</th><th>범위</th><th>서비스·비용 적격쌍</th><th>모형 공동감소</th><th>평균 ΔJ</th><th>평균 Δ최고AP °C</th></tr></thead><tbody>'''+table+'</tbody></table></html>'
    (args.output/'index.html').write_text(page, encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='source_hashes'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
