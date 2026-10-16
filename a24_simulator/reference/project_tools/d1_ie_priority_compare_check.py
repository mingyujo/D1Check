"""Read-only audit of completed IE comparison evidence; no simulation starts."""
import argparse,gzip,hashlib,json,subprocess
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def check(run):
    run=Path(run);reg=read(run/'registration.json');starts={};ends={}
    caps=dict(reg['stage_caps']);expected=448;planned=28544
    if (run/'response_verification.json').exists():
        assert read(run/'response_verification.json')['status']=='PASS'
        caps.update(response_development=28,response_final_gate=4);expected=480;planned=30144
    for line in (run/'executions.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if row['phase'] not in caps:continue
        table=ends if 'event' in row else starts
        assert row['number'] not in table,'duplicate start/completion'
        table[row['number']]=row
    assert set(starts)==set(ends) and len(starts)==expected
    phase=Counter(r['phase'] for r in starts.values())
    assert dict(phase)==caps and len(starts)<=reg['new_environment_cap']
    for path,h in reg['source_sha256'].items():assert sha(ROOT/path)==h,path
    counts=dict(environments=expected,planned=0,completed=0,decisions=0,protect_selected=0,physical_overlap_s=0.)
    for number,start in starts.items():
        end=ends[number];assert end['status']=='completed'
        path=run/'items'/(start['identity']+'.json.gz');assert sha(path)==end['sha256']
        item=json.loads(gzip.decompress(path.read_bytes()));ledger=item['result']['ledger']
        assert len(ledger)==start['planned'] and len({q['id'] for q in ledger})==len(ledger)
        assert all(q['status']=='succeeded' for q in ledger)
        assert item['row']['completed']==len(ledger) and item['row']['incomplete']==0
        counts['planned']+=len(ledger);counts['completed']+=len(ledger)
        lanes={'CPU':[],'GPU':[]};by_id={q['id']:q for q in ledger}
        for q in ledger:
            assert q['backend'] in lanes and (q['task']!='detection' or q['backend']=='CPU')
            keys=('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')
            values=[q[k] for k in keys];assert values==sorted(values) and values[0]>=q['arrival_ns']
            response=q['output_ready_ns'] if q['task']=='classification' else q['persist_complete_ns']
            # The engine truncates absolute and elapsed ns independently.
            assert abs(q['response_ns']-(response-q['arrival_ns']))<=1
            assert q['late_success']==(q['response_ns']>q['deadline_offset_ns'])
            lanes[q['backend']].append(q)
        for jobs in lanes.values():
            jobs.sort(key=lambda q:q['dispatch_ns'])
            assert all(a['lane_available_ns']<=b['dispatch_ns'] for a,b in zip(jobs,jobs[1:]))
        for a in lanes['CPU']:
            for b in lanes['GPU']:
                overlap=min(a['lane_available_ns'],b['lane_available_ns'])-max(a['dispatch_ns'],b['dispatch_ns'])
                if overlap>0:
                    assert a['task']=='detection' and b['task']=='classification'
                    counts['physical_overlap_s']+=overlap/1e9
        for d in item['result']['decisions']:
            counts['decisions']+=1
            assert all(by_id[r]['arrival_ns']<=d['now_ns'] for r in d.get('ordered_ids',[]))
            if d.get('ordered_ids'):assert d['head_request_id']==d['ordered_ids'][0]
            selected=d.get('selected')
            if selected and d.get('sequencing_rule'):
                assert selected==dict(request_id=d['head_request_id'],backend=d['chosen_backend'])
            guard=d.get('CPU_protection')
            if guard and guard['GPU_route_allowed']:
                assert guard['classification_GPU_response']<=guard['classification_due']
                assert guard['GPU_route_expected_D_misses']<guard['CPU_route_expected_D_misses']
                assert not guard['future_arrivals_used'] and d['chosen_backend']=='GPU'
                counts['protect_selected']+=bool(selected)
        for priority,key in [('urgent','urgent_failure'),('normal','normal_failure')]:
            assert item['row'][key]==sum(q['priority']==priority and q['late_success'] for q in ledger)
    assert counts['planned']==planned and counts['planned']==counts['completed']
    assert read(run/'gate_verification.json')['status']=='PASS' and not (run/'owner.lock').exists()
    progress=read(run/'progress.json')['consumption']
    assert progress['new_environment_starts']==expected and progress['cumulative_environment_starts']==9269+expected
    assert progress['new_learning_starts']==0 and progress['cumulative_learning_starts']==1449
    result=dict(status='PASS',utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty=True,checker_sha256=sha(__file__),registration_sha256=sha(run/'registration.json'),source_files_verified=len(reg['source_sha256']),
        counts=counts,phase_counts=dict(phase),consumption=progress,latest_shared_consumption=read(run/'progress.json')['consumption'],verification_environment_learning_device_starts=0,
        scope='completed ledger/phase/lane/decision support audit; no physical energy or temperature accuracy claim')
    (run/'final_artifact_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    return result
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--run',required=True);args=a.parse_args();print(json.dumps(check(args.run),indent=2))
