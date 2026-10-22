"""Apply the same frozen85% targets to new confirmation; never change selection."""
import datetime,hashlib,html,json
from pathlib import Path
H=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def main():
 s=read(H/'IMPROVEMENT_SUMMARY.json');a=read(H/'ANALYSIS.json');chosen=s['selected_before_confirm8'];assessments={}
 for cohort,expected in [('development32',24),('confirm8',6)]:
  q=s['cohorts'][cohort]['nominal85'];v=q[chosen];b=q['BC_FULL'];edf=q['EDF_NPU'];coverage=v['cases']==b['cases']==edf['cases']==expected
  gates=dict(registered_nominal85_coverage=coverage,unfinished_zero=v['unfinished']==0,urgent_at_least99_9=v['urgent_on_percent']>=99.9,raw_BC_energy_increase_at_most1percent=coverage and v['API_J']<=1.01*b['API_J'],raw_BC_AP_increase_at_most0_1C=coverage and v['AP_C']<=b['AP_C']+.1)
  assessments[cohort]=dict(expected_inputs=expected,gates=gates,all_frozen_targets_pass=all(gates.values()),candidate=v,BC=b,EDF=edf,whole_on_delta_pp=v['all_on_percent']-b['all_on_percent'] if coverage else None,EDF_energy_delta_percent=100*(v['API_J']/edf['API_J']-1) if coverage else None)
 verdict=assessments['confirm8']['all_frozen_targets_pass']
 record=dict(status='FROZEN_CONFIRMATION_TARGETS_PASS' if verdict else 'FROZEN_CONFIRMATION_TARGETS_NOT_ALL_MET',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected_before_confirmation=chosen,selection_changed=False,adopted=False,assessments=assessments,source_sha256=sha(Path(__file__)),analysis_sha256=sha(H/'ANALYSIS.json'),selection_sha256=sha(H/'SELECTION_FROZEN.json'),interpretation='The1% raw-BC energy bound remains unchanged even though missing work makes it unequal-service. Separately report completed-EDF savings; do not relax targets after seeing confirmation. The nominal85 subgroup has6 new inputs, not an independent device/generalization certification.')
 save(H/'CONFIRMATION_ASSESSMENT.json',record)
 d=assessments['development32'];v=d['candidate'];b=d['BC'];c=assessments['confirm8'];cv=c['candidate'];cb=c['BC']
 message='새 확인 입력에서도 사전 명목85% 목표를 모두 충족했다.' if verdict else '개발 입력의 목표 충족을 새 확인 입력 전체의 성공으로 전용하지 않는다. 새 확인에서는 사전 명목85% 목표 중 미충족 항목이 있다.'
 card='<section class="note"><h2>최종 판독: 개발과 새 확인을 구분</h2><p><b>'+message+'</b> 기존 공식 최종은 유지하며 이번 후보는 비채택이다.</p><p>새 확인6입력의 미완료 '+str(cb['unfinished'])+'→'+str(cv['unfinished'])+'건, 긴급 정시 '+f'{cb["urgent_on_percent"]:.3f}→{cv["urgent_on_percent"]:.3f}%'+', API-J '+f'{cb["API_J"]:.3f}→{cv["API_J"]:.3f}'+', 평균AP '+f'{cb["AP_C"]:.3f}→{cv["AP_C"]:.3f}℃'+'.</p><p>개발 명목85% 전체 정시율은 '+f'{b["all_on_percent"]:.3f}→{v["all_on_percent"]:.3f}%'+', 새 확인 명목85%는 '+f'{cb["all_on_percent"]:.3f}→{cv["all_on_percent"]:.3f}%'+'. 늦은 요청을 끝까지 처리하면서 정시 건수가 줄어들 수 있다. 긴급·미완료 개선을 모든 서비스 지표의 공동 우위로 표현하지 않는다.</p><p>확인 목표 판정: '+html.escape(json.dumps(c['gates'],ensure_ascii=False))+'</p><p>105% 스트레스와 전체32/8 결과는 아래 표에 전부 보존한다. 낮은 기존 BC 사용량에는 미처리 요청이 포함돼 있으며, 실제 완료 서비스를 맞춘 EDF 비교를 함께 읽어야 한다.</p></section>'
 text=(H/'REPORT_KO.html').read_text(encoding='utf-8');needle='<h1>롤링+ATC+BC의 서비스 개선 후보</h1>';assert text.count(needle)==1;text=text.replace(needle,needle+card)
 with (H/'FINAL_REVIEW_KO.html').open('x',encoding='utf-8',newline='\n') as f:f.write(text)
 save(H/'FINAL_REVIEW_MANIFEST.json',dict(html_sha256=sha(H/'FINAL_REVIEW_KO.html'),base_report_sha256=sha(H/'REPORT_KO.html'),assessment_sha256=sha(H/'CONFIRMATION_ASSESSMENT.json'),source_sha256=sha(Path(__file__)),adopted=False))
 print('CONFIRMATION_ASSESSMENT',record['status'],flush=True)
if __name__=='__main__':main()
