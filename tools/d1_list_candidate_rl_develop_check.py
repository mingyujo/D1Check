"""Verify completed artifacts/physical boundaries; never reruns an episode."""
import argparse,gzip,hashlib,json
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(run):
    run=Path(run);starts={};completed={}
    for line in (run/'execution.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line);target=starts if 'event' not in row else completed
        if row['number'] in target:raise ValueError('duplicate ledger record')
        target[row['number']]=row
    if set(starts)!=set(completed):raise ValueError('incomplete start/failure ledger')
    counts=dict(environments=len(starts),learning=sum(r['learning'] for r in starts.values()),planned=0,completed=0,
                failed=0,unsupported=0,lane_overlap=0,concurrent_scheduled_seconds=0.,response_rounding_max_ns=0)
    for number,start in starts.items():
        end=completed[number]
        if end['status']!='completed':raise ValueError('native failure remains')
        artifact=run/'items'/(start['identity']+'.json.gz')
        if sha(artifact)!=end['artifact_sha256']:raise ValueError('raw SHA mismatch')
        if end.get('controller_sha256') and sha(artifact.with_suffix('').with_suffix('.pt'))!=end['controller_sha256']:
            raise ValueError('controller artifact SHA mismatch')
        result=json.loads(gzip.decompress(artifact.read_bytes()));ledger=result['result']['ledger']
        if len(ledger)!=start['planned'] or len({q['id'] for q in ledger})!=len(ledger):raise ValueError('request lost/duplicated')
        counts['planned']+=start['planned'];counts['completed']+=sum(q['status']=='succeeded' for q in ledger)
        lanes={'CPU':[],'GPU':[]}
        for q in ledger:
            if q['backend'] not in lanes or (q['task']=='detection' and q['backend']!='CPU'):raise ValueError('unsupported backend')
            keys=('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')
            values=[q[k] for k in keys]
            if values!=sorted(values):raise ValueError('nonmonotonic phase/early release')
            response=q['output_ready_ns'] if q['task']=='classification' else q['persist_complete_ns']
            rounding=abs(q['response_ns']-(response-q['arrival_ns']))
            counts['response_rounding_max_ns']=max(counts['response_rounding_max_ns'],rounding)
            if rounding>1:raise ValueError('response/lane boundary confused')
            if q['late_success']!=(q['response_ns']>q['deadline_offset_ns']):raise ValueError('late completion hidden')
            lanes[q['backend']].append(q)
        for jobs in lanes.values():
            jobs.sort(key=lambda q:q['dispatch_ns'])
            if any(a['lane_available_ns']>b['dispatch_ns'] for a,b in zip(jobs,jobs[1:])):raise ValueError('lane reused before available')
        for a in lanes['CPU']:
            for b in lanes['GPU']:
                overlap=min(a['lane_available_ns'],b['lane_available_ns'])-max(a['dispatch_ns'],b['dispatch_ns'])
                if overlap>0:
                    if (a['task'],b['task'])!=('detection','classification'):raise ValueError('unmeasured parallel group')
                    counts['concurrent_scheduled_seconds']+=overlap/1e9
    if counts['environments']!=120 or counts['learning']!=0:raise ValueError('registered final count mismatch')
    if counts['planned']!=counts['completed']:raise ValueError('unfinished requests')
    if (run/'owner.lock').exists():raise ValueError('owned run not finished')
    evidence=dict(status='PASS',counts=counts,new_environment_starts=0,new_learning_starts=0,device_commands=0,
      response_rounding_scope='<=1ns from separately rounded absolute event/latency fields; not a KPI nonworse epsilon',
      parallel_scope='actual scheduled lane occupation, not hardware execution-only overlap')
    (run/'final_development_artifact_verification.json').write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    return evidence

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args();print(json.dumps(verify(args.run),indent=2))
