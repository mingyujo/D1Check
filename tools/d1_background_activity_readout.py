"""Offline CPU/whole-device association only. Missing trace/clock/loss is not zero activity."""
import argparse
import csv
import json
import subprocess
import time
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
ROOT=Path(__file__).resolve().parents[1]
QUERIES=('sched','frequency','loss','clock')


def read_csv(file,columns):
    with Path(file).open(encoding='utf8',newline='') as f:
        reader=csv.DictReader(f)
        if not set(columns)<=set(reader.fieldnames or []):raise ValueError('trace export schema '+str(file))
        return list(reader)


def summarize(folder,start_ns,end_ns,expected_cpus=None,deadline=None):
    folder=Path(folder)
    def time_check():
        if deadline is not None and time.monotonic()>deadline:raise TimeoutError('trace content audit aggregate deadline')
    time_check()
    if not 0<=start_ns<end_ns:raise ValueError('window')
    clocks=read_csv(folder/'clock.csv',('ts','clock_id','clock_value'))
    if not clocks or any(int(c['clock_id'])!=6 or int(c['ts'])!=int(c['clock_value']) for c in clocks):
        raise ValueError('BOOTTIME alignment unavailable; do not shift to fit AP')
    losses=read_csv(folder/'loss.csv',('name','value'))
    if losses:raise ValueError('trace loss/error; activity inference unsupported')
    rows=read_csv(folder/'sched.csv',('ts','dur','cpu','activity_class'))
    time_check()
    if not rows or min(int(r['ts']) for r in rows)>start_ns or max(int(r['ts'])+int(r['dur']) for r in rows)<end_ns:
        raise ValueError('trace does not bracket window')
    groups=('benchmark','tracer','other','unknown','idle');width=5_000_000_000
    buckets=[dict(a=a,b=min(end_ns,a+width),total={k:0 for k in groups}) for a in range(start_ns,end_ns,width)]
    per_cpu={}
    # Each scheduler slice contributes only to intersected bins, rather than scanning
    # every trace row again for every bin. Bounds/clipping and denominators unchanged.
    for i,r in enumerate(rows):
        if i%4096==0:time_check()
        ts=int(r['ts']);dur=int(r['dur']);cpu=int(r['cpu']);k=r['activity_class']
        if k not in groups:raise ValueError('unregistered activity class')
        if dur<=0:raise ValueError('overlapping/unfinished sched slices')
        per_cpu.setdefault(cpu,[]).append((ts,ts+dur))
        a=max(ts,start_ns);b=min(ts+dur,end_ns)
        if b<=a:continue
        for index in range((a-start_ns)//width,(b-1-start_ns)//width+1):
            bucket=buckets[index];bucket['total'][k]+=min(b,bucket['b'])-max(a,bucket['a'])
    cpus=set(per_cpu)
    if expected_cpus is not None:
        declared={int(r['cpu']) for r in read_csv(folder/'cpu.csv',('cpu',))}
        if declared != set(expected_cpus) or cpus != declared:
            raise ValueError('missing/unexpected CPU; metadata and sched coverage required')
    for values in per_cpu.values():
        time_check();previous=None
        for ts,end in sorted(values):
            if previous is not None and ts<previous:raise ValueError('overlapping/unfinished sched slices')
            previous=end
    bins=[]
    for bucket in buckets:
        a,b,total=bucket['a'],bucket['b'],bucket['total'];covered=sum(total.values());expected=(b-a)*len(cpus)
        if covered>expected:raise ValueError('overlapping/double counted scheduler slices')
        full=covered==expected
        bins.append(dict(start_s=(a-start_ns)/1e9,end_s=(b-start_ns)/1e9,
            sched_coverage_fraction=covered/expected,full_sched_coverage=full,
            **{k+'_cpu_seconds':v/1e9 if full else None for k,v in total.items()}))
    frequencies=read_csv(folder/'frequency.csv',('ts','value','cpu'));time_check()
    return dict(status='descriptive_cpu_activity_only',bins=bins,
        cpu_frequency_supported=bool(frequencies),frequency_samples=len(frequencies),
        absence_of_activity_proven=False,rail_power_identified=False,gpu_radio_identified=False,
        trace_to_app_clock='verified BOOTTIME equality',experiment_ready=False)


def export(processor,trace,output,deadline=None,include_cpu=False):
    output=Path(output)
    if output.exists():raise ValueError('fresh export only')
    output.mkdir(parents=True)
    binding=dict(processor_sha256=p.digest(processor),trace_sha256=p.digest(trace),queries={})
    try:
        for name in QUERIES+(('cpu',) if include_cpu else ()):
            query=ROOT/f'tools/perfetto/background_{name}.sql'
            binding['queries'][name]=p.digest(query)
            limit=60 if deadline is None else min(60,deadline-time.monotonic())
            if limit<=0:raise TimeoutError('trace export aggregate deadline')
            started=time.monotonic()
            try:
                result=subprocess.run([str(processor),str(trace),'--query-file',str(query)],capture_output=True,timeout=limit)
            except subprocess.TimeoutExpired as error:
                (output/(name+'.csv')).write_bytes(error.stdout or b'')
                (output/(name+'.stderr')).write_bytes(error.stderr or b'')
                cal.write_new(output/(name+'.result.json'),dict(exit_code=None,status='timeout',elapsed_seconds=time.monotonic()-started,error=repr(error)))
                raise
            (output/(name+'.csv')).write_bytes(result.stdout)
            (output/(name+'.stderr')).write_bytes(result.stderr)
            cal.write_new(output/(name+'.result.json'),dict(exit_code=result.returncode,elapsed_seconds=time.monotonic()-started))
            if result.returncode:raise RuntimeError('trace SQL failed '+name+'; partial output preserved')
    except BaseException as error:
        binding.update(status='failed_or_partial',error=repr(error))
        raise
    else:binding['status']='exported_not_yet_validated'
    finally:cal.write_new(output/'export_binding.json',binding)
    return binding


def audit(processor,processor_sha256,trace,session_folder,output,deadline,expected_cpus):
    started=time.monotonic()
    if p.digest(processor)!=processor_sha256:raise ValueError('bound TraceProcessor hash drift')
    boundary_file=Path(session_folder)/'artifacts/common_boundary.json'
    if not boundary_file.is_file():raise ValueError('no complete app common window; trace not eligible for full-window analysis')
    boundary=p.read(boundary_file)
    history_file=Path(session_folder)/'artifacts/history_boundary.json'
    if history_file.is_file():
        history=p.read(history_file)
        if history.get('version')!='registered-history-control-v1':raise ValueError('unknown history boundary')
        boundary=dict(boundary,start_ns=history['conditioning_start_ns'])
    export(processor,trace,output,deadline,include_cpu=True)
    result=summarize(output,boundary['start_ns'],boundary['planned_end_ns'],expected_cpus,deadline)
    if not all(x['full_sched_coverage'] for x in result['bins']):
        raise ValueError('incomplete CPU coverage; no next session')
    if time.monotonic()>deadline:raise TimeoutError('trace content audit aggregate deadline')
    result.update(status='content_eligible_descriptive_only',elapsed_seconds=time.monotonic()-started,
        processor_sha256=processor_sha256,trace_sha256=p.digest(trace),expected_cpus=expected_cpus)
    cal.write_new(Path(output)/'audit.json',result)
    return result


def main():
    a=argparse.ArgumentParser();sub=a.add_subparsers(dest='action',required=True)
    e=sub.add_parser('export')
    for name in ('processor','trace','output'):e.add_argument('--'+name,required=True)
    s=sub.add_parser('summarize');s.add_argument('--folder',required=True)
    s.add_argument('--start-ns',required=True,type=int);s.add_argument('--end-ns',required=True,type=int)
    q=a.parse_args()
    result=export(q.processor,q.trace,q.output) if q.action=='export' else summarize(q.folder,q.start_ns,q.end_ns)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
