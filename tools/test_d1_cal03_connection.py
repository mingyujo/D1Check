"""Synthetic PC timing risks; these are not GPU/device or predictive tests."""
import unittest

from tools import d1_arrival_timing_dev as old
from tools import d1_cal03_connection as c
from tools import d1_cal03_simulator as sim


def fixture():
    cells, vectors = {}, {}
    for key in c.CELLS:
        priority = key.rsplit('_', 1)[1]
        # A->S=10, S->O=20, O->P=30, P->W=4, W->L=6.
        phases = {f: dict(c.stats([v] * 4), response_use=c.calibration.usage(priority, f, 'response'),
                         lane_use=c.calibration.usage(priority, f, 'lane_from_dispatch'))
                  for f, v in zip(old.ALL_FIELDS, (7, 10, 20, 30, 10))}
        cells[key] = dict(observed_phases=phases, adaptive_decision_to_dispatch_ns=None,
            joint={k: c.stats([v] * 4) for k, v in zip(c.JOINTS, (30 if priority == 'urgent' else 60, 70, 60, 40, 10))})
        vectors[key] = [dict(source_request_id=f'{key}-{i}', durations_ns=[10, 20, 30, 4, 6]) for i in range(4)]
    return (dict(protocol=c.VERSION, policy=c.POLICY, experiment_ready=False,
                 scope=dict(maximum_concurrency=1, unit='ns'), cells=cells),
            dict(protocol=c.VERSION, cells=vectors))


def ticket(rid='a', arrival=0, priority='urgent', ordinal=0):
    return dict(id=rid, task='classification', priority=priority, ordinal=ordinal, arrival_ns=arrival)


def request(*args, **kwargs):
    return dict(ticket(*args, **kwargs), deadline_offset_ns=1000)


