import unittest
from fractions import Fraction as F
from tools.d1_arrival_delta_selection import choose,non_timely_pp,gap


def row(policy,misses,urgent):
    return dict(policy=policy,normal_n='90',normal_misses=str(misses),urgent_p95_ms=str(urgent),
        completion='1',normal_completion='1',planned='120',arrived='120',unfinished='0',not_arrived='0',
        simulated_failures='0',simulated_rejections='0',simulated_expirations='0')


class DeltaTests(unittest.TestCase):
    def test_exact_boundary_without_display_rounding(self):
        ref=row('CPU_URGENT',26,600);b=row('B2_PC',30,500)
        self.assertEqual(gap(b,ref),F(40,9))
        self.assertEqual(choose([ref,b],ref,F('4.444'))[1],[ref])
        self.assertEqual(choose([ref,b],ref,F(40,9))[1],[b])

    def test_ties_retained_and_no_old_secondary_objective(self):
        ref=row('CPU_URGENT',26,600);b=row('B2_PC',20,500);p=row('P_PAIR_COST_PC',17,500)
        b.update(normal_mean_ms='9000',urgent_deadline_violation='0.2')
        p.update(normal_mean_ms='1000',urgent_deadline_violation='0')
        self.assertEqual(choose([ref,b,p],ref,F(0))[1],[b,p])

    def test_unfinished_cannot_benefit_from_completed_only_latency(self):
        ref=row('CPU_URGENT',26,600);bad=row('P_PAIR_COST_PC',0,1)
        bad.update(completion='.99',unfinished='1')
        self.assertEqual(choose([ref,bad],ref,F(100))[1],[ref])
        # 70 timely +10 late completions +10 unfinished/failed: all90 denominator.
        self.assertEqual(non_timely_pp(70,90),F(200,9))
        self.assertNotEqual(non_timely_pp(70,90),non_timely_pp(70,80))

    def test_negative_gap_is_feasible_at_zero_and_negative_delta_rejected(self):
        ref=row('CPU_URGENT',26,600);b=row('B2_PC',20,500)
        self.assertEqual(choose([ref,b],ref,F(0))[1],[b])
        with self.assertRaises(ValueError):choose([ref,b],ref,F(-1))


if __name__=='__main__':unittest.main()
