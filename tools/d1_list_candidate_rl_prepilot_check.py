"""Pure formula checks only: no native environment, policy adapter or learner."""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "docs/results/list_candidate_rl_prepilot_02"
BACKENDS = {"classification": ("CPU", "GPU"), "detection": ("CPU",)}
DEADLINES = {"classification": 1.5, "detection": 6.}


class PredictionUnknown(ValueError):
    pass


def classify(da, dj, service_ok=True, numeric_resolved=True):
    if not service_ok:
        return "service_failed"
    if not numeric_resolved or da is None or dj is None:
        return "numerically_undetermined"
    if not math.isfinite(da) or not math.isfinite(dj):
        return "numerically_undetermined"
    if da == 0 and dj == 0:
        return "tie"
    if da < 0 and dj == 0:
        return "heat_only"
    if da == 0 and dj < 0:
        return "energy_only"
    if da < 0 and dj < 0:
        return "joint"
    if da < 0 < dj or dj < 0 < da:
        return "tradeoff"
    return "worse"


def promotion(rows, traces, references, contexts, seeds, frozen_families=None):
    """Rows are hypothetical paired metrics, not generated evaluations."""
    families = ("low", "queue", "burst", "sustained")
    expected = set(itertools.product(traces, families, contexts, seeds, references))
    keys = [tuple(row[k] for k in ("trace", "family", "context", "seed", "reference")) for row in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        return []
    lookup = dict(zip(keys, rows))
    for row in rows:
        if classify(row["da"], row["dj"], row["service"], row["resolved"]) not in (
            "tie", "heat_only", "energy_only", "joint"
        ):
            return []
        if row["family"] in ("low", "sustained") and not row["absolute_primary"]:
            return []
    allowed = ("low", "sustained") if frozen_families is None else tuple(frozen_families)
    return [family for family in allowed if family in ("low", "sustained") and all(
        classify(lookup[key]["da"], lookup[key]["dj"]) in ("heat_only", "energy_only", "joint")
        for key in expected if key[1] == family
    )]


def compatible(left, right):
    if left["backend"] == right["backend"]:
        return False
    return {(left["task"], left["backend"]), (right["task"], right["backend"])} == {
        ("classification", "GPU"), ("detection", "CPU")
    }


def owned_end(now, dispatch, stage, mean):
    """Retain legacy dispatch-anchored point means; never clip an overrun."""
    phase_end = dispatch + sum(mean[:stage+1])
    lane_end = dispatch + sum(mean)
    if not 0 <= stage < 5 or mean[stage] <= 0 or phase_end <= now or lane_end <= now:
        raise PredictionUnknown("owned predicted phase/lane already ended")
    return lane_end


def first_start(task, backend, release, length, intervals):
    probe = {"task": task, "backend": backend}
    start = release
    for _ in range(len(intervals) + 1):
        conflicts = [job for job in intervals if start < job["end"] and start+length > job["start"]
                     and not compatible(probe, job)]
        if not conflicts:
            return start
        following = max(job["end"] for job in conflicts)
        assert following > start
        start = following
    raise AssertionError("finite interval accounting failed")


def shadow(now, heads, owned, immediate, holds, means):
    """One fixed-order two-head accounting; never optimize or emit dispatches."""
    if len(heads) > 2 or len({head["task"] for head in heads}) != len(heads):
        raise ValueError("current FIFO heads only")
    intervals = [dict(job) for job in owned]
    if any(job.get("end") is None for job in intervals):
        raise PredictionUnknown("owned forecast unknown")
    by_id = {head["id"]: head for head in heads}
    result = {}

    def place(head, backend, start):
        mu = means[(head["task"], backend)]
        count = 2 if head["task"] == "classification" else 3
        end = start + sum(mu)
        job = dict(task=head["task"], backend=backend, start=start, end=end)
        intervals.append(job)
        result[head["id"]] = dict(backend=backend, start=start, response=start+sum(mu[:count]), end=end)

    for rid, backend in immediate:
        head = by_id[rid]
        if backend not in BACKENDS[head["task"]] or rid in result:
            raise ValueError("unsupported/duplicate atom")
        assert first_start(head["task"], backend, now, sum(means[(head["task"], backend)]), intervals) == now
        place(head, backend, now)
    ordered = sorted(heads, key=lambda q: (q["arrival"]+DEADLINES[q["task"]], q["arrival"], q["ordinal"], q["id"]))
    for head in ordered:
        if head["id"] in result:
            continue
        release = max(now, holds.get(head["id"], now))
        choices = []
        for backend in BACKENDS[head["task"]]:
            length = sum(means[(head["task"], backend)])
            start = first_start(head["task"], backend, release, length, intervals)
            choices.append((start+length, backend != "CPU", backend, start))
        _, _, backend, start = min(choices)
        place(head, backend, start)
    return result


def urgent_envelope_excess(candidate_latency, l0_latency, past_p95, past_count, present=True):
    """Seconds -> normalized risk once. Not an episode P95 guarantee."""
    if not present:
        return 0.
    if candidate_latency is None or l0_latency is None:
        raise PredictionUnknown("head latency unknown")
    if past_count:
        if past_p95 is None:
            raise PredictionUnknown("observed P95 unknown")
        candidate_latency = max(candidate_latency, past_p95)
        l0_latency = max(l0_latency, past_p95)
    return max(0., candidate_latency-l0_latency) / 1.5


def service_risk5(heads, predictions, l0_predictions, past_p95=None, past_count=0):
    by_task = {head["task"]: head for head in heads}
    late, severity = {}, {}
    for task in BACKENDS:
        if task not in by_task:
            late[task], severity[task] = 0, 0.
            continue
        head = by_task[task]
        row = predictions.get(head["id"])
        if row is None or row.get("response") is None:
            raise PredictionUnknown("present head response unknown")
        excess = row["response"] - head["arrival"] - DEADLINES[task]
        late[task] = int(excess > 0)
        severity[task] = max(0., excess) / DEADLINES[task]
    urgent = 0.
    if "classification" in by_task:
        head = by_task["classification"]
        baseline = l0_predictions.get(head["id"])
        if baseline is None or baseline.get("response") is None:
            raise PredictionUnknown("L0 head response unknown")
        urgent = urgent_envelope_excess(predictions[head["id"]]["response"]-head["arrival"],
            baseline["response"]-head["arrival"], past_p95, past_count)
    return (late["classification"], late["detection"], severity["classification"],
            severity["detection"], urgent)


def audit():
    contract = json.loads((BUNDLE / "prepilot_contract.json").read_text(encoding="utf8"))
    for name, expected in contract["source_basis"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected, name
    assert contract["promotion"]["new_numeric_epsilon"] == 0
    assert not contract["policy_learner_event_adapter_implemented"]
    assert contract["online"]["base_and_fallback_and_training_reference"] == "new list L0"
    assert not contract["online"]["rolling_or_full_queue_added"]
    assert all(value == 0 for value in contract["consumption"].values())
    budget = contract["budget"]
    assert 1448+24+48 == budget["total_expected"] == 1520
    assert 512+24 == budget["before_confirmation_if_all_prior_stages_complete"] == 536
    assert 536+432+144+408 == 1520
    assert sum(budget["learning_breakdown"].values()) == budget["learning_cap"] == 416
    assert budget["total_cap"]-1520 == budget["unconsumed_reserve"] == 16
    assert not budget["automatic_native_execution_by_this_discussion"]

    pairs = [(da, dj) for da in (-1., 0., 1.) for dj in (-1., 0., 1.)]
    assert [classify(*p) for p in pairs] == ["joint", "heat_only", "tradeoff", "energy_only", "tie", "worse", "tradeoff", "worse", "worse"]
    assert classify(-1., 0., False) == "service_failed"
    assert classify(None, -1.) == "numerically_undetermined"
    assert classify(-1., 0., numeric_resolved=False) == "numerically_undetermined"
    traces, contexts, seeds, refs = (1, 2), ("mean", "short_context", "long_context"), (11, 23, 37), ("L0", "Band", "Triton")
    rows = [dict(trace=t, family=f, context=c, seed=s, reference=b, da=0.,
                 dj=-1. if f == "sustained" else 0., service=True, resolved=True, absolute_primary=True)
            for t, f, c, s, b in itertools.product(traces, ("low", "queue", "burst", "sustained"), contexts, seeds, refs)]
    assert promotion(rows, traces, refs, contexts, seeds) == ["sustained"]
    broken = [dict(row) for row in rows]
    next(row for row in broken if row["family"] == "sustained" and row["seed"] == 37)["dj"] = 0.
    assert promotion(broken, traces, refs, contexts, seeds) == []
    assert promotion(rows[:-1], traces, refs, contexts, seeds) == []
    assert promotion(rows, traces, refs, contexts, seeds, frozen_families=["low"]) == []

    model = json.loads((ROOT/"docs/results/online_policy_study_01/overnight_sustained_run01/model.json").read_text(encoding="utf8"))
    means = {}
    for task, backends in BACKENDS.items():
        for backend in backends:
            cell = task+"_"+backend+"_"+("urgent" if task == "classification" else "normal")
            vectors = [group["phase_means_ns"][cell] for group in model["service"].values() if cell in group["phase_means_ns"]]
            means[(task, backend)] = [sum(values)/len(values)/1e9 for values in zip(*vectors)]
    now = 90.
    heads = [dict(id="C1", task="classification", arrival=now-1.1, ordinal=1),
             dict(id="D1", task="detection", arrival=now-5.15, ordinal=0)]
    plain = shadow(now, heads, [], [], {}, means)
    assert plain["D1"]["start"] >= plain["C1"]["end"]
    mixed = shadow(now, heads, [], [("C1", "GPU")], {"D1": now+.125}, means)
    assert mixed["D1"]["start"] == now+.125 < mixed["C1"]["end"]
    try:
        owned_end(1., 0., 1, [.1, .2, .1, .1, .1])
        raise AssertionError("overrun accepted")
    except PredictionUnknown:
        pass
    assert urgent_envelope_excess(.2, .18, .25, 1) == 0.
    assert urgent_envelope_excess(.2, .18, None, 0) > 0.
    assert urgent_envelope_excess(None, None, None, 0, present=False) == 0.
    assert service_risk5(heads, mixed, plain)[-1] > 0.
    rank95 = lambda values: sorted(values)[math.ceil(.95*len(values))-1]
    assert rank95(list(range(1, 21))) == rank95([0, *range(1, 21)]) == 19

    lc, lg, ld = (sum(means[pair]) for pair in (("classification", "CPU"), ("classification", "GPU"), ("detection", "CPU")))
    rc = sum(means[("classification", "CPU")][:2])
    rg = sum(means[("classification", "GPU")][:2])
    rd = sum(means[("detection", "CPU")][:3])
    pair_c2 = min(lg+rg, ld+rc)
    cpu_first_c2, cpu_first_d = lc+rg, lc+rd
    assert cpu_first_c2 < .5 < pair_c2 < 1. and cpu_first_d < .85
    increments = model["energy_increment_w"]
    pair_j = increments["classification_GPU+detection_CPU"]*(2*lg) + increments["detection_CPU"]*(ld-2*lg)
    cpu_first_j = increments["classification_CPU"]*lc + increments["classification_GPU+detection_CPU"]*lg + increments["detection_CPU"]*(ld-lg)
    assert pair_j < cpu_first_j
    alias = dict(C2_response_pair_s=pair_c2, C2_response_CPU_first_s=cpu_first_c2,
                 D1_response_CPU_first_s=cpu_first_d, three_request_increment_pair_J=pair_j,
                 three_request_increment_CPU_first_J=cpu_first_j,
                 energy_difference_J=pair_j-cpu_first_j,
                 scope="static three-request arithmetic; no encoder/whole-trace/physical proof")
    if (BUNDLE/"artifact_manifest.json").exists():
        for name, expected in json.loads((BUNDLE/"artifact_manifest.json").read_text(encoding="utf8"))["artifacts"].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected, name
    result = dict(status="PASS", scope="pure prepilot formula audit; no native engine or policy execution",
                  head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  contract_sha256=hashlib.sha256((BUNDLE/"prepilot_contract.json").read_bytes()).hexdigest(),
                  cost_type_sign_cases=9, promotion_cases=4, formula_examples="CPU collision, per-head hold, overrun, urgent envelope, quantile correction",
                  C2_alias=alias, native_environment_starts=0, learning_starts=0, device_commands=0)
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    audit()
