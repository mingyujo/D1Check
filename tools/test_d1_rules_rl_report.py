import unittest
from unittest.mock import patch
from tools import d1_rules_rl_report as r
from tools import d1_recombination_readout as audit


class Tests(unittest.TestCase):
    def test_joint_cost_gain_does_not_hide_service_failure_or_missing_AP(self):
        base=dict(trace_seed=1,family='low',context='mean',policy='SHARED_EFT',kind='baseline',
            planned=3,completed=3,equal_work=True,urgent_service_failure=0,normal_service_failure=0,
            energy_j=10.,peak_ap_c=30.,thermal_degree_seconds=4.,urgent_p95_ms=100.,normal_mean_ms=1000.)
        good=dict(base,policy='P',kind='latest',energy_j=9.,peak_ap_c=29.,thermal_degree_seconds=3.)
        failed=dict(good,policy='F',completed=2,normal_service_failure=1)
        missing=dict(good,policy='M',thermal_degree_seconds=None)
        rows=r.paired([base,good,failed,missing],'SHARED_EFT')
        self.assertTrue(rows[0]['strict_joint']);self.assertFalse(rows[1]['joint_nonworsening'])
        self.assertEqual(rows[1]['incomplete'],1);self.assertFalse(rows[2]['joint_nonworsening'])
        self.assertIsNone(rows[2]['delta_thermal_degree_seconds'])
        groups=r.aggregate(rows);self.assertTrue(all(g['expected_cases']==96 for g in groups))

    def test_actual_branch_audit_is_read_only_and_excludes_reference_incumbent(self):
        with patch.object(audit.r.v.q.old.engine,'simulate',side_effect=AssertionError('no new environment')):
            rows=audit.audit()
        self.assertEqual(len(rows),96)
        self.assertTrue(all(len(x['sequence'])==3 and x['prefix_failures'] for x in rows))
        self.assertEqual(sum(x['stage']=='confirmation' for x in rows),48)


if __name__=='__main__':unittest.main()
