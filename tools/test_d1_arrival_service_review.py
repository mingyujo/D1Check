"""Tests only for the new post-hoc aggregation, not the old simulator suite."""
import unittest
from tools import d1_arrival_service_review as review


class ServiceReviewTests(unittest.TestCase):
    def test_relative_is_paired_mean_not_ratio_of_means(self):
        rows=[dict(seed=1,value=2),dict(seed=2,value=9)]
        refs={1:dict(value=1),2:dict(value=10)}
        self.assertAlmostEqual(review.paired_relative(rows,refs,'value'),45)
        self.assertNotEqual(45,100*((2+9)/(1+10)-1))

    def test_missing_pair_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'paired seed'):
            review.paired_relative([dict(seed=1,value=2)],{},'value')

    def test_deadline_turns_latency_dominance_into_tradeoff(self):
        a=dict(urgent_p95_ms=400,normal_mean_ms=4100,normal_deadline_violation=20/90)
        b=dict(urgent_p95_ms=1000,normal_mean_ms=4150,normal_deadline_violation=17/90)
        self.assertEqual(review.dominance(a,b),'B2_weakly_dominates')
        self.assertEqual(review.dominance(a,b,tuple(a)),'tradeoff')

    def test_both_service_constraints_and_completion_are_required(self):
        ref=dict(policy='CPU_URGENT',normal_mean_ms=100,normal_deadline_violation=.1,
                 completion=1,urgent_deadline_violation=0,urgent_p95_ms=100)
        candidate=dict(ref,policy='B2_PC',normal_mean_ms=110,normal_deadline_violation=.15,urgent_p95_ms=50)
        self.assertEqual(review.select([ref,candidate],ref,9.9,5),'CPU_URGENT')
        self.assertEqual(review.select([ref,candidate],ref,10,4.9),'CPU_URGENT')
        self.assertEqual(review.select([ref,candidate],ref,10,5),'B2_PC')
        candidate['completion']=.99
        self.assertEqual(review.select([ref,candidate],ref,100,100),'CPU_URGENT')

    def test_trace_boundary_nearest_rank_and_ablation_identity(self):
        ledger=[]
        for p in ('urgent','normal'):
            for i in range(6):
                ledger.append(dict(priority=p,response_ns=(i+1)*1000000,
                    arrival_ns=1000000,dispatch_ns=1500000,backend='GPU',late_success=False))
        result=dict(policy='P_PAIR_COST_PC',ledger=ledger,decisions=[],
                    settings=dict(decision_ns=100000,record_ns=100000,dispatch_ns=100000))
        rows=review.trace_summary(result,'case','P_NO_PAIR_COST_PC')
        self.assertEqual(rows[0]['policy'],'P_NO_PAIR_COST_PC')
        self.assertEqual(rows[0]['response_p95_ms'],6)
        self.assertEqual(rows[0]['wait_mean_ms'],.5)
        self.assertEqual(rows[0]['dispatch_to_response_mean_ms'],3)


if __name__=='__main__':
    unittest.main()
