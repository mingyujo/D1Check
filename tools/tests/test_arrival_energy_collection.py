import json
import tempfile
import unittest
from pathlib import Path

from tools import d1_arrival_energy_collection as plan
from tools import d1_arrival_energy_analysis as analysis


class ArrivalEnergyCollectionTest(unittest.TestCase):
    def test_api_overlap_is_only_intersection(self):
        rows=[dict(selected_backend='CPU',execution_start_ns=0,lane_available_ns=10_000_000_000),
              dict(selected_backend='GPU',execution_start_ns=4_000_000_000,lane_available_ns=6_000_000_000),
              dict(selected_backend='GPU',execution_start_ns=11_000_000_000,lane_available_ns=12_000_000_000)]
        self.assertEqual(2,analysis.lane_overlap_s(rows))
    def test_fixed_trace_and_budget(self):
        self.assertEqual(12, len(plan.layout()))
        self.assertEqual(10620, plan.BUDGET['total_seconds'])
        self.assertEqual(700, sum(plan.BUDGET[x] for x in
            ('stage_gate_seconds','host_poll_seconds','recovery_seconds','cleanup_seconds')))
        for scenario in plan.SCENARIOS:
            rows=plan.requests(scenario,'f0dfc551-f69f-5c7e-8650-47a5ba878cb9')
            self.assertEqual(24,len(rows))
            self.assertEqual(6,sum(x['priority']=='urgent' for x in rows))
            self.assertEqual(sorted(x['offset_ms'] for x in rows),[x['offset_ms'] for x in rows])
        self.assertEqual(27600,plan.requests('low','s')[-1]['offset_ms'])
        self.assertEqual(4600,plan.requests('queue','s')[-1]['offset_ms'])
        self.assertEqual(4840,plan.requests('burst','s')[-1]['offset_ms'])

    def test_common_and_completion_energy_are_different_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'00_case';a=folder/'artifacts';a.mkdir(parents=True)
            def put(name,value):(a/name).write_text(json.dumps(value),encoding='utf-8')
            put('manifest.json',dict(session_id='s',phase='development',scenario='queue',policy='CPU_URGENT'))
            put('summary.json',dict(status='completed'));put('cleanup.json',dict(status='completed'))
            put('common_boundary.json',dict(start_ns=30_000_000_000,planned_end_ns=150_000_000_000,
                                             end_ns=150_100_000_000))
            put('requests.json',[dict(request_id=str(i),priority='urgent' if i%4==1 else 'normal',
                selected_backend='CPU',execution_start_ns=32_000_000_000,
                terminal_status='succeeded',scheduled_arrival_ns=30_000_000_000,
                deadline_ns=40_000_000_000,output_ready_ns=35_000_000_000,
                persist_complete_ns=40_000_000_000+i,lane_available_ns=41_000_000_000+i)
                                 for i in range(24)])
            events=[]
            def add(kind,phase,ns,**kwargs):events.append(dict(kind=kind,phase=phase,mono_ns=ns,sequence=len(events),**kwargs))
            add('phase_start','resident_baseline',0)
            for s in range(211):
                ns=s*1_000_000_000
                add('power_sample','x',ns+100_000_000,snapshot_start_ns=ns,
                    sensor_read_end_ns=ns+100_000_000,state_snapshot_ns=ns+100_000_000,
                    current_raw=-1000,voltage_mV=4000,plugged=0,current_valid=True)
            add('phase_end','resident_baseline',30_000_000_000)
            add('phase_end','resident_cooling',210_000_000_000)
            (a/'progress.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf-8')
            (folder/'thermal.jsonl').write_text(''.join(json.dumps(dict(mono_ns=s*1_000_000_000,AP='30.0',
                sampling_uncertainty_ns=0))+'\n' for s in range(0,212,2)),encoding='utf-8')
            x=analysis.summarize(folder)
            common=x['windows'][1];completion=x['windows'][2]
            self.assertAlmostEqual(480,common['energy_j_conditional_mA'])
            self.assertAlmostEqual(40,completion['energy_j_conditional_mA'],places=4)
            self.assertEqual(0,x['common_unfinished'])
            # A missing current segment is unknown, never a zero-energy success.
            events=[e for e in events if not (e['kind']=='power_sample' and 70_000_000_000<=e['snapshot_start_ns']<=75_000_000_000)]
            for i,e in enumerate(events):e['sequence']=i
            (a/'progress.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf-8')
            self.assertIsNone(analysis.summarize(folder)['windows'][1]['energy_j_conditional_mA'])


if __name__=='__main__':unittest.main()
