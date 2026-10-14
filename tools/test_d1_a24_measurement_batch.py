import json
import tempfile
import unittest
from pathlib import Path
from d1_a24_measurement_batch import assemble, finish_only_closed_owned_process, PACKAGE, TARGET_KEYS, ValidationError

class BatchTests(unittest.TestCase):
    def test_assembly_preserves_request_and_model_contract_and_original(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp);prepared=r/'prepared';prepared.mkdir();inputs=r/'inputs';inputs.mkdir()
            def put(name,data):p=r/name;p.write_text(json.dumps(data),encoding='utf-8');return str(p)
            sid='12086e3c-817f-520f-88b0-53340522ad79'
            source={'session_id':sid,'protocol':'a24-laptop-measurement-v1','plan_id':'MOCK_PLAN',
              'plan_sha256':'1'*64,'stage':'I','requests':[{'task':'C','scheduled_arrival_ns':35}],
              'models':{k:{'runtime':{'cpu_threads':1},'target':dict.fromkeys(TARGET_KEYS,'unverified')} for k in ['C_CPU','C_GPU','D_CPU','D_GPU']}}
            p=prepared/(sid+'.json');p.write_text(json.dumps(source),encoding='utf-8');before=p.read_bytes()
            (inputs/'input.txt').write_bytes(b'MOCK_INPUT')
            source_manifest=put('source.json',{'files':[]});gate=put('gate.json',{'frozen':False})
            identity=put('apk.json',{'apk_sha256':'2'*64,'package':PACKAGE})
            registration={**dict.fromkeys(TARGET_KEYS,'MOCK'),'device_id':'mock_a24','build_fingerprint':'MOCK_FP','model':'SM-A245N','adb_serial':'MOCK','api_level':36,'ram_bytes':1000,'hardware_serial':'MOCK_PHYSICAL'}
            target=put('target.json',registration)
            lock=r/'lock';lock.write_bytes(b'STDLIB');adb=r/'adb';adb.write_bytes(b'MOCK_NEVER_EXECUTED')
            repo=r/'repo';(repo/'tools').mkdir(parents=True);(repo/'tools/d1_a24_laptop_control.py').write_bytes(b'MOCK_CONTROLLER')
            job={'prepared_manifests':str(prepared),'apk_identity':identity,'device_registration':target,
              'source_base_commit':'MOCK','source_manifest':source_manifest,'input_root':str(inputs),'input_filenames':['input.txt'],
              'gate':gate,'apk':'MOCK_APK','adb':str(adb),'repo':str(repo),'host_dependency_lock':str(lock)}
            m,c,a,g=assemble(job,source,r)
            self.assertEqual(m['requests'],source['requests']);self.assertEqual(p.read_bytes(),before)
            self.assertEqual(m['models']['C_CPU']['runtime'],source['models']['C_CPU']['runtime'])
            self.assertEqual(m['minimum_battery_percent'],10);self.assertFalse(g['frozen'])
            self.assertEqual(a['scope'],'one_new_session');self.assertFalse((r/'registry').exists())
            self.assertEqual(set(m['models']['C_CPU']['target']),TARGET_KEYS)
            self.assertNotIn('hardware_serial',m['models']['C_CPU']['target'])
            registration['device_id']='UPPERCASE_PHYSICAL';Path(target).write_text(json.dumps(registration),encoding='utf-8')
            other={**source,'session_id':'422172fe-f64c-57a4-a883-e9e4fd4efea0'}
            (prepared/(other['session_id']+'.json')).write_text(json.dumps(other),encoding='utf-8')
            with self.assertRaisesRegex(ValidationError,'logical device_id'):
                assemble(job,other,r)
            self.assertFalse((r/'bindings'/other['session_id']).exists())
    def test_only_proved_closed_owned_process_can_be_stopped(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp);calls=[]
            class Fake:
                def command(self,*args,**kw):calls.append(args);return b'123' if args[:2]==('shell','pidof') and args[2]==PACKAGE+':a24_preparation' else b''
            self.assertFalse(finish_only_closed_owned_process(Fake(),r,'SID'));self.assertEqual(calls,[])
            for name,data in {'identity.json':{'session_id':'SID','process_id':123},'journal_closed.json':{'status':'SYNCED_AND_CLOSED','session_id':'SID','process_id':123},'cleanup.json':{'status':'DRAINED','actual_return_confirmed':True}}.items():
                (r/name).write_text(json.dumps(data),encoding='utf-8')
            self.assertTrue(finish_only_closed_owned_process(Fake(),r,'SID'))
            self.assertIn(('shell','am','force-stop',PACKAGE),calls)
            calls.clear();self.assertFalse(finish_only_closed_owned_process(Fake(),r,'OTHER'));self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()
