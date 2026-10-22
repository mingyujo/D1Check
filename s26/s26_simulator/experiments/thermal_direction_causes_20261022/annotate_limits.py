"""Make improvement concentration explicit; preserve draft report and conclusion."""
from engine import *
import re,markdown
O=H/'artifacts/G001';md=(H/'REPORT_KO.md').read_text(encoding='utf-8');ht=(H/'REPORT_KO.html').read_text(encoding='utf-8');c=read(O/'CONCLUSION.json');b=read(O/'PAIRED_DIAGNOSTICS.json');r=read(O/'COMPARISON.json')
rise=next(v for v in b['statistics'] if v['candidate']=='MARGIN_STEADY_GUARD' and v['metric']=='LATE_RISE_direction');fall=next(v for v in b['statistics'] if v['candidate']=='MARGIN_STEADY_GUARD' and v['metric']=='LATE_FALL_direction')
note=f"**개선 폭과 적용 범위는 작다.** 장시간 상승 방향은 {rise['sessions']}세션 중 {rise['improved']}세션에서만 개선됐고 {rise['equal']}세션은 동률이다. 하강은 {fall['improved']}세션 개선, {fall['worse']}세션 악화, {fall['equal']}세션 동률이다. 두 방향 개선의 기술적 재표집 구간은 0을 포함한다. 전체 상승 방향 정확도는 74.09→73.69%로 소폭 하락했다. 평균 온도오차·정체 정확도를 보존한 개발 후보로 남기되, 장시간 추세 문제 해결이나 새 집단에 대한 일반적 우수성을 선언하지 않는다.\n\n"
for name,value in [('REPORT_KO_INITIAL_DRAFT.md',md),('REPORT_KO_INITIAL_DRAFT.html',ht)]:
    with (H/name).open('x',encoding='utf-8') as f:f.write(value)
save(O/'CONCLUSION_INITIAL_DRAFT.json',c);c.update(development_mean_only=True,late_rise_improved_sessions=rise['improved'],late_rise_total_sessions=rise['sessions'],late_fall_improved_sessions=fall['improved'],general_superiority_confirmed=False,independent_confirmation=False)
(O/'CONCLUSION.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8');md=md.replace('## 2. 왜 장시간 방향이 낮았나: 확인한 사실과 가설',note+'## 2. 왜 장시간 방향이 낮았나: 확인한 사실과 가설');css=re.search(r'<style>(.*?)</style>',ht,re.S).group(1)
(H/'REPORT_KO.md').write_text(md,encoding='utf-8');(H/'REPORT_KO.html').write_text('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>S26 방향 원인과 정체 보호</title><style>'+css+'</style></head><body><main>'+markdown.markdown(md,extensions=['tables','fenced_code'])+'</main></body></html>',encoding='utf-8')
print(json.dumps(dict(status='CONCENTRATION_AND_GLOBAL_RISE_TRADEOFF_DISCLOSED',rise_improved=rise['improved'],fall_improved=fall['improved']),ensure_ascii=False))
