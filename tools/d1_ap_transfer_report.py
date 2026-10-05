"""PC-only report adapter; preserves the frozen transfer runner and plan.

No device APIs or commands. Invalid/partial observations produce null scores,
an evidence inventory and a reason, never completed comparison curves.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import traceback
from pathlib import Path

from tools import d1_ap_transfer_confirmation as transfer

VERSION = 'cgdc-transfer-report-v1'


def save(file, value):
    file.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False)+'\n', encoding='utf-8')


def rows(file):
    with file.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def csv_write(file, values):
    with file.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader(); writer.writerows(values)


def inventory(plan):
    """Only this session's evidence, no directory/device discovery."""
    root = Path(plan['output_root'])
    session = root/('00_'+plan['entries'][0]['session_id'])
    files = [root/'FINAL_RECEIPT.json']
    for parent in (session, session/'artifacts', session/'failure_prefix'):
        if parent.is_dir():
            files += [f for f in parent.iterdir() if f.is_file() and
                      f.suffix in ('.json', '.jsonl')]
    return [dict(file=f.relative_to(root).as_posix(), bytes=f.stat().st_size,
                 sha256=transfer.p.digest(f)) for f in sorted(set(files)) if f.is_file()]


def timing(plan_file, plan, origin):
    design = transfer.p.read(plan['input_bundle']['path'])['requests']
    if transfer.p.digest(plan['input_bundle']['path']) != plan['input_bundle']['sha256']:
        raise ValueError('timing input hash changed')
    artifact = Path(plan['output_root'])/('00_'+plan['entries'][0]['session_id'])/'artifacts'
    actual = transfer.p.read(artifact/'requests.json')
    planned = {q['request_id']: q for q in design}
    if len(planned) != 24 or len(actual) != 24 or {q['request_id'] for q in actual} != set(planned):
        raise ValueError('timing request denominator/identity')
    table = []
    fields = ('dispatch_ns', 'execution_start_ns', 'output_ready_ns',
              'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')
    for r in sorted(actual, key=lambda q: planned[q['request_id']]['ordinal']):
        q = planned[r['request_id']]
        if (r['task_id'], r['selected_backend']) != (q['task_id'], q['recorded_backend']):
            raise ValueError('timing task/backend differs')
        times = [r[k] for k in fields]
        if any(not isinstance(x, int) for x in times) or times != sorted(times):
            raise ValueError('timing lane/response order')
        out = dict(ordinal=q['ordinal'], task=q['task_id'], backend=q['recorded_backend'],
                   terminal_status=r['terminal_status'],
                   planned_arrival_s=q['offset_ms']/1000,
                   actual_arrival_s=(r['scheduled_arrival_ns']-origin)/1e9,
                   release_s=q['release_offset_ns']/1e9)
        if abs(out['planned_arrival_s']-out['actual_arrival_s']) > 1e-9:
            raise ValueError('actual arrival grid differs')
        for field in fields:
            out['actual_'+field[:-3]+'_s'] = (r[field]-origin)/1e9
        for field in fields[1:]:
            out['pc_'+field[:-3]+'_s'] = q['pc_'+field]/1e9
        out['dispatch_after_release_s'] = out['actual_dispatch_s']-out['release_s']
        if out['dispatch_after_release_s'] < -1e-9:
            raise ValueError('dispatch precedes release')
        out['lane_delta_vs_pc_s'] = out['actual_lane_available_s']-out['pc_lane_available_s']
        table.append(out)
    return table


