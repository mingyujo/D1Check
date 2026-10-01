"""PC readout for a fixed two-history AP confirmation bundle, including failure."""
from __future__ import annotations
import argparse
import bisect
import html
import json
import traceback
from pathlib import Path
from tools import d1_ap_bundle_confirmation as bundle
from tools import d1_ap_transfer_confirmation as transfer
from tools import d1_ap_transfer_report as graphics


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


def progress_prefix(file):
    """Count only an intact JSONL prefix; never repair the source or skip a bad row."""
    events=[]
    try:
        with file.open('rb') as stream:
            for number,line in enumerate(stream,1):
                if not line.endswith(b'\n'):
                    return events,dict(status='partial_prefix',line=number,error='incomplete final record')
                try:
                    row=json.loads(line.decode('utf-8'))
                    if not isinstance(row,dict):raise ValueError('progress row is not an object')
                except (UnicodeError,ValueError) as error:
                    return events,dict(status='partial_prefix',line=number,error=repr(error))
                events.append(row)
    except OSError as error:
        return events,dict(status='unreadable',error=repr(error))
    return events,dict(status='parsed',records=len(events),
                       completeness='parsing success alone does not prove terminal completion')


def cleanup_evidence(file):
    if not file.exists():return None
    try:return transfer.p.read(file)
    except (OSError,ValueError) as error:return dict(status='unreadable',error=repr(error))


def consumption(plan):
    root=Path(plan['output_root']);counts=[]
    receipt=transfer.p.read(root/'FINAL_RECEIPT.json')
    for e in plan['entries']:
        folder=root/f"{e['index']:02d}_{e['session_id']}"
        available=next((folder/x for x in ('artifacts/progress.jsonl','failure_prefix/progress.jsonl')
                        if (folder/x).is_file()),None)
        events,integrity=progress_prefix(available) if available else ([],dict(status='not_recovered'))
        kinds=('runtime_start','runtime_return','warmup_start','warmup_return',
               'request_start','request_return','host_inference_start','host_inference_return',
               'output_ready','persist_complete','worker_release','lane_available')
        # Missing files alone never establish zero calls. Require the host attempt receipt.
        attempts=receipt.get('session_attempts')
        not_attempted=(not folder.exists() and isinstance(attempts,int) and e['index']>=attempts)
        event_counts={k:sum(x.get('kind')==k for x in events) if available else
                0 if not_attempted else None for k in kinds}
        counts.append(dict(role=e['phase'],planned_requests=24,
            launch_attempted=(folder/'launch_attempt.json').exists(),
            counts=event_counts,progress_integrity=integrity,confirmed_not_attempted=not_attempted,
            return_event_kind='host_inference_return; request_return is a separate legacy record kind',
            confirmed_request_returns=event_counts['host_inference_return'],
            count_meaning='observed event counts, lower bounds if partial; not absence-of-execution claims',
            progress_recovered=available is not None,
            app_cleanup=cleanup_evidence(folder/'artifacts/cleanup.json'),
            host_cleanup=cleanup_evidence(folder/'host_cleanup.json') if (folder/'host_cleanup.json').exists() else
                cleanup_evidence(folder/'failure_host_cleanup.json'),
            missing_calls='unknown within per-session hard cap without complete evidence; zero only with host attempt receipt'))
    return counts


