"""Separate reviewable HTML/JSON readout of guarded BC; no adoption/publication."""
import datetime,html,json
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,v):
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
names={'BC_RESOURCE_EDF_NORMAL':'BC+자원보호+일반 EDF','BC_FULL':'기존 롤링+ATC+BC','BC_DISPATCH_ONLY':'BC+대기 금지','BC_PROGRESS_GUARD':'BC+대기·진행 보호','BC_RESOURCE_GUARD':'BC+자원·진행 보호','PPO_FULL':'기존 롤링+ATC+BC+PPO','EDF_NPU':'NPU 우선 EDF','EDF_GPU':'GPU 우선 EDF','CPU_RESERVE_SLACK':'기존 CPU예약·납기여유 규칙'}
def brief(s):
 return dict(cases=s['cases'],API_J=s['J_mean'],AP_C=s['AP_mean'],AP_peak_C=s['AP_peak_max'],all_on_percent=s['all']['ontime_percent_pooled'],urgent_on_percent=s['urgent']['ontime_percent_pooled'],unfinished=s['unfinished'],urgent_P95_s=s['urgent']['P95_s_mean'],normal_max_s=s['normal']['max_completed_response_s'],vs_BC_API_J_percent=s.get('vs_BC_J_percent'),vs_BC_AP_C=s.get('vs_BC_AP_C'),vs_EDF_NPU_API_J_percent=s.get('vs_EDF_NPU_J_percent'),raw_gap_retained_percent=s.get('raw_BC_to_EDF_energy_gap_retained_percent'),energy_service_qualified=s.get('same_service_energy_qualification'))
