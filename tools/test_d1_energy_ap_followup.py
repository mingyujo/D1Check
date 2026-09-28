"""PC-only checks for the two-condition follow-up entry boundary."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_arrival_plan as p
from tools import d1_energy_ap_followup as followup
from tools import d1_energy_collection_device as device
from tools import d1_energy_state_collection as state


class FakeDevice:
    def __init__(self,*args,**kwargs):
        self.deadline=None
        self.sequence=0
        self.command_limit=None
    def call(self,*args,**kwargs):
        self.sequence+=1


class FollowupTest(unittest.TestCase):
    def fixture(self,root):
        frozen=root/'prior_freeze.json'
        frozen.write_text(json.dumps({'version':'energy-ap-state-regimen-fit-v1','marker':'unchanged'}),encoding='utf-8')
        entries=[]
        for i,pair in enumerate(followup.PAIRS):
            path=root/f'{i}.json';path.write_text('{}',encoding='utf-8')
            entries.append(dict(index=i,phase='confirmation',pair=pair,mode='calibration',
                                session_id=f'new-{i}',manifest=path.name))
        value=dict(state_model_calibration=True,state_model_followup=True,
            protocol=state.PROTOCOL,output_root=str(root/'run'),registry=str(root/'registry'),
            budget=followup.BUDGET,apk_preflight={'candidate':{}},apk_sha256='fixture',
            source_files={},entries=entries,
            prior_freeze={'path':str(frozen),'sha256':p.digest(frozen)})
        path=root/'plan.json';path.write_text(json.dumps(value),encoding='utf-8')
        return path,frozen

    def test_confirmation_only_reuses_exact_freeze_and_never_refits(self):
        followup.budget_check()
        self.assertEqual(followup.BUDGET['explicit_inference'],3384)
        self.assertEqual(followup.BUDGET['fixed_observation_seconds'],34*60)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,frozen=self.fixture(root)
            def summarize(_,manifest,plan):
                index=int(Path(manifest).stem)
                return dict(status='eligible_regimen_only',condition=followup.PAIRS[index],
                            work_calls=1,eligibility_calls=4,warmup_calls=8)
            with patch.object(followup,'check'),patch.object(device,'ObservedDevice',FakeDevice),\
                 patch.object(device,'installed_preflight',return_value={'status':'verified'}),\
                 patch.object(device,'gates'),patch.object(device.install,'installed_hash',return_value='fixture'),\
                 patch.object(device.shared,'stage_inputs',return_value='remote'),\
                 patch.object(device,'poll') as poll,patch.object(device,'recover',return_value={'status':'recovered'}),\
                 patch.object(device.shared,'cleanup',return_value={'status':'completed'}),\
                 patch.object(state,'summarize_session',side_effect=summarize),\
                 patch.object(state,'freeze',side_effect=AssertionError('must not refit')),\
                 patch.object(state,'evaluate',return_value={'signed_energy_error_on_covered_time_j':1}) as evaluate:
                result=device.run(plan,'NO_ADB',None,p.digest(plan),True)
            self.assertEqual(result['status'],'completed_followup_confirmation_only')
            self.assertEqual(result['sessions'],2)
            self.assertEqual(evaluate.call_count,2)
            self.assertEqual(poll.call_count,2)
            self.assertTrue(all('diagnostic_stop_after_preparation' not in call.kwargs
                                for call in poll.call_args_list))
            self.assertEqual((root/'run/development_freeze.json').read_bytes(),frozen.read_bytes())
            self.assertEqual([json.loads(x.read_text())['condition'] for x in sorted((root/'run').glob('0?_*/*validated.json'))],
                             list(followup.PAIRS))
            self.assertEqual(json.loads((root/'registry/completed.json').read_text())['status'],result['status'])

    def test_first_session_failure_stops_without_second_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,_=self.fixture(root)
            with patch.object(followup,'check'),patch.object(device,'ObservedDevice',FakeDevice),\
                 patch.object(device,'installed_preflight',return_value={'status':'verified'}),\
                 patch.object(device,'gates'),patch.object(device.install,'installed_hash',return_value='fixture'),\
                 patch.object(device.shared,'stage_inputs',return_value='remote'),\
                 patch.object(device,'poll',side_effect=TimeoutError('fixture ADB timeout')) as poll,\
                 patch.object(device,'pull_file',side_effect=OSError('fixture partial recovery')),\
                 patch.object(device.shared,'cleanup',side_effect=OSError('fixture cleanup')),\
                 self.assertRaisesRegex(TimeoutError,'fixture ADB timeout'):
                device.run(plan,'NO_ADB',None,p.digest(plan),True)
            self.assertEqual(poll.call_count,1)
            receipt=json.loads((root/'run/FINAL_RECEIPT.json').read_text())
            self.assertEqual(receipt['completed_sessions'],0)
            self.assertIn('fixture ADB timeout',receipt['exception_stack'])
            self.assertIn('fixture cleanup',receipt['host_cleanup_error'])
            self.assertEqual(json.loads((root/'registry/stopped.json').read_text())['status'],'stopped_no_resume')
            with patch.object(followup,'check'),self.assertRaises(FileExistsError):
                device.run(plan,'NO_ADB',None,p.digest(plan),True)


if __name__=='__main__':unittest.main()
