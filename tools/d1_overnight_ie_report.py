"""Read-only raw checks and small offline evidence for the registered IE batch."""
import csv,gzip,html,json,statistics,subprocess
from collections import Counter
from datetime import datetime,timezone
from tools import d1_overnight_ie_run as d

NAMES=dict(Band='Band 전체 요청 대응',Triton='Triton 고정 요청 대응',L0='서비스 우선 리스트',Rule='기존 열·에너지 리스트',R1='관측 전 대기 금지',R2='현재 응답 보존 리스트')

def summary(rows):
    base={q['condition']:q for q in rows if q['policy']=='Band'};out=[]
    for role in d.ROLES:
        rs=[q for q in rows if q['policy']==role];paired=[(q,base[q['condition']]) for q in rs]
        out.append(dict(policy=role,name=NAMES[role],conditions=len(rs),planned=sum(q['planned'] for q in rs),completed=sum(q['completed'] for q in rs),urgent_failure=sum(q['urgent_failure'] for q in rs),normal_failure=sum(q['normal_failure'] for q in rs),mean_urgent_p95_ms=statistics.mean(q['urgent_p95_ms'] for q in rs),mean_normal_ms=statistics.mean(q['normal_mean_ms'] for q in rs),mean_J=statistics.mean(q['energy_j'] for q in rs),mean_AP=statistics.mean(q['peak_ap_c'] for q in rs),mean_delta_J=statistics.mean(q['energy_j']-b['energy_j'] for q,b in paired),mean_delta_AP=statistics.mean(q['peak_ap_c']-b['peak_ap_c'] for q,b in paired),mean_native_seconds=statistics.mean(q['native_seconds'] for q in rs),service_nonworse=sum(q['urgent_failure']<=b['urgent_failure'] and q['normal_failure']<=b['normal_failure'] and q['urgent_p95_ms']<=b['urgent_p95_ms'] for q,b in paired),joint_cost_nonworse=sum(q['energy_j']<=b['energy_j'] and q['peak_ap_c']<=b['peak_ap_c'] for q,b in paired)))
    return out

def schedule_key(raw):
    return [(q['id'],q.get('backend'),q.get('dispatch_ns'),q.get('response_ns'),q.get('lane_available_ns')) for q in sorted(raw['result']['ledger'],key=lambda q:q['ordinal'])]

def svg_timeline(raws):
    height=60+len(raws)*95;out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="{height}" viewBox="0 0 1120 {height}" style="font-family:Malgun Gothic,sans-serif"><rect width="1120" height="{height}" fill="white"/><text x="18" y="26" font-size="18">사전 고정 96요청: 도착 후 CPU/GPU 점유 시간표</text>']
    left=195;scale=850/40
    for j,(role,raw) in enumerate(raws.items()):
        top=55+j*95;out.extend([f'<text x="10" y="{top+23}" font-size="14">{NAMES[role]}</text>',f'<text x="{left-40}" y="{top+18}" font-size="12">CPU</text>',f'<text x="{left-40}" y="{top+45}" font-size="12">GPU</text>'])
        for q in raw['result']['ledger']:
            a=(q['dispatch_ns']-35e9)/1e9;b=(q['lane_available_ns']-35e9)/1e9;y=top+(0 if q['backend']=='CPU' else 28);color='#da8840' if q['task']=='detection' else '#367eb6'
            out.append(f'<rect x="{left+a*scale:.3f}" y="{y}" width="{max(.6,(b-a)*scale):.3f}" height="20" fill="{color}"><title>{html.escape(q["id"])}: {a:.4f}..{b:.4f}s / {q["backend"]}</title></rect>')
        for second in range(0,41,5):out.append(f'<text x="{left+second*scale-5}" y="{top+73}" font-size="11">{second}</text>')
    out.append('<text x="890" y="30" font-size="12">파랑: 분류 / 주황: 탐지 · 시작 후 초</text></svg>');return ''.join(out)

