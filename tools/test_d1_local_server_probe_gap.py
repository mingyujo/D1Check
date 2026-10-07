import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import d1_adb_observed_client as a


class ProbeTests(unittest.TestCase):
    def test_local_timeout_can_reprobe_without_duplicate_device_client(self):
        for allowed in (0,2):
            with self.subTest(allowed=allowed),tempfile.TemporaryDirectory() as tmp:
                device=a.ObservedDevice('FAKE','fixture',tmp);device.deadline=999999999
                device.local_server_probe_gap_limit=allowed
                def run(command,folder,*args,**kwargs):
                    folder.mkdir();(folder/'stdout.bin').write_bytes(b'device\n');(folder/'stderr.bin').write_bytes(b'')
                    return dict(status='returned',returncode=0)
                with patch.object(a,'server_probe',side_effect=[TimeoutError('fixture local timeout'),{'protocol_version':'0029'}]) as probe,patch.object(a,'host_snapshot',return_value={}),patch.object(a.time,'sleep'),patch.object(a.rp,'run',side_effect=run) as client:
                    if allowed:
                        self.assertEqual(device.call('get-state',timeout=3).stdout,b'device\n');self.assertEqual(probe.call_count,2);client.assert_called_once()
                    else:
                        with self.assertRaisesRegex(RuntimeError,'server unavailable'):device.call('get-state',timeout=3)
                        self.assertEqual(probe.call_count,1);client.assert_not_called()
                self.assertEqual((Path(tmp)/'0000/server_precheck_gap.json').exists(),bool(allowed))

    def test_not_listening_or_wrong_protocol_never_reprobes(self):
        for error in [ConnectionRefusedError('not listening'),RuntimeError('protocol mismatch')]:
            with self.subTest(error=error),tempfile.TemporaryDirectory() as tmp:
                device=a.ObservedDevice('FAKE','fixture',tmp);device.deadline=999999999;device.local_server_probe_gap_limit=2
                with patch.object(a,'server_probe',side_effect=error) as probe,patch.object(a,'host_snapshot',return_value={}),patch.object(a.rp,'run') as client:
                    with self.assertRaisesRegex(RuntimeError,'server unavailable'):device.call('get-state',timeout=3)
                    probe.assert_called_once();client.assert_not_called()

    def test_campaign_reprobe_bound_stops_further_client_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            device=a.ObservedDevice('FAKE','fixture',tmp);device.deadline=999999999
            device.local_server_probe_gap_limit=2;device.local_server_probe_gaps=2
            with patch.object(a,'server_probe',side_effect=TimeoutError('fixture timeout')) as probe,patch.object(a,'host_snapshot',return_value={}),patch.object(a.rp,'run') as client:
                with self.assertRaisesRegex(RuntimeError,'server unavailable'):device.call('get-state',timeout=3)
                probe.assert_called_once();client.assert_not_called()


if __name__=='__main__':unittest.main()
