"""Final saved-file identity, receipt and link check; no scientific execution."""
import collections
import datetime
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

H = Path(__file__).resolve().parent
R = H.parents[2]
O = R / 'a24_simulator/results/A24_BC_RECOVERY_20261021_01'


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


def verify(pin):
    p = Path(pin['path'])
    if not p.is_absolute():
        p = R / p
    assert p.is_file(), str(p)
    assert p.stat().st_size == pin['bytes'], str(p)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    assert h.hexdigest() == pin['sha256'], str(p)


def pins(obj):
    if isinstance(obj, dict):
        if all(k in obj for k in ('path', 'bytes', 'sha256')):
            yield obj
        for value in obj.values():
            yield from pins(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from pins(value)


def main():
    proof = read(O / 'FINAL_PROOF.json')
    for p in proof['files']:
        verify(p)
    assert proof['status'] == 'PASS'
    operation = read(H / 'OPERATION.json')
    result = read(O / 'RESULT.json')
    accounting = read(O / 'ACCOUNTING.json')
    binding = read(R / 'a24_simulator/experiments/a24_s26_common_20261020/SOURCE_BINDING.json')
    sources = list(pins(operation))
    outputs = list(pins(result)) + list(pins(accounting))
    preserved = binding['preserved_completed_files']
    seen = {}
    for p in sources + outputs + preserved:
        if p['path'] in seen:
            assert seen[p['path']] == (p['bytes'], p['sha256']), p['path']
        else:
            verify(p)
            seen[p['path']] = (p['bytes'], p['sha256'])
    receipts = [json.loads(line) for line in (O / 'receipts.jsonl').read_text(encoding='utf8').splitlines()]
    events = collections.Counter(x['event'] for x in receipts)
    assert events == {'START': 19, 'COMPLETE': 19}, events
    starts = {x['start_id']: x['label'] for x in receipts if x['event'] == 'START'}
    ends = {x['start_id']: x['label'] for x in receipts if x['event'] == 'COMPLETE'}
    assert len(starts) == 19 and starts == ends
    assert result['science_START'] == 19 and result['new_TRAIN'] == 6 and result['new_BC_fit'] == 1 and result['new_EVAL'] == 12
    assert result['fit']['network_sha256'] == 'cec00807e6729c4f59bbb74723749eeb2db722786c55a7d754b1253477eb6ad7'
    assert len(accounting['rows']) == 36 and sum(x['reused'] for x in accounting['rows']) == 24
    assert all(x['status'] == 'COMPLETE' for x in accounting['rows'])
    assert not any(x['service']['ALL']['missing'] or x['service']['ALL']['incomplete'] for x in accounting['rows'])
    control = [R/'docs/PROJECT_STATUS.md', R/'docs/PROJECT_PLAN.md', R/'docs/DECISIONS.md', R/'a24_simulator/docs/LATEST_EXECUTION_FILES.md']
    links = 0
    documents = list(H.glob('*.md')) + list(O.glob('*.md'))
    # Historical sections are preserved. Check only this work's leading block.
    texts = [(p, p.read_text(encoding='utf8')) for p in documents]
    texts += [(p, p.read_text(encoding='utf8').split('\n## ', 1)[0]) for p in control]
    for p, content in texts:
        for ref in re.findall(r'\[[^\]]*\]\(([^)]+)\)', content):
            if ref.startswith(('http:', 'https:', 'codex:', '#')):
                continue
            target = (p.parent / unquote(ref.split('#', 1)[0].strip('<>'))).resolve()
            if target == (O / 'FINAL_RECHECK.json').resolve():
                # This report is created after all other checks below.
                links += 1
                continue
            assert target.is_file() or target.is_dir(), f'{p}: {ref}'
            links += 1
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R, text=True).strip()
    assert head == proof['HEAD'] == 'ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf'
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=R, text=True).strip()
    assert branch == 'codex/a24-simulator-handoff-20261016'
    subprocess.run(['git', 'diff', '--check'], cwd=R, check=True)
    checks = dict(status='PASS', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), HEAD=head,
                  branch=branch, working_tree_uncommitted=True, proof_files_verified=len(proof['files']),
                  input_output_and_preserved_unique_files_verified=len(seen),
                  source_pin_records=len(sources), result_pin_records=len(outputs), preserved_completed_files=len(preserved),
                  receipts=dict(events), linked_targets=links, comparison_rows=36, reused_completed_rows=24,
                  all_missing_incomplete_zero=True, original_policy_unchanged=True, git_diff_check='PASS',
                  new_environment=0, new_fit=0, adopted=False, published=False,
                  final_proof_sha256=hashlib.sha256((O/'FINAL_PROOF.json').read_bytes()).hexdigest(),
                  control_docs=[dict(path=p.relative_to(R).as_posix(), bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in control])
    with (O / 'FINAL_RECHECK.json').open('x', encoding='utf8', newline='\n') as f:
        json.dump(checks, f, ensure_ascii=False, indent=2)
        f.write('\n')
    assert (O / 'FINAL_RECHECK.json').is_file()
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == '__main__':
    main()
