from pathlib import Path
import sys,unittest
P=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(P/'src'),str(P/'reference/model_integration')]
from diagnostics import schedule_groups,add_diagnostics
from four_route_model import extend_gains,labels,conditional_energy
class Tests(unittest.TestCase):
 def test_equivalence(self):
  r={'policy':'A','requests':[{'request_id':'x','route':'CPU','dispatch_ns':1,'response_ns':2,'available_ns':3}],'wait_s':0}
  b={**r,'policy':'B'};self.assertEqual(schedule_groups([r,b])['unique_schedules'],1)
  b={**b,'requests':[{**r['requests'][0],'route':'GPU'}]};self.assertEqual(schedule_groups([r,b])['unique_schedules'],2)
 def test_preserved_baseline(self):
  p={'cost_anchor':{'energy_increment_w':dict(zip(__import__('thermal_four_route').STATES,[1]*8))},'measured35':{'baseline_w':2}}
  s={'owner_intervals':[{'task':'C','route':'CPU','start_s':1.,'end_s':3.}],'activity_coverage_s':[0,180]}
  e=conditional_energy(s,p);self.assertEqual(e['baseline_J'],360);self.assertEqual(e['historical_conditional_J'],362)
 def test_lane_safety(self):
  with self.assertRaises(ValueError):labels([{'task':'C','route':'CPU'},{'task':'D','route':'CPU'}])
 def test_transfer_not_inflated(self):
  self.assertEqual(extend_gains([1,2,3,4]),[1,2,3,4,4,4,3,5])
if __name__=='__main__':unittest.main()
