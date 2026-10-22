"""Readiness on stored inputs; no policy workload evaluation or NN execution."""
import ast
import shutil
import subprocess
import sys
from study import H, O, R, A, old, read, new, stamp, verify, cases, public_and_contexts, bankfile_for, B, C, Policy


def main():
    assert not O.exists() and not (H / 'OPERATION.json').exists()
    for p in H.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    for name in ('audit_report.cjs', 'audit_lsf_helpers.cjs'):
        subprocess.run(['node', '--check', str(H / name)], check=True)
    proposal = read(H / 'PROPOSAL.json'); verify(proposal['pins'])
    assert proposal['planned_START'] == 18 and proposal['budget']['derived_total'] == 137759
    assert 'Ran 21 tests' in (H / 'TESTS_V3.log').read_text(encoding='utf-8')
    assert 'Ran 2 tests' in (H / 'DROP_TESTS.log').read_text(encoding='utf-8')
    for name in ('TESTS_V3.log', 'DROP_TESTS.log'):
        assert '\nOK' in (H / name).read_text(encoding='utf-8')
    helper = read(H / 'AUDIT_HELPER_TESTS.log')
    assert helper['status'] == 'PASS' and helper['synthetic_states'] == 21 and helper['checks'] == 589
    manifest = read(H / 'SOURCE_MANIFEST.json'); verify(manifest['files'])
    assert manifest['full_Band_reproduction'] is False and len(manifest['files']) == 9
    registered = []
    for case in cases():
        public, contexts, parent = public_and_contexts(case)
        assert len(public['requests']) == len(contexts) == case['n']
        bank = read(bankfile_for(case))
        nominal = B.SavedNominal(public, [dict(nominal_vectors=bank['nominal_vectors'])])
        physics = C.Physics(read(A / 'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),
                            B.Config(**parent['physics']), 'ORIGINAL', read(old.PORT / 'SHAPE.json'))
        for request in (public['requests'][0], public['requests'][-1]):
            for route in ('CPU', 'GPU'):
                assert len(nominal.vector(request, route, {})) == 5
        registered.append(dict(case=case['id'], n=case['n'], load=case['condition']['rate_multiplier'], bank=str(bankfile_for(case))))
    assert [c['n'] for c in registered] == [760,960,1520,1920,2280,2880]
    import psutil
    new(H / 'READINESS.json', dict(status='PASS', utc=stamp(), pins_verified=len(proposal['pins']),
        decision_contract_tests=21, synthetic_drop_contract_tests=2, cases=registered,
        full_Band_runtime=False, new_environment=0, new_NN_execution=0, new_training=0,
        new_fit=0, available_disk_bytes=shutil.disk_usage(R).free,
        available_memory_bytes=psutil.virtual_memory().available, python=sys.version, HEAD=proposal['HEAD']))
    print('LSF_BAND_READY', len(proposal['pins']), 'pins; 23 contracts; six exact inputs; START0')


if __name__ == '__main__':
    main()
