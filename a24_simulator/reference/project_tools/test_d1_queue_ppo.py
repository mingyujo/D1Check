import copy
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch
from tools import d1_queue_ppo as q


def empty():
    return {b: dict(request=None, phase='AVAILABLE', since=0, dispatch=None) for b in ('CPU', 'GPU')}


class QueuePPOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        q.prev.seed_all(101)
        cls.frozen, case = q.p.inputs(q.p.BUNDLE)
        cls.initial = {k: case['initial'][k] for k in ('preload', 'preload_power_w')}

    def net(self, action):
        q.prev.seed_all(101); network = q.ActorCritic()
        with torch.no_grad():
            network.actor.weight.zero_(); network.actor.bias.fill_(-20); network.actor.bias[action] = 20
        return network

    def tickets(self):
        rows = q.old.workload('queue', 103)[:3]
        for i, row in enumerate(rows):
            row.update(arrival_ns=35_000_000_000, task='classification' if i == 0 else 'detection',
                       priority='urgent' if i == 0 else 'normal', deadline_offset_ns=1_500_000_000 if i == 0 else 6_000_000_000)
        return rows

    def test_real_event_nonhead_selection_and_lane_ownership(self):
        row, result, c, extra = q.simulate(self.frozen, self.initial, self.tickets(), 'mean', 'QUEUE', self.net(2))
        first = next(d['selected'] for d in result['decisions'] if d['selected'])
        self.assertEqual(first['request_id'], self.tickets()[1]['id'])
        self.assertEqual(row['completed'], 3)
        for backend in ('CPU', 'GPU'):
            jobs = sorted((r for r in result['ledger'] if r.get('backend') == backend), key=lambda r: r['dispatch_ns'])
            self.assertTrue(all(a['lane_available_ns'] <= b['dispatch_ns'] for a, b in zip(jobs, jobs[1:])))
        self.assertEqual(len(c.rollout_data[0]['obs']), 85)
        reward = q.rewards(c, result, extra, self.initial, self.frozen)
        self.assertAlmostEqual(float(reward[:, 0].sum())*-10, row['energy_j'], delta=.0001)
        self.assertAlmostEqual(float(reward[:, 3].sum())*100, row['thermal_degree_seconds'], delta=.0001)
        self.assertAlmostEqual(float(reward[:, 4].sum()), row['peak_ap_c'], delta=.00001)

    def test_head_mask_and_wait_aging_guard(self):
        c = q.Controller(self.frozen, self.initial, 'HEAD')
        tickets = self.tickets()
        _, mask, _, _ = c.legal(tickets, empty(), 35.)
        self.assertFalse(mask[2:16].any())
        _, aged, _, _ = c.legal(tickets, empty(), 36.4)
        self.assertFalse(aged[16])
        self.assertTrue(aged[:2].any())
        self.assertFalse(aged[2:16].any())

    def test_forced_eligible_request_beyond_initial_eight(self):
        tickets = [dict(id=str(i), ordinal=i, task='detection', priority='normal', arrival_ns=35e9,
                        deadline_offset_ns=6e9) for i in range(8)]
        urgent = dict(id='urgent9', ordinal=8, task='classification', priority='urgent',
                      arrival_ns=40.2e9, deadline_offset_ns=1.5e9)
        lanes = empty(); lanes['CPU'] = dict(request=copy.deepcopy(tickets[0]), phase='RUNNING', since=41.5e9, dispatch=41.5e9)
        c = q.Controller(self.frozen, self.initial, 'QUEUE')
        candidates, mask, _, reason = c.legal(tickets+[urgent], lanes, 41.6)
        self.assertEqual(candidates[0]['id'], 'urgent9'); self.assertTrue(mask[1])
        self.assertFalse(mask[2:].any()); self.assertEqual(reason, 'forced_aging')

    def test_unknown_overrun_and_unsupported_cell(self):
        c = q.Controller(self.frozen, self.initial, 'QUEUE'); lanes = empty()
        lanes['CPU'] = dict(request=self.tickets()[0], phase='RUNNING', since=35e9, dispatch=35e9)
        _, mask, _, reason = c.legal(self.tickets()[1:], lanes, 36.)
        self.assertFalse(mask.any()); self.assertEqual(reason, 'unknown_overrun_event_wait')
        bad = copy.deepcopy(self.tickets()); bad[0]['priority'] = 'normal'
        with self.assertRaises(ValueError): c.legal(bad, empty(), 35.)

    def test_causal_observation_mask_and_future_rejection(self):
        tickets = self.tickets(); net = self.net(1)
        a = q.Controller(self.frozen, self.initial, 'QUEUE', net)
        b = q.Controller(self.frozen, self.initial, 'QUEUE', net)
        out_a = a({}, tickets, empty(), 35e9, {}, None, None)
        out_b = b({}, copy.deepcopy(tickets), empty(), 35e9, {}, None, None)
        self.assertEqual(out_a, out_b)
        np.testing.assert_equal(a.rollout_data[0]['obs'], b.rollout_data[0]['obs'])
        bad = copy.deepcopy(tickets); bad[0]['arrival_ns'] = 36e9
        with self.assertRaises(ValueError): a.legal(bad, empty(), 35.)
        lanes = empty(); lanes['CPU']['durations'] = [1]
        with self.assertRaises(ValueError): a.legal(tickets, lanes, 35.)

    def test_five_value_optimizer_and_actor_roundtrip(self):
        net = self.net(1)
        _, result, c, extra = q.simulate(self.frozen, self.initial, self.tickets(), 'mean', 'QUEUE', net, False)
        channels = q.rewards(c, result, extra, self.initial, self.frozen)
        stats = q.prev.optimize(net, torch.optim.Adam(net.parameters(), lr=.0003), q.pack([(c, channels)]), [10., 10., 1., 1.])
        self.assertGreater(stats['minibatch_updates'], 0)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'actor.json'; q.save_actor(path, net)
            self.assertEqual(q.prev.model_hash(net), q.prev.model_hash(q.load_actor(path)))

    def test_absolute_service_cost_and_null_failure(self):
        row = dict(urgent_service_failure=1, urgent_n=2, normal_service_failure=0, normal_n=3,
                   energy_j=10., thermal_degree_seconds=5., peak_ap_c=30.)
        self.assertEqual(q.costs(row, row)[0], .5)
        row['peak_ap_c'] = None
        with self.assertRaises(ValueError): q.costs(row, row)

    def test_partial_readout_has_null_gain_and_no_joint_claim(self):
        ref = dict(trace_seed=1, family='queue', context='mean', policy='SHARED_EFT', equal_work=True,
                   urgent_service_failure=0, normal_service_failure=0, energy_j=10., peak_ap_c=30., thermal_degree_seconds=5.)
        candidate = dict(ref, policy='QUEUE', equal_work=False, energy_j=1.)
        with tempfile.TemporaryDirectory() as folder:
            q.report(folder, [ref, candidate])
            with (Path(folder)/'paired_differences.csv').open(encoding='utf8') as stream:
                rows = list(q.csv.DictReader(stream))
            self.assertEqual(rows[1]['delta_energy_j'], '')
            self.assertEqual(rows[1]['joint_model_improvement'], 'False')

    def test_receipt_failure_keeps_original_and_releases_own_lock(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(q, 'LOCK', Path(folder)/'lock.json'):
            r = q.Recorder(Path(folder)/'run', 900); original = dict(type='Original', message='fixture')
            real = q.atomic
            def failing(path, obj):
                if Path(path).name == 'FINAL_RECEIPT.json': raise OSError('fixture disk error')
                return real(path, obj)
            with patch.object(q, 'atomic', failing): r.finish('stopped', original)
            error = json.loads((r.output/'RECEIPT_ERROR.json').read_text())
            self.assertEqual(error['original_error'], original)
            self.assertFalse(q.LOCK.exists())

    def test_duplicate_owner_output_and_budget_block(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(q, 'LOCK', Path(folder)/'lock.json'):
            r = q.Recorder(Path(folder)/'run', 120)
            with self.assertRaises(TimeoutError): r.budget()
            with self.assertRaises(FileExistsError): q.Recorder(Path(folder)/'other', 900)
            with self.assertRaises(FileExistsError): q.Recorder(Path(folder)/'run', 900)
            r.finish('stopped')

    def test_plan_counts_split_and_frozen_files(self):
        plan = q.load_plan(); train, val, test = q.cases(plan)
        self.assertEqual((len(train), len(val), len(test)), (2048, 48, 192))
        self.assertFalse({x[0] for x in train} & {x[0] for x in val})
        self.assertEqual(plan['budget']['formal_simulation_runs_total'], 17936)

    def test_keyboard_cancel_keeps_original_without_formal_restart(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(q, 'LOCK', Path(folder)/'lock.json'):
            with patch.object(q, 'check', return_value={'sources':q.hashes()}), patch.object(q, 'input_manifest', return_value={}), \
                 patch.object(q, 'formal', side_effect=KeyboardInterrupt('fixture cancel')) as formal:
                with self.assertRaises(KeyboardInterrupt): q.run(Path(folder)/'run')
                self.assertEqual(formal.call_count, 1)
            receipt = json.loads((Path(folder)/'run/FINAL_RECEIPT.json').read_text())
            self.assertEqual(receipt['error']['type'], 'KeyboardInterrupt')
            self.assertEqual(receipt['counts']['training'], 0)
            self.assertFalse(q.LOCK.exists())

    def test_actual_powershell_check_no_adb_no_output_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            trap = Path(folder)/'adb.cmd'; marker = Path(folder)/'CALLED'
            trap.write_text('@echo off\necho called > "'+str(marker)+'"\nexit /b 99\n')
            env = dict(q.os.environ, PATH=str(Path(folder))+q.os.pathsep+q.os.environ['PATH'])
            process = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(q.p.ROOT/'tools/RUN_QUEUE_PPO.ps1'),
                '-Action', 'Check', '-Python', q.sys.executable], env=env, capture_output=True, text=True, timeout=90)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn('CHECK_PASSED', process.stdout); self.assertFalse(marker.exists())


if __name__ == '__main__': unittest.main()
