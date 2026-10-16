"""One-shot guarded pure synthetic tests for the saved contract supplement."""
from __future__ import annotations

import argparse
import importlib.util
import io
from pathlib import Path
import sys
import unittest

from runtime_guard import canonical, operation as run_operation, pin, require, sha, write_new

WORK = Path(__file__).resolve().parent
EXPECTED = {
    'runtime_guard.py': 'd2583f2b6d3e92197893bb97736543723dd99c0e924a75a843a2cb3f08b83735',
    'audit_contract_supplement.py': '34372931f42dc19e99aa974d38d9de86f3c2489eb30668cff6691728f62fbba6',
    'test_audit_contract_supplement.py': '96095cb77c67984a4c225d2db1236e4d585e30539e971b56e527a63d88031ad7',
}
EXPECTED_TESTS = 16


def load_exact(spec):
    path = pin(spec)
    require(path.resolve().parent == WORK and path.name in EXPECTED, 'Only the exact local fixture/source whitelist may be imported')
    require(spec['sha256'] == EXPECTED[path.name], 'Fixture/source SHA differs from predeclared whitelist')
    name = path.stem
    require(name not in sys.modules, 'Fresh test process required; fixture/source was already imported')
    loader = importlib.util.spec_from_file_location(name, path)
    require(loader is not None and loader.loader is not None, 'Exact source loader unavailable')
    module = importlib.util.module_from_spec(loader)
    sys.modules[name] = module
    loader.loader.exec_module(module)
    require(Path(module.__file__).resolve() == path.resolve(), 'Imported file identity differs')
    return module


def run_tests(op, out, operation_path):
    require(op.get('mode') == 'CONTRACT_AUDIT_TEST', 'Only new supplement fixture operation allowed')
    require(op.get('expected_test_count') == EXPECTED_TESTS, 'Exact predeclared synthetic fixture count required')
    require(op.get('new_policy_simulations') == op.get('new_fit') == op.get('AP_replay_queries') == op.get('NN') == 0,
            'Only pure synthetic saved-contract fixture work is registered')
    require(len(op['protected_pins']) >= 351, 'Protected351 original union may not be reduced')
    require(Path(op['worker_lock_path']).resolve() == (WORK.parent.parent / 'outputs/A24-INTEGRATED-SIM-20261016-G002/worker.lock').resolve(),
            'Original G002 worker lock required')
    sources = {Path(s['path']).name: s for s in op['source_pins']}
    require(len(sources) == len(op['source_pins']) and set(sources) == {*EXPECTED, Path(__file__).name},
            'Exact four-file source closure required; no original auditor/test discovery')
    for name, expected_sha in EXPECTED.items():
        spec = sources[name]
        require(Path(spec['path']).resolve() == WORK / name and spec['sha256'] == expected_sha, 'Exact source whitelist binding differs')
        pin(spec)
    require(Path(sources[Path(__file__).name]['path']).resolve() == Path(__file__).resolve(), 'Runner exact entry identity')
    require(not op['input_pins'], 'Synthetic test runner accepts no real dataset/raw/model inputs')
    module = load_exact(sources['audit_contract_supplement.py'])
    fixture = load_exact(sources['test_audit_contract_supplement.py'])
    suite = unittest.TestLoader().loadTestsFromModule(fixture)
    require(suite.countTestCases() == EXPECTED_TESTS, 'Loaded fixture count differs from preregistration')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    ok = result.wasSuccessful() and result.testsRun == EXPECTED_TESTS and not result.skipped
    report = {'schema': 'A24-CONTRACT-SUPPLEMENT-TEST-v1', 'status': 'PASS' if ok else 'FAIL',
              'operation_sha256': sha(operation_path), 'testsRun': result.testsRun, 'expected_test_count': EXPECTED_TESTS,
              'failures': [(str(test), error) for test, error in result.failures],
              'errors': [(str(test), error) for test, error in result.errors],
              'skipped': [(str(test), reason) for test, reason in result.skipped], 'output': stream.getvalue(),
              'source_pins': op['source_pins'], 'source_pins_sha256': module.digest(op['source_pins']),
              'new_policy_simulations': 0, 'new_environment': 0, 'new_fit': 0, 'AP_replay_queries': 0,
              'NN': 0, 'HTTP': 0, 'device_commands': 0, 'real_data_files_read': 0,
              'scope': 'Pure synthetic saved schemas/arithmetic only; not real forecast audit or predictive accuracy PASS'}
    write_new(out / 'TEST_RESULT.json', report)
    require(ok, 'Registered supplemental fixture failed; TEST_RESULT retained, automatic retry forbidden')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--operation')
    group.add_argument('--describe', action='store_true')
    args = parser.parse_args()
    if args.describe:
        print(canonical({'mode': 'CONTRACT_AUDIT_TEST', 'expected_test_count': EXPECTED_TESTS,
                         'source_sha256_whitelist': EXPECTED, 'source_pins': [*EXPECTED, Path(__file__).name],
                         'input_pins': [], 'required_zeros': ['new_environment', 'HTTP', 'device_commands', 'new_policy_simulations', 'new_fit', 'AP_replay_queries', 'NN'],
                         'runtime': 'unchanged runtime_guard.operation as run_operation; original G002 lock/process/8GiB/protected351',
                         'outputs': ['START.json', 'TEST_RESULT.json', 'COMPLETE.json or FAILURE.json'], 'automatic_retry': False}))
        return
    with run_operation(args.operation, __file__) as (op, out):
        report = run_tests(op, out, args.operation)
        print(canonical({key: report[key] for key in ('schema', 'status', 'testsRun', 'expected_test_count')}))


if __name__ == '__main__':
    main()
