"""Seal saved-only verification and current source; never run a simulation."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

H = Path(__file__).resolve().parent
R = H.parents[2]
O = R / 'a24_simulator/results/A24_IDLE_WAIT_REPAIR_20261019_01'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def pin(p):
    with p.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    return dict(path=p.relative_to(R).as_posix(), bytes=p.stat().st_size, sha256=digest)


def verify(pins):
    for p in pins:
        assert pin(R / p['path']) == p, p['path']


def main():
    assert not (O / 'VERIFICATION.json').exists()
    review = read(O / 'SAVED_STATE_REVIEW.json')
    assert review['status'] == 'PASS' and review['counts']['frames'] == 3781
    assert review['new_environment'] == review['new_training'] == review['new_fit'] == 0
    verify(review['repair_sources']);verify(review['sources'])
    op = read(R / 'a24_simulator/experiments/a24_atc_bc_20261019/OPERATION.json')
    verify(op['pins'])
    assert read(O / 'MASK_AUDIT.json')['status'] == read(O / 'NN_AUDIT.json')['status'] == 'PASS'
    assert len(review['late_request_states']) == 9
    for p in H.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    log_bytes = (H / 'TESTS_FINAL.log').read_bytes()
    log = log_bytes.decode('utf-16' if log_bytes.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8')
    assert 'Ran 16 tests' in log and '\nOK' in log
    git = lambda *args:subprocess.check_output(['git', *args], cwd=R, text=True, encoding='utf-8').strip()
    assert git('rev-parse', 'HEAD') == review['HEAD']
    files = [p for d in (H, O) for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [R / p for p in ('docs/PROJECT_STATUS.md', 'docs/PROJECT_PLAN.md', 'docs/DECISIONS.md',
                             'a24_simulator/docs/LATEST_EXECUTION_FILES.md')]
    python = r'C:\Users\chomg\Documents\Codex\2026-10-11\dkfo\work\atcenv\Scripts\python.exe'
    stem = 'a24_simulator/experiments/a24_idle_wait_repair_20261019/'
    record = dict(status='PASS', version='A24_IDLE_WAIT_DOMINANCE_V1',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), HEAD=git('rev-parse', 'HEAD'),
        branch=git('branch', '--show-current'), working_tree=git('status', '--short'), published=False,
        regression_tests=16, saved_states=3781, independent_mask_checks=read(O/'MASK_AUDIT.json')['checks'],
        Float64_NN_frames=read(O/'NN_AUDIT.json')['frames'], source_and_input_pins_verified=len(op['pins']),
        new_environment=0, new_training=0, new_fit=0, new_device=0,
        budget_conservative_total=137715, approved_cap=137715, new_budget_consumed=0,
        performance_after_fix_measured=False, old_completed_experiments_rerun=0,
        commands=[[python, '-B', '-X', 'utf8', stem+'test_contracts.py'],
                  [python, '-B', '-X', 'utf8', stem+'review_saved.py'],
                  ['node', stem+'audit_masks.cjs'],
                  [python, '-B', '-X', 'utf8', stem+'audit_nn.py'],
                  [python, '-B', '-X', 'utf8', stem+'seal.py']],
        files=[pin(p) for p in sorted(set(files))])
    with (O/'VERIFICATION.json').open('x', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2, allow_nan=False)
    print('IDLE_WAIT_REPAIR_SEALED', len(files), 'files;', len(op['pins']), 'original pins preserved')


if __name__ == '__main__':
    main()
