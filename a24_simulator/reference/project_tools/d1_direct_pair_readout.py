"""Preserve direct-pair eligibility and whole-arrival denominators, never rank.

No statistical threshold, physical-model fitting, simulator or device action.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import subprocess
from tools import d1_joint_evidence_requirements as evidence

P=evidence.P
ROOT=evidence.ROOT
HISTORICAL_SHA={
    'summary.json':'0c435344bef03be815172a8b86d9e050fd68c63949d6056587e79a1af79ae29f',
    'timing.csv':'91bee575b629d8b16a082d4bb9df78925885fa8707232af6ddb7fd04c14b4e7d'}


def input_signature(requests):
    required={'ordinal','offset_ms','deadline_ms','priority','task_id'}
    rows=[];ids=set()
    for q in requests:
        if set(q) != required|{'request_id'}:raise ValueError('exact request-input fields required')
        if q['request_id'] in ids:raise ValueError('duplicate planned request id')
        ids.add(q['request_id'])
        if not all(math.isfinite(q[k]) for k in ('ordinal','offset_ms','deadline_ms')) or q['deadline_ms']<=0:
            raise ValueError('finite independent arrival/deadline required')
        rows.append({k:q[k] for k in sorted(required)})
    if {q['ordinal'] for q in rows} != set(range(len(rows))):raise ValueError('whole planned ordinal denominator required')
    rows.sort(key=lambda q:q['ordinal'])
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def pair(candidate, reference):
    reasons=[]
    if candidate['planned'] != reference['planned']:reasons.append('planned_count_mismatch')
    for item in (candidate,reference):
        if type(item['ap_complete'])!=bool:raise ValueError('explicit AP completeness boolean required')
        if not item['input_signature'] or not item['protocol_signature']:reasons.append('input_or_protocol_identity_missing')
    if candidate['input_signature'] != reference['input_signature']:reasons.append('request_input_mismatch')
    if candidate['protocol_signature'] != reference['protocol_signature']:reasons.append('protocol_mismatch')
    valid_counts=True
    for item in (candidate,reference):
        counts=item['outcomes']
        if set(counts)!={'completed','failed','incomplete','unknown'} or any(type(v)!=int or v<0 for v in counts.values()):
            raise ValueError('explicit disjoint nonnegative terminal/unknown counts required')
        if type(item['planned'])!=int or item['planned']<=0 or sum(counts.values())!=item['planned']:raise ValueError('all planned arrivals must remain in denominator')
        if type(item['deadline_met'])!=int or not 0<=item['deadline_met']<=counts['completed']:raise ValueError('deadline count must be within actual completed denominator')
        if counts['completed']!=item['planned'] or item['deadline_met']!=item['planned']:valid_counts=False
    if not valid_counts:reasons.append('whole_work_or_deadline_not_met')
    common_ok=not reasons
    energy_ok=common_ok and candidate['energy_window_s']==reference['energy_window_s']==[0.,120.]
    if not energy_ok:reasons.append('whole_common_energy_pair_unavailable')
    values=(candidate['energy_j'],reference['energy_j'])
    if any(v is None or not math.isfinite(v) for v in values):
        energy_ok=False;reasons.append('energy_missing_or_nonfinite')
    ap_ok=common_ok and candidate['ap_window_s']==reference['ap_window_s']==[35.,180.] and candidate['ap_complete'] and reference['ap_complete']
    ap_values=(candidate['peak_ap_c'],reference['peak_ap_c'])
    if any(v is None or not math.isfinite(v) for v in ap_values):ap_ok=False
    if not ap_ok:reasons.append('AP_common_window_or_complete_observation_unavailable')
    return dict(energy_point_delta_j=candidate['energy_j']-reference['energy_j'] if energy_ok else None,
        AP_point_delta_c=candidate['peak_ap_c']-reference['peak_ap_c'] if ap_ok else None,
        energy_point_comparison_eligible=energy_ok, AP_point_comparison_eligible=ap_ok,
        whole_service_eligible=valid_counts, reasons=sorted(set(reasons)),
        candidate_planned=candidate['planned'],reference_planned=reference['planned'],
        candidate_outcomes=candidate['outcomes'],reference_outcomes=reference['outcomes'],
        initial_conditions_matched=candidate['initial']==reference['initial'],
        inferential_pair_error_bound_j=None, differential_controller_j_separately_added=False,
        independent_prediction_validation=False, policy_winner=None, experiment_ready=False)


def analyze():
    for filename,sha in HISTORICAL_SHA.items():
        if P.digest(P.BUNDLE/filename)!=sha:raise ValueError('frozen historical evidence hash mismatch')
    source=evidence.analyze()
    manifest=json.loads((P.BUNDLE/'initial_inputs.json').read_text(encoding='utf8'))
    if P.digest(P.BUNDLE/'initial_inputs.json')!=P.INITIAL_SHA:raise ValueError('frozen input identity mismatch')
    summary=json.loads((P.BUNDLE/'summary.json').read_text(encoding='utf8'))
    metrics=summary['metrics']
    actual={r['index']:r for r in metrics if r['prediction']=='actual_schedule_conditional'}
    with (P.BUNDLE/'timing.csv').open(encoding='utf8',newline='') as file:timing=list(csv.DictReader(file))
    normalized={}
    for m in manifest:
        row=actual[m['index']];requests=m['manifest_requests'];ledger=[q for q in timing if int(q['index'])==m['index']]
        if len(ledger)!=len(requests) or {q['id'] for q in ledger}!={q['request_id'] for q in requests}:
            raise ValueError('actual timing ledger and whole planned input mismatch')
        if any(not math.isfinite(float(q['actual_response_ms'])) or float(q['actual_response_ms'])<0 for q in ledger):
            raise ValueError('finite nonnegative actual response boundary required')
        met=sum(float(q['actual_response_ms'])<=float(q['deadline_ms']) for q in ledger)
        if met!=row['actual_deadline_met']:raise ValueError('saved whole-arrival deadline count mismatch')
        normalized[m['index']]=dict(input_signature=input_signature(requests),protocol_signature=summary['plan_sha256'],
            planned=row['planned'],outcomes=dict(completed=len(ledger),failed=0,incomplete=0,unknown=0),deadline_met=met,
            energy_window_s=[0.,120.],energy_j=row['observed_120s_j'],
            ap_window_s=[row['ap_window_start_s'],row['ap_window_end_s']],ap_complete=False,
            peak_ap_c=row['observed_peak_ap_c'],initial=dict(AP=row['common_start_ap_c'],preload_w=row['preload_power_w']))
    rows=[]
    for p in range(4):
        members={r['policy']:r for r in actual.values() if r['pair']==p}
        cpu=members['CPU_URGENT_ONLINE_V1'];par=members['B2_PARALLEL_ONLINE_V1']
        result=pair(normalized[par['index']],normalized[cpu['index']])
        result.update(pair=p,input_signature=normalized[par['index']]['input_signature'],
                      scope='existing 192-request measured point comparison; not 48-request certification',
                      protocol_identity='historical shared bundle only; new protocol requires full device/APK/sensor/runtime/resident identity')
        rows.append(result)
    resources={**source['resources'],(P.BUNDLE/'timing.csv').relative_to(P.ROOT).as_posix():P.digest(P.BUNDLE/'timing.csv')}
    return dict(version='direct-pair-readout-v1',rows=rows,resources=resources,
        same_request_semantics_all_pairs=all(r['energy_point_comparison_eligible'] for r in rows),
        independent_pairs=4,new_simulations=0,device_commands=0,model_refits=0,
        initial_conditions_differ=True,policy_winner=None,experiment_ready=False,
        conclusion='whole J points available; complete same-window AP comparison and causal/inferential policy advantage remain unestablished')


def save(result,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    P.write(out/'result.json',result)
    P.write(out/'analysis_manifest.json',dict(utc_after_analysis=datetime.now(timezone.utc).isoformat(),base_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_dirty=True,source_sha256=P.digest(__file__),resources=result['resources'],retrospective_readout=True))
    (out/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
    evidence.sensitivity.source.study.followup.x.old.csv_write(out/'pairs.csv',result['rows'])
    fields=('pair','energy_point_delta_j','AP_point_delta_c','initial_conditions_matched','reasons','policy_winner')
    table='<tr>'+''.join('<th>'+f+'</th>' for f in fields)+'</tr>'
    table+=''.join('<tr>'+''.join('<td>'+html.escape('미판정 / null' if r[f] is None else str(r[f]))+'</td>' for f in fields)+'</tr>' for r in result['rows'])
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>직접 비교의 분모·관측창 검사</title><style>body{font:16px/1.7 system-ui;margin:24px}td,th{border:1px solid #aaa;padding:8px}table{border-collapse:collapse}.scroll{overflow:auto}</style><h1>기존 네 쌍의 입력·분모·관측창 판독</h1><p>세션별 요청ID는 달라도 예정도착·작업·우선순위·기한의 의미는 같습니다. 실제1536요청 기록과 전체기한을 확인했습니다. 전체120초J의 관측 차이는 보존하지만, 초기조건이 다르고 완전한 같은창AP관측·추론오차근거가 없어 정책순위는null입니다. 미완료/실패/미확인은 분모에서 제거하지 않으며 없는AP를0으로 채우지 않습니다.</p><div class="scroll"><table>'+table+'</table></div><p><a href="pairs.csv">전체 네 쌍</a> · <a href="result.json">조건·원해시·null</a> · <a href="../README.md">재현·검증·해석</a></p>',encoding='utf8')
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    save(analyze(),parser.parse_args().output)
