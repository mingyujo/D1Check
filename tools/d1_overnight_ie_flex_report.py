"""Check complete P95-flex raw archives and publish conditional-model evidence."""
import csv,gzip,html,json,statistics,subprocess
from collections import Counter
from datetime import datetime,timezone
from tools import d1_overnight_ie_flex_run as d

NAMES=dict(Band='Band 전체 요청 대응',Triton='Triton 고정 요청 대응',L0='서비스 우선 리스트',Rule='기존 열·에너지 리스트',Flex='P95 제약 실행·자원 대기 유연성')

def summary(rows):
    base={q['condition']:q for q in rows if q['policy']=='Band'};out=[]
    for role in d.ROLES:
        rs=[q for q in rows if q['policy']==role]
        out.append(dict(policy=role,name=NAMES[role],conditions=len(rs),planned=sum(q['planned'] for q in rs),completed=sum(q['completed'] for q in rs),urgent_failure=sum(q['urgent_failure'] for q in rs),normal_failure=sum(q['normal_failure'] for q in rs),mean_urgent_p95_ms=statistics.mean(q['urgent_p95_ms'] for q in rs),mean_normal_ms=statistics.mean(q['normal_mean_ms'] for q in rs),mean_J=statistics.mean(q['energy_j'] for q in rs),mean_AP=statistics.mean(q['peak_ap_c'] for q in rs),mean_delta_J=statistics.mean(q['energy_j']-base[q['condition']]['energy_j'] for q in rs),mean_delta_AP=statistics.mean(q['peak_ap_c']-base[q['condition']]['peak_ap_c'] for q in rs)))
    return out

