"""Opt-in model-only session selector; no deployment, fitting, or device API.

The registered workload is known in advance. This is not a per-arrival online
policy. Existing production/strict decision-support guards remain unchanged.
"""
import argparse
import html
import json
import math
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_sustained_protocol as protocol
from tools import d1_sustained_readout as readout

VERSION = 'ENERGY_AP_SESSION_SELECTOR_PC_V1'
ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/results/energy_ap_session_selector_01/contract.json'


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def select(options, ap_cap_c=None):
    """Reference decision rule, NOT a justified real-device recommendation."""
    if len(options) != 2 or {o['policy'] for o in options} != set(protocol.POLICIES):
        raise ValueError('exact two registered actions required')
    for o in options:
        if not all(finite(o[k]) for k in ('energy_0_120_j', 'sampled_peak_ap_35_180_c')):
            raise ValueError('missing/nonfinite cost; never substitute zero')
        if o['energy_0_120_j'] < 0 or o['planned'] != protocol.COUNT:
            raise ValueError('invalid energy or denominator')
        if not 0 <= o['deadline_met'] <= o['completed'] <= o['planned']:
            raise ValueError('invalid service counts')
    if ap_cap_c is not None and not finite(ap_cap_c):
        raise ValueError('finite explicit research AP cap required')
    eligible = [o for o in options if o['completed'] == o['deadline_met'] == o['planned']
                and o['last_lane_s'] <= 120 and ap_cap_c is not None
                and o['sampled_peak_ap_35_180_c'] <= ap_cap_c]
    winner = min(eligible, key=lambda o: (o['energy_0_120_j'],
                 o['sampled_peak_ap_35_180_c'], o['policy'])) if eligible else None
    return dict(version=VERSION, ap_cap_c=ap_cap_c,
                status=('missing_research_cap' if ap_cap_c is None else
                        'model_only_feasible' if winner else 'model_only_infeasible'),
                model_only_action=None if winner is None else winner['policy'],
                eligible_actions=[o['policy'] for o in eligible],
                deployable_action=None, policy_winner=None, accuracy_pass=None,
                future_error_bound=None, dispatch_enabled=False, strict_supported=False,
                experiment_ready=False,
                reason='model design only; future J/AP variation is not bounded; no safety guarantee')


