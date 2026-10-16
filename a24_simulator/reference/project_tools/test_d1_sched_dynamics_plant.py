"""Short synthetic contract checks; no full simulation, fitting or learning."""
import copy
import unittest
from pathlib import Path
from tools import d1_sched_dynamics_profiles as p
from tools import d1_sched_dynamics_plant as e

def ticket(rid='r',task='classification',priority='urgent',arrival=0,units=1):
    return dict(id=rid,task=task,priority=priority,ordinal=0,arrival_ns=arrival,
                deadline_offset_ns=1_500_000_000 if priority=='urgent' else 6_000_000_000,work_units=units)

def toy(name='neutral',step=.05):
    # Actual anchor loading is read-only. Synthetic five-phase work replaces it.
    profile=p.profiles('A24')[name]; profile['step_s']=step
    source=profile['service_anchor']
    ds=[10_000_000,1_000_000_000,200_000_000,10_000_000,300_000_000]
    source['means']={k:list(ds) for k in source['means']}
    source['pools']={s:{k:[dict(durations_ns=list(ds),source_request_id='synthetic')] for k in source['means']} for s in ('train','dev','confirm')}
    return profile

class Contracts(unittest.TestCase):
    def test_output_is_not_available(self):
        d=e.Device(toy(),deterministic=True); q=ticket(); d.dispatch([(q,'CPU')]); d.advance(1_010_000_000)
        self.assertIn('response_ns',d.records['r']); self.assertEqual(d.public()['lanes']['CPU']['phase'],'OUTPUT_READY')
        self.assertFalse(d.feasible([(ticket('r2'),'CPU')])); d.advance(1_520_000_000)
        self.assertIsNone(d.public()['lanes']['CPU']); self.assertTrue(d.feasible([(ticket('r2'),'CPU')]))
        self.assertEqual(d.records['r']['lane_available_ns'],1_520_000_000)

    def test_supported_pairs_only(self):
        d=e.Device(toy()); c=ticket('c'); det=ticket('d','detection','normal')
        self.assertTrue(d.feasible([(c,'GPU'),(det,'CPU')]))
        self.assertFalse(d.feasible([(c,'CPU'),(det,'CPU')]))
        self.assertFalse(d.feasible([(c,'NPU')]))
        self.assertFalse(d.feasible([(det,'GPU')]))
        d.dispatch([(c,'GPU'),(det,'CPU')]); self.assertFalse(d.feasible([(ticket('z'),'NPU')]))

    def test_duplicate_and_future_dispatch(self):
        d=e.Device(toy()); q=ticket(); self.assertFalse(d.feasible([(ticket(arrival=1),'CPU')]))
        d.dispatch([(q,'CPU')]); self.assertFalse(d.feasible([(q,'GPU')]))
        self.assertRaises(ValueError,d.dispatch,[(q,'GPU')])

    def test_public_has_no_remaining_or_future(self):
        d=e.Device(toy()); d.dispatch([(ticket(),'CPU')]); d.advance(250_000_000); public=d.public()
        self.assertEqual(set(public['lanes']['CPU']),{'request','phase','since','dispatch','estimate_ns'})
        self.assertNotIn('realized_work_ns',str(public)); self.assertNotIn('sample_origin',str(public))
        self.assertFalse(public['ambient_is_measured']); self.assertEqual(public['now_ns'],250_000_000)
        self.assertTrue(all(v['time_ns']<=d.now for v in public['observed_history']))

    def test_known_work_scales_only_execution(self):
        d=e.Device(toy()); a=d.estimate(ticket(units=1),'GPU'); b=d.estimate(ticket(units=3),'GPU')
        self.assertEqual(b[1],3*a[1]); self.assertEqual(b[:1]+b[2:],a[:1]+a[2:])

    def test_hot_state_and_recent_load_change_estimate(self):
        d=e.Device(toy('thermal_only'),initial={'ap_c':42.,'reference_ap_c':30.}); q=ticket()
        before=d.estimate(q,'CPU')[1]; self.assertGreater(before,1e9)
        d.dispatch([(q,'CPU')]); d.advance(500_000_000)
        self.assertGreater(d.public()['recent_activity']['CPU'],0.)

    def test_parallel_has_cost_and_interference(self):
        d=e.Device(toy('parallel_only')); c=ticket('c'); det=ticket('d','detection','normal')
        pair=[(c,'GPU'),(det,'CPU')]
        self.assertGreater(d.estimate(c,'GPU',pair)[1],d.estimate(c,'GPU')[1])
        d.dispatch(pair); d.advance(500_000_000)
        self.assertGreater(d.current_cost()['parallel_extra_energy_j'],0.)
        self.assertEqual(d.current_cost()['activation_energy_j'],0.)

    def test_activation_cost_and_tail_are_separate(self):
        d=e.Device(toy('activation_only')); d.dispatch([(ticket(),'GPU')]); d.advance(2_000_000_000)
        cost=d.current_cost(); self.assertGreater(cost['activation_energy_j'],0.); self.assertGreater(cost['idle_tail_energy_j'],0.)
        self.assertAlmostEqual(cost['additional_energy_j'],cost['activation_energy_j']+cost['parallel_extra_energy_j']+cost['idle_tail_energy_j'])

    def test_step_convergence_short_synthetic(self):
        outputs=[]
        for step in (.05,.025):
            d=e.Device(toy('full',step),deterministic=True,initial={'ap_c':40.,'reference_ap_c':30.})
            d.dispatch([(ticket('c'),'GPU'),(ticket('d','detection','normal'),'CPU')]); d.advance(3_000_000_000)
            outputs.append((d.records,d.current_cost()))
        self.assertLess(abs(outputs[0][0]['c']['response_ns']-outputs[1][0]['c']['response_ns']),5_000_000)
        self.assertLess(abs(outputs[0][1]['energy_window_j']-outputs[1][1]['energy_window_j']),.005)
        self.assertLess(abs(outputs[0][1]['mean_ap_c']-outputs[1][1]['mean_ap_c']),.005)

    def test_random_is_request_backend_keyed(self):
        profile=toy(); source=profile['service_anchor']; key='classification|GPU'
        source['pools']['train'][key]=[dict(durations_ns=[0,900_000_000+i*10_000_000,0,0,0],source_request_id=str(i)) for i in range(9)]
        first=e.Device(profile,environment_seed=23); second=e.Device(profile,environment_seed=23)
        first.dispatch([(ticket('target'),'GPU')]); second.dispatch([(ticket('other'),'CPU')]); second.advance(2_000_000_000); second.dispatch([(ticket('target'),'GPU')])
        self.assertEqual(first.records['target']['sample_origin'],second.records['target']['sample_origin'])

    def test_profile_zero_terms_and_independent_devices(self):
        neutral=toy(); full=toy('full')
        for k in ('thermal_slowdown_per_c','recent_slowdown','parallel_extra_slowdown','startup_s','startup_j','idle_tail_w'):
            self.assertFalse(any(neutral[k].values()))
        self.assertEqual(neutral['parallel_extra_w'],0.); self.assertGreater(full['parallel_extra_w'],0.)
        self.assertRaises(ValueError,e.Device,full,device='S26')

    def test_registered_step_and_public_abi_fail_closed(self):
        self.assertRaises(ValueError,e.Device,toy(),step_s=.1)
        self.assertRaises(ValueError,e.validate_request,dict(ticket(),future_energy_j=0))
        self.assertRaises(ValueError,e.validate_request,ticket(units=4))

    def test_s26_mean_neutral_matches_frozen_phase_boundaries(self):
        path=p.ROOT.parents[1]/'outputs/S26-PAIR-OBSERVER-06/repaired_final_model_START0.json'
        source=p.read(path); profile=p.profiles('S26',source)['neutral']
        dynamic=e.Device(profile,deterministic=True)
        original=e.old.Device(source['service'],deterministic=True)
        c=ticket('c'); det=ticket('d','detection','normal')
        jobs=[(c,'NPU'),(det,'CPU')]; dynamic.dispatch(jobs)
        original.dispatch([({k:v for k,v in q.items() if k!='work_units'},b) for q,b in jobs])
        dynamic.advance(1_000_000_000); original.advance(1_000_000_000)
        for rid in ('c','d'):
            for field in (*e.FIELDS,'response_ns'):
                self.assertEqual(dynamic.records[rid][field],original.records[rid][field])
        self.assertEqual(dynamic.current_cost()['additional_energy_j'],0.)
        self.assertFalse(dynamic.feasible([(ticket('z','detection','normal'),'NPU')]))

    def test_s26_baseline_delegate_intact_samples_and_events(self):
        path=p.ROOT.parents[1]/'outputs/S26-PAIR-OBSERVER-06/repaired_final_model_START0.json'
        source=p.read(path); original=e.old.Device(source['service'],environment_seed=27)
        wrapped=e.FrozenS26ServiceDevice(source,environment_seed=27)
        q={k:v for k,v in ticket().items() if k!='work_units'}
        for dev in (original,wrapped): dev.dispatch([(q,'CPU')]); dev.advance(1_000_000_000)
        self.assertEqual(original.records,wrapped.records); self.assertEqual(original.events,wrapped.events)

    def test_delayed_observations_and_internal_ticks_are_not_decisions(self):
        d=e.Device(toy('full'),initial={'ap_c':40.,'reference_ap_c':30.}); before=d.public(); revision=d.decision_revision
        d.advance(800_000_000); after=d.public()
        self.assertEqual(after['ap_c'],before['ap_c']); self.assertEqual(after['power_w'],before['power_w'])
        self.assertEqual(d.decision_revision,revision); self.assertEqual(d.integration_segments,16)
        self.assertAlmostEqual(after['thermal_observation_age_s'],.8)
        d.advance(900_000_000); self.assertEqual(d.decision_revision,revision+1)
        d.advance(2_000_000_000); self.assertNotEqual(d.public()['ap_c'],before['ap_c'])
        self.assertEqual(d.public()['thermal_observation_age_s'],0.)

    def test_cooling_requires_available_and_learning_stops_at120(self):
        d=e.Device(toy()); d.advance(e.HORIZON_NS); snapshot=d.current_cost(); trace=copy.deepcopy(d.learning_cost_trace)
        d.observe_cooling(); self.assertEqual(trace,d.learning_cost_trace)
        self.assertEqual(trace[-1]['time_ns'],e.HORIZON_NS)
        self.assertIsNotNone(d.current_cost()['mean_after35_c']); self.assertIsNotNone(snapshot['mean_after35_c'])
        busy=e.Device(toy()); busy.advance(119_000_000_000); busy.dispatch([(ticket(arrival=119_000_000_000),'CPU')]); busy.advance(e.HORIZON_NS)
        self.assertRaises(ValueError,busy.observe_cooling)

    def test_declared_and_original_slo_are_separate(self):
        q=ticket(); q['deadline_offset_ns']=2_500_000_000; e.validate_request(q)
        row=dict(q,status='succeeded',response_ns=2_000_000_000)
        metrics=e.old.metrics([row]); self.assertEqual(metrics['urgent_failure'],1); self.assertEqual(metrics['urgent_declared_failure'],0)

if __name__=='__main__': unittest.main()