def validate_tables(data, summary):
    """Refuse whole-window labels if endpoints or CSV scores disagree."""
    energy = rows(data/'energy_path.csv'); ap = rows(data/'ap_paths.csv')
    phases = rows(data/'phase_energy_residuals.csv')
    states = rows(data/'actual_states.csv')
    def close(a, b):
        if not math.isclose(float(a), float(b), abs_tol=1e-8, rel_tol=1e-9):
            raise ValueError('CSV/summary or full-window boundary differs')
    if not energy or not ap or any(r[k] == '' for r in energy for k in
                                   ('observed_j', 'predicted_j', 'signed_error_j')):
        raise ValueError('missing cumulative energy; no zero filling')
    close(energy[-1]['elapsed_s'], 120.)
    close(energy[-1]['observed_j'], summary['observed_energy_120s_j'])
    close(energy[-1]['predicted_j'], summary['predicted_energy_120s_j'])
    close(energy[-1]['signed_error_j'], summary['signed_energy_error_j'])
    close(sum(float(r['duration_s']) for r in phases), 120.)
    for key, total in (('observed_j', 'observed_energy_120s_j'),
                       ('predicted_j', 'predicted_energy_120s_j'),
                       ('signed_error_j', 'signed_energy_error_j')):
        if any(r[key] == '' for r in phases):
            raise ValueError('missing phase energy')
        close(sum(float(r[key]) for r in phases), summary[total])
    close(states[0]['start_s'], 0.); close(states[-1]['end_s'], 120.)
    for a, b in zip(states, states[1:]): close(a['end_s'], b['start_s'])
    for model in ('frozen', 'candidate'):
        residual = [float(r[model+'_signed_error_c']) for r in ap]
        for r in ap:
            close(float(r[model+'_ap_c'])-float(r['observed_ap_c']), r[model+'_signed_error_c'])
        close(sum(map(abs, residual))/len(residual), summary['ap_scores'][model]['mae_c'])
        close(max(map(abs, residual)), summary['ap_scores'][model]['max_absolute_error_c'])
    if summary['strict_support'] or summary['accuracy_pass'] is not None or summary['policy_rank'] is not None:
        raise ValueError('diagnostic promoted to validated policy output')
    return energy, ap, phases, states


def complete_energy_endpoint(data, summary):
    """Complete the plotted path at 120 s; never move/extend observation window.

    The frozen forecast already includes 120 s in its summary, but its path CSV
    contains sensor timestamps only. The observation's full energy required
    valid bracketing at 120 s. Preserve the original path; do not change scores.
    """
    energy = rows(data/'energy_path.csv')
    if not energy: raise ValueError('missing energy path')
    last = float(energy[-1]['elapsed_s'])
    if last == 120.: return summary
    if not 0 < last < 120.: raise ValueError('invalid final energy timestamp')
    phases = rows(data/'phase_energy_residuals.csv')
    if any(r['predicted_j']=='' for r in phases): raise ValueError('missing full-window phase prediction')
    if not math.isclose(sum(float(r['duration_s']) for r in phases),120.,abs_tol=1e-8):
        raise ValueError('phase window incomplete')
    predicted = sum(float(r['predicted_j']) for r in phases)
    actual = summary['observed_energy_120s_j']
    if not math.isclose(predicted,summary['predicted_energy_120s_j'],abs_tol=1e-8,rel_tol=1e-9):
        raise ValueError('full-window phase prediction differs from frozen summary')
    (data/'frozen_reader_energy_path.csv').write_bytes((data/'energy_path.csv').read_bytes())
    energy.append(dict(elapsed_s=120., observed_j=actual, predicted_j=predicted,
                       signed_error_j=predicted-actual))
    csv_write(data/'energy_path.csv',energy)
    save(data/'endpoint_completion.json',dict(reason='last in-window sensor timestamp is not common window end',
        original_csv_end_s=last, completed_csv_end_s=120.,
        prediction='sum frozen W times exact actual state durations over [0,120]',
        observation='original full-window integration with valid boundary brackets',
        coefficient_change=False, window_change=False, summary_scores_changed=False))
    return summary


