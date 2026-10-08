"""Source-rule and elapsed-wait hand cases; pure projections, no environments."""
import copy,unittest
from tools import d1_thermal_slack_v3 as x
from tools.test_d1_ie_dispatch import ticket,lanes

def controller(policy=x.LONG):
    frozen,data=x.p.inputs(x.p.BUNDLE);return x.Controller(frozen,data['initial'],policy)
def forecasts(peak=30.,j=10.,p95=100.,normal=0,valid=True):
    return {ctx:dict(valid=valid,peak_ap_c=peak,global_peak_ap_c=30.,remaining_increment_j=j,urgent_misses=0,normal_misses=normal,urgent_p95_ms=p95,lane_end_s=40.) for ctx in x.core.CONTEXTS}

class ThermalSlackTests(unittest.TestCase):
    def test_credit_counts_elapsed_and_only_dispatch_resets(self):
        c=controller();ls=lanes();c.observe(35e9,ls);c.cool_since=35e9;c.observe(35.3e9,ls)
        self.assertAlmostEqual(c.credit,.7);c.cool_since=35.3e9;c.observe(35.4e9,ls);self.assertAlmostEqual(c.credit,.6)
        ls['CPU']=dict(request=ticket('d',0,'detection',35.,6.),phase='ASSIGNED',since=35.4e9,dispatch=35.4e9);c.observe(35.4e9,ls);self.assertEqual(c.credit,1.)

    def test_urgent_arrival_removes_cooling(self):
        c=controller();ls=lanes();d=ticket('d',0,'detection',35.,6.);base=dict(selected=dict(request_id='d',backend='CPU'))
        self.assertTrue(any(a['kind']=='cool_wait' for a in c.physical_candidates([d],ls,35e9,base)))
        u=ticket('u',1,arrival=35.1);self.assertFalse(any(a['kind']=='cool_wait' for a in c.physical_candidates([d,u],ls,35.1e9,base)))

    def test_no_wait_ablation_has_no_cooling(self):
        c=controller(x.NOWAIT);d=ticket('d',0,'detection',35.,6.);actions=c.physical_candidates([d],lanes(),35e9,dict(selected=dict(request_id='d',backend='CPU')))
        self.assertFalse(any(a['kind']=='cool_wait' for a in actions))

    def test_actual_busy_lane_and_detection_gpu_never_candidates(self):
        c=controller();ls=lanes();ls['CPU']=dict(request=ticket('running',0,'detection',35.,6.),phase='WORKER_RELEASED',since=35.1e9,dispatch=35e9)
        qs=[ticket('c',1),ticket('d',2,'detection',35.,6.)];actions=c.physical_candidates(qs,ls,35.1e9,dict(selected=None))
        self.assertTrue(any(a['jobs']==[dict(request_id='c',backend='GPU')] for a in actions))
        self.assertFalse(any(j['backend']=='CPU' or j['request_id']=='d' for a in actions for j in a['jobs']))

    def test_future_ticket_is_rejected(self):
        c=controller()
        with self.assertRaises(ValueError):c.decide({},[ticket('future',0,arrival=36.)],lanes(),35e9,{},None,None)

    def test_heat_selection_and_all_service_energy_filters(self):
        base=dict(base=True,jobs=[],forecasts=forecasts());good=dict(base=False,jobs=[],wait_until_ns=35.25e9,forecasts=forecasts(peak=29.))
        self.assertIs(x.Controller.select([base,good]),good)
        for change in (dict(j=10.01),dict(p95=100.01),dict(normal=1),dict(valid=False)):
            bad=dict(good,forecasts=forecasts(peak=29.,**change));self.assertIs(x.Controller.select([base,bad]),base)

    def test_invalid_base_uses_exact_fallback(self):
        base=dict(base=True,jobs=[],forecasts=forecasts(valid=False));good=dict(base=False,jobs=[],forecasts=forecasts(peak=29.))
        self.assertIs(x.Controller.select([base,good]),base)

    def test_projection_does_not_mutate_real_band_or_use_future_arrivals(self):
        c=controller();ls=lanes();c.observe(35e9,ls);qs=[ticket('d',0,'detection',35.,6.),ticket('c',1)]
        original=copy.deepcopy(c.band.__dict__);action=dict(jobs=[],base=True)
        projection=x.project_band(c.estimates,c.profiles,qs,ls,35e9,action,'mean',c.band)
        self.assertEqual(c.band.__dict__,original);self.assertEqual({j['id'] for j in projection['jobs']},{'c','d'})
        self.assertTrue(all(d['at_ns']>=35e9 for d in projection['dispatches']))

if __name__=='__main__':unittest.main()
