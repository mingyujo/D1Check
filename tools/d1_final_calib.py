"""Prospective bounded service calibration planning; never scheduling simulation."""
import copy
import datetime as dt
from pathlib import Path
import uuid

from tools.d1_service_model import sha, ordered
from tools.d1_task_profile import read
from tools.d1_sim_prepare import canonical

SEED = 20260920


def save_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(canonical(value))


def recipes(source, samples, seed=SEED):
    """Extend the documented recipes only for mandated early/warm observations."""
    source = Path(source)
    images = ordered(samples, seed)
    if len(images) != 20 or len(set(images)) != 20:
        raise ValueError('the existing 20 verified images are required')
    templates = {}
    for task in ('classification', 'detection'):
        base = read(source / f'transition_{task}.json')
        base['requests'] = [copy.deepcopy(q) for q in base['requests'] for _ in range(3)]
        templates['transition_' + task] = base
    for cpu_task, gpu_task in (('classification', 'detection'), ('detection', 'classification')):
        name = ('corun_classification_CPU_detection_GPU' if cpu_task == 'classification'
                else 'corun_classification_GPU_detection_CPU')
        base = read(source / (name + '.json'))
        # Retain the original 30s/500ms paired arrivals; add immediate early calls.
        early = copy.deepcopy(base['requests'][:2])
        base['requests'][2:2] = early
        templates[name] = base
    for task in ('classification', 'detection'):
        for backend in ('CPU', 'GPU'):
            qs = [dict(model_key=f'{task}_{backend}', sample_id=s, priority=('normal' if i % 2 else 'urgent'),
                       role='holdout', worker=0, offset_ms=0)
                  for i, s in enumerate(images[:2] + images)]
            templates[f'solo_{task}_{backend}'] = dict(purpose='holdout', allowed_concurrency=1, requests=qs)
    control = copy.deepcopy(templates['corun_classification_CPU_detection_GPU'])
    control['allowed_concurrency'] = 1
    control['purpose'] = 'solo'
    for q in control['requests']:
        q['model_key'] = q['model_key'].replace('_GPU', '_CPU')
        q['worker'] = 0
    templates['CPU_only_control'] = control
    return templates


def validate_recipe(recipe):
    qs = recipe['requests']
    if not 1 <= len(qs) <= 48 or recipe['allowed_concurrency'] not in (1, 2):
        raise ValueError('bounded recipe required')
    offsets = [q['offset_ms'] for q in qs]
    if offsets != sorted(offsets) or not all(0 <= x <= 60000 for x in offsets):
        raise ValueError('arrival order/bound')
    if any(q['worker'] not in range(recipe['allowed_concurrency']) for q in qs):
        raise ValueError('worker budget')
    return True


def make_plan(source, samples):
    templates = recipes(source, samples)
    a = ['transition_classification', 'transition_detection',
         'corun_classification_GPU_detection_CPU', 'corun_classification_CPU_detection_GPU']
    b = [f'solo_{t}_{k}' for t in ('classification', 'detection') for k in ('CPU', 'GPU')]
    b = [name for name in b + a for _ in range(2)]
    entries = []
    for phase, names in [('A', a), ('B', b), ('C', ['CPU_only_control'] * 2)]:
        for index, name in enumerate(names):
            recipe = copy.deepcopy(templates[name])
            if phase == 'B':
                for q in recipe['requests']:
                    q['role'] = 'holdout'
            validate_recipe(recipe)
            entries.append(dict(phase=phase, index=index, name=name, session_id=str(uuid.uuid4()),
                                recipe=recipe, recipe_sha256=sha(recipe)))
    return dict(protocol='service-final-measurement-plan-v1', created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                seed=SEED, sessions=entries, maximum_duration_ms=120000,
                thermal_start_status=0, thermal_model_scope=[0],
                battery_start_range_deci_c=None,
                battery_range_note='no previously frozen numeric battery gate; record continuously, thermal status 0 required; paired thermal mismatch reported',
                memory_rule='record /proc/meminfo before/during/after plus 500ms app PSS; existing candidate guard only, no true peak claim',
                deadline='calibration_pending', retry='never replay Activity/session; at most two read-only reconnect inventories',
                control_limitation='unchanged probe serial worker owns one runtime: task changes recreate it; not a warm two-resident-model CPU control',
                change_rationale='documented minimum: transition triplets add early and warm; co-run adds immediate early pair while keeping all original arrivals; solo cold+early+20warm')


def check_entry(plan, entry):
    matches = [s for s in plan['sessions'] if s['session_id'] == entry['session_id']]
    if len(matches) != 1 or matches[0] != entry or sha(entry['recipe']) != entry['recipe_sha256']:
        raise ValueError('unplanned or changed workload')
    validate_recipe(entry['recipe'])
    return True
