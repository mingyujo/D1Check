"""Bounded deterministic regressions. No engine.run, training or fit calls."""
import copy
from dataclasses import replace
import gzip
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from a24_logic_repair_20261019 import load_components
C = load_components()
from a24_logic_repair_20261019.forecast import predict, predict_actions
from a24_logic_repair_20261019.physics import idle_peak

NS = 1_000_000_000


def request(rid='job', *, task='D', arrival=0., due=10., priority='U', ordinal=0):
    return dict(request_id=rid, ordinal=ordinal, task=task, priority=priority,
                scheduled_arrival_ns=round(arrival * NS), deadline_ns=round(due * NS))


def snapshot(jobs=(), owners=(), now=0.):
    return dict(now_ns=round(now * NS), queue=list(jobs), owners=list(owners),
                wait_used_ns=0, sensor=dict(temperature_c=27., shared_z=0.,
                                           peak_c=27., increment_so_far=0.))


class UnitPhysics:
    """Independent known answer: unit work/s, unit power/job, constant 27 C."""
    def __init__(self):
        self.c = SimpleNamespace(idle_c=26.)
        self.solo = {t + '_' + r: 1. for t in ('classification', 'detection')
                     for r in ('CPU', 'GPU')}
        self.active_calls = []

    def speed(self, *args):
        return 1.

    def rates(self, T, active):
        return {o['request_id']: 1. for o in active}

    def transition(self, state, active, dt):
        self.active_calls.append((len(active), dt))
        return copy.deepcopy(state), dict(
            increment=len(active) * dt, temperature_area=27 * dt,
            peak=27., speeds=self.rates(27, active))


def vectors(jobs, vec=(0., 1., 0., 0., 0.)):
    return {(j['request_id'], r): list(vec) for j in jobs for r in ('CPU', 'GPU')}


def dispatch(rid='job', route='CPU'):
    return dict(kind='DISPATCH', request_id=rid, route=route)


class ForecastRegression(unittest.TestCase):
    def test_capped_cost_has_truthful_coverage(self):
        j = request(due=2000.)
        p = UnitPhysics()
        f = predict(snapshot([j]), dispatch(), [j], vectors([j], (0, 1000, 0, 0, 0)),
                    p, dict(service_stop_s=3100.))
        self.assertTrue(f['capped'])
        self.assertEqual(f['steps'], 800)
        self.assertEqual(f['requested_H_s'], 3000.)
        self.assertEqual(f['H_s'], 400.)
        self.assertEqual(f['cost'][0], 400.)
        self.assertAlmostEqual(f['cost'][1], .1)

    def test_capped_candidates_use_same_prefix(self):
        j = request(due=2000.)
        s, v = snapshot([j]), vectors([j], (0, 1000, 0, 0, 0))
        before = copy.deepcopy((s, v))
        actions = [dispatch(), dict(kind='WAIT', wait_ns=50_000_000)]
        fs = predict_actions(s, actions, [j], v, UnitPhysics(), dict(service_stop_s=3100.))
        self.assertEqual((s, v), before)
        self.assertEqual(fs[0]['H_s'], fs[1]['H_s'])
        self.assertAlmostEqual(fs[0]['H_s'], 399.55)
        for f in fs:
            self.assertTrue(f['comparison_complete'])
            self.assertTrue(f['horizon_reduced'])
            self.assertTrue(f['capped'])
            self.assertLessEqual(f['evaluation_steps'], 1600)
            self.assertAlmostEqual(f['cost'][1], .1)
        self.assertAlmostEqual(fs[0]['cost'][0], fs[0]['H_s'])
        self.assertAlmostEqual(fs[1]['cost'][0], fs[0]['H_s'] - .05)

    def test_completion_exactly_at_horizon_counts(self):
        j = request(due=1.)
        f = predict(snapshot([j]), dispatch(), [j], vectors([j]),
                    UnitPhysics(), dict(service_stop_s=1.))
        self.assertEqual(f['H_s'], 1.)
        self.assertEqual(f['cost'], [1., .1, 0., 0., 0.])
        self.assertFalse(f['capped'])

    def test_zero_work_phases_consume_no_time_or_slot(self):
        jobs = [request(str(i), due=0., ordinal=i) for i in range(5)]
        p = UnitPhysics()
        f = predict(snapshot(jobs), dispatch('0'), jobs, vectors(jobs, (0, 0, 0, 0, 0)),
                    p, dict(service_stop_s=10.))
        self.assertEqual(f['cost'], [0., .1, 0., 0., 0.])
        self.assertTrue(all(n == 0 for n, dt in p.active_calls))

    def test_existing_owner_uses_original_deadline_length(self):
        owner = {**request(arrival=-9., due=1.), 'route': 'CPU', 'stage': 2,
                 'public_progress_s': 0., 'response_ns': None}
        s = snapshot(owners=[owner], now=2.)
        f = predict(s, dict(kind='WAIT', wait_ns=0), [],
                    vectors([owner], (0, 0, 2, 0, 0)), UnitPhysics(),
                    dict(service_stop_s=4.))
        self.assertAlmostEqual(f['cost'][2], 1 + .02 * 3 / 10)
        self.assertEqual(f['cost'][4], 0.)

    def test_c_response_output_and_d_response_persistence(self):
        # Only stage 2 extends past H: C responded, D has not responded.
        costs = []
        for task in ('C', 'D'):
            j = request(task=task, due=1.)
            f = predict(snapshot([j]), dispatch(), [j], vectors([j], (0, .5, 2, 0, 0)),
                        UnitPhysics(), dict(service_stop_s=1.))
            costs.append(f['cost'])
        self.assertEqual(costs[0][2], 0.)
        self.assertEqual(costs[1][2], 1.)
        self.assertEqual([c[4] for c in costs], [1., 1.])

    def test_step_budget_validation(self):
        j = request()
        with self.assertRaises(ValueError):
            predict(snapshot([j]), dispatch(), [j], vectors([j]), UnitPhysics(),
                    dict(service_stop_s=10.), max_steps=0)


