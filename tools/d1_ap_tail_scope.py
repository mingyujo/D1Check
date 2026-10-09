"""Explicit, AP-only diagnostic guard. Never used by default/strict/RL engines."""
import argparse
import hashlib
import json
import math
import traceback
from pathlib import Path

from tools import d1_ap_tail_identification as tail

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / 'docs/results/ap_tail_scope_01/scope.json'
SCOPE_SHA = 'c630f315c31efd1d06ec9e215c41723e67bf8338b20453c73d923242112656c8'
PREDICTOR_SOURCE_HASHES = {
    'tools/d1_ap_tail_identification.py': '024826a99f8840eaf57be4a935708351ffa08e722606fd0a0012478890595265',
    'tools/d1_resident_ap_structure.py': '5e038256882073ac55d3557d6b6f810a2c9cff82c0453444104c8c5b0d2542dc',
    'tools/d1_model_refinement.py': '81c668d0e3d347ecadbcece17ad452f392c9cbef9b6252a1e051bf57a362c9cb',
    'tools/d1_ap_completion_model.py': 'd40f26595b04a10641eb0501673e94962483165925ad5a84a74b7ab5a9c44ded',
    'tools/d1_ap_preparation_memory.py': '20af3304f8386c7f6adc1df56f5c593e0fd35600ae60d2ce60a518d5c418c40d',
    'tools/d1_ap_idle_response.py': '2812472aa31386158a616559955e1bd88d849a5a96e5f5ffc4c59ccc73a2efe6',
    'tools/d1_arrival_recorded_replay_analysis.py': '16314a0e756a380f060d2d20627ce6a284c48442871b29ace9a5d9744ebb52ea',
    'tools/d1_resident_identification_plan.py': 'd7b04c707d338f4e45c02f1a0ddfe0270b0a907aa039b04801c11b73c0d57597',
    'tools/d1_energy_collection.py': '8e7027d172425c476d819ac8eecb8e54f68dd843425f5c03daefa6657c06efdd',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_sha(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def read_assets():
    if sha(SCOPE) != SCOPE_SHA:
        raise ValueError('diagnostic scope changed')
    scope = tail.s.j.m.read(SCOPE)
    for path, key in ((scope['model_file'], 'model_file_sha256'),
                      (scope['original_model_file'], 'original_model_sha256')):
        if sha(ROOT / path) != scope[key]:
            raise ValueError('frozen asset changed: ' + path)
    for path, expected in PREDICTOR_SOURCE_HASHES.items():
        if source_sha(ROOT / path) != expected:
            raise ValueError('predictor code changed: ' + path)
    return scope, tail.s.j.m.read(ROOT / scope['original_model_file']), \
        tail.s.j.m.read(ROOT / scope['model_file'])['LOAD_SLOW']


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def same(value, expected):
    # Python considers True == 1; a boolean cannot assert an integer runtime contract.
    return type(value) is type(expected) and value == expected


def schedule_reasons(case, scope):
    """Input geometry only: no outcomes, winning IDs, targets or future sensor values."""
    reasons = []
    profile = case.get('policy')
    if profile not in scope['profiles']:
        reasons.append('unregistered_profile_or_arrival_schedule')
    if case.get('common_end_s') is None:
        reasons.append('common_window_unrecorded_in_case')
    elif case.get('common_end_s') != scope['common_end_s']:
        reasons.append('common_window_mismatch')
    pre = case.get('pre')
    try:
        last = pre[-1]['ap']
        lo, hi = scope['observed_pre_last_ap_range_c']
        if not finite(last) or not lo <= last <= hi:
            reasons.append('pre_last_AP_outside_candidate_development_context')
        if any(not all(finite(p[k]) for k in ('t', 'ap', 'lo', 'hi')) or
               not p['lo'] <= p['t'] <= p['hi'] < scope['load_start_s'] for p in pre):
            reasons.append('invalid_or_future_preload_AP')
    except (KeyError, IndexError, TypeError):
        reasons.append('missing_preload_AP')
    segments, query = case.get('actual'), case.get('q')
    try:
        cursor = scope['schedule_origin_s']
        for seg in segments:
            a, b = seg['start_s'], seg['end_s']
            state = tail.s.j.m.thermal.state_key(seg['state'])
            if not finite(a) or not finite(b) or b <= a or abs(a - cursor) > 1e-6:
                reasons.append('noncontiguous_or_invalid_lane_schedule'); break
            if state not in ('resident_idle',) + tail.s.STATES:
                reasons.append('unsupported_task_backend_state'); break
            if state != 'resident_idle' and a < scope['load_start_s']:
                reasons.append('work_before_initialization_cutoff'); break
            cursor = b
        if not segments:
            reasons.append('missing_lane_schedule')
        if profile in scope['profiles']:
            variant = next(v for v in scope['variants'].values() if profile in v['profiles'])
            a, b = variant['schedule_end_range_s']
            if not a <= cursor <= b:
                reasons.append('observation_horizon_mismatch')
        if not query or any(not finite(t) for t in query) or query[0] < scope['load_start_s'] or \
                query[-1] > cursor or any(not 0 < b-a <= 10 for a, b in zip(query, query[1:])):
            reasons.append('invalid_or_uncovered_query_times')
        if profile == 'C0_LONG':
            if any(tail.s.j.m.thermal.state_key(z['state']) != 'resident_idle' for z in segments):
                reasons.append('C0_has_registered_work')
        elif profile in ('DEV_A', 'DEV_B', 'LOAD_A_LONG'):
            check = dict(case, policy='DEV_A' if profile == 'LOAD_A_LONG' else profile)
            if not tail.s.registered_schedule(check):
                reasons.append('state_entry_exit_or_order_outside_registered_blocks')
    except (KeyError, TypeError, ValueError, IndexError):
        reasons.append('malformed_schedule_or_query')
    return list(dict.fromkeys(reasons))


def forecast(case, context, *, opt_in=False):
    scope, original, model = read_assets()
    result = dict(status='blocked', reasons=[], prediction_ap_c=None, energy_prediction_j=None,
                  response_prediction_s=None, strict_support=False, accuracy_pass=None,
                  default_changed=False, rl_changed=False, experiment_ready=False,
                  time_identified=False, candidate_application_allowed=model['application_allowed'])
    if not isinstance(case, dict) or not isinstance(context, dict):
        result['reasons'] = ['malformed_case_or_context']
        return result
    if opt_in is not True:
        result['reasons'].append('explicit_diagnostic_opt_in_required')
    result['reasons'].extend(schedule_reasons(case, scope))
    for key, expected in scope['expected_context'].items():
        if not same(context.get(key), expected):
            result['reasons'].append('context_mismatch:' + key)
    profile = case.get('policy')
    variant = next((v for v in scope['variants'].values() if profile in v['profiles']), None)
    if variant:
        for key in ('protocol', 'apk_sha256', 'screen_observation'):
            if not same(context.get(key), variant[key]):
                result['reasons'].append('context_mismatch:' + key)
        result['evidence'] = variant['evidence']
    if result['reasons']:
        return result
    # Strip every measured target and post-load power field before numerical prediction.
    predictor_input = dict(pre=[{k: row[k] for k in ('t', 'ap', 'lo', 'hi')} for row in case['pre']],
                           actual=[{k: row[k] for k in ('start_s', 'end_s', 'state')}
                                   for row in case['actual']], q=list(case['q']))
    try:
        pred, parts = tail.predict(predictor_input, original, model)
    except (ValueError, KeyError, TypeError) as error:
        result.update(status='calculation_failed', reasons=['original_predictor_rejected_input'],
                      original_error=dict(type=type(error).__name__, message=str(error),
                                          stack=traceback.format_exc()))
        return result
    result.update(status='diagnostic_AP_only', prediction_ap_c=pred, decomposition=parts,
                  query_window_s=[case['q'][0], case['q'][-1]],
                  prediction_layer='actual_schedule_conditional',
                  diagnostic_context_matches=True, physical_cause_identified=False)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--context', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--opt-in', action='store_true')
    args = parser.parse_args()
    result = forecast(tail.s.j.m.read(args.case), tail.s.j.m.read(args.context), opt_in=args.opt_in)
    with Path(args.output).open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'reasons', 'strict_support', 'accuracy_pass')}))


if __name__ == '__main__':
    main()
