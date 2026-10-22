"""Fresh masked set-PPO for the separately registered A24 rolling experiment.

Set encoder/actor/critic equations adapted verbatim from the original GEN002
ppo.py (SHA256 a029c96ac7c0bbcc3c9eabd4ba23dabcf08283d3ed6530b4fe7f0b190c8e88b1).
No import of that experiment, its candidate builder, or its checkpoints occurs.
Construction/training is performed only by the registered experiment runner.
"""
from __future__ import annotations
import copy
import hashlib
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import numpy as np
import torch
from torch import nn

VERSION = "a24-rolling-atc-rl-native-v1"
SCHEMA = "req24x24-res3x12-global24-actions80x16-fivecost-v1"
ALPHAS = (.70, .80, .90, .95, 1.)
INPUTS = ("requests", "resources", "global_state", "features", "request_index", "backend_index", "mask")
FAMILIES = ("JOINT_ATC_RL", "ATC_ROUTE_RL", "ATC_RESIDUAL_RL", "NO_ATC_RL")


@dataclass(frozen=True)
class Settings:
    episodes_per_update: int = 8
    epochs: int = 3
    minibatch_frames: int = 256
    learning_rate: float = 3e-4
    clip: float = .2
    value_coef: float = .5
    entropy_coef: float = .01
    gradient_clip: float = .5
    kl_stop: float = .03
    gae_time_s: float = 20.
    dual_lr: float = 5.


class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.request = nn.Sequential(nn.Linear(24, 64), nn.Tanh())
        self.resource = nn.Sequential(nn.Linear(12, 32), nn.Tanh())
        self.state = nn.Sequential(nn.Linear(188, 128), nn.Tanh(), nn.Linear(128, 64), nn.Tanh())
        self.actor = nn.Sequential(nn.Linear(176, 64), nn.Tanh(), nn.Linear(64, 1))
        self.critic = nn.Linear(64, 5)
        for layer in self.modules():
            if isinstance(layer, nn.Linear):
                nn.init.orthogonal_(layer.weight, math.sqrt(2))
                nn.init.zeros_(layer.bias)
        nn.init.zeros_(self.actor[-1].weight)

    def forward(self, requests, resources, global_state, features, request_index, backend_index, mask):
        present = requests[:, :, -1:]
        encoded = self.request(requests)
        mean = (encoded * present).sum(1) / present.sum(1).clamp_min(1)
        maximum = encoded.masked_fill(present == 0, -1e9).max(1).values
        maximum = torch.where(present.sum(1) > 0, maximum, torch.zeros_like(maximum))
        state = self.state(torch.cat((mean, maximum, resources.flatten(1), global_state), -1))
        reqenc = torch.gather(encoded, 1, request_index[:, :, None].expand(-1, -1, 64))
        resenc = torch.gather(self.resource(resources), 1, backend_index[:, :, None].expand(-1, -1, 32))
        executing = 1 - features[:, :, 3:4]
        joint = torch.cat((reqenc * executing, resenc * executing,
                           state[:, None, :].expand(-1, features.shape[1], -1), features), -1)
        return self.actor(joint).squeeze(-1).masked_fill(~mask, -1e9), self.critic(state)


def input_digest(bank):
    digest = hashlib.sha256()
    for key in (*INPUTS, "prior_logits"):
        value = np.ascontiguousarray(bank[key])
        digest.update(key.encode())
        digest.update(value.dtype.str.encode())
        digest.update(repr(value.shape).encode())
        digest.update(value.tobytes())
    return digest.hexdigest()


def network_digest(network):
    digest = hashlib.sha256()
    for name, value in sorted(network.state_dict().items()):
        a = value.detach().cpu().contiguous().numpy()
        digest.update(name.encode())
        digest.update(a.dtype.str.encode())
        digest.update(repr(a.shape).encode())
        digest.update(a.tobytes())
    return digest.hexdigest()


