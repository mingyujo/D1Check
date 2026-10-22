"""Readiness/contract checks only; no new environment or NN execution."""
import ast
import shutil
import subprocess
import sys
from pathlib import Path
import study
from study import H, O, R, read, old, verify, new, stamp, RoundRobin, VERSION


def main():
    assert not O.exists() and not (H / 'EXECUTION_AUTHORIZATION.json').exists()
    assert not (H / 'OPERATION.json').exists()
    for p in H.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    subprocess.run(['node', '--check', str(H / 'audit_report.cjs')], check=True)
    op = read(H / 'PROPOSAL.json');verify(op['pins'])
    assert op['planned_START'] == 2 and op['new_training'] == op['new_NN_execution'] == 0
    assert op['code_version'] == VERSION == 'A24_CLASS_RR_CPU3_GPU1_V1'
    assert RoundRobin().capacity == dict(CPU=3, GPU=1)
    cases = []
    for case in old.cases():
        public, contexts, parent = old.public_and_contexts(case)
        assert len(public['requests']) == len(contexts) == case['n']
        assert case['condition']['supply_s'] == 600
        cases.append(dict(case=case['id'], n=case['n']))
    assert [c['n'] for c in cases] == [760, 960]
    for fn in (study.register, study.run):
        try:
            fn()
        except FileNotFoundError:
            pass
        else:
            raise AssertionError('Missing registration was not rejected')
    import psutil
    new(H / 'READINESS.json', dict(status='PASS', utc=stamp(), version=VERSION,
        pins_verified=len(op['pins']), cases=cases, regression_tests=16,
        missing_authorization_fail_closed=True, new_environment=0, new_training=0, new_fit=0,
        new_NN_execution=0, available_disk_bytes=shutil.disk_usage(R).free,
        available_memory_bytes=psutil.virtual_memory().available, python=sys.version,
        HEAD=op['HEAD'], working_tree=op['working_tree']))
    print('RR600_READY', len(op['pins']), 'pins; new scientific units 0')


if __name__ == '__main__':
    main()
