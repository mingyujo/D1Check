"""Focused COLLECT-04/05 and sampler raw replay. Never invokes ADB or reruns fits."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import statistics

from tools import d1_energy_trace_account as ledger
from tools import d1_energy_temperature as old_gate
from tools.d1_logger_v4 import parse_thermalservice


def read(p):return json.loads(p.read_text(encoding='utf8'))
def lines(p):return [json.loads(x) for x in p.read_text(encoding='utf8').splitlines()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def session(d):
    progress=d/'artifacts/progress.jsonl'
    if not progress.exists():progress=d/'failure_prefix/progress.jsonl'
    ev=lines(progress);th=lines(d/'thermal.jsonl')
    # Actual persisted dumpsys -> existing parser, not hand-crafted sensor mocks.
    for t in th:
        parsed=parse_thermalservice(t['raw'])
        assert parsed['AP']==t['AP'] and parsed['thermal_status']==t['thermal_status']
    req=d/'artifacts/load.requests.json'
    replay=ledger.replay(ev,read(req) if req.exists() else [])
    phases=[]
    for x in replay['partition']:
        a,b=x['start_ns'],x['end_ns'];rr=[t for t in th if a<=t['mono_ns']<=b and t.get('AP','')!='']
        vals=[float(t['AP']) for t in rr]
        tail=[float(t['AP']) for t in rr if t['mono_ns']>=b-60e9]
        phases.append(dict(phase=x['phase'],start_ns=a,end_ns=b,duration_s=(b-a)/1e9,
            complete=x['phase_end_observed'],samples=len(rr),energy=x['energy'],
            AP_median=statistics.median(vals) if vals else None,AP_first=vals[0] if vals else None,
            AP_last=vals[-1] if vals else None,AP_range=[min(vals),max(vals)] if vals else None,
            last60_range=[min(tail),max(tail)] if tail else None))
    reasons=collections.Counter()
    ready=d/'gate_probe/probe.ready.json'
    if ready.exists() and (d/'gate_probe/temperature_preparation_failure.json').exists():
        a=read(ready)['mono_ns'];history=[]
        anchor=read(d/'gate_probe/temperature_preparation_failure.json')['anchor_c']
        for t in th:
            history.append(t)
            if t['mono_ns']>=a:reasons[old_gate.assess(history,a,anchor)['reason']]+=1
    validated=d/'validated.json'
    if validated.exists():
        v=read(validated)
        for old,new in [('equal_work','work_to_persist_complete'),('common_window','common_work_window')]:
            assert abs(v['metrics'][old]['covered_energy_j']-replay['windows'][new]['covered_energy_j'])<1e-6
    return dict(session=d.name,progress_sha256=sha(progress),thermal_sha256=sha(d/'thermal.jsonl'),
        evidence_paths=[str(progress),str(d/'thermal.jsonl')],
        first_event_ns=ev[0]['mono_ns'],last_event_ns=ev[-1]['mono_ns'],
        runtime_return_ns=[x['mono_ns'] for x in ev if x['kind']=='runtime_return'],
        warmup_return_ns=[x['mono_ns'] for x in ev if x['kind']=='warmup_return'],
        phases=phases,replay=replay,old_gate_reasons=dict(reasons),
        app_cleanup_observed=any(x['kind']=='app_cleanup' for x in ev),
        parser_replay_samples=len(th))


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();assert not a.output.exists(),'new output only'
    runs=[]
    for name in ('energy_collection_run_v4','energy_collection_run_v5','energy_sampler_load_run_v1'):
        root=a.root/name
        entries=[session(d) for d in sorted(root.glob('[0-9][0-9]_*')) if d.is_dir()]
        runs.append(dict(run=name,receipt_sha256=sha(root/'FINAL_RECEIPT.json'),receipt=read(root/'FINAL_RECEIPT.json'),sessions=entries))
    a.output.mkdir(parents=True)
    (a.output/'review.json').write_text(json.dumps(dict(version='energy-design-review-v1',runs=runs),indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps({'runs':len(runs),'sessions':sum(len(r['sessions']) for r in runs),
        'parser_samples':sum(s['parser_replay_samples'] for r in runs for s in r['sessions']),
        'output':str(a.output),'device_commands':0}))


if __name__=='__main__':main()
