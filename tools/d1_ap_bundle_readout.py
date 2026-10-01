"""PC readout for a fixed two-history AP confirmation bundle, including failure."""
from __future__ import annotations
import argparse
import bisect
import csv
import html
import json
from pathlib import Path
from tools import d1_ap_bundle_confirmation as bundle
from tools import d1_ap_transfer_confirmation as transfer
from tools import d1_ap_transfer_report as graphics
from tools import d1_arrival_energy_analysis as descriptive


def direction(points,start,end,max_gap=10.):
    """Fixed endpoints only. No extrapolation, endpoint shift or missing-as-zero."""
    times=[r['elapsed_s'] for r in points]
    def at(t):
        i=bisect.bisect_left(times,t)
        if i<len(times) and abs(times[i]-t)<1e-9:return points[i]
        if i==0 or i==len(times) or times[i]-times[i-1]>max_gap:return None
        a,b=points[i-1],points[i];f=(t-times[i-1])/(times[i]-times[i-1])
        return {k:a[k]+f*(b[k]-a[k]) for k in ('observed_ap_c','frozen_ap_c','candidate_ap_c')}
    a,b=at(start),at(end)
    if a is None or b is None:return dict(start_s=start,end_s=end,status='missing_bracket',observed_change_c=None)
    return dict(start_s=start,end_s=end,status='observed',**{
        k+'_change_c':b[k+'_ap_c']-a[k+'_ap_c'] for k in ('observed','frozen','candidate')})


def consumption(plan):
    root=Path(plan['output_root']);counts=[]
    for e in plan['entries']:
        folder=root/f"{e['index']:02d}_{e['session_id']}"
        available=next((folder/x for x in ('artifacts/progress.jsonl','failure_prefix/progress.jsonl')
                        if (folder/x).is_file()),None)
        events=descriptive.read_lines(available) if available else []
        kinds=('runtime_start','runtime_return','warmup_start','warmup_return',
               'request_start','request_return','output_ready','persist_complete','worker_release','lane_available')
        counts.append(dict(role=e['phase'],planned_requests=24,
            launch_attempted=(folder/'launch_attempt.json').exists(),
            counts={k:sum(x.get('kind')==k for x in events) for k in kinds},
            progress_recovered=available is not None,
            app_cleanup=transfer.p.read(folder/'artifacts/cleanup.json') if (folder/'artifacts/cleanup.json').exists() else None,
            host_cleanup=transfer.p.read(folder/'host_cleanup.json') if (folder/'host_cleanup.json').exists() else
                transfer.p.read(folder/'failure_host_cleanup.json') if (folder/'failure_host_cleanup.json').exists() else None,
            missing_calls='unknown within per-session hard cap when launched without complete evidence; unlaunched session not attempted'))
    return counts


def report(plan_file,output):
    plan_file,output=Path(plan_file),Path(output);plan=transfer.p.read(plan_file)
    root=Path(plan['output_root']).resolve()
    for protected in (root,Path(plan['registry']).resolve(),plan_file.parent.resolve()):
        if output.resolve()==protected or protected in output.resolve().parents:raise ValueError('protected output')
    if output.exists():raise FileExistsError(output)
    transfer.old.require(plan['experiment_id']==bundle.EXPERIMENT and plan['source_code']==bundle.identity(),
                         'frozen source changed')
    transfer.old.require(transfer.p.digest(plan['candidate_freeze']['path'])==transfer.FREEZE_SHA,
                         'candidate changed')
    output.mkdir(parents=True)
    receipt=transfer.p.read(root/'FINAL_RECEIPT.json')
    inventory=[dict(path=f.relative_to(root).as_posix(),bytes=f.stat().st_size,sha256=transfer.p.digest(f))
               for f in sorted(root.rglob('*')) if f.is_file()]
    transfer.cal.write_new(output/'inventory.json',dict(files=inventory,total_bytes=sum(x['bytes'] for x in inventory)))
    sessions=[]
    for e in plan['entries']:
        folder=root/f"{e['index']:02d}_{e['session_id']}"
        item=dict(role=e['phase'],status='unattempted_or_ineligible',scores=None)
        if (folder/'validated.json').exists():
            try:
                data=output/e['phase'];s=transfer.readout_session(plan_file,plan,e,data)
                graphics.complete_energy_endpoint(data,s)
                energy,ap,_,states=graphics.validate_tables(data,s)
                contract=transfer.p.read(plan['analysis_contract']['path'])
                ap_float=[{k:float(v) if k!='phase' else v for k,v in r.items()} for r in ap]
                directions=[direction(ap_float,*window) for window in contract['fixed_direction_windows_s']]
                item.update(status='evaluated_conditional_transfer',scores=s,directions=directions,
                            independent_sessions=1,accuracy_pass=None,policy_selection_pass=None)
                # AP/energy only: shifted release timing is registered input, not a new PC realized lane forecast.
                graphics.figures(data,[],energy,ap,states,'prospective bundled AP confirmation')
            except (ValueError,OSError,KeyError,TypeError) as error:
                item.update(status='analysis_ineligible',error=repr(error))
        sessions.append(item)
    summary=dict(experiment_id=bundle.EXPERIMENT,receipt=receipt,sessions=sessions,
        consumption=consumption(plan),candidate_freeze_sha256=transfer.FREEZE_SHA,
        original_freeze_sha256=transfer.replay.FROZEN_SHA,
        data_role='prospective fixed-procedure protocol transfer; two histories, one session per history',
        post_load_refit=False,strict_support=False,experiment_ready=False,
        accuracy_pass=None,policy_rank=None,device_commands_by_analysis=0)
    transfer.cal.write_new(output/'summary.json',summary)
    body='<h1>AP 일괄 확인 · 두 부하 이력</h1><p>기존 후보 고정 · 부하 전 AP＋실제 일정 조건부 전이 확인. 계수 재적합·정책 PASS 없음. J는 raw=mA 조건부이며 절대 정확도 미인증.</p>'
    for item in sessions:
        body+='<h2>'+html.escape(item['role'])+'</h2><p>'+html.escape(item['status'])+'</p>'
        if item['scores']:
            s=item['scores'];body+='<pre>'+html.escape(json.dumps({k:s[k] for k in ('initial_ap_c','actual_parallel_seconds','observed_energy_120s_j','signed_energy_error_j','ap_scores')},ensure_ascii=False,indent=2))+'</pre>'
            body+=f'<img style="max-width:100%" src="{item["role"]}/ap.svg"><img style="max-width:100%" src="{item["role"]}/energy.svg">'
            body+='<pre>'+html.escape(json.dumps(item['directions'],indent=2))+'</pre>'
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>AP bundle</title>'+body,encoding='utf-8')
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();result=report(a.plan,a.output)
    print(json.dumps(dict(status=result['receipt']['status'],sessions=result['sessions']),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
