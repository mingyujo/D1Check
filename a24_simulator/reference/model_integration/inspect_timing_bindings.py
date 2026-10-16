"""Registered metadata-only timing binding inspection. Import is inert.

No raw per-request result body is read. Only thirteen exact public manifests
may be decompressed, under the frozen runtime guard and a predeclared allowlist.
The compact normalized dataset and saved DEV profile are already derived inputs.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile
from runtime_guard import canonical, operation, pin, read, require, sha, write_new

SCHEMA = 'A24-timing-binding-inspection-v1'
WORKER_LOCK = Path('C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/A24-INTEGRATED-SIM-20261016-G002/worker.lock')
DEV_PROFILE_SHA256 = '26b24df6f5e2f679496e850031eaa0f80952085d65abccdc146144c750fa85f0'
PUBLIC_KEYS = ('session_id', 'recipe', 'bank', 'bank_id', 'bank_sha256', 'apk_sha256',
               'source_commit', 'source_manifest_sha256', 'arm', 'route', 'order',
               'concurrency', 'service_cutoff_ns', 'sensor_end_ns')
BINDING_KEYS = ('request_id', 'ordinal', 'task', 'route', 'backend', 'requested_backend',
                'actual_backend_claim', 'input_sha256', 'tensor_sha256', 'model_sha256',
                'model_sha256_declared', 'route_selected_model_identity_verified',
                'issues', 'result_binding_issues')
REQUEST_PUBLIC_KEYS = ('id', 'request_id', 'ordinal', 'task', 'group', 'priority',
                       'arrival_ns', 'scheduled_arrival_ns', 'deadline_ns',
                       'input_sha256', 'tensor_sha256', 'model_sha256')
def digest(obj):
    return hashlib.sha256(canonical(obj).encode('utf-8')).hexdigest()
def path_key(value):
    return os.path.normcase(os.path.abspath(value))
def registered(spec, registry):
    require((path_key(spec['path']), spec['sha256']) in registry,
            'Logical input is not in registered input pins')
    return pin(spec)
def jp(value):
    return str(value).replace('~', '~0').replace('/', '~1')
def scalar_leaves(value, pointer=''):
    rows = []
    if isinstance(value, dict):
        for key, child in value.items():
            rows.extend(scalar_leaves(child, pointer + '/' + jp(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(scalar_leaves(child, pointer + '/' + str(index)))
    else:
        rows.append({'pointer': pointer, 'type': type(value).__name__, 'value': value})
    return rows
def public_member_ref(spec):
    refs = [r for r in spec.get('members', []) if r.get('role') == 'PUBLIC_MANIFEST']
    require(refs and len({r['sha256'] for r in refs}) == 1,
            'Unambiguous exact public member SHA required')
    for ref in refs:
        require(ref['member'] == 'public_manifests/' + spec['session_id'] + '.json',
                'Public member path/session binding differs')
    return sorted(refs, key=lambda r: (path_key(r['archive_path']), r['member']))[0], refs
def normalized_group_rows(session, dataset_index):
    grouped = {}
    for index, request in enumerate(session.get('requests', [])):
        key = (request.get('task'), request.get('route', request.get('backend')))
        group = grouped.setdefault(key, {'task': key[0], 'route': key[1], 'count': 0,
            'missing_model_sha256': 0, 'declared_model_values': set(),
            'result_model_values': set(), 'request_issue_patterns': Counter(),
            'result_issue_patterns': Counter(), 'first': None})
        group['count'] += 1
        group['missing_model_sha256'] += request.get('model_sha256') is None
        group['declared_model_values'].add(request.get('model_sha256_declared'))
        content = request.get('content_provenance') or {}
        result = content.get('result_declared') or {}
        group['result_model_values'].add(result.get('model_sha256'))
        group['request_issue_patterns'][canonical(request.get('issues', []))] += 1
        group['result_issue_patterns'][canonical(request.get('result_binding_issues', []))] += 1
        if group['first'] is None:
            pointer = '/sessions/' + str(dataset_index) + '/requests/' + str(index)
            group['first'] = {'dataset_json_pointer': pointer,
                'keys': sorted(request), 'binding_values': {k: request.get(k) for k in BINDING_KEYS},
                'content_provenance': content,
                'content_provenance_pointer': pointer + '/content_provenance'}
    output = []
    for group in grouped.values():
        for key in ('declared_model_values', 'result_model_values'):
            group[key] = sorted(group[key], key=lambda v: canonical(v))
        for key in ('request_issue_patterns', 'result_issue_patterns'):
            group[key] = [{'issues': json.loads(k), 'count': v} for k, v in group[key].items()]
        output.append(group)
    return sorted(output, key=lambda q: (str(q['task']), str(q['route'])))
def dev_evidence(profile, sid):
    pins = [(i, r) for i, r in enumerate(profile['provenance']['manifest_pins'])
            if r['session_id'] == sid]
    samples = [(i, q) for i, q in enumerate(profile.get('samples', []))
               if q.get('session_id') == sid]
    counts = Counter(q.get('bank') for _, q in samples)
    return {'manifest_pins': [{'pointer': '/provenance/manifest_pins/' + str(i), 'value': r}
                             for i, r in pins],
            'sample_count': len(samples),
            'banks': [{'value': bank, 'count': count} for bank, count in sorted(counts.items(), key=lambda x: str(x[0]))],
            'sample_bank_first_pointer': '/samples/' + str(samples[0][0]) + '/bank' if samples else None,
            'sample_metadata_only': True, 'durations_or_outcomes_emitted': False}
def inspect(op, out):
    require(op['mode'] == 'BINDING_INSPECTION', 'Exact inspection mode required')
    require(path_key(op['worker_lock_path']) == path_key(WORKER_LOCK), 'Original G002 worker lock required')
    require(len(op['protected_pins']) >= 351, 'Protected351 union required')
    require(op.get('fit', 0) == 0 and op.get('NN', 0) == 0, 'No fit or NN allowed')
    registry = {(path_key(s['path']), s['sha256']) for s in op['input_pins']}
    dataset = read(registered(op['dataset_pin'], registry))
    specs_body = read(registered(op['session_specs_pin'], registry))
    require(op['dev_profile_pin']['sha256'] == DEV_PROFILE_SHA256, 'Canonical DEV profile SHA differs')
    profile = read(registered(op['dev_profile_pin'], registry))
    targets = op['target_session_ids']
    require(isinstance(targets, list) and len(targets) == 13 and len(set(targets)) == 13
            and all(isinstance(sid, str) and re.fullmatch('[0-9a-f-]{36}', sid) for sid in targets),
            'Exact thirteen target session IDs required')
    sessions = dataset['sessions']
    dataset_by = {s['session_id']: (i, s) for i, s in enumerate(sessions)}
    specs = specs_body['sessions']
    spec_by = {s['session_id']: s for s in specs}
    require(len(dataset_by) == len(sessions) and len(spec_by) == len(specs), 'Duplicate session identity')
    require(set(targets) <= set(dataset_by) and set(targets) <= set(spec_by), 'Target absent from input')
    families = Counter(spec_by[sid]['family'] for sid in targets)
    require(families == {'INITIAL_DEV8': 8, 'RESUMED_NEW5': 5}, 'Registered initial8/new5 families differ')
    allowlist = op['public_member_allowlist']
    require(isinstance(allowlist, list) and len(allowlist) == 13, 'Exact public-only allowlist required')
    allow_keys = {(r['session_id'], path_key(r['archive_path']), r['archive_sha256'], r['member'], r['sha256'])
                  for r in allowlist}
    require(len(allow_keys) == 13, 'Duplicate public member allowlist identity')
    selected, archives, output = {}, {}, []
    cap = op.get('max_public_manifest_bytes', 16 * 1024 ** 2)
    require(type(cap) is int and 0 < cap <= 16 * 1024 ** 2, 'Public manifest byte cap')
    for sid in targets:
        spec = spec_by[sid]
        ref, aliases = public_member_ref(spec)
        key = (sid, path_key(ref['archive_path']), ref['archive_sha256'], ref['member'], ref['sha256'])
        require(key in allow_keys, 'Selected public member not predeclared in allowlist')
        archive_spec = {'path': ref['archive_path'], 'sha256': ref['archive_sha256'], 'bytes': ref['archive_bytes']}
        if path_key(ref['archive_path']) not in archives:
            archives[path_key(ref['archive_path'])] = registered(archive_spec, registry)
        with zipfile.ZipFile(archives[path_key(ref['archive_path'])]) as z:
            infos = [info for info in z.infolist() if info.filename == ref['member']]
            require(len(infos) == 1 and not infos[0].is_dir(), 'Selected ZIP member absent/nonunique')
            info = infos[0]
            require(info.file_size <= cap and not (info.flag_bits & 1), 'Public manifest oversized/encrypted')
            raw = z.read(info)
            require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'Public member SHA differs')
            require(ref.get('bytes') is None or len(raw) == ref['bytes'], 'Public member byte count differs')
        public = json.loads(raw.decode('utf-8-sig'))
        require(isinstance(public, dict) and public.get('session_id') == sid, 'Public payload session identity differs')
        index, session = dataset_by[sid]
        first = public.get('requests', [None])[0] if public.get('requests') else None
        public_facts = {k: {'pointer': '/' + jp(k), 'present': k in public, 'value': public.get(k)}
                        for k in PUBLIC_KEYS}
        result_names = [{k: r.get(k) for k in ('member', 'sha256', 'archive_path', 'archive_sha256')}
                        for r in spec['members'] if r.get('role') == 'REQUEST_RESULT']
        output.append({'session_id': sid, 'family': spec['family'], 'cohort_id': session.get('cohort_id'),
            'dataset_pointer': '/sessions/' + str(index),
            'normalized_bank': session.get('bank'), 'spec_bank': spec.get('bank'),
            'normalized_compatibility': session.get('compatibility'),
            'normalized_request_groups': normalized_group_rows(session, index),
            'public_receipt': {**ref, 'actual_bytes': len(raw), 'CRC32': info.CRC,
                'selected_member_CRC_checked_by_zip_read': True, 'member_sha256_verified': True,
                'unselected_members_decompressed': False, 'same_SHA_aliases': aliases},
            'public_top_level_keys': sorted(public), 'public_declared_fields': public_facts,
            'public_models': {'pointer': '/models', 'type': type(public.get('models')).__name__,
                              'value': public.get('models'), 'scalar_leaves': scalar_leaves(public.get('models'), '/models')},
            'public_first_request': {'pointer': '/requests/0', 'type': type(first).__name__,
                'keys': sorted(first) if isinstance(first, dict) else None,
                'public_values': {k: first.get(k) for k in REQUEST_PUBLIC_KEYS} if isinstance(first, dict) else None},
            'public_request_count': len(public.get('requests', [])),
            'DEV_profile_evidence': dev_evidence(profile, sid),
            'result_member_metadata_only': result_names, 'raw_result_bodies_read': 0})
        selected[key] = True
    require(set(selected) == allow_keys, 'Public allowlist not consumed exactly once')
    body = {'schema': SCHEMA, 'status': 'METADATA_INSPECTION_ONLY_NOT_MODEL_PASS',
        'dataset_pin': op['dataset_pin'], 'session_specs_pin': op['session_specs_pin'],
        'dev_profile_pin': op['dev_profile_pin'], 'target_session_ids': targets,
        'families': dict(families), 'sessions': output, 'public_manifests_read': len(output),
        'raw_result_bodies_read': 0, 'unselected_members_decompressed': 0,
        'HTTP': 0, 'device_commands': 0, 'fit': 0, 'NN': 0, 'new_environment': 0,
        'fresh_confirmation': False, 'measured_J': None,
        'semantic_changes_to_dataset': 0, 'original_files_modified': 0}
    write_new(out / 'TIMING_BINDING_INSPECTION.json', body)
    write_new(out / 'INSPECTION_RESULT.json', {'schema': SCHEMA, 'status': body['status'],
        'sessions': len(output), 'public_manifests_read': len(output), 'raw_result_bodies_read': 0,
        'inspection_sha256': sha(out / 'TIMING_BINDING_INSPECTION.json'),
        'HTTP': 0, 'fit': 0, 'NN': 0, 'new_environment': 0})
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation', required=True)
    args = parser.parse_args()
    with operation(args.operation, __file__) as (op, out):
        inspect(op, out)
if __name__ == '__main__':
    main()

