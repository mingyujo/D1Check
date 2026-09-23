"""Plan-only validator for an exploratory staggered-arrival simulation; never simulates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools import d1_arrival_plan as common


VERSION = "arrival-extension-exploratory-simulation-plan-v1"


def make_plan(audit_path):
    audit_path = Path(audit_path)
    audit = common.read(audit_path)
    if audit.get("status") != "PASS" or audit.get("frozen_decision", {}).get("conditional_joint_primary_pass") is not False:
        raise ValueError("verified post-analysis with preserved frozen FAIL required")
    return dict(
        protocol=VERSION, status="PLAN_ONLY_NOT_EXECUTED", evidence_role="post-unblinding exploratory fit/diagnostic",
        source=dict(audit_path=str(audit_path), audit_sha256=common.digest(audit_path),
                    sessions=27, requests=198, paired_primary_blocks=6),
        separation=dict(existing_support_simulation="unchanged support-constrained-simulation-v1",
                        independent_evaluation="already unblinded; fit is not independent validation",
                        success_criteria="not set in this plan"),
        timing_model=dict(
            arrivals="use scheduled arrival offsets from observed workload templates; actual lag retained as diagnostic",
            queue_wait="derived by simulation as execution_start - queue_entry; never sampled as service",
            service="sample/fit execution_start -> worker_release occupancy, with urgent completion at output_ready and normal completion at persist_complete",
            residual="non-preemptive remaining occupancy conditional on elapsed service at arrival",
            policy_cost="observed policy_compute_ns occurs before dispatch and remains inside response boundary",
            worker_release="lane becomes available only at worker_release_ns",
            forbidden="response_ns/end-to-end latency may not be used as service time"),
        supported=dict(
            device="same A24 fingerprint, current models/input, resident runtimes, CPU thread1, two workers, thermal status0",
            workloads=["primary_burst", "reversed_burst", "low", "queue"],
            policies=["CPU_FIFO", "CPU_URGENT", "CONDITIONAL"],
            strongest="exact observed-trace replay and decomposition",
            conditional="counterfactual scheduling only under explicit exchangeability and interference assumptions",
            observed_service_cells=audit.get("simulation_component_support", {}).get("service_cells", []),
            missing_service_cells=audit.get("simulation_component_support", {}).get("missing_cells", [])),
        assumptions=[
            dict(id="A1", text="task/backend occupancy is exchangeable within the same workload and observed thermal/resident state"),
            dict(id="A2", text="overlap effect is conditioned on observed opposite-lane overlap bin; unseen overlap is bounded by sensitivity, not treated as measured"),
            dict(id="A3", text="whole session/block resampling preserves within-session request dependence"),
            dict(id="A4", text="arrival templates are discrete observed templates; no claim for arbitrary real traffic"),
            dict(id="A5", text="GPU/CPU allocation selection in evaluation is confounded with policy; causal adaptive-policy superiority is not identified")],
        exploratory_grid=dict(
            arrival_templates=["primary_burst", "reversed_burst", "low", "queue"],
            overlap_sensitivity=["no_extra_penalty", "observed_overlap_conditioned", "worst_observed_within_cell"],
            service_sensitivity=["empirical_central", "within-cell_low", "within-cell_high"],
            policies=["CPU_FIFO", "CPU_URGENT", "CONDITIONAL"],
            fixed_split="unsupported primary comparison; allow only labeled sensitivity after missing cells are measured"),
        statistics=dict(unit="whole paired workload block/session, never request",
                        primary_uncertainty="exact ordered whole-block bootstrap 6^6=46656 if execution is later approved",
                        supporting_conditions="n=1 each; descriptive only, no interval",
                        fit_check="replay error and component coverage; not independent validation"),
        budget=dict(max_base_cells=108, max_exact_block_resamples_per_contrast=46656,
                    max_wall_minutes=10, max_memory_mib=2048, random_draws=0,
                    stop_on=["unsupported task/backend/overlap cell", "timing-order violation", "missing terminal", "nonfinite KPI", "source hash mismatch"]),
        unresolved_measurement_minimum=[
            "fixed CPU/GPU split paired sessions on the same primary workload",
            "matched same-request service with and without controlled overlap for interference identification",
            "classification/GPU arrival-workload cell if role-reversed or fixed-split simulation remains in scope",
            "at least one untouched workload/session set for independent simulator ranking and paired-effect validation",
            "additional device only if cross-device generalization remains a research claim"],
        execution_requires_new_approval=True)


def validate(plan):
    required = {"protocol", "status", "evidence_role", "source", "separation", "timing_model", "supported",
                "assumptions", "exploratory_grid", "statistics", "budget", "unresolved_measurement_minimum",
                "execution_requires_new_approval"}
    if set(plan) != required or plan["protocol"] != VERSION or plan["status"] != "PLAN_ONLY_NOT_EXECUTED":
        raise ValueError("plan identity/status")
    if plan["separation"]["success_criteria"] != "not set in this plan":
        raise ValueError("new success criterion forbidden")
    if "response_ns" not in plan["timing_model"]["forbidden"] or "execution_start -> worker_release" not in plan["timing_model"]["service"]:
        raise ValueError("service boundary")
    if plan["statistics"]["unit"] != "whole paired workload block/session, never request":
        raise ValueError("statistical unit")
    if plan["budget"]["random_draws"] != 0 or plan["execution_requires_new_approval"] is not True:
        raise ValueError("execution guard")
    return True


def generate(audit, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    plan = make_plan(audit)
    validate(plan)
    path = output / "simulation_plan.json"
    path.write_bytes(common.canonical(plan))
    receipt = dict(protocol=VERSION, plan_sha256=common.digest(path), status=plan["status"],
                   simulation_runs=0, simulated_completions=0, random_draws=0, result_files=0)
    (output / "plan_receipt.json").write_bytes(common.canonical(receipt))
    return receipt


def dry_run(plan_path, expected_sha256=None):
    plan_path = Path(plan_path)
    if expected_sha256 and common.digest(plan_path) != expected_sha256:
        raise ValueError("plan hash mismatch")
    validate(common.read(plan_path))
    return dict(protocol=VERSION, status="DRY_RUN_PASS", plan_sha256=common.digest(plan_path),
                simulation_runs=0, simulated_completions=0, random_draws=0, result_files=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--audit", type=Path, required=True); gen.add_argument("--output", type=Path, required=True)
    dry = sub.add_parser("dry-run")
    dry.add_argument("--plan", type=Path, required=True); dry.add_argument("--expected-sha256")
    args = parser.parse_args()
    result = generate(args.audit, args.output) if args.command == "generate" else dry_run(args.plan, args.expected_sha256)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
