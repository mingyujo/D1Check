import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import d1_separated_power_readout as r
from tools.test_d1_online_policy_study import synthetic


class ReadoutTests(unittest.TestCase):
    def bundle(self, root):
        cases, z = synthetic()
        m = r.shared.model
        with patch.object(m, 'energy_at', side_effect=lambda c,a,b:b-a+float(m.exposure(c['inputs']['segments'],a,b)@z)):
            frozen = m.develop(cases)
        frozen.update(version='separated-power-model-v1', preload_power_window_s=[-20,30], energy_baseline_mode='session_preload')
        r.shared.write(root/'model.json', frozen)
        r.shared.write(root/'initial_inputs.json', [dict(id='fixture', phase='confirmation',
            initial=dict(preload=cases[0]['inputs']['preload'], preload_power_w=1.),
            manifest_requests=r.protocol.requests('confirmation'))])
        self.bind(root)

    def bind(self, root):
        r.shared.write(root/'resources.json', dict(files={name:r.shared.p.digest(root/name)
            for name in ('model.json','initial_inputs.json')}))

    def test_actual_replay_and_future_information_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.bundle(root)
            policy=r.shared.model.POLICIES[1]
            r.predict(root,'fixture',policy,root/'a')
            first=r.shared.p.read(root/'a/result.json')
            self.assertEqual(len(first['forecast']['ledger']),96)
            self.assertFalse(first['experiment_ready'])
            self.assertIsNone(first['decision_support']['future_error_bound'])
            self.assertFalse(first['decision_support']['equality_of_policies_established'])
            cases=r.shared.p.read(root/'initial_inputs.json')
            cases[0]['initial'].update(observed_ap_c=[999], power_samples=[999])
            r.shared.write(root/'initial_inputs.json',cases);self.bind(root)
            r.predict(root,'fixture',policy,root/'b')
            second=r.shared.p.read(root/'b/result.json')
            self.assertEqual(first['forecast'],second['forecast'])
            self.assertEqual(first['costs'],second['costs'])

    def test_wrong_model_role_and_tampered_bundle_blocked(self):
        for fault in ('model','phase','hash','missing_binding'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);self.bundle(root)
                if fault=='model':
                    f=r.shared.p.read(root/'model.json');f['version']='old';r.shared.write(root/'model.json',f);self.bind(root)
                elif fault=='phase':
                    c=r.shared.p.read(root/'initial_inputs.json');c[0]['phase']='development';r.shared.write(root/'initial_inputs.json',c);self.bind(root)
                elif fault=='hash':
                    (root/'model.json').write_text('{}',encoding='utf8')
                else:
                    r.shared.write(root/'resources.json',dict(files={}))
                with self.assertRaises(ValueError):
                    r.predict(root,'fixture',r.shared.model.POLICIES[0],root/'result')
                self.assertFalse((root/'result').exists())

    def test_policy_selection_is_not_inferred_from_point_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.bundle(root)
            with self.assertRaisesRegex(ValueError,'no validated bound'):
                r.predict(root,'fixture',r.shared.model.POLICIES[0],root/'out',
                          purpose='energy-ap-policy-selection')
            self.assertFalse((root/'out').exists())
        with self.assertRaisesRegex(ValueError,'unknown prediction purpose'):
            r.decision_support('silently-rank')


if __name__=='__main__':unittest.main()
