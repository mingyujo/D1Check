"""Prove a closed FAILED host attempt stopped before MAIN at config-open denial.

Never relabel its outcome, refund APP budget, replay the session, or fabricate
closure. This narrow proof permits later, unused sessions after app self-close.
"""
import json
from pathlib import Path
from d1_a24_laptop_validator import load_json,sha256,PROTOCOL
from d1_a24_revision02_suite import require

CAUSE='ADB command failed/timeout; preserve raw and never restart session: shell perfetto --txt'


def verify_closed_trace_failure(root,plan,row,recovered,*,plan_sha256):
    sid=row['session_id'];reg=root/'registry'/PROTOCOL/plan['plan_id']/sid
    outcome=load_json(root/(sid+'.outcome.json'))
    require(outcome.get('status')=='FAILED_PRESERVED' and outcome.get('reason')==CAUSE
        and outcome.get('APP_launch_intent') is True and row['perfetto']=='ON','not the exact pre-MAIN trace failure')
    require(any(x==outcome for x in load_json(root/'WINDOW_STOPPED.json')['outcomes']),
        'host visit did not close with this exact failed outcome')
    require(not any((reg/n).exists() for n in ['START.json','CLAIM.json','COMPLETE.json']),'MAIN/claim already exists')
    reject=load_json(reg/'PRESTART_REJECT.json')
    require(reject.get('START') is False and reject.get('session_run_consumed') is False and reject.get('reason')==CAUSE,
        'no exact pre-MAIN host rejection')
    failures=[]
    for line in (root/'adb_commands.jsonl').read_bytes().splitlines():
        x=json.loads(line);args=x.get('argv',[])
        require(not ('push' in args and any(sid in str(a) and 'start_approval' in str(a) for a in args)),
            'approval upload exists; cannot prove no MAIN')
        if '--detach=a24_'+sid.replace('-','') in args:
            require('perfetto' in args and '--txt' in args and x.get('exit')==1
                and 'Could not open ' in x.get('stderr','') and 'Permission denied' in x.get('stderr','')
                and '/data/local/tmp/a24-'+sid+'-perfetto.pbtxt' in x.get('stderr',''),
                'trace may have started; unsupported failure')
            failures.append(x)
    require(len(failures)==1,'exact one failed trace start required; no replay')
    identity=load_json(recovered/'identity.json');ready=load_json(recovered/'ready.json')
    closed=load_json(recovered/'journal_closed.json');cleanup=load_json(recovered/'cleanup.json');failure=load_json(recovered/'failure.json')
    pid=identity.get('process_id')
    require(identity.get('session_id')==sid and ready.get('session_id')==sid and ready.get('plan_sha256')==plan_sha256,
        'prepared identity differs')
    require(type(pid) is int and pid>0 and closed.get('session_id')==sid and closed.get('process_id')==pid
        and closed.get('status')=='SYNCED_AND_CLOSED','actual journal closure absent')
    require(cleanup.get('status')=='DRAINED' and cleanup.get('actual_return_confirmed') is True
        and cleanup.get('error') is None and bool(cleanup.get('session_failure')) and failure.get('status')=='FAILED',
        'failed app not safely drained')
    events=[json.loads(s) for s in (recovered/'events.jsonl').read_bytes().splitlines()]
    forbidden={'common_start','arrival','queue_entry','dispatch','worker_start','execution_start','output_ready',
        'request_complete','response_complete','wait_start','worker_release','lane_available'}
    require(events and not any(e.get('kind') in forbidden for e in events),'MAIN activity in failure evidence')
    requests=load_json(recovered/'requests.json')
    require(len(requests)==row['request_count'] and all(r.get('terminal_status')=='UNFINISHED' for r in requests),
        'planned unfinished requests lost or completed')
    names=['identity.json','ready.json','journal_closed.json','cleanup.json','failure.json','events.jsonl','requests.json']
    return {'status':'PROVED_CLOSED_FAILED_TRACE_CONFIG_BEFORE_MAIN','session_id':sid,'process_id':pid,
        'APP_budget_consumed':1,'MAIN_START':False,'MAIN_completed':0,'planned_unfinished':row['request_count'],
        'old_host_failure_status_preserved':True,'normal_comparison_eligible':False,'automatic_replay':False,'budget_refund':False,
        'recovered_files_sha256':{n:sha256(recovered/n) for n in names},
        'outcome_sha256':sha256(root/(sid+'.outcome.json')),'PRESTART_REJECT_sha256':sha256(reg/'PRESTART_REJECT.json')}
