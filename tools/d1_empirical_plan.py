"""Host-only empirical protocol amendment. Never executes ADB or a simulator.

The plan is intentionally non-executable until within-session transition telemetry
and prospective tail precision are resolved. Old prediction acceptance is untouched.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import random
import statistics
import uuid

from tools import d1_telemetry_v4 as v

PROTOCOL = 'empirical-calibration-plan-v1'
BLOCK = 'joint-empirical-session-v1'
SEED = 2026092101
CELLS = ['classification/CPU', 'classification/GPU', 'detection/CPU', 'detection/GPU']
FAMILIES = ['solo/' + c for c in CELLS] + [
    'transition/' + t + '/' + d for t in ('classification', 'detection')
    for d in ('CPU_to_GPU', 'GPU_to_CPU')] + ['resident_cpu_serial', 'resident_corun']
STATES = ['cold_first', 'early_after_cold', 'stabilization', 'warm_candidate']
SCHEMA = Path(__file__).with_name('schemas') / 'empirical-calibration-plan-v1.schema.json'


def uid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, '/'.join(map(str, (PROTOCOL,) + parts))))


def design_size(evidence):
    """Exploratory mean precision proxy; explicitly NOT a P95 power calculation."""
    cvs = [x['cv'] for x in evidence['variability'].values()]
    worst = max(cvs)
    even = lambda n: 2 * math.ceil(n / 2)
    minimum = even(max(4, math.ceil((1.96 * worst / .35) ** 2)))
    recommended = even(max(minimum, math.ceil((1.96 * worst / .25) ** 2)))
    dropout = evidence['dropout_upper95']
    return dict(worst_session_cv=worst, minimum_per_family_phase=minimum,
                recommended_per_family_phase=recommended,
                selected_per_family_phase=minimum,
                rationale='bounded exploratory acquisition; approval precision not guaranteed',
                mean_precision_proxy=[.35, .25],
                p95_one_sided_rank_minimum=math.ceil(math.log(.05) / math.log(.95)),
                dropout_proxy=dropout,
                attempt_cap_per_family_phase=math.ceil(minimum / (1 - dropout)),
                retry='no automatic retries; failed attempt retained, unused reserve UUID only',
                paired_power='unknown: old controls confounded; one v4 pair has no variance',
                minimum_total=minimum * 20, recommended_total=recommended * 20,
                maximum_device_seconds=120, host_overhead_budget_seconds=30)


def criteria():
    return dict(request_PI_required=False, scheduler_uses_PI=False,
                artifact_completeness=1, output_equivalence=1,
                state_cell_coverage=1, paired_completeness=1,
                median_relative_drift_max=.10, p95_relative_drift_max=.20,
                normalized_wasserstein_max=.10, deadline_CDF_difference_max=.05,
                bootstrap_confidence=.95, bootstrap_replicates=2000,
                median_relative_full_CI_width_max=.20,
                p95_relative_full_CI_width_max=.40,
                bootstrap_unit='session within family; pair for paired contrast',
                simultaneous_inference=False,
                missing_or_underpowered='INCOMPLETE; no threshold widening or optional stopping',
                effect_claim='only paired independent validation CI excluding zero; exploratory multiplicity disclosed')


def build_plan(evidence, registry, pins, seed=SEED):
    sizes = design_size(evidence)
    n = sizes['selected_per_family_phase']
    cap = sizes['attempt_cap_per_family_phase']
    entries = []
    for phase in ('calibration', 'validation'):
        for i in range(cap):
            order = 'AB' if (i + (seed % 2)) % 2 == 0 else 'BA'
            families = FAMILIES[:8].copy()
            random.Random(f'{seed}/{phase}/{i}').shuffle(families)
            families += FAMILIES[8:] if order == 'AB' else FAMILIES[8:][::-1]
            for family in families:
                sid = uid(seed, phase, i, family)
                paired = family.startswith('resident_')
                transition = family.startswith('transition/')
                entries.append(dict(session_id=sid, phase=phase, family=family,
                    replicate=i, reserve=i >= n, output_root='sessions/' + sid,
                    seed=int(v.sha([seed, phase, i])[:8], 16),
                    pair_id=uid(seed, phase, i, 'pair') if paired else None,
                    pair_order=order if paired else None,
                    task_mix=['classification', 'detection'] if paired else [family.split('/')[1]],
                    states=STATES.copy(), thermal_gate=0, memory_contract=v.MEMORY,
                    warmup_per_runtime=6, invocations_per_runtime=12,
                    arrivals_ms=[0] * (12 if paired else 6),
                    priorities='classification urgent/detection normal' if paired else 'normal',
                    input_schedule='canonical image 00575b9132bb3746 repeated; image-specific scope',
                    deadline_ns=None, setup_outside_active=True,
                    runtime_lifecycle='close source then construct target in same session' if transition else 'resident until workload end',
                    execution_supported=not transition,
                    telemetry='task-profile-v4', maximum_duration_ms=120000))
    return dict(protocol=PROTOCOL, schema_version=1, seed=seed, sizes=sizes,
                status='EMPIRICAL_CALIBRATION_PLAN_INCOMPLETE', device_execution_allowed=False,
                blockers=['within-session transition path absent in pinned v4 APK',
                          'cold-state population P95 precision not established by bounded design',
                          'fair paired variance/effect size unavailable; no superiority power claim'],
                pins=pins, registry_sha256=v.sha(registry), criteria=criteria(),
                state_definition=dict(cold_first=[1], early_after_cold=[2], stabilization=[3, 4, 5, 6],
                    warm_candidate=[7, 8, 9, 10, 11, 12], warm_qualified=False,
                    qualification='calibration session-bootstrap CI of median(inv10..12)/median(inv7..9) inside [0.9,1.1] for every cell/origin; otherwise no warm support; no K search'),
                deadline=dict(status='calibration_pending', fit_phase='calibration_only',
                    urgent_quantiles=[.50, .75, .90, .95], normal_quantiles=[.90, .95, .99],
                    cold_included=True, population='equal-session weighted ready-to-output and worker-occupancy separately by task/context; cold-start adds setup once',
                    selection='publish all candidates; no best deadline selection',
                    sensitivity_multipliers=[.75, 1., 1.25],
                    primary='urgent Q90 and normal Q95; never pooled across tasks',
                    discrimination='calibration matched arms: at least one candidate has CDF strictly between .1 and .9; otherwise pending, no range extension'),
                entries=entries)


def validate_plan(plan, evidence, registry, pins):
    import jsonschema
    jsonschema.validate(plan, v.read(SCHEMA))
    if plan != build_plan(evidence, registry, pins, plan['seed']):
        raise ValueError('frozen design altered: cells/states/pairs/split/criteria/pins')
    sessions = [e['session_id'] for e in plan['entries']]
    if len(sessions) != len(set(sessions)) or set(sessions) & set(registry['sessions']):
        raise ValueError('consumed data or calibration/validation leakage')
    return True


def make_block(root, expected_manifest_hash, delegate_log, registry):
    """Import original files, never caller-assembled setup/active/memory fields."""
    root = Path(root)
    receipt = v.validate(root, expected_manifest_hash, delegate_log,
                         registry['sessions'] + registry['requests'], registry['traces'])
    manifest = v.read(root / 'manifest.json')
    if manifest['purpose'] != 'instrumentation_calibration':
        raise ValueError('smoke/old data is development only')
    events = v.read(root / 'events.json')
    return dict(protocol=BLOCK, session_id=manifest['session_id'],
                source_provenance_sha256=v.digest(root / 'provenance.json'),
                manifest_sha256=expected_manifest_hash, manifest=manifest,
                events=events, receipt=receipt,
                terminal_outcome=v.read(root / 'summary.json')['status'],
                interpretation='whole session; setup referenced once per runtime; no independent field sampling')


def validate_block(block, root, expected_manifest_hash, delegate_log, registry):
    import jsonschema
    jsonschema.validate(block, v.read(SCHEMA.with_name('joint-empirical-session-v1.schema.json')))
    if block != make_block(root, expected_manifest_hash, delegate_log, registry):
        raise ValueError('joint identity/setup/active/environment recombination or mutation')
    return True


def validate_dataset(blocks, plan, phase, registry, other_phase_ids=()):
    """Coverage approval only after each block's original-source validation.

    Failed blocks remain in the ledger/denominator but cannot fill successful
    empirical support slots. A missing transition makes this version fail closed.
    """
    if phase not in ('calibration','validation'): raise ValueError('phase')
    expected={e['session_id']:e for e in plan['entries'] if e['phase']==phase and not e['reserve']}
    ids=[b['session_id'] for b in blocks]
    if len(ids)!=len(set(ids)) or set(ids)&(set(registry['sessions'])|set(other_phase_ids)):
        raise ValueError('consumed/leaked/replayed session')
    if set(ids)!=set(expected): raise ValueError('cell/state/paired coverage incomplete')
    for b in blocks:
        if b['terminal_outcome']!='succeeded': raise ValueError('failed block retained, approval incomplete')
        if not expected[b['session_id']]['execution_supported']: raise ValueError('transition unsupported')
    return True


def draw_block(blocks, seed, index):
    """Structural no-clock sampler; callers must validate original source first."""
    if not blocks or len({b['session_id'] for b in blocks}) != len(blocks):
        raise ValueError('empty or duplicate session pool')
    return copy.deepcopy(sorted(blocks, key=lambda b: b['session_id'])[
        int(v.sha([seed, index]), 16) % len(blocks)])


def bootstrap_session_quantiles(session_values, seed=SEED, repetitions=2000):
    """Equal session weights via one P50/P95 per session. Not request-iid CI."""
    import numpy as np
    if len(session_values) < 2 or any(not x for x in session_values):
        raise ValueError('insufficient independent sessions')
    if any(not math.isfinite(y) or y <= 0 for x in session_values for y in x):
        raise ValueError('nonpositive/nonfinite service time')
    summaries = np.array([[np.quantile(x, .5), np.quantile(x, .95)] for x in session_values])
    rng = np.random.default_rng(seed)
    estimates = np.mean(summaries[rng.integers(len(summaries), size=(repetitions, len(summaries)))], axis=1)
    point = summaries.mean(axis=0)
    bounds = np.quantile(estimates, [.025, .975], axis=0)
    def mixture(indices):
        values=np.concatenate([session_values[i] for i in indices])
        weights=np.concatenate([np.full(len(session_values[i]),1/len(session_values[i])) for i in indices])
        order=np.argsort(values); values=values[order];cdf=np.cumsum(weights[order]);cdf/=cdf[-1]
        return values[np.minimum(np.searchsorted(cdf,[.5,.95]),len(values)-1)]
    mix_point=mixture(range(len(session_values)))
    mix_draws=np.array([mixture(rng.integers(len(session_values),size=len(session_values))) for _ in range(repetitions)])
    mix_ci=np.quantile(mix_draws,[.025,.975],axis=0)
    return dict(estimand='mean of per-session quantiles; not pooled population P95',
                sessions=len(session_values), point=point.tolist(), CI95=bounds.tolist(),
                relative_full_width=((bounds[1] - bounds[0]) / point).tolist(),
                equal_session_mixture=dict(point=mix_point.tolist(),CI95=mix_ci.tolist(),
                    relative_full_width=((mix_ci[1]-mix_ci[0])/mix_point).tolist(),
                    caveat='cluster percentile bootstrap; sparse cold tail may be unidentifiable, not a coverage guarantee'))


def distribution_gate(calibration, validation, deadlines, seed=SEED):
    """Read-only predeclared per-stratum assessment; each list item is one session.

    This is service distribution validation, never a scheduling simulation. The
    caller must first enforce source provenance, strata and session disjointness.
    """
    import numpy as np
    from scipy.stats import wasserstein_distance
    c=criteria()
    if min(len(calibration),len(validation))<8 or not deadlines:
        raise ValueError('insufficient session count or frozen deadline candidates')
    if any(not math.isfinite(d) or d<=0 for d in deadlines): raise ValueError('invalid deadline')
    ca=bootstrap_session_quantiles(calibration,seed,c['bootstrap_replicates'])['equal_session_mixture']
    va=bootstrap_session_quantiles(validation,seed+1,c['bootstrap_replicates'])['equal_session_mixture']
    def flatten(sessions):
        return np.concatenate(sessions),np.concatenate([np.full(len(s),1/(len(s)*len(sessions))) for s in sessions])
    x,wx=flatten(calibration);y,wy=flatten(validation)
    drift=[abs(a-b)/a for a,b in zip(ca['point'],va['point'])]
    w=float(wasserstein_distance(x,y,wx,wy)/ca['point'][0])
    cdf=max(abs(float(wx[x<=d].sum()-wy[y<=d].sum())) for d in deadlines)
    widths=[max(a,b) for a,b in zip(ca['relative_full_width'],va['relative_full_width'])]
    sparse_tail=any(all(len(s)==1 for s in data) and len(data)<59 for data in (calibration,validation))
    passed=(drift[0]<=c['median_relative_drift_max'] and drift[1]<=c['p95_relative_drift_max']
            and w<=c['normalized_wasserstein_max'] and cdf<=c['deadline_CDF_difference_max']
            and widths[0]<=c['median_relative_full_CI_width_max'] and widths[1]<=c['p95_relative_full_CI_width_max']
            and not sparse_tail)
    return dict(passed=passed,median_relative_drift=drift[0],p95_relative_drift=drift[1],
                normalized_wasserstein=w,deadline_CDF_difference=cdf,
                relative_CI_full_width=widths,sparse_cold_tail=sparse_tail,
                calibration_sessions=len(calibration),validation_sessions=len(validation),
                scope='service distribution only; queue-level policy fidelity not inferred')


def dry_run(plan):
    return dict(protocol=PROTOCOL, plan_sha256=v.sha(plan), device_commands=[],
                dispatches=0, simulated_completions=0, execution_allowed=False,
                status=plan['status'], blockers=plan['blockers'])


def native_manifest(entry, templates):
    """Compile supported workload only; never pretend separate sessions transition."""
    if not entry['execution_supported']: raise ValueError('transition runner absent')
    family = entry['family']
    catalog = {k: spec for m in templates for k, spec in m['models'].items()}
    m = copy.deepcopy(templates[0])
    if family.startswith('solo/'):
        keys = [family.removeprefix('solo/').replace('/', '_')]
        configuration = 'lifecycle'
    else:
        configuration = family
        keys = ['classification_CPU', 'detection_' + ('CPU' if family == 'resident_cpu_serial' else 'GPU')]
    sid = entry['session_id']
    m.update(session_id=sid, purpose='instrumentation_calibration', configuration=configuration,
             seed=entry['seed'], warmup_per_runtime=6, models={}, runtimes=[], warmup_requests=[], requests=[],
             paired=dict(pair_id=entry['pair_id'] or uid(sid, 'standalone'),
                         order=entry['pair_order'] or 'AB',
                         arm='standalone' if len(keys)==1 else ('A' if family=='resident_cpu_serial' else 'B')))
    for i, key in enumerate(keys):
        m['models'][key] = copy.deepcopy(catalog[key])
        m['models'][key]['identity']['session_id'] = sid
        # Fixed design timestamp is not evidence of device execution or freshness.
        m['models'][key]['identity']['created_utc'] = '2026-09-21T00:00:00Z'
        m['runtimes'].append(dict(model_key=key, runtime_id=uid(sid, key, 'runtime'),
                                  worker_id=0 if configuration=='resident_cpu_serial' else i))
        for j in range(12):
            q=dict(model_key=key, request_id=uid(sid, key, j), sample_id=m['images'][0]['sample_id'],
                   priority='urgent' if j>=6 and len(keys)==2 and i==0 else 'normal', offset_ms=0)
            m['warmup_requests' if j<6 else 'requests'].append(q)
    if len(keys)==2:
        # Interleave task arrivals with fixed tie order; same sequence in both arms.
        m['requests'].sort(key=lambda q:(int(next(j for j in range(6,12) if q['request_id']==uid(sid,q['model_key'],j))), keys.index(q['model_key'])))
    v.manifest(m)
    return m


def generate(development, smoke, output):
    output.mkdir(parents=True, exist_ok=False)
    old = v.read(development / 'development_registry.json')
    smoke_plan = v.read(smoke / 'smoke_plan_v2/plan.json')
    smoke_receipts = v.read(smoke / 'smoke_result.json')['receipts']
    registry = dict(protocol='consumed-empirical-registry-v1',
        sessions=sorted(old['consumed_sessions'] + [x['session_id'] for x in smoke_receipts]),
        requests=sorted(old['requests'] + [s['request_id'] for r in smoke_receipts for s in r['samples']]),
        traces=sorted(old['fingerprints'] + [old['diagnostic_fingerprint']] + [r['trace_fingerprint'] for r in smoke_receipts]),
        role='consumed development only; old independent holdout failure unchanged')
    evidence = v.read(development / 'sample_size.json')
    gate = v.read(smoke / 'host_gate.json')
    for p, h in gate['apk_sha256'].items():
        if v.digest(Path(p)) != h: raise ValueError('APK changed')
    for p, h in gate['source_hashes'].items():
        if v.digest(Path(p)) != h: raise ValueError('tested telemetry source changed')
    pins = dict(apk=smoke_plan['apk_sha256'], tested_source=gate['source_hashes'],
                evidence={str(development / n): v.digest(development / n) for n in
                          ('development_registry.json', 'development_rows.json', 'sample_size.json')},
                smoke_plan_sha256=v.digest(smoke / 'smoke_plan_v2/plan.json'),
                template_manifests={str(Path(e['manifest'])): e['manifest_sha256'] for e in smoke_plan['entries']},
                analysis_sha256=v.digest(Path(__file__)), schema_sha256=v.digest(SCHEMA),
                block_schema_sha256=v.digest(SCHEMA.with_name('joint-empirical-session-v1.schema.json')))
    plan = build_plan(evidence, registry, pins)
    validate_plan(plan, evidence, registry, pins)
    rows = v.read(development / 'development_rows.json')
    groups = {}
    for row in rows:
        key = row['cell'] + '|' + row['phase']
        groups.setdefault(key, {}).setdefault(row['session_id'], []).append(row['active_service_ns'])
    uncertainty = {k: bootstrap_session_quantiles(list(s.values())) for k, s in sorted(groups.items()) if len(s) >= 2}
    templates = [v.read(Path(e['manifest'])) for e in smoke_plan['entries']]
    natives = {e['session_id']: native_manifest(e, templates) for e in plan['entries'] if e['execution_supported']}
    for phase in ('calibration','validation'):
        for i in range(plan['sizes']['attempt_cap_per_family_phase']):
            arms = [e for e in plan['entries'] if e['phase']==phase and e['replicate']==i and e['pair_id']]
            a=next(e for e in arms if e['family']=='resident_cpu_serial')
            b=next(e for e in arms if e['family']=='resident_corun')
            v.paired(natives[a['session_id']], natives[b['session_id']])
    products = {'plan.json': plan, 'consumed_registry.json': registry, 'design_evidence.json': evidence,
                'legacy_uncertainty.json': uncertainty, 'no_op.json': dry_run(plan),
                'native_manifest_catalog.json': natives,
                'manifest_template.json': dict(protocol=PROTOCOL, telemetry=v.PROTOCOL,
                    entry=plan['entries'][0], native_manifest_required=True,
                    status='logical template, not an Activity manifest; transition compiler missing')}
    for name, value in products.items(): (output / name).write_bytes(v.canonical(value))
    freeze = dict(protocol='empirical-plan-freeze-v1', files={n: v.digest(output / n) for n in products},
                  analysis_sha256=v.digest(Path(__file__)), schema_sha256=v.digest(SCHEMA),
                  block_schema_sha256=v.digest(SCHEMA.with_name('joint-empirical-session-v1.schema.json')),
                  status=plan['status'], approval='design only; no device execution')
    (output / 'freeze.json').write_bytes(v.canonical(freeze))
    return v.digest(output / 'freeze.json')


def verify(output, expected):
    if v.digest(output / 'freeze.json') != expected: raise ValueError('freeze immutability')
    freeze = v.read(output / 'freeze.json')
    if freeze['analysis_sha256'] != v.digest(Path(__file__)) or freeze['schema_sha256'] != v.digest(SCHEMA):
        raise ValueError('stale analysis/schema')
    if freeze['block_schema_sha256'] != v.digest(SCHEMA.with_name('joint-empirical-session-v1.schema.json')):
        raise ValueError('stale block schema')
    for name, h in freeze['files'].items():
        if Path(name).name != name or v.digest(output / name) != h: raise ValueError('frozen manifest mutation')
    plan = v.read(output / 'plan.json')
    for p,h in {**plan['pins']['tested_source'], **plan['pins']['evidence'], **plan['pins']['template_manifests']}.items():
        if v.digest(Path(p))!=h: raise ValueError('stale source/evidence/template')
    validate_plan(plan, v.read(output / 'design_evidence.json'), v.read(output / 'consumed_registry.json'), plan['pins'])
    return dry_run(plan)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['generate', 'verify', 'dry-run'])
    p.add_argument('--development', type=Path); p.add_argument('--smoke', type=Path)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--expected-sha256')
    a = p.parse_args()
    result = generate(a.development, a.smoke, a.output) if a.command == 'generate' else verify(a.output, a.expected_sha256)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
