"""One-session route tests with no adb executable or device command."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_arrival_plan as p
from tools import d1_energy_ap_short_transition as short
from tools import d1_energy_collection_device as device
from tools import d1_energy_state_collection as state


class FakeDevice:
    def __init__(self,*args,**kwargs):
        self.deadline=None;self.sequence=0;self.command_limit=None
    def call(self,*args,**kwargs):
        self.sequence+=1
        return subprocess.CompletedProcess(args,0,b'',b'')


class ShortTransitionTest(unittest.TestCase):
    def test_block_and_budget_bounds(self):
        short.budget_check()
        self.assertEqual(len(short.SHORT_BLOCKS),36)
        self.assertEqual(sum(s for _,_,s in short.SHORT_BLOCKS),480)
        self.assertEqual(sum(len(l)*s*4 for _,l,s in short.SHORT_BLOCKS),1680)
        self.assertEqual(sum(s for _,l,s in short.SHORT_BLOCKS if len(l)==2),120)

    def test_one_session_loads_freeze_and_labels_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);freeze=root/'freeze.json';freeze.write_text('{"version":"frozen"}',encoding='utf-8')
            manifest=root/'manifest.json';manifest.write_text(json.dumps(dict(
                session_control='device-after-probe-diagnostic-v1',autonomous_diagnostic_only=True)),encoding='utf-8')
            plan=root/'plan.json';plan.write_text(json.dumps(dict(
                state_model_calibration=True,autonomous_diagnostic_only=True,
                short_transition_diagnostic_only=True,diagnostic_only=True,state_model_followup=False,
                protocol=state.PROTOCOL,experiment_id=short.EXPERIMENT,
                output_root=str(root/'run'),registry=str(root/'registry'),budget=short.BUDGET,
                prior_freeze=dict(path=str(freeze),sha256=p.digest(freeze)),
                apk_preflight={'candidate':{}},apk_sha256='fixture',source_files={},entries=[dict(
                    index=0,phase='confirmation',pair='CC_DG',mode='calibration',session_id='fixture',
                    manifest=manifest.name)])),encoding='utf-8')
            with patch.object(short,'check'),patch.object(device,'ObservedDevice',FakeDevice),\
                 patch.object(device,'installation',return_value={'status':'verified'}),\
                 patch.object(device,'gates'),patch.object(device.install,'installed_hash',return_value='fixture'),\
                 patch.object(device.shared,'stage_inputs',return_value='remote'),\
                 patch.object(device,'poll'),patch.object(device,'recover',return_value={'status':'recovered'}),\
                 patch.object(device.shared,'cleanup',return_value={'status':'completed'}),\
                 patch.object(state,'summarize_session',return_value=dict(
                     status='eligible_regimen_only',condition='CC_DG',work_calls=1,
                     eligibility_calls=4,warmup_calls=8)),\
                 patch.object(state,'evaluate',return_value={'signed_energy_error_on_covered_time_j':2.0}),\
                 patch.object(state,'freeze',side_effect=AssertionError('no fitting')):
                result=device.run(plan,'NO_ADB',None,p.digest(plan),True)
            self.assertEqual(result['status'],'completed_short_transition_protocol_diagnostic_only')
            self.assertEqual((root/'run/development_freeze.json').read_bytes(),freeze.read_bytes())
            session=next((root/'run').glob('00_*/validated.json'))
            values=json.loads(session.read_text(encoding='utf-8'))
            self.assertFalse(values['formal_confirmation'])
            self.assertNotIn('confirmation_errors',values)
            self.assertIsNone(values['transition_errors']['accuracy_pass'])
            self.assertTrue((root/'registry/completed.json').exists())
            with patch.object(short,'check'),self.assertRaises(FileExistsError):
                device.run(plan,'NO_ADB',None,p.digest(plan),True)


if __name__=='__main__':unittest.main()
