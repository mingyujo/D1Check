import unittest
from tools import d1_overnight_rl_amount as x

class AmountContract(unittest.TestCase):
    def test_budget_arithmetic(self):
        a=x.arithmetic();self.assertEqual(a['normal'],sum(a[k] for k in ('reference','train','development','confirmation','no_wait')))
        self.assertEqual(a['conditional_total'],a['normal']+a['conditional_no_thermal']);self.assertEqual(a['learning'],3*(512-32));self.assertLessEqual(a['conditional_total'],a['cap'])
    def test_partition(self):
        self.assertEqual(len(x.x.cases(x.TRAIN_SEEDS,True)),480);self.assertEqual(len(x.x.cases(x.FINAL_SEEDS)),48)
        self.assertFalse(set(x.TRAIN_SEEDS)&set(x.FINAL_SEEDS));self.assertEqual(x.TARGETS,(64,128,256,512))
    def rows(self,n=2):
        return [dict(condition=i,policy=role,family='low',planned=2,completed=2,incomplete=0,urgent_failure=0,normal_failure=0,urgent_p95_ms=100,energy_j=2 if role=='PPO' else 3,peak_ap_c=30) for i in range(n) for role in ('Band','Triton','Rule','PPO')]
    def test_gate_all_common(self):self.assertTrue(x.gate_rows(self.rows(),'PPO',2)['promising'])
    def test_gate_duplicate(self):
        rows=self.rows();rows.append(rows[0])
        with self.assertRaises(ValueError):x.gate_rows(rows,'PPO',2)
    def test_service_loss_blocks_energy(self):
        rows=self.rows();rows[-1]['normal_failure']=1
        self.assertFalse(x.gate_rows(rows,'PPO',2)['promising'])
    def test_equal_policy_is_not_gain(self):
        rows=self.rows()
        for q in rows:q['energy_j']=3
        self.assertFalse(x.gate_rows(rows,'PPO',2)['promising'])
    def test_rule_nonworse_required(self):
        rows=self.rows();rows[2]['energy_j']=1
        self.assertFalse(x.gate_rows(rows,'PPO',2)['maintenance_pass'])

if __name__=='__main__':unittest.main()
