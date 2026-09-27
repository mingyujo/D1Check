"""Screen existing exploratory policy results without rerunning the event model."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/results/arrival_diagnostic_02'
OUTPUT = ROOT / 'docs/results/arrival_policy_screen_01'
POLICIES = ('CPU_URGENT', 'FIXED_SPLIT', 'B2_PC', 'B3_SOLO_EFT_PC', 'P_PAIR_COST_PC')
METRICS = ('urgent_p95_ms', 'urgent_not_timely_rate', 'normal_mean_ms',
           'normal_not_timely_rate', 'unfinished')
COST_POLICIES = ('CPU_URGENT', 'B2_PC', 'B3_SOLO_EFT_PC')
HORIZON_NS = 120_000_000_000


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def digest_text(path):
    """Hash canonical UTF-8 text so Git checkout CRLF conversion does not break the bundle."""
    return hashlib.sha256(path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()


def dominates(a, b):
    return all(a[k] <= b[k] for k in METRICS) and any(a[k] < b[k] for k in METRICS)


def screen(rows):
    grouped = defaultdict(dict)
    for raw in rows:
        if raw['policy'] == 'P_PAIR_COST_PC' and float(raw['predicted']) != 1.5:
            continue
        key = (raw['scenario'], float(raw['realized']), int(raw['seed']))
        policy = raw['policy']
        if policy not in POLICIES or policy in grouped[key]:
            raise ValueError(f'unsupported or duplicated policy: {key}/{policy}')
        row = {k: float(raw[k]) for k in METRICS}
        row['unfinished'] = int(raw['unfinished'])
        for field in ('planned', 'urgent_planned', 'normal_planned'):
            row[field] = int(raw[field])
        if (row['planned'], row['urgent_planned'], row['normal_planned']) != (24, 6, 18):
            raise ValueError(f'inconsistent denominator: {key}/{policy}')
        for priority, count in (('urgent', 6), ('normal', 18)):
            rate = row[f'{priority}_not_timely_rate']
            if abs(rate * count - round(rate * count)) > 1e-8:
                raise ValueError(f'nonintegral deadline misses: {key}/{policy}')
        grouped[key][policy] = row
    if len(grouped) != 45 or any(set(group) != set(POLICIES) for group in grouped.values()):
        raise ValueError('incomplete scenario/realized/seed comparison')
    if any({(v['planned'], v['urgent_planned'], v['normal_planned']) for v in group.values()} != {(24, 6, 18)}
           for group in grouped.values()):
        raise ValueError('unequal workload')
    output = []
    for scenario in ('low', 'queue', 'burst'):
        for realized in (1., 1.5, 2.):
            seeds = [grouped[scenario, realized, seed] for seed in range(201, 206)]
            means = {policy: {k: sum(seed[policy][k] for seed in seeds) / 5 for k in METRICS}
                     for policy in POLICIES}
            for policy in POLICIES:
                values = [seed[policy] for seed in seeds]
                dominators = [other for other in POLICIES if other != policy and
                              dominates(means[other], means[policy])]
                nondominated_seeds = sum(not any(dominates(seed[other], seed[policy])
                                             for other in POLICIES if other != policy)
                                         for seed in seeds)
                output.append(dict(scenario=scenario, realized=realized, policy=policy,
                    predicted=1.5 if policy == 'P_PAIR_COST_PC' else '',
                    seed_count=5, planned=120, urgent_planned=30, normal_planned=90,
                    unfinished=sum(v['unfinished'] for v in values),
                    urgent_p95_mean_ms=means[policy]['urgent_p95_ms'],
                    urgent_p95_min_ms=min(v['urgent_p95_ms'] for v in values),
                    urgent_p95_max_ms=max(v['urgent_p95_ms'] for v in values),
                    normal_mean_response_ms=means[policy]['normal_mean_ms'],
                    normal_response_min_ms=min(v['normal_mean_ms'] for v in values),
                    normal_response_max_ms=max(v['normal_mean_ms'] for v in values),
                    urgent_miss_count=sum(round(v['urgent_not_timely_rate'] * 6) for v in values),
                    normal_miss_count=sum(round(v['normal_not_timely_rate'] * 18) for v in values),
                    mean_frontier=not dominators, nondominated_seeds=nondominated_seeds,
                    dominated_by=';'.join(dominators)))
    return output


def save(rows, output, source=SOURCE):
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'policy_screen.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    payload = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    template = (ROOT / 'tools/assets/d1_arrival_policy_screen.html').read_text(encoding='utf-8')
    (output / 'dashboard.html').write_text(template.replace('/*__ROWS__*/', f'const ROWS={payload};'), encoding='utf-8')
    paths = [source / 'interference_metrics.csv', source / 'energy_boundaries.csv',
             source / 'ap_sensitivity.csv', source / 'CONFIG.json']
    (output / 'SOURCE_HASHES.json').write_text(json.dumps({str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p):hashlib.sha256(p.read_bytes()).hexdigest()
                                                    for p in paths}, indent=2) + '\n', encoding='utf-8')


def state_name(ledger_state):
    if ledger_state == 'idle':
        return 'idle'
    members = sorted(':'.join(item.split(':')[:2]) for item in ledger_state.split('+'))
    if len(members) > 2 or any(item.count(':') != 1 for item in members):
        raise ValueError(f'unsupported occupancy: {ledger_state}')
    return '+'.join(members)


def occupancy(result, scenario, realized, seed, policy):
    from tools import d1_energy_thermal as thermal
    rows = []
    for seg in thermal.ledger_segments(result, HORIZON_NS):
        state = state_name(seg['state'])
        if rows and rows[-1]['state'] == state and math.isclose(rows[-1]['end_s'], seg['start_s'], abs_tol=1e-9):
            rows[-1]['end_s'] = seg['end_s']
        else:
            rows.append(dict(scenario=scenario, realized=realized, seed=seed, policy=policy,
                             start_s=seg['start_s'], end_s=seg['end_s'], state=state))
    if not rows or not math.isclose(sum(r['end_s']-r['start_s'] for r in rows), 120., abs_tol=1e-6):
        raise ValueError('incomplete common 120-second accounting window')
    return rows


def detailed_cost_schedule(source=SOURCE):
    """Replay only 135 selected schedules; reject any mismatch with stored results."""
    from tools import d1_arrival_explore as engine
    from tools import d1_arrival_explore_batch as batch
    bundle = ROOT / 'docs/results/arrival_explore_20260925/input_bundle'
    freeze = json.loads((ROOT / 'docs/results/arrival_explore_20260925/freeze_before_evaluation.json').read_text(encoding='utf-8'))
    estimate = json.loads((bundle / 'estimates.json').read_text(encoding='utf-8'))
    vectors = json.loads((bundle / 'realizations.json').read_text(encoding='utf-8'))
    stored = {(r['scenario'], float(r['realized']), int(r['seed']), r['policy']): r
              for r in read_csv(source / 'interference_metrics.csv') if r['policy'] in COST_POLICIES}
    out = []
    for scenario in ('low', 'queue', 'burst'):
        for realized in (1., 1.5, 2.):
            for seed in range(201, 206):
                for policy in COST_POLICIES:
                    settings = batch.defaults('explore')
                    settings['interference'] = realized
                    settings.update({k: freeze['B2']['explore']['settings'][k]
                                     for k in ('static_map', 'static_parallel')})
                    result = engine.simulate(estimate, vectors, batch.workload(scenario, 'evaluation'),
                                             policy=policy, settings=settings, seed=seed)
                    reference = stored[scenario, realized, seed, policy]
                    m = result['metrics']
                    checks = dict(urgent_p95_ms=m['urgent_p95_ms'], normal_mean_ms=m['normal_mean_ms'],
                                  urgent_not_timely_rate=m['urgent_deadline_violation'],
                                  normal_not_timely_rate=1-m['normal_timely'], unfinished=m['unfinished'])
                    if any(not math.isclose(float(reference[k]), value, abs_tol=1e-6) for k, value in checks.items()):
                        raise ValueError(f'stored metric mismatch: {scenario}/{realized}/{seed}/{policy}')
                    if m['completion'] != 1 or len(result['ledger']) != 24:
                        raise ValueError('unsupported incomplete cost schedule')
                    out.extend(occupancy(result, scenario, realized, seed, policy))
    return out


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def assumed_account(schedule, power_w, ap_equilibrium_c, initial_ap_c=29., tau_s=60.):
    """Whole-device fixed-schedule accounting; these inputs are never inferred measurements."""
    from tools import d1_energy_thermal as thermal
    energy, temperature, peak = 0., initial_ap_c, initial_ap_c
    previous = 0.
    for row in schedule:
        start, end, state = float(row['start_s']), float(row['end_s']), row['state']
        if not math.isclose(start, previous, abs_tol=1e-8) or end < start:
            raise ValueError('gap or overlap in schedule')
        if state not in power_w or state not in ap_equilibrium_c:
            raise ValueError(f'unsupported state: {state}')
        dt = end-start
        energy += dt*power_w[state]
        temperature = thermal.transition(temperature, ap_equilibrium_c[state], tau_s, dt)
        peak = max(peak, temperature)
        previous = end
    if not math.isclose(previous, 120., abs_tol=1e-7):
        raise ValueError('incomplete horizon')
    return energy, peak


def representative_comparisons(schedule, assumptions):
    cases = [('low',1.5),('queue',1.5),('burst',2.)]
    groups = defaultdict(list)
    for row in schedule:
        groups[row['scenario'],float(row['realized']),int(row['seed']),row['policy']].append(row)
    result=[]
    for scenario,realized in cases:
        for policy in COST_POLICIES:
            values=[assumed_account(groups[scenario,realized,seed,policy],assumptions['power_w'],
                                    assumptions['ap_equilibrium_c'],assumptions['initial_ap_c'],
                                    assumptions['tau_s']) for seed in range(201,206)]
            result.append(dict(scenario=scenario,realized=realized,policy=policy,seeds=5,
                               energy_mean_j=sum(x[0] for x in values)/5,
                               energy_min_j=min(x[0] for x in values),energy_max_j=max(x[0] for x in values),
                               ap_peak_mean_c=sum(x[1] for x in values)/5,
                               evidence='PC schedule + unmeasured whole-device power/AP stress inputs'))
    return result


def pair_plane(first, second, power_w):
    """Return ΔE intercept/slopes for independently priced CG_DC and detection CPU+GPU."""
    def durations(rows):
        out=defaultdict(float)
        for r in rows:
            out[r['state']]+=float(r['end_s'])-float(r['start_s'])
        return out
    a,b=durations(first),durations(second)
    x='classification:GPU+detection:CPU'; y='detection:CPU+detection:GPU'
    delta={s:a[s]-b[s] for s in power_w}
    constant=sum(delta[s]*power_w[s] for s in delta if s not in (x,y))
    return constant,delta[x],delta[y]


def pair_plane_examples(schedule, assumptions):
    groups=defaultdict(list)
    for r in schedule:
        groups[r['scenario'],float(r['realized']),int(r['seed']),r['policy']].append(r)
    rows=[]
    for scenario,realized in (('low',1.5),('queue',1.5),('burst',2.)):
        for seed in range(201,206):
            constant,dx,dy=pair_plane(groups[scenario,realized,seed,'B2_PC'],
                                      groups[scenario,realized,seed,'B3_SOLO_EFT_PC'],
                                      assumptions['power_w'])
            rows.append(dict(scenario=scenario,realized=realized,seed=seed,
                             constant_j=constant,cg_dc_slope_s=dx,d_cpu_gpu_slope_s=dy,
                             tied_d_cpu_gpu_w_at_cg_dc_2w=(-constant-2*dx)/dy if abs(dy)>1e-9 else '',
                             evidence='fixed PC schedule; other whole-device state powers held at assumed defaults'))
    return rows


def service_rows(source):
    rows = []
    for r in read_csv(source / 'interference_metrics.csv'):
        if r['policy'] not in POLICIES or (r['policy']=='P_PAIR_COST_PC' and float(r['predicted'])!=1.5):
            continue
        rows.append({k: r[k] for k in ('scenario','realized','seed','policy','urgent_p95_ms',
                    'normal_mean_ms','urgent_not_timely_rate','normal_not_timely_rate',
                    'unfinished','planned','urgent_planned','normal_planned')})
    if len(rows) != 225:
        raise ValueError('five-policy response coverage')
    return rows


def render_bundle(bundle, output, template):
    manifest = json.loads((bundle / 'SOURCE_HASHES.json').read_text(encoding='utf-8'))
    for name, expected in manifest['bundle_files'].items():
        actual = digest_text(bundle / name)
        if actual != expected:
            raise ValueError(f'bundle hash mismatch: {name}')
    service = read_csv(bundle / 'service_metrics.csv')
    schedule = read_csv(bundle / 'occupancy_segments.csv')
    assumptions = json.loads((bundle / 'assumptions.json').read_text(encoding='utf-8'))
    payload = json.dumps(dict(service=service, schedule=schedule, assumptions=assumptions),
                         ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    output.mkdir(parents=True, exist_ok=True)
    html = template.read_text(encoding='utf-8').replace('/*__DATA__*/', f'const DATA={payload};')
    extra = ('thermal_metrics.csv','thermal_assignments.csv','thermal_decisions.csv',
             'thermal_CONFIG.json','thermal_fragment.html')
    if all((bundle/name).exists() for name in extra):
        feedback = dict(metrics=read_csv(bundle/'thermal_metrics.csv'),
                        assignments=read_csv(bundle/'thermal_assignments.csv'),
                        decisions=read_csv(bundle/'thermal_decisions.csv'),
                        config=json.loads((bundle/'thermal_CONFIG.json').read_text(encoding='utf-8')))
        fragment = (bundle/'thermal_fragment.html').read_text(encoding='utf-8')
        fragment = fragment.replace('/*__THERMAL__*/',
            'const THERMAL='+json.dumps(feedback,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';')
        html = html.replace('</main>',fragment+'</main>')
    (output / 'dashboard.html').write_text(html, encoding='utf-8')


def integrated(output=OUTPUT, source=SOURCE):
    bundle = output / 'repro_bundle'
    bundle.mkdir(parents=True, exist_ok=True)
    write_csv(bundle / 'service_metrics.csv', service_rows(source))
    schedule = detailed_cost_schedule(source)
    write_csv(bundle / 'occupancy_segments.csv', schedule)
    states = sorted({r['state'] for r in schedule})
    assumptions = dict(version='arrival-integrated-exploration-v1', source_head='b15526a71557ba0ea7e8fc783120fcd95642e689',
        horizon_s=120, seeds=[201,202,203,204,205], policies=list(COST_POLICIES), all_policies=list(POLICIES), states=states,
        power_w={s:1. if s=='idle' else 2. for s in states},
        ap_equilibrium_c={s:29. if s=='idle' else 34. if '+' not in s else 30. for s in states},
        initial_ap_c=29., tau_s=60.,
        provenance='PC replay of frozen CAL-03 schedules; power/AP coefficients are unmeasured researcher stress assumptions, whole-device absolute W, not device calibration',
        deadlines='request-wise research deadlines: urgent 1.5 s, normal 6 s; not a service SLA',
        limitation='post-hoc accounting, no power/temperature feedback, no BAT model or absolute energy certification')
    (bundle / 'assumptions.json').write_text(json.dumps(assumptions, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    write_csv(output / 'representative_comparisons.csv', representative_comparisons(schedule, assumptions))
    write_csv(output / 'pair_plane_examples.csv', pair_plane_examples(schedule, assumptions))
    template = ROOT / 'tools/assets/d1_arrival_policy_screen.html'
    shutil.copyfile(template, bundle / 'dashboard_template.html')
    shutil.copyfile(Path(__file__), bundle / 'reproduce.py')
    names = ('service_metrics.csv','occupancy_segments.csv','assumptions.json','dashboard_template.html','reproduce.py')
    source_names = [source/'interference_metrics.csv',
                    ROOT/'docs/results/arrival_explore_20260925/input_bundle/estimates.json',
                    ROOT/'docs/results/arrival_explore_20260925/input_bundle/realizations.json',
                    ROOT/'docs/results/arrival_explore_20260925/freeze_before_evaluation.json',
                    ROOT/'tools/d1_arrival_explore.py',ROOT/'tools/d1_energy_thermal.py']
    manifest = dict(hash_contract='SHA-256 of UTF-8 text after CRLF normalization to LF',
                    bundle_files={n:digest_text(bundle/n) for n in names},
                    source_files={str(p.relative_to(ROOT)):digest_text(p) for p in source_names})
    (bundle / 'SOURCE_HASHES.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    render_bundle(bundle, output, bundle / 'dashboard_template.html')
    return schedule, assumptions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--bundle', type=Path, help='standalone relative-path reproduction from copied small bundle')
    parser.add_argument('--template', type=Path)
    parser.add_argument('--attach-thermal', action='store_true',
                        help='attach frozen thermal candidate results without replaying old schedules')
    args = parser.parse_args()
    if args.bundle:
        render_bundle(args.bundle, args.output, args.template or args.bundle/'dashboard_template.html')
        print(f'bundle dashboard -> {args.output / "dashboard.html"}')
        return
    if args.attach_thermal:
        bundle=args.output/'repro_bundle'
        new=ROOT/'docs/results/arrival_thermal_feedback_01/run_v1'
        names={'metrics.csv':'thermal_metrics.csv',
               'assignment_differences.csv':'thermal_assignments.csv',
               'decision_trace.csv':'thermal_decisions.csv',
               'summary.csv':'thermal_summary.csv',
               'paired_differences.csv':'thermal_paired_differences.csv',
               'decision_cost_stress.csv':'thermal_decision_cost_stress.csv',
               'comparison.svg':'thermal_comparison.svg'}
        for original, renamed in names.items():shutil.copyfile(new/original,bundle/renamed)
        shutil.copyfile(ROOT/'docs/results/arrival_thermal_feedback_01/CONFIG.json',bundle/'thermal_CONFIG.json')
        shutil.copyfile(ROOT/'tools/assets/d1_arrival_thermal_fragment.html',bundle/'thermal_fragment.html')
        shutil.copyfile(Path(__file__),bundle/'reproduce.py')
        manifest=json.loads((bundle/'SOURCE_HASHES.json').read_text(encoding='utf-8'))
        for name in (*names.values(),'thermal_CONFIG.json','thermal_fragment.html','reproduce.py'):
            manifest['bundle_files'][name]=digest_text(bundle/name)
        manifest['thermal_source_files']={str(p.relative_to(ROOT)):digest_text(p) for p in
            (ROOT/'tools/d1_arrival_explore.py',ROOT/'tools/d1_arrival_thermal_feedback.py',
             ROOT/'tools/d1_arrival_thermal_feedback_batch.py',
             ROOT/'tools/d1_arrival_thermal_feedback_analysis.py',
             ROOT/'docs/results/arrival_thermal_feedback_01/CONFIG.json')}
        (bundle/'SOURCE_HASHES.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        render_bundle(bundle,args.output,bundle/'dashboard_template.html')
        print(f'frozen feedback comparison attached -> {args.output / "dashboard.html"}')
        return
    rows = screen(read_csv(args.source / 'interference_metrics.csv'))
    save(rows, args.output, args.source)
    integrated(args.output, args.source)
    print(f'{len(rows)} policy/condition summaries -> {args.output}')


if __name__ == '__main__':
    main()
