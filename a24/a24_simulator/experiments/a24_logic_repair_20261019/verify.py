"""Verify this repair without invoking a producer, engine.run, learner or fit."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    import test_logic as tests
    suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    operation = ROOT / 'a24_simulator/experiments/a24_duration_040_20261019/OPERATION.json'
    pins = json.loads(operation.read_text(encoding='utf-8'))['pins']
    # Read-only relocation of historical pins. Never edit their original paths.
    for pin in pins:
        suffix = pin['path'].replace('\\', '/').split('/a24_simulator/', 1)[1]
        p = ROOT / 'a24_simulator' / suffix
        if sha(p) != pin['sha256'] or p.stat().st_size != pin['bytes']:
            raise ValueError('Frozen source/input changed: ' + suffix)
    baseline = HERE.parent / 'a24_s26_method_20261019'
    spec = importlib.util.spec_from_file_location('_verify_original_forecast', baseline / 'forecast.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    from a24_logic_repair_20261019.forecast import predict
    j = tests.request(due=2000.)
    args = (tests.snapshot([j]), tests.dispatch(), [j], tests.vectors([j], (0, 1000, 0, 0, 0)))
    old_cap = old.predict(*args, tests.UnitPhysics(), dict(service_stop_s=3100.))
    new_cap = predict(*args, tests.UnitPhysics(), dict(service_stop_s=3100.))
    j = tests.request(due=1.)
    args = (tests.snapshot([j]), tests.dispatch(), [j], tests.vectors([j]))
    old_end = old.predict(*args, tests.UnitPhysics(), dict(service_stop_s=1.))
    new_end = predict(*args, tests.UnitPhysics(), dict(service_stop_s=1.))
    sources = list(HERE.glob('*.py'))
    sources += [baseline / name for name in ('engine.py', 'forecast.py', 'policy.py', 'physics.py')]
    sources += [ROOT / 'a24_simulator/experiments/a24_parallel_20261018/physics_parallel.py']
    inputs = [ROOT / 'a24_simulator/results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json',
              HERE.parent / 'a24_parallel_20261018/OPERATION.json', baseline / 'SHAPE.json',
              ROOT / 'a24_simulator/results/A24_DURATION_040_20261019_01/D040_T60_P0_S160.PUBLIC.json',
              HERE.parent / 'a24_duration_040_20261019/banks/D040_T60_P0_S160.BANK.json.gz']
    def evidence(paths):
        return [dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size,
                     sha256=sha(p)) for p in sorted(paths)]
    git = lambda *args: subprocess.check_output(['git', *args], cwd=ROOT, text=True, encoding='utf-8').strip()
    record = dict(schema='A24_LOGIC_REPAIR_VERIFICATION_V1', status='PASS',
                  utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  HEAD=git('rev-parse', 'HEAD'), working_tree=git('status', '--short'),
                  python=sys.version, command=[sys.executable, '-B', '-X', 'utf8',
                      'a24_simulator/experiments/a24_logic_repair_20261019/verify.py', *sys.argv[1:]],
                  tests_run=result.testsRun, frozen_duration_pins_verified=len(pins),
                  frozen_operation_sha256=sha(operation), sources=evidence(sources),
                  inputs=evidence(inputs), new_scientific_environments=0, new_training=0,
                  new_physical_fit=0, new_device_runs=0,
                  regression_examples=dict(
                      capped_original=dict(reported_H_s=old_cap['H_s'], cost=old_cap['cost']),
                      capped_repaired=dict(integrated_H_s=new_cap['H_s'], cost=new_cap['cost']),
                      exact_boundary_original_cost=old_end['cost'],
                      exact_boundary_repaired_cost=new_end['cost']))
    if '--write' in sys.argv:
        (HERE / 'VERIFICATION.json').write_text(json.dumps(record, ensure_ascii=False, indent=2,
                                                          allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=record['status'], tests=result.testsRun,
                         frozen_pins=len(pins), new_scientific_environments=0)))


if __name__ == '__main__':
    main()
