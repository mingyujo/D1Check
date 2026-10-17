"""Only bank census fixtures; no engine, predictions, NN, or environment."""
import sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'experiments/rl_cost_20261017'),
 str(ROOT/'experiments/edf_cpu_first_20261016'),str(ROOT/'experiments/competition_cost_20261017')]
from observer import Observer

class CensusTests(unittest.TestCase):
    def bank(self):
        actions=[{'kind':'PAD'} for _ in range(80)]
        actions[0]={'kind':'DISPATCH','request_id':'a','route':'CPU'}
        actions[1]={'kind':'DISPATCH','request_id':'a','route':'GPU'}
        actions[72]={'kind':'WAIT','wait_ns':50000000}
        mask=np.zeros(80,dtype=bool);mask[[0,1,72]]=True
        return dict(actions=actions,mask=mask,physical_mask=mask.copy(),prior_logits=np.zeros(80),
                    diagnostic={'protection':{'removed_actions':0,'critical_request':None}})

    def observer(self):
        x=Observer.__new__(Observer);x.mode='COST_PRIOR';x.opportunities=[];return x

    def test_WAIT_and_two_routes_are_not_two_requests(self):
        x=self.observer();x.choose(self.bank(),0)
        s=x.summary();self.assertEqual(s['multiple_requests_after'],0)
        self.assertEqual(s['multiple_dispatch_actions'],1);self.assertEqual(s['WAIT_allowed'],1)
        self.assertEqual(s['two_free_routes'],1)

    def test_protection_counts_separately_from_physical_capacity(self):
        x=self.observer();b=self.bank();b['actions'][3]={'kind':'DISPATCH','request_id':'b','route':'CPU'}
        b['physical_mask'][3]=True;b['mask'][1]=False
        x.choose(b,0);v=x.opportunities[0]
        self.assertEqual(v['requests_before'],2);self.assertEqual(v['requests_after'],1)
        self.assertEqual(v['free_routes'],1);self.assertTrue(v['two_physical_routes'])

    def test_EDF_selection_does_not_apply_shadow_protection(self):
        x=self.observer();x.mode='EDF';b=self.bank();b['mask'][0]=False
        x.public_call_state={'now_ns':0,'owners':[], 'queue':[
            {'request_id':'a','task':'C','scheduled_arrival_ns':0,'deadline_ns':100,'ordinal':0}]}
        self.assertEqual(x.choose(b,0),0)

if __name__=='__main__':unittest.main()
