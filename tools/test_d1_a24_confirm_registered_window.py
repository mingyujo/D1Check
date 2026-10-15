import copy
import unittest
from d1_a24_confirm_registered_window import scoped_rows
from d1_a24_revision02_suite import draft_plan
from d1_a24_laptop_validator import ValidationError


class ConfirmationVisitScopeCases(unittest.TestCase):
    def setUp(self):
        self.plan,_=draft_plan('A24R02-SUITE-CONFIRM-PC-WINDOW')
        self.window={'registered_session_ids':[r['session_id'] for r in self.plan['sessions'][:4]]}

    def test_only_exact_registered_prefix_of_full40_is_selected(self):
        self.assertEqual(scoped_rows(self.plan,self.window),self.plan['sessions'][:4])
        self.assertEqual(len(self.plan['sessions']),40)

    def test_empty_unknown_reordered_or_discontinuous_scope_is_rejected(self):
        ids=self.window['registered_session_ids']
        for bad in ([],['unknown'],ids[::-1],[ids[0],ids[2]],[ids[0],ids[0]]):
            with self.subTest(ids=bad),self.assertRaises(ValidationError):scoped_rows(self.plan,{'registered_session_ids':bad})

    def test_dev8_cannot_be_mislabeled_confirmation(self):
        dev,_=draft_plan('A24R02-SUITE-DEV-PC-WINDOW',stage='DEV')
        with self.assertRaises(ValidationError):scoped_rows(dev,self.window)


if __name__=='__main__':unittest.main()
