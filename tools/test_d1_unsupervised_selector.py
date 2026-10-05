import copy
import unittest
import numpy as np
from tools import d1_unsupervised_selector as u


class UnsupervisedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys,cls.X=u.history_matrix();cls.rows=u.m.read(u.m.SOURCE)
        cls.fits={k:u.cluster_fit(cls.X,k) for k in ('kmeans','gmm')}

    def test_split_unit(self):
        self.assertEqual(len(self.keys),36)
        self.assertFalse(any(u.m.holdout(e) for e,_ in self.keys))
        self.assertEqual({seed for _,seed in self.keys},{81001,81002})

    def test_deterministic_feature_only_clustering(self):
        for kind in self.fits:
            again=u.cluster_fit(self.X,kind)
            np.testing.assert_array_equal(again[2],self.fits[kind][2])

    def test_evaluation_labels_do_not_change_mapping(self):
        rows=copy.deepcopy(self.rows)
        for r in rows:
            if r['stage']!='development':r.update(energy_j=-100000,deadline_met=0)
        for f in self.fits.values():
            self.assertEqual(u.calibrate(self.keys,f[2],rows),u.calibrate(self.keys,f[2],self.rows))

    def test_no_feasible_does_not_skip_fallback(self):
        f=self.fits['kmeans'];mapping={int(c):dict(energy=None,thermal=None) for c in set(f[2])}
        e,seed=self.keys[0];d=u.choose(f,mapping,u.m.previous(e,seed),'energy')
        self.assertEqual(d['policy'],'EFT_REFERENCE');self.assertEqual(d['reason'],'no_cluster_feasible_policy')

    def test_out_of_radius(self):
        f=self.fits['kmeans'];mapping=u.calibrate(self.keys,f[2],self.rows)
        e,seed=self.keys[0];h=u.m.previous(e,seed)
        for q in h:q['arrival_ns']*=1000
        self.assertEqual(u.choose(f,mapping,h,'energy')['reason'],'outside_training_radius')

    def test_future_history_rejected(self):
        f=self.fits['kmeans'];mapping=u.calibrate(self.keys,f[2],self.rows)
        e,seed=self.keys[0];h=u.m.previous(e,seed);h[-1]['arrival_ns']=1
        with self.assertRaises(ValueError):u.choose(f,mapping,h,'energy')

    def test_missing_cost_not_zero(self):
        rows=copy.deepcopy(self.rows);e,seed=self.keys[0]
        next(r for r in rows if r['envelope']==e['id'] and int(r['seed'])==seed)['energy_j']=None
        with self.assertRaises(ValueError):u.calibrate(self.keys,self.fits['kmeans'][2],rows)

    def test_invalid_method_shape(self):
        with self.assertRaises(ValueError):u.cluster_fit(self.X,'invented')
        with self.assertRaises(ValueError):u.cluster_fit(self.X[:8],'kmeans')


if __name__=='__main__':unittest.main()
