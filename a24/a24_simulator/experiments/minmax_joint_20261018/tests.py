import copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'deep_repair_20261018'))
from minmax_labels import scalar,labels,B,np

class Tests(unittest.TestCase):
    def test_energy_loss_cannot_be_offset_by_heat_gain(self):self.assertGreater(scalar(101.,1.,100.,10.),1.)
    def test_heat_loss_cannot_be_offset_by_energy_gain(self):self.assertGreater(scalar(1.,10.1,100.,10.),1.)
    def test_both_improvements_are_below_reference(self):self.assertLess(scalar(99.,9.9,100.,10.),1.)
    def test_reference_is_exactly_one(self):self.assertEqual(scalar(100.,10.,100.,10.),1.)
    def test_potential_differences_telescope(self):
        points=[scalar(e,h,100.,10.) for e,h in [(0.,0.),(10.,.2),(20.,6.),(90.,9.)]]
        self.assertAlmostEqual(.5*sum(2*(b-a) for a,b in zip(points,points[1:])),points[-1])
    def test_invalid_normalizer_is_rejected(self):
        with self.assertRaises(ValueError):scalar(1.,1.,0.,1.)
        with self.assertRaises(ValueError):scalar(1.,1.,1.,0.)

    def fixture(self,times):
        class Physics:
            c=SimpleNamespace(idle_c=26.,baseline=1.)
            def transition(self,state,active,dt):return state,dict(increment=(1. if active else .25)*dt,temperature_area=state['temperature_c']*dt)
        trace=[dict(start_ns=35_000_000_000,end_ns=36_000_000_000,dt=1.,active=[1],state=dict(temperature_c=28.)),dict(start_ns=36_000_000_000,end_ns=39_000_000_000,dt=3.,active=[],state=dict(temperature_c=27.))]
        result=dict(requests=[dict(available_ns=36_000_000_000)],trace=trace);frames=[dict(time_ns=t,x=[[1.,2.,3.]]) for t in times]
        original=np.arange(len(frames)*5,dtype=float).reshape(len(frames),5)
        with patch.object(B,'repaired_labels',return_value=(original,dict(cost_sum=original.sum(0).tolist()))):
            costs,audit=labels(result,frames,dict(drain_stop_s=40),Physics(),{},38_000_000_000,dict(completion_total_J_proxy=4.,common_increment_J_proxy=3.,mean_AP_c=28.))
        return original,costs,audit,frames

    def test_increment_and_heat_use_common_horizon_including_idle_tail(self):
        original,costs,audit,_=self.fixture([35_100_000_000,35_400_000_000,35_800_000_000])
        self.assertAlmostEqual(costs[:,0].sum()/2,2/3);self.assertEqual(audit['prefix_records'][-1]['common_increment_prefix_J_proxy'],1.5)
        self.assertEqual(audit['prefix_records'][-1]['heat_excess_prefix_Cs'],4.);self.assertTrue(np.array_equal(costs[:,2:],original[:,2:]));self.assertTrue(np.all(costs[:,1]==0))

    def test_same_time_and_refined_decisions_preserve_total_objective(self):
        _,a,_,_=self.fixture([35_100_000_000,35_400_000_000,35_800_000_000]);_,b,_,_=self.fixture([35_100_000_000,35_100_000_000,35_200_000_000,35_400_000_000,35_800_000_000])
        self.assertAlmostEqual(a[:,0].sum(),b[:,0].sum());self.assertTrue(np.isfinite(b).all())

    def test_reward_transformation_keeps_observations_unchanged(self):
        times=[35_100_000_000,35_400_000_000,35_800_000_000];_,_,audit,frames=self.fixture(times)
        self.assertEqual(frames,[dict(time_ns=t,x=[[1.,2.,3.]]) for t in times]);self.assertFalse(audit['new_NN_observation_features'])

if __name__=='__main__':unittest.main()
