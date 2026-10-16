"""Read-only historical forecast audit for the three-AI rolling review.

No native simulator, policy rollout, new plant forecast, learner, or device
imports. This recounts existing conditional forecasts, not policy performance.
"""
import argparse,csv,gzip,hashlib,json,subprocess
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_rolling_prefix_selection as prototype
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'docs/results/rolling_prefix_01/prefix_guard_events.json.gz'
SOURCE_SHA='53cc3298422352ab76ccc1eb499ba3b45e442d825e2d2bede669a6ad3a40f207'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def audit(output):
    assert sha(SOURCE)==SOURCE_SHA,'existing diagnostic changed'
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    events=json.loads(gzip.decompress(SOURCE.read_bytes()));rows=[];counts=Counter();examples=[]
    for row in events:
        if not row['identity'].startswith('development/'):continue
        passed=row['passed'];counts['development_records']+=1;counts['passed']+=passed
        values={}
        if passed:
            assert all(row['first'][c]['valid'] and row['references'][c]['valid'] for c in prototype.CONTEXTS)
            for label,key in [('future','peak_ap_c'),('global','global_peak_ap_c'),('J','remaining_increment_j')]:
                values[label]=max(row['first'][c][key]-row['references'][c][key] for c in prototype.CONTEXTS)
            f=values['future']<-prototype.EPS;g=values['global']<-prototype.EPS;j=values['J']<-prototype.EPS
            only=f and abs(values['global'])<=prototype.EPS and abs(values['J'])<=prototype.EPS
            counts['future_strict']+=f;counts['global_strict']+=g;counts['J_strict']+=j
            counts['global_or_J_strict']+=g or j;counts['future_only_global_J_tie']+=only
            if only and len(examples)<1:examples.append(dict(identity=row['identity'],at_s=row['now_ns']/1e9,deltas=values))
        else:f=g=j=only=False
        rows.append(dict(identity=row['identity'],at_s=row['now_ns']/1e9,passed=passed,
            future_delta_ap_c=values.get('future'),global_delta_ap_c=values.get('global'),delta_increment_j=values.get('J'),
            future_strict=f,global_strict=g,J_strict=j,future_only_global_J_tie=only,
            evidence='saved original prefix projection; wait semantics unverified; no new policy execution'))
    assert (counts['development_records'],counts['passed'],counts['future_strict'],counts['global_strict'],counts['J_strict'],counts['future_only_global_J_tie'])==(655,633,289,208,2,81)
    with (output/'historical_forecast_audit.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    protected=['tools/d1_rolling_joint_thermal.py','tools/d1_rolling_prefix_guard.py','tools/d1_fast_thermal_forecast.py','tools/d1_rolling_terminal.py',
        'docs/results/online_policy_study_01/overnight_sustained_run01/model.json','docs/results/online_policy_study_01/overnight_sustained_run01/initial_inputs.json']
    result=dict(task='ROLLING-EXPERT-REVIEW-04',status='historical_audit_and_unconnected_prototype',utc=datetime.now(timezone.utc).isoformat(),
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,source_sha256=sha(SOURCE),
        development_only=True,confirmation_records_not_used=len(events)-len(rows),counts=dict(counts),example=examples,
        source_files={p:sha(ROOT/p) for p in protected},prototype_version=prototype.VERSION,
        prototype_source_sha256={p:sha(ROOT/p) for p in ['tools/d1_rolling_prefix_selection.py','tools/test_d1_rolling_prefix_selection.py','tools/d1_rolling_expert_review.py']},
        native_environment_starts=0,new_model_projections=0,learning_starts=0,device_commands=0,
        cumulative_policy_environment_starts=9749,cumulative_policy_learning_starts=1449,
        previous_IE_cap_spent=480,previous_IE_cap=480,budgets_reopened=False,
        alternative_prefix_opportunity='unknown; all alternative-prefix forecasts absent from saved evidence',
        online_policy_connected=False,policy_performance_claim=False,small_difference_is_physical_gain=False)
    write(output/'verification.json',result)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=Path('C:/Windows/Fonts/malgun.ttf')
    if font.exists():plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False
    fig,ax=plt.subplots(figsize=(10,4.5))
    labels=['미래 AP 감소','전체 최고 AP 감소','에너지 감소','미래 AP만 감소\n전체 최고·에너지 유지']
    ax.bar(labels,[289,208,2,81],color=['#7998b1','#33786c','#33786c','#c68132'])
    for i,v in enumerate([289,208,2,81]):ax.text(i,v+4,str(v),ha='center')
    ax.set_ylim(0,330);ax.set_ylabel('저장된 판단 기록 수');ax.set_title('개발 통과633판단의 기존 예측값 재집계 · 새 성능 실험 아님')
    fig.text(.5,.01,'앞의 세 항목은 중복 가능. 81건은 전체 최고 AP·J 동률. 실제 대기 의미·새 정책 효과 미검증.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.04,1,1));fig.savefig(output/'01_미래온도와_전체최고의_차이.png',dpi=160);plt.close(fig)
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>공동 롤링 전문가 검토</title>
<style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:0 16px;line-height:1.65}img{max-width:100%}td,th{padding:9px;border:1px solid #ddd}table{border-collapse:collapse}</style>
<h1>공동 롤링: 실제 첫 행동을 직접 비교하는 보완</h1>
<p>세 AI가 두 라운드에서 합의한 설계와 순수 선택기 검증. 정책 미연결·새 환경/예측/학습/기기0회. 실제 개선은 아직 미확정.</p>
<table><tr><th>관점</th><th>반론과 반영</th></tr><tr><td>모바일</td><td>대기는 미래 작업 배정을 확정하지 않음. 실제 대기·취소 의미가 맞는 예측만 허용.</td></tr>
<tr><td>산업공학</td><td>전체 계획 1등 하나 대신 같은8후보의 실행 첫 행동별로 선택. 전체 최고 AP와 에너지로 평가.</td></tr>
<tr><td>RL</td><td>유효한 대안 선택 기회부터 확인. 순수 검사 통과를 정책 성과·RL 필요성으로 표시하지 않음.</td></tr></table>
<p><a href="README.md">회의·계산식·미완료</a> · <a href="historical_forecast_audit.csv">개발655판단 CSV</a> · <a href="verification.json">근거와 검증</a></p>
<img src="01_미래온도와_전체최고의_차이.png" alt="기존 개발 예측의 미래 AP 감소와 전체 최고 AP 개선 구분">
<p>개발 통과633 중 미래 AP 감소289, 전체 최고 AP 감소208, 에너지 감소2, 미래만 감소81. 원 대기 예측의 실행 의미는 별도 검증 대상이며 81회 실행을 제거했다는 결과가 아니다.</p>
<p>다음은 최대8개 개발 상태의 공개 입력 복원·대안 첫 행동 예측 진단이다. 별도 등록 전에는 실행하지 않으며 기존 확인자료를 새 독립 확인으로 쓰지 않는다.</p></html>'''
    (output/'index.html').write_text(page,encoding='utf-8',newline='\n')
    return result
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args();print(json.dumps(audit(args.output),ensure_ascii=False,indent=2))
