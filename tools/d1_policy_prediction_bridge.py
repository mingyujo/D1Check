"""Connect prospective policy schedules to unchanged empirical model diagnostics.

This path admits no measured future schedule, current, or AP target as input.
Computability is explicitly separate from measurement support and validation.
"""
import argparse
import copy
import csv
import html
import json
import math
from pathlib import Path

from tools import d1_simulator as sim
from tools import d1_ap_completion_model as ap
from tools import d1_arrival_policy_screen as screen
from tools.d1_arrival_recorded_replay_analysis import state_key

CONTRACT = sim.RESULTS / 'policy_prediction_bridge_01/contract.json'


class StartFloor:
    """Existing engine admission seam: delay dispatch, never move arrivals/deadlines."""
    def __init__(self, until_ns):
        self.until = until_ns
        self.released = False

    def interactions_at(self, now):
        if not self.released and now >= self.until:
            self.released = True
            return True
        return False

    def expiries_at(self, now):
        return False

    def next_event(self):
        return None if self.released else self.until

    def eligible(self, queue, now):
        return queue if now >= self.until else []

    def check_dispatch(self, request, now, pending):
        return now >= self.until

    def snapshot(self, queue, now):
        return dict(start_floor_ns=self.until, released=self.released)


def initial_inputs(case_id, register=sim.AP_REGISTER):
    spec = sim.read(register)
    for rel, expected in spec['files'].items():
        file = (sim.ROOT / rel).resolve()
        if not file.is_relative_to(sim.ROOT) or sim.digest(file) != expected:
            raise ValueError('frozen AP resource changed: ' + rel)
    if any(spec[key] not in spec['files'] for key in ('cases_file', 'model_file')):
        raise ValueError('unbound AP source')
    matches = [c for c in sim.read(sim.ROOT / spec['cases_file']) if c['id'] == case_id]
    if len(matches) != 1 or case_id not in spec['case_ids']:
        raise ValueError('unknown initial observation')
    # Whitelist, not a copy of the observed case: no future schedule or targets.
    return copy.deepcopy(matches[0]['inputs']['preload']), sim.read(sim.ROOT / spec['model_file'])


def predict(requests, *, policy, hold_s, preload, model, power_w, config, vectors,
            settings, seed):
    if policy not in sim.POLICIES or not math.isfinite(hold_s) or not 0 <= hold_s <= 2:
        raise ValueError('unsupported policy or bounded hold')
    if not requests or any(r['arrival_ns'] < 35_000_000_000 for r in requests):
        raise ValueError('requests must follow initialization cutoff')
    admission = StartFloor(35_000_000_000 + round(hold_s * 1e9)) if hold_s else None
    result = sim.engine.simulate(config, vectors, copy.deepcopy(requests), policy=policy,
        settings=copy.deepcopy(settings), seed=seed, admission=admission)
    service = sim.accounting.aggregate(requests, result)['service']
    answer = dict(policy=policy, start_hold_s=hold_s, service=service, ledger=result['ledger'],
        strict_support=False, independent_accuracy_pass=None, policy_rank=None,
        experiment_ready=False, future_measurements_used=False,
        thermal_performance_feedback='unidentified; no throttle curve introduced')
    if service['unfinished']:
        return dict(answer, diagnostic=None, reason='incomplete lane occupancy; no partial full-window cost')
    segments = screen.occupancy(result, 'queue', settings['interference'], seed, policy)
    missing_power = sorted({state_key(s['state']) for s in segments} - power_w.keys())
    missing_ap = sorted({state_key(s['state']) for s in segments} - model['parameters']['ap_slope_at_30_c_per_s'].keys())
    cumulative = 0.
    energy_path = [dict(common_s=0., predicted_j=0.)]
    prospective = 0.
    if not missing_power:
        for s in segments:
            w = power_w[state_key(s['state'])]
            if not math.isfinite(w) or w < 0:
                raise ValueError('invalid whole-device power')
            cumulative += (s['end_s'] - s['start_s']) * w
            prospective += max(0., s['end_s'] - max(35., s['start_s'])) * w
            energy_path.append(dict(common_s=s['end_s'], predicted_j=cumulative))
    ap_path = None
    initial = None
    if not missing_ap:
        ap_segments = copy.deepcopy(segments)
        ap_segments.append(dict(start_s=120., end_s=180., state='idle'))
        times = list(range(35, 181))
        values, initial = ap.predict({'inputs':dict(preload=preload, segments=ap_segments, query_s=times)}, model)
        ap_path = [dict(common_s=t, predicted_c=v) for t, v in zip(times, values)]
    state_seconds = {}
    for s in segments:
        state_seconds[s['state']] = state_seconds.get(s['state'], 0.) + s['end_s'] - s['start_s']
    unsupported_reasons = ['short transition/queue/callback transfer not independently validated',
        'service interference 1.5 is an assumption, not a measured response law',
        'preparation AP is a supplied initial condition, not an ambient measurement']
    if any(s not in ('idle','classification:GPU','detection:CPU','classification:GPU+detection:CPU') for s in state_seconds):
        unsupported_reasons.append('selected M0 confirmation did not cover all resource states in this policy')
    return dict(answer, diagnostic=dict(
        whole_120s_j=None if missing_power else cumulative,
        prospective_35_120s_j=None if missing_power else prospective,
        whole_window_role='0..35 retrospective idle component plus 35..120 prospective schedule forecast',
        energy_path=None if missing_power else energy_path, ap_path=ap_path, initial=initial,
        ap_peak_c=None if ap_path is None else max(p['predicted_c'] for p in ap_path),
        missing_power_states=missing_power, missing_ap_states=missing_ap,
        state_seconds=state_seconds, segments=segments,
        status='frozen_formula_extrapolation_not_validated_policy_prediction',
        unresolved=unsupported_reasons))


