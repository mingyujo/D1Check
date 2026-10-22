"""Seal local BC600 artifacts and provenance; never run a simulation."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

H = Path(__file__).resolve().parent
A = H.parents[1]
R = A.parent
O = A / 'results/A24_BC_600_20261019_01'


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    read = lambda p:json.loads(p.read_text(encoding='utf-8'))
    op = read(H / 'OPERATION.json')
    for p in op['pins']:
        f = R / p['path']
        assert f.stat().st_size == p['bytes'] and sha(f) == p['sha256'], p['path']
    result = read(O / 'RESULT.json')
    assert (result['START'],result['COMPLETE'],result['FAIL']) == (2,2,0)
    for name in ('AUDIT.json','NN_AUDIT.json','REPLAY.json'):
        assert read(O/name)['status'] == 'PASS'
    amendment = read(H / 'AUDITOR_AMENDMENT.json')
    for key in ('original','revised','original_failure_log'):
        assert sha(H/amendment[key]['path']) == amendment[key]['sha256']
    files = [p for folder in (H,O) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [R / p for p in ('docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md',
                             'a24_simulator/docs/LATEST_EXECUTION_FILES.md')]
    git = lambda *args:subprocess.check_output(['git',*args],cwd=R,text=True,encoding='utf-8').strip()
    record = dict(schema='A24_BC600_LOCAL_FINAL_PROOF_V1',status='PASS',
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),HEAD=git('rev-parse','HEAD'),
        working_tree=git('status','--short'),operation_sha256=sha(H/'OPERATION.json'),
        preregistration=op['preregistration'],published=False,new_START=2,new_COMPLETE=2,new_FAIL=0,
        new_training=0,new_physical_fit=0,new_device=0,old_environments_rerun=0,
        budget=op['budget'],logic_repair_applied=False,registered_pins_verified=len(op['pins']),
        original_auditor_and_setup_failures_retained=True,
        commands=[
            'python -B -X utf8 a24_simulator/experiments/a24_bc_600_20261019/study.py',
            'python -B -X utf8 a24_simulator/experiments/a24_bc_600_20261019/study.py --register',
            'python -B -X utf8 a24_simulator/experiments/a24_bc_600_20261019/study.py --run --registered',
            'node a24_simulator/experiments/a24_bc_600_20261019/audit_report_v2.cjs',
            'python -B -X utf8 a24_simulator/experiments/a24_bc_600_20261019/audit_nn.py',
            'python -B -X utf8 a24_simulator/experiments/a24_bc_600_20261019/seal.py'],
        files=[dict(path=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(set(files))])
    with (O/'FINAL_HANDOFF_PROOF.json').open('x',encoding='utf-8') as f:
        json.dump(record,f,ensure_ascii=False,indent=2,allow_nan=False)
    print('BC600_LOCAL_SEALED',len(record['files']),'files;',len(op['pins']),'registered pins verified')


if __name__=='__main__':
    main()
