"""SYNTHETIC — 파이프라인 검증 전용. 어떤 주장에도 쓰지 않음.

Builds a config/vectors pair in 조민규's CAL-03 8-cell schema so his engine can run.
Only the S->O medians come from his published table (ARRIVAL_CAL03_EXECUTION_20260924.md:56-63);
every other interval is an arbitrary placeholder and is labelled as such.
Every request keeps all five lane intervals because his engine stores urgent results too;
the per-priority response/lane applicability comes from his own `calibration.usage`.
"""
from __future__ import annotations

MS = 1_000_000

# 조민규 CAL-03 development medians of start_to_output_ready (ms). Published values.
S_TO_O_MS = {
    'classification_CPU_normal': 96.407, 'classification_CPU_urgent': 94.094,
    'classification_GPU_normal': 240.138, 'classification_GPU_urgent': 237.666,
    'detection_CPU_normal': 553.166, 'detection_CPU_urgent': 548.513,
    'detection_GPU_normal': 1054.499, 'detection_GPU_urgent': 1072.072,
}
# Arbitrary placeholders (not measured anywhere).
ARBITRARY_MS = dict(decision_to_dispatch=1.0, dispatch_to_start=5.0,
                    output_ready_to_persist=70.0, persist_to_worker=2.0, worker_to_lane=3.0)
VECTOR_SPREAD = (0.97, 0.99, 1.01, 1.03)  # arbitrary realisation spread around the median

PROVENANCE = {
    'status': 'SYNTHETIC',
    'claim_use': 'none — pipeline check only',
    'start_to_output_ready': 'published median, ARRIVAL_CAL03_EXECUTION_20260924.md:56-63',
    'other_intervals': 'arbitrary placeholder',
    'vector_spread': 'arbitrary placeholder',
}


def ns(ms):
    """His schema requires nonnegative integer nanoseconds."""
    return int(round(ms * MS))


def build(c, legacy):
    """c = his d1_cal03_connection, legacy = his d1_arrival_timing_dev."""
    a = ARBITRARY_MS
    cells, vectors = {}, {}
    for key in sorted(c.CELLS):
        priority = key.rsplit('_', 1)[1]
        so = S_TO_O_MS[key]
        pl = a['persist_to_worker'] + a['worker_to_lane']
        phase_ms = dict(zip(legacy.ALL_FIELDS, (a['decision_to_dispatch'], a['dispatch_to_start'], so,
                                                 a['output_ready_to_persist'], pl)))
        phases = {f: dict(c.stats([ns(v)] * 4), response_use=c.calibration.usage(priority, f, 'response'),
                          lane_use=c.calibration.usage(priority, f, 'lane_from_dispatch'))
                  for f, v in phase_ms.items()}
        response = a['dispatch_to_start'] + so + (0 if priority == 'urgent' else a['output_ready_to_persist'])
        joint_ms = dict(dispatch_to_response_ns=response,
                        dispatch_to_lane_ns=a['dispatch_to_start'] + so + a['output_ready_to_persist'] + pl,
                        start_to_lane_ns=so + a['output_ready_to_persist'] + pl,
                        output_to_lane_ns=a['output_ready_to_persist'] + pl,
                        persist_to_lane_ns=pl)
        cells[key] = dict(observed_phases=phases, adaptive_decision_to_dispatch_ns=None,
                          joint={k: c.stats([ns(joint_ms[k])] * 4) for k in c.JOINTS})
        vectors[key] = [dict(source_request_id=f'SYNTHETIC/{key}/{i}',
                             durations_ns=[ns(a['dispatch_to_start']), ns(so * f), ns(a['output_ready_to_persist']),
                                           ns(a['persist_to_worker']), ns(a['worker_to_lane'])])
                        for i, f in enumerate(VECTOR_SPREAD)]
    config = dict(protocol=c.VERSION, policy=c.POLICY, experiment_ready=False,
                  scope=dict(maximum_concurrency=1, unit='ns'), cells=cells)
    c.validate_config(config)  # his validator — schema conformance evidence
    return config, dict(protocol=c.VERSION, cells=vectors)
