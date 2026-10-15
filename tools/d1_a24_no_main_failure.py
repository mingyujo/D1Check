"""Closed continuation evidence for an ambiguous APP delivery with no MAIN.

Never relabel the host failure, refund its budget, replay APP, or fabricate a
journal. Two read-only observations and absence of start approval are required.
"""
import json
from pathlib import Path
from d1_a24_laptop_validator import load_json, sha256, PROTOCOL
from d1_a24_revision02_suite import require
from d1_a24_failed_prestart_evidence import verify_failed_prestart


def verify_failed_without_main(root,plan,row,recovered,*,plan_sha256):
    outcome=load_json(root/(row['session_id']+'.outcome.json'))
    if outcome['status']=='PRESTART_REJECT':
        return verify_failed_prestart(root,plan,row,recovered,plan_sha256=plan_sha256)
    sid=row['session_id'];reg=root/'registry'/PROTOCOL/plan['plan_id']/sid
    require(outcome['status']=='FAILED_PRESERVED' and outcome.get('APP_launch_intent') is True
        and outcome.get('reason')=='connection recovered after ambiguous mutation; never replay install/push/start/claim',
        'only the exact ambiguous-delivery failure is covered')
    require(not any((reg/n).exists() for n in ['START.json','CLAIM.json','COMPLETE.json']), 'MAIN/claim already exists')
    reject=load_json(reg/'PRESTART_REJECT.json')
    require(reject['START'] is False and reject['session_run_consumed'] is False,'not a no-MAIN failure')
    stop=load_json(root/'WINDOW_STOPPED.json')
    require(any(x['session_id']==sid and x==outcome for x in stop['outcomes']), 'actual host visit not closed with this failure')
    evidence=load_json(recovered/'NO_MAIN_READONLY_OBSERVATIONS.json')
    require(evidence['session_id']==sid and evidence['plan_sha256']==plan_sha256
        and evidence['outcome_sha256']==sha256(root/(sid+'.outcome.json')),'foreign no-MAIN evidence')
    reads=evidence['observations']
    require(len(reads)==2 and reads[1]['host_after_ns']-reads[0]['host_before_ns']>=5_000_000_000,
        'two separated post-reconnect observations required')
    for read in reads:
        require(read['registered_identity_match'] is True and read['all_app_processes_absent'] is True
            and read['remote_output_directory_absent'] is True and read['remote_start_approval_absent'] is True,
            'existing process/output/approval or different phone; cannot continue')
    # Approval upload is a host mutation. Check the original exact command log,
    # not only an inferred absence of completed requests.
    for p in [root/'adb_commands.jsonl',root/'measurement_adb_commands.jsonl']:
        if not p.exists():continue
        for line in p.read_bytes().splitlines():
            argv=json.loads(line).get('argv',[])
            require(not ('push' in argv and any(sid in str(x) and 'start_approval' in str(x) for x in argv)),
                'start approval upload exists; no-MAIN proof invalid')
    files={'NO_MAIN_READONLY_OBSERVATIONS.json':sha256(recovered/'NO_MAIN_READONLY_OBSERVATIONS.json')}
    return {'status':'PROVED_NO_MAIN_APPROVAL_AND_NO_APP_EVIDENCE_AFTER_AMBIGUOUS_DELIVERY',
        'session_id':sid,'APP_budget_consumed':1,'MAIN_START':False,'MAIN_completed':0,
        'planned_unfinished':row['request_count'],'normal_comparison_eligible':False,
        'automatic_retry':False,'budget_refund':False,'actual_warmup_calls':None,
        'recovered_files_sha256':files,'outcome_sha256':sha256(root/(sid+'.outcome.json')),
        'PRESTART_REJECT_sha256':sha256(reg/'PRESTART_REJECT.json')}
