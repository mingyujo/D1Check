import unittest
import numpy as np
from shared_policy import minimum_legal


class ChoiceContracts(unittest.TestCase):
    def bank(self):
        mask=np.zeros(76,dtype=bool);mask[[0,1,3]]=True
        return dict(mask=mask,prior_logits=np.zeros(76))

    def test_choose_lowest_exact_cost(self):
        c={i:dict(marginal_full_episode_J_proxy=e) for i,e in ((0,.3),(1,.2),(3,.4))}
        self.assertEqual(minimum_legal(self.bank(),c),1)

    def test_mask_cannot_be_bypassed(self):
        c={i:dict(marginal_full_episode_J_proxy=e) for i,e in ((0,.3),(1,.2),(3,.4),(4,-10))}
        with self.assertRaises(ValueError):minimum_legal(self.bank(),c)

    def test_all_legal_candidates_required(self):
        with self.assertRaises(ValueError):minimum_legal(self.bank(),{0:dict(marginal_full_episode_J_proxy=.1)})

    def test_old_prior_tiebreak_is_deterministic(self):
        b=self.bank();b['prior_logits'][3]=1
        c={i:dict(marginal_full_episode_J_proxy=.2) for i in (0,1,3)}
        self.assertEqual(minimum_legal(b,c),3)


if __name__=='__main__':unittest.main()