def figures(output, table, energy, ap, states, evidence_label):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    def finish(fig, name):
        # English stamp avoids depending on a platform-specific Korean font.
        stamp = 'PC TEST FIXTURE - NOT MEASURED' if evidence_label.startswith('PC fixture') else 'CONDITIONAL DIAGNOSTIC - NOT POLICY VALIDATION'
        fig.suptitle(stamp, fontsize=10)
        fig.tight_layout(rect=(0,0,1,.96)); fig.savefig(output/(name+'.svg')); fig.savefig(output/(name+'.png'), dpi=130)
        plt.close(fig)
    if table:
        fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        for ax, label in zip(axes, ('Stored PC lane occupancy (planned)', 'Observed dispatch to lane available')):
            ax.set_title(label); ax.set_yticks([0, 1], ['C_GPU', 'D_CPU']); ax.set_ylim(-.7, 1.7)
            for r in table:
                y = 0 if r['task'] == 'classification' else 1
                start = r['release_s'] if ax is axes[0] else r['actual_dispatch_s']
                end = r['pc_lane_available_s'] if ax is axes[0] else r['actual_lane_available_s']
                ax.broken_barh([(start, end-start)], (y-.3, .6), facecolors='tab:blue' if y == 0 else 'tab:orange')
            ax.set_xlim(0, 120); ax.grid(axis='x', alpha=.2)
        axes[-1].set_xlabel('Seconds from common start (120 s window)'); finish(fig, 'lanes')
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    times = [0.]+[float(r['elapsed_s']) for r in energy]
    # Zero is the integral's initial condition, not an imputed sensor sample.
    for key, label in (('observed_j', 'Observed (raw=mA conditional)'), ('predicted_j', 'Frozen W diagnostic')):
        axes[0].plot(times, [0.]+[float(r[key]) for r in energy], label=label)
    axes[0].set_ylabel('Cumulative energy (J)'); axes[0].legend()
    axes[1].plot(times, [0.]+[float(r['signed_error_j']) for r in energy])
    axes[1].axhline(0, color='black', lw=.6); axes[1].set_ylabel('Prediction - observation (J)')
    axes[1].set_xlabel('Seconds from common start'); axes[1].set_xlim(0, 120)
    finish(fig, 'energy')
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    times = [float(r['elapsed_s']) for r in ap]
    for key, label in (('observed_ap_c', 'Observed AP'), ('frozen_ap_c', 'Frozen AP diagnostic'),
                       ('candidate_ap_c', 'Fixed preload-conditioned candidate')):
        axes[0].plot(times, [float(r[key]) for r in ap], label=label)
    axes[0].set_ylabel('AP (C)'); axes[0].legend(fontsize=8)
    for key in ('frozen', 'candidate'):
        axes[1].plot(times, [float(r[key+'_signed_error_c']) for r in ap], label=key)
    for ax in axes:
        for r in states:
            if r['state'] != 'idle': ax.axvspan(float(r['start_s']), float(r['end_s']), alpha=.12, color='orange')
        ax.set_xlim(times[0], times[-1])
    axes[1].axhline(0, color='black', lw=.6); axes[1].set_ylabel('Prediction - observation (C)')
    axes[1].set_xlabel('Seconds from common start; post-dispatch to cooling end')
    finish(fig, 'ap')


