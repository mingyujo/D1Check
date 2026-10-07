"""PC-only real poll entry, actual silent-timeout fixture, no device capability."""
import copy
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools import d1_arrival_energy_collection_device as runner
from tools import d1_postapproval_observation as observe

FIXTURE=Path(__file__).resolve().parents[1]/'docs/results/history_control_plan_01/run_v2/timeout_fixture.json'


class Clock:
    def __init__(self):self.now=100.
    def monotonic(self):return self.now
    def sleep(self,seconds):self.now+=seconds


class PostapprovalTests(unittest.TestCase):
    def exercise(self,tmp,*,optin=True,second=False,thermal_failure=False,screen_failure=False,deadline=400.,cap=100):
        folder=Path(tmp);clock=Clock();calls=[]
        d=SimpleNamespace(root=folder/'commands',sequence=0,adb='FAKE',serial='fixture',deadline=1000.,bundle_checkpoint=Mock())
        listings=0;listing_times=[]
        def call(*args,**kwargs):
            nonlocal listings
            index=d.sequence;d.sequence+=1;calls.append(args[0]);clock.now+=.1
            if args[0]=='logcat':return SimpleNamespace(stdout=b'fixture')
            if args[:2]==('shell','pidof'):return SimpleNamespace(stdout=b'42')
            listings+=1
            listing_times.append(clock.now)
            if listings==3 or (second and listings==4):
                p=d.root/f'{index:04d}'/'client';p.mkdir(parents=True)
                result=copy.deepcopy(json.loads(FIXTURE.read_text())['result']);result['command']=[d.adb,'-s',d.serial,*args]
                (p/'result.json').write_text(json.dumps(result));clock.now+=3
                raise RuntimeError('actual fixture silent timeout')
            return SimpleNamespace(stdout=b'warmup.ready.json\n' if listings==1 else b'start_ap.ready.json\n' if listings==2 else b'cleanup.json\n')
        d.call=call
        def thermal(*args):
            calls.append('thermal')
            if thermal_failure and (folder/'postapproval_observation_gap.json').exists():raise RuntimeError('mandatory thermal unknown')
        def screen(*args):
            calls.append('screen')
            if screen_failure and (folder/'postapproval_observation_gap.json').exists():raise ValueError('mandatory screen violation')
        values=[dict(key=k,result={}) for k in runner.c.old.KEYS for _ in range(2)]
        def read(f):return {'manifest_sha256':'hash'} if str(f)=='warmup.ready.json' else values if str(f)=='warmup.json' else {}
        plan=dict(history_control=True,online_policy_study=True,prewarmup_observation='precommon-observation-gap-v3',
            budget=dict(host_poll_seconds=deadline-100,adb_commands=cap,per_session_adb_commands=cap,adb_recovery_cleanup_reserve=10),
            entries=[dict(index=0,session_id='fixture')],screen_contract={},references={k:dict(path='ref',sha256='hash') for k in runner.c.old.KEYS})
        if optin:plan['postapproval_observation']=observe.VERSION
        manifest=dict(session_id='fixture',history_control_version='registered-history-control-v1',start_ap_gate='numeric-ap-observe-v2')
        with ExitStack() as stack:
            for obj,name,opts in [(runner.time,'monotonic',dict(side_effect=clock.monotonic)),(runner.time,'sleep',dict(side_effect=clock.sleep)),
                (runner.energy_device,'thermal',dict(side_effect=thermal)),(runner.screen,'snapshot',dict(side_effect=screen)),
                (runner.energy_device,'pull_file',dict(side_effect=lambda d,r,n,f:n)),(runner.p,'read',dict(side_effect=read)),
                (runner.p,'digest',dict(return_value='hash')),(runner.c.old,'quality',{}),(runner.energy_device,'gpu_proof',dict(return_value={})),
                (runner.energy_device,'arm',{}),(runner.d1_arrival_start_ap,'approve',{})]:
                stack.enter_context(patch.object(obj,name,**opts))
            stack.enter_context(patch('subprocess.Popen',side_effect=AssertionError('real process/device forbidden')))
            try:runner.poll(d,'remote',folder,manifest,plan)
            except BaseException as error:return dict(error=error,calls=calls,listing_times=listing_times,arm=runner.energy_device.arm.call_count,approve=runner.d1_arrival_start_ap.approve.call_count,sequence=d.sequence)
            return dict(error=None,calls=calls,listing_times=listing_times,arm=runner.energy_device.arm.call_count,approve=runner.d1_arrival_start_ap.approve.call_count,sequence=d.sequence)

    def test_actual_poll_one_gap_refreshes_environment_no_duplicate_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.exercise(tmp);self.assertIsNone(r['error']);self.assertEqual((r['arm'],r['approve']),(1,1))
            evidence=json.loads((Path(tmp)/'postapproval_observation_gap.json').read_text())
            self.assertIn('actual fixture silent timeout',evidence['original_stack']);self.assertEqual(evidence['used_gaps'],1)
            self.assertEqual(r['calls'][-3:],['thermal','screen','shell'])
            self.assertGreaterEqual(r['listing_times'][3]-r['listing_times'][2],5)
            self.assertFalse((Path(tmp)/'prewarmup_observation_gap.json').exists())

    def test_second_listing_gap_is_fatal_original_evidence_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.exercise(tmp,second=True);self.assertIsInstance(r['error'],RuntimeError)
            self.assertIn('silent timeout',str(r['error']));self.assertEqual((r['arm'],r['approve']),(1,1))
            self.assertEqual(json.loads((Path(tmp)/'postapproval_observation_gap.json').read_text())['used_gaps'],1)

    def test_mandatory_environment_failures_never_reach_next_progress_query(self):
        for name in ['thermal_failure','screen_failure']:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                r=self.exercise(tmp,**{name:True});self.assertIn('mandatory',str(r['error']))
                self.assertEqual(r['sequence'],5) # warmup listing, pid, logcat, AP ready, failed listing

    def test_legacy_armed_listing_remains_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.exercise(tmp,optin=False);self.assertIsInstance(r['error'],RuntimeError)
            self.assertFalse((Path(tmp)/'postapproval_observation_gap.json').exists())

    def test_command_reserve_prevents_next_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.exercise(tmp,cap=15);self.assertIn('cap reserve',str(r['error']))
            self.assertEqual(r['sequence'],5)

    def test_short_remaining_poll_time_does_not_accept_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.exercise(tmp,deadline=120);self.assertIn('silent timeout',str(r['error']))
            self.assertFalse((Path(tmp)/'postapproval_observation_gap.json').exists())

    def test_context_and_unknown_version_block_before_device_call(self):
        for plan,manifest in [(dict(postapproval_observation='unknown'),{}),
            (dict(postapproval_observation=observe.VERSION,history_control=True),dict(history_control_version='wrong',start_ap_gate='numeric-ap-observe-v2'))]:
            d=SimpleNamespace(call=Mock(side_effect=AssertionError('no device call')))
            with self.assertRaisesRegex(ValueError,'context mismatch'):runner.poll(d,'remote',Path('.'),manifest,plan)
            d.call.assert_not_called()

    def test_only_exact_reaped_silent_timeout_is_eligible(self):
        for changes in [dict(root_reaped=False),dict(stdout_bytes=1),dict(stderr_bytes=13),dict(status='nonzero_exit'),dict(returncode=None),dict(timeout_seconds=4),dict(command=['wrong'])]:
            with self.subTest(changes=changes),tempfile.TemporaryDirectory() as tmp:
                d=SimpleNamespace(root=Path(tmp)/'commands',sequence=0,adb='FAKE',serial='fixture',deadline=1000)
                def call(*args,**kwargs):
                    p=d.root/'0000/client';p.mkdir(parents=True);d.sequence+=1
                    result=copy.deepcopy(json.loads(FIXTURE.read_text())['result']);result['command']=[d.adb,'-s',d.serial,*args];result.update(changes)
                    (p/'result.json').write_text(json.dumps(result));raise RuntimeError('original fixture failure')
                d.call=call
                with patch.object(observe.time,'monotonic',return_value=100):
                    with self.assertRaisesRegex(RuntimeError,'original fixture'):observe.listing(d,'remote',Path(tmp),runner.legacy.PACKAGE,dict(gaps=0),400)
                self.assertFalse((Path(tmp)/'postapproval_observation_gap.json').exists())

    def test_recording_failure_keeps_original_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'postapproval_observation_gap.json').write_text('previous evidence')
            r=self.exercise(tmp);self.assertIn('silent timeout',str(r['error']))
            self.assertEqual((Path(tmp)/'postapproval_observation_gap.json').read_text(),'previous evidence')
            self.assertIsInstance(r['error'].__cause__,FileExistsError)


if __name__=='__main__':unittest.main()