class ComponentFixture:
    @classmethod
    def setUpClass(cls):
        root = HERE.parents[1]
        cls.model = json.loads((root / 'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json').read_text())
        op = json.loads((HERE.parent / 'a24_parallel_20261018/OPERATION.json').read_text(encoding='utf-8'))
        cls.config = C.B.Config(**op['physics'])
        cls.shape = json.loads((HERE.parent / 'a24_s26_method_20261019/SHAPE.json').read_text())
        cls.physics = C.Physics(cls.model, cls.config, 'ORIGINAL', cls.shape)
        spec = importlib.util.spec_from_file_location('_test_frozen_physics', HERE.parent / 'a24_s26_method_20261019/physics.py')
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        cls.old = m.Physics(cls.model, cls.config, 'ORIGINAL', cls.shape)


class PhysicsRegression(ComponentFixture, unittest.TestCase):
    def test_idle_peak_matches_independent_ode_integration(self):
        # RK4 integrates dT/dt=(idle-T+R*shared*z)/tau, dz/dt=-z/tz.
        # Both distinct and equal decay constants; no reuse of analytic formula.
        for tz in (.9, 25., 40.):
            cfg = replace(self.config, idle_tail_s=tz)
            for T0 in (26., 27., 35.):
                T, z, peak, h = T0, 1., T0, .001
                def rhs(t, z):
                    return ((cfg.idle_c - t + cfg.thermal_resistance * self.physics.shared * z)
                            / cfg.thermal_tau_s, -z / tz)
                for _ in range(30000):
                    k1, l1 = rhs(T, z)
                    k2, l2 = rhs(T + h*k1/2, z + h*l1/2)
                    k3, l3 = rhs(T + h*k2/2, z + h*l2/2)
                    k4, l4 = rhs(T + h*k3, z + h*l3)
                    T += h*(k1 + 2*k2 + 2*k3 + k4)/6
                    z += h*(l1 + 2*l2 + 2*l3 + l4)/6
                    peak = max(peak, T)
                self.assertAlmostEqual(idle_peak(T0, 1., 30., cfg, self.physics.shared), peak, delta=1e-8)

    def test_real_model_interior_peak_and_trajectory_preserved(self):
        state = dict(temperature_c=26., shared_z=1.)
        old_state, old_terms = self.old.transition(state, [], 30.)
        new_state, new_terms = self.physics.transition(state, [], 30.)
        self.assertEqual(new_state, old_state)
        for k in old_terms:
            if k != 'peak':
                self.assertEqual(new_terms[k], old_terms[k])
        self.assertAlmostEqual(new_terms['peak'], 26.08297195357692)
        self.assertGreater(new_terms['peak'], old_terms['peak'] + .05)

    def test_active_and_no_tail_transitions_unchanged(self):
        for active, z in (([dict(request_id='a', task='D', route='CPU', stage=1)], 1.), ([], 0.)):
            state = dict(temperature_c=29., shared_z=z)
            self.assertEqual(self.physics.transition(state, active, .3),
                             self.old.transition(state, active, .3))

    def test_other_profiles_require_separate_version(self):
        with self.assertRaises(ValueError):
            C.Physics(self.model, self.config, 'S26_STYLE', self.shape)


