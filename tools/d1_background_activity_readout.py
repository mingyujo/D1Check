"""Offline CPU/whole-device association only. Missing trace/clock/loss is not zero activity."""
import argparse
import csv
import json
import subprocess
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


def summarize(folder,start_ns,end_ns):
    folder=Path(folder)
    if not 0<=start_ns<end_ns:raise ValueError('window')
    clocks=read_csv(folder/'clock.csv',('ts','clock_id','clock_value'))
    if not clocks or any(int(c['clock_id'])!=6 or int(c['ts'])!=int(c['clock_value']) for c in clocks):
        raise ValueError('BOOTTIME alignment unavailable; do not shift to fit AP')
    losses=read_csv(folder/'loss.csv',('name','value'))
    if losses:raise ValueError('trace loss/error; activity inference unsupported')
    rows=read_csv(folder/'sched.csv',('ts','dur','cpu','activity_class'))
    if not rows or min(int(r['ts']) for r in rows)>start_ns or max(int(r['ts'])+int(r['dur']) for r in rows)<end_ns:
        raise ValueError('trace does not bracket window')
    groups=('benchmark','tracer','other','unknown','idle');bins=[]
    cpus={int(r['cpu']) for r in rows}
    for cpu in cpus:
        previous=None
        for row in sorted((r for r in rows if int(r['cpu'])==cpu),key=lambda r:int(r['ts'])):
            ts=int(row['ts']);dur=int(row['dur'])
            if dur<=0 or (previous is not None and ts<previous):raise ValueError('overlapping/unfinished sched slices')
            previous=ts+dur
    for a in range(start_ns,end_ns,5_000_000_000):
        b=min(end_ns,a+5_000_000_000);total={k:0 for k in groups}
        for r in rows:
            k=r['activity_class']
            if k not in total:raise ValueError('unregistered activity class')
            ts=int(r['ts']);dur=int(r['dur'])
            if dur<=0:raise ValueError('unfinished/negative sched duration')
            total[k]+=max(0,min(ts+dur,b)-max(ts,a))
        covered=sum(total.values())
        expected=(b-a)*len(cpus)
        if covered>expected:raise ValueError('overlapping/double counted scheduler slices')
        full=covered==expected
        bins.append(dict(start_s=(a-start_ns)/1e9,end_s=(b-start_ns)/1e9,
            sched_coverage_fraction=covered/expected,full_sched_coverage=full,
            **{k+'_cpu_seconds':v/1e9 if full else None for k,v in total.items()}))
    frequencies=read_csv(folder/'frequency.csv',('ts','value','cpu'))
    return dict(status='descriptive_cpu_activity_only',bins=bins,
        cpu_frequency_supported=bool(frequencies),frequency_samples=len(frequencies),
        absence_of_activity_proven=False,rail_power_identified=False,gpu_radio_identified=False,
        trace_to_app_clock='verified BOOTTIME equality',experiment_ready=False)


def export(processor,trace,output):
    output=Path(output)
    if output.exists():raise ValueError('fresh export only')
    output.mkdir(parents=True)
    binding=dict(processor_sha256=p.digest(processor),trace_sha256=p.digest(trace),queries={})
    for name in QUERIES:
        query=ROOT/f'tools/perfetto/background_{name}.sql'
        binding['queries'][name]=p.digest(query)
        result=subprocess.run([str(processor),str(trace),'--query-file',str(query)],capture_output=True,timeout=60)
        (output/(name+'.csv')).write_bytes(result.stdout)
        (output/(name+'.stderr')).write_bytes(result.stderr)
        cal.write_new(output/(name+'.result.json'),dict(exit_code=result.returncode))
        if result.returncode:raise RuntimeError('trace SQL failed '+name+'; partial output preserved')
    cal.write_new(output/'export_binding.json',binding)
    return binding


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
