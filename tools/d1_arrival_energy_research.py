"""Synthetic arrival research contract and accounting; never a device validation.

The existing arrival engine supplies service events. Fixed CC_DG 870-job power/AP
profiles cannot be spread over arbitrary arrivals. Energy/AP is therefore either
explicitly unsupported or calculated from a caller-supplied assumption profile.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from tools import d1_arrival_explore_batch as batch
from tools import d1_energy_thermal as thermal

VERSION = 'arrival-energy-research-pc-v1'
SCENARIOS = ('low', 'queue', 'burst')
HORIZON_NS = 120_000_000_000


def scenarios():
    """Reuse the pre-existing exploratory traces, without selecting by outcome."""
    return {name: batch.workload(name, 'evaluation') for name in SCENARIOS}


def scenario_manifest():
    result = {}
    for name, rows in scenarios().items():
        payload = json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()
        result[name] = dict(requests=len(rows), urgent=sum(r['priority'] == 'urgent' for r in rows),
                            normal=sum(r['priority'] == 'normal' for r in rows),
                            last_arrival_ns=max(r['arrival_ns'] for r in rows),
                            sha256=hashlib.sha256(payload).hexdigest())
    return dict(version=VERSION, scenarios=result, horizon_ns=HORIZON_NS,
                deadline_origin='existing PC exploratory 1.5s urgent / 6s normal; research assumptions, not SLA',
                comparison_window='0..120s common horizon from first scheduled arrival; no 870-job block deadline',
                energy_scope='unsupported for arbitrary arrivals without an explicit state profile',
                experiment_ready=False)


def _rank95(values):
    return sorted(values)[math.ceil(.95 * len(values))-1] if values else None


def aggregate(requests, result, *, horizon_ns=HORIZON_NS, profile=None, initial_ap_c=None):
    """Full scheduled denominator, explicit response boundaries and common window.

    A completed response is not necessarily a completed request: urgent response is
    output_ready, normal response is persist_complete; lane release is separate.
    Missing/unfinished work is never silently scored as zero-energy success.
    """
    if horizon_ns <= 0 or len({r['id'] for r in requests}) != len(requests):
        raise ValueError('invalid horizon or duplicate IDs')
    if any(r['arrival_ns'] < 0 or r['arrival_ns'] > horizon_ns for r in requests):
        raise ValueError('all scheduled arrivals must lie in the common horizon')
    ledger = result['ledger']
    if {r['id'] for r in ledger} != {r['id'] for r in requests} or len(ledger) != len(requests):
        raise ValueError('ledger/request denominator mismatch')
    planned = {r['id']: r for r in requests}
    groups = {}
    for priority in ('urgent', 'normal'):
        group = [r for r in ledger if r['priority'] == priority]
        responses = []
        timely = late = missing = succeeded = 0
        boundary = 'output_ready_ns' if priority == 'urgent' else 'persist_complete_ns'
        for row in group:
            source = planned[row['id']]
            if any(row[k] != source[k] for k in ('task', 'priority', 'arrival_ns', 'deadline_offset_ns')):
                raise ValueError('ledger changed scheduled request')
            if row.get('status') == 'succeeded':
                succeeded += 1
            t = row.get(boundary)
            if t is None or t > horizon_ns:
                missing += 1
                continue
            if t < row['arrival_ns']:
                raise ValueError('response before arrival')
            responses.append((t-row['arrival_ns'])/1e6)
            if t <= row['arrival_ns'] + row['deadline_offset_ns']:
                timely += 1
            else:
                late += 1
        groups[priority] = dict(planned=len(group), response_observed=len(responses),
            completed_requests=succeeded, timely=timely, late=late, missing_response=missing,
            timely_rate=timely/len(group) if group else None,
            not_confirmed_timely=late+missing,
            not_confirmed_timely_rate=(late+missing)/len(group) if group else None,
            response_p95_ms=_rank95(responses),
            response_mean_ms=sum(responses)/len(responses) if responses else None,
            boundary=boundary)
    for row in ledger:
        if row.get('status') == 'succeeded' and row.get('lane_available_ns', math.inf) > horizon_ns:
            raise ValueError('succeeded without lane release in common horizon')
    unfinished = sum(r.get('status') != 'succeeded' for r in ledger)
    service = dict(planned=len(requests), succeeded=len(requests)-unfinished,
                   unfinished=unfinished, urgent=groups['urgent'], normal=groups['normal'],
                   lane_released=sum(r.get('lane_available_ns', math.inf) <= horizon_ns for r in ledger),
                   horizon_ns=horizon_ns, completion_rate=(len(requests)-unfinished)/len(requests) if requests else None,
                   observed_response_p95_excludes_missing=True)
    if profile is None:
        energy = dict(status='UNSUPPORTED_MISSING_ARRIVAL_STATE_PROFILE',
                      whole_device_energy_j=None, ap_peak_c=None,
                      reason='fixed 870-job profile does not identify request-level, idle, queue or arbitrary overlap costs')
    elif profile.get('evidence') == 'development_episode_template':
        from tools import d1_energy_model_bridge_v2 as measured_bridge
        energy = measured_bridge.engine_support(result, horizon_ns)
    else:
        if (profile.get('evidence') != 'explicit_assumptions' or initial_ap_c is None
                or not isinstance(profile.get('source'), str) or not profile['source'].strip()
                or not isinstance(profile.get('unit_status'), str) or not profile['unit_status'].strip()):
            raise ValueError('only source-labelled assumption profiles with units and initial AP are allowed')
        if unfinished:
            energy = dict(status='UNSUPPORTED_INCOMPLETE_LEDGER', whole_device_energy_j=None,
                          ap_peak_c=None, reason='open occupancy interval cannot be silently called idle')
        else:
            segments = thermal.ledger_segments(result, horizon_ns)
            # Queue occupancy changes whole-device state; do not charge it as an
            # unqualified idle interval. Scheduler cost remains part of the
            # explicitly assumed interval power, not an extra additive charge.
            for segment in segments:
                if segment['waiting']:
                    segment['state'] += '|queued'
            accounting = thermal.account(segments, profile, device=profile['device'],
                model=profile['model'], mode='assumption_exploration',
                initial_temperature={'AP': initial_ap_c}, planned=len(requests),
                completed=len(requests), service_constraints_met=(groups['urgent']['timely'] == groups['urgent']['planned']
                    and groups['normal']['timely'] == groups['normal']['planned']))
            energy = dict(status='ASSUMPTION_EXPLORATION_ONLY',
                          whole_device_energy_j=accounting['energy_j'],
                          ap_peak_c=accounting['peak_temperature']['AP'],
                          common_window_s=accounting['common_window_s'],
                          profile_source=profile.get('source'), state_trace=accounting['trace'])
    return dict(version=VERSION, service=service, energy_ap=energy,
                policy=result.get('policy'), scenario_evidence='synthetic research; not a service SLA',
                experiment_ready=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest-out', type=Path, required=True)
    args = parser.parse_args()
    if args.manifest_out.exists():
        raise FileExistsError(args.manifest_out)
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(scenario_manifest(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
