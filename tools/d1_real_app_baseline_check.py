"""Bounded PC compatibility check; not Ente execution or a performance simulation.

Only an existing D1Check admission rule is exercised. No app source is imported,
no inference runs, and no model coefficients or execution plans are changed.
"""
import argparse
import hashlib
import json
from pathlib import Path

from tools.d1_arrival_interaction import InteractionGate, DEFAULT_IDLE_NS


SOURCES = {
    'compute_controller.dart': 'd949ce675121aa2544c932156c524ad8cc1170d9a5b26b5bfe1383244d9f51c6',
    'ml_service.dart': 'c49419ec9868ee6c52341e42cb40b0d75d23d2eba9d46a543f9633321aea405b',
    'ml_run_control.dart': '049af2fb7e1948594aa72078e31b2235c81d25608d3ab052d76e0a4f04128e11',
    'device_health_policy.dart': 'd6baa3d41cd8a60c172e8764883cad63ebeef3334fd25527fef18b7265e25cea',
}
COMMIT = 'a492f9db8e67def81d5f17c687f69b5778ec0df3'
NS = 1_000_000_000


def gate_bound(name, arrival_s, interactions_s, expected_wait_s, expected_blocked):
    arrival = arrival_s * NS
    gate = InteractionGate([dict(id=f'interaction-{i}', at_ns=t * NS)
                            for i, t in enumerate(interactions_s)])
    while gate.next_event() is not None and gate.next_event() <= arrival:
        now = gate.next_event()
        gate.interactions_at(now)
        gate.expiries_at(now)
    normal = dict(id='background', priority='normal')
    urgent = dict(id='interactive', priority='urgent')
    normal_allowed = normal in gate.eligible([normal], arrival)
    earliest = max(arrival, gate.blocked_until_ns or arrival)
    wait = (earliest - arrival) / NS
    assert wait == expected_wait_s and (not normal_allowed) == expected_blocked
    assert urgent in gate.eligible([urgent], arrival)  # D1 adaptation, NOT an Ente urgent queue.
    return dict(case=name, arrival_s=arrival_s, observed_interactions_s=interactions_s,
                earliest_dispatch_bound_s=earliest / NS, minimum_wait_s=wait,
                d1_normal_deadline_s=6, deadline_impossible_even_with_zero_service=wait > 6,
                bound_assumptions='no later interaction; health and resource available; service time unknown nonnegative',
                measured_response_s=None, energy_j=None, ap_c=None,
                source_behavior_equivalence='not_tested; D1 request-level adaptation only')


def result(source_dir=None):
    verified = False
    if source_dir:
        for name, digest in SOURCES.items():
            if hashlib.sha256((source_dir / name).read_bytes()).hexdigest() != digest:
                raise ValueError('pinned upstream source mismatch: ' + name)
        verified = True
    assert DEFAULT_IDLE_NS == 15 * NS
    cases = [gate_bound('interaction_at_arrival', 0, [0], 15, True),
             gate_bound('one_second_after_interaction', 1, [0], 14, True),
             gate_bound('ten_seconds_after_interaction', 10, [0], 5, True),
             gate_bound('exact_expiry', 15, [0], 0, False),
             gate_bound('reset_before_expiry', 15, [0, 14], 14, True),
             gate_bound('no_interaction', 0, [], 0, False)]
    return dict(id='REAL-APP-BASELINE-PC-01', selected_real_app='Ente Photos',
                upstream_commit=COMMIT, source_sha256=SOURCES,
                source_bytes_verified=verified,
                scope='foreground Android background-ML start permission, source-pinned; no override/force',
                production_release_binary_verified=False, original_app_executed=False,
                original_dart_callbacks_executed=False, cases=cases,
                direct_d1_vs_ente_performance_comparison_ready=False,
                blockers=['different tasks/runtime/quality and completion semantics',
                          '15s background admission versus D1 6s engineering deadline',
                          'D1 initial idle differs from Ente foreground initialization',
                          'D1 urgent exemption and request boundary are not Ente stages',
                          'original app and paired intervention not built or validated'],
                next_boundary='reproduce selected original Ente workflow before any app-level performance claim',
                device_commands=0, inference_calls=0, new_measurement_plan=False,
                experiment_ready=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    data = result(args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(cases=len(data['cases']), source_bytes_verified=data['source_bytes_verified'],
                          comparison_ready=False, device_commands=0)))


if __name__ == '__main__':
    main()
