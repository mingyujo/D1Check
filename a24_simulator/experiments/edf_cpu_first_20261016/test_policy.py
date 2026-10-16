"""Pure policy/window fixtures; no simulation, fitting, or model initialization."""
import unittest
from policy import select, window_heat

def req(rid, deadline, task='C', arrival=0, ordinal=0):
    return dict(request_id=rid, deadline_ns=deadline, task=task,
                scheduled_arrival_ns=arrival, queue_entry_ns=arrival, ordinal=ordinal)

class EDFTests(unittest.TestCase):
    def state(self, queue, owners=()):
        return dict(now_ns=100, queue=queue, owners=list(owners))
    def test_absolute_deadline_before_arrival_and_task(self):
        s=self.state([req('early-arrival', 300), req('earlier-deadline', 200, 'D', 50)])
        self.assertEqual(select(s),dict(kind='DISPATCH', request_id='earlier-deadline',route='CPU'))
    def test_no_prediction_selection(self):
        s=self.state([req('a',200)])
        s['estimates']={'a':{'CPU':{'response_ns':10**12,'energy_proxy_j':999},
                             'GPU':{'response_ns':1,'energy_proxy_j':0}}}
        self.assertEqual(select(s)['route'],'CPU')
    def test_cpu_busy_uses_gpu_for_both_tasks(self):
        for task in ('C','D'):
            self.assertEqual(select(self.state([req('a',200,task)], [{'route':'CPU'}]))['route'],'GPU')
    def test_gpu_busy_uses_cpu(self):
        self.assertEqual(select(self.state([req('a',200)], [{'route':'GPU'}]))['route'],'CPU')
    def test_busy_and_empty_wait(self):
        self.assertEqual(select(self.state([req('a',200)],[{'route':'CPU'},{'route':'GPU'}])),{'kind':'RESOURCE_WAIT'})
        self.assertEqual(select(self.state([])),{'kind':'RESOURCE_WAIT'})
    def test_equal_deadline_arrival_then_ordinal(self):
        self.assertEqual(select(self.state([req('z',200,arrival=50),req('b',200,ordinal=2),req('a',200,ordinal=1)]))['request_id'],'a')
    def test_future_is_rejected(self):
        with self.assertRaises(ValueError): select(self.state([req('a',300,arrival=101)]))
    def test_invalid_lane_is_rejected(self):
        with self.assertRaises(ValueError): select(self.state([req('a',300)],[{'route':'NPU'}]))
    def test_does_not_mutate_input(self):
        import copy
        s=self.state([req('b',300),req('a',200)]);old=copy.deepcopy(s)
        select(s);self.assertEqual(s,old)
    def test_heat_exact_interpolated_window(self):
        s={'AP':{'t_s':[0,1,2],'ap_c':[20,22,24]}}
        m=window_heat(s,.25,1.75)
        self.assertAlmostEqual(m['mean_AP_c'],22)
        self.assertAlmostEqual(m['peak_AP_c'],23.5)
        self.assertAlmostEqual(m['end_AP_c'],23.5)
    def test_heat_missing_coverage_rejected(self):
        with self.assertRaises(ValueError): window_heat({'AP':{'t_s':[0,1],'ap_c':[20,22]}},0,2)
    def test_heat_constant(self):
        self.assertAlmostEqual(window_heat({'AP':{'t_s':[0,1,2],'ap_c':[21,21,21]}},.2,1.3)['mean_AP_c'],21)

if __name__=='__main__': unittest.main()
