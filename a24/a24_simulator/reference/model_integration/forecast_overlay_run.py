"""V3 registered INITIAL_DEV8 bank overlay on the byte-preserved V2 forecast.

Only a separately pinned public-recipe/development proof can fill the eight
declared null session banks. Original dataset and V2 remain immutable. Exact
nonbank and thermal-input projections must agree before and after the overlay;
the fitted AP artifacts still bind their original dataset, without a new AP fit.

Import is inert. This file does not amend the frozen G002 sources, original
receipts, budgets, models, or dashboards. Every attempted policy schedule
consumes a new durable START, including a failure. The frozen runtime wrapper's
top-level new_environment=0 denotes its orchestration hook only: the separate
forecast ledger is the actual simulation cost and is reported without netting
FAILs against successes. No network, device calls or neural training exists.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics

from runtime_guard import (append, canonical, free_guard, now, operation, pin,
                           process_guard, read, require, sha, write_new)

WORK = Path(__file__).resolve().parent
BASE = Path('C:/Users/chomg/Documents/Codex/2026-10-11/dkfo')
WORKER_LOCK = BASE / 'outputs/A24-INTEGRATED-SIM-20261016-G002/worker.lock'
VERSION = 'A24-REGISTERED-RULE-FORECAST-v1'
GLOBAL_CAP = 137712
CANONICAL_START = 26454
A24_POOL_CAP = 2048
A24_CANONICAL_START = 1695
A24_REMAINING = 353
SHARED_FORECAST_CAP = 256
OVERLAY_VERSION = 'A24_INITIAL_DEV8_TIMING_BANK_OVERLAY_V1'
V2_SOURCE_SHA256 = '07c14743c8feb1f9eb366629cf981d828c2177c9beddd35ffe04c41d08145078'
ORIGINAL_DATASET_SHA256 = 'f54df34fb498d235a97779aacf23e6a83cb1e4d71be807458d603face1254800'
INITIAL_DEV8_COHORT = 'INITIAL_DEV8:R02DEV01'
INITIAL_DEV8_IDS = frozenset((
    '1ced3c7b-08b1-5451-83d0-bcb67becf67a', '2bb07991-50e6-5fcd-a349-2dec89eca1cf',
    '3a4a1779-792f-5ac2-81db-6305d5d30ce1', '3b932f77-cb31-5bcf-8107-84438fe8986a',
    '5c5e6b24-f763-5765-b9bf-d1aa6b514d2b', '746e37fa-1d5e-59f4-80ef-678585c5af1b',
    'dabc27c2-bc7c-50cc-984f-ee7f810a081c', 'ee4ea490-91c2-5821-9049-33aa5e313196'))
DEFAULT_RULES = ('FIFO_SERIAL_CG', 'FIFO_PAIR_CG', 'FIFO_WAIT_CG', 'ATC', 'MOBILE_DEADLINE_ENERGY')
ARRIVAL_MODES = ('original', 'dense0.65', 'burstbucket2s')
DEADLINE_MODES = ('original', 'relative0.65')
PUBLIC_REQUEST_FIELDS = ('ordinal', 'task', 'priority', 'group', 'input_sha256', 'tensor_sha256')
STATIC_INITIAL_FIELDS = ('initial_ap_c', 'initial_ap_time_s', 'initial_ap_hi_s',
                         'prehistory_start_s', 'ambient_c', 'forecast_origin_s')
PUBLIC_COMPATIBILITY_FIELDS = ('public_apk_sha256', 'public_models', 'source_commit_declared',
    'source_manifest_sha256', 'bank_sha256', 'source_generation', 'installed_APK_verified',
    'signer_verified', 'source_clock_authority', 'quality_binding_verified',
    'automatic_cross_version_pooling', 'ap_activity_domain', 'activity_pool_qualified', 'ap_sensor_contract')


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def thermal_input_projection(sessions):
    """Exact raw inputs of frozen AP features, targets, domains and eligibility.

    This is a projection equality check, not a fit or feature evaluation. The
    stronger full nonbank dataset digest below also preserves every field not
    listed here, including all request outcomes and provenance.
    """
    names = ('session_id', 'cohort_id', 'device', 'source_family', 'source_generation',
             'protocol', 'compatibility', 'target_eligibility', 'target_exclusions',
             'initial_ap_c', 'initial_ap_time_s', 'initial_ap_hi_s', 'forecast_origin_s',
             'prehistory_start_s', 'ambient_c', 'observations', 'owner_intervals',
             'state_intervals', 'activity_coverage_s', 'provenance')
    return [{k: session[k] for k in names if k in session} for session in sessions]


def nonbank_dataset_projection(dataset):
    """Remove only the explicitly amended session-level bank leaf."""
    return {k: [{name: value for name, value in session.items() if name != 'bank'}
                for session in value] if k == 'sessions' else value
            for k, value in dataset.items()}


def bank_map(sessions):
    return [{'session_id': s['session_id'], 'bank_present': 'bank' in s, 'bank': s.get('bank')}
            for s in sorted(sessions, key=lambda s: s['session_id'])]


def apply_timing_bank_overlay(dataset, overlay, original_dataset_pin, overlay_sha256):
    """Apply only eight registered public-label repairs on a detached copy.

    Public recipe and DEVELOPMENT evidence are saved, pinned projections. This
    function never opens an archive or claims to reverify raw CRCs. Their exact
    registered proof is required, and all nonbank content stays identical.
    """
    require(overlay.get('schema') == OVERLAY_VERSION, 'Timing bank overlay schema')
    require(original_dataset_pin.get('sha256') == ORIGINAL_DATASET_SHA256,
            'V3 overlay is bound to the original f54 compact dataset only')
    declared = overlay.get('original_dataset_pin', {})
    require(declared.get('sha256') == original_dataset_pin.get('sha256') and
            _path_key(declared.get('path', '')) == _path_key(original_dataset_pin.get('path', '')) and
            declared.get('bytes') == original_dataset_pin.get('bytes'),
            'Overlay original dataset exact path/SHA/size binding differs')
    require(re.fullmatch(r'[0-9a-f]{64}', str(overlay_sha256)) is not None,
            'Registered overlay SHA required')
    sessions = dataset.get('sessions')
    require(isinstance(sessions, list) and all(isinstance(s, dict) for s in sessions), 'Dataset session rows')
    by_id = {s.get('session_id'): s for s in sessions}
    require(len(by_id) == len(sessions) and None not in by_id, 'Duplicate or absent dataset session identity')
    require({s['session_id'] for s in sessions if s.get('cohort_id') == INITIAL_DEV8_COHORT} == INITIAL_DEV8_IDS,
            'Original INITIAL_DEV8 whole-cohort roster differs')
    records = overlay.get('records')
    require(isinstance(records, list) and len(records) == 8 and
            {r.get('session_id') for r in records} == INITIAL_DEV8_IDS,
            'Overlay must contain exactly the eight registered INITIAL_DEV8 sessions')
    before_nonbank = digest(nonbank_dataset_projection(dataset))
    before_thermal = digest(thermal_input_projection(sessions))
    before_banks = digest(bank_map(sessions))
    effective = copy.deepcopy(dataset)
    effective_by_id = {s['session_id']: s for s in effective['sessions']}
    changes = []
    for row in records:
        sid, bank = row['session_id'], row.get('bank')
        source = by_id[sid]
        require(bank in ('C252', 'L64', 'M128'), 'Overlay bank is not a declared public bank')
        require('old_bank' in row and row['old_bank'] is None and
                'bank' in source and source['bank'] is None, 'Overlay may fill an explicit null session bank only')
        require(row.get('cohort_id') == source.get('cohort_id') == INITIAL_DEV8_COHORT and
                source.get('source_family') == 'm8' and source.get('device') == 'A24',
                'Overlay session/cohort/device/source identity differs')
        require(row.get('provenance_reference') == source.get('provenance', {}).get('saved_full_reference') and
                isinstance(row.get('provenance_reference'), dict), 'Overlay original compact provenance differs')
        public, development = row.get('public_recipe', {}), row.get('development_proof', {})
        require(public.get('session_id') == sid and public.get('bank') == bank and
                public.get('crc_verified') is True and isinstance(public.get('source_member'), str) and
                bool(public['source_member']) and
                re.fullmatch(r'[0-9a-f]{64}', str(public.get('source_sha256'))) is not None,
                'Pinned public recipe bank/SID/CRC projection proof is absent or disagrees')
        require(development.get('session_id') == sid and development.get('bank') == bank and
                development.get('role') == 'DEVELOPMENT' and isinstance(development.get('source_path'), str) and
                bool(development['source_path']) and
                re.fullmatch(r'[0-9a-f]{64}', str(development.get('source_sha256'))) is not None,
                'Pinned DEVELOPMENT bank/SID proof is absent or disagrees')
        request_null_banks = 0
        for request in source.get('requests', []):
            if 'bank' in request:
                require(request['bank'] is None or request['bank'] == bank,
                        'Explicit request bank conflicts with registered session overlay')
                request_null_banks += request['bank'] is None
        effective_by_id[sid]['bank'] = bank
        changes.append({'session_id': sid, 'cohort_id': source['cohort_id'], 'old_bank': None, 'bank': bank,
                        'request_fields_changed': 0, 'explicit_null_request_bank_retained': request_null_banks,
                        'public_recipe_sha256': digest(public), 'development_proof_sha256': digest(development)})
    after_nonbank = digest(nonbank_dataset_projection(effective))
    after_thermal = digest(thermal_input_projection(effective['sessions']))
    require(before_nonbank == after_nonbank, 'Bank overlay changed nonbank dataset content')
    require(before_thermal == after_thermal, 'Bank overlay changed AP feature/target/domain content')
    proof = {'schema': OVERLAY_VERSION + '-APPLICATION-PROOF', 'overlay_sha256': overlay_sha256,
             'data_original_sha256': original_dataset_pin['sha256'], 'original_dataset_pin': original_dataset_pin,
             'session_count': len(sessions), 'amended_sessions': 8, 'changes': sorted(changes, key=lambda r: r['session_id']),
             'bank_map_before_sha256': before_banks, 'effective_bank_map_sha256': digest(bank_map(effective['sessions'])),
             'effective_dataset_canonical_sha256': digest(effective),
             'nonbank_dataset_before_sha256': before_nonbank, 'nonbank_dataset_after_sha256': after_nonbank,
             'thermal_input_before_sha256': before_thermal, 'thermal_input_after_sha256': after_thermal,
             'all_nonbank_content_unchanged': True, 'AP_inputs_targets_domains_and_roster_unchanged': True,
             'original_dataset_mutated': False, 'thermal_artifacts_training_dataset_remains_original': True,
             'new_AP_fit': 0, 'NN_training': 0, 'simulation_START_consumed': 0,
             'raw_CRC_reverified_here': False, 'proof_basis': 'exact registered saved public-recipe and DEVELOPMENT projections',
             'operation_effect': 'session.bank only; no request/AP/ownership/initial/domain/version/clock change'}
    return effective, proof


def _support_fingerprints(model):
    return {name + '_sha256': digest(getattr(model, name)) for name in ('samples', 'admissions', 'gaps')}


def install_lookup_cache(model, label):
    """Instance-local exact lookup optimization; scientific source is frozen.

    Original lookup runs on the first key. Its exact sample objects/order are
    retained in a tuple; every caller receives a fresh list. Only exact_public
    nominal scalar summaries ignore state, because the frozen original does.
    No draw, latent selection, observation clock, phase/progress math, coefficient
    or cross-fold model is cached or changed.
    """
    from timing_model import UnsupportedContext, feature_stratum
    require(not hasattr(model, '_forecast_cache'), 'Model cache already installed')
    original_pool, original_nominal = model._pool, model.nominal
    state = {'label': label, 'before': _support_fingerprints(model), 'pool': {}, 'nominal': {},
             'pool_hits': 0, 'pool_misses': 0, 'nominal_hits': 0, 'nominal_misses': 0,
             'configuration': (model.feature_mode, model.bank_mode)}
    def unchanged_config():
        require(state['configuration'] == (model.feature_mode, model.bank_mode), 'Cached lookup configuration changed')
    def pool(samples, context, task, route, protocol, public_state=None, **kwargs):
        unchanged_config()
        observed_state = kwargs.pop('state', public_state)
        require(not kwargs, 'Unexpected pool cache keyword')
        key = (id(samples), digest(context), task, route, protocol,
               feature_stratum(observed_state or {}, model.feature_mode))
        if key in state['pool']:
            state['pool_hits'] += 1
            result = state['pool'][key]
        else:
            state['pool_misses'] += 1
            try:
                result = ('OK', tuple(original_pool(samples, context, task, route, protocol, observed_state)))
            except UnsupportedContext as exc:
                result = ('UNKNOWN', str(exc))
            state['pool'][key] = result
        if result[0] == 'UNKNOWN':
            raise UnsupportedContext(result[1])
        return list(result[1])
    def nominal(context, task, route, protocol='SERIAL', public_state=None, **kwargs):
        # Existing callers spell the argument state=. Preserve both forms and
        # leave queue_ap's original path entirely state dependent.
        observed_state = kwargs.pop('state', public_state)
        require(not kwargs, 'Unexpected nominal cache keyword')
        unchanged_config()
        if model.feature_mode != 'exact_public':
            return original_nominal(context, task, route, protocol, state=observed_state)
        key = (digest(context), task, route, protocol)
        if key in state['nominal']:
            state['nominal_hits'] += 1
            result = state['nominal'][key]
        else:
            state['nominal_misses'] += 1
            try:
                result = ('OK', copy.deepcopy(original_nominal(context, task, route, protocol, state=observed_state)))
            except UnsupportedContext as exc:
                result = ('UNKNOWN', str(exc))
            state['nominal'][key] = result
        if result[0] == 'UNKNOWN':
            raise UnsupportedContext(result[1])
        return copy.deepcopy(result[1])
    model._pool, model.nominal, model._forecast_cache = pool, nominal, state
    return model


def lookup_cache_report(model):
    state = model._forecast_cache
    after = _support_fingerprints(model)
    require(state['before'] == after, 'Timing support mutated while exact lookup cache was active')
    return {'label': state['label'], 'before': state['before'], 'after': after,
            'support_bytes_canonical_digest_unchanged': True,
            **{k: state[k] for k in ('pool_hits', 'pool_misses', 'nominal_hits', 'nominal_misses')},
            'pool_keys': len(state['pool']), 'nominal_keys': len(state['nominal']),
            'boundary': 'instance/fold-local exact lookup only; original first call, same references/order, fresh lists; no latent/progress/phase/fit changes'}


def _path_key(path):
    return os.path.normcase(os.path.abspath(path)).replace('\\', '/').rstrip('/')


def _integer(value, label, minimum=0):
    require(type(value) is int and value >= minimum, label + ': integer required')
    return value


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _ns(row, name):
    value = row.get(name + '_ns')
    if value is not None:
        return _integer(value, name + '_ns')
    value = row.get(name + '_s')
    require(_finite(value) and value >= 0, 'Explicit public ' + name + ' clock required')
    return round(value * 1_000_000_000)


def _window_ns(session, name):
    if session.get(name + '_ns') is not None or session.get(name + '_s') is not None:
        return _ns(session, name)
    windows = session.get('planned_windows', {})
    field = 'service_cutoff_s' if name == 'service_stop' else 'sensor_end_s'
    return _ns({'declared_s': windows.get(field)}, 'declared')


def _declared_model(compatibility, task, route):
    models = compatibility.get('public_models', {}) if isinstance(compatibility, dict) else {}
    entry = models.get(task + '_' + route, {}) if isinstance(models, dict) else {}
    model = entry.get('model', {}) if isinstance(entry, dict) else {}
    return model.get('sha256') if isinstance(model, dict) else None


def public_template(session, *, bank=None, dataset_sha256=None):
    """Copy public plan fields and actual pre-origin context, never outcomes.

    Measured actual admission/dispatch/service/response/overlap/queue/deadline
    outcomes, original post-origin AP, and original owner intervals are absent.
    Source request IDs live only in a separately labeled input mapping. The new
    IDs depend on task and ordinal so paired policies use identical potentials.
    """
    source_compatibility = session.get('compatibility', {})
    compatibility = {k: copy.deepcopy(source_compatibility.get(k)) for k in PUBLIC_COMPATIBILITY_FIELDS
                     if k in source_compatibility}
    requests, mapping, seen = [], [], set()
    for q in session.get('requests', []):
        ordinal = _integer(q.get('ordinal'), 'public ordinal')
        task = q.get('task')
        require(task in ('C', 'D'), 'Public task must be C or D')
        require(ordinal not in seen, 'Unique public ordinals required')
        seen.add(ordinal)
        arrival, deadline = _ns(q, 'scheduled_arrival'), _ns(q, 'deadline')
        require(deadline >= arrival, 'Public deadline precedes arrival')
        rid = 'cf-' + task.lower() + '-' + str(ordinal).zfill(5)
        request = {k: copy.deepcopy(q.get(k)) for k in PUBLIC_REQUEST_FIELDS}
        request.update(request_id=rid, scheduled_arrival_ns=arrival, deadline_ns=deadline,
                       model_sha256=_declared_model(compatibility, task, 'GPU' if task == 'C' else 'CPU'))
        requests.append(request)
        mapping.append({'forecast_request_id': rid, 'source_public_request_id': q.get('request_id'),
                        'ordinal': ordinal, 'task': task})
    requests.sort(key=lambda q: (q['ordinal'], q['request_id']))
    stop, drain, end = (_window_ns(session, key) for key in ('service_stop', 'drain_stop', 'observation_end'))
    require(0 < stop <= drain <= end, 'Explicit planned windows inconsistent')
    past = []
    for row in session.get('observations', []):
        if (row.get('channel') == 'AP' and row.get('initial_eligible') is True and
                _finite(row.get('t_s')) and _finite(row.get('hi_s')) and
                row['t_s'] <= row['hi_s'] <= 0 and _finite(row.get('ap_c'))):
            past.append({k: copy.deepcopy(row.get(k)) for k in
                         ('channel', 't_s', 'lo_s', 'hi_s', 'ap_c', 'initial_eligible')})
    compatibility['ap_sensor_contract_qualified'] = bool(past) and source_compatibility.get('ap_sensor_contract_qualified') is True
    result = {'session_id': 'A24_CF_PUBLIC_TEMPLATE', 'source_session_id': session['session_id'],
              'cohort_id': session.get('cohort_id'), 'source_family': session.get('source_family'),
              'source_generation': session.get('source_generation'), 'device': 'A24',
              'bank': bank if bank is not None else session.get('bank'), 'compatibility': compatibility,
              'requests': requests, 'observations': past, 'counterfactual': True,
              'service_stop_ns': stop, 'drain_stop_ns': drain, 'observation_end_ns': end,
              'public_input_provenance': {'dataset_sha256': dataset_sha256,
                                          'source_session_id': session['session_id'],
                                          'source_cohort_id': session.get('cohort_id')},
              'request_id_mapping': mapping, **{k: copy.deepcopy(session.get(k)) for k in STATIC_INITIAL_FIELDS}}
    result['forecast_origin_s'] = 0. if result.get('forecast_origin_s') is None else result['forecast_origin_s']
    require(result['forecast_origin_s'] == 0., 'This registered common-clock scenario starts at0')
    if not (_finite(result.get('initial_ap_c')) and _finite(result.get('initial_ap_time_s'))
            and _finite(result.get('initial_ap_hi_s')) and result['initial_ap_time_s'] <= result['initial_ap_hi_s'] <= 0):
        result.update(initial_ap_c=None, initial_ap_time_s=None, initial_ap_hi_s=None,
                      initial_context_status='UNKNOWN_NO_REAL_COMPLETED_PRE_ORIGIN_AP')
    else:
        result['initial_context_status'] = 'REAL_COMPLETED_PRE_ORIGIN_AP_REFERENCE'
    result['public_base_sha256'] = digest({k: result[k] for k in
                                         ('bank', 'requests', 'compatibility', 'service_stop_ns',
                                          'drain_stop_ns', 'observation_end_ns')})
    result['public_initial_context_sha256'] = digest({k: result.get(k) for k in
                                                     (*STATIC_INITIAL_FIELDS, 'observations', 'compatibility')})
    return result


def transform_public_template(template, arrival_mode='original', deadline_mode='original',
                              original_deadline_semantics='PRESERVE_RELATIVE_BUDGET'):
    require(arrival_mode in ARRIVAL_MODES and deadline_mode in DEADLINE_MODES, 'Unknown registered intervention')
    require(original_deadline_semantics in ('PRESERVE_RELATIVE_BUDGET', 'PRESERVE_ABSOLUTE'), 'Deadline intervention contract')
    result = copy.deepcopy(template)
    origin = min((q['scheduled_arrival_ns'] for q in result['requests']), default=0)
    for q in result['requests']:
        original_arrival, original_deadline = q['scheduled_arrival_ns'], q['deadline_ns']
        if arrival_mode == 'dense0.65':
            arrival = origin + ((original_arrival - origin) * 65 + 50) // 100
        elif arrival_mode == 'burstbucket2s':
            arrival = origin + ((original_arrival - origin) // 2_000_000_000) * 2_000_000_000
        else:
            arrival = original_arrival
        relative = original_deadline - original_arrival
        if deadline_mode == 'relative0.65':
            deadline = arrival + (relative * 65 + 50) // 100
        elif original_deadline_semantics == 'PRESERVE_ABSOLUTE':
            deadline = original_deadline
        else:
            deadline = arrival + relative
        require(deadline >= arrival, 'Transformed public deadline precedes arrival')
        q.update(scheduled_arrival_ns=arrival, deadline_ns=deadline)
    result['intervention'] = {'arrival_mode': arrival_mode, 'deadline_mode': deadline_mode,
                              'first_arrival_anchor_ns': origin,
                              'original_deadline_semantics': original_deadline_semantics,
                              'service_window_changed': False}
    result['public_scenario_sha256'] = digest({k: result[k] for k in
                                              ('public_base_sha256', 'requests', 'intervention')})
    return result


def custom_public_template(reference, custom):
    """Registered arbitrary public requests; no past outcome fields accepted.

    Custom model/input transfer is possible only through an explicit registered
    timing reference mapping, whose public target binding is retained. An
    unsupported unmapped input remains UNKNOWN rather than silently pooled.
    """
    allowed = {'request_id', 'ordinal', 'task', 'priority', 'group', 'scheduled_arrival_ns',
               'scheduled_arrival_s', 'deadline_ns', 'deadline_s', 'input_sha256',
               'tensor_sha256', 'model_sha256', 'timing_reference'}
    result = copy.deepcopy(reference)
    result['bank'] = custom.get('bank', result['bank'])
    requests, seen_ids, seen_ordinals, mapping_rows = [], set(), set(), []
    for q in custom['requests']:
        require(not (set(q) - allowed), 'Custom requests contain forbidden/nonpublic fields')
        ordinal = _integer(q.get('ordinal'), 'custom ordinal')
        task = q.get('task')
        require(task in ('C', 'D') and q.get('priority') in ('U', 'N'), 'Custom task/priority contract')
        rid = q.get('request_id', 'cf-' + task.lower() + '-' + str(ordinal).zfill(5))
        require(isinstance(rid, str) and rid and rid not in seen_ids and ordinal not in seen_ordinals, 'Duplicate/invalid custom identity')
        seen_ids.add(rid)
        seen_ordinals.add(ordinal)
        arrival, deadline = _ns(q, 'scheduled_arrival'), _ns(q, 'deadline')
        require(deadline >= arrival, 'Custom public deadline precedes arrival')
        item = {k: copy.deepcopy(q.get(k)) for k in PUBLIC_REQUEST_FIELDS}
        stable_id = 'cf-' + task.lower() + '-' + str(ordinal).zfill(5)
        item.update(request_id=stable_id, scheduled_arrival_ns=arrival, deadline_ns=deadline,
                    model_sha256=q.get('model_sha256') or _declared_model(result['compatibility'], task, 'GPU' if task == 'C' else 'CPU'))
        if q.get('timing_reference') is not None:
            mapping = q['timing_reference']
            require(isinstance(mapping, dict) and mapping.get('assumption') == 'EXPLICIT_UNMEASURED_INPUT_TRANSFER',
                    'Custom timing reference requires an explicit transfer assumption')
            require(set(mapping) <= {'input_sha256', 'tensor_sha256', 'model_sha256', 'assumption'}, 'Unknown timing mapping field')
            require(all(isinstance(mapping.get(k), str) and mapping[k] for k in ('input_sha256', 'tensor_sha256')), 'Timing reference binding missing')
            item['timing_reference'] = copy.deepcopy(mapping)
        requests.append(item)
        mapping_rows.append({'forecast_request_id': stable_id, 'source_public_request_id': rid,
                             'ordinal': ordinal, 'task': task})
    result['requests'] = sorted(requests, key=lambda q: (q['ordinal'], q['request_id']))
    result['request_id_mapping'] = mapping_rows
    result['intervention'] = {'arrival_mode': 'REGISTERED_CUSTOM', 'deadline_mode': 'REGISTERED_CUSTOM',
                              'custom_label': custom['label'], 'model_input_mapping_is_measured': False}
    result['public_scenario_sha256'] = digest({k: result[k] for k in ('public_base_sha256', 'bank', 'requests', 'intervention')})
    return result


def timing_template(public):
    result = copy.deepcopy(public)
    flags = []
    for q in result['requests']:
        reference = q.pop('timing_reference', None)
        if reference is not None:
            q['public_target_input_binding'] = {k: q.get(k) for k in ('input_sha256', 'tensor_sha256', 'model_sha256')}
            q.update({k: reference[k] for k in ('input_sha256', 'tensor_sha256')})
            if reference.get('model_sha256') is not None:
                require(reference['model_sha256'] == q.get('model_sha256'), 'Cross-model timing transfer is not identified')
            flags.append({'request_id': q['request_id'], 'flag': 'UNMEASURED_INPUT_TO_REGISTERED_REFERENCE_TIMING_TRANSFER',
                          'public_target': q['public_target_input_binding'], 'timing_reference': reference})
    return result, flags


def build_cases(sessions, op):
    by_id = {s['session_id']: s for s in sessions}
    require(len(by_id) == len(sessions), 'Duplicate source session identity')
    bases = {}
    for spec in op['templates']:
        sid = spec['session_id']
        require(sid in by_id, 'Registered public template session absent')
        bank = spec['bank']
        require(bank not in bases, 'One explicitly selected source per bank')
        bases[bank] = public_template(by_id[sid], bank=bank, dataset_sha256=op['dataset_pin']['sha256'])
    seeds = op.get('seeds', [0, 1])
    require(seeds and len(set(seeds)) == len(seeds), 'Distinct registered seeds required')
    for seed in seeds:
        _integer(seed, 'seed')
    rules = op.get('policies', list(DEFAULT_RULES))
    rules = ['MOBILE_DEADLINE_ENERGY' if p == 'MOBILE' else p for p in rules]
    require(rules and len(set(rules)) == len(rules) and all(p in (*DEFAULT_RULES, 'FIFO_SERIAL_CPU') for p in rules),
            'Registered source supports rule forecasts only; frozen RL is not connected')
    cases = []
    for bank, base in bases.items():
        for declared_arrivals in op.get('arrival_modes', list(ARRIVAL_MODES)):
            arrivals = {'burst2s': 'burstbucket2s'}.get(declared_arrivals, declared_arrivals)
            for declared_deadlines in op.get('deadline_modes', list(DEADLINE_MODES)):
                deadlines = {'relative_original': 'original', 'relative_times0.65': 'relative0.65'}.get(declared_deadlines, declared_deadlines)
                template = transform_public_template(base, arrivals, deadlines,
                          op.get('original_deadline_semantics', 'PRESERVE_RELATIVE_BUDGET'))
                for policy in rules:
                    for seed in seeds:
                        label = '_'.join((bank, arrivals, deadlines, policy, 'S' + str(seed)))
                        cases.append({'label': label, 'bank': bank, 'policy': policy, 'seed': seed,
                                      'template': template, 'kind': 'PREDECLARED_NOVEL_GRID',
                                      'scenario_key': [base['public_base_sha256'], seed]})
    for custom in op.get('custom_cases', []):
        require(custom['reference_bank'] in bases, 'Custom case lacks registered static reference')
        template = custom_public_template(bases[custom['reference_bank']], custom)
        policy = 'MOBILE_DEADLINE_ENERGY' if custom['policy'] == 'MOBILE' else custom['policy']
        require(policy in (*DEFAULT_RULES, 'FIFO_SERIAL_CPU'), 'Unsupported custom policy')
        seed = _integer(custom.get('seed', 0), 'custom seed')
        cases.append({'label': custom['label'], 'bank': template['bank'], 'policy': policy, 'seed': seed,
                      'template': template, 'kind': 'REGISTERED_CUSTOM',
                      'scenario_key': [template['public_base_sha256'], seed]})
    require(len({c['label'] for c in cases}) == len(cases), 'Duplicate forecast label')
    require(len(cases) <= op['budget']['operation_simulation_cap'], 'Predeclared schedule count exceeds operation cap')
    return cases


class LedgerSnapshot:
    """Parse immutable receipts once, recheck exact bytes every START."""
    def __init__(self, spec):
        self.spec = copy.deepcopy(spec)
        self.path = Path(spec['path'])
        self.counts, self.rows, self.start_rows = {'START': 0, 'COMPLETE': 0, 'FAIL': 0}, 0, []
        if spec.get('missing'):
            require(not self.path.exists(), 'Declared missing ledger appeared')
            require(spec.get('START', 0) == 0, 'Missing ledger cannot consume a declared START')
            self.sha256 = None
            return
        h = hashlib.sha256()
        with self.path.open('rb') as source:
            for line in source:
                h.update(line)
                if not line.strip():
                    continue
                row = json.loads(line.decode('utf-8-sig'))
                require(isinstance(row, dict), 'Ledger row must be object')
                self.rows += 1
                event = row.get('event')
                if event in self.counts:
                    self.counts[event] += 1
                if event == 'START':
                    self.start_rows.append(row)
        self.sha256 = h.hexdigest()
        require(self.sha256 == spec['sha256'], 'Receipt source SHA changed')
        for key in ('START', 'COMPLETE', 'FAIL'):
            if key in spec:
                require(self.counts[key] == spec[key], 'Receipt event count mismatch: ' + key)
        if 'rows' in spec:
            require(self.rows == spec['rows'], 'Receipt row count mismatch')
        if 'bytes' in spec:
            require(self.path.stat().st_size == spec['bytes'], 'Receipt byte count mismatch')

    def check(self):
        if self.spec.get('missing'):
            require(not self.path.exists(), 'Previously absent canonical ledger appeared')
        else:
            require(sha(self.path) == self.sha256, 'Pinned receipt bytes changed before START')
        return {'path': str(self.path), 'sha256': self.sha256, 'missing': bool(self.spec.get('missing')),
                'rows': self.rows, **self.counts}


def budget_arithmetic(config, *, canonical_global, canonical_a24, extra_global,
                      prior_forecast_global, prior_a24, prior_shared, current_used):
    """Pure arithmetic: START, not successful completion, is the cost unit."""
    for key in ('global_cap', 'global_registered_total', 'operation_simulation_cap', 'shared_forecast_cap',
                'a24_pool_cap', 'a24_remaining_before_allocation', 'allocated_from_existing_a24',
                'reserved_global_excluding_this', 'reserved_a24_excluding_this'):
        _integer(config.get(key), 'budget.' + key)
    require(config['global_cap'] == GLOBAL_CAP, 'Global137712 cap cannot change')
    require(119750 <= config['global_registered_total'] <= GLOBAL_CAP, 'Registered global reservation total')
    require(config.get('additional_global_reservation') == 0, 'Forecast allocation must add no global reservation')
    require(config['a24_pool_cap'] == A24_POOL_CAP and canonical_a24 == A24_CANONICAL_START,
            'Original A24 shared2048 source binding')
    require(config['a24_remaining_before_allocation'] == A24_REMAINING and
            config['allocated_from_existing_a24'] == SHARED_FORECAST_CAP and
            config['shared_forecast_cap'] == SHARED_FORECAST_CAP, 'Allocate256 from original A24remaining353')
    require(canonical_global == CANONICAL_START, 'Canonical10 START total26454 changed')
    cap = config['operation_simulation_cap']
    require(0 < cap <= SHARED_FORECAST_CAP and current_used < cap, 'Operation START cap exhausted')
    require(prior_shared + current_used + 1 <= config['shared_forecast_cap'], 'Shared forecast256 START cap exhausted')
    total = canonical_global + extra_global + prior_forecast_global + current_used + 1
    reserved = config['reserved_global_excluding_this'] + cap - current_used - 1
    require(total + reserved == config['global_registered_total'], 'Global actual+reserved accounting differs')
    require(total <= GLOBAL_CAP and total + reserved <= GLOBAL_CAP, 'Global actual+reserved cap exceeded')
    a24 = canonical_a24 + prior_a24 + current_used + 1
    a24_reserved = config['reserved_a24_excluding_this'] + cap - current_used - 1
    require(a24 + a24_reserved == A24_POOL_CAP and a24 <= A24_POOL_CAP, 'A24 actual+reserved2048 pool cap')
    require(prior_a24 + current_used + 1 <= A24_REMAINING, 'Original A24remaining353 exceeded')
    return {'canonical_START': canonical_global, 'external_new_START': extra_global,
            'prior_A24_forecast_START': prior_forecast_global, 'this_forecast_START_before': current_used,
            'this_forecast_START_after': current_used + 1, 'operation_simulation_cap': cap,
            'global_START_after': total, 'global_reserved_remaining_after': reserved,
            'global_actual_plus_reserved': total + reserved, 'global_cap': GLOBAL_CAP,
            'a24_shared_START_after': a24, 'a24_reserved_remaining_after': a24_reserved,
            'a24_shared_cap': A24_POOL_CAP, 'shared_forecast_START_after': prior_shared + current_used + 1,
            'shared_forecast_cap': SHARED_FORECAST_CAP, 'FAIL_is_consumed': True}


def _ledger_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig') as source:
        return [json.loads(line) for line in source if line.strip()]


class ForecastBudgetGuard:
    def __init__(self, op, out, operation_path):
        self.op, self.out, self.operation_path = op, Path(out), Path(operation_path)
        self.operation_sha256 = sha(operation_path)
        reservation = read(pin(op['canonical_reservation_pin']))
        require(reservation.get('global_cap') == GLOBAL_CAP and reservation.get('combined_reserved') == 119750,
                'Pinned original global reservation contract')
        allocation = read(pin(op['forecast_allocation_pin']))
        require(allocation.get('global_cap') == GLOBAL_CAP and allocation.get('additional_global_reservation') == 0
                and allocation.get('original_A24_pool_cap') == A24_POOL_CAP
                and allocation.get('original_A24_START_consumed') == A24_CANONICAL_START
                and allocation.get('unused_before') == A24_REMAINING
                and allocation.get('allocated_from_original_unused') == SHARED_FORECAST_CAP
                and allocation.get('remaining_original_unallocated') == 97,
                'Registered existing A24 pool allocation binding')
        require(_path_key(allocation['prior_reservation_pin']['path']) == _path_key(op['canonical_reservation_pin']['path'])
                and allocation['prior_reservation_pin']['sha256'] == op['canonical_reservation_pin']['sha256'],
                'Allocation/canonical reservation source differs')
        require(op['budget']['reservation_id'] == 'A24CF256:' + op['forecast_allocation_pin']['sha256'],
                'Stable shared forecast reservation identity must bind the allocation SHA')
        canonical_specs = reservation['canonical_prior_ledgers']
        require(len(canonical_specs) == 10, 'Exactly10 canonical original ledger entries required')
        extra_specs = op.get('extra_consumption_ledgers', [])
        prior_specs = op.get('prior_forecast_ledger_pins', [])
        specs = [*canonical_specs, *extra_specs, *prior_specs]
        keys = [_path_key(s['path']) for s in specs]
        require(len(keys) == len(set(keys)), 'Duplicate canonical/external/forecast ledger path')
        require(op.get('all_extra_and_prior_forecast_ledgers_asserted_complete') is True,
                'Explicit complete new-forecast ledger registry assertion required')
        self.canonical = [LedgerSnapshot(s) for s in canonical_specs]
        self.extra = [LedgerSnapshot(s) for s in extra_specs]
        self.prior = [LedgerSnapshot(s) for s in prior_specs]
        self.canonical_global = sum(s.counts['START'] for s in self.canonical)
        a24_suffixes = ('/outputs/a24-integrated-sim-20261016/receipts.jsonl',
                        '/outputs/a24-integrated-sim-20261016-g002/receipts.jsonl')
        pool = [s for s in self.canonical if any(_path_key(s.path).lower().endswith(k) for k in a24_suffixes)]
        require(len(pool) == 2, 'Both original A24 parent+child ledgers required')
        self.canonical_a24 = sum(s.counts['START'] for s in pool)
        self.extra_global = sum(s.counts['START'] for s in self.extra)
        self.prior_global = sum(s.counts['START'] for s in self.prior)
        require(not any(s.spec.get('a24_pool') for s in self.extra), 'A24 new forecasts belong in prior_forecast ledger list')
        require(all(s.spec.get('a24_pool') is True for s in self.prior), 'Prior A24 forecast pool annotation required')
        self.prior_a24 = self.prior_global
        reservation_id = op['budget']['reservation_id']
        self.prior_shared = sum(sum(r.get('reservation_id', r.get('manifest', {}).get('reservation_id')) == reservation_id
                                    for r in s.start_rows) for s in self.prior)
        self.prior_fingerprints = {r.get('logical_case_sha256') for s in self.prior for r in s.start_rows}
        self.ledger = self.out / 'forecast_receipts.jsonl'
        before = read(self.out / 'START.json')['protection_before']
        require(before['count'] >= 351, 'Protected351 original union is required')
        self.protection_before = before

    def before_start(self, logical_case_sha256):
        require(sha(self.operation_path) == self.operation_sha256, 'Forecast operation changed')
        for spec in self.op['source_pins']:
            pin(spec)
        pin(self.op['canonical_reservation_pin'])
        pin(self.op['forecast_allocation_pin'])
        evidence = [s.check() for s in (*self.canonical, *self.extra, *self.prior)]
        rows = _ledger_rows(self.ledger)
        starts = [r for r in rows if r.get('event') == 'START']
        require(logical_case_sha256 not in self.prior_fingerprints and
                not any(r.get('logical_case_sha256') == logical_case_sha256 for r in starts),
                'Consumed forecast case; FAIL and COMPLETE cannot be automatically retried')
        arithmetic = budget_arithmetic(self.op['budget'], canonical_global=self.canonical_global,
                    canonical_a24=self.canonical_a24, extra_global=self.extra_global,
                    prior_forecast_global=self.prior_global, prior_a24=self.prior_a24,
                    prior_shared=self.prior_shared, current_used=len(starts))
        process = process_guard(__file__, self.op.get('known_PS_producer_paths', []))
        volumes = free_guard([self.out, self.operation_path, *[s['path'] for s in self.op['input_pins']], 'D:/'])
        return {'checked_utc': now(), 'arithmetic': arithmetic, 'ledger_sources': evidence,
                'process': process, 'volumes': volumes,
                'protection_before': self.protection_before,
                'protected_recheck_scope': 'frozen runtime_guard operation verifies all pins before and after the whole operation',
                'worker_lock_scope': 'frozen runtime_guard holds original G002 worker.lock for this operation'}


def _child(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    require(target != root and root in target.parents, 'Forecast output escapes its new namespace')
    return target


def _bytes_new(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())


class ForecastJournal:
    """raw -> prepared -> row -> immutable terminal, all with exact SHA."""
    def __init__(self, op, out, operation_sha256, guard):
        self.op, self.out, self.operation_sha256, self.guard = op, Path(out), operation_sha256, guard
        self.receipts, self.rows = self.out / 'forecast_receipts.jsonl', self.out / 'forecast_rows.jsonl'
        # The new output namespace owns an immutable initial empty row ledger.
        # All-FAIL runs therefore have a real zero-byte SHA/readable row input.
        _bytes_new(self.rows, b'')
        prefix = op['forecast_identity_prefix']
        require(isinstance(prefix, str) and re.fullmatch(r'A24CF_[A-Z0-9_]{3,64}', prefix), 'New A24CF identity prefix required')
        self.prefix = prefix

    def run(self, case, model_bindings, callback):
        logical = digest({'public_scenario_sha256': case['template']['public_scenario_sha256'],
                          'policy': case['policy'], 'seed': case['seed'], 'model_bindings': model_bindings})
        identity = self.prefix + '_' + digest([self.operation_sha256, logical])[:28]
        require(not any(r.get('identity') == identity for r in _ledger_rows(self.receipts)), 'Consumed forecast identity')
        guards = self.guard.before_start(logical)
        manifest = {'schema': VERSION, 'identity': identity, 'label': case['label'],
                    'logical_case_sha256': logical, 'operation_sha256': self.operation_sha256,
                    'reservation_id': self.op['budget']['reservation_id'],
                    'public_scenario_sha256': case['template']['public_scenario_sha256'],
                    'policy': case['policy'], 'seed': case['seed'], 'model_bindings': model_bindings}
        case['comparison_group_id'] = digest([case['template']['public_scenario_sha256'],
                           case['template']['public_initial_context_sha256'], case['seed'], model_bindings])
        append(self.receipts, {'event': 'START', 'identity': identity, 'logical_case_sha256': logical,
                              'reservation_id': manifest['reservation_id'], 'manifest': manifest,
                              'guards': guards, 'utc': now(), 'pid': os.getpid(),
                              'new_simulator_environments_consumed': 1, 'automatic_retry': False})
        paths, stage = {}, 'START_DURABLE'
        try:
            result, compact = callback({'durable_START_consumed': True, 'start_id': identity,
                                         'registration_sha256': self.operation_sha256})
            result['forecast_manifest'] = manifest
            raw = _child(self.out, 'raw/' + identity + '.json.gz')
            _bytes_new(raw, gzip.compress((canonical(result) + '\n').encode('utf-8'), mtime=0))
            paths.update(raw_path=str(raw), raw_sha256=sha(raw))
            stage = 'RAW_DURABLE'
            row = {'schema': VERSION + '-ROW', 'identity': identity, 'label': case['label'],
                   'manifest': manifest, 'bank': case['bank'], 'kind': case['kind'],
                   'intervention': case['template']['intervention'], 'policy': case['policy'],
                   'seed': case['seed'], 'status': compact['status'], **paths,
                   **{k: v for k, v in compact.items() if k != 'status'}}
            row.update(source_public_template_sha256=case['template']['public_base_sha256'],
                       public_scenario_sha256=case['template']['public_scenario_sha256'],
                       public_initial_context_sha256=case['template']['public_initial_context_sha256'],
                       comparison_group_id=case['comparison_group_id'])
            prepared = _child(self.out, 'prepared/' + identity + '.json')
            write_new(prepared, {'schema': VERSION + '-PREPARED', 'manifest': manifest, 'row': row})
            paths.update(prepared_path=str(prepared), prepared_sha256=sha(prepared))
            stage = 'PREPARED_DURABLE'
            append(self.receipts, {'event': 'PREPARED', 'identity': identity, **paths, 'utc': now()})
            row.update(paths)
            row_sha = digest(row)
            append(self.rows, row)
            stage = 'ROW_DURABLE'
            terminal = _child(self.out, 'terminal/' + identity + '.json')
            write_new(terminal, {'schema': VERSION + '-TERMINAL', 'event': 'COMPLETE',
                                'identity': identity, 'operation_sha256': self.operation_sha256,
                                **paths, 'row_sha256': row_sha,
                                'row_sha256_semantics': 'SHA256_CANONICAL_JSON_WITHOUT_NEWLINE',
                                'new_simulator_environments_consumed': 1, 'utc': now()})
            append(self.receipts, {'event': 'COMPLETE', 'identity': identity, **paths,
                                  'row_sha256': row_sha, 'terminal_path': str(terminal),
                                  'terminal_sha256': sha(terminal), 'utc': now()})
            return row
        except BaseException as exc:
            failure = {'schema': VERSION + '-TERMINAL', 'event': 'FAIL', 'identity': identity,
                       'operation_sha256': self.operation_sha256, 'stage': stage, **paths,
                       'error_type': type(exc).__name__, 'error': str(exc), 'utc': now(),
                       'new_simulator_environments_consumed': 1, 'automatic_retry': False}
            terminal = _child(self.out, 'terminal/' + identity + '.json')
            if not terminal.exists():
                write_new(terminal, failure)
            else:
                failure['existing_terminal_preserved'] = True
            append(self.receipts, {**failure, 'terminal_path': str(terminal), 'terminal_sha256': sha(terminal)})
            self.last_failure = {**failure, 'terminal_path': str(terminal), 'terminal_sha256': sha(terminal)}
            raise


class FixedObserverBudget:
    """Count fixed activity queries separately from policy schedule STARTs."""
    def __init__(self, out, ap_cap, energy_cap):
        self.out = Path(out)
        self.caps = {'AP': _integer(ap_cap, 'fixed AP cap'),
                     'HISTORICAL_J': _integer(energy_cap, 'fixed historical J cap')}
        self.used = {k: 0 for k in self.caps}

    def consume(self, target, identity):
        require(target in self.used and self.used[target] < self.caps[target], 'Registered fixed observer query cap exhausted')
        self.used[target] += 1
        append(self.out / 'fixed_observer_receipts.jsonl', {'event': 'FIXED_ACTIVITY_QUERY',
               'target': target, 'schedule_identity': identity, 'index': self.used[target],
               'cap': self.caps[target], 'utc': now(), 'new_policy_simulator_START': 0})


def generated_activity(public, prediction):
    """Only simulator ownership becomes future activity; no measured schedule."""
    end = public['observation_end_ns'] / 1_000_000_000
    owners = []
    for q in prediction['requests']:
        if q.get('dispatch_ns') is None:
            continue
        start = q['dispatch_ns'] / 1_000_000_000
        available = q.get('available_ns')
        stop = min(end, available / 1_000_000_000) if available is not None else end
        if start < stop:
            owners.append({'start_s': start, 'end_s': stop, 'request_id': q['request_id'],
                           'task': q['task'], 'route': q['route'],
                           'end_is_censored_forecast_window': available is None or available / 1_000_000_000 > end})
    result = copy.deepcopy(public)
    result.update(owner_intervals=owners, activity_coverage_s=[0., end],
                  observation_window_s=[0., end], actual_recorded_window_s=None,
                  activity_coverage_role='SIMULATED_FUTURE_NOT_DEVICE_OBSERVATION',
                  counterfactual=True)
    return result


def historical_mobile_comparator(profile):
    baseline = profile['measured35']['baseline_w']
    increments = profile['cost_anchor']['energy_increment_w']
    require(_finite(baseline) and baseline >= 0, 'Historical baseline proxy missing')
    def cost(request, route, estimate, public_state):
        label = ('classification' if request['task'] == 'C' else 'detection') + '_' + route
        increment = increments.get(label)
        require(_finite(increment) and baseline + increment >= 0, 'Historical route proxy missing')
        return estimate['occupancy_ns'] / 1_000_000_000 * (baseline + increment)
    return cost


def _ap_times(public, spec):
    if isinstance(spec, list):
        values = list(spec)
    else:
        spec = spec or {'start_s': 0., 'step_s': .5}
        lo, hi, step = spec.get('start_s', 0.), public['observation_end_ns'] / 1_000_000_000, spec.get('step_s', .5)
        require(_finite(lo) and _finite(step) and 0 <= lo <= hi and step > 0, 'AP forecast query grid')
        count = math.floor((hi - lo) / step)
        require(count <= 100000, 'AP query grid cap')
        values = [lo + i * step for i in range(count + 1)]
        if not values or values[-1] < hi:
            values.append(hi)
    require(all(_finite(x) and 0 <= x <= public['observation_end_ns'] / 1_000_000_000 for x in values)
            and all(a <= b for a, b in zip(values, values[1:])), 'Ordered public AP query times required')
    return values


def _select_redispatch(model, template, policy, case, op):
    """Predeclare whole-schedule overhead mode; never retry a failed simulation.

    The dispatch-time engine still checks every MEASURED context. This public
    support diagnostic can choose a named ideal-zero comparator before START,
    retaining UNKNOWN support and its reason. It makes no measured-latency claim.
    """
    from timing_model import context_for_route, context_of
    support = []
    for q in template['requests']:
        context, _ = context_of(template, q, model.strict)
        routes = ('CPU',) if q['task'] == 'D' or policy == 'FIFO_SERIAL_CPU' else ('GPU',) if policy in DEFAULT_RULES[:3] else ('CPU', 'GPU')
        for route in routes:
            try:
                target = context_for_route(context, q['task'], route)
                model.nominal(target, q['task'], route, state={'initial_ap_c': template.get('initial_ap_c'),
                                                              'queue_count': len(template['requests'])})
            except ValueError:
                continue
            matching = [s for s in model.gaps if model._context_matches(s, target) and s['task'] == q['task'] and s['route'] == route]
            # WAIT/control intent is separately unmeasured, and rolling joins
            # need both public occupancy regimes to avoid a later silent zero.
            protocols = {s['protocol'] for s in matching}
            support.append('SERIAL' in protocols and (policy in ('FIFO_SERIAL_CPU', 'FIFO_SERIAL_CG', 'FIFO_WAIT_CG') or 'CG_DC' in protocols))
    all_supported = bool(support) and all(support) and policy != 'FIFO_WAIT_CG'
    if all_supported:
        return {'mode': 'MEASURED', 'zero_baseline_id': None, 'support': 'PREDECLARED_EXACT_READY_IDLE_GAPS',
                'limits': 'Observed gaps include the measured controller/policy event handling; not identified new policy runtime.'}
    require(op.get('unknown_redispatch') == 'EXPLICIT_IDEAL_ZERO_DIAGNOSTIC', 'Unknown redispatch requires registered diagnostic choice')
    baseline = op.get('zero_redispatch_baseline_id')
    require(isinstance(baseline, str) and baseline, 'Named zero redispatch baseline required')
    return {'mode': 'ZERO_EXPLICIT_BASELINE', 'zero_baseline_id': baseline,
            'support': 'UNKNOWN_MEASURED_REDISPATCH_EXPLICIT_IDEAL_ZERO_DIAGNOSTIC',
            'limits': 'This assumption can change queue/deadline predictions. It is not measured ATC/mobile/RL latency.'}


def _quantile(values, fraction=.95):
    if not values:
        return None
    values = sorted(values)
    return values[math.ceil(fraction * len(values)) - 1]


def deadline_summary(requests, *, service_stop_ns, drain_stop_ns):
    """Full requested denominators, exact values or right-censor lower bounds.

    P95 is nearest rank. An incomplete request never silently disappears into a
    completed-only P95 or zero tardiness. Upper bounds remain unknown.
    """
    def summarize(rows):
        completed, response_bounds, tardiness_bounds, missing = [], [], [], []
        ontime = 0
        for q in rows:
            response = q.get('response_ns')
            arrival, deadline = q['scheduled_arrival_ns'], q['deadline_ns']
            known = response is not None and response <= drain_stop_ns
            if known:
                latency, tardiness = max(0, response - arrival), max(0, response - deadline)
                completed.append(latency / 1_000_000_000)
                ontime += response <= deadline
            else:
                latency, tardiness = max(0, drain_stop_ns - arrival), max(0, drain_stop_ns - deadline)
                missing.append({'request_id': q['request_id'], 'response_lower_bound_s': latency / 1_000_000_000,
                                'tardiness_lower_bound_s': tardiness / 1_000_000_000,
                                'deadline_after_drain': deadline > drain_stop_ns,
                                'not_arrived_by_drain': arrival > drain_stop_ns})
            response_bounds.append(latency / 1_000_000_000)
            tardiness_bounds.append(tardiness / 1_000_000_000)
        return {'planned': len(rows), 'response_completed_by_drain': len(completed), 'uncompleted': len(missing),
                'on_time': int(ontime), 'on_time_rate_planned': ontime / len(rows) if rows else None,
                'P95_all_requested_response_s': _quantile(response_bounds) if not missing else None,
                'P95_all_requested_response_lower_bound_s': _quantile(response_bounds),
                'P95_completed_response_s': _quantile(completed),
                'P95_all_requested_tardiness_s': _quantile(tardiness_bounds) if not missing else None,
                'P95_all_requested_tardiness_lower_bound_s': _quantile(tardiness_bounds),
                'total_tardiness_s': sum(tardiness_bounds) if not missing else None,
                'total_tardiness_lower_bound_s': sum(tardiness_bounds),
                'uncompleted_lower_bounds': missing, 'quantile_method': 'NEAREST_RANK',
                'service_threshold_flags': {str(p): ontime / len(rows) >= p / 100 if rows else None
                                            for p in (70, 80, 90, 95, 100)},
                'missing_response_imputed': False}
    output = summarize(requests)
    cohorts = {'U': lambda q: q.get('priority') == 'U', 'N': lambda q: q.get('priority') == 'N',
               'C': lambda q: q.get('task') == 'C', 'D': lambda q: q.get('task') == 'D'}
    for task in ('C', 'D'):
        for priority in ('U', 'N'):
            cohorts[task + priority] = lambda q, t=task, p=priority: q.get('task') == t and q.get('priority') == p
    output['by_cohort'] = {key: summarize([q for q in requests if match(q)]) for key, match in cohorts.items()}
    output.update(service_stop_s=service_stop_ns / 1_000_000_000,
                  drain_stop_s=drain_stop_ns / 1_000_000_000,
                  service_cutoff_is_from_public_template=True)
    return output


def ap_summary(prediction, public, window=None):
    window = list(window or [0., public['observation_end_ns'] / 1_000_000_000])
    require(len(window) == 2 and all(_finite(t) for t in window) and 0 <= window[0] < window[1] <= public['observation_end_ns'] / 1_000_000_000,
            'AP summary window must be explicit and within forecast coverage')
    points = list(zip(prediction.get('t_s', []), prediction.get('ap_c', [])))
    selected = [(t, c) for t, c in points if window[0] <= t <= window[1]]
    eligible = (prediction.get('status') == 'CONDITIONAL_AP_PREDICTION' and selected and
                selected[0][0] == window[0] and selected[-1][0] == window[1] and all(_finite(c) for _, c in selected))
    mean = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(selected, selected[1:])) / (window[1] - window[0]) if eligible else None
    endpoint = selected[-1][1] if eligible else None
    initial = public.get('initial_ap_c')
    return {'AP_summary_window_s': window, 'AP_mean_c': mean,
            'AP_peak_c': max(c for _, c in selected) if eligible else None, 'AP_endpoint_c': endpoint,
            'AP_residual_c': endpoint - initial if endpoint is not None and _finite(initial) else None,
            'AP_residual_definition': 'summary-window endpoint minus real pre-origin initial AP',
            'AP_mean_method': 'TRAPEZOID_ON_PREDICTED_QUERY_GRID',
            'AP_points': [[t, c] for t, c in points]}


def work_scope(prediction, public, energy_window):
    rows = prediction['requests']
    energy_end = energy_window[1] * 1_000_000_000
    service, drain = public['service_stop_ns'], public['drain_stop_ns']
    def active(at):
        return [q['request_id'] for q in rows if q.get('dispatch_ns') is not None and q['dispatch_ns'] <= at
                and (q.get('available_ns') is None or q['available_ns'] > at)]
    end = public['observation_end_ns']
    after = sum(max(0, min(q.get('available_ns') if q.get('available_ns') is not None else end, end)
                       - max(q['dispatch_ns'], energy_end)) / 1_000_000_000
                for q in rows if q.get('dispatch_ns') is not None)
    return {'planned': len(rows), 'responded_by_drain': sum(q.get('response_ns') is not None and q['response_ns'] <= drain for q in rows),
            'AVAILABLE_by_drain': sum(q.get('available_ns') is not None and q['available_ns'] <= drain for q in rows),
            'unfinished_by_drain': sum(q.get('available_ns') is None or q['available_ns'] > drain for q in rows),
            'energy_window_s': energy_window,
            'responded_by_energy_end': sum(q.get('response_ns') is not None and q['response_ns'] <= energy_end for q in rows),
            'AVAILABLE_by_energy_end': sum(q.get('available_ns') is not None and q['available_ns'] <= energy_end for q in rows),
            'owners_at_service_cutoff': active(service), 'owners_at_drain_cutoff': active(drain),
            'owners_at_energy_cutoff': active(energy_end), 'modeled_owner_seconds_after_energy_window': after,
            'right_censored_owner_hold_is_assumption': any(q.get('dispatch_ns') is not None and q.get('available_ns') is None for q in rows),
            'energy_decrease_is_efficiency_or_goal_PASS': False}


def predict_case(case, model, thermal, profile, op, execution_guard, *, ap_query_times=None,
                 validation_source=None, residual_bands=None, observer_consume=None):
    from protocol_simulator import simulate_protocol
    import thermal_model
    from historical_observer import conditional_energy
    template, transfer_flags = timing_template(case['template'])
    overhead = _select_redispatch(model, template, case['policy'], case, op)
    prediction = simulate_protocol(template, model, case['policy'], execution_guard=execution_guard,
                    scenario_key=case['scenario_key'], admission_protocol=op.get('admission_protocol', 'SERIAL'),
                    redispatch_mode=overhead['mode'], zero_baseline_id=overhead['zero_baseline_id'],
                    concurrency_mode='DATA_DERIVED_PROGRESS', unidentified_overlap='SERIAL_INDEPENDENT',
                    mobile_energy=historical_mobile_comparator(profile), decision_cap=op.get('decision_cap', 4096),
                    pair_scope=op.get('pair_scope', 'READY_QUEUE'))
    activity = generated_activity(case['template'], prediction)
    query_times = _ap_times(case['template'], ap_query_times if ap_query_times is not None else op.get('ap_query_grid'))
    summary_window = op.get('AP_summary_window_s', [0., case['template']['observation_end_ns'] / 1_000_000_000])
    if validation_source is None:
        query_times = sorted(set([*query_times, *summary_window]))
    if observer_consume is not None:
        observer_consume('AP', execution_guard['start_id'])
    ap = thermal_model.predict(thermal, activity, times=query_times,
                               reference_domain=op.get('AP_reference_domain'), allow_extrapolation=True)
    if observer_consume is not None:
        observer_consume('HISTORICAL_J', execution_guard['start_id'])
    energy = conditional_energy(activity, profile, start_s=op.get('energy_start_s', 0.),
                                 end_s=op.get('energy_end_s', 180.))
    if observer_consume is not None:
        observer_consume('HISTORICAL_J', execution_guard['start_id'])
    full_energy = conditional_energy(activity, profile, start_s=0.,
                                      end_s=case['template']['observation_end_ns'] / 1_000_000_000)
    flags = [*transfer_flags, *[{'flag': f} for f in ap.get('extrapolation_flags', [])]]
    if overhead['mode'] == 'ZERO_EXPLICIT_BASELINE':
        flags.append({'flag': overhead['support']})
    rates = prediction.get('rate_history', [])
    if any('UNIDENTIFIED' in r.get('evidence', {}).get('evidence', '') for r in rates):
        flags.append({'flag': 'UNIDENTIFIED_OVERLAP_EXPLICIT_SERIAL_INDEPENDENT_FALLBACK'})
    if any(q.get('timing', {}).get('bank_extrapolation') for q in prediction['requests']):
        flags.append({'flag': 'EXPLICIT_SAME_BINDING_BANK_TIMING_TRANSFER'})
    compact = {'status': prediction['status'], 'metrics': prediction['metrics'],
               'deadline_summary': deadline_summary(prediction['requests'], service_stop_ns=template['service_stop_ns'], drain_stop_ns=template['drain_stop_ns']),
               'AP_status': ap.get('status'), **ap_summary(ap, case['template'], summary_window),
               'AP_model_sha256': ap.get('model_sha256'),
               'historical_conditional_J': energy.get('historical_conditional_J'), 'energy_status': energy.get('status'),
               'energy_window_s': energy.get('window_s'),
               'historical_conditional_J_full_forecast_window': full_energy.get('historical_conditional_J'),
               'full_forecast_energy_status': full_energy.get('status'),
               'work_scope': work_scope(prediction, case['template'], [op.get('energy_start_s', 0.), op.get('energy_end_s', 180.)]),
               'gantt': [[q['start_s'], q['end_s'], q['task'], q['route']] for q in activity['owner_intervals']],
               'redispatch': overhead, 'uncertainty_flags': flags,
               'predicted_schedule_not_measured': True, 'new_simulator_environments_consumed': 1,
               'measured_J': None, 'NN_training': 0, 'RL_connected': False,
               'predictive_accuracy_PASS': None, 'physical_goal_pass': False}
    domain = ap.get('activity_domain')
    band = (residual_bands or {}).get(domain)
    compact['AP_heldout_residual_band'] = band
    compact['AP_uncertainty_role'] = 'DESCRIPTIVE_WHOLE_SESSION_HELDOUT_RESIDUAL_RANGE_NOT_CONFIDENCE_INTERVAL' if band else 'UNKNOWN_NO_INDEPENDENT_RESIDUAL_CALIBRATION'
    result = {'schema': VERSION, 'public_input': case['template'], 'simulation': prediction,
              'simulated_activity': activity, 'AP_prediction': ap, 'historical_conditional_energy': energy,
              'historical_conditional_energy_full_forecast_window': full_energy,
              'compact': compact, 'qualification': {'role': 'RULE_COUNTERFACTUAL_MODEL_EXPERIMENT',
              'model_validation_is_separate_grouped_CV': True, 'fresh_confirmation': False,
              'RL_retraining_or_new_RL_performance': False, 'measured_device_energy': None,
              'timing_response_interval': None, 'AP_prediction_interval': None,
              'point_estimate_uncertainty_not_independent_seed_CI': True,
              'right_censored_owner_hold_is_simulated_activity_assumption': True}}
    if band is not None:
        result['AP_heldout_residual_band'] = {'calibration': band,
            'points': [[t, c + band['residual_low_c'], c + band['residual_high_c']] if _finite(c) else [t, None, None]
                       for t, c in zip(ap.get('t_s', []), ap.get('ap_c', []))],
            'confidence_interval': False, 'unmeasured_schedule_transfer_is_unvalidated': True}
    if validation_source is not None:
        validation = score_validation_trace(prediction, validation_source, case['template'])
        ap_validation = score_ap_validation(validation_source, ap)
        compact['validation'] = validation
        compact['AP_validation'] = ap_validation
        result['validation'] = validation
        result['AP_validation'] = ap_validation
    return result, compact


def score_ap_validation(source, prediction):
    """All actual AP target rows retained; unsupported query windows stay null."""
    import thermal_model
    target = thermal_model._targets(source)
    predicted = dict(zip(prediction.get('t_s', []), prediction.get('ap_c', [])))
    rows = []
    for q in target:
        value = predicted.get(q['t_s'])
        eligible = prediction.get('status') == 'CONDITIONAL_AP_PREDICTION' and _finite(value)
        rows.append({'t_s': q['t_s'], 'observed_ap_c': q['ap_c'],
                     'predicted_ap_c': value if eligible else None,
                     'error_c': value - q['ap_c'] if eligible else None,
                     'status': 'POSTHOC_HELDOUT_ERROR' if eligible else 'UNKNOWN_FORECAST_WINDOW_OR_AP_DOMAIN'})
    eligible = [r for r in rows if r['error_c'] is not None]
    return {'session_id': source['session_id'], 'cohort_id': source['cohort_id'],
            'all_target_records': len(rows), 'eligible_records': len(eligible), 'unknown_records': len(rows) - len(eligible),
            'rows': rows, 'mae_c': statistics.mean(abs(r['error_c']) for r in eligible) if eligible else None,
            'max_abs_error_c': max((abs(r['error_c']) for r in eligible), default=None),
            'endpoint_error_c': rows[-1]['error_c'] if rows else None,
            'extrapolation_flags': prediction.get('extrapolation_flags', []),
            'all_actual_recorded_targets_retained': True, 'final_all_trained_model_used': False,
            'predictive_accuracy_PASS': None}


def _maybe_ns(row, name):
    value = row.get(name + '_ns')
    if type(value) is int and value >= 0:
        return value
    value = row.get(name + '_s')
    return round(value * 1_000_000_000) if _finite(value) and value >= 0 else None


def _actual_response(row):
    if 'response_s' in row or 'response_ns' in row:
        return _maybe_ns(row, 'response')
    if row.get('complete_vector'):
        return _maybe_ns(row, 'output_ready' if row['task'] == 'C' else 'persist_complete')
    return None


def actual_deadline_summary(requests, source, *, service_stop_ns):
    """Observed missing telemetry is not a verified continuous nonresponse.

    Only an explicit tracking contract plus a finite actual recorded endpoint
    qualifies missing-response bounds. Planned simulation drain is never an
    actual censor clock. Valid recorded completions remain observed completions.
    """
    recorded = source.get('actual_recorded_window_s', source.get('observation_window_s'))
    observed_end = recorded[1] if isinstance(recorded, list) and len(recorded) == 2 and _finite(recorded[1]) and recorded[1] >= 0 else None
    tracking = source.get('continuous_response_tracking_verified') is True
    def summarize(rows):
        completed, response_bounds, tardiness_bounds, missing = [], [], [], []
        ontime, service_success = 0, 0
        for q in rows:
            response, arrival, deadline = q.get('response_ns'), q['scheduled_arrival_ns'], q['deadline_ns']
            if response is not None:
                latency, tardiness = max(0, response - arrival) / 1e9, max(0, response - deadline) / 1e9
                completed.append(latency)
                ontime += response <= deadline
                service_success += response <= min(service_stop_ns, deadline)
            else:
                response_assumption = max(0., observed_end - arrival / 1e9) if observed_end is not None else None
                tardiness_assumption = max(0., observed_end - deadline / 1e9) if observed_end is not None else None
                qualified = tracking and observed_end is not None
                latency = response_assumption if qualified else None
                tardiness = tardiness_assumption if qualified else None
                missing.append({'request_id': q['request_id'], 'response_lower_bound_s': latency,
                    'tardiness_lower_bound_s': tardiness, 'qualified': qualified,
                    'actual_recorded_observation_end_s': observed_end,
                    'recorded_end_assumption_only_response_bound_s': response_assumption,
                    'recorded_end_assumption_only_tardiness_bound_s': tardiness_assumption,
                    'reason': None if qualified else 'MISSING_TELEMETRY_DOES_NOT_PROVE_CONTINUOUS_NONRESPONSE_OR_ENDPOINT_UNKNOWN'})
            response_bounds.append(latency)
            tardiness_bounds.append(tardiness)
        qualified_all = all(x is not None for x in response_bounds + tardiness_bounds)
        return {'planned': len(rows), 'response_completed_recorded': len(completed),
                'uncompleted': len(missing), 'missing_or_invalid_response': len(missing),
                'on_time': int(ontime), 'on_time_rate_planned': ontime / len(rows) if rows else None,
                'on_time_within_source_service_cutoff': int(service_success),
                'P95_all_requested_response_s': _quantile(completed) if not missing else None,
                'P95_all_requested_response_lower_bound_s': _quantile(response_bounds) if qualified_all else None,
                'P95_completed_response_s': _quantile(completed),
                'P95_all_requested_tardiness_s': _quantile(tardiness_bounds) if not missing else None,
                'P95_all_requested_tardiness_lower_bound_s': _quantile(tardiness_bounds) if qualified_all else None,
                'total_tardiness_s': sum(tardiness_bounds) if not missing else None,
                'total_tardiness_lower_bound_s': sum(tardiness_bounds) if qualified_all else None,
                'uncompleted_lower_bounds': missing, 'censor_lower_bounds_qualified': qualified_all,
                'service_threshold_flags': {str(p): ontime / len(rows) >= p / 100 if rows else None for p in (70, 80, 90, 95, 100)},
                'service_threshold_population': 'OBSERVED_VALID_RESPONSE_COUNT_OVER_ALL_PLANNED; missing is not proof of failure',
                'quantile_method': 'NEAREST_RANK', 'missing_response_imputed': False}
    result = summarize(requests)
    result['by_cohort'] = {}
    for name in ('U', 'N', 'C', 'D', 'CU', 'CN', 'DU', 'DN'):
        result['by_cohort'][name] = summarize([q for q in requests if name in
            (q.get('priority'), q.get('task'), str(q.get('task')) + str(q.get('priority')))])
    result.update(service_stop_s=service_stop_ns / 1e9,
                  actual_recorded_observation_end_s=observed_end,
                  continuous_response_tracking_verified=tracking,
                  missing_telemetry_is_proof_of_nonresponse=False,
                  censor_clock='ACTUAL_RECORDED_ENDPOINT_ONLY; never planned simulation drain')
    return result


def score_validation_trace(prediction, source, public):
    """Read heldout outcomes only after the new schedule has finished."""
    by_source = {q['request_id']: q for q in source.get('requests', [])}
    mapping = {q['forecast_request_id']: q['source_public_request_id'] for q in public['request_id_mapping']}
    comparisons, actual_rows = [], []
    for predicted in prediction['requests']:
        original_id = mapping.get(predicted['request_id'])
        actual = by_source.get(original_id)
        row = {'request_id': predicted['request_id'], 'source_request_id': original_id,
               'status': 'UNKNOWN', 'queue_error_s': None, 'response_latency_error_s': None,
               'AVAILABLE_error_s': None, 'on_time_disagreement': None}
        if actual is not None:
            arrival, deadline = _ns(actual, 'scheduled_arrival'), _ns(actual, 'deadline')
            dispatch, queue = _maybe_ns(actual, 'dispatch'), _maybe_ns(actual, 'queue_entry')
            response = _actual_response(actual)
            available = _maybe_ns(actual, 'available')
            if available is None and not actual.get('issues'):
                available = _maybe_ns(actual, 'lane_available')
            if dispatch is not None and queue is not None and dispatch >= queue and predicted.get('dispatch_ns') is not None:
                row['queue_error_s'] = ((predicted['dispatch_ns'] - predicted['queue_entry_ns']) - (dispatch - queue)) / 1_000_000_000
            if response is not None and predicted.get('response_ns') is not None:
                row['response_latency_error_s'] = ((predicted['response_ns'] - predicted['scheduled_arrival_ns']) - (response - arrival)) / 1_000_000_000
                row['on_time_disagreement'] = int((predicted['response_ns'] <= predicted['deadline_ns']) != (response <= deadline))
            if available is not None and predicted.get('available_ns') is not None:
                row['AVAILABLE_error_s'] = (predicted['available_ns'] - available) / 1_000_000_000
            row.update(actual_response_s=response / 1_000_000_000 if response is not None else None,
                       predicted_response_s=predicted['response_ns'] / 1_000_000_000 if predicted.get('response_ns') is not None else None,
                       actual_AVAILABLE_s=available / 1_000_000_000 if available is not None else None,
                       predicted_AVAILABLE_s=predicted['available_ns'] / 1_000_000_000 if predicted.get('available_ns') is not None else None,
                       actual_issues=copy.deepcopy(actual.get('issues', [])))
            if all(row[k] is not None for k in ('queue_error_s', 'response_latency_error_s', 'AVAILABLE_error_s', 'on_time_disagreement')):
                row['status'] = 'POSTHOC_WHOLE_COHORT_PREDICTION_ERROR'
            actual_rows.append({'request_id': predicted['request_id'], 'task': actual['task'],
                                'priority': actual.get('priority'), 'scheduled_arrival_ns': arrival,
                                'deadline_ns': deadline, 'response_ns': response, 'available_ns': available,
                                'dispatch_ns': dispatch, 'route': actual.get('route', actual.get('backend'))})
        comparisons.append(row)
        if actual is None:
            actual_rows.append({'request_id': predicted['request_id'], 'task': predicted['task'],
                                'priority': predicted.get('priority'),
                                'scheduled_arrival_ns': predicted['scheduled_arrival_ns'],
                                'deadline_ns': predicted['deadline_ns'], 'response_ns': None,
                                'available_ns': None, 'dispatch_ns': None, 'route': None})
    summary = actual_deadline_summary(actual_rows, source, service_stop_ns=public['service_stop_ns'])
    predicted_summary = deadline_summary(prediction['requests'], service_stop_ns=public['service_stop_ns'], drain_stop_ns=public['drain_stop_ns'])
    observed_end = summary['actual_recorded_observation_end_s']
    observed_endpoint_in_prediction = observed_end is not None and observed_end * 1e9 <= public['observation_end_ns']
    predicted_observed_window = (deadline_summary(prediction['requests'], service_stop_ns=public['service_stop_ns'],
                                 drain_stop_ns=round(observed_end * 1e9)) if observed_endpoint_in_prediction else None)
    errors = {}
    for name in ('queue_error_s', 'response_latency_error_s', 'AVAILABLE_error_s'):
        values = [abs(q[name]) for q in comparisons if q[name] is not None]
        errors[name + '_mae'] = statistics.mean(values) if values else None
        errors[name + '_worst_abs'] = max(values) if values else None
        errors[name + '_eligible_requests'] = len(values)
    for name in ('P95_all_requested_response_s', 'P95_all_requested_response_lower_bound_s',
                 'total_tardiness_s', 'total_tardiness_lower_bound_s'):
        comparison_prediction = predicted_observed_window if 'lower_bound' in name and summary['uncompleted'] else predicted_summary
        a, b = comparison_prediction[name] if comparison_prediction is not None else None, summary[name]
        errors[name + '_error'] = a - b if a is not None and b is not None else None
    actual_intervals = [(q['dispatch_ns'], q['available_ns']) for q in actual_rows]
    overlap = None
    if all(a is not None and b is not None and a <= b for a, b in actual_intervals):
        overlap = sum(max(0, min(a[1], b[1], public['drain_stop_ns']) - max(a[0], b[0]))
                      for i, a in enumerate(actual_intervals) for b in actual_intervals[i + 1:])
    response_count_identified = summary['uncompleted'] == 0 or (
        summary['continuous_response_tracking_verified'] and observed_endpoint_in_prediction)
    deadline_count_identified = summary['uncompleted'] == 0 or (
        response_count_identified and observed_end is not None and
        all(q['deadline_ns'] <= observed_end * 1e9 for q in actual_rows if q.get('response_ns') is None))
    count_prediction = predicted_observed_window if predicted_observed_window is not None else predicted_summary
    return {'session_id': source['session_id'], 'cohort_id': source['cohort_id'],
            'role': 'POSTHOC_GROUPED_MODEL_DEVELOPMENT_NOT_FRESH_CONFIRMATION', 'per_request': comparisons,
            'actual': summary, 'predicted': predicted_summary, **errors,
            'predicted_at_actual_recorded_endpoint': predicted_observed_window,
            'actual_censor_endpoint_within_prediction_coverage': observed_endpoint_in_prediction,
            'planned_denominator_mismatch': len(actual_rows) != len(prediction['requests']),
            'on_time_count_error': count_prediction['on_time'] - summary['on_time'] if deadline_count_identified else None,
            'uncompleted_count_error': count_prediction['uncompleted'] - summary['uncompleted'] if response_count_identified else None,
            'observed_recorded_on_time_count_difference': count_prediction['on_time'] - summary['on_time'],
            'actual_response_count_identified': response_count_identified,
            'actual_deadline_count_identified': deadline_count_identified,
            'overlap_error_s': (prediction['metrics']['overlap_ns'] - overlap) / 1_000_000_000 if overlap is not None else None,
            'predictive_accuracy_PASS': None, 'existing_model_baseline': 'NOT_RESIMULATED_WITHIN_THIS_256_START_BUDGET'}


def selected_cv_context(cv, sessions):
    """Reuse frozen grouped splits and their selected combined fold models."""
    choice = cv.get('selection', {}).get('combined', {})
    candidate = next((c for c in cv.get('candidates', []) if c['candidate_index'] == choice.get('candidate_index')), None)
    models = {x['fold_id']: x['model'] for x in candidate['modes']['combined']['fold_models']} if candidate else {}
    roster = {s['session_id']: s for s in sessions}
    context = {}
    folds = cv.get('folds', {}).get('folds', [])
    for fold in folds:
        held, train = set(fold['heldout_session_ids']), set(fold['training_session_ids'])
        require(not (held & train) and held | train == set(roster), 'Registered CV fold roster/leakage')
        held_cohorts = {roster[sid]['cohort_id'] for sid in held}
        train_cohorts = {roster[sid]['cohort_id'] for sid in train}
        require(not (held_cohorts & train_cohorts), 'Whole cohort split across fold')
        for group in cv.get('folds', {}).get('groups', {}).values():
            require(not (set(group) & held and set(group) & train), 'Native/session identity split across fold')
        model = models.get(fold['fold_id'], {'status': 'UNAVAILABLE', 'reason': 'MISSING_REGISTERED_HELDOUT_FOLD_MODEL'})
        if model.get('model_sha256'):
            require(digest({k: v for k, v in model.items() if k != 'model_sha256'}) == model['model_sha256'],
                    'Heldout AP model content hash differs')
        require(set(model.get('training_sessions', [])) <= train and
                not (set(model.get('training_cohorts', [])) & held_cohorts), 'Heldout AP model trained on target cohort')
        for sid in held:
            require(sid not in context, 'Session held out more than once')
            context[sid] = {'fold_id': fold['fold_id'], 'training_ids': sorted(train),
                            'heldout_ids': sorted(held), 'thermal_model': model}
    return context, candidate


def exact_measured_policy(source, op):
    arm = source.get('arm')
    direct = {p: p for p in ('FIFO_SERIAL_CPU', 'FIFO_SERIAL_CG', 'FIFO_PAIR_CG', 'FIFO_WAIT_CG')}
    direct.update(op.get('measured_arm_policy_map', {}))
    candidates = [direct[arm]] if arm in direct else []
    for mapping in op.get('measured_protocol_mappings', []):
        fields = ('arm', 'public_route', 'public_order', 'public_declared_protocol')
        require('arm' in mapping and all(k in (*fields, 'policy') for k in mapping), 'Explicit public protocol mapping schema')
        if all(source.get(k) == mapping[k] for k in fields if k in mapping):
            candidates.append(mapping['policy'])
    candidates = sorted(set(candidates))
    if len(candidates) != 1:
        return None, 'UNKNOWN_OR_AMBIGUOUS_EXACT_PUBLIC_POLICY_DECLARATION'
    policy = candidates[0]
    if policy not in direct or policy not in ('FIFO_SERIAL_CPU', 'FIFO_SERIAL_CG', 'FIFO_PAIR_CG', 'FIFO_WAIT_CG'):
        return None, 'UNSUPPORTED_MEASURED_POLICY_CONTRACT'
    expected_protocol = 'CG_DC' if policy == 'FIFO_PAIR_CG' else 'SERIAL'
    if source.get('protocol') != expected_protocol:
        return None, 'PUBLIC_POLICY_PROTOCOL_MISMATCH'
    order = source.get('public_order')
    if order is not None and str(order).upper() not in ('FIFO', 'ARRIVAL', 'ORDINAL', 'PLANNED_FIFO'):
        return None, 'UNSUPPORTED_EXACT_PUBLIC_ORDER'
    route = source.get('public_route')
    if route in ('CPU', 'GPU') and route != ('CPU' if policy == 'FIFO_SERIAL_CPU' else 'GPU'):
        return None, 'PUBLIC_POLICY_ROUTE_MISMATCH'
    return policy, None


def cv_residual_bands(candidate, sessions):
    """Whole-session heldout residual summaries, never a confidence interval."""
    if not candidate:
        return {}
    import thermal_model
    sources = {s['session_id']: s for s in sessions}
    rows = {r['session_id']: r for r in candidate['modes']['combined']['rows']}
    by_domain = {}
    for p in candidate['modes']['combined']['predictions']:
        source = sources.get(p['session_id'])
        if source is None or p.get('status') != 'CONDITIONAL_AP_PREDICTION':
            continue
        targets = thermal_model._targets(source)
        if [q['t_s'] for q in targets] != p.get('t_s'):
            continue
        residuals = [q['ap_c'] - predicted for q, predicted in zip(targets, p.get('ap_c', [])) if _finite(predicted)]
        if not residuals:
            continue
        domain = p.get('activity_domain', rows.get(source['session_id'], {}).get('activity_domain'))
        by_domain.setdefault(domain, []).append({'session_id': source['session_id'], 'cohort_id': source['cohort_id'],
                                               'low': _quantile(residuals, .05), 'high': _quantile(residuals, .95)})
    result = {}
    for domain, values in by_domain.items():
        result[domain] = {'residual_low_c': _quantile([v['low'] for v in values], .05),
                          'residual_high_c': _quantile([v['high'] for v in values], .95),
                          'whole_sessions': len(values), 'whole_cohorts': len({v['cohort_id'] for v in values}),
                          'session_ids': [v['session_id'] for v in values],
                          'method': '5/95 quantiles of whole-session 5/95 actual-minus-heldout-prediction residual summaries',
                          'role': 'POSTHOC_SELECTED_CV_DESCRIPTIVE_RANGE', 'confidence_interval': False}
    return result


def heldout_validation_stage(op, out, sessions, cv, profile, config, journal, common_bindings, observer_consume):
    from timing_model import UnsupportedContext, build_timing_candidate
    import thermal_model
    if op.get('run_heldout_validation', True) is False:
        previous = read(pin(op['prior_heldout_validation_pin']))
        require(previous.get('dataset_sha256') == op['dataset_pin']['sha256'] and
                previous.get('thermal_cv_sha256') == op['thermal_cv_pin']['sha256'] and
                previous.get('timing_bank_overlay_sha256') == common_bindings['timing_bank_overlay_sha256'] and
                previous.get('effective_bank_map_sha256') == common_bindings['effective_bank_map_sha256'] and
                previous.get('timing_configuration') == config and previous.get('registered_sessions') == 69,
                'Reusable validation must bind the exact same original dataset, bank overlay, split artifact and timing configuration')
        report = {**previous, 'status': 'PINNED_PRIOR_VALIDATION_REUSED_NO_NEW_POLICY_START',
                  'prior_validation_pin': op['prior_heldout_validation_pin'],
                  'original_validation_START_consumed': previous['simulation_START_consumed'],
                  'simulation_START_consumed': 0, 'timing_model_builds': 0, 'reused': True}
        write_new(out / 'HELDOUT_VALIDATION.json', report)
        write_new(out / 'HELDOUT_LOOKUP_CACHE_REPORT.json', {'schema': VERSION, 'models': [], 'reused': True})
        _, candidate = selected_cv_context(cv, sessions)
        return report, [], cv_residual_bands(candidate, sessions)
    roster = op.get('heldout_validation_session_ids')
    require(isinstance(roster, list) and len(roster) == 69 and len(set(roster)) == 69,
            'Exact registered69 timing-qualified M8 validation roster required')
    by_id = {s['session_id']: s for s in sessions}
    require(set(roster) <= set(by_id), 'Heldout roster absent from dataset')
    context, candidate = selected_cv_context(cv, sessions)
    fold_ids = sorted({context[sid]['fold_id'] for sid in roster if sid in context})
    require(len(fold_ids) <= op['validation_timing_build_cap'] <= 29, 'Registered validation timing model-build cap')
    models, build_rows = {}, []
    for fold_id in fold_ids:
        selected = next(x for x in context.values() if x['fold_id'] == fold_id)
        models[fold_id] = build_timing_candidate([by_id[sid] for sid in selected['training_ids']], **config)
        install_lookup_cache(models[fold_id], 'heldout-fold-' + str(fold_id))
        build_rows.append({'fold_id': fold_id, 'training_session_ids': selected['training_ids'],
                           'heldout_session_ids': selected['heldout_ids'], 'timing_model_digest': models[fold_id].metadata['model_digest'],
                           'timing_metadata': models[fold_id].metadata, 'exclusion_ledger': models[fold_id].ledger})
    write_new(out / 'HELDOUT_TIMING_MODEL_BINDINGS.json', {'schema': VERSION, 'model_builds': len(models),
                'parameter_fits': 0, 'folds': build_rows, 'thermal_cv_sha256': op['thermal_cv_pin']['sha256'],
                'selection_uses_policy_gap': False, 'whole_cohort_folds': True})
    validations, forecast_rows, plan = [], [], []
    for sid in roster:
        source = by_id[sid]
        policy, reason = exact_measured_policy(source, op)
        if source.get('source_family') != 'm8' or not source.get('target_eligibility', {}).get('timing_fit'):
            reason = 'SOURCE_NOT_REGISTERED_TIMING_QUALIFIED_M8'
        if sid not in context:
            reason = 'MISSING_WHOLE_COHORT_CV_FOLD'
        if reason is not None:
            public = transform_public_template(public_template(source, dataset_sha256=op['dataset_pin']['sha256']))
            unknown_case = {'label': 'HELDOUT_' + sid, 'kind': 'WHOLE_COHORT_HELDOUT_VALIDATION',
                            'bank': public['bank'], 'policy': policy, 'seed': op.get('validation_seed', 0),
                            'template': public}
            validations.append({'session_id': sid, 'cohort_id': source.get('cohort_id'), 'status': 'UNVALIDATED',
                                'reason': reason, 'simulation_START_consumed': 0,
                                'case_status': case_status(unknown_case)})
            plan.append({'session_id': sid, 'policy': policy, 'status': 'UNKNOWN_NO_START', 'reason': reason})
            continue
        fold = context[sid]
        public = public_template(source, dataset_sha256=op['dataset_pin']['sha256'])
        public = transform_public_template(public)
        case = {'label': 'HELDOUT_' + sid, 'bank': public['bank'], 'policy': policy,
                'seed': op.get('validation_seed', 0), 'template': public,
                'kind': 'WHOLE_COHORT_HELDOUT_VALIDATION',
                'scenario_key': [public['public_base_sha256'], op.get('validation_seed', 0)]}
        bindings = {**common_bindings, 'role': 'WHOLE_COHORT_HELDOUT_VALIDATION',
                    'fold_id': fold['fold_id'], 'training_session_ids_sha256': digest(fold['training_ids']),
                    'timing_model_digest': models[fold['fold_id']].metadata['model_digest'],
                    'thermal_model_sha256': fold['thermal_model'].get('model_sha256'),
                    'thermal_artifact_sha256': op['thermal_cv_pin']['sha256']}
        targets = thermal_model._targets(source)
        times = [q['t_s'] for q in targets if 0 <= q['t_s'] <= public['observation_end_ns'] / 1_000_000_000]
        plan.append({'session_id': sid, 'policy': policy, 'fold_id': fold['fold_id'], 'status': 'PLANNED_ONE_START'})
        try:
            row = journal.run(case, bindings,
                    lambda start, case=case, source=source, fold=fold, times=times: predict_case(case,
                        models[fold['fold_id']], fold['thermal_model'], profile, op, start,
                        ap_query_times=times, validation_source=source, observer_consume=observer_consume))
            forecast_rows.append(row)
            validations.append({'session_id': sid, 'cohort_id': source['cohort_id'], 'fold_id': fold['fold_id'],
                                'status': 'POSTHOC_WHOLE_COHORT_MODEL_VALIDATION', 'identity': row['identity'],
                                'simulation_START_consumed': 1, 'validation': row['validation'],
                                'AP_validation': row['AP_validation'], 'uncertainty_flags': row['uncertainty_flags'],
                                'raw_path': row['raw_path'], 'raw_sha256': row['raw_sha256'],
                                'case_status': case_status(case, row=row)})
        except UnsupportedContext as exc:
            if op.get('case_failure_policy') != 'RECORD_UNSUPPORTED_CONTINUE_DISTINCT_CASES':
                raise
            validations.append({'session_id': sid, 'cohort_id': source['cohort_id'], 'fold_id': fold['fold_id'],
                                'status': 'UNVALIDATED_SIMULATION_FAIL', 'reason': str(exc),
                                'simulation_START_consumed': 1, 'automatic_retry': False,
                                'case_status': case_status(case, failure=journal.last_failure)})
    write_new(out / 'HELDOUT_PLAN.json', {'schema': VERSION, 'roster': roster, 'sessions': plan,
                                         'calls_upper_bound': 69, 'whole_cohort_folds': True})
    report = {'schema': VERSION, 'status': 'POSTHOC_GROUPED_VALIDATION_WITH_ALL_UNKNOWNS_RETAINED',
              'roster': roster, 'registered_sessions': 69, 'sessions': validations,
              'simulation_START_consumed': sum(v['simulation_START_consumed'] for v in validations),
              'timing_model_builds': len(models), 'parameter_fits': 0,
              'dataset_sha256': op['dataset_pin']['sha256'], 'thermal_cv_sha256': op['thermal_cv_pin']['sha256'],
              'timing_bank_overlay_sha256': common_bindings['timing_bank_overlay_sha256'],
              'effective_bank_map_sha256': common_bindings['effective_bank_map_sha256'],
              'timing_configuration': config,
              'thermal_source': 'selected_candidate_combined_registered_fold_models_only',
              'final_all_trained_AP_model_used_for_validation': False, 'fresh_confirmation': False,
              'predictive_accuracy_PASS': None, 'confidence_interval': None,
              'existing_model_baseline_extra_simulation': 0}
    write_new(out / 'HELDOUT_VALIDATION.json', report)
    write_new(out / 'HELDOUT_LOOKUP_CACHE_REPORT.json', {'schema': VERSION,
                                                       'models': [lookup_cache_report(m) for m in models.values()]})
    return report, forecast_rows, cv_residual_bands(candidate, sessions)


def effect_rows(rows):
    groups = {}
    for row in rows:
        if row.get('kind') == 'WHOLE_COHORT_HELDOUT_VALIDATION':
            continue
        intervention = row['intervention']
        key = row['comparison_group_id']
        groups.setdefault(key, {})[row['policy']] = row
    output = []
    for key, policies in groups.items():
        baseline = policies.get('FIFO_SERIAL_CG')
        for policy, row in policies.items():
            result = {'comparison_key': key, 'policy': policy, 'baseline': 'FIFO_SERIAL_CG',
                      'identity': row['identity'], 'baseline_identity': baseline.get('identity') if baseline else None,
                      'status': 'UNKNOWN_PAIRED_RESULT', 'on_time_change': None, 'conditional_J_change': None,
                      'AP_peak_change_c': None, 'AP_endpoint_change_c': None,
                      'no_policy_selection': True, 'measured_J': None}
            if baseline is not None and row.get('metrics') and baseline.get('metrics'):
                result.update(status='PAIRED_COUNTERFACTUAL_POINT_ESTIMATES',
                              on_time_change=row['metrics']['on_time'] - baseline['metrics']['on_time'])
                for source, target in (('historical_conditional_J', 'conditional_J_change'),
                                       ('AP_peak_c', 'AP_peak_change_c'), ('AP_endpoint_c', 'AP_endpoint_change_c')):
                    a, b = row.get(source), baseline.get(source)
                    if _finite(a) and _finite(b):
                        result[target] = a - b
            result['deadline_harm'] = result['on_time_change'] is not None and result['on_time_change'] < 0
            result['conditional_energy_proxy_harm'] = result['conditional_J_change'] is not None and result['conditional_J_change'] > 0
            result['AP_peak_harm'] = result['AP_peak_change_c'] is not None and result['AP_peak_change_c'] > 0
            a, b = row.get('work_scope', {}), baseline.get('work_scope', {}) if baseline else {}
            result['work_equivalence'] = {'same_planned': a.get('planned') == b.get('planned') if a and b else None,
                'same_responded_by_drain': a.get('responded_by_drain') == b.get('responded_by_drain') if a and b else None,
                'same_AVAILABLE_by_energy_end': a.get('AVAILABLE_by_energy_end') == b.get('AVAILABLE_by_energy_end') if a and b else None,
                'both_complete_by_drain': a.get('unfinished_by_drain') == 0 and b.get('unfinished_by_drain') == 0 if a and b else None}
            result['conditional_energy_decrease_is_efficiency_or_goal_PASS'] = False
            output.append(result)
    return output


def case_status(case, *, row=None, failure=None):
    public = case['template']
    comparison = row.get('comparison_group_id') if row else case.get('comparison_group_id', digest([
        public['public_scenario_sha256'], public['public_initial_context_sha256'], case['seed']]))
    return {'label': case['label'], 'kind': case['kind'], 'bank': case['bank'],
            'intervention': public['intervention'], 'policy': case['policy'], 'seed': case['seed'],
            'planned': len(public['requests']), 'source_session_id': public.get('source_session_id'),
            'validation_cohort_id': public.get('cohort_id'),
            'identity': row['identity'] if row else failure.get('identity') if failure else None,
            'row_identity': row['identity'] if row else None,
            'comparison_group_id': comparison,
            'source_public_template_sha256': public['public_base_sha256'],
            'public_scenario_sha256': public['public_scenario_sha256'],
            'public_initial_context_sha256': public['public_initial_context_sha256'],
            'status': row['status'] if row else 'FAIL_START_CONSUMED' if failure else 'UNKNOWN_NO_START',
            'simulation_START_consumed': 1 if row or failure else 0,
            'raw_path': row.get('raw_path') if row else failure.get('raw_path') if failure else None,
            'raw_sha256': row.get('raw_sha256') if row else failure.get('raw_sha256') if failure else None,
            'failure_ref': {'path': failure['terminal_path'], 'sha256': failure['terminal_sha256']} if failure else None,
            'receipt_identity': row['identity'] if row else failure.get('identity') if failure else None,
            'automatic_retry': False}


def _validate_operation(op):
    require(op['mode'] in ('FORECAST', 'FORECAST_TEST'), 'Forecast entry mode')
    require(_path_key(op['worker_lock_path']) == _path_key(WORKER_LOCK), 'Original G002 worker lock required')
    require(len(op['protected_pins']) >= 351, 'Protected351 union may not be reduced')
    names = {Path(s['path']).name for s in op['source_pins']}
    required = {'forecast_overlay_run.py', 'forecast_run.py', 'runtime_guard.py', 'timing_model.py', 'protocol_simulator.py',
                'thermal_model.py', 'historical_observer.py'}
    require(required <= names, 'Exact imported source closure pins required')
    require(sum(Path(s['path']).name == 'forecast_run.py' for s in op['source_pins']) == 1 and
            next(s for s in op['source_pins'] if Path(s['path']).name == 'forecast_run.py')['sha256'] == V2_SOURCE_SHA256,
            'Preserved byte-exact V2 source pin required as overlay provenance')
    require(op.get('new_environment') == 0 and op.get('HTTP') == 0 and op.get('device_commands') == 0,
            'Frozen orchestration hook contract changed')
    require(op.get('automatic_retry') is False, 'Automatic retry forbidden')
    if op['mode'] == 'FORECAST':
        require(op.get('orchestration_zero_is_not_simulation_accounting') is True,
                'Explicit nested simulator START accounting acknowledgment required')
        require(op.get('thermal_training_mode', 'combined') == 'combined', 'Novel forecasts use final combined AP model')
        logical_pins = ('dataset_pin', 'thermal_models_pin', 'thermal_cv_pin', 'historical_profile_pin',
                        'canonical_reservation_pin', 'forecast_allocation_pin', 'timing_bank_overlay_pin')
        registered = {(_path_key(s['path']), s['sha256']) for s in op['input_pins']}
        require(all((_path_key(op[name]['path']), op[name]['sha256']) in registered for name in logical_pins),
                'Forecast data/model/CV/reservation pins must all be registered inputs')
        require(all((_path_key(s['path']), s['sha256']) in registered for s in
                    (*op.get('extra_consumption_ledgers', []), *op.get('prior_forecast_ledger_pins', []))
                    if not s.get('missing')), 'External/prior forecast receipt pins must be registered inputs')
        if op.get('run_heldout_validation', True) is False:
            previous = op['prior_heldout_validation_pin']
            require((_path_key(previous['path']), previous['sha256']) in registered, 'Prior validation is not input-pinned')
    else:
        require('test_overlay_forecast.py' in names, 'Overlay-only test source must be exact-pinned')


def forecast_stage(op, out, operation_path):
    from timing_model import build_timing_candidate
    _validate_operation(op)
    dataset = read(pin(op['dataset_pin']))
    overlay = read(pin(op['timing_bank_overlay_pin']))
    dataset, overlay_proof = apply_timing_bank_overlay(dataset, overlay, op['dataset_pin'],
                                                       op['timing_bank_overlay_pin']['sha256'])
    write_new(out / 'TIMING_BANK_OVERLAY_PROOF.json', overlay_proof)
    sessions = dataset['sessions']
    thermal_artifact = read(pin(op['thermal_models_pin']))
    thermal = thermal_artifact['final_models'][op.get('thermal_training_mode', 'combined')]
    require(thermal.get('model_sha256') == op['thermal_model_sha256'] and
            digest({k: v for k, v in thermal.items() if k != 'model_sha256'}) == thermal.get('model_sha256'),
            'Final thermal model content/hash binding')
    require(set(thermal.get('training_sessions', [])) <= {s['session_id'] for s in sessions}, 'Thermal training roster outside dataset')
    require(op['thermal_dataset_sha256'] == op['dataset_pin']['sha256'], 'Thermal final-fit dataset binding')
    profile = read(pin(op['historical_profile_pin']))
    cv = read(pin(op['thermal_cv_pin']))
    config = copy.deepcopy(op.get('timing_configuration', {'family': 'combined', 'estimator': 'empirical',
                               'feature_mode': 'exact_public', 'seed': 0, 'strict': True,
                               'bank_mode': 'TASK_BINDING_TRANSFER'}))
    require(config.get('strict', True) is True and config.get('family', 'combined') == 'combined', 'Combined strict timing support required')
    require(op.get('timing_model_build_cap') == 1, 'Exactly one final-data novel-grid timing support build predeclared')
    model = build_timing_candidate(sessions, **config)
    install_lookup_cache(model, 'novel-final-data')
    bindings = {'dataset_sha256': op['dataset_pin']['sha256'], 'thermal_artifact_sha256': op['thermal_models_pin']['sha256'],
                'data_original_sha256': op['dataset_pin']['sha256'],
                'timing_bank_overlay_sha256': op['timing_bank_overlay_pin']['sha256'],
                'effective_bank_map_sha256': overlay_proof['effective_bank_map_sha256'],
                'effective_dataset_canonical_sha256': overlay_proof['effective_dataset_canonical_sha256'],
                'thermal_input_projection_sha256': overlay_proof['thermal_input_after_sha256'],
                'timing_bank_overlay_proof_sha256': sha(out / 'TIMING_BANK_OVERLAY_PROOF.json'),
                'thermal_model_sha256': thermal['model_sha256'], 'timing_configuration': config,
                'timing_model_digest': model.metadata['model_digest'],
                'historical_profile_sha256': op['historical_profile_pin']['sha256'],
                'source_pins_sha256': digest(op['source_pins'])}
    write_new(out / 'MODEL_BINDINGS.json', {'schema': VERSION, 'model_bindings': bindings,
                'timing_metadata': model.metadata, 'timing_exclusions': model.ledger,
                'timing_model_builds': 1, 'parameter_fits': 0, 'NN_training': 0,
                'all_source_sessions': len(sessions), 'role': 'POSTHOC_DEVELOPMENT_MODEL_COUNTERFACTUAL'})
    cases = build_cases(sessions, op)
    validation_upper = 69 if op.get('run_heldout_validation', True) else 0
    require(len(cases) + validation_upper <= op['budget']['operation_simulation_cap'], 'Validation plus novel calls exceed registered START cap')
    write_new(out / 'PUBLIC_CASES.json', {'schema': VERSION, 'cases': cases, 'calls': len(cases),
               'public_only': True, 'original_outcome_times_copied': False,
               'static_real_initial_context_allowed': True})
    guard = ForecastBudgetGuard(op, out, operation_path)
    journal = ForecastJournal(op, out, sha(operation_path), guard)
    observers = FixedObserverBudget(out, op['fixed_AP_observer_cap'], op['fixed_historical_energy_observer_cap'])
    require(op['fixed_AP_observer_cap'] >= len(cases) + validation_upper and
            op['fixed_historical_energy_observer_cap'] >= 2 * (len(cases) + validation_upper), 'Fixed observer query caps below planned upper bound')
    validation, validation_rows, bands = heldout_validation_stage(op, out, sessions, cv, profile,
                                    config, journal, bindings, observers.consume)
    write_new(out / 'HELDOUT_RESIDUAL_BANDS.json', {'schema': VERSION, 'bands': bands,
               'thermal_cv_sha256': op['thermal_cv_pin']['sha256'], 'confidence_interval': False,
               'role': 'DESCRIPTIVE_SELECTED_HELDOUT_RESIDUAL_RANGE_FOR_NEW_COUNTERFACTUALS'})
    rows, failures = list(validation_rows), []
    statuses = [v['case_status'] for v in validation['sessions']] if validation_upper else []
    from timing_model import UnsupportedContext
    for case in cases:
        try:
            row = journal.run(case, bindings, lambda start, case=case: predict_case(case, model, thermal, profile, op, start,
                                                     residual_bands=bands, observer_consume=observers.consume))
            rows.append(row)
            statuses.append(case_status(case, row=row))
        except UnsupportedContext as exc:
            if op.get('case_failure_policy') != 'RECORD_UNSUPPORTED_CONTINUE_DISTINCT_CASES':
                raise
            failures.append({'label': case['label'], 'error_type': type(exc).__name__, 'error': str(exc),
                             'consumed_START': True, 'automatic_retry': False})
            statuses.append(case_status(case, failure=journal.last_failure))
    receipts = _ledger_rows(journal.receipts)
    starts = [r for r in receipts if r.get('event') == 'START']
    fail_events = [r for r in receipts if r.get('event') == 'FAIL']
    for status in statuses:
        identity = status['identity']
        status['receipt_refs'] = {'path': str(journal.receipts), 'sha256': sha(journal.receipts), 'identity': identity} if identity else None
        terminal = _child(out, 'terminal/' + identity + '.json') if identity else None
        status['terminal_ref'] = {'path': str(terminal), 'sha256': sha(terminal)} if terminal is not None and terminal.exists() else None
    write_new(out / 'CASE_STATUS.json', {'schema': VERSION + '-CASE-STATUS', 'cases': statuses,
               'registered_case_roster': validation_upper + len(cases), 'heldout_roster': validation_upper, 'novel_roster': len(cases),
               'simulation_START_consumed': len(starts), 'no_unknown_or_failed_case_dropped': True})
    effects = effect_rows(rows)
    write_new(out / 'EFFECTS_AND_HARMS.json', {'schema': VERSION, 'effects': effects,
                'deadline_harms': [r for r in effects if r['deadline_harm']],
                'AP_peak_harms': [r for r in effects if r['AP_peak_harm']],
                'conditional_proxy_harms': [r for r in effects if r['conditional_energy_proxy_harm']],
                'failed_cases': failures, 'policy_selection': None, 'confidence_intervals': None,
                'independent_grouped_validation': False, 'measured_J': None})
    has_unknown = bool(fail_events) or any(s['simulation_START_consumed'] == 0 or 'HOLD' in s['status'] or 'FAIL' in s['status'] for s in statuses)
    result = {'schema': VERSION, 'status': 'COUNTERFACTUAL_GRID_COMPLETE_WITH_UNKNOWNS' if has_unknown else 'COUNTERFACTUAL_GRID_COMPLETE_UNVALIDATED',
              'planned_schedule_calls_upper_bound': validation_upper + len(cases), 'heldout_validation_roster': validation_upper,
              'novel_grid_calls': len(cases), 'simulation_START_consumed': len(starts),
              'new_simulator_environments_consumed': len(starts), 'COMPLETE': len(rows), 'FAIL': len(fail_events),
              'complete_artifacts_are_not_predictive_or_physical_PASS': True,
              'unqualified_or_partial_case_statuses_retained': has_unknown,
              'all_failed_STARTs_remain_consumed': True, 'automatic_retry': False,
              'root_orchestration_hook_new_environment': 0,
              'scientific_environment_accounting_ledger': str(journal.receipts),
              'global_START_after': CANONICAL_START + guard.extra_global + guard.prior_global + len(starts),
              'global_actual_plus_reserved': op['budget']['global_registered_total'], 'global_cap': GLOBAL_CAP,
              'a24_shared_START_after': A24_CANONICAL_START + guard.prior_a24 + len(starts),
              'a24_shared_cap': A24_POOL_CAP, 'shared_forecast_cap': SHARED_FORECAST_CAP,
              'timing_model_builds': 1 + validation['timing_model_builds'],
              'novel_timing_model_builds': 1, 'validation_timing_model_builds': validation['timing_model_builds'],
              'fixed_observer_queries': observers.used, 'fixed_observer_caps': observers.caps,
              'parameter_fits': 0, 'NN_training': 0, 'device_calls': 0, 'HTTP': 0,
              'RL_connected': False, 'new_RL_performance_claim': False, 'policy_selection': None,
              'measured_J': None, 'predictive_accuracy_PASS': None, 'physical_goal_pass': False,
              'model_bindings_sha256': sha(out / 'MODEL_BINDINGS.json'),
              'public_cases_sha256': sha(out / 'PUBLIC_CASES.json'),
              'case_status_sha256': sha(out / 'CASE_STATUS.json'),
              'heldout_validation_sha256': sha(out / 'HELDOUT_VALIDATION.json'),
              'receipt_ledger_sha256': sha(journal.receipts) if journal.receipts.exists() else None,
              'row_ledger_sha256': sha(journal.rows) if journal.rows.exists() else None,
              'seed_semantics': 'Paired policies share the same public-base/ordinal/task/seed potential; estimator median can produce identical seed outputs, never independent confidence replicates.'}
    write_new(out / 'FORECAST_RESULT.json', result)
    write_new(out / 'LOOKUP_CACHE_REPORT.json', {'schema': VERSION, 'novel': lookup_cache_report(model),
                                               'heldout_report_sha256': sha(out / 'HELDOUT_LOOKUP_CACHE_REPORT.json')})
    # Wrapper COMPLETE remains frozen. This explicit terminal is authoritative
    # about nested simulation consumption and prevents interpreting top0 as free.
    write_new(out / 'FORECAST_COMPLETE.json', {**result, 'completed_utc': now(),
                'forecast_result_sha256': sha(out / 'FORECAST_RESULT.json'),
                'effects_sha256': sha(out / 'EFFECTS_AND_HARMS.json')})
    return result


def description():
    return {'schema': VERSION, 'modes': ['--describe', '--sample-input', '--operation REGISTERED_JSON'],
            'default_grid': {'banks': ['C252', 'L64', 'M128'], 'arrivals': ARRIVAL_MODES,
                             'deadlines': DEADLINE_MODES, 'policies': DEFAULT_RULES, 'seeds': [0, 1],
                             'schedule_STARTs': 180, 'shared_cap': 256},
            'default_validation': {'whole_cohort_sessions': 69, 'shared_thermal_CV_folds': True,
                                   'validation_plus_novel_START_upper_bound': 249,
                                   'final_AP_model_used_for_heldout_validation': False},
            'operation_schema': 'A24-local-model-improvement-operation-v1',
            'required_inputs': ['exact source/input/protected pins', 'canonical_reservation_pin',
                                'dataset_pin', 'thermal_models_pin', 'thermal_model_sha256',
                                'thermal_dataset_sha256', 'historical_profile_pin', 'templates',
                                'extra_consumption_ledgers', 'prior_forecast_ledger_pins', 'budget',
                                'forecast_allocation_pin', 'thermal_cv_pin', 'heldout_validation_session_ids',
                                'timing_bank_overlay_pin',
                                'validation_timing_build_cap', 'fixed_AP_observer_cap', 'fixed_historical_energy_observer_cap'],
            'bank_overlay': {'schema': OVERLAY_VERSION, 'session_count': 8, 'only_changed_leaf': 'session.bank',
                             'original_dataset_sha256': ORIGINAL_DATASET_SHA256, 'new_AP_fit': 0,
                             'preserved_V2_source_sha256': V2_SOURCE_SHA256},
            'future_custom_only': 'Set arrival_modes=[] and custom_cases=[...]. Reuse the exact same pinned prior69 validation with run_heldout_validation=False/prior_heldout_validation_pin; all prior forecast STARTs count against shared256.',
            'novel_predictions': 'Arbitrary registered arrivals/priorities/deadlines/C-D task and public model/input mappings; unknown support stays flagged.',
            'no_execution_in_describe_or_sample': True, 'RL': 'not connected; no retraining or claimed new RL result',
            'accounting': 'Every new discrete-event schedule START, including FAIL, consumes one environment. Frozen wrapper top0 is orchestration only.'}


def sample_input():
    return {'label': 'CUSTOM_PUBLIC_EXAMPLE', 'reference_bank': 'M128', 'bank': 'M128_CUSTOM',
            'policy': 'ATC', 'seed': 0, 'requests': [
                {'request_id': 'cf-c-00000', 'ordinal': 0, 'task': 'C', 'priority': 'U', 'group': 0,
                 'scheduled_arrival_s': 35., 'deadline_s': 35.8,
                 'input_sha256': 'REPLACE_WITH_REGISTERED_PUBLIC_INPUT_SHA256',
                 'tensor_sha256': 'REPLACE_WITH_REGISTERED_PUBLIC_TENSOR_SHA256'},
                {'request_id': 'cf-d-00001', 'ordinal': 1, 'task': 'D', 'priority': 'N', 'group': 0,
                 'scheduled_arrival_s': 35.1, 'deadline_s': 37.1,
                 'input_sha256': 'REPLACE_WITH_REGISTERED_PUBLIC_INPUT_SHA256',
                 'tensor_sha256': 'REPLACE_WITH_REGISTERED_PUBLIC_TENSOR_SHA256'}],
            'note': 'This is an input example, not an executable authorization. Register exact input/model/policy/source pins and remaining START allocation first.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--operation')
    group.add_argument('--describe', action='store_true')
    group.add_argument('--sample-input', action='store_true')
    args = parser.parse_args()
    if args.describe or args.sample_input:
        print(canonical(description() if args.describe else sample_input()))
        return
    with operation(args.operation, __file__) as (op, out):
        _validate_operation(op)
        if op['mode'] == 'FORECAST_TEST':
            import io
            import unittest
            suite = unittest.TestLoader().discover(str(WORK), pattern='test_overlay_forecast.py')
            stream = io.StringIO()
            tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            write_new(out / 'FORECAST_TEST_RESULT.json', {'status': 'PASS' if tests.wasSuccessful() else 'FAIL',
                        'testsRun': tests.testsRun, 'output': stream.getvalue(),
                        'failures': [(str(t), e) for t, e in tests.failures], 'errors': [(str(t), e) for t, e in tests.errors],
                        'real_simulator_START': 0, 'raw_archive_access': 0, 'fit': 0, 'NN': 0})
            require(tests.wasSuccessful(), 'Registered forecast source tests failed; preserve namespace, no retry')
        else:
            forecast_stage(op, out, args.operation)
    print(canonical({'status': 'COMPLETE', 'mode': op['mode'], 'output': str(out)}))


if __name__ == '__main__':
    main()
