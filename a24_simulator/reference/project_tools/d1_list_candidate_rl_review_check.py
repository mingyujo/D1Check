"""Audit the review proposal; never import a policy, simulator or learner."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "docs/results/list_candidate_rl_review_01"


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    proposal = read(BUNDLE / "design_amendment_v4.json")
    old_path = ROOT / "docs/results/list_candidate_rl_design_01/design_contract.json"
    old = read(old_path)
    assert sha(old_path) == proposal["base_contract_sha256"]
    for name, expected in proposal["source_basis"].items():
        assert sha(ROOT / name) == expected, name
    assert not proposal["implementation_complete"]
    assert not proposal["learning_started"] and not proposal["native_evaluation_complete"]
    assert proposal["architecture"]["rl_policy"] == proposal["rl_policy"]
    assert proposal["architecture"]["training_reference"] == proposal["base_policy"]
    assert "rolling_horizon" in proposal["architecture"]["excluded_online"]
    assert "Band_reference_reward" in proposal["architecture"]["excluded_online"]

    features = proposal["features"]
    assert features["state_fields"] == old["observations"]["state_fields"]
    assert len(features["state_fields"]) == features["state_size"] == 56
    assert len(set(features["candidate_fields"])) == features["candidate_size"] == 28
    fields = old["observations"]["candidate_fields"].copy()
    fields[fields.index("C_head.included_now")] = "proxy_span_duration_over_6s"
    fields[fields.index("D_head.included_now")] = "proxy_span_duration_known"
    assert fields == features["candidate_fields"]
    assert features["slots"] == features["max_live"] == 8
    network = proposal["network"]
    parameters = sum(a * b + b for key in (
        "state_layers", "candidate_layers", "score_layers", "critic_layers"
    ) for a, b in zip(network[key], network[key][1:]))
    assert parameters == features["parameter_count"] == 16455
    assert not features["old_weights_or_optimizer_compatible"]

    hold = proposal["hold"]
    assert hold["credit_s"] == .25 and hold["defer_s"] == [.125, .25]
    assert hold["phase_only_keeps_timer"] and hold["elapsed_time_debit_once"]
    assert not hold["long_resource_wait_added"]
    events = proposal["public_event_adapter"]
    assert not events["implemented"] and events["opt_in_PC_hook_proposed"]
    assert events["Android_changes"] == 0
    assert {"output_ready_ns", "persist_complete_ns", "lane_available_ns", "dispatch_ns"} <= set(events["allowed_events"])
    assert "realized_AP_curve" in events["forbidden_payloads"]
    pair = proposal["pair_commit"]
    assert pair["first_dispatch_retained_if_second_fails"]
    assert pair["second_unassigned_request_retained"] and pair["same_commit_no_resampling"]
    assert not pair["physical_simultaneous_start_guaranteed"]
    assert proposal["proxy"]["unknown_raw_values"] is None
    assert not proposal["proxy"]["whole_episode_cost_ranking_claim"]

    # A math counterexample, not new environmental performance samples.
    signed_service = [-1., 1.]
    assert sum(signed_service) / 2 == 0
    assert sum(max(0., value) for value in signed_service) / 2 == .5
    objective = proposal["objective"]
    assert all("max(0," in value for value in objective["service_costs"])
    assert objective["J_cost"].startswith("signed") and objective["gamma"] == 1

    # Costs belong to the interval AFTER the selected action; include final tail.
    reward_cases = [
        ([30., 30.1, 30.3], 31.2, 31.4),
        ([31., 31., 31.], 31., 31.2),
        ([30.5], 31.5, 31.1),
    ]
    for peaks, end_peak, reference in reward_cases:
        rewards = [-(right-left) for left, right in zip(peaks, peaks[1:])]
        rewards.append(-(end_peak-peaks[-1]) + reference-peaks[0])
        assert abs(sum(rewards) - (reference-end_peak)) < 1e-12
        repeated = [peaks[0], *peaks]
        inserted = [-(b-a) for a, b in zip(repeated, repeated[1:])]
        inserted.append(-(end_peak-repeated[-1]) + reference-repeated[0])
        assert abs(sum(inserted) - sum(rewards)) < 1e-12
    assert not proposal["reward_attribution"]["actor_receives_realized_curve"]
    assert proposal["invalid_channels"]["AP_J_whole_episode_trajectory_mask"]
    assert proposal["invalid_channels"]["unknown_metrics_report_null"]

    # Per-episode score sums differ from an unrequested 1/T actor objective.
    episodes = [[1., 2.], [3.]]
    score_sum = sum(sum(values) for values in episodes) / len(episodes)
    count_mean = sum(sum(values)/len(values) for values in episodes) / len(episodes)
    assert score_sum == 3. and count_mean == 2.25
    aggregation = proposal["learner_aggregation"]
    assert not aggregation["divide_actor_by_episode_decision_count"]
    assert aggregation["zero_actor_last_layer_retained"]
    assert not aggregation["CPO_optimizer_or_guarantee"]

    evaluation = proposal["evaluation"]
    assert evaluation["primary_absolute_requirements"] == {"F": 0, "U": 0, "N": 0}
    assert evaluation["existing_deadlines_s"] == {"classification": 1.5, "detection": 6}
    assert evaluation["strict_low_sustained_thermal_gate_unchanged"]
    assert evaluation["training_seeds"] == [11, 23, 37]
    assert not evaluation["64_episodes_is_convergence_test"]
    budget = proposal["future_budget"]
    assert budget["environment_expected_max"] == budget["original_base_expected"] + 24 == 1472
    assert budget["original_first_stage_environment_cap"] == 512
    assert budget["conditional_before_final_total"] == 512 + 24 == 536
    assert budget["environment_expected_max"] <= budget["overall_proposed_cap"] == 1536
    assert budget["learning_proposed_cap"] == 416
    assert budget["cumulative_environment_starts"] + 1536 <= 20000
    assert budget["cumulative_learning_starts"] + 416 <= 6144
    assert not budget["execution_authorized_by_this_review"]
    assert proposal["matched_nonlearning_control"]["development_conditions"] == 24
    assert proposal["matched_nonlearning_control"]["final_conditions_automatically_added"] == 0
    assert not proposal["preserved"]["experiment_ready"]
    assert all(value == 0 for value in proposal["consumption"].values())

    debate = read(BUNDLE / "debate_record.json")
    assert debate["participants"] == ["mobile_review", "ie_review", "rl_review"]
    assert len(debate["rounds"]) == 3 and debate["direct_peer_exchange_confirmed_by_reviewers"]
    assert not debate["human_expert_review"] and not debate["automatic_model_switch"]
    links = 0
    for name in ("docs/LIST_CANDIDATE_RL_REVIEW_20261009.md", "docs/results/list_candidate_rl_review_01/README.md"):
        path = ROOT / name
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf8")):
            if target.startswith(("https://", "http://", "#")):
                continue
            assert (path.parent / target.split("#", 1)[0]).exists(), target
            links += 1
    manifest = BUNDLE / "artifact_manifest.json"
    if manifest.exists():
        for name, expected in read(manifest)["artifacts"].items():
            assert sha(ROOT / name) == expected, name
    result = {
        "status": "PASS", "scope": "static proposal audit; not engine, training or performance verification",
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "checker_sha256": sha(Path(__file__)), "proposal_sha256": sha(BUNDLE / "design_amendment_v4.json"),
        "participants": 3, "debate_rounds": 3, "state_fields": 56, "candidate_fields": 28,
        "parameters": parameters, "reward_attribution_algebra_cases": 3,
        "service_cancellation_counterexamples": 1, "actor_aggregation_counterexamples": 1,
        "local_links": links, "source_hashes": len(proposal["source_basis"]),
        "environment_starts": 0, "learning_starts": 0, "device_commands": 0,
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    audit()
