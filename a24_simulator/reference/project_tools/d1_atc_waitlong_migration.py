"""Explicit exact continuation of all three terminal-4096 V8 learners; no rollout."""
import copy
import hashlib
from pathlib import Path

import numpy as np
import torch

from tools import d1_atc_waitlink_ppo as learning
from tools import d1_atc_waitlink_study as origin

ARM = "DROP_FLAG_WAIT1"
BASE_EPISODES = 4096
SEEDS = (1013, 1019, 1021)


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_origin(snapshot, dependencies, seed):
    if snapshot["seed"] != seed or snapshot["dependencies"] != dependencies:
        raise ValueError("origin seed/dependencies changed")
    if snapshot["episodes"] != BASE_EPISODES or snapshot["pending"]:
        raise ValueError("origin must be terminal4096 with pending0")
    if len(snapshot["logs"]) != 512 or len(snapshot["episode_logs"]) != BASE_EPISODES:
        raise ValueError("origin update/history mismatch")
    if not np.array_equal(snapshot["multipliers"], [1., 1., *([100.]*6), 20.]):
        raise ValueError("origin objective multipliers changed")
    learner = learning.Learner.from_snapshot(snapshot, dependencies)
    if origin.payload_digest(snapshot) != origin.payload_digest(learner.snapshot()):
        raise ValueError("origin full restore mismatch")
    return learner


def rebind(snapshot, old_dependencies, new_dependencies, seed):
    """Only dependencies.sources/input_sha change. All old learner state stays exact."""
    validate_origin(snapshot, old_dependencies, seed)
    immutable = ("schema", "arm", "sequencing", "objective")
    if any(new_dependencies[k] != old_dependencies[k] for k in immutable):
        raise ValueError("ABI/arm/objective change requires fresh learner")
    if set(new_dependencies) != set(old_dependencies):
        raise ValueError("unexpected dependency migration fields")
    migrated = copy.deepcopy(snapshot)
    migrated["dependencies"] = copy.deepcopy(new_dependencies)
    learner = learning.Learner.from_snapshot(migrated, new_dependencies)
    restored = learner.snapshot()
    if origin.payload_digest(restored) != origin.payload_digest(migrated):
        raise ValueError("new full restore mismatch")
    keys = tuple(k for k in snapshot if k != "dependencies")
    old_payload = {k: snapshot[k] for k in keys}
    new_payload = {k: restored[k] for k in keys}
    if origin.payload_digest(old_payload) != origin.payload_digest(new_payload):
        raise ValueError("migration changed network/Adam/RNG/pending/history")
    # Same public, current-state bank; no simulator or hidden realization.
    f, initial, _ = origin.a.hybrid.load()
    observer = origin.a.Controller(f, initial["initial"], mode=origin.a.RULE, coupling=ARM)
    queue = [dict(id="migration_C", ordinal=0, task="classification", priority="urgent",
                  arrival_ns=35e9, deadline_offset_ns=1.5e9, work_units=1),
             dict(id="migration_D", ordinal=1, task="detection", priority="normal",
                  arrival_ns=35e9, deadline_offset_ns=6e9, work_units=1)]
    lanes = {b: dict(request=None, phase="AVAILABLE", since=35e9, dispatch=None) for b in ("CPU", "GPU")}
    bank = origin.a.bank(queue, lanes, 35e9, observer.estimates, coupling=ARM)
    encoded = observer.encode(queue, lanes, 35e9, bank)
    tensors = [torch.from_numpy(encoded[k])[None] for k in ("state", "candidates", "mask")]
    old_learner = learning.Learner.from_snapshot(snapshot, old_dependencies)
    with torch.no_grad():
        old_dist, old_value = old_learner.network(*tensors)
        new_dist, new_value = learner.network(*tensors)
        actions = torch.tensor(np.flatnonzero(encoded["mask"]), dtype=torch.long)
    if not (torch.equal(old_dist.logits, new_dist.logits) and torch.equal(old_value, new_value)
            and torch.equal(old_dist.log_prob(actions), new_dist.log_prob(actions))):
        raise ValueError("public fixture forward/logprob/value migration mismatch")
    action = torch.Generator(); action.set_state(snapshot["action_rng"].clone())
    shuffle = torch.Generator(); shuffle.set_state(snapshot["shuffle_rng"].clone())
    clone = learning.Learner.from_snapshot(restored, new_dependencies)
    if not torch.equal(torch.rand(5, generator=action), torch.rand(5, generator=clone.action_rng)):
        raise ValueError("migration action RNG replay")
    if not torch.equal(torch.randperm(17, generator=shuffle), torch.randperm(17, generator=clone.shuffle_rng)):
        raise ValueError("migration shuffle RNG replay")
    receipt = dict(seed=seed, arm=ARM, origin_episodes=BASE_EPISODES,
                   origin_updates=len(snapshot["logs"]), origin_Adam_steps=snapshot["steps"],
                   pending=0, objective=snapshot["objective"], schema=snapshot["schema"],
                   old_dependencies_sha=origin.a.native.digest(old_dependencies),
                   new_dependencies_sha=origin.a.native.digest(new_dependencies),
                   exact_non_dependency_payload_sha=origin.payload_digest(old_payload),
                   changed_fields=["dependencies.sources", "dependencies.input_sha"],
                   network_Adam_action_shuffle_pending_history_exact=True,
                   next_rng_exact=True, public_forward_logprob_value_exact=True,
                   new_environments=0, new_learning=0)
    return learner, receipt


def read_origins(folder):
    """Read registration and terminal PT only. No old final/freeze/selection results."""
    folder = Path(folder)
    reg = origin.check(folder)
    models = {}
    for seed in SEEDS:
        path = origin.learner_path(folder / f"seed{seed}", ARM, seed, BASE_EPISODES)
        before = file_sha(path)
        data = torch.load(path, map_location="cpu", weights_only=False)
        validate_origin(data, origin.deps(reg, ARM), seed)
        if file_sha(path) != before:
            raise ValueError("origin changed while read")
        models[seed] = dict(path=path, sha256=before, snapshot=data)
    return reg, models
