import math
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_arrival_plan as p
from tools import d1_energy_state_collection as state
from tools import d1_logger_v4 as logger
from tools import d1_energy_thermal as thermal
from tools import d1_energy_collection_device as device
from tools import d1_arrival_timing_calibration as calibration
from tools import d1_adb_observed_client as observed


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
        self.assertEqual(state.BUDGET['total_seconds'], 225*60)
        self.assertEqual((state.BUDGET['apk_transfers'],state.BUDGET['installs'],
                          state.BUDGET['installed_host_pulls']),(0,0,1))
        self.assertEqual(state.BUDGET['fixed_observation_seconds'], 102*60)
        self.assertEqual((state.BUDGET['pre_cleanup_command_slots'],
                          state.BUDGET['adb_command_slots']),(62400,62500))
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
            folder=Path(temp);(folder/'energy_ap_state_plan_v4').mkdir()
            plan_file=folder/'energy_ap_state_plan_v4'/'collection_plan.json'
            plan_file.write_text('{}')
            frozen=state.freeze(results,{'source_code':{},'analysis':{'current_unit':'synthetic_fixture'},
                                         'plan_file':str(plan_file)},folder/'energy_ap_state_run_v4')
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
            def __init__(self,*args,**kwargs):self.deadline=None;self.sequence=0;self.command_limit=None
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
                  patch.object(device,'installed_preflight',return_value={'status':'verified'}),
                  patch.object(device,'gates'),patch.object(device.install,'installed_hash',return_value='hash'),
                  patch.object(device.shared,'stage_inputs',return_value='remote') as stage,
                  patch.object(device,'poll') as poll,patch.object(device,'recover',return_value={'status':'recovered'}),
                  patch.object(device.shared,'cleanup',return_value={'status':'completed'}),
                  patch.object(state,'summarize_session',side_effect=summarize),
                  patch.object(state,'freeze',return_value={'version':'frozen_development_only'}) as freeze,
                  patch.object(state,'evaluate',return_value={'accuracy_pass':None}) as evaluate):
                result=device.run(file,'NOT_ADB',None,p.digest(file),True)
            self.assertEqual(result['sessions'],6)
            self.assertEqual(result['explicit_inference'],6*(100+4+8))
            self.assertEqual(freeze.call_count,1)
            self.assertEqual(evaluate.call_count,3)
            self.assertEqual(poll.call_count,6)
            self.assertTrue(all('diagnostic_stop_after_preparation' not in call.kwargs
                                for call in poll.call_args_list))
            self.assertTrue(all(call.args[-1]==state.PROTOCOL for call in stage.call_args_list))
            self.assertFalse(result['experiment_ready'])
            self.assertTrue((root/'run/FINAL_RECEIPT.json').is_file())
            self.assertTrue((root/'registry/completed.json').is_file())
            checkpoints=[json.loads(p.read_text())['stage'] for p in sorted((root/'run/host_checkpoints').glob('*.json'))]
            self.assertEqual(checkpoints[-1],'completed')

    def test_current_transport_selection_and_apk_deploy_block(self):
        with tempfile.TemporaryDirectory() as temp:
            serial='adb-example._adb-tls-connect._tcp'; commands=[]
            def client(command,folder,timeout,display,root_only):
                commands.append(command)
                folder.mkdir(parents=True)
                value=({('devices','-l'):('List of devices attached\n'+serial+' device\n').encode(),
                        ('shell','getprop','ro.product.model'):b'SM-A245N\n',
                        ('shell','getprop','ro.build.fingerprint'):b'fingerprint\n'})[
                            tuple(command[1:] if command[1]!='-s' else command[3:])]
                (folder/'stdout.bin').write_bytes(value);(folder/'stderr.bin').write_bytes(b'')
                return dict(status='returned',returncode=0)
            with patch.object(observed,'server_probe',return_value={'protocol_version':'0029'}), \
                 patch.object(observed,'host_snapshot',return_value={'status':'captured'}), \
                 patch.object(observed.rp,'run',side_effect=client):
                d=observed.ObservedDevice('adb',None,Path(temp),allow_select=True,
                                          forbid_apk_deploy=True)
                d.deadline=time.monotonic()+30
                identity=d.identify('fingerprint')
                with self.assertRaisesRegex(ValueError,'forbidden'):
                    d.call('shell','pm','install','-r','/data/local/tmp/candidate.apk')
                with self.assertRaisesRegex(ValueError,'forbidden'):
                    d.call('push','candidate.apk','/data/local/tmp/candidate.apk')
            self.assertEqual(identity['serial'],serial)
            self.assertEqual(commands[0],['adb','devices','-l'])
            self.assertTrue(all(command[1:3]==['-s',serial] for command in commands[1:]))
            self.assertEqual(len(commands),3)

    def test_installed_mismatch_stops_without_deploy(self):
        class Device:
            deadline=None
            def call(self,*args,**kwargs):raise AssertionError('APK deploy/device call')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);root.mkdir(exist_ok=True)
            plan={'budget':state.BUDGET}
            with patch.object(device.apk,'preflight',return_value=dict(installed='old',candidate='new')), \
                 patch.object(device,'gates',side_effect=AssertionError('gates after mismatch')):
                with self.assertRaisesRegex(ValueError,'no deploy fallback'):
                    device.installed_preflight(Device(),plan,root/'plan.json',root, time.monotonic()+400)
            receipt=json.loads((root/'installed_preflight_receipt.json').read_text())
            self.assertEqual((receipt['apk_transfer_attempts'],receipt['install_attempts']),(0,0))

    def test_frozen_check_is_pc_only_and_consumed_plan_stays_consumed(self):
        path=os.environ.get('D1_ENERGY_STATE_INSTALLED_PLAN')
        if not path:self.skipTest('frozen installed-only plan not supplied')
        with patch.object(device,'ObservedDevice',side_effect=AssertionError('device reached')):
            plan=json.loads(Path(path).read_text(encoding='utf-8'))
            if Path(plan['output_root']).exists():
                with self.assertRaisesRegex(ValueError,'consumed'):
                    state.check(path)
            else:self.assertEqual(state.check(path)['device_commands'],0)


if __name__ == '__main__':unittest.main()