def main():
 a=read(H/'ANALYSIS.json');assert a['status']=='PASS_GUARDED_BC_REPAIR_SAVED_AUDIT';selected=a['selection']['selected'];data={cohort:{scope:{m:brief(v) for m,v in methods.items()} for scope,methods in item['descriptive_subgroups'].items()} for cohort,item in a['cohorts'].items()}
 result=dict(status='REVIEW_ONLY_NOT_ADOPTED',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected_before_confirm8=selected,development_target_met=a['selection']['target_met'],new_attempts=a['START'],completed=a['COMPLETE'],execution_failures=a['FAIL'],independent_saved_checks=a['checks'],cohorts=data,original4_BC_published_reference=a['selection']['baseline_original4'],official_final_unchanged=True,new_training=0,new_measurements=0,physical_accuracy_gate='FAIL unchanged',adopted=False)
 save(H/'IMPROVEMENT_SUMMARY.json',result)
 parts=['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>S26 BC 서비스 개선 후보</title><style>body{font-family:Malgun Gothic,Arial,sans-serif;max-width:1140px;margin:40px auto;padding:0 24px;color:#163b46;line-height:1.7}h1{font-size:30px}h2{margin-top:40px}p{max-width:1000px}table{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0 24px}th{background:#226a70;color:white;text-align:left}td,th{padding:9px;border-bottom:1px solid #d6e4e1}tbody tr:nth-child(odd){background:#eff5f4}.note{background:#fff1d8;border-left:4px solid #be8424;padding:14px}.ok{background:#e8f4f0;padding:14px}.num{text-align:right}code{font-size:12px;overflow-wrap:anywhere}@media print{body{margin:12mm}table{font-size:10px}h2{break-after:avoid}tr{break-inside:avoid}}</style><h1>롤링+ATC+BC의 서비스 개선 후보</h1><p><b>기존 공식 최종 유지 / 새 후보 비채택 / 2026-10-20</b></p>']
 parts.append('<p class="ok">새 입력 확인 전에 고정한 후보: <b>'+names[selected]+'</b>. 첫148회에서 드러난 일반 정시율 손실을 보완해 일반 CPU 순위를 EDF로 고정했다. 기존 32특징·최대27행동 BC 가중치를 유지하고, 원 BC 로짓 뒤에 별도의 허용 행동·진행 규칙을 붙였다. 새 학습·PPO 갱신·실측·물리계수 보정은 0회다.</p>')
 parts.append('<p>기존 공식 최종은 롤링+ATC+공개 교사학습 초기화+PPO881087이며 변경하지 않았다. 여기서 BC는 마지막 PPO 직전 체크포인트로, 더 이전 PPO 계보도 있다. 이번 개선은 보호 규칙을 포함한 시스템 패키지의 효과이며 BC 자체의 학습 개선으로 주장하지 않는다.</p>')
 parts.append(f'<p><b>실행 원장: START {a["START"]} / COMPLETE {a["COMPLETE"]} / FAIL {a["FAIL"]}.</b> 실패는0건 완료로 간주하거나 대체seed로 메우지 않는다. 표의 입력 수가 다르면 전체 평균으로 에너지 차이·보존율을 계산하지 않는다. 입력별 대응 비교는 저장된 공통 입력만 사용하며 등록 전체가 없으면 사전 개선 PASS를 주지 않는다.</p>')
 failed=read(H/'artifacts/G001/RESULT.json')['failures']
 if failed:parts.append('<p class="note">보존한 실행 실패: '+html.escape('; '.join(v['label']+': '+v['error'] for v in failed))+'</p>')
 parts.append('<h2>비교 설계</h2><p>기존 추가 입력32 × 새 후보1 =32회, 원 최종4입력 × 새 후보1 =4회, 다시 별도 새8입력 × BC·새 후보·EDF =24회, 합계60회다. 앞선148회와 선정 기록은 그대로 보존했다. 일반 EDF 보완은 개발32의 첫 보호 후보가 일반 정시율을 낮춘 결과를 본 뒤 설계했다. 완료된 기존 방법은 재실행하지 않고 저장 결과를 재사용했다. 개발32와 원4만으로 후보를 선정해 새8 실행 전에 봉인했으며, 새8 결과가 나빠도 선정·seed를 바꾸지 않는다.</p>')
 parts.append('<p>초기 목표: 원4의 긴급100%·미완료0·정시 손실0.1%p 이내, API-J 증가1%·AP 증가0.1℃ 이내. 개발 명목85%에서도 미완료0·긴급99.9% 이상·API-J 증가1%·AP 증가0.1℃ 이내. 이 목표는 분석 기준이며 산업 표준·실기기 오차 허용치가 아니다. 개발 목표 충족: <b>'+str(a['selection']['target_met'])+'</b>.</p>')
 parts.append('<h2>보존한 첫 비교와 이번 추가 규칙</h2><p>이번에는 자원·진행 보호에 일반 EDF를 결합한 한 가지 고정 규칙만 새로 평가했다. 아래 앞선 세 후보는 보존한148회에 속하며, 개발32 표에서 그 결과를 재사용한다. 일반 CPU 경로가 실행 가능하면 가장 이른 납기의 일반 요청을 선택하므로, 일반 순서에는 BC가 개입하지 않는다. 이 구성의 성능을 BC 독립 기여로 주장하지 않는다.</p><ol><li><b>대기 금지:</b> 원 BC 로짓 중 실제 배정 행동만 선택한다. 불필요한 대기를 없앤 효과와 에너지 증가를 분리한다.</li><li><b>진행 보호:</b> 긴급 선두의 명목 응답+점유1건이 납기에 닿으면 명목상 납기 가능한 경로를 우선한다. 그렇지 않고 가장 오래된 일반 요청이 이미 늦었다면 그 요청을 처리한다. 실제 납기의 수학적 보장은 아니다.</li><li><b>자원·진행 보호:</b> 위 규칙에 CPU 추론슬롯의 탐지 예약, NPU 우선 분류, 현재 NPU 단독 EDF 순차 예측이 납기를 넘을 때의 GPU 분산을 결합한다. 빈 허용 집합은 다음 엔진 사건까지 NONE이며, 이 지연도 실제 응답시간에 포함된다.</li></ol>')
 for cohort,title in [('original4','원 최종4입력의 새 후보 확인'),('development32','기존 추가32입력의 같은 입력 비교'),('confirm8','선정 뒤 별도 새8입력 확인')]:
  parts.append('<h2>'+title+'</h2>')
  if cohort=='original4':
   old=a['selection']['baseline_original4'];parts.append(f'<p>보존·재사용하는 원 BC4 평균: {old["J"]:.3f} API-J / AP {old["AP"]:.3f}℃ / 정시 {old["on_percent"]:.3f}%. 원 BC4 긴급100%·미완료0. 새 후보만 실행했고 기존 최종 결과는 바꾸지 않았다.</p>')
  for scope,title2 in [('all','전체 등록 입력'),('nominal85','명목85% 부분집합'),('stress105','105% 스트레스 부분집합')]:
   if scope not in data[cohort] or cohort=='original4' and scope!='all':continue
   parts.append('<h3>'+title2+'</h3><table><thead><tr><th>방법</th><th>입력 수</th><th>평균 API-J</th><th>평균 AP℃</th><th>최고 AP℃</th><th>전체 정시%</th><th>긴급 정시%</th><th>미완료</th><th>긴급 P95초</th><th>일반 최대초</th></tr></thead><tbody>')
   for m,z in data[cohort][scope].items():
    values=[names[m],z['cases'],f'{z["API_J"]:.3f}',f'{z["AP_C"]:.3f}',f'{z["AP_peak_C"]:.3f}',f'{z["all_on_percent"]:.3f}',f'{z["urgent_on_percent"]:.3f}',z['unfinished'],f'{z["urgent_P95_s"]:.3f}' if z['urgent_P95_s'] is not None else 'NA',f'{z["normal_max_s"]:.3f}' if z['normal_max_s'] is not None else 'NA'];parts.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in values)+'</tr>')
   parts.append('</tbody></table>')
  s=data[cohort].get('nominal85',{}).get(selected)
  if s and s['vs_BC_API_J_percent'] is not None:parts.append(f'<p>선정 후보의 명목85%: 기존 BC 대비 API-J {s["vs_BC_API_J_percent"]:+.3f}% / AP {s["vs_BC_AP_C"]:+.4f}℃. 같은 EDF NPU우선 대비 API-J {s["vs_EDF_NPU_API_J_percent"]:+.3f}%. 원 BC와 EDF 사이 사용량 차이의 {s["raw_gap_retained_percent"]:.1f}%를 남겼다. 이 보존율은 서로 다른 완료량을 포함한 원 BC 수치와의 기술통계이며, BC 대비 동일 서비스 절감률이 아니다.</p>')
 parts.append('<h2>NN의 역할과 검산</h2>')
 new=[v for k,v in a['neural_guard_audits'].items() if k.endswith('__'+selected)];calls=sum(v['decisions'] for v in new);overrides=sum(v['overrides'] for v in new)
 parts.append(f'<p>선정 후보 전체에서 원 BC 선택 {calls:,}건 중 보호 규칙이 {overrides:,}건({100*overrides/max(1,calls):.2f}%)을 바꿨다. 원 BC 로짓과 최종 행동을 모두 저장했다. {a["checks"]:,}개 저장 검산에서 물리 슬롯·CPU3·도착/납기·AVAILABLE·전체 도착 분모·API-J/AP 적분을 확인하고, 별도 NumPy 신경망과 Python 보호 규칙으로 선택을 대조했다. 수치 근접 동률은 저장 float32 로짓과 독립 계산 오차 범위를 함께 검사했다.</p>')
 parts.append('<p class="note">전력·열 정확도 gate는 FAIL이다. API-J/AP는 조건부 모형 수치이며 실제 S26 소비·온도 감소 인증이 아니다. CPU3 추가 코어·간섭과 모바일 NN/예측/보호 제어 비용은 미측정이다. 기존 롤링 캐시의 정확한 동등성 주장 FAIL도 유지했고 이 단계에서 고치지 않았다. 후속 원인 분리와 실기기 검증이 필요하다.</p>')
 parts.append('<p>전체32/8 결과를 숨기지 않고85%와105%를 나눠 기술했다. 새8은 같은 표본 풀·모형·초기 문맥의 합성 입력이며 조건당 반복1회뿐이다. 통계적 일반화, 미래 납기·대기 상한 또는 독립 실기기 확인으로 해석하지 않는다. 원 공식 정책·실패·원자료·optimizer/RNG·예산은 보존한다.</p><h2>근거 파일</h2><ul>')
 for f in ['PROTOCOL.json','OPERATION.json','SELECTION_FROZEN.json','ANALYSIS.json','IMPROVEMENT_SUMMARY.json','RESULTS.csv','PRESERVATION.json','service_guard.cjs','policy.cjs']:
  parts.append('<li><a href="'+f+'">'+f+'</a></li>')
 parts.append('</ul></html>')
 with (H/'REPORT_KO.html').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(parts))
 print('REPORT_AUTHORED',selected,'target',a['selection']['target_met'],flush=True)
if __name__=='__main__':main()
