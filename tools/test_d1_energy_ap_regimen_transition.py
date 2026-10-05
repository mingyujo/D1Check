import unittest
from copy import deepcopy
import csv
import json
from pathlib import Path

from tools import d1_energy_ap_regimen_transition as bridge


class RegimenSupportTest(unittest.TestCase):
    def setUp(self):
        self.frozen = {'initial_ap_development_range_c':[32.5,34.0]}
        self.models = {k:{'model':{'sha256':k},'runtime':{'cpu_threads':1}}
                       for k in ('classification_CPU','classification_GPU','detection_CPU','detection_GPU')}
        self.old = {'device_fingerprint':'same-A24','images':[{'sha256':'input'}],
                    'models':self.models,'cpu_threads':1,'apk_sha256':'old'}
        self.new = deepcopy(self.old); self.new.update(apk_sha256='new',
            session_control='device-after-probe-diagnostic-v1',autonomous_diagnostic_only=True,mode='calibration')
        self.stats = {'status':'eligible_regimen_only','condition':'CG_DC','phase':'confirmation','start_ap_c':32.6,
                      'blocks':[{'name':name,'state':state} for name,state in zip(bridge.BLOCKS,bridge.STATES)],
                      'common_window':{'full_energy_j':1.0}}

    def test_protocol_change_only_allows_observed_regimen(self):
        self.assertEqual(bridge.support(self.stats,self.new,self.old,self.frozen),'posthoc_protocol_transfer_only')
        self.assertEqual(bridge.support(self.stats,self.new,self.old,self.frozen,mode='arbitrary_arrivals'),
                         'unsupported_arrival_or_unobserved_schedule')
        self.stats['start_ap_c']=34.1
        self.assertIn('unsupported_initial_ap',bridge.support(self.stats,self.new,self.old,self.frozen))

    def test_no_reverse_pair_or_runtime_transfer(self):
        self.stats['blocks'][0]['state']='classification_CPU+detection_GPU'
        self.assertEqual(bridge.support(self.stats,self.new,self.old,self.frozen),'unsupported_state_sequence')
        self.stats['blocks'][0]['state']=bridge.STATES[0]
        self.new['models']['classification_GPU']={'model':{'sha256':'changed'},'runtime':{'cpu_threads':1}}
        self.assertEqual(bridge.support(self.stats,self.new,self.old,self.frozen),'unsupported_model_or_runtime')

    def test_missing_energy_is_unsupported(self):
        self.stats['common_window']['full_energy_j']=None
        self.assertEqual(bridge.calculate(self.stats,self.new,self.old,self.frozen)['energy_j'],None)

    def test_shared_curves_and_blocks_match_summary(self):
        root=Path(__file__).resolve().parents[1]/'docs/results/energy_ap_transition_01'
        summary=json.loads((root/'summary.json').read_text(encoding='utf-8'))
        with (root/'blocks.csv').open(encoding='utf-8',newline='') as f:blocks=list(csv.DictReader(f))
        with (root/'energy_path.csv').open(encoding='utf-8',newline='') as f:energy=list(csv.DictReader(f))
        with (root/'ap_path.csv').open(encoding='utf-8',newline='') as f:ap=list(csv.DictReader(f))
        self.assertAlmostEqual(sum(float(r['signed_energy_error_j']) for r in blocks),summary['mapped_signed_error_j'])
        self.assertAlmostEqual(float(energy[-1]['observed_energy_j']),summary['observed_common_energy_j'])
        self.assertAlmostEqual(max(float(r['predicted_ap_c']) for r in ap),summary['errors']['ap_peak_predicted_c'])


if __name__=='__main__':unittest.main()
