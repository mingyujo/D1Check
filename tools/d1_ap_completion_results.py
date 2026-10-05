"""Read-only evidence analysis of a completed or stopped AP completion study."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
from tools import d1_ap_completion_study as study
from tools import d1_resident_control_readout as control

p=study.p


def safe_csv(path,rows,fallback):
    fields=list(dict.fromkeys(k for row in rows for k in row)) or fallback
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def command_kind(command):
    args=command[3:] if len(command)>2 and command[1]=='-s' else command[1:]
    if args[:3]==['exec-out','cat','/proc/uptime']:return 'uptime'
    if args[:3]==['shell','dumpsys','thermalservice']:return 'thermal'
    if 'ls' in args:return 'listing'
    if 'force-stop' in args:return 'force_stop'
    if args[:3]==['shell','ps','-A']:return 'process_check'
    if args and args[0]=='pull':return 'installed_pull'
    if 'test' in args and '-e' in args:return 'fresh_path_probe'
    if 'cat' in args:return 'recovery_or_input'
    if args and args[0]=='push' or 'mv' in args or 'sha256sum' in args:return 'staging_or_gate'
    return 'identity_environment_launch_other'


def commands(root):
    groups=defaultdict(list);rows=[];overlap=[];previous=None
    for f in sorted(root.glob('*/client/result.json')):
        r=p.read(f);kind=command_kind(r['command'])
        row=dict(slot=f.parents[1].name,kind=kind,status=r['status'],exit_code=r['returncode'],
                 start_utc=r['utc_start'],end_utc=r['utc_end'],elapsed_s=r['elapsed_seconds'],
                 timeout_s=r['timeout_seconds'],stdout_bytes=r['stdout_bytes'],stderr_bytes=r['stderr_bytes'])
        if previous and r['monotonic_start']<previous['monotonic_end']:overlap.append(row['slot'])
        previous=r;rows.append(row);groups[kind].append(row)
    stats=[]
    for kind,items in groups.items():
        values=[r['elapsed_s'] for r in items if r['status']=='returned']
        stats.append(dict(kind=kind,count=len(items),returned=len(values),
            timeouts=sum(r['status']=='timeout' for r in items),nonzero=sum(r['status']=='nonzero_exit' for r in items),
            median_s=float(np.median(values)) if values else None,
            p95_s=float(np.percentile(values,95)) if values else None,
            p99_s=float(np.percentile(values,99)) if values else None,
            maximum_returned_s=max(values) if values else None,
            client_wait_sum_s=sum(r['elapsed_s'] for r in items)))
    return dict(rows=rows,groups=stats,overlap_slots=overlap,
        timeout_is_censored=True,client_wait_is_not_device_cpu_time=True)


def analyse(file,output):
    file,output=Path(file),Path(output);s=p.read(file);root=Path(s['output_root'])
    for protected in (root,file.parent,Path(s['registry'])):
        study.require(output.resolve()!=protected.resolve() and protected.resolve() not in output.resolve().parents,'protected evidence output')
    study.require(not output.exists(),'fresh PC readout required')
    receipt=p.read(root/'FINAL_RECEIPT.json');study.verify_sources(s)
    output.mkdir(parents=True);summary=dict(status=receipt['status'],plan_sha256=p.digest(file),
        budget=s['budget'],elapsed_s=receipt['elapsed_seconds'],blocks=[],model_fit_performed=(root/'development_selection.json').exists(),
        model_frozen=(root/'model_freeze.json').exists(),confirmation_attempted=(root/'confirmation').exists(),
        analysis_device_commands=0,accuracy_pass=None,strict_support=False,experiment_ready=False)
    ap_paths=[];session_rows=[]
    if s.get('confirmation_only'):
        binding=s['confirmation_model'];study.verify_remaining_freeze(s)
        summary.update(model_frozen=True,model_freeze_sha256=binding['sha256'],model_fit_performed=False,
            confirmation_only=True,previous_confirmations_retained=2,confirmation_continuity=s['continuity'])
    if 'imported_development' in s:
        binding=s['imported_development'];source_file=Path(binding['plan']['path']);source=p.read(source_file)
        entry=source['entries'][0];folder=Path(source['output_root'])/f"00_{entry['session_id']}"
        case=study.imported_case(s);params=p.read(study.contrast.memory.CANDIDATE)['fixed_parameters']
        values,init=study.model.predict(case,dict(beta=params['ap_cooling_rate_per_s'],k=1.,g=0.,parameters=params))
        desc=study.readout.describe(case,values,init,p.read(study.contrast.BUNDLE/'analysis_contract.json'))
        energy=control.session(folder,p.read(source_file.parent/entry['manifest']),p.read(source['frozen_model']['path']))
        session_rows.append(dict(phase='development',role=entry['phase'],condition='C',
            status='eligible_imported_from_stopped_v1',new_session=False,source_block='stopped_v1',
            energy_120s_j=energy['windows']['common']['observed_j'],predicted_diagnostic_j=energy['frozen_diagnostic_120s_j'],
            signed_energy_error_j=energy['signed_diagnostic_error_j'],ap_start_c=case['common_start_ap_c'],
            ap_first_s=desc['first_s'],ap_last_s=desc['last_s'],ap_samples=desc['samples'],
            ap_mae_c=desc['scores']['mae_c'],ap_max_error_c=desc['scores']['max_absolute_error_c'],
            ap_peak_signed_error_c=desc['scores']['peak_signed_error_c']))
        for t,y,v in zip(case['inputs']['query_s'],case['observed_ap_c'],values):
            ap_paths.append(dict(role=entry['phase'],common_s=t,observed_c=y,m0_c=v,residual_c=v-y,source_block='stopped_v1'))
        summary.update(imported_development_sessions=1,development_continuity=s['continuity'],
            previous_stopped_consumption=s['cumulative_previous'])
    for phase in ('development','confirmation'):
        planfile=file.parent/phase/'collection_plan.json';blockroot=root/phase
        if not planfile.exists():
            summary['blocks'].append(dict(phase=phase,status='not_attempted',sessions_completed=0))
            template=file.parent/phase/'template_plan.json'
            if template.exists():
                for e in p.read(template)['entries']:
                    session_rows.append(dict(phase=phase,role=e['phase'],condition=e['condition'],status='not_attempted',
                        energy_120s_j=None,predicted_diagnostic_j=None,ap_mae_c=None))
            continue
        plan=p.read(planfile)
        if not (blockroot/'FINAL_RECEIPT.json').exists():
            summary['blocks'].append(dict(phase=phase,status='receipt_missing_state_unknown'));continue
        r=p.read(blockroot/'FINAL_RECEIPT.json');cons=study.consumption.consumption(plan)
        cmd=commands(blockroot/'host_commands');safe_csv(output/(phase+'_command_latency.csv'),cmd['rows'],['slot','kind','status'])
        safe_csv(output/(phase+'_command_groups.csv'),cmd['groups'],['kind','count'])
        block=dict(phase=phase,status=r['status'],sessions_attempted=r.get('session_attempts'),
            sessions_completed=r.get('completed_sessions',r.get('sessions')),adb_commands=r['adb_commands'],
            elapsed_s=r['elapsed_seconds'],consumption=[],command_groups=cmd['groups'],command_overlap_slots=cmd['overlap_slots'])
        for e,consumed in zip(plan['entries'],cons):
            folder=blockroot/f"{e['index']:02d}_{e['session_id']}"
            clean={k:consumed[k] for k in ('role','planned_requests','launch_attempted','confirmed_not_attempted','counts','progress_integrity')}
            clean.update(app_cleanup_status=(consumed['app_cleanup'] or {}).get('status'),
                host_cleanup_status=(consumed['host_cleanup'] or {}).get('status'),
                call_counts_are_event_lower_bounds=not (folder/'validated.json').exists())
            block['consumption'].append(clean)
            item=dict(phase=phase,role=e['phase'],condition=e['condition'],
                status='not_attempted' if clean['confirmed_not_attempted'] else 'incomplete',
                energy_120s_j=None,predicted_diagnostic_j=None,ap_mae_c=None,new_session=True,source_block='current')
            if (folder/'validated.json').exists():
                case=study.readout.case_from_session(planfile,plan,e)
                params=p.read(study.contrast.memory.CANDIDATE)['fixed_parameters']
                frozen=dict(beta=params['ap_cooling_rate_per_s'],k=1.,g=0.,parameters=params)
                values,init=study.model.predict(case,frozen)
                desc=study.readout.describe(case,values,init,p.read(study.contrast.BUNDLE/'analysis_contract.json'))
                energy=control.session(folder,p.read(planfile.parent/e['manifest']),p.read(plan['frozen_model']['path']))
                study.common.write_json(output/(e['phase']+'_technical_readout.json'),dict(ap_m0=desc,energy=energy,
                    directions=study.model.directions(case,values,p.read(study.CONTRACT)['direction_windows_s']),
                    new_model_validation=False,new_fit=0))
                item.update(status='eligible_partial_study_descriptive',energy_120s_j=energy['windows']['common']['observed_j'],
                    predicted_diagnostic_j=energy['frozen_diagnostic_120s_j'],signed_energy_error_j=energy['signed_diagnostic_error_j'],
                    ap_start_c=case['common_start_ap_c'],ap_first_s=desc['first_s'],ap_last_s=desc['last_s'],
                    ap_samples=desc['samples'],ap_mae_c=desc['scores']['mae_c'],ap_max_error_c=desc['scores']['max_absolute_error_c'],
                    ap_peak_signed_error_c=desc['scores']['peak_signed_error_c'])
                for t,y,v in zip(case['inputs']['query_s'],case['observed_ap_c'],values):
                    ap_paths.append(dict(role=e['phase'],common_s=t,observed_c=y,m0_c=v,residual_c=v-y))
            session_rows.append(item)
        summary['blocks'].append(block)
    safe_csv(output/'sessions.csv',session_rows,['phase','status'])
    safe_csv(output/'ap_paths.csv',ap_paths,['role','common_s','observed_c','m0_c','residual_c'])
    if (root/'development_selection.json').exists():
        selection=p.read(root/'development_selection.json')
        summary['development_selection']={k:selection.get(k) for k in ('status','reason','selected_name')}
    if (root/'model_freeze.json').exists():summary['model_freeze_sha256']=p.digest(root/'model_freeze.json')
    summary['session_denominator']=len(session_rows)
    study.common.write_json(output/'summary.json',summary)
    # Original raw evidence is never changed; inventory is external, not published wholesale.
    inventory=[dict(path=f.relative_to(root).as_posix(),bytes=f.stat().st_size,sha256=p.digest(f))
               for f in sorted(root.rglob('*')) if f.is_file()]
    study.common.write_json(output/'inventory.json',dict(files=inventory,total_bytes=sum(r['bytes'] for r in inventory)))
    return summary


def main():
    q=argparse.ArgumentParser(description=__doc__);q.add_argument('--plan',required=True);q.add_argument('--output',required=True)
    a=q.parse_args();summary=analyse(a.plan,a.output)
    print(json.dumps(dict(status=summary['status'],elapsed_s=summary['elapsed_s'],model_frozen=summary['model_frozen'],device_commands=0),indent=2))


if __name__=='__main__':main()
