"""Service-first claim boundaries; no engine or output authoring."""
import unittest
from tools import d1_ie_dispatch_report as r


def rows():
    base=dict(seed=1,family='low',context='mean',planned=4,completed=4,
        urgent_service_failure=0,normal_service_failure=0,urgent_p95_ms=100.,
        normal_mean_ms=400.,deadline_met=4,energy_j=12.,peak_ap_c=31.)
    return [dict(base,policy=policy) for policy in (*r.BASES,*r.NEW)]


class Eligibility(unittest.TestCase):
    def test_cost_reduction_does_not_hide_worse_response(self):
        xs=rows();xs[-1].update(urgent_p95_ms=101.,energy_j=10.,peak_ap_c=30.)
        ps=[x for x in r.compare(xs) if x['policy']==r.NEW[-1]]
        self.assertTrue(all(not p['service_preserved'] and not p['joint_gain'] for p in ps))

    def test_missing_work_not_success(self):
        xs=rows();xs[-1].update(completed=3,energy_j=8.,peak_ap_c=None)
        self.assertTrue(all(not p['joint_gain'] for p in r.compare(xs) if p['policy']==r.NEW[-1]))

    def test_valid_joint_and_null_are_separate(self):
        xs=rows();xs[-1].update(energy_j=11.,peak_ap_c=30.)
        self.assertTrue(all(p['joint_gain'] for p in r.compare(xs) if p['policy']==r.NEW[-1]))
        xs[-1]['peak_ap_c']=None
        self.assertTrue(all(p['service_preserved'] and not p['cost_eligible'] for p in r.compare(xs) if p['policy']==r.NEW[-1]))

    def test_duplicate_identity_rejected(self):
        xs=rows();xs.append(dict(xs[0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):r.compare(xs)

    def test_baseline_already_late_not_absolute_success(self):
        xs=rows()
        for x in xs:x.update(normal_service_failure=1,deadline_met=3)
        xs[-1].update(energy_j=11.,peak_ap_c=30.)
        ps=[x for x in r.compare(xs) if x['policy']==r.NEW[-1]]
        self.assertTrue(all(p['joint_gain'] and not p['joint_gain_all_deadlines'] for p in ps))


if __name__=='__main__':unittest.main()
