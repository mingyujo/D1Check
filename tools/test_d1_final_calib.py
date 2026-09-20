import copy
import json
from pathlib import Path
import tempfile
import unittest
from tools import d1_final_calib as f


class FinalPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for task in ('classification', 'detection'):
            q = [dict(model_key=task+'_'+b, sample_id='00', priority='normal', role='calibration', worker=0, offset_ms=0) for b in ('CPU','GPU','CPU')]
            (self.root/f'transition_{task}.json').write_text(json.dumps(dict(purpose='transition',allowed_concurrency=1,requests=q)))
        for c,g in [('CPU','GPU'),('GPU','CPU')]:
            q = [dict(model_key=t+'_'+b, sample_id='00',priority='urgent' if w==0 else 'normal',role='calibration',worker=w,offset_ms=o)
                 for o in (0,30000,30500,31000,31500) for w,(t,b) in enumerate([('classification',c),('detection',g)])]
            (self.root/f'corun_classification_{c}_detection_{g}.json').write_text(json.dumps(dict(purpose='corun',allowed_concurrency=2,requests=q)))
        self.samples = [f'{i:016x}' for i in range(20)]

    def test_fixed_counts_and_bounds(self):
        p=f.make_plan(self.root,self.samples)
        self.assertEqual([sum(x['phase']==phase for x in p['sessions']) for phase in 'ABC'],[4,16,2])
        self.assertEqual(len({x['session_id'] for x in p['sessions']}),22)
        for e in p['sessions']:self.assertTrue(f.check_entry(p,e))

    def test_seed_reproducible(self):
        self.assertEqual(f.recipes(self.root,self.samples),f.recipes(self.root,self.samples))

    def test_control_matches_arrivals_and_mix(self):
        r=f.recipes(self.root,self.samples)
        a=r['corun_classification_CPU_detection_GPU']['requests'];b=r['CPU_only_control']['requests']
        for x,y in zip(a,b):
            for k in ('sample_id','priority','offset_ms'):self.assertEqual(x[k],y[k])
            self.assertEqual(x['model_key'].split('_')[0],y['model_key'].split('_')[0])
            self.assertTrue(y['model_key'].endswith('_CPU'))

    def test_drift_rejected(self):
        p=f.make_plan(self.root,self.samples);e=copy.deepcopy(p['sessions'][0]);e['recipe']['requests'][0]['offset_ms']=1
        with self.assertRaises(ValueError):f.check_entry(p,e)

    def test_no_overwrite(self):
        p=self.root/'lock.json';f.save_new(p,{})
        with self.assertRaises(FileExistsError):f.save_new(p,{})

    def test_solo_has_twenty_warm_images(self):
        r=f.recipes(self.root,self.samples)['solo_classification_CPU']['requests']
        self.assertEqual(len(r),22);self.assertEqual(len({q['sample_id'] for q in r[2:]}),20)

    def test_early_corun_retains_original_arrivals(self):
        r=f.recipes(self.root,self.samples)['corun_classification_CPU_detection_GPU']['requests']
        self.assertEqual([q['offset_ms'] for q in r],[0]*4+[30000]*2+[30500]*2+[31000]*2+[31500]*2)

    def test_bad_worker_rejected(self):
        r=f.recipes(self.root,self.samples)['CPU_only_control'];r['requests'][0]['worker']=1
        with self.assertRaises(ValueError):f.validate_recipe(r)


if __name__=='__main__':unittest.main()
