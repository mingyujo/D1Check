import unittest
from tools import d1_simulation_model_v3 as model


class V3StudyTests(unittest.TestCase):
    def test_primary_uses_arrival_contract_and_equal_sources_not_long_recovery(self):
        rows=[dict(id='old'+str(i),group='old',mode='B',error=2.) for i in range(6)]
        rows+=[dict(id='history',group='history30',mode='B',error=6.),
               dict(id='recovery',group='new_recovery',mode='A',error=1000.)]
        score=model.aggregate_rows(rows)
        self.assertEqual(score['primary_mean'],4.)
        self.assertEqual(score['primary_mode'],'B')
        self.assertEqual(score['A_source_means']['new_recovery'],1000.)

    def test_no_arrival_contract_falls_back_explicitly_to_A(self):
        score=model.aggregate_rows([dict(id='a',group='macro',mode='A',error=2.),dict(id='b',group='new_recovery',mode='A',error=4.)])
        self.assertEqual(score['primary_mean'],3.)
        self.assertIn('fallback',score['primary_mode'])

    def test_candidate_roster_is_bounded_and_ties_choose_strong_prior_small_correction(self):
        self.assertEqual(len(model.candidate_choices('thermal')),18)
        self.assertEqual(len(model.candidate_choices('energy')),18)
        score=dict(primary_mean=1.,worst_group=1.,worst_session=1.)
        a=model.choice_key(score,dict(lambda_=100.,gain=0.),'energy')
        b=model.choice_key(score,dict(lambda_=10.,gain=1.),'energy')
        self.assertLess(a,b)


if __name__=='__main__':unittest.main()
