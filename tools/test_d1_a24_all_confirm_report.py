"""PC-only checks: missing HAL coverage never becomes a thermal improvement."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from d1_a24_all_confirm_report import thermal_pair_eligibility, aggregate
from d1_a24_measurement_report import save_csv


def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


class ReportBoundaries(unittest.TestCase):
    def test_gap_excludes_peak_and_ci_without_changing_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            sessions=[];paired=[]
            for b,gap in [('A',True),('B',False)]:
                for arm in ['BASE','PAIR_G']:
                    sessions.append({'block':b,'recipe':'M128','arm':arm,'thermal_window_status':
                        'INELIGIBLE_GAP' if gap and arm=='BASE' else 'READOUT_WINDOW_COVERED'})
                paired.append({'comparison':'혼합 병행','block':b,'status':'PAIRED',
                    'delta_mean_AP_c':-.1,'delta_observed_peak_AP_c':-.5,'delta_C_on_time_rate_all_planned':.8})
            save_csv(p/'sessions.csv',sessions);save_csv(p/'paired.csv',paired)
            save_csv(p/'paired_intervals.csv',[{'comparison':'혼합 병행','metric':'delta_observed_peak_AP_c',
                'n_independent_blocks':2,'mean':-.5,'lower95':-.5,'upper95':-.5}])
            thermal_pair_eligibility(p);a,b=rows(p/'paired.csv')
            self.assertEqual(a['thermal_pair_eligible'],'False');self.assertEqual(a['delta_observed_peak_AP_c'],'')
            self.assertEqual(a['delta_C_on_time_rate_all_planned'],'0.8')
            self.assertEqual(b['thermal_pair_eligible'],'True');self.assertEqual(b['delta_observed_peak_AP_c'],'-0.5')
            interval=rows(p/'paired_intervals.csv')[0]
            self.assertEqual(interval['n_independent_blocks'],'1');self.assertEqual(interval['lower95'],'')
            self.assertEqual(rows(p/'paired_frozen_export.csv')[0]['delta_observed_peak_AP_c'],'-0.5')

    def test_partial_plan_cannot_be_called_original40(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for name,value in [('plan',{'session_count':1,'sessions':[{'stage':'CONFIRM'}]}),('binding',{})]:
                (p/(name+'.json')).write_text(json.dumps(value),encoding='utf-8')
            job={'plan':str(p/'plan.json'),'global_binding':str(p/'binding.json')}
            (p/'job.json').write_text(json.dumps(job),encoding='utf-8')
            with self.assertRaises(ValueError):aggregate(p/'job.json',p/'view',p/'report')
            self.assertFalse((p/'view').exists())


if __name__=='__main__':unittest.main()
