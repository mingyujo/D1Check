import copy
import unittest
from tools import d1_request_ppo_report as r


class PPOReportTests(unittest.TestCase):
    def test_crossed_intervals_keep_contexts_clustered(self):
        data=[]
        for family in r.FAMILIES:
            for seed in (11,23,37):
                for trace in range(8):
                    for context in range(3):
                        data.append(dict(family=family,baseline='EFT_REFERENCE',learn_seed=seed,trace_seed=trace,
                            **{k:float(context-1) for k in ('delta_j','delta_thermal','delta_peak','delta_urgent_failure','delta_normal_failure','delta_p95')}))
        result=r.cluster_intervals(data)
        self.assertEqual(len(result),24)
        # Whole context triplets average exactly0; treating individual contexts
        # as independent would create a spurious nonzero interval.
        self.assertTrue(all(x['mean']==x['low']==x['high']==0. for x in result))

    def test_missing_thermal_remains_null(self):
        data=[]
        for family in r.FAMILIES:
            data.append(dict(family=family,baseline='EFT_REFERENCE',learn_seed=11,trace_seed=1,
                delta_j=1.,delta_thermal=None,delta_peak=None,delta_urgent_failure=0.,delta_normal_failure=0.,delta_p95=1.))
        result=r.cluster_intervals(data)
        self.assertTrue(all(x['mean'] is None for x in result if x['metric'] in ('delta_thermal','delta_peak')))

    def test_pairs_do_not_match_different_arrivals_or_contexts(self):
        rows=[]
        for trace in (1,2):
            for scenario in ('mean','long_context'):
                for policy in ('CPU_REFERENCE','SPLIT_REFERENCE','EFT_REFERENCE','ENERGY_AP_REQUEST_V1','MC_RL_01','PPO_seed11'):
                    rows.append(dict(trace_seed=trace,family='queue',scenario=scenario,policy=policy,
                        planned=24,completed=24,deadline_met=24,urgent_service_failure=0,normal_service_failure=0,
                        urgent_n=6,normal_n=18,energy_j=trace*100+(1 if scenario=='long_context' else 0)+(2 if policy=='PPO_seed11' else 0),
                        thermal_degree_seconds=10.,peak_ap_c=30.,urgent_p95_ms=100.))
        result=r.paired(rows)
        self.assertEqual(len(result),20);self.assertTrue(all(x['delta_j']==2 for x in result))


if __name__=='__main__':unittest.main()
