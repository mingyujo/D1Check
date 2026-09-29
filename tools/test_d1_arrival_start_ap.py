import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from tools import d1_arrival_start_ap as g

class StartApTest(unittest.TestCase):
    def exercise(self,ap):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td);(f/'input_manifest.json').write_text('{}')
            (f/'start_ap_gate').mkdir(); ready=f/'ready.json'
            ready.write_text(json.dumps(dict(manifest_sha256=g.p.digest(f/'input_manifest.json'),mono_ns=100)))
            d=Mock()
            with patch.object(g.device,'pull_file',return_value=ready),patch.object(g.device,'thermal',return_value=dict(
                AP=ap,thermal_status='0',before_ns=200,after_ns=300)):
                try:g.approve(d,'remote',f,dict(session_id='00000000-0000-0000-0000-000000000001'))
                except ValueError:
                    self.assertEqual(d.call.call_count,0);return False
            self.assertEqual(d.call.call_count,1)
            self.assertIn('&& mv',d.call.call_args.args[-1])
            self.assertTrue((f/'start_ap_gate/host_approval.json').exists())
            return True
    def test_single_approval(self):self.assertTrue(self.exercise('32.5'))
    def test_invalid_never_arms(self):
        for ap in ('','32.3','34.1','nan'):
            self.assertFalse(self.exercise(ap))
    def test_real_poll_routes_warmup_then_single_start_approval(self):
        from tools import d1_arrival_energy_collection_device as runner
        from contextlib import ExitStack
        import time
        with tempfile.TemporaryDirectory() as td, ExitStack() as stack:
            folder=Path(td);(folder/'input_manifest.json').write_text('{}')
            ready=folder/'ready.json';ready.write_text(json.dumps(dict(manifest_sha256=g.p.digest(folder/'input_manifest.json'))))
            warm=folder/'warm.json';warm.write_text(json.dumps([dict(key=k,result={}) for k in runner.c.old.KEYS for _ in range(2)]))
            reference=folder/'reference.json';reference.write_text('{}')
            listings=iter([b'warmup.ready.json',b'start_ap.ready.json',b'start_ap.ready.json',b'cleanup.json'])
            d=Mock(deadline=time.monotonic()+60)
            def call(*args,**kwargs):
                if 'ls' in args:return Mock(stdout=next(listings))
                if 'pidof' in args:return Mock(stdout=b'123')
                return Mock(stdout=b'')
            d.call.side_effect=call
            stack.enter_context(patch.object(runner.energy_device,'pull_file',side_effect=lambda d,r,n,f: ready if n.endswith('ready.json') else warm))
            for owner,name in [(runner.energy_device,'thermal'),(runner.energy_device,'arm'),(runner.energy_device,'gpu_proof'),
                               (runner.screen,'snapshot'),(runner.c.old,'quality'),(runner.time,'sleep')]:
                stack.enter_context(patch.object(owner,name,return_value={}))
            approve=stack.enter_context(patch.object(g,'approve'))
            runner.poll(d,'remote',folder,dict(session_id='fixture',start_ap_gate=g.VERSION),
                        dict(screen_contract={},references={k:dict(path=str(reference),sha256=g.p.digest(reference)) for k in runner.c.old.KEYS}))
            self.assertEqual(approve.call_count,1)

if __name__=='__main__':unittest.main()
