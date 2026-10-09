"""Episode-boundary native-PPO learner, without an environment runner.

This module never starts a simulator or charges an experiment budget. The
orchestrator owns every environment/learning start, case cursor and deadline.
Rollouts are complete episodes. A restored learner creates a fresh controller
for the next episode; its archived last controller is not a live engine resume.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import random
import inspect
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch

from tools import d1_list_candidate_rl as core

VERSION = 'list-candidate-episodic-ppo-training-v1'


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
    lambda_eta: float = .01
    lambda_cap: float = 100.


def dependency_manifest(extra=None):
    """Capture code/schema dependencies; the caller adds cache/input contracts."""
    modules = (core, core.p, core.p.model, core.p.memory, core.formula,
               core.p.model.energy, core.p.model.states, core.p.model.common, core.p.model.ap)
    paths = {Path(__file__).resolve(), *(Path(module.__file__).resolve() for module in modules)}
    paths.add(Path(inspect.getsourcefile(core.p.memory.preload_reference)).resolve())
    paths.add(core.ROOT/'tools/d1_list_candidate_rl_engine.py')
    paths.add(core.ROOT/'docs/results/list_candidate_rl_review_01/design_amendment_v4.json')
    manifest = dict(version=VERSION, model_sha256=core.p.MODEL_SHA,
                    initial_sha256=core.p.INITIAL_SHA, torch_version=str(torch.__version__),
                    numpy_version=np.__version__, python_version=list(sys.version_info[:3]), sources={})
    for path in sorted(paths):
        manifest['sources'][path.relative_to(core.ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest['caller_contracts'] = copy.deepcopy(extra or {})
    return manifest


def _canonical(value):
    if isinstance(value, torch.Tensor):
        return dict(tensor_dtype=str(value.dtype), shape=list(value.shape),
                    bytes_sha256=hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest())
    if isinstance(value, np.ndarray):
        return dict(array_dtype=str(value.dtype), shape=list(value.shape),
                    bytes_sha256=hashlib.sha256(value.tobytes()).hexdigest())
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, dict): return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [_canonical(v) for v in value]
    if isinstance(value, set): return sorted((_canonical(v) for v in value), key=lambda x: json.dumps(x, sort_keys=True))
    return value


def state_digest(value):
    return hashlib.sha256(json.dumps(_canonical(value), sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode('utf8')).hexdigest()


def rng_state():
    return dict(python=random.getstate(), numpy=np.random.get_state(), torch=torch.get_rng_state().clone())


def restore_rng(state):
    random.setstate(state['python']); np.random.set_state(state['numpy']); torch.set_rng_state(state['torch'])


def _validate_frames(episodes):
    for episode in episodes:
        for frame in episode:
            for name, shape, dtype in (('state', (56,), np.float32), ('candidates', (8, 28), np.float32),
                                       ('mask', (8,), np.bool_), ('target', (6,), np.float32), ('valid', (6,), np.bool_)):
                array = frame[name]
                if not isinstance(array, np.ndarray) or array.shape != shape or array.dtype != dtype:
                    raise ValueError('rollout ABI mismatch: '+name)
                if dtype == np.float32 and not np.isfinite(array).all(): raise ValueError('nonfinite '+name)
            action = frame['action']
            if not isinstance(action, (int, np.integer)) or not 0 <= action < 8 or not frame['mask'][action]:
                raise ValueError('unsupported rollout action')
            if frame['informative']:
                old = frame.get('old_value')
                if old is None or np.asarray(old).shape != (6,) or not np.isfinite(old).all():
                    raise ValueError('sampled rollout old values missing')
                if frame.get('logprob') is None or not math.isfinite(frame['logprob']):
                    raise ValueError('sampled rollout likelihood missing')
                if int(frame['mask'].sum()) <= 1: raise ValueError('forced action marked sampled')


def prepare_batch(network, episodes, multipliers):
    """Freeze one full-batch normalization and old values for every PPO epoch."""
    if not episodes or not any(episodes): raise ValueError('empty rollout batch')
    _validate_frames(episodes)
    with torch.no_grad(): reference = core.ppo_losses(network, episodes, multipliers)
    frames = [frame for episode in episodes for frame in episode]
    n, b = len(frames), len(episodes)
    tensors = {name: torch.from_numpy(np.stack([frame[name] for frame in frames]))
               for name in ('state', 'candidates', 'mask', 'target', 'valid')}
    tensors['action'] = torch.tensor([frame['action'] for frame in frames], dtype=torch.long)
    tensors['old_log'] = torch.tensor([frame.get('logprob') if frame.get('logprob') is not None else 0. for frame in frames], dtype=torch.float32)
    tensors['informative'] = torch.tensor([bool(frame['informative']) for frame in frames])
    raw_advantage = reference['advantage'].clone()
    weights = torch.tensor(multipliers, dtype=torch.float32)
    if weights.shape != (5,) or not torch.isfinite(weights).all() or (weights < 0).any():
        raise ValueError('invalid multipliers')
    combined = raw_advantage[:, 0]-(raw_advantage[:, 1:]*weights).sum(-1)
    actor_weight = torch.zeros(n); value_weight = torch.zeros(n); entropy_weight = torch.zeros(n); kl_weight = torch.zeros(n)
    means, seconds, slices = [], [], []; cursor = 0
    for episode in episodes:
        sl = slice(cursor, cursor+len(episode)); slices.append(sl); cursor += len(episode)
        info = tensors['informative'][sl]; count = int(info.sum())
        if len(episode): value_weight[sl] = 1./(b*len(episode))
        if count:
            actor_weight[sl] = info.float()/b
            entropy_weight[sl] = info.float()/(b*count)
            kl_weight[sl] = info.float()/count
            selected = combined[sl][info]; means.append(selected.mean()); seconds.append(selected.square().mean())
    if means:
        center = torch.stack(means).mean()
        variance = (torch.stack(seconds).mean()-center.square()).clamp(min=0)
        denominator = variance.sqrt()+1e-8
        combined = (combined-center)/denominator
        kl_weight /= len(means)
    else:
        center, denominator = torch.tensor(0.), torch.tensor(1.)
    tensors.update(combined=combined, actor_weight=actor_weight, value_weight=value_weight,
                   entropy_weight=entropy_weight, kl_weight=kl_weight)
    return dict(tensors=tensors, n=n, episode_count=b, slices=slices,
                normalization=dict(center=float(center), denominator=float(denominator)),
                raw_advantage=raw_advantage, direct_energy=-weights[0]*raw_advantage[:, 1],
                sampled_choices=int(tensors['informative'].sum()), reference=reference)


def minibatch_losses(network, prepared, indices, settings=Settings(), *, unbiased_scale=False):
    """A weighted partition, or N/m-scaled unbiased uniform-frame estimate.

    Unscaled partition losses sum to core.ppo_losses at fixed parameters. The
    scaled losses have the same full objective in expectation; their m/N
    weighted partition sum equals the full objective at fixed parameters.
    Adam takes one step per sampled partition, not one accumulated epoch step.
    """
    indices = torch.as_tensor(indices, dtype=torch.long)
    if not len(indices): raise ValueError('empty minibatch')
    d = prepared['tensors']; dist, values = network(d['state'][indices], d['candidates'][indices], d['mask'][indices])
    logprob = dist.log_prob(d['action'][indices]); ratio = (logprob-d['old_log'][indices]).exp()
    advantage = d['combined'][indices]
    surrogate = torch.minimum(ratio*advantage, ratio.clamp(1-settings.clip, 1+settings.clip)*advantage)
    actor = -(surrogate*d['actor_weight'][indices]).sum()
    valid = d['valid'][indices]
    per_frame = ((values-d['target'][indices]).square()*valid).sum(-1)/valid.sum(-1).clamp(min=1)
    critic = (per_frame*d['value_weight'][indices]).sum()
    entropy = (dist.entropy()*d['entropy_weight'][indices]).sum()
    scale = prepared['n']/len(indices) if unbiased_scale else 1.
    return dict(loss=(actor+settings.value_coefficient*critic-settings.entropy_coefficient*entropy)*scale,
                actor=actor*scale, critic=critic*scale, entropy=entropy*scale, scale=scale)


def dual_update(multipliers, episodes, settings=Settings()):
    updated = np.asarray(multipliers, dtype=np.float64).copy(); means = []
    for channel in range(5):
        values = [float(e['costs'][channel]) for e in episodes if bool(e['valid'][channel+1])]
        if any(not math.isfinite(v) for v in values): raise ValueError('nonfinite valid dual cost')
        if channel and any(v < 0 for v in values): raise ValueError('signed service cost violates positive-part contract')
        mean = float(np.mean(values)) if values else None; means.append(mean)
        if mean is not None: updated[channel] = np.clip(updated[channel]+settings.lambda_eta*mean, 0., settings.lambda_cap)
    return updated, means


def _gradient_norm(parameters):
    return math.sqrt(sum(float(p.grad.detach().double().square().sum()) for p in parameters if p.grad is not None))


class Learner:
    def __init__(self, seed, schema_id, dependency_manifest=None, settings=Settings()):
        if settings != Settings(): raise ValueError('unregistered PPO hyperparameter change')
        torch.set_num_threads(1); torch.use_deterministic_algorithms(True)
        random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
        self.seed, self.schema_id, self.settings = int(seed), schema_id, settings
        self.dependency_manifest = copy.deepcopy(dependency_manifest if dependency_manifest is not None else globals()['dependency_manifest']())
        self.network = core.ActorCritic()
        self.optimizer = torch.optim.Adam(self.network.parameters(), lr=settings.learning_rate, eps=settings.adam_eps)
        self.multipliers = np.asarray([1., 10., 1., 1., 1.], dtype=np.float64)
        self.pending_episodes = []; self.logs = []; self.episode_logs = []; self.failed_updates = []
        self.accepted_episodes = 0; self.update_count = 0; self.optimizer_steps = 0
        self.cursor = None; self.consumption = {}; self.last_controller_state = None; self.extra_rng_states = {}

    def fresh_controller(self, frozen, initial):
        controller = core.Controller(frozen, initial, core.PPO, network=self.network,
                                     deterministic=False, feature_variant='head2+C_next')
        if controller.schema_id != self.schema_id: raise ValueError('fresh controller schema mismatch')
        return controller

    def add_episode(self, data, row, costs, valid, *, controller=None, cursor=None,
                    consumption=None, reference_hash=None, metadata=None, extra_rng_states=None):
        _validate_frames([data])
        costs, valid = np.asarray(costs, dtype=np.float64), np.asarray(valid, dtype=bool)
        if costs.shape != (5,) or valid.shape != (6,): raise ValueError('episode cost ABI')
        if any(not math.isfinite(costs[i]) for i in range(5) if valid[i+1]): raise ValueError('nonfinite valid episode cost')
        if any(not np.array_equal(frame['valid'], valid) or not np.array_equal(frame['target'][1:], costs.astype(np.float32)) for frame in data):
            raise ValueError('episode-wide channel validity/cost targets changed between frames')
        if controller is not None:
            if controller.schema_id != self.schema_id: raise ValueError('episode controller schema mismatch')
            self.last_controller_state = core.controller_state(controller)
        self.pending_episodes.append(copy.deepcopy(dict(data=data, costs=costs, valid=valid,
            row=row, reference_hash=reference_hash, metadata=metadata or {})))
        self.accepted_episodes += 1
        self.cursor = copy.deepcopy(cursor)
        if consumption is not None: self.consumption = copy.deepcopy(consumption)
        if extra_rng_states is not None: self.extra_rng_states = copy.deepcopy(extra_rng_states)
        self.episode_logs.append(copy.deepcopy(dict(number=self.accepted_episodes, row=row, costs=costs,
            valid=valid, reference_hash=reference_hash, metadata=metadata or {},
            sampled_choices=sum(bool(d['informative']) for d in data), frames=len(data))))

    def observe_episode(self, controller, row, curve, reference, **kwargs):
        data, rewards, costs, valid = core.episode_targets(controller, row, curve, reference)
        self.add_episode(data, row, costs, valid, controller=controller, **kwargs)
        return dict(reward_sum=float(rewards.sum()), costs=costs.copy(), valid=valid.copy(), frames=len(data))

    def update_if_ready(self):
        if len(self.pending_episodes) < self.settings.episodes_per_update: return None
        if len(self.pending_episodes) != self.settings.episodes_per_update: raise ValueError('rollout batch exceeded fixed eight episodes')
        before = dict(network=copy.deepcopy(self.network.state_dict()), optimizer=copy.deepcopy(self.optimizer.state_dict()),
                      rng=rng_state(), multipliers=self.multipliers.copy(), optimizer_steps=self.optimizer_steps,
                      update_count=self.update_count, log_count=len(self.logs), pending=self.pending_episodes)
        try:
            return self._update_ready_batch()
        except BaseException as error:
            # An episode-boundary archive never claims a partially applied PPO
            # epoch is complete. The orchestrator records/charges the failure.
            self.network.load_state_dict(before['network']); self.optimizer.load_state_dict(before['optimizer'])
            restore_rng(before['rng']); self.multipliers = before['multipliers']
            self.optimizer_steps = before['optimizer_steps']; self.update_count = before['update_count']
            self.logs = self.logs[:before['log_count']]; self.pending_episodes = before['pending']
            self.optimizer.zero_grad(set_to_none=True)
            self.failed_updates.append(dict(accepted_episodes=self.accepted_episodes, error=repr(error), rolled_back=True))
            raise

    def _update_ready_batch(self):
        episodes = self.pending_episodes; data = [episode['data'] for episode in episodes]
        before_lambda = self.multipliers.copy(); started = time.perf_counter()
        prepared = prepare_batch(self.network, data, before_lambda)
        if not prepared['sampled_choices']: raise ValueError('no informative rollout actions; do not silently train a critic-only batch')
        epoch_logs = []; step_logs = []; early_stop = False
        for epoch in range(self.settings.epochs):
            ordering = torch.randperm(prepared['n'])
            for start in range(0, prepared['n'], self.settings.minibatch_frames):
                indices = ordering[start:start+self.settings.minibatch_frames]
                parts = minibatch_losses(self.network, prepared, indices, self.settings, unbiased_scale=True)
                if not torch.isfinite(parts['loss']): raise ValueError('nonfinite PPO loss')
                self.optimizer.zero_grad(set_to_none=True); parts['loss'].backward()
                gradients = dict(actor=_gradient_norm(self.network.actor.parameters()),
                                 critic=_gradient_norm(self.network.critic.parameters()),
                                 state=_gradient_norm(self.network.state.parameters()),
                                 candidate=_gradient_norm(self.network.candidate.parameters()))
                total_gradient = float(torch.nn.utils.clip_grad_norm_(self.network.parameters(), self.settings.gradient_clip))
                if not math.isfinite(total_gradient): raise ValueError('nonfinite PPO gradient')
                self.optimizer.step(); self.optimizer_steps += 1
                step_logs.append(dict(epoch=epoch+1, frames=len(indices), scale=parts['scale'],
                    loss=float(parts['loss'].detach()), actor=float(parts['actor'].detach()),
                    critic=float(parts['critic'].detach()), entropy=float(parts['entropy'].detach()),
                    gradient_before_clip=total_gradient, gradients=gradients))
            with torch.no_grad():
                d = prepared['tensors']
                dist, _ = self.network(d['state'], d['candidates'], d['mask'])
                kl = float(((d['old_log']-dist.log_prob(d['action']))*d['kl_weight']).sum())
            epoch_logs.append(dict(epoch=epoch+1, sampled_old_minus_new_kl=kl))
            if kl > self.settings.target_kl: early_stop = True; break
        self.multipliers, means = dual_update(before_lambda, episodes, self.settings)
        self.update_count += 1
        advantage = prepared['raw_advantage']
        contributions = torch.cat((advantage[:, :1], -advantage[:, 1:]*torch.tensor(before_lambda, dtype=torch.float32)), dim=1)
        log = dict(update=self.update_count, accepted_episodes=self.accepted_episodes,
            batch_episodes=len(episodes), frames=prepared['n'], sampled_choices=prepared['sampled_choices'],
            lambda_before=before_lambda.tolist(), lambda_after=self.multipliers.tolist(), dual_valid_means=means,
            normalization=prepared['normalization'], raw_advantage_mean=advantage.mean(0).tolist(),
            combined_component_means=contributions.mean(0).tolist(),
            direct_energy_max=float(prepared['direct_energy'].abs().max()),
            epochs=epoch_logs, steps=step_logs, optimizer_steps_cumulative=self.optimizer_steps,
            early_stop=early_stop, seconds=time.perf_counter()-started,
            actor_aggregation='episode-sum/8; uniform-frame minibatch N/m scale',
            critic_entropy_aggregation='episode-mean/8', gamma=1.)
        self.logs.append(log); self.pending_episodes = []
        return copy.deepcopy(log)

    def snapshot(self):
        return dict(version=VERSION, seed=self.seed, schema_id=self.schema_id, settings=asdict(self.settings),
                    dependencies=copy.deepcopy(self.dependency_manifest), network=copy.deepcopy(self.network.state_dict()),
                    optimizer=copy.deepcopy(self.optimizer.state_dict()), multipliers=self.multipliers.copy(),
                    pending_episodes=copy.deepcopy(self.pending_episodes), logs=copy.deepcopy(self.logs),
                    episode_logs=copy.deepcopy(self.episode_logs), failed_updates=copy.deepcopy(self.failed_updates),
                    accepted_episodes=self.accepted_episodes,
                    update_count=self.update_count, optimizer_steps=self.optimizer_steps,
                    cursor=copy.deepcopy(self.cursor), consumption=copy.deepcopy(self.consumption),
                    last_controller_state=copy.deepcopy(self.last_controller_state), extra_rng_states=copy.deepcopy(self.extra_rng_states),
                    rng=rng_state(), archive_scope='completed-episode learner/controller archive; next engine must be fresh')

    def save(self, path):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix+'.tmp')
        payload = self.snapshot()
        with temporary.open('wb') as stream:
            torch.save(payload, stream); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @classmethod
    def load(cls, path, *, expected_schema_id, expected_dependencies, expected_settings=Settings()):
        payload = torch.load(path, map_location='cpu', weights_only=False)
        if (payload['version'] != VERSION or payload['schema_id'] != expected_schema_id
                or payload['dependencies'] != expected_dependencies or payload['settings'] != asdict(expected_settings)):
            raise ValueError('learner source/schema/input/cache/settings mismatch')
        learner = cls(payload['seed'], expected_schema_id, expected_dependencies, expected_settings)
        learner.network.load_state_dict(payload['network']); learner.optimizer.load_state_dict(payload['optimizer'])
        for name in ('multipliers', 'pending_episodes', 'logs', 'episode_logs', 'failed_updates', 'accepted_episodes', 'update_count',
                     'optimizer_steps', 'cursor', 'consumption', 'last_controller_state', 'extra_rng_states'):
            setattr(learner, name, copy.deepcopy(payload[name]))
        restore_rng(payload['rng'])
        return learner