class PolicyIntegration(ComponentFixture, unittest.TestCase):
    def test_saved_nominals_preserve_ordinary_uncapped_forecasts(self):
        root = HERE.parents[1]
        name = 'D040_T60_P0_S160'
        saved = json.loads((root / 'results/A24_DURATION_040_20261019_01' / (name + '.PUBLIC.json')).read_text(encoding='utf-8'))
        with gzip.open(HERE.parent / 'a24_duration_040_20261019/banks' / (name + '.BANK.json.gz'), 'rt', encoding='utf-8') as f:
            bank = json.load(f)
        nominal = C.B.SavedNominal(saved['public'], [dict(nominal_vectors=bank['nominal_vectors'])])
        jobs = saved['public']['requests'][:8]
        s = snapshot(jobs, now=max(j['scheduled_arrival_ns'] for j in jobs) / NS)
        spec = importlib.util.spec_from_file_location('_test_frozen_policy', HERE.parent / 'a24_s26_method_20261019/policy.py')
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        old_bank, old_actions = m.Policy(nominal, self.old, saved['case'], 'TEACHER').encode(s)
        new_bank, actions = C.Policy(nominal, self.physics, saved['case'], 'TEACHER').encode(s)
        self.assertEqual(actions, old_actions)
        self.assertTrue((new_bank['mask'] == old_bank['mask']).all())
        self.assertTrue(all(not f['capped'] for f in new_bank['forecasts']))
        for old, new in zip(old_bank['forecasts'], new_bank['forecasts']):
            for a, b in zip(old['cost'], new['cost']):
                self.assertAlmostEqual(a, b, delta=1e-6)
            self.assertAlmostEqual(old['AP_end'], new['AP_end'], delta=1e-6)
        self.assertTrue(all(f['no_future_arrivals'] and f['no_future_latents'] for f in new_bank['forecasts']))

    def test_component_policy_uses_common_forecasts_and_same_nn_shape(self):
        # Single decision only. No event engine and no learner/optimizer involved.
        j = request(due=2000.)
        s = snapshot([j])
        class Nominal:
            def vector(self, job, route, state):
                return [0., 1000., 0., 0., 0.]
        actor = C.Policy(Nominal(), self.physics,
                         dict(service_stop_s=3100., supply_stop_s=3035., n=1), 'TEACHER')
        before = copy.deepcopy(s)
        bank, actions = actor.encode(s)
        self.assertEqual(s, before)
        self.assertEqual(bank['x'].shape, (36, 48))
        self.assertEqual(int(bank['mask'].sum()), len(actions))
        self.assertEqual(len({f['H_s'] for f in bank['forecasts']}), 1)
        self.assertTrue(all(f['capped'] for f in bank['forecasts']))
        self.assertTrue(all(math.isfinite(float(v)) for row in bank['x'] for v in row))
        # The NN's selected action is returned unchanged.
        class Learner:
            def choose(self, bank, collect):
                return 1, {}
        actor.learner = Learner()
        a = actor(s)
        self.assertEqual(a, actions[1])
        self.assertFalse(actor.calls[-1]['post_NN_override'])

    def test_fifo_and_edf_bypass_forecast_as_before(self):
        jobs = [request('a', ordinal=0, due=9), request('b', ordinal=1, due=2)]
        for mode, rid in (('FIFO_CPU', 'a'), ('EDF_CPU', 'b')):
            actor = C.Policy(None, self.physics, {}, mode)
            self.assertEqual(actor(snapshot(jobs)), dispatch(rid))


if __name__ == '__main__':
    unittest.main(verbosity=2)
