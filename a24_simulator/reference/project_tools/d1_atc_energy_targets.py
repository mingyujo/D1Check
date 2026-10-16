"""Episode-end labels only. Gate removes only negative E/AP suffix costs."""
import numpy as np
from tools import d1_atc_waitlink_targets as original
from tools import d1_atc_energy_ppo as learning

SERVICE = ("incomplete", "urgent_failure", "urgent_original_cap_failure",
           "normal_failure", "normal_original_cap_failure", "urgent_p95_ms")


def service_gate(raw, reference):
    """Whole-episode service, completion and units guard, strict epsilon zero."""
    row, ref = raw["row"], reference["row"]
    if (row["planned"] != ref["planned"] or row["planned_work_units"] != ref["planned_work_units"] or
        row["completed"] != row["planned"] or row["completed_work_units"] != row["planned_work_units"] or
        row["completed"] < ref["completed"] or row["completed_work_units"] < ref["completed_work_units"]):
        return False
    return all(row[key] is not None and ref[key] is not None and row[key] <= ref[key] for key in SERVICE)


def targets(controller, raw, resident_baseline_j, reward_arm, reference):
    if reward_arm not in learning.ARMS:
        raise ValueError("unknown energy reward")
    frames, costs, valid, reward = original.targets(
        controller, raw, resident_baseline_j, learning.COUPLING, reference)
    costs = costs.copy()
    if reward_arm == "GATED_ECO5_AP180":
        steps = [step for step in controller.snapshots if "model_error" not in step]
        for frame, step in zip(frames, steps):
            frame["target"][2] = (ap_suffix(raw, step["now_ns"]) - ap_suffix(reference, step["now_ns"])) / .1
        costs[1] = frames[0]["target"][2]
    ungated = np.stack([frame["target"][1:3] for frame in frames]).copy()
    gate = service_gate(raw, reference)
    applied = reward_arm.startswith("GATED_") and not gate
    if applied:
        for frame in frames:
            frame["target"][1:3] = np.maximum(frame["target"][1:3], 0.)
        costs[:2] = frames[0]["target"][1:3]
    controller.energy_label_receipt = dict(reward_arm=reward_arm, gate_met=gate, gate_applied=applied,
        AP_target_end_s=180 if reward_arm.endswith("AP180") else 120,
        ungated_episode_E_AP_cost=ungated[0].tolist(), final_episode_E_AP_cost=costs[:2].tolist(),
        negative_frames_before=(ungated < 0).sum(0).tolist(),
        clamped_frames=((ungated < 0).sum(0) if applied else np.zeros(2, dtype=int)).tolist(),
        removed_negative_cost_mass=((-np.minimum(ungated, 0)).sum(0) if applied else np.zeros(2)).tolist(),
        positive_cost_mass_unchanged=np.maximum(ungated, 0).sum(0).tolist())
    return frames, costs, valid, reward


def ap_suffix(raw, now_ns):
    """Same prefix-anchor peak increment as native, extended offline to180s."""
    curve = [(float(time) * 1e9, float(value)) for time, value in raw["curve"] if time <= 180]
    if not curve or curve[0][0] != 35e9 or curve[-1][0] != 180e9 or now_ns > 120e9:
        raise ValueError("full AP180 coverage/current decision boundary")
    before = max(value for time, value in curve if time <= max(now_ns, 35e9))
    final = max(value for _, value in curve)
    return final - before
