from pathlib import Path
import unittest
from d1_a24_registered_report import unique_actual


class EvidenceSelection(unittest.TestCase):
    def test_no_favorable_selection_of_duplicate_execution(self):
        failed=(Path('old'),Path('old/outcome'),{'status':'FAILED_PRESERVED','APP_launch_intent':True})
        normal=(Path('new'),Path('new/outcome'),{'status':'COMPLETE_TRACE_RECOVERED','APP_launch_intent':True})
        with self.assertRaises(ValueError):unique_actual([failed,normal])
        self.assertEqual(unique_actual([failed]),failed)
        deferred=(Path('defer'),Path('defer/outcome'),{'status':'NOT_ATTEMPTED','APP_launch_intent':False})
        self.assertEqual(unique_actual([deferred,normal]),normal)


if __name__=='__main__':unittest.main()
