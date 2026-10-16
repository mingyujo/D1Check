"""Read-only v3 inputs: fixed development roster, causal public data, frozen service.

The old predictor/service is an already fitted prior. Grouped validation using it
is prior-conditional, not a complete family/service out-of-fold experiment.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import os

from tools import d1_session_contrast_cost as archive
from tools import d1_simulation_model_v2 as previous

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = Path(os.environ.get('D1CHECK_ARRIVAL_EXTENSION', str(Path.home()/'Documents'/'D1Check_Arrival_Extension')))
NEW_RUN = ROOT / 'output/model_v2_20261010_v1/user_resume/run'
GROUPS = ('old', 'history30', 'history180', 'macro', 'new_recovery')
CPU = 'CPU_URGENT_ONLINE_V1'
PAR = 'B2_PARALLEL_ONLINE_V1'
POLICIES = {CPU: CPU, PAR: PAR, 'ARRIVAL_CPU96': CPU, 'ARRIVAL_PAR96': PAR}
VALIDATION_SCOPE = (
    'fixed historical model/service prior conditional grouped validation; '
    'historical prior coefficients, service and model family are not fully OOF; '
    'all existing confirmation outcomes previously viewed; no fresh accuracy PASS'
)
_SOURCE_HASHES: dict[str, str] = {}
_CONTRACTS: dict[str, dict] = {}


def _checked(path, expected=None):
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError('registered source drift: ' + str(path))
    key = str(path.resolve())
    if key in _SOURCE_HASHES and _SOURCE_HASHES[key] != digest:
        raise ValueError('loaded source changed within evaluation: ' + key)
    _SOURCE_HASHES[key] = digest
    return json.loads(path.read_text(encoding='utf8'))


def group(c):
    ident = c['id']
    if 'MODEL2_RECOVERY_' in ident or 'ARRIVAL_CPU96' in ident or 'ARRIVAL_PAR96' in ident:
        return 'new_recovery'
    if ident.startswith('session_'):
        return 'macro'
    if '_30_' in ident:
        return 'history30'
    if '_180_' in ident:
        return 'history180'
    return 'old'


def _contract(manifest, family):
    models = {}
    for key, value in manifest.get('models', {}).items():
        models[key] = dict(sha256=value.get('model', {}).get('sha256'),
                           runtime=copy.deepcopy(value.get('runtime')),
                           tensor=copy.deepcopy(value.get('tensor')))
    keys = ('apk_sha256', 'protocol', 'cpu_threads', 'history_control_version',
            'power_sampling_version', 'power_identification_version',
            'identification_profile', 'power_sample_period_ms')
    return dict(source_family=family, exact_manifest_available=bool(manifest),
                **{k: copy.deepcopy(manifest[k]) for k in keys if k in manifest},
                models=models, images=[r.get('sha256') for r in manifest.get('images', [])],
                cross_protocol_transfer_is_hypothesis=True)


def _history(c):
    inventory = _checked(ROOT / 'docs/results/recovery_service_01/run_v1/inputs.json')
    location = inventory['source_locations'].get(c['id'])
    if location is None:
        return
    directory = EXTERNAL / location
    expected = inventory['raw_hashes']
    boundary = _checked(directory / 'artifacts/history_boundary.json',
                        expected[c['id'] + '/history_boundary.json'])
    rows = _checked(directory / 'artifacts/conditioning_requests.json',
                    expected[c['id'] + '/conditioning_requests.json'])
    manifest = _checked(directory / 'input_manifest.json',
                        expected[c['id'] + '/input_manifest.json'])
    origin = boundary['target_start_ns']
    relative = [dict(r, dispatch_ns=r['dispatch_ns'] - origin,
                     lane_available_ns=r['lane_available_ns'] - origin) for r in rows]
    c['history'] = previous.occupancy(relative, boundary['conditioning_start_ns'] - origin, 0)
    c['history_scope'] = 'recorded completed conditioning before target origin; no future work'
    c['source_manifest'] = str(directory / 'input_manifest.json')
    c['source_manifest_sha256'] = expected[c['id'] + '/input_manifest.json']
    c['manifest_requests'] = copy.deepcopy(manifest['requests'])
    c['source_contract'] = _contract(manifest, group(c))


def _archive_cases():
    registration = _checked(ROOT / 'docs/results/session_contrast_cost_01/registration_v2.json')
    for name, expected in registration['sources'].items():
        if name.endswith(('inputs.json.gz', 'model.json')):
            path = ROOT / name
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != expected:
                raise ValueError('registered archive changed: ' + name)
            _SOURCE_HASHES[str(path.resolve())] = digest
    data = copy.deepcopy(archive.cases())
    if len(data) != 35 or len({c['id'] for c in data}) != 35:
        raise ValueError('fixed archival 35 session roster')
    development = set(registration['development_ids'])
    if {c['id'] for c in data if c['role'] == 'development'} != development:
        raise ValueError('archival development role/roster drift')
    for c in data:
        _history(c)
        c.setdefault('source_contract', _contract({}, group(c)))
        c['source_group'] = group(c)
        _CONTRACTS[c['id']] = copy.deepcopy(c['source_contract'])
    return data


def _new_cases():
    summary = _checked(ROOT / 'docs/results/simulation_model_v2_01/run_v1/summary.json')
    expected = {str(Path(name).resolve()): value for name, value in summary['source_hashes'].items()}
    data = []
    paths = sorted(NEW_RUN.glob('*/validated.json'))
    if len(paths) != 8:
        raise ValueError('fixed new v2 eight session roster')
    for path in paths:
        key = str(path.resolve())
        if key not in expected:
            raise ValueError('new session missing registered hash')
        record = _checked(path, expected[key])
        c = copy.deepcopy(record['analysis_case'])
        manifest_path = path.parent / 'input_manifest.json'
        mkey = str(manifest_path.resolve())
        if mkey not in expected:
            raise ValueError('new manifest missing registered hash')
        manifest = _checked(manifest_path, expected[mkey])
        if c.get('manifest_requests') is not None and c['manifest_requests'] != manifest['requests']:
            raise ValueError('new exact planned requests mismatch')
        c['source_manifest'] = str(manifest_path)
        c['source_manifest_sha256'] = expected[mkey]
        c['source_group'] = group(c)
        c['source_contract'] = _contract(manifest, group(c))
        c['application_lifecycle_pass'] = record.get('application_lifecycle_pass')
        c['post_cleanup_failure_preserved'] = bool(record.get('post_cleanup_failure'))
        _CONTRACTS[c['id']] = copy.deepcopy(c['source_contract'])
        data.append(c)
    if sum(c['role'] == 'development' for c in data) != 4:
        raise ValueError('fixed new development four session roster')
    return data


def load_development():
    data = [c for c in _archive_cases() + _new_cases() if c['role'] == 'development']
    if len(data) != 17 or len({c['id'] for c in data}) != 17:
        raise ValueError('fixed development 13 + new four session roster')
    return data


def load_seen():
    data = [c for c in _archive_cases() + _new_cases() if c['role'] != 'development']
    if len(data) != 26 or len({c['id'] for c in data}) != 26:
        raise ValueError('fixed previously viewed 22 + new four session roster')
    for c in data:
        c['evaluation_scope'] = 'previously viewed posthoc; never coefficient/hyperparameter selection'
    return data


def public_input(c):
    """Whitelist predictor inputs. Electrical future and measured schedule stay out."""
    pre = copy.deepcopy(c['pre'])
    if not pre or any(not all(math.isfinite(float(r[k])) for k in ('lo', 't', 'hi', 'ap'))
                      or not r['lo'] <= r['t'] <= r['hi'] < 35 for r in pre):
        raise ValueError('noncausal or invalid pre AP')
    q = list(c['q'])
    if not q or any(not math.isfinite(float(t)) or t < 35 for t in q) or any(b <= a for a, b in zip(q, q[1:])):
        raise ValueError('invalid evaluation query grid')
    if not math.isfinite(float(c['pre_w'])) or c['pre_w'] <= 0:
        raise ValueError('invalid causal initial power')
    result = dict(id=c['id'], role=c['role'], source_group=group(c),
                  pre=pre, pre_w=float(c['pre_w']), q=q)
    history = copy.deepcopy(c.get('history', []))
    if history:
        previous.validate_segments(history)
        if history[-1]['end_s'] > 35:
            raise ValueError('future history input')
        result['history'] = history
    if 'power_t' in c and 'power_w' in c:
        if len(c['power_t']) != len(c['power_w']):
            raise ValueError('electrical time/value length')
        prefix = [(t, w) for t, w in zip(c['power_t'], c['power_w']) if t < 35]
        if prefix and prefix[0][0] <= 10 and prefix[-1][0] >= 30:
            late = previous.prior.integral(dict(power_t=[t for t, _ in prefix],
                                                power_w=[w for _, w in prefix]), 10, 30) / 20
            if not math.isfinite(late) or late <= 0:
                raise ValueError('invalid late initial power')
            result['initial_power_late_w'] = late
    return result


def _old_manifest(c):
    if c['id'] in ('development_0', 'development_1'):
        version, index = (1, 0) if c['id'] == 'development_0' else (2, 0)
        plan_path = EXTERNAL / f'separated_power_plan_v{version}/development/collection_plan.json'
    elif c['id'].startswith('confirmation_') and c['id'].rsplit('_', 1)[-1].isdigit():
        version, index = 4, int(c['id'].rsplit('_', 1)[-1])
        plan_path = EXTERNAL / 'separated_power_plan_v4/confirmation/collection_plan.json'
    elif c['id'].startswith('sustained_'):
        index = int(c['id'].split('_')[-1])
        plan_path = EXTERNAL / 'sustained_confirmation_plan_v1/collection_plan.json'
        inventory = _checked(ROOT / 'docs/results/model_refinement_01/source_inventory.json')
        expected = inventory['files'][str(plan_path.relative_to(EXTERNAL))]
        _checked(plan_path, expected)
    else:
        raise ValueError('no exact source manifest for ' + c['id'])
    plan = _checked(plan_path)
    entry = next(e for e in plan['entries'] if e['index'] == index)
    planned = _checked(plan_path.parent / entry['manifest'], entry['manifest_sha256'])
    folder = Path(plan['output_root']) / f"{index:02d}_{entry['session_id']}"
    path = folder / 'input_manifest.json'
    manifest = _checked(path, entry['manifest_sha256'])
    if manifest != planned:
        raise ValueError('executed/planned exact manifest mismatch')
    return path, manifest


def source_manifest(c):
    """Return exact executed manifest and path, never infer tickets from completions."""
    if c.get('source_manifest'):
        path = Path(c['source_manifest'])
        manifest = _checked(path, c.get('source_manifest_sha256'))
    else:
        path, manifest = _old_manifest(c)
    if c.get('manifest_requests') is not None and c['manifest_requests'] != manifest['requests']:
        raise ValueError('exact planned requests disagree with derived case')
    expected_policy = POLICIES.get(c['policy'])
    if manifest.get('policy') != expected_policy:
        raise ValueError('exact manifest policy mismatch')
    _CONTRACTS[c['id']] = _contract(manifest, group(c))
    return path, manifest


def development_B_cases(cases, original):
    """Build supported B cases; 17 development inputs yield exactly six.

