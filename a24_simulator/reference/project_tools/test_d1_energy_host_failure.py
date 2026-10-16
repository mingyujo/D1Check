"""PC-only fault injection at host run and process boundaries; no ADB client."""

import json
from contextlib import nullcontext
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from tools import d1_arrival_plan as plan_io
from tools import d1_energy_collection_device as device
from tools import d1_energy_collection as collection
from tools import d1_energy_host_checkpoints as checkpoints
from tools import d1_energy_state_collection as state
from tools import d1_recorded_process as process


class FakeDevice:
    def __init__(self,*args,**kwargs):self.deadline=None;self.sequence=0;self.command_limit=None
    def call(self,*args,**kwargs):return None


class HostFailureTest(unittest.TestCase):
    def test_resident_freeze_failure_summarizes_last_development_not_next_confirmation(self):
        # Real host loop advances e to confirmation index4 before freeze raises.
        # The last recovered development allowed1200; upcoming confirmation only600.
        from tools import d1_resident_identification_plan as resident
        with TemporaryDirectory() as tmp:
            root=Path(tmp);path=self.fixture(root);plan=json.loads(path.read_text())
            plan.update(resident_identification=True,autonomous_diagnostic_only=True,diagnostic_only=True,
                        budget=dict(resident.budget(),intersession_cooling_seconds=0))
            plan['entries']=[dict(index=i,phase='development' if i<4 else 'confirmation',pair='CC_DG',mode='calibration',
                                  family='regimen',session_id=f'fixture{i}',manifest='manifest.json',
                                  work_requests=1200 if i<4 else 600,eligibility_requests=4) for i in range(5)]
            path.write_text(json.dumps(plan),encoding='utf8')
            (root/'manifest.json').write_text(json.dumps({'protocol':resident.PROTOCOL,
                'session_control':'device-after-probe-diagnostic-v1'}),encoding='utf8')
            with patch.object(resident,'check'),patch.object(device,'ObservedDevice',FakeDevice), \
                 patch.object(device,'installation',return_value={'status':'verified'}),patch.object(device,'gates'), \
                 patch.object(device.install,'installed_hash',return_value='fixture'), \
                 patch.object(device.shared,'stage_inputs',return_value='remote'),patch.object(device,'poll'), \
                 patch.object(device,'recover',return_value={'status':'recovered'}), \
                 patch.object(device.shared,'cleanup',return_value={'status':'completed'}) as cleanup, \
                 patch.object(resident,'summarize_session',return_value={'status':'eligible_identification_only',
                             'work_calls':853,'eligibility_calls':4,'warmup_calls':8}), \
                 patch.object(resident,'freeze',side_effect=ValueError('AP model unidentified; no confirmation')), \
                 patch.object(device,'pull_file'),patch.object(resident,'progress_consumption',return_value={'fixture':True}) as consumption:
                with self.assertRaisesRegex(ValueError,'AP model unidentified'):
                    device.run(path,'NO_ADB','PC_FAKE_ONLY',plan_io.digest(path),True)
            self.assertEqual(cleanup.call_count,4)  # No second cleanup after freeze failure.
            self.assertEqual(consumption.call_args.kwargs['load_cap'],1200)
            receipt=json.loads((root/'run/FINAL_RECEIPT.json').read_text(encoding='utf8'))
            self.assertEqual(receipt['completed_sessions'],4)
            self.assertNotIn('progress_summary_error',receipt)
            self.assertIn('AP model unidentified',receipt['error'])
            self.assertFalse((root/'run/04_fixture4').exists())

    def test_new_checkpoint_module_is_in_frozen_source_identity(self):
        self.assertIn('tools/d1_energy_host_checkpoints.py',collection.HOST_FILES)
        self.assertIn('tools/d1_energy_host_checkpoints.py',state.identity())

    def fixture(self,root):
        (root/'manifest.json').write_text('{}',encoding='utf-8')
        value=dict(state_model_calibration=True,protocol=state.PROTOCOL,
            output_root=str(root/'run'),registry=str(root/'registry'),
            budget=state.BUDGET,apk_preflight={'candidate':{}},apk_sha256='fixture',
            source_files={},entries=[dict(index=0,phase='development',pair='CC_DG',
                mode='calibration',session_id='fixture',manifest='manifest.json')])
        path=root/'plan.json';path.write_text(json.dumps(value),encoding='utf-8')
        return path

    def invoke(self,path,poll_error,cleanup_error=None,progress_error=None,receipt_error=False,real_poll=False):
        original=checkpoints.atomic_new
        def write(path,value):
            if receipt_error and Path(path).name=='FINAL_RECEIPT.json':
                raise OSError('fixture final receipt write failed')
            return original(path,value)
        def interrupted_poll(*args,**kwargs):
            kwargs['checkpoint']('temperature_preparation_waiting',session_id='fixture')
            raise poll_error
        poll_patch=(nullcontext() if real_poll else patch.object(device,'poll',side_effect=interrupted_poll))
        with patch.object(state,'check'),patch.object(device,'ObservedDevice',FakeDevice), \
             patch.object(device,'installed_preflight',return_value={'status':'verified'}), \
             patch.object(device,'gates'),patch.object(device.install,'installed_hash',return_value='fixture'), \
             patch.object(device.shared,'stage_inputs',return_value='remote'), \
             poll_patch, \
             patch.object(device,'pull_file',side_effect=OSError('fixture partial recovery')), \
             patch.object(device.shared,'cleanup',side_effect=cleanup_error or OSError('fixture cleanup')), \
             patch.object(state,'progress_consumption',side_effect=progress_error or ValueError('fixture journal parse')), \
             patch.object(checkpoints,'atomic_new',side_effect=write):
            with self.assertRaises(type(poll_error)):
                device.run(path,'NO_ADB',None,plan_io.digest(path),True)

    def test_temperature_failure_keeps_original_stack_and_stop_receipt(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);path=self.fixture(root)
            with patch.object(device,'thermal',side_effect=RuntimeError('fixture AP read failed')):
                self.invoke(path,RuntimeError('fixture AP read failed'),real_poll=True)
            receipt=json.loads((root/'run/FINAL_RECEIPT.json').read_text(encoding='utf-8'))
            self.assertEqual(receipt['exception_type'],'RuntimeError')
            self.assertIn('fixture AP read failed',receipt['exception_stack'])
            self.assertIn('cleanup',receipt['host_cleanup_error'])
            self.assertIn('journal parse',receipt['progress_summary_error'])
            self.assertEqual(json.loads((root/'registry/stopped.json').read_text())['status'],'stopped_no_resume')
            stages=[json.loads(p.read_text(encoding='utf-8'))['stage'] for p in sorted((root/'run/host_checkpoints').glob('*.json'))]
            self.assertIn('launch_returned',stages)
            self.assertEqual(stages[-1],'stopped')
            with patch.object(state,'check'),self.assertRaises(FileExistsError):
                device.run(path,'NO_ADB',None,plan_io.digest(path),True)

    def test_keyboard_interrupt_and_system_exit_are_recorded(self):
        for error in (KeyboardInterrupt(),SystemExit(9)):
            with self.subTest(error=type(error).__name__),TemporaryDirectory() as tmp:
                root=Path(tmp);path=self.fixture(root)
                self.invoke(path,error)
                result=json.loads((root/'run/FINAL_RECEIPT.json').read_text(encoding='utf-8'))
                self.assertEqual(result['exception_type'],type(error).__name__)
                self.assertTrue((root/'registry/stopped.json').exists())

    def test_failed_final_write_keeps_fallback_and_registry_stop(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);path=self.fixture(root)
            self.invoke(path,TimeoutError('fixture command timeout'),receipt_error=True)
            self.assertFalse((root/'run/FINAL_RECEIPT.json').exists())
            fallback=json.loads((root/'run/FAILURE_RECEIPT_FALLBACK.json').read_text())
            self.assertIn('final receipt write failed',fallback['final_receipt_write_error'])
            self.assertEqual(json.loads((root/'registry/stopped.json').read_text())['exception_type'],'TimeoutError')

    def test_postpublication_checkpoint_error_does_not_reverse_completion(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);path=self.fixture(root)
            original=checkpoints.Checkpoints.mark
            def mark(journal,stage,**details):
                if stage=='completed':raise OSError('fixture late checkpoint failure')
                return original(journal,stage,**details)
            with patch.object(state,'check'),patch.object(device,'ObservedDevice',FakeDevice), \
                 patch.object(device,'installed_preflight',return_value={'status':'verified'}), \
                 patch.object(device,'gates'),patch.object(device.install,'installed_hash',return_value='fixture'), \
                 patch.object(device.shared,'stage_inputs',return_value='remote'), \
                 patch.object(device,'poll'),patch.object(device,'recover',return_value={'status':'recovered'}), \
                 patch.object(device.shared,'cleanup',return_value={'status':'completed'}), \
                 patch.object(state,'summarize_session',return_value={'status':'eligible_regimen_only',
                     'phase':'development','condition':'CC_DG','work_calls':1,'eligibility_calls':4,'warmup_calls':8}), \
                 patch.object(checkpoints.Checkpoints,'mark',mark):
                result=device.run(path,'NO_ADB',None,plan_io.digest(path),True)
            self.assertEqual(result['sessions'],1)
            self.assertTrue((root/'run/FINAL_RECEIPT.json').exists())
            self.assertTrue((root/'registry/completed.json').exists())
            self.assertFalse((root/'registry/stopped.json').exists())

    def test_local_subprocess_timeout_and_nonzero_keep_command_evidence(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            bad=process.run([sys.executable,'-c','import sys;sys.stderr.write("bad\\n");sys.exit(7)'],
                root/'bad',3,['fixture'],root_only=False)
            self.assertEqual((bad['status'],bad['returncode']),('nonzero_exit',7))
            self.assertIn(b'bad',(root/'bad/stderr.bin').read_bytes())
            slow=process.run([sys.executable,'-c','import time;time.sleep(5)'],
                root/'slow',.1,['fixture'],root_only=False)
            self.assertEqual(slow['status'],'timeout')
            self.assertTrue((root/'slow/result.json').exists())

    def test_abrupt_python_exit_leaves_checkpoint_but_not_receipt(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            code=('from tools.d1_energy_host_checkpoints import Checkpoints;'
                  'import os,sys;'
                  'j=Checkpoints(sys.argv[1],"fixture");'
                  'j.mark("temperature_preparation_waiting");'
                  'os._exit(19)')
            result=subprocess.run([sys.executable,'-c',code,str(root/'checkpoints')],
                                  cwd=Path(__file__).resolve().parents[1],timeout=5)
            self.assertEqual(result.returncode,19)
            self.assertEqual(json.loads((root/'checkpoints/0000.json').read_text())['stage'],
                             'temperature_preparation_waiting')
            self.assertFalse((root/'FINAL_RECEIPT.json').exists())

    @unittest.skipUnless(os.name=='nt','PowerShell entry fixture requires Windows')
    def test_powershell_entry_records_python_fixture_exit(self):
        # The rendered, real entry script is invoked. A PATH shim substitutes only
        # the device-facing Python command with a PC fault-injection test.
        for exit_code in (0,17):
            with self.subTest(exit_code=exit_code),TemporaryDirectory() as tmp:
                root=Path(tmp);bin_dir=root/'bin';bin_dir.mkdir()
                script=root/'RUN_AFTER_APPROVAL.ps1'
                script.write_text(state.render_run_script('fixture-sha'),encoding='utf-8-sig')
                (root/'collection_plan.json').write_text('{}',encoding='utf-8')
                shim=bin_dir/'python.cmd'
                shim.write_text('@echo off\r\n'
                    'echo %* > "%D1_FAKE_ARGS_PATH%"\r\n'
                    '"%D1_REAL_PYTHON%" -B -m unittest '
                    'tools.test_d1_energy_host_failure.HostFailureTest.test_temperature_failure_keeps_original_stack_and_stop_receipt -q\r\n'
                    'echo fixture native stderr 1>&2\r\n'
                    'exit /b %D1_FAKE_EXIT%\r\n',encoding='ascii')
                env=dict(os.environ,PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],
                         D1_REAL_PYTHON=sys.executable,D1_FAKE_ARGS_PATH=str(root/'args.txt'),
                         D1_FAKE_EXIT=str(exit_code))
                child=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(script),
                                      '-Action','Run','-Approved'],cwd=root,env=env,
                                     capture_output=True,text=True,timeout=20)
                self.assertEqual(child.returncode==0,exit_code==0)
                self.assertIn('--expected-sha fixture-sha',(root/'args.txt').read_text())
                entries=list(root.glob('host_entry_*'))
                self.assertEqual(len(entries),1)
                entry=entries[0]
                raw_stderr=(entry/'stderr.txt').read_bytes()
                stderr=raw_stderr.decode('utf-16' if raw_stderr.startswith(b'\xff\xfe') else 'utf-8-sig')
                self.assertEqual(json.loads((entry/'end.json').read_text(encoding='utf-8-sig'))['python_exit_code'],
                                 exit_code,child.stderr+'\n'+stderr)
                self.assertIn('fixture native stderr',stderr)
                self.assertIn('Ran 1 test',stderr)


if __name__=='__main__':unittest.main()
