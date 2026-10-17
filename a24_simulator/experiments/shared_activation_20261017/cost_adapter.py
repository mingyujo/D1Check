"""Opt-in evaluator and public nominal candidate cost for the new generation."""
from pathlib import Path
import hashlib
import json
from shared_cost import SharedActivationCost

ROOT = Path(__file__).resolve().parents[2]


class CostObserver:
    def __init__(self, shared_scale=None, idle_decay_s=None):
        config = json.loads((Path(__file__).parent/'COST_BUNDLE.json').read_text(encoding='utf-8'))
        pin = config['steady_model']
        path = ROOT/pin['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin['sha256']:
            raise ValueError('Frozen steady model changed')
        model = json.loads(path.read_text(encoding='utf-8'))
        self.engine = SharedActivationCost(model,
            config['shared_scale'] if shared_scale is None else shared_scale,
            config['idle_decay_s'] if idle_decay_s is None else idle_decay_s)

    def observe(self, summary, lo, hi, history_start=0., initial_shared=0.):
        cost = self.engine.observe(summary['gantt'], lo, hi, history_start, initial_shared)
        return dict(conditional_state_cost=cost,
            full_episode=self.engine.episode(summary['gantt'], history_start, initial_shared),
            current_cost_state=cost['shared_activation_state'],
            simulations_started=0, NN_updates=0, physical_model_revalidated=False,
            model_role='hypothesis-enabled scheduling research; opt-in new generation')

    def marginal(self, past_owners, nominal_reservations, candidate, now, horizon, **kwargs):
        return self.engine.marginal(past_owners, nominal_reservations, candidate, now, horizon, **kwargs)

    def annotate(self, summary, lo, hi, **kwargs):
        return dict(summary, shared_activation_cost=self.observe(summary, lo, hi, **kwargs))
