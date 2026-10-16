import copy
import unittest
from tools import d1_slack_residual_design_audit as a


def candidate(kind, signature, reasons):
    return dict(reasons=reasons,effective_action=dict(kind=kind,signature=signature))


class DesignAuditTests(unittest.TestCase):
    def item(self, candidates):
        return dict(row=dict(seed=1,family='fixture',context='mean',planned=1),
            records=[dict(now_ns=35000000000,immutable_caps={'q':36.},candidates=candidates)])

    def tickets(self):
        return [dict(id='q',arrival_ns=35000000000,deadline_offset_ns=6000000000)]

    def test_early_cap_and_hypothetical_new_dispatch_are_not_sla_proof(self):
        x=self.item([candidate('DISPATCH',['DISPATCH','q','CPU'],[]),
                     candidate('DISPATCH',['DISPATCH','q','GPU'],[a.CAP])])
        r=a.analyze(x,self.tickets())
        self.assertEqual(r['mean_unused_deadline_slack_s'],5.)
        self.assertEqual(r['multiple_actions_ignoring_cap'],1)
        self.assertEqual(r['additional_immediate_dispatch_callbacks_ignoring_cap'],1)
        self.assertTrue(r['hypothetical_signatures_are_not_new_feasible_actions'])

    def test_other_vetoes_survive_dropping_cap(self):
        c=[candidate('DISPATCH',['DISPATCH','q','GPU'],[a.CAP,'wait_limit'])]
        self.assertEqual(a.signatures(c,(a.CAP,)),set())

    def test_energy_veto_survives_cap_removal(self):
        c=[candidate('DISPATCH',['DISPATCH','q','GPU'],[a.CAP,a.ENERGY])]
        self.assertEqual(a.signatures(c,(a.CAP,)),set())
        self.assertEqual(len(a.signatures(c,(a.CAP,a.ENERGY))),1)

    def test_busy_lane_and_numeric_rejection_never_count_as_choices(self):
        c=[candidate('INVALID_BUSY_DISPATCH',['DISPATCH','q','GPU'],[a.CAP]),
           candidate('REJECTED',['REJECTED'],[a.CAP])]
        self.assertEqual(a.signatures(c,(a.CAP,)),set())

    def test_wait_dedup_does_not_invent_dispatch_options(self):
        c=[candidate('WAIT',['WAIT',35250000000],[]),
           candidate('WAIT',['WAIT',35250000000],[a.CAP])]
        r=a.analyze(self.item(c),self.tickets())
        self.assertEqual(r['multiple_actions_ignoring_cap'],0)
        self.assertEqual(r['additional_immediate_dispatch_callbacks_ignoring_cap'],0)

    def test_missing_caps_are_reported_not_filled_with_deadline(self):
        x=self.item([]);x['records']=[]
        r=a.analyze(x,self.tickets())
        self.assertEqual(r['missing_caps'],1)
        self.assertIsNone(r['mean_unused_deadline_slack_s'])

    def test_changed_or_future_caps_are_rejected(self):
        x=self.item([]);second=copy.deepcopy(x['records'][0]);second['immutable_caps']['q']=37.
        x['records'].append(second)
        with self.assertRaisesRegex(AssertionError,'cap changed'):a.analyze(x,self.tickets())
        x=self.item([]);x['records'][0]['now_ns']=34000000000
        with self.assertRaisesRegex(AssertionError,'future'):a.analyze(x,self.tickets())


if __name__=='__main__':unittest.main()
