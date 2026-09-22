"""계획-only 회귀: synthetic fixture이며 latency/시뮬레이션 결과 생성 없음."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import jsonschema

from tools import d1_simulation_plan as p


class SimulationPlanTests(unittest.TestCase):
    def setUp(self):
        self.audit = {'test_fixture': True}
        self.registry = {'sessions': [], 'requests': [], 'traces': []}

    def test_plan_valid_but_not_ready(self):
        plan = p.make_plan(self.audit)
        self.assertTrue(p.validate_plan(plan, self.audit))
        self.assertEqual(p.no_op(plan)['status'], 'SIMULATION_PLAN_INCOMPLETE')

    def test_forged_ready_rejected(self):
        plan = p.make_plan(self.audit)
        plan['status'] = 'SIMULATION_PLAN_READY'
        with self.assertRaises(jsonschema.ValidationError):
            p.validate_plan(plan, self.audit)

    def test_seed_policy_and_null_promotion_rejected(self):
        for field in ('seed', 'policy', 'replications', 'unresolved', 'schema'):
            plan = p.make_plan(self.audit)
            if field == 'seed':
                plan['configuration']['random']['master_seed'] += 1
            elif field == 'policy':
                plan['configuration']['policies'][0]['concurrency'] = 2
            elif field == 'replications':
                plan['configuration']['execution']['replications'] = 100
            elif field == 'unresolved':
                plan['configuration']['unresolved'] = []
            else:
                plan['schema_version'] = 2
            plan['configuration_sha256'] = p.sha(plan['configuration'])
            with self.subTest(field=field), self.assertRaises((ValueError, jsonschema.ValidationError)):
                p.validate_plan(plan, self.audit)

    def test_seed_is_deterministic_separated_and_not_sampled(self):
        before = random.getstate()
        self.assertEqual(p.seed('core', 0, 'joint_pair'), p.seed('core', 0, 'joint_pair'))
        self.assertNotEqual(p.seed('core', 0, 'joint_pair'), p.seed('core', 1, 'joint_pair'))
        self.assertNotEqual(p.seed('core', 0, 'joint_pair'), p.seed('core', 0, 'workload'))
        self.assertEqual(before, random.getstate())
        for args in [('x', -1, 'joint_pair'), ('x', True, 'joint_pair'), ('x', 0, 'SP1/ADAPTIVE')]:
            with self.assertRaises(ValueError):
                p.seed(*args)

    def test_no_op_has_no_writes_random_or_processes(self):
        plan = p.make_plan(self.audit)
        with patch.object(Path, 'write_bytes', side_effect=AssertionError('write')), \
                patch('subprocess.run', side_effect=AssertionError('process')), \
                patch('random.Random', side_effect=AssertionError('random')):
            result = p.no_op(plan)
        for key in ('random_samples', 'dispatches', 'simulated_completions', 'result_files'):
            self.assertEqual(result[key], 0)

    def test_paths_reject_traversal_ads_and_absolute(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'ok.json').write_text('{}')
            self.assertEqual(p.contained(root, 'ok.json'), root/'ok.json')
            for name in ('../ok.json', '/ok.json', 'C:/ok.json', 'ok.json:stream', './/ok.json', 'x\\ok.json'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    p.contained(root, name)

    def test_symlink_rejected_without_platform_privileges(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'ok').write_text('x')
            with patch.object(Path, 'is_symlink', return_value=True), self.assertRaises(ValueError):
                p.contained(Path(tmp), 'ok')

    def test_consumed_and_fingerprint_replay_rejected(self):
        block = {'session_id': 's', 'receipt': {'trace_fingerprint': 'trace', 'samples': [{'request_id': 'r'}]}}
        p.register(block, self.registry)
        for sid, rid, trace in [('s', 'new', 'new'), ('new', 'r', 'new'), ('new', 'new', 'trace')]:
            modified = {'session_id': sid, 'receipt': {'trace_fingerprint': trace, 'samples': [{'request_id': rid}]}}
            with self.assertRaises(ValueError):
                p.register(modified, self.registry)

    def test_ba_pair_keeps_logical_arms_and_actual_time_order(self):
        a = {'manifest': {'paired': {'arm': 'A'}}, 'receipt': {'session_start_ns': 20}}
        b = {'manifest': {'paired': {'arm': 'B'}}, 'receipt': {'session_start_ns': 10}}
        with patch.object(p.telemetry, 'paired', return_value=True) as validate:
            p.validate_pair_blocks([b, a])
            validate.assert_called_once_with(a['manifest'], b['manifest'], [b['receipt'], a['receipt']])
        with self.assertRaises(ValueError):
            p.validate_pair_blocks([a, a])

    def test_schedule_change_rejected_even_if_same_mix(self):
        schedule = [{'task': 'classification', 'priority': 'urgent', 'offset_ms': 0, 'backend': 'CPU'},
                    {'task': 'detection', 'priority': 'normal', 'offset_ms': 0, 'backend': 'GPU'}]
        self.assertTrue(p.require_observed_schedule(schedule, copy.deepcopy(schedule)))
        with self.assertRaises(ValueError):
            p.require_observed_schedule(schedule, schedule[::-1])
        for field, value in [('offset_ms', 1), ('priority', 'normal'), ('backend', 'GPU')]:
            altered = copy.deepcopy(schedule)
            altered[0][field] = value
            with self.assertRaises(ValueError):
                p.require_observed_schedule(schedule, altered)

    def test_duplicate_json_and_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'x.json'
            for text in ('{"a":1,"a":2}', '{"a":NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    p.read(path)

    def test_deterministic_roots_and_noop_file_immutability(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(p, 'audit', return_value=(self.audit, self.registry)):
            root = Path(tmp)
            source = root/'source'
            source.mkdir()
            one, two = root/'one', root/'two'
            a, b = p.generate(source, one), p.generate(source, two)
            self.assertEqual(a, b)
            before = {x.name: x.read_bytes() for x in one.iterdir()}
            self.assertEqual(before, {x.name:x.read_bytes() for x in two.iterdir()})
            p.verify(one, a['freeze_sha256'])
            self.assertEqual(before, {x.name:x.read_bytes() for x in one.iterdir()})
            with self.assertRaises(ValueError):
                p.generate(source, one)

    def test_input_output_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                p.generate(Path(tmp), Path(tmp)/'new')

    def test_wrong_empirical_hash_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source/'simulation_input').mkdir()
            (source/'simulation_input/simulation_input.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'pinned empirical'):
                p.audit(source)

    def test_hash_code_registry_and_extra_result_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(p, 'audit', return_value=(self.audit, self.registry)):
            root = Path(tmp)
            source = root/'source'
            source.mkdir()
            output = root/'out'
            result = p.generate(source, output)
            with self.assertRaises(ValueError):
                p.verify(output, '0'*64)
            with patch.object(p, 'code_hashes', return_value={}), self.assertRaises(ValueError):
                p.verify(output, result['freeze_sha256'])
            frozen = p.read(output/'freeze.json')
            (output/'input_registry.json').write_bytes(p.canonical({'sessions': ['forged']}))
            frozen['files']['input_registry.json'] = p.digest(output/'input_registry.json')
            (output/'freeze.json').write_bytes(p.canonical(frozen))
            with self.assertRaisesRegex(ValueError, 'registry'):
                p.verify(output, p.digest(output/'freeze.json'))
            (output/'result.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'unexpected'):
                p.verify(output, p.digest(output/'freeze.json'))


if __name__ == '__main__':
    unittest.main()
