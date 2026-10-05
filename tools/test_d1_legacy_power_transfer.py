import unittest
import numpy as np
from tools import d1_legacy_power_transfer as c


class LegacyTransferTests(unittest.TestCase):
    def test_known_occupancy_and_baseline_preserve_other_model_terms(self):
        rows=[];z=np.array([1.1,.8,.5,.4,.9])
        for i in range(5):
            occupancy=np.zeros(4)
            if i:occupancy[i-1]=5.
            rows.append(dict(zip(c.m.STATES,occupancy),role='legacy_development',observed_j=float(np.r_[5,occupancy]@z)))
        old=dict(ap={'k':1.},service={'frozen':True})
        model,err=c.fit(rows,old)
        np.testing.assert_allclose([model['resident_w'],*model['energy_increment_w'].values()],z,atol=1e-10)
        np.testing.assert_allclose(err,0,atol=1e-10)
        self.assertEqual(model['ap'],old['ap']);self.assertNotIn('resident_w',old)
        rows[0]['role']='confirmation'
        with self.assertRaisesRegex(ValueError,'development only'):c.fit(rows,old)

    def test_rank_failure_not_filled_with_other_state(self):
        rows=[dict.fromkeys(c.m.STATES,0.) | dict(role='legacy_development',observed_j=5.)]*8
        with self.assertRaisesRegex(ValueError,'unidentified'):c.fit(rows,{})


if __name__=='__main__':unittest.main()
