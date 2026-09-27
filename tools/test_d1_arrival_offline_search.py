"""Small, deterministic checks of the offline action set and engine replay."""
import unittest

from tools import d1_arrival_explore_batch as arrivals
from tools import d1_arrival_explore as engine
from tools import d1_arrival_thermal_feedback as feedback
from tools import d1_arrival_thermal_feedback_batch as frozen
from tools import d1_arrival_offline_search as offline


class OfflineSearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study=frozen.read(frozen.CONFIG)
        cls.freeze=frozen.verify(cls.study)
        cls.config=frozen.read(frozen.INPUT/'estimates.json')
        cls.vectors=frozen.read(frozen.INPUT/'realizations.json')
        cls.settings=frozen.settings(feedback.POLICY,cls.study,cls.freeze)
        cls.model=frozen.model(cls.study['profiles'][0],cls.study)

    def run_script(self, requests, prefix):
        return offline.replay(self.config,self.vectors,requests,self.settings,self.model,301,
                              prefix,250_000_000,500_000_000)

    def test_one_ticket_complete_enumeration_finds_manual_energy_minimum(self):
        request=arrivals.workload('low','evaluation')[:1]
        found=offline.search_case(self.config,self.vectors,request,self.settings,self.model,301,
            step_ns=250_000_000,max_wait_ns=0,max_nodes=100,wall_seconds=10)
        self.assertEqual(found['status'],'complete')
        self.assertEqual({p for p,_ in found['leaves']},{('CPU',),('GPU',)})
        manual=[self.run_script(request,(b,))['thermal']['energy_j'] for b in ('CPU','GPU')]
        self.assertAlmostEqual(min(x['thermal']['energy_j'] for _,x in found['leaves']),min(manual))

    def test_wait_arrival_and_actual_lane_release(self):
        request=arrivals.workload('burst','evaluation')[:3]
        result=self.run_script(request,('WAIT','GPU','CPU','GPU'))
        self.assertEqual(len(result['ledger']),3)
        self.assertTrue(any(d['reason']=='offline_discrete_wait' for d in result['decisions']))
        for row in result['ledger']:
            self.assertGreaterEqual(row['dispatch_ns'],row['arrival_ns'])
            self.assertGreaterEqual(row['lane_available_ns'],row['worker_release_ns'])
            self.assertGreaterEqual(row['worker_release_ns'],row['persist_complete_ns'])
        path=offline.thermal_path('toy','offline',result,self.model)
        self.assertAlmostEqual(float(path[-1]['cumulative_energy_j']),result['thermal']['energy_j'])
        self.assertAlmostEqual(float(path[-1]['ap_c']),result['thermal']['ap_final_c'])

    def test_budget_exhaustion_and_response_denominator(self):
        request=arrivals.workload('queue','evaluation')[:3]
        found=offline.search_case(self.config,self.vectors,request,self.settings,self.model,301,
            step_ns=250_000_000,max_wait_ns=500_000_000,max_nodes=1,wall_seconds=10)
        self.assertEqual(found['status'],'budget_exhausted')
        self.assertEqual(found['leaves'],[])
        complete=offline.search_case(self.config,self.vectors,request,self.settings,self.model,301,
            step_ns=250_000_000,max_wait_ns=500_000_000,max_nodes=1000,wall_seconds=10)['leaves'][0][1]
        item=offline.summary(complete)
        self.assertEqual(item['planned'],3)
        self.assertEqual(item['urgent_n']+item['normal_n'],3)
        no_response=dict(item,response_by_id={k:float('inf') for k in item['response_by_id']},unfinished=3)
        self.assertFalse(offline.feasible(no_response,item,500,dict(response_ms=1e-6)))

    def test_numeric_tolerance_does_not_erase_real_tradeoff(self):
        tol=dict(response_ms=1e-6,energy_j=1e-6,ap_c=1e-6)
        a=dict(unfinished=0,urgent_miss=0,normal_miss=0,energy_j=120.,ap_peak_c=30.,ap_exceed_s=0.,
               response_by_id={'u':100.})
        tiny=dict(a,energy_j=120.-5e-7)
        tradeoff=dict(a,energy_j=119.,response_by_id={'u':101.})
        self.assertFalse(offline.improvements(tiny,a,tol)['energy'])
        self.assertFalse(offline.dominates(tradeoff,a,tol))
        self.assertFalse(offline.dominates(a,tradeoff,tol))
        self.assertTrue(offline.feasible(tradeoff,a,1.,tol))

    def test_offline_hook_cannot_relabel_existing_policy(self):
        with self.assertRaisesRegex(ValueError,'isolated'):
            engine.simulate(self.config,self.vectors,arrivals.workload('low','evaluation')[:1],
                policy='CPU_URGENT',settings=frozen.settings('CPU_URGENT',self.study,self.freeze),
                seed=301,thermal_model=self.model,decision_provider=offline.Script((),250_000_000,500_000_000))


if __name__=='__main__':
    unittest.main()
