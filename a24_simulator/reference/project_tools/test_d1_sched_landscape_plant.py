"""V20 short synthetic fixtures; no full requests, fitting or learning."""
import copy
import math
import unittest
from tools import d1_sched_dynamics_plant as base
from tools import d1_sched_dynamics_profiles as profiles
from tools import d1_sched_landscape_plant as new

def ticket(rid='r',task='classification',priority='urgent'):
    return dict(id=rid,task=task,priority=priority,ordinal=0,arrival_ns=0,
                deadline_offset_ns=1_500_000_000 if priority=='urgent' else 6_000_000_000,work_units=1)

def toy(w=(0.,0.,0.),step=.05):
    p=profiles.profiles('A24')['neutral'];p['abi']=new.PROFILE_ABI;p['active_route_extra_w']=dict(zip(base.BACKENDS,w));p['step_s']=step
    source=p['service_anchor'];ds=[100_000_000,1_000_000_000,200_000_000,100_000_000,500_000_000]
    source['means']={k:list(ds) for k in source['means']}
    source['pools']={s:{k:[dict(durations_ns=list(ds),source_request_id='synthetic')] for k in source['means']} for s in ('train','dev','confirm')}
    return p

class Landscape(unittest.TestCase):
    def test_known_cpu_route_j_and_heat(self):
        d=new.Device(toy((4.,0.,0.)),deterministic=True);d.dispatch([(ticket(),'CPU')]);d.advance(1_100_000_000)
        c=d.current_cost();self.assertAlmostEqual(c['active_route_extra_energy_j'],4.,places=12)
        self.assertAlmostEqual(c['active_route_extra_energy_by_backend_j']['CPU'],4.,places=12)
        self.assertEqual(c['active_route_extra_energy_by_backend_j']['GPU'],0.);self.assertEqual(c['active_route_extra_energy_by_backend_j']['NPU'],0.)
        expected=.8*4*(1-math.exp(-.05))
        self.assertAlmostEqual(d._extra_ap,expected,places=12)

    def test_output_keeps_owner_but_stops_route_power(self):
        d=new.Device(toy((4.,0.,0.)),deterministic=True);q=ticket();d.dispatch([(q,'CPU')]);d.advance(1_100_000_000)
        self.assertEqual(d.public()['lanes']['CPU']['phase'],'OUTPUT_READY');self.assertFalse(d.feasible([(ticket('next'),'CPU')]))
        self.assertEqual(d.current_cost()['active_route_extra_w_current'],0.)
        d.advance(1_900_000_000);self.assertIsNone(d.public()['lanes']['CPU']);self.assertAlmostEqual(d.current_cost()['active_route_extra_energy_j'],4.,places=12)

    def test_route_and_parallel_are_separate(self):
        p=toy((4.,2.,0.));p['parallel_extra_w']=.5
        d=new.Device(p,deterministic=True);d.dispatch([(ticket('c'),'GPU'),(ticket('d','detection','normal'),'CPU')]);d.advance(1_100_000_000)
        c=d.current_cost();self.assertAlmostEqual(c['active_route_extra_energy_j'],6.,places=12);self.assertAlmostEqual(c['parallel_extra_energy_j'],.5,places=12)
        self.assertAlmostEqual(c['additional_energy_j'],c['active_route_extra_energy_j']+c['parallel_extra_energy_j']+c['activation_energy_j']+c['idle_tail_energy_j'],places=12)
        self.assertAlmostEqual(d._extra_ap,.8*6.5*(1-math.exp(-.05)),places=12)

    def test_zero_overlay_matches_parent_short_trajectory_exactly(self):
        p=toy();old=copy.deepcopy(p);old['abi']=profiles.ABI;old.pop('active_route_extra_w')
        a=base.Device(old,deterministic=True);b=new.Device(p,deterministic=True)
        for d in (a,b):d.dispatch([(ticket(),'CPU')]);d.advance(2_000_000_000)
        self.assertEqual(a.records,b.records);self.assertEqual(a.events,b.events);self.assertEqual(a.public(),b.public());self.assertEqual(a.learning_cost_trace,b.learning_cost_trace)
        self.assertEqual(a.cost_trace,b.cost_trace)
        for k,v in a.current_cost().items():self.assertEqual(v,b.current_cost()[k])

    def test_missing_route_key_defaults_to_zero(self):
        p=toy();p.pop('active_route_extra_w');d=new.Device(p);d.dispatch([(ticket(),'GPU')]);d.advance(2_000_000_000)
        self.assertEqual(d.current_cost()['active_route_extra_energy_j'],0.)

    def test_public_power_is_last_completed_sample(self):
        d=new.Device(toy((4.,0.,0.)),deterministic=True);initial=d.public()['power_w'];d.dispatch([(ticket(),'CPU')]);d.advance(850_000_000)
        self.assertEqual(d.public()['power_w'],initial);d.advance(900_000_000)
        sampled=d.public()['power_w'];self.assertGreater(sampled,initial+4.)
        d.advance(1_100_000_000);self.assertEqual(d.public()['power_w'],sampled);self.assertLess(d.current_cost()['power_w'],sampled)
        self.assertNotIn('active_route_extra_w',d.public());self.assertNotIn('realized_work_ns',str(d.public()))

    def test_backend_switch_time_and_j_match_estimate_and_ledger(self):
        p=toy();p['switch_s_by_backend']={'CPU':.15};p['switch_j_by_backend']={'CPU':.8}
        d=new.Device(p,deterministic=True);d.dispatch([(ticket('c'),'CPU')]);d.advance(1_900_000_000)
        q=ticket('d','detection','normal');estimate=d.estimate(q,'CPU');self.assertEqual(estimate[0],250_000_000)
        d.dispatch([(q,'CPU')]);d.advance(2_150_000_000)
        self.assertEqual(d.records['d']['realized_work_ns'][0],250_000_000);self.assertEqual(d.records['d']['activation_energy_j'],.8)
        self.assertEqual(d.records['d']['execution_start_ns'],2_150_000_000)

    def test_backend_switch_absent_uses_scalar(self):
        p=toy();p['switch_s']=.02;p['switch_j']=.03;p['switch_s_by_backend']={'GPU':.1};p['switch_j_by_backend']={'GPU':.5}
        d=new.Device(p,deterministic=True);d.dispatch([(ticket('c'),'CPU')]);d.advance(1_900_000_000);q=ticket('d','detection','normal')
        self.assertEqual(d.estimate(q,'CPU')[0],120_000_000);d.dispatch([(q,'CPU')]);self.assertEqual(d.records['d']['activation_energy_j'],.03)

    def test_step25_50_small_feedback_convergence(self):
        values=[]
        for step in (.05,.025):
            p=toy((4.,0.,0.),step);p['thermal_threshold_offset_c']=.1;p['thermal_slowdown_per_c']['CPU']=.2
            d=new.Device(p,deterministic=True);d.dispatch([(ticket(),'CPU')]);d.advance(3_000_000_000);values.append((d.records['r']['response_ns'],d.current_cost()))
        self.assertLess(abs(values[0][0]-values[1][0]),10_000_000)
        self.assertLess(abs(values[0][1]['active_route_extra_energy_j']-values[1][1]['active_route_extra_energy_j']),.04)
        self.assertLess(abs(values[0][1]['mean_ap_c']-values[1][1]['mean_ap_c']),.01)

    def test_bad_overlay_fails_closed(self):
        for value in (-1.,float('inf'),True):
            p=toy();p['active_route_extra_w']['CPU']=value;self.assertRaises(ValueError,new.Device,p)
        p=toy();p['switch_j_by_backend']={'NPU':float('nan')};self.assertRaises(ValueError,new.Device,p)
        p=toy();p['active_route_extra_w']={'CPU':1.};self.assertRaises(ValueError,new.Device,p)
        p=toy();p['abi']=profiles.ABI;self.assertRaises(ValueError,new.Device,p)

    def test_supported_combinations_not_expanded(self):
        d=new.Device(toy((4.,2.,1.)));det=ticket('d','detection','normal')
        self.assertFalse(d.feasible([(det,'GPU')]));self.assertFalse(d.feasible([(ticket(),'NPU')]))
        self.assertTrue(d.feasible([(ticket(),'GPU'),(det,'CPU')]))

    def test_s26_npu_route_uses_same_energy_and_heat_path(self):
        source=profiles.read(profiles.ROOT.parents[1]/'outputs/S26-PAIR-OBSERVER-06/repaired_final_model_START0.json')
        p=profiles.profiles('S26',source)['neutral'];p['abi']=new.PROFILE_ABI;p['active_route_extra_w']={'CPU':8.,'GPU':1.,'NPU':.4}
        ds=[100_000_000,1_000_000_000,200_000_000,100_000_000,500_000_000]
        p['service_anchor']['means']={k:list(ds) for k in p['service_anchor']['means']}
        d=new.Device(p,deterministic=True);d.dispatch([(ticket(),'NPU')]);d.advance(1_100_000_000)
        c=d.current_cost();self.assertAlmostEqual(c['active_route_extra_energy_j'],.4,places=12)
        self.assertEqual(c['active_route_extra_energy_by_backend_j']['CPU'],0.)
        self.assertAlmostEqual(d._extra_ap,.8*.4*(1-math.exp(-.05)),places=12)
        self.assertEqual(d.public()['lanes']['NPU']['phase'],'OUTPUT_READY')
        self.assertFalse(d.feasible([(ticket('d','detection','normal'),'NPU')]))

if __name__=='__main__':unittest.main()
