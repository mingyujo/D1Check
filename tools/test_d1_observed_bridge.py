import unittest
from tools.d1_arrival_observed_bridge import replay

def row(rid='a',offset=0,priority='urgent'):
    r=dict(request_id=rid,selected_backend='CPU',priority=priority,scheduled_arrival_ns=offset,
        dispatch_ns=offset,execution_start_ns=offset+10,output_ready_ns=offset+30,
        persist_complete_ns=offset+60,worker_release_ns=offset+64,lane_available_ns=offset+70)
    r['completion_ns']=offset+(30 if priority=='urgent' else 60);return r

class ReplayTest(unittest.TestCase):
    def test_recorded_boundaries_and_reuse(self):
        x=replay([row(),row('b',70,'normal')]);self.assertEqual(x['lane_reuse_pairs'],1)
        self.assertEqual([r['response_ns'] for r in x['requests']],[30,60])
    def test_release_not_worker(self):
        with self.assertRaises(ValueError):replay([row(),row('b',64)])
    def test_wrong_response_boundary(self):
        r=row();r['completion_ns']=60
        with self.assertRaises(ValueError):replay([r])

if __name__=='__main__':unittest.main()
