"""Seal the approved three-unit local run. Reads saved evidence only."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

H = Path(__file__).resolve().parent
R = H.parents[2]
O = R / 'a24_simulator/results/A24_ATC_BC600_20261019_01'
PYTHON = r'C:\Users\chomg\Documents\Codex\2026-10-11\dkfo\work\atcenv\Scripts\python.exe'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify(pins):
    for p in pins:
        file = R / p['path']
        assert file.stat().st_size == p['bytes'] and sha(file) == p['sha256'], p['path']


def main():
    assert not (O / 'FINAL_HANDOFF_PROOF.json').exists()
    op = read(H / 'OPERATION.json')
    assert op['status'] == 'APPROVED_REGISTERED' and op['approved_cap'] == 137715
    verify(op['pins'])
    verify([op['approval']])
    approval = read(R / op['approval']['path'])
    assert approval['approved'] is True and approval['user_message'] == '추가 3단위 승인하고 실행'
    assert sha(H / 'PROPOSAL.json') == 'de227e54b54afdc4a594d466fb1bed0e3d52ad1f651b3482ff33fc987505f993'
    result = read(O / 'RESULT.json')
    assert (result['START'], result['COMPLETE'], result['FAIL']) == (2, 2, 0)
    assert (result['FIT_START'], result['FIT_COMPLETE'], result['total_scientific_START']) == (1, 1, 3)
    assert result['new_BC_fit'] == 1 and result['new_PPO'] == result['new_fit'] == result['new_device'] == 0
    receipts = [json.loads(line) for line in (O / 'receipts.jsonl').read_text().splitlines()]
    starts = [r for r in receipts if r['event'] == 'START']
    completed = [r for r in receipts if r['event'] == 'COMPLETE']
    assert len(starts) == len(completed) == len(set(r['start_id'] for r in starts)) == 3
    assert {r['start_id'] for r in starts} == {r['start_id'] for r in completed}
    assert len(receipts) == 6
    assert sum(r['kind'] == 'FIT' for r in starts) == 1
    assert sum(r['kind'] == 'EVAL' for r in starts) == 2
    for name in ('AUDIT.json', 'NN_AUDIT.json', 'REPLAY.json', 'LATE_CASE_REVIEW.json'):
        assert read(O / name)['status'] == 'PASS'
    summary = read(O / 'SUMMARY.json')
    groups = {g['policy']:g for g in summary['groups']}
    assert summary['old_results_rerun'] == 0 and len(groups) == 5
    new, old = groups['ATC_BC'], groups['BC']
    assert new['common_J'] > old['common_J'] and new['AP'] > old['AP']
    assert new['service']['U']['on'] == 439 and old['service']['U']['on'] == 440
    assert new['incomplete'] == new['service']['ALL']['missing'] == 0
    assert read(O / 'BC_TRAINING.json')['EVAL_used_for_selection'] is False
    assert read(H / 'READINESS.json')['status'] == 'PASS_AWAITING_BUDGET_APPROVAL'
    assert read(O / 'LATE_CASE_REVIEW.json')['reviews'][0]['lateness_ns'] == 1546159
    git = lambda *args:subprocess.check_output(['git', *args], cwd=R, text=True, encoding='utf-8').strip()
    assert git('rev-parse', 'HEAD') == op['HEAD']
    assert git('branch', '--show-current') == 'codex/a24-simulator-handoff-20261016'
    files = [p for folder in (H, O) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [R / p for p in ('docs/PROJECT_STATUS.md', 'docs/PROJECT_PLAN.md', 'docs/DECISIONS.md',
                              'a24_simulator/docs/LATEST_EXECUTION_FILES.md')]
    stem = 'a24_simulator/experiments/a24_atc_bc_20261019/'
    record = dict(schema='A24_ATC_BC600_LOCAL_FINAL_PROOF_V1', status='PASS',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), HEAD=git('rev-parse', 'HEAD'),
        branch=git('branch', '--show-current'), working_tree=git('status', '--short'),
        published=False, operation_sha256=sha(H / 'OPERATION.json'),
        proposal_sha256=sha(H / 'PROPOSAL.json'), approval=op['approval'],
        registered_pins_verified=len(op['pins']), new_scientific_START=3, new_scientific_COMPLETE=3,
        new_scientific_FAIL=0, new_BC_fit=1, new_EVAL=2, new_PPO=0, new_training_environment=0,
        new_physical_fit=0, new_device=0, old_environments_rerun=0,
        budget=dict(before=137712, additional_approved=3, additional_consumed=3,
                    conservative_total=137715, approved_cap=137715, refund=0),
        logic_repair_applied=True, ATC_only_effect_isolated=False,
        conclusion='Retain old BC for energy/AP and full on-time service in these two 600s cases.',
        commands=[
            [PYTHON, '-B', '-X', 'utf8', stem+'study.py', '--register'],
            [PYTHON, '-B', '-X', 'utf8', stem+'study.py', '--run'],
            ['node', stem+'audit_report.cjs'],
            [PYTHON, '-B', '-X', 'utf8', stem+'audit_nn.py'],
            [PYTHON, '-B', '-X', 'utf8', stem+'review_saved.py'],
            [PYTHON, '-B', '-X', 'utf8', stem+'seal.py']],
        files=[dict(path=p.relative_to(R).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
               for p in sorted(set(files))])
    with (O / 'FINAL_HANDOFF_PROOF.json').open('x', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2, allow_nan=False)
    print('ATC_BC600_LOCAL_SEALED', len(record['files']), 'files;', len(op['pins']), 'registered pins verified')


if __name__ == '__main__':
    main()
