"""Bounded read-only failure capture plus PC-only durable-prefix accounting."""
import json
from pathlib import Path
import time

from tools import d1_arrival_device as legacy
from tools import d1_arrival_plan as p

CONTRACT = 'arrival-failure-journal-v1'


def summarize_journal(data, manifest, manifest_sha256=None):
    """Start records bound calls, never complete them. Torn tail is not a valid event."""
    records, invalid = [], None
    expected_hash = manifest_sha256 or p_hash(manifest)
    for i, line in enumerate(data.splitlines(keepends=True)):
        try:
            if not line.endswith(b'\n'):
                raise ValueError('torn final record')
            row = json.loads(line)
            if (row['protocol'] != CONTRACT or row['session_id'] != manifest['session_id']
                    or row['manifest_sha256'] != expected_hash or row['sequence'] != i
                    or row['performance_excluded'] is not True):
                raise ValueError('identity/sequence mismatch')
            if records and row['mono_ns'] < records[-1]['mono_ns']:
                raise ValueError('clock regression')
            records.append(row)
        except (ValueError, KeyError, TypeError) as error:
            invalid = str(error)
            break
    result = dict(valid_prefix_records=len(records), invalid_suffix=invalid,
                  last_record=records[-1] if records else None, performance_eligible=False)
    for stage, collection in [('warmup','warmup_requests'), ('diagnostic','requests')]:
        planned = {q['request_id'] for q in manifest[collection]}
        started, returned, failed = set(), set(), set()
        for row in records:
            if row['stage'] != stage:
                continue
            rid = row['request_id']
            if rid not in planned:
                raise ValueError('unplanned call')
            edge = row['edge']
            if edge == 'start':
                if rid in started:
                    raise ValueError('duplicate start/retry')
                started.add(rid)
            elif edge in ('succeeded','failed','cancelled','timeout'):
                if rid not in started or rid in returned | failed:
                    raise ValueError('orphan/duplicate terminal edge')
                (returned if edge == 'succeeded' else failed).add(rid)
        # Missing/torn records and power loss do not prove that unlogged requests never started.
        result[stage] = dict(planned=len(planned), durable_start_intents=len(started),
            adapter_returned=len(returned), failed_or_cancelled=len(failed),
            intents_without_terminal=len(started-returned-failed),
            no_start_evidence=len(planned-started), actual_call_bounds=[len(returned), len(planned)],
            within_valid_prefix_call_bounds=[len(returned), len(started)],
            official_success_not_inferred=True)
    return result


def p_hash(manifest):
    import hashlib
    return hashlib.sha256(p.canonical(manifest)).hexdigest()


def collect_failure(device, folder, pid=None, seconds=5):
    """Pre-cleanup evidence only; max5s total, max2s/command. Never waits for an app response."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    previous = device.deadline
    device.deadline = min(previous if previous is not None else float('inf'), time.monotonic()+seconds)
    commands = [('processes', ('shell','ps','-A')),
                ('crash', ('logcat','-d','-b','crash','-t','80','-v','threadtime')),
                ('exit_info', ('shell','dumpsys','activity','exit-info',legacy.PACKAGE))]
    if pid and str(pid).isdigit():
        commands.insert(1, ('threads', ('shell','ps','-T','-p',str(pid))))
        commands.insert(2, ('pid_log', ('logcat','-d','-t','160','-v','threadtime','--pid='+str(pid))))
    result = dict(status='partial_or_complete', utc=legacy.utc(), pid=pid,
                  budget_seconds=seconds, cleanup_must_follow=True, commands=[])
    try:
        for name, args in commands:
            if time.monotonic() >= device.deadline:
                result['commands'].append(dict(name=name,status='skipped_budget'))
                continue
            try:
                response=device.call(*args,timeout=2,check=False)
                raw=response.stdout[:262144]
                (folder/(name+'.txt')).write_bytes(raw)
                result['commands'].append(dict(name=name,status='captured' if response.returncode==0 else 'command_failed',
                    returncode=response.returncode, stderr=response.stderr.decode(errors='replace')[:1024],
                    truncated=len(response.stdout)>len(raw)))
            except Exception as error:
                result['commands'].append(dict(name=name,status='capture_failed',error=repr(error)))
    finally:
        device.deadline=previous
    legacy.write_new(folder/'capture.json',result)
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='PC-only journal accounting; never calls ADB')
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = p.read(args.artifacts/'manifest.json')
    journal = args.artifacts/'failure_progress.jsonl'
    # Android hashes the exact manifest bytes, not a parsed/reserialized object.
    result = summarize_journal(journal.read_bytes() if journal.exists() else b'', manifest,
                               p.digest(args.artifacts/'manifest.json'))
    result['journal_present'] = journal.exists()
    legacy.write_new(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
