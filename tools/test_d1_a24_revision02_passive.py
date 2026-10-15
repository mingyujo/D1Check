"""Synthetic passive-cooling gate behavior; no native subprocess or inference."""
import datetime,json,tempfile,unittest
from pathlib import Path
from unittest import mock
from d1_a24_revision02_window import passive_before_next_app
from d1_a24_laptop_mock import fixture_manifest
from d1_a24_laptop_validator import NS,ValidationError
from test_d1_a24_laptop_control import FakeAdb


class PassiveBeforeAppCases(unittest.TestCase):
    def test_within_band_but_above_reference_does_not_launch_then_stable_cool_returns(self):
        class ReadOnlyFake(FakeAdb):
            def command(self,*args,**kwargs):
                self.ap=29.1 if self.clock<120*NS else 28.9
                return super().command(*args,**kwargs).replace(b'MOCK_AP',b'AP')
        fake=ReadOnlyFake(fixture_manifest('C252_CPU'))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'block_reference.json').write_text(json.dumps({'Tref_c':29.0}))
            window={'hard_stop_UTC':(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=1)).isoformat()}
            with mock.patch('time.sleep',side_effect=lambda seconds:fake.sleep_ns(int(seconds*NS))),mock.patch('subprocess.run',side_effect=AssertionError('native invocation forbidden')):
                passive_before_next_app({},fake,{'session_id':'SYNTHETIC'},root,window)
            proof=json.loads((root/'pre_app_cooldown/SYNTHETIC.ready.json').read_text())
            self.assertGreaterEqual(proof['samples'],25)
            self.assertEqual(proof['last_AP_c'],28.9)
            self.assertFalse(proof['new_app_started'])
            self.assertTrue(proof['post_warmup_gate_still_required'])
            self.assertTrue(all(call[:2] in {('shell','cat'),('shell','dumpsys')} for call in fake.calls))

    def test_no_remaining_app_budget_refuses_before_any_read_or_inference(self):
        fake=FakeAdb(fixture_manifest('C252_CPU'))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'block_reference.json').write_text(json.dumps({'Tref_c':29.0}))
            window={'hard_stop_UTC':(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=5)).isoformat()}
            with self.assertRaises(ValidationError):passive_before_next_app({},fake,{'session_id':'SYNTHETIC'},root,window)
            self.assertFalse(fake.calls)


if __name__=='__main__':unittest.main()
