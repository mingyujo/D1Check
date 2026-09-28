"""Read-only audit of one observed host-command archive; writes aggregate data only."""
import argparse
import bisect
import collections
import datetime as dt
import json
import statistics
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def category(command):
    args = command[1:]
    if args[:1] == ['-s']:
        args = args[2:]
    if args[:3] == ['shell', 'run-as', 'com.example.d1check.benchmarkrunner.modelprobe']:
        return 'readiness_ls' if args[3:4] == ['ls'] else 'app_artifact_read'
    if args[:2] == ['shell', 'dumpsys']:
        return 'thermal' if args[2:3] == ['thermalservice'] else 'screen_or_system_dumpsys'
    if args[:2] == ['shell', 'settings']:
        return 'screen_settings'
    if args[:2] == ['shell', 'sha256sum']:
        return 'installed_apk_hash'
    if args[:2] == ['shell', 'pm']:
        return 'package_query'
    if args[:3] == ['shell', 'sh', '-c']:
        return 'screen_power_state'
    if args[:3] == ['shell', 'test', '-e'] or args[:3] == ['shell', 'mkdir', '-p']:
        return 'staging_setup'
    if args[:2] == ['shell', 'am'] and args[2:3] == ['force-stop']:
        return 'host_force_stop'
    if args[:2] == ['shell', 'am']:
        return 'app_launch_or_arm'
    if args[:1] == ['push']:
        return 'staging_push'
    if args[:1] == ['pull']:
        return 'installed_apk_pull'
    if args[:1] == ['exec-out']:
        if args[1:3] == ['cat', '/proc/uptime']:
            return 'device_uptime_bracket'
        return 'archive_or_artifact_exec_out'
    if args[:2] == ['shell', 'pidof']:
        return 'heartbeat_pidof'
    if args[:1] == ['logcat']:
        return 'delegate_log'
    if args[:1] == ['devices']:
        return 'transport_list'
    return 'other:' + ' '.join(args[:2])


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered)-1)*q
    lower = int(index)
    return ordered[lower] + (ordered[min(lower+1,len(ordered)-1)]-ordered[lower])*(index-lower)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root, output = Path(args.run_root), Path(args.output)
    checkpoints = [read(x) for x in root.glob('host_checkpoints/*.json')]
    checkpoints.sort(key=lambda x: x['utc'])
    current_session = None
    for checkpoint in checkpoints:
        if checkpoint['stage'] == 'session_reserved':
            current_session = checkpoint['session_index']
        checkpoint['effective_session'] = current_session
    checkpoint_times = [dt.datetime.fromisoformat(x['utc']).timestamp() for x in checkpoints]
    groups = collections.defaultdict(list)
    records = []
    for folder in root.glob('host_commands/*'):
        result_path = folder/'client/result.json'
        if not result_path.is_file():
            continue
        record = read(result_path)
        when = dt.datetime.fromisoformat(record['utc_start']).timestamp()
        index = bisect.bisect_right(checkpoint_times, when)-1
        prior = checkpoints[index] if index >= 0 else {}
        kind = category(record['command'])
        row = dict(slot=int(folder.name), category=kind, stage=prior.get('stage','pre_checkpoint'),
                   session_index=prior.get('effective_session'), status=record['status'],
                   returncode=record['returncode'], elapsed_s=record['elapsed_seconds'],
                   stdout_bytes=record['stdout_bytes'], stderr_bytes=record['stderr_bytes'],
                   start=record['monotonic_start'], end=record['monotonic_end'])
        records.append(row)
        groups[(row['session_index'],kind)].append(row)
    records.sort(key=lambda x:x['slot'])
    summary=[]
    for (session,kind),rows in sorted(groups.items(),key=lambda pair:(-1 if pair[0][0] is None else pair[0][0],pair[0][1])):
        returned=[r['elapsed_s'] for r in rows if r['status']=='returned' and r['returncode']==0]
        summary.append(dict(session='preflight_or_final' if session is None else session, category=kind,
            count=len(rows), returned=len(returned), timeout=sum(r['status']=='timeout' for r in rows),
            other_failure=sum(r['status']!='timeout' and (r['status']!='returned' or r['returncode']!=0) for r in rows),
            p50_returned_s=percentile(returned,.5),p95_returned_s=percentile(returned,.95),
            p99_returned_s=percentile(returned,.99),max_returned_s=max(returned) if returned else None,
            client_elapsed_sum_s=sum(r['elapsed_s'] for r in rows),
            stdout_bytes=sum(r['stdout_bytes'] for r in rows),stderr_bytes=sum(r['stderr_bytes'] for r in rows),
            stdout_p50_bytes=percentile([r['stdout_bytes'] for r in rows],.5),
            stdout_p95_bytes=percentile([r['stdout_bytes'] for r in rows],.95),
            stdout_max_bytes=max(r['stdout_bytes'] for r in rows)))
    overlaps=[]
    for left,right in zip(records,records[1:]):
        if right['start'] < left['end']:
            overlaps.append([left['slot'],right['slot']])
    readiness=[r for r in records if r['category']=='readiness_ls']
    gaps=[b['start']-a['start'] for a,b in zip(readiness,readiness[1:]) if a['session_index']==b['session_index']]
    result=dict(recorded_commands=len(records),first_slot=records[0]['slot'],last_slot=records[-1]['slot'],
                missing_slots=sorted(set(range(records[-1]['slot']+1))-{r['slot'] for r in records}),
                client_elapsed_sum_s=sum(r['elapsed_s'] for r in records),
                overlapping_adjacent_clients=overlaps,
                readiness_start_gap_p50_s=percentile(gaps,.5),
                readiness_start_gap_p95_s=percentile(gaps,.95),
                categories=summary,
                timeout_slots=[r['slot'] for r in records if r['status']=='timeout'])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(commands=len(records),timeouts=result['timeout_slots'],
                          overlaps=len(overlaps),readiness=len(readiness),
                          client_elapsed_sum_s=result['client_elapsed_sum_s']),ensure_ascii=False))

if __name__ == '__main__':
    main()
