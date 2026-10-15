"""Create a readable offline overview from finished PC reports and public replay.

No fitting, device command, policy selection, threshold changes, or experiment.
Original confirmation and post-observation families remain separate throughout.
"""
import argparse
import csv
import html
import json
from pathlib import Path
import statistics

from d1_a24_measurement_report import save_csv
from d1_a24_revision02_suite import require

FAMILIES=[('ORIGINAL40','original40','원독립 확인'),('EXTRA4','extra4','안정 기준 개정4'),
          ('SUP12','supplement12','과거 실패 보완12'),('TRACE2','trace2','계측 경로 확인2'),
          ('NEW6','new6','새 공통 기준6')]
ARM_NAMES={('L64','BASE'):'저부하 · 직렬',('L64','PAIR_G'):'저부하 · 병행 허용',
    ('C252','CPU'):'분류 · CPU',('C252','GPU'):'분류 · GPU',('M128','BASE'):'혼합 · 직렬',
    ('M128','ORDER'):'혼합 · 납기순',('M128','PAIR_G'):'혼합 · 병행 허용',('M128','WAIT200'):'혼합 · 200ms 대기'}

def read_csv(p):
    with p.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))

def number(v):return float(v) if v not in (None,'') else None
def average(rows,key):
    vals=[number(r.get(key)) for r in rows if number(r.get(key)) is not None]
    return statistics.mean(vals) if vals else None
def fmt(v,digits=3):return '미판정' if v is None else f'{v:,.{digits}f}'
def escaped(v):return html.escape(str(v))

