"""Seal the RR2 comparison and its updated methodology; saved-only checks."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

H = Path(__file__).resolve().parent
R = H.parents[2]
O = R / 'a24_simulator/results/A24_RR_600_20261020_01'


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
    assert not (O / 'FINAL_HANDOFF_PROOF.json').exists()
    op = read(H / 'OPERATION.json');verify(op['pins']);verify([op['authorization']])
    assert op['status'] == 'AUTHORIZED_REGISTERED' and op['authorized_total'] == 137719
    auth = read(R / op['authorization']['path'])
    assert auth['user_message'] == 'RR 하고는 비교 못함?' and auth['authorized_units'] == 2
    assert auth['numeric_total_explicitly_stated_by_user'] is False
    result = read(O / 'RESULT.json')
    assert (result['START'], result['COMPLETE'], result['FAIL']) == (2, 2, 0)
    assert all(result[k] == 0 for k in ('new_training', 'new_BC_fit', 'new_PPO', 'new_NN_execution', 'new_fit', 'new_device'))
    verify([r['raw'] for r in result['rows']])
    receipts = [json.loads(x) for x in (O / 'receipts.jsonl').read_text().splitlines()]
    starts = [r for r in receipts if r['event'] == 'START']
    complete = [r for r in receipts if r['event'] == 'COMPLETE']
    assert len(receipts) == 4 and len(starts) == len(complete) == 2
    assert {r['start_id'] for r in starts} == {r['start_id'] for r in complete}
    assert len(set(r['start_id'] for r in starts)) == 2
    for name in ('AUDIT.json', 'REPLAY.json', 'RR_FIFO_DIAGNOSIS.json'):
        assert read(O / name)['status'] == 'PASS'
    assert read(O / 'AUDIT.json')['rows'] == 14
    assert read(O / 'REPLAY.json')['calls'] == 1720
    assert all(c['action_and_time_exactly_equal_FIFO'] and c['comparison_window_unchanged']
               for c in read(O / 'RR_FIFO_DIAGNOSIS.json')['cases'])
    summary = read(O / 'SUMMARY.json');groups = {g['policy']:g for g in summary['groups']}
    assert len(groups) == 7 and summary['old_results_rerun'] == 0
    rr = groups['RR_CPU']
    assert rr['service']['ALL']['on'] == rr['service']['ALL']['n'] == 1720
    assert rr['service']['U']['on'] == rr['service']['U']['n'] == 440
    assert rr['incomplete'] == rr['service']['ALL']['missing'] == 0
    assert rr['common_J'] == groups['FIFO_CPU']['common_J'] > groups['IDLE_BC']['common_J']
    assert rr['AP'] == groups['FIFO_CPU']['AP'] > groups['IDLE_BC']['AP']
    for p in H.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    blob = (H / 'TESTS.log').read_bytes()
    tests = blob.decode('utf-16' if blob.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8')
    assert 'Ran 16 tests' in tests and '\nOK' in tests
    git = lambda *args:subprocess.check_output(['git', *args], cwd=R, text=True, encoding='utf-8').strip()
    assert git('rev-parse', 'HEAD') == op['HEAD']
    assert git('branch', '--show-current') == op['branch']
    files = [p for d in (H, O) for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [R / p for p in ('docs/PROJECT_STATUS.md', 'docs/PROJECT_PLAN.md', 'docs/DECISIONS.md',
        'a24_simulator/docs/LATEST_EXECUTION_FILES.md', 'a24_simulator/docs/A24_POLICY_METHODOLOGY_KO.md')]
    python = r'C:\Users\chomg\Documents\Codex\2026-10-11\dkfo\work\atcenv\Scripts\python.exe'
    stem = 'a24_simulator/experiments/a24_rr_600_20261020/'
    record = dict(status='PASS', schema='A24_RR600_LOCAL_FINAL_PROOF_V1',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), HEAD=git('rev-parse', 'HEAD'),
        branch=git('branch', '--show-current'), working_tree=git('status', '--short'), published=False,
        operation_sha256=pin(H / 'OPERATION.json')['sha256'], authorization=op['authorization'],
        registered_pins_verified=len(op['pins']), new_START=2, new_COMPLETE=2, new_FAIL=0,
        new_training=0, new_BC_fit=0, new_PPO=0, new_NN_execution=0, new_physical_fit=0, new_device=0,
        old_completed_environments_rerun=0, original_RR_definition_preserved=True,
        budget=dict(previous_closed_total=137717, current_requested_EVAL=2, current_consumed=2,
                    conservative_total=137719, automatic_extra_experiments=0, refund=0),
        commands=[[python, '-B', '-X', 'utf8', stem+'test_rr.py'],
                  [python, '-B', '-X', 'utf8', stem+'study.py', '--propose'],
                  [python, '-B', '-X', 'utf8', stem+'verify_ready.py'],
                  [python, '-B', '-X', 'utf8', stem+'study.py', '--register'],
                  [python, '-B', '-X', 'utf8', stem+'study.py', '--run'],
                  ['node', stem+'audit_report.cjs'],
                  [python, '-B', '-X', 'utf8', stem+'review_rr.py'],
                  [python, '-B', '-X', 'utf8', stem+'seal.py']],
        files=[pin(p) for p in sorted(set(files))])
    with (O / 'FINAL_HANDOFF_PROOF.json').open('x', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2, allow_nan=False)
    print('RR600_LOCAL_SEALED', len(files), 'files;', len(op['pins']), 'registered pins preserved')


if __name__ == '__main__':
    main()
