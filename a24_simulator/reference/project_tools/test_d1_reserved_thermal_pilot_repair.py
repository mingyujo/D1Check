import unittest
from tools import d1_reserved_thermal_pilot_repair as repair
from tools import test_d1_reserved_thermal as original_tests


class NumericPlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original_tests.ControllerBoundaryTests.setUpClass()
        cls.frozen = original_tests.ControllerBoundaryTests.frozen
        cls.initial = original_tests.ControllerBoundaryTests.initial
        cls.q = dict(original_tests.ControllerBoundaryTests.q, task='detection', priority='normal',
                     deadline_offset_ns=6000000000)

    def test_sub_nanosecond_overlap_is_removed_and_segment_supported(self):
        c=repair.Controller(self.frozen,self.initial)
        a=c.place(dict(self.q,id='a'),'CPU',35.,[])
        earliest=a['end']-3.333440190544934e-10
        old=c.place(dict(self.q,id='b'),'CPU',earliest,[a])
        self.assertLess(old['start'],a['end'])
        new=repair.StrictPlacement(c).place(dict(self.q,id='b'),'CPU',earliest,[a])
        self.assertEqual(new['start'],a['end'])
        self.assertEqual(new['end']-new['start'],old['end']-old['start'])
        self.assertTrue(repair.rule.P.segments([a,new],35.,120.))

    def test_real_retained_gap_and_original_deadline_remain_unchanged(self):
        c=repair.Controller(self.frozen,self.initial)
        a=c.place(dict(self.q,id='a'),'CPU',35.,[])
        b=repair.StrictPlacement(c).place(dict(self.q,id='b'),'CPU',a['end']+.25,[a])
        self.assertEqual(b['start'],a['end']+.25)
        self.assertEqual(b['deadline'],(self.q['arrival_ns']+self.q['deadline_offset_ns'])/1e9)

    def test_large_conflict_is_not_silently_repaired(self):
        class Broken:
            def place(self,q,b,earliest,jobs):
                return dict(start=35.,end=36.,state='detection_CPU',backend='CPU')
        with self.assertRaisesRegex(ValueError,'exceeds numerical'):
            repair.StrictPlacement(Broken()).place(self.q,'CPU',35.,
                [dict(start=35.,end=36.,state='detection_CPU',backend='CPU')])


if __name__=='__main__':
    unittest.main()
