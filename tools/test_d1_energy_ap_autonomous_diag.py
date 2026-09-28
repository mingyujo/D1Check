"""PC entry-boundary checks; no ADB client is launched."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_arrival_plan as p
from tools import d1_energy_ap_autonomous_diag as diag
from tools import d1_energy_collection_device as device
from tools import d1_energy_state_collection as state


class FakeDevice:
    def __init__(self,*args,**kwargs):
        self.deadline=None
        self.sequence=0
        self.command_limit=None
    def call(self,*args,**kwargs):
        self.sequence+=1
        return subprocess.CompletedProcess(args,0,b'',b'')


class AutonomousDiagnosticTest(unittest.TestCase):
    def fixture(self,root):
        manifest=root/'manifest.json'
        manifest.write_text(json.dumps(dict(session_control=diag.CONTROL,autonomous_diagnostic_only=True)),encoding='utf-8')
        plan=root/'plan.json'
        plan.write_text(json.dumps(dict(state_model_calibration=True,autonomous_diagnostic_only=True,
            diagnostic_only=True,protocol=state.PROTOCOL,experiment_id=diag.EXPERIMENT,
            output_root=str(root/'run'),registry=str(root/'registry'),budget=diag.BUDGET,
            apk_preflight={'candidate':{}},apk_sha256='fixture',source_files={},entries=[dict(
                index=0,phase='confirmation',pair='CG_DC',mode='calibration',session_id='fixture',
                manifest=manifest.name)])),encoding='utf-8')
        return plan

    def common(self):
        return (patch.object(diag,'check'),patch.object(device,'ObservedDevice',FakeDevice),
                patch.object(device,'installation',return_value={'status':'verified'}),
                patch.object(device,'gates'),patch.object(device.install,'installed_hash',return_value='fixture'),
                patch.object(device.shared,'stage_inputs',return_value='remote'))

    def test_one_session_completes_without_freeze_or_confirmation_evaluation(self):
        diag.budget_check()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.fixture(root)
            a,b,c,d,e,f=self.common()
            with a,b,c,d,e,f,patch.object(device,'poll') as poll,\
                 patch.object(device,'recover',return_value={'status':'recovered'}),\
                 patch.object(device.shared,'cleanup',return_value={'status':'completed'}),\
                 patch.object(state,'summarize_session',return_value=dict(
                     status='eligible_regimen_only',condition='CG_DC',work_calls=1,
                     eligibility_calls=4,warmup_calls=8)),\
                 patch.object(state,'freeze',side_effect=AssertionError('diagnostic must not fit')):
                result=device.run(plan,'NO_ADB',None,p.digest(plan),True)
            self.assertEqual(result['sessions'],1)
            self.assertEqual(result['status'],'completed_regimen_diagnostic_only')
            self.assertEqual(poll.call_count,1)
            self.assertFalse((root/'run/development_freeze.json').exists())
            self.assertTrue((root/'registry/completed.json').exists())

    def test_lost_observation_after_arm_intent_does_not_force_stop_or_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=self.fixture(root)
            def lose(_,__,folder,*args,**kwargs):
                (folder/'autonomous_segment_arm_intent.json').write_text('{}',encoding='utf-8')
                raise RuntimeError('fixture error: closed')
            a,b,c,d,e,f=self.common()
            with a,b,c,d,e,f,patch.object(device,'poll',side_effect=lose),\
                 patch.object(device,'pull_file',side_effect=OSError('fixture recovery unavailable')),\
                 patch.object(device.shared,'cleanup') as cleanup,\
                 self.assertRaisesRegex(RuntimeError,'fixture error: closed'):
                device.run(plan,'NO_ADB',None,p.digest(plan),True)
            receipt=json.loads((root/'run/FINAL_RECEIPT.json').read_text(encoding='utf-8'))
            self.assertEqual(receipt['status'],'stopped_no_resume')
            self.assertEqual(receipt['host_cleanup']['status'],'deferred_device_segment_may_be_active')
            self.assertIn('fixture error: closed',receipt['exception_stack'])
            cleanup.assert_not_called()
            self.assertFalse((root/'registry/completed.json').exists())
            with patch.object(diag,'check'),self.assertRaises(FileExistsError):
                device.run(plan,'NO_ADB',None,p.digest(plan),True)

    def test_real_poll_arms_preparation_but_only_observes_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'input_manifest.json').write_text('{}',encoding='utf-8')
            sha=p.digest(folder/'input_manifest.json')
            (folder/'thermal.jsonl').write_text(''.join(json.dumps({'mono_ns':x,'AP':'30.0'})+'\n'
                for x in range(110, 270, 6)),encoding='utf-8')
            keys=sorted(device.c.KEYS)
            warm=[dict(key=k,result={}) for k in keys for _ in range(2)]
            listing_count=[0]
            class ListingDevice:
                deadline=__import__('time').monotonic()+15
                def call(self,*args,**kwargs):
                    if args[:3]==('shell','run-as',device.legacy.PACKAGE) and args[3]=='ls':
                        listing_count[0]+=1
                        names=('warmup.ready.json\nserial_probe.ready.json\nprobe.ready.json\n'
                            if listing_count[0]==1 else 'baseline.ready.json\n'
                            if listing_count[0]==2 else 'cleanup.json\n')
                        return subprocess.CompletedProcess(args,0,names.encode(),b'')
                    if args[:2]==('shell','pidof'):
                        return subprocess.CompletedProcess(args,0,b'1234\n',b'')
                    return subprocess.CompletedProcess(args,0,b'',b'')
            def pulled(_,remote,name,target):
                target.mkdir(parents=True,exist_ok=True)
                value=(dict(manifest_sha256=sha,mono_ns=100) if name.endswith('.ready.json') else
                    warm if name=='warmup.json' else
                    [{'id':'probe-0','key':keys[0]}] if name.endswith('.requests.json') else
                    [{'kind':'phase_start','phase':'resident_baseline','mono_ns':100},
                     {'kind':'phase_end','phase':'resident_baseline','mono_ns':300}] if name=='progress.jsonl' else {})
                path=target/name
                if name=='progress.jsonl':path.write_text(''.join(json.dumps(x)+'\n' for x in value),encoding='utf-8')
                else:path.write_text(json.dumps(value),encoding='utf-8')
                return path
            arms=[]
            m=dict(session_control=diag.CONTROL,autonomous_diagnostic_only=True,
                   mode='calibration',pair='CG_DC',session_id='fixture')
            plan=dict(autonomous_diagnostic_only=True,diagnostic_only=True,
                      operational_only=True,temperature_preparation={'max_wait_seconds':360},
                      budget={'host_poll_seconds':10},screen_contract={},
                      references={key:{'path':str(folder/'input_manifest.json')} for key in keys})
            sensor=dict(mono_ns=250,after_ns=260,AP='30.0')
            with patch.object(device,'thermal',return_value=sensor),\
                 patch.object(device.screen,'snapshot'),patch.object(device,'pull_file',side_effect=pulled),\
                 patch.object(device,'gpu_proof',return_value={}),\
                 patch.object(device.c,'quality'),patch.object(device.c,'validate_rows'),\
                 patch.object(device.c.operational_rules,'probe_specs',return_value=[('eligibility_serial_probe','serial')]),\
                 patch.object(device.c.operational_rules,'assess',return_value={'ready':True,'reason':'ready'}),\
                 patch.object(device,'arm',side_effect=lambda *a:arms.append(a[2])),\
                 patch.object(device.time,'sleep'):
                device.poll(ListingDevice(),'remote',folder,m,plan)
            self.assertEqual(arms,['warmup','serial_probe','probe'])
            self.assertTrue((folder/'autonomous_segment_arm_intent.json').exists())
            self.assertTrue((folder/'gate_baseline/observation_receipt.json').exists())
            self.assertFalse((folder/'gate_baseline/arm_receipt.json').exists())

    def test_stopped_recovery_requires_host_exit_and_exact_terminal_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);apk=root/'candidate.apk';apk.write_bytes(b'fixture-apk')
            plan_file=root/'plan.json';sid='fixture-session';mf=root/'manifest.json'
            mf.write_text('{}',encoding='utf-8')
            (root/'registry').mkdir()
            run=root/'run';session=run/f'00_{sid}';session.mkdir(parents=True)
            (session/'launch_attempt.json').write_text('{}',encoding='utf-8')
            (session/'autonomous_segment_arm_intent.json').write_text(json.dumps(dict(
                session_id=sid,manifest_sha256=p.digest(mf))),encoding='utf-8')
            plan=dict(experiment_id=diag.EXPERIMENT,autonomous_diagnostic_only=True,
                source_code=diag.identity(),apk_path=str(apk),apk_sha256=p.digest(apk),
                output_root=str(run),registry=str(root/'registry'),device_fingerprint='A24-fixture',
                device_hardware_serial='hardware-fixture',entries=[dict(index=0,session_id=sid,
                    manifest_sha256=p.digest(mf))])
            plan_file.write_text(json.dumps(plan),encoding='utf-8')
            host_identity=dict(child=dict(status='present',pid=31,creation_date='start',
                executable='python.exe',command_line='diagnostic'),parent=dict(status='present',pid=30,
                creation_date='start',executable='powershell.exe',command_line='wrapper'))
            (root/'registry/claimed.json').write_text(json.dumps(dict(
                plan_sha256=p.digest(plan_file),host_run_id='fixture-host',
                host_identity=host_identity)),encoding='utf-8')
            (root/'registry/stopped.json').write_text('{}',encoding='utf-8')
            (run/'host_checkpoints').mkdir()
            (run/'host_checkpoints/0000.json').write_text(json.dumps(dict(
                stage='claimed',plan_sha256=p.digest(plan_file),host_run_id='fixture-host',
                host_identity=host_identity)),encoding='utf-8')
            out=root/(diag.RUN_FOLDER+'_read_only_recovery');calls=[]
            class RecoveryDevice(FakeDevice):
                def identify(self,fingerprint):
                    calls.append(('identify',fingerprint));return dict(serial='fixture-transport')
                def call(self,*args,**kwargs):
                    calls.append(args);self.sequence+=1
                    return subprocess.CompletedProcess(args,0,b'hardware-fixture\n',b'')
            def pulled(_,remote,name,folder):
                calls.append(('pull',name,remote))
                folder.mkdir(parents=True,exist_ok=True);target=folder/name
                target.write_text('{}' if name=='manifest.json' else '{"status":"completed"}',encoding='utf-8')
                return target
            def active(pid):return host_identity['child'] if pid==31 else host_identity['parent']
            def exited(pid):return dict(status='absent',pid=pid)
            with patch.object(device,'pull_file',side_effect=pulled) as pull:
                with self.assertRaisesRegex(ValueError,'original host active'):
                    diag.recover_stopped(plan_file,'NO_ADB',out,query=active,device_factory=RecoveryDevice)
                pull.assert_not_called()
            self.assertFalse(out.exists())
            with patch.object(device,'pull_file',side_effect=pulled),\
                 patch.object(device,'recover',return_value={'status':'recovered'}) as archive:
                result=diag.recover_stopped(plan_file,'NO_ADB',out,query=exited,device_factory=RecoveryDevice)
            self.assertEqual(result['status'],'same_session_recovered')
            self.assertEqual(result['app_terminal'],'completed')
            self.assertTrue((root/'registry/read_only_recovery_claim/claimed.json').exists())
            archive.assert_called_once()
            self.assertEqual(archive.call_args.args[1],f'files/{state.PROTOCOL}/{sid}')
            self.assertFalse(any('am' in item or 'force-stop' in item for item in calls))
            with self.assertRaisesRegex(ValueError,'one fixed read-only'):
                diag.recover_stopped(plan_file,'NO_ADB',out,query=exited,device_factory=RecoveryDevice)


if __name__=='__main__':unittest.main()