def summarize(prediction, manifest):
    """Use the complete registered request denominator and response boundaries."""
    expected = {r['request_id']: r for r in manifest}
    rows = prediction['forecast']['ledger']
    ids = [r['id'] for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError('missing/duplicate/unexpected request ledger')
    completed = met = 0
    urgent, normal, last = [], [], []
    for r in rows:
        q = expected[r['id']]
        if r['priority'] != q['priority'] or r['arrival_ns'] != q['offset_ms'] * 1_000_000:
            raise ValueError('changed priority/arrival')
        if r['status'] != 'succeeded':
            continue
        times = [r[k] for k in ('dispatch_ns', 'execution_start_ns', 'output_ready_ns',
                               'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')]
        if not all(finite(v) for v in times) or any(b < a for a, b in zip(times, times[1:])):
            raise ValueError('invalid completion boundaries')
        boundary = 'output_ready_ns' if q['priority'] == 'urgent' else 'persist_complete_ns'
        response = (r[boundary] - q['offset_ms'] * 1_000_000) / 1e6
        if response < 0:
            raise ValueError('negative response')
        completed += 1
        met += response <= q['deadline_ms']
        (urgent if q['priority'] == 'urgent' else normal).append(response)
        last.append(r['lane_available_ns'] / 1e9)
    costs = prediction['costs']
    if len(costs['ap_path']) != 146 or not all(finite(v) for v in costs['ap_path']):
        raise ValueError('AP grid incomplete')
    if not costs['energy_path'] or costs['energy_path'][-1]['common_s'] != 120:
        raise ValueError('common energy window')
    if costs['energy_path'][-1]['predicted_j'] != costs['whole_120s_j']:
        raise ValueError('energy path/total disagreement')
    return dict(policy=prediction['policy'], planned=len(expected), completed=completed,
                deadline_met=met, energy_0_120_j=costs['whole_120s_j'],
                sampled_peak_ap_35_180_c=max(costs['ap_path']),
                last_lane_s=max(last) if last else 0,
                urgent_p95_ms=sorted(urgent)[math.ceil(.95 * len(urgent))-1] if urgent else None,
                normal_p95_ms=sorted(normal)[math.ceil(.95 * len(normal))-1] if normal else None)


def frontier(options):
    """Exact thresholds of this two-action reference rule, not tuned AP caps."""
    thresholds = sorted({o['sampled_peak_ap_35_180_c'] for o in options})
    rows = [dict(lower_inclusive_c=None, upper_exclusive_c=thresholds[0],
                 **select(options, math.nextafter(thresholds[0], -math.inf)))]
    for i, low in enumerate(thresholds):
        rows.append(dict(lower_inclusive_c=low,
                         upper_exclusive_c=thresholds[i+1] if i+1 < len(thresholds) else None,
                         **select(options, low)))
    return rows


def run(bundle, index, output, ap_cap_c=None):
    output, bundle = Path(output), Path(bundle)
    if output.exists():
        raise ValueError('new output required')
    contract = p.read(CONTRACT)
    if contract['version'] != VERSION or contract['actions'] != list(protocol.POLICIES):
        raise ValueError('contract/action mismatch')
    contract_sha = p.digest(CONTRACT)
    output.mkdir(parents=True)
    options, predictions = [], []
    for policy in protocol.POLICIES:
        folder = output / policy
        # Keep the original descriptive validation path; do not unlock its
        # energy-ap-policy-selection purpose or promote this calculation to it.
        readout.predict(bundle, index, policy, folder, purpose='descriptive')
        pred = p.read(folder / 'result.json')
        manifest = next(c['manifest_requests'] for c in p.read(bundle/'initial_inputs.json') if c['index'] == index)
        options.append(summarize(pred, manifest))
        predictions.append(pred)
    result = dict(version=VERSION, initial_index=index, options=options,
                  reference_rule=select(options, ap_cap_c), ap_cap_intervals=frontier(options),
                  contract_sha256=contract_sha, model_sha256=p.digest(bundle/'model.json'),
                  inputs_sha256=p.digest(bundle/'initial_inputs.json'),
                  implementation_sha256=p.digest(Path(__file__)),
                  comparisons_not_calculated={
                      'B2_PC': 'old policy namespace/config is not the registered online B2',
                      'B3_SOLO_EFT_PC': 'frozen service vectors are policy-context-specific; dynamic reassignment unvalidated',
                      'P_PAIR_COST_PC': 'CAL03 pair-cost assumptions are not this frozen service model'},
                  independent_selector_validation=False, uses_future_measurements=False,
                  known_future_arrivals=True, device_commands=0, experiment_ready=False)
    if p.digest(CONTRACT) != contract_sha:
        raise ValueError('contract changed during calculation')
    readout.write(output/'summary.json', result)
    readout.csv_write(output/'options.csv', options)
    rows=[]
    for pred in predictions:
        for point in pred['costs']['energy_path']:
            rows.append(dict(policy=pred['policy'],kind='energy',common_s=point['common_s'],value=point['predicted_j']))
        for t, value in zip(range(35,181), pred['costs']['ap_path']):
            rows.append(dict(policy=pred['policy'],kind='AP',common_s=t,value=value))
    readout.csv_write(output/'predicted_curves.csv', rows)
    render(output, result)
    return result


def render(output, result):
    options=result['options']
    data=json.dumps(options,ensure_ascii=False).replace('<','\\u003c')
    body='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>에너지·AP 세션 선택 후보</title>
<style>body{font:16px system-ui;max-width:1050px;margin:32px auto;padding:16px}td,th{padding:9px;border:1px solid #bbb}table{border-collapse:collapse}pre{white-space:pre-wrap}.warn{background:#fff2d9;padding:15px}</style>
<h1>에너지·AP를 선택 기준에 넣는 후보</h1><p>등록된 192요청을 미리 알고, 부하 전 관측으로 CPU 직렬/PAR 고정 배정 중 선택하는 PC 설계. 요청마다 바꾸는 온라인 정책이 아닙니다.</p>
<p class="warn">실측 결과가 아닌 동결 모형 계산입니다. 모형상 후보가 있어도 실제 실행 권고·정책 우월성은 미판정입니다. 기존 strict/선택 차단은 그대로 유지합니다.</p>
<p>목적: 공통0–120초 전체 기기 J 최소화. 조건: 예정192요청 전부 기한 충족·lane 해제120초 이내·35–180초 1초격자 예측 AP 상한. 격자 최고값은 연속 시간의 최고온도나 안전 보장이 아닙니다. AP≠BAT 온도, J≠잔량/사용시간.</p>
<table><thead><tr><th>방식</th><th>기한 충족</th><th>예측 J</th><th>격자 최고 AP °C</th><th>긴급 P95 ms</th></tr></thead><tbody>'''
    for o in options:
        body+='<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in
             (o['policy'],f"{o['deadline_met']}/{o['planned']}",round(o['energy_0_120_j'],6),
              round(o['sampled_peak_ap_35_180_c'],6),round(o['urgent_p95_ms'],3)))+'</tr>'
    body+='''</tbody></table><p><label>연구용 AP 상한 °C <input id="cap" type="number" step="any" placeholder="미설정"></label></p><p id="choice">상한 미설정 — 임의 안전 기준을 정하지 않았습니다.</p>
<h2>모형상 선택의 정확한 분기점</h2><pre>'''+html.escape(json.dumps(result['ap_cap_intervals'],ensure_ascii=False,indent=2))+'''</pre>
<p>실제 미지원 B3/P를 다른 처리시간이나 전력값으로 채우지 않습니다. 미래 실제 완료/AP/전류를 판단에 넣지 않으며, 서비스시간의 온도 의존성·결정 연산 오버헤드는 미검증입니다.</p>
<p><a href="../README.md">정의·판독·재현</a> · <a href="options.csv">수치 CSV</a> · <a href="predicted_curves.csv">예측 곡선 CSV</a></p>'''
    body+='<script>const options='+data+''';document.getElementById('cap').addEventListener('input',e=>{
const text=e.target.value,cap=Number(text),target=document.getElementById('choice');
if(text===''||!Number.isFinite(cap)){target.textContent='상한 미설정';return;}
const eligible=options.filter(o=>o.completed===o.planned&&o.deadline_met===o.planned&&o.last_lane_s<=120&&o.sampled_peak_ap_35_180_c<=cap);
eligible.sort((a,b)=>a.energy_0_120_j-b.energy_0_120_j||a.sampled_peak_ap_35_180_c-b.sampled_peak_ap_35_180_c||a.policy.localeCompare(b.policy));
target.textContent=(eligible.length?'모형상 후보: '+eligible[0].policy:'모형상 조건을 만족하는 후보 없음')+' — 실제 실행 권고 아님';});</script></html>'''
    (output/'index.html').write_text(body,encoding='utf-8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',required=True)
    parser.add_argument('--index',type=int,default=0)
    parser.add_argument('--output',required=True)
    parser.add_argument('--ap-cap-c',type=float)
    args=parser.parse_args()
    result=run(args.bundle,args.index,args.output,args.ap_cap_c)
    print(json.dumps(result,ensure_ascii=False,indent=2))
