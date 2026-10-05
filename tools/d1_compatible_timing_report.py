"""Reaggregate compatible backfill and paired saved controls; never simulate."""
import argparse
import hashlib
import html
from pathlib import Path
from tools import d1_detector_gpu_report as shared
from tools import d1_compatible_timing_backfill as c

ROOT = c.b.ROOT/'compatible_backfill_v2'


def verify(root):
    shared.verify(c.b.ROOT)
    registration = shared.load(root/'registered_before_run.json')
    for relative, expected in registration['hashes'].items():
        if hashlib.sha256(shared.source_bytes(c.b.f.x.p.ROOT/relative)).hexdigest() != expected:
            raise ValueError('compatible registered source/input changed: '+relative)
    if registration['power_model'] is not None or registration['AP_model'] is not None:
        raise ValueError('timing-only boundary changed')


def validate(records, controls, inputs):
    expected = {(z['envelope'], z['seed'], factor): z['tickets']
                for z in inputs for factor in (1., 1.5)}
    actual = {}
    from tools.d1_detector_gpu_reference import occupancy
    for rec in records:
        meta = rec['meta']; key = meta['envelope'], meta['seed'], meta['interference']
        if key in actual or key not in expected:
            raise ValueError('missing/duplicate/unregistered case')
        actual[key] = rec
        if meta['policy'] != c.POLICY or meta['energy_j'] is not None or meta['ap_peak_c'] is not None:
            raise ValueError('policy/current physical boundary changed')
        tickets = {z['id']: z for z in expected[key]}
        ledger = {z['id']: z for z in rec['ledger']}
        if len(ledger) != 48 or len(rec['ledger']) != 48 or set(ledger) != set(tickets):
            raise ValueError('full arrival denominator changed')
        for rid, q in ledger.items():
            t = tickets[rid]
            if any(q[k] != t[k] for k in ('arrival_ns', 'deadline_offset_ns', 'task', 'priority')):
                raise ValueError('arrival/deadline identity changed')
            if q['status'] == 'succeeded':
                times = [q[k] for k in ('dispatch_ns', 'execution_start_ns', 'output_ready_ns',
                         'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')]
                if times != sorted(times) or times[0] < t['arrival_ns']:
                    raise ValueError('actual response/release order changed')
                if q['task'] == 'classification' and q['backend'] != 'CPU':
                    raise ValueError('classification CPU scope changed')
        if meta['completed'] != sum(q['status'] == 'succeeded' for q in rec['ledger']):
            raise ValueError('completion denominator mismatch')
        if meta['detection_gpu_jobs'] != sum(q.get('backend') == 'GPU' and q['task'] == 'detection' for q in rec['ledger']):
            raise ValueError('detector GPU count mismatch')
        segments = occupancy(rec['ledger'])
        if segments != rec['segments'] or any(not z['historical_fixed_state_exists'] for z in segments):
            raise ValueError('incompatible pair escaped occupancy mask')
        if abs(sum(z['end_s']-z['start_s'] for z in segments)-120) > 1e-7:
            raise ValueError('common timing window changed')
    if set(actual) != set(expected):
        raise ValueError('incomplete registered study')
    paired = {}
    for rec in controls:
        m = rec['meta']; key = m['envelope'], m['seed'], m['interference'], m['policy']
        if key in paired:
            raise ValueError('duplicate saved control')
        paired[key] = rec
    comparisons = []
    for key, rec in actual.items():
        m = rec['meta']
        for policy in ('CPU_URGENT', 'LEGACY_STATIC_CG_DC', 'LEGACY_STATIC_CC_DG'):
            old = paired.get((*key, policy))
            if old is None:
                raise ValueError('missing same-input control')
            old_tickets = {z['id']: z for z in old['ledger']}
            if any(any(q[k] != old_tickets[q['id']][k] for k in ('arrival_ns', 'task', 'priority', 'deadline_offset_ns'))
                   for q in rec['ledger']):
                raise ValueError('unpaired control input')
            om = old['meta']
            comparisons.append(dict(envelope=key[0], seed=key[1], interference=key[2],
                reference=policy, planned=48, candidate_deadline_met=m['deadline_met'],
                reference_deadline_met=om['deadline_met'],
                delta_urgent_p95_ms=m['urgent_p95_ms']-om['urgent_p95_ms'],
                delta_normal_mean_ms=m['normal_mean_ms']-om['normal_mean_ms'],
                energy_j=None, ap_peak_c=None, current_profile_supported=False,
                deployment_allowed=False))
    return comparisons


