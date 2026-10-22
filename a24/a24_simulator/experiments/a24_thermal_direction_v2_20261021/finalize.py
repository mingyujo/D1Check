"""Final saved consistency checks and bounded handoff, no fitting or rollout."""
import csv,json,math,re
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from prepare import H,R,A,O,PREV,FIRST,read,write,sha,pin

def main():
    V=A/'reviews/A24_THERMAL_DIRECTION_20261021_02';V.mkdir(exist_ok=False);reg=read(O/'REGISTRATION.json');f=read(O/'FINDINGS.json');checks=0
    for p in [reg['inputs'],*reg['sources'],*read(O/'POST_SOURCES.json')['sources']]:assert sha(R/p['path'])==p['sha256'];checks+=1
    assert read(O/'AUDIT.json')['status']=='PASS_GROUP_REUSE_AND_RUNTIME_AUDIT'
    assert read(FIRST/'FIT_COMPLETE.json')['fits']==309 and read(O/'FIT_COMPLETE.json')['fits']==200;checks+=2
    with (O/'AP_SAMPLES.csv').open(encoding='utf-8-sig',newline='') as file:
        rows=[r for r in csv.DictReader(file) if r['family']=='m8' and r['scope']=='registered' and r['policy'] in ['CALIBRATED_V1_OOF','CALIBRATED_OOF']]
    for policy in ['CALIBRATED_V1_OOF','CALIBRATED_OOF']:
        rr=[r for r in rows if r['policy']==policy];assert len(rr)==3691
        summary=next(r for r in f['overall'] if (r['family'],r['scope'],r['policy'],r['phase'])==('m8','registered',policy,'all'))
        errors=[float(r['error_C']) for r in rr];assert abs(sum(map(abs,errors))/len(errors)-summary['MAE_C'])<1e-10;checks+=1
        for r in rr:assert abs(float(r['predicted_C'])-float(r['observed_C'])-float(r['error_C']))<1e-10;checks+=1
    with (O/'DIRECTION_PAIRED_WINDOWS.csv').open(encoding='utf-8-sig',newline='') as file:paired=list(csv.DictReader(file))
    assert len(paired)==428
    for d in ['rise','fall','stable']:
        rr=[r for r in paired if r['observed_direction']==d]
        for policy,key in [('CALIBRATED_V1_OOF','before_correct'),('CALIBRATED_OOF','after_correct')]:
            score=100*sum(r[key]=='True' for r in rr)/len(rr)
            row=next(r for r in f['directions'] if (r['family'],r['scope'],r['policy'],r['width_s'],r['threshold_C'],r['direction'])==('m8','registered',policy,20,.2,d))
            assert abs(score-row['direction_accuracy_pct'])<1e-10;checks+=1
    assert Counter(r['family'] for r in f['worsening'])=={'m8':9,'old':5};checks+=1
    report=(O/'REPORT_KO.md').read_text(encoding='utf-8');links=0
    for link in re.findall(r'\]\(([^)]+)\)',report):
        if link.startswith(('http:','https:','#')):continue
        assert (O/link.split('#')[0]).exists(),link;links+=1
    assessment='''# A24 방향 보완03 · 결과02 판정

동일실측71세션·원AP35~180초·22그룹/5outer/3inner·20초/±0.2℃에서상승방향73.98→90.24%,하강79.31→81.03%,유지92.59→92.59%다. 전체428창83.64→88.79%,균형81.96→87.96%이며온도MAE0.138360→0.111000℃(19.78%감소)다. 상승32오분류중20/하강24중2를회복했고유지에서는9회복/9새오분류가상쇄됐다. 하강22오분류와개별MAE악화최근9/과거5세션이남는다.

V1의54/56상승하강오분류는유지였고50/56은0.3℃이하작은변화였다. 상승13창은작업종료경계/4창은종료뒤다. 양의병렬1차상태만으로지연피크를표현하기어려워AP반응상태를추가했다. 최근모든outer와최종선정은5초이며물리원인·유일시간상수식별은아니다.

방향벌점도검토했으나주개선은AP반응상태였다. matched제거에서벌점의추가효과는거의없고최종최근모형은벌점0이다. 첫구현01의손실합/평균규모불일치를수정한02가01보다모든지표에서우수한것도아니다(01전체89.02%,02 88.79%). 01의309fit/결과/원소스와02의200fit/109고정모형재사용을모두보존했다. 결과를보고최고변형만골라주표로바꾸지않았다.

과거35는별도계수/계약이며MAE0.418705→0.396188℃,상승66.67→76.58/하강53.39→74.58%는개선됐으나유지97.22→91.36%는악화했다. 전체창·민감도·그룹/최악/악화를전량보존했다.

연속온도/평가문턱/표본/초기정보/분할불변이다. outer그룹의target은모든적합·선정에서제외하고OOF와최종전체자료모형을분리했다. Python행렬/직접식/JS runtime106세션최대T차6.61e−13℃·적분8.88e−10℃·초/미래target변경불변/clone·복원·분할검산PASS다. 이것은새독립실측정확도인증이아니다.

최근관측AP26~31℃/145초밖,장기600초·CPU3/D_GPU·절대J·열→시간/종단간정책효과는미검증이다. 기존기본물리/BC/정책결과는보존하고새선택형factory만제공했다. 새정책환경/BC/PPO/실측/ADB/게시0·공유잠금반환·HEAD ac3a5af+미커밋이다.

정본: ../../results/A24_THERMAL_DIRECTION_20261021_02/REPORT_KO.md
다음: 새독립확인규약 또는 요청된새모형의후속평가. 남은하강오분류를완전해결로쓰지않는다.
'''
    (V/'ASSESSMENT_KO.md').write_text(assessment,encoding='utf-8',newline='\n')
    controls=[R/'docs/PROJECT_STATUS.md',R/'docs/PROJECT_PLAN.md',R/'docs/DECISIONS.md',A/'docs/LATEST_EXECUTION_FILES.md'];backup=V/'control_docs_before_direction';backup.mkdir(exist_ok=False)
    for p in controls:
        original=p.read_bytes();(backup/p.name).write_bytes(original)
        link='../a24_simulator/results/A24_THERMAL_DIRECTION_20261021_02/REPORT_KO.md' if p.parent==R/'docs' else '../results/A24_THERMAL_DIRECTION_20261021_02/REPORT_KO.md'
        top=f'''## 2026-10-21 A24-THERMAL-DIR-03 · 방향 오분류 원인·보완·동일조건 재검증 완료

[보고서]({link}). 같은71세션/원AP35~180초·5outer/3inner·±0.2℃에서 상승방향73.98→90.24%,하강79.31→81.03%,유지92.59%동일·전체83.64→88.79%다. 온도MAE0.138→0.111℃로줄었으나하강22오분류/개별MAE악화최근9·과거5가남는다. 주원인은AP반응지연상태추가이며최근최종선정5초/방향벌점0이다. 방향벌점의추가이득이확인됐다고쓰지않는다.

첫구현01의기본손실합/방향평균규모불일치를02에서수정했다.01의309fit/결과/원소스와02의200fit/109고정벌점0모형재사용을보존하며01대비02의작은손해도공개했다. 과거35는별도계수로MAE.419→.396℃/상승하강개선·유지악화다. 평가문턱/원표본/분할은불변이고OOF/배포모형·모든제거진단/민감도/악화를구분했다.

Python직접식/JS runtime전량수치·그룹/재사용/미래target비사용검산PASS를새독립실측인증으로쓰지않는다. 관측26~31℃/145초밖·장기/CPU3/D_GPU/절대J/종단간정책미검증이다. 기존shared기본물리/BC/결과보존·새선택형factory저장,새정책환경/실측/ADB/게시0·공유잠금반환·HEAD ac3a5af+미커밋이다. 다음: 새독립확인규약또는요청된후속비교. 아래는이전작업이력이다.

'''
        p.write_bytes(top.encode('utf-8')+original)
    write(V/'CHECKS.json',{'status':'PASS_SAVED_RESULTS_CONSISTENT','checks':checks,'local_links_checked':links,'PNG_figures_visually_checked':2,'figure_exports':4,
        'control_docs':[pin(p) for p in controls],'post_final_source':pin(H/'finalize.py'),'physical_accuracy_certified':False,'new_fits':0})
    folders=[H,H.parent/'a24_thermal_direction_20261021',O,FIRST,V]
    paths=sorted({p for folder in folders for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    write(V/'FINAL_PROOF.json',{'utc':datetime.now(timezone.utc).isoformat(),'status':'DIRECTION_REPAIR_AND_REPORT_COMPLETE','files':[pin(p) for p in paths],
        'original_source_pins':reg['sources'],'completed_first_variant_preserved':True,'fit01':309,'fit02':200,'policy_environments':0,'new_measurements':0,'fresh_confirmation':False})
    print(json.dumps({'status':'FINAL_COMPLETE','checks':checks,'links':links,'sealed_files':len(paths),'report':str(O/'REPORT_KO.md')},ensure_ascii=False))
if __name__=='__main__':main()
