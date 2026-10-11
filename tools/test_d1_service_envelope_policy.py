import copy,unittest
from unittest.mock import patch
from tools import d1_service_envelope_policy as x

class Envelope(unittest.TestCase):
    def setUp(self):
        f,i,_=x.r.h.load();self.c=x.Controller(f,i['initial']);self.now=35_000_000_000
        self.q=[x.r.h.prior.ticket('C','classification'),x.r.h.prior.ticket('D','detection',35,1)]
        self.lanes=x.r.old.core.empty_lanes(self.now);self.c.observe(self.now,self.lanes)
    def test_joint_C_GPU_D_CPU_is_legal_service_reference(self):
        a,w=self.c.bank(self.q,self.lanes,self.now);e=self.c.encode(self.q,self.lanes,self.now,a,w)
        self.assertEqual({(q['request_id'],q['backend']) for q in e['actions'][0]['jobs']},{('C','GPU'),('D','CPU')})
        self.assertTrue(e['mask'][0]);self.assertTrue(e['physical_mask'][0])
        for f in e['forecasts'][0]:self.assertTrue(f['valid']);self.assertEqual((f['urgent_misses'],f['normal_misses']),(0,0))
        self.assertNotEqual(e['schema_id'],x.r.SCHEMA)
    def test_individual_urgent_delay_is_not_old_L0_gate(self):
        f=dict(valid=True,responses={'C':35.4,'D':35.8},lane_end_s=36.,urgent_p95_ms=400.,urgent_misses=0,normal_misses=0)
        ref=dict(f,responses={'C':35.2,'D':36.})
        action=dict(kind='bundle',jobs=[dict(request_id='C',backend='GPU'),dict(request_id='D',backend='CPU')])
        self.assertTrue(self.c.admission(action,[f]*3,[ref]*3,self.q,self.now,self.c.risk(self.q,self.now))[0])
    def test_unsupported_detection_GPU_remains_physical_false(self):
        a=dict(kind='single',jobs=[dict(request_id='D',backend='GPU')])
        self.assertFalse(x.r.physical(a,self.q,self.lanes,self.now,self.c.credit))
    def test_worker_release_is_not_available(self):
        l=copy.deepcopy(self.lanes);l['CPU'].update(request=self.q[1],phase='WORKER_RELEASED',dispatch=self.now)
        a=dict(kind='single',jobs=[dict(request_id='D',backend='CPU')]);self.assertFalse(x.r.physical(a,self.q,l,self.now,self.c.credit))
    def test_unknown_forecast_does_not_become_zero_cost(self):
        self.assertEqual(self.c.admission(dict(kind='single'),[dict(valid=False)]*3,[],self.q,self.now,{}),(False,'unknown_forecast'))
    def test_process_local_scope_restores_after_exception(self):
        previous=x.r.service_suffix_scope
        with self.assertRaises(RuntimeError):
            with x.parent_scope():raise RuntimeError('fixture')
        self.assertIs(x.r.service_suffix_scope,previous)
    def test_full_queue_service_lateness_includes_owned_request(self):
        f=dict(responses={'C':36.6,'D':41.2},urgent_misses=1,normal_misses=1)
        owned=copy.deepcopy(self.lanes);owned['CPU']['request']=self.q[1]
        s=x.service(f,self.q[:1],owned);self.assertAlmostEqual(s[2],.1);self.assertAlmostEqual(s[3],.2)

if __name__=='__main__':unittest.main()
