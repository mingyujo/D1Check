import copy
import unittest
from tools import d1_simulation_model_v2 as m
from tools import d1_simulation_model_v2_report as report
from tools import d1_arrival_plan as p
from tools import d1_separated_power_protocol as s


class ReportTests(unittest.TestCase):
    def test_completed_p95_excludes_failed_response_and_keeps_full_arrival_denominator(self):
        rows=[dict(priority='urgent',terminal_status=status,scheduled_arrival_ns=0,output_ready_ns=t,deadline_ns=1_500_000_000)
              for status,t in [('succeeded',1_000_000_000),('succeeded',2_000_000_000),('failed',9_000_000_000),('unfinished',None)]]
        rows.append(dict(priority='normal',terminal_status='unfinished',scheduled_arrival_ns=0,persist_complete_ns=None,deadline_ns=6_000_000_000))
        s=report.actual_service(dict(actual_requests=rows))
        self.assertEqual(s['urgent']['response_P95_ms'],2000)
        self.assertEqual(s['urgent']['completion_success_rate'],.5)
        self.assertEqual(s['urgent']['service_success_rate'],.25)
        self.assertEqual(s['urgent']['planned'],4)
        self.assertIsNone(s['normal']['response_P95_ms'])
    def test_future_measurement_changes_scores_but_not_forecast_or_initial_state(self):
        original=p.read(m.prior.MODEL);model=copy.deepcopy(original)
        model['ap']=dict(beta=original['ap']['beta'],slow_tau_s=1920.,slow_input_w=original['energy_increment_w'],coefficients=[.03]*5)
        model['service']=m.archive_service();rows=s.requests('confirmation','fixture')
        tickets=[dict(id=r['request_id'],ordinal=r['ordinal'],task=r['task_id'],priority=r['priority'],arrival_ns=r['offset_ms']*1000000,deadline_offset_ns=r['deadline_ms']*1000000) for r in rows]
        simulated=m.simulate(tickets,model['service'],'PAR')['ledger']
        actual=[dict(r,request_id=r['id'],terminal_status=r['status'],scheduled_arrival_ns=r['arrival_ns'],deadline_ns=r['arrival_ns']+r['deadline_offset_ns']) for r in simulated]
        initial=p.read(m.ROOT/'docs/results/online_policy_study_01/overnight_sustained_run01/initial_inputs.json')[0]['initial']
        c=dict(policy='ARRIVAL_PAR96',manifest_requests=rows,actual_requests=actual,pre=initial['preload'],pre_w=initial['preload_power_w'],q=list(range(35,181)),ap=[29.]*146,power_t=list(range(-30,182)),power_w=[1.]*212)
        before=report.arrival_assessment(c,model,original);c['ap']=[60.]*146;c['power_w']=[2.]*212
        after=report.arrival_assessment(c,model,original)
        self.assertEqual(before['ledger'],after['ledger']);self.assertEqual(before['predicted_AP_c'],after['predicted_AP_c']);self.assertEqual(before['initial'],after['initial'])
        self.assertNotEqual(before['energy_signed_j'],after['energy_signed_j']);self.assertNotEqual(before['AP_scores'],after['AP_scores'])

if __name__=='__main__':unittest.main()
