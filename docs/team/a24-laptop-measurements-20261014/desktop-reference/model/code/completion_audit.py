"""Fail-closed completion gate using recorded evidence only; never simulates/trains.

Final policy inputs are archived while actions remain deterministic.  Completion
means the registered experiment is auditable, not that its numerical goal was met.
"""
import collections
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

import numpy as np
import torch

from common import OUT, WORK, VENDOR, ALPHAS, SEEDS, H120, H180, sha, digest, read, save, stamp
import audit
import cases
import ppo


def require(condition, message):
    if not condition:
        raise ValueError(message)


def network_sha(network):
    state = network.state_dict() if hasattr(network, "state_dict") else network
    h = hashlib.sha256()
    for key, value in state.items():
        h.update(key.encode()); h.update(value.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def close(actual, expected, context, atol=1e-6, rtol=1e-8):
    """Compare nested scientific results, including exact null/boolean contracts."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict), context + ": expected mapping")
        for key, value in expected.items():
            require(key in actual, context + ": missing " + key)
            close(actual[key], value, context + "/" + key, atol, rtol)
    elif isinstance(expected, (list, tuple)):
        require(isinstance(actual, (list, tuple)) and len(actual) == len(expected), context + ": length")
        for i, value in enumerate(expected): close(actual[i], value, context + "/" + str(i), atol, rtol)
    elif isinstance(expected, bool) or expected is None or isinstance(expected, str):
        require(actual == expected, context + ": value mismatch")
    elif isinstance(expected, (int, np.integer)):
        require(actual == expected, context + ": integer mismatch")
    else:
        require(actual is not None and math.isfinite(float(actual)) and math.isfinite(float(expected)), context + ": nonfinite")
        require(abs(float(actual) - float(expected)) <= atol + rtol * abs(float(expected)), context + ": numeric mismatch")


def frame_arrays(frames):
    require(bool(frames), "cannot archive an empty evaluation")
    n = len(frames); nq = max(len(f["requests"]) for f in frames); na = max(len(f["features"]) for f in frames)
    arrays = {}
    for key, width, slots in (("requests", 24, nq), ("features", 16, na)):
        value = np.zeros((n, slots, width), dtype=frames[0][key].dtype)
        for i, frame in enumerate(frames): value[i, :len(frame[key])] = frame[key]
        arrays[key] = value
    for key in ("mask", "request_index", "backend_index", "physical_mask"):
        require(key in frames[0], "evaluation capture missing " + key)
        value = np.zeros((n, na), dtype=frames[0][key].dtype)
        for i, frame in enumerate(frames): value[i, :len(frame[key])] = frame[key]
        arrays[key] = value
    for key in ("resources", "global_state", "value"):
        arrays[key] = np.stack([f[key] for f in frames])
    arrays.update(time_ns=np.array([f["time_ns"] for f in frames], np.int64),
                  index=np.array([f["index"] for f in frames], np.int64),
                  old_logp=np.array([f["old_logp"] for f in frames], np.float64),
                  original_sizes=np.array([[len(f["requests"]), len(f["features"])] for f in frames], np.int32),
                  input_sha=np.array([f["input_sha"] for f in frames]),
                  alpha=np.array([f["alpha"] for f in frames], np.float64),
                  heat=np.array([f["heat"] for f in frames], np.float64))
    return arrays


def archive_frames(path):
    with np.load(path, allow_pickle=False) as archive:
        require(all(k in archive for k in ppo.INPUTS + ("original_sizes", "time_ns", "index", "old_logp", "value", "input_sha")),
                "archive lacks model inputs or labels: " + str(path))
        n = len(archive["index"]); frames = []
        for key in ppo.INPUTS + ("original_sizes", "time_ns", "index", "old_logp", "value", "input_sha"):
            require(len(archive[key]) == n, "archive leading dimension: " + key)
        for i in range(n):
            nq, na = map(int, archive["original_sizes"][i])
            require(0 < nq <= archive["requests"].shape[1] and 0 < na <= archive["features"].shape[1], "archive padding size")
            frame = {k: archive[k][i].copy() for k in ppo.INPUTS}
            frame["requests"] = frame["requests"][:nq]
            for key in ("features", "mask", "request_index", "backend_index"): frame[key] = frame[key][:na]
            frame.update(time_ns=int(archive["time_ns"][i]), index=int(archive["index"][i]),
                         old_logp=float(archive["old_logp"][i]), value=archive["value"][i].copy(), input_sha=str(archive["input_sha"][i]))
            for key in ("target", "adv", "cost", "alpha", "heat", "actor_valid"):
                if key in archive: frame[key] = archive[key][i].copy()
            if "physical_mask" in archive: frame["physical_mask"] = archive["physical_mask"][i, :na].copy()
            require(ppo.input_digest(frame) == frame["input_sha"], "recorded input digest changed")
            require(frame["mask"].dtype == np.bool_ and frame["mask"].any(), "empty/nonboolean policy mask")
            require(0 <= frame["index"] < na and frame["mask"][frame["index"]], "chosen action not legal")
            if "physical_mask" in frame:
                require(np.all(~frame["mask"] | frame["physical_mask"]), "policy mask exceeds physical mask")
                require(frame["physical_mask"][frame["index"]], "action violates physical mask")
            require(frame["request_index"].min() >= 0 and frame["request_index"].max() < nq, "request gather index")
            require(frame["backend_index"].min() >= 0 and frame["backend_index"].max() < 3, "backend gather index")
            frames.append(frame)
        require(n > 0 and all(frames[i]["time_ns"] <= frames[i + 1]["time_ns"] for i in range(n - 1)), "empty/nonmonotonic frame archive")
        rng = archive["action_rng_after"].copy() if "action_rng_after" in archive else None
    return frames, rng


def replay_frames(network, frames, deterministic=False, decisions=None):
    """Verify every input/action/log probability/critic, in shape-exact batches."""
    require(bool(frames), "no policy frames to replay")
    groups = collections.defaultdict(list)
    for i, frame in enumerate(frames):
        require(ppo.input_digest(frame) == frame["input_sha"], "input digest mismatch")
        groups[(len(frame["requests"]), len(frame["features"]))].append((i, frame))
    max_logp = max_value = 0.
    with torch.no_grad():
        for group in groups.values():
            # Production FINAL inference is batch1.  Near actor ties can change
            # argmax under a batched BLAS kernel even when errors are tiny.
            batch_size = 1 if deterministic else 128
            for start in range(0, len(group), batch_size):
                batch = group[start:start + batch_size]
                tensors = [torch.from_numpy(np.stack([f[key] for _, f in batch])) for key in ppo.INPUTS]
                logits, values = network(*tensors); logp = logits.log_softmax(-1)
                require(torch.isfinite(logits).all() and torch.isfinite(values).all(), "nonfinite replay inference")
                for j, (i, frame) in enumerate(batch):
                    idx = frame["index"]
                    require(frame["mask"][idx], "sampled action excluded by policy mask")
                    if deterministic: require(idx == int(logits[j].argmax()), "FINAL action differs from frozen argmax")
                    err = abs(float(logp[j, idx]) - frame["old_logp"])
                    verr = float(np.max(np.abs(values[j].numpy() - frame["value"])))
                    max_logp = max(max_logp, err); max_value = max(max_value, verr)
                    require(err <= 2e-5 and verr <= 2e-5, "stored log probability/critic differs from network")
                    if decisions is not None:
                        require(len(decisions) == len(frames), "decision/frame coverage mismatch")
                        decision = decisions[i]
                        close(decision["chosen_index"], idx, "decision index")
                        close(decision["input_sha"], frame["input_sha"], "decision input digest")
                        close(decision["logprob"], frame["old_logp"], "decision logprob", atol=2e-5)
                        close(decision["critic"], frame["value"].tolist(), "decision critic", atol=2e-5)
                        close(decision["time_ns"], frame["time_ns"], "decision clock")
                        require(not decision.get("model_fallback", False), "model fallback invalidates policy comparison")
    return dict(frames=len(frames), max_logprob_error=max_logp, max_critic_error=max_value, deterministic=deterministic)


def persist_eval(controller, identity, source_generation=None):
    """Archive captured FINAL inputs without labels, sampling, or optimizer work."""
    require(not controller.collect, "evaluation accidentally uses stochastic collection")
    require(not controller.errors, "evaluation model fallback")
    proof = replay_frames(controller.net, controller.frames, True, controller.decisions)
    arrays = frame_arrays(controller.frames)
    path = OUT / "evaluation_inputs" / (identity + ".npz"); path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), "evaluation archive already exists; use explicit recovery")
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    with temporary.open("r+b") as stream: stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    return dict(path=str(path), sha=sha(path), bytes=path.stat().st_size, frames=len(controller.frames),
                network_sha=network_sha(controller.net), source_generation=source_generation, proof=proof,
                action_selection="argmax", collection=False)


def json_lines(path):
    path = Path(path)
    require(path.exists(), "missing evidence " + str(path))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_raw(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream: return json.load(stream)


def receipts_proof(rows, receipts, cap):
    """Each durable START consumes budget, including failures and resumed attempts."""
    active = {}; completed = {}; starts = []; failures = []; errors = []
    for receipt in receipts:
        event = receipt["event"]; identity = receipt["identity"]
        if event == "START":
            require(identity not in active, "overlapping START: " + identity)
            require(identity not in completed, "completed identity rerun: " + identity)
            require(receipt["number"] == len(starts) + 1, "nonconsecutive environment consumption")
            active[identity] = receipt; starts.append(receipt)
        elif event in ("ERROR", "PREPARED"):
            require(identity in active, "recoverable commit error without START")
            if event == "ERROR": errors.append(receipt)
        else:
            require(event in ("COMPLETE", "FAIL"), "unknown terminal receipt")
            require(identity in active, "terminal receipt without START: " + identity)
            start = active.pop(identity)
            require(receipt["unix"] >= start["unix"], "receipt time reversed")
            if event == "COMPLETE": completed[identity] = (start, receipt)
            else: failures.append((start, receipt))
    require(not active, "unterminated environment STARTs: " + ",".join(sorted(active)[:8]))
    byid = {row["identity"]: row for row in rows}
    require(len(byid) == len(rows), "duplicate durable result identity")
    require(set(byid) == set(completed), "rows/COMPLETE coverage differs")
    require(len(starts) <= cap, "environment consumption exceeds registered corrected cap")
    for identity, row in byid.items():
        require(row["raw_sha"] == completed[identity][1]["raw_sha"], "receipt/raw hash mismatch: " + identity)
    return dict(environments_started=len(starts), completed=len(completed), failures=len(failures),
                training_starts=sum(bool(r.get("training")) for r in starts),
                validation_training_completed=sum(bool(completed[r["identity"]][0].get("training")) and r["split"] != "TRAIN" for r in rows),
                training_completed=sum(r["split"] == "TRAIN" for r in rows), recovered_commit_errors=len(errors), unresolved=0), completed


def metric_proof(row, raw, requests):
    """Recompute ledger arithmetic and fixed-window metric identities."""
    import plant
    require(len(raw["ledger"]) == len(requests), "truncated raw ledger")
    require(raw["device"] == row["device"], "raw device mismatch")
    close(row["metrics"], raw["metrics"], row["identity"] + "/row metrics")
    expected = plant.contract.active_metrics(raw["ledger"], plant.base.old.metrics(raw["ledger"]), H120)
    cost = raw["cost_120"]; cooling = raw["cooling_180"]; complete = expected["incomplete"] == 0
    expected.update(energy_prefix_j=cost["energy_window_j"],
        energy_180_j=cooling["energy_window_j"] if complete and cooling else None,
        energy_j=cost["energy_window_j"] if complete else None,
        mean_ap_c=cooling["mean_after35_c"] if complete and cooling else None,
        peak_ap_c=cooling["peak_after35_c"] if complete and cooling else None,
        mean_ap_0_120_c=cost["mean_ap_c"], peak_ap_0_120_c=cost["peak_ap_c"],
        completed_work_units=sum(q.get("work_units", 1) for q in raw["ledger"] if q["status"] == "succeeded"),
        planned_work_units=sum(q.get("work_units", 1) for q in raw["ledger"]))
    close(raw["metrics"], expected, row["identity"] + "/recomputed metrics")
    phases = ("ASSIGNED", "EXECUTING", "OUTPUT_READY", "PERSISTED", "WORKER_RELEASED", "AVAILABLE")
    grouped = collections.defaultdict(list)
    for event in raw["events"]: grouped[event["id"]].append(event)
    for q, record in zip(requests, raw["ledger"]):
        for key in ("id", "ordinal", "task", "priority", "arrival_ns", "deadline_offset_ns", "work_units"):
            require(record[key] == q[key], "raw request content changed: " + key)
        events = grouped.get(q["id"], [])
        require(tuple(event["phase"] for event in events) == phases[:len(events)], "nonpreemptive phase sequence")
        require(all(event["time_ns"] >= q["arrival_ns"] for event in events), "request event before arrival")
        if record["status"] == "succeeded":
            require(len(events) == len(phases), "successful request lacks release phases")
            close(record["response_ns"], record["response_at_ns"] - q["arrival_ns"], "response arithmetic")
    close(row["wait_used_ns"], raw["wait_used_ns"], "row WAIT accounting")
    wait = None; used = 0
    for event in raw["wait_events"]:
        if event["event"] == "WAIT_START":
            require(wait is None and event["quantum_ns"] > 0, "overlapping or zero WAIT")
            wait = event
        else:
            require(event["event"] == "WAIT_END" and wait is not None, "WAIT end lacks start")
            elapsed = event["time_ns"] - wait["time_ns"]
            require(0 <= elapsed <= wait["quantum_ns"] and elapsed == event["elapsed_ns"], "actual WAIT elapsed differs")
            used += elapsed; wait = None
    require(wait is None and used == raw["wait_used_ns"] <= 12_000_000_000, "WAIT total/cap")
    samples = raw["cost_samples"]
    require(samples and samples[0]["time_ns"] == 0 and samples[0]["energy_j"] == 0, "missing zero cost origin")
    for before, after in zip(samples, samples[1:]):
        require(after["time_ns"] >= before["time_ns"] and after["energy_j"] >= before["energy_j"] - 1e-7, "cost samples reverse time/energy")
        require(after["ap_area"] >= before["ap_area"] - 1e-7, "AP integration area decreases")
    at120 = [s for s in samples if s["time_ns"] == H120]
    require(bool(at120), "no 120s cost endpoint")
    close(at120[-1]["energy_j"], cost["energy_window_j"], "120s energy")
    if complete:
        require(cooling is not None and samples[-1]["time_ns"] == H180, "complete run lacks full cooling tail")
        close(samples[-1]["energy_j"], expected["energy_180_j"], "180s total energy")
        close(samples[-1]["ap_area"] / 145, expected["mean_ap_c"], "35..180s AP mean")
        require(expected["energy_180_j"] >= expected["energy_prefix_j"], "negative tail energy")
    else:
        require(raw["metrics"]["energy_180_j"] is None and raw["metrics"]["mean_ap_c"] is None, "incomplete row gains eligible tail metrics")
    for snapshot in (cost, cooling or {}):
        if "anchor_energy_j" in snapshot:
            close(snapshot["energy_window_j"], snapshot["anchor_energy_j"] + snapshot["additional_energy_j"], "energy component sum")
    audit.physical(raw, requests)
    return expected


def source_proof(store, frozen):
    generation = store.generation
    require(frozen["source_generation"] == generation, "FINAL freeze uses a different source generation")
    for name, expected in generation["source_sha"].items():
        require(sha(WORK / name) == expected, "current source hash mismatch: " + name)
    protected = {}; mutable_documents = {}
    for name, expected in store.reg["protected"].items():
        actual = sha(name)
        if name.endswith("ROLLING_ATC_RL_COMPLETION_PLAN_20261014.md"):
            mutable_documents[name] = dict(registered_sha=expected, current_sha=actual, unchanged=actual == expected)
        else:
            require(actual == expected, "protected original changed: " + name); protected[name] = actual
    for name, expected in generation["profile_sha"].items():
        device, layer = name.split("/")
        require(sha(VENDOR / "profiles" / f"{device}_G36_{layer}.json") == expected, "physical profile changed: " + name)
    for name, expected in store.reg["profile_sha"].items():
        require(generation["profile_sha"].get(name) == expected, "registered physical profile replaced")
    roster = read(OUT / "INPUT_ROSTER_HASHES.json")
    splits = collections.defaultdict(set)
    for item in roster: splits[item["split"]].add(item["request_sha"])
    for split, expected in store.reg["input_split_sha"].items():
        require(digest(sorted(splits[split])) == expected, "registered split roster altered: " + split)
    split_names = sorted(splits)
    for i, split in enumerate(split_names):
        for other in split_names[i + 1:]: require(not splits[split] & splits[other], "cross-split input content collision")
    require(generation["physical_fits"] == 0 and generation["physical_profile_changes"] == 0, "physical model tuned")
    return dict(generation=generation["generation"], sources=len(generation["source_sha"]), split_roster_hashes_verified=True,
                profiles=len(generation["profile_sha"]), protected=protected, planning_documents=mutable_documents)


def checkpoint_proof(path, device, arm, seed, episodes, expected_sha=None):
    import study
    require(Path(path).is_file(), "missing full checkpoint: " + str(path))
    if expected_sha is not None: require(sha(path) == expected_sha, "full checkpoint SHA changed")
    snapshot = torch.load(path, map_location="cpu", weights_only=False)
    required = ("network", "optimizer", "action_rng", "shuffle_rng", "pending", "pending_meta", "duals", "steps", "updates", "logs")
    require(all(key in snapshot for key in required), "incomplete resumable checkpoint")
    require(snapshot["version"] == "ratr37-native-v2" and snapshot["schema"] == ppo.SCHEMA, "checkpoint ABI")
    require((snapshot["device"], snapshot["seed"], snapshot["episodes"]) == (device, seed, episodes), "checkpoint identity/exposure")
    require((snapshot["kind"], snapshot["allow_wait"], snapshot["family"]) == study.ARMS[arm], "learning arm checkpoint mismatch")
    close(snapshot["settings"], study.asdict_settings(), "checkpoint PPO settings")
    require(snapshot["updates"] == episodes // snapshot["settings"]["episodes_per_update"], "checkpoint update exposure")
    require(not snapshot["pending"] and not snapshot["pending_meta"], "stage checkpoint has uncommitted episodes")
    require(len(snapshot["logs"]) == snapshot["updates"] and snapshot["logs"][-1]["adam_steps"] == snapshot["steps"], "checkpoint optimizer log coverage")
    for i, log in enumerate(snapshot["logs"], 1):
        require(log["update"] == i and log["episodes"] == i * 8, "checkpoint update sequence")
    require(snapshot["steps"] >= snapshot["updates"], "no actual Adam updates")
    net = ppo.Net(); net.load_state_dict(snapshot["network"])
    for value in snapshot["network"].values(): require(torch.isfinite(value).all(), "nonfinite checkpoint network")
    optimizer = snapshot["optimizer"]
    require(len(optimizer["state"]) == len(list(net.parameters())), "missing Adam parameter states")
    for state in optimizer["state"].values():
        require(all(key in state for key in ("step", "exp_avg", "exp_avg_sq")), "incomplete Adam state")
        require(int(state["step"].item()) == snapshot["steps"], "Adam step/counter mismatch")
        require(torch.isfinite(state["exp_avg"]).all() and torch.isfinite(state["exp_avg_sq"]).all(), "nonfinite Adam moments")
        require((state["exp_avg_sq"] >= 0).all(), "negative Adam second moment")
    for key in ("action_rng", "shuffle_rng"):
        state = snapshot[key]
        require(isinstance(state, torch.Tensor) and state.dtype == torch.uint8 and state.ndim == 1, "invalid saved " + key)
        generator = torch.Generator(); generator.set_state(state)
        require(torch.equal(generator.get_state(), state), "nonrecoverable " + key)
    require(np.isfinite(snapshot["duals"]).all() and snapshot["duals"].shape == (5, 3), "dual state ABI")
    loaded = ppo.Learner.load(path)
    require(network_sha(loaded.net) == network_sha(snapshot["network"]), "checkpoint network restore changes bytes")
    require(torch.equal(loaded.action_rng.get_state(), snapshot["action_rng"]) and torch.equal(loaded.shuffle_rng.get_state(), snapshot["shuffle_rng"]), "checkpoint RNG restore differs")
    return snapshot, net


def expected_final(frozen):
    identities = set(); roster = []
    for device in ("A24", "S26"):
        for layer in frozen["layers"]:
            profile = read(VENDOR / "profiles" / f"{device}_G36_{layer}.json")
            for ci in range(len(cases.SPECS)):
                for rep in range(frozen["final_replicates"]):
                    qs = cases.requests(profile, ci, "FINAL", rep)
                    roster.append(dict(device=device, layer=layer, case=ci, replicate=rep,
                        request_sha=digest(qs), environment_seed=cases.environment_seed("FINAL", rep)))
                    prefix = f"FINAL_{device}_{layer}_C{ci}_R{rep}_"
                    identities.update(prefix + baseline for baseline in frozen["baselines"])
                    for arm in frozen["arms"]:
                        for seed in SEEDS:
                            for alpha in ALPHAS: identities.add(prefix + f"{arm}_S{seed}_A{int(alpha*100)}")
    return identities, roster


def training_proof(rows, frozen, generation):
    """Every main episode must have its real pre-update inputs and native state."""
    models = {(m["device"], m["arm"], m["seed"]): m for m in frozen["models"]}
    expected_keys = {(d, arm, seed) for d in ("A24", "S26") for arm in frozen["arms"] for seed in SEEDS}
    require(set(models) == expected_keys and len(models) == len(frozen["models"]), "frozen learner/seed coverage")
    train_rows = {r["identity"]: r for r in rows if r["split"] == "TRAIN"}
    expected_train = set(); count = frame_count = 0; max_logp = max_critic = 0.; checked_models = []
    # GATE is the registered 256-episode prelearning ablation, also audited.
    keys = sorted(expected_keys | {(d, "GATE", seed) for d in ("A24", "S26") for seed in SEEDS})
    for device, arm, seed in keys:
        exposure = 256 if arm == "GATE" else frozen["B"]
        folder = OUT / "learners" / device / arm / str(seed)
        model = models.get((device, arm, seed))
        endpoint = model.get("endpoint", str(folder / f"ep_{exposure}.pt")) if model else str(folder / f"ep_{exposure}.pt")
        endpoint_sha = model.get("endpoint_sha") if model else None
        snapshot, _ = checkpoint_proof(endpoint, device, arm, seed, exposure, endpoint_sha)
        if model:
            require(model["exposure"] == exposure, "unequal learner exposure")
            selected, selected_net = checkpoint_proof(model["selected"], device, arm, seed, model["episodes"], model["sha"])
            require(model["episodes"] <= exposure, "FINAL checkpoint exceeds frozen exposure")
            if "network_sha" in model: require(network_sha(selected_net) == model["network_sha"], "frozen selected network SHA")
            if "endpoint_network_sha" in model: require(network_sha(snapshot["network"]) == model["endpoint_network_sha"], "endpoint network SHA")
            for name, value in (("selected_updates", selected["updates"]), ("selected_adam_steps", selected["steps"]),
                                ("exposure_updates", snapshot["updates"]), ("exposure_adam_steps", snapshot["steps"])):
                if name in model: require(model[name] == value, "frozen checkpoint counters differ: " + name)
        learning = json_lines(folder / "learning.jsonl")
        require([entry["episode"] for entry in learning] == list(range(1, exposure + 1)), "learning log missing/duplicate exposure")
        optimizer = json_lines(folder / "optimizer.jsonl")
        close(optimizer, snapshot["logs"], "optimizer log/full checkpoint")
        current_update = None; network = None; last_rng = None
        for i, entry in enumerate(learning):
            episode = i + 1; identity = f"TRAIN_{device}_{arm}_{seed}_EP{episode}"; expected_train.add(identity)
            require(identity in train_rows, "missing training experience: " + identity)
            row = train_rows[identity]
            require((row["device"], row["case_index"], row["index"]) == (device, i % 12, i), "training input schedule")
            training_layers = frozen.get("training_layers", frozen["layers"][:3])
            require(row["layer"] == training_layers[(i // 12) % len(training_layers)], "training layer exposure")
            require(abs(row["alpha"] - ALPHAS[i % 5]) < 1e-6, "training alpha exposure")
            require(entry["source_generation"] == generation["generation"], "training mixed source generations")
            close(entry["metrics"], row["metrics"], "learning metric copy")
            archive = entry["archive"]; require(sha(archive["path"]) == archive["sha"], "training rollout archive SHA")
            if row.get("training_archive"):
                require(row["training_archive"]["sha"] == archive["sha"], "row/learning archive mismatch")
            frames, rng = archive_frames(archive["path"])
            require(rng is not None, "training action RNG not persisted")
            require(all("physical_mask" in frame for frame in frames), "main rollout lacks physical masks")
            state = torch.from_numpy(rng); generator = torch.Generator(); generator.set_state(state)
            require(torch.equal(generator.get_state(), state), "training action RNG cannot restore")
            last_rng = state
            update = i // 8
            if update != current_update:
                network = ppo.Net()
                network.load_state_dict(torch.load(folder / f"network_update{update}.pt", map_location="cpu", weights_only=False))
                current_update = update
            post_update = episode // 8
            if episode % 8:
                recorded_network = network_sha(network)
            else:
                recorded_network = network_sha(torch.load(folder / f"network_update{post_update}.pt", map_location="cpu", weights_only=False))
            require(entry["network_sha"] == recorded_network, "learning entry network/update relationship")
            require(entry["updates"] == post_update, "learning entry update number")
            raw = load_raw(row["raw_path"])
            proof = replay_frames(network, frames, False, raw["decisions"])
            # Labels are recalculated without gradients, optimizer steps, or a simulator.
            original = [{key: np.array(f[key], copy=True) for key in ("target", "adv", "cost")} for f in frames]
            for f in frames:
                f["alpha"] = ALPHAS[i % 5]; f["heat"] = (.25, .5, .75)[(i // 5) % 3]
                f["learn_actor"] = int(f["mask"].sum()) > 1
                require(bool(f["actor_valid"]) == f["learn_actor"], "rollout actor mask label")
            controller = type("RecordedController", (), dict(frames=frames, errors=[], alpha=ALPHAS[i % 5]))()
            _, meta = ppo.labels(controller, raw, ppo.Settings(**snapshot["settings"]), snapshot["family"])
            close(entry["cost"], meta, "native recorded cost labels", atol=2e-5)
            for original_frame, recomputed in zip(original, frames):
                for key in ("target", "adv", "cost"):
                    require(np.allclose(original_frame[key], recomputed[key], atol=2e-5, rtol=1e-6), "rollout label arithmetic: " + key)
            count += 1; frame_count += proof["frames"]
            max_logp = max(max_logp, proof["max_logprob_error"]); max_critic = max(max_critic, proof["max_critic_error"])
        require(torch.equal(last_rng, snapshot["action_rng"]), "endpoint action RNG differs from actual last rollout")
        last_network = torch.load(folder / f"network_update{snapshot['updates']}.pt", map_location="cpu", weights_only=False)
        require(network_sha(last_network) == network_sha(snapshot["network"]), "last network update/full endpoint mismatch")
        checked_models.append(dict(device=device, arm=arm, seed=seed, exposure=exposure, updates=snapshot["updates"],
                                   adam_steps=snapshot["steps"], network_sha=network_sha(snapshot["network"])))
        save(OUT / "COMPLETION_AUDIT_PROGRESS.json", dict(phase="TRAINING_REPLAY", unix=stamp(), learners_checked=len(checked_models), episodes=count, frames=frame_count))
    require(set(train_rows) == expected_train, "unexpected main training exposure")
    return dict(learners=checked_models, episodes=count, frames=frame_count, max_logprob_error=max_logp, max_critic_error=max_critic)


def qualified(metrics, alpha, normal_only=False):
    if metrics["incomplete"] or metrics.get("energy_180_j") is None or metrics.get("mean_ap_c") is None: return False
    return all(not metrics[p + "_planned"] or metrics[p + "_on_time"] >= math.ceil(alpha * metrics[p + "_planned"] - 1e-9)
               for p in (("normal",) if normal_only else ("urgent", "normal")))


def effect(metrics, baseline):
    if not metrics.get("energy_180_j") or not baseline.get("energy_180_j") or metrics.get("mean_ap_c") is None or baseline.get("mean_ap_c") is None: return None
    energy = (baseline["energy_180_j"] - metrics["energy_180_j"]) / baseline["energy_180_j"]
    heat = baseline["mean_ap_c"] - metrics["mean_ap_c"]
    return dict(energy_reduction_pct=100 * energy, mean_AP_reduction_c=heat,
                joint_target=energy >= .1 and heat >= .5,
                service_not_worse=all(metrics[p + "_on_time"] >= baseline[p + "_on_time"] for p in ("urgent", "normal")))


def independent_interval(pairs, seed):
    clusters = {}
    for case, energy, heat in pairs: clusters.setdefault(case, []).append((energy, heat))
    if len(clusters) < 2:
        return dict(energy_CI95=None, AP_CI95=None, independent_case_clusters=len(clusters), strict_mean_target_lower_bounds=False)
    keys = sorted(clusters)
    sums = np.array([np.sum(clusters[key], axis=0) for key in keys])
    weights = np.array([len(clusters[key]) for key in keys])
    draws = np.random.default_rng(seed).integers(0, len(keys), size=(4000, len(keys)))
    means = sums[draws].sum(axis=1) / weights[draws].sum(axis=1)[:, None]
    lower, upper = np.quantile(means, [.025, .975], axis=0)
    return dict(energy_CI95=[float(lower[0]), float(upper[0])], AP_CI95=[float(lower[1]), float(upper[1])],
        independent_case_clusters=len(clusters), strict_mean_target_lower_bounds=bool(lower[0] >= 10 and lower[1] >= .5))


def comparison_stats(chosen, baseline_for, alpha, tails, normal_only=False):
    pairs = []; effects = []
    counts = dict(total=len(chosen), policy_eligible=0, baseline_eligible=0, common_eligible=0,
        policy_incomplete_pairs=0, service_worse_pairs=0, joint_target_pairs=0,
        target_with_service_not_worse=0, tail_AP180_worse_pairs=0, peak_AP_worse_pairs=0)
    for row in chosen:
        base = baseline_for(row); metrics = row["metrics"]; bm = base["metrics"]
        policy_ok = qualified(metrics, alpha, normal_only); baseline_ok = qualified(bm, alpha, normal_only)
        counts["policy_eligible"] += policy_ok; counts["baseline_eligible"] += baseline_ok
        counts["common_eligible"] += policy_ok and baseline_ok
        counts["policy_incomplete_pairs"] += metrics["incomplete"] > 0
        counts["service_worse_pairs"] += any(metrics[p + "_on_time"] < bm[p + "_on_time"] for p in ("urgent", "normal"))
        delta = effect(metrics, bm)
        if not (delta and policy_ok and baseline_ok): continue
        effects.append(delta); pairs.append((row["case_index"], delta["energy_reduction_pct"], delta["mean_AP_reduction_c"]))
        counts["joint_target_pairs"] += delta["joint_target"]
        counts["target_with_service_not_worse"] += delta["joint_target"] and delta["service_not_worse"]
        counts["tail_AP180_worse_pairs"] += tails[row["identity"]] > tails[base["identity"]] + 1e-9
        counts["peak_AP_worse_pairs"] += metrics["peak_ap_c"] > bm["peak_ap_c"] + 1e-9
    energy = float(np.mean([p[1] for p in pairs])) if pairs else None
    heat = float(np.mean([p[2] for p in pairs])) if pairs else None
    counts.update(energy_reduction_pct_mean=energy, mean_AP_reduction_c=heat)
    return counts, pairs, effects


def result_proof(final, frozen, tails):
    byid = {row["identity"]: row for row in final}
    groups = collections.defaultdict(list)
    for row in final:
        if row["alpha"] is not None:
            match = re.search(r"_(ATC_WAIT|EDD_WAIT|DIRECT_WAIT|NONDELAY)_S(\d+)_A", row["identity"])
            require(match is not None, "unknown learned FINAL arm")
            groups[row["device"], row["layer"], match[1], row["alpha"]].append(row)
        for alpha in ALPHAS: require(qualified(row["metrics"], alpha) == cases.qualifies(row["metrics"], alpha), "service qualifier implementation disagrees")
    summary = read(OUT / "FINAL_SUMMARY.json")
    summaries = {(r["device"], r["layer"], r["alpha"], r["baseline"]): r for r in summary}
    expected_summary_keys = {(d, layer, alpha, baseline) for d in ("A24", "S26") for layer in frozen["layers"] for alpha in ALPHAS for baseline in frozen["baselines"]}
    require(set(summaries) == expected_summary_keys and len(summaries) == len(summary), "primary report cell coverage")
    pooled = read(OUT / "ALL_ARMS_CONFIDENCE.json"); seeds = read(OUT / "ALL_ARMS_SEED_SUMMARY.json")
    normal = read(OUT / "NORMAL_ONLY_AUXILIARY.json"); ablation = read(OUT / "ABLATION_SUMMARY.json")
    pooled_by = {(r["device"], r["layer"], r["arm"], r["alpha"], r["baseline"]): r for r in pooled}
    seed_by = {(r["device"], r["layer"], r["arm"], r["alpha"], r["baseline"], r["learner_seed"]): r for r in seeds}
    normal_by = {(r["device"], r["layer"], r["arm"], r["alpha"], r["baseline"]): r for r in normal}
    ablation_by = {(r["device"], r["layer"], r["alpha"], r["baseline_arm"]): r for r in ablation}
    expected_pooled = {(d, layer, arm, alpha, baseline) for d in ("A24", "S26") for layer in frozen["layers"] for arm in frozen["arms"] for alpha in ALPHAS for baseline in frozen["baselines"]}
    require(set(pooled_by) == expected_pooled and len(pooled_by) == len(pooled), "all-arm confidence cell coverage")
    require(set(normal_by) == expected_pooled and len(normal_by) == len(normal), "normal-only auxiliary cell coverage")
    require(set(seed_by) == {key + (seed,) for key in expected_pooled for seed in SEEDS} and len(seed_by) == len(seeds), "individual learner seed confidence coverage")
    require(set(ablation_by) == {(d, layer, alpha, arm) for d in ("A24", "S26") for layer in frozen["layers"] for alpha in ALPHAS for arm in ("NONDELAY", "EDD_WAIT", "DIRECT_WAIT")} and len(ablation_by) == len(ablation), "learned comparator ablation coverage")
    for key in sorted(expected_pooled):
        device, layer, arm, alpha, baseline = key; chosen = groups[device, layer, arm, alpha]
        comparator = lambda row: byid[f"FINAL_{device}_{layer}_C{row['case_index']}_R{row['index']}_{baseline}"]
        counts, pairs, deltas = comparison_stats(chosen, comparator, alpha, tails)
        stats = {k: v for k, v in counts.items() if k != "target_with_service_not_worse"}
        stats.update(independent_interval(pairs, int(digest(list(key))[:8], 16)))
        close(pooled_by[key], stats, "pooled effects/confidence")
        require(pooled_by[key]["evidence_grade"] == frozen["evidence_grades"][layer], "evidence grade mixed")
        for seed in SEEDS:
            subset = [r for r in chosen if f"_S{seed}_A" in r["identity"]]
            values, seed_pairs, _ = comparison_stats(subset, comparator, alpha, tails)
            values.pop("target_with_service_not_worse")
            values.update(independent_interval(seed_pairs, int(digest(list(key) + [seed])[:8], 16)))
            close(seed_by[key + (seed,)], values, "individual seed effects/confidence")
        normal_counts, normal_pairs, _ = comparison_stats(chosen, comparator, alpha, tails, True)
        normal_counts.pop("target_with_service_not_worse")
        normal_counts.update(independent_interval(normal_pairs, int(digest(list(key) + ["normal"])[:8], 16)),
            absent_normal_pairs=sum(r["metrics"]["normal_planned"] == 0 for r in chosen))
        close(normal_by[key], normal_counts, "normal-only effects/confidence")
        if arm == "ATC_WAIT":
            primary = {k: v for k, v in counts.items() if k not in ("tail_AP180_worse_pairs", "peak_AP_worse_pairs")}
            met = bool(pairs and counts["energy_reduction_pct_mean"] >= 10 and counts["mean_AP_reduction_c"] >= .5)
            outcome = ("evaluation_ineligible" if not pairs else "conditional_mean_target" if met else
                "joint_improvement_below_target" if counts["energy_reduction_pct_mean"] > 0 and counts["mean_AP_reduction_c"] > 0 else
                "cost_tradeoff" if counts["energy_reduction_pct_mean"] > 0 or counts["mean_AP_reduction_c"] > 0 else "no_joint_improvement")
            primary.update(energy_worst_pct=min((p[1] for p in pairs), default=None), AP_worst_c=min((p[2] for p in pairs), default=None),
                mean_joint_target=met, all_pairs_qualified=counts["common_eligible"] == len(chosen) and bool(chosen), outcome=outcome)
            close(summaries[device, layer, alpha, baseline], primary, "primary summary")
    for (device, layer, alpha, other), recorded in ablation_by.items():
        chosen = groups[device, layer, "ATC_WAIT", alpha]
        comparator = lambda row: byid[row["identity"].replace("_ATC_WAIT_S", f"_{other}_S")]
        values, pairs, _ = comparison_stats(chosen, comparator, alpha, tails); values.pop("target_with_service_not_worse")
        values.update(independent_interval(pairs, int(digest([device, layer, alpha, other])[:8], 16)), exposure=frozen["B"])
        close(recorded, values, "paired learned-arm ablation")
    stored_pairs = load_raw(OUT / "FINAL_PAIRS.json.gz")
    expected_pairs = {(r["identity"], baseline) for r in final if "_ATC_WAIT_S" in r["identity"] for baseline in frozen["baselines"]}
    seen = set()
    for pair in stored_pairs:
        identity = pair["identity"]; baseline = pair["baseline"]; key = identity, baseline
        require(key not in seen and key in expected_pairs, "duplicate/unregistered final pair")
        seen.add(key); row = byid[identity]
        base = byid[f"FINAL_{row['device']}_{row['layer']}_C{row['case_index']}_R{row['index']}_{baseline}"]
        delta = effect(row["metrics"], base["metrics"])
        close(pair, dict(policy_qualified=qualified(row["metrics"], row["alpha"]), baseline_qualified=qualified(base["metrics"], row["alpha"]),
            effect=delta, policy_metrics=row["metrics"], baseline_metrics=base["metrics"]), "full paired result")
    require(seen == expected_pairs, "missing final paired result")
    close(read(OUT / "CHECKPOINT_EXPOSURE.json"), frozen["models"], "checkpoint exposure disclosure")
    model_pairs = load_raw(OUT / "MODEL_CHANGE_PAIRS.json.gz")
    expected_model_pairs = {r["identity"] for r in final if r["layer"] == "M1_coupled"}
    seen_models = set()
    for pair in model_pairs:
        identity = pair["identity"]
        require(identity in expected_model_pairs and identity not in seen_models, "model-change pair coverage/duplicate")
        seen_models.add(identity); row = byid[identity]
        reference_identity = identity.replace("_M1_coupled_", "_M0_frozen35_")
        metrics, baseline = row["metrics"], byid[reference_identity]["metrics"]
        close(pair, dict(reference_identity=reference_identity,
            energy_change_j=metrics["energy_180_j"] - baseline["energy_180_j"] if metrics["energy_180_j"] is not None and baseline["energy_180_j"] is not None else None,
            mean_AP_change_c=metrics["mean_ap_c"] - baseline["mean_ap_c"] if metrics["mean_ap_c"] is not None and baseline["mean_ap_c"] is not None else None,
            incomplete_M0=baseline["incomplete"], incomplete_M1=metrics["incomplete"]), "M0/M1 model-change arithmetic")
    require(seen_models == expected_model_pairs, "missing model-change comparison")
    return dict(primary_cells=len(summary), pooled_cells=len(pooled), individual_seed_cells=len(seeds),
        normal_only_cells=len(normal), learned_ablation_cells=len(ablation), pairs=len(seen), model_change_pairs=len(seen_models),
        goal_met_rows=sum(r["mean_joint_target"] for r in summary),
        confidence_supported_main_rows=sum(r.get("strict_mean_target_lower_bounds", False) for r in pooled if r["arm"] == "ATC_WAIT"))


def selection_proof(rows, frozen):
    """Recheck DEV-only checkpoint/rule selection without inspecting FINAL costs."""
    import study
    byid = {r["identity"]: r for r in rows}
    for model in frozen["models"]:
        folder = OUT / "learners" / model["device"] / model["arm"] / str(model["seed"])
        alternatives = []
        for path in folder.glob("dev_*.json"):
            result = read(path)
            if result["episodes"] > frozen["B"]: continue
            require((result["device"], result["arm"], result["seed"]) == (model["device"], model["arm"], model["seed"]), "DEV learner identity")
            expected = {f"DEV_{model['device']}_{model['arm']}_{model['seed']}_EP{result['episodes']}_{layer}_C{ci}_R{rep}_A{int(alpha*100)}"
                for layer in ("M0_frozen35", "M1_coupled") for ci in study.DEV_CASES for rep in range(2) for alpha in ALPHAS}
            require({r["identity"] for r in result["rows"]} == expected and len(result["rows"]) == len(expected), "DEV checkpoint selection incomplete conditions")
            for row in result["rows"]:
                close(row["metrics"], byid[row["identity"]]["metrics"], "DEV row disclosure")
            scores = {}
            for alpha in ALPHAS:
                subset = [r for r in result["rows"] if abs(r["alpha"] - alpha) < 1e-6]
                missing = sum(not qualified(r["metrics"], alpha) for r in subset)
                service = sum(max(0, alpha - (r["metrics"][p + "_success_pct"] if r["metrics"][p + "_success_pct"] is not None else 100) / 100)
                              for r in subset for p in ("urgent", "normal"))
                costs = [r["metrics"]["energy_180_j"] / 20 + r["metrics"]["mean_ap_c"] / .5
                         if r["metrics"]["energy_180_j"] is not None and r["metrics"]["mean_ap_c"] is not None else 1e5 for r in subset]
                scores[str(alpha)] = [missing, service, float(np.mean(costs))]
            close(result["scores"], scores, "DEV selection score")
            aggregate = [sum(value[j] for value in scores.values()) for j in range(3)]
            alternatives.append((aggregate, result["episodes"], result))
        chosen = min(alternatives, key=lambda value: (value[0], value[1]))
        require(chosen[2]["checkpoint"] == model["selected"] and chosen[2]["sha"] == model["sha"], "checkpoint chosen outside DEV selection rule")
        close(model["dev_score"], chosen[0], "frozen DEV selection score")
    for device in ("A24", "S26"):
        alternatives = []
        for baseline in frozen["baselines"]:
            subset = [byid[f"DEV_RULE_{device}_{layer}_C{ci}_R{rep}_{baseline}"]
                      for layer in ("M0_frozen35", "M1_coupled") for ci in study.DEV_CASES for rep in range(2)]
            score = (sum(not qualified(r["metrics"], .95) for r in subset),
                float(np.mean([r["metrics"]["energy_180_j"] / 20 + r["metrics"]["mean_ap_c"] / .5
                    if r["metrics"]["energy_180_j"] is not None and r["metrics"]["mean_ap_c"] is not None else 1e5 for r in subset])))
            alternatives.append((score, baseline))
        require(min(alternatives)[1] == frozen["strong_DEV_baseline"][device], "strong rule selected outside DEV protocol")
    return dict(selected_models=len(frozen["models"]), strong_rules=2, selection_split="DEV")


def _run(store, frozen):
    started = stamp()
    source = source_proof(store, frozen)
    require(frozen["final_argmax"] is True and frozen["FINAL_reselection"] is False, "unsealed FINAL policy protocol")
    require(frozen["alphas"] == list(ALPHAS) and frozen["final_replicates"] == 4, "FINAL service/repetition contract")
    require(frozen["layers"] == list(store.generation["layers"]), "FINAL physical layer coverage")
    close(frozen["cases"], list(cases.SPECS), "FINAL workload case contract")
    require(frozen["FINAL_inputs_sha"] == store.reg["input_split_sha"]["FINAL"], "registered FINAL superset changed")
    rows = json_lines(OUT / "rows.jsonl"); receipts = json_lines(OUT / "receipts.jsonl")
    receipt_counts, completed = receipts_proof(rows, receipts, store.reg["environment_cap"])
    require((store.n, store.failures, len(store.rows)) == (receipt_counts["environments_started"], receipt_counts["failures"], len(rows)), "in-memory consumption differs from durable ledger")
    final = [r for r in rows if r["split"] == "FINAL"]
    expected_ids, roster = expected_final(frozen)
    require({r["identity"] for r in final} == expected_ids and len(final) == len(expected_ids), "FINAL condition/seed/alpha/baseline coverage")
    require(digest(roster) == frozen["actual_FINAL_roster_sha"], "actual sealed FINAL input roster digest")
    for row in final:
        require(completed[row["identity"]][0]["unix"] >= frozen["unix"], "FINAL environment executed before freeze")
    profiles = {(d, layer): read(VENDOR / "profiles" / f"{d}_G36_{layer}.json")
                for d in ("A24", "S26") for layer in store.generation["layers"]}
    tails = {}; eval_networks = {}; eval_frames = 0; checked = 0
    for model in frozen["models"]:
        net = ppo.Net(); snapshot = torch.load(model["selected"], map_location="cpu", weights_only=False)
        net.load_state_dict(snapshot["network"])
        eval_networks[model["device"], model["arm"], model["seed"]] = net
    for row in rows:
        identity = row["identity"]; path = Path(row["raw_path"])
        require(path.is_file() and sha(path) == row["raw_sha"], "raw file missing/changed: " + identity)
        raw = load_raw(path)
        qs = cases.requests(profiles[row["device"], row["layer"]], row["case_index"], row["split"] if row["split"] != "P0FIX" else "P0FIX", row["index"])
        request_sha = digest(qs)
        require(request_sha == completed[identity][0]["request_sha"] == raw["request_sha"], "input receipt/raw/request digest: " + identity)
        require(row["environment_seed"] == raw["environment_seed"] == cases.environment_seed(row["split"], row["index"]), "environment seed contract")
        require(row["arrival_seed"] == cases.arrival_seed(row["split"], row["index"]), "arrival seed contract")
        require(row["physical_PASS"] is True and not raw["hardware_validated"] and not raw["online_learning"], "physical/evidence flags")
        require(row["decisions"] == len(raw["decisions"]) == len(raw["audit"]), "decision/audit coverage")
        metric_proof(row, raw, qs)
        if row["split"] in ("FINAL", "TRAIN"):
            require(row.get("source_generation") == store.generation["generation"], "main experiment raw from another source generation")
        if row["split"] == "FINAL":
            tails[identity] = raw["cooling_180"]["ap_c"] if raw["cooling_180"] else math.nan
            if row["alpha"] is not None:
                archive = row.get("evaluation_archive")
                require(archive is not None and sha(archive["path"]) == archive["sha"], "missing/changed FINAL model-input archive")
                match = re.search(r"_(ATC_WAIT|EDD_WAIT|DIRECT_WAIT|NONDELAY)_S(\d+)_A", identity)
                network = eval_networks[row["device"], match[1], int(match[2])]
                require(archive["network_sha"] == network_sha(network), "FINAL archive model identity")
                require(archive["source_generation"] == store.generation["generation"] and archive["collection"] is False, "FINAL archive capture semantics")
                frames, _ = archive_frames(archive["path"])
                require(all("physical_mask" in f for f in frames), "FINAL capture lacks physical masks")
                replay = replay_frames(network, frames, True, raw["decisions"])
                require(replay["frames"] == archive["frames"], "FINAL archive frame metadata")
                eval_frames += replay["frames"]
        checked += 1
        if checked % 128 == 0:
            save(OUT / "COMPLETION_AUDIT_PROGRESS.json", dict(phase="RAW_AND_FINAL_REPLAY", unix=stamp(), raw_checked=checked,
                total_raw=len(rows), final_frames=eval_frames))
    selection = selection_proof(rows, frozen)
    training = training_proof(rows, frozen, store.generation)
    results = result_proof(final, frozen, tails)
    consumption = read(OUT / "CONSUMPTION.json")
    expected_consumption = {key: receipt_counts[key] for key in ("environments_started", "completed", "failures", "training_completed", "validation_training_completed")}
    expected_consumption.update(environment_cap=store.reg["environment_cap"],
        remaining_environment_starts=store.reg["environment_cap"] - receipt_counts["environments_started"],
        hardware=0, APK=0, physical_fits=0, protected_unchanged=True, goal_met_rows=results["goal_met_rows"])
    close(consumption, expected_consumption, "recomputed consumption")
    source_proof(store, frozen)
    artifact_names = ("FINAL_SUMMARY.json", "FINAL_PAIRS.json.gz", "ALL_ARMS_CONFIDENCE.json", "ALL_ARMS_SEED_SUMMARY.json",
        "NORMAL_ONLY_AUXILIARY.json", "ABLATION_SUMMARY.json", "CHECKPOINT_EXPOSURE.json", "MODEL_CHANGE_PAIRS.json.gz", "CONSUMPTION.json")
    return dict(status="PASS", unix=stamp(), elapsed_s=stamp() - started, source=source, receipts=receipt_counts,
        raw_files=len(rows), physical_and_metric_recomputations=len(rows), final_environments=len(final),
        final_input_roster_sha=digest(roster), final_argmax_replay_frames=eval_frames,
        DEV_selection=selection, training=training, results=results, consumption=expected_consumption,
        freeze_sha=sha(OUT / "FINAL_FREEZE.json"), rows_sha=sha(OUT / "rows.jsonl"), receipts_sha=sha(OUT / "receipts.jsonl"),
        verified_artifact_sha={name: sha(OUT / name) for name in artifact_names},
        evidence_limits=["Fixed simulator coefficients; no new physical identification or real-device validation.",
            "Intervals describe case resampling within each physical layer, not physical coefficient uncertainty.",
            "Current generation main TRAIN and FINAL networks replayed; preserved earlier validation has raw/metric/physical audits.",
            "Training uses three physical layers; fixed-power fourth layer is a counterfactual evaluation control."])


def run(store, frozen):
    """Return PASS only after durable, physical, policy, and statistical checks."""
    try:
        result = _run(store, frozen)
    except Exception as error:
        save(OUT / "COMPLETION_AUDIT.json", dict(status="FAIL", unix=stamp(), error_type=type(error).__name__, error=str(error)))
        raise
    save(OUT / "COMPLETION_AUDIT.json", result)
    save(OUT / "FINAL_AUDIT.json", result)
    save(OUT / "COMPLETION_AUDIT_PROGRESS.json", dict(phase="PASS", unix=stamp(), raw_checked=result["raw_files"],
        final_frames=result["final_argmax_replay_frames"], training_frames=result["training"]["frames"]))
    return result
