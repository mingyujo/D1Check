"""Read-only publication integrity and raw-request aggregation check (stdlib only)."""
import csv
import gzip
import hashlib
import json
import math
import pathlib

P = pathlib.Path(__file__).resolve().parent
R = P.parents[2]
O = R / 'a24_simulator/results/A24_S26_MATCHED_BC_20261022_01'


def read(p):
    if p.suffix == '.gz':
        return json.loads(gzip.decompress(p.read_bytes()))
    return json.loads(p.read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def near(a, b):
    assert math.isfinite(a) and math.isfinite(b) and abs(a - b) < 2e-7, (a, b)


manifest = read(P / 'PUBLICATION.json')
for pin in manifest['files']:
    p = R / pin['path']
    assert p.is_file() and p.stat().st_size == pin['bytes'] and sha(p) == pin['sha256'], pin['path']

proof = read(O / 'FINAL_PROOF.json')
for pin in proof['files']:
    name = manifest['sealed_control_snapshots'].get(pin['path'], pin['path'])
    assert sha(R / name) == pin['sha256'], ('Original scientific seal', pin['path'])

operation = read(R / 'a24_simulator/experiments/a24_s26_matched_bc_20261022/OPERATION.json')
for pin in operation['source_pins'] + [operation['checkpoint']]:
    assert sha(R / pin['path']) == pin['sha256'], ('Frozen source', pin['path'])

result = read(O / 'RESULT.json')
summary = read(O / 'SUMMARY.json')
assert result['counts'] == {'START': 105, 'COMPLETE': 105, 'FAIL': 0}
with (P / 'PRIMARY.csv').open(encoding='utf-8', newline='') as f:
    published = {x['policy']: x for x in csv.DictReader(f)}
primary = next(c for c in summary['cohorts'] if c['cohort'] == 'PRIMARY')
for aggregate in primary['overall']:
    rows = [x for x in result['rows'] if x['kind'] == 'EVAL'
            and x['condition']['cohort'] == 'PRIMARY' and x['policy'] == aggregate['policy']]
    assert len(rows) == 4
    raw_metrics = []
    for row in rows:
        d = read(R / row['raw']['path'])
        r = d['result']
        end = d['case']['observation_end_s']
        metric = {'J': r['config']['baseline'] * end + math.fsum(t['increment'] for t in r['trace']),
                  'AP': math.fsum(t['temperature_area'] for t in r['trace']) / (end - 35)}
        for group in ['ALL', 'U', 'N']:
            requests = [q for q in r['requests'] if group == 'ALL' or q['priority'] == group]
            answered = [q for q in requests if q['response_ns'] is not None and q['response_ns'] <= round(end * 1e9)]
            delays = sorted((q['response_ns'] - q['scheduled_arrival_ns']) / 1e9 for q in answered)
            metric[group + '_n'] = len(requests)
            metric[group + '_on'] = sum(q['response_ns'] <= q['deadline_ns'] for q in answered)
            metric[group + '_P95'] = delays[math.ceil(.95 * len(delays)) - 1]
            metric[group + '_missing'] = len(requests) - len(answered)
            metric[group + '_incomplete'] = sum(q['available_ns'] is None or q['available_ns'] > round(end * 1e9) for q in requests)
        raw_metrics.append(metric)
    for k in ['J', 'AP', 'U_P95', 'N_P95']:
        value = math.fsum(m[k] for m in raw_metrics) / 4
        near(value, aggregate[k])
        near(value, float(published[aggregate['policy']][k]))
    for group in ['ALL', 'U', 'N']:
        for suffix in ['n', 'on', 'missing', 'incomplete']:
            key = group + '_' + suffix
            assert sum(m[key] for m in raw_metrics) == aggregate[key]
        key = group + '_on_pct'
        near(100 * aggregate[group + '_on'] / aggregate[group + '_n'], float(published[aggregate['policy']][key]))

teacher = next(x for x in primary['overall'] if x['policy'] == 'TEACHER_MATCH')
assert teacher['ALL_on'] == teacher['ALL_n'] == 2048
assert teacher['U_on'] == teacher['U_n'] == 1280
assert teacher['N_on'] == teacher['N_n'] == 768
assert not read(O / 'TEACHER_MATCH_CONTRACT.json')['uses_retrained_NN']
stress = next(c for c in summary['cohorts'] if c['cohort'] == 'STRESS')
stress_teacher = next(x for x in stress['overall'] if x['policy'] == 'TEACHER_MATCH')
assert stress_teacher['ALL_on'] == 726 and stress_teacher['ALL_n'] == 1024
with (P / 'COMPARISONS.csv').open(encoding='utf-8', newline='') as f:
    for comparison in csv.DictReader(f):
        reference = next(x for x in primary['overall'] if x['policy'] == comparison['reference'])
        near(float(comparison['ALL_gain_pp']), teacher['ALL_on_pct'] - reference['ALL_on_pct'])
        near(float(comparison['predicted_energy_saving_pct']), 100 * (reference['J'] - teacher['J']) / reference['J'])
        near(float(comparison['mean_AP_reduction_C']), reference['AP'] - teacher['AP'])
print(json.dumps({'status': 'PASS', 'publication_files': len(manifest['files']),
                  'original_sealed_files': len(proof['files']),
                  'primary_raw_episodes_checked': 36, 'teacher_on_time': '2048/2048',
                  'new_simulations': 0, 'new_fits': 0}, ensure_ascii=False))