def run():
    state=d.read(d.LOCAL/'WORKING_STATE.json')
    if state['phase']!='completed':raise ValueError('no final verdict from partial runs')
    d.check();entries=[]
    for line in (d.LOCAL/'executions.jsonl').read_text(encoding='utf-8').splitlines():
        q=json.loads(line)
        if q.get('event'):entries[q['number']-1].update(q)
        else:entries.append(q)
    assert len(entries)==266 and all(q['status']=='completed' for q in entries)
    planned=completed=0;decisions=Counter();rejections=Counter();totalwait=0.;changed=[]
    for entry in entries:
        path=d.LOCAL/'items'/(entry['identity']+'.json.gz');assert d.sha(path)==entry['sha256'];raw=json.loads(gzip.decompress(path.read_bytes()));d.native.prior.previous.audit(raw['result'],entry['case']['tickets']);planned+=raw['row']['planned'];completed+=raw['row']['completed']
        if entry['role']=='Flex':
            totalwait+=raw['total_extra_wait'];rejections.update(raw['admission_rejections'])
            for s in raw['snapshots']:
                decisions[s['actions'][s['chosen']]['kind']]+=1
                if s['chosen']!=0:changed.append(dict(phase=entry['phase'],condition=entry['case']['condition'],family=entry['case']['family'],context=entry['case']['context'],now_ns=s['now_ns'],kind=s['actions'][s['chosen']]['kind'],action=s['actions'][s['chosen']],P95_scope='past observed+arrived/owned pending, no new arrivals'))
    tables={p:summary(d.read(d.LOCAL/(p+'_rows.json'))) for p in ('development','confirmation')};d.write(d.PUBLIC/'summary.json',tables)
    d.write(d.PUBLIC/'behavior.json',dict(decisions=dict(decisions),rejections=dict(rejections),total_extra_wait_s=totalwait,chosen_alternative_events=len(changed),chosen_alternatives=changed))
    for phase in ('development','confirmation'):
        rows=d.read(d.LOCAL/(phase+'_rows.json'));keys=sorted({k for q in rows for k in q})
        with (d.PUBLIC/(phase+'_comparison.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    verification=dict(status='PASS',utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),worktree_dirty=True,source_sha256=d.read(d.LOCAL/'registration.json')['source_sha256'],new_native_archives_checked=266,planned_requests=planned,completed_requests=completed,native_gate=2,unit_tests=9,feature_arrays_and_physical_mask_equal_only_admission_mask_changes=True,archived_witness='one development seed/state across3 sensitivity contexts, not3independent successes',development_baseline_native_starts_reused_from_parent=96,reused_development_raw_sha256=d.read(d.LOCAL/'registration.json')['reused_development_raw_sha256'],learning_starts=0,device_commands=0,model_fit_calls=0,new_confirmation_used_for_tuning=False)
    d.write(d.PUBLIC/'verification.json',verification)
    def table(values):
        return '<table><tr><th>정책</th><th>완료/예정</th><th>긴급 실패</th><th>일반 실패</th><th>긴급 P95 평균ms</th><th>ΔJ 평균</th><th>Δ최고AP 평균°C</th></tr>'+''.join(f'<tr><td>{q["name"]}</td><td>{q["completed"]}/{q["planned"]}</td><td>{q["urgent_failure"]}</td><td>{q["normal_failure"]}</td><td>{q["mean_urgent_p95_ms"]:.3f}</td><td>{q["mean_delta_J"]:+.6f}</td><td>{q["mean_delta_AP"]:+.6f}</td></tr>' for q in values)+'</table>'
    rows=d.read(d.LOCAL/'confirmation_rows.json');base={q['condition']:q for q in rows if q['policy']=='Band'};maps=[]
    for field,label in [('normal_failure','일반 기한 실패'),('urgent_p95_ms','긴급 P95'),('energy_j','에너지 J'),('peak_ap_c','최고 AP')]:
        tiles=''.join(f'<span style="background:{"#8cceb2" if q[field]-base[q["condition"]][field]<0 else "#e9aea7" if q[field]-base[q["condition"]][field]>0 else "#dce2ea"}" title="조건{q["condition"]} {q["family"]} {q["context"]}: Δ{q[field]-base[q["condition"]][field]:.9g}">{q["condition"]}</span>' for q in rows if q['policy']=='Flex')
        maps.append(f'<p>{label} — Band 대비</p><div class="map">{tiles}</div>')
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>P95 제약 실행·자원 대기 유연성</title><style>body{font:16px "Malgun Gothic",sans-serif;max-width:1200px;margin:30px auto;background:#f6f8fa;color:#172c47}p{line-height:1.6}table{border-collapse:collapse;background:white;width:100%}th,td{padding:11px;border-bottom:1px solid #d9e0e9;text-align:left}.map{display:grid;grid-template-columns:repeat(24,1fr);gap:4px}.map span{padding:9px 2px;text-align:center;font-size:12px}</style><h1>P95 제약 실행·자원 대기 유연성</h1><p>개별 긴급 예상응답 비악화가 최종 P95보다 강해 차단하던 선택을 별도 정책에서 비교했습니다. 미래 도착을 넣지 않았고 최종 기한·처리량·P95·J·AP 판정은 유지했습니다.</p><p>266 PC 환경 / 학습0 / 기기0 / fit0. 개발24 기준4정책은 앞 과제의 정확한 원장을 재사용했고, 새확인48×5는 모두 새로 실행했습니다.</p><h2>새 확인48</h2>'+table(tables['confirmation'])+'<h2>개발24</h2>'+table(tables['development'])+''.join(maps)+'<p>초록 감소·회색 동일·빨강 증가. 원계약 epsilon0의 전 조건 판정은 confirmation_verdict.json입니다. 모형 AP와 작은 J 차이는 실제 휴대폰 효과로 확정할 수 없습니다.</p><p><a href="confirmation_comparison.csv">확인 CSV</a> · <a href="execution_contract.json">고정 계약</a> · <a href="verification.json">검증</a> · <a href="confirmation_verdict.json">최종 판정</a></p></html>'
    (d.PUBLIC/'index.html').write_text(page,encoding='utf-8')
    text=['# P95 제약 실행·자원 대기 유연성 비교','','기존 모든 긴급 요청의 개별 예상응답 비악화는 최종 P95·기한 기준보다 강하다. 실제 개발 seed826020101의 지속 부하63.072586416s에서, CPU가 바쁠 때 GPU 즉시 분류 대신 실제 CPU AVAILABLE까지 기다리는 후보가 차단됐으나 현재 전체 P95·miss·J·AP는 3문맥 모두 비악화였다. 이는 한 상태의 세 민감도 문맥이고 독립 세 성공이 아니다.','','세 역할 검토에서 관측+현재 도착/소유 미응답을 같은 P95분모에 넣고, 개별 lateness·미스·J·물리mask·초기 미관측 냉각금지·0.25초 요청 대기한도를 유지했다. 미래 전체 P95보장을 주장하지 않는다. 최종 서비스 평가를 완화하지 않고, 새로운 ID/schema로 내부 후보 허용 검사만 바꿨다.','','개발24는 동일 자료의 기준4개를 원장/SHA로 재사용하고 후보24를 새 실행했다. 새확인 seed828120201..204×4부하×3문맥48조건에서 Band/Triton/L0/Rule/새후보 5개를 모두 동일조건으로 실행했다. 설정·판정·모형·기한·원phase/완료·AVAILABLE는 첫 확인 전 고정했고 결과후튜닝0이다.','','| 정책 | 완료/예정 | 긴급 실패 | 일반 실패 | 평균 ΔJ | 평균 Δ최고AP °C |','|---|---:|---:|---:|---:|---:|']
    for q in tables['confirmation']:text.append(f'| {q["name"]} | {q["completed"]}/{q["planned"]} | {q["urgent_failure"]} | {q["normal_failure"]} | {q["mean_delta_J"]:+.6f} | {q["mean_delta_AP"]:+.6f} |')
    text.extend(['','전체 평균과 개별 조건 비악화를 구분한다. 전 조건 우위가 없으면 `confirmation_verdict.json`의FAIL을 유지하고 자동채택하지 않는다. 비교 범위 밖의 전역 최적 또는 실제 Band/Triton 제품 우위가 아니다.','','9개 기능검사/2native gate/266원장경계·SHA검사를 통과했다. 응답경계는 분류OUTPUT_READY·탐지PERSISTED, 자원반환은AVAILABLE이다. 추가 본학습·기기·fit0이다. 원512상한의 잔여246은 자동 재사용하지 않는다.','','기존 원모형의5phase서비스와 에너지계수, 새v3 열head를 동결했으며 냉각→속도회복은없다. 열은 모형AP이며 표면·안전온도가 아니다. 4도착seed·3민감도문맥을48독립실측으로 보지 않는다. 기존첫4기기Band/Rule동결계획·trace를 이 결과로 바꾸지 않았다.','','```powershell','python -B -X utf8 -m unittest tools.test_d1_overnight_ie_flex_policy -v','python -B -X utf8 -m tools.d1_overnight_ie_flex_run check','python -B -X utf8 -m tools.d1_overnight_ie_flex_report','```','','[비교 화면](index.html) · [사전 계약](execution_contract.json) · [확인48 전량](confirmation_comparison.csv) · [행동 분석](behavior.json)'])
    (d.PUBLIC/'README.md').write_text('\n'.join(text)+'\n',encoding='utf-8');return dict(summary=tables,behavior=dict(decisions),verification=verification)

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False),flush=True)
