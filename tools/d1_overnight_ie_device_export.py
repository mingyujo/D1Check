"""Correct fixed-plan time-origin ABI; no new simulator/device invocation.

The registered96 PC trace always starts at35s on common0. The first export
mistakenly subtracted35s for an issue-relative payload. Preserve it and issue
a distinct common0 payload before any physical replay. KPI/raw remain exact.
"""
import gzip,json
from datetime import datetime,timezone
from tools import d1_overnight_ie_run as d

def run():
    out=d.LOCAL/'device_common0';out.mkdir(exist_ok=False)
    reg=d.read(d.LOCAL/'registration.json');sources=reg['source_sha256']
    receipt=dict(task='OVERNIGHT-IE-DEVICE-EXPORT-COMMON0',utc=datetime.now(timezone.utc).isoformat(),original_trace='35s+i*350ms from common0, not new trace',original_issue_relative_exports_preserved=True,native_additional_starts=0,device_commands=0,model_fit_calls=0,source_sha256=d.sha(d.ROOT/'tools/d1_overnight_ie_device_export.py'),payloads={})
    for role in d.ROLES:
        rawpath=d.LOCAL/'items'/('representative_'+role+'.json.gz');raw=json.loads(gzip.decompress(rawpath.read_bytes()));requests=[]
        for q in sorted(raw['result']['ledger'],key=lambda q:q['ordinal']):
            assert q['arrival_ns']==35_000_000_000+q['ordinal']*350_000_000 and q['status']=='succeeded'
            requests.append(dict(ordinal=q['ordinal'],source_request_id=q['id'],task_id=q['task'],priority=q['priority'],offset_ms=q['arrival_ns']/1e6,deadline_ms=q['deadline_offset_ns']/1e6,release_offset_ns=q['dispatch_ns'],recorded_backend=q['backend'],
                pc_dispatch_ns=q['dispatch_ns'],pc_execution_start_ns=q['execution_start_ns'],pc_output_ready_ns=q['output_ready_ns'],pc_persist_complete_ns=q['persist_complete_ns'],pc_worker_release_ns=q['worker_release_ns'],pc_lane_available_ns=q['lane_available_ns'],pc_response_duration_ns=q['response_ns'],pc_late=q['late_success']))
        plan=dict(version='frozen-plan-v2',payload_time_origin='common_session_zero',policy_id=d.IDS[role],model_sha256=d.x.r.h.UPSTREAM_SHA,trace_seed=None,source_sha256=sources,requests=requests,online_mobile_policy=False,
            raw_sha256=d.sha(rawpath),pc_metrics=raw['row'],pc_ap_curve=raw['curve'],original_issue_relative_payload_sha256=d.sha(d.LOCAL/f'device_plan_{role}.json'),meaning='same original no-future online PC ledger; 35s idle included; frozen physical replay only')
        path=out/(f'device_plan_{role}.json');d.write(path,plan);receipt['payloads'][role]=dict(sha256=d.sha(path),raw_sha256=d.sha(rawpath),first_offset_ms=35000,first_dispatch_ns=requests[0]['release_offset_ns'])
    d.write(out/'contract.json',receipt);d.write(d.PUBLIC/'device_export_common0_contract.json',receipt);return receipt

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False),flush=True)
