"""Synthetic engine control-flow contracts; no measured workload evaluation."""
import copy
import unittest
from types import SimpleNamespace
from study import C, drop_engine


class Physics:
    cpu_slots = 3
    profile = 'ORIGINAL'
    wait_limit_ns = 10**9
    c = SimpleNamespace(tick_s=.5, baseline=1.)

    def initial(self, temperature):
        return dict(temperature_c=temperature, shared_z=0.)

    def rates(self, temperature, active):
        return {j['request_id']: 1. for j in active}

    def transition(self, state, active, dt):
        return dict(state), dict(increment=0., baseline=dt, dynamic=0., shared=0.,
                                 temperature_area=state['temperature_c'] * dt,
                                 peak=state['temperature_c'], speeds=self.rates(26, active), dt=dt)


class Model:
    def __init__(self):
        self.draws = 0

    def request_context(self, public, request):
        return {}, None

    def admission(self, context, task, potential, protocol):
        return dict(scheduled_to_actual_ns=0, actual_to_queue_ns=0)

    def draw_latent_serial(self, selected, snapshot, potential):
        self.draws += 1
        return dict(stages_ns=[1000000] * 5)


PUBLIC = dict(requests=[dict(request_id='unit-only-0', ordinal=0, task='C', priority='U',
                            scheduled_arrival_ns=35 * 10**9, deadline_ns=36 * 10**9)],
              initial_ap_c=26., service_stop_ns=36 * 10**9,
              drain_stop_ns=37 * 10**9, observation_end_ns=38 * 10**9)
# A synthetic prerequisite fixture for exercising engine control flow only.
UNIT_GUARD = dict(durable_START_consumed=True, start_id='SYNTHETIC_UNIT_ONLY_NO_SCIENTIFIC_START')


class DropContracts(unittest.TestCase):
    def test_drop_keeps_arrival_and_never_draws_work(self):
        model = Model()
        result = drop_engine.run(copy.deepcopy(PUBLIC), model,
                                 lambda s: dict(kind='DROP', request_id='unit-only-0',
                                                reason='PUBLIC_PREDICTED_SLO_VIOLATION'),
                                 Physics(), 'SYNTHETIC', UNIT_GUARD)
        self.assertEqual(len(result['requests']), 1)
        request = result['requests'][0]
        self.assertEqual(request['dropped_ns'], 35 * 10**9)
        self.assertIsNone(request['dispatch_ns'])
        self.assertIsNone(request['response_ns'])
        self.assertIsNone(request['available_ns'])
        self.assertEqual(model.draws, 0)
        self.assertEqual(sum(e['kind'] == 'dropped' for e in result['events']), 1)
        self.assertTrue(all(not t['active'] for t in result['trace']))

    def test_non_drop_synthetic_trajectory_exact(self):
        def actor(state):
            return dict(kind='DISPATCH', request_id='unit-only-0', route='CPU')
        original = C.engine.run(copy.deepcopy(PUBLIC), Model(), actor, Physics(), 'SYNTHETIC', UNIT_GUARD)
        fork = drop_engine.run(copy.deepcopy(PUBLIC), Model(), actor, Physics(), 'SYNTHETIC', UNIT_GUARD)
        self.assertEqual(original, fork)


if __name__ == '__main__':
    unittest.main(verbosity=2)