class ConnectionTest(unittest.TestCase):
    def setUp(self):
        self.config, self.vectors = fixture()
        self.lanes = {b: c.available() for b in ('CPU', 'GPU')}

    def busy(self, phase='EXECUTING', since=10, persist=None):
        self.lanes['CPU'] = dict(phase=phase, phase_since_ns=since, persist_since_ns=persist,
                                task='classification', priority='urgent', request_id='running')

    def test_joint_median_not_sum_of_medians(self):
        # Use an asymmetric pairing for a concrete non-additive median.
        a, b = [0, 1, 2, 100], [100, 1, 0, 2]
        self.assertNotEqual(c.stats([x+y for x, y in zip(a, b)])['median_ns'],
                            c.stats(a)['median_ns'] + c.stats(b)['median_ns'])
        self.config['cells']['classification_CPU_urgent']['joint']['dispatch_to_response_ns'] = c.stats([31]*4)
        d = c.decide(self.config, [ticket()], self.lanes, 0)
        self.assertEqual(d['candidates'][0]['predictions']['CPU']['dispatch_to_response_ns'], 31)

    def test_priority_response_boundary_and_missing_vs_na(self):
        a = c.decide(self.config, [ticket()], self.lanes, 0)
        b = c.decide(self.config, [ticket(priority='normal')], self.lanes, 0)
        self.assertEqual(a['candidates'][0]['predictions']['CPU']['dispatch_to_response_ns'], 30)
        self.assertEqual(b['candidates'][0]['predictions']['CPU']['dispatch_to_response_ns'], 60)
        self.assertIsNone(a['candidates'][0]['predictions']['CPU']['decision_to_response_ns'])
        p = self.config['cells']['classification_CPU_urgent']['observed_phases']['output_ready_to_persist_ns']
        self.assertEqual((p['response_use'], p['lane_use'], p['median_ns']), ('not_applicable', 'applicable', 30))

    def test_dispatch_delay_overrun_does_not_free_lane(self):
        self.busy('ASSIGNED', 0)
        d = c.decide(self.config, [ticket()], self.lanes, 11)
        self.assertEqual(d['residuals']['CPU']['state'], 'UNKNOWN_OVERRUN')
        self.assertIsNone(d['selected'])
        self.assertEqual(self.lanes['CPU']['phase'], 'ASSIGNED')

    def test_service_overrun_no_zero_or_invented_residual(self):
        self.busy()
        d = c.decide(self.config, [ticket()], self.lanes, 30)
        self.assertEqual(d['residuals']['CPU'], dict(ns=None, state='UNKNOWN_OVERRUN'))
        self.assertIsNone(d['selected'])

    def test_remaining_joint_no_second_dispatch_cost(self):
        self.busy()
        self.assertEqual(c.remaining(self.config, 'CPU', self.lanes['CPU'], 15)['ns'], 55)

    def test_output_and_worker_release_are_still_busy(self):
        self.busy('OUTPUT_READY', 30)
        self.assertIsNone(c.decide(self.config, [ticket()], self.lanes, 31)['selected'])
        self.busy('WORKER_RELEASED', 64, 60)
        self.assertEqual(c.remaining(self.config, 'CPU', self.lanes['CPU'], 65)['ns'], 5)
        self.assertIsNone(c.decide(self.config, [ticket()], self.lanes, 65)['selected'])
        self.lanes['CPU'] = c.available(70)
        self.assertIsNotNone(c.decide(self.config, [ticket()], self.lanes, 70)['selected'])

    def test_both_busy_and_empty_decisions_recorded(self):
        self.busy()
        self.lanes['GPU'] = dict(self.lanes['CPU'], request_id='gpu')
        self.assertIsNone(c.decide(self.config, [ticket()], self.lanes, 11)['selected'])
        self.assertEqual(c.decide(self.config, [], self.lanes, 11)['reason'], 'wait_empty')

    def test_causal_schema_rejects_future_outcomes_and_arrivals(self):
        for q in [[dict(ticket(), actual_finish_ns=100)], [ticket(arrival=10)]]:
            with self.assertRaises(ValueError): c.decide(self.config, q, self.lanes, 0)
        self.lanes['CPU']['future_release_ns'] = 100
        with self.assertRaises(ValueError): c.decide(self.config, [ticket()], self.lanes, 0)

    def test_decision_snapshot_replay(self):
        d = c.decide(self.config, [ticket('later', 0, 'normal', 0), ticket('urgent', 0, 'urgent', 1)], self.lanes, 0)
        self.assertEqual(d, c.decide(self.config, d['queue'], d['lanes'], d['now_ns']))
        self.assertEqual(d['selected']['request_id'], 'urgent')

    def test_unknown_cost_fallback_vs_explicit_assumption_ranking(self):
        self.config['cells']['classification_GPU_urgent']['joint']['dispatch_to_response_ns'] = c.stats([5]*4)
        strict = c.decide(self.config, [ticket()], self.lanes, 0)
        assumed = c.decide(self.config, [ticket()], self.lanes, 0, assumed_common_decision_ns=3)
        self.assertEqual(strict['selected']['backend'], 'CPU')
        self.assertEqual(assumed['selected']['backend'], 'GPU')
        self.assertFalse(assumed['experiment_ready'])

    def test_old_policy_null_contract_stays_unchanged(self):
        budgets = {key: {f: None for f in old.ALL_FIELDS} for key in old.KEYS}
        lanes = {b: dict(phase='AVAILABLE', request_id=None, task=None, phase_since_ns=0, persist_since_ns=None) for b in ('CPU', 'GPU')}
        decision = old.replay([{k: v for k, v in ticket().items() if k != 'arrival_ns'}], lanes, 0, budgets)
        self.assertEqual(decision['reason'], 'fallback_cpu_unknown')
        self.assertTrue(all(v is None for b in budgets.values() for v in b.values()))


