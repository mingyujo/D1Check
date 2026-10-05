import copy
import math
import unittest
from tools import d1_energy_ap_session_selector as s
from tools import d1_separated_power_readout as protected


def options():
    return [dict(policy=p,planned=192,completed=192,deadline_met=192,last_lane_s=115,
                 energy_0_120_j=e,sampled_peak_ap_35_180_c=t)
            for p,e,t in zip(s.protocol.POLICIES,(180.,178.),(33.,34.))]


class SelectorTests(unittest.TestCase):
    def test_energy_and_ap_both_change_choice(self):
        a,b=s.protocol.POLICIES
        self.assertEqual(a,s.select(options(),33)['model_only_action'])
        self.assertEqual(b,s.select(options(),34)['model_only_action'])
        x=options();x[1]['energy_0_120_j']=181
        self.assertEqual(a,s.select(x,34)['model_only_action'])

    def test_no_implicit_cap_or_infeasible_fallback(self):
        self.assertEqual('missing_research_cap',s.select(options())['status'])
        self.assertIsNone(s.select(options(),32.9)['model_only_action'])

    def test_deadline_and_full_denominator(self):
        x=options();x[1]['deadline_met']=191
        self.assertEqual(x[0]['policy'],s.select(x,40)['model_only_action'])
        x[0]['completed']=191;x[0]['deadline_met']=191
        self.assertIsNone(s.select(x,40)['model_only_action'])

    def test_common_window_last_lane(self):
        x=options();x[1]['last_lane_s']=120.00001
        self.assertEqual(x[0]['policy'],s.select(x,40)['model_only_action'])

    def test_null_nan_unknown_action_denominator_rejected(self):
        for value in (None,math.nan,math.inf):
            x=options();x[0]['energy_0_120_j']=value
            with self.assertRaises(ValueError):s.select(x,40)
        x=options();x[1]['policy']='P_PAIR_COST_PC'
        with self.assertRaises(ValueError):s.select(x,40)
        x=options();x[0]['planned']=191
        with self.assertRaises(ValueError):s.select(x,40)

    def test_never_returns_deployable_winner_or_changes_guard(self):
        r=s.select(options(),40)
        for k in ('deployable_action','policy_winner','accuracy_pass','future_error_bound'):
            self.assertIsNone(r[k])
        self.assertFalse(r['dispatch_enabled'])
        with self.assertRaisesRegex(ValueError,'selection unavailable'):
            protected.decision_support('energy-ap-policy-selection')

    def test_thresholds_are_inclusive_and_input_unchanged(self):
        x=options();before=copy.deepcopy(x);rows=s.frontier(x)
        self.assertIsNone(rows[0]['model_only_action'])
        self.assertEqual([33.,34.],[r['lower_inclusive_c'] for r in rows[1:]])
        self.assertEqual([o['policy'] for o in x],[r['model_only_action'] for r in rows[1:]])
        self.assertEqual(before,x)

    def test_missing_ledger_never_becomes_complete(self):
        with self.assertRaisesRegex(ValueError,'ledger'):
            s.summarize({'forecast':{'ledger':[]}},s.protocol.requests())

    def test_response_boundary_is_output_for_urgent_persist_for_normal(self):
        manifest=s.protocol.requests();ledger=[]
        for q in manifest:
            a=q['offset_ms']*1_000_000
            ledger.append(dict(id=q['request_id'],priority=q['priority'],arrival_ns=a,status='succeeded',
                dispatch_ns=a,execution_start_ns=a,output_ready_ns=a+1_000_000_000,
                persist_complete_ns=a+2_000_000_000,worker_release_ns=a+2_500_000_000,
                lane_available_ns=a+3_000_000_000))
        pred=dict(policy=s.protocol.POLICIES[0],forecast=dict(ledger=ledger),
                  costs=dict(ap_path=[30.]*146,energy_path=[dict(common_s=120,predicted_j=150)],whole_120s_j=150))
        x=s.summarize(pred,manifest)
        self.assertEqual((192,1000,2000),(x['deadline_met'],x['urgent_p95_ms'],x['normal_p95_ms']))
        pred['costs']['whole_120s_j']=151
        with self.assertRaisesRegex(ValueError,'disagreement'):s.summarize(pred,manifest)


if __name__=='__main__':unittest.main()
