import tempfile
import unittest
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from tools import d1_separated_power_followup as s


class FollowupTests(unittest.TestCase):
    def test_actual_import_and_remaining_plan(self):
        file=Path('C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_plan_v2/study_plan.json')
        if not file.exists():self.skipTest('local prepared fixture absent')
        study=s.p.read(file);cases=s.imported_cases(study)
        self.assertEqual(len(cases),1);self.assertEqual(cases[0]['policy'],'CPU_URGENT_ONLINE_V1')
        dev,_=s.block_spec(file,'development');conf,_=s.block_spec(file,'confirmation')
        self.assertEqual([x['policy'] for x in dev['entries']],list(s.prior.original.POLICIES)[1:])
        self.assertEqual(len(conf['entries']),6)
        self.assertTrue(dev['installed_only']);self.assertEqual(dev['budget']['installs'],0)
        self.assertEqual(dev['budget']['total_seconds']+conf['budget']['total_seconds']+180,7520)
        corrupted=dict(study,imported_development=dict(study['imported_development'],files={'missing':'changed'}))
        with self.assertRaises((OSError,ValueError)):s.imported_cases(corrupted)

    def test_root_imports_before_fit_and_freezes_before_confirmation(self):
        from tools import d1_arrival_energy_collection_device as runner
        from tools import d1_energy_host_lifecycle as lifecycle
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=Path(tmp);(root/'development').mkdir();(root/'confirmation').mkdir()
            s.base.cal.write_new(root/'old.json',{'whole_device_power_w':{}})
            s.base.cal.write_new(root/'development/collection_plan.json',{'frozen_model':{'path':str(root/'old.json')}})
            file=root/'study_plan.json';s.base.cal.write_new(file,dict(output_root=str(root/'run'),registry=str(root/'registry'),contract={'sha256':'fixed'},budget=s.p.read(s.CONTRACT)['budget']))
            seen=[]
            def run_block(file,*args):
                seen.append(file.parent.name)
                if file.parent.name=='confirmation':self.assertTrue((root/'run/model_freeze.json').exists())
                return {'status':'completed_descriptive_only'}
            def fit(cases):self.assertEqual(cases,['importedCPU','newPAR','newSER']);return {'fixed':True}
            for obj,name,kw in [(s,'check',{}),(s,'check_block',{}),(s,'identity',{'return_value':{}}),
                (s,'imported_cases',{'return_value':['importedCPU']}),(s,'load_cases',{'side_effect':[['newPAR','newSER'],['confirm']]}),
                (s.model,'develop',{'side_effect':fit}),(s.model,'evaluate',{'return_value':[]}),
                (s,'block_spec',{'side_effect':lambda f,phase,b:({'study_freeze':b,'budget':{'total_seconds':5250}},[])}),
                (runner,'run',{'side_effect':run_block}),(lifecycle,'host_identity',{'return_value':{}})]:stack.enter_context(patch.object(obj,name,**kw))
            stack.enter_context(patch('subprocess.Popen',side_effect=AssertionError('real process forbidden')))
            result=s.base.run(file,'FAKE',s.p.digest(file),True,adapter=s)
            self.assertEqual(result['status'],'completed_development_and_confirmation')
            self.assertEqual(seen,['development','confirmation'])
            with self.assertRaises(FileExistsError):s.base.run(file,'FAKE',s.p.digest(file),True,adapter=s)


if __name__=='__main__':unittest.main()
