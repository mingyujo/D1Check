import unittest
from unittest.mock import patch
from tools import d1_separated_power_protocol as p


class SeparatedProtocolTests(unittest.TestCase):
    def test_fixed_arrivals_and_balanced_counts(self):
        for role in ('development','confirmation'):
            rows=p.requests(role);p.validate(role,rows)
            self.assertEqual(sum(r['task_id']=='classification' for r in rows),48)
            self.assertEqual(len(rows),96)
            self.assertTrue(all(a['offset_ms']<b['offset_ms'] for a,b in zip(rows,rows[1:])))
        rows=p.requests('development')
        self.assertEqual([rows[i]['offset_ms'] for i in (0,32,64)],[35000,55000,85000])
        self.assertTrue(all(r['task_id']=='classification' for r in rows[:32]))
        self.assertTrue(all(r['task_id']=='detection' for r in rows[32:64]))

    def test_reject_late_shift_or_confirmation_relabel(self):
        rows=p.requests('development');rows[32]['offset_ms']+=1
        with self.assertRaises(ValueError):p.validate('development',rows)
        with self.assertRaises(ValueError):p.validate('development',p.requests('confirmation'))
        with self.assertRaises(ValueError):p.requests('retry')

    def test_actual_forecast_entry_requires_planning_opt_in(self):
        from tools.test_d1_online_policy_study import synthetic
        cases,z=synthetic()
        with patch.object(p.m,'energy_at',side_effect=lambda c,a,b:b-a+float(p.m.exposure(c['inputs']['segments'],a,b)@z)):
            frozen=p.m.develop(cases)
        rows=p.requests('development')
        with self.assertRaisesRegex(ValueError,'unregistered'):p.m.forecast({},rows,p.m.POLICIES[0],frozen)
        result,_=p.m.forecast({},rows,p.m.POLICIES[0],frozen,planning_input_role='development')
        self.assertEqual(len(result['ledger']),96)
        self.assertTrue(all(r['status']=='succeeded' for r in result['ledger']))


if __name__=='__main__':unittest.main()
