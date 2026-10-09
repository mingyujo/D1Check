import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from tools import d1_energy_screen as s


class ScreenProtoTests(unittest.TestCase):
    def fixture(self):return Path('tools/fixtures/energy_screen_proto_a24.bin').read_bytes()
    def test_actual_sanitized_A24_fields_match_same_text_state(self):
        self.assertEqual(s.parse_proto(self.fixture()),s.parse(b'mWakefulness=Awake\nmHalInteractiveModeEnabled=true\n__D1_POWER_EXIT_0\n'))
    def test_missing_truncated_failed_or_duplicate_producer_is_not_success(self):
        raw=self.fixture()
        for x in [raw[:-1],raw.replace(b'EXIT_0',b'EXIT_1'),raw+b'\n__D1_PROTO_EXIT_0\n',b'\x18\x01\x78\x01',b'\x18\x01\x78\x01\x0a\x09'+b'\n__D1_PROTO_EXIT_0\n']:
            with self.assertRaises(ValueError):s.parse_proto(x)
    def test_missing_duplicate_wrong_wire_and_windows_text_translation_fail(self):
        marker=b'\n__D1_PROTO_EXIT_0\n'
        for body in [b'\x18\x01',b'\x18\x01\x18\x01\x78\x01',b'\x1a\x01\x01\x78\x01',b'\r\n\x02\x08\x01\x18\x01\x78\x01']:
            with self.assertRaises(ValueError):s.parse_proto(body+marker)
    def test_nonawake_or_noninteractive_is_a_violation(self):
        self.assertFalse(s.parse_proto(self.fixture().replace(b'\x18\x01',b'\x18\x02'))['awake'])
        self.assertFalse(s.parse_proto(self.fixture().replace(b'\x78\x01',b'\x78\x00'))['interactive'])
    def test_actual_command_bytes_timeout_and_settings_are_preserved(self):
        commands=[];raw=self.fixture()
        class Fake:
            screen_version=s.PROTO_VERSION
            def call(self,*args,**kwargs):
                commands.append((args,kwargs))
                if args[0]=='exec-out':return SimpleNamespace(stdout=raw)
                return SimpleNamespace(stdout={'screen_brightness':b'81','screen_brightness_mode':b'0','screen_off_timeout':b'18000000'}[args[-1]])
        with tempfile.TemporaryDirectory() as tmp:
            result=s.snapshot(Fake(),tmp,'test',dict(screen_brightness=81,screen_brightness_mode=0,screen_off_timeout=18000000),settings=True)
            self.assertEqual(result['status'],'sample_pass');self.assertEqual(len(commands),4)
            self.assertEqual(commands[0],(('exec-out','sh','-c',s.PROTO_SCRIPT),{'timeout':2}))
            self.assertTrue((Path(tmp)/'screen_observations/test_power.pb').exists())
    def test_old_mode_keeps_old_producer_and_bound(self):
        commands=[]
        class Fake:
            def call(self,*args,**kwargs):
                commands.append((args,kwargs));return SimpleNamespace(stdout=b'mWakefulness=Awake\nmHalInteractiveModeEnabled=true\n__D1_POWER_EXIT_0\n')
        with tempfile.TemporaryDirectory() as tmp:s.snapshot(Fake(),tmp,'test',{})
        self.assertEqual(commands[0][0][:3],('shell','sh','-c'));self.assertEqual(commands[0][1]['timeout'],2)


if __name__=='__main__':unittest.main()
