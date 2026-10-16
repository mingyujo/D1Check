import unittest
from tools import d1_thermal_load_gate as x
from tools.test_d1_thermal_slack_v3 import controller,forecasts
from tools.test_d1_ie_dispatch import ticket,lanes

def hand():
    base=controller();return x.Controller(base.frozen,base.initial)
def actions(c,history,queue=None,now=37.4e9):
    c.arrival_history=history;q=queue or [ticket('d',0,'detection',now/1e9,6.)]
    return c.physical_candidates(q,lanes(),now,dict(selected=dict(request_id=q[0]['id'],backend='CPU')))

class LoadGateTests(unittest.TestCase):
    def test_sparse_workload_allows_cooling(self):
        self.assertTrue(any(a['kind']=='cool_wait' for a in actions(hand(),{'a':35e9,'b':36.2e9,'d':37.4e9})))
    def test_burst_and_sustained_pressure_block_cooling(self):
        for step in (.08,.2,.4):
            now=(35+2*step)*1e9;c=hand();aa=actions(c,{'a':35e9,'b':(35+step)*1e9,'d':now},now=now)
            self.assertFalse(any(a['kind']=='cool_wait' for a in aa))
    def test_insufficient_history_never_guesses_a_gap(self):
        self.assertFalse(any(a['kind']=='cool_wait' for a in actions(hand(),{'d':37.4e9})))
    def test_queued_total_work_and_elapsed_window_are_counted(self):
        qs=[ticket('d0',0,'detection',37.4,6.),ticket('d1',1,'detection',37.4,6.)]
        self.assertFalse(any(a['kind']=='cool_wait' for a in actions(hand(),{'a':35e9,'b':36.2e9,'d':37.4e9},qs)))
        self.assertFalse(any(a['kind']=='cool_wait' for a in actions(hand(),{'a':35e9,'b':36.2e9,'d':37.4e9},now=38e9)))
    def test_same_time_arrivals_mean_zero_window(self):
        self.assertFalse(any(a['kind']=='cool_wait' for a in actions(hand(),{'a':35e9,'b':35e9,'d':37.4e9})))
    def test_cooling_requires_absolute_forecast_feasibility(self):
        f=forecasts(peak=29.);g=forecasts()
        for z in f.values():z['feasible']=True
        for z in g.values():z['feasible']=True
        base=dict(kind='single',base=True,jobs=[],forecasts=g);wait=dict(kind='cool_wait',base=False,jobs=[],forecasts=f)
        self.assertIs(x.Controller.select([base,wait]),wait)
        g['mean']['feasible']=False;self.assertIs(x.Controller.select([base,wait]),base)

if __name__=='__main__':unittest.main()
