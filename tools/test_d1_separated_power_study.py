import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from tools import d1_separated_power_study as s
from tools.test_d1_online_policy_study import synthetic


class SeparatedStudyTests(unittest.TestCase):
    def test_cli_storage_gate_blocks_before_claim_and_device(self):
        with patch.object(s.sys,'argv',['study','run','--plan','fixture','--adb','FAKE','--approved']),patch.object(s.p,'read',side_effect=[{'output_root':'output/fake'},{'minimum_host_free_bytes':2**31}]),patch.object(s.shutil,'disk_usage',return_value=SimpleNamespace(free=0)),patch.object(s.base,'run') as execute:
            with self.assertRaisesRegex(ValueError,'host storage reserve'):s.main()
            execute.assert_not_called()

    def test_shared_root_uses_new_adapter_and_freezes_before_confirmation(self):
        from tools import d1_arrival_energy_collection_device as runner
        from tools import d1_energy_host_lifecycle as lifecycle
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=Path(tmp);(root/'development').mkdir();(root/'confirmation').mkdir()
            s.base.cal.write_new(root/'old.json',{'whole_device_power_w':{}})
            s.base.cal.write_new(root/'development/collection_plan.json',{'frozen_model':{'path':str(root/'old.json')}})
            file=root/'study_plan.json';s.base.cal.write_new(file,dict(output_root=str(root/'run'),registry=str(root/'registry'),contract={'sha256':'fixed'},budget=s.p.read(s.CONTRACT)['budget']))
            seen=[]
            def run_block(file,*args):
                phase=file.parent.name;seen.append(phase)
                if phase=='confirmation':self.assertTrue((root/'run/model_freeze.json').exists())
                return {'status':'completed_descriptive_only'}
            for obj,name,kw in [(s,'check',{}),(s,'check_block',{}),(s,'identity',{'return_value':{}}),(s,'load_cases',{'return_value':[]}),
                (s.Model,'develop',{'return_value':{'fixed':True}}),(s.Model,'evaluate',{'return_value':[]}),
                (s,'block_spec',{'side_effect':lambda f,phase,b:({'study_freeze':b,'budget':{'total_seconds':5250}},[])}),
                (runner,'run',{'side_effect':run_block}),(lifecycle,'host_identity',{'return_value':{}})]:stack.enter_context(patch.object(obj,name,**kw))
            stack.enter_context(patch('subprocess.Popen',side_effect=AssertionError('real process forbidden')))
            result=s.base.run(file,'FAKE',s.p.digest(file),True,adapter=s)
            self.assertEqual(result['status'],'completed_development_and_confirmation')
            self.assertEqual(seen,['development','confirmation'])
            with self.assertRaises(FileExistsError):s.base.run(file,'FAKE',s.p.digest(file),True,adapter=s)

    def test_development_only_fit_keeps_ap_fixed(self):
        cases,z=synthetic();original={'ap':{'beta':.1,'k':1.},'service':{}}
        def read(file):return {'unchanged_model':{'path':'old','sha256':'hash'}} if file==s.CONTRACT else {'model':original}
        with patch.object(s.p,'read',side_effect=read),patch.object(s.p,'digest',return_value='hash'),patch.object(s.original,'energy_at',side_effect=lambda c,a,b:b-a+float(s.original.exposure(c['inputs']['segments'],a,b)@z)):
            fit=s.Model.develop(cases)
            self.assertEqual(fit['ap'],original['ap']);self.assertNotIn('version',original)
            np.testing.assert_allclose(list(fit['energy_increment_w'].values()),z,atol=1e-10)
            self.assertEqual(fit['preload_power_window_s'],[-20,30])
            cases[0]['study_phase']='confirmation'
            with self.assertRaisesRegex(ValueError,'development3'):s.Model.develop(cases)

    def test_actual_plan_builder_budgets_inputs_and_no_device(self):
        archive=Path('C:/Users/LG/Documents/D1Check_Arrival_Extension')
        source=archive/'online_power_sampling_plan_v2/collection_plan.json';build=archive/'separated_power_build_v1/verified_build_receipt.json'
        if not source.exists() or not build.exists():self.skipTest('local signed source fixture unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'study_plan.json';candidate=s.p.read(build)['candidate']
            s.base.cal.write_new(file,dict(source_plan={'path':str(source)},build_receipt={'path':str(build),'sha256':s.p.digest(build)},candidate=candidate,
                contract={'path':str(s.CONTRACT),'sha256':s.p.digest(s.CONTRACT)},output_root=str(root/'run'),block_registry_root=str(root/'registry')))
            for role,n in [('development',3),('confirmation',6)]:
                plan,manifests=s.block_spec(file,role)
                self.assertEqual(len(manifests),n);self.assertNotIn('online_sampling_audit',plan)
                self.assertEqual(plan['budget']['explicit_inference'],n*104)
                self.assertEqual(plan['budget']['total_seconds'],600+n*700+(n-1)*90)
                self.assertEqual(plan['installed_only'],role=='confirmation')
                for m in manifests:
                    s.protocol.validate(role,m['requests']);self.assertEqual(m['power_sample_period_ms'],900)
                    self.assertEqual(m['power_identification_version'],s.protocol.VERSION)
            self.assertFalse((root/'run').exists());self.assertFalse((root/'registry').exists())


if __name__=='__main__':unittest.main()
