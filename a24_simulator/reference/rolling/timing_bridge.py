"""Pure A24 DEV-vector adapter for an integer-ns rolling event engine.

No simulate, device, fitting, energy model, neural network, or journal calls.
Reading/normalizing a saved vector is not a new simulated environment.  Callers
must register and durably consume START before any actual engine simulation.
S26 priority-dependent response and unobserved inner phases are never imported.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path

NS = 10**9
DEFAULT_PROFILE = Path('C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/A24-DEV8-TIMING-20261015/DEV_PROFILE.json')
DEFAULT_PROFILE_SHA256 = '26b24df6f5e2f679496e850031eaa0f80952085d65abccdc146144c750fa85f0'
SCHEMA = 'A24-INTEGRATED-TIMING-BRIDGE-v1'
RESPONSE_BY_TASK = {'C': 'output_ready_ns', 'D': 'persist_complete_ns'}
SOURCE_STAGES = ('dispatch_to_execution', 'execution_to_output', 'output_to_persist',
                 'persist_to_worker_release', 'worker_release_to_available')
SOURCE_OFFSETS = ('execution_start', 'output_ready', 'persist_complete',
                  'worker_release', 'lane_available')
PHASES = ('execution_start_ns', 'host_inference_start_ns', 'host_inference_return_ns',
          'output_ready_ns', 'persist_complete_ns', 'readback_start_ns',
          'readback_end_ns', 'response_ns', 'worker_release_ns', 'lane_available_ns')
KINDS = ('EXECUTION_START', 'HOST_INFERENCE_START', 'HOST_INFERENCE_RETURN',
         'OUTPUT_READY', 'PERSIST_COMPLETE', 'READBACK_START',
         'READBACK_COMPLETE', 'RESPONSE', 'WORKER_RELEASE', 'AVAILABLE')
ALLOWED_PAIRS = (frozenset({('C', 'GPU'), ('D', 'CPU')}),)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f'{name}: exact integer >= {minimum} required')
    return value


def _task(value):
    try:
        return {'C': 'C', 'D': 'D', 'classification': 'C', 'detection': 'D'}[value]
    except (KeyError, TypeError) as exc:
        raise ValueError('A24 task must be C or D') from exc


def _priority(value):
    try:
        return {'U': 'U', 'N': 'N', 'urgent': 'U', 'normal': 'N'}[value]
    except (KeyError, TypeError) as exc:
        raise ValueError('A24 priority must be U or N') from exc


def _median_ns(values):
    """Integer floor of median; public nominal summary, not a phase vector."""
    values = sorted(values)
    if not values:
        raise ValueError('empty nominal distribution')
    n = len(values)
    return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) // 2


def _pool(profile, bank, task, route, protocol):
    if profile.get('schema') != SCHEMA:
        raise ValueError('load_profile must normalize the frozen A24 profile first')
    key = {'device': 'A24', 'task': 'classification' if _task(task) == 'C' else 'detection',
           'backend': route, 'bank': bank, 'prep': 'NONE', 'protocol': protocol,
           'priority': 'POOLED_NOT_CONDITIONED'}
    found = [p for p in profile['pools'] if p['key'] == key]
    if len(found) != 1:
        raise ValueError('UnsupportedContext: ' + repr(key))
    return found[0]


def load_profile(profile_path=DEFAULT_PROFILE, expected_sha256=DEFAULT_PROFILE_SHA256):
    """Validate saved DEV-only whole vectors and expose a new derived contract.

    Priority remains public request metadata, but is NOT a timing-fit stratum.
    Original source bytes/hash, every five-stage vector and original sample ID
    remain explicit.  Any replacement profile requires its own expected hash and
    new experiment registration; this function never opens CONFIRM outcomes.
    """
    path = Path(profile_path)
    payload = path.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if expected_sha256 is None or sha != expected_sha256:
        raise ValueError('A24 source profile SHA mismatch or missing registration pin')
    raw = json.loads(payload)
    if raw.get('schema') != 'A24-DEV-timing-profile-v1' or raw.get('device', 'A24') != 'A24':
        raise ValueError('wrong source profile/device')
    if raw.get('provenance', {}).get('response_boundary_by_task') != {'C': 'output_ready', 'D': 'persist_complete'}:
        raise ValueError('A24 source response contract changed')
    groups = defaultdict(list)
    ids = set()
    for source in raw['samples']:
        sid = source['sample_id']
        if not isinstance(sid, str) or not sid or sid in ids:
            raise ValueError('empty or duplicate whole-vector sample ID')
        ids.add(sid)
        task = _task(source['task']); route = source['backend']; protocol = source['protocol']
        if (task, route) not in {('C', 'CPU'), ('C', 'GPU'), ('D', 'CPU')}:
            raise ValueError('unsupported A24 route')
        if protocol not in ('SERIAL', 'CG_DC') or (protocol == 'CG_DC' and (task, route) not in ALLOWED_PAIRS[0]):
            raise ValueError('unsupported A24 protocol/pair member')
        running = 0
        for stage, offset in zip(SOURCE_STAGES, SOURCE_OFFSETS):
            running += _integer(source['durations_ns'][stage], stage)
            if _integer(source['offsets_ns'][offset], offset) != running:
                raise ValueError('nonconserving whole vector: ' + sid)
        if running <= 0 or source['durations_ns']['dispatch_to_available'] != running:
            raise ValueError('invalid AVAILABLE offset: ' + sid)
        boundary = RESPONSE_BY_TASK[task]
        if source['response_boundary'] + '_ns' != boundary or source['offsets_ns']['response'] != source['offsets_ns'][boundary[:-3]]:
            raise ValueError('task-based response boundary mismatch: ' + sid)
        timestamps = source.get('timestamps_common_ns', {})
        if timestamps:
            dispatch = _integer(timestamps['dispatch_ns'], 'source dispatch')
            for field in SOURCE_OFFSETS:
                if _integer(timestamps[field + '_ns'], field) - dispatch != source['offsets_ns'][field]:
                    raise ValueError('source timestamp/vector mismatch: ' + sid)
        diagnostics = source.get('diagnostics', {})
        admission = {'scheduled_to_actual': _integer(diagnostics['scheduled_to_actual_ns'], 'scheduled-to-actual'),
                     'actual_to_queue': _integer(diagnostics['actual_to_queue_ns'], 'actual-to-queue')}
        key = {'device': 'A24', 'task': 'classification' if task == 'C' else 'detection',
               'backend': route, 'bank': source['bank'], 'prep': 'NONE', 'protocol': protocol,
               'priority': 'POOLED_NOT_CONDITIONED'}
        offsets = {field: None for field in PHASES}
        offsets.update({name + '_ns': source['offsets_ns'][name] for name in SOURCE_OFFSETS})
        offsets['response_ns'] = offsets[boundary]
        sample = {'sample_id': sid, 'key': key, 'offsets_ns': offsets,
                  'durations_ns': copy.deepcopy(source['durations_ns']),
                  'admission_lags_ns': admission, 'response_boundary': boundary,
                  'redispatch_delay_ns': 0,
                  'redispatch_evidence': 'UNIDENTIFIED_IDEAL_CONTROLLER_ASSUMPTION',
                  'model_sha256': source['model_sha256'], 'input_sha256': source['input_sha256'],
                  'tensor_sha256': source['tensor_sha256'],
                  'source': {'profile_path': str(path), 'profile_sha256': sha,
                             'split': 'DEV', 'session_id': source['session_id'],
                             'raw_result_sha256': source['raw_result_sha256'],
                             'whole_source_sample_sha256': digest(source)},
                  'diagnostics_not_additive': copy.deepcopy(diagnostics),
                  'actual_backend_claim': source.get('actual_backend_claim', 'unverified_requested_route')}
        groups[tuple(key.values())].append(sample)
    if not groups:
        raise ValueError('empty A24 DEV profile')
    pools = []
    for samples in groups.values():
        key = samples[0]['key']
        for binding in ('model_sha256', 'input_sha256', 'tensor_sha256'):
            if len({s[binding] for s in samples}) != 1:
                raise ValueError('mixed binding inside exact A24 pool: ' + binding)
        pools.append({'key': copy.deepcopy(key), 'samples': samples,
                      'priority_conditioning': 'NONE; original profile pooled priorities',
                      'support_requests': len(samples),
                      'support_sessions': len({s['source']['session_id'] for s in samples})})
    pools.sort(key=lambda p: tuple(p['key'].values()))
    result = {'schema': SCHEMA, 'device': 'A24', 'source_profile_sha256': sha,
              'source_provenance': copy.deepcopy(raw['provenance']), 'pools': pools,
              'response_by_task': dict(RESPONSE_BY_TASK),
              'unknown_phases': ['host_inference_start_ns', 'host_inference_return_ns',
                                 'readback_start_ns', 'readback_end_ns'],
              'capabilities': {'requested_routes': [['C', 'CPU'], ['C', 'GPU'], ['D', 'CPU']],
                               'max_active': 2, 'allowed_pair': [['C', 'GPU'], ['D', 'CPU']]},
              'assumptions': ['DEV empirical vectors; independent accuracy not established',
                              'Dynamic policies share route-specific SERIAL vectors only in explicitly controlled mode',
                              'Admission uses a common canonical route across policy arms',
                              'Controller redispatch is ideal zero, not measured RL runtime',
                              'Inner inference/readback phases unobserved; null is not zero',
                              'Priority is not a timing stratum; response depends on task',
                              'No thermal-to-service feedback or physical delegate proof'],
              'source_limits': copy.deepcopy(raw.get('limits', {})),
              'source_warnings': copy.deepcopy(raw.get('warnings', []))}
    result['normalized_profile_digest'] = digest(result)
    return result


def available_routes(profile, bank, task, priority=None, protocol='SERIAL'):
    """Only exact measured pools; no cross-bank filling or S26 route reuse."""
    task = _task(task)
    if priority is not None:
        _priority(priority)  # validate without pretending it selects a timing pool
    return sorted({p['key']['backend'] for p in profile['pools']
                   if p['key']['bank'] == bank and p['key']['protocol'] == protocol
                   and p['key']['task'] == ('classification' if task == 'C' else 'detection')})


def compile_scenario(recipe, *, drain_stop_ns=None, split='DEV_MODEL_EXPERIMENT'):
    """Bind saved plan input only.  Outcomes and profile sampling are absent."""
    if recipe.get('device', 'A24') != 'A24':
        raise ValueError('only A24 recipes supported')
    service = _integer(recipe['service_cutoff_ns'], 'service stop', 1)
    end = _integer(recipe['sensor_end_ns'], 'observation end', service)
    # The predecessor completes through sensor_end.  A 150 s drain is an explicit
    # caller override, never silently substituted for the A24 210 s contract.
    drain = end if drain_stop_ns is None else _integer(drain_stop_ns, 'drain stop', service)
    if drain > end:
        raise ValueError('drain exceeds observed window')
    requests = []; ids = set(); ordinals = set()
    for q in recipe['requests']:
        rid = q.get('id', q.get('request_id')); ordinal = _integer(q['ordinal'], 'ordinal')
        if not isinstance(rid, str) or not rid or rid in ids or ordinal in ordinals:
            raise ValueError('nonempty unique request IDs and ordinals required')
        ids.add(rid); ordinals.add(ordinal)
        arrival = _integer(q.get('arrival_ns', q.get('scheduled_arrival_ns')), 'arrival')
        relative = _integer(q.get('deadline_offset_ns', q.get('relative_deadline_ns')), 'relative deadline')
        deadline = _integer(q['deadline_ns'], 'deadline')
        if arrival + relative != deadline:
            raise ValueError('absolute/relative deadline mismatch')
        image = q.get('input_sha256', recipe.get('input_image_sha256'))
        if recipe.get('input_image_sha256') is not None and image != recipe['input_image_sha256']:
            raise ValueError('request image binding differs from recipe')
        requests.append({'request_id': rid, 'ordinal': ordinal, 'task': _task(q['task']),
                         'priority': _priority(q['priority']),
                         'burst_index': _integer(q.get('group', q.get('burst_index', -1)), 'group', -1),
                         'scheduled_arrival_ns': arrival, 'deadline_ns': deadline,
                         'relative_deadline_ns': relative, 'input_sha256': image,
                         'tensor_sha256': q.get('tensor_sha256')})
    if not requests:
        raise ValueError('empty planned inputs')
    return {'scenario_id': recipe['label'], 'device': 'A24', 'bank': recipe['bank'], 'prep': 'NONE',
            'split': split, 'requests': sorted(requests, key=lambda r: (r['ordinal'], r['request_id'])),
            'service_stop_ns': service, 'drain_stop_ns': drain, 'observation_end_ns': end,
            'policy_id': 'DYNAMIC_REGISTERED_SCHEDULER', 'clock_axis': 'common_relative_ns',
            'wait_contract': None, 'wait_overrun_ns': recipe.get('wait_overrun_ns', 0),
            'source_recipe_sha256': digest(recipe), 'source_session_id': recipe.get('session_id'),
            'input_seed': recipe.get('input_seed'), 'input_image_sha256': recipe.get('input_image_sha256'),
            'source_response_by_task': dict(RESPONSE_BY_TASK)}


def sample(profile, scenario, request, route, seed=0, mode='SAMPLED', protocol='SERIAL'):
    """Return a whole hidden draw; never put this selected vector in policy obs.

    Keyed CRN excludes policy, dispatch time, realized AP, completion and overlap.
    Selection preserves all five adjacent intervals jointly.  MEDOID is one
    observed vector, not the vector of individually averaged/median phases.
    """
    _integer(seed, 'sample seed')
    if mode not in ('SAMPLED', 'MEDOID'):
        raise ValueError('timing mode must be SAMPLED or MEDOID')
    if scenario.get('device', 'A24') != 'A24' or scenario.get('prep', 'NONE') != 'NONE':
        raise ValueError('unsupported device/preparation context')
    task = _task(request['task']); _priority(request['priority'])
    p = _pool(profile, scenario['bank'], task, route, protocol)
    samples = p['samples']
    if mode == 'SAMPLED':
        key = [seed, scenario['bank'], scenario.get('prep', 'NONE'), request['ordinal'],
               task, route, protocol, request.get('input_sha256'), request.get('tensor_sha256')]
        selected = samples[int(digest(key), 16) % len(samples)]
    else:
        target = _median_ns([s['offsets_ns']['lane_available_ns'] for s in samples])
        selected = min(samples, key=lambda s: (abs(s['offsets_ns']['lane_available_ns'] - target), s['sample_id']))
    for binding in ('input_sha256', 'tensor_sha256'):
        if request.get(binding) is not None and request[binding] != selected[binding]:
            raise ValueError('UnsupportedContext: request ' + binding + ' differs from exact pool')
    result = copy.deepcopy(selected)
    result['selection'] = {'mode': mode, 'seed': seed, 'support_requests': p['support_requests'],
                           'support_sessions': p['support_sessions'],
                           'policy_dependent': False, 'whole_vector': True}
    return result


def nominal_estimates(profile, scenario, protocol='SERIAL'):
    """Public distribution summaries independent of the selected hidden draw.

    Energy proxy stays null: timing alone cannot identify Joules or temperature.
    A separately registered A24 cost adapter may add a qualified proxy.  Do not
    replace missing energy with free execution or S26 coefficients.
    """
    out = {}
    for request in scenario['requests']:
        estimates = {}
        task = _task(request['task'])
        for route in available_routes(profile, scenario['bank'], task, request['priority'], protocol):
            p = _pool(profile, scenario['bank'], task, route, protocol)
            response = RESPONSE_BY_TASK[task]
            for binding in ('input_sha256', 'tensor_sha256'):
                if request.get(binding) is not None and any(s[binding] != request[binding] for s in p['samples']):
                    raise ValueError('nominal source binding mismatch: ' + binding)
            estimates[route] = {'occupancy_ns': _median_ns([s['offsets_ns']['lane_available_ns'] for s in p['samples']]),
                                'response_ns': _median_ns([s['offsets_ns'][response] for s in p['samples']]),
                                'energy_proxy_j': None, 'thermal_proxy': None,
                                'support_requests': p['support_requests'], 'support_sessions': p['support_sessions'],
                                'response_boundary': response,
                                'estimate_basis': 'DEV empirical marginal medians; not hidden draw or joint phase vector'}
        if not estimates:
            raise ValueError('No measured route for request ' + request['request_id'])
        out[request['request_id']] = estimates
    return out


def legal_overlap(active, task, route, *, serial=False):
    """Pure occupancy legality. active is iterable of (task, requested route)."""
    active = [(_task(t), r) for t, r in active]
    candidate = (_task(task), route)
    if candidate not in {('C', 'CPU'), ('C', 'GPU'), ('D', 'CPU')}:
        return False
    if any(r == route for _, r in active) or len(active) >= (1 if serial else 2):
        return False
    return not active or frozenset(active + [candidate]) in ALLOWED_PAIRS
