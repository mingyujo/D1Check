"""Read-only audit of the one causal area-veto candidate, no new simulations."""
import argparse
import gzip
import html
import json
from pathlib import Path
import numpy as np
from tools import d1_joint_queue_study as study

P = study.P
ROOT = study.ROOT


def analyze(source):
    source = Path(source)
    registration = json.loads((source/'registered_before_run.json').read_text(encoding='utf8'))
    if registration['spec'] != study.specification(): raise ValueError('candidate rule changed')
    for name, digest in {**registration['code'], **registration['resources']}.items():
        if P.digest(P.ROOT/name) != digest: raise ValueError('candidate registered hash mismatch '+name)
    if P.digest(source/'inputs.json') != registration['input_sha256']: raise ValueError('candidate input hash mismatch')
    rule = registration['spec']; data = json.loads((source/'inputs.json').read_text(encoding='utf8'))
    tickets = {r['seed']: r['tickets'] for r in data}
    expected = {(seed, context, policy) for seed in rule['seeds'] for context in rule['scenarios'] for policy in rule['policies']}
    records = [json.loads(r) for r in gzip.decompress((source/'records.jsonl.gz').read_bytes()).decode().splitlines()]
    if len(records) != 12 or {(r['meta']['seed'], r['meta']['scenario'], r['meta']['policy']) for r in records} != expected:
        raise ValueError('complete twelve-run denominator required')
    frozen, case = P.inputs(P.BUNDLE); initial = case['initial']; paths = {}
    profile = P.profile(frozen)
    C, G, D = (sum(profile[k])/1e9 for k in P.CELLS)
    watts = frozen['energy_increment_w']
    gpu_term = watts['classification_GPU']*G-watts['classification_CPU']*C
    pair_term = watts['classification_GPU']+watts['detection_CPU']-watts['classification_GPU+detection_CPU']
    for record in records:
        m = record['meta']; key = (m['seed'], m['scenario'], m['policy'])
        if study.followup.tickets(record) != tickets[m['seed']]: raise ValueError('full fixed arrivals changed')
        study.work.audit_record(record, frozen)
        cost = P.model.costs(record['segments'], initial, list(range(35, 181)), frozen, 180.)
        idle = cost['initial']['reference_c']; ap = np.array(cost['ap_path'])
        weights = np.ones(len(ap)); weights[[0, -1]] = .5
        for name, value in dict(energy_j=cost['whole_120s_j'], peak_ap_c=max(ap),
            thermal_degree_seconds=float(weights@np.maximum(ap-idle, 0.))).items():
            if abs(m[name]-value) > 1e-7: raise ValueError('full model window metric mismatch')
        by_id = {q['id']: q for q in record['ledger']}
        for guard in record.get('guards', []):
            if any(rid not in by_id or by_id[rid]['arrival_ns'] > guard['now_ns'] for rid in guard['arrived_ids']):
                raise ValueError('future arrival leaked into controller guard')
            if guard.get('selected_sequence'):
                if any(rid not in guard['arrived_ids'] for rid, _, _ in guard['selected_sequence']):
                    raise ValueError('future request planned by causal candidate')
                predicted = guard['prediction']; reference = guard['reference']
                if any(predicted[k] > reference[k]+1e-8 for k in
                       ('remaining_energy_j', 'predicted_peak_ap_c', 'future_rectified_AP_area_c_s')):
                    raise ValueError('recorded local joint guard violated')
        paths[key] = cost
    pairs = study.followup.compare([r['meta'] for r in records])
    summary = json.loads((source/'summary.json').read_text(encoding='utf8'))
    if summary['PC_runs'] != 12 or summary['joint_nonworsening'] != sum(r['joint_nonworsening'] for r in pairs):
        raise ValueError('candidate summary denominator mismatch')
    ledger = {(r['meta']['seed'], r['meta']['scenario'], r['meta']['policy']): r for r in records}
    rows = []
    for pair in pairs:
        ref = ledger[pair['seed'], pair['scenario'], 'EFT_REFERENCE']
        candidate = ledger[pair['seed'], pair['scenario'], study.candidate.LABEL]
        study.work.budget.same_input(candidate, ref)
        pr = P.profile(frozen, pair['scenario'])
        C, G = sum(pr['classification_CPU_urgent'])/1e9, sum(pr['classification_GPU_urgent'])/1e9
        gpu_term = watts['classification_GPU']*G-watts['classification_CPU']*C
        gpu_delta = sum(q['backend'] == 'GPU' for q in candidate['ledger'])-sum(q['backend'] == 'GPU' for q in ref['ledger'])
        overlap_delta = candidate['meta']['overlap_s']-ref['meta']['overlap_s']
        identity = gpu_delta*gpu_term-overlap_delta*pair_term
        if abs(identity-pair['delta_energy_j']) > 2e-8: raise ValueError('modeled energy identity mismatch')
        rows.append(dict(pair, delta_GPU_assignments=gpu_delta, delta_pair_overlap_s=overlap_delta,
            energy_from_changed_GPU_assignments_j=gpu_delta*gpu_term,
            energy_from_changed_overlap_j=-overlap_delta*pair_term,
            energy_identity_j=identity,
            candidate_PC_callback_total_s=candidate['meta']['decision_host_total_s'],
            EFT_PC_callback_total_s=None, actual_device_controller_delta_j=None,
            local_guard_pass_is_global_guarantee=False, strict_supported=False, experiment_ready=False))
    return dict(version='joint-queue-area-readout-v1', rows=rows, paths=paths,
        source=str(source.relative_to(P.ROOT)), summary=summary,
        resources={p.relative_to(P.ROOT).as_posix(): P.digest(p) for p in
            (source/'registered_before_run.json', source/'inputs.json', source/'records.jsonl.gz', source/'summary.json')},
        controller_guards_checked=True, new_simulations=0, device_commands=0, experiment_ready=False,
        independent_prediction_validation=False, physical_advantage_proven=False, accuracy_pass=None)


