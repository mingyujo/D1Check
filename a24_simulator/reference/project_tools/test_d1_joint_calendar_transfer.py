import copy
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import d1_joint_calendar_transfer as transfer


class FixedCalendarTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prior = transfer.readout.load(transfer.ROOT/'joint_calendar_v1', transfer.ROOT/'joint_calendar_witness_v1')
        cls.detail = prior['details'][0]
        cls.frozen, case = transfer.P.inputs(transfer.P.BUNDLE); cls.initial = case['initial']
        cls.tickets = transfer.readout.study.followup.tickets(cls.detail['reference'])
        cls.jobs = cls.detail['result']['jobs']
        cls.engine_sha = transfer.P.digest(transfer.x.old.engine.__file__)
        cls.planner_sha = transfer.P.digest(transfer.readout.study.solver.original.__file__)

    def controller(self):
        return transfer.NotBeforeReplay(self.frozen, self.initial, self.jobs)

    def test_not_before_and_actual_lane_ownership(self):
        controller = self.controller(); job = self.jobs[0]
        ticket = next(q for q in self.tickets if q['id'] == job['id'])
        now = round(job['start']*1e9)
        lanes = {b: dict(request=None) for b in ('CPU', 'GPU')}
        before = controller(None, [ticket], lanes, now-1, None, None, None)
        self.assertIsNone(before['selected']); self.assertEqual(before['wait_until_ns'], now)
        late = controller(None, [ticket], lanes, now+int(100e6), None, None, None)
        self.assertEqual(late['selected']['request_id'], job['id'])
        self.assertEqual(late['dispatch_lateness_ns'], int(100e6))
        lanes[job['backend']]['request'] = ticket
        self.assertIsNone(controller(None, [ticket], lanes, now+int(100e6), None, None, None)['selected'])

    def test_unsupported_pair_and_future_queue_rejected(self):
        controller = self.controller()
        job = next(j for j in self.jobs if j['state'] == 'classification_CPU')
        ticket = next(q for q in self.tickets if q['id'] == job['id'])
        lanes = dict(CPU=dict(request=None), GPU=dict(request=dict(task='classification')))
        self.assertIsNone(controller(None, [ticket], lanes, round(job['start']*1e9)+1, None, None, None)['selected'])
        future = dict(ticket, arrival_ns=int(200e9))
        with self.assertRaisesRegex(ValueError, 'future queue'):
            controller(None, [future], lanes, int(40e9), None, None, None)

    def test_full_engine_long_context_keeps_real_service_and_fixed_releases(self):
        jobs = copy.deepcopy(self.jobs)
        result = transfer.replay(self.frozen, self.initial, self.tickets, 'long_context', jobs)
        self.assertEqual(result['metrics']['planned'], 48)
        self.assertEqual(result['metrics']['completed'], 48)
        self.assertEqual(jobs, self.jobs)
        self.assertGreaterEqual(result['maximum_dispatch_lateness_ms'], 0.)
        releases = {j['id']: round(j['start']*1e9) for j in jobs}
        profile = transfer.P.profile(self.frozen, 'long_context')
        for q in result['ledger']:
            self.assertGreaterEqual(q['dispatch_ns'], releases[q['id']])
            duration = profile[transfer.P.key(q, q['backend'])]
            fields = ('execution_start_ns', 'output_ready_ns', 'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')
            for i, field in enumerate(fields):
                self.assertLessEqual(abs(q[field]-q['dispatch_ns']-sum(duration[:i+1])), 1.01)

    def test_no_new_context_or_frozen_source_mutation(self):
        with self.assertRaisesRegex(ValueError, 'registered contexts'):
            transfer.replay(self.frozen, self.initial, self.tickets, 'mean', self.jobs)
        self.assertEqual(transfer.P.digest(transfer.x.old.engine.__file__), self.engine_sha)
        self.assertEqual(transfer.P.digest(transfer.readout.study.solver.original.__file__), self.planner_sha)
        self.assertEqual(transfer.P.digest(transfer.P.BUNDLE/'model.json'), transfer.P.MODEL_SHA)
        self.assertEqual(transfer.P.digest(transfer.P.BUNDLE/'initial_inputs.json'), transfer.P.INITIAL_SHA)

    def test_output_reexecution_blocked_before_new_replay(self):
        with TemporaryDirectory() as tmp, patch.object(transfer, 'replay', side_effect=AssertionError('must not run')):
            with self.assertRaises(FileExistsError): transfer.run(tmp)

    def test_original_error_and_partial_evidence_preserved(self):
        first = transfer.replay(self.frozen, self.initial, self.tickets, 'short_context', self.jobs)
        with TemporaryDirectory() as tmp, patch.object(transfer, 'replay', side_effect=[first, RuntimeError('original transfer fixture')]):
            out = Path(tmp)/'failed'
            with self.assertRaisesRegex(RuntimeError, 'original transfer fixture'): transfer.run(out)
            error = json.loads((out/'PC_FAILURE.json').read_text(encoding='utf8'))
            self.assertEqual(error['completed_replays'], 1)
            self.assertIn('RuntimeError: original transfer fixture', error['stack'])
            self.assertEqual(len(gzip.decompress((out/'records.jsonl.gz').read_bytes()).splitlines()), 1)
            self.assertFalse((out/'summary.json').exists())


if __name__ == '__main__': unittest.main()
