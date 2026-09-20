import unittest
import struct
from tools.d1_detection_contract import decode, resize_rgb, iou, require_canonical_png


class DetectionContractTest(unittest.TestCase):
    def test_embedded_color_metadata_rejected_before_inference(self):
        chunk = lambda kind, data: struct.pack('>I',len(data))+kind+data+b'\0'*4
        prefix = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',b'\0'*13)
        suffix = chunk(b'IDAT',b'x')+chunk(b'IEND',b'')
        require_canonical_png(prefix+suffix)
        for data in (prefix+chunk(b'iCCP',b'profile')+suffix, (prefix+suffix)[:-1]):
            with self.assertRaises(ValueError):
                require_canonical_png(data)
    def test_resize_identity_and_single_pixel(self):
        rgb = bytes(range(12))
        self.assertEqual(resize_rgb(rgb, 2, 2, 2), rgb)
        self.assertEqual(resize_rgb(bytes([1, 128, 255]), 1, 1, 3), bytes([1, 128, 255]) * 9)

    def test_integer_half_pixel_interpolation(self):
        self.assertEqual(resize_rgb(bytes([0, 0, 0, 255, 255, 255]), 2, 1, 3),
                         bytes([0, 0, 0, 128, 128, 128, 255, 255, 255]) * 3)

    def test_yxhw_offset_and_original_coordinates(self):
        result = decode([[0.1, 0.75]], [[0.5, -0.25, 0, 0]], [[0.5, 0.5, 0.4, 0.2]], ['a', 'b'], 100, 200)
        self.assertEqual(result[0]['label'], 'b')
        for actual, expected in zip(result[0]['box'], [20, 100, 40, 40]):
            self.assertAlmostEqual(actual, expected)

    def test_threshold_is_inclusive_and_nms_class_agnostic(self):
        result = decode([[0.5, 0.1], [0.1, 0.7], [0.499, 0.1]], [[0, 0, 0, 0]] * 3,
                        [[0.5, 0.5, 0.2, 0.2]] * 3, ['a', 'b'], 100, 100)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['label'], 'b')
        self.assertEqual(len(decode([[0.5]], [[0, 0, 0, 0]], [[0.5, 0.5, 1, 1]], ['a'], 1, 1)), 1)

    def test_nonfinite_and_bad_shapes_rejected(self):
        for scores in ([[float('nan')]], [[0.5, 0.6]]):
            with self.assertRaises(ValueError):
                decode(scores, [[0, 0, 0, 0]], [[0.5, 0.5, 1, 1]], ['a'], 1, 1)
        with self.assertRaises(ValueError):
            resize_rgb(b'', 1, 1)

    def test_iou_and_tie_are_deterministic(self):
        self.assertEqual(iou([0, 0, 2, 2], [0, 0, 2, 2]), 1)
        result = decode([[0.5, 0.5]], [[0, 0, 0, 0]], [[0.5, 0.5, 1, 1]], ['a', 'b'], 1, 1)
        self.assertEqual(result[0]['label'], 'a')


if __name__ == '__main__':
    unittest.main()
