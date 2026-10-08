"""Read-only design/evidence checks. Does not import a controller or start an engine."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'docs/results/edd_ect_residual_design_01'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(rel):
    with (ROOT / rel).open(encoding='utf8', newline='') as stream:
        return list(csv.DictReader(stream))


def check():
    c = read(BUNDLE / 'design_contract.json')
    v = read(BUNDLE / 'verification.json')
    for rel, expected in {**c['evidence_hashes'], **v['artifact_hashes']}.items():
        assert sha(ROOT / rel) == expected, 'hash drift: ' + rel
    assert c['status'] == 'DESIGN_COMPLETE_NOT_IMPLEMENTED'
    assert not c['training_allowed'] and not c['environment_run_allowed_by_this_design']
    assert all(value == 0 for value in c['current_work'].values())
    base = c['policy_ids']['base']
    assert base == 'IE_EDD_ECT_LANE_PC_V1'
    assert c['semantics']['forecast_suffix'] == c['semantics']['candidate_deltas_against'] == base
    assert not c['semantics']['base_aging_override']
    assert c['semantics']['routing_key'] == ['mean_all_five_phase_lane_end', 'CPU_first']
    parent = read(ROOT / 'docs/results/slack_residual_design_01/design_contract.json')
    assert c['frozen'] == parent['frozen'] and c['numeric_eps'] == parent['numeric_eps']
    assert not c['frozen']['experiment_ready'] and not c['frozen']['strict_supported']

    obs, ppo = c['observation'], c['ppo_proposal']
    assert len(obs['state_fields']) == len(set(obs['state_fields'])) == obs['state_dimension'] == 109
    assert len(obs['candidate_fields']) == len(set(obs['candidate_fields'])) == obs['candidate_dimension'] == 68
    assert sum('is_edd_head' in s for s in obs['state_fields']) == 8
    assert not any('forced_aging' in s for s in obs['state_fields'])
    assert ppo['state_encoder'][0] == 109 and ppo['candidate_encoder'][0] == 68
    assert len(ppo['critic_heads']) == 6 and len(ppo['cost_definitions']) == 5
    refs = [base, 'SHARED_EFT', 'BAND_HEFT_WHOLE_REQUEST_ADAPT_V1']
    assert ppo['closed_episode_references'] == refs
    action = c['actions']
    assert action['cooling_recharge'] == 'actual dispatch only'
    assert not action['cooling_limit_applies_to_base_resource_wait']
    assert max(8 + n + n * (8 - n) + 2 for n in range(9)) == action['maximum_raw_combinations'] == 30
    assert action['slots'] == 32

    # Algebra checks, deliberately separate from any claim of controller tests.
    for m in range(2, 33):
        prior = math.exp(math.log(9 * (m - 1)))
        assert abs(prior / (prior + m - 1) - .9) < 1e-14
    for anchor, peaks, reference in [(32., [29., 29.5, 30.], 30.1), (29., [30., 31., 31.], 30.8)]:
        reward = -(peaks[0] - anchor)
        reward -= sum(b - a for a, b in zip(peaks, peaks[1:]))
        reward += reference - anchor
        assert abs(reward - (reference - peaks[-1])) < 1e-12
    # Beating a weak own base must still incur a cost versus a stronger reference.
    policy_j, reference_js = 9., [10., 8., 8.5]
    assert max(0., *(policy_j - j for j in reference_js)) == 1.

    b, s, pilot = c['budget_proposal'], c['selection_proposal'], c['prototype_proposal']
    old_receipts = rows('docs/results/reserved_thermal_01/execution_receipts.csv')
    ie_receipts = rows('docs/results/ie_dispatch_01/execution_receipts.csv')
    assert [len(old_receipts), len(ie_receipts)] == b['historical_parts'] == [2241, 584]
    assert [int(r['cumulative_number']) for r in ie_receipts] == list(range(2242, 2826))
    assert sum(b['historical_parts']) == b['existing_used'] == 2825
    assert b['remaining_before'] == b['environment_ceiling'] - b['existing_used'] == 17175
    a = b['allocation']
    assert b['reference_policies'] == refs
    assert a['training_reference_worst_case'] == (b['main_learning_per_seed'] + b['learning_fixture_ceiling']) * len(refs) == 6240
    assert a['main_training'] == b['main_learning_total'] == 3 * 2032 == 6096
    assert a['learning_fixtures'] + a['main_training'] == b['all_learning_total'] == b['training_ceiling'] == 6144
    assert a['validation_rl'] == len(s['learning_seeds']) * len(s['checkpoints']) * s['validation_conditions'] == 288
    assert len(s['validation_fixed_policies']) == len(set(s['validation_fixed_policies'])) == 7
    assert a['validation_fixed'] == 7 * 24 == 168
    assert len(s['final_policies']) == len(set(s['final_policies'])) == 17
    previous = {r['policy'] for r in rows('docs/results/reserved_thermal_01/final_rule_only/results.csv')}
    assert len(previous) == 11 and previous.issubset(s['final_policies'])
    assert a['final_evaluation'] == 17 * s['final_conditions'] == 3264
    assert pilot['policy_runs'] == pilot['conditions'] * len(pilot['policies']) == 60
    assert pilot['paired_branch_runs'] == pilot['conditions'] * 2 == 24
    assert pilot['policy_runs'] + pilot['paired_branch_runs'] + pilot['fixture_error_ceiling'] == a['prototype'] == 128
    assert sum(a.values()) == b['additional_environment_maximum'] == 16488
    assert b['existing_used'] + sum(a.values()) == b['conservative_final_used'] == 19313
    assert b['environment_ceiling'] - b['conservative_final_used'] == b['remaining_unallocated'] == 687
    assert b['training_wall_seconds'] is None and s['trace_seed_assignment'] is None and not b['budget_reset']

    # Verify the factual motivation against the already completed comparison.
    primary = [r for r in rows('docs/results/ie_dispatch_01/pair_summary.csv') if r['scope'] == 'primary' and r['policy'] == base]
    pair = {r['baseline']: r for r in primary}
    assert math.isclose(float(pair['SHARED_EFT']['mean_delta_energy_j_all']), .080970082, abs_tol=1e-8)
    assert math.isclose(float(pair[refs[2]]['mean_delta_energy_j_all']), .169819540, abs_tol=1e-8)
    policies = {r['policy']: r for r in rows('docs/results/ie_dispatch_01/policy_summary.csv') if r['scope'] == 'all'}
    assert [int(policies[p]['normal_failures']) for p in refs] == [292, 204, 193]

    docs = [ROOT / 'docs/EDD_ECT_RESIDUAL_RL_DESIGN_20261008.md', BUNDLE / 'README.md', BUNDLE / 'DESIGN_REVIEW.md']
    for path in docs:
        text = path.read_text(encoding='utf8')
        assert '\ufffd' not in text and '???' not in text, 'encoding damage: ' + str(path)
        for link in re.findall(r'\]\(([^)]+)\)', text):
            if '://' in link or link.startswith('#'):
                continue
            target = path.parent / link.split('#')[0]
            assert target.exists(), 'missing local link: ' + link
    return dict(status='PASS', scope='design evidence/schema/algebra/budget only; no controller gates passed',
                state_dimension=109, candidate_dimension=68, final_policy_max=17,
                current_environment_used=2825, proposed_additional_max=16488,
                actual_engine_starts=0, actual_learning_episodes=0, device_commands=0)


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
