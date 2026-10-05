"""PC-only design check. Intentionally has no device runner or subprocess API."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'docs/results/resident_control_design_01'
ID = 'ENERGY-AP-RESIDENT-CONTROL-DESIGN-01'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(plan):
    assert plan['id'] == ID
    assert plan['status'] == 'DESIGN_CHECKED_EXECUTION_BLOCKED'
    assert plan['approved'] is False and plan['execution_ready'] is False
    assert plan['candidate_apk_sha256'] is None
    assert plan['run_command'] is None
    assert [x['role'] for x in plan['sessions']] == ['no_load_control', 'registered_load']
    assert [x['work_requests'] for x in plan['sessions']] == [0, 24]
    assert all(x['runtime'] == 4 and x['warmup'] == 8 for x in plan['sessions'])
    b = plan['proposed_budget']
    assert b['sessions'] == 2 and b['work_requests'] == 24
    assert b['explicit_inferences'] == b['work_requests'] + b['warmup'] == 40
    assert b['warmup'] == 16 and b['runtime'] == 8 and b['eligibility_inferences'] == 0
    assert b['staging'] == 2 and b['staging_files'] == 14
    assert b['retry'] == b['replacement'] == b['additional'] == 0
    assert b['session_seconds'] == sum(b[k] for k in
        ('stage_gate_seconds', 'poll_seconds', 'recovery_seconds', 'cleanup_seconds')) == 700
    assert b['total_seconds'] == b['installation_seconds'] + 2*b['session_seconds'] + b['between_seconds'] == 2090
    assert b['fixed_observation_seconds'] == 2*(30+120+60) == 420
    # Deliberately include a possible initial poll at t=0 for each command kind.
    per = math.ceil(b['poll_seconds']/.25)+1 + 3*(math.ceil(b['poll_seconds']/2)+1) + math.ceil(b['poll_seconds']/10)+1
    assert per == 2723 and b['adb_commands'] == 6600
    assert b['nonpoll_command_allowance'] == b['adb_commands'] - 2*per == 1154
    for file, sha in plan['evidence_sha256'].items():
        assert digest(ROOT/file) == sha, 'evidence changed: '+file
    schedule = json.loads((BUNDLE/'load_input.json').read_text(encoding='utf-8'))
    assert len(schedule['requests']) == 24
    assert schedule['shift_seconds'] == 35 and schedule['common_window_seconds'] == 120
    assert all(q['recorded_backend'] == ('GPU' if q['task_id'] == 'classification' else 'CPU')
               and q['offset_ms']*1_000_000 <= q['release_offset_ns'] < 120_000_000_000
               for q in schedule['requests'])
    assert len(plan['execution_blockers']) == 3
    return dict(design_check='passed', execution_ready=False,
                status=plan['status'], device_commands=0,
                blockers=plan['execution_blockers'], proposed_budget=b)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check'])
    parser.add_argument('--plan', type=Path, default=BUNDLE/'design_plan.json')
    args = parser.parse_args()
    result = check(json.loads(args.plan.read_text(encoding='utf-8')))
    result['design_plan_sha256'] = digest(args.plan)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