def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+escaped(s)+'</th>' for s in headers)+'</tr></thead><tbody>'+''.join(
        '<tr>'+''.join('<td>'+escaped(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def build(root):
    verification=json.loads((root/'public_reproduction/VERIFICATION.json').read_text(encoding='utf-8'))
    public=read_csv(root/'public_reproduction/reproduced_sessions.csv')
    require(len(public)==64 and verification['sessions']==64,'not the exact five registered families')
    require(verification['device_commands']==0 and verification['J_calibrated'] is False,'invalid PC summary')
    contract=json.loads((root/'PUBLIC_REPLAY_CONTRACT.json').read_text(encoding='utf-8'))
    source={s['public_event_replay_manifest']['session_id']:s['public_event_replay_manifest'] for s in contract['sessions']}
    counts=[]
    for key,folder,label in FAMILIES:
        rows=[r for r in public if r['family']==key]
        counts.append({'family':key,'name':label,'registered':len(rows),
            'normal':sum(r['normal_comparison_eligible']=='True' for r in rows),
            'failed_before_MAIN':sum(r['status'] in {'PRESTART_REJECT','FAILED_PRESERVED'} for r in rows),
            'not_attempted':sum(r['status'].startswith('NOT_ATTEMPTED') for r in rows),
            'planned_MAIN':sum(int(r['planned']) for r in rows),'completed_MAIN':sum(int(r['completed']) for r in rows),
            'pooled_with_original40':key=='ORIGINAL40'})
    save_csv(root/'family_counts.csv',counts)
    summary=[]
    original=[r for r in public if r['family']=='ORIGINAL40']
    for (recipe,arm),label in ARM_NAMES.items():
        rows=[r for r in original if (r['recipe'],r['arm'])==(recipe,arm)]
        normal=[r for r in rows if r['normal_comparison_eligible']=='True']
        covered=[r for r in normal if r['thermal_window_status']=='READOUT_WINDOW_COVERED']
        planned={task:sum(q['task']==task for r in rows for q in source[r['session_id']]['requests']) for task in ['C','D']}
        item={'recipe':recipe,'arm':arm,'name':label,'registered':len(rows),'normal':len(normal),
            'planned_MAIN':sum(int(r['planned']) for r in rows),'completed_MAIN':sum(int(r['completed']) for r in rows),
            'mean_session_urgent_P95_ms':average(normal,'C_response_P95_ms_service_successes'),
            'min_session_urgent_P95_ms':min((float(r['C_response_P95_ms_service_successes']) for r in normal),default=None),
            'max_session_urgent_P95_ms':max((float(r['C_response_P95_ms_service_successes']) for r in normal),default=None),
            'AP_eligible_sessions':len(covered),'mean_eligible_AP_c':average(covered,'mean_AP_c'),
            'mean_eligible_observed_peak_AP_c':average(covered,'observed_peak_AP_c'),'validated_energy_J':None}
        for task in ['C','D']:
            ontime=sum(int(r[task+'_on_time']) for r in normal)
            item[task+'_planned_all_registered']=planned[task];item[task+'_on_time']=ontime
            item[task+'_on_time_rate_all_registered']=ontime/planned[task] if planned[task] else None
        summary.append(item)
    save_csv(root/'original40_arm_summary.csv',summary)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=FontProperties(fname=r'C:\Windows\Fonts\malgun.ttf');plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False})
    fig,ax=plt.subplots(figsize=(11,5.4));names=[s['name'] for s in summary]
    for i,s in enumerate(summary):
        vals=[float(r['C_response_P95_ms_service_successes']) for r in original
            if (r['recipe'],r['arm'])==(s['recipe'],s['arm']) and r['normal_comparison_eligible']=='True']
        ax.scatter([i]*len(vals),vals,alpha=.65,s=32)
        ax.plot([i-.22,i+.22],[s['mean_session_urgent_P95_ms']]*2,color='#162b45',linewidth=2)
    ax.set_xticks(range(len(names)),names,rotation=30,ha='right');ax.set_ylabel('긴급 응답 P95 (ms, 각 정상 세션)')
    ax.set_title('원독립 확인: 점은 각 정상 세션, 가로선은 세션 P95 평균')
    ax.text(0,-.37,'실패·미실행은 P95 계산에서 분리하고 전체 예정 완료율의 분모에 포함함. 같은 요청 구조 반복이며 사용자 모집단 CI가 아님.',transform=ax.transAxes,fontsize=9)
    fig.subplots_adjust(bottom=.29);fig.savefig(root/'01_원확인_긴급응답.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for i,s in enumerate(summary):
        eligible=[r for r in original if (r['recipe'],r['arm'])==(s['recipe'],s['arm'])
            and r['normal_comparison_eligible']=='True' and r['thermal_window_status']=='READOUT_WINDOW_COVERED']
        vals=[float(r['mean_AP_c']) for r in eligible];peaks=[float(r['observed_peak_AP_c']) for r in eligible]
        axes[0].scatter([i-.1]*len(vals),vals,s=25,color='#267995',label='창 평균' if i==0 else None)
        axes[0].scatter([i+.1]*len(peaks),peaks,s=30,marker='x',color='#be7623',label='관측 최고' if i==0 else None)
        axes[1].bar(i,100*s['completed_MAIN']/s['planned_MAIN'],color='#277e9b')
    axes[0].set_ylabel('적격 창 AP 읽기값 (℃)');axes[0].set_title('AP 판정창 35~180초 / 공백 상한 10초');axes[0].legend()
    axes[1].set_ylabel('전체 예정 요청 대비 완료 (%)');axes[1].set_ylim(0,105);axes[1].set_title('실패·미실행 요청도 분모에 포함')
    for ax in axes:ax.set_xticks(range(len(names)),names,rotation=65,ha='right',fontsize=8)
    fig.tight_layout();fig.savefig(root/'02_원확인_AP와_전체완료.png',dpi=160);plt.close(fig)
    countrows=[[c['name'],c['normal'],c['registered'],c['failed_before_MAIN'],c['not_attempted'],f"{c['completed_MAIN']:,}/{c['planned_MAIN']:,}"] for c in counts]
    service=[[s['name'],f"{s['normal']}/{s['registered']}",fmt(s['mean_session_urgent_P95_ms'],1),
        fmt(100*s['C_on_time_rate_all_registered'],1)+'%',
        '해당 없음' if s['D_on_time_rate_all_registered'] is None else fmt(100*s['D_on_time_rate_all_registered'],1)+'%',
        f"{s['completed_MAIN']}/{s['planned_MAIN']}",fmt(s['mean_eligible_AP_c']),fmt(s['mean_eligible_observed_peak_AP_c']),s['AP_eligible_sessions']] for s in summary]
    newrows=[[ARM_NAMES.get((r['recipe'],r['arm']),r['arm']),r['status'],f"{r['completed']}/{r['planned']}",
        fmt(number(r.get('C_response_P95_ms_service_successes')),1),fmt(number(r.get('mean_AP_c'))),fmt(number(r.get('observed_peak_AP_c')),1),fmt(number(r.get('actual_overlap_s')),2)]
        for r in public if r['family']=='NEW6']
    links=''.join(f'<a class="pill" href="{folder}/index.html">{label} 상세·그림</a>' for _,folder,label in FAMILIES)
    doc='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>A24 밤샘 실측 최종 비교</title><style>
*{box-sizing:border-box}body{font-family:Malgun Gothic,system-ui,sans-serif;color:#183047;background:#eef3f7;margin:0;line-height:1.65}
main{max-width:1280px;margin:auto;padding:24px}header{background:#132d46;color:white;padding:28px;border-radius:16px}
h1{margin:0;font-size:28px}h2{margin-top:32px}section{background:white;padding:22px;margin:20px 0;border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px;border-bottom:1px solid #d9e3eb;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{background:#eaf1f7}.scroll{overflow-x:auto}
.pill{display:inline-block;background:#e7f0f8;color:#194a70;padding:7px 12px;border-radius:9px;margin:4px;text-decoration:none}img{width:100%;height:auto}code{background:#e9eef3;padding:2px 5px}.warning{border-left:5px solid #c78424;padding-left:14px}a{color:#126a96}small{color:#536879}</style>
<main><header><h1>A24 실제 요청 흐름: 최종 실측 묶음</h1><p>CPU/GPU · 분류/탐지 · 전체 예정 요청 보존 · 원확인과 추가 반복 분리</p></header>
<section><p class="warning"><b>응답·완료·HAL AP 읽기값을 비교합니다.</b> 검증된 에너지 J는 미판정이며 물리 표면 온도도 확인되지 않았습니다. 추가 반복을 원독립 확인의 성공으로 바꾸지 않았습니다.</p>'''
    doc+=table(['자료 역할','정상','등록','MAIN 전 실패','미실행','완료/예정 MAIN'],countrows)+links+'</section>'
    doc+='<section><h2>원독립 확인 40조건</h2><p>응답은 정상 세션별 P95의 평균이며, 전체 요청을 합친 P95가 아닙니다. 기한 내 완료율과 완료/예정 건수에는 호스트·시작 조건 실패와 미실행도 포함합니다. 열 평균과 최고값 평균은 적격 AP 창만 사용하며, 최고값 평균은 각 세션의 관측 최고 AP를 평균한 값입니다.</p>'
    doc+=table(['조건','정상/등록','긴급 P95 평균(ms)','긴급 기한 내','일반 기한 내','완료/예정','평균 AP(℃)','최고AP 평균(℃)','AP 적격'],service)
    doc+='<img src="01_원확인_긴급응답.png" alt="정상 세션의 긴급 응답 P95"><img src="02_원확인_AP와_전체완료.png" alt="AP 읽기값과 전체 예정 완료율"></section>'
    doc+='<section><h2>새 공통 시작 기준 6조건</h2><p>첫 적격 안정 구간에서 저부하·혼합 묶음별 기준을 각각 한 번 고정했습니다. 관측 후 추가한 단일 반복이며 원확인 5블록 CI에 합산하지 않습니다. 병행 시간은 앱 자원 점유 경계의 겹침이며 GPU 커널 동시성의 직접 증거가 아닙니다.</p>'
    doc+=table(['조건','원상태','완료/예정','긴급 P95(ms)','평균 AP(℃)','관측 최고AP(℃)','실제 점유 겹침(s)'],newrows)+'</section>'
    doc+='''<section><h2>해석과 재현</h2><p>분류 단독의 CPU/GPU 우열과 혼합 요청의 병행 이득은 다른 질문입니다. 실행 순서·자원 선택·대기를 분리해 읽어야 합니다. AP가 낮다는 이유만으로 전력·배터리 절감을 확정하지 않습니다.</p>
<p>입력은 승인된 한 이미지와 고정 도착 구조의 반복입니다. 새로운 독립 사용자·이미지 모집단, 새로운 RL 정책의 실기기 검증, 사전 수치 예측이 없던 8군의 독립 예측 정확도 검증을 뜻하지 않습니다. 임의 온도 한도를 만들지 않아 한도 초과 시간은 미판정입니다. 스케줄러 판단시간·기기 제어 에너지도 분리 계측되지 않았습니다.</p>
<p><a href="README.md">한국어 결과 보고서</a> · <a href="RAW_DATA_INDEX.md">묶음별 원자료 ZIP</a> · <a href="PUBLIC_REPLAY_CONTRACT.json">공개 재계산 계약</a> · <a href="public_reproduction/VERIFICATION.json">공개 ZIP 재현 검증</a> · <a href="original40_arm_summary.csv">8조건 요약 CSV</a> · <a href="family_counts.csv">실패 포함 원장 CSV</a></p>
<p>저장소 루트에서 <code>python -B tools/d1_a24_public_reproduce.py docs/results/a24_final_measurements_20261016/PUBLIC_REPLAY_CONTRACT.json output/a24_public_replay_new</code></p>
<p><small>오프라인 HTML. 외부 폰트·CDN·네트워크 요청 없음. 원자료는 SHA를 고정한 ZIP으로 보존하며 개인 식별 설정·모델·APK·승인 이미지·키·전체 시스템 로그의 제외를 명시합니다.</small></p></section></main></html>'''
    (root/'index.html').write_text(doc,encoding='utf-8')
    result={'families':counts,'registered':len(public),'normal':verification['normal'],
        'planned_MAIN':verification['all_planned_requests'],'completed_MAIN':verification['normal_completed_requests'],
        'quality_failures':verification['decoded_quality_failures'],'energy_J':None,'report_device_commands':0,
        'surface_temperature_verified':False,'experiment_ready':False}
    (root/'FINAL_COUNTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report_root',type=Path);a=p.parse_args();build(a.report_root)
