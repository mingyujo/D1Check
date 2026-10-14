"""Pure immutable-spec/identity tests; no device or model invocation."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parent))
import d1_a24_laptop_bind as b


def fixture():
    specs={}
    for old,new in b.KEYS.items():
        task=new[0]; size=224 if task=='C' else 320
        specs[old]=dict(identity=dict(session_id='7aa2fdf8-f6d0-4502-a73d-e77459d7f8c2'),
          target=dict(adb_serial='OLD_SERIAL',build_fingerprint='OLD_FINGERPRINT'),
          model=dict(task_id='classification' if task=='C' else 'detection',sha256=b.MODEL_DIGESTS[task],label_sha256=b.LABEL_DIGESTS[task]),
          tensor=dict(input_count=1,inputs=[dict(shape=[1,size,size,3],dtype='FLOAT32')],normalization='(RGB-127.0)/128.0' if task=='C' else '(RGB-127.5)/127.5'),
          runtime=dict(litert_version='1.4.2',cpu_threads=1,xnnpack=True,gpu_profile_id='gpu-fp32-strict-v1',gpu_configuration_sha256=b.GPU_CONFIGURATION),
          input=dict(kind='deterministic_rgb',seed=2),
          comparator=dict(atol=1e-4,rtol=1e-3,decoded_score_atol=1e-3,decoded_box_atol_px=2.0),
          execution=dict(backend=new.split('_')[1]))
    binding=json.loads((Path(__file__).parents[1]/'docs/team/a24-laptop-measurements-20261014/MATERIALS_BINDING.json').read_text(encoding='utf-8'))
    files={x['filename']:{'bytes':x['bytes'],'sha256':x['sha256'],'logical_path':x['filename']} for x in binding['files']}
    request=dict(task='C',input_file='00575b9132bb3746.png',input_sha256=files['00575b9132bb3746.png']['sha256'],tensor_sha256=binding['tensors']['classification']['sha256'])
    session=dict(session_id='14e41d08-fada-5d53-99e9-8b1b350df30b',consumed=False,registry_claim=None,requests=[request])
    return specs,binding,files,session


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.models,self.binding,self.files,self.session=fixture()

    def bind(self):
        return b.bind_session(self.session,self.models,'a'*64,self.files,self.binding,'b'*64,'2026-10-14T00:00:00Z')

    def test_exact_four_source_cells(self):
        self.assertEqual(b.source_models({'models':self.models}),self.models)
        del self.models['detection_GPU']
        with self.assertRaises(ValueError):b.source_models({'models':self.models})

    def test_runtime_mapping_or_model_change_rejected(self):
        for section,key,value in [('execution','backend','CPU'),('model','sha256','f'*64),('runtime','cpu_threads',4),('runtime','gpu_profile_id','gpu-compat-default-v1')]:
            altered=copy.deepcopy(self.models);altered['classification_GPU'][section][key]=value
            with self.assertRaises(ValueError):b.source_models({'models':altered})

    def test_new_id_target_gate_and_science_preserved(self):
        original=copy.deepcopy(self.models);m=self.bind()
        self.assertEqual(self.models,original)
        self.assertEqual(set(m['models']),{'C_CPU','C_GPU','D_CPU','D_GPU'})
        for old,new in b.KEYS.items():
            spec=m['models'][new]
            for section in b.MODEL_KEYS-{'identity','target'}:
                self.assertEqual(spec[section],original[old][section])
            self.assertEqual(spec['identity']['session_id'],self.session['session_id'])
            self.assertEqual(spec['target']['build_fingerprint'],'DEVICE_UNVERIFIED')
            self.assertIsNone(spec['target']['ram_bytes'])
            self.assertIsNone(spec['target']['api_level'])
        self.assertNotIn('OLD_SERIAL',json.dumps(m));self.assertNotIn('OLD_FINGERPRINT',json.dumps(m))
        self.assertFalse(m['execution_authorized']);self.assertFalse(m['mock'])
        self.assertFalse(m['device_gate_verified']);self.assertEqual(m['device_status'],'DEVICE_UNVERIFIED')
        self.assertNotIn('D_GPU',m['permitted_request_runtime_keys'])
        self.assertEqual(m['requests'],self.session['requests'])

    def test_no_old_uuid_or_consumed_import(self):
        self.session['session_id']=next(iter(self.models.values()))['identity']['session_id']
        with self.assertRaises(ValueError):self.bind()
        self.session['session_id']='14e41d08-fada-5d53-99e9-8b1b350df30b';self.session['consumed']=True
        with self.assertRaises(ValueError):self.bind()

    def test_bank_input_or_tensor_tampering_rejected(self):
        for key in ['input_sha256','tensor_sha256','input_file']:
            original=self.session['requests'][0][key];self.session['requests'][0][key]='incorrect'
            with self.assertRaises(ValueError):self.bind()
            self.session['requests'][0][key]=original

    def test_idle_still_binds_approved_warmup(self):
        self.session['requests']=[];m=self.bind()
        self.assertEqual(m['warmup_input']['input_file'],'00575b9132bb3746.png')
        self.assertEqual(m['warmup_input']['d_tensor_sha256'],self.binding['tensors']['detection']['sha256'])

    def test_target_cannot_invent_device_numeric_facts(self):
        target=b.offline_target('a'*64)
        self.assertIsNone(target['ram_bytes']);self.assertIsNone(target['api_level'])
        self.assertEqual(target['apk_sha256'],'a'*64)
        self.assertEqual(target['adb_serial'],'DEVICE_UNVERIFIED')

    def test_source_tolerance_is_not_relaxed(self):
        self.models['detection_CPU']['comparator']['decoded_box_atol_px']=3
        with self.assertRaises(ValueError):b.source_models({'models':self.models})

    def test_binding_cannot_replace_approved_tensor_hash(self):
        self.binding['tensors']['detection']['sha256']='f'*64
        with self.assertRaises(ValueError):self.bind()

    def test_metadata_digest_is_canonical(self):
        self.assertEqual(b.canonical_sha({'x':1,'z':2}),b.canonical_sha({'z':2,'x':1}))


if __name__=='__main__':unittest.main()
