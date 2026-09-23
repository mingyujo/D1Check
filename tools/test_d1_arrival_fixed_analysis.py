import copy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import d1_arrival_fixed_analysis as a
from tools import d1_arrival_plan as p


class FixedAnalysisTest(unittest.TestCase):
    def fixture(self):
        rows=[]
        for kind in a.KINDS:
            for i in range(3):
                for policy in p.FIXED_POLICIES:
                    scale={"CPU_URGENT":2,"FIXED_SPLIT":1,"CONDITIONAL":.5}[policy]
                    rows.append(dict(kind=kind, policy=policy, replicate=i,pair_id=f"{kind}{i}",
                        fully_validated=True, **{key:(i+1)*scale for key in a.METRICS}))
        return dict(entries=[{}]*27), rows

    def test_relative_of_pairs_not_ratio_of_pooled_requests(self):
        plan, rows=self.fixture()
        # Keep three independent blocks; request counts never enter the CI.
        next(r for r in rows if r['kind']=='burst' and r['replicate']==2 and r['policy']=='CONDITIONAL')['urgent_session_max_ms']=3
        result=a.summarize(plan,rows)
        effect=next(e for e in result['effects'] if e['primary_relative_endpoint'] and e['metric']=='urgent_session_max_ms')
        self.assertEqual(effect['relative']['n'],3)
        self.assertAlmostEqual(effect['relative']['mean'],(-.5-.5+0)/3)
        self.assertNotAlmostEqual(effect['relative']['mean'],(.5+1+3)/(1+2+3)-1)
        self.assertEqual(effect['relative']['confidence'],.975)
        self.assertEqual(effect['absolute']['confidence'],.95)
        self.assertEqual(len(result['effects']),3*3*len(a.METRICS))

    def test_small_sample_t_interval(self):
        ci=a.interval([1,2,3],.975)
        self.assertAlmostEqual(ci['mean'],2)
        self.assertAlmostEqual(ci['high']-ci['mean'],6.205346816570706/math.sqrt(3))
        self.assertIsNone(a.interval([1],.95)['low'])
        self.assertIsNone(a.interval([],.95)['mean'])

    def test_any_failed_session_suppresses_primary_ci(self):
        plan, rows=self.fixture()
        next(r for r in rows if r['kind']=='low' and r['policy']=='CPU_URGENT')['fully_validated']=False
        effects=a.summarize(plan,rows)['effects']
        for e in effects:
            if e['primary_relative_endpoint']:
                self.assertIsNone(e['relative']['low'])
                self.assertIsNotNone(e['relative']['mean'])

    def test_zero_baseline_and_ties_are_not_divided_or_ranked_away(self):
        plan, rows=self.fixture()
        for r in rows:
            r['urgent_deadline_miss_rate']=0
        result=a.summarize(plan,rows)
        rows=[b for b in result['block_effects'] if b['metric']=='urgent_deadline_miss_rate']
        self.assertTrue(all(b['sign']==0 and b['relative_difference'] is None for b in rows))

    def test_refuses_intermediate_results_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); plan=root/'plan.json'
            plan.write_bytes(p.canonical(dict(protocol=p.FIXED_PROTOCOL)))
            with patch.object(p,'validate'):
                with self.assertRaisesRegex(ValueError,'not finalized'):
                    a.analyze(plan,root,root/'new_output')
            self.assertFalse((root/'new_output').exists())


if __name__ == '__main__':
    unittest.main()