def render(root, groups, comparisons, records, controls):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    pick = dict(envelope='g0.45_c0.5_b4', seed=623001, interference=1.5)
    candidates = controls+records
    order = ['CPU_URGENT', 'LEGACY_STATIC_CG_DC', c.POLICY]
    fig, axes = plt.subplots(3, 1, figsize=(12, 6), sharex=True)
    colors = {'classification': '#3977ad', 'detection': '#d58626'}
    for ax, policy in zip(axes, order):
        rec = next(z for z in candidates if z['meta']['policy'] == policy and
                   all(z['meta'][k] == v for k, v in pick.items()))
        for q in rec['ledger']:
            if q['status'] != 'succeeded':
                continue
            ax.broken_barh([(q['dispatch_ns']/1e9, (q['lane_available_ns']-q['dispatch_ns'])/1e9)],
                           (0 if q['backend'] == 'CPU' else 1, .6), facecolors=colors[q['task']])
        ax.set_yticks([.3, 1.3], ['CPU', 'GPU']); ax.set_title(policy, loc='left', fontsize=9)
        ax.grid(axis='x', alpha=.25)
    axes[-1].set_xlim(34, 70); axes[-1].set_xlabel('PC time (s), dispatch through actual lane release')
    axes[-1].legend(handles=[Patch(color=v, label=k) for k, v in colors.items()], fontsize=8)
    fig.suptitle('Historical timing transfer: compatible backfill vs saved controls\nExisting 1.5 interference assumption; J/AP unidentified; not a device validation', fontsize=10)
    fig.tight_layout()
    for suffix in ('png', 'svg'):
        fig.savefig(root/f'paired_timing.{suffix}', dpi=135)
    plt.close(fig)
    svg = root/'paired_timing.svg'
    svg.write_text('\n'.join(x.rstrip() for x in svg.read_text(encoding='utf8').splitlines())+'\n', encoding='utf8')
    fields = list(groups[0])
    head = ''.join('<th>'+html.escape(k)+'</th>' for k in fields)
    body = ''.join('<tr>'+''.join('<td>'+html.escape('미계측 / null' if z[k] is None else
        str(round(z[k], 4) if type(z[k]) is float else z[k]))+'</td>' for k in fields)+'</tr>' for z in groups)
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>호환 자원 backfill PC 비교</title>
<style>body{font:16px sans-serif;max-width:1300px;margin:30px auto;padding:0 20px}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccc;padding:6px}img{width:100%}.warn{padding:15px;background:#fff2cf}</style>
<h1>분류 CPU 고정·탐지 CPU/GPU 호환 backfill</h1>
<p class="warn">과거 CAL03 시간자료를 전용한 사후 PC 개발 결과입니다. 새 기기 자료·현재 J/AP 예측·정책 우월성·독립 예측 확인이 아닙니다. 비용 결측을 0으로 채우지 않았습니다.</p>
<p>새 16계산/768요청, 저장된 동일 입력 정적 48계산 재사용. 큐는 실제 도착만 사용하고 worker_release 뒤 실제 lane_available까지 busy입니다. 같은 종류의 CPU/GPU 병행은 차단합니다. 신규 물리 가정·기기 명령·계획·claim은 0입니다.</p>
<p>저부하는 CPU 기준과 동일, queue는 긴급/일반 응답의 상충, burst는 전체 기한 미충족입니다. 새 기본 정책으로 채택하지 않습니다. 현재 실측 기반 EFT와 이 과거 시간 프로필의 원 지연값을 직접 비교하지 않습니다.</p>
<p><a href="../README.md">근거·한계·재현</a> · <a href="paired_comparisons.csv">동일 seed 대조</a> · <a href="timing_groups.csv">집계 CSV</a></p>
<img src="paired_timing.png" alt="관측이 아닌 저장된 과거 시간 프로필의 PC 일정"><table><thead><tr>'''+head+'</tr></thead><tbody>'+body+'</tbody></table></html>'
    (root/'index.html').write_text(page, encoding='utf8')


def report(root=ROOT):
    root = Path(root); verify(root)
    records = shared.load(root/'timing_ledgers.json')
    controls = shared.load(c.b.ROOT/'run_v1/timing_ledgers.json')
    inputs = shared.load(c.b.ROOT/'run_v1/inputs.json')
    comparisons = validate(records, controls, inputs)
    groups = shared.aggregate(controls+records)
    c.b.f.x.old.csv_write(root/'paired_comparisons.csv', comparisons)
    c.b.f.x.old.csv_write(root/'timing_groups.csv', groups)
    render(root, groups, comparisons, records, controls)
    return comparisons


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', default=str(ROOT))
    report(p.parse_args().root)
