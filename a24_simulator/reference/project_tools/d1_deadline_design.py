"""Development-profile deadline design only; no simulation or device calls.

CPU context means are engineering references, NOT P95, WCET or user SLAs.
The output is not accepted by the legacy fixed-deadline empirical runner.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'docs/results/online_policy_study_01/overnight_sustained_run01/model.json'
MODEL_SHA = '5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2'
PAIRS = {
    'classification': ('urgent', 'classification_CPU_urgent', 2),
    'detection': ('normal', 'detection_CPU_normal', 3),
}
MULTIPLIERS = ((2, 4), (4, 8), (8, 16))


def reference(model):
    result = {}
    for task, (priority, cell, phases) in PAIRS.items():
        values = []
        for context, service in sorted(model['service'].items()):
            vector = service['phase_means_ns'].get(cell)
            if vector is None:
                continue
            if (len(vector) != 5 or any(isinstance(v, bool) or not isinstance(v, (float, int))
                    or not math.isfinite(v) or v < 0 for v in vector)):
                raise ValueError('invalid complete five-phase vector')
            response_ns = sum(vector[:phases])
            if response_ns <= 0:
                raise ValueError('nonpositive response reference')
            values.append(dict(context=context, response_ns=response_ns,
                               lane_ns=sum(vector)))
        if not values:
            raise ValueError('missing CPU development reference: ' + task)
        response_ns = max(v['response_ns'] for v in values)
        result[task] = dict(priority=priority, cell=cell, contexts=values,
                            reference_ns=math.ceil(response_ns / 1_000_000) * 1_000_000,
                            unrounded_response_ns=response_ns,
                            reference_kind='maximum_of_development_context_means_not_quantile')
    return result


def design(model):
    refs = reference(model)
    scenarios = []
    for index, (urgent, normal) in enumerate(MULTIPLIERS, 1):
        multipliers = dict(classification=urgent, detection=normal)
        scenarios.append(dict(id=f'normalized_{index}',
            relative_deadline_ns={t: multipliers[t] * refs[t]['reference_ns'] for t in PAIRS},
            response_multipliers=multipliers,
            interpretation='engineering_sensitivity_not_user_SLA'))
    scenarios.append(dict(id='legacy_1500_6000',
        relative_deadline_ns=dict(classification=1_500_000_000, detection=6_000_000_000),
        response_multipliers={t: d / refs[t]['unrounded_response_ns'] for t, d in
                             [('classification', 1_500_000_000), ('detection', 6_000_000_000)]},
        interpretation='historical_comparison_not_new_validation'))
    return dict(version='deadline-design-v1', status='design_only_runner_not_connected',
                references=refs, scenarios=scenarios, user_sla=None,
                precision_claim=None, experiment_ready=False,
                multiplier_basis='preregistered_factor_two_sensitivity_choice_not_measured_tolerance')


def assign(tickets, scenario):
    """Pure input construction. Deadlines never depend on chosen backend/outcome."""
    result = copy.deepcopy(tickets)
    for ticket in result:
        task = ticket['task']
        if task not in PAIRS or ticket['priority'] != PAIRS[task][0]:
            raise ValueError('unsupported task/priority')
        deadline = scenario['relative_deadline_ns'][task]
        if type(deadline) is not int or deadline <= 0:
            raise ValueError('invalid relative deadline')
        ticket['deadline_offset_ns'] = deadline
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = MODEL.read_bytes()
    if hashlib.sha256(data).hexdigest() != MODEL_SHA:
        raise ValueError('frozen model hash mismatch')
    result = design(json.loads(data))
    result['source'] = dict(model=MODEL.relative_to(ROOT).as_posix(), sha256=MODEL_SHA,
                           producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    # Fail closed on an existing output; original designs cannot be overwritten.
    with args.output.open('x', encoding='utf8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print('deadline design written; simulation=0 device=0; runner not connected')


if __name__ == '__main__':
    main()
