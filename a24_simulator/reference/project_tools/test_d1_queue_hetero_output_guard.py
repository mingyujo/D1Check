import json,unittest
import numpy as np
from pathlib import Path
from unittest.mock import patch
from tools import d1_queue_hetero_study as s

class OutputOnly(unittest.TestCase):
    def test_unavailable_metadata_does_not_become_zero(self):
        key=s.key([dict(incomplete=1,urgent_failure=0,normal_failure=1,urgent_p95_ms=300,energy_j=None,peak_ap_c=None)])
        self.assertTrue(np.isinf(key[-1]))
        exported=s.serial(dict(development_key=key,values=np.array([1.,float('inf')])))
        self.assertEqual(exported['development_key'][-1],'UNAVAILABLE')
        self.assertEqual(exported['values'],[1.,'UNAVAILABLE'])
        json.dumps(exported,allow_nan=False)
    def test_effective_driver_and_original_receipt_guard(self):
        folder=s.ROOT.parent/'QUEUE-HETERO-PPO-03'
        s.check(folder)
        original=s.budget.digest
        def changed(path):
            return 'mutated' if Path(path).resolve()==Path(s.__file__).resolve() else original(path)
        with patch.object(s.budget,'digest',side_effect=changed):
            with self.assertRaises(ValueError):s.check(folder)

if __name__=='__main__':unittest.main()
