import subprocess
import tempfile
import unittest
from pathlib import Path
from d1_a24_measurement_connection import ReconnectingAdbClient, read_only_command
from d1_a24_laptop_control import ValidationError

class ConnectionTests(unittest.TestCase):
    def fixture(self, root):
        clock=[0.0]; calls=[]; state={'lost':True}
        def run(argv,**kwargs):
            calls.append(argv)
            if argv[-1]=='devices': return subprocess.CompletedProcess(argv,0,b'List of devices attached\nNEW device\n',b'')
            if argv[-1]=='get-state': return subprocess.CompletedProcess(argv,1,b'',b'offline')
            if argv[-1]=='ro.serialno': return subprocess.CompletedProcess(argv,0,b'PHONE\n',b'')
            if argv[-1]=='ro.build.fingerprint': return subprocess.CompletedProcess(argv,0,b'FP\n',b'')
            if state['lost']: state['lost']=False;return subprocess.CompletedProcess(argv,1,b'',b'device offline')
            return subprocess.CompletedProcess(argv,0,b'RAW',b'')
        client=ReconnectingAdbClient('FAKE_ADB_NEVER_EXECUTED','OLD','PHONE','FP',root/'commands.jsonl',
             sleep=lambda s:clock.__setitem__(0,clock[0]+s),clock=lambda:clock[0],runner=run)
        return client,calls,clock
    def test_read_reconnects_same_phone_and_retries_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            client,calls,_=self.fixture(Path(tmp));self.assertEqual(client.command('shell','cat','/proc/uptime'),b'RAW')
            self.assertEqual(client.prefix[-1],'NEW');self.assertEqual(client.disconnects,1)
    def test_ambiguous_start_is_never_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            client,calls,_=self.fixture(Path(tmp))
            with self.assertRaisesRegex(ValidationError,'ambiguous mutation'):client.command('shell','am','start')
            self.assertEqual(len([c for c in calls if c[-3:]==['shell','am','start']]),1)
    def test_mutations_are_not_classified_as_read_only(self):
        for cmd in [('install','-r','apk'),('push','a','b'),('shell','am','start'),('shell','run-as','package','cp'),
                    ('shell','settings','put','system','screen_brightness','1'),('shell','dumpsys','battery','reset')]:
            self.assertFalse(read_only_command(cmd))
    def test_disconnect_wait_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock=[0.0]
            client=ReconnectingAdbClient('FAKE','X','PHONE','FP',Path(tmp)/'commands.jsonl',wait_seconds=20,
              runner=lambda argv,**kw:subprocess.CompletedProcess(argv,0,b'List of devices attached\n',b''),
              sleep=lambda s:clock.__setitem__(0,clock[0]+s),clock=lambda:clock[0])
            with self.assertRaisesRegex(ValidationError,'20 minutes'):client.reconnect()
            self.assertLessEqual(clock[0],25)

    def test_local_daemon_failure_recovers_even_when_get_state_says_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            client,calls,_=self.fixture(Path(tmp));original=client.runner;failed=[False]
            def runner(argv,**kwargs):
                if argv[-1]=='get-state':return subprocess.CompletedProcess(argv,0,b'device\n',b'')
                if argv[-1]=='/proc/uptime' and not failed[0]:
                    failed[0]=True;return subprocess.CompletedProcess(argv,1,b'',b'* daemon still not running; cannot connect to daemon at tcp:5037')
                # Bypass the fixture's independent initial offline event.
                if argv[-1]=='/proc/uptime':return subprocess.CompletedProcess(argv,0,b'123 0\n',b'')
                return original(argv,**kwargs)
            client.runner=runner
            self.assertEqual(client.command('shell','cat','/proc/uptime'),b'123 0\n')
            self.assertEqual(client.disconnects,1)

    def test_read_timeout_also_requires_same_phone_handshake_before_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            client,calls,_=self.fixture(Path(tmp));original=client.runner;failed=[False]
            def runner(argv,**kwargs):
                if argv[-1]=='get-state':return subprocess.CompletedProcess(argv,0,b'device\n',b'')
                if argv[-1]=='/proc/uptime':
                    if not failed[0]:failed[0]=True;raise subprocess.TimeoutExpired(argv,30)
                    return subprocess.CompletedProcess(argv,0,b'123 0\n',b'')
                return original(argv,**kwargs)
            client.runner=runner
            self.assertEqual(client.command('shell','cat','/proc/uptime'),b'123 0\n')
            self.assertTrue(any(c[-1]=='ro.serialno' for c in calls))
            self.assertTrue(any(c[-1]=='ro.build.fingerprint' for c in calls))

if __name__=='__main__':unittest.main()
