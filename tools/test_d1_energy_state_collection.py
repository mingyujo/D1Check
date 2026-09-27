import math
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_arrival_plan as p
from tools import d1_energy_state_collection as state
from tools import d1_logger_v4 as logger
from tools import d1_energy_thermal as thermal
from tools import d1_energy_collection_device as device
from tools import d1_arrival_timing_calibration as calibration


class StateCollectionTest(unittest.TestCase):
    def test_apk_sources_exclude_host_tests_but_bind_android_production(self):
        identity={'benchmark-runner/src/testModelProbe/java/X.kt':'one',
                  'benchmark-runner/src/modelProbe/java/X.kt':'two'}
        self.assertEqual(calibration.apk_sources(identity),
                         {'benchmark-runner/src/modelProbe/java/X.kt':'two'})

    def test_budget_and_distinct_pair_states(self):
        state.budget_check()
        self.assertEqual(state.block_state('CG_DC', 'pair'),
                         'classification_GPU+detection_CPU')
        self.assertEqual(state.block_state('DC_DG', 'pair'),
                         'detection_CPU+detection_GPU')
        self.assertNotEqual(state.block_state('CC_DG', 'pair'),
                            state.block_state('CG_DC', 'pair'))
        self.assertEqual(state.BUDGET['total_seconds'], 230*60)
        self.assertEqual(state.BUDGET['fixed_observation_seconds'], 102*60)
        self.assertEqual(state.probe_counts('CC_DG'),{'classification':2,'detection':2})
        self.assertEqual(state.probe_counts('DC_DG'),{'classification':0,'detection':4})

    def test_partial_journal_never_implies_zero_or_completion(self):
        raw=(b'{"kind":"request_start","phase":"load","id":"x"}\n'
             b'{"kind":"request_start","phase":"load","id":"y"}')
        result=state.progress_consumption(raw, True)
        self.assertEqual(result['counts']['load']['confirmed_started_at_least'], 1)
        self.assertEqual(result['counts']['load']['confirmed_returned'], 0)
        self.assertEqual(result['counts']['load']['actual_started_upper'], state.WORK_CAP)
        self.assertEqual(result['partial_lines'], 1)

    def test_first_order_fit_development_only_and_confirmation_error(self):
        beta=1/200
        states=sorted({state.block_state(pair,name) for pair in state.PAIRS
                       for name,_,_ in state.BLOCKS['development']})
        slope={key: .001*(i+1) for i,key in enumerate(states)}
        results=[]
        for pair in state.PAIRS:
            temperature=29.5+state.PAIRS.index(pair)*.35
            blocks=[];clock=0
            for name,_,duration in state.BLOCKS['development']:
                key=state.block_state(pair,name);path=[]
                for _ in range(duration//2+1):
                    path.append(dict(mono_ns=clock,ap_c=temperature))
                    temperature+=2*(slope[key]-beta*(temperature-30))
                    clock+=2_000_000_000
                blocks.append(dict(state=key,ap_path=path,
                    power=dict(covered_energy_j=duration*(1.5+states.index(key)*.1),
                               covered_s=duration)))
            results.append(dict(condition=pair,phase='development',status='eligible_regimen_only',
                start_ap_c=29.5+state.PAIRS.index(pair)*.35,blocks=blocks,
                input_hashes={'synthetic_fixture':'not_device_data'}))
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'energy_ap_state_plan_v3').mkdir()
            (folder/'energy_ap_state_plan_v3'/'collection_plan.json').write_text('{}')
            frozen=state.freeze(results,{'source_code':{},'analysis':{'current_unit':'synthetic_fixture'}},
                                folder/'energy_ap_state_run_v3')
        self.assertEqual(frozen['ap_fit_rank'],len(states)+1)
        self.assertTrue(math.isclose(frozen['ap_cooling_rate_per_s'],beta,rel_tol=.03))
        self.assertEqual(frozen['accuracy_pass'],None)

    def test_recorded_a24_parser_and_energy_boundary(self):
        fixture=Path(__file__).parent/'fixtures/energy_state_recorded_parser.json'
        record=json.loads(fixture.read_text(encoding='utf-8'))
        parsed=logger.parse_thermalservice(record['thermal_raw'])
        self.assertEqual(parsed['AP'],record['thermal_parsed']['AP'])
        self.assertEqual(parsed['thermal_status'],record['thermal_parsed']['thermal_status'])
        samples=record['power_samples'];a=samples[0]['mono_ns'];b=samples[-1]['mono_ns']
        actual=thermal.integrate(samples,a,b,1000)
        self.assertGreater(actual['covered_energy_j'],0)
        self.assertLessEqual(actual['covered_s'],(b-a)/1e9)
        self.assertTrue(all(r['snapshot_start_ns']<=r['sensor_read_end_ns']<=r['state_snapshot_ns']<=r['mono_ns']
                            for r in samples))

    def test_shared_runner_freezes_before_confirmation_and_uses_new_namespace(self):
        class Device:
            def __init__(self,*args):self.deadline=None
            def call(self,*args,**kwargs):pass
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);entries=[]
            for i,(phase,pair) in enumerate(state.ORDER):
                manifest=root/f'{i}.json';manifest.write_text('{}')
                entries.append(dict(index=i,phase=phase,pair=pair,mode='calibration',
                                    session_id=str(i),manifest=manifest.name))
            plan=dict(state_model_calibration=True,protocol=state.PROTOCOL,
                      output_root=str(root/'run'),registry=str(root/'registry'),
                      budget=state.BUDGET,apk_preflight={'candidate':{}},
                      apk_sha256='hash',source_files={},entries=entries)
            file=root/'plan.json';file.write_text(json.dumps(plan))
            index=0
            def summarize(*args):
                nonlocal index
                if index>=3:self.assertTrue((root/'run/development_freeze.json').is_file())
                phase,pair=state.ORDER[index];index+=1
                return dict(status='eligible_regimen_only',condition=pair,phase=phase,
                            work_calls=100,eligibility_calls=4,warmup_calls=8)
            with (patch.object(state,'check'),patch.object(device,'ObservedDevice',Device),
                  patch.object(device,'installation',return_value={'status':'verified'}),
                  patch.object(device,'gates'),patch.object(device.install,'installed_hash',return_value='hash'),
                  patch.object(device.shared,'stage_inputs',return_value='remote') as stage,
                  patch.object(device,'poll'),patch.object(device,'recover',return_value={'status':'recovered'}),
                  patch.object(device.shared,'cleanup',return_value={'status':'completed'}),
                  patch.object(state,'summarize_session',side_effect=summarize),
                  patch.object(state,'freeze',return_value={'version':'frozen_development_only'}) as freeze,
                  patch.object(state,'evaluate',return_value={'accuracy_pass':None}) as evaluate):
                result=device.run(file,'NOT_ADB','fixture',p.digest(file),True)
            self.assertEqual(result['sessions'],6)
            self.assertEqual(result['explicit_inference'],6*(100+4+8))
            self.assertEqual(freeze.call_count,1)
            self.assertEqual(evaluate.call_count,3)
            self.assertTrue(all(call.args[-1]==state.PROTOCOL for call in stage.call_args_list))
            self.assertFalse(result['experiment_ready'])


if __name__ == '__main__':unittest.main()
