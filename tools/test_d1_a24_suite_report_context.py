import unittest
from d1_a24_suite_report_context import host_inference_overlap_ns


def phase(rid, edge, instant):
    return {'kind':'phase','stage':'host_inference','request_id':rid,'edge':edge,'mono_ns':instant}


class RecordedInferenceCases(unittest.TestCase):
    def test_actual_succeeded_schema_measures_overlap_and_serial_zero(self):
        requests=[{'request_id':'D','backend':'CPU'},{'request_id':'C','backend':'GPU'}]
        e=[phase('D','start',10),phase('C','start',20),phase('D','succeeded',30),phase('C','succeeded',40)]
        self.assertEqual(host_inference_overlap_ns(e,requests),10)
        e=[phase('D','start',10),phase('D','succeeded',20),phase('C','start',20),phase('C','succeeded',30)]
        self.assertEqual(host_inference_overlap_ns(e,requests),0)

    def test_missing_or_unrecognized_terminal_event_is_not_imputed(self):
        r=[{'request_id':'C','backend':'GPU'}]
        with self.assertRaises(AssertionError):host_inference_overlap_ns([phase('C','start',10)],r)
        with self.assertRaises(ValueError):host_inference_overlap_ns([phase('C','start',10),phase('C','end',20)],r)

    def test_same_lane_overlap_is_rejected(self):
        r=[{'request_id':'A','backend':'CPU'},{'request_id':'B','backend':'CPU'}]
        e=[phase('A','start',10),phase('B','start',20),phase('A','succeeded',30),phase('B','succeeded',40)]
        with self.assertRaises(AssertionError):host_inference_overlap_ns(e,r)


if __name__=='__main__':unittest.main()
