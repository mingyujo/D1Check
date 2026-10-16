import copy,unittest
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_rolling_list_rl as r


class Controller(unittest.TestCase):
    def setUp(self):
        f,i,_=r.h.load();self.c=r.Controller(f,i['initial']);self.now=35e9
        self.lanes=r.old.core.empty_lanes(self.now);self.c.observe(self.now,self.lanes)
        self.d=r.h.prior.ticket('D','detection');self.q=[self.d]
        self.base=dict(kind='single',jobs=[dict(request_id='D',backend='CPU')])
        self.wait=dict(kind='cool_wait',until_ns=35.25e9,hold_signature=self.c.signature(self.q,self.lanes))
    def forecast(self,queue,lanes,now,action,context):
        return dict(valid=True,responses={q['id']:q['arrival_ns']/1e9+.7 for q in queue},lane_end_s=36.,urgent_p95_ms=None,urgent_misses=0,normal_misses=0,
            remaining_increment_j=3.,global_peak_ap_c=30.-.01*(action['kind']=='cool_wait'),peak_ap_c=30.-.01*(action['kind']=='cool_wait'))
    def encode(self,queue=None):
        queue=queue or self.q
        with patch.object(self.c,'predict',side_effect=self.forecast):return self.c.encode(queue,self.lanes,self.now,[self.base,self.wait],queue)
    def test_fixed_ABI_empty_slots_and_distinct_physical_admission(self):
        e=self.encode();self.assertEqual(e['state'].shape,(56,));self.assertEqual(e['candidates'].shape,(8,28));self.assertTrue(e['mask'][:2].all());self.assertFalse(e['mask'][2:].any())
        other=dict(self.d,id='D2',ordinal=1);e=self.encode([self.d,other])
        self.assertTrue(e['physical_mask'][1]);self.assertFalse(e['mask'][1]);self.assertEqual(e['admissions'][1],'D_backlog')
    def test_observed_CPU_pressure_rejects_wait_without_future_trace(self):
        self.c.arrivals={str(i):dict(self.d,id=str(i),arrival_ns=(34.+i*.2)*1e9) for i in range(3)}
        e=self.encode();self.assertGreater(e['risk']['rho'],1);self.assertFalse(e['mask'][1])
    def test_request_cumulative_cap_survives_dispatch_credit_renewal(self):
        self.c.request_wait['D']=.1;e=self.encode();self.assertFalse(e['mask'][1]);self.assertEqual(e['admissions'][1],'request_wait_cap')
    def test_actual_wait_debit_stops_on_arrival(self):
        self.c.apply_prefix(self.wait,self.q,self.lanes,self.now,dict(selected=self.base['jobs'][0]))
        self.c.observe(35.1e9,self.lanes);self.assertAlmostEqual(self.c.request_wait['D'],.1)
        q=[self.d,dict(self.d,id='new',arrival_ns=35.1e9)]
        with patch.object(self.c,'choose_prefix',return_value=None):self.c.decide(None,q,self.lanes,35.1e9,{},None,None)
        self.c.observe(35.2e9,self.lanes);self.assertAlmostEqual(self.c.request_wait['D'],.1);self.assertNotIn('new',self.c.request_wait)
    def test_physical_support_owner_and_urgent_wait_blocked(self):
        busy=copy.deepcopy(self.lanes);busy['CPU']['request']=self.d
        self.assertFalse(r.physical(self.base,self.q,busy,self.now,.25))
        bad=dict(kind='single',jobs=[dict(request_id='D',backend='GPU')]);self.assertFalse(r.physical(bad,self.q,self.lanes,self.now,.25))
        cq=r.h.prior.ticket('C','classification');self.assertFalse(r.physical(self.wait,[cq],self.lanes,self.now,.25))
    def test_L0_remains_admitted_when_projection_unknown(self):
        with patch.object(self.c,'predict',return_value=dict(valid=False,reason='unknown')):
            e=self.c.encode(self.q,self.lanes,self.now,[self.base,self.wait],self.q)
        self.assertTrue(e['mask'][0]);self.assertFalse(e['mask'][1])
    def test_same_bank_rule_and_PPO_have_same_encoding_and_mask(self):
        self.c.mode=r.RULE;e=self.encode();self.c.mode=r.PPO;e2=self.encode()
        for name in ('state','candidates','mask','physical_mask'):np.testing.assert_array_equal(e[name],e2[name])
    def test_network_cannot_sample_empty_or_unsupported_slots(self):
        net=r.c.ActorCritic();e=self.encode();e['mask'][1]=False
        dist,value=net(torch.from_numpy(e['state'])[None],torch.from_numpy(e['candidates'])[None],torch.from_numpy(e['mask'])[None])
        self.assertEqual(float(dist.probs[0,0].detach()),1.);self.assertEqual(tuple(value.shape),(1,6))
    def test_suffix_hook_restores_original_on_failure(self):
        a,b=r.old.LightBand,r.old.fast.LightBand
        with self.assertRaises(RuntimeError):
            with r.service_suffix_scope():self.assertIs(r.old.LightBand,r.ServiceLight);raise RuntimeError('fixture')
        self.assertIs(r.old.LightBand,a);self.assertIs(r.old.fast.LightBand,b)
    def test_episode_AP_reward_telescopes_with_same_time_dispatches(self):
        e=self.encode();self.c.snapshots=[dict(e,chosen=0,actor_eligible=False),dict(e,chosen=0,actor_eligible=False)]
        row=dict(planned=1,completed=1,energy_j=3.,incomplete=0,urgent_failure=0,normal_failure=0,urgent_p95_ms=0.,peak_ap_c=30.)
        ref=dict(row,peak_ap_c=30.1);frames,rewards,costs,valid=r.c.episode_targets(self.c,row,[(35.,29.),(180.,30.)],ref)
        self.assertAlmostEqual(sum(rewards),.1);self.assertTrue(valid.all());self.assertEqual(len(frames),2)

if __name__=='__main__':unittest.main()
