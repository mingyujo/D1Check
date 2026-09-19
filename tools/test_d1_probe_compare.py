import unittest
from tools.d1_probe_compare import finite_comparison, gpu_evidence, compare_decoded


class CompareTest(unittest.TestCase):
    def test_decoded_count_label_box_score_are_separate_fixed_checks(self):
        ref = [dict(label='cat', score=.75, box=[1,2,3,4])]
        self.assertTrue(compare_decoded(ref, ref)['passed'])
        for candidate in ([], [dict(ref[0],label='dog')], [dict(ref[0],score=.752)],
                          [dict(ref[0],box=[4,2,3,4])]):
            self.assertFalse(compare_decoded(ref,candidate)['passed'])

    def test_decoded_nan_rejected(self):
        with self.assertRaises(ValueError):
            compare_decoded([], [dict(label='cat',score=float('nan'),box=[1,2,3,4])])

    def test_fixed_tolerance_pass_and_failure(self):
        self.assertTrue(finite_comparison([0., 1.], [0.00009, 1.001])['passed'])
        self.assertEqual(1, finite_comparison([0.], [0.00011])['violations'])

    def test_nonfinite_and_mismatched_arrays_fail(self):
        for a, b in [([], []), ([1], [1, 2]), ([float('nan')], [0]), ([0], [float('inf')])]:
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                finite_comparison(a, b)

    def log(self):
        prefix = '09-20 03:00:00.000 42 43 I tflite : '
        return '\n'.join(prefix + text for text in ['session_start=test model=x'] +
            ['Replacing 4 out of 4 node(s) with delegate (TfLiteGpuDelegateV2)', 'Created 1 GPU delegate kernels.'] * 4 +
            ['session_finalized=test artifacts=8'])

    def test_session_scoped_backend_evidence(self):
        self.assertEqual('verified_full', gpu_evidence(self.log(), 'test')['status'])
        for log in [self.log().replace('4 out of 4', '3 out of 4'), self.log() + '\n' + self.log(),
                    self.log().replace('artifacts=8', 'fallback artifacts=8')]:
            with self.assertRaises(ValueError):
                gpu_evidence(log, 'test')
