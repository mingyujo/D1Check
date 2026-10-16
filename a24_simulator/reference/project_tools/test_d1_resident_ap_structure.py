import copy
import unittest
import numpy as np
from tools import d1_resident_ap_structure as s


class StructureTests(unittest.TestCase):
    def case(self,profile='DEV_A',sid='fixture'):
        pre=[dict(t=float(t),ap=28.,lo=t-.1,hi=t+.1) for t in range(-30,35,2)]
        cursor=35.;actual=[dict(start_s=0.,end_s=35.,state='idle')]
        for b in s.roster.blocks(profile):
            state='+'.join(sorted(s.roster.old.KEYS[i] for i in b['lane_indices'])) or 'idle'
            actual.append(dict(start_s=cursor,end_s=cursor+b['seconds'],state=state));cursor+=b['seconds']
        actual.append(dict(start_s=cursor,end_s=815.,state='idle'))
        return dict(id=sid,role='development',policy=profile,pre=pre,actual=actual,q=list(range(35,815,3)))

    def original(self):return s.j.m.read(s.j.m.MODEL)

    def model(self,mode='STATE_DELAYED'):
        o=self.original()
        return dict(mode=mode,coefficients=[.08,.12,.05,.2,.7] if mode=='STATE_DELAYED' else [.08,.12,.05,.2],
                    beta_fixed=o['ap']['beta'],tau_fixed_s=30.,original_model_sha256=s.j.m.MODEL_SHA)

    def test_synthetic_four_state_and_delayed_coefficients_recovered(self):
        o=self.original();expected=self.model();cases=[]
        for i,p in enumerate(['DEV_A','DEV_B','DEV_A']):
            c=self.case(p,str(i));c['ap']=s.predict(c,o,expected)[0];cases.append(c)
        fitted=s.fit(cases,o,'STATE_DELAYED')
        np.testing.assert_allclose(fitted['coefficients'],expected['coefficients'],atol=1e-10,rtol=0)
        self.assertEqual(fitted['numerical_rank'],5)
        self.assertFalse(fitted['default'])

    def test_targets_and_future_power_never_enter_prediction(self):
        c=self.case();c['ap']=[0]*len(c['q']);a=s.predict(c,self.original(),self.model())[0]
        c['ap']=[1000]*len(c['q']);c['power_w']=[float('nan')]*100
        self.assertEqual(a,s.predict(c,self.original(),self.model())[0])

    def test_zero_delayed_is_same_direct_model_and_paths_add(self):
        c=self.case();full=self.model();full['coefficients'][-1]=0.
        a,parts=s.predict(c,self.original(),full);b,_=s.predict(c,self.original(),self.model('STATE_DIRECT'))
        np.testing.assert_allclose(a,b,atol=1e-12)
        np.testing.assert_allclose(a,np.array(parts['initial_path_c'])+parts['direct_path_c']+parts['delayed_path_c'],atol=1e-12)

    def test_identical_state_split_keeps_temperature_continuity(self):
        c=self.case();before=s.predict(c,self.original(),self.model())[0];r=c['actual'][1];mid=(r['start_s']+r['end_s'])/2
        c['actual'][1:2]=[dict(r,end_s=mid),dict(r,start_s=mid)]
        np.testing.assert_allclose(before,s.predict(c,self.original(),self.model())[0],atol=1e-11,rtol=0)

    def test_archived_colon_alias_uses_same_task_specific_state(self):
        c=self.case();before=s.predict(c,self.original(),self.model())[0]
        for seg in c['actual']:seg['state']=seg['state'].replace('_CPU',':CPU').replace('_GPU',':GPU')
        self.assertEqual(before,s.predict(c,self.original(),self.model())[0])

    def test_future_initialization_and_unknown_state_blocked(self):
        c=self.case();c['pre'][-1]['hi']=35.
        with self.assertRaisesRegex(ValueError,'future AP'):s.predict(c,self.original(),self.model())
        c=self.case();c['actual'][1]['state']='detection_GPU'
        with self.assertRaisesRegex(ValueError,'unsupported state'):s.predict(c,self.original(),self.model())

    def test_confirmation_or_archival_development_cannot_fit(self):
        cs=[self.case(sid=str(i)) for i in range(3)];cs[0]['role']='confirmation'
        with self.assertRaisesRegex(ValueError,'fit forbidden'):s.fit(cs,self.original(),'STATE_DELAYED')
        cs[0]['role']='development';cs[0]['policy']='CPU_URGENT_ONLINE_V1'
        with self.assertRaisesRegex(ValueError,'fit forbidden'):s.fit(cs,self.original(),'STATE_DELAYED')

    def test_rank_deficiency_and_negative_coefficients_blocked(self):
        cs=[self.case(sid=str(i)) for i in range(3)]
        for c in cs:c['actual']=[dict(start_s=0.,end_s=815.,state='idle')];c['ap']=[28]*len(c['q'])
        with self.assertRaisesRegex(ValueError,'unidentified'):s.fit(cs,self.original(),'STATE_DELAYED')
        m=self.model();m['coefficients'][0]=-1
        with self.assertRaisesRegex(ValueError,'coefficient mismatch'):s.predict(self.case(),self.original(),m)

    def test_original_frozen_hash_unchanged(self):
        self.assertEqual(s.sha(s.j.m.MODEL),s.j.m.MODEL_SHA)

    def test_opt_in_scope_blocks_arrival_other_device_and_modified_candidate(self):
        scope=s.j.m.read(s.BUNDLE/'application_scope.json');model=s.j.m.read(s.BUNDLE/'run_v2/candidate.json')
        c=self.case();c['common_end_s']=635.;context=copy.deepcopy(scope['expected_context'])
        result=s.forecast_candidate(c,self.original(),model,context)
        self.assertIsNotNone(result['prediction_ap_c']);self.assertFalse(result['strict_support'])
        context['device_model']='S26'
        self.assertIsNone(s.forecast_candidate(c,self.original(),model,context)['prediction_ap_c'])

        context=scope['expected_context'];c['policy']='CPU_URGENT_ONLINE_V1'
        self.assertIsNone(s.forecast_candidate(c,self.original(),model,context)['prediction_ap_c'])
        c['policy']='DEV_A';c['pre'][-1]['ap']=29.
        self.assertIsNone(s.forecast_candidate(c,self.original(),model,context)['prediction_ap_c'])
        c['pre'][-1]['ap']=None
        self.assertIsNone(s.forecast_candidate(c,self.original(),model,context)['prediction_ap_c'])
        c=self.case();c['common_end_s']=635.;c['pre'][0]['ap']=None
        self.assertIsNone(s.forecast_candidate(c,self.original(),model,context)['prediction_ap_c'])
        c=self.case();c['common_end_s']=635.;c['actual']=[dict(start_s=0.,end_s=815.,state='idle')]
        self.assertIsNone(s.forecast_candidate(c,self.original(),model,context)['prediction_ap_c'])
        c=self.case();c['common_end_s']=635.;c['actual'][-1]['end_s']=830.;c['q'].append(818.)
        self.assertIsNone(s.forecast_candidate(c,self.original(),model,context)['prediction_ap_c'])
        c=self.case();c['common_end_s']=635.;model['coefficients'][0]+=1.
        self.assertIsNone(s.forecast_candidate(c,self.original(),model,context)['prediction_ap_c'])

    def test_one_sided_completion_after_pair_deadline_is_not_new_dispatch(self):
        c=self.case();pair=c['actual'][-2];idle=c['actual'][-1];deadline=pair['end_s']
        c['actual'][-2:]=[dict(pair,end_s=deadline+.1),
                          dict(start_s=deadline+.1,end_s=deadline+.4,state='detection_CPU'),
                          dict(idle,start_s=deadline+.4)]
        self.assertTrue(s.registered_schedule(c))
        c['actual'][-3]['end_s']=deadline+30.1;c['actual'][-2]['start_s']=deadline+30.1
        c['actual'][-2]['end_s']=deadline+30.4;c['actual'][-1]['start_s']=deadline+30.4
        self.assertFalse(s.registered_schedule(c))


if __name__=='__main__':unittest.main()
