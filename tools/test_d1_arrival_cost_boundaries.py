import math
import tempfile
import unittest
from pathlib import Path

from tools import d1_arrival_cost_boundaries as costs


class CostBoundariesTest(unittest.TestCase):
    def test_fixed_schedule_inversion_and_algebraic_crossing(self):
        d = costs.recover_durations(120 + 30 + 20, 120 + 30 + 40)
        self.assertEqual(d, dict(idle=70., single=30., pair=20.))
        b = dict(idle=80., single=30., pair=10.)
        cross, status = costs.boundary(d, b, 1., 2.)
        self.assertEqual(status, 'algebraic_unmeasured_power')
        self.assertEqual(cross, 1.)
        self.assertTrue(math.isclose(sum((d[k]-b[k])*p for k,p in
                                     (('idle',1.),('single',2.),('pair',cross))),0.))
        self.assertEqual(costs.boundary(d,d,1.,2.),(None,'identical'))

    def test_stored_schedule_alignment_and_reverse_pair_identity(self):
        with tempfile.TemporaryDirectory() as path:
            states,pairs,reps,ap,summary = costs.build(Path(path))
            self.assertEqual((len(states),len(pairs),len(reps),len(ap),len(summary)),
                             (135,135,9,9,27))
            queue_b2 = next(x for x in reps if x['scenario']=='queue' and x['policy']=='B2_PC')
            queue_b3 = next(x for x in reps if x['scenario']=='queue' and x['policy']=='B3_SOLO_EFT_PC')
            self.assertGreater(queue_b2['pair_CG_DC'], 0)
            self.assertEqual(queue_b2['pair_CC_DG'], 0)
            self.assertGreater(queue_b3['pair_DCPU_DGPU'], 0)
            self.assertGreater(queue_b3['request_wait_sum_s'], 0)
            self.assertTrue(all(x['first_unfinished']==x['second_unfinished']==0 for x in pairs))
            self.assertEqual(sum(x['cross_count'] for x in summary if x['scenario']=='low'),0)
            self.assertTrue((Path(path)/'dashboard.html').is_file())


if __name__=='__main__':
    unittest.main()
