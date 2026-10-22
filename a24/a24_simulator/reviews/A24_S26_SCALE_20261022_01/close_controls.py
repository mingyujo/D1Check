import json,hashlib
from pathlib import Path
V=Path(__file__).resolve().parent;R=V.parents[2];A=R/'a24_simulator';O=A/'results/A24_S26_SCALE_20261022_01'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
s=read(O/'SUMMARY.json');c=s['CONF_comparisons'][1]
files=[R/'docs/PROJECT_STATUS.md',R/'docs/PROJECT_PLAN.md',R/'docs/DECISIONS.md',A/'docs/LATEST_EXECUTION_FILES.md']
record=[]
for i,p in enumerate(files):
    before=p.read_bytes();backup=V/f'CONTROL_COMPLETION_BEFORE_{i}.bin'
    with backup.open('xb') as f:f.write(before)
    result=('../results/A24_S26_SCALE_20261022_01/REPORT_KO.md' if i==3 else '../a24_simulator/results/A24_S26_SCALE_20261022_01/REPORT_KO.md')
    head=f'''## 2026-10-22 A24-S26-SCALE-01 · 같은 평가기준·규모 조정 비교 완료

[정본]({result}). S26의 분류긴급0.8초/탐지일반2초·두혼합·전체도착 분모·입력별P95평균·고정관측창을 유지하고 A24 입력규모10설정을100회 탐색, 선택설정은 별도합성입력4개·20회로 확인했다. 선택은 입력당512건·4건묶음·A24명목25%(분류50/75% 각각2.612820/3.968551건/s)다.

확인에서 다섯정책 모두 전체2,048/2,048·긴급1,280/1,280·일반768/768정시, 미응답/미완료0이다. BC는 FIFO/EDF/RR 대비 예측소비 {c['energy_saving_pct']:.6f}%·평균AP {c['AP_reduction_C']:.6f}℃감소, 긴급/일반P95 +{c['U_P95_increase_s']:.6f}/+{c['N_P95_increase_s']:.6f}초다. 교사와BC는 거의같다. 기준선도100%여서 정시율우위는 없다. 가벼운 입력의 조건부성과이며 원S26의1,024건·16묶음·85%와 같은 난도/전역최적/실기기 절감은 아니다.

동결A24-05 BC·원미교정물리/CPU3·D_GPU전이가정 유지, 최근보정관측기 대입/학습/fit/실측/기존완료 재시작0이다. START120/COMPLETE120/FAIL0·JS9,902,576/Python163,886검사 PASS·공유잠금반환. 전체120행·손해167행·창민감도·4입력시간그래프 보존. 묶음간작업순서도변하는 입력대응 한정은 정본에 공개했다. 기본자동채택/게시/자동추가0·HEAD ac3a5af+미커밋, 최종검산·봉인은 결과폴더 FINAL_PROOF.json을 따른다. 다음: 정본검토·발표자료반영 또는 사용자 후속요청. 아래는 등록/이전 이력이다.

'''
    p.write_bytes(head.encode('utf-8')+before);assert p.read_bytes().endswith(before);assert p.read_bytes().endswith((V/f'CONTROL_BEFORE_{i}.bin').read_bytes())
    record.append({'path':p.relative_to(R).as_posix(),'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'previous_bytes_preserved_as_suffix':True})
with (V/'CONTROL_COMPLETION.json').open('x',encoding='utf-8') as f:json.dump({'files':record,'status':'PASS'},f,ensure_ascii=False,indent=2)
with (V/'VISUAL_REVIEW.json').open('x',encoding='utf-8') as f:json.dump({'status':'PASS','reviewed_pngs':['CONF_COMPARISON','GRID_COMPARISON','CONF_AP_TIME','CONF_ENERGY_TIME'],'Korean_text_legible':True,'labels_and_units_clear':True,'overlap_note':'FIFO/EDF/RR coincide exactly in CONF, teacher and BC nearly coincide. Main table discloses this.','review_date':'2026-10-22'},f,ensure_ascii=False,indent=2)
with (V/'REPORT_ERRATA.json').open('x',encoding='utf-8') as f:json.dump({'file':'CONTINUE_RUNNING.md','correction':'Unused CONF banks = 40 prepared minus 4 selected = 36, not 40. Corrected after report.py, which is retained as generated.','science_data_change':False},f,ensure_ascii=False,indent=2)
print('CONTROL_COMPLETION_PASS',len(record))