def report(plan_file,output,*,evidence_label='prospective bundled AP confirmation'):
    plan_file,output=Path(plan_file),Path(output);plan=transfer.p.read(plan_file)
    root=Path(plan['output_root']).resolve()
    for protected in (root,Path(plan['registry']).resolve(),plan_file.parent.resolve()):
        if output.resolve()==protected or protected in output.resolve().parents:raise ValueError('protected output')
    if output.exists():raise FileExistsError(output)
    transfer.old.require(plan['experiment_id']==bundle.run_names(plan.get('bundle_edition',1))[0] and
                         plan['source_code']==bundle.identity(),
                         'frozen source changed')
    transfer.old.require(transfer.p.digest(plan['candidate_freeze']['path'])==transfer.FREEZE_SHA,
                         'candidate changed')
    transfer.old.require(transfer.p.digest(plan['frozen_model']['path'])==transfer.replay.FROZEN_SHA,
                         'original freeze changed')
    transfer.old.require(transfer.p.digest(plan['analysis_contract']['path'])==plan['analysis_contract']['sha256'],
                         'analysis contract changed')
    fixture=evidence_label.startswith('PC fixture')
    output.mkdir(parents=True)
    receipt=transfer.p.read(root/'FINAL_RECEIPT.json')
    inventory=[dict(path=f.relative_to(root).as_posix(),bytes=f.stat().st_size,sha256=transfer.p.digest(f))
               for f in sorted(root.rglob('*')) if f.is_file()]
    transfer.cal.write_new(output/'inventory.json',dict(files=inventory,total_bytes=sum(x['bytes'] for x in inventory)))
    sessions=[]
    for e in plan['entries']:
        folder=root/f"{e['index']:02d}_{e['session_id']}"
        attempts=receipt.get('session_attempts')
        not_attempted=not folder.exists() and isinstance(attempts,int) and e['index']>=attempts
        item=dict(role=e['phase'],status='unattempted' if not_attempted else 'incomplete_or_ineligible',
                  scores=None,rendering_status='not_attempted')
        if (folder/'validated.json').exists():
            try:
                data=output/e['phase'];s=transfer.readout_session(plan_file,plan,e,data)
                graphics.complete_energy_endpoint(data,s)
                energy,ap,_,states=graphics.validate_tables(data,s)
                contract=transfer.p.read(plan['analysis_contract']['path'])
                ap_float=[{k:float(v) if k!='phase' else v for k,v in r.items()} for r in ap]
                directions=[direction(ap_float,*window) for window in contract['fixed_direction_windows_s']]
                if fixture:
                    s.update(status='pc_fixture_replay_not_new_confirmation',independent_sessions=0)
                    graphics.save(data/'summary.json',s)
                item.update(status='evaluated_pc_replay' if fixture else 'evaluated_conditional_transfer',
                            scores=s,directions=directions,independent_sessions=0 if fixture else 1,
                            accuracy_pass=None,policy_selection_pass=None)
            except (ValueError,OSError,KeyError,TypeError) as error:
                item.update(status='analysis_ineligible',error=repr(error),original_stack=traceback.format_exc())
            except Exception as error:
                item.update(status='analysis_processing_failed',error=repr(error),original_stack=traceback.format_exc())
            if item['scores'] is not None:
                try:
                    # Shifted releases are registered input, not a new realized lane forecast.
                    graphics.figures(data,[],energy,ap,states,evidence_label)
                    item['rendering_status']='completed'
                except Exception as error:
                    item.update(rendering_status='failed',rendering_error=repr(error),
                                rendering_stack=traceback.format_exc())
                    try:(data/'rendering_error.txt').write_text(item['rendering_stack'],encoding='utf-8')
                    except OSError as recording_error:item['rendering_evidence_error']=repr(recording_error)
        sessions.append(item)
    evaluated=sum(x['scores'] is not None for x in sessions)
    summary=dict(experiment_id=plan['experiment_id'],receipt=receipt,sessions=sessions,
        consumption=consumption(plan),candidate_freeze_sha256=transfer.FREEZE_SHA,
        original_freeze_sha256=transfer.replay.FROZEN_SHA,
        readout_status='complete' if evaluated==len(sessions) else 'partial' if evaluated else 'not_evaluable',
        evaluated_sessions=evaluated,expected_sessions=len(sessions),evidence_label=evidence_label,
        data_role='PC replay of existing data; no new independent confirmation' if fixture else
            'prospective fixed-procedure protocol transfer; two histories, one session per history',
        post_load_refit=False,strict_support=False,experiment_ready=False,
        accuracy_pass=None,policy_rank=None,device_commands_by_analysis=0)
    transfer.cal.write_new(output/'summary.json',summary)
    body='<h1>AP 일괄 확인 · 두 부하 이력</h1><p>'+html.escape(evidence_label)+'</p>'
    body+='<p>기존 후보 고정 · 부하 전 AP＋실제 일정 조건부 계산. 계수 재적합·정책 PASS 없음. J는 raw=mA 조건부이며 절대 정확도 미인증.</p>'
    body+='<p>원 실행: '+html.escape(receipt['status'])+f' · 판독 가능 {evaluated}/{len(sessions)}. 판독 완료와 원 실행 완료는 별도입니다.</p>'
    for item in sessions:
        body+='<h2>'+html.escape(item['role'])+'</h2><p>'+html.escape(item['status'])+'</p>'
        if item['scores']:
            s=item['scores'];body+='<pre>'+html.escape(json.dumps({k:s[k] for k in ('initial_ap_c','actual_parallel_seconds','observed_energy_120s_j','signed_energy_error_j','ap_scores')},ensure_ascii=False,indent=2))+'</pre>'
            if item['rendering_status']=='completed':
                body+=f'<img style="max-width:100%" src="{item["role"]}/ap.svg"><img style="max-width:100%" src="{item["role"]}/energy.svg">'
            else:body+='<p>그림 저장 실패: 점수와 원본은 보존됐습니다.</p>'
            body+='<pre>'+html.escape(json.dumps(item['directions'],indent=2))+'</pre>'
        elif item.get('error'):body+='<pre>'+html.escape(item['error'])+'</pre>'
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>AP bundle</title>'+body,encoding='utf-8')
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--output',required=True)
    p.add_argument('--evidence-label',default='prospective bundled AP confirmation')
    a=p.parse_args();result=report(a.plan,a.output,evidence_label=a.evidence_label)
    print(json.dumps(dict(status=result['receipt']['status'],sessions=result['sessions']),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
