import copy
import unittest
import numpy as np
from tools import d1_rolling_forecast as r


class RollingForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=r.h.m.read(r.BUNDLE/'inputs.json.gz');cls.frozen=r.h.m.read(r.h.m.MODEL);cls.contract=r.h.m.read(r.BUNDLE/'contract.json')

    def test_midpoint_is_not_availability(self):
        data=[dict(t=40.,available=41.,value=30.)]
        self.assertEqual(r.available(data,40.5),[])
        self.assertEqual(len(r.available(data,41.)),1)

    def test_future_targets_do_not_change_prediction(self):
        c=copy.deepcopy(self.cases[1]);before=r.snapshot(c,65,self.frozen,self.contract)
        ap=r.forecast_ap(c,self.frozen,before,'ROLLING_OFFSET',[66.,70.,75.]);j=r.forecast_energy(c,self.frozen,before,'ROLLING_OFFSET',75)
        for data in (c['ap_observations'],c['power_observations']):
            for x in data:
                if x['available']>65:x['value']=9999
        after=r.snapshot(c,65,self.frozen,self.contract)
        self.assertEqual(before,after)
        np.testing.assert_array_equal(ap,r.forecast_ap(c,self.frozen,after,'ROLLING_OFFSET',[66.,70.,75.]))
        self.assertEqual(j,r.forecast_energy(c,self.frozen,after,'ROLLING_OFFSET',75))

    def test_frozen_matches_original_and_energy_difference(self):
        original_cases=r.h.m.read(r.h.BUNDLE/'inputs.json.gz')
        for c,old in zip(self.cases,original_cases):
            q=[45.,55.,65.];pred,_=r.h.ap_prediction(r.h.inputs(dict(old,q=q)),self.frozen)
            np.testing.assert_allclose(pred,r.frozen_ap(c,self.frozen,q),atol=1e-12,rtol=0)
            snap=r.snapshot(c,45,self.frozen,self.contract)
            actual=r.forecast_energy(c,self.frozen,snap,'FROZEN_OPEN_LOOP',55)
            ref=r.h.m.energy_prediction(old,old['actual'],self.frozen,dict(name='FROZEN'),55)-r.h.m.energy_prediction(old,old['actual'],self.frozen,dict(name='FROZEN'),45)
            self.assertAlmostEqual(actual,ref,places=10)

    def test_stale_missing_and_gap_not_zero(self):
        c=copy.deepcopy(self.cases[1]);c['ap_observations']=[x for x in c['ap_observations'] if x['t']<40]
        c['power_observations']=[x for x in c['power_observations'] if x['t']<40]
        snap=r.snapshot(c,65,self.frozen,self.contract)
        self.assertEqual(snap['ap_status'],'unavailable');self.assertEqual(snap['power_status'],'unavailable')
        with self.assertRaises(ValueError):r.forecast_ap(c,self.frozen,snap,'ROLLING_OFFSET',[70.])
        with self.assertRaises(ValueError):r.forecast_energy(c,self.frozen,snap,'ROLLING_OFFSET',75)

    def test_zero_offset_identity_and_continuity(self):
        c=self.cases[1];snap=r.snapshot(c,65,self.frozen,self.contract)
        snap.update(ap_delta=0.,power_delta_w=0.)
        np.testing.assert_array_equal(r.forecast_ap(c,self.frozen,snap,'ROLLING_OFFSET',[66.,70.]),r.forecast_ap(c,self.frozen,snap,'FROZEN_OPEN_LOOP',[66.,70.]))
        self.assertEqual(r.forecast_energy(c,self.frozen,snap,'ROLLING_OFFSET',75),r.forecast_energy(c,self.frozen,snap,'FROZEN_OPEN_LOOP',75))
        snap=r.snapshot(c,65,self.frozen,self.contract)
        anchored=r.forecast_ap(c,self.frozen,snap,'ROLLING_OFFSET',[snap['ap_t']])[0]
        self.assertAlmostEqual(anchored,snap['ap_value'],places=12)

    def test_prefix_does_not_interpolate_from_future_power(self):
        c=copy.deepcopy(self.cases[1]);snap=r.snapshot(c,45,self.frozen,self.contract)
        max_available=max(x['available'] for x in c['power_observations'] if x['available']<=45)
        self.assertEqual(snap['power_available'],max_available)
        self.assertLessEqual(snap['history_end_s'],45)
        self.assertEqual(r.h.m.sha(r.h.m.MODEL),r.h.m.MODEL_SHA)

    def test_snapshot_and_persistence_need_no_future_schedule(self):
        c=copy.deepcopy(self.cases[1]);snap=r.snapshot(c,65,self.frozen,self.contract)
        changed=copy.deepcopy(c)
        for segment in changed['actual']:
            if segment['start_s']>=65:segment['state']='unknown_future_state'
        changed['actual']=[dict(segment,end_s=min(segment['end_s'],65.)) for segment in changed['actual'] if segment['start_s']<65]
        after=r.snapshot(changed,65,self.frozen,self.contract)
        self.assertEqual(snap,after)
        self.assertEqual(r.forecast_energy(c,self.frozen,snap,'OBSERVATION_PERSISTENCE',75),r.forecast_energy(changed,self.frozen,after,'OBSERVATION_PERSISTENCE',75))
        np.testing.assert_array_equal(r.forecast_ap(c,self.frozen,snap,'OBSERVATION_PERSISTENCE',[70.,75.]),r.forecast_ap(changed,self.frozen,after,'OBSERVATION_PERSISTENCE',[70.,75.]))

    def test_first_origin_and_exact_initial_anchor(self):
        for c in self.cases:
            snap=r.snapshot(c,35,self.frozen,self.contract)
            self.assertEqual(snap['ap_status'],'available')
            last=c['pre'][-1]
            self.assertAlmostEqual(r.frozen_ap(c,self.frozen,[last['t']])[0],last['ap'],places=12)


if __name__=='__main__':unittest.main()
