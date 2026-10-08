import copy,unittest
from tools import d1_ie_candidates_v2_report as r


def rows():
    base=dict(seed=1,family='low',context='mean',planned=10,completed=10,deadline_met=10,
        energy_full_work_eligible=True,energy_j=10.,peak_ap_c=30.,urgent_p95_ms=100.,normal_mean_ms=200.,urgent_service_failure=0,normal_service_failure=0)
    return [dict(base,policy=p) for p in r.LABELS]


class Selection(unittest.TestCase):
    def test_missing_heat_is_not_silently_dropped_from_mean(self):
        self.assertIsNone(r.full_mean([dict(peak_ap_c=30.),dict(peak_ap_c=None)],'peak_ap_c'))
    def test_equal_reward_or_schedule_is_not_joint_gain(self):
        self.assertFalse(any(x['eligible'] for x in r.eligibility(rows())))
    def test_both_references_joint_gain_required(self):
        rs=rows();p=next(x for x in rs if x['policy']=='PPO_seed11');p.update(energy_j=9.,peak_ap_c=29.)
        self.assertTrue(next(x for x in r.eligibility(rs) if x['policy']==p['policy'])['eligible'])
        next(x for x in rs if x['policy']==r.TRITON)['energy_j']=8.
        self.assertFalse(next(x for x in r.eligibility(rs) if x['policy']==p['policy'])['eligible'])
    def test_less_work_cannot_win(self):
        rs=rows();p=next(x for x in rs if x['policy']=='DDQN_seed23');p.update(energy_j=8.,peak_ap_c=29.,completed=9,energy_full_work_eligible=False)
        self.assertFalse(next(x for x in r.eligibility(rs) if x['policy']==p['policy'])['eligible'])
    def test_service_regression_disqualifies_cost_saving(self):
        for key,value in [('urgent_p95_ms',101.),('normal_service_failure',1),('deadline_met',9)]:
            rs=rows();p=next(x for x in rs if x['policy']=='DDQN_seed37');p.update(energy_j=8.,peak_ap_c=29.);p[key]=value
            self.assertFalse(next(x for x in r.eligibility(rs) if x['policy']==p['policy'])['eligible'])


if __name__=='__main__':unittest.main()
