import unittest
from tools import d1_scheduler_condition_selector as c


class SelectorTests(unittest.TestCase):
    def fixture(self):
        rows=[]
        for e in c.s.envelopes():
            for pol in c.s.POLICIES:
                for seed in (81001,81002):
                    for scenario in c.s.a.old.SCENARIOS:
                        rows.append(dict(stage='development',envelope=e['id'],policy=pol,seed=seed,scenario=scenario,
                            planned=48,completed=48,deadline_met=48,energy_j=10 if pol=='PAIR_COALESCE_V1' else 20,
                            peak_ap_c=29 if pol=='TOKEN_CPU_V1' else 30,thermal_degree_seconds=100))
        return rows

    def test_goals_distinct_and_no_confirmation_fitting(self):
        rows=self.fixture();a=c.fit(rows)
        rows.append(dict(stage='test',energy_j=-1e9))
        self.assertEqual(a,c.fit(rows))
        for v in a.values():self.assertEqual(v,dict(energy='PAIR_COALESCE_V1',thermal='TOKEN_CPU_V1'))

    def test_missing_or_infeasible_not_success(self):
        rows=self.fixture()
        with self.assertRaises(ValueError):c.fit(rows[:-1])
        for r in rows:r['deadline_met']=47
        out=c.fit(rows)
        self.assertTrue(all(v['energy'] is None for v in out.values()))
        with self.assertRaises(ValueError):c.choose(out,next(iter(out)),'energy')

    def test_unregistered_input_rejected(self):
        with self.assertRaises(ValueError):c.choose({},'unknown','thermal')

    def test_sub_micro_joule_noise_cannot_select_delayed_policy(self):
        rows=self.fixture()
        for r in rows:
            r.update(energy_j=20.,peak_ap_c=30.,thermal_degree_seconds=100.)
            if r['policy']=='JIT_CPU_V1':r['energy_j']-=1e-8;r['peak_ap_c']+=.01
        self.assertTrue(all(v['energy']=='CPU_REFERENCE' for v in c.fit(rows).values()))


if __name__=='__main__':unittest.main()
