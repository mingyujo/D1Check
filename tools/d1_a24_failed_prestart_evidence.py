"""Prove closure of a consumed APP rejected before MAIN; never promote to success.

Read-only PC validation. A separately recovered same-session directory may be
used if the original partial archive preceded the final fsync/close artifact.
No device actions, replay, reference re-selection or budget refund are provided.
"""
import json
from pathlib import Path

from d1_a24_laptop_validator import load_json, sha256, PROTOCOL
from d1_a24_revision02_suite import require


def verify_failed_prestart(root: Path, plan: dict, row: dict, recovered: Path, *, plan_sha256: str) -> dict:
    sid = row['session_id']
    registry = root/'registry'/PROTOCOL/plan['plan_id']/sid
    outcome = load_json(root/(sid+'.outcome.json'))
    require(outcome.get('session_id') == sid and outcome.get('status') == 'PRESTART_REJECT'
            and outcome.get('APP_launch_intent') is True, 'not a consumed prestart rejection')
    require(not any((registry/n).exists() for n in ['START.json', 'CLAIM.json', 'COMPLETE.json']),
            'MAIN or claim already recorded')
    reject = load_json(registry/'PRESTART_REJECT.json')
    require(reject.get('START') is False and reject.get('session_run_consumed') is False,
            'rejection does not prove absent MAIN')
    identity = load_json(recovered/'identity.json')
    closed = load_json(recovered/'journal_closed.json')
    cleanup = load_json(recovered/'cleanup.json')
    failure = load_json(recovered/'failure.json')
    ready = load_json(recovered/'ready.json')
    require(identity.get('session_id') == sid and ready.get('session_id') == sid
            and ready.get('plan_sha256') == plan_sha256, 'prepared identity differs')
    pid = identity.get('process_id')
    require(type(pid) is int and pid > 0 and closed.get('session_id') == sid
            and closed.get('process_id') == pid and closed.get('status') == 'SYNCED_AND_CLOSED',
            'failed APP journal not proved closed')
    require(cleanup.get('status') == 'DRAINED' and cleanup.get('actual_return_confirmed') is True
            and cleanup.get('error') is None and bool(cleanup.get('session_failure'))
            and failure.get('status') == 'FAILED', 'failed APP not drained')
    events = [json.loads(x) for x in (recovered/'events.jsonl').read_bytes().splitlines() if x]
    forbidden = {'common_start', 'arrival', 'queue_entry', 'dispatch', 'worker_start',
                 'output_ready', 'request_complete', 'response_complete', 'wait_start'}
    require(events and not any(x.get('kind') in forbidden for x in events),
            'failed-prestart evidence contains MAIN activity')
    requests = load_json(recovered/'requests.json')
    require(len(requests) == row['request_count']
            and all(x.get('terminal_status') == 'UNFINISHED' for x in requests),
            'failed-prestart planned requests missing or completed')
    names = ['identity.json', 'ready.json', 'failure.json', 'cleanup.json',
             'journal_closed.json', 'events.jsonl', 'requests.json']
    files = {name: sha256(recovered/name) for name in names}
    return {'status': 'PROVED_CLOSED_CONSUMED_PRESTART_REJECTION', 'session_id': sid,
            'APP_budget_consumed': 1, 'MAIN_START': False, 'MAIN_completed': 0,
            'planned_unfinished': row['request_count'], 'normal_comparison_eligible': False,
            'automatic_retry': False, 'budget_refund': False, 'process_id': pid,
            'recovered_files_sha256': files, 'outcome_sha256': sha256(root/(sid+'.outcome.json')),
            'PRESTART_REJECT_sha256': sha256(registry/'PRESTART_REJECT.json')}