class EngineTest(unittest.TestCase):
    def setUp(self): self.config, self.vectors = fixture()

    def run_model(self, requests, **kwargs):
        return sim.simulate(self.config, self.vectors, requests, decision_cost_ns=kwargs.pop('decision_cost_ns', 5),
                            horizon_ns=kwargs.pop('horizon_ns', 1000), **kwargs)

    def test_delay_service_reply_and_release_distinct(self):
        r = self.run_model([request()])['ledger'][0]
        self.assertEqual([r[k] for k in ('decision_ns', 'dispatch_ns', 'execution_start_ns', 'output_ready_ns',
            'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')], [0, 5, 15, 35, 65, 69, 75])
        self.assertEqual((r['response_ns'], r['service_ns'], r['dispatch_to_start_ns']), (35, 20, 10))

    def test_arrival_independent_of_completion_and_tie_release(self):
        out = self.run_model([request(), request('b', 20, 'normal', 1), request('c', 75, 'urgent', 2)])
        rows = {r['id']: r for r in out['ledger']}
        self.assertEqual(rows['b']['actual_arrival_ns'], 20)
        self.assertEqual(rows['c']['dispatch_ns'], 80)
        self.assertGreater(rows['b']['dispatch_ns'], rows['c']['lane_available_ns'])
        self.assertTrue(out['complete_drain'])
        self.assertEqual(rows['b']['completion_ns'], rows['b']['persist_complete_ns'])

    def test_arrivals_during_decision_are_not_hidden_or_delayed(self):
        out = self.run_model([request(), request('b', 3, ordinal=1)], decision_cost_ns=5)
        self.assertEqual(out['ledger'][1]['actual_arrival_ns'], 3)
        self.assertEqual(out['ledger'][0]['dispatch_ns'], 5)

    def test_outcome_changes_do_not_leak_into_initial_choice(self):
        first = self.run_model([request()], assumption_ranking=True)
        self.vectors['cells']['classification_CPU_urgent'][0]['durations_ns'][1] = 200
        second = self.run_model([request()], assumption_ranking=True)
        for d in (first['decisions'][0], second['decisions'][0]): d.pop('pc_compute_ns')
        self.assertEqual(first['decisions'][0], second['decisions'][0])
        self.assertNotEqual(first['ledger'][0]['response_ns'], second['ledger'][0]['response_ns'])

    def test_overrun_while_busy_and_callback_release(self):
        self.vectors['cells']['classification_CPU_urgent'][0]['durations_ns'][1] = 100
        out = self.run_model([request(), request('b', 50, ordinal=1)])
        at50 = next(d for d in out['decisions'] if d['now_ns'] == 50)
        self.assertIsNone(at50['selected'])
        self.assertEqual(at50['residuals']['CPU']['state'], 'UNKNOWN_OVERRUN')
        self.assertGreaterEqual(out['ledger'][1]['dispatch_ns'], out['ledger'][0]['lane_available_ns'])

    def test_horizon_keeps_all_denominators_and_partial_success(self):
        out = self.run_model([request(), request('b', 1, ordinal=1), request('c', 1000, ordinal=2)], horizon_ns=40)
        self.assertEqual((out['denominator_planned'], out['denominator_arrived']), (3, 2))
        self.assertEqual(out['response_ready_count'], 1)
        self.assertEqual(out['terminal_counts'], dict(succeeded=0, unfinished_at_horizon=2, not_arrived=1))
        self.assertIsNone(out['makespan_arrival_to_lane_ns'])

    def test_unmeasured_overlap_and_missing_cost_rejected(self):
        with self.assertRaises(ValueError): self.run_model([request()], maximum_concurrency=2)
        with self.assertRaises(ValueError): self.run_model([request()], decision_cost_ns=None)

    def test_priority_vectors_are_not_task_aliases(self):
        self.vectors['cells']['classification_CPU_normal'][0]['durations_ns'][2] = 100
        out = self.run_model([request(priority='normal')])
        self.assertEqual(out['ledger'][0]['response_ns'], 135)

    def test_zero_cost_is_labeled_assumption_not_missing_measurement(self):
        out = self.run_model([request()], decision_cost_ns=0)
        self.assertEqual(out['assumptions']['decision_cost_ns'], 0)
        self.assertIn('unmeasured', out['assumptions']['decision_cost_role'])
        self.assertIsNone(out['decisions'][0]['candidates'][0]['predictions']['CPU']['decision_to_response_ns'])

    def test_measured_config_cannot_be_promoted_or_missing_cost_filled(self):
        self.config['experiment_ready'] = True
        with self.assertRaises(ValueError): self.run_model([request()])
        self.config['experiment_ready'] = False
        self.config['cells']['classification_CPU_urgent']['adaptive_decision_to_dispatch_ns'] = 0
        with self.assertRaises(ValueError): self.run_model([request()])


if __name__ == '__main__': unittest.main()
