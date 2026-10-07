"""Python re-implementation of the request-runner policy (PolicyStudy.choose) for cross-checks.

Source of the rule: feature/arrival-scheduling-20260923 @ d588323
  benchmark-runner/src/modelProbe/.../ArrivalPolicyStudy.kt 50~62 (choose) — CPU / PAR verbatim;
  d1sim/docs/혼합요청_사전등록_v1.md §2 — PAR-NPU = PAR with the classification lane GPU -> NPU.
Used by: make_test_fixtures.py (K2 cross-check cases) and mixreq_validate.py (rule 4: resource assignment).
Pure functions, no I/O.
"""
from __future__ import annotations

POLICY_CPU = "CPU_URGENT_ONLINE_V1"
POLICY_PAR = "B2_PARALLEL_ONLINE_V1"
POLICY_PAR_NPU = "S26_NPU_PARALLEL_V1"
POLICIES = (POLICY_CPU, POLICY_PAR, POLICY_PAR_NPU)
REASON = "online_arrived_priority_then_ordinal"
LANES = ("CPU", "GPU", "NPU")

BLOCK_POLICIES = {"A": (POLICY_CPU, POLICY_PAR), "N": (POLICY_CPU, POLICY_PAR_NPU)}
BLOCK_KEYS = {
    "A": ("classification_CPU", "classification_GPU", "detection_CPU", "detection_GPU"),
    "N": ("classification_CPU", "classification_GPU", "detection_CPU", "detection_GPU", "classification_NPU"),
}
USED_KEYS = {
    POLICY_CPU: ("classification_CPU", "detection_CPU"),
    POLICY_PAR: ("classification_GPU", "detection_CPU"),
    POLICY_PAR_NPU: ("classification_NPU", "detection_CPU"),
}


def lane_for(policy: str, task: str) -> str:
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy}")
    if policy == POLICY_CPU or task == "detection":
        return "CPU"
    if policy == POLICY_PAR:
        return "GPU"
    return "NPU"


def choose(policy: str, waiting: list[dict], free_cpu: bool, free_gpu: bool, free_npu: bool = True):
    """waiting rows: {'id','task','priority','ordinal'}. Returns {'id','backend','reason'} or None."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy}")
    if policy == POLICY_CPU and (not free_cpu or not free_gpu):
        return None
    ordered = sorted(waiting, key=lambda t: (t["priority"] != "urgent", t["ordinal"], t["id"]))
    free = {"CPU": free_cpu, "GPU": free_gpu, "NPU": free_npu}
    for q in ordered:
        lane = lane_for(policy, q["task"])
        if free[lane]:
            return {"id": q["id"], "backend": lane, "reason": REASON}
    return None


def overlap_keys(policy: str) -> tuple[str, str]:
    """The two lanes whose simultaneous busy time is the 'overlap' KPI (등록 §5)."""
    if policy == POLICY_CPU:
        return ("classification_CPU", "detection_CPU")  # overlap must be 0: one lane only
    if policy == POLICY_PAR:
        return ("classification_GPU", "detection_CPU")
    return ("classification_NPU", "detection_CPU")
