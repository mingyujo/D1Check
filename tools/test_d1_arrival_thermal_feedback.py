"""Small contract checks for the explore-only online thermal candidate."""
import copy
import csv
import math
import unittest

from tools import d1_arrival_explore as engine
from tools import d1_arrival_explore_batch as arrivals
from tools import d1_arrival_thermal_feedback as feedback
from tools import d1_arrival_thermal_feedback_batch as study


class ThermalFeedbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=study.read(study.CONFIG)
        cls.frozen=study.read(study.FREEZE)
        cls.estimate=study.read(study.INPUT/'estimates.json')
        cls.vectors=study.read(study.INPUT/'realizations.json')

    def run_one(self, profile, scenario='queue', seed=201, policy=feedback.POLICY,
                vectors=None, requests=None):
        return engine.simulate(self.estimate,vectors or self.vectors,
            requests or arrivals.workload(scenario,'evaluation'),policy=policy,
            settings=study.settings(policy,self.config,self.frozen),seed=seed,
            thermal_model=study.model(self.config['profiles'][profile],self.config))

    def test_strict_and_missing_costs_are_unsupported(self):
        model=study.model(self.config['profiles'][0],self.config)
        bad=copy.deepcopy(model)
        del bad['predicted']['power_w']['classification:GPU']
        with self.assertRaises(ValueError): feedback.validate(bad)
        strict=study.settings(feedback.POLICY,self.config,self.frozen)
        strict['mode']='strict'
        with self.assertRaises(ValueError):
            engine.simulate(self.estimate,self.vectors,arrivals.workload('low','evaluation'),
                policy=feedback.POLICY,settings=strict,seed=201,thermal_model=model)

    def test_power_and_ap_change_real_dispatch(self):
        cpu=self.run_one(0)
        heat=self.run_one(1)
        power=self.run_one(2)
        self.assertEqual(cpu['decisions'][0]['selected']['backend'],'CPU')
        self.assertEqual(heat['decisions'][0]['selected']['backend'],'GPU')
        self.assertEqual(power['decisions'][0]['selected']['backend'],'GPU')
        self.assertNotEqual(cpu['ledger'][0]['backend'],heat['ledger'][0]['backend'])
        self.assertEqual(cpu['metrics']['planned'],24)

    def test_prediction_and_realization_separate(self):
        a=self.run_one(2);b=self.run_one(3)
        self.assertEqual(a['decisions'][0]['chosen_prediction'],b['decisions'][0]['chosen_prediction'])
        self.assertNotEqual(a['thermal']['energy_j'],b['thermal']['energy_j'])

    def test_future_request_and_actual_duration_not_visible(self):
        base=arrivals.workload('low','evaluation')
        x=self.run_one(0,scenario='low',requests=base)
        future=copy.deepcopy(base)
        future[-1]['arrival_ns']+=10_000_000
        y=self.run_one(0,scenario='low',requests=future)
        self.assertEqual(x['decisions'][0],y['decisions'][0])
        vectors=copy.deepcopy(self.vectors)
        for cell in vectors['cells'].values():
            for v in cell:v['durations_ns']=[int(z*1.1) for z in v['durations_ns']]
        z=self.run_one(0,scenario='low',vectors=vectors)
        self.assertEqual(x['decisions'][0],z['decisions'][0])

    def test_common_window_energy_and_no_early_release(self):
        x=self.run_one(1)
        self.assertEqual(x['thermal']['common_window_s'],120)
        self.assertTrue(math.isclose(x['thermal']['energy_j'],x['thermal']['online_energy_j'],abs_tol=1e-6))
        self.assertTrue(math.isclose(x['thermal']['ap_final_c'],x['thermal']['online_final_ap_c'],abs_tol=1e-6))
        self.assertTrue(all(r['lane_available_ns']>=r['worker_release_ns']>=r['persist_complete_ns']
                            for r in x['ledger'] if r['status']=='succeeded'))
        self.assertTrue(all(r['dispatch_ns']>=r['arrival_ns'] for r in x['ledger'] if 'dispatch_ns' in r))

    def test_ap_crossing_and_idle_decay(self):
        self.assertAlmostEqual(feedback.seconds_above(29,31,10,10,30),
                               10-10*math.log(2),places=6)
        self.assertEqual(feedback.seconds_above(31,29,10,10,32),0)
        x=self.run_one(1,scenario='queue')
        self.assertLess(x['thermal']['online_final_ap_c'],x['thermal']['ap_peak_c'])
        self.assertGreater(x['thermal']['ap_exceed_s'],0)

    def test_legacy_result_unchanged_without_model(self):
        qs=arrivals.workload('low','evaluation')
        settings=study.settings('CPU_URGENT',self.config,self.frozen)
        old=engine.simulate(self.estimate,self.vectors,qs,policy='CPU_URGENT',settings=settings,seed=201)
        with_model=engine.simulate(self.estimate,self.vectors,qs,policy='CPU_URGENT',
            settings=settings,seed=201,thermal_model=study.model(self.config['profiles'][0],self.config))
        self.assertEqual(old['ledger'],with_model['ledger'])
        self.assertEqual(old['metrics'],with_model['metrics'])
        self.assertEqual(old['decisions'],with_model['decisions'])

    def test_bounded_wait_or_fallback_not_infinite(self):
        for index in range(4):
            x=self.run_one(index,scenario='burst')
            self.assertLess(len(x['decisions']),10000)
            self.assertEqual(x['metrics']['planned'],24)
            self.assertEqual(x['metrics']['unfinished']+x['metrics']['not_arrived']+
                             round(x['metrics']['completion']*24),24)

    def test_arrival_during_wait_is_seen_before_timer(self):
        requests=arrivals.workload('low','evaluation')
        future=copy.deepcopy(requests[-1]);future.update(id='test/new',ordinal=24,
            arrival_ns=8_450_000_000,priority='urgent')
        requests.append(future)
        x=self.run_one(1,scenario='low',seed=301,requests=requests)
        self.assertTrue(any(d['reason'].startswith('wait_for_') and
                            d['now_ns']==8_400_000_000 for d in x['decisions']))
        self.assertTrue(any(d['now_ns']==8_450_000_000 and
                            any(q['id']=='test/new' for q in d['queue']) for d in x['decisions']))
        self.assertEqual(next(r for r in x['ledger'] if r['id']=='test/new')['queue_entry_ns'],8_450_000_000)

    def test_preserved_matrix_row_reproduces_after_strict_guard(self):
        with (study.OUTPUT/'metrics.csv').open(encoding='utf-8',newline='') as stream:
            row=next(r for r in csv.DictReader(stream) if r['phase']=='pc_confirmation'
                and r['profile']=='thermal_cap' and r['scenario']=='queue' and r['seed']=='301'
                and r['policy']==feedback.POLICY)
        result=self.run_one(1,scenario='queue',seed=301)
        self.assertAlmostEqual(float(row['energy_120s_j_assumed']),result['thermal']['energy_j'])
        self.assertAlmostEqual(float(row['urgent_p95_ms']),result['metrics']['urgent_p95_ms'])


if __name__=='__main__':unittest.main()
