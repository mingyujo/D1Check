"""Fail-closed comparison of finalized raw probes and separately bound f32 captures."""
import array
import hashlib
import math
import re
import sys
from pathlib import Path
from tools import d1_model_probe as probe


def compare_decoded(reference, candidate):
    for rows in (reference, candidate):
        for row in rows:
            if set(row) != {'label', 'score', 'box'} or not isinstance(row['label'], str) or not row['label'] or len(row['box']) != 4:
                raise ValueError('invalid decoded result')
            if not all(type(v) in (float, int) and math.isfinite(v) for v in [row['score'], *row['box']]):
                raise ValueError('non-finite decoded result')
        if rows != sorted(rows, key=lambda row: (-row['score'], row['label'], row['box'])):
            raise ValueError('decoded order mismatch')
    pairs = [{'label_matches': a['label'] == b['label'], 'score_delta': abs(a['score'] - b['score']),
              'max_box_delta_px': max(abs(x-y) for x, y in zip(a['box'], b['box']))}
             for a, b in zip(reference, candidate)]
    passed = len(reference) == len(candidate) and all(
        p['label_matches'] and p['score_delta'] <= 1e-3 and p['max_box_delta_px'] <= 2 for p in pairs)
    return {'passed': passed, 'reference_count': len(reference), 'candidate_count': len(candidate),
            'pairs': pairs, 'quality_evaluated': False}


def finite_comparison(reference, candidate):
    if not reference or len(reference) != len(candidate):
        raise ValueError('output size mismatch')
    count, maximum, relative = 0, 0.0, 0.0
    for a, b in zip(reference, candidate):
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError('non-finite output')
        delta = abs(a - b)
        maximum = max(maximum, delta)
        relative = max(relative, delta / max(abs(a), 1e-6))
        count += delta > 1e-4 + 1e-3 * abs(a)
    return {'elements': len(reference), 'violations': count, 'max_abs_error': maximum,
            'max_relative_error': relative, 'passed': count == 0}


def load_capture(root, manifest_path, artifacts):
    manifest = probe.validate_manifest_data(probe.read_json(manifest_path))
    session = manifest['identity']['session_id']
    probe.validate_artifacts(artifacts, session, manifest['target']['device_id'])
    raw = probe.read_json(artifacts / 'raw_equivalence.json')
    digest = probe.sha256_file(manifest_path)
    if raw['manifest_sha256'] != digest:
        raise ValueError('artifact manifest mismatch')
    capture = probe.read_json(root / 'capture.json')
    if set(capture) != {'protocol', 'session_id', 'manifest_sha256', 'seed', 'backend', 'input_sha256', 'outputs'}:
        raise ValueError('capture fields mismatch')
    if (capture['protocol'], capture['session_id'], capture['manifest_sha256'], capture['seed'], capture['backend']) != (
            'model-probe-raw-v1', session, digest, manifest['input']['seed'], manifest['execution']['backend']):
        raise ValueError('capture identity mismatch')
    if raw['input_sha256'] != [capture['input_sha256']]:
        raise ValueError('input identity mismatch')
    if len(capture['outputs']) != len(manifest['tensor']['outputs']):
        raise ValueError('output tensor count mismatch')
    expected = {'capture.json'}
    values = []
    for index, (item, tensor) in enumerate(zip(capture['outputs'], manifest['tensor']['outputs'])):
        name = f'output_{index}.f32le'
        expected.add(name)
        if set(item) != {'filename', 'bytes', 'sha256'} or item['filename'] != name:
            raise ValueError('invalid capture path')
        count = math.prod(tensor['shape'])
        path = root / name
        if path.is_symlink() or not path.is_file() or path.resolve().parent != root.resolve():
            raise ValueError('capture must be a regular contained file')
        data = path.read_bytes()
        if item['bytes'] != count * 4 or len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('capture size/hash mismatch')
        if item['sha256'] not in raw['output_sha256']:
            raise ValueError('capture not bound to finalized outputs')
        floats = array.array('f')
        floats.frombytes(data)
        if sys.byteorder != 'little':
            floats.byteswap()
        values.append(floats)
    if root.is_symlink() or {p.name for p in root.iterdir()} != expected or (root / 'capture.json').is_symlink():
        raise ValueError('capture artifact set mismatch')
    return manifest, capture, values


def gpu_evidence(log, session):
    lines = log.splitlines()
    starts = [i for i, line in enumerate(lines) if f'session_start={session} ' in line]
    ends = [i for i, line in enumerate(lines) if f'session_finalized={session} ' in line]
    if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
        raise ValueError('missing/ambiguous completed session log')
    # Android threadtime: date time PID TID level tag message.
    pid = lines[starts[0]].split()[2]
    scoped = '\n'.join(line for line in lines[starts[0]:ends[0]+1] if len(line.split()) > 2 and line.split()[2] == pid)
    replacements = re.findall(r'Replacing (\d+) out of (\d+) node\(s\) with delegate \(TfLiteGpuDelegateV2\)', scoped)
    kernels = re.findall(r'Created (\d+) GPU delegate kernels', scoped)
    if len(replacements) != 4 or len(kernels) != 4 or any(int(a) != int(b) or int(a) <= 0 for a, b in replacements) or any(int(k) <= 0 for k in kernels):
        raise ValueError('full delegation evidence incomplete')
    if re.search(r'fallback|failed|restor\w*.*plan|unsupported op|TfLiteXNNPackDelegate', scoped, re.I):
        raise ValueError('GPU fallback/failure evidence')
    return {'status': 'verified_full', 'pid': int(pid), 'instances': 4, 'replacements': replacements,
            'scoped_log_sha256': hashlib.sha256(scoped.encode()).hexdigest()}


def compare_pair(cpu, gpu, gpu_log):
    cm, cc, cv = load_capture(*cpu)
    gm, gc, gv = load_capture(*gpu)
    if cm['execution']['backend'] != 'CPU' or gm['execution']['backend'] != 'GPU':
        raise ValueError('expected ordered CPU/GPU pair')
    for key in ('target', 'model', 'tensor', 'runtime', 'input', 'comparator'):
        if cm[key] != gm[key]:
            raise ValueError(f'pair provenance mismatch: {key}')
    if cc['input_sha256'] != gc['input_sha256'] or cc['session_id'] == gc['session_id']:
        raise ValueError('pair input/session mismatch')
    evidence = gpu_evidence(gpu_log, gc['session_id'])
    comparisons = [finite_comparison(a, b) for a, b in zip(cv, gv)]
    result = {'task': cm['model']['task_id'], 'seed': cc['seed'], 'cpu_session': cc['session_id'],
              'gpu_session': gc['session_id'], 'gpu_evidence': evidence, 'outputs': comparisons,
              'passed': all(c['passed'] for c in comparisons), 'quality_evaluated': False}
    if result['task'] == 'classification':
        result['cpu_top5'] = sorted(range(len(cv[0])), key=lambda i: (-cv[0][i], i))[:5]
        result['gpu_top5'] = sorted(range(len(gv[0])), key=lambda i: (-gv[0][i], i))[:5]
    return result
