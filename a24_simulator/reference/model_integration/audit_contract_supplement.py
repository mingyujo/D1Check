"""Saved-only forecast contract supplement. SOURCE ONLY until registration.

No simulator/timing builder, AP prediction/replay, fitting, neural training,
ZIP/archive, device or network API is imported or invoked. This reads exact
completed saved artifacts. Gzip is a saved JSON transport, opened only inside
the registered audit after producer COMPLETE verification. Unknown controller
implementation and unsupported WAIT schema remain explicit unknowns.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
import os
from pathlib import Path

from runtime_guard import (canonical, operation as run_operation, pin, read,
                           require, sha, write_new)

VERSION = 'A24-SAVED-CONTRACT-SUPPLEMENT-v1'
WORK = Path(__file__).resolve().parent
ORIGINAL_LOCK = WORK.parent.parent / 'outputs/A24-INTEGRATED-SIM-20261016-G002/worker.lock'
GLOBAL_CAP, GLOBAL_REGISTERED, CANONICAL_START = 137712, 119750, 26454
A24_CAP, A24_CANONICAL, SHARED_CAP = 2048, 1695, 256
LOGICAL_PINS = ('forecast_operation_pin', 'forecast_runtime_complete_pin', 'forecast_complete_pin',
                'forecast_result_pin', 'case_status_pin', 'forecast_rows_pin', 'forecast_receipts_pin',
                'heldout_timing_model_bindings_pin', 'thermal_cv_pin', 'thermal_selection_pin',
                'session_metadata_pin', 'source_policy_contract_pin', 'overlay_proof_pin',
                'canonical_reservation_pin', 'forecast_allocation_pin')
QUEUE_FIELDS = {'request_id', 'ordinal', 'task', 'priority', 'group', 'scheduled_arrival_ns', 'queue_entry_ns', 'deadline_ns'}
OWNER_FIELDS = {'request_id', 'task', 'route', 'dispatch_ns', 'reservation_id', 'protocol'}


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def path_key(value):
    return os.path.normcase(os.path.abspath(value)).replace('\\', '/').rstrip('/')


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def json_lines(path):
    with Path(path).open(encoding='utf-8-sig') as source:
        return [json.loads(line) for line in source if line.strip()]


class Checks:
    def __init__(self):
        self.count, self.failed, self.failures = 0, 0, []

    def check(self, ok, label, context=None):
        self.count += 1
        if not ok:
            self.failed += 1
            if len(self.failures) < 1000:
                self.failures.append({'check': label, 'context': context})
        return bool(ok)

    def equal(self, actual, expected, label, context=None):
        return self.check(actual == expected, label, context)


class SavedArtifacts:
    """Completion-map authorization plus exact pin, containment and byte caps."""
    def __init__(self, operation_pin, complete_pin):
        self.operation_pin, self.complete_pin = operation_pin, complete_pin
        self.operation = read(pin(operation_pin))
        self.complete = read(pin(complete_pin))
        self.root = Path(complete_pin['path']).resolve().parent
        require(self.root == Path(self.operation['output_dir']).resolve(), 'Forecast completed namespace differs')
        require(self.complete.get('operation_sha256') == operation_pin['sha256'], 'Forecast outer COMPLETE operation SHA differs')
        require(not (self.root / 'FAILURE.json').exists(), 'A failed producer namespace is not a completed audit input')
        self.pins, self.expanded = {}, 0
        for relative, spec in self.complete['outputs'].items():
            target = self.root / relative
            require(target.resolve().is_relative_to(self.root), 'Completion member escapes forecast namespace')
            self.pins[path_key(target)] = {'path': str(target), **spec}

    def bound(self, target, expected_sha=None):
        target = Path(target)
        target = target if target.is_absolute() else self.root / target
        require(target.resolve().is_relative_to(self.root), 'Saved reference escapes forecast namespace')
        spec = self.pins.get(path_key(target))
        require(spec is not None, 'Saved reference absent from exact completion map: ' + str(target))
        if expected_sha is not None:
            require(spec['sha256'] == expected_sha, 'Ledger reference SHA differs from producer COMPLETE')
        for ancestor in (target, *target.parents):
            require(not ancestor.is_symlink() and not (getattr(ancestor.stat(), 'st_file_attributes', 0) & 0x400), 'Saved reference has reparse/symlink ancestor')
            if ancestor.resolve() == self.root:
                break
        return pin(spec)

    def object(self, target, expected_sha=None):
        return read(self.bound(target, expected_sha))

    def raw(self, target, expected_sha, per_file_cap, total_cap):
        with gzip.open(self.bound(target, expected_sha), 'rb') as source:
            payload = source.read(per_file_cap + 1)
        require(len(payload) <= per_file_cap, 'Saved raw expanded per-file cap exceeded')
        self.expanded += len(payload)
        require(self.expanded <= total_cap, 'Saved raw expanded total cap exceeded')
        return json.loads(payload.decode('utf-8-sig'))


def selected_fold_context(cv, selection, metadata, timing_bindings, dataset_sha, checks):
    """No model evaluation: only exact selected-fold identity/training evidence."""
    sessions = {s['session_id']: s for s in metadata['sessions']}
    checks.check(len(sessions) == len(metadata['sessions']), 'Unique metadata session roster')
    checks.equal(metadata['dataset_sha256'], dataset_sha, 'Session metadata original dataset binding')
    checks.equal(selection['dataset_sha256'], dataset_sha, 'Thermal selection original dataset binding')
    checks.equal(selection['selection'], cv['selection'], 'Exact saved thermal selection')
    chosen = cv['selection']['combined']['candidate_index']
    candidates = [c for c in cv['candidates'] if c['candidate_index'] == chosen]
    require(len(candidates) == 1, 'Selected combined CV candidate absent or duplicate')
    fold_models = candidates[0]['modes']['combined']['fold_models']
    models = {m['fold_id']: m['model'] for m in fold_models}
    checks.check(len(models) == len(fold_models), 'Unique selected combined fold models')
    timing = {f['fold_id']: f for f in timing_bindings['folds']}
    checks.check(len(timing) == len(timing_bindings['folds']), 'Unique heldout timing fold bindings')
    context = {}
    for fold in cv['folds']['folds']:
        held, train = set(fold['heldout_session_ids']), set(fold['training_session_ids'])
        checks.check(not held & train and held | train == set(sessions), 'Whole CV session partition', fold['fold_id'])
        require(held | train <= set(sessions), 'CV session absent from pinned metadata')
        held_cohorts = {sessions[sid]['cohort_id'] for sid in held}
        train_cohorts = {sessions[sid]['cohort_id'] for sid in train}
        checks.check(not held_cohorts & train_cohorts, 'Whole cohort train/heldout disjointness', fold['fold_id'])
        for group in cv['folds'].get('groups', {}).values():
            checks.check(not (set(group) & held and set(group) & train), 'Native/group train/heldout disjointness', fold['fold_id'])
        model = models.get(fold['fold_id'], {'status': 'UNAVAILABLE', 'reason': 'MISSING_REGISTERED_HELDOUT_FOLD_MODEL'})
        if model.get('model_sha256') is not None:
            checks.equal(digest({k: v for k, v in model.items() if k != 'model_sha256'}), model['model_sha256'], 'Selected fold internal model hash', fold['fold_id'])
        trained = model.get('training_sessions', [])
        trained_cohorts = set(model.get('training_cohorts', []))
        checks.check(len(trained) == len(set(trained)) and set(trained) <= train and not trained_cohorts & held_cohorts,
                     'Selected AP model training excludes heldout IDs/cohorts', fold['fold_id'])
        checks.check(trained_cohorts <= train_cohorts, 'AP training cohorts within selected fold', fold['fold_id'])
        if trained:
            checks.equal(trained_cohorts, {sessions[sid]['cohort_id'] for sid in trained}, 'AP training cohort roster derived from training IDs', fold['fold_id'])
        if fold['fold_id'] in timing:
            saved = timing[fold['fold_id']]
            checks.equal(saved['training_session_ids'], sorted(train), 'Timing support uses matching AP fold training roster', fold['fold_id'])
            checks.equal(saved['heldout_session_ids'], sorted(held), 'Timing support uses matching AP fold heldout roster', fold['fold_id'])
        for sid in held:
            checks.check(sid not in context, 'Session held out once', sid)
            context[sid] = {'fold_id': fold['fold_id'], 'model_sha256': model.get('model_sha256'),
                            'model_status': model.get('status'), 'training_ids_sha256': digest(sorted(train)),
                            'training_sessions': sorted(set(trained)), 'training_cohorts': sorted(trained_cohorts),
                            'heldout_cohorts': sorted(held_cohorts),
                            'selected_model_record_present': fold['fold_id'] in models,
                            'timing_binding_present': fold['fold_id'] in timing}
    checks.equal(set(context), set(sessions), 'Every metadata session has one heldout fold')
    return context, sessions


def check_heldout_model(case, row, raw, context, forecast_operation, checks, manifest=None):
    sid = case['source_session_id']
    require(sid in context, 'Heldout case has no selected-fold context')
    expected = context[sid]
    checks.check(expected['timing_binding_present'], 'Heldout selected timing fold binding exists', sid)
    if manifest is None and row is not None:
        manifest = row['manifest']
    if manifest is not None:
        bindings = manifest['model_bindings']
        checks.equal(bindings.get('fold_id'), expected['fold_id'], 'START bound selected heldout fold', sid)
        checks.equal(bindings.get('training_session_ids_sha256'), expected['training_ids_sha256'], 'START training-ID binding', sid)
        checks.equal(bindings.get('thermal_artifact_sha256'), forecast_operation['thermal_cv_pin']['sha256'], 'START heldout uses CV artifact, never final artifact', sid)
        checks.equal(bindings.get('thermal_model_sha256'), expected['model_sha256'], 'START exact selected combined fold model', sid)
    if row is None or raw is None:
        return {'status': 'EXPECTED_FOLD_CHECKED_NO_SUCCESSFUL_RAW', 'fold_id': expected['fold_id'],
                'expected_AP_model_sha256': expected['model_sha256'], 'AP_model_status': expected['model_status']}
    bindings = row['manifest']['model_bindings']
    checks.equal(bindings.get('fold_id'), expected['fold_id'], 'Raw bound selected heldout fold', sid)
    checks.equal(bindings.get('training_session_ids_sha256'), expected['training_ids_sha256'], 'Raw timing/AP training-ID binding', sid)
    checks.equal(bindings.get('thermal_artifact_sha256'), forecast_operation['thermal_cv_pin']['sha256'], 'Heldout uses CV artifact, never final artifact', sid)
    checks.equal(bindings.get('thermal_model_sha256'), expected['model_sha256'], 'Manifest uses exact selected combined fold model', sid)
    checks.equal(row.get('AP_model_sha256'), expected['model_sha256'], 'Row uses exact selected fold model', sid)
    checks.equal(raw['AP_prediction'].get('model_sha256'), expected['model_sha256'], 'Raw uses exact selected fold model', sid)
    if expected['model_sha256'] is None:
        checks.check(raw['AP_prediction'].get('status') == 'UNKNOWN' and all(v is None for v in raw['AP_prediction'].get('ap_c', [])),
                     'Unavailable selected fold stays UNKNOWN/null', sid)
    return {'status': 'EXACT_SELECTED_FOLD_BINDINGS_CHECKED', 'fold_id': expected['fold_id'],
            'expected_AP_model_sha256': expected['model_sha256'], 'AP_model_status': expected['model_status'],
            'training_cohorts_disjoint': not bool(set(expected['training_cohorts']) & set(expected['heldout_cohorts']))}


def ledger_summary(rows):
    """Cost is every START row, including duplicate/unresolved legacy rows."""
    counts = Counter(r.get('event') for r in rows)
    starts = [r for r in rows if r.get('event') == 'START']
    ids = Counter(r.get('identity') for r in starts)
    terminals = Counter(r.get('identity') for r in rows if r.get('event') in ('COMPLETE', 'FAIL'))
    return {'rows': len(rows), 'START': counts['START'], 'COMPLETE': counts['COMPLETE'], 'FAIL': counts['FAIL'],
            'duplicate_START_identities': {str(k): n for k, n in ids.items() if n > 1},
            'unresolved_START_rows': sum(max(0, n - terminals[k]) for k, n in ids.items()),
            'excess_terminal_rows': sum(max(0, n - ids[k]) for k, n in terminals.items()),
            'cost_unit': 'ALL_START_ROWS_NOT_UNIQUE_SUCCESSFUL_OR_RESOLVED_IDENTITIES'}


def validate_budget_config(config):
    for name in ('global_cap', 'global_registered_total', 'a24_pool_cap', 'shared_forecast_cap',
                 'allocated_from_existing_a24', 'a24_remaining_before_allocation', 'additional_global_reservation',
                 'operation_simulation_cap', 'reserved_global_excluding_this', 'reserved_a24_excluding_this'):
        require(type(config.get(name)) is int and config[name] >= 0, 'Nonnegative exact budget integer required: ' + name)
    require(config['global_cap'] == GLOBAL_CAP and config['global_registered_total'] == GLOBAL_REGISTERED and
            config['a24_pool_cap'] == A24_CAP and config['shared_forecast_cap'] == SHARED_CAP and
            config['allocated_from_existing_a24'] == SHARED_CAP and config['a24_remaining_before_allocation'] == 353 and
            config['additional_global_reservation'] == 0, 'Original global/A24/shared reservation contract differs')
    cap = config['operation_simulation_cap']
    require(0 < cap <= SHARED_CAP, 'Positive operation cap within shared256 allocation required')
    return cap


def independent_budget(config, *, canonical, canonical_a24, extra, prior, prior_shared, index):
    cap = validate_budget_config(config)
    require(canonical == CANONICAL_START and canonical_a24 == A24_CANONICAL, 'Canonical fixed original totals differ')
    require(type(index) is int and 0 <= index < cap, 'Operation START cap exhausted')
    global_after = canonical + extra + prior + index + 1
    reserved = config['reserved_global_excluding_this'] + cap - index - 1
    a24_after = canonical_a24 + prior + index + 1
    a24_reserved = config['reserved_a24_excluding_this'] + cap - index - 1
    shared_after = prior_shared + index + 1
    require(global_after + reserved == GLOBAL_REGISTERED and global_after + reserved <= GLOBAL_CAP,
            'Global actual plus reserved conservation/cap differs')
    require(a24_after + a24_reserved == A24_CAP and prior + index + 1 <= 353 and shared_after <= SHARED_CAP,
            'A24 actual plus reserved/shared allocation conservation differs')
    return {'canonical_START': canonical, 'external_new_START': extra, 'prior_A24_forecast_START': prior,
            'this_forecast_START_before': index, 'this_forecast_START_after': index + 1,
            'operation_simulation_cap': cap, 'global_START_after': global_after,
            'global_reserved_remaining_after': reserved, 'global_actual_plus_reserved': global_after + reserved,
            'global_cap': GLOBAL_CAP, 'a24_shared_START_after': a24_after, 'a24_reserved_remaining_after': a24_reserved,
            'a24_shared_cap': A24_CAP, 'shared_forecast_START_after': shared_after, 'shared_forecast_cap': SHARED_CAP,
            'FAIL_is_consumed': True}


def receipt_index(receipts, rows, checks):
    groups = defaultdict(list)
    for position, receipt in enumerate(receipts):
        groups[receipt['identity']].append((position, receipt))
    by_row = {row['identity']: row for row in rows}
    checks.equal(len(by_row), len(rows), 'Unique saved success rows')
    indexed = {}
    for identity, events in groups.items():
        starts = [(p, r) for p, r in events if r['event'] == 'START']
        terminals = [(p, r) for p, r in events if r['event'] in ('COMPLETE', 'FAIL')]
        prepared = [(p, r) for p, r in events if r['event'] == 'PREPARED']
        checks.check(len(starts) == len(terminals) == 1, 'One START and terminal per forecast identity', identity)
        if len(starts) != 1 or len(terminals) != 1:
            continue
        checks.check(starts[0][0] < terminals[0][0], 'START precedes terminal', identity)
        terminal = terminals[0][1]
        if terminal['event'] == 'COMPLETE':
            checks.check(len(prepared) == 1 and identity in by_row, 'Completed forecast has one PREPARED event and one row', identity)
        else:
            checks.check(len(prepared) <= 1 and identity not in by_row, 'Failed forecast is not a successful row', identity)
        if prepared:
            checks.check(starts[0][0] < prepared[0][0] < terminals[0][0], 'PREPARED event lies between START and terminal', identity)
            for stem in ('raw', 'prepared'):
                for suffix in ('path', 'sha256'):
                    key = stem + '_' + suffix
                    checks.equal(prepared[0][1].get(key), terminal.get(key), 'PREPARED event/terminal reference ' + key, identity)
        if identity in by_row:
            for key in ('raw_path', 'raw_sha256', 'prepared_path', 'prepared_sha256'):
                checks.equal(by_row[identity].get(key), terminal.get(key), 'Row/terminal reference ' + key, identity)
        indexed[identity] = {'start': starts[0][1], 'terminal': terminal,
                             'prepared': prepared[0][1] if len(prepared) == 1 else None,
                             'row': by_row.get(identity)}
    checks.equal(set(by_row), {identity for identity, item in indexed.items() if item['terminal']['event'] == 'COMPLETE'},
                 'Success rows exactly match COMPLETE identities')
    return indexed


def terminal_body_check(item, body, operation_sha, checks):
    terminal, start = item['terminal'], item['start']
    identity = start['identity']
    checks.equal(body.get('identity'), identity, 'Terminal body identity', identity)
    checks.equal(body.get('operation_sha256'), operation_sha, 'Terminal body operation', identity)
    preserved = terminal['event'] == 'FAIL' and terminal.get('existing_terminal_preserved') is True and body.get('event') == 'COMPLETE'
    checks.check(body.get('event') == terminal['event'] or preserved, 'Terminal event or explicitly preserved pre-existing COMPLETE', identity)
    for key in ('raw_path', 'raw_sha256', 'prepared_path', 'prepared_sha256'):
        if key in terminal:
            checks.equal(body.get(key), terminal[key], 'Terminal body/receipt reference ' + key, identity)
    if terminal['event'] == 'COMPLETE':
        checks.equal(body.get('row_sha256'), digest(item['row']), 'Terminal canonical row SHA', identity)
    return 'EXPLICIT_PRESERVED_COMPLETE_AFTER_FAILED_FINALIZATION' if preserved else 'TERMINAL_EVENT_AND_REFERENCES_CHECKED'


def ready_order_key(row):
    return (row['deadline_ns'], row['scheduled_arrival_ns'], row['ordinal'], row['request_id'])


def check_policy_bindings(raw, row, start, checks):
    identity = row['identity']
    manifest = row['manifest']
    checks.equal(raw['forecast_manifest'], manifest, 'Raw/row manifest', identity)
    checks.equal(manifest, start['manifest'], 'Row/START manifest', identity)
    for value in (manifest['policy'], raw['forecast_manifest']['policy'], raw['simulation']['policy']):
        checks.equal(value, row['policy'], 'Saved simulation policy equals declared policy', identity)
    compact = raw['compact']
    for key, value in compact.items():
        checks.equal(row.get(key), value, 'Raw compact/row ' + key, identity)
    for container in (compact, compact.get('source_policy_contract', {}), raw.get('qualification', {}).get('source_policy_contract', {})):
        if 'policy' in container:
            checks.equal(container['policy'], row['policy'], 'Stored compact contract policy', identity)
    meta = row.get('source_policy_contract')
    checks.equal(meta, compact.get('source_policy_contract'), 'Compact policy contract metadata', identity)
    checks.equal(meta, raw.get('qualification', {}).get('source_policy_contract'), 'Qualification policy contract metadata', identity)
    if meta:
        checks.check(meta.get('EXACT_INSTALLED') is False and meta.get('SCHEDULER_BODY_NOT_VERIFIED') is True,
                     'Installed scheduler uncertainty remains explicit', identity)
    return {'status': 'MANIFEST_SIMULATION_AND_STORED_COMPACT_POLICY_CHECKED',
            'compact_top_policy_field': 'CHECKED' if 'policy' in compact else 'NOT_STORED; row/manifest/simulation and available nested policy checked'}


def check_ORDER_trace(raw, checks):
    public, simulation = raw['public_input'], raw['simulation']
    rows, end = simulation['requests'], public['observation_end_ns']
    by_id = {r['request_id']: r for r in rows}
    checks.equal(simulation['policy'], 'EDD', 'ORDER uses EDD')
    checks.equal(simulation.get('mode'), 'GENERALIZED_ROLLING_COUNTERFACTUAL_ATOMIC_RESERVATIONS', 'ORDER uses frozen atomic/global-serial executor')
    reserved, decision_ids = [], []
    for decision in simulation.get('decisions', []):
        state, action, at = decision['public_state'], decision['action'], decision['time_ns']
        checks.equal(digest(state), decision['public_state_sha256'], 'ORDER predecision state hash', at)
        checks.equal(state['now_ns'], at, 'ORDER predecision clock', at)
        checks.equal(state['owners'], [], 'ORDER global SERIAL waits for every AVAILABLE', at)
        checks.check(not decision.get('applied_control') and action.get('kind') == 'DISPATCH', 'ORDER has no WAIT control', at)
        queue = state.get('queue', [])
        checks.check(bool(queue) and all(set(q) <= QUEUE_FIELDS and q['queue_entry_ns'] <= at for q in queue), 'ORDER queue is ready/public only', at)
        ready_ids = {q['request_id'] for q in rows if q['queue_entry_ns'] <= at and
                     (q.get('reserved_at_ns') is None or q['reserved_at_ns'] >= at)}
        checks.equal({q['request_id'] for q in queue}, ready_ids, 'ORDER snapshot contains every currently ready unreserved request', at)
        if not queue:
            continue
        head = min(queue, key=ready_order_key)
        checks.equal(action.get('request_id'), head['request_id'], 'ORDER deterministic earliest deadline ready head', at)
        checks.equal(action.get('route'), 'GPU' if head['task'] == 'C' else 'CPU', 'ORDER fixed C_GPU D_CPU action', at)
        checks.check(action.get('pair_with') is None, 'ORDER dispatch is globally serial, no companion', at)
        if action.get('request_id') in by_id and by_id[action['request_id']].get('dispatch_ns') is not None:
            request = by_id[action['request_id']]
            checks.equal(request.get('reserved_at_ns'), at, 'ORDER dispatch reservation matches predecision clock', request['request_id'])
            decision_ids.append(request['request_id'])
    for request in rows:
        if request.get('dispatch_ns') is None:
            continue
        rid, dispatch = request['request_id'], request['dispatch_ns']
        checks.equal(request['route'], 'GPU' if request['task'] == 'C' else 'CPU', 'ORDER fixed request route', rid)
        checks.equal(request.get('protocol'), 'SERIAL', 'ORDER whole-vector SERIAL draw', rid)
        release = request.get('available_ns')
        reserved.append((request['reserved_at_ns'], release if release is not None else end, rid))
        offsets = request.get('timing', {}).get('offsets_ns')
        if offsets is not None:
            for boundary in ('execution_start', 'output_ready', 'persist_complete', 'worker_release'):
                actual = request.get(boundary + '_ns')
                if actual is not None:
                    checks.equal(actual, dispatch + offsets[boundary], 'ORDER atomic phase offset', [rid, boundary])
            if release is not None:
                checks.equal(release, dispatch + offsets['lane_available'], 'ORDER atomic AVAILABLE offset', rid)
        else:
            checks.check(False, 'ORDER atomic offsets metadata absent', rid)
    checks.equal(Counter(decision_ids), Counter(rid for _, _, rid in reserved), 'ORDER every dispatch has exactly one ready-head decision')
    for previous, current in zip(sorted(reserved), sorted(reserved)[1:]):
        checks.check(current[0] >= previous[1], 'ORDER no new owner before previous actual AVAILABLE', [previous[2], current[2]])
    checks.equal(simulation.get('wait_used_ns'), 0, 'ORDER has no WAIT dose')
    return {'status': 'SOURCE_DECLARED_EDD_FIXED_ROUTE_GLOBAL_SERIAL_RECORDS_CHECKED', 'dispatches': len(reserved),
            'installed_verified': False, 'scheduler_body_verified': False, 'full_scheduler_reproduction': False}


def check_WAIT_trace(raw, policy, checks):
    simulation, public = raw['simulation'], raw['public_input']
    if not isinstance(simulation.get('decisions'), list) or type(simulation.get('wait_used_ns')) is not int:
        return {'status': 'UNKNOWN_WAIT_ACTION_SCHEMA_UNAVAILABLE', 'full_scheduler_reproduction': False}
    wait, intervals, groups = 0, [], set()
    for decision in simulation['decisions']:
        at, state = decision['time_ns'], decision['public_state']
        checks.equal(state.get('now_ns'), at, 'WAIT/public predecision clock', at)
        if 'public_state_sha256' in decision:
            checks.equal(decision['public_state_sha256'], digest(state), 'WAIT/public snapshot exact hash', at)
        for q in state.get('queue', []):
            checks.check(set(q) <= QUEUE_FIELDS and q['queue_entry_ns'] <= at, 'WAIT/public queue excludes future/latent outcomes', at)
        for owner in state.get('owners', []):
            checks.check(set(owner) <= OWNER_FIELDS and owner['dispatch_ns'] <= at, 'Public owner excludes latent finish', at)
        action = decision.get('applied_control') or decision.get('action', {})
        if action.get('kind') != 'WAIT':
            continue
        dose = action.get('wait_ns')
        checks.check(type(dose) is int and dose > 0, 'Positive integer WAIT action dose', at)
        if type(dose) is not int or dose <= 0:
            continue
        wait += dose
        interval = (at, min(public['service_stop_ns'], at + dose))
        intervals.append(interval)
        if policy == 'FIFO_WAIT_CG':
            checks.equal(dose, 200_000_000, 'Source WAIT200 dose', at)
            checks.equal(state.get('owners', []), [], 'Source WAIT control starts only when all owners idle', at)
            request_id = decision.get('action', {}).get('request_id')
            heads = [q for q in state.get('queue', []) if q['request_id'] == request_id]
            if not heads:
                return {'status': 'UNKNOWN_WAIT_GROUP_BINDING_ABSENT', 'dose_sum_ns': wait, 'full_scheduler_reproduction': False}
            group = heads[0].get('group')
            checks.check(type(group) is int and 0 <= group < 16 and group not in groups, 'Source WAIT is once per eligible native group', at)
            groups.add(group)
    checks.equal(simulation['wait_used_ns'], wait, 'WAIT recorded dose sum')
    checks.check(wait <= 12_000_000_000, 'Frozen general WAIT cumulative cap')
    if policy == 'FIFO_WAIT_CG':
        checks.check(wait <= 16 * 200_000_000, 'Source WAIT200 max16 groups/cumulative3.2s')
    for request in simulation['requests']:
        reserved = request.get('reserved_at_ns')
        if reserved is not None:
            checks.check(not any(lo <= reserved < hi for lo, hi in intervals), 'No new reservation inside active WAIT interval', request['request_id'])
    events = simulation.get('events')
    if intervals and isinstance(events, list) and simulation.get('status') == 'COUNTERFACTUAL_COMPLETE_UNVALIDATED':
        endings = Counter(e['time_ns'] for e in events if e.get('kind') == 'WAIT_END')
        checks.equal(endings, Counter(hi for _, hi in intervals), 'WAIT interval end events')
        boundary_status = 'CHECKED'
    else:
        boundary_status = 'NO_WAIT_RECORDED' if not intervals else 'UNKNOWN_PARTIAL_SCHEDULE_OR_WAIT_END_SCHEMA'
    return {'status': 'RECORDED_WAIT_CONSTRAINTS_CHECKED', 'dose_sum_ns': wait, 'eligible_groups': sorted(groups),
            'interval_end_evidence': boundary_status, 'installed_verified': False,
            'full_scheduler_reproduction': False}


def same_pin(left, right):
    return (path_key(left['path']), left['sha256'], left.get('bytes')) == (path_key(right['path']), right['sha256'], right.get('bytes'))


def audit_budget_sources(op, forecast, reservation, allocation, receipts, result, complete, checks):
    """Fresh saved ledgers plus independent arithmetic for every charged START.

    Legacy unresolved/duplicate identities are exposed, never deducted from cost.
    No claim of discovering unregistered ledgers: the explicit closed registry is
    bound to the original operation and inspected on every original START.
    """
    checks.equal(reservation.get('global_cap'), GLOBAL_CAP, 'Canonical global137712 cap')
    checks.equal(reservation.get('combined_reserved'), GLOBAL_REGISTERED, 'Canonical119750 reservation')
    checks.equal(reservation.get('prior_policy_environment_START'), CANONICAL_START, 'Original26454 accounting preserved')
    expected_allocation = {'global_cap': GLOBAL_CAP, 'additional_global_reservation': 0,
                           'original_A24_pool_cap': A24_CAP, 'original_A24_START_consumed': A24_CANONICAL,
                           'unused_before': 353, 'allocated_from_original_unused': SHARED_CAP,
                           'remaining_original_unallocated': 97}
    for key, value in expected_allocation.items():
        checks.equal(allocation.get(key), value, 'Allocation contract ' + key)
    checks.check(same_pin(allocation['prior_reservation_pin'], forecast['canonical_reservation_pin']), 'Allocation original reservation exact binding')
    config = forecast['budget']
    reservation_id = 'A24CF256:' + forecast['forecast_allocation_pin']['sha256']
    checks.equal(config['reservation_id'], reservation_id, 'Stable allocation-SHA reservation identity')
    checks.check(forecast.get('all_extra_and_prior_forecast_ledgers_asserted_complete') is True, 'Explicit complete source ledger registry assertion')
    canonical_specs = reservation['canonical_prior_ledgers']
    extra_specs = forecast.get('extra_consumption_ledgers', [])
    prior_specs = forecast.get('prior_forecast_ledger_pins', [])
    checks.equal(len(canonical_specs), 10, 'Exactly original10 canonical ledger entries')
    all_specs = [*canonical_specs, *extra_specs, *prior_specs]
    require(len({path_key(s['path']) for s in all_specs}) == len(all_specs), 'Duplicate canonical/extra/prior ledger path')
    supplied = {path_key(s['path']): s for s in op['source_ledger_pins']}
    require(len(supplied) == len(op['source_ledger_pins']), 'Duplicate supplemental source ledger pin')
    checks.equal(set(supplied), {path_key(s['path']) for s in all_specs if not s.get('missing')}, 'Fresh source ledger roster equals closed original registry')
    records, source_starts, evidence = [], {}, []
    for spec in all_specs:
        key = path_key(spec['path'])
        if spec.get('missing'):
            require(not Path(spec['path']).exists(), 'Originally missing canonical ledger appeared; register new source audit')
            summary = ledger_summary([])
            checks.equal(spec.get('START', 0), 0, 'Absent ledger has zero declared cost', key)
            evidence.append({'path': spec['path'], 'sha256': None, 'missing': True,
                             **{k: summary[k] for k in ('rows', 'START', 'COMPLETE', 'FAIL')}})
            records.append({'path': spec['path'], 'missing': True, **summary})
            source_starts[key] = []
            continue
        require(key in supplied, 'Existing source ledger has no fresh exact byte pin')
        fresh = supplied[key]
        require(type(fresh.get('bytes')) is int and fresh['bytes'] >= 0, 'Fresh source ledger exact bytes required')
        require(fresh['sha256'] == spec['sha256'], 'Fresh source ledger differs from original registered bytes')
        rows = json_lines(pin(fresh))
        summary = ledger_summary(rows)
        for field in ('rows', 'START', 'COMPLETE', 'FAIL'):
            if field in spec:
                checks.equal(summary[field], spec[field], 'Fresh source ledger count ' + field, key)
        if 'bytes' in spec:
            checks.equal(fresh['bytes'], spec['bytes'], 'Fresh source ledger bytes', key)
        evidence.append({'path': spec['path'], 'sha256': fresh['sha256'], 'missing': False,
                         **{k: summary[k] for k in ('rows', 'START', 'COMPLETE', 'FAIL')}})
        records.append({'path': spec['path'], 'sha256': fresh['sha256'], 'bytes': fresh['bytes'], 'missing': False, **summary})
        source_starts[key] = [r for r in rows if r.get('event') == 'START']
    amounts = {path_key(r['path']): r['START'] for r in records}
    canonical = sum(amounts[path_key(s['path'])] for s in canonical_specs)
    suffixes = ('/outputs/a24-integrated-sim-20261016/receipts.jsonl', '/outputs/a24-integrated-sim-20261016-g002/receipts.jsonl')
    pool = [s for s in canonical_specs if any(path_key(s['path']).lower().endswith(end) for end in suffixes)]
    checks.equal(len(pool), 2, 'Both A24 parent and child canonical ledgers')
    canonical_a24 = sum(amounts[path_key(s['path'])] for s in pool)
    extra = sum(amounts[path_key(s['path'])] for s in extra_specs)
    prior = sum(amounts[path_key(s['path'])] for s in prior_specs)
    checks.check(not any(s.get('a24_pool') for s in extra_specs), 'A24 ledgers cannot be hidden as external consumption')
    checks.check(all(s.get('a24_pool') is True for s in prior_specs), 'Every prior A24 forecast explicitly belongs to original pool')
    prior_shared = sum(r.get('reservation_id', r.get('manifest', {}).get('reservation_id')) == reservation_id
                       for s in prior_specs for r in source_starts[path_key(s['path'])])
    prior_logical = {r.get('logical_case_sha256') for s in prior_specs for r in source_starts[path_key(s['path'])]}
    starts = [r for r in receipts if r.get('event') == 'START']
    cap = validate_budget_config(config)
    require(canonical + extra + prior + config['reserved_global_excluding_this'] + cap == GLOBAL_REGISTERED,
            'Even zero-START operation must conserve the global reservation')
    require(canonical_a24 + prior + config['reserved_a24_excluding_this'] + cap == A24_CAP,
            'Even zero-START operation must conserve the A24 reservation')
    require(prior_shared + cap <= SHARED_CAP and prior + cap <= 353, 'Registered full operation allocation exceeds remaining pool')
    checks.equal(canonical, CANONICAL_START, 'Fresh canonical START total, no success-only refund')
    checks.equal(canonical_a24, A24_CANONICAL, 'Fresh A24 START1695 total including parent FAIL')
    evidence_by = {path_key(e['path']): {k: v for k, v in e.items() if k != 'path'} for e in evidence}
    arithmetic_rows = []
    for index, start in enumerate(starts):
        expected = independent_budget(config, canonical=canonical, canonical_a24=canonical_a24,
                                      extra=extra, prior=prior, prior_shared=prior_shared, index=index)
        checks.equal(start['guards']['arithmetic'], expected, 'Every START independent global/A24/reservation arithmetic', start['identity'])
        checks.equal(start.get('reservation_id'), reservation_id, 'START shared reservation identity', start['identity'])
        checks.equal(start['manifest'].get('reservation_id'), reservation_id, 'Manifest shared reservation identity', start['identity'])
        checks.check(start.get('logical_case_sha256') not in prior_logical, 'FAIL/COMPLETE logical cases not retried', start['identity'])
        recorded = start['guards']['ledger_sources']
        checks.equal(len(recorded), len(evidence), 'Every START has every canonical/external/prior ledger proof', start['identity'])
        by_path = {path_key(e['path']): {k: v for k, v in e.items() if k != 'path'} for e in recorded}
        checks.equal(by_path, evidence_by, 'Every START source SHA/missing/count proof matches fresh saved bytes', start['identity'])
        checks.check(start.get('new_simulator_environments_consumed') == 1 and start.get('automatic_retry') is False,
                     'Every successful or failed START consumes one simulator environment', start['identity'])
        arithmetic_rows.append({'identity': start['identity'], **expected})
    checks.equal(len({r.get('logical_case_sha256') for r in starts}), len(starts), 'No repeated logical cases in current operation')
    checks.equal(result['simulation_START_consumed'], len(starts), 'Reported result all START consumed')
    checks.equal(complete['simulation_START_consumed'], len(starts), 'Reported inner completion all START consumed')
    checks.equal(result['new_simulator_environments_consumed'], len(starts), 'Nested scientific environment count')
    checks.equal(result['global_START_after'], canonical + extra + prior + len(starts), 'Reported fresh global START total')
    checks.equal(result['a24_shared_START_after'], canonical_a24 + prior + len(starts), 'Reported fresh A24 START total')
    checks.equal(result['global_actual_plus_reserved'], GLOBAL_REGISTERED, 'Reported global reservation conservation')
    checks.equal(result['root_orchestration_hook_new_environment'], 0, 'Wrapper zero is orchestration hook only')
    return {'canonical_START': canonical, 'canonical_A24_START': canonical_a24, 'extra_START': extra,
            'prior_A24_START': prior, 'prior_same_reservation_START': prior_shared, 'this_forecast_START': len(starts),
            'global_START_after': canonical + extra + prior + len(starts), 'global_reserved_total': GLOBAL_REGISTERED,
            'global_cap': GLOBAL_CAP, 'A24_cap': A24_CAP, 'shared_forecast_cap': SHARED_CAP,
            'reservation_id': reservation_id, 'source_ledgers': records, 'START_arithmetic': arithmetic_rows,
            'legacy_unresolved_or_duplicate_START_is_charged': True,
            'registry_scope': 'EXACT_REGISTERED_CANONICAL_PLUS_EXPLICIT_EXTRA_PRIOR_LEDGERS; undisclosed external ledgers cannot be discovered by this saved audit'}


def validate_operation(op):
    require(op.get('mode') == 'AUDIT_CONTRACT_SUPPLEMENT', 'Wrong saved contract supplement mode')
    require(path_key(op['worker_lock_path']) == path_key(ORIGINAL_LOCK), 'Original G002 worker lock required')
    require(len(op['protected_pins']) >= 351, 'Protected351 original union may not be reduced')
    for key in ('new_policy_simulations', 'new_fit', 'NN', 'AP_replay_queries'):
        require(op.get(key) == 0, 'Saved-only supplement requires zero ' + key)
    require(op.get('expected_case_count') == 249 and op.get('expected_heldout_count') == 69 and op.get('expected_novel_count') == 180,
            'Exact registered249/69/180 roster required')
    require(type(op.get('raw_expanded_byte_cap')) is int and 0 < op['raw_expanded_byte_cap'] <= 64 * 1024**2,
            'Positive bounded raw per-file expansion cap required, max64MiB')
    require(type(op.get('raw_total_expanded_byte_cap')) is int and 0 < op['raw_total_expanded_byte_cap'] <= 4 * 1024**3,
            'Positive bounded saved raw total expansion cap required, max4GiB')
    registered = {(path_key(s['path']), s['sha256'], s.get('bytes')) for s in op['input_pins']}
    for spec in [*(op[k] for k in LOGICAL_PINS), *op['source_ledger_pins']]:
        require(type(spec.get('bytes')) is int and spec['bytes'] >= 0, 'Logical input requires exact SHA and byte pin')
        require((path_key(spec['path']), spec['sha256'], spec['bytes']) in registered, 'Logical input absent from operation input closure')
    names = {Path(s['path']).name for s in op['source_pins']}
    require({'audit_contract_supplement.py', 'runtime_guard.py'} <= names, 'Supplement entry/runtime exact source closure required')
    require(not any(Path(s['path']).name in ('protocol_simulator.py', 'timing_model.py', 'thermal_model.py') for s in op['source_pins']),
            'Supplement does not import simulator, timing builder or AP implementation')


def check_prepared(item, prepared, checks):
    start, terminal, row = item['start'], item['terminal'], item['row']
    checks.equal(prepared.get('manifest'), start['manifest'], 'Prepared/START exact manifest', start['identity'])
    saved = prepared['row']
    checks.equal(saved.get('identity'), start['identity'], 'Prepared row identity', start['identity'])
    checks.equal(saved.get('manifest'), start['manifest'], 'Prepared row exact manifest', start['identity'])
    for key in ('raw_path', 'raw_sha256'):
        checks.equal(saved.get(key), terminal.get(key), 'Prepared/terminal ' + key, start['identity'])
    if row is not None:
        checks.equal(saved, {k: v for k, v in row.items() if k not in ('prepared_path', 'prepared_sha256')},
                     'Prepared row exactly precedes its own durable path/SHA fields', start['identity'])
    return saved


def audit(op, out, operation_path):
    validate_operation(op)
    checks = Checks()
    saved = SavedArtifacts(op['forecast_operation_pin'], op['forecast_runtime_complete_pin'])
    forecast = saved.operation
    forecast_sha = op['forecast_operation_pin']['sha256']
    for key in ('thermal_cv_pin', 'source_policy_contract_pin', 'canonical_reservation_pin', 'forecast_allocation_pin'):
        checks.check(same_pin(op[key], forecast[key]), 'Supplement/original operation exact ' + key)
    # Saved producer outputs must be both direct operation inputs and present in
    # the producer outer COMPLETE, including the legitimate empty rows file.
    for key in ('forecast_complete_pin', 'forecast_result_pin', 'case_status_pin', 'forecast_rows_pin',
                'forecast_receipts_pin', 'heldout_timing_model_bindings_pin', 'overlay_proof_pin'):
        spec = op[key]
        saved.bound(spec['path'], spec['sha256'])
    result, complete = read(op['forecast_result_pin']['path']), read(op['forecast_complete_pin']['path'])
    checks.equal(complete['forecast_result_sha256'], op['forecast_result_pin']['sha256'], 'Inner completion result SHA')
    checks.equal(result['case_status_sha256'], op['case_status_pin']['sha256'], 'Result case roster SHA')
    checks.equal(result['receipt_ledger_sha256'], op['forecast_receipts_pin']['sha256'], 'Result durable receipts SHA')
    checks.equal(result['row_ledger_sha256'], op['forecast_rows_pin']['sha256'], 'Result durable rows SHA, including empty file')
    checks.check(result.get('measured_J') is None and result.get('physical_goal_pass') is False and result.get('RL_connected') is False,
                 'Saved forecast has no physical/J/RL success claim')
    checks.check(result.get('all_failed_STARTs_remain_consumed') is True and result.get('automatic_retry') is False,
                 'No failed START refunded or retried')
    case_document = read(op['case_status_pin']['path'])
    cases = case_document['cases']
    kinds = Counter(c['kind'] for c in cases)
    checks.equal(len(cases), op['expected_case_count'], 'All249 cases retained')
    checks.equal(kinds, {'PREDECLARED_NOVEL_GRID': op['expected_novel_count'], 'WHOLE_COHORT_HELDOUT_VALIDATION': op['expected_heldout_count']}, 'Exact69 heldout/180 novel roles')
    checks.equal(case_document.get('registered_case_roster'), 249, 'Case document registered denominator')
    checks.check(case_document.get('no_unknown_or_failed_case_dropped') is True, 'Unknown/failure denominator preservation')
    rows, receipts = json_lines(op['forecast_rows_pin']['path']), json_lines(op['forecast_receipts_pin']['path'])
    indexed = receipt_index(receipts, rows, checks)
    starts = [r for r in receipts if r.get('event') == 'START']
    checks.equal(Counter(c['identity'] for c in cases if c.get('identity')), Counter(r['identity'] for r in starts), 'Case-to-START exact identity coverage')
    checks.equal(sum(c['simulation_START_consumed'] for c in cases), len(starts), 'All case consumed START sum')
    checks.equal(len({c['label'] for c in cases}), len(cases), 'Unique public case labels')
    counts = Counter(r.get('event') for r in receipts)
    checks.equal(counts['COMPLETE'], len(rows), 'Every COMPLETE has one saved row')
    checks.equal(result['COMPLETE'], counts['COMPLETE'], 'Reported COMPLETE count')
    checks.equal(result['FAIL'], counts['FAIL'], 'Reported FAIL count')
    cv, selection = read(op['thermal_cv_pin']['path']), read(op['thermal_selection_pin']['path'])
    timing_bindings, metadata = read(op['heldout_timing_model_bindings_pin']['path']), read(op['session_metadata_pin']['path'])
    checks.equal(timing_bindings.get('thermal_cv_sha256'), op['thermal_cv_pin']['sha256'], 'Timing folds bind exact AP CV artifact')
    checks.check(timing_bindings.get('whole_cohort_folds') is True and timing_bindings.get('selection_uses_policy_gap') is False,
                 'Heldout timing uses fixed whole-cohort folds without policy outcome selection')
    context, session_by = selected_fold_context(cv, selection, metadata, timing_bindings, forecast['dataset_pin']['sha256'], checks)
    heldout_ids = [c['source_session_id'] for c in cases if c['kind'] == 'WHOLE_COHORT_HELDOUT_VALIDATION']
    checks.equal(sorted(heldout_ids), sorted(forecast['heldout_validation_session_ids']), 'Heldout case roster exact original operation IDs')
    checks.equal(sorted(heldout_ids), sorted(metadata['timing_qualified_M8_ids']), 'All69 timing-qualified M8 sessions retained')
    contract = read(op['source_policy_contract_pin']['path'])
    checks.equal(contract['original_dataset_pin']['sha256'], forecast['dataset_pin']['sha256'], 'Source policy contract original dataset binding')
    order_contracts = [c for c in contract['contracts'] if c.get('arm') == 'ORDER']
    checks.equal(len(order_contracts), 1, 'One exact source-declared ORDER contract')
    if order_contracts:
        expected_order = {'policy': 'EDD', 'public_order': 'EDD', 'public_route': 'C_GPU_D_CPU', 'protocol': 'SERIAL',
                          'validation_execution': 'ATOMIC_PROTOCOL_GLOBAL_SERIAL', 'classification_route': 'GPU', 'detection_route': 'CPU',
                          'installed_verified': False, 'scheduler_body_verified': False}
        for key, value in expected_order.items():
            checks.equal(order_contracts[0].get(key), value, 'Exact ORDER source contract ' + key)
    overlay = read(op['overlay_proof_pin']['path'])
    checks.check(overlay.get('all_nonbank_content_unchanged') is True and overlay.get('AP_inputs_targets_domains_and_roster_unchanged') is True,
                 'Timing-only bank overlay left thermal inputs/domains/roster unchanged')
    reports = []
    for case in cases:
        before = checks.failed
        identity = case.get('identity')
        report = {k: case.get(k) for k in ('identity', 'row_identity', 'label', 'kind', 'bank', 'policy', 'seed', 'planned',
                                          'source_session_id', 'validation_cohort_id', 'status', 'simulation_START_consumed')}
        item, raw, row = indexed.get(identity), None, None
        if identity is None:
            checks.equal(case['simulation_START_consumed'], 0, 'No-START UNKNOWN costs zero', case['label'])
            checks.check(case.get('row_identity') is None and case.get('raw_path') is None, 'No-START UNKNOWN has no fabricated row/raw', case['label'])
            report['chain_status'] = 'UNKNOWN_NO_START_RETAINED'
        else:
            require(item is not None, 'Case identity absent from indexed START/terminal chain')
            start, terminal, row = item['start'], item['terminal'], item['row']
            checks.equal(start['manifest']['operation_sha256'], forecast_sha, 'START exact producer operation', identity)
            checks.equal(start['manifest']['label'], case['label'], 'START public case label', identity)
            checks.equal(start['manifest']['policy'], case['policy'], 'START public case policy', identity)
            checks.equal(start['manifest']['seed'], case['seed'], 'START public case seed', identity)
            bindings = start['manifest']['model_bindings']
            for key in ('data_original_sha256', 'dataset_sha256'):
                checks.equal(bindings.get(key), forecast['dataset_pin']['sha256'], 'START original dataset ' + key, identity)
            checks.equal(bindings.get('source_pins_sha256'), digest(forecast['source_pins']), 'START original source closure hash', identity)
            checks.equal(bindings.get('timing_bank_overlay_sha256'), forecast['timing_bank_overlay_pin']['sha256'], 'START registered bank-only overlay', identity)
            checks.equal(bindings.get('timing_bank_overlay_proof_sha256'), op['overlay_proof_pin']['sha256'], 'START exact overlay proof', identity)
            checks.equal(bindings.get('effective_bank_map_sha256'), overlay['effective_bank_map_sha256'], 'START effective bank map', identity)
            checks.equal(bindings.get('thermal_input_projection_sha256'), overlay['thermal_input_after_sha256'], 'START unchanged AP input projection', identity)
            checks.equal(case['simulation_START_consumed'], 1, 'START stays charged on FAIL', identity)
            body = saved.object(terminal['terminal_path'], terminal['terminal_sha256'])
            report['terminal_status'] = terminal_body_check(item, body, forecast_sha, checks)
            prepared_row = None
            if terminal.get('prepared_path') is not None:
                prepared = saved.object(terminal['prepared_path'], terminal['prepared_sha256'])
                prepared_row = check_prepared(item, prepared, checks)
            if terminal.get('raw_path') is not None:
                raw = saved.raw(terminal['raw_path'], terminal['raw_sha256'], op['raw_expanded_byte_cap'], op['raw_total_expanded_byte_cap'])
                effective_row = row or prepared_row or {**raw['compact'], 'identity': identity, 'manifest': start['manifest'], 'policy': case['policy']}
                report['policy_binding'] = check_policy_bindings(raw, effective_row, start, checks)
                source_meta = effective_row.get('source_policy_contract', {})
                checks.equal(source_meta.get('source_policy_contract_sha256'), op['source_policy_contract_pin']['sha256'], 'Raw exact source policy contract SHA', identity)
                expected_role = 'EXACT_VALIDATION' if case['kind'] == 'WHOLE_COHORT_HELDOUT_VALIDATION' else 'GENERALIZED_NOVEL'
                checks.equal(source_meta.get('experiment_role'), expected_role, 'Exact validation versus generalized novel role', identity)
                checks.equal(len(raw['public_input']['requests']), case.get('planned'), 'Raw all-request denominator equals public case', identity)
                checks.equal(raw['public_input'].get('source_session_id'), case['source_session_id'], 'Raw source session identity', identity)
                if case['kind'] == 'WHOLE_COHORT_HELDOUT_VALIDATION' and session_by[case['source_session_id']].get('arm') == 'ORDER':
                    report['ORDER'] = check_ORDER_trace(raw, checks)
                report['WAIT'] = check_WAIT_trace(raw, case['policy'], checks)
                row = effective_row
            report['chain_status'] = 'COMPLETE_CHAIN_CHECKED' if terminal['event'] == 'COMPLETE' else 'FAIL_WITH_PRESENT_REFS_CHECKED_AND_CONSUMED'
            report['present_FAIL_refs'] = [key for key in ('raw_path', 'prepared_path', 'terminal_path') if terminal.get(key)] if terminal['event'] == 'FAIL' else []
        if case['kind'] == 'WHOLE_COHORT_HELDOUT_VALIDATION':
            checks.equal(case.get('validation_cohort_id'), session_by[case['source_session_id']]['cohort_id'], 'Heldout case exact source cohort', case['label'])
            report['heldout_model'] = check_heldout_model(case, row, raw, context, forecast, checks,
                                                        manifest=item['start']['manifest'] if item else None)
        elif item:
            bindings = item['start']['manifest']['model_bindings']
            checks.equal(bindings.get('thermal_artifact_sha256'), forecast['thermal_models_pin']['sha256'], 'Novel uses registered final AP artifact', case['label'])
            checks.equal(bindings.get('thermal_model_sha256'), forecast['thermal_model_sha256'], 'Novel uses exact registered final AP model', case['label'])
        report['failed_checks'] = checks.failed - before
        reports.append(report)
    budget = audit_budget_sources(op, forecast, read(op['canonical_reservation_pin']['path']), read(op['forecast_allocation_pin']['path']),
                                  receipts, result, complete, checks)
    output = {'schema': VERSION, 'status': 'PASS_SAVED_CONTRACT_BINDINGS_WITH_EXPLICIT_UNKNOWNS' if checks.failed == 0 else 'FAIL_SAVED_CONTRACT_BINDINGS',
              'operation_sha256': sha(operation_path), 'forecast_operation_sha256': forecast_sha,
              'checks': checks.count, 'failed_checks': checks.failed, 'failures': checks.failures,
              'registered_case_roster': len(cases), 'heldout_roster': kinds['WHOLE_COHORT_HELDOUT_VALIDATION'],
              'novel_roster': kinds['PREDECLARED_NOVEL_GRID'], 'all_249_cases_retained': len(reports) == len(cases) == 249,
              'cases': reports, 'forecast_environment_START_consumed': len(starts), 'budget': budget,
              'source_bindings': {**{name: op[name] for name in LOGICAL_PINS}, 'source_ledger_pins': op['source_ledger_pins']},
              'source_pins': op['source_pins'], 'source_pins_sha256': digest(op['source_pins']),
              'saved_raw_expanded_bytes': saved.expanded, 'new_policy_simulations': 0, 'new_fit': 0, 'AP_replay_queries': 0,
              'NN': 0, 'HTTP': 0, 'device_commands': 0, 'measured_J': None, 'physical_goal_pass': False, 'fresh_confirmation': False,
              'full_scheduler_reproduction': False, 'installed_verified': False,
              'limitations': ['Saved contract and model-membership checks only; no AP arithmetic replay in this supplement.',
                              'Source-declared ORDER constraints are checked; full installed scheduler body was unavailable.',
                              'Other arms retain declared rolling/global FIFO/current-lane compatibility and explicit source limitations.',
                              'WAIT records are checked only where schema exposes actions/boundaries; missing schema stays UNKNOWN.',
                              'All115 sessions were already development data; posthoc heldouts are not fresh confirmation.',
                              'The ledger closure is the exact registered registry, not discovery of undisclosed external consumption.']}
    write_new(out / 'RESULT.json', output)
    require(checks.failed == 0, 'Supplement failed checks; RESULT preserved, no successful outer COMPLETE')
    return output


def description():
    return {'schema': VERSION, 'mode': 'AUDIT_CONTRACT_SUPPLEMENT', 'runtime': 'runtime_guard.operation aliased as run_operation; unchanged original lock/process/8GiB/351 protections',
            'required_logical_pins': list(LOGICAL_PINS), 'required_extra_input_array': 'source_ledger_pins',
            'source_ledger_roster': 'existing canonical8 + all forecast.extra_consumption_ledgers + forecast.prior_forecast_ledger_pins; exact path/sha256/bytes in input_pins; declared missing2 remain absent',
            'required_standard_fields': ['schema=A24-local-model-improvement-operation-v1', 'allow_execution=true', 'source_pins', 'input_pins', 'protected_pins>=351',
                                         'worker_lock_path=original G002 worker.lock', 'output_dir=fresh namespace', 'known_PS_producer_paths',
                                         'new_environment=0', 'HTTP=0', 'device_commands=0', 'automatic_retry=false'],
            'required_mode_fields': {'new_policy_simulations': 0, 'new_fit': 0, 'AP_replay_queries': 0, 'NN': 0,
                                     'expected_case_count': 249, 'expected_heldout_count': 69, 'expected_novel_count': 180,
                                     'raw_expanded_byte_cap': 33554432, 'raw_total_expanded_byte_cap': 2147483648},
            'source_closure': ['audit_contract_supplement.py', 'runtime_guard.py'],
            'pin_contract': 'Every logical/source-ledger pin is exact path+sha256+bytes and included in input_pins; forecast outputs additionally bind producer outer COMPLETE map.',
            'output': 'RESULT.json then frozen runtime START/COMPLETE or FAILURE. PASS status preserves explicit UNKNOWNs and every249 case; no simulator/fit/AP-replay START.',
            'CLI': 'python -B audit_contract_supplement.py --operation <registered operation>; --describe prints this schema only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--describe', action='store_true')
    choice.add_argument('--operation')
    args = parser.parse_args()
    if args.describe:
        print(canonical(description()))
        return
    with run_operation(args.operation, __file__) as (op, out):
        result = audit(op, out, args.operation)
        print(canonical({k: result[k] for k in ('schema', 'status', 'checks', 'failed_checks', 'registered_case_roster', 'forecast_environment_START_consumed')}))


if __name__ == '__main__':
    main()
