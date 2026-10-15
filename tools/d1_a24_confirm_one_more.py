"""One explicitly requested untouched CONFIRM, after a pre-APP time refusal.

This PC coordinator adds history validation only. It delegates device execution
to the unchanged C3 coordinator and frozen core179. No APP delivery is replayed.
"""
import argparse
import json
from pathlib import Path
import d1_a24_confirm_after_diagnostic as parent
from d1_a24_laptop_validator import load_json, sha256, PROTOCOL
from d1_a24_revision02_suite import require

ORIGINAL_INSPECT=parent.inspect


def check_history(job,binding,ledger):
    plan=load_json(Path(job['plan']))
    for item in binding['previous_visits']:
        root=Path(item['root'])
        require(sha256(root/'WINDOW_STOPPED.json')==item['stop_sha256'],'previous stop changed')
    for global_root in binding['previous_global_reservation_roots']:
        require(not (Path(global_root)/'ACTIVE_OWNER.json').exists(),'previous owner still active')
    for record in ledger['records']:
        sid=record['session_id'];raw_hits=[]
        for item in binding['previous_visits']:
            root=Path(item['root']);raw=root/'raw'/sid
            if (raw/'events.jsonl').exists():
                raw_hits.append(raw)
                require(record['APP_launches']==1,'unlaunched ID has raw evidence')
                require(sha256(raw/'events.jsonl')==record['events_sha256'] and
                        sha256(raw/'journal_closed.json')==record['closed_sha256'],'prior raw changed')
                continue
            registry=root/'registry'/PROTOCOL/plan['plan_id']/sid
            artifacts=[root/'bindings'/sid,root/(sid+'.outcome.json'),registry,raw]
            if not any(p.exists() for p in artifacts):continue
            key=root.name+'/'+sid
            proof=binding['preserved_preAPP_artifacts'].get(key)
            require(proof is not None,'unproved prior artifact')
            if raw.exists():
                require({p.name for p in raw.iterdir()}=={'host_hal_partial.jsonl'} and
                        (raw/'host_hal_partial.jsonl').stat().st_size==0,'preAPP raw contains samples')
            if registry.exists():
                require({p.name for p in registry.iterdir()}=={'host_hal_partial.jsonl','PRESTART_REJECT.json'},'preAPP registry has execution evidence')
                rejection=load_json(registry/'PRESTART_REJECT.json')
                require(rejection['START'] is False and rejection['session_run_consumed'] is False,'registry refusal consumed the run')
                require((registry/'host_hal_partial.jsonl').stat().st_size==0,'preAPP registry contains samples')
            actual={str(p.relative_to(root)).replace('\\','/'):sha256(p)
                    for entry in artifacts if entry.exists() for p in ([entry] if entry.is_file() else entry.rglob('*')) if p.is_file()}
            require(actual==proof['files'],'preserved preAPP bytes changed')
            outcome=root/(sid+'.outcome.json')
            if outcome.exists():
                x=load_json(outcome)
                require(x['APP_launch_intent'] is False,'prior outcome contains APP intent')
                if x['reason']!='bounded window does not admit APP_CREATE':
                    require(x['reason']=='ADB command failed/timeout; preserve raw and never restart session: shell run-as com.example.d1check.benchmarkrunner.a24measurement','unexpected preAPP failure')
                    commands=[json.loads(line) for line in (root/'adb_commands.jsonl').read_text(encoding='utf-8').splitlines()]
                    require(not any('am' in c['argv'] and 'start' in c['argv'] and sid in c['argv'] for c in commands),'APP delivery was attempted')
                    require(any(c['argv'][-4:]==['test','!','-e','files/a24_laptop_inputs/'+sid] and c['exit']==1 for c in commands),'input collision unproved')
                    receipt=load_json(Path(binding['preAPP_input_preservation_receipt']))
                    require(sha256(Path(binding['preAPP_input_preservation_receipt']))==binding['preAPP_input_preservation_sha256'] and
                            receipt['session_id']==sid and receipt['APP']==receipt['START']==receipt['claim']==0 and
                            receipt['device_output_directory_absent'] and receipt['moved_files_byte_identical'],'preAPP preservation is not proven')
                    require(receipt['C4_command_log_sha256']==sha256(root/'adb_commands.jsonl'),'preAPP command log changed')
            for old in binding['previous_global_reservation_roots']:
                if root.name=='A24R02C2' and record['APP_launches']:
                    # This binding was followed by the unique successful C3
                    # execution, whose exact raw was checked above.
                    continue
                require(not (Path(old)/'reservations'/sid/'APP_LAUNCH_INTENT.json').exists(),'preAPP ID already has APP delivery intent')
        require(len(raw_hits)==record['APP_launches'],'missing/duplicate executed ID')


def inspect(job,require_pc=True):
    contract=load_json(Path(job['revision_contract_file']))
    require(contract['one_more_coordinator_sha256']==sha256(Path(__file__)),'one-more coordinator changed')
    parent.check_history=check_history
    rows,*rest=ORIGINAL_INSPECT(job,require_pc=require_pc)
    require(len(rows)==1 and rows[0]['recipe']=='L64' and rows[0]['arm']=='BASE','scope must be exactly next L64 BASE')
    require(rows[0]['plan_ordinal']==16,'not the requested seventeenth condition')
    return rows,*rest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
    job=load_json(a.job)
    if a.execute_authorized:
        parent.inspect=inspect
        parent.execute(job)
    else:
        rows,*_=inspect(job)
        print({'status':'PC_INSPECT_ONLY','conditions':len(rows),'device_commands':0})
