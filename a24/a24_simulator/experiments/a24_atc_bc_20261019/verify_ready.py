"""Preflight with saved states only; no optimizer step, fit, or engine.run."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import unittest
import psutil
import test_contracts
import study
from common_transfer import np,torch,loadpt


def main():
    H,A,R=study.H,study.A,study.R
    suite=unittest.defaultTestLoader.loadTestsFromModule(test_contracts)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful()
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
    subprocess.check_call(['node','--check',str(H/'audit_report.cjs')])
    data=study.read(H/'DATASET.json');proposal=study.read(H/'PROPOSAL.json')
    study.verify(proposal['pins']);study.verify([data['dataset'],*data['source']])
    saved=loadpt(R/data['dataset']['path']);frames=saved['frames']
    assert saved['version']==study.VERSION and len(frames)==data['frames']==1320
    source_map={}
    for p in data['source']:
        if '.raw.json.gz' in p['path']:
            raw=study.read(R/p['path']);source_map[raw['case']['id']]=raw
    state_bindings=0
    for f in frames:
        assert f['x'].shape==(36,50) and f['mask'].shape==f['teacher_mask'].shape==(36,)
        assert np.isfinite(f['x']).all() and f['teacher_mask'][f['index']]
        assert not (f['teacher_mask'] & ~f['mask']).any()
        raw=source_map[f['case']];s=raw['result']['decisions'][f['source_decision_index']]['public_state']
        assert study.B.L.digest(s)==f['public_state_sha256'];state_bindings+=1
    assert set(f['case'] for f in frames)==set(data['train_case_ids'])
    assert data['evaluation_cases_used']==0
    assert data['changed_teacher_actions']==0 and data['compatible_multi_target_frames']==13 and data['capped_forecasts']==0
    assert not (H/'BUDGET_APPROVAL.json').exists() and not (H/'OPERATION.json').exists() and not study.O.exists()
    for command in (study.register,study.run):
        try:command()
        except FileNotFoundError:pass
        else:raise AssertionError('Budget guard failed closed')
    assert not study.O.exists() and not (H/'OPERATION.json').exists()
    import_manifest=study.read(A/'experiments/s26_virtual_transfer_20261018/SOURCE_IMPORT.json')
    rel='s26_simulator/experiments/route_group_learning_v1/policy.cjs'
    reference=next(p for p in import_manifest['files'] if p['path']==rel)
    assert study.sha(A/'experiments/s26_virtual_transfer_20261018/vendor'/rel)==reference['sha256']
    git=lambda *a:subprocess.check_output(['git',*a],cwd=R,text=True,encoding='utf-8').strip()
    study.new(H/'READINESS.json',dict(status='PASS_AWAITING_BUDGET_APPROVAL',utc=study.stamp(),
        HEAD=git('rev-parse','HEAD'),working_tree=git('status','--short'),
        command=[sys.executable,'-B','-X','utf8','a24_simulator/experiments/a24_atc_bc_20261019/verify_ready.py'],
        tests=result.testsRun,proposal_sha256=study.sha(H/'PROPOSAL.json'),
        registered_source_input_pins_verified=len(proposal['pins']),
        prepared_frames=len(frames),saved_public_state_bindings=state_bindings,
        new_environment_START=0,new_BC_fit=0,new_PPO=0,new_measurement=0,
        budget_guard_verified=True,BC_model_created=False,
        requested_additional_units=3,existing_cap=137712,requested_cap=137715,
        environment=dict(python=sys.version,numpy=np.__version__,torch=torch.__version__,psutil=psutil.__version__),
        source_s26_commit=import_manifest['source_commit']))
    print('ATC_BC_PREFLIGHT_PASS',result.testsRun,'tests;',state_bindings,'public states; new science 0')


if __name__=='__main__':main()
