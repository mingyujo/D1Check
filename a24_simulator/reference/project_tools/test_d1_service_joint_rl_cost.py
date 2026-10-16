import unittest
import numpy as np
from types import SimpleNamespace
from tools import d1_service_joint_rl_cost as x

class AbsoluteService(unittest.TestCase):
    def target(self,normal=45,refnormal=45):
        s=dict(state=np.zeros(56,np.float32),candidates=np.zeros((8,28),np.float32),mask=np.array([True]+[False]*7),chosen=0,now_ns=35_000_000_000)
        row=dict(planned=100,completed=100,incomplete=0,energy_j=150.,peak_ap_c=30.,urgent_failure=0,normal_failure=normal,urgent_p95_ms=300.,urgent_planned=40,normal_planned=60)
        ref=dict(row,normal_failure=refnormal)
        return x.episode_targets(SimpleNamespace(snapshots=[s]),row,[(35,30.)],ref)
    def test_matching_failed_reference_is_not_zero_service(self):
        q=self.target();self.assertEqual(q[2][3],45);self.assertEqual(q[4]['relative_excess']['normal'],0)
    def test_excess_is_not_double_counted(self):
        q=self.target(46,45);self.assertEqual(q[2][3],46);self.assertEqual(q[4]['relative_excess']['normal'],1)
    def test_critic_target_abi(self):
        q=self.target();self.assertEqual(q[0][0]['target'].shape,(6,));np.testing.assert_array_equal(q[0][0]['target'][1:],q[2].astype(np.float32))

if __name__=='__main__':unittest.main()
