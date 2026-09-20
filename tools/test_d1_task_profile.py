import json
from pathlib import Path
import tempfile
import unittest
import uuid
from tools import d1_task_profile as p
from tools.test_d1_model_probe import manifest


class ProfileEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        spec = manifest()
        self.session = spec['identity']['session_id']
        self.request = str(uuid.uuid4())
        self.m = dict(protocol='task-profile-v2', session_id=self.session,
                      apk_sha256=spec['target']['apk_sha256'], device_fingerprint=spec['target']['build_fingerprint'],
                      maximum_duration_ms=120000, purpose='solo', allowed_concurrency=1,
                      models={'classification_CPU': spec}, images=[dict(sample_id='sample', sha256='b'*64)],
                      requests=[dict(request_id=self.request, model_key='classification_CPU', sample_id='sample',
                                     priority='normal', role='calibration', worker=0, offset_ms=0)])
        self.result = dict(image_sha256='b'*64, model_sha256=spec['model']['sha256'], input_tensor_sha256='c'*64,
                           requested_backend='CPU', actual_backend='CPU', results=[dict(label='cat', score=.9)])
        self.event = dict(request_id=self.request, session_id=self.session, sample_id='sample', priority='normal',
                          role='calibration', worker=0, requested_backend='CPU', actual_backend='CPU',
                          task_id='classification', model_id=spec['model']['model_id'], scheduled_arrival_ns=10,
                          enqueue_ns=11, execution_start_ns=12, output_ready_ns=20, persist_complete_ns=22,
                          completion_ns=22, terminal_ns=23, service_ns=10, inference_ns=5, prepare_ns=1,
                          input_tensor_sha256='c'*64, deadline_ns=None, deadline_outcome='not_set',
                          terminal_status='succeeded', result_file=self.request+'.result.json', cold=True)

    def write(self):
        def save(name, obj):
            (self.root/name).write_text(json.dumps(obj), encoding='utf8')
        save('manifest.json', self.m)
        save(self.event['result_file'], self.result)
        self.event['result_sha256'] = p.digest(self.root/self.event['result_file'])
        save('events.jsonl', self.event)
        save(self.request+'.event.json', self.event)
        save('environment.json', [dict(mono_ns=10, total_pss_kb=123, thermal_status=0)])
        save('summary.json', dict(protocol=self.m['protocol'], session_id=self.session, request_count=1, succeeded=1, failed=0))
        save('provenance.json', dict(protocol=self.m['protocol'], session_id=self.session,
             apk_sha256=self.m['apk_sha256'], manifest_sha256=p.digest(self.root/'manifest.json'),
             files=[dict(name=f.name, bytes=f.stat().st_size, sha256=p.digest(f)) for f in self.root.iterdir() if f.name != 'provenance.json']))

    def test_normal_completion_and_all_arrival_denominator(self):
        self.write()
        self.assertEqual(p.validate(self.root)['service_success_rate'], 1)

    def test_urgent_output_boundary(self):
        self.m['requests'][0]['priority'] = self.event['priority'] = 'urgent'
        self.event.update(completion_ns=20, service_ns=8)
        self.write()
        self.assertEqual(p.validate(self.root)['events'][0]['completion_ns'], 20)

    def test_semantic_tampering_with_rehashed_artifacts_is_rejected(self):
        for key, bad in [('completion_ns', 20), ('enqueue_ns', 30), ('actual_backend', 'GPU'),
                         ('deadline_ns', 100), ('inference_ns', 11), ('input_tensor_sha256', 'd'*64)]:
            with self.subTest(key=key):
                old = self.event[key]
                self.event[key] = bad
                self.write()
                with self.assertRaises(ValueError):
                    p.validate(self.root)
                self.event[key] = old

    def test_hash_and_unlisted_artifact_rejected(self):
        self.write()
        (self.root/'extra').write_text('unlisted')
        with self.assertRaises(ValueError):
            p.validate(self.root)
        (self.root/'extra').unlink()
        (self.root/'events.jsonl').write_text('{}')
        with self.assertRaises(ValueError):
            p.validate(self.root)

    def test_duplicate_arrival_rejected(self):
        self.m['requests'] *= 2
        self.write()
        with self.assertRaises(ValueError):
            p.validate(self.root)

    def test_nonfinite_decoded_value_rejected(self):
        self.result['results'][0]['score'] = float('nan')
        self.write()
        with self.assertRaises(ValueError):
            p.validate(self.root)

    def test_rehashed_journal_divergence_rejected(self):
        self.write()
        path = self.root/(self.request+'.event.json')
        row = p.read(path);row['terminal_ns'] += 1
        path.write_text(json.dumps(row))
        provenance = p.read(self.root/'provenance.json')
        for entry in provenance['files']:
            if entry['name'] == path.name:
                entry.update(bytes=path.stat().st_size, sha256=p.digest(path))
        (self.root/'provenance.json').write_text(json.dumps(provenance))
        with self.assertRaises(ValueError):
            p.validate(self.root)

    def v3(self):
        self.m['protocol'] = 'task-profile-v3'
        self.m['images'][0].update(width=2, height=3)
        self.result.update(adapter_contract='explicit-image-task-v2', canonical_input_contract='canonical-srgb-png-v2',
                           task_id=self.event['task_id'], model_id=self.event['model_id'],
                           inference_ns=self.event['inference_ns'], image_size=[2, 3], raw_output_sha256=['e'*64])

    def test_v3_hash_and_result_contract(self):
        self.v3()
        self.write()
        self.assertEqual(p.validate(self.root)['succeeded'], 1)

    def test_v3_rehashed_raw_hash_tampering_rejected(self):
        self.v3()
        for bad in (None, [], ['e'*63], ['e'*64, 'f'*64], [42]):
            self.result['raw_output_sha256'] = bad
            self.write()
            with self.assertRaisesRegex(ValueError, 'raw output hash'):
                p.validate(self.root)

    def test_v3_rehashed_result_identity_timing_geometry_rejected(self):
        self.v3()
        for key, bad in [('task_id', 'detection'), ('model_id', 'wrong'), ('inference_ns', 4), ('image_size', [3, 2])]:
            with self.subTest(key=key):
                previous = self.result[key]
                self.result[key] = bad
                self.write()
                with self.assertRaisesRegex(ValueError, 'result task/timing/geometry'):
                    p.validate(self.root)
                self.result[key] = previous

    def test_v3_first_runtime_cannot_be_marked_warm(self):
        self.v3()
        self.event['cold'] = False
        self.write()
        with self.assertRaisesRegex(ValueError, 'cold runtime transition'):
            p.validate(self.root)


if __name__ == '__main__':
    unittest.main()
