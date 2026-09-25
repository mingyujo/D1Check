import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tools import d1_energy_screen_observe as o

class ObserveTest(unittest.TestCase):
    def test_real_battery_gate_bytes_boundary(self):
        class Device:
            def call(self,*a,**kw):
                raw=b'level: 94\nscale: 100\ntemperature: 280\nAC powered: false\nUSB powered: false\nWireless powered: false\n' if a[-1]=='battery' else b'Thermal Status: 0\n'
                return subprocess.CompletedProcess(a,0,raw,b'')
        with tempfile.TemporaryDirectory() as t:
            plan=dict(battery_start_percent=20,battery_min_percent=20,require_unplugged=True,battery_max_temperature_tenths_c=350)
            o.environment(Device(),plan,Path(t),'pass')
            self.assertIn(b'level: 94',(Path(t)/'pass_battery.txt').read_bytes())
            plan['battery_start_percent']=95
            with self.assertRaises(RuntimeError):o.environment(Device(),plan,Path(t),'fail')
    def test_run_cap_and_failure_no_retry(self):
        for fail in (False,True):
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as t:
                root=Path(t);p=dict(output_root=str(root/'run'),registry=str(root/'registry'),device_fingerprint='fp',hardware_serial='id',screen_contract={},budget={})
                file=root/'plan.json';file.write_text(json.dumps(p))
                class Device:
                    def __init__(self,*a):pass
                    def identify(self,*a):return {'device':'mock'}
                    def call(self,*a,**kw):return subprocess.CompletedProcess(a,0,b'id',b'')
                with patch.object(o,'check'),patch.object(o,'ObservedDevice',Device),patch.object(o,'environment'),patch.object(o.legacy,'require_stopped'),patch.object(o.time,'sleep'),patch.object(o.screen,'snapshot') as query:
                    if fail:query.side_effect=TimeoutError('mock timeout')
                    else:query.side_effect=lambda *a,**kw:dict(status='sample_pass',host_end=o.time.monotonic())
                    r=o.run(file,'serial','unused',True,o.sha(file))
                self.assertEqual(query.call_count,1 if fail else 32)
                self.assertEqual(r['queries_attempted'],1 if fail else 32)
                self.assertEqual(r['queries_succeeded'],0 if fail else 32)
                self.assertEqual(r['inference'],0)
                self.assertTrue((root/'registry/finished.json').exists())
    def test_no_approval_prevents_claim(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'p.json';f.write_text('{}')
            with self.assertRaises(ValueError):o.run(f,'s','a',False,o.sha(f))
            self.assertEqual(len(list(Path(t).iterdir())),1)

if __name__=='__main__':unittest.main()
