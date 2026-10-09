import unittest
from tools import d1_model_accuracy_expert_diagnostics as d


class DiagnosticTests(unittest.TestCase):
    def test_initialization_does_not_rewrite_observed_history(self):
        self.assertEqual(d.component_diagnostic(35.,.1,1.,2.,0.,35.),(35.,35.))
        no_offset,recent=d.component_diagnostic(128.5,.1,1.,2.,0.,120.)
        self.assertAlmostEqual(no_offset,120.)
        self.assertAlmostEqual(recent,205.)

    def test_component_decomposition_preserves_interval_additivity(self):
        whole=d.component_diagnostic(220.,.1,1.,1.2,0.,200.)
        left=d.component_diagnostic(60.,.1,1.,1.2,0.,50.)
        right=d.component_diagnostic(160.,.1,1.,1.2,50.,200.)
        for total,a,b in zip(whole,left,right):self.assertAlmostEqual(total,a+b)

    def test_missing_or_invalid_value_is_not_filled_with_zero(self):
        for value in (float('nan'),float('inf')):
            with self.assertRaises(ValueError):d.component_diagnostic(value,.1,1.,1.,0.,120.)

    def test_counterbalanced_order_preserves_same_policy_difference(self):
        cpu=dict(session='cpu',policy='CPU_URGENT_ONLINE_V1')
        par=dict(session='par',policy='B2_PARALLEL_ONLINE_V1')
        self.assertEqual(d.orient_policy_pair(cpu,par),('cpu','par'))
        self.assertEqual(d.orient_policy_pair(par,cpu),('cpu','par'))

    def test_unregistered_pair_is_not_silently_substituted(self):
        with self.assertRaisesRegex(ValueError,'registered'):
            d.orient_policy_pair(dict(session='a',policy='B2_SERIAL_ONLINE_V1'),
                                 dict(session='b',policy='B2_PARALLEL_ONLINE_V1'))


if __name__=='__main__':unittest.main()
