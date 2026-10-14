import copy,json,math,unittest
from pathlib import Path
import numpy as np
from tools import d1_dual_trend27 as m
from tools import d1_dual_trend27_runtime as r
from tools import d1_s26_refine26_runtime as prior_s26

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'outputs/DUAL-TREND-CALIBRATION-27'
PKG=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pkg=PKG if(PKG/'profiles/A24.json').exists()else OUT/'repro';cls.a=read(cls.pkg/'profiles/A24.json');cls.s=read(cls.pkg/'profiles/S26.json');cls.fixture=read(cls.pkg/'test_fixture.json')
    def test_additive_level_does_not_change_trend_score(self):
        c=self.fixture['A24'];p=c['initial_c']+np.asarray(c['design'])@c['prior'];a=m.score(c,p);b=m.score(c,p+10)
        self.assertAlmostEqual(a['phase_delta_MAE_c'],b['phase_delta_MAE_c']);self.assertEqual(a['direction_matches'],b['direction_matches']);self.assertGreater(b['absolute_MAE_c'],a['absolute_MAE_c'])
    def test_same_direction_wrong_amplitude_is_penalized(self):
        t=np.arange(0,101);c=dict(identity='x',device='A24',cohort='x',sensor='AP',kind='P',times=t.tolist(),truth=(30+t/20).tolist(),windows=[('rise',0,100)])
        row=m.score(c,30+t/10);self.assertEqual(row['direction_matches'],1);self.assertGreater(row['phase_delta_MAE_c'],4)
    def test_missing_edge_is_not_zero_filled(self):
        self.assertEqual(m.phase_rows([0,2,4,6],[('notcovered',0,60)]),[])
    def test_deadband_flat_separate_from_rise_and_fall(self):
        self.assertEqual([m.direction(x)for x in (-.3,-.1,0,.1,.3)],[-1,0,0,0,1])
    def test_20s_local_trend_responds_to_timing(self):
        a=m.phase_rows(np.arange(0,101,2),[('early',0,20),('late',80,100)]);self.assertEqual(len(a),2);self.assertGreater(a[1]['elapsed_s'],0)
    def test_a24_future_pre_rejected(self):
        pre=copy.deepcopy(self.a['trend27_anchor']['public_boundary']['pre']);pre[-1]['hi']=1.
        with self.assertRaises(ValueError):r.initialize_a24(pre,self.a['trend27_anchor']['public_boundary']['beta'])
    def test_a24_available_and_supported_pair(self):
        cfg=self.a['trend27_anchor'];state=r.A24Cost(self.a['cost_anchor'],cfg['thermal']['AP'],cfg['public_boundary']);state.dispatch('G','classification','GPU');state.dispatch('D','detection','CPU')
        with self.assertRaises(ValueError):state.dispatch('C','classification','CPU')
        self.assertEqual(len(state.owners),2);state.advance(.1);state.available('G','GPU');self.assertIn('CPU',state.owners)
    def test_a24_energy_exact_frozen_state_power(self):
        cfg=self.a['trend27_anchor'];state=r.A24Cost(self.a['cost_anchor'],cfg['thermal']['AP'],cfg['public_boundary']);baseline=cfg['public_boundary']['pre_w'];state.dispatch('G','classification','GPU');state.advance(.1);state.dispatch('D','detection','CPU');state.advance(1.);state.available('G','GPU');state.advance(2.);state.available('D','CPU');state.advance(3.)
        p=self.a['cost_anchor']['energy_increment_w'];expected=3*baseline+.1*p['classification_GPU']+.9*p['classification_GPU+detection_CPU']+p['detection_CPU'];self.assertAlmostEqual(state.energy,expected)
    def test_a24_stream_temperature_against_recorded_affine_design(self):
        c=self.fixture['A24'];cfg=self.a['trend27_anchor'];state=r.A24Cost(self.a['cost_anchor'],cfg['thermal']['AP'],cfg['public_boundary']);segments=c['input']['actual'];queries=np.asarray(c['times'])-35;cursor=0;prediction=[];last=0.;current={}
        for t in queries:
            while cursor<len(segments)and segments[cursor]['end_s']-35<=t:
                segment=segments[cursor];end=max(0,segment['end_s']-35)
                labels=[]if segment['state']=='idle'else segment['state'].replace(':','_').split('+')
                desired={key.rsplit('_',1)[1]:key.rsplit('_',1)[0]for key in labels}
                for b in list(state.owners):
                    if desired.get(b)!=state.owners[b][1]:state.available(state.owners[b][0],b)
                for b,task in desired.items():
                    if b not in state.owners:state.dispatch('test'+str(cursor)+b,task,b)
                state.advance(end);cursor+=1
            segment=segments[cursor]if cursor<len(segments)else dict(state='idle')
            labels=[]if segment['state']=='idle'else segment['state'].replace(':','_').split('+');desired={key.rsplit('_',1)[1]:key.rsplit('_',1)[0]for key in labels}
            for b in list(state.owners):
                if desired.get(b)!=state.owners[b][1]:state.available(state.owners[b][0],b)
            for b,task in desired.items():
                if b not in state.owners:state.dispatch('query'+str(t)+b,task,b)
            state.advance(float(t));prediction.append(state.temperature())
        expected=c['initial_c']+np.asarray(c['design'])@cfg['thermal']['AP']['coefficients'];np.testing.assert_allclose(prediction,expected,atol=1e-8)
    def test_s26_frozen_energy_unchanged_by_thermal_calibration(self):
        cfg=self.s['trend27_anchor'];parent=self.s['refine26_anchor'];a=r.S26Cost(parent['model'],parent['public_boundary'],cfg['thermal'],cfg['preserved23_cost'],cfg['preserved23_initial']);b=prior_s26.CostState(parent['model'],parent['public_boundary'])
        for state in (a,b):
            state.dispatch('C','classification','CPU');state.set_activity([0,0,0,0,1,0]);state.advance(.05);state.set_activity([1,0,0,0,0,0]);state.advance(.1);state.set_activity([0,0,0,0,0,1]);state.advance(.12);state.available('C','CPU');state.set_activity([0]*6);state.advance(1.)
        self.assertAlmostEqual(a.snapshot()['energy_window_j'],b.snapshot()['energy_window_j'],places=12)
    def test_policy_name_is_not_trend_feature(self):
        c=copy.deepcopy(self.fixture['A24']);a=m.fit([dict(c,cohort=str(i))for i in range(3)],c['prior'],[0]*6,[1]*5+[2],.1,1)
        c['policy']='magic';b=m.fit([dict(c,cohort=str(i))for i in range(3)],c['prior'],[0]*6,[1]*5+[2],.1,1);np.testing.assert_array_equal(a['coefficients'],b['coefficients'])

if __name__=='__main__':unittest.main()
