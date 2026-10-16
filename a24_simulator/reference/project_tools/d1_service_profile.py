"""Build diagnostic service observations from validated real-task artifacts only."""
import argparse
import json
import math
from pathlib import Path
from tools.d1_task_profile import validate, digest, read


def describe(values):
    values = sorted(values)
    return dict(n=len(values), mean_ns=sum(values)/len(values) if values else None,
                p95_ns=values[math.ceil(.95*len(values))-1] if values else None,
                min_ns=values[0] if values else None, max_ns=values[-1] if values else None)


def build(session_roots):
    sessions, ids = [], set()
    for folder in map(Path, session_roots):
        log = folder/'delegate_log.txt'
        receipt = validate(folder/'artifacts', log.read_text() if log.exists() else None)
        if receipt['session_id'] in ids:
            raise ValueError('duplicate profile session')
        ids.add(receipt['session_id'])
        if receipt['gpu']['status'] == 'unverified':
            raise ValueError('GPU observations lack actual backend evidence')
        manifest = read(folder/'artifacts/manifest.json')
        groups = {}
        for event in receipt['events']:
            key = '/'.join([event['task_id'], event['requested_backend'], event['priority'],
                            event['role'], 'cold' if event.get('cold') else 'warm'])
            group = groups.setdefault(key, dict(arrivals=0, succeeded=0, failed=0, service=[], response=[], prepare=[]))
            group['arrivals'] += 1
            if event['terminal_status'] == 'succeeded':
                group['succeeded'] += 1
                group['service'].append(event['service_ns'])
                group['response'].append(event['completion_ns']-event['scheduled_arrival_ns'])
                group['prepare'].append(event['prepare_ns'])
            else:
                group['failed'] += 1
        for group in groups.values():
            for key in ('service', 'response', 'prepare'):
                group[key] = describe(group[key])
            group['service_success_rate'] = group['succeeded']/group['arrivals']
        sessions.append(dict(session_id=receipt['session_id'], purpose=manifest['purpose'],
                             manifest_sha256=receipt['source_manifest_sha256'],
                             provenance_sha256=digest(folder/'artifacts/provenance.json'),
                             apk_sha256=manifest['apk_sha256'], device_fingerprint=manifest['device_fingerprint'],
                             groups=groups, actual_gpu_evidence=receipt['gpu'],
                             sampled_peak_pss_kb=receipt['sampled_peak_pss_kb'], max_thermal_status=receipt['max_thermal_status']))
    if not sessions:
        raise ValueError('no actual service observations')
    return dict(protocol='service-observations-v1', status='diagnostic_not_frozen', unit='ns', sessions=sessions,
                deadline='calibration_pending', independent_prediction_validation='pending',
                scope='real task service; setup model verification excluded; cold preparation included; never add preparation twice',
                limitation='small bounded pilot; conditional P95 and all-arrival success rate; no policy comparison or simulated completions')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sessions', nargs='+', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.sessions), indent=2))
