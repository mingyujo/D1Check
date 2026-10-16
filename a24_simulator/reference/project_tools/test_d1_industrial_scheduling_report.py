import gzip
import json
from pathlib import Path
import tempfile
import unittest

from tools import d1_industrial_scheduling as x
from tools import d1_industrial_scheduling_report as report


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,case=x.p.inputs(x.p.BUNDLE);cls.initial=case['initial']
        cls.records=report.read_records(x.ROOT/'run_v2')

    def test_all45_energy_paths_preserve_common_total(self):
        self.assertEqual(len(self.records),45)
        for d in self.records:
            self.assertAlmostEqual(report.energy_at(d['segments'],0,self.initial,self.frozen),0.)
            self.assertAlmostEqual(report.energy_at(d['segments'],120,self.initial,self.frozen),d['meta']['energy_j'],places=8)

    def test_missing_cost_is_not_zero(self):
        with self.assertRaises(ValueError):
            report.energy_at([dict(state='detection_GPU',start_s=35,end_s=40)],120,self.initial,self.frozen)

    def test_shared_gzip_is_sufficient_without_parent_or_plain(self):
        with tempfile.TemporaryDirectory() as folder:
            raw=(json.dumps(self.records[0])+'\n').encode()
            (Path(folder)/'records.jsonl.gz').write_bytes(gzip.compress(raw,mtime=0))
            self.assertEqual(report.read_records(folder),[self.records[0]])


if __name__=='__main__':unittest.main()
