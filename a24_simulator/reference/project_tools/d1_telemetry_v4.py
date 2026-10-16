"""Fail-closed telemetry v4 validation and resident-pair input contract; no ADB execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import uuid

from tools.d1_task_profile import read, digest
from tools.d1_sim_prepare import canonical

PROTOCOL='task-profile-v4'
MEMORY='android-low-memory-resident-v1'
SCHEMA=Path(__file__).with_name('schemas')/'task-profile-v4-event.schema.json'
REQUEST_EVENTS=['request_enqueue','worker_acquisition_start','worker_dispatch','queue_wait_end','memory_admission',
                'active_service_start','preprocess_start','preprocess_end','invocation_start','invocation_end',
                'output_readback_start','output_readback_end','decode_postprocess_start','decode_postprocess_end',
                'output_ready','active_service_end','worker_release_start','worker_release_end','request_terminal']
RUNTIME_EVENTS=['runtime_creation_requested','model_file_open_start','model_file_open_end','model_map_start','model_map_end',
                'interpreter_construction_start','interpreter_construction_end','tensor_allocation_start','tensor_allocation_end',
                'runtime_ready','runtime_close_start','interpreter_close_start','interpreter_close_end','runtime_close_end']
EVENTS=set(REQUEST_EVENTS+RUNTIME_EVENTS+['session_start','session_end','workload_start','workload_end','memory_sample',
    'memory_sample_failed','request_error','persist_complete','delegate_creation_start','delegate_creation_end',
    'delegate_attachment_start','delegate_attachment_end','delegate_close_start','delegate_close_end',
    'delegate_creation_not_applicable','delegate_close_not_applicable','interpreter_close_failed','delegate_close_failed'])


def sha(x):return hashlib.sha256(canonical(x)).hexdigest()


def identity(s):
    if str(uuid.UUID(s))!=s:raise ValueError('invalid UUID')
    return s


def integer(v,positive=False):
    if type(v) is not int or v < (1 if positive else 0):raise ValueError('invalid nonnegative integer')
    return v


def memory_decision(d):
    for k in ('avail_bytes','threshold_bytes','pss_bytes','observed_peak_pss_bytes','thermal_status','memory_class_mib','large_memory_class_mib'):
        integer(d[k])
    if type(d['low_memory']) is not bool:raise ValueError('invalid lowMemory')
    if d['threshold_bytes']<=0 or d['observed_peak_pss_bytes']<=0:return 'missing_memory_evidence'
    if d['thermal_status']!=0:return 'thermal_outside_zero'
    if d['low_memory']:return 'android_low_memory'
    reserve=max(d['threshold_bytes'],d['observed_peak_pss_bytes'])
    if d['avail_bytes']<=d['threshold_bytes'] or d['avail_bytes']-d['threshold_bytes']<=reserve:return 'insufficient_dynamic_reserve'
    return 'admit'


def manifest(m,consumed=()):
    if (m['protocol'],m['schema_version'],m['maximum_duration_ms'])!=(PROTOCOL,1,120000) or m['purpose'] not in ('telemetry_smoke','instrumentation_calibration'):
        raise ValueError('protocol/scope/bound mismatch')
    sid=identity(m['session_id'])
    if sid in consumed:raise ValueError('consumed/replayed session')
    if m['memory_contract']!=MEMORY or m['thermal_gate']!=0 or m['deadline_ns'] is not None:
        raise ValueError('memory/thermal/deadline contract')
    if not re.fullmatch('[a-f0-9]{64}',m['apk_sha256']):raise ValueError('APK binding')
    slots=m['runtimes'];configuration=m['configuration']
    if configuration not in ('lifecycle','resident_cpu_serial','resident_corun'):raise ValueError('configuration')
    if len(slots)!=(1 if configuration=='lifecycle' else 2):raise ValueError('runtime residency count')
    runtime_ids=[identity(s['runtime_id']) for s in slots];keys=[s['model_key'] for s in slots]
    if len(set(runtime_ids))!=len(slots) or len(set(keys))!=len(slots) or set(keys)!=set(m['models']):raise ValueError('runtime replay/binding')
    for i,s in enumerate(slots):
        if s['worker_id']!=(0 if configuration=='resident_cpu_serial' else i):raise ValueError('worker lane mismatch')
        model=m['models'][s['model_key']]
        if model['identity']['session_id']!=sid or model['target']['apk_sha256']!=m['apk_sha256']:
            raise ValueError('model session/APK identity')
        if model['execution']['backend'] not in ('CPU','GPU'):raise ValueError('backend unsupported')
        if model['runtime']['cpu_threads']!=1 or not model['runtime']['xnnpack']:raise ValueError('runtime contract')
    backends=[m['models'][k]['execution']['backend'] for k in keys]
    if configuration=='resident_cpu_serial' and backends!=['CPU','CPU']:raise ValueError('not CPU serial')
    if configuration=='resident_corun' and set(backends)!={'CPU','GPU'}:raise ValueError('not cross-backend')
    if len(slots)==2 and {m['models'][k]['model']['task_id'] for k in keys}!={'classification','detection'}:raise ValueError('task balance')
    requests=m['warmup_requests']+m['requests']; ids=[identity(q['request_id']) for q in requests]
    if len(ids)!=len(set(ids)) or set(ids)&set(consumed):raise ValueError('request replay')
    count=integer(m['warmup_per_runtime'])
    if not 1<=len(m['requests'])<=48 or not 2<=count<=20 or len(requests)>48:raise ValueError('bounded request contract')
    if m['purpose']=='telemetry_smoke' and (len(m['requests'])>8 or count!=2):raise ValueError('bounded smoke only')
    if len(m['warmup_requests'])!=count*len(slots) or any(sum(q['model_key']==k for q in m['warmup_requests'])!=count for k in keys):
        raise ValueError('warmup residency imbalance')
    images={i['sample_id']:i for i in m['images']}
    for q in requests:
        if q['model_key'] not in keys or q['sample_id'] not in images or q['priority'] not in ('urgent','normal'):
            raise ValueError('request contract')
        if not 0<=integer(q['offset_ms'])<=60000:raise ValueError('arrival bound')
    if [q['offset_ms'] for q in m['requests']]!=sorted(q['offset_ms'] for q in m['requests']):raise ValueError('arrival order')
    if m['paired']['order'] not in ('AB','BA') or m['paired']['arm'] not in ('A','B','standalone'):
        raise ValueError('paired order')
    identity(m['paired']['pair_id']);integer(m['seed'])
    return True


def exactly(events,name):
    found=[e for e in events if e['event']==name]
    if len(found)!=1:raise ValueError('missing/duplicate event: '+name)
    return found[0]


def ordered(events,names):
    sequence=[exactly(events,n)['sequence'] for n in names]
    if sequence!=sorted(sequence):raise ValueError('event boundary order')


def validate_events(m,events,success=True):
    import jsonschema
    manifest(m); schema=jsonschema.Draft202012Validator(read(SCHEMA))
    by_runtime={s['runtime_id']:s for s in m['runtimes']}
    requests={q['request_id']:q for q in m['warmup_requests']+m['requests']}
    by_key={s['model_key']:s for s in m['runtimes']}; ended=set(); previous=-1; session_ended=False
    for seq,e in enumerate(events):
        schema.validate(e)
        if e['sequence']!=seq or e['mono_ns']<previous:raise ValueError('event replay/order/clock')
        previous=e['mono_ns']
        if e['session_id']!=m['session_id'] or e['event'] not in EVENTS:raise ValueError('session/unknown event')
        if session_ended:raise ValueError('event after session terminal')
        rid=e['runtime_id'];qid=e['request_id']
        if rid is None:
            if qid is not None or e['worker_id'] is not None or any(e[k]!='not_applicable' for k in ('task','requested_backend','actual_backend')):
                raise ValueError('global identity mismatch')
            if e['event'] not in ('session_start','session_end','workload_start','workload_end','memory_sample','memory_sample_failed','memory_admission'):
                raise ValueError('runtime/request event without identity')
        else:
            if rid not in by_runtime:raise ValueError('runtime identity mismatch')
            slot=by_runtime[rid];spec=m['models'][slot['model_key']];backend=spec['execution']['backend']
            if (e['task'],e['requested_backend'],e['actual_backend'],e['worker_id'])!=(spec['model']['task_id'],backend,'CPU' if backend=='CPU' else 'GPU_unverified',slot['worker_id']):
                raise ValueError('actual backend/task/worker mismatch')
            if qid is not None:
                if qid not in requests or by_key[requests[qid]['model_key']]['runtime_id']!=rid:raise ValueError('request/runtime identity')
                if qid in ended:raise ValueError('execution after request terminal')
        if e['event']=='request_terminal':
            if qid is None or e['terminal_state'] not in ('succeeded','failed','rejected'):raise ValueError('terminal state')
            ended.add(qid)
        elif e['event']=='session_end':session_ended=True
        elif e['terminal_state']!='running' and e['event']!='memory_sample_failed':raise ValueError('premature terminal')
        if e['event'] in ('memory_admission','memory_sample'):
            d=e['data'];integer(d['snapshot_start_ns']);integer(d['snapshot_end_ns'])
            if not d['snapshot_start_ns']<=d['snapshot_end_ns']<=e['mono_ns']:raise ValueError('memory clock')
            reason=memory_decision(d)
            if success and (d['thermal_status']!=0 or d['low_memory']):raise ValueError('out-of-scope environmental sample')
            if e['event']=='memory_admission':
                if (d['contract'],d['reason'],d['decision'],d['reserve_bytes'])!=(MEMORY,reason,'admit' if reason=='admit' else 'reject',max(d['threshold_bytes'],d['observed_peak_pss_bytes'])):
                    raise ValueError('memory gate falsified')
                if success and reason!='admit':raise ValueError('failed admission in success')
    first=exactly(events,'session_start');last=exactly(events,'session_end')
    if first['sequence']!=0 or last['sequence']!=len(events)-1 or last['mono_ns']-first['mono_ns']>120000000000:
        raise ValueError('session boundary/bound')
    if not success:
        if last['terminal_state']=='succeeded':raise ValueError('failure disguised')
        rejected=[e for e in events if e['event']=='memory_admission' and e['data']['decision']=='reject']
        if any(e['data']['stage'] in ('before_runtime_creation','before_workload') for e in rejected) and any(e['event']=='workload_start' for e in events):
            raise ValueError('workload after admission rejection')
        return dict(status='failed_preserved',session_id=m['session_id'])
    if last['terminal_state']!='succeeded' or ended!=set(requests):raise ValueError('missing successful terminals')
    if any(e['event'] in ('memory_sample_failed','request_error') for e in events):raise ValueError('hidden telemetry failure')
    ws=exactly(events,'workload_start');we=exactly(events,'workload_end')
    ordered(events,['session_start','workload_start','workload_end','session_end'])
    for rid,slot in by_runtime.items():
        es=[e for e in events if e['runtime_id']==rid and e['request_id'] is None]
        ordered(es,RUNTIME_EVENTS)
        backend=m['models'][slot['model_key']]['execution']['backend']
        required=set(RUNTIME_EVENTS+['memory_admission']+(['delegate_creation_not_applicable','delegate_close_not_applicable'] if backend=='CPU' else
            ['delegate_creation_start','delegate_creation_end','delegate_attachment_start','delegate_attachment_end','delegate_close_start','delegate_close_end']))
        if len(es)!=len(required) or {e['event'] for e in es}!=required:raise ValueError('unexpected/duplicate runtime event')
        if backend=='CPU':
            exactly(es,'delegate_creation_not_applicable');exactly(es,'delegate_close_not_applicable')
            if any(e['event']=='delegate_creation_start' for e in es):raise ValueError('fabricated CPU delegate')
        else:
            ordered(es,['delegate_creation_start','delegate_creation_end','delegate_attachment_start','delegate_attachment_end','interpreter_construction_start',
                        'runtime_ready','runtime_close_start','delegate_close_start','delegate_close_end','runtime_close_end'])
        if exactly(es,'runtime_ready')['mono_ns']>=ws['mono_ns'] or exactly(es,'runtime_close_start')['mono_ns']<=we['mono_ns']:
            raise ValueError('setup/close inside active workload')
        gate=exactly(es,'memory_admission')
        if gate['data']['stage']!='before_runtime_creation' or gate['sequence']>=exactly(es,'runtime_creation_requested')['sequence']:
            raise ValueError('missing pre-create admission')
    globalgate=exactly([e for e in events if e['runtime_id'] is None],'memory_admission')
    if globalgate['data']['stage']!='before_workload' or globalgate['sequence']>=ws['sequence']:raise ValueError('workload admission order')
    warm_ids={q['request_id'] for q in m['warmup_requests']}; samples=[];lanes={}
    invocation_counts={}
    for qid in sorted(requests,key=lambda q:exactly([e for e in events if e['request_id']==q],'invocation_start')['sequence']):
        q=requests[qid]
        es=[e for e in events if e['request_id']==qid];ordered(es,REQUEST_EVENTS)
        required=set(REQUEST_EVENTS+(['persist_complete'] if q['priority']=='normal' else []))
        if len(es)!=len(required) or {e['event'] for e in es}!=required:raise ValueError('unexpected/duplicate request event')
        if exactly(es,'request_terminal')['terminal_state']!='succeeded':raise ValueError('failed request')
        if q['priority']=='normal':ordered(es,['output_ready','persist_complete','active_service_end'])
        elif any(e['event']=='persist_complete' for e in es):raise ValueError('wrong completion contract')
        start=exactly(es,'active_service_start');end=exactly(es,'active_service_end')
        inference=exactly(es,'invocation_end')['mono_ns']-exactly(es,'invocation_start')['mono_ns']
        if end['data']['inference_ns']!=inference or inference<0:raise ValueError('official inference timer mismatch')
        release=exactly(es,'worker_release_end');dispatch=exactly(es,'worker_dispatch')
        lanes.setdefault(dispatch['worker_id'],[]).append((dispatch['mono_ns'],release['mono_ns']))
        if qid in warm_ids:
            if release['sequence']>=ws['sequence']:raise ValueError('warmup inside workload')
        elif not ws['sequence']<start['sequence']<release['sequence']<we['sequence']:raise ValueError('workload boundary')
        runtime=[e for e in events if e['runtime_id']==start['runtime_id'] and e['request_id'] is None]
        completion=exactly(es,'persist_complete' if q['priority']=='normal' else 'output_ready')['mono_ns']
        if end['mono_ns']!=completion:raise ValueError('active completion boundary mismatch')
        rid=start['runtime_id'];invocation_counts[rid]=invocation_counts.get(rid,0)+1
        ordinal=invocation_counts[rid]
        samples.append(dict(session_id=m['session_id'],runtime_id=start['runtime_id'],request_id=qid,task=start['task'],
            backend=start['requested_backend'],role='warmup' if qid in warm_ids else m['purpose'],
            setup_ns=exactly(runtime,'runtime_ready')['mono_ns']-exactly(runtime,'runtime_creation_requested')['mono_ns'],
            active_service_ns=completion-start['mono_ns'],worker_occupancy_ns=release['mono_ns']-dispatch['mono_ns'],
            queue_wait_ns=exactly(es,'queue_wait_end')['mono_ns']-exactly(es,'request_enqueue')['mono_ns'],
            inference_ns=inference,thermal_applicability=[0],memory_admission='admit',
            runtime_state=dict(origin='initial_setup',invocation=ordinal,state='cold_first' if ordinal==1 else 'early_after_cold' if ordinal==2 else 'warm',
                               warm_qualified=False,meaning='warm label is ordinal only, not service-model approval'),
            transition_after_setup=dict(observed=False,reason='resident runtimes are not recreated during this workload'),
            setup_scope='one shared runtime lifecycle; do not add once per request'))
    for times in lanes.values():
        times.sort()
        if any(a[1]>b[0] for a,b in zip(times,times[1:])):raise ValueError('worker lane overlap')
    counts={e['data'].get('resident_count') for e in events if e['event']=='memory_sample'}
    if not set(range(len(by_runtime)+1))<=counts:raise ValueError('missing residency PSS')
    return dict(status='validated_events',session_id=m['session_id'],samples=samples)


def delegate_proof(m,log):
    count=sum(s['execution']['backend']=='GPU' for s in m['models'].values())
    if not count:return dict(actual_backend='CPU',status='not_requested')
    lines=log.splitlines();sid=m['session_id']
    starts=[i for i,l in enumerate(lines) if 'session_start='+sid in l];ends=[i for i,l in enumerate(lines) if 'session_finalized='+sid in l]
    if len(starts)!=1 or len(ends)!=1 or starts[0]>=ends[0]:raise ValueError('GPU log scope missing')
    pid=lines[starts[0]].split()[2]
    scoped='\n'.join(l for l in lines[starts[0]:ends[0]+1] if len(l.split())>2 and l.split()[2]==pid)
    replacements=re.findall(r'Replacing (\d+) out of (\d+) node\(s\) with delegate \(TfLiteGpuDelegateV2\)',scoped)
    kernels=re.findall(r'Created (\d+) GPU delegate kernels',scoped)
    if len(replacements)!=count or len(kernels)!=count or any(int(a)<=0 or a!=b for a,b in replacements) or any(int(k)<=0 for k in kernels):
        raise ValueError('unverified full GPU actual backend')
    if re.search(r'fallback|failed|unsupported op|restor\w*.*plan',scoped,re.I):raise ValueError('silent fallback')
    return dict(status='verified_full',actual_backend='GPU',instances=count,log_sha256=sha(scoped))


def validate(root,expected_manifest_sha256,delegate_log='',consumed=(),seen_traces=()):
    root=Path(root)
    if digest(root/'manifest.json')!=expected_manifest_sha256:raise ValueError('stale manifest binding')
    m=read(root/'manifest.json');manifest(m,consumed)
    p=read(root/'provenance.json')
    if p['protocol']!=PROTOCOL or p['session_id']!=m['session_id']:raise ValueError('provenance identity')
    names=[]
    for f in p['files']:
        name=f['name'];names.append(name)
        if Path(name).name!=name or (root/name).is_symlink() or digest(root/name)!=f['sha256'] or (root/name).stat().st_size!=f['bytes']:
            raise ValueError('artifact hash/path mismatch')
    if len(names)!=len(set(names)) or set(names)|{'provenance.json'}!={f.name for f in root.iterdir()}:
        raise ValueError('missing/replayed artifact')
    summary=read(root/'summary.json');events=read(root/'events.json')
    if summary['protocol']!=PROTOCOL or summary['session_id']!=m['session_id']:raise ValueError('summary identity')
    fingerprint=sha([{k:e[k] for k in ('event','mono_ns','task','requested_backend','worker_id')} for e in events])
    if fingerprint in seen_traces:raise ValueError('replayed event trace')
    result=validate_events(m,events,summary['status']=='succeeded')
    result.update(manifest_sha256=expected_manifest_sha256,trace_fingerprint=fingerprint,artifact_sha256=digest(root/'provenance.json'))
    result['session_start_ns']=exactly(events,'session_start')['mono_ns']
    result['session_end_ns']=exactly(events,'session_end')['mono_ns']
    environmental=[e['data'] for e in events if e['event'] in ('memory_sample','memory_admission')]
    result['thermal_drift']=dict(start=environmental[0]['thermal_status'],end=environmental[-1]['thermal_status'],
        battery_start_deci_c=environmental[0].get('battery_temperature_deci_c'),battery_end_deci_c=environmental[-1].get('battery_temperature_deci_c'))
    if summary['status']=='succeeded':
        result['gpu']=delegate_proof(m,delegate_log)
        peak=max(e['data']['pss_bytes'] for e in events if e['event'] in ('memory_sample','memory_admission'))
        if summary['sampled_peak_pss_bytes']!=peak:raise ValueError('sampled PSS summary mismatch')
        for s in result['samples']:
            r=read(root/(s['request_id']+'.result.json'))
            q=next(q for q in m['requests']+m['warmup_requests'] if q['request_id']==s['request_id'])
            im=next(i for i in m['images'] if i['sample_id']==q['sample_id']);model=m['models'][q['model_key']]
            if (r['inference_ns'],r['task_id'],r['requested_backend'],r['image_sha256'],r['model_sha256'])!=(s['inference_ns'],s['task'],s['backend'],im['sha256'],model['model']['sha256']):
                raise ValueError('result binding/timing')
            if r['actual_backend']!=('CPU' if s['backend']=='CPU' else 'unverified_requires_host_delegate_log'):
                raise ValueError('result actual backend')
            s['provenance_sha256']=result['artifact_sha256']
        result['sampled_peak_pss_bytes']=peak
    return result


def workload_key(m):
    def query(q):
        spec=m['models'][q['model_key']]
        return dict(task=spec['model']['task_id'],model=spec['model']['sha256'],sample=q['sample_id'],priority=q['priority'],offset_ms=q['offset_ms'])
    return sha(dict(seed=m['seed'],images=m['images'],requests=[query(q) for q in m['requests']],
                    warmup=[query(q) for q in m['warmup_requests']],thermal=m['thermal_gate'],deadline=m['deadline_ns'],
                    memory=m['memory_contract'],preprocess='canonical-srgb-png-v2/canonical-srgb-q16-stretch-v2',
                    terminal='output_ready_urgent/persist_complete_normal',warmup_count=m['warmup_per_runtime']))


def paired(a,b,receipts=None,consumed=()):
    manifest(a,consumed);manifest(b,consumed)
    if a['session_id']==b['session_id'] or a['configuration']!='resident_cpu_serial' or b['configuration']!='resident_corun':raise ValueError('pair arms')
    if a['paired']['pair_id']!=b['paired']['pair_id'] or a['paired']['order']!=b['paired']['order'] or (a['paired']['arm'],b['paired']['arm'])!=('A','B'):
        raise ValueError('paired identity/order')
    if workload_key(a)!=workload_key(b) or a['apk_sha256']!=b['apk_sha256'] or a['device_fingerprint']!=b['device_fingerprint']:
        raise ValueError('unmatched workload/environment')
    if ({q['request_id'] for q in a['requests']+a['warmup_requests']} & {q['request_id'] for q in b['requests']+b['warmup_requests']} or
            {s['runtime_id'] for s in a['runtimes']} & {s['runtime_id'] for s in b['runtimes']}):raise ValueError('paired request/runtime replay')
    if receipts is not None:
        if len(receipts)!=2 or {r['session_id'] for r in receipts}!={a['session_id'],b['session_id']} or any(r['status']!='validated_events' for r in receipts):raise ValueError('partial/failed pair')
        expected=[a['session_id'],b['session_id']] if a['paired']['order']=='AB' else [b['session_id'],a['session_id']]
        if [r['session_id'] for r in receipts]!=expected:raise ValueError('actual pair order mismatch')
        if receipts[0]['session_end_ns']>=receipts[1]['session_start_ns']:raise ValueError('paired time order/clock reset')
        if any(r['thermal_drift']['start']!=0 or r['thermal_drift']['end']!=0 for r in receipts):raise ValueError('paired thermal scope')
    return dict(status='matched_plan' if receipts is None else 'complete_pair',workload_sha256=workload_key(a))


def joint_sample(receipt,seed):
    if receipt['status']!='validated_events' or not receipt.get('samples'):raise ValueError('unvalidated joint block')
    integer(seed); sid=receipt['session_id']
    if any(s['session_id']!=sid or s['provenance_sha256']!=receipt['artifact_sha256'] for s in receipt['samples']):raise ValueError('mixed-session empirical sample')
    result=dict(protocol='service-v2-joint-v4',session_id=sid,provenance_sha256=receipt['artifact_sha256'],seed=seed,
                samples=receipt['samples'],scope='entire joint session; no independent setup/active mixing',service_model_approved=False)
    import jsonschema
    jsonschema.validate(result,read(SCHEMA.with_name('service-v2-joint-v4.schema.json')))
    setups={}
    for s in result['samples']:
        rid=s['runtime_id'];setups.setdefault(rid,s['setup_ns'])
        if setups[rid]!=s['setup_ns']:raise ValueError('mixed runtime setup samples')
    return result


def resample_session(receipts,seed,draw):
    integer(seed);integer(draw)
    if not receipts or len({r['session_id'] for r in receipts})!=len(receipts):raise ValueError('empty/replayed empirical session catalog')
    blocks=[joint_sample(r,seed) for r in sorted(receipts,key=lambda r:r['session_id'])]
    return blocks[int(sha(['joint-session-v4',seed,draw]),16)%len(blocks)]


def no_op(m):
    manifest(m)
    return dict(protocol=PROTOCOL,manifest_sha256=sha(m),device_commands=[],dispatch_count=0,simulated_completion_count=0)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['validate','no-op','dry-run'])
    p.add_argument('--root',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--expected-manifest-sha256');p.add_argument('--delegate-log',type=Path)
    a=p.parse_args()
    result=validate(a.root,a.expected_manifest_sha256,a.delegate_log.read_text() if a.delegate_log else '') if a.command=='validate' else no_op(read(a.manifest))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
