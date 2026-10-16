import copy
import unittest
from tools import d1_rolling_energy_shrink as s


def row(identity,x,y,role='development'):
    return dict(id=identity,block='history',role=role,base_j=10.,correction_j=x,observed_j=10.+y)


class ShrinkTests(unittest.TestCase):
    def test_known_gain_and_no_intercept(self):
        rows=[row('a',1,.2),row('a',2,.4),row('b',-1,-.2)]
        fit=s.fit_alpha(rows);self.assertAlmostEqual(fit['alpha'],.2)
        self.assertAlmostEqual(s.loss(rows,.2),0)

    def test_bounds_zero_information_and_tie(self):
        self.assertEqual(s.fit_alpha([row('a',1,2)])['alpha'],1)
        self.assertEqual(s.fit_alpha([row('a',1,-1)])['alpha'],0)
        self.assertAlmostEqual(s.fit_alpha([row('a',1,.2),row('a',1,.8)])['alpha'],.2)
        with self.assertRaises(ValueError):s.fit_alpha([row('a',0,1)])

    def test_equal_session_weight_not_sample_weight(self):
        rows=[row('a',1,1) for _ in range(100)]+[row('b',1,0)]
        self.assertAlmostEqual(s.fit_alpha(rows)['alpha'],0)

    def test_median_minimizes_independent_grid_fixture(self):
        rows=[row('a',.5,.1),row('a',-2,-.3),row('b',1,.6),row('b',.1,-.1)]
        alpha=s.fit_alpha(rows)['alpha'];minimum=s.loss(rows,alpha)
        self.assertTrue(all(s.loss(rows,i/1000)>=minimum-1e-12 for i in range(1001)))

    def test_evaluation_cannot_fit_or_select(self):
        with self.assertRaises(ValueError):s.fit_alpha([row('a',1,.2,role='confirmation')])
        rows=s.load_rows();baseline=s.freeze(rows);changed=copy.deepcopy(rows)
        for x in changed:
            if x['role']!='development':x['observed_j']*=1000
        self.assertEqual(s.freeze(changed),baseline)

    def test_original_full_correction_and_partial_sum(self):
        rows=s.load_rows()
        self.assertEqual(len(rows),160)
        for x in rows:
            self.assertEqual(s.apply(x['base_j'],x['correction_j'],0),x['base_j'])
            self.assertAlmostEqual(s.apply(x['base_j'],x['correction_j'],1),x['base_j']+x['correction_j'])
        subset=[x for x in rows if x['id']==rows[0]['id']]
        self.assertEqual(len(subset),8)
        self.assertEqual(subset[0]['start_s'],35)
        self.assertEqual(subset[-1]['end_s'],115)

    def test_nonfinite_and_nonpositive_not_clipped(self):
        for alpha in (-.1,1.1,float('nan')):
            with self.assertRaises(ValueError):s.apply(10,1,alpha)
        with self.assertRaises(ValueError):s.apply(1,-2,1)
        self.assertEqual(s.previous.h.m.sha(s.previous.h.m.MODEL),s.previous.h.m.MODEL_SHA)

    def test_prediction_entry_and_future_prefix(self):
        r=s.previous;case=r.h.m.read(r.BUNDLE/'inputs.json.gz')[1];frozen=r.h.m.read(r.h.m.MODEL);contract=r.h.m.read(r.BUNDLE/'contract.json')
        snap=r.snapshot(case,65,frozen,contract)
        self.assertEqual(s.predict(case,frozen,snap,0,75),r.forecast_energy(case,frozen,snap,'FROZEN_OPEN_LOOP',75))
        self.assertEqual(s.predict(case,frozen,snap,1,75),r.forecast_energy(case,frozen,snap,'ROLLING_OFFSET',75))
        changed=copy.deepcopy(case)
        for x in changed['power_observations']:
            if x['available']>65:x['value']=9999
        self.assertEqual(s.predict(case,frozen,snap,.2,75),s.predict(changed,frozen,snap,.2,75))
        with self.assertRaises(ValueError):s.predict(case,frozen,dict(snap,power_available=66),.2,75)
        with self.assertRaises(ValueError):s.predict(case,frozen,snap,.2,70)


if __name__=='__main__':unittest.main()
