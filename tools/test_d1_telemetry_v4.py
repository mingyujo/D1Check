import copy
from pathlib import Path
import unittest
import uuid

from tools import d1_telemetry_v4 as v


def uid(n):return str(uuid.UUID(int=n))


def fixture(configuration='resident_cpu_serial',base=1):
    sid=uid(base);models={};slots=[];warm=[];requests=[]
    tasks=['classification'] if configuration=='lifecycle' else ['classification','detection']
    for i,task in enumerate(tasks):
        backend='GPU' if configuration=='resident_corun' and i==1 else 'CPU'
        key=task+'_'+backend
        models[key]=dict(identity=dict(session_id=sid),target=dict(apk_sha256='a'*64),execution=dict(backend=backend),
                         runtime=dict(cpu_threads=1,xnnpack=True),model=dict(task_id=task,sha256=str(i)*64))
        slots.append(dict(model_key=key,runtime_id=uid(base+100+i),worker_id=0 if configuration=='resident_cpu_serial' else i))
        for j in range(2):warm.append(dict(model_key=key,request_id=uid(base+1000+i*10+j),sample_id='im',priority='normal',offset_ms=0))
        requests.append(dict(model_key=key,request_id=uid(base+2000+i),sample_id='im',priority='urgent' if i==0 else 'normal',offset_ms=0))
    m=dict(protocol=v.PROTOCOL,schema_version=1,purpose='telemetry_smoke',maximum_duration_ms=120000,session_id=sid,
           apk_sha256='a'*64,device_fingerprint='device',memory_contract=v.MEMORY,thermal_gate=0,deadline_ns=None,
           configuration=configuration,models=models,runtimes=slots,warmup_per_runtime=2,warmup_requests=warm,
           requests=requests,images=[dict(sample_id='im',sha256='f'*64)],seed=20260921,
           paired=dict(pair_id=uid(999999),order='AB',arm='A' if configuration=='resident_cpu_serial' else 'B'))
    events=[]
    def emit(name,slot=None,q=None,data=None,state='running'):
        spec=models[slot['model_key']] if slot else None;backend=spec['execution']['backend'] if spec else 'not_applicable'
        now=(len(events)+1)*100
        if name in ('memory_sample','memory_admission'):
            default=dict(snapshot_start_ns=now-2,snapshot_end_ns=now-1,avail_bytes=10000,threshold_bytes=100,
                         pss_bytes=500,observed_peak_pss_bytes=500,low_memory=False,memory_class_mib=256,large_memory_class_mib=512,thermal_status=0)
            if name=='memory_admission':default.update(contract=v.MEMORY,reserve_bytes=500,reason='admit',decision='admit')
            default.update(data or {});data=default
        events.append(dict(protocol=v.PROTOCOL,schema_version=1,session_id=sid,request_id=q['request_id'] if q else None,
            runtime_id=slot['runtime_id'] if slot else None,worker_id=slot['worker_id'] if slot else None,
            task=spec['model']['task_id'] if spec else 'not_applicable',requested_backend=backend,
            actual_backend='GPU_unverified' if backend=='GPU' else backend,clock_domain='elapsedRealtimeNanos',mono_ns=now,
            sequence=len(events),event=name,terminal_state=state,data=data or {}))
    emit('session_start');emit('memory_sample',data=dict(resident_count=0))
    for i,slot in enumerate(slots):
        emit('memory_admission',slot,data=dict(stage='before_runtime_creation'))
        for name in v.RUNTIME_EVENTS[:5]:emit(name,slot)
        if models[slot['model_key']]['execution']['backend']=='GPU':
            for name in ['delegate_creation_start','delegate_creation_end','delegate_attachment_start','delegate_attachment_end']:emit(name,slot)
        else:emit('delegate_creation_not_applicable',slot)
        for name in v.RUNTIME_EVENTS[5:10]:emit(name,slot)
        emit('memory_sample',data=dict(resident_count=i+1))
    def request(q):
        slot=next(s for s in slots if s['model_key']==q['model_key'])
        for name in v.REQUEST_EVENTS:
            if name=='active_service_end' and q['priority']=='normal':emit('persist_complete',slot,q)
            emit(name,slot,q,data=dict(stage='before_invocation') if name=='memory_admission' else dict(inference_ns=100) if name=='active_service_end' else None,
                 state='succeeded' if name=='request_terminal' else 'running')
            if name=='active_service_end':events[-1]['mono_ns']=events[-2]['mono_ns']
    for q in warm:request(q)
    emit('memory_admission',data=dict(stage='before_workload'));emit('workload_start')
    for q in requests:request(q)
    emit('workload_end')
    for slot in slots:
        for name in v.RUNTIME_EVENTS[10:-1]:emit(name,slot)
        if models[slot['model_key']]['execution']['backend']=='GPU':
            emit('delegate_close_start',slot);emit('delegate_close_end',slot)
        else:emit('delegate_close_not_applicable',slot)
        emit('runtime_close_end',slot)
    emit('session_end',state='succeeded')
    return m,events


