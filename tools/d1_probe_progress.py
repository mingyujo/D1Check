"""Validate a separately retrieved, possibly incomplete MODEL-02B diagnostic journal."""
import argparse
import json
import re
import uuid
from pathlib import Path


def validate_progress(text, session_id, manifest_sha256):
    if str(uuid.UUID(session_id)) != session_id or not re.fullmatch('[a-f0-9]{64}', manifest_sha256):
        raise ValueError('invalid expected identity')
    if not text.endswith('\n'):
        raise ValueError('truncated journal; preserve raw bytes but do not accept evidence')
    rows = [json.loads(line) for line in text.splitlines()]
    if not rows:
        raise ValueError('empty journal')
    bound = False
    previous = -1
    opened = []
    for sequence, row in enumerate(rows):
        if set(row) != {'protocol', 'session_id', 'manifest_sha256', 'sequence', 'mono_ns', 'clock', 'phase', 'edge', 'thread_id'}:
            raise ValueError('progress fields mismatch')
        if row['protocol'] != 'model-probe-progress-v1' or row['session_id'] != session_id or row['sequence'] != sequence:
            raise ValueError('stale/replayed or discontinuous progress')
        if row['clock'] != 'elapsedRealtimeNanos' or type(row['mono_ns']) is not int or row['mono_ns'] < max(previous, 0):
            raise ValueError('invalid monotonic clock')
        previous = row['mono_ns']
        if row['phase'] == 'manifest_binding':
            if bound or row['edge'] != 'finish':
                raise ValueError('duplicate/invalid binding')
            bound = True
        if row['manifest_sha256'] != (manifest_sha256 if bound else None):
            raise ValueError('manifest binding mismatch')
        if not re.fullmatch('[a-z0-9_]+', row['phase']) or row['edge'] not in ('start', 'finish', 'failed'):
            raise ValueError('invalid phase')
        if row['edge'] == 'start':
            opened.append(row['phase'])
        elif row['phase'] != 'manifest_binding':
            if not opened or opened[-1] != row['phase']:
                raise ValueError('unmatched phase edge')
            opened.pop()
    if not bound:
        raise ValueError('no validated manifest binding; pre-validation evidence only')
    return {'session_id': session_id, 'records': len(rows), 'last_phase': rows[-1]['phase'],
            'last_edge': rows[-1]['edge'], 'open_phases': opened, 'performance_evidence': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--session', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(validate_progress(args.journal.read_text(encoding='utf-8'), args.session, args.manifest_sha256), indent=2))


if __name__ == '__main__':
    main()
