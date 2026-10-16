import copy,unittest
from tools import test_d1_list_candidate_service_list as fixtures
from tools import d1_list_candidate_service_backlog as repair
from tools import d1_list_candidate_service_backlog_study as study

class Contract(unittest.TestCase):
    def test_stage_cap_is24_not_confirmation_cap192(self):
        budget=study.Budget.__new__(study.Budget);budget.phase='backlog_development';budget.rows=[dict(phase=budget.phase)]*24
        budget.work_guard=lambda:None
        with self.assertRaisesRegex(TimeoutError,'cap24'):budget.guard()
    def test_backlog_blocks_wait_but_keeps_immediate_L0(self):
        base,q,l=fixtures.Contract().setup_controller();ctrl=repair.BacklogList(base.frozen,base.initial,feature_variant='head2+C_next')
        ctrl.__dict__.update(copy.deepcopy({k:v for k,v in base.__dict__.items() if k not in ('network','selector')}))
        q2=q+[dict(q[1],id='D2',ordinal=2)]
        actions=ctrl.bank(q2,l,35e9);encoded=ctrl.encode(q2,l,35e9,actions)
        self.assertTrue(ctrl.admitted(encoded['base'],encoded,actions,q2))
        for i,a in enumerate(actions):
            if a['wait']>0:self.assertFalse(ctrl.admitted(i,encoded,actions,q2))

if __name__=='__main__':unittest.main()
