import json
import unittest
from tools.d1_probe_progress import validate_progress


class ProgressTest(unittest.TestCase):
    session = '00000000-0000-0000-0000-000000000001'
    digest = 'a' * 64

    def rows(self):
        return [dict(protocol='model-probe-progress-v1', session_id=self.session,
                     manifest_sha256=None if i == 0 else self.digest, sequence=i, mono_ns=i,
                     clock='elapsedRealtimeNanos', phase=phase, edge=edge, thread_id=1)
                for i, (phase, edge) in enumerate([('request_validation', 'start'),
                    ('manifest_binding', 'finish'), ('request_validation', 'finish'),
                    ('interpreter_construction', 'start')])]

    def validate(self, rows):
        return validate_progress(''.join(json.dumps(r) + '\n' for r in rows), self.session, self.digest)

    def test_partial_stall_is_diagnostic_only(self):
        result = self.validate(self.rows())
        self.assertEqual(['interpreter_construction'], result['open_phases'])
        self.assertFalse(result['performance_evidence'])

    def test_stale_binding_clock_sequence_and_edges_rejected(self):
        for field, value in [('session_id', 'other'), ('manifest_sha256', 'b' * 64),
                             ('mono_ns', -1), ('sequence', 99), ('edge', 'finish')]:
            with self.subTest(field=field):
                rows = self.rows()
                rows[-1][field] = value
                with self.assertRaises(ValueError):
                    self.validate(rows)

    def test_unbound_truncated_and_replayed_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(self.rows()[:1])
        with self.assertRaises(ValueError):
            validate_progress(json.dumps(self.rows()[0]), self.session, self.digest)
        with self.assertRaises(ValueError):
            self.validate(self.rows() + self.rows())
