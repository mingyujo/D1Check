import copy,unittest
from tools import d1_overnight_ie_reference_gap as d


class PublicHistory(unittest.TestCase):
    def setUp(self):
        self.case=dict(condition=0,seed=1,family='fixture',context='mean',tickets=[dict(id='D',ordinal=0,task='detection',priority='normal',arrival_ns=10),dict(id='C',ordinal=1,task='classification',priority='urgent',arrival_ns=13)])
        self.raw=dict(snapshots=[],result=dict(ledger=[dict(id='D',backend='CPU',dispatch_ns=10),dict(id='C',backend='GPU',dispatch_ns=15)],transitions=[dict(at_ns=t,backend='CPU',request_id='D',event=e) for t,e in [(11,'execution_start_ns'),(12,'output_ready_ns'),(13,'worker_release_ns'),(14,'lane_available_ns')]]))
    def test_worker_release_does_not_return_lane(self):
        state=d.public_before(self.case,self.raw,13);self.assertEqual(state['owners']['CPU'],'D');self.assertEqual(state['phases']['CPU'],'WORKER_RELEASED');self.assertEqual([q['id'] for q in state['queue']],['C'])
    def test_actual_available_before_next_decision_returns_lane(self):
        state=d.public_before(self.case,self.raw,14);self.assertIsNone(state['owners']['CPU']);self.assertEqual(state['phases']['CPU'],'AVAILABLE')
    def test_unseen_later_dispatch_and_phase_values_do_not_change_state(self):
        new=copy.deepcopy(self.raw);new['result']['transitions'].append(dict(at_ns=100,backend='GPU',request_id='C',event='lane_available_ns'));new['result']['ledger'][1]['dispatch_ns']=90
        self.assertEqual(d.public_before(self.case,self.raw,13),d.public_before(self.case,new,13))
    def test_no_saved_encoder_means_no_mask_cause_inferred(self):
        other=copy.deepcopy(self.raw);other['result']['ledger'][1]['backend']='CPU'
        result=d.first_difference(self.case,self.raw,other);self.assertFalse(result['snapshot_found']);self.assertIn('no encoded',result['classification'])

if __name__=='__main__':unittest.main()
