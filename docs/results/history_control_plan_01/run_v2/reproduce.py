"""Read-only failure readout. No device operations or model fitting."""
import argparse
import collections
import csv
import hashlib
import json
import re
from pathlib import Path

import numpy as np


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def readout(root, output):
    root, output = Path(root), Path(output)
    child = root / 'primary'
    receipt = read(child / 'FINAL_RECEIPT.json')
    plan = read(child / 'frozen_collection_plan.json')
    assert sha(child/'original_model_freeze.json')==plan['frozen_model']['sha256']
    assert sha(plan['activity_model']['path'])==plan['activity_model']['sha256']
    session = next(child.glob('00_*'))
    events = [json.loads(x) for x in (session / 'failure_prefix/progress.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
    counts = collections.Counter(e['kind'] for e in events)
    rows = [read(p) for p in sorted((child / 'host_commands').glob('*/client/result.json'))]
    assert len(rows) == receipt['adb_commands']
    origin = read(root / 'claim.json')['monotonic_start']
    groups = collections.defaultdict(list)
    commands = []
    for r in rows:
        command = r['command'][3:]
        if command[:4] == ['shell', 'run-as', 'com.example.d1check.benchmarkrunner.modelprobe', 'ls']:
            purpose = 'session_listing'
        elif command == ['shell', 'dumpsys', 'thermalservice']:
            purpose = 'thermal'
        elif command == ['exec-out', 'cat', '/proc/uptime']:
            purpose = 'clock_bracket'
        elif command[0] in ('push', 'pull') or command[:3] == ['shell', 'pm', 'install']:
            purpose = 'transfer_install_pull'
        elif command[:3] == ['shell', 'am', 'force-stop'] or command[:3] == ['shell', 'ps', '-A']:
            purpose = 'host_cleanup'
        else:
            purpose = 'other_gate_staging_recovery_trace'
        commands.append(dict(index=len(commands), purpose=purpose, status=r['status'], returncode=r['returncode'],
            start_s=r['monotonic_start']-origin, end_s=r['monotonic_end']-origin,
            elapsed_s=r['elapsed_seconds'], timeout_s=r['timeout_seconds'],
            right_censored=r['status']=='timeout', stdout_bytes=r['stdout_bytes'], stderr_bytes=r['stderr_bytes']))
        groups[purpose].append(r)
    delays=[]
    for purpose, rs in groups.items():
        exact=[r['elapsed_seconds'] for r in rs if r['status']!='timeout']
        delays.append(dict(purpose=purpose, attempts=len(rs), timeout_count=sum(r['status']=='timeout' for r in rs),
            nonzero_return_count=sum(r['status']!='timeout' and r['returncode']!=0 for r in rs),
            returned_median_s=float(np.median(exact)) if exact else None,
            returned_p95_s=float(np.quantile(exact,.95)) if exact else None,
            returned_max_s=max(exact) if exact else None,
            client_wait_s=sum(r['elapsed_seconds'] for r in rs)))
    failure = next(r for r in rows if r['status']=='timeout')
    boundary = read(session/'failure_prefix/conditioning_common_boundary.json')
    requests = read(session/'failure_prefix/conditioning_requests.json')
    assert len(requests)==96 and all(r['terminal_status']=='succeeded' for r in requests)
    assert all(counts[k]==96 for k in ['request_start','host_inference_return','output_ready','persist_complete','worker_release','lane_available'])
    approval=read(session/'start_ap_gate/host_approval.json')
    cleanup=read(session/'failure_host_cleanup.json')
    hal=cleanup['thermal'].split('Current temperatures from HAL:',1)[1].split('Current cooling devices',1)[0]
    final_temperatures={name:float(value) for value,name in re.findall(r'mValue=([0-9.]+), mType=\d+, mName=(\w+)',hal)}
    process_stdout=(child/'host_commands/0617/client/stdout.bin').read_bytes()
    assert rows[617]['returncode']==0 and b'com.example.d1check.benchmarkrunner.modelprobe' not in process_stdout
    missing=[p.name for p in (session/'failure_prefix').glob('*.invalid.bin')]
    summary=dict(status=receipt['status'], source_head='a081d55e9cc9d1a732bee9bed9e1ca8535244b29',
        campaign_plan_sha256=read(root/'claim.json')['plan_sha256'],
        primary_receipt_sha256=sha(child/'FINAL_RECEIPT.json'),
        campaign_receipt_sha256=sha(root/'primary_campaign_receipt.json'),
        frozen_model_sha256=sha(child/'original_model_freeze.json'),
        activity_model_sha256=plan['activity_model']['sha256'],
        eligible_development=0, eligible_confirmation=0, session_attempts=1, launches=1,
        attempted_condition='development_30_C0', runtime_started=counts['runtime_start'],runtime_returned=counts['runtime_return'],
        warmup_started=counts['warmup_start'],warmup_returned=counts['warmup_return'],
        conditioning_started=counts['request_start'],conditioning_returned=counts['host_inference_return'],
        conditioning_output_ready=counts['output_ready'],conditioning_persisted=counts['persist_complete'],
        conditioning_worker_release=counts['worker_release'],conditioning_lane_available=counts['lane_available'],
        known_inference_starts=counts['warmup_start']+counts['request_start'],
        planned_target_requests=0, target_common_window_started=False,
        last_durable_event=events[-1]['kind'], last_durable_phase=events[-1]['phase'],
        missing_calls='unknown after final durable prefix; not assigned zero',
        conditioning_registered_window_s=(boundary['planned_end_ns']-boundary['start_ns'])/1e9,
        conditioning_recorded_end_s=(boundary['end_ns']-boundary['start_ns'])/1e9,
        power_samples=len([e for e in events if e['kind']=='power_sample']),
        conditioning_power_tail_unbracketed_s=(boundary['planned_end_ns']-max(e['mono_ns'] for e in events if e['kind']=='power_sample'))/1e9,
        start_ap_host_c=float(approval['sample']['AP']), start_ap_in_development_range=approval['initial_ap_in_frozen_development_range'],
        failure=dict(command_index=605,purpose='session_listing',status=failure['status'],timeout_s=failure['timeout_seconds'],
            elapsed_client_s=failure['elapsed_seconds'],returncode=failure['returncode'],root_reaped=failure.get('root_reaped'),
            stdout_bytes=failure['stdout_bytes'],stderr_bytes=failure['stderr_bytes'],
            utc_start=failure['utc_start'],utc_end=failure['utc_end'],internal_cause='unresolved'),
        adb_attempts=len(rows), installation=read(child/'installation/installation_receipt.json')['status'],
        apk_pushes=receipt['installation']['apk_transfer_attempts'],installs=receipt['installation']['install_attempts'],
        installed_host_pulls=sum(r['command'][3]=='pull' and r['command'][4].endswith('.apk') for r in rows),
        trace_host_pulls=sum(r['command'][3]=='pull' and r['command'][4].endswith('.pftrace') for r in rows),
        staging_attempts=1,staged_files=sum(r['command'][3]=='push' and r['command'][5].endswith('.part') for r in rows),child_elapsed_s=receipt['elapsed_seconds'],
        campaign_elapsed_s=21600-read(root/'primary_campaign_receipt.json')['remaining_seconds'],
        returned_client_wait_s=sum(r['elapsed_seconds'] for r in rows if r['status']!='timeout'),
        censored_timeout_client_wait_s=sum(r['elapsed_seconds'] for r in rows if r['status']=='timeout'),
        host_command_overlapping_pairs=sum(b['monotonic_start']<a['monotonic_end'] for a,b in zip(rows,rows[1:])),
        host_cleanup=cleanup['status'], app_cleanup='not_recovered',
        session_host_force_stop_count=sum(r['command'][3:]==['shell','am','force-stop','com.example.d1check.benchmarkrunner.modelprobe'] for r in rows[605:]),
        process_absence='confirmed by original command 0617 after force-stop',
        final_numeric_ap_c=final_temperatures['AP'], final_bat_c=final_temperatures['BAT'],
        final_thermal_status=int(re.search(r'Thermal Status:\s*(\d+)',cleanup['thermal']).group(1)),
        connection_loss='not demonstrated; silent timeout and successful subsequent recovery',
        connection_wait_attempts=0, supplementary_recovery_attempts=0, repair_runs=0,
        app_lifecycle_failure='not present in recovered prefix; later callbacks unknown',
        missing_artifacts=missing, prediction_j=None,prediction_ap_error=None,candidate_freeze=None,
        analysis_scope='failure/partial conditioning evidence only; no completed target or model accuracy comparison',
        accuracy_pass=None,strict_support=False,experiment_ready=False)
    output.mkdir(parents=True,exist_ok=True)
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for name,data in [('commands.csv',commands),('command_delays.csv',delays)]:
        with (output/name).open('w',encoding='utf8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    timeline=[]
    wanted={'session_start','host_gate_accepted','phase_start','phase_end','common_start','common_end','history_conditioning_start','history_recovery_start','activity_lifecycle'}
    for e in events:
        if e['kind'] in wanted:
            timeline.append(dict(clock='Android monotonic',event=e['kind'],phase=e['phase'],time_ns=e['mono_ns'],
                relative_s=(e['mono_ns']-boundary['start_ns'])/1e9,host_utc='',meaning='recorded app event'))
    for i in [603,604,605,606,615,616,617]:
        r=rows[i]
        timeline.append(dict(clock='host monotonic + UTC',event='host_command_'+str(i),phase=commands[i]['purpose'],
            time_ns='',relative_s=r['monotonic_start']-origin,host_utc=r['utc_start'],meaning=r['status']))
    with (output/'timeline.csv').open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(timeline[0]));writer.writeheader();writer.writerows(timeline)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(10,5.8),layout='constrained')
    app_start=next(e['mono_ns'] for e in events if e['kind']=='session_start')
    baseline_start=next(e['mono_ns'] for e in events if e['kind']=='phase_start')
    baseline_end=next(e['mono_ns'] for e in events if e['kind']=='phase_end')
    recovery_start=events[-1]['mono_ns']
    for name,a,b,color in [('Setup/warmup',app_start,baseline_start,'#888888'),('Resident baseline',baseline_start,baseline_end,'#4c78a8'),
        ('Conditioning common window',boundary['start_ns'],boundary['end_ns'],'#f58518')]:
        axes[0].barh(name,(b-a)/1e9,left=(a-boundary['start_ns'])/1e9,color=color)
    axes[0].axvline((recovery_start-boundary['start_ns'])/1e9,color='#b22222',linestyle='--',label='Last durable event: recovery start')
    axes[0].set(xlabel='Android monotonic seconds relative to conditioning origin',title='Partial app evidence; target window never recorded')
    axes[0].legend(fontsize=8)
    for c in commands:
        color='#b22222' if c['right_censored'] else '#4c78a8'
        axes[1].plot([c['start_s'],c['end_s']],[c['index'],c['index']],color=color,linewidth=2)
    axes[1].axvline(commands[605]['start_s'],color='#b22222',linestyle='--',label='Listing timeout (3 s bound)')
    axes[1].set(xlabel='Host monotonic seconds relative to parent claim (different origin)',ylabel='ADB command index',title='Original command log only; no assumed direct host/app clock alignment')
    axes[1].legend(fontsize=8)
    for extension in ('png','svg'):fig.savefig(output/('execution_boundary.'+extension),dpi=140)
    plt.close(fig)
    svg=output/'execution_boundary.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    return summary


if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('--raw',required=True);cli.add_argument('--output',required=True)
    args=cli.parse_args();print(json.dumps(readout(args.raw,args.output),ensure_ascii=False,indent=2))