The name denotes the primary development use. Passing previously viewed cases
is also allowed for a fixed, post-selection readout; their roles are retained.
"""
    result = []
    for c in cases:
        policy = POLICIES.get(c['policy'])
        if policy is None:
            continue
        path, manifest = source_manifest(c)
        requests = copy.deepcopy(manifest['requests'])
        public = public_input(c)
        initial = dict(preload=public['pre'], preload_power_w=public['pre_w'])
        if len(requests) == 192:
            if c['role'] == 'development':
                raise ValueError('unregistered development sustained workload')
            role = 'sustained-confirmation-v1'
        else:
            # This argument selects an exact registered ticket SHAPE, not a
            # statistical train/test role. History development uses mixed350.
            from tools import d1_separated_power_protocol as separated
            try:
                separated.validate('development', requests)
                role = 'development'
            except ValueError:
                separated.validate('confirmation', requests)
                role = 'confirmation'
        legacy, segments = previous.prior.base.forecast(initial, requests, policy, original,
                                                       planning_input_role=role)
        segments = copy.deepcopy(segments)
        end = max(180., public['q'][-1])
        if segments[-1]['end_s'] < end:
            segments.append(dict(start_s=segments[-1]['end_s'], end_s=end, state='idle'))
        previous.validate_segments(segments)
        result.append(dict(case=copy.deepcopy(c), public=dict(public, actual=segments),
                           legacy=legacy, requests=requests, policy=policy, group=group(c),
                           source_manifest=str(path), planning_shape_role=role,
                           validation_scope=VALIDATION_SCOPE))
    return result


def source_inventory():
    return dict(files=copy.deepcopy(_SOURCE_HASHES), source_contracts=copy.deepcopy(_CONTRACTS),
                source_groups=list(GROUPS), validation_scope=VALIDATION_SCOPE,
                already_seen_confirmation=True, new_device_commands=0,
                source_contracts_are_not_pooled_device_coefficients=True,
                default=False, strict_support=False, experiment_ready=False)
