"""Portable PC workbench: frozen scheduler, support guard and separate observations.

Never launches a device, fits coefficients, or substitutes observations for costs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from pathlib import Path

from tools import d1_arrival_explore as engine
from tools import d1_arrival_explore_batch as batch
from tools import d1_arrival_energy_research as accounting
from tools import d1_arrival_service_guard as guard
from tools import d1_energy_operational_decision as episode

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'docs/results'
CONTRACT = RESULTS / 'simulator_workbench_01/resources.json'
BUNDLE = RESULTS / 'arrival_explore_20260925/input_bundle'
FREEZE = RESULTS / 'arrival_explore_20260925/freeze_before_evaluation.json'
TIMELINE = RESULTS / 'arrival_visualization_01/timeline.csv'
OBSERVED = RESULTS / 'recorded_policy_comparison_01/run01'
PROFILE = RESULTS / 'energy_operational_sim_01/frozen_profile.json'
EVALUATION = RESULTS / 'energy_operational_sim_01/confirmation_evaluation.json'
POLICIES = ('CPU_URGENT', 'B2_PC', 'B3_SOLO_EFT_PC')
VERSION = 'd1-simulator-workbench-v1'
SCHEDULE_FIELDS = ('id', 'task', 'priority', 'backend', 'status', 'arrival_ns',
                   'deadline_offset_ns', 'dispatch_ns', *engine.FIELDS)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def verify_resources(contract=CONTRACT):
    spec = read(contract)
    if spec['version'] != VERSION:
        raise ValueError('resource contract version')
    for name, expected in spec['files'].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or digest(path) != expected:
            raise ValueError('resource mismatch: ' + name)
    return dict(spec['files'])


def canonical_schedule(ledger):
    return [{k: str(row.get(k)) for k in SCHEDULE_FIELDS}
            for row in sorted(ledger, key=lambda r: r['id'])]


def archived_match(result, scenario, mode, seed):
    if (scenario, mode, seed) != ('queue', 'explore', 201):
        return False
    source = [r for r in rows(TIMELINE) if (r['scenario'], r['mode'], int(r['seed']), r['policy'])
              == (scenario, mode, seed, result['policy'])]
    return bool(source) and canonical_schedule(source) == canonical_schedule(result['ledger'])


def guard_row(policy, service, scenario, seed):
    u, n = service['urgent'], service['normal']
    return dict(scenario=scenario, realized='1.5', seed=str(seed), policy=policy,
        planned=service['planned'], urgent_planned=u['planned'], normal_planned=n['planned'],
        unfinished=service['unfinished'], urgent_not_timely=u['not_confirmed_timely'],
        normal_not_timely=n['not_confirmed_timely'],
        urgent_p95_ms=str(u['response_p95_ms']), normal_mean_ms=str(n['response_mean_ms']))


def service_guard(policy, reference, contract):
    if any(r[k] == 'None' for r in (policy, reference)
           for k in ('urgent_p95_ms', 'normal_mean_ms')):
        return dict(eligible=False, failed_conditions='missing_response_metric',
                    energy_ap_rank=None)
    return guard.screen(policy, reference, contract)


def observations(policy):
    source = read(OBSERVED / 'summary.json')
    selected = []
    for item in source['sessions']:
        if item['source_policy'] != policy:
            continue
        index = item['index']
        selected.append(dict(summary=item,
            energy_path=[[float(r['elapsed_s']), float(r['observed_cumulative_j'])]
                         for r in rows(OBSERVED / f'{index}_energy.csv')],
            ap_path=[[float(r['elapsed_s']), float(r['observed_ap_c'])]
                     for r in rows(OBSERVED / f'{index}_ap.csv')],
            schedule=rows(OBSERVED / f'{index}_schedule.csv')))
    return selected


def arrival(scenario='queue', mode='explore', seed=201):
    provenance = verify_resources()
    if scenario not in ('low', 'queue', 'burst') or mode not in ('strict', 'explore') or type(seed) is not int:
        raise ValueError('unsupported workload/mode/seed')
    config, vectors = read(BUNDLE / 'estimates.json'), read(BUNDLE / 'realizations.json')
    freeze = read(FREEZE)
    settings = batch.defaults(mode)
    settings.update({key: freeze['B2'][mode]['settings'][key]
                     for key in ('static_map', 'static_parallel')})
    requests = batch.workload(scenario, 'evaluation')
    cases = []
    # Prediction never receives the comparison sessions, current, or AP path.
    for policy in POLICIES:
        result = engine.simulate(config, vectors, requests, policy=policy,
                                 settings=settings, seed=seed)
        evaluated = accounting.aggregate(requests, result, profile={
            'evidence': 'energy_ap_state_regimen_fit_v1'})
        cases.append(dict(policy=policy, service=evaluated['service'],
            energy_ap=evaluated['energy_ap'], ledger=result['ledger'],
            recorded_source_schedule_match=archived_match(result, scenario, mode, seed),
            observations=[], guard=None))
    reference = guard_row(cases[0]['policy'], cases[0]['service'], scenario, seed)
    for case in cases:
        case['guard'] = service_guard(guard_row(case['policy'], case['service'], scenario, seed),
                                      reference, read(guard.CONTRACT))
        if case['recorded_source_schedule_match']:
            case['observations'] = observations(case['policy'])
    return dict(version=VERSION, route='arrival', scenario=scenario, mode=mode, seed=seed,
        settings=settings, requests=requests, common_window_s=120, cases=cases,
        provenance=provenance, experiment_ready=False, energy_ap_policy_rank=None,
        prediction_evidence='calibration-conditioned schedule simulation; interference and queue transfer assumed',
        observation_evidence='recorded dispatch replay, not online policy or independent end-to-end prediction validation',
        thermal_performance_feedback='unsupported; no invented throttle curve',
        independent_accuracy_pass=None)


def fixed_episode(initial_ap_c=29.1, completion_cap=None, ap_cap=None):
    provenance = verify_resources()
    profile = read(PROFILE)
    query = episode.query_from_recorded_profile(profile, initial_ap_c)
    query.update(profile_sha256=digest(PROFILE), max_work_completion_s=completion_cap,
                 max_load_ap_peak_c=ap_cap)
    result = episode.decide(PROFILE, EVALUATION, query)
    return dict(version=VERSION, route='fixed_episode', result=result,
        provenance=provenance, experiment_ready=False,
        interpretation='archived CC_DG 678 classification CPU + 192 detection GPU; 480s common energy; no arbitrary arrivals',
        confirmation_role='already-seen archived one session per arm; no new independent validation')


def plot(series, ylabel):
    """Small standalone SVG. Gaps split paths; never replace missing values by 0."""
    finite = [(x, y) for _, points in series for x, y in points if x is not None and y is not None]
    if not finite:
        return '<p>관측 없음 / 계산 불가</p>'
    xmin, xmax = min(x for x, _ in finite), max(x for x, _ in finite)
    ymin, ymax = min(y for _, y in finite), max(y for _, y in finite)
    dx, dy = max(xmax-xmin, 1), max(ymax-ymin, .1)
    colors = ('#0e7490', '#b45309', '#6d28d9', '#0f766e')
    parts = [f'<svg viewBox="0 0 800 250" role="img" aria-label="{html.escape(ylabel)}">',
             '<path d="M55 20V215H780" fill="none" stroke="#64748b"/>',
             f'<text x="58" y="16">{html.escape(ylabel)} · {ymin:.2f}–{ymax:.2f}</text>',
             f'<text x="590" y="244">{xmin:.1f}–{xmax:.1f}초</text>']
    for index, (label, points) in enumerate(series):
        segments, current = [], []
        for x, y in points:
            if x is None or y is None:
                if current: segments.append(current)
                current = []
            else:
                current.append(f'{55+725*(x-xmin)/dx:.2f},{215-185*(y-ymin)/dy:.2f}')
        if current: segments.append(current)
        color = colors[index % len(colors)]
        for segment in segments:
            parts.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{65+index*175}" y="235" fill="{color}">{html.escape(label)}</text>')
    return ''.join(parts) + '</svg>'


def timeline(ledger):
    end = max((r.get('lane_available_ns') or 0)/1e9 for r in ledger)
    body = ['<svg viewBox="0 0 800 115" role="img" aria-label="PC lane 일정">']
    for backend, y in (('CPU', 32), ('GPU', 70)):
        body.append(f'<text x="0" y="{y+15}">{backend}</text>')
        for r in ledger:
            if r.get('backend') != backend or r.get('dispatch_ns') is None or r.get('lane_available_ns') is None:
                continue
            start, finish = r['dispatch_ns']/1e9, r['lane_available_ns']/1e9
            color = '#0e7490' if r['task'] == 'classification' else '#b45309'
            title = html.escape(f"{r['id']} · dispatch {start:.6f}s → lane {finish:.6f}s")
            body.append(f'<rect x="{55+725*start/max(end,1):.2f}" y="{y}" width="{max(.2,725*(finish-start)/max(end,1)):.2f}" height="23" fill="{color}"><title>{title}</title></rect>')
    body.append(f'<text x="55" y="110">0–{end:.3f}초 · 분류(청록) / 탐지(갈색) · dispatch→lane 해제</text></svg>')
    return ''.join(body)


def fmt(value):
    return '미지원/미확인' if value is None else f'{value:.3f}' if isinstance(value, float) else str(value)


def render(result):
    esc = html.escape
    content = ['<h1>D1Check 시뮬레이터</h1><p>일정 예측 · 실측 참조 · 모형 지원을 분리합니다. experiment_ready=false</p>',
        '<p><a href="result.json">전체 결과·입력·해시 JSON</a> · <a href="summary.csv">수치 CSV</a></p>']
    if result['route'] == 'arrival':
        content.append(f'<p>{result["scenario"]} / seed {result["seed"]} / {result["mode"]} · 24요청 · 공통 120초. strict는 기존 스케줄러 실행 제한이며 물리 모형 검증 PASS가 아닙니다.</p>')
        content.append('<p class="notice">응답은 기존 단독 실측 시간에서 생성한 조건부 PC 계산입니다. 간섭 1.5는 가정입니다. 동적 에너지·AP와 열→처리시간 연결은 미지원으로 차단합니다. 아래 J/AP 관측을 새로운 일정의 예측값으로 사용하지 않습니다.</p><label>정책 <select id="policy">')
        content.extend(f'<option>{p}</option>' for p in POLICIES)
        content.append('</select></label>')
        for index, case in enumerate(result['cases']):
            s = case['service']
            content.append(f'<section data-policy="{case["policy"]}"{(" hidden" if index else "")}><h2>{case["policy"]}</h2>')
            content.append('<h3>PC 일정·서비스</h3><table><tr><th>완료/예정</th><th>urgent P95 ms</th><th>normal 평균 ms</th><th>마감 충족</th><th>서비스 비교 규칙</th><th>예측 J / AP</th></tr>')
            content.append(f'<tr><td>{s["succeeded"]}/{s["planned"]}</td><td>{fmt(s["urgent"]["response_p95_ms"])}</td><td>{fmt(s["normal"]["response_mean_ms"])}</td><td>{s["urgent"]["timely"]+s["normal"]["timely"]}/24</td><td>{"적격" if case["guard"]["eligible"] else "부적격"}</td><td>미지원 / 미지원</td></tr></table>')
            content.append(f'<p>비교 규칙 차단: {esc(case["guard"]["failed_conditions"] or "없음")} · 적격은 정확도나 정책 우월성 PASS가 아닙니다.</p>')
            content.append(timeline(case['ledger']))
            content.append(f'<p>에너지·AP 차단: {esc(case["energy_ap"]["status"])}. 유휴 이력·짧은 전환의 전용 가능 비용이 미검증입니다.</p><h3>별도 기기 관측 참조</h3>')
            if not case['observations']:
                content.append('<p>이 입력·정책·전체 일정에 대응하는 실측 참조 없음. 다른 seed/부하/정책의 J·AP를 대입하지 않습니다.</p>')
            else:
                content.append('<p>저장 일정과 일치하는 재생 실측입니다. 온라인 정책 실행 또는 새 입력의 예측 검증이 아닙니다. 두 관측은 초기 AP·배터리·이력이 다릅니다. 전류 raw=mA 조건부 J, 절대 정확도 미인증.</p><table><tr><th>관측</th><th>J/120초</th><th>초기/최고 AP °C</th><th>urgent P95 ms</th><th>마감</th></tr>')
                for obs in case['observations']:
                    m = obs['summary']
                    content.append(f'<tr><td>{m["index"]}</td><td>{m["energy_j"]:.3f}</td><td>{m["ap_start_c"]:.1f}/{m["ap_peak_c"]:.1f}</td><td>{m["urgent_p95_ms"]:.3f}</td><td>{m["timely_count"]}/24</td></tr>')
                content.append('</table>')
                for key, label in (('energy_path', '관측 누적 J'), ('ap_path', '관측 AP °C')):
                    content.append(plot([(f'관측 {o["summary"]["index"]}', o[key]) for o in case['observations']], label))
            content.append('</section>')
    else:
        r = result['result']
        content.append('<h2>기록된 고정 CC_DG 870건</h2><p>분류 CPU678 + 탐지 GPU192 · 공통480초. 새 도착 입력으로 확장할 수 없습니다. AP는 개발 곡선의 시작값 정렬 가정이며 물리 열법칙이 아닙니다.</p>')
        content.append(f'<p>{esc(r["status"])}: {esc(r["reason"])}</p>')
        content.append('<p>기존 확인 1세션/조건의 오차를 대입한 민감도는 오차 상한이나 신뢰구간이 아닙니다. 제약값은 사용자 탐색 조건이며 안전 기준이 아닙니다.</p><table><tr><th>배정</th><th>계산 종류</th><th>작업 완료 s</th><th>480초 J</th><th>부하 AP 최고 °C</th></tr>')
        for mode, record in r.get('nominal_and_sensitivity', {}).items():
            for kind, values in record.items():
                content.append(f'<tr><td>{mode}</td><td>{"원 모형" if kind == "nominal" else "이미 본 확인 오차 민감도"}</td>'+''.join(f'<td>{fmt(values[k])}</td>' for k in episode.METRICS)+'</tr>')
        content.append('</table>')
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>D1Check 시뮬레이터</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:1050px;margin:32px auto;padding:0 24px;color:#172b3a;background:#f5f8fa}table{border-collapse:collapse;width:100%;background:white}td,th{padding:9px;border-bottom:1px solid #d7e1e7;text-align:left}h2{margin-top:28px}svg{width:100%;background:white;margin:8px 0}svg text{font:13px system-ui}.notice{border-left:4px solid #b45309;padding:12px;background:#fff5de}select{padding:8px;font:inherit}section{padding-bottom:24px}[hidden]{display:none}</style><body>'+''.join(content)+'<script>const p=document.getElementById("policy");if(p)p.addEventListener("change",()=>document.querySelectorAll("[data-policy]").forEach(s=>s.hidden=s.dataset.policy!==p.value));</script></body></html>'


def export(result, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    result['code_sha256'] = {str(p.relative_to(ROOT)).replace('\\', '/'): digest(p)
                            for p in (Path(__file__), Path(engine.__file__), Path(batch.__file__),
                                      Path(accounting.__file__), Path(guard.__file__), Path(episode.__file__),
                                      ROOT / 'tools/d1_cal03_connection.py',
                                      ROOT / 'tools/d1_energy_operational_sim.py')}
    (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    (output / 'index.html').write_text(render(result), encoding='utf-8')
    summary = []
    if result['route'] == 'arrival':
        for c in result['cases']:
            s = c['service']
            summary.append(dict(policy=c['policy'], planned=s['planned'], completed=s['succeeded'],
                timely=s['urgent']['timely']+s['normal']['timely'],
                urgent_p95_ms=s['urgent']['response_p95_ms'], normal_mean_ms=s['normal']['response_mean_ms'],
                service_eligible=c['guard']['eligible'], energy_j=None, ap_peak_c=None,
                energy_ap_status=c['energy_ap']['status'], observed_reference_count=len(c['observations'])))
            with (output / f'{c["policy"]}_schedule.csv').open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=SCHEDULE_FIELDS, extrasaction='ignore')
                writer.writeheader(); writer.writerows(c['ledger'])
    else:
        for mode, record in result['result'].get('nominal_and_sensitivity', {}).items():
            summary.extend(dict(mode=mode, calculation=kind, **v) for kind, v in record.items())
        if not summary:
            summary = [dict(status=result['result']['status'], reason=result['result']['reason'])]
    with (output / 'summary.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=summary[0].keys())
        writer.writeheader(); writer.writerows(summary)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('route', choices=('arrival', 'episode'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--scenario', choices=('low', 'queue', 'burst'), default='queue')
    parser.add_argument('--mode', choices=('strict', 'explore'), default='explore')
    parser.add_argument('--seed', type=int, default=201)
    parser.add_argument('--initial-ap-c', type=float, default=29.1)
    parser.add_argument('--completion-cap-s', type=float)
    parser.add_argument('--ap-cap-c', type=float)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('existing output is preserved; choose a new output directory')
    if args.route == 'arrival':
        if args.initial_ap_c != 29.1 or args.completion_cap_s is not None or args.ap_cap_c is not None:
            parser.error('AP/constraint options belong to the archived episode route only')
        result = arrival(args.scenario, args.mode, args.seed)
    else:
        if (args.scenario, args.mode, args.seed) != ('queue', 'explore', 201):
            parser.error('arrival options do not modify the fixed episode')
        result = fixed_episode(args.initial_ap_c, args.completion_cap_s, args.ap_cap_c)
    export(result, args.output)
    print(json.dumps(dict(route=result['route'], output=str(args.output), device_commands=0,
                         experiment_ready=False), ensure_ascii=True))


if __name__ == '__main__':
    main()
