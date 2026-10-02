import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tools import d1_preparation_observation as o
from tools import d1_arrival_energy_collection_device as runner


class ObservationTests(unittest.TestCase):
    def test_actual_warmup_to_common_approval_boundary(self):
        for common_approved in (False,True):
            with self.subTest(common=common_approved),tempfile.TemporaryDirectory() as tmp:
                d=SimpleNamespace(root=Path(tmp)/'commands',sequence=0,adb='FAKE',serial='fixture',deadline=time.monotonic()+100)
                listings=0;thermals=0;seen=[]
                def call(*args,**kw):
                    nonlocal listings
                    d.sequence+=1
                    if args[0]=='logcat':return SimpleNamespace(stdout=b'fixture')
                    if args[1:2]==('pidof',):return SimpleNamespace(stdout=b'42')
                    listings+=1
                    return SimpleNamespace(stdout=(b'warmup.ready.json\n' if listings==1 else b'start_ap.ready.json\n' if common_approved and listings==2 else b'cleanup.json\n'))
                d.call=call
                def thermal(*args):
                    nonlocal thermals
                    thermals+=1
                    if thermals==(3 if common_approved else 2):
                        path=d.root/f'{d.sequence:04d}'/'client';path.mkdir(parents=True);d.sequence+=1
                        (path/'result.json').write_text(json.dumps(dict(command=[d.adb,'-s',d.serial,'shell','dumpsys','thermalservice'],status='timeout',root_reaped=True,stdout_bytes=0,stderr_bytes=0,timeout_seconds=2)))
                        raise RuntimeError('thermal timeout')
                rows=[{'key':k,'result':{}} for k in runner.c.old.KEYS for _ in range(2)]
                def read(f):
                    return {'manifest_sha256':'hash'} if str(f)=='warmup.ready.json' else rows if str(f)=='warmup.json' else {}
                plan=dict(prewarmup_observation='precommon-observation-gap-v3',budget=dict(host_poll_seconds=200,adb_commands=100),screen_contract={},references={k:{'path':'ref','sha256':'hash'} for k in runner.c.old.KEYS})
                clock=iter(range(100,2000,4));d.deadline=2000
                with patch.object(runner.time,'monotonic',side_effect=lambda:next(clock)),patch.object(runner.time,'sleep'),patch.object(runner.energy_device,'thermal',side_effect=thermal),patch.object(runner.screen,'snapshot'),patch.object(runner.energy_device,'pull_file',side_effect=lambda d,r,n,f:n),patch.object(runner.p,'read',side_effect=read),patch.object(runner.p,'digest',return_value='hash'),patch.object(runner.c.old,'quality'),patch.object(runner.energy_device,'gpu_proof',return_value={}),patch.object(runner.energy_device,'arm'),patch.object(runner.d1_arrival_start_ap,'approve'):
                    if common_approved:
                        with self.assertRaisesRegex(RuntimeError,'thermal timeout'):runner.poll(d,'remote',Path(tmp),{'session_id':'fixture','start_ap_gate':runner.d1_arrival_start_ap.DIAGNOSTIC_VERSION},plan)
                    else:runner.poll(d,'remote',Path(tmp),{'session_id':'fixture'},plan)
                self.assertEqual((Path(tmp)/'prewarmup_observation_gap.json').exists(),not common_approved)

    def test_thermal_gap_requires_fresh_gate_before_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=SimpleNamespace(root=Path(tmp)/'commands',sequence=0,adb='FAKE',serial='fixture',deadline=time.monotonic()+100)
            seen=[]
            def thermal(*args):
                seen.append('thermal')
                if len(seen)==1:
                    path=d.root/'0000/client';path.mkdir(parents=True);d.sequence+=1
                    (path/'result.json').write_text(json.dumps(dict(command=[d.adb,'-s',d.serial,'shell','dumpsys','thermalservice'],status='timeout',root_reaped=True,stdout_bytes=0,stderr_bytes=0,timeout_seconds=2)))
                    raise RuntimeError('thermal timeout')
            def call(*args,**kw):
                seen.append('listing');d.sequence+=1
                return SimpleNamespace(stdout=b'cleanup.json\n')
            d.call=call
            with patch.object(runner.energy_device,'thermal',side_effect=thermal),patch.object(runner.screen,'snapshot'),patch.object(runner.time,'sleep'):
                runner.poll(d,'remote',Path(tmp),{},dict(prewarmup_observation=o.ENV_VERSION,budget=dict(host_poll_seconds=20,adb_commands=100),screen_contract={}))
            self.assertEqual(seen,['thermal','thermal','listing'])
            self.assertIn('thermal timeout',(Path(tmp)/'prewarmup_observation_gap.json').read_text())

    def test_thermal_violation_not_reclassified_as_missing(self):
        d=SimpleNamespace(sequence=0,root=Path('.'),deadline=time.monotonic()+100)
        def violated(*args):raise ValueError('host thermal gate')
        with self.assertRaisesRegex(ValueError,'host thermal gate'):o.thermal(d,Path('.'),0,{'gaps':0},False,violated)

    def test_actual_poll_tolerates_one_preapproval_gap_only(self):
        for second_timeout in (False,True):
            with self.subTest(second_timeout=second_timeout),tempfile.TemporaryDirectory() as tmp:
                d=SimpleNamespace(root=Path(tmp)/'commands',sequence=0,adb='FAKE',serial='fixture',deadline=time.monotonic()+100)
                def call(*args,**kw):
                    n=d.sequence;d.sequence+=1
                    if n==0 or second_timeout:
                        path=d.root/f'{n:04d}'/'client';path.mkdir(parents=True)
                        (path/'result.json').write_text(json.dumps(dict(command=[d.adb,'-s',d.serial,*args],status='timeout',root_reaped=True,stdout_bytes=0,stderr_bytes=0,timeout_seconds=3)))
                        raise RuntimeError('original timeout')
                    return SimpleNamespace(stdout=b'cleanup.json\n')
                d.call=call
                plan=dict(prewarmup_observation=o.VERSION,budget=dict(host_poll_seconds=20,adb_commands=100),screen_contract={})
                with patch.object(runner.energy_device,'thermal'),patch.object(runner.screen,'snapshot'),patch.object(runner.time,'sleep'),patch('subprocess.Popen',side_effect=AssertionError('real device forbidden')):
                    if second_timeout:
                        with self.assertRaisesRegex(RuntimeError,'original timeout'):runner.poll(d,'remote',Path(tmp),{},plan)
                    else:runner.poll(d,'remote',Path(tmp),{},plan)
                self.assertEqual(d.sequence,2)
                self.assertTrue((Path(tmp)/'prewarmup_observation_gap.json').exists())

    def test_after_approval_disconnect_and_unreaped_fail_closed(self):
        for armed,status,reaped,stderr in [(True,'timeout',True,0),(False,'nonzero_exit',True,13),(False,'timeout',False,0),(False,'timeout',True,13)]:
            with self.subTest(armed=armed,status=status,reaped=reaped,stderr=stderr),tempfile.TemporaryDirectory() as tmp:
                d=SimpleNamespace(root=Path(tmp)/'commands',sequence=0,adb='FAKE',serial='fixture',deadline=time.monotonic()+100)
                def call(*args,**kw):
                    path=d.root/'0000/client';path.mkdir(parents=True);d.sequence+=1
                    (path/'result.json').write_text(json.dumps(dict(command=[d.adb,'-s',d.serial,*args],status=status,root_reaped=reaped,stdout_bytes=0,stderr_bytes=stderr,timeout_seconds=3)))
                    raise RuntimeError('original')
                d.call=call
                with self.assertRaisesRegex(RuntimeError,'original'):o.listing(d,'remote',Path(tmp),'package',{'gaps':0},armed)
                self.assertFalse((Path(tmp)/'prewarmup_observation_gap.json').exists())

    def test_old_protocol_remains_fail_fast(self):
        d=SimpleNamespace(sequence=0,deadline=time.monotonic()+100)
        d.call=lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('unchanged'))
        with patch.object(runner.energy_device,'thermal'),patch.object(runner.screen,'snapshot'):
            with self.assertRaisesRegex(RuntimeError,'unchanged'):
                runner.poll(d,'remote',Path('.'),{},dict(budget=dict(host_poll_seconds=20,adb_commands=100),screen_contract={}))


if __name__=='__main__':unittest.main()
