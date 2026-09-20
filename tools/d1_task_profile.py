"""Validate bounded task-profile-v1 evidence; no scheduler or simulation execution."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import uuid
from tools import d1_model_probe


def read(path):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError('duplicate JSON key')
            result[k] = v
        return result
    return json.loads(path.read_text(encoding='utf8'), object_pairs_hook=unique,
                      parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file(root, name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,126}', name):
        raise ValueError('invalid artifact name')
    path = root / name
    if path.is_symlink() or not path.is_file() or path.resolve().parent != root.resolve():
        raise ValueError('artifact escapes root or is not regular')
    return path


def _number(v, name, positive=False):
    if type(v) is not int or v < (1 if positive else 0):
        raise ValueError('invalid integer: ' + name)
    return v


def validate(root, delegate_log=None):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('invalid profile root')
    provenance = read(_file(root, 'provenance.json'))
    manifest = read(_file(root, 'manifest.json'))
    summary = read(_file(root, 'summary.json'))
    session = manifest['session_id']
    if str(uuid.UUID(session)) != session or manifest['protocol'] not in ('task-profile-v1', 'task-profile-v2', 'task-profile-v3'):
        raise ValueError('invalid profile identity')
    if manifest['maximum_duration_ms'] != 120000 or manifest['purpose'] not in ('correctness', 'solo', 'transition', 'corun', 'holdout'):
        raise ValueError('not an authorized bounded calibration recipe')
    if type(manifest['allowed_concurrency']) is not int or manifest['allowed_concurrency'] not in (1, 2):
        raise ValueError('invalid concurrency')
    for spec in manifest['models'].values():
        d1_model_probe.validate_manifest_data(spec)
        if spec['runtime']['cpu_threads'] != 1 or spec['runtime']['litert_version'] != '1.4.2' or spec['runtime']['xnnpack'] is not True:
            raise ValueError('profile runtime contract mismatch')
        if spec['identity']['session_id'] != session or spec['target']['apk_sha256'] != manifest['apk_sha256'] or spec['target']['build_fingerprint'] != manifest['device_fingerprint']:
            raise ValueError('model manifest identity mismatch')
    for obj in (provenance, summary):
        if obj['session_id'] != session or obj['protocol'] != manifest['protocol']:
            raise ValueError('profile identity mismatch')
    if provenance['manifest_sha256'] != digest(root / 'manifest.json') or provenance['apk_sha256'] != manifest['apk_sha256']:
        raise ValueError('manifest/APK binding mismatch')
    seen = set()
    for entry in provenance['files']:
        if set(entry) != {'name', 'bytes', 'sha256'} or entry['name'] in seen or entry['name'] == 'provenance.json':
            raise ValueError('duplicate or invalid provenance entry')
        seen.add(entry['name'])
        file = _file(root, entry['name'])
        if file.stat().st_size != entry['bytes'] or digest(file) != entry['sha256']:
            raise ValueError('artifact hash/size mismatch')
    if {p.name for p in root.iterdir()} != seen | {'provenance.json'}:
        raise ValueError('artifact set mismatch')
    events = [json.loads(line) for line in (root / 'events.jsonl').read_text().splitlines()]
    requests = {r['request_id']: r for r in manifest['requests']}
    if not 1 <= len(requests) <= 48 or any(r['worker'] not in range(manifest['allowed_concurrency']) for r in requests.values()):
        raise ValueError('request bounds')
    if len(requests) != len(manifest['requests']) or len(events) != len(requests) or len({r['request_id'] for r in events}) != len(events):
        raise ValueError('missing/duplicate arrival terminal')
    expected = {'manifest.json', 'events.jsonl', 'environment.json', 'summary.json'}
    success = 0
    for event in events:
        if manifest['protocol'] in ('task-profile-v2', 'task-profile-v3'):
            journal_name = event['request_id'] + '.event.json'
            if read(_file(root, journal_name)) != event:
                raise ValueError('durable request journal mismatch')
            expected.add(journal_name)
        req = requests[event['request_id']]
        spec = manifest['models'][req['model_key']]
        if event['session_id'] != session or any(event[k] != req[k] for k in ('sample_id', 'priority', 'role', 'worker')):
            raise ValueError('request binding mismatch')
        if (event['requested_backend'], event['task_id'], event['model_id']) != (spec['execution']['backend'], spec['model']['task_id'], spec['model']['model_id']):
            raise ValueError('task/backend binding mismatch')
        actual = 'CPU' if event['requested_backend'] == 'CPU' else 'unverified_requires_host_delegate_log'
        if event['actual_backend'] != actual:
            raise ValueError('silent fallback or unproved actual backend')
        times = [_number(event[k], k) for k in ('scheduled_arrival_ns', 'enqueue_ns', 'execution_start_ns')]
        if event['deadline_ns'] is not None or event['deadline_outcome'] != 'not_set':
            raise ValueError('uncalibrated deadline')
        if event['terminal_status'] == 'succeeded':
            success += 1
            ready = _number(event['output_ready_ns'], 'output_ready_ns')
            complete = event.get('persist_complete_ns') if event['priority'] == 'normal' else ready
            times += [ready, _number(complete, 'completion'), _number(event['terminal_ns'], 'terminal')]
            if event['completion_ns'] != complete or event['service_ns'] != complete - event['execution_start_ns']:
                raise ValueError('completion boundary mismatch')
            if not 0 <= _number(event['inference_ns'], 'inference') <= event['service_ns'] or not 0 <= event['prepare_ns'] <= event['service_ns']:
                raise ValueError('invalid service decomposition')
            name = event['request_id'] + '.result.json'
            if event['result_file'] != name or event['result_sha256'] != digest(_file(root, name)):
                raise ValueError('result binding mismatch')
            expected.add(name)
            result = read(root / name)
            if manifest['protocol'] == 'task-profile-v3' and (result.get('adapter_contract'), result.get('canonical_input_contract')) != ('explicit-image-task-v2', 'canonical-srgb-png-v2'):
                raise ValueError('v3 canonical color contract missing')
            image = next(i for i in manifest['images'] if i['sample_id'] == event['sample_id'])
            if result['image_sha256'] != image['sha256'] or result['model_sha256'] != spec['model']['sha256'] or result['input_tensor_sha256'] != event['input_tensor_sha256']:
                raise ValueError('result input/model binding mismatch')
            if result['requested_backend'] != event['requested_backend'] or result['actual_backend'] != actual:
                raise ValueError('result backend mismatch')
            for prediction in result['results']:
                values = [prediction['score'], *prediction.get('box', [])]
                if not prediction['label'] or not all(type(v) in (float, int) and math.isfinite(v) for v in values):
                    raise ValueError('invalid decoded values')
        elif event['terminal_status'] == 'failed':
            if 'result_file' in event or 'result_sha256' in event or not event.get('error'):
                raise ValueError('failed request misrepresented as completed')
            times.append(_number(event['terminal_ns'], 'terminal'))
        else:
            raise ValueError('unsupported calibration terminal')
        if times != sorted(times):
            raise ValueError('request clock regressed')
    if expected != seen or summary['request_count'] != len(events) or summary['succeeded'] != success or summary['failed'] != len(events) - success:
        raise ValueError('summary/arrival/artifact mismatch')
    environment = read(root / 'environment.json')
    if not environment or [r['mono_ns'] for r in environment] != sorted(r['mono_ns'] for r in environment):
        raise ValueError('invalid environment timeline')
    for row in environment:
        _number(row['total_pss_kb'], 'PSS', positive=True)
        _number(row['thermal_status'], 'thermal status')
    if success == len(events) and any(row['thermal_status'] > 1 for row in environment):
        raise ValueError('baseline thermal violation')
    gpu_count = sum(r.get('cold', False) and r['requested_backend'] == 'GPU' for r in events)
    gpu = {'status': 'not_requested'}
    if gpu_count:
        gpu = {'status': 'unverified'}
        if delegate_log is not None:
            lines = delegate_log.splitlines()
            starts = [i for i, line in enumerate(lines) if f'session_start={session}' in line]
            ends = [i for i, line in enumerate(lines) if f'session_finalized={session}' in line]
            if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
                raise ValueError('missing GPU session log boundaries')
            pid = lines[starts[0]].split()[2]
            scoped = '\n'.join(line for line in lines[starts[0]:ends[0]+1] if len(line.split()) > 2 and line.split()[2] == pid)
            replacements = re.findall(r'Replacing (\d+) out of (\d+) node\(s\) with delegate \(TfLiteGpuDelegateV2\)', scoped)
            kernels = re.findall(r'Created (\d+) GPU delegate kernels', scoped)
            if len(replacements) != gpu_count or len(kernels) != gpu_count or any(int(a) <= 0 or a != b for a, b in replacements) or any(int(k) <= 0 for k in kernels):
                raise ValueError('incomplete full GPU delegation evidence')
            if re.search(r'fallback|failed|unsupported op|restor\w*.*plan', scoped, re.I):
                raise ValueError('GPU fallback/failure')
            gpu = {'status': 'verified_full', 'actual_backend': 'GPU', 'instances': gpu_count, 'scoped_log_sha256': hashlib.sha256(scoped.encode()).hexdigest()}
    return {'protocol': 'task-profile-validation-v1', 'session_id': session, 'artifact_integrity': 'passed',
            'gpu': gpu, 'arrivals': len(events), 'succeeded': success, 'failed': len(events)-success,
            'service_success_rate': success / len(events), 'deadline_status': 'calibration_pending',
            'sampled_peak_pss_kb': max(r['total_pss_kb'] for r in environment),
            'max_thermal_status': max(r['thermal_status'] for r in environment),
            'events': events, 'source_manifest_sha256': digest(root / 'manifest.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--delegate-log', type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.root, args.delegate_log.read_text() if args.delegate_log else None), indent=2))


if __name__ == '__main__':
    main()
