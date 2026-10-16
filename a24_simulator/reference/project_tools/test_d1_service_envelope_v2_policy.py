import copy,unittest
from unittest.mock import patch
import numpy as np
from tools import d1_service_envelope_v2_policy as n
class V2(unittest.TestCase):
    def setUp(self):
        f,i,_=n.x.r.h.load();self.c=n.Controller(f,i['initial']);self.now=35_000_000_000;self.q=[n.x.r.h.prior.ticket('D','detection')];self.l=n.x.r.old.core.empty_lanes(self.now)
    def encoded(self):
        ref=dict(valid=True,responses={'D':35.7},urgent_misses=0,normal_misses=0,urgent_p95_ms=None,lane_end_s=36.,remaining_increment_j=2.,global_peak_ap_c=30.,peak_ap_c=30.)
        alt=dict(ref,responses={'D':35.95},lane_end_s=36.25,global_peak_ap_c=29.9,peak_ap_c=29.9)
        return dict(state=np.zeros(56,dtype=np.float32),candidates=np.zeros((8,28),dtype=np.float32),physical_mask=np.array([True,True]+[False]*6),mask=np.array([True,False]+[False]*6),actions=[dict(kind='single',jobs=[dict(request_id='D',backend='CPU')]),dict(kind='cool_wait',until_ns=35_250_000_000)],forecasts=[[ref]*3,[alt]*3],admissions=['JointList_reference','Joint_service_envelope_rejected'],risk=dict(known=True,rho=.5),now_ns=self.now)
    def test_CPU_only_later_but_deadline_and_P95_preserved_is_admitted(self):
        with patch.object(n.x.Controller,'encode',return_value=self.encoded()):e=self.c.encode(self.q,self.l,self.now,[],[])
        self.assertTrue(e['mask'][1]);self.assertTrue(e['mask'][0]);self.assertNotEqual(e['schema_id'],n.x.SCHEMA)
    def test_unknown_cooling_stays_blocked(self):
        original=self.encoded();original['risk']['known']=False
        with patch.object(n.x.Controller,'encode',return_value=original):e=self.c.encode(self.q,self.l,self.now,[],[])
        self.assertFalse(e['mask'][1]);self.assertTrue(e['mask'][0])
    def test_miss_lateness_cannot_be_exchanged_for_AP(self):
        original=self.encoded();alt=dict(original['forecasts'][1][0],normal_misses=1,responses={'D':41.1});original['forecasts'][1]=[alt]*3
        with patch.object(n.x.Controller,'encode',return_value=original):e=self.c.encode(self.q,self.l,self.now,[],[])
        self.assertFalse(e['mask'][1])
if __name__=='__main__':unittest.main()
