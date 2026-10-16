import copy
import unittest

import numpy as np

from tools import d1_simulation_model_v3_energy as energy


class EnergyV3Tests(unittest.TestCase):
    def case(self, identity='fixture', group='old'):
        states = ['idle', *energy.STATES, 'idle']
        edges = [0., 35., 45., 55., 65., 75., 120.]
        segments = [dict(start_s=a, end_s=b, state=s) for a, b, s in zip(edges, edges[1:], states)]
        increments = np.array([.2, .4, .3, .6])
        times = list(np.arange(-20., 121., .5)); power = []
        for t in times:
            value = 1.
            for s, increment in zip(segments[1:5], increments):
                if s['start_s'] <= t < s['end_s']:
                    value += increment
            power.append(value)
        return dict(id=identity, role='development', source_group=group, pre_w=1.,
            actual=segments, power_t=times, power_w=power, common_end_s=120.)

    def original(self):
        return dict(energy_increment_w=dict(zip(energy.STATES, [.2, .4, .3, .6])))

    def safe(self, c):
        return dict(pre_w=c['pre_w'], actual=c['actual'],
            initial_power_late_w=energy.initial_power_late(c))

    def test_future_values_do_not_enter_late_initial_power(self):
        c = self.case(); first = energy.initial_power_late(c)
        c['power_w'] = [p if t < 35 else float('nan') for t, p in zip(c['power_t'], c['power_w'])]
        self.assertEqual(energy.initial_power_late(c), first)
        self.assertEqual(first, 1.)

    def test_predict_rejects_future_power_and_AP_and_pre_future_sample(self):
        c = self.case(); head = energy.fit([self.case(str(i)) for i in range(3)], self.original(), 1., .5)
        for field, value in [('power_w', [999.]), ('power_t', [100.]), ('ap', [999.]), ('observed_ap_c', [999.])]:
            bad = dict(self.safe(c), **{field: value})
            with self.assertRaises(ValueError):
                energy.predict(bad, head, 120.)
        bad = dict(pre_power_t=[10., 30., 35.], pre_power_w=[1., 1., 1.])
        with self.assertRaises(ValueError):
            energy.initial_power_late(bad)

    def test_constant_prior_no_relaxation_and_energy_additivity(self):
        c = self.case(); data = [self.case(str(i)) for i in range(3)]
        head = energy.fit(data, self.original(), 1., 1.)
        safe = self.safe(c)
        self.assertEqual(energy.relaxation_integral(safe, 120.), 0.)
        expected = 120. + float(energy.prior.base.exposure(c['actual'], 0, 120) @ np.array(list(head['increments'].values())))
        self.assertAlmostEqual(energy.predict(safe, head, 120.), expected)
        self.assertEqual(energy.predict(safe, head, 0.), 0.)

    def test_relaxation_signed_integral_and_issue_boundary(self):
        safe = dict(pre_w=1., initial_power_late_w=1.2)
        self.assertEqual(energy.relaxation_integral(safe, 35.), 0.)
        value = energy.relaxation_integral(safe, 65.)
        self.assertAlmostEqual(value, .2 * (30. - 30. * (1. - np.exp(-1.))))
        self.assertAlmostEqual(energy.relaxation_integral(dict(safe, initial_power_late_w=.8), 65.), -value)

    def test_source_and_session_equal_weight_is_duplication_invariant(self):
        a = self.case('a', 'old'); b = self.case('b', 'macro'); c = self.case('c', 'new_recovery')
        b['power_w'] = [p + .05 if t >= 35 else p for t, p in zip(b['power_t'], b['power_w'])]
        first = energy.fit([a, b, c], self.original(), .1, 0.)
        copies = [dict(copy.deepcopy(a), id='a' + str(i)) for i in range(3)]
        second = energy.fit(copies + [b, c], self.original(), .1, 0.)
        np.testing.assert_allclose(list(first['increments'].values()), list(second['increments'].values()), atol=1e-12)

    def test_rank_role_identity_and_registered_settings_guards(self):
        cases = [self.case(str(i)) for i in range(3)]
        for lambda_, gain in [(-1., 0.), (.02, 0.), (0., .25), (float('nan'), 0.)]:
            with self.assertRaises(ValueError):
                energy.fit(cases, self.original(), lambda_, gain)
        for bad in [cases[:2], [dict(c, role='confirmation') for c in cases], [cases[0]] * 3]:
            with self.assertRaises(ValueError):
                energy.fit(bad, self.original(), 0., 0.)
        for c in cases:
            c['actual'] = [dict(start_s=0., end_s=120., state='idle')]
        with self.assertRaises(ValueError):
            energy.fit(cases, self.original(), 0., 0.)

    def test_pre_gap_invalid_power_and_schedule_are_rejected(self):
        for bad in [dict(pre_power_t=[10., 30.], pre_power_w=[1., 1.]),
                    dict(initial_power_late_w=-1.), dict(initial_power_late_w=float('inf'))]:
            with self.assertRaises(ValueError):
                energy.initial_power_late(bad)
        data = [self.case(str(i)) for i in range(3)]
        head = energy.fit(data, self.original(), 0., 0.)
        safe = self.safe(data[0]); safe['actual'][0]['end_s'] = 34.
        with self.assertRaises(ValueError):
            energy.predict(safe, head, 120.)


if __name__ == '__main__':
    unittest.main()