def checked_bank(bank, family):
    """Copy exact typed public inputs; physical/hierarchy masks are caller-owned."""
    typed = {}
    for key in INPUTS:
        dtype = np.bool_ if key == "mask" else np.int64 if key.endswith("index") else np.float32
        typed[key] = np.asarray(bank[key], dtype=dtype).copy()
    q, r, g, f = (typed[k] for k in ("requests", "resources", "global_state", "features"))
    n = len(f)
    if not (q.shape == (24, 24) and r.shape == (3, 12) and g.shape == (24,) and f.shape == (80, 16)):
        raise ValueError("set-PPO input ABI must be exactly 24x24,3x12,24,80x16")
    for key in ("mask", "request_index", "backend_index"):
        if typed[key].shape != (n,):
            raise ValueError("action-vector shape: " + key)
    if not typed["mask"].any():
        raise ValueError("empty hierarchy mask; engine must supply a legal no-dispatch action")
    if np.any(typed["request_index"] < 0) or np.any(typed["request_index"] >= 24):
        raise ValueError("request gather index")
    if np.any(typed["backend_index"] < 0) or np.any(typed["backend_index"] >= 3):
        raise ValueError("resource gather index")
    physical = np.asarray(bank.get("physical_mask", typed["mask"]), dtype=np.bool_).copy()
    if physical.shape != (n,) or np.any(typed["mask"] & ~physical):
        raise ValueError("hierarchy mask must be a subset of physical mask")
    if family == "ATC_RESIDUAL_RL":
        if "prior_logits" not in bank:
            raise ValueError("ATC residual requires predeclared normalized ATC prior_logits")
        prior = np.asarray(bank["prior_logits"], dtype=np.float32).copy()
        if prior.shape != (n,) or not np.isfinite(prior).all():
            raise ValueError("invalid ATC prior")
    else:
        prior = np.zeros(n, dtype=np.float32)
    typed["prior_logits"] = prior
    typed["physical_mask"] = physical
    if any(not np.isfinite(typed[k]).all() for k in ("requests", "resources", "global_state", "features")):
        raise ValueError("nonfinite public input")
    return typed


def tensors(bank):
    return [torch.from_numpy(bank[key]).unsqueeze(0) for key in INPUTS]


class Controller:
    def __init__(self, learner, alpha, heat, collect):
        if alpha not in ALPHAS or not 0 <= heat <= 1:
            raise ValueError("unregistered alpha/heat")
        self.learner, self.alpha, self.heat, self.collect = learner, alpha, heat, collect
        self.frames, self.decisions = [], []
        self.network_sha256 = network_digest(learner.net)
        self.capture_inputs = True

    def choose(self, bank, time_ns, collect=None):
        """Return an action index. Evaluation uses argmax and consumes no action RNG."""
        collect = self.collect if collect is None else bool(collect)
        typed = checked_bank(bank, self.learner.family)
        if self.frames and int(time_ns) < self.frames[-1]["time_ns"]:
            raise ValueError("nonmonotonic decision time")
        before = self.learner.action_rng.get_state().clone()
        with torch.no_grad():
            residual, value = self.learner.net(*tensors(typed))
            logits = (residual + torch.from_numpy(typed["prior_logits"])[None, :]).masked_fill(
                ~torch.from_numpy(typed["mask"])[None, :], -1e9)
            logp = logits.log_softmax(-1)
            if not torch.isfinite(logits).all() or not torch.isfinite(value).all():
                raise ValueError("nonfinite network output; no implicit fallback/recollection")
            idx = int(torch.multinomial(logp.exp()[0], 1, generator=self.learner.action_rng)) if collect else int(logits[0].argmax())
        if not typed["mask"][idx] or not typed["physical_mask"][idx]:
            raise ValueError("sample outside legal mask")
        frame = dict(time_ns=int(time_ns), index=idx, old_logp=float(logp[0, idx]),
                     value=value[0].numpy().copy(), learn_actor=int(typed["mask"].sum()) > 1,
                     alpha=float(self.alpha), heat=float(self.heat), input_sha=input_digest(typed),
                     network_sha256=self.network_sha256, optimizer_steps=self.learner.steps,
                     action_rng_before=before, action_rng_after=self.learner.action_rng.get_state().clone(),
                     collect=collect, **typed)
        self.frames.append(frame)
        self.decisions.append(dict(time_ns=int(time_ns), index=idx, logprob=frame["old_logp"],
                                   critic=frame["value"].tolist(), input_sha=frame["input_sha"],
                                   network_sha256=self.network_sha256, collect=collect))
        return idx


