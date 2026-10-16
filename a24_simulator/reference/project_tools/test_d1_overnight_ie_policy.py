import copy,unittest
from unittest.mock import patch
from tools import d1_overnight_ie_policy as x


class Policy(unittest.TestCase):
    def setUp(self):
        f,i,_=x.r.h.load();self.c=x.Controller(f,i['initial'])
        self.q=[x.r.h.prior.ticket('D','detection')];self.now=35_000_000_000
        self.lanes=x.r.old.core.empty_lanes(self.now);self.c.observe(self.now,self.lanes)
        self.base=dict(kind='single',jobs=[dict(request_id='D',backend='CPU')])
        self.wait=dict(kind='cool_wait',until_ns=35_250_000_000)
        self.f=dict(valid=True,responses={'D':35.7},lane_end_s=36.,remaining_increment_j=2.,global_peak_ap_c=30.,peak_ap_c=30.,urgent_p95_ms=None,urgent_misses=0,normal_misses=0)
        self.risk=dict(known=False,rho=0.,gap=0.,gap_known=False,queued=.7)
    def accept(self,action=None,risk=None,f=None,ref=None):
        return self.c.admission(action or self.wait,[f or self.f]*3,[ref or self.f]*3,self.q,self.now,risk or self.risk)
    def test_unknown_load_cooling_rejected(self):
        self.assertEqual(self.accept(),(False,'unknown_observed_CPU_load_no_cooling'))
    def test_unknown_load_keeps_immediate_dispatch(self):
        self.assertTrue(self.accept(self.base)[0])
    def test_known_light_load_preserves_original_wait_option(self):
        self.assertTrue(self.accept(risk=dict(self.risk,known=True,rho=.5))[0])
    def test_known_saturated_load_rejected_by_original_contract(self):
        self.assertEqual(self.accept(risk=dict(self.risk,known=True,rho=1.)),(False,'observed_CPU_D_pressure'))
    def test_R2_blocks_normal_delay_even_when_deadline_still_met(self):
        self.c.variant=x.R2
        self.assertEqual(self.accept(self.base,f=dict(self.f,responses={'D':35.8})),(False,'current_response_preservation'))
    def test_R2_equal_response_keeps_cost_alternative(self):
        self.c.variant=x.R2;self.assertTrue(self.accept(self.base,f=dict(self.f,remaining_increment_j=1.9))[0])
    def test_incomplete_forecasts_do_not_create_zero_cost(self):
        self.assertFalse(self.accept(self.base,f=dict(valid=False))[0])
    def test_L0_stays_unmasked_under_unknown_forecast(self):
        with patch.object(self.c,'predict',return_value=dict(valid=False)):
            e=self.c.encode(self.q,self.lanes,self.now,[self.base,self.wait],self.q)
        self.assertTrue(e['mask'][0]);self.assertFalse(e['mask'][1]);self.assertTrue(e['physical_mask'][1])
    def test_unknown_known_flags_use_only_observed_arrivals(self):
        self.c.arrivals={q['id']:q for q in self.q};self.assertFalse(self.c.risk(self.q,self.now)['known'])
        self.c.arrivals.update({str(j):dict(self.q[0],id=str(j),ordinal=j,arrival_ns=(35+j*2)*1e9) for j in (1,2)})
        self.assertTrue(self.c.risk(self.q,39e9)['known'])

if __name__=='__main__':unittest.main()