def save(result, output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    compact = {k: v for k, v in result.items() if k != 'paths'}
    compact['analysis_code_sha256'] = P.digest(__file__)
    P.write(out/'result.json', compact)
    study.candidate.x.old.csv_write(out/'comparisons.csv', result['rows'])
    curves = []
    for row in result['rows']:
        ref = result['paths'][row['seed'], row['scenario'], 'EFT_REFERENCE']
        candidate = result['paths'][row['seed'], row['scenario'], study.candidate.LABEL]
        times = list(range(121))
        def energy(data):
            return np.interp(times, [r['common_s'] for r in data['energy_path']], [r['predicted_j'] for r in data['energy_path']])
        deltas = energy(candidate)-energy(ref)
        for t, value in zip(times, deltas): curves.append(dict(seed=row['seed'], scenario=row['scenario'], time_s=t, delta_modeled_J=float(value), delta_modeled_AP_c=None))
        for t, a, b in zip(range(35, 181), candidate['ap_path'], ref['ap_path']):
            curves.append(dict(seed=row['seed'], scenario=row['scenario'], time_s=t, delta_modeled_J=None, delta_modeled_AP_c=a-b))
    study.candidate.x.old.csv_write(out/'modeled_difference_paths.csv', curves)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for col, seed in enumerate(study.specification()['seeds']):
        for context, style in zip(study.specification()['scenarios'], ('-', ':', '--')):
            data = [r for r in curves if r['seed'] == seed and r['scenario'] == context]
            en = [r for r in data if r['delta_modeled_J'] is not None]
            ap = [r for r in data if r['delta_modeled_AP_c'] is not None]
            axes[0, col].plot([r['time_s'] for r in en], [r['delta_modeled_J'] for r in en], style, label=context)
            axes[1, col].plot([r['time_s'] for r in ap], [r['delta_modeled_AP_c'] for r in ap], style, label=context)
        axes[0, col].set_title('Fresh synthetic seed '+str(seed))
        axes[0, col].set_ylabel('Candidate minus EFT / modeled J')
        axes[1, col].set_ylabel('Candidate minus EFT / modeled AP (C)')
        for ax in axes[:, col]:
            ax.axhline(0., color='black', lw=.7); ax.grid(alpha=.2); ax.legend(); ax.set_xlabel('Common seconds')
    fig.suptitle('Arrived-queue J/peak/area veto / conditional model comparison, not device measurements')
    for ext in ('png', 'svg'): fig.savefig(out/f'modeled_differences.{ext}', dpi=140)
    plt.close(fig)
    svg = out/'modeled_differences.svg'; svg.write_text('\n'.join(r.rstrip() for r in svg.read_text(encoding='utf8').splitlines())+'\n', encoding='utf8')
    fields = ('seed', 'scenario', 'deadline_met', 'planned', 'delta_energy_j', 'delta_peak_ap_c',
        'delta_thermal_degree_seconds', 'delta_urgent_p95_ms', 'delta_normal_mean_ms', 'delta_GPU_assignments',
        'delta_pair_overlap_s', 'candidate_PC_callback_total_s', 'joint_nonworsening')
    table = '<tr>'+''.join('<th>'+k+'</th>' for k in fields)+'</tr>'
    table += ''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in fields)+'</tr>' for r in result['rows'])
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>온라인 큐 후보의 에너지·열 상충</title>'+
        '<style>body{font:16px/1.7 system-ui;margin:24px}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #aaa;padding:6px}.note{background:#fff2ca;padding:15px}.scroll{overflow:auto}img{max-width:100%}</style>'+
        '<h1>현재 큐의 공동 제약은 전체 입력의 공동 절감 보장이 아니다</h1><p class="note">새 합성2seed×기존3문맥 모두48/48기한을지켰지만 AP 감소와 에너지 증가가 상충했습니다. 사후 개발 후보 하나의 PC 비교이며 실제 기기 절감·독립 확인·정확도 PASS가 아닙니다.</p>'+
        '<p>분류GPU 수와 CG_DC 겹침 감소의 J 항을 분리했습니다. 양의 에너지 차이와 음의 AP 차이를 숨기지 않습니다. callback PC 실행시간은 휴대폰 비용으로 환산하지 않으며 EFT timer 부재는null입니다. 그림은 모형끼리의 비교이고 센서 보간/실측 곡선이 아닙니다.</p>'+
        '<div class="scroll"><table>'+table+'</table></div><img src="modeled_differences.png" alt="모형 에너지 및 AP 차이, 실기기 관측이 아님">'+
        '<p><a href="comparisons.csv">전체6대조·항별분해</a> · <a href="result.json">해시·미확인</a> · <a href="../README.md">결론·재현·한계</a></p>', encoding='utf8')
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--source', default=str(ROOT/'joint_queue_area_v1'))
    parser.add_argument('--output', required=True); args = parser.parse_args()
    save(analyze(args.source), args.output)