def page(output, summary, label):
    escaped = html.escape(label)
    body = f'<h1>CG_DC 전이 판독</h1><p>자료 구분: {escaped}</p>'
    if summary['status'] == 'report_complete_diagnostic_only':
        body += '<p>실제 일정 조건부 진단입니다. 온라인 B2·정책 순위·정확도 PASS가 아닙니다. 전류 raw=mA 조건부, 절대 정확도 미인증.</p>'
        body += '<p>AP는 부하 전 관측으로 유효 유휴 기준을 계산한 고정 절차이며, 부하 후 관측은 점수에만 사용합니다. AP 분모는 첫 dispatch 이후~냉각 끝, J 분모는 공통120초입니다.</p>'
        body += '<table><tr><th>지표</th><th>값</th></tr>'
        for key in ('initial_ap_c', 'initial_ap_in_development_range', 'actual_parallel_seconds',
                    'observed_energy_120s_j', 'predicted_energy_120s_j', 'signed_energy_error_j',
                    'relative_energy_error', 'ap_comparison_start_s', 'ap_comparison_end_s'):
            body += f'<tr><td>{key}</td><td>{html.escape(str(summary[key]))}</td></tr>'
        for model, score in summary['ap_scores'].items():
            for key in ('mae_c', 'max_absolute_error_c'):
                body += f'<tr><td>{model} {key}</td><td>{score[key]}</td></tr>'
        body += '</table><p>미지원: strict 전체창 J/AP·AP 최고/한도·정책 판별력. 시작 AP 지원 판정과 짧은 전환 지원은 별개입니다.</p>'
        for name in ('lanes', 'energy', 'ap'):
            body += f'<h2>{name}</h2><img src="{name}.svg" alt="{name} diagnostic"><p><a href="{name}.png">PNG</a></p>'
        body += '<p><a href="timing.csv">예정·실제 시간 경계</a></p>'
        for file in ('ap_paths.csv', 'energy_path.csv', 'phase_energy_residuals.csv', 'actual_states.csv'):
            body += f'<a href="data/{file}">{file}</a> '
    else:
        body += '<p>자료 미판정: 완료된 비교 그림·전체창 점수를 만들지 않았습니다. 기록 부재는 호출0이나 앱 실패를 뜻하지 않습니다.</p>'
        body += '<p>'+html.escape(summary['reason'])+'</p>'
    body += '<p><a href="report.json">기계 판독·검증 경계</a> · <a href="inventory.json">원본 파일 SHA inventory</a></p>'
    (output/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>CG_DC 판독</title><style>body{font:16px sans-serif;max-width:1100px;margin:24px auto;padding:16px}td,th{border:1px solid #ccc;padding:6px}table{border-collapse:collapse}img{width:100%}</style>'+body+'</html>', encoding='utf-8')


def report(plan_file, output, *, evidence_label='실측 원자료 · 별도 전이 확인 block'):
    plan_file, output = Path(plan_file), Path(output)
    if output.exists(): raise FileExistsError('fresh PC report output only')
    plan = transfer.p.read(plan_file)
    if plan.get('experiment_id') != transfer.EXPERIMENT:
        raise ValueError('not the prepared CG_DC transfer plan')
    root = Path(plan['output_root']).resolve()
    for protected in (root, Path(plan['registry']).resolve(), plan_file.parent.resolve()):
        if output.resolve() == protected or protected in output.resolve().parents:
            raise ValueError('report cannot write to run/registry/plan')
    output.mkdir(parents=True)
    context = dict(version=VERSION, evidence_label=evidence_label, device_commands=0,
        plan_sha256=transfer.p.digest(plan_file), report_code_sha256=transfer.p.digest(Path(__file__)),
        experiment_ready=False, strict_support=False, accuracy_pass=None, policy_rank=None)
    try:
        save(output/'inventory.json', inventory(plan))
        summary = transfer.readout(plan_file, output/'data')
        summary = complete_energy_endpoint(output/'data', summary)
        energy, ap, phases, states = validate_tables(output/'data', summary)
        artifact = root/('00_'+plan['entries'][0]['session_id'])/'artifacts'
        table = timing(plan_file, plan, transfer.p.read(artifact/'common_boundary.json')['start_ns'])
        csv_write(output/'timing.csv', table)
    except Exception as error:
        context.update(status='not_evaluable' if isinstance(error, (ValueError, OSError, KeyError, TypeError))
                       else 'processing_error', reason=str(error), error_type=type(error).__name__,
                       observed_energy_120s_j=None, predicted_energy_120s_j=None,
                       signed_energy_error_j=None, ap_scores=None,
                       incomplete_data_not_zero=True, comparison_figures=0)
        # Local error detail can contain local paths. Not a shared device result.
        (output/'processing_error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        save(output/'report.json', context); page(output, context, evidence_label)
        return context
    context.update(summary, status='report_complete_diagnostic_only', comparison_figures=3)
    save(output/'report.json', context)
    # Rendering failure is separate from data adequacy and preserved in a receipt.
    try:
        figures(output, table, energy, ap, states, evidence_label)
        page(output, context, evidence_label)
    except Exception as error:
        context.update(status='rendering_failed', comparison_figures=None, rendering_error=str(error))
        save(output/'report.json', context)
        (output/'rendering_error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    return context


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--plan', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    result = report(args.plan, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'report_complete_diagnostic_only' else 2


if __name__ == '__main__': raise SystemExit(main())
