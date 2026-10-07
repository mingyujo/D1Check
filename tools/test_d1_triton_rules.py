"""Source-condition examples and original engine boundary checks."""
import copy
import unittest

from tools import d1_triton_rules as r
from tools import d1_triton_study as s


def ticket(name, task='classification', at=35., ordinal=0):
    return dict(id=name, task=task, priority='urgent' if task == 'classification' else 'normal',
                ordinal=ordinal, arrival_ns=round(at * 1e9),
                deadline_offset_ns=1500000000 if task == 'classification' else 6000000000)


def state(cap=1, det_weight=1, enabled=True):
    return r.RateState(dict(enabled=enabled, capacity=cap,
                           weights={'classification': 1, 'detection': det_weight}))


class SourceCases(unittest.TestCase):
    def test_zero_priority_means_one_and_counts_are_execution_counts(self):
        x = state()
        x.executions['detection'] = 3
        x.config['weights']['detection'] = 0
        self.assertEqual(x.priority('detection'), 3)
        x.config['weights']['detection'] = 2
        self.assertEqual(x.priority('detection'), 6)

    def test_submit_allocates_immediately_not_after_collecting_staged_batch(self):
        x = state()
        x.executions['detection'] = 100
        x.submit(ticket('d', 'detection'))
        x.submit(ticket('c'))
        self.assertEqual(x.dispatch[0][1]['id'], 'd')
        self.assertEqual(x.staged[0][1]['id'], 'c')

    def test_capacity_holds_tokens_then_release_rejudges_without_drop(self):
        x = state()
        x.submit(ticket('d', 'detection'))
        x.submit(ticket('c'))
        self.assertEqual(len(x.dispatch), 1)
        x.dispatch.clear()
        x.release('detection', 'd')
        self.assertEqual(x.dispatch[0][1]['id'], 'c')
        self.assertEqual(x.executions, {'classification': 0, 'detection': 1})

    def test_release_own_restage_before_final_attempt_and_tie_first_staged(self):
        x = state()
        x.executions['classification'] = 1
        x.submit(ticket('d1', 'detection'))
        x.submit(ticket('d2', 'detection'))
        x.submit(ticket('c'))
        x.dispatch.clear()
        x.release('detection', 'd1')
        self.assertEqual(x.dispatch[0][1]['id'], 'c')
        self.assertEqual(x.staged[0][1]['id'], 'd2')

    def test_weight_changes_next_choice_in_source_condition(self):
        chosen = []
        for weight in (1, 2):
            x = state(det_weight=weight)
            x.executions['classification'] = 2
            x.submit(ticket('d1', 'detection'))
            x.submit(ticket('c'))
            x.submit(ticket('d2', 'detection'))
            x.dispatch.clear()
            x.release('detection', 'd1')
            chosen.append(x.dispatch[0][1]['id'])
        self.assertEqual(chosen, ['d2', 'c'])

    def test_fifo_specific_requests_and_no_mid_request_preemption(self):
        x = state(cap=2)
        for q in (ticket('c1'), ticket('c2'), ticket('d', 'detection')):
            x.submit(q)
        self.assertEqual([q['id'] for _, q in x.dispatch], ['c1', 'd'])
        self.assertEqual(x.allocated['classification'], 'c1')
        x.dispatch.clear()
        x.release('classification', 'c1')
        self.assertEqual(x.dispatch[0][1]['id'], 'c2')

    def test_off_ignores_configured_token_capacity(self):
        x = state(cap=1, enabled=False)
        x.submit(ticket('c'))
        x.submit(ticket('d', 'detection'))
        self.assertEqual(len(x.dispatch), 2)

    def test_wrong_release_identity_rejected(self):
        x = state()
        x.submit(ticket('c'))
        with self.assertRaisesRegex(ValueError, 'release identity'):
            x.release('classification', 'other')


class EngineCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen, case = r.prior.p.inputs(r.prior.p.BUNDLE)
        cls.initial = {k: copy.deepcopy(case['initial'][k]) for k in ('preload', 'preload_power_w')}

    def simulate(self, tickets, policy, legacy=False):
        s.begin_environment('fixture', test=self.id(), policy=policy)
        return (r.prior.simulate if legacy else r.simulate)(self.frozen, self.initial, tickets, 'mean', policy)

    def test_source_choices_retain_all_requests_respect_capacity_and_all_phases(self):
        tickets = [ticket('d1', 'detection'), ticket('c1', at=35.01, ordinal=1),
                   ticket('c2', at=35.02, ordinal=2), ticket('d2', 'detection', at=35.03, ordinal=3)]
        for policy in list(r.CONFIGS)[:4]:
            result, controller = self.simulate(tickets, policy)
            s.prior.audit(result, tickets)
            self.assertTrue(all(x['status'] == 'succeeded' for x in result['ledger']))
            self.assertEqual(sum(controller.rate.executions.values()), 4)
            by_id = {x['id']: x for x in result['ledger']}
            releases = [x for x in controller.rate.events if x['event'] == 'release']
            self.assertTrue(all(x['at_ns'] >= by_id[x['request_id']]['lane_available_ns'] for x in releases))
            if r.CONFIGS[policy]['capacity'] == 1:
                self.assertTrue(all(x['occupied'] <= 1 for x in controller.rate.events if x['event'] == 'allocate'))
                jobs = sorted(result['ledger'], key=lambda x: x['dispatch_ns'])
                self.assertTrue(all(a['lane_available_ns'] <= b['dispatch_ns'] for a, b in zip(jobs, jobs[1:])))

    def test_future_private_observations_rejected_and_response_does_not_release(self):
        c = r.Controller(self.frozen, self.initial, r.OFF)
        lanes = {b: dict(request=None, phase='AVAILABLE', since=35e9, dispatch=None) for b in ('CPU', 'GPU')}
        with self.assertRaisesRegex(ValueError, 'future ticket'):
            c.validate_public([ticket('future', at=36)], lanes, 35e9)
        q = ticket('c')
        c.rate.submit(q)
        c.rate.dispatch.clear()
        lanes['GPU'] = dict(request=q, phase='OUTPUT_READY', since=35.3e9, dispatch=35e9)
        c.observe(35.3e9, lanes)
        self.assertEqual(c.rate.executions['classification'], 0)
        lanes['GPU']['phase'] = 'WORKER_RELEASED'
        c.observe(35.31e9, lanes)
        self.assertEqual(c.rate.executions['classification'], 0)
        lanes['GPU']['request'] = None
        c.observe(35.32e9, lanes)
        self.assertEqual(c.rate.executions['classification'], 1)
        lanes['CPU']['left'] = 1
        with self.assertRaisesRegex(ValueError, 'private lane'):
            c.validate_public([], lanes, 35.32e9)

    def test_old_fixed_policy_remains_identical_to_rate_off_when_fifo_uncontended(self):
        tickets = [ticket('c'), ticket('d', 'detection', at=36, ordinal=1)]
        a, _ = self.simulate(tickets, r.OFF)
        b, _ = self.simulate(tickets, 'SPLIT_REFERENCE', legacy=True)
        fields = ('id', 'backend', 'dispatch_ns', 'output_ready_ns', 'persist_complete_ns', 'lane_available_ns')
        self.assertEqual([[x[k] for k in fields] for x in a['ledger']],
                         [[x[k] for k in fields] for x in b['ledger']])
        self.assertEqual(a['metrics'], b['metrics'])


if __name__ == '__main__':
    unittest.main()
