"""Saved-only A24 M8 extraction. No work, file access, or fit runs on import.

Parent must register this source/test, audit pins, exact member/session roster,
clock declaration evidence and all uses/exclusions BEFORE calling extract().
This module has no networking, process launch, model fit or simulator APIs.
No source-commit/APK/delegate claim becomes an installed-binary verification.

API: inventory_from_audits([{'pin': filepin, 'generation': str}]) is metadata
only. extract(operation) is the explicitly gated raw entry. It returns JSON
data and never writes files. See M8_SOURCE_PREPARATION.json for the contract.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import zipfile

NS = 1_000_000_000
SCHEMA = 'A24-M8-normalized-sessions-v1'
OP_SCHEMA = 'A24-M8-extraction-operation-v1'
HEX = re.compile(r'^[0-9a-f]{64}$')
SID_PATH = re.compile(r'^(?:raw|public_manifests|host_receipts|host_outcomes|host_preAPP)/([0-9a-f-]{36})(?:/|\.json$)', re.I)
PHASES = ('actual_arrival_ns', 'queue_entry_ns', 'dispatch_ns',
          'execution_start_ns', 'output_ready_ns', 'persist_complete_ns',
          'worker_release_ns', 'lane_available_ns')
FIVE = ('dispatch_to_execution', 'execution_to_output', 'output_to_persist',
        'persist_to_worker_release', 'worker_release_to_available')
ZERO_EXECUTION = ('new_environment', 'NN', 'fit', 'optimizer', 'CostState',
                  'model_change', 'selection', 'HTTP', 'device_commands')
PUBLIC_FIELDS = ('id', 'ordinal', 'task', 'group', 'priority', 'arrival_ns', 'deadline_ns')
NATIVE_PUBLIC_POINTERS = {'id': 'request_id', 'ordinal': 'ordinal', 'task': 'task',
                          'group': 'group', 'priority': 'priority',
                          'arrival_ns': 'scheduled_arrival_ns', 'deadline_ns': 'deadline_ns'}
PROJECTED_PUBLIC_POINTERS = {key: key for key in PUBLIC_FIELDS}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def checked_file(spec):
    require(isinstance(spec, dict) and {'path', 'sha256', 'bytes'} <= spec.keys(), 'Complete file pin required')
    require(type(spec['bytes']) is int and spec['bytes'] >= 0 and HEX.fullmatch(str(spec['sha256'])), 'Invalid pin types')
    path = Path(spec['path'])
    require(path.is_file() and path.stat().st_size == spec['bytes'] and file_sha(path) == spec['sha256'], 'File pin differs: ' + str(path))
    return path


def read_json(spec):
    return json.loads(checked_file(spec).read_text(encoding='utf-8-sig'))


def safe_member(name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name,
            'Canonical POSIX member name required')
    p = PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts and str(p) == name, 'Unsafe/noncanonical member path')
    return name


def member_key(ref):
    return (str(Path(ref['archive_path']).resolve()).casefold(), ref['archive_sha256'], ref['member'], ref['sha256'])


def inventory_from_audits(audit_sources):
    """Interpret saved hash metadata only; never open an archive or its payload.

    V2 has {'archives': [...]}; resumed V5 is a bare list. Member names establish
    only path attribution. They never verify opaque JSONL record membership.
    """
    members, archives, duplicate_refs = [], [], []
    seen = set()
    for source in audit_sources:
        body = read_json(source['pin'])
        rows = (body.get('archives', body.get('files')) if isinstance(body, dict) else body)
        require(isinstance(rows, list), 'Unknown saved archive-audit schema')
        for a in rows:
            archive_only = 'member_hashes' not in a
            require((a.get('CRC') == 'PASS' and a.get('safe_paths') == 'PASS')
                    or (archive_only and a.get('CRC_PASS') is True), 'Prior archive audit did not pass')
            archive = {'path': a['path'], 'sha256': a['sha256'], 'bytes': a['bytes'],
                       'generation': source['generation'], 'audit_pin': source['pin'],
                       'prior_CRC': a.get('CRC', 'PASS' if a.get('CRC_PASS') else None),
                       'prior_safe_paths': a.get('safe_paths'),
                       'member_binding_available': not archive_only,
                       'exclusion': 'ARCHIVE_LEVEL_RECEIPT_ONLY_NO_SAVED_MEMBER_SHA; use audited repack if identical' if archive_only else None}
            archives.append(archive)
            if archive_only:
                continue
            require(isinstance(a.get('member_hashes'), dict), 'Explicit audited member hashes required')
            for name, sha in a['member_hashes'].items():
                safe_member(name)
                require(HEX.fullmatch(str(sha)), 'Invalid audited member SHA')
                match = SID_PATH.match(name)
                ref = {'archive_path': a['path'], 'archive_sha256': a['sha256'],
                       'archive_bytes': a['bytes'], 'member': name, 'sha256': sha,
                       'bytes': None, 'source_generation': source['generation'],
                       'path_session_id': match.group(1).lower() if match else None,
                       'audit_pin_sha256': source['pin']['sha256'],
                       'opaque_payload_membership_verified': False}
                key = member_key(ref)
                if key in seen:
                    duplicate_refs.append(ref)
                else:
                    seen.add(key)
                    members.append(ref)
    by_stream = {}
    for ref in members:
        sid = ref['path_session_id']
        if sid:
            # Exact path is part of the key: result files, attempts and partial
            # streams remain distinct even if their basenames happen to match.
            by_stream.setdefault((sid, ref['member']), {}).setdefault(ref['sha256'], []).append(ref)
    conflicts = [{'session_id': sid, 'member': name, 'versions': list(versions.values())}
                 for (sid, name), versions in sorted(by_stream.items()) if len(versions) > 1]
    return {'schema': 'A24-M8-received-member-inventory-v1', 'archives': archives,
            'members': members, 'identical_audit_references': duplicate_refs,
            'member_conflicts': conflicts,
            'session_ids_from_paths_only': sorted({r['path_session_id'] for r in members if r['path_session_id']}),
            'raw_payload_reads': 0, 'opaque_payload_membership_verified': False}


def roster_from_metadata(metadata_sources):
    """Load pinned previously saved metadata schemas, never public/raw members.

    Explicit new-design rows may be supplied by the parent in EXPLICIT_ROWS.
    Families with no independently declared clock evidence remain excluded by
    build_session_specs. A path UUID stays a candidate until payload binding.
    """
    merged = {}
    for source in metadata_sources:
        body = read_json(source['pin'])
        kind = source['kind']
        if kind == 'SOURCE_INVENTORY_ROWS':
            rows = body['session_rows']
        elif kind == 'FINAL_PHASE_B_OCCURRENCES':
            require(isinstance(body, list), 'Phase B occurrences must be list')
            rows = []
            for q in body:
                bindings = q.get('metadata_bindings') or []
                if isinstance(bindings, dict):
                    bindings = [bindings]
                require(isinstance(bindings, list) and all(isinstance(b, dict) for b in bindings), 'Unknown Phase B metadata bindings container')
                for binding in bindings or [{}]:
                    rows.append({'session_id': q['payload_session_id'],
                                 'family': binding.get('literal_family'),
                                 'phase_b_metadata_binding': binding,
                                 'phase_b_public_sha256': q.get('public_sha256'),
                                 'phase_b_clock_status': q.get('clock', {}).get('status'),
                                 'phase_b_occurrence': q.get('occurrence_index')})
        elif kind == 'FOLLOWON_CONTRACT_MAP':
            rows = [q for group in body['groups'] for q in group['items']]
        elif kind == 'DEV_PROFILE_PINS':
            rows = [{'session_id': q['session_id'], 'family': source.get('family', 'INITIAL_DEV8'),
                     'stage': 'DEV', 'block': source.get('block', 'R02DEV01'), 'manifest_pin': q}
                    for q in body['provenance']['manifest_pins']]
        elif kind == 'EXPLICIT_ROWS':
            rows = body if isinstance(body, list) else body['sessions']
        else:
            raise ValueError('Unknown metadata roster adapter: ' + str(kind))
        for row in rows:
            sid = row.get('session_id')
            require(isinstance(sid, str) and re.fullmatch('[0-9a-f-]{36}', sid, re.I), 'Invalid metadata payload/session ID')
            sid = sid.lower()
            target = merged.setdefault(sid, {'session_id': sid, 'metadata_occurrences': [], 'metadata_conflicts': []})
            target['metadata_occurrences'].append({'pin': source['pin'], 'kind': kind, 'row': row})
            # Preserve conflicting labels; do not promote a later status to
            # overwrite an original failed status or original role.
            for key in ('family', 'block', 'stage', 'arm', 'bank', 'recipe'):
                value = row.get(key)
                if value is None:
                    continue
                if key in target and target[key] != value:
                    target['metadata_conflicts'].append({'field': key, 'retained': target[key], 'other': value})
                else:
                    target[key] = value
            statuses = target.setdefault('declared_status_versions', [])
            for value in row.get('published_status_versions', row.get('declared_status_versions', [])):
                if value not in statuses:
                    statuses.append(value)
            aliases = target.setdefault('family_aliases', [])
            if row.get('family') and row['family'] not in aliases:
                aliases.append(row['family'])
    return merged


def build_session_specs(inventory, roster, clock_contracts, generation='ALL_RECEIVED_A24_M8'):
    """Pure metadata builder for the full scope; does not open ZIP payloads.

    clock_contracts is an explicit parent-registered mapping by family or SID.
    No clock contract is inferred from a filename, 35-second arrivals or AP.
    A conflicting logical stream excludes that complete session attempt until
    a separate parent-registered resolution; every version remains inventoried.
    """
    by_sid = {}
    for ref in inventory['members']:
        if ref['path_session_id']:
            by_sid.setdefault(ref['path_session_id'], []).append(ref)
    sessions, excluded_members, chosen_keys = [], [], set()
    candidate_ids = sorted(set(by_sid).union(roster))
    for sid in candidate_ids:
        meta = roster.get(sid, {})
        family = meta.get('family') or 'UNATTRIBUTED_RECEIVED'
        block = meta.get('block') or 'ALL_RECORDED_BLOCKS'
        contract = clock_contracts.get(sid, clock_contracts.get(family))
        refs = []
        for incoming in by_sid.get(sid, []):
            r = dict(incoming); name = r['member']; basename = PurePosixPath(name).name
            if name == 'public_manifests/' + sid + '.json':
                role, logical = 'PUBLIC_MANIFEST', 'public_manifest'
            elif name.startswith('raw/' + sid + '/') and basename in ('requests.json', 'events.jsonl', 'summary.json', 'host_hal_raw.jsonl', 'host_hal_partial.jsonl'):
                role, logical = 'RAW_STREAM', basename
            elif name.startswith('raw/' + sid + '/') and basename.endswith('.result.json'):
                role, logical = 'REQUEST_RESULT', basename
            elif name.startswith('host_preAPP/' + sid + '/') and basename.endswith('.jsonl') and contract and contract.get('preapp_HAL_schema') == 'SAME_CURRENT_HAL_DEVICE_BRACKET':
                role, logical = 'RAW_STREAM', 'preAPP/' + name.split('/', 2)[2]
            else:
                continue
            r.update(role=role, logical_stream=logical); refs.append(r)
        reason = None
        if not meta:
            reason = 'NO_PINNED_SESSION_METADATA_ROSTER; path attribution only'
        elif contract is None:
            reason = 'NO_PARENT_REGISTERED_SOURCE_CLOCK_DECLARATION'
        try:
            groups = deduplicate_refs(refs)
        except ValueError:
            groups = []
            reason = 'CONFLICTING_RECEIVED_LOGICAL_MEMBER_VERSIONS; all versions retained'
        if not any(g['selected']['role'] == 'PUBLIC_MANIFEST' for g in groups):
            reason = reason or 'NO_UNAMBIGUOUS_PUBLIC_MANIFEST_MEMBER'
        if not any(g['logical_stream'] in ('host_hal_raw.jsonl', 'host_hal_partial.jsonl') for g in groups):
            # Timing-only sessions remain usable; absence of AP is not exclusion.
            pass
        spec = {'session_id': sid, 'attempt_id': 'RECEIVED_DISTINCT_SESSION_WITH_ALL_VERSION_PROVENANCE',
                'source_generation': generation, 'received_generations': sorted({r['source_generation'] for r in refs}),
                'family': family, 'block': block, 'cohort_id': family + ':' + block,
                'original_role': str(meta.get('stage') or 'UNKNOWN'),
                'bank': meta.get('bank', meta.get('recipe')),
                'declared_status_versions': meta.get('declared_status_versions', []),
                'metadata_provenance': meta, 'clock_contract': contract,
                'members': refs, 'use': 'INVENTORY_EXCLUDED' if reason else 'DEVELOPMENT', 'exclusion': reason,
                'hal_streams': [g['logical_stream'] for g in groups if g['logical_stream'] in ('host_hal_raw.jsonl', 'host_hal_partial.jsonl') or g['logical_stream'].startswith('preAPP/')]}
        sessions.append(spec)
        chosen_keys.update(member_key(r) for r in refs)
    for ref in inventory['members']:
        if member_key(ref) not in chosen_keys:
            excluded_members.append({**ref, 'reason': 'RECEIVED_METADATA_BINARY_TRACE_OR_UNRECOGNIZED_STREAM; inventoried, no guessed semantic parser'})
    return {'sessions': sessions, 'excluded_members': excluded_members,
            'session_attempt_roster_sha256': digest([[s['session_id'], s['attempt_id']] for s in sessions]),
            'describe': {'candidate_session_ids': len(candidate_ids),
                         'development_sessions': sum(s['use'] == 'DEVELOPMENT' for s in sessions),
                         'excluded_sessions': sum(s['use'] != 'DEVELOPMENT' for s in sessions),
                         'archive_occurrences': len(inventory['archives']), 'audited_member_occurrences': len(inventory['members']),
                         'family_counts': {f: sum(s['family'] == f for s in sessions) for f in sorted({s['family'] for s in sessions})},
                         'raw_payload_reads': 0}}


def deduplicate_refs(refs):
    """Collapse repackaged identical logical bytes, preserve all provenance.

    Different bytes for one logical stream are a blocking conflict. Selecting a
    later attempt is the parent's explicit version/exclusion decision.
    """
    by = {}
    for ref in refs:
        safe_member(ref['member'])
        logical = ref.get('logical_stream', ref['member'])
        by.setdefault(logical, {}).setdefault(ref['sha256'], []).append(ref)
    conflicts = {name: versions for name, versions in by.items() if len(versions) != 1}
    require(not conflicts, 'CONFLICTING_LOGICAL_MEMBER_VERSIONS: ' + ','.join(sorted(conflicts)))
    return [{'logical_stream': name, 'selected': sorted(next(iter(versions.values())), key=lambda r: member_key(r))[0],
             'all_republications': next(iter(versions.values()))}
            for name, versions in sorted(by.items())]


def json_lines(raw):
    rows, invalid = [], []
    for no, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            q = json.loads(line)
            require(isinstance(q, dict), 'JSONL record must be object')
            rows.append((no, q, hashlib.sha256(line).hexdigest()))
        except (ValueError, UnicodeError, TypeError) as exc:
            invalid.append({'line': no, 'reason': str(exc), 'line_sha256': hashlib.sha256(line).hexdigest()})
    return rows, invalid


def project_public(public, sid, contract):
    """Exact public native fields. Integer group stays integer; no raw coercion."""
    require(public.get('session_id') == sid, 'Public manifest session binding differs')
    require(contract.get('planned_clock_basis') == 'COMMON_START_RELATIVE_NANOSECONDS'
            and contract.get('planned_clock_shift_ns') == 0, 'Explicit public planned clock declaration required')
    require(isinstance(public.get('requests'), list), 'Public requests array required')
    fields = contract.get('public_field_pointers')
    require(fields in (NATIVE_PUBLIC_POINTERS, PROJECTED_PUBLIC_POINTERS), 'Exact registered native/projected public field mapping required')
    requests, seen_ids, seen_ord = [], set(), set()
    for source in public['requests']:
        require(isinstance(source, dict) and set(fields.values()) <= source.keys(), 'Missing native public planned fields')
        q = {key: source[field] for key, field in fields.items()}
        require(isinstance(q['id'], str) and q['id'] and q['id'] not in seen_ids, 'Duplicate/invalid public request ID')
        require(type(q['ordinal']) is int and q['ordinal'] not in seen_ord, 'Duplicate/invalid public ordinal')
        require(type(q['group']) in (int, str), 'Public group has unsupported native type')
        require(q['task'] in ('C', 'D') and q['priority'] in ('U', 'N', 'urgent', 'normal'), 'Unsupported public task/priority')
        require(type(q['arrival_ns']) is int and type(q['deadline_ns']) is int
                and 0 <= q['arrival_ns'] <= q['deadline_ns'], 'Invalid public relative clock')
        seen_ids.add(q['id']); seen_ord.add(q['ordinal'])
        q['public_native_group_type'] = type(q['group']).__name__
        q['content_provenance'] = {key: source.get(key) for key in
                                   ('input_sha256', 'tensor_sha256', 'input_file', 'input_slot', 'content_binding', 'model_sha256')}
        requests.append(q)
    for key in ('service_cutoff_ns', 'sensor_end_ns'):
        require(type(public.get(key)) is int and public[key] >= 0, 'Explicit public planned window required')
    return requests


def resolve_origin(event_rows, summary, contract):
    """Use only the clock source declared before raw access. Never infer offset."""
    source = contract.get('origin_source')
    commons = [q.get('origin_ns') for _, q, _ in event_rows if q.get('kind') == 'common_start']
    event_origin = commons[0] if len(commons) == 1 and type(commons[0]) is int else None
    summary_origin = summary.get('common_start_ns') if isinstance(summary, dict) else None
    if type(summary_origin) is not int:
        summary_origin = None
    if source == 'UNIQUE_EVENTS_COMMON_START_ORIGIN_NS':
        origin = event_origin
    elif source == 'SUMMARY_COMMON_START_NS':
        origin = summary_origin
    else:
        raise ValueError('Unsupported declared origin source')
    issues = []
    if origin is None:
        issues.append('MISSING_OR_NONUNIQUE_DECLARED_INTEGER_ORIGIN')
    if event_origin is not None and summary_origin is not None and event_origin != summary_origin:
        issues.append('EVENT_SUMMARY_ORIGIN_CONFLICT')
        origin = None
    return origin, issues


def normalize_requests(raw, planned, origin, public, results=None):
    """Full planned denominator, five paired stages, separate response/AVAILABLE."""
    require(isinstance(raw, list), 'requests.json must remain a native list')
    by = {}
    for q in raw:
        require(isinstance(q, dict) and isinstance(q.get('request_id'), str), 'Invalid observed request identity')
        require(q['request_id'] not in by, 'Duplicate observed request identity')
        by[q['request_id']] = q
    require(not (set(by) - {q['id'] for q in planned}), 'Unplanned observed request identity')
    rows = []
    results = results or {}
    declared_protocol = public.get('concurrency')
    protocol = {'PAIR': 'CG_DC', 'CG_DC': 'CG_DC', 'SERIAL': 'SERIAL'}.get(declared_protocol)
    for p in planned:
        q = by.get(p['id']); issues = []
        times = {k: None for k in PHASES}
        if q is None:
            issues.append('MISSING_OBSERVED_RECORD')
        elif origin is None:
            issues.append('MISSING_DECLARED_CLOCK_ORIGIN')
        else:
            for key in ('ordinal', 'task', 'group'):
                if type(q.get(key)) is not type(p[key]) or q.get(key) != p[key]:
                    issues.append('PLAN_BINDING_MISMATCH_' + key)
            for key, want in [('scheduled_arrival_ns', origin + p['arrival_ns']), ('deadline_ns', origin + p['deadline_ns'])]:
                if type(q.get(key)) is not int or q[key] != want:
                    issues.append('PLAN_BINDING_MISMATCH_' + key)
            for key in PHASES:
                if q.get(key) is not None:
                    if type(q[key]) is not int:
                        issues.append('INVALID_CLOCK_' + key)
                    else:
                        times[key] = q[key] - origin
            known = [p['arrival_ns']] + [times[k] for k in PHASES if times[k] is not None]
            if any(a > b for a, b in zip(known, known[1:])):
                issues.append('REVERSED_RECORDED_PHASE_DAG')
            if times['dispatch_ns'] is not None and times['dispatch_ns'] >= public['service_cutoff_ns']:
                issues.append('DISPATCH_AFTER_SERVICE_STOP')
        rf = 'output_ready_ns' if p['task'] == 'C' else 'persist_complete_ns'
        response = times[rf]
        if response is not None and q.get('response_complete_ns') != origin + response:
            issues.append('TASK_RESPONSE_BOUNDARY_MISMATCH')
        # Actual recorded windows are kept. No forced 120/180/210 truncation.
        successful = q is not None and q.get('terminal_status') == 'COMPLETED'
        valid_response = response if not issues and successful else None
        available = times['lane_available_ns'] if not issues else None
        five_times = [times[k] for k in PHASES[2:]]
        complete = not issues and all(type(t) is int for t in five_times)
        stages = {name: (b - a) / NS for name, a, b in zip(FIVE, five_times, five_times[1:])} if complete else None
        result = results.get(p['id'])
        content = dict(p['content_provenance'])
        result_issues = []
        modelkey = p['task'] + '_' + str(q.get('backend') if q else None)
        route_model = public.get('models', {}).get(modelkey) if isinstance(public.get('models'), dict) else None
        declared_model = route_model.get('model', {}).get('sha256') if isinstance(route_model, dict) and isinstance(route_model.get('model'), dict) else None
        if result is not None:
            require(isinstance(result, dict), 'Per-request result must be object')
            if result.get('request_id') not in (None, p['id']):
                result_issues.append('RESULT_REQUEST_ID_MISMATCH')
            for public_key, result_key in [('input_sha256', 'image_sha256'), ('tensor_sha256', 'input_tensor_sha256')]:
                if content.get(public_key) is not None and result.get(result_key) != content[public_key]:
                    result_issues.append('RESULT_CONTENT_BINDING_MISMATCH_' + public_key)
            content['result_declared'] = {k: result.get(k) for k in
                                          ('image_sha256', 'input_tensor_sha256', 'model_sha256', 'requested_backend', 'actual_backend')}
            content['result_payload_sha256'] = digest(result.get('results'))
            if declared_model is not None and result.get('model_sha256') != declared_model:
                result_issues.append('RESULT_MODEL_BINDING_MISMATCH')
        content['route_selected_declared_model_sha256'] = declared_model
        model_sha = (result or {}).get('model_sha256')
        model_verified = bool(model_sha and declared_model == model_sha and not result_issues)
        row = {'request_id': p['id'], 'id': p['id'], 'ordinal': p['ordinal'], 'task': p['task'],
               'priority': {'urgent': 'U', 'normal': 'N'}.get(p['priority'], p['priority']),
               'group': p['group'], 'public_native_group_type': p['public_native_group_type'],
               'route': q.get('backend') if q else None, 'backend': q.get('backend') if q else None,
               'requested_backend': (result or {}).get('requested_backend', q.get('backend') if q else None),
               'actual_backend_claim': (result or {}).get('actual_backend'),
               'actual_hardware_delegate_verified': False, 'protocol': protocol,
               'public_declared_protocol': declared_protocol,
               'input_sha256': content.get('input_sha256'), 'tensor_sha256': content.get('tensor_sha256'),
               'model_sha256': model_sha if model_verified else None,
               'model_sha256_declared': declared_model,
               'route_selected_model_identity_verified': model_verified,
               'scheduled_arrival_s': p['arrival_ns'] / NS, 'arrival_s': p['arrival_ns'] / NS,
               'deadline_s': p['deadline_ns'] / NS,
               'status': q.get('terminal_status') if q else 'MISSING_OBSERVED_RECORD',
               'declared_terminal_status': q.get('terminal_status') if q else 'MISSING_OBSERVED_RECORD',
               'response_boundary': 'output_ready' if p['task'] == 'C' else 'persist_complete',
               'recorded_response_s': response / NS if response is not None else None,
               'response_s': valid_response / NS if valid_response is not None else None,
               'response_latency_s': (valid_response - p['arrival_ns']) / NS if valid_response is not None else None,
               'available_s': available / NS if available is not None else None,
               'phases_s': stages, 'durations_s': stages,
               'complete_vector': complete and successful and not result_issues,
               'raw_phase_common_ns': times, 'content_provenance': content,
               'issues': issues, 'result_binding_issues': result_issues,
               'quality_equivalence_verified': False}
        row.update({k[:-3] + '_s': t / NS if t is not None else None for k, t in times.items()})
        row['admission_s'] = ((times['queue_entry_ns'] - p['arrival_ns']) / NS
                              if times['queue_entry_ns'] is not None and not issues else None)
        row['queue_wait_s'] = ((times['dispatch_ns'] - times['queue_entry_ns']) / NS
                               if times['dispatch_ns'] is not None and times['queue_entry_ns'] is not None and not issues else None)
        rows.append(row)
    return rows


def parse_hal(raw, origin, provenance):
    """HAL AP type0 only, read completion clock; full recorded history retained."""
    lines, invalid = json_lines(raw)
    points, channels = [], []
    for no, q, line_sha in lines:
        lo, hi = q.get('device_elapsed_before_ns'), q.get('device_elapsed_after_ns')
        if origin is None or type(lo) is not int or type(hi) is not int or lo > hi:
            invalid.append({'line': no, 'reason': 'MISSING_CLOCK_OR_REVERSED_DEVICE_READ_BRACKET', 'line_sha256': line_sha})
            continue
        sensors = q.get('sensors')
        if not isinstance(sensors, list):
            invalid.append({'line': no, 'reason': 'SENSOR_LIST_MISSING', 'line_sha256': line_sha})
            continue
        base = {'t_s': (hi - origin) / NS, 'lo_s': (lo - origin) / NS, 'hi_s': (hi - origin) / NS,
                't_ns': hi - origin, 'lo_ns': lo - origin, 'hi_ns': hi - origin,
                'source_line': no, 'line_sha256': line_sha, 'provenance': provenance,
                'sensor_source_section': q.get('sensor_source_section'),
                'timestamp_semantics': 'DEVICE_READ_COMPLETION_NOT_SENSOR_REFRESH',
                'surface_temperature_verified': False}
        for s in sensors:
            if isinstance(s, dict):
                channels.append({**base, 'channel': s.get('sensor_name'), 'sensor_type': s.get('sensor_type'),
                                 'value_c': s.get('value_c'), 'sensor_raw': s})
        ap = [s for s in sensors if isinstance(s, dict) and s.get('sensor_name') == 'AP' and type(s.get('sensor_type')) is int and s['sensor_type'] == 0]
        if q.get('sensor_source_section') != 'CURRENT_HAL' or len(ap) != 1 or not number(ap[0].get('value_c')):
            invalid.append({'line': no, 'relative_read_end_ns': hi - origin,
                            'reason': 'UNIQUE_CURRENT_HAL_AP_TYPE0_NOT_AVAILABLE', 'line_sha256': line_sha})
            continue
        s = ap[0]
        points.append({**base, 'channel': 'AP', 'sensor_type': 0, 'ap_c': s['value_c'], 'AP_c': s['value_c'],
                       'initial_eligible': hi <= origin,
                       'sensor_timestamp_ns': s.get('sensor_timestamp_ns'), 'cache_age_ns': s.get('cache_age_ns'),
                       'sensor_path': s.get('sensor_path', s.get('path')), 'sensor_raw': s})
    points.sort(key=lambda p: (p['t_ns'], p['source_line']))
    for a, b in zip(points, points[1:]):
        b['gap_from_previous_s'] = (b['t_ns'] - a['t_ns']) / NS
    return points, channels, invalid


def ap_zoh(points, initial_ap_c=None, gap_s=5, window_s=(35, 180)):
    """Two-sided qualification, causal left ZOH; no future-value interpolation."""
    require(gap_s in (5, 10), 'Only separately declared 5s/10s methods supported')
    lo, hi = (int(t * NS) for t in window_s)
    require(lo < hi, 'Reversed AP window')
    valid = all(type(p.get('t_ns')) is int and number(p.get('ap_c', p.get('AP_c'))) for p in points)
    pts = sorted(points, key=lambda p: p['t_ns']) if valid else []
    times = [p['t_ns'] for p in pts]; reasons = [] if valid else ['INVALID_PROJECTED_POINT']
    duplicates = [a for a, b in zip(times, times[1:]) if a == b]
    if duplicates:
        reasons.append('DUPLICATE_READ_COMPLETION_CLOCK')
    boundaries, boundary = {}, {}
    for target in (lo, hi):
        left, right = bisect.bisect_right(times, target) - 1, bisect.bisect_left(times, target)
        a, b = pts[left] if left >= 0 else None, pts[right] if right < len(pts) else None
        good = a is not None and b is not None and target - a['t_ns'] <= gap_s * NS and b['t_ns'] - target <= gap_s * NS
        boundaries[str(target)] = {'left': a, 'right': b, 'qualified': good}
        if good:
            boundary[target] = a.get('ap_c', a.get('AP_c'))
        else:
            reasons.append('MISSING_OR_OVER_LIMIT_TWO_SIDED_BOUNDARY_' + str(target))
    gaps = [{'left_ns': a, 'right_ns': b, 'gap_ns': b - a} for a, b in zip(times, times[1:])
            if a < hi and b > lo and b - a > gap_s * NS]
    if gaps:
        reasons.append('INTERIOR_COMPLETION_GAP_OVER_LIMIT')
    out = {'method': 'FROZEN5S_READ_COMPLETION_ZOH' if gap_s == 5 else 'SEPARATE10S_READ_COMPLETION_ZOH_DIAGNOSTIC',
           'window_s': list(window_s), 'gap_limit_s': gap_s, 'qualified': not reasons,
           'reasons': sorted(set(reasons)), 'evidence': {'boundaries': boundaries, 'long_gaps': gaps, 'duplicate_completion_ns': duplicates},
           'mean_c': None, 'peak_c': None, 'end_c': None, 'residual_from_initial_c': None,
           'physical_interpolation': False, 'future_value_interpolation': False, 'sensor_update_time_known': False}
    if reasons:
        return out
    last_t, last_v, area, peak = lo, boundary[lo], 0.0, boundary[lo]
    for p in pts:
        if lo < p['t_ns'] <= hi:
            area += (p['t_ns'] - last_t) / NS * last_v
            last_t, last_v = p['t_ns'], p.get('ap_c', p.get('AP_c'))
            peak = max(peak, last_v)
    area += (hi - last_t) / NS * last_v
    out.update(mean_c=area / ((hi - lo) / NS), peak_c=peak, end_c=boundary[hi],
               residual_from_initial_c=boundary[hi] - initial_ap_c if number(initial_ap_c) else None)
    return out


def ownership(rows):
    intervals, unclosed = [], []
    for q in rows:
        start, end = q['dispatch_s'], q['available_s']
        if start is None:
            continue
        if end is None or q['issues']:
            unclosed.append({'request_id': q['request_id'], 'start_s': start, 'end_s': end, 'issues': q['issues']})
        elif end >= start:
            intervals.append({'start_s': start, 'end_s': end, 'task': q['task'], 'route': q['route'],
                              'request_id': q['request_id'], 'kind': 'DISPATCH_TO_AVAILABLE', 'hardware_delegate_verified': False})
    pairs = []
    for index, a in enumerate(intervals):
        for b in intervals[index + 1:]:
            start, end = max(a['start_s'], b['start_s']), min(a['end_s'], b['end_s'])
            if start < end:
                pair = {(a['task'], a['route']), (b['task'], b['route'])}
                pairs.append({'start_s': start, 'end_s': end, 'duration_s': end - start,
                              'request_ids': [a['request_id'], b['request_id']],
                              'CG_DC': pair == {('C', 'GPU'), ('D', 'CPU')}})
    return intervals, {'unclosed_owners': unclosed, 'observed_pair_overlaps': pairs,
                       'actual_overlap_used_for_timing_pool': False,
                       'complete_dispatched_ownership': not unclosed,
                       'unfinished_not_assumed_idle': True}


def wait_rows(event_rows, origin, event_clock_field):
    starts, waits, invalid = {}, [], []
    for no, q, line_sha in event_rows:
        kind = str(q.get('kind', '')).upper()
        if kind not in ('WAIT_START', 'WAIT_END'):
            continue
        key, t = q.get('wait_id'), q.get(event_clock_field)
        if not isinstance(key, str) or type(t) is not int or origin is None:
            invalid.append({'line': no, 'reason': 'UNSUPPORTED_WAIT_ID_OR_DECLARED_CLOCK', 'raw': q})
            continue
        if kind == 'WAIT_START':
            if key in starts:
                invalid.append({'line': no, 'reason': 'DUPLICATE_WAIT_START', 'raw': q})
            else:
                starts[key] = (t, no)
        else:
            start = starts.pop(key, None)
            if start is None or t < start[0]:
                invalid.append({'line': no, 'reason': 'MISSING_OR_REVERSED_WAIT_START', 'raw': q})
            else:
                waits.append({'wait_id': key, 'start_s': (start[0] - origin) / NS,
                              'end_s': (t - origin) / NS, 'actual_s': (t - start[0]) / NS,
                              'start_line': start[1], 'end_line': no, 'end_line_sha256': line_sha})
    invalid.extend({'reason': 'WAIT_END_UNOBSERVED', 'wait_id': key, 'start_ns': start[0]} for key, start in starts.items())
    return {'rows': waits, 'invalid': invalid, 'dose_s': sum(q['actual_s'] for q in waits) if waits and not invalid else None,
            'count': len(waits) if waits and not invalid else None, 'missing_instrumentation_is_zero': False}


def battery_proxy(event_rows, origin):
    samples, invalid = [], []
    for no, q, line_sha in event_rows:
        if q.get('kind') != 'sensor_sample':
            continue
        lo, hi = q.get('read_start_ns'), q.get('read_end_ns')
        if origin is None or type(lo) is not int or type(hi) is not int or lo > hi:
            invalid.append({'line': no, 'reason': 'MISSING_OR_REVERSED_BATTERY_DEVICE_READ_BRACKET'})
            continue
        samples.append({'t_s': ((lo + hi) // 2 - origin) / NS, 'lo_s': (lo - origin) / NS, 'hi_s': (hi - origin) / NS,
                        'source_line': no, 'line_sha256': line_sha,
                        **{k: q.get(k) for k in ('current_raw', 'current_unit', 'voltage_raw', 'voltage_unit',
                                                'charge_counter_raw', 'charge_unit', 'plugged', 'battery_level')}})
    return {'raw_samples': samples, 'invalid': invalid, 'current_unit_qualified': False,
            'raw_API_proxy_only': True, 'refresh_time_known': False,
            'measured_J': None, 'energy_prediction_error': None, 'scale_correction_applied': False}


def denominators(rows):
    by = {}
    for name in ('ALL', 'U', 'N', 'C', 'D', 'CU', 'CN', 'DU', 'DN'):
        selected = [q for q in rows if name in ('ALL', q['priority'], q['task'], q['task'] + q['priority'])]
        by[name] = {'planned': len(selected), 'responded': sum(q['response_s'] is not None for q in selected),
                    'available': sum(q['available_s'] is not None for q in selected),
                    'failed': sum(q['status'] == 'FAILED' for q in selected),
                    'missing_records': sum('MISSING_OBSERVED_RECORD' in q['issues'] for q in selected),
                    'invalid_records': sum(bool(q['issues']) for q in selected),
                    'no_valid_response': sum(q['response_s'] is None for q in selected)}
    return by


def request_event_coverage(rows, events, origin):
    """Exact queue/dispatch/AVAILABLE event crosscheck; no WAIT absence claim."""
    issues, by = [], {}
    for no, event, _ in events:
        kind = event.get('kind')
        by.setdefault((kind, event.get('request_id')), []).append((no, event))
        if str(kind).upper() in ('WAIT_START', 'WAIT_END'):
            issues.append('WAIT_CONTEXT_REQUIRES_SEPARATE_TRACE_QUALIFICATION')
    if origin is None:
        issues.append('MISSING_CLOCK_ORIGIN')
    for row in rows:
        if row['issues'] or not row['complete_vector']:
            issues.append('INCOMPLETE_OR_INVALID_REQUEST_TRACE')
        for kind, field in (('queue_entry', 'queue_entry_ns'), ('dispatch', 'dispatch_ns'), ('lane_available', 'lane_available_ns')):
            selected = by.get((kind, row['request_id']), [])
            expected = row['raw_phase_common_ns'][field]
            if len(selected) != 1 or expected is None or origin is None or selected[0][1].get(field) != origin + expected:
                issues.append('MISSING_DUPLICATE_OR_MISMATCHED_' + kind.upper() + '_EVENT')
    return {'status': 'COMPLETE' if not issues else 'UNKNOWN', 'issues': sorted(set(issues)),
            'scope': 'Exact completed request queue/dispatch/AVAILABLE only; zero WAIT is not inferred'}


def normalize_session(spec, public, streams, receipts):
    """Pure decoded-bytes normalization. Does not authorize file/raw access."""
    sid, contract = spec['session_id'], spec['clock_contract']
    planned = project_public(public, sid, contract)
    events, event_errors = json_lines(streams.get('events.jsonl', b''))
    require(all(q.get('session_id') in (None, sid) for _, q, _ in events), 'Event payload session binding differs')
    summary = json.loads(streams['summary.json']) if 'summary.json' in streams else {}
    origin, clock_errors = resolve_origin(events, summary, contract)
    require('EVENT_SUMMARY_ORIGIN_CONFLICT' not in clock_errors, 'Inconsistent recorded clock origins fail closed')
    raw = json.loads(streams['requests.json']) if 'requests.json' in streams else []
    results = {name[:-12]: json.loads(value) for name, value in streams.items() if name.endswith('.result.json')}
    requests = normalize_requests(raw, planned, origin, public, results)
    event_coverage = request_event_coverage(requests, events, origin)
    clock_binding = {'authority': contract.get('clock_basis_authority', 'SOURCE_DECLARATION'),
                     'unique_recorded_common_origin_ns': origin,
                     'planned_count': len(planned), 'observed_count': len(raw),
                     'missing_observed_count': sum('MISSING_OBSERVED_RECORD' in q['issues'] for q in requests),
                     'clock_plan_mismatch_count': sum(any(i.startswith('PLAN_BINDING_MISMATCH_scheduled_arrival_ns')
                                                        or i.startswith('PLAN_BINDING_MISMATCH_deadline_ns')
                                                        or i.startswith('INVALID_CLOCK_') for i in q['issues']) for q in requests),
                     'origin_inferred_from_outcomes': False,
                     'installed_or_runtime_clock_verified': False,
                     'public_relative_vs_recorded_absolute_arithmetic_only': True}
    hal_names = spec.get('hal_streams', ['host_hal_raw.jsonl'])
    observations, channels, invalid_hal = [], [], []
    for name in hal_names:
        pts, ch, invalid = parse_hal(streams.get(name, b''), origin, receipts.get(name))
        observations.extend(pts); channels.extend(ch); invalid_hal.extend({**q, 'stream': name} for q in invalid)
    observations.sort(key=lambda q: (q['t_ns'], str(q['provenance']), q['source_line']))
    pre = [q for q in observations if q['hi_ns'] <= 0]
    initial = max(pre, key=lambda q: q['hi_ns']) if pre else None
    owners, execution = ownership(requests)
    clock_field = contract['event_clock_field']
    normalized_events = []
    for no, q, line_sha in events:
        t = q.get(clock_field)
        normalized_events.append({'source_line': no, 'line_sha256': line_sha, 'kind': q.get('kind'),
                                  't_s': (t - origin) / NS if type(t) is int and origin is not None else None, 'raw': q})
    clocks = [q['t_s'] for q in observations] + [e['t_s'] for e in normalized_events if e['t_s'] is not None]
    clocks += [t / NS for q in requests for t in q['raw_phase_common_ns'].values() if t is not None]
    ap0 = initial['ap_c'] if initial else None
    declared_models = public.get('models')
    compatibility = {'public_apk_sha256': public.get('apk_sha256'), 'public_models': declared_models,
                     'source_commit_declared': public.get('source_commit'),
                     'source_manifest_sha256': public.get('source_manifest_sha256'),
                     'bank_sha256': public.get('bank_sha256'), 'source_generation': spec['source_generation'],
                     'installed_APK_verified': False, 'signer_verified': False,
                     'source_clock_authority': 'PINNED_DECLARED_SOURCE_ONLY; installed/runtime clock unverified',
                     'route_selected_model_identity_verified': False,
                     'quality_binding_verified': False, 'automatic_cross_version_pooling': False}
    compatibility['ap_sensor_contract_qualified'] = bool(observations)
    compatibility['ap_sensor_contract'] = {'source_section': 'CURRENT_HAL', 'sensor_name': 'AP',
                                         'sensor_type': 0, 'clock': 'DEVICE_READ_COMPLETION',
                                         'raw_bracket_required': True,
                                         'included_records_per_line_AP_uniqueness_verified': True,
                                         'surface_temperature_verified': False}
    if spec.get('ap_activity_domain'):
        compatibility['ap_activity_domain'] = spec['ap_activity_domain']
    counts = denominators(requests)
    activity_complete = (origin is not None and not clock_errors and not event_errors
                         and not execution['unclosed_owners']
                         and counts['ALL']['missing_records'] == 0 and counts['ALL']['invalid_records'] == 0)
    coverage = [0.0, max(clocks)] if activity_complete and clocks and max(clocks) >= 0 else None
    ap_fit = bool(observations and initial is not None and coverage is not None)
    return {'session_id': sid, 'attempt_id': spec['attempt_id'], 'cohort_id': spec['cohort_id'],
            'source_family': 'm8', 'source_generation': spec['source_generation'], 'device': 'A24',
            'family': spec['family'], 'block': spec['block'], 'arm': public.get('arm'),
            'bank': spec.get('bank', public.get('recipe')),
            'protocol': {'PAIR': 'CG_DC', 'CG_DC': 'CG_DC', 'SERIAL': 'SERIAL'}.get(public.get('concurrency')),
            'public_declared_protocol': public.get('concurrency'),
            'public_route': public.get('route'), 'public_order': public.get('order'),
            'observed_role': 'DEVELOPMENT', 'original_role': spec['original_role'],
            'independent_confirm_claim': False, 'declared_status_versions': spec.get('declared_status_versions', []),
            'observations': observations, 'sensor_channels': channels, 'owner_intervals': owners,
            'requests': requests, 'events': normalized_events, 'invalid_events': event_errors,
            'initial_ap_c': ap0, 'initial_ap_time_s': initial['t_s'] if initial else None,
            'initial_ap_hi_s': initial['hi_s'] if initial else None, 'forecast_origin_s': 0.0,
            'prehistory_start_s': min(q['t_s'] for q in pre) if pre else None,
            'initial_sensor_refresh_time_known': False, 'ambient_c': None,
            'actual_recorded_window_s': [min(clocks), max(clocks)] if clocks else None,
            'planned_windows': {'service_cutoff_s': public['service_cutoff_ns'] / NS,
                                'sensor_end_s': public['sensor_end_ns'] / NS, 'AP_window_s': public.get('AP_window_s')},
            'common_origin_ns': origin, 'clock_issues': clock_errors,
            'recorded_clock_binding': clock_binding,
            'clock_contract': contract, 'invalid_HAL_records': invalid_hal,
            'AP_primary_frozen5s': ap_zoh(observations, ap0, 5),
            'AP_followon10s_diagnostic': ap_zoh(observations, ap0, 10),
            'execution': execution, 'WAIT': wait_rows(events, origin, clock_field),
            'request_event_coverage': event_coverage['status'],
            'request_event_coverage_evidence': event_coverage,
            'denominators': counts, 'idle_planned_session': len(planned) == 0,
            'activity_coverage_s': coverage,
            'target_eligibility': {'ap_fit': ap_fit, 'timing_fit': any(q['complete_vector'] for q in requests),
                                   'measured_energy_fit': False},
            'target_exclusions': {'ap_fit': None if ap_fit else 'MISSING_REAL_INITIAL_AP_OR_INCOMPLETE_ACTIVITY_OR_CLOCK_COVERAGE',
                                  'measured_energy_fit': 'CURRENT_UNIT_AND_PHYSICAL_ACCOUNTING_UNRESOLVED'},
            'battery': battery_proxy(events, origin), 'measured_J': None,
            'physical_goal_pass': False, 'compatibility': compatibility,
            'compatibility_sha256': digest(compatibility), 'provenance': receipts,
            'raw_sources': spec['members'], 'use': spec['use'], 'exclusion': spec.get('exclusion'),
            'normal_closed_is_not_on_time_success': True, 'causal_effect_claim': False}


def validate_operation(operation, inventory):
    require(operation.get('schema') == OP_SCHEMA and operation.get('allow_raw_access') is True,
            'Parent-registered raw extraction operation required')
    require(operation.get('device') == 'A24' and operation.get('observed_role') == 'DEVELOPMENT', 'A24 development-only scope required')
    for name in ZERO_EXECUTION:
        require(type(operation.get(name)) is int and operation[name] == 0, 'Zero-execution boundary differs: ' + name)
    require(operation.get('measured_J') is None and operation.get('physical_goal_pass') is False,
            'Uncalibrated energy/physical scope differs')
    checked_file(operation['operator_pin']); checked_file(operation['test_pin'])
    require(Path(operation['operator_pin']['path']).resolve() == Path(__file__).resolve(), 'Operator pin is not this exact source')
    checked_file(operation['registration_pin'])
    for pin in operation.get('protected_pins', []):
        checked_file(pin)
    sessions = operation.get('sessions')
    require(isinstance(sessions, list) and sessions, 'Exact registered sessions/attempts required')
    require(len({(s['session_id'], s['attempt_id']) for s in sessions}) == len(sessions), 'Duplicate session attempt')
    by_sid_cohort = {}
    for s in sessions:
        by_sid_cohort.setdefault(s['session_id'], set()).add(s['cohort_id'])
    require(all(len(groups) == 1 for groups in by_sid_cohort.values()), 'One session/version family cannot cross holdout cohorts')
    require(operation.get('session_attempt_roster_sha256') == digest([[s['session_id'], s['attempt_id']] for s in sessions]), 'Session attempt roster pin differs')
    audited = {member_key(r) for r in inventory['members']}
    selected = set()
    for s in sessions:
        for key in ('attempt_id', 'source_generation', 'cohort_id', 'family', 'block', 'original_role', 'use'):
            require(isinstance(s.get(key), str) and s[key], 'Explicit session field required: ' + key)
        require(s['use'] in ('DEVELOPMENT', 'INVENTORY_EXCLUDED'), 'Unknown session use')
        if s['use'] == 'INVENTORY_EXCLUDED':
            require(isinstance(s.get('exclusion'), str) and s['exclusion'], 'Explicit excluded-attempt reason required')
        contract = s.get('clock_contract') or {}
        if s['use'] == 'DEVELOPMENT':
            _validate_clock_contract(contract)
        refs = s.get('members', [])
        require(isinstance(refs, list), 'Exact members list required')
        for r in refs:
            require(member_key(r) in audited, 'Selected member lacks exact audited SHA binding')
            require(r.get('role') in ('PUBLIC_MANIFEST', 'RAW_STREAM', 'REQUEST_RESULT', 'INVENTORY_ONLY'), 'Unknown selected member role')
            match = SID_PATH.match(r['member'])
            require(match and match.group(1).lower() == s['session_id'].lower(), 'Member path/session binding differs')
            selected.add(member_key(r))
        if s['use'] == 'DEVELOPMENT':
            groups = deduplicate_refs(refs)
            require(sum(g['selected']['role'] == 'PUBLIC_MANIFEST' for g in groups) == 1,
                    'Exactly one deduplicated public manifest required')
    exclusions = operation.get('excluded_members')
    require(isinstance(exclusions, list), 'All received member use/exclusion ledger required')
    excluded = set()
    for r in exclusions:
        require(member_key(r) in audited and isinstance(r.get('reason'), str) and r['reason'], 'Excluded member identity/reason invalid')
        excluded.add(member_key(r))
    require(not selected.intersection(excluded), 'A received member has both selected and excluded uses')
    require(selected.union(excluded) == audited, 'Received member use/exclusion inventory is incomplete')


def _validate_clock_contract(contract):
        require(contract.get('clock_basis_authority', 'SOURCE_DECLARATION') in
                ('SOURCE_DECLARATION', 'EMPIRICAL_RECORDED_CLOCK_BINDING'), 'Unknown clock authority')
        if contract.get('clock_basis_authority') == 'EMPIRICAL_RECORDED_CLOCK_BINDING':
            require(contract.get('origin_source') == 'UNIQUE_EVENTS_COMMON_START_ORIGIN_NS', 'Empirical binding requires unique explicit recorded origin')
        require(contract.get('planned_clock_basis') == 'COMMON_START_RELATIVE_NANOSECONDS'
                and type(contract.get('planned_clock_shift_ns')) is int and contract['planned_clock_shift_ns'] == 0,
                'Predeclared planned clock source required')
        require(contract.get('event_clock_field') in ('mono_ns', 'elapsed_realtime_ns'), 'Explicit supported event clock field required')
        require(contract.get('public_field_pointers') in (NATIVE_PUBLIC_POINTERS, PROJECTED_PUBLIC_POINTERS), 'Explicit public field projection required')
        require(contract.get('origin_source') in ('UNIQUE_EVENTS_COMMON_START_ORIGIN_NS', 'SUMMARY_COMMON_START_NS'), 'Explicit origin source required')
        evidence = contract.get('evidence_pins')
        require(isinstance(evidence, list) and evidence, 'Pinned source clock declarations must precede payload access')
        for e in evidence:
            require(e.get('role') in ('PUBLIC_GENERATOR_CLOCK_SOURCE', 'PUBLIC_CLOCK_DECLARATION')
                    and isinstance(e.get('source_location'), str) and e['source_location'], 'Clock authority/location required')
            checked_file(e)


def _read_selected(selected):
    """Hash full archive, decompress only exact selected members; never testzip."""
    by_archive, data, receipts = {}, {}, {}
    for ref in selected:
        by_archive.setdefault((ref['archive_path'], ref['archive_sha256'], ref['archive_bytes']), []).append(ref)
    for (name, sha, size), refs in by_archive.items():
        checked_file({'path': name, 'sha256': sha, 'bytes': size})
        with zipfile.ZipFile(name) as z:
            names = z.namelist()
            require(len(names) == len(set(names)), 'Duplicate ZIP member names')
            for member in names:
                safe_member(member.rstrip('/'))
            for ref in refs:
                raw = z.read(ref['member'])
                require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'Selected member SHA differs')
                require(ref.get('bytes') is None or len(raw) == ref['bytes'], 'Selected member bytes differ')
                key = member_key(ref)
                data[key] = raw
                receipts[key] = {**ref, 'actual_bytes': len(raw), 'actual_member_SHA_verified': True,
                                 'selected_member_CRC_checked_by_zip_read': True,
                                 'unselected_members_decompressed': False}
    return data, receipts


def extract(operation):
    """Single raw entry. Parent owns registration/locks/budget/output sealing."""
    inventory = inventory_from_audits(operation['audit_sources'])
    validate_operation(operation, inventory)
    all_selected = [r for s in operation['sessions'] if s['use'] == 'DEVELOPMENT'
                    for group in deduplicate_refs(s['members']) for r in [group['selected']]
                    if r['role'] != 'INVENTORY_ONLY']
    payloads, payload_receipts = _read_selected(all_selected)
    sessions, excluded_attempts = [], []
    for s in operation['sessions']:
        if s['use'] != 'DEVELOPMENT':
            excluded_attempts.append(s)
            continue
        streams, receipts, public = {}, {}, None
        for group in deduplicate_refs(s['members']):
            ref = group['selected']
            if ref['role'] == 'INVENTORY_ONLY':
                continue
            key = member_key(ref)
            receipt = {**payload_receipts[key], 'identical_republications': group['all_republications']}
            if ref['role'] == 'PUBLIC_MANIFEST':
                public = json.loads(payloads[key]); receipts['public_manifest'] = receipt
            else:
                stream = ref.get('logical_stream', PurePosixPath(ref['member']).name)
                require(stream not in streams, 'Duplicate selected stream name')
                streams[stream] = payloads[key]; receipts[stream] = receipt
        require(public is not None, 'Public manifest unavailable')
        try:
            sessions.append(normalize_session(s, public, streams, receipts))
        except ValueError as exc:
            # A new public schema is an explicit eligibility exclusion, not a
            # guessed coercion or silently omitted planned denominator. Identity,
            # duplication, integrity and inconsistent clocks still fail closed.
            semantic_absence = ('Missing native public planned fields', 'Public requests array required',
                                'Explicit public planned window required', 'Public group has unsupported native type')
            if any(str(exc).startswith(reason) for reason in semantic_absence):
                excluded_attempts.append({**s, 'use': 'INVENTORY_EXCLUDED',
                                          'exclusion': 'UNSUPPORTED_PUBLIC_SCHEMA: ' + str(exc),
                                          'verified_member_receipts': receipts})
            else:
                raise
    # Preservation recheck prevents a result from claiming an unchanged protected
    # source when a concurrent writer changed it during extraction.
    for pin in operation.get('protected_pins', []):
        checked_file(pin)
    return {'schema': SCHEMA, 'device': 'A24', 'sessions': sessions,
            'excluded_attempts': excluded_attempts, 'inventory': inventory,
            'excluded_members': operation['excluded_members'],
            'operation_sha256': digest(operation), 'observed_role': 'DEVELOPMENT',
            'new_environment': 0, 'fit': 0, 'NN': 0, 'HTTP': 0,
            'measured_J': None, 'independent_confirm_claim': False, 'physical_goal_pass': False,
            'planned_requests': sum(len(s['requests']) for s in sessions),
            'missing_response_count': sum(s['denominators']['ALL']['no_valid_response'] for s in sessions)}
