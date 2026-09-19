import copy
import tempfile
import unittest
import uuid
from pathlib import Path
from tools import d1_sim_prepare as sim


def draft():
    tasks = [dict(task_id=t, model_id=t+'-model', model_sha256='a'*64,
                  preprocessing_id=t+'-v1', adapter_status='pending') for t in ('classification', 'detection')]
    return dict(protocol='sim-input-preparation-v1', schema_version=1, plan_revision='4.4', device_id='fixture',
        tasks=tasks, capabilities=[dict(task_id=t['task_id'], backend=b, status='unverified', evidence_sha256=None)
             for t in tasks for b in ('CPU', 'GPU')],
        workloads=[dict(workload_id='W-burst', arrival_source='synthetic_assumption', mix=[
            dict(task_id=t['task_id'], priority=p, fraction=.25) for t in tasks for p in ('urgent', 'normal')])],
        seed=dict(contract='d1-seed-sha256-v1', master_seed=0, repetitions_state='thresholds_pending'),
        deadline=dict(state='calibration_pending', values_ns=None),
        constraints=dict(state='thresholds_pending', max_in_flight=1, allowed_corun=[]),
        policies=sim.POLICIES.copy(), evidence={gate:None for gate in sim.REQUIRED_EVIDENCE})


class PreparationTest(unittest.TestCase):
    def test_noop_is_deterministic_and_never_dispatches_or_promotes(self):
        with tempfile.TemporaryDirectory() as root:
            first = sim.noop(draft(), root)
            self.assertEqual(first, sim.noop(draft(), root))
            self.assertEqual('SIM-01_INCOMPLETE', first['status'])
            self.assertEqual(0, first['dispatch_count'])
            self.assertEqual(0, first['simulated_completion_count'])
            self.assertEqual([], list(Path(root).iterdir()))

    def test_unvalidated_numbers_missing_cells_and_drift_rejected(self):
        mutations = [lambda v: v['capabilities'].pop(), lambda v: v['tasks'].pop(),
            lambda v: v['deadline'].update(values_ns=100000000),
            lambda v: v['constraints'].update(max_in_flight=2),
            lambda v: v['workloads'][0]['mix'][0].update(fraction=float('nan')),
            lambda v: v['policies'].update({'4.4/B2':'oracle'}), lambda v: v.update(unexpected=True)]
        with tempfile.TemporaryDirectory() as root:
            for mutate in mutations:
                with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                    value=draft(); mutate(value); sim.noop(value, root)

    def test_evidence_hash_and_path_must_be_valid(self):
        with tempfile.TemporaryDirectory() as root:
            for path in ('../escape', '/absolute', 'missing.json'):
                value=draft()
                value['evidence']['quality']=dict(path=path, sha256='a'*64, status='verified')
                with self.assertRaises(ValueError):
                    sim.noop(value, root)

    def test_seed_namespaces_and_types(self):
        seeds={sim.derive_seed(0,p,'arrival',b) for p in ('calibration','development','evaluation') for b in range(5)}
        self.assertEqual(15,len(seeds))
        self.assertEqual(sim.derive_seed(0,'development','arrival',0),sim.derive_seed(0,'development','arrival',0))
        for bad in (True,-1,2**64):
            with self.assertRaises(ValueError):
                sim.derive_seed(bad,'development','arrival',0)


class KpiTest(unittest.TestCase):
    def pair(self, priority='urgent'):
        identity=str(uuid.uuid4())
        arrival=dict(request_id=identity, task_id='classification', priority=priority, arrival_ns=0, deadline_ns=10)
        row=dict(request_id=identity,status='succeeded',requested_backend='CPU',actual_backend='CPU',enqueue_ns=1,
            execution_start_ns=2,execution_finish_ns=8,output_ready_ns=9,persist_complete_ns=12 if priority=='normal' else None,terminal_ns=13)
        return arrival,row

    def test_late_persistence_and_failed_denominator(self):
        a,r=self.pair('normal')
        b,s=self.pair('normal')
        s.update(status='failed',actual_backend=None,execution_start_ns=None,execution_finish_ns=None,
                 output_ready_ns=None,persist_complete_ns=None)
        result=sim.request_kpis([a,b],[r,s])['normal']
        self.assertEqual(1,result['late'])
        self.assertEqual(.5,result['service_success_rate'])
        self.assertEqual(0,result['on_time_service_rate'])
        self.assertEqual(12,result['completed_response_p95_ns'])

    def test_pending_deadline_has_no_on_time_rate(self):
        a,r=self.pair();a['deadline_ns']=None
        self.assertIsNone(sim.request_kpis([a],[r])['urgent']['on_time_service_rate'])

    def test_missing_duplicate_and_fallback_rejected(self):
        a,r=self.pair()
        for rows in ([],[r,r],[dict(r,actual_backend='GPU')],[dict(r,execution_finish_ns=0)]):
            with self.assertRaises(ValueError):
                sim.request_kpis([a],rows)

    def test_all_failure_outcomes_remain_distinct(self):
        arrivals=[];terminals=[]
        for status in ('failed','rejected','expired','cancelled','unfinished'):
            a,r=self.pair();r.update(status=status,actual_backend=None,enqueue_ns=None,execution_start_ns=None,
                execution_finish_ns=None,output_ready_ns=None,persist_complete_ns=None)
            arrivals.append(a);terminals.append(r)
        group=sim.request_kpis(arrivals,terminals)['urgent']
        self.assertEqual(0,group['service_success_rate'])
        self.assertIsNone(group['completed_response_p95_ns'])
        for status in ('failed','rejected','expired','cancelled','unfinished'):
            self.assertEqual(1,group[status])