def svg_map(rows,field,title):
    base={q['condition']:q for q in rows if q['policy']=='Band'};roles=('Rule','R1','R2');height=205;out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="{height}" viewBox="0 0 1120 {height}" style="font-family:Malgun Gothic,sans-serif"><rect width="1120" height="{height}" fill="white"/><text x="16" y="26" font-size="18">{title} — 확인 48조건, Band 대비</text><text x="16" y="47" font-size="12">초록: 감소 / 회색: 동일 / 빨강: 증가 · 아래 숫자는 조건 ID</text>']
    left=190;width=18
    for j,role in enumerate(roles):
        y=65+j*33;out.append(f'<text x="10" y="{y+17}" font-size="13">{NAMES[role]}</text>')
        for q in [q for q in rows if q['policy']==role]:
            delta=q[field]-base[q['condition']][field];color='#69b897' if delta<0 else '#d8827a' if delta>0 else '#d8dfe8';x=left+q['condition']*width
            label=f'{q["condition"]} {q["family"]} {q["context"]} Δ={delta:.9g}'
            out.append(f'<rect x="{x}" y="{y}" width="{width-2}" height="24" fill="{color}"><title>{label}</title></rect>')
    for j in range(48):out.append(f'<text x="{left+j*width}" y="175" font-size="8">{j}</text>')
    out.append('</svg>');return ''.join(out)

