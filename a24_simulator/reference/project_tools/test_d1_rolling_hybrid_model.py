import copy, json, unittest
import numpy as np
from tools import d1_rolling_hybrid_model as h


class Hybrid(unittest.TestCase):
    def setUp(self):
        self.frozen,self.case,self.model=h.load();self.initial=self.case['initial']
    def test_streaming_matches_delivered_v3_api_all_supported_states(self):
        ref=json.loads((h.MODEL.parent/'thermal_equivalence_fixture.json').read_text(encoding='utf-8'))
        values=h.path(ref['segments'],ref['queries'],ref['initial'],self.model)
        self.assertLess(np.max(np.abs(np.array(values)-ref['expected'])),1e-9)
    def test_state_propagation_composes_with_nonzero_slow_memory(self):
        state=h.initialize(self.initial,self.model)
        one=h.advance(state,h.STATES[3],7.,self.model)
        two=h.advance(h.advance(state,h.STATES[3],3.,self.model),h.STATES[3],4.,self.model)
        for key in ('t','h','slow'):self.assertAlmostEqual(one[key],two[key],places=12)
        self.assertGreater(one['slow'],0.)
    def test_online_grid_and_future_forecast_equal_full_schedule(self):
        c=h.ExecutionController(self.frozen,self.initial)
        lanes=h.prior.new.old.core.empty_lanes(0)
        c.observe(0,lanes);c.observe(35e9,lanes)
        q=h.prior.ticket('C','classification')
        active=copy.deepcopy(lanes);active['CPU']=dict(request=q,phase='ASSIGNED',since=35e9,dispatch=35e9)
        c.observe(35e9,active)
        active['CPU'].update(phase='EXECUTING',since=40e9);c.observe(40e9,active)
        ss=[dict(start_s=0,end_s=35,state='idle'),dict(start_s=35,end_s=45,state=h.STATES[0]),dict(start_s=45,end_s=180,state='idle')]
        expected=h.path(ss,list(range(35,181)),self.initial,self.model)
        for t in range(35,41):self.assertAlmostEqual(c.grid[t],expected[t-35],places=10)
        forecast=h.costs(c,[dict(start=40,end=45,state=h.STATES[0])],40e9)
        self.assertAlmostEqual(forecast['peak_ap_c'],max([c.t]+expected[5:]),places=10)
        self.assertAlmostEqual(forecast['global_peak_ap_c'],max(expected),places=10)
        self.assertAlmostEqual(forecast['remaining_increment_j'],5*self.frozen['energy_increment_w'][h.STATES[0]],places=12)
        c.observe(45e9,h.prior.new.old.core.empty_lanes(45e9));c.observe(60e9,h.prior.new.old.core.empty_lanes(60e9))
        self.assertAlmostEqual(c.t,expected[25],places=10)
    def test_scoped_hook_restores_original_after_exception(self):
        fast=h.prior.new.old.fast;before=fast.costs;key=h.prior.new.state_key
        with self.assertRaises(RuntimeError):
            with h.forecast_scope():
                self.assertIs(fast.costs,h.costs);raise RuntimeError('fixture')
        self.assertIs(fast.costs,before);self.assertIs(h.prior.new.state_key,key)
    def test_future_preload_and_unmodeled_history_rejected(self):
        bad=copy.deepcopy(self.initial);bad['preload'][-1]['hi']=35.
        with self.assertRaises(ValueError):h.initialize(bad,self.model)
        bad=copy.deepcopy(self.initial);bad['history']=[dict(start_s=-1,end_s=0,state=h.STATES[0])]
        with self.assertRaises(ValueError):h.initialize(bad,self.model)
        with self.assertRaises(ValueError):h.advance(h.initialize(self.initial,self.model),'detection_GPU',1,self.model)
    def test_energy_and_service_identity_preserved(self):
        self.assertEqual(self.frozen['energy_increment_w'],self.model['energy']['increments'])
        self.assertEqual(h.p.MODEL_SHA,self.model['service']['sha256'])
        self.assertEqual(self.model['energy']['gain'],0.)

if __name__=='__main__':unittest.main()
