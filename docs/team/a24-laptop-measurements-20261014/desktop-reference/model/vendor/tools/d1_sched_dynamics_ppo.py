"""Fresh causal dynamics ABI PPO; no old weights, online rollouts, or device work.

The clipped/episode-weighted PPO equations follow d1_s26_npu_ppo.  This
module intentionally creates a new network/Adam/action RNG/shuffle RNG.
Only ``targets`` may inspect completed-episode labels and cost traces.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn

OBJECTIVE = "DYNAMICS_SERVICE_FIRST_INCREMENTAL_J_AP_V1"
VERSION = "d1-sched-dynamics-native-ppo-v1"
HORIZON_NS = 120_000_000_000


@dataclass(frozen=True)
class ABI:
    schema: str
    state_dim: int
    action_dim: int
    slots: int


def default_abi():
    from tools import d1_sched_dynamics_policy as policy
    return ABI(policy.SCHEMA, policy.STATE_DIM, policy.ACTION_DIM, policy.SLOTS)


@dataclass(frozen=True)
class Settings:
    episodes_per_update: int = 8
    epochs: int = 4
    minibatch_frames: int = 256
    learning_rate: float = .0003
    adam_eps: float = 1e-5
    clip: float = .2
    value_coefficient: float = .5
    entropy_coefficient: float = .01
    gradient_clip: float = .5
    target_kl: float = .03
    service_multiplier: float = 10.
    energy_coefficient: float = 1.
    heat_coefficient: float = 1.
    energy_scale_j: float = 10.
    heat_scale_c_s: float = 120.


def validate_settings(settings):
    for key in ("episodes_per_update", "epochs", "minibatch_frames"):
        v = getattr(settings, key)
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            raise ValueError("positive integer PPO setting: " + key)
    for key, value in asdict(settings).items():
        if not math.isfinite(value) or value < 0:
            raise ValueError("nonfinite/negative PPO setting: " + key)
    if settings.learning_rate <= 0 or settings.adam_eps <= 0 or settings.clip <= 0 or settings.gradient_clip <= 0 or settings.energy_scale_j <= 0 or settings.heat_scale_c_s <= 0:
        raise ValueError("positive PPO/normalization setting required")


class ActorCritic(nn.Module):
    def __init__(self, abi=None):
        super().__init__()
        self.abi = abi or default_abi()
        self.schema_id = self.abi.schema
        if any(not isinstance(v, int) or isinstance(v, bool) or v <= 0 for v in (self.abi.state_dim, self.abi.action_dim, self.abi.slots)):
            raise ValueError("actor ABI dimensions")
        self.state = nn.Sequential(nn.Linear(self.abi.state_dim, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh())
        self.candidate = nn.Sequential(nn.Linear(self.abi.action_dim, 32), nn.Tanh(), nn.Linear(32, 32), nn.Tanh())
        self.actor = nn.Sequential(nn.Linear(96, 64), nn.Tanh(), nn.Linear(64, 1))
        self.critic = nn.Linear(64, 1)
        for layer in self.modules():
            if isinstance(layer, nn.Linear):
                nn.init.orthogonal_(layer.weight, 2**.5)
                nn.init.zeros_(layer.bias)
        nn.init.zeros_(self.actor[-1].weight)
        nn.init.zeros_(self.actor[-1].bias)

    def forward(self, state, candidates, mask):
        a = self.abi
        if state.ndim != 2 or candidates.ndim != 3 or mask.ndim != 2 or state.shape[-1] != a.state_dim or candidates.shape[1:] != (a.slots, a.action_dim) or mask.shape[1] != a.slots or not (state.shape[0] == candidates.shape[0] == mask.shape[0]):
            raise ValueError("new dynamics actor ABI mismatch")
        if mask.dtype != torch.bool or not mask.any(-1).all():
            raise ValueError("all-masked or nonboolean dynamics mask")
        if not torch.isfinite(state).all() or not torch.isfinite(candidates).all():
            raise ValueError("nonfinite dynamics input")
        h = self.state(state)
        c = self.candidate(candidates)
        logits = self.actor(torch.cat((h[:, None, :].expand(-1, a.slots, -1), c), -1)).squeeze(-1)
        return torch.distributions.Categorical(logits=logits.masked_fill(~mask, -torch.inf)), self.critic(h)


class Controller:
    def __init__(self, network, generator=None, deterministic=True, collect=False, *, builder=None, fallback=None):
        self.network = network
        self.generator = generator
        self.deterministic = bool(deterministic)
        self.collect = bool(collect)
        self.builder = builder
        self.fallback = fallback
        if not self.deterministic and self.generator is None:
            raise ValueError("stochastic controller requires separate action RNG")
        self.frames = []
        self.decisions = []
        self.errors = []

    def choose(self, dev, waiting):
        if not waiting:
            return None
        if self.builder is None or self.fallback is None:
            from tools import d1_sched_dynamics_policy as policy
            builder = self.builder or policy.build
            fallback = self.fallback or (lambda d, w: policy.rule_choice(d, w, "EDD"))
        else:
            builder, fallback = self.builder, self.fallback
        start = time.perf_counter_ns()
        try:
            pack = builder(dev, waiting)
            state, vectors, mask, actions = (pack[k] for k in ("state", "candidates", "mask", "actions"))
            physical = pack["physical_mask"]
            a = self.network.abi
            if state.shape != (a.state_dim,) or vectors.shape != (a.slots, a.action_dim) or mask.shape != (a.slots,) or physical.shape != (a.slots,) or mask.dtype != np.bool_ or physical.dtype != np.bool_:
                raise ValueError("controller input ABI mismatch")
            if (mask & ~physical).any() or mask[len(actions):].any() or not mask.any():
                raise ValueError("controller padding/physical mask mismatch")
            build_us = (time.perf_counter_ns() - start) / 1e3
            infer_start = time.perf_counter_ns()
            with torch.no_grad():
                dist, value = self.network(torch.from_numpy(state)[None], torch.from_numpy(vectors)[None], torch.from_numpy(mask)[None])
                probs = dist.probs[0]
                if not torch.isfinite(probs).all() or not torch.isfinite(value).all():
                    raise ValueError("nonfinite PPO output")
                chosen = int(torch.argmax(probs)) if self.deterministic else int(torch.multinomial(probs, 1, generator=self.generator))
                logprob = float(dist.log_prob(torch.tensor([chosen])))
                old_value = float(value[0, 0])
            infer_us = (time.perf_counter_ns() - infer_start) / 1e3
            if not 0 <= chosen < len(actions) or not mask[chosen]:
                raise ValueError("PPO selected illegal/padded action")
            jobs = actions[chosen]
            if jobs and not dev.feasible(jobs):
                raise ValueError("physical state changed before dispatch")
        except (ValueError, RuntimeError, TypeError, KeyError, IndexError, AttributeError) as error:
            jobs = fallback(dev, waiting)
            self.errors.append(repr(error))
            self.decisions.append(dict(now_ns=int(dev.now), queue=len(waiting), model_error=repr(error), chosen=[(q["id"], b) for q, b in jobs or []], total_us=(time.perf_counter_ns()-start)/1e3))
            return jobs or None
        decision = dict(now_ns=int(dev.now), queue=len(waiting), actions=len(actions), physical_legal=int(physical.sum()), legal=int(mask.sum()), chosen=[(q["id"], b) for q, b in jobs], chosen_index=chosen, build_us=build_us, infer_us=infer_us, total_us=(time.perf_counter_ns()-start)/1e3, diagnostics=copy.deepcopy(pack.get("diagnostics", {})))
        self.decisions.append(decision)
        if self.collect:
            self.frames.append(dict(now_ns=int(dev.now), state=state.copy(), candidates=vectors.copy(), mask=mask.copy(), action=chosen, informative=bool(mask.sum() > 1), logprob=logprob, old_value=old_value))
        return jobs or None


def _service_cost(r, n, nu, nn):
    """Original S26 request cost: ns units, original 1.5/6s and declared d."""
    priority = r["priority"]
    den = max(nu if priority == "urgent" else nn, 1)
    d = r["deadline_offset_ns"]
    cap = 1_500_000_000 if priority == "urgent" else 6_000_000_000
    declared_cap = 2_500_000_000 if priority == "urgent" else 9_000_000_000
    if priority not in ("urgent", "normal") or not 0 < d <= declared_cap or not 0 <= r["arrival_ns"] < HORIZON_NS:
        raise ValueError("service reward request ABI/range")
    response = r.get("response_ns", HORIZON_NS-r["arrival_ns"])
    missing = "response_ns" not in r
    weight = 20. if priority == "urgent" else 5.
    return weight*((missing or response > d)+(missing or response > cap))/den + (.2 if priority == "urgent" else .1)*response/cap/den + (2 if priority == "urgent" else 1)*max(response-d, 0)/d/max(n, 1) + 50*(r["status"] != "succeeded")/max(n, 1)


def targets(controller, result, settings=Settings()):
    """Post-episode gamma=1 MC labels; never called by online choose/build.

    service_multiplier*original service cost + incremental J/10J +
    max(AP-referenceAP,0) degree-seconds/120 degree-seconds.  The fixed
    120-second resident energy is subtracted only as an action-independent
    reward constant; reported total energy remains untouched.
    """
    validate_settings(settings)
    frames = copy.deepcopy(controller.frames)
    if not frames:
        raise ValueError("no collected decisions")
    if controller.errors:
        raise ValueError("training episode has model fallback")
    times = np.asarray([f["now_ns"] for f in frames], dtype=np.int64)
    if (np.diff(times) < 0).any() or times[0] < 0 or times[-1] >= HORIZON_NS:
        raise ValueError("decision clock mismatch")
    rewards = np.zeros(len(frames), dtype=np.float64)
    ledger = result["ledger"]
    n = len(ledger)
    nu = sum(r["priority"] == "urgent" for r in ledger)
    nn = n-nu
    service = 0.
    for r in ledger:
        cost = _service_cost(r, n, nu, nn)
        service += cost
        at = r.get("response_at_ns", HORIZON_NS) if r["status"] == "succeeded" else HORIZON_NS
        index = max(0, min(len(frames)-1, int(np.searchsorted(times, at, side="right"))-1))
        rewards[index] -= settings.service_multiplier*cost
    if "service_cost" in result["metrics"] and abs(service-result["metrics"]["service_cost"]) > 1e-8:
        raise ValueError("original service reward mismatch")
    trace = result["learning_cost_trace"]
    if not trace or trace[-1]["time_ns"] != HORIZON_NS:
        raise ValueError("learning cost trace must end at120s")
    baseline = result["metrics"]["resident_baseline_j"]
    if not math.isfinite(baseline) or not 0 <= baseline <= trace[-1]["energy_j"]+1e-8:
        raise ValueError("resident baseline reward mismatch")
    last_t = -1
    last_e = last_a = 0.
    for point in trace:
        t, energy, area = point["time_ns"], point["energy_j"], point["ap_excess_area_c_s"]
        if not isinstance(t, int) or t < last_t or not 0 <= t <= HORIZON_NS or not math.isfinite(energy) or not math.isfinite(area) or energy < last_e-1e-8 or area < last_a-1e-8:
            raise ValueError("learning trace clock/cumulative cost mismatch")
        index = max(0, min(len(frames)-1, int(np.searchsorted(times, t, side="right"))-1))
        resident_interval = baseline*(t-max(last_t, 0))/HORIZON_NS
        rewards[index] -= settings.energy_coefficient*(energy-last_e-resident_interval)/settings.energy_scale_j
        rewards[index] -= settings.heat_coefficient*(area-last_a)/settings.heat_scale_c_s
        last_t, last_e, last_a = t, energy, area
    expected = settings.service_multiplier*service + settings.energy_coefficient*(last_e-baseline)/settings.energy_scale_j + settings.heat_coefficient*last_a/settings.heat_scale_c_s
    if abs(-rewards.sum()-expected) > 1e-7:
        raise ValueError("gamma1 reward telescope mismatch")
    returns = np.cumsum(rewards[::-1])[::-1]
    for frame, ret, reward in zip(frames, returns, rewards):
        frame.update(target=np.array([ret], dtype=np.float32), valid=np.array([True]), reward=float(reward))
    return frames


def prepare(network, episodes):
    if not episodes or any(not episode for episode in episodes):
        raise ValueError("empty episode batch")
    frames = [f for episode in episodes for f in episode]
    n, b, a = len(frames), len(episodes), network.abi
    specs = (("state", (a.state_dim,), np.float32), ("candidates", (a.slots, a.action_dim), np.float32), ("mask", (a.slots,), np.bool_), ("target", (1,), np.float32), ("valid", (1,), np.bool_))
    for frame in frames:
        for key, shape, dtype in specs:
            if frame[key].shape != shape or frame[key].dtype != dtype:
                raise ValueError("rollout ABI: "+key)
            if dtype == np.float32 and not np.isfinite(frame[key]).all():
                raise ValueError("nonfinite rollout: "+key)
        if not 0 <= frame["action"] < a.slots or not frame["mask"][frame["action"]] or not frame["valid"].all():
            raise ValueError("invalid selected action/target")
        if bool(frame["informative"]) != bool(frame["mask"].sum() > 1) or not math.isfinite(frame["logprob"]) or not math.isfinite(frame["old_value"]):
            raise ValueError("collection likelihood/value mismatch")
    d = {k: torch.from_numpy(np.stack([f[k] for f in frames])) for k in ("state", "candidates", "mask", "target", "valid")}
    d["action"] = torch.tensor([f["action"] for f in frames], dtype=torch.long)
    d["old_log"] = torch.tensor([f["logprob"] for f in frames], dtype=torch.float32)
    info = torch.tensor([bool(f["informative"]) for f in frames])
    d["informative"] = info
    old = torch.tensor([f["old_value"] for f in frames], dtype=torch.float32)
    combined = d["target"][:, 0]-old
    aw, vw, ew, kw = (torch.zeros(n) for _ in range(4))
    means, seconds = [], []
    cursor = 0
    for episode in episodes:
        sl = slice(cursor, cursor+len(episode))
        cursor += len(episode)
        ii = info[sl]
        count = int(ii.sum())
        vw[sl] = 1/(b*len(episode))
        if count:
            aw[sl] = ii.float()/b
            ew[sl] = ii.float()/(b*count)
            kw[sl] = ii.float()/count
            means.append(combined[sl][ii].mean())
            seconds.append(combined[sl][ii].square().mean())
    if means:
        center = torch.stack(means).mean()
        denominator = (torch.stack(seconds).mean()-center.square()).clamp(min=0).sqrt()+1e-8
        kw /= len(means)
    else:
        center, denominator = torch.tensor(0.), torch.tensor(1.)
    d.update(combined=(combined-center)/denominator, actor_weight=aw, value_weight=vw, entropy_weight=ew, kl_weight=kw)
    return dict(tensors=d, n=n, normalization=dict(center=float(center), denominator=float(denominator), informative_episodes=len(means)))


def minibatch_losses(network, prepared, indices, settings=Settings(), *, unbiased_scale=False):
    """Episode-weighted clipped PPO; partition-additive before optional N/m."""
    indices = torch.as_tensor(indices, dtype=torch.long)
    if not len(indices):
        raise ValueError("empty PPO minibatch")
    d = prepared["tensors"]
    dist, values = network(d["state"][indices], d["candidates"][indices], d["mask"][indices])
    logprob = dist.log_prob(d["action"][indices])
    ratio = (logprob-d["old_log"][indices]).exp()
    advantage = d["combined"][indices]
    surrogate = torch.minimum(ratio*advantage, ratio.clamp(1-settings.clip, 1+settings.clip)*advantage)
    actor = -(surrogate*d["actor_weight"][indices]).sum()
    valid = d["valid"][indices]
    per_frame = ((values-d["target"][indices]).square()*valid).sum(-1)/valid.sum(-1).clamp(min=1)
    critic = (per_frame*d["value_weight"][indices]).sum()
    entropy = (dist.entropy()*d["entropy_weight"][indices]).sum()
    scale = prepared["n"]/len(indices) if unbiased_scale else 1.
    return dict(loss=(actor+settings.value_coefficient*critic-settings.entropy_coefficient*entropy)*scale, actor=actor*scale, critic=critic*scale, entropy=entropy*scale)


def canonical(obj):
    if isinstance(obj, torch.Tensor):
        return dict(dtype=str(obj.dtype), shape=list(obj.shape), sha=hashlib.sha256(obj.detach().cpu().contiguous().numpy().tobytes()).hexdigest())
    if isinstance(obj, np.ndarray):
        return dict(dtype=str(obj.dtype), shape=list(obj.shape), sha=hashlib.sha256(obj.tobytes()).hexdigest())
    if isinstance(obj, dict):
        return {str(k): canonical(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [canonical(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def digest(obj):
    return hashlib.sha256(json.dumps(canonical(obj), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class Learner:
    def __init__(self, seed, dependencies, settings=Settings(), abi=None):
        validate_settings(settings)
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        self.seed = int(seed)
        self.dependencies = copy.deepcopy(dependencies)
        self.settings = settings
        self.abi = abi or default_abi()
        with torch.random.fork_rng():
            torch.manual_seed(self.seed)
            self.network = ActorCritic(self.abi)
        self.action_rng = torch.Generator().manual_seed(self.seed+10_000_000)
        self.shuffle_rng = torch.Generator().manual_seed(self.seed+20_000_000)
        self.optimizer = torch.optim.Adam(self.network.parameters(), lr=settings.learning_rate, eps=settings.adam_eps)
        self.pending = []
        self.episodes = 0
        self.steps = 0
        self.logs = []
        self.episode_logs = []

    def controller(self, deterministic=False, collect=True):
        return Controller(self.network, self.action_rng, deterministic, collect)

    def add(self, controller, result):
        self.pending.append(targets(controller, result, self.settings))
        self.episodes += 1
        self.episode_logs.append(dict(episode=self.episodes, metrics=copy.deepcopy(result["metrics"])))
        if len(self.pending) >= self.settings.episodes_per_update:
            self.update()

    def update(self):
        if not self.pending:
            raise ValueError("no pending PPO episodes")
        batch = prepare(self.network, self.pending)
        d = batch["tensors"]
        before = copy.deepcopy(self.network.actor.state_dict())
        grads = []
        kl = 0.
        for epoch in range(self.settings.epochs):
            order = torch.randperm(batch["n"], generator=self.shuffle_rng)
            for start in range(0, batch["n"], self.settings.minibatch_frames):
                losses = minibatch_losses(self.network, batch, order[start:start+self.settings.minibatch_frames], self.settings, unbiased_scale=True)
                self.optimizer.zero_grad(set_to_none=True)
                losses["loss"].backward()
                grad = sum(float(x.grad.detach().double().square().sum()) for x in self.network.actor.parameters() if x.grad is not None)**.5
                norm = float(torch.nn.utils.clip_grad_norm_(self.network.parameters(), self.settings.gradient_clip))
                if not math.isfinite(norm):
                    raise ValueError("nonfinite PPO gradient")
                self.optimizer.step()
                self.steps += 1
                grads.append(grad)
            with torch.no_grad():
                dist, _ = self.network(d["state"], d["candidates"], d["mask"])
                kl = float(((d["old_log"]-dist.log_prob(d["action"]))*d["kl_weight"]).sum())
            if not math.isfinite(kl):
                raise ValueError("nonfinite PPO KL")
            if kl > self.settings.target_kl:
                break
        changed = any(not torch.equal(v, self.network.actor.state_dict()[k]) for k, v in before.items())
        self.logs.append(dict(update=len(self.logs)+1, episodes=self.episodes, optimizer_steps=self.steps, frames=batch["n"], epochs=epoch+1, kl=kl, actor_changed=changed, actor_gradient_max=max(grads), normalization=batch["normalization"]))
        self.pending = []

    def finish(self):
        """Only explicit training closure; final/evaluation never calls update."""
        if self.pending:
            self.update()
        if self.pending:
            raise ValueError("unflushed PPO pending episodes")

    def snapshot(self):
        return dict(version=VERSION, schema=self.abi.schema, abi=asdict(self.abi), objective=OBJECTIVE, seed=self.seed, dependencies=copy.deepcopy(self.dependencies), settings=asdict(self.settings), network=copy.deepcopy(self.network.state_dict()), optimizer=copy.deepcopy(self.optimizer.state_dict()), action_rng=self.action_rng.get_state().clone(), shuffle_rng=self.shuffle_rng.get_state().clone(), pending=copy.deepcopy(self.pending), episodes=self.episodes, steps=self.steps, logs=copy.deepcopy(self.logs), episode_logs=copy.deepcopy(self.episode_logs))

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix+".tmp")
        with tmp.open("wb") as f:
            torch.save(self.snapshot(), f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    @classmethod
    def load(cls, path, dependencies, settings=Settings(), abi=None):
        data = torch.load(path, map_location="cpu", weights_only=False)
        expected_abi = abi or default_abi()
        if data["version"] != VERSION or data["schema"] != expected_abi.schema or data["abi"] != asdict(expected_abi) or data["objective"] != OBJECTIVE or data["dependencies"] != dependencies or data["settings"] != asdict(settings):
            raise ValueError("checkpoint ABI/source/settings/objective mismatch")
        learner = cls(data["seed"], dependencies, settings, expected_abi)
        learner.network.load_state_dict(data["network"])
        learner.optimizer.load_state_dict(data["optimizer"])
        learner.action_rng.set_state(data["action_rng"])
        learner.shuffle_rng.set_state(data["shuffle_rng"])
        for key in ("pending", "episodes", "steps", "logs", "episode_logs"):
            setattr(learner, key, copy.deepcopy(data[key]))
        if any(not torch.isfinite(v).all() for v in learner.network.state_dict().values()):
            raise ValueError("nonfinite checkpoint network")
        return learner
