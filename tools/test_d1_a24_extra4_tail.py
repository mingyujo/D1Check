import unittest
from pathlib import Path
from d1_a24_extra4_tail import previous
from d1_a24_laptop_validator import load_json, ValidationError


class TailCases(unittest.TestCase):
    def job(self):
        m=Path('output/A24R02R2/job.json')
        if not m.exists():self.skipTest('local immutable prior execution evidence unavailable')
        j=load_json(m);r1=Path(j['previous_extra4_root']);r2=Path(j['run_root'])
        from d1_a24_laptop_validator import sha256
        j.update(first_extra4_root=str(r1),second_extra4_root=str(r2),
                 previous_stop_sha256s=[sha256(p/'WINDOW_STOPPED.json') for p in [r1,r2]])
        return j

    def test_exact_never_started_ORDER_and_closed_failed_PAIR(self):
        row,ref=previous(self.job())
        self.assertEqual(row['arm'],'ORDER');self.assertEqual(row['request_count'],128)
        self.assertEqual(load_json(ref)['Tref_c'],27.6)

    def test_changed_previous_receipt_is_rejected(self):
        j=self.job();j['previous_stop_sha256s'][1]='a'*64
        with self.assertRaises(ValidationError):previous(j)


if __name__=='__main__':unittest.main()