def run():
    if d.read(d.LOCAL/'WORKING_STATE.json')['phase']!='completed':raise ValueError('only complete batch can be reported')
    d.check();ledger=[]
    for line in (d.LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines():
        v=json.loads(line)
        if v.get('event'):ledger[v['number']-1].update(v)
        else:ledger.append(v)
    assert len(ledger)==442 and all(q['status']=='completed' for q in ledger)
    audited=0;all_requests=0;completed=0;raws={};guard_opportunities=[];behavior={phase:{r:dict(schedule_same_Band=0,cooling_actions=0,total_extra_wait_s=0.,admission_rejections={}) for r in d.ROLES} for phase in ('development','confirmation')}
    for v in ledger:
        path=d.LOCAL/'items'/(v['identity']+'.json.gz');assert d.sha(path)==v['sha256'];raw=json.loads(gzip.decompress(path.read_bytes()));d.prior.previous.audit(raw['result'],v['case']['tickets']);audited+=1;all_requests+=raw['row']['planned'];completed+=raw['row']['completed'];raws[v['identity']]=raw
        if v['phase'] in behavior:
            target=behavior[v['phase']][v['role']];target['cooling_actions']+=raw['cooling_count'];target['total_extra_wait_s']+=raw['total_extra_wait'];counter=Counter(target['admission_rejections']);counter.update(raw['admission_rejections']);target['admission_rejections']=dict(counter)
            if v['role']=='Rule':
                # Diagnostic of an internal action restriction using archived
                # causal projections only; never replay the unseen trace.
                for snapshot in raw['snapshots']:
                    for j,reason in enumerate(snapshot['admissions']):
                        if reason!='urgent_response' or not snapshot['physical_mask'][j]:continue
                        fs=snapshot['forecasts'][j];rs=snapshot['forecasts'][0]
                        fields=('urgent_misses','normal_misses','urgent_p95_ms','remaining_increment_j','global_peak_ap_c')
                        allowed=all(f['valid'] and ref['valid'] and f['lane_end_s']<=120. and all((f[k] or 0)<=(ref[k] or 0) for k in fields) for f,ref in zip(fs,rs))
                        gain=all(f['remaining_increment_j']<ref['remaining_increment_j'] or f['global_peak_ap_c']<ref['global_peak_ap_c'] for f,ref in zip(fs,rs)) if allowed else False
                        if allowed and gain:guard_opportunities.append(dict(phase=v['phase'],condition=v['case']['condition'],arrival_seed=v['case']['seed'],family=v['case']['family'],context=v['case']['context'],now_ns=snapshot['now_ns'],action=snapshot['actions'][j],forecasts=fs,L0_reference=rs,meaning='all current global projected KPIs nonworse but individual urgent-response rule blocks this action; conditional current queue, no future performance guarantee'))
    for phase in behavior:
        for v in [v for v in ledger if v['phase']==phase]:
            same=schedule_key(raws[v['identity']])==schedule_key(raws[f'{phase}_Band_{v["case"]["condition"]:02d}']);behavior[phase][v['role']]['schedule_same_Band']+=same
    tables={phase:summary(d.read(d.LOCAL/(phase+'_rows.json'))) for phase in ('development','confirmation')}
    d.write(d.PUBLIC/'summary.json',tables);d.write(d.PUBLIC/'behavior.json',behavior)
    d.write(d.LOCAL/'guard_opportunities.json',guard_opportunities)
    d.write(d.PUBLIC/'guard_opportunity_summary.json',dict(total_candidate_events=len(guard_opportunities),development_events=sum(q['phase']=='development' for q in guard_opportunities),confirmation_events=sum(q['phase']=='confirmation' for q in guard_opportunities),independent_successes=False,native_additional_starts=0,model_additional_projections=0,first3=guard_opportunities[:3]))
    for phase in ('development','confirmation'):
        rows=d.read(d.LOCAL/(phase+'_rows.json'))
        with (d.PUBLIC/(phase+'_comparison.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    verification=dict(status='PASS',utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),worktree_dirty=True,registered_sources_verified=True,source_manifest=d.read(d.LOCAL/'registration.json')['source_sha256'],raw_archive_sha_checked=audited,ledger_boundary_audits=audited,planned_requests=all_requests,completed_requests=completed,unit_tests=dict(command='python -B -X utf8 -m unittest tools.test_d1_overnight_ie_policy -v',passed=9,scope='executed before registration; native fixtures separately counted'),native_gates=4,device_commands=0,learning_starts=0,model_fit_calls=0,concurrent_root_and_RL_consumption_excluded=True)
    d.write(d.PUBLIC/'verification.json',verification)
    figures=d.PUBLIC/'figures';figures.mkdir(exist_ok=True)
    (figures/'01_실행시간표.svg').write_text(svg_timeline({r:raws['representative_'+r] for r in ('Band','Rule','R1','R2')}),encoding='utf-8')
    confirmation=d.read(d.LOCAL/'confirmation_rows.json')
    for name,field,title in [('02_에너지조건지도.svg','energy_j','에너지 차이'),('03_AP조건지도.svg','peak_ap_c','최고 AP 차이'),('04_기한조건지도.svg','normal_failure','일반 기한 실패 차이')]:
        (figures/name).write_text(svg_map(confirmation,field,title),encoding='utf-8')
    def table(values):
        return '<table><tr><th>정책</th><th>완료/예정</th><th>긴급 실패</th><th>일반 실패</th><th>긴급 P95 평균 ms</th><th>ΔJ 평균</th><th>Δ최고AP 평균 °C</th></tr>'+''.join(f'<tr><td>{q["name"]}</td><td>{q["completed"]}/{q["planned"]}</td><td>{q["urgent_failure"]}</td><td>{q["normal_failure"]}</td><td>{q["mean_urgent_p95_ms"]:.3f}</td><td>{q["mean_delta_J"]:+.6f}</td><td>{q["mean_delta_AP"]:+.6f}</td></tr>' for q in values)+'</table>'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>산업공학 롤링 보완 비교</title><style>body{font:16px "Malgun Gothic",sans-serif;max-width:1160px;margin:30px auto;background:#f5f7fa;color:#172b44}table{border-collapse:collapse;background:white;width:100%}th,td{padding:12px;text-align:left;border-bottom:1px solid #dbe1e9}h1{font-size:28px}img{width:100%;background:white;margin:15px 0}p{line-height:1.6}</style><h1>관측 전 대기 금지·현재 응답 보존 리스트</h1><p>개발24 / 새 확인48 ×6정책. 사전고정96 교대 요청은 실제 기기 동결계획 검증용이며 온라인 기기 정책 실행이 아닙니다.</p><p>442/768 PC 환경 · 학습0 · 기기 명령0 · 요청 전량 완료. R1은 초기 미관측 냉각 금지, R2는 R1에 현재 큐 전체의 예상 응답 비악화를 추가합니다.</p><h2>새 확인 결과</h2>'+table(tables['confirmation'])+'<h2>개발 결과</h2>'+table(tables['development'])+'<p>전체 평균을 최종 채택으로 해석하지 않습니다. 조건별 기한·P95·J·AP 비악화와 low/sustained 절대 기한 조건을 원 계약 그대로 평가했습니다.</p>'+''.join(f'<img src="figures/{name}" alt="{name}">' for name in ('01_실행시간표.svg','02_에너지조건지도.svg','03_AP조건지도.svg','04_기한조건지도.svg'))+'<p>AP는 동일 온도 모형 채널이며 표면 온도·안전 한도가 아닙니다. 작은 비용 차이를 휴대폰 실절감으로 확정할 수 없습니다. 4개 확인 도착 seed와 3개 문맥은 서로 다른 종류의 반복이며 48개 독립 실측이 아닙니다.</p><p><a href="confirmation_comparison.csv">확인 전량 CSV</a> · <a href="development_comparison.csv">개발 전량 CSV</a> · <a href="execution_contract.json">사전 계약</a> · <a href="verification.json">검증</a> · <a href="behavior.json">행동 분해</a></p></html>'
    (d.PUBLIC/'index.html').write_text(page,encoding='utf-8')
    lines=['# 산업공학 기반 롤링 보완 비교','', '기존 같은 리스트의 냉각 대기 위험을 최소 변경 두 가지로 분리했다. 기존 Rule·PPO·모형·결과는 보존했다.','', '| 구분 | 구현 | 한계 |','|---|---|---|','| R1 | 관측 부하가 미확인인 초기 냉각 대기 금지 | 최근 관측으로 미래 도착을 보장하지 않음 |','| R2 | R1 + 현재 모든 요청의 예상 응답을 L0보다 늦추지 않음 | 별도 보수적 정책 제약이며 원 기준 변경 아님 |','', '개발은 기존 seed826020101/102의24조건, 확인은 새 seed828110101..104의48조건이다. 저부하·큐·순간 몰림·지속 부하와 mean/short/long 문맥을 모두 포함한다. 같은 입력·초기 상태·CPU/GPU·기한·실현 비용·J0..120/AP35..180을 썼다.','', '## 새 확인 결과','','| 정책 | 완료/예정 | 일반 실패 | 긴급 실패 | 평균 ΔJ | 평균 Δ최고AP °C |','|---|---:|---:|---:|---:|---:|']
    for q in tables['confirmation']:lines.append(f'| {q["name"]} | {q["completed"]}/{q["planned"]} | {q["normal_failure"]} | {q["urgent_failure"]} | {q["mean_delta_J"]:+.6f} | {q["mean_delta_AP"]:+.6f} |')
    lines.extend(['','## 판단','','최종 판단은 `confirmation_verdict.json`의 전 조건 비악화 기준이다. 기한 위반 또는 일부 조건의 AP/J 증가를 평균 비용 감소로 상쇄하지 않는다. 정책별 행동과 반례는 `behavior.json` 및 전량 CSV에 남겼다.','', 'R1/R2가 기존 Band와 동일 일정이면 그 trace에서 별개 스케줄러 우위 실측은 성립하지 않는다. 대표96trace의 Band/R1/R2/L0는 동일 일정이며, 기존 Rule만 짧은 냉각 대기에 따른 작은 모델 비용 차이를 보였다. 대표trace는 결과 후 바꾸지 않았다.','', '냉각으로 서비스시간이 회복되는 효과는 고정5phase에 없다. AP는 모형 온도이고 에너지는 원 실측계수 기반 추정이다. 제어 계산시간은 PC에서 기록했으며 휴대폰 오버헤드/에너지로 전용하지 않는다. 작은 AP/J 차이와 독립 실제 정책 개선의 증거를 구분한다.','', '## 검증·재현','','9개 새 기능 검사, native4 gate와442개 원장의 요청/phase/응답/AVAILABLE/CPU-GPU 호환성/마스크/원본SHA 검증을 통과했다. PC442환경·학습0·실측0·fit0이며 다른 동시 과제의 소비는 포함하지 않는다. 원768상한의 남은326은 자동 재사용하지 않는다.','', '```powershell','python -B -X utf8 -m unittest tools.test_d1_overnight_ie_policy -v','python -B -X utf8 -m tools.d1_overnight_ie_run check','python -B -X utf8 -m tools.d1_overnight_ie_report','```','', '등록/실행은 같은 task directory의 시계·예산을 재설정하지 않는다. 원 대용량 gz·기기 동결계획은 local output에 보존하고 공개물에는 소규모 코드/설정/CSV/그림/문서만 포함한다.','', '[오프라인 화면](index.html) · [사전 계약](execution_contract.json) · [확인48 전량](confirmation_comparison.csv) · [행동 분석](behavior.json)'])
    (d.PUBLIC/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return dict(summary=tables,behavior=behavior,verification=verification)

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False),flush=True)