class TelemetryV4Tests(unittest.TestCase):
    def test_valid_cpu_lifecycle(self):self.assertEqual(v.validate_events(*fixture('lifecycle'))['status'],'validated_events')
    def test_resident_cpu_serial(self):self.assertEqual(len(v.validate_events(*fixture())['samples']),6)
    def test_resident_corun(self):self.assertEqual(len(v.validate_events(*fixture('resident_corun'))['samples']),6)

    def test_every_required_event_missing_rejected(self):
        for name in set(v.REQUEST_EVENTS+v.RUNTIME_EVENTS):
            m,e=fixture();index=next(i for i,r in enumerate(e) if r['event']==name);del e[index]
            for i,r in enumerate(e):r['sequence']=i
            with self.subTest(name=name),self.assertRaises(ValueError):v.validate_events(m,e)

    def test_duplicate_rejected(self):
        m,e=fixture();e.insert(5,copy.deepcopy(e[4]))
        with self.assertRaises(ValueError):v.validate_events(m,e)

    def test_duplicate_resequenced_rejected(self):
        m,e=fixture();i=next(i for i,r in enumerate(e) if r['event']=='model_map_start');e.insert(i,copy.deepcopy(e[i]))
        for i,r in enumerate(e):r['sequence']=i
        with self.assertRaises(ValueError):v.validate_events(m,e)

    def test_reverse_event_rejected(self):
        m,e=fixture();e[4],e[5]=e[5],e[4]
        with self.assertRaises(ValueError):v.validate_events(m,e)

    def test_clock_regression(self):
        m,e=fixture();e[4]['mono_ns']=1
        with self.assertRaises(ValueError):v.validate_events(m,e)

    def test_foreign_protocol_clock_and_actual_missing(self):
        import jsonschema
        for change in [dict(protocol='task-profile-v3'),dict(clock_domain='wall_clock'),dict(mono_ns=-1)]:
            m,e=fixture();e[4].update(change)
            with self.assertRaises((ValueError,jsonschema.ValidationError)):v.validate_events(m,e)
        m,e=fixture();del e[4]['actual_backend']
        with self.assertRaises(jsonschema.ValidationError):v.validate_events(m,e)

    def test_identity_mismatches(self):
        for key,value in [('session_id',uid(999)),('runtime_id',uid(999)),('worker_id',1),('request_id',uid(999)),('actual_backend','GPU_unverified')]:
            m,e=fixture();i=next(i for i,r in enumerate(e) if r['event']=='invocation_start');e[i][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):v.validate_events(m,e)

    def test_no_events_after_terminal(self):
        m,e=fixture();i=next(i for i,r in enumerate(e) if r['event']=='request_terminal');x=copy.deepcopy(e[i]);x.update(event='invocation_start',terminal_state='running');e.insert(i+1,x)
        for i,r in enumerate(e):r['sequence']=i
        with self.assertRaises(ValueError):v.validate_events(m,e)

    def test_inference_boundary_exact_legacy_code(self):
        p=Path('benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner')
        def block(name):
            s=(p/name).read_text();return s[s.index('        val startedNs = SystemClock.elapsedRealtimeNanos()'):s.index('        val finishedNs = SystemClock.elapsedRealtimeNanos()')+len('        val finishedNs = SystemClock.elapsedRealtimeNanos()')]
        self.assertEqual(block('ProbeRawAdapter.kt'),block('V4RawAdapter.kt'))
        self.assertEqual(block('ProbeRawAdapter.kt').count('\n'),2)

    def test_forged_inference_duration(self):
        m,e=fixture();next(x for x in e if x['event']=='active_service_end')['data']['inference_ns']=999
        with self.assertRaises(ValueError):v.validate_events(m,e)

    def test_close_before_workload_end(self):
        m,e=fixture();next(x for x in e if x['event']=='runtime_close_start')['mono_ns']=1
        with self.assertRaises(ValueError):v.validate_events(m,e)

    def test_missing_worker_release(self):
        m,e=fixture();e=[x for x in e if x['event']!='worker_release_end']
        with self.assertRaises(ValueError):v.validate_events(m,e)

    def test_two_residency_samples_required(self):
        m,e=fixture()
        for x in e:
            if x['event']=='memory_sample':x['data']['resident_count']=0
        with self.assertRaises(ValueError):v.validate_events(m,e)

    def test_memory_pass_and_pressure_reject(self):
        _,e=fixture();d=copy.deepcopy(next(x['data'] for x in e if x['event']=='memory_admission'))
        self.assertEqual(v.memory_decision(d),'admit');d['avail_bytes']=600
        self.assertEqual(v.memory_decision(d),'insufficient_dynamic_reserve')

    def test_low_memory_fail_closed(self):
        m,e=fixture();next(x for x in e if x['event']=='memory_admission')['data']['low_memory']=True
        with self.assertRaises(ValueError):v.validate_events(m,e)

    def test_safe_rejection_artifact(self):
        m,e=fixture();e=e[:3];e[2]['data'].update(low_memory=True,decision='reject',reason='android_low_memory')
        end=copy.deepcopy(e[0]);end.update(event='session_end',terminal_state='failed',sequence=3,mono_ns=400);e.append(end)
        self.assertEqual(v.validate_events(m,e,False)['status'],'failed_preserved')

    def test_same_task_warmup_rejected(self):
        m,_=fixture();m['warmup_requests'][2]['model_key']=m['warmup_requests'][0]['model_key']
        with self.assertRaises(ValueError):v.manifest(m)

    def test_paired_ab_and_ba(self):
        a,_=fixture(base=1);b,_=fixture('resident_corun',base=10001)
        self.assertEqual(v.paired(a,b)['status'],'matched_plan')
        a['paired']['order']=b['paired']['order']='BA'
        self.assertEqual(v.paired(a,b,[dict(session_id=b['session_id'],status='validated_events',session_end_ns=2,thermal_drift=dict(start=0,end=0)),
                                      dict(session_id=a['session_id'],status='validated_events',session_start_ns=3,thermal_drift=dict(start=0,end=0))])['status'],'complete_pair')

    def test_partial_pair_rejected(self):
        a,_=fixture();b,_=fixture('resident_corun',base=10001)
        with self.assertRaises(ValueError):v.paired(a,b,[dict(session_id=a['session_id'],status='validated_events')])

    def test_unmatched_workload(self):
        a,_=fixture();b,_=fixture('resident_corun',base=10001);b['requests'][0]['offset_ms']=1;b['requests'][1]['offset_ms']=1
        with self.assertRaises(ValueError):v.paired(a,b)

    def test_consumed_holdout(self):
        m,_=fixture()
        with self.assertRaises(ValueError):v.manifest(m,[m['session_id']])

    def test_joint_session_provenance(self):
        m,e=fixture();r=v.validate_events(m,e);r['artifact_sha256']='a'*64
        for s in r['samples']:s['provenance_sha256']='a'*64
        self.assertEqual(v.joint_sample(r,42),v.joint_sample(r,42))
        self.assertEqual(v.resample_session([r],42,0),v.resample_session([r],42,0))
        with self.assertRaises(ValueError):v.resample_session([r,r],42,0)
        r['samples'][0]['session_id']=uid(9090)
        with self.assertRaises(ValueError):v.joint_sample(r,42)

    def test_noop_dry_run(self):
        m,_=fixture();self.assertEqual(v.no_op(m),v.no_op(m));self.assertEqual(v.no_op(m)['device_commands'],[])

    def test_urgent_persistence_not_charged_to_completion(self):
        m,e=fixture();r=v.validate_events(m,e)
        s=next(s for s in r['samples'] if s['request_id']==m['requests'][0]['request_id'])
        es=[x for x in e if x['request_id']==s['request_id']]
        self.assertEqual(s['active_service_ns'],v.exactly(es,'output_ready')['mono_ns']-v.exactly(es,'active_service_start')['mono_ns'])
        self.assertGreater(s['worker_occupancy_ns'],s['active_service_ns'])

    def test_mismatched_active_end_rejected(self):
        m,e=fixture();next(x for x in e if x['event']=='active_service_end')['mono_ns']+=1
        with self.assertRaises(ValueError):v.validate_events(m,e)

    def test_whole_trace_replay_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m,e=fixture()
            (root/'manifest.json').write_bytes(v.canonical(m));(root/'events.json').write_bytes(v.canonical(e))
            (root/'summary.json').write_bytes(v.canonical(dict(protocol=v.PROTOCOL,session_id=m['session_id'],status='succeeded')))
            files=[dict(name=p.name,sha256=v.digest(p),bytes=p.stat().st_size) for p in root.iterdir()]
            (root/'provenance.json').write_bytes(v.canonical(dict(protocol=v.PROTOCOL,session_id=m['session_id'],files=files)))
            fingerprint=v.sha([{k:r[k] for k in ('event','mono_ns','task','requested_backend','worker_id')} for r in e])
            with self.assertRaisesRegex(ValueError,'replayed event trace'):
                v.validate(root,v.digest(root/'manifest.json'),seen_traces=[fingerprint])


if __name__=='__main__':unittest.main()
