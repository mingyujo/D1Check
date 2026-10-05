import copy
import json
import unittest
from tools import d1_request_rl as rl
from tools import d1_empirical_request_policy as p
from tools.test_d1_empirical_request_policy import empty


class RequestRLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen, case = p.inputs(p.BUNDLE)
        cls.initial = case['initial']; cls.estimates = p.profile(cls.frozen)
        cls.tickets = rl.workload('queue', 77)

    def run_case(self, tickets=None, table=None, epsilon=0, scenario='mean'):
        return rl.simulate(self.frozen, self.initial, tickets or self.tickets, scenario,
                           p.RL_POLICY, {} if table is None else table, epsilon, 12)

    def test_contract_and_split(self):
        spec = rl.specification()
        self.assertEqual(json.loads(rl.CONTRACT.read_text(encoding='utf8')), spec)
        self.assertFalse(set(spec['train_seeds']) & set(spec['evaluation_seeds']))
        self.assertEqual(len(spec['train_seeds'])*4*3, spec['train_episodes'])
        self.assertEqual(len(spec['evaluation_seeds'])*4*3*5, spec['evaluation_runs'])

    def test_generator_deterministic_bounded_and_different(self):
        for family in rl.FAMILIES:
            a = rl.workload(family, 1001); b = rl.workload(family, 2001)
            self.assertEqual(a, rl.workload(family, 1001)); self.assertNotEqual(a, b)
            self.assertEqual(len(a), 192 if family=='sustained' else 24)
            self.assertTrue(all(35e9 <= q['arrival_ns'] < 120e9 for q in a))
            self.assertEqual(sum(q['priority']=='urgent' for q in a), 96 if family=='sustained' else 6)
            self.assertEqual(sorted(q['arrival_ns'] for q in a), [q['arrival_ns'] for q in a])

    def test_first_visit_update_exact_no_duplicate_credit(self):
        table = {}; trajectory = [('s','CPU'), ('s','CPU'), ('t','WAIT')]
        rl.update_table(table, trajectory, [1,2,3,4])
        rl.update_table(table, trajectory, [3,4,5,6])
        self.assertEqual(table['s']['CPU'], dict(n=2, mean=[2.,3.,4.,5.]))

    def test_empty_table_actual_entry_equals_eft(self):
        _, result, _ = self.run_case()
        _, reference, _ = rl.simulate(self.frozen, self.initial, self.tickets, 'mean','EFT_REFERENCE',seed=12)
        self.assertEqual(result['ledger'], reference['ledger'])

    def test_training_reproducible_changes_table_and_uses_wait(self):
        a, ra, ca = self.run_case(epsilon=1)
        b, rb, cb = self.run_case(epsilon=1)
        self.assertEqual(ra, rb); self.assertTrue(ca.trajectory)
        self.assertTrue(any(action=='WAIT' for _,action in ca.trajectory))
        table = {}; rl.update_table(table, ca.trajectory, rl.terminal_cost(a,a))
        self.assertTrue(table); self.assertEqual(ca.trajectory, cb.trajectory)

    def test_frozen_evaluation_read_only_and_learned_action_executed(self):
        row, _, c = self.run_case(epsilon=1)
        table = {}; rl.update_table(table,c.trajectory,rl.terminal_cost(row,row))
        before = copy.deepcopy(table)
        result, _, _ = self.run_case(table=table)
        self.assertEqual(table,before); self.assertGreater(result['learned_decisions'],0)

    def test_lexicographic_cost_no_energy_trade_for_misses(self):
        self.assertLess((0,10,100,10000),(.01,0,-100,1))
        self.assertLess((0,0,100,10000),(0,.01,-100,1))
        r = dict(planned=24, deadline_misses=1, peak_ap_35_180_c=None,energy_120s_j=1,urgent_p95_ms=None)
        c = rl.terminal_cost(r,r)
        self.assertEqual(c[0],1/24); self.assertEqual(c[1],1000)
        self.assertIsNone(r['peak_ap_35_180_c'])

    def test_future_arrival_does_not_change_decision_prefix(self):
        a = self.tickets; b = copy.deepcopy(a); b[-1]['arrival_ns'] += 4e9
        _, ra, _ = self.run_case(a,epsilon=1); _, rb, _ = self.run_case(b,epsilon=1)
        cutoff = a[-1]['arrival_ns']
        self.assertEqual([d for d in ra['decisions'] if d['now_ns']<cutoff],
                         [d for d in rb['decisions'] if d['now_ns']<cutoff])

    def test_private_fields_and_future_queue_rejected(self):
        c = rl.Learner(self.frozen,self.initial,self.estimates,{})
        settings = rl.batch.defaults('explore'); lanes = empty(); config = {}
        with self.assertRaises(ValueError): c(config,[self.tickets[0]],lanes,34e9,settings,None,None)
        lanes['CPU']['future_duration'] = 1
        with self.assertRaises(ValueError): c(config,[self.tickets[0]],lanes,35e9,settings,None,None)

    def test_real_entry_ownership_wait_bounds_and_completion_denominator(self):
        row, result, _ = self.run_case(epsilon=1, scenario='long_context')
        self.assertEqual(row['planned'],24); self.assertEqual(len(result['ledger']),24)
        original = {r['id']:r for r in self.tickets}
        for d in result['decisions']:
            if d.get('rl_action')=='WAIT':
                self.assertLessEqual(d['chosen_explicit_delay_s'],.25)
                self.assertLessEqual(d['wait_until_ns']-original[d['head_request_id']]['arrival_ns'],2e9+1)
        for backend in ('CPU','GPU'):
            jobs = sorted((r for r in result['ledger'] if r.get('backend')==backend), key=lambda r:r['dispatch_ns'])
            self.assertTrue(all(a['lane_available_ns']<=b['dispatch_ns'] for a,b in zip(jobs,jobs[1:])))
        self.assertEqual([r['arrival_ns'] for r in result['ledger']], [r['arrival_ns'] for r in self.tickets])
        self.assertEqual(row['deadline_misses']+row['deadline_met'],24)
        self.assertEqual(p.digest(p.BUNDLE/'model.json'),p.MODEL_SHA)


if __name__=='__main__': unittest.main()