def label_episode(frames, costs, alpha, counts, settings):
    if not frames:
        raise ValueError("empty episode cannot train")
    costs = np.asarray(costs, dtype=np.float64)
    if costs.shape != (len(frames), 5) or not np.isfinite(costs).all():
        raise ValueError("cost increments must be finite [decision,5]")
    if alpha not in ALPHAS or any(abs(f["alpha"] - alpha) > 1e-8 for f in frames):
        raise ValueError("episode alpha mismatch")
    if any(not f["collect"] for f in frames):
        raise ValueError("argmax evaluation frames cannot train")
    times = np.array([f["time_ns"] for f in frames], dtype=np.int64)
    if (np.diff(times) < 0).any():
        raise ValueError("nonmonotonic labels")
    values = np.stack([f["value"] for f in frames]).astype(np.float64)
    returns = np.cumsum(costs[::-1], axis=0)[::-1].copy()
    advantages = np.zeros_like(costs)
    following = np.zeros(5)
    for i in reversed(range(len(frames))):
        nextvalue = values[i + 1] if i + 1 < len(frames) else np.zeros(5)
        dt = (times[i + 1] - times[i]) / 1e9 if i + 1 < len(frames) else 0.
        following = costs[i] + nextvalue - values[i] + math.exp(-dt / settings.gae_time_s) * following
        advantages[i] = following
    labelled = copy.deepcopy(frames)
    for i, frame in enumerate(labelled):
        frame.update(cost=costs[i].astype(np.float32), target=returns[i].astype(np.float32), adv=advantages[i].astype(np.float32))
    totals = costs.sum(0)
    error = float(np.max(np.abs(returns[0] - totals)))
    if error > 1e-8:
        raise ValueError("cost telescope")
    meta = dict(total_cost=totals.tolist(), telescope_error=error, alpha=float(alpha),
                role_counts={"urgent": int(counts.get("urgent", counts.get("U", 0))),
                             "normal": int(counts.get("normal", counts.get("N", 0)))},
                frames=len(frames), actor_frames=sum(f["learn_actor"] for f in frames))
    return labelled, meta


def pack(episodes):
    frames = [frame for episode in episodes for frame in episode]
    data = {key: torch.from_numpy(np.stack([f[key] for f in frames])) for key in INPUTS}
    for key in ("value", "target", "adv", "prior_logits"):
        data[key] = torch.from_numpy(np.stack([f[key] for f in frames]))
    data["index"] = torch.tensor([f["index"] for f in frames], dtype=torch.long)
    data["old_logp"] = torch.tensor([f["old_logp"] for f in frames], dtype=torch.float32)
    data["actor_valid"] = torch.tensor([f["learn_actor"] for f in frames], dtype=torch.bool)
    n, ne = len(frames), len(episodes)
    data["value_weight"] = torch.tensor([n / (ne * len(ep)) for ep in episodes for _ in ep])
    data["actor_weight"] = torch.tensor([n / (ne * max(1, sum(f["learn_actor"] for f in ep))) for ep in episodes for _ in ep])
    return data, frames


