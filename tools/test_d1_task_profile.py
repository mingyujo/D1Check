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
        self.m = dict(protocol='task-profile-v1', session_id=self.session,
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
        save('environment.json', [dict(mono_ns=10, total_pss_kb=123, thermal_status=0)])
        save('summary.json', dict(protocol='task-profile-v1', session_id=self.session, request_count=1, succeeded=1, failed=0))
        save('provenance.json', dict(protocol='task-profile-v1', session_id=self.session,
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


if __name__ == '__main__':
    unittest.main()
