import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from tools import d1_ap_rate_identification as a
from tools import d1_ap_preparation_memory as m


PARAMETERS = {'ap_cooling_rate_per_s':.05,
              'ap_slope_at_30_c_per_s':{'resident_idle':.1,'detection_CPU':.3}}


def synthetic():
    pre=[]
    for t in range(-30,35,3):
        temp,_=m.advance(31,-.03,0,29,.05,30,0,t+30)
        pre.append(dict(t=float(t),ap=temp,lo=t-.05,hi=t+.05))
    c=dict(id='idle_development',inputs=dict(preload=pre,
        segments=[dict(start_s=0,end_s=35,state='idle'),
                  dict(start_s=35,end_s=47,state='detection:CPU'),
                  dict(start_s=47,end_s=180,state='idle')],query_s=list(range(36,179,3))))
    c['observed_ap_c']=a.predict(c,PARAMETERS,.05,1.4)[0]
    return c


class IdentificationTests(unittest.TestCase):
    def test_exact_synthetic_rate_gain_recovery(self):
        best,rows=a.fit(synthetic(),PARAMETERS,[.025,.05,.1])
        self.assertEqual(best['beta_per_s'],.05)
        self.assertAlmostEqual(best['gain'],1.4,places=10)
        self.assertLess(best['rmse_c'],1e-10)

    def test_linear_gain_and_future_targets_not_used(self):
        c=synthetic();zero,_=a.predict(c,PARAMETERS,.05,0);one,_=a.predict(c,PARAMETERS,.05,1)
        two,_=a.predict(c,PARAMETERS,.05,2)
        np.testing.assert_allclose(two,2*np.array(one)-zero,atol=1e-12)
        c['observed_ap_c']=[9999]*len(c['observed_ap_c'])
        self.assertEqual(a.predict(c,PARAMETERS,.05,2)[0],two)

    def test_confirmation_rejected_as_development(self):
        c=synthetic();c['id']='confirmation_preidle65'
        with self.assertRaisesRegex(ValueError,'development role'):a.fit(c,PARAMETERS,[.05])

    def test_no_load_has_no_gain_information(self):
        c=synthetic();c['no_load']=True;c['inputs']['segments']=[dict(start_s=0,end_s=180,state='idle')]
        c['observed_ap_c']=a.predict(c,PARAMETERS,.05,1)[0]
        r=a.profile(c,PARAMETERS,[.05])[0]
        self.assertIsNone(r['gain']);self.assertEqual(r['gain_information'],0)
        self.assertEqual(a.state_information(c,PARAMETERS)['rank'],0)
        with self.assertRaisesRegex(ValueError,'unidentified'):a.fit(c,PARAMETERS,[.05])

    def test_two_idle_decay_rates_can_exchange_labels(self):
        # Same observable T(t), different labels beta and 1/tau. This establishes
        # an algebraic ambiguity, not a physical conclusion about the phone.
        beta=.06;rate=.025;E=29.;A=1.2;B=-.5;T=E+A+B
        for t in [0,1,10,40,100]:
            first=m.advance(T,(beta-rate)*B,0,E,beta,1/rate,0,t)[0]
            swapped=m.advance(T,(rate-beta)*A,0,E,rate,1/beta,0,t)[0]
            self.assertAlmostEqual(first,swapped,places=12)

    def test_control_future_bracket_and_gap_rejected(self):
        c=synthetic();c['no_load']=True;c['inputs']['segments']=[dict(start_s=0,end_s=180,state='idle')]
        c['inputs']['preload'][-1]['hi']=37
        with self.assertRaisesRegex(ValueError,'boundary'):a.predict(c,PARAMETERS,.05,1)
        c=synthetic();c['no_load']=True;c['inputs']['segments']=[dict(start_s=0,end_s=180,state='idle')]
        c['inputs']['query_s']=[36,70]
        with self.assertRaisesRegex(ValueError,'targets'):a.predict(c,PARAMETERS,.05,1)

    def test_missing_target_fails_before_fit_or_output(self):
        data=a.inputs();data['cases'][1]['observed_ap_c'][0]=float('nan')
        with tempfile.TemporaryDirectory() as temp,patch.object(a,'fit') as fit:
            out=Path(temp)/'new'
            with self.assertRaisesRegex(ValueError,'missing target'):a.run(data,a.common.read(a.CONTRACT),out)
            fit.assert_not_called();self.assertFalse(out.exists())

    def test_unsupported_state_and_missing_window(self):
        c=synthetic();c['inputs']['segments'][1]['state']='unknown'
        with self.assertRaises(ValueError):a.predict(c,PARAMETERS,.05,1)
        self.assertIsNone(a.window_delta([0,20],[28,29],0,10))
        self.assertEqual(a.window_delta([0,5,10],[28,28.5,29],0,10),1)


if __name__=='__main__':unittest.main()