class Learner:
    def __init__(self, seed, family="ATC_RESIDUAL_RL", settings=None):
        if family not in FAMILIES:
            raise ValueError("unknown family: " + str(family))
        self.seed, self.family, self.settings = int(seed), family, settings or Settings()
        # Network initialization cannot perturb any external/environment RNG.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(self.seed)
            self.net = Net()
        self.opt = torch.optim.Adam(self.net.parameters(), lr=self.settings.learning_rate, eps=1e-5)
        self.action_rng = torch.Generator().manual_seed(self.seed + 100000)
        self.shuffle_rng = torch.Generator().manual_seed(self.seed + 200000)
        self.duals = np.tile(np.array([10., 10., 50.]), (5, 1))
        self.pending, self.pending_meta, self.logs = [], [], []
        self.episodes = self.steps = self.updates = 0

    def controller(self, alpha=.95, heat=.5, collect=False):
        return Controller(self, alpha, heat, collect)

    def add_episode(self, frames, costs, alpha, counts):
        labelled, meta = label_episode(frames, costs, alpha, counts, self.settings)
        current_network_sha = network_digest(self.net)
        if any(f["network_sha256"] != current_network_sha for f in labelled):
            raise ValueError("episode was collected by a different network")
        self.pending.append(labelled)
        self.pending_meta.append(meta)
        self.episodes += 1
        if len(self.pending) >= self.settings.episodes_per_update:
            self.update()
        return meta

    def update(self):
        if not self.pending:
            raise ValueError("no pending experiences")
        data, frames = pack(self.pending)
        weighted = []
        for frame in frames:
            ai = ALPHAS.index(frame["alpha"])
            weights = np.r_[1 - frame["heat"], frame["heat"], self.duals[ai]]
            weighted.append(-float(frame["adv"] @ weights))
        advantage = torch.tensor(weighted, dtype=torch.float32)
        valid = data["actor_valid"]
        selected = advantage[valid]
        if len(selected) > 1:
            advantage = (advantage - selected.mean()) / selected.std(unbiased=False).clamp_min(1e-8)
        n, settings = len(frames), self.settings
        kls, losses, stop = [], [], False
        for _epoch in range(settings.epochs):
            permutation = torch.randperm(n, generator=self.shuffle_rng)
            for start in range(0, n, settings.minibatch_frames):
                ids = permutation[start:start + settings.minibatch_frames]
                residual, values = self.net(*[data[key][ids] for key in INPUTS])
                logits = (residual + data["prior_logits"][ids]).masked_fill(~data["mask"][ids], -1e9)
                logp = logits.log_softmax(-1)
                chosen = logp.gather(1, data["index"][ids, None]).squeeze(1)
                logratio = chosen - data["old_logp"][ids]
                ratio = logratio.exp()
                av, aw = valid[ids], data["actor_weight"][ids]
                surrogate = torch.minimum(ratio * advantage[ids], ratio.clamp(1-settings.clip, 1+settings.clip) * advantage[ids])
                actor = -(surrogate * av * aw).mean()
                entropy = -(logp.exp() * logp).sum(-1)
                critic = ((values - data["target"][ids]).square().mean(-1) * data["value_weight"][ids]).mean()
                loss = actor + settings.value_coef * critic - settings.entropy_coef * (entropy * av * aw).mean()
                if not torch.isfinite(loss):
                    raise ValueError("nonfinite PPO loss")
                self.opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), settings.gradient_clip)
                self.opt.step()
                self.steps += 1
                kl = float(((ratio - 1) - logratio)[av].mean().detach()) if av.any() else 0.
                kls.append(kl)
                losses.append(float(loss.detach()))
                if kl > settings.kl_stop:
                    stop = True
                    break
            if stop:
                break
        for ai, alpha in enumerate(ALPHAS):
            rows = [m for m in self.pending_meta if m["alpha"] == alpha]
            for j, role in enumerate(("urgent", "normal", "incomplete")):
                observed = [m["total_cost"][j + 2] for m in rows if role == "incomplete" or m["role_counts"][role] > 0]
                if observed:
                    budget = 0. if role == "incomplete" else 1 - alpha
                    self.duals[ai, j] = np.clip(self.duals[ai, j] + settings.dual_lr * (np.mean(observed) - budget), 0, 200)
        self.updates += 1
        log = dict(update=self.updates, episodes=self.episodes, frames=n, actor_frames=int(valid.sum()),
                   adam_steps=self.steps, loss_mean=float(np.mean(losses)), kl_max=max(kls),
                   early_stop=stop, duals=self.duals.tolist())
        self.logs.append(log)
        self.pending, self.pending_meta = [], []
        return log

    def snapshot(self):
        return copy.deepcopy(dict(version=VERSION, schema=SCHEMA, seed=self.seed, family=self.family,
            settings=asdict(self.settings), network=self.net.state_dict(), optimizer=self.opt.state_dict(),
            network_sha256=network_digest(self.net), action_rng=self.action_rng.get_state(),
            shuffle_rng=self.shuffle_rng.get_state(), duals=self.duals, episodes=self.episodes,
            steps=self.steps, updates=self.updates, logs=self.logs, pending=self.pending, pending_meta=self.pending_meta))

    def save_snapshot(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        torch.save(self.snapshot(), temp)
        with temp.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(temp, path)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @classmethod
    def load_snapshot(cls, path):
        snapshot = torch.load(path, map_location="cpu", weights_only=False)
        if snapshot["version"] != VERSION or snapshot["schema"] != SCHEMA:
            raise ValueError("checkpoint ABI")
        learner = cls(snapshot["seed"], snapshot["family"], Settings(**snapshot["settings"]))
        learner.net.load_state_dict(snapshot["network"])
        learner.opt.load_state_dict(snapshot["optimizer"])
        learner.action_rng.set_state(snapshot["action_rng"])
        learner.shuffle_rng.set_state(snapshot["shuffle_rng"])
        for key in ("duals", "episodes", "steps", "updates", "logs", "pending", "pending_meta"):
            setattr(learner, key, snapshot[key])
        if network_digest(learner.net) != snapshot["network_sha256"]:
            raise ValueError("checkpoint network digest")
        return learner


def replay_frame(network, frame):
    """Read-only saved-input logprob/critic/argmax audit; never samples RNG."""
    if input_digest(frame) != frame["input_sha"]:
        raise ValueError("saved NN input digest")
    with torch.no_grad():
        residual, value = network(*tensors(frame))
        logits = (residual + torch.from_numpy(frame["prior_logits"])[None, :]).masked_fill(
            ~torch.from_numpy(frame["mask"])[None, :], -1e9)
        logp = logits.log_softmax(-1)
    return dict(logprob=float(logp[0, frame["index"]]), critic=value[0].numpy().copy(),
                argmax=int(logits[0].argmax()), input_sha=input_digest(frame),
                network_sha256=network_digest(network))
