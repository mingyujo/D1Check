"""Snapshots only; no engine episode, training, timing restoration or LP."""
from pathlib import Path
import sys,unittest
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'experiments/coupled_345_20261017'))
from dynamics import Physics,Config
sys.path.insert(0,str(HERE))
from guard_controller import GuardController


class Nominal:
    def vector(self,q,r,state):return [.005]*5


class Tests(unittest.TestCase):
    def actor(self,on):
        import json
        physics=Physics(json.loads((ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json').read_text()),Config())
        return GuardController(Nominal(),physics,dict(n=2,service_stop_s=755,drain_stop_s=785),'EDF',deadline_guard=on)

    def state(self,due=39.,spent=0):
        return dict(now_ns=40_000_000_000,queue=[dict(request_id='a',ordinal=0,task='C',priority='U',scheduled_arrival_ns=35_000_000_000,queue_entry_ns=35_000_000_000,deadline_ns=round(due*1e9)),
                    dict(request_id='b',ordinal=1,task='D',priority='N',scheduled_arrival_ns=35_100_000_000,queue_entry_ns=35_100_000_000,deadline_ns=80_000_000_000)],owners=[],
                    sensor=dict(temperature_c=34.,shared_z=1.,peak_c=34.,increment_so_far=.05),wait_used_ns=spent)

    def options(self,on,due=39.,spent=0,head=0):
        a=self.actor(on);a.wait_per_head['a']=head;a(self.state(due,spent));return a.calls[-1]['actions']

    def test_only_wait_mask_changes_for_late_urgent(self):
        on=self.options(True);off=self.options(False)
        self.assertEqual(on,[x for x in off if x['kind']=='DISPATCH'])
        self.assertEqual(sum(x['kind']=='WAIT' for x in on),0)
        self.assertEqual(sum(x['kind']=='WAIT' for x in off),3)

    def test_safe_waits_unchanged(self):self.assertEqual(self.options(True,80.),self.options(False,80.))
    def test_global_cap_unchanged(self):
        for on in (True,False):self.assertFalse(any(x['kind']=='WAIT' for x in self.options(on,spent=12_000_000_000)))
    def test_per_head_cap_unchanged(self):
        for on in (True,False):self.assertFalse(any(x['kind']=='WAIT' for x in self.options(on,head=1.5)))

    def test_no_other_baseline_source_change(self):
        a=(HERE/'guard_controller.py').read_text(encoding='utf-8')
        a=a.replace('Only urgent WAIT deadline mask is configurable; every other baseline line retained.','Public-only candidate continuations and independently acting neural policy.')
        a=a.replace('class GuardController:','class Controller:')
        a=a.replace('mode,learner=None,collect=False,deadline_guard=True):','mode,learner=None,collect=False):')
        a=a.replace('\n        self.deadline_guard=deadline_guard','')
        a=a.replace('feasible=(not self.deadline_guard) or all(','feasible=all(')
        self.assertEqual(a,(ROOT/'experiments/coupled_345_20261017/controller.py').read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
