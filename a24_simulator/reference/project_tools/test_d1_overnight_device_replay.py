"""Small semantic checks for the new bounded frozen-plan path; no ADB."""
import copy
import unittest

from tools import d1_overnight_device_replay as r
from tools import d1_overnight_device_build as b


def rows():
    return [dict(ordinal=i,source_request_id=f'q{i}',task_id='classification' if i%2==0 else 'detection',
        priority='urgent' if i%2==0 else 'normal',offset_ms=35000+i*350,
        deadline_ms=1500 if i%2==0 else 6000,release_offset_ns=(35000+i*350)*1_000_000,
        recorded_backend='GPU' if i%2==0 else 'CPU') for i in range(96)]


class FrozenReplayContract(unittest.TestCase):
    def test_exact_supported_input(self):
        r.shape(rows())
        cpu=rows();cpu[0]['recorded_backend']='CPU';r.shape(cpu)

    def test_no_arrival_or_deadline_rewrite(self):
        for field,value in [('offset_ms',0),('deadline_ms',9999),('priority','normal'),('ordinal',9)]:
            bad=rows();bad[0][field]=value
            with self.assertRaises(ValueError):r.shape(bad)

    def test_no_early_release_or_unsupported_gpu_detection(self):
        for index,field,value in [(0,'release_offset_ns',1),(1,'recorded_backend','GPU'),(0,'recorded_backend','NPU')]:
            bad=rows();bad[index][field]=value
            with self.assertRaises(ValueError):r.shape(bad)

    def test_full_denominator_and_budget(self):
        with self.assertRaises(ValueError):r.shape(rows()[:-1])
        self.assertEqual(r.BUDGET['explicit_inference'],4*(96+8))
        self.assertEqual(r.BUDGET['save_reserve_seconds'],600)
        self.assertEqual(r.BUDGET['sessions'],4)
        self.assertEqual(r.BUDGET['installs'],1)

    def test_source_transform_is_fail_closed(self):
        with self.assertRaises(ValueError):b.activity_source('unrelated source')
        with self.assertRaises(ValueError):b.replay_source('unrelated source')


if __name__=='__main__':unittest.main()
