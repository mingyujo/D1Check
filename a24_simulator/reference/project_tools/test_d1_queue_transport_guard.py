"""Read-only transport and source guard regression; no environment or learning."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools import d1_queue_legacy_compare as legacy
from tools import d1_queue_direct_cli as cli

class Dummy:
    def __init__(self):self.events=[]
class Hook(Dummy):
    def on_public_event(self,event):self.events.append(event)

class Contracts(unittest.TestCase):
    def test_legacy_without_hook_keeps_old_path(self):
        c=Dummy();p=legacy.LegacyProxy(c)
        self.assertIsNone(getattr(p,'on_public_event',None));self.assertEqual(c.events,[])
    def test_existing_hook_is_forwarded(self):
        c=Hook();p=legacy.LegacyProxy(c);p.on_public_event(dict(event='arrived'))
        self.assertEqual(c.events,[dict(event='arrived')])
    def test_supplement_guard_rejects_mutation(self):
        key=Path(cli.study.__file__).resolve().relative_to(cli.study.ROOT).as_posix()
        sha=cli.study.budget.digest(cli.study.__file__)
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);cli.study.write(folder/'registration.json',dict(sources={}))
            receipt=dict(path=key,sha256=sha,registration_sha256=cli.study.budget.digest(folder/'registration.json'))
            cli.study.write(folder/'driver_freeze_receipt.json',receipt)
            with patch.object(cli.study,'check',return_value=dict(sources={})):
                cli.guard(folder)
                receipt['sha256']='changed';cli.study.write(folder/'driver_freeze_receipt.json',receipt)
                with self.assertRaisesRegex(ValueError,'driver changed'):cli.guard(folder)

if __name__=='__main__':unittest.main()
