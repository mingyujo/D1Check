import unittest
import numpy as np
from tools.d1_energy_identifiability import geometry


class GeometryTests(unittest.TestCase):
    def test_duplicate_and_absent_state_not_identifiable(self):
        g=geometry([[1,2,0],[2,4,0],[3,6,0]])
        self.assertEqual(g['rank'],1)
        self.assertTrue(all(c['coefficient_change_bound_per_unit_l2_energy'] is None for c in g['columns']))

    def test_orthogonal_occupancy_and_units(self):
        g=geometry(np.diag([5.,2.,1.]))
        self.assertEqual(g['rank'],3)
        np.testing.assert_allclose([c['independent_fraction'] for c in g['columns']],1)
        np.testing.assert_allclose([c['coefficient_change_bound_per_unit_l2_energy'] for c in g['columns']],[.2,.5,1])


if __name__=='__main__':unittest.main()
