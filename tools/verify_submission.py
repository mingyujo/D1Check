"""Check saved bytes and recompute saved-result arithmetic; never run models."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    path = Path(path)
    data = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    return json.loads(data.decode('utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def near(a, b, name):
    if not math.isfinite(a) or not math.isfinite(b) or abs(a - b) > 2e-7 * max(1, abs(b)):
        raise RuntimeError(f'{name}: {a} != {b}')


def p95(values):
    ordered = sorted(values)
    return ordered[math.ceil(.95 * len(ordered)) - 1]


def verify_a24():
    base = ROOT / 'a24'
    result_dir = base / 'a24_simulator/results/A24_S26_MATCHED_BC_20261022_01'
    saved = read(result_dir / 'RESULT.json')
    summary = read(result_dir / 'SUMMARY.json')
    primary = next(c for c in summary['cohorts'] if c['cohort'] == 'PRIMARY')
    checked = 0
    for aggregate in primary['overall']:
        rows = [r for r in saved['rows'] if r['kind'] == 'EVAL' and r['condition']['cohort'] == 'PRIMARY' and r['policy'] == aggregate['policy']]
        if len(rows) != 4:
            raise RuntimeError('A24 PRIMARY expected four inputs per policy')
        metrics = []
        for row in rows:
            path = base / row['raw']['path']
            if row['raw'].get('sha256') and sha(path) != row['raw']['sha256']:
                raise RuntimeError('A24 raw hash differs: ' + row['raw']['path'])
            episode = read(path)
            r = episode['result']
            end = episode['case']['observation_end_s']
            end_ns = round(end * 1e9)
            metric = {'J': r['config']['baseline'] * end + math.fsum(t['increment'] for t in r['trace']),
                      'AP': math.fsum(t['temperature_area'] for t in r['trace']) / (end - 35)}
            for group in ['ALL', 'U', 'N']:
                requests = [q for q in r['requests'] if group == 'ALL' or q['priority'] == group]
                answered = [q for q in requests if q['response_ns'] is not None and q['response_ns'] <= end_ns]
                metric[group + '_n'] = len(requests)
                metric[group + '_on'] = sum(q['response_ns'] <= q['deadline_ns'] for q in answered)
                metric[group + '_missing'] = len(requests) - len(answered)
                metric[group + '_incomplete'] = sum(q['available_ns'] is None or q['available_ns'] > end_ns for q in requests)
                metric[group + '_P95'] = p95([(q['response_ns'] - q['scheduled_arrival_ns']) / 1e9 for q in answered])
            metrics.append(metric)
            checked += 1
        for key in ['J', 'AP', 'U_P95', 'N_P95']:
            near(math.fsum(m[key] for m in metrics) / len(metrics), aggregate[key], 'A24 ' + key)
        for group in ['ALL', 'U', 'N']:
            for suffix in ['n', 'on', 'missing', 'incomplete']:
                key = group + '_' + suffix
                near(sum(m[key] for m in metrics), aggregate[key], 'A24 ' + key)
            near(100 * aggregate[group + '_on'] / aggregate[group + '_n'], aggregate[group + '_on_pct'], 'A24 rate')
    teacher = next(r for r in primary['overall'] if r['policy'] == 'TEACHER_MATCH')
    bc = next(r for r in primary['overall'] if r['policy'] == 'BC_OLD')
    if (teacher['ALL_on'], teacher['ALL_n'], teacher['U_on'], teacher['U_n']) != (2048, 2048, 1280, 1280):
        raise RuntimeError('A24 teacher reference changed')
    if (bc['ALL_on'], bc['ALL_n'], bc['U_on'], bc['U_n']) != (2047, 2048, 1279, 1280):
        raise RuntimeError('A24 BC reference changed')
    contract = read(result_dir / 'TEACHER_MATCH_CONTRACT.json')
    if contract['uses_retrained_NN']:
        raise RuntimeError('A24 100% contract unexpectedly uses NN')
    stress = next(c for c in summary['cohorts'] if c['cohort'] == 'STRESS')
    stress_teacher = next(r for r in stress['overall'] if r['policy'] == 'TEACHER_MATCH')
    if (stress_teacher['ALL_on'], stress_teacher['ALL_n']) != (726, 1024):
        raise RuntimeError('A24 stress reference changed')
    edf = next(r for r in primary['overall'] if r['policy'] == 'EDF_DYN')
    return {'raw_episodes': checked, 'teacher_on_time': '2048/2048', 'BC_on_time': '2047/2048',
            'teacher_stress_on_time': '726/1024', 'vs_EDF_energy_saving_pct': 100 * (edf['J'] - teacher['J']) / edf['J'],
            'vs_EDF_AP_reduction_C': edf['AP'] - teacher['AP']}


def verify_s26():
    base = ROOT / 's26'
    data = read(base / 's26_simulator/publications/rolling_atc_bc_candidate_20261021/FOUR_POLICY_DATA.json')
    metrics = []
    for row in data['rows']:
        path = base / row['raw_path']
        if sha(path) != row['raw_sha256']:
            raise RuntimeError('S26 raw hash differs: ' + row['raw_path'])
        raw = read(path)
        energy = math.fsum(t[2] for t in raw['integrals']) + 35 * raw['baseline_API_W']
        ap = math.fsum(t[3] for t in raw['integrals']) / (raw['observation_end_s'] - 35)
        near(energy, row['J'], 'S26 energy')
        near(ap, row['AP_mean'], 'S26 temperature')
        service = {}
        for group in ['all', 'urgent', 'normal']:
            requests = [q for q in raw['requests'] if group == 'all' or q['priority'] == group]
            answered = [q for q in requests if q.get('response') is not None and q['response'] <= raw['observation_end_s']]
            service[group] = {'planned': len(requests), 'completed': len(answered),
                              'on_time': sum(q['response'] <= q['deadline'] + 1e-9 for q in answered),
                              'p95_s': p95([q['response'] - q['arrival'] for q in answered])}
            for key, value in service[group].items():
                near(value, row['service'][group][key], 'S26 ' + group + ' ' + key)
        metrics.append({'method': row['method'], 'J': energy, 'AP_mean': ap, 'service': service, 'unfinished': raw['unfinished']})
    for method, aggregate in data['summary'].items():
        rows = [r for r in metrics if r['method'] == method]
        if len(rows) != 4:
            raise RuntimeError('S26 expected four inputs per method')
        for key in ['J', 'AP_mean']:
            near(math.fsum(r[key] for r in rows) / 4, aggregate[key], 'S26 average ' + key)
        near(sum(r['unfinished'] for r in rows), aggregate['unfinished'], 'S26 unfinished')
        for group in ['all', 'urgent', 'normal']:
            for key in ['planned', 'completed', 'on_time']:
                near(sum(r['service'][group][key] for r in rows), aggregate['service'][group][key], 'S26 total ' + key)
            near(math.fsum(r['service'][group]['p95_s'] for r in rows) / 4, aggregate['service'][group]['mean_case_P95_s'], 'S26 average P95')
    ours, edf = data['summary']['OURS'], data['summary']['EDF']
    if ours['service']['urgent']['on_time'] != 2560 or ours['service']['all']['on_time'] != 3976:
        raise RuntimeError('S26 presentation reference changed')
    if ours['service']['urgent']['mean_case_P95_s'] <= edf['service']['urgent']['mean_case_P95_s']:
        raise RuntimeError('S26 latency tradeoff reference changed')
    return {'raw_episodes': len(metrics), 'urgent_on_time': '2560/2560', 'all_on_time': '3976/4096',
            'vs_EDF_energy_saving_pct': 100 * (edf['J'] - ours['J']) / edf['J'],
            'vs_EDF_AP_reduction_C': edf['AP_mean'] - ours['AP_mean'],
            'urgent_P95_s': ours['service']['urgent']['mean_case_P95_s']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hashes-only', action='store_true')
    args = parser.parse_args()
    manifest = read(ROOT / 'data/FILES.json')
    missing, mismatched = [], []
    for row in manifest['files']:
        path = ROOT / row['path']
        if not path.is_file():
            missing.append(row['path'])
        elif path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            mismatched.append(row['path'])
    if missing or mismatched:
        print(json.dumps({'status': 'FAIL', 'missing_count': len(missing), 'mismatched_count': len(mismatched),
                          'first_missing': missing[:5], 'first_mismatched': mismatched[:5],
                          'next': 'python tools/fetch_data.py'}, ensure_ascii=False))
        raise SystemExit(1)
    result = {'status': 'PASS', 'verified_files': len(manifest['files']), 'new_experiments': 0, 'new_training': 0}
    if not args.hashes_only:
        result.update(A24=verify_a24(), S26=verify_s26())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
