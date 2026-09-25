import json
from pathlib import Path
import subprocess
import sys
import shlex
import tempfile
import unittest
from tools import d1_energy_screen as s
from tools import d1_energy_collection_device as d
from tools import d1_recorded_process as rp

GOOD=b'  mWakefulness=Awake\n  mHalInteractiveModeEnabled=true\n__D1_POWER_EXIT_0\n'

class ScreenTest(unittest.TestCase):
    def test_exact_fresh_complete(self):
        self.assertEqual(s.parse(GOOD),dict(awake=True,interactive=True))
        self.assertEqual(shlex.split(shlex.quote(s.SCRIPT)),[s.SCRIPT])
    def test_missing_duplicate_nonzero_rejected(self):
        for raw in (GOOD.split(b'__D1')[0],GOOD+GOOD,GOOD.replace(b'EXIT_0',b'EXIT_1'),b''):
            with self.assertRaises(ValueError):s.parse(raw)
    def test_sleep_is_separate_violation(self):
        self.assertFalse(s.parse(GOOD.replace(b'Awake',b'Asleep'))['awake'])
    def test_timeout_never_reuses_partial_or_retries(self):
        class Device:
            calls=0
            def call(self,*args,**kwargs):
                self.calls+=1
                assert kwargs['timeout']==2
                raise TimeoutError('partial bytes remain in recorded client files')
        with tempfile.TemporaryDirectory() as t:
            device=Device()
            with self.assertRaises(TimeoutError):s.snapshot(device,t,'x',{})
            self.assertEqual(device.calls,1)
            self.assertEqual(json.loads((Path(t)/'screen_observations/x.json').read_text())['status'],'query_unavailable')
    def test_fresh_query_and_setting_mismatch(self):
        class Device:
            def call(self,*args,**kwargs):
                return subprocess.CompletedProcess(args,0,GOOD if args[1]=='sh' else b'99',b'')
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):s.snapshot(Device(),t,'x',{'screen_brightness':81},True)
            self.assertEqual(json.loads((Path(t)/'screen_observations/x.json').read_text())['status'],'setting_violation')
    def test_cat_error_is_not_cleanup_json(self):
        class Device:
            def call(self,*a,**kw):return subprocess.CompletedProcess(a,0,b'cat: No such file',b'')
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):d.pull_file(Device(),'files/test','cleanup.json',t)
            self.assertFalse((Path(t)/'cleanup.json').exists())
            self.assertTrue((Path(t)/'cleanup.json.invalid.bin').exists())
    def test_process_bound_and_partial_file_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            cmd=[sys.executable,'-u','-c','import time;print("partial",flush=True);time.sleep(5)']
            result=rp.run(cmd,Path(t)/'client',.5,cmd,root_only=True)
            self.assertEqual(result['status'],'timeout')
            self.assertTrue(result['root_reaped'])
            self.assertIn(b'partial',(Path(t)/'client/stdout.bin').read_bytes())
            self.assertLessEqual(result['spawn_start_monotonic'],result['spawn_return_monotonic'])
            self.assertLessEqual(result['spawn_return_monotonic'],result['wait_start_monotonic'])

if __name__=='__main__':unittest.main()