def run(contract=CONTRACT):
    spec = sim.read(contract)
    if spec['version'] != 'policy-prediction-bridge-v1':
        raise ValueError('contract version')
    provenance = sim.verify_resources()
    preload, model = initial_inputs(spec['initialization_case_id'])
    config, vectors = sim.read(sim.BUNDLE/'estimates.json'), sim.read(sim.BUNDLE/'realizations.json')
    settings = sim.batch.defaults('explore')
    settings.update(sim.read(sim.FREEZE)['B2']['explore']['settings'])
    requests = sim.batch.workload(spec['scenario'], 'evaluation')
    for r in requests:
        r['arrival_ns'] += round(spec['arrival_origin_s'] * 1e9)
    cases = [predict(requests,policy=arm['policy'],hold_s=arm['start_hold_s'],preload=preload,
        model=model,power_w=spec['whole_device_power_w'],config=config,vectors=vectors,
        settings=settings,seed=spec['seed']) for arm in spec['arms']]
    reference = sim.guard_row(cases[0]['policy'], cases[0]['service'], spec['scenario'], spec['seed'])
    for c in cases:
        c['service_guard'] = sim.service_guard(sim.guard_row(c['policy'],c['service'],spec['scenario'],spec['seed']),
            reference, sim.read(sim.guard.CONTRACT))
    return dict(version=spec['version'], contract_sha256=sim.digest(contract), cases=cases,
        requests=requests, provenance=provenance, source_ap_register_sha256=sim.digest(sim.AP_REGISTER),
        assumptions=dict(interference=settings['interference'], source='unchanged original PC engine settings'),
        initial_observation_source=spec['initialization_case_id'], new_fit=0, device_commands=0,
        observed_comparison=None, independent_end_to_end_validation=False,
        original_research_goal_complete=False, experiment_ready=False)


def export(result, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    rows = []
    for c in result['cases']:
        d = c['diagnostic'] or {}
        rows.append(dict(policy=c['policy'],hold_s=c['start_hold_s'],planned=c['service']['planned'],
            unfinished=c['service']['unfinished'],urgent_p95_ms=c['service']['urgent']['response_p95_ms'],
            service_guard=c['service_guard']['eligible'],diagnostic_120s_j=d.get('whole_120s_j'),
            diagnostic_ap_peak_c=d.get('ap_peak_c'),validated_policy_cost=False,policy_rank=None))
    with (output/'summary.csv').open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    body='<h1>원래 목표: 도착·배정·대기 → 일정·응답·에너지·AP</h1><p>PC 연결 구현 완료, 원래 연구 목표는 진행 중입니다. 아래 곡선은 예정 입력과 동결식의 외삽 계산이며 새 실측이나 독립 예측 검증 결과가 아닙니다. 이후 관측 AP·전류·실제 실행시간을 입력으로 쓰지 않습니다. 우열/정확도 PASS 없음.</p>'
    for c in result['cases']:
        body+='<h2>'+html.escape(c['policy'])+' / 시작 대기 '+str(c['start_hold_s'])+'초</h2>'
        body+='<p>응답 P95 '+str(round(c['service']['urgent']['response_p95_ms'],3))+'ms; 서비스 조건 '+str(c['service_guard']['eligible'])+'</p>'
        d=c['diagnostic']
        if d:
            if d['ap_path']: body+=sim.plot([('동결 M0 외삽',[[p['common_s'],p['predicted_c']] for p in d['ap_path']])],'AP °C')
            if d['energy_path']: body+=sim.plot([('원래 W식 외삽',[[p['common_s'],p['predicted_j']] for p in d['energy_path']])],'누적 J')
            body+='<p>'+html.escape('; '.join(d['unresolved']))+'</p>'
    (output/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>정책 예측 연결</title><style>body{font:16px system-ui;max-width:1000px;margin:auto;padding:24px}svg{max-width:100%}</style>'+body+'<p><a href="summary.csv">수치</a> · <a href="result.json">입력·경계·가정</a></p></html>',encoding='utf8')


def main():
    q=argparse.ArgumentParser(description=__doc__);q.add_argument('--output',required=True,type=Path)
    a=q.parse_args();export(run(),a.output)
    print('PC prospective policy bridge exported; independent validation pending; device commands 0')


if __name__ == '__main__':
    main()
