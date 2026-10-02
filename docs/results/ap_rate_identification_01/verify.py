"""Check published calculations; optional archive hash checks, no device APIs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = Path(__file__).resolve().parent


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def verify(archive=None):
    import sys
    sys.path.insert(0, str(ROOT))
    from tools import d1_ap_model_completion as common
    from tools import d1_ap_rate_identification as analysis
    out = BUNDLE/'final'
    summary = read(out/'summary.json')
    for name, expected in summary['source_sha256'].items():
        assert sha(ROOT/name) == expected, name
    assert sha(BUNDLE/'contract.json') == summary['contract_sha256']
    old = read(ROOT/'docs/results/ap_preparation_memory_01/verification.json')
    for name, expected in old['source_sha256'].items():
        assert sha(ROOT/name) == expected, name
    candidate = ROOT/'docs/results/ap_preparation_memory_01/final/candidate.json'
    assert sha(candidate) == 'd885b87c32d7df5b812b4cd85dcdae5230f47c9bd16d7ae2807df427b26c1466'
    scores = rows(out/'scores.csv')
    paths = rows(out/'paths.csv')
    for r in scores:
        pp = [p for p in paths if p['case'] == r['case']]
        key = 'frozen_memory_c' if r['model'] == 'frozen_memory' else 'diagnostic_c'
        obs = [float(p['observed_c']) for p in pp]
        pred = [float(p[key]) for p in pp]
        assert len(pp) == int(r['samples'])
        assert float(pp[0]['common_s']) == float(r['first_s'])
        assert float(pp[-1]['common_s']) == float(r['last_s'])
        for k, v in common.score(obs, pred).items():
            assert abs(v-float(r[k])) < 1e-12, (r['case'], k)
    original = {r['case']: r for r in rows(ROOT/'docs/results/ap_preparation_memory_01/final/scores.csv')
                if r['model'] == 'preparation_memory'}
    for r in read(ROOT/'docs/results/ap_memory_confirmation_01/run01/summary.json')['sessions']:
        original[r['role']] = r['scores']
    for name, saved in original.items():
        base = next(r for r in scores if r['case'] == name and r['model'] == 'frozen_memory')
        for k in ('mae_c', 'max_absolute_error_c', 'signed_mean_c', 'peak_signed_error_c'):
            assert abs(float(saved[k])-float(base[k])) < 1e-12, (name, k)
        changed = next(r for r in scores if r['case'] == name and r['model'] == 'rate_gain_diagnostic')
        assert abs(float(changed['peak_signed_error_c'])) > abs(float(saved['peak_signed_error_c']))
    for r in rows(out/'control_profile.csv'):
        assert r['gain'] == '' and float(r['gain_information']) == 0
    for r in rows(out/'directions.csv'):
        pp = [p for p in paths if p['case'] == r['case']]
        ts = [float(p['common_s']) for p in pp]
        key = 'frozen_memory_c' if r['model'] == 'frozen_memory' else 'diagnostic_c'
        for val, col in [('observed_change_c', 'observed_c'), ('predicted_change_c', key)]:
            expected = analysis.window_delta(ts, [float(p[col]) for p in pp], float(r['start_s']), float(r['end_s']))
            assert (r[val] == '' and expected is None) or (r[val] != '' and abs(float(r[val])-expected) < 1e-12)
    assert summary['family_count'] == 1 and summary['fresh_independent_confirmation'] == 0
    assert not summary['strict_support'] and not summary['default_changed'] and not summary['experiment_ready']
    upstream = read(ROOT/'docs/results/ap_preparation_memory_01/inputs.json')['source_sha256']
    checked = 0
    for name, expected in upstream.items():
        p = ROOT/name if name.startswith(('docs/', 'tools/')) else (archive/name if archive else None)
        if p is not None:
            assert sha(p) == expected, name
            checked += 1
    freezes = {}
    if archive:
        for name, expected in old['original_freezes_verified_unchanged'].items():
            assert sha(archive/name) == expected, name
            freezes[name] = expected
    return dict(input_hashes_verified=len(summary['source_sha256']), upstream_sources_verified=checked,
                old_scores_reproduced=len(original), new_score_rows_recomputed=len(scores),
                old_candidate_sha256=sha(candidate), original_freezes_verified=freezes,
                archive_checked=bool(archive), device_commands=0)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path)
    args = p.parse_args()
    print(json.dumps(verify(args.archive), indent=2))
