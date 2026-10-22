"""Seal the two requested frozen-checkpoint evaluations and saved audits."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

H = Path(__file__).resolve().parent
R = H.parents[2]
O = R / 'a24_simulator/results/A24_IDLE_WAIT600_20261019_01'


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
    assert op['status'] == 'AUTHORIZED_REGISTERED' and op['authorized_total'] == 137717
    auth = read(R / op['authorization']['path'])
    assert auth['user_message'] == '이거 결과 내봐' and auth['authorized_units'] == 2
    assert auth['numeric_total_explicitly_stated_by_user'] is False
    result = read(O / 'RESULT.json')
    assert (result['START'], result['COMPLETE'], result['FAIL']) == (2, 2, 0)
    assert all(result[k] == 0 for k in ('new_training', 'new_BC_fit', 'new_PPO', 'new_fit', 'new_device'))
    assert result['checkpoint'] == op['checkpoint'];verify([result['checkpoint']])
    verify([r['raw'] for r in result['rows']])
    receipts = [json.loads(x) for x in (O / 'receipts.jsonl').read_text().splitlines()]
    starts = [r for r in receipts if r['event'] == 'START']
    complete = [r for r in receipts if r['event'] == 'COMPLETE']
    assert len(receipts) == 4 and len(starts) == len(complete) == 2
    assert {r['start_id'] for r in starts} == {r['start_id'] for r in complete}
    assert len(set(r['start_id'] for r in starts)) == 2
    for name in ('AUDIT.json', 'NN_AUDIT.json', 'REPLAY.json', 'OUTCOME_REVIEW.json'):
        assert read(O / name)['status'] == 'PASS'
    assert read(O / 'AUDIT.json')['rows'] == 12
    assert read(O / 'NN_AUDIT.json')['frames'] == read(O / 'REPLAY.json')['frames'] == 3769
    outcome = read(O / 'OUTCOME_REVIEW.json')
    assert len(outcome['targets']) == 1
    assert outcome['targets'][0]['response_improvement_ns'] == 420000000
    assert outcome['targets'][0]['after_margin_ns'] == 418453841
    summary = read(O / 'SUMMARY.json')
    groups = {g['policy']:g for g in summary['groups']}
    assert len(groups) == 6 and summary['old_results_rerun'] == 0
    after = groups['IDLE_BC']
    assert after['service']['ALL']['on'] == after['service']['ALL']['n'] == 1720
    assert after['service']['U']['on'] == after['service']['U']['n'] == 440
    assert after['incomplete'] == after['service']['ALL']['missing'] == 0
    assert groups['BC']['common_J'] < after['common_J'] < groups['ATC_BC']['common_J']
    assert after['service']['ALL']['mean_session_P95_s'] > groups['ATC_BC']['service']['ALL']['mean_session_P95_s']
    for p in H.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    git = lambda *args:subprocess.check_output(['git', *args], cwd=R, text=True, encoding='utf-8').strip()
    assert git('rev-parse', 'HEAD') == op['HEAD']
    assert git('branch', '--show-current') == op['branch']
    files = [p for d in (H, O) for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [R / p for p in ('docs/PROJECT_STATUS.md', 'docs/PROJECT_PLAN.md', 'docs/DECISIONS.md',
                             'a24_simulator/docs/LATEST_EXECUTION_FILES.md')]
    python = r'C:\Users\chomg\Documents\Codex\2026-10-11\dkfo\work\atcenv\Scripts\python.exe'
    stem = 'a24_simulator/experiments/a24_idle_wait_eval_20261019/'
    record = dict(status='PASS', schema='A24_IDLE_WAIT600_LOCAL_FINAL_PROOF_V1',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), HEAD=git('rev-parse', 'HEAD'),
        branch=git('branch', '--show-current'), working_tree=git('status', '--short'), published=False,
        operation_sha256=pin(H / 'OPERATION.json')['sha256'], authorization=op['authorization'],
        registered_pins_verified=len(op['pins']), new_START=2, new_COMPLETE=2, new_FAIL=0,
        new_training=0, new_BC_fit=0, new_PPO=0, new_physical_fit=0, new_device=0,
        old_completed_environments_rerun=0,
        budget=dict(previous_closed_total=137715, current_requested_EVAL=2,
                    current_consumed=2, conservative_total=137717, automatic_extra_experiments=0, refund=0),
        commands=[[python, '-B', '-X', 'utf8', stem+'study.py', '--propose'],
                  [python, '-B', '-X', 'utf8', stem+'verify_ready.py'],
                  [python, '-B', '-X', 'utf8', stem+'study.py', '--register'],
                  [python, '-B', '-X', 'utf8', stem+'study.py', '--run'],
                  ['node', stem+'audit_report.cjs'],
                  [python, '-B', '-X', 'utf8', stem+'audit_nn.py'],
                  [python, '-B', '-X', 'utf8', stem+'review_outcomes.py'],
                  [python, '-B', '-X', 'utf8', stem+'seal.py']],
        files=[pin(p) for p in sorted(set(files))])
    with (O / 'FINAL_HANDOFF_PROOF.json').open('x', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2, allow_nan=False)
    print('IDLE_WAIT600_LOCAL_SEALED', len(files), 'files;', len(op['pins']), 'registered pins preserved')


if __name__ == '__main__':
    main()
