"""PC-only fault injection for host identity, one-shot rescue and real entry script."""

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from tools import d1_arrival_plan as p
from tools import d1_energy_host_checkpoints as checkpoints
from tools import d1_energy_host_lifecycle as lifecycle
from tools import d1_energy_host_recovery as recovery
from tools import d1_energy_host_diagnostic as diagnostic
from tools import d1_energy_collection_device as runner
from tools.d1_adb_observed_client import ObservedDevice


def identity(pid):
    return dict(status='present',pid=pid,creation_date=f'time-{pid}',
                executable='python.exe',command_line='python -m fixture')


class FakeDevice:
    def __init__(self,*args,**kwargs):self.sequence=0;self.deadline=None;self.command_limit=None
    def identify(self,fingerprint):return dict(model='SM-A245N',fingerprint=fingerprint,serial='fixture')
    def call(self,*args,**kwargs):
        self.sequence+=1
        stdout=(b'123\n' if args[:2]==('shell','pidof') else
                (runner.ACTIVITY+' session_id=fixture').encode() if args[:3]==('shell','dumpsys','activity') else
                b'fixture-hardware\n')
        return subprocess.CompletedProcess(args,0,stdout,b'')


class LifecycleTest(unittest.TestCase):
    def test_exact_process_identity_and_parent_child_independence(self):
        self.assertEqual(lifecycle.identity_state(identity(11),lambda pid:identity(pid)),'active')
        self.assertEqual(lifecycle.identity_state(identity(11),lambda pid:dict(status='absent')),'exited')
        changed=dict(identity(11),creation_date='later')
        self.assertEqual(lifecycle.identity_state(identity(11),lambda pid:changed),'replaced')
        self.assertEqual(lifecycle.identity_state(identity(11),lambda pid:dict(status='query_failed')),'unknown')
        with TemporaryDirectory() as temp:
            root=Path(temp);registry=root/'registry';registry.mkdir()
            (root/'run').mkdir()
            bound=dict(child=identity(11),parent=identity(22))
            checkpoints.atomic_new(registry/'claimed.json',dict(plan_sha256='sha',host_run_id='run',
                                                                host_identity=bound))
            journal=checkpoints.Checkpoints(root/'run/host_checkpoints','sha','run',
                                           bound)
            journal.mark('temperature_preparation_waiting')
            self.assertEqual(lifecycle.inspect_run(root/'run',registry,'sha',
                lambda pid: identity(pid) if pid==11 else dict(status='absent'))['status'],'active')
            self.assertTrue(lifecycle.inspect_run(root/'run',registry,'sha',
                lambda pid: dict(status='absent'))['recoverable'])
            self.assertFalse(lifecycle.inspect_run(root/'run',registry,'sha',
                lambda pid: dict(status='query_failed'))['recoverable'])
            checkpoints.atomic_new(registry/'completed.json',{'status':'completed'})
            self.assertFalse(lifecycle.inspect_run(root/'run',registry,'sha',
                lambda pid: dict(status='absent'))['recoverable'])

    def test_real_live_child_cannot_be_recovered_from_old_heartbeat(self):
        if os.name!='nt':self.skipTest('Windows creation identity')
        child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(3)'],
                               stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            snapshot=lifecycle.process_snapshot(child.pid)
            self.assertEqual(snapshot['status'],'present')
            self.assertEqual(lifecycle.identity_state(snapshot),'active')
        finally:
            child.terminate();child.wait(timeout=5)

    def test_one_shot_recovery_keeps_original_and_followup_failures(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);plan=root/'plan.json';out=root/'rescue';run=root/'run';reg=root/'registry'
            plan.write_text(json.dumps(dict(output_root=str(run),registry=str(reg),
                entries=[dict(index=0,session_id='fixture')],protocol='fixture-protocol',
                device_fingerprint='fixture',device_hardware_serial='fixture-hardware')))
            (run/'00_fixture').mkdir(parents=True);(run/'00_fixture/launch_attempt.json').write_text('{}')
            gate=dict(status='host_exited',recoverable=True)
            with patch.object(recovery.lifecycle,'inspect_run',return_value=gate), \
                 patch.object(recovery,'remaining_budget',return_value=150), \
                 patch.object(recovery,'ObservedDevice',FakeDevice), \
                 patch.object(recovery.collection,'pull_file',side_effect=OSError('prefix failed')), \
                 patch.object(recovery.shared,'cleanup',side_effect=OSError('cleanup failed')), \
                 patch.object(recovery.collection,'recover',side_effect=OSError('archive failed')):
                result=recovery.run(plan,out,'NO_ADB',p.digest(plan),True,150)
                self.assertEqual(result['status'],'partial_or_unconfirmed')
                self.assertIn('cleanup failed',result['host_cleanup_error'])
                self.assertIn('archive failed',result['recovery_error'])
                self.assertTrue((out/'RECOVERY_RECEIPT.json').exists())
                again=recovery.run(plan,out,'NO_ADB',p.digest(plan),True,150)
                self.assertEqual(again['status'],result['status'])
            self.assertEqual(len(list(out.glob('commands/*'))),0)

    def test_active_run_blocks_device_and_claim(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);plan=root/'plan.json';out=root/'rescue'
            plan.write_text(json.dumps(dict(output_root=str(root/'run'),registry=str(root/'registry'),entries=[])))
            with patch.object(recovery.lifecycle,'inspect_run',return_value=dict(status='active',recoverable=False)), \
                 patch.object(recovery,'ObservedDevice',side_effect=AssertionError('device reached')):
                value=recovery.run(plan,out,'NO_ADB',p.digest(plan),True,150)
            self.assertEqual(value['status'],'recovery_blocked')
            self.assertFalse(out.exists())

    def test_recovery_cannot_stop_unidentified_app(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);plan=root/'plan.json';out=root/'rescue';run=root/'run'
            (run/'00_fixture').mkdir(parents=True);(run/'00_fixture/launch_attempt.json').write_text('{}')
            plan.write_text(json.dumps(dict(output_root=str(run),registry=str(root/'registry'),
                entries=[dict(index=0,session_id='fixture')],protocol='fixture-protocol',
                device_fingerprint='fixture',device_hardware_serial='fixture-hardware')))
            class OtherApp(FakeDevice):
                def call(self,*args,**kwargs):
                    if args[:3]==('shell','dumpsys','activity'):
                        self.sequence+=1
                        return subprocess.CompletedProcess(args,0,b'unrelated session',b'')
                    return super().call(*args,**kwargs)
            with patch.object(recovery.lifecycle,'inspect_run',return_value=dict(status='host_exited',recoverable=True)), \
                 patch.object(recovery,'remaining_budget',return_value=150), \
                 patch.object(recovery,'ObservedDevice',OtherApp), \
                 patch.object(recovery.collection,'pull_file',side_effect=OSError('prefix missing')), \
                 patch.object(recovery.collection,'recover',return_value={'status':'recovered'}), \
                 patch.object(recovery.shared,'cleanup',side_effect=AssertionError('foreign app stopped')):
                value=recovery.run(plan,out,'NO_ADB',p.digest(plan),True,150)
            self.assertEqual(value['status'],'partial_or_unconfirmed')
            self.assertFalse(value['host_requested_stop'])

    def test_command_budget_blocks_before_adb_client(self):
        with TemporaryDirectory() as temp:
            d=ObservedDevice('NO_ADB','fixture',Path(temp)/'commands')
            d.command_limit=0
            with self.assertRaisesRegex(RuntimeError,'slot cap'):
                d.call('shell','echo','should-not-run')
            self.assertFalse((Path(temp)/'commands').exists())

    def test_diagnostic_failure_retains_original_after_cleanup_and_receipt_failure(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);plan=root/'plan.json';mf=root/'manifest.json'
            mf.write_text(json.dumps(dict(session_id='fixture',pair='CC_DG')))
            plan.write_text(json.dumps(dict(output_root=str(root/'run'),registry=str(root/'registry'),
                protocol='fixture-protocol',device_fingerprint='fixture',device_hardware_serial='fixture-hardware',
                apk_sha256='sha',apk_preflight=dict(candidate={}),source_files={},
                entries=[dict(index=0,session_id='fixture',manifest='manifest.json')],budget=diagnostic.BUDGET)))
            original=checkpoints.atomic_new
            def write(path,value):
                if Path(path).name=='FINAL_RECEIPT.json':raise OSError('receipt media failure')
                return original(path,value)
            with patch.object(diagnostic,'check',return_value={'status':'ready'}), \
                 patch.object(diagnostic,'ObservedDevice',FakeDevice), \
                 patch.object(runner,'installed_preflight',return_value={'status':'verified'}), \
                 patch.object(runner,'gates'),patch.object(runner.install,'installed_hash',return_value='sha'), \
                 patch.object(diagnostic.shared,'stage_inputs',return_value='remote'), \
                 patch.object(runner,'poll',side_effect=RuntimeError('AP preparation failure')), \
                 patch.object(runner,'pull_file',side_effect=OSError('partial retrieval failed')), \
                 patch.object(diagnostic.shared,'cleanup',side_effect=OSError('cleanup failed')), \
                 patch.object(runner,'recover',side_effect=OSError('archive failed')), \
                 patch.object(checkpoints,'atomic_new',side_effect=write):
                value=diagnostic.run(plan,'NO_ADB',None,p.digest(plan),True)
            self.assertEqual(value['status'],'stopped_no_resume')
            self.assertIn('AP preparation failure',value['exception_stack'])
            self.assertIn('cleanup failed',value['host_cleanup_error'])
            self.assertIn('archive failed',value['recovery_error'])
            self.assertTrue((root/'run/FAILURE_RECEIPT_FALLBACK.json').exists())
            self.assertTrue((root/'registry/stopped.json').exists())

    def test_diagnostic_session_stops_before_baseline_and_consumes_once(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);plan=root/'plan.json';mf=root/'manifest.json'
            mf.write_text(json.dumps(dict(session_id='fixture',pair='CC_DG')))
            plan.write_text(json.dumps(dict(output_root=str(root/'run'),registry=str(root/'registry'),
                protocol='fixture-protocol',device_fingerprint='fixture',device_hardware_serial='fixture-hardware',
                apk_sha256='sha',apk_preflight=dict(candidate={}),source_files={},
                entries=[dict(index=0,session_id='fixture',manifest='manifest.json')],
                budget=diagnostic.BUDGET)))
            def recovered(_device,_remote,dest,*args):
                dest=Path(dest);dest.mkdir(parents=True)
                rows=[]
                for i in range(4):
                    rows.extend((dict(kind='runtime_start',key=str(i)),dict(kind='runtime_return',key=str(i))))
                for i in range(8):
                    rows.extend((dict(kind='warmup_start',id=str(i)),dict(kind='warmup_return',id=str(i))))
                for i in range(4):
                    rows.extend((dict(kind='request_start',phase='eligibility_parallel_probe',id=str(i)),
                                 dict(kind='lane_available',phase='eligibility_parallel_probe',id=str(i))))
                (dest/'progress.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
                return {'status':'recovered'}
            with patch.object(diagnostic,'check',return_value={'status':'ready'}), \
                 patch.object(diagnostic,'ObservedDevice',FakeDevice), \
                 patch.object(runner,'installed_preflight',return_value={'status':'verified'}), \
                 patch.object(runner,'gates'),patch.object(runner.install,'installed_hash',return_value='sha'), \
                 patch.object(diagnostic.shared,'stage_inputs',return_value='remote'), \
                 patch.object(runner,'poll',return_value=dict(status='preparation_observed_host_stop_required',assessment={'ready':True})), \
                 patch.object(runner,'pull_file',side_effect=OSError('missing app cleanup')), \
                 patch.object(diagnostic.shared,'cleanup',return_value={'status':'completed'}), \
                 patch.object(runner,'recover',side_effect=recovered):
                value=diagnostic.run(plan,'NO_ADB',None,p.digest(plan),True)
            self.assertEqual(value['status'],'observed_preparation_host_stop')
            self.assertEqual((value['confirmed_baseline_calls'],value['confirmed_load_calls']),(0,0))
            self.assertEqual(value['app_cleanup'],'unconfirmed')
            self.assertTrue((root/'registry/stopped.json').exists())
            with self.assertRaises(FileExistsError):
                with patch.object(diagnostic,'check',return_value={'status':'ready'}):
                    diagnostic.run(plan,'NO_ADB',None,p.digest(plan),True)

    @unittest.skipUnless(os.name=='nt','PowerShell entry fixture requires Windows')
    def test_rendered_entry_crosses_real_powershell_python_fixture(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);bin_dir=root/'bin';bin_dir.mkdir()
            script=root/'RUN_AFTER_APPROVAL.ps1'
            script.write_text(diagnostic.render_script('fixture-sha'),encoding='utf-8-sig')
            (root/'diagnostic_plan.json').write_text('{}')
            self.assertIn("'diagnostic_plan.json'",script.read_text(encoding='utf-8-sig'))
            shim=bin_dir/'python.cmd'
            shim.write_text('@echo off\r\n'
                'echo %D1_ENERGY_HOST_RUN_ID% > "%D1_FAKE_RUN_ID%"\r\n'
                '"%D1_REAL_PYTHON%" -B -m unittest tools.test_d1_energy_host_lifecycle.LifecycleTest.test_diagnostic_session_stops_before_baseline_and_consumes_once -q\r\n'
                'exit /b %D1_FAKE_EXIT%\r\n',encoding='ascii')
            env=dict(os.environ,PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],
                     D1_REAL_PYTHON=sys.executable,D1_FAKE_RUN_ID=str(root/'run_id.txt'),D1_FAKE_EXIT='17')
            proc=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(script),
                '-Action','Run','-Approved'],cwd=root,env=env,capture_output=True,text=True,timeout=30)
            self.assertNotEqual(proc.returncode,0)
            entry=list(root.glob('host_entry_*'))[0]
            start=json.loads((entry/'start.json').read_text(encoding='utf-8-sig'))
            end=json.loads((entry/'end.json').read_text(encoding='utf-8-sig'))
            self.assertEqual(start['host_run_id'],end['host_run_id'])
            self.assertEqual(start['host_run_id'],(root/'run_id.txt').read_text().strip())
            self.assertEqual(end['python_exit_code'],17)

    @unittest.skipUnless(os.name=='nt','Windows PowerShell parent lifecycle')
    def test_parent_exit_does_not_imply_child_exit_or_cleanup(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);bin_dir=root/'bin';bin_dir.mkdir()
            script=root/'RUN_AFTER_APPROVAL.ps1'
            script.write_text(diagnostic.render_script('fixture-sha'),encoding='utf-8-sig')
            (root/'diagnostic_plan.json').write_text('{}')
            fake=root/'fake_child.py'
            fake.write_text('import os,time,pathlib\n'
                'root=pathlib.Path(os.environ["D1_CHILD_MARK_ROOT"])\n'
                '(root/"child_started").write_text(str(os.getpid()))\n'
                'time.sleep(2)\n'
                '(root/"child_finished").write_text("completed")\n')
            (bin_dir/'python.cmd').write_text('@echo off\r\n"%D1_REAL_PYTHON%" "%D1_FAKE_CHILD%"\r\n',encoding='ascii')
            env=dict(os.environ,PATH=str(bin_dir)+os.pathsep+os.environ['PATH'],
                     D1_REAL_PYTHON=sys.executable,D1_FAKE_CHILD=str(fake),D1_CHILD_MARK_ROOT=str(root))
            parent=subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-File',str(script),
                '-Action','Run','-Approved'],cwd=root,env=env,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                until=time.monotonic()+10
                while not (root/'child_started').exists() and time.monotonic()<until:time.sleep(.05)
                self.assertTrue((root/'child_started').exists())
                parent.kill();parent.wait(timeout=5)
                until=time.monotonic()+5
                while not (root/'child_finished').exists() and time.monotonic()<until:time.sleep(.05)
                self.assertTrue((root/'child_finished').exists())
                entry=list(root.glob('host_entry_*'))[0]
                self.assertFalse((entry/'end.json').exists())
            finally:
                if parent.poll() is None:parent.kill();parent.wait(timeout=5)


if __name__=='__main__':unittest.main()
