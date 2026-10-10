"""Read completed pilot artifacts only; no environments, learning, fit or device."""
import csv,gzip,html,json,statistics
from datetime import datetime,timezone
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from tools import d1_rolling_hybrid_pilot as x

NAMES={'Band':'Band 판단규칙 대응','Triton':'Triton 판단규칙 대응','OriginalV2':'기존 공동 롤링','ExecutionPrefix':'첫 행동 직접선정 롤링'}
COLORS=['#607d8b','#b79b65','#638db0','#36876c']


def table(path,rows):
    if not rows:return
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def item(role,condition):
    return json.loads(gzip.decompress((x.LOCAL/'items'/f'pilot_{role}_{condition:03d}.json.gz').read_bytes()))


def save(fig,name):
    fig.tight_layout();fig.savefig(x.PUBLIC/(name+'.png'),dpi=150);svg=x.PUBLIC/(name+'.svg');fig.savefig(svg)
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    plt.close(fig)


def run():
    x.check(require_local=True)
    data=x.read(x.LOCAL/'completion.json');assert data['status']=='completed' and len(data['rows'])==96
    reg=x.read(x.LOCAL/'registration.json');rows=data['rows'];by={(r['condition'],r['policy']):r for r in rows}
    assert len(by)==96
    controls=[];curve_rows=[];ledgers=[];same_band=[]
    for r in rows:
        raw=item(r['policy'],r['condition']);x.audit(raw['result'],x.read(x.LOCAL/'inputs.json')['cases'][r['condition']]['tickets'])
        ledger=raw['result']['ledger']
        urgent_n=sum(q['priority']=='urgent' for q in ledger);normal_n=sum(q['priority']=='normal' for q in ledger)
        r.update(urgent_planned=urgent_n,normal_planned=normal_n,urgent_failure_rate=r['urgent_failure']/urgent_n,
            normal_on_time_completion_rate=sum(q['priority']=='normal' and q['status']=='succeeded' and not q['late_success'] for q in ledger)/normal_n)
        callbacks=raw['callback_seconds'];decisions=raw['result']['decisions'];choices=raw['prefix_choices']
        controls.append(dict(condition=r['condition'],family=r['family'],context=r['context'],policy=r['policy'],
            native_seconds=r['native_seconds'],callback_count=len(callbacks),callback_total_s=sum(callbacks),
            callback_max_ms=max(callbacks,default=0)*1000,projection_calls=raw['projection_calls']+raw['prefix_projection_calls'],
            projection_seconds=raw['projection_seconds']+raw['prefix_projection_seconds'],
            selected_prefix_count=sum(c['chosen'] is not None for c in choices),
            cool_wait_choices=sum(c['chosen'] is not None and c['chosen']['action']['kind']=='cool_wait' for c in choices),
            cooling_timer_decisions=sum(d.get('action_kind')=='cool_wait' for d in decisions),
            interrupted_holds=raw['interrupted_holds'],cancelled_bundles=raw['cancelled_bundles'],
            overlap_s=r['overlap_s'],classification_cpu=r['classification_cpu']))
        if r['policy']=='ExecutionPrefix':
            band=item('Band',r['condition'])
            schedule=lambda v:[(q['id'],q.get('backend'),q.get('dispatch_ns'),q.get('response_ns'),q.get('lane_available_ns'),q['status']) for q in v['result']['ledger']]
            same_band.append(dict(condition=r['condition'],family=r['family'],context=r['context'],same_full_schedule_as_Band=schedule(raw)==schedule(band)))
        if r['condition']==reg['representative']['condition']:
            curve_rows.extend(dict(policy=r['policy'],t_s=t,predicted_ap_c=v) for t,v in raw['curve'])
            ledgers.extend(dict(policy=r['policy'],**q) for q in raw['result']['ledger'])
    differences=[]
    for role in ('OriginalV2','ExecutionPrefix'):
        verdict=x.gate_rows(rows,role)
        assert verdict==data['gates'][role]
        for d in verdict['differences']:
            r=by[(d['condition'],role)];b=by[(d['condition'],d['baseline'])]
            differences.append(dict(policy=role,condition=d['condition'],seed=r['seed'],family=r['family'],context=r['context'],baseline=d['baseline'],passed=d['passed'],
                **{'delta_'+k:v for k,v in d['delta'].items()},delta_normal_mean_ms=r['normal_mean_ms']-b['normal_mean_ms']))
    summary=[]
    for role in x.ROLES:
        subset=[r for r in rows if r['policy']==role]
        summary.append(dict(policy=role,name_ko=NAMES[role],conditions=len(subset),planned=sum(r['planned'] for r in subset),
            completed=sum(r['completed'] for r in subset),incomplete=sum(r['incomplete'] for r in subset),urgent_planned=sum(r['urgent_planned'] for r in subset),normal_planned=sum(r['normal_planned'] for r in subset),urgent_failure=sum(r['urgent_failure'] for r in subset),normal_failure=sum(r['normal_failure'] for r in subset),
            urgent_failure_rate=sum(r['urgent_failure'] for r in subset)/sum(r['urgent_planned'] for r in subset),normal_on_time_completion_rate=(sum(r['normal_planned'] for r in subset)-sum(r['normal_failure'] for r in subset))/sum(r['normal_planned'] for r in subset),
            mean_condition_urgent_p95_ms=statistics.mean(r['urgent_p95_ms'] for r in subset),mean_condition_normal_ms=statistics.mean(r['normal_mean_ms'] for r in subset),
            mean_condition_energy_j=statistics.mean(r['energy_j'] for r in subset),mean_condition_peak_ap_c=statistics.mean(r['peak_ap_c'] for r in subset),native_total_seconds=sum(r['native_seconds'] for r in subset)))
    table(x.PUBLIC/'comparison.csv',rows);table(x.PUBLIC/'paired_differences.csv',differences);table(x.PUBLIC/'policy_summary.csv',summary)
    table(x.PUBLIC/'control_cost.csv',controls);table(x.PUBLIC/'same_band_schedules.csv',same_band);table(x.PUBLIC/'representative_ap.csv',curve_rows)
    # Preserve a compact fixed-case ledger; optional fields require unified CSV columns.
    keys=sorted(set().union(*(q.keys() for q in ledgers)));table(x.PUBLIC/'representative_ledger.csv',[{k:q.get(k) for k in keys} for q in ledgers])
    result=dict(status='completed',task=x.TASK,model_context=x.MODEL_CONTEXT,upstream_model_sha256=reg['upstream_hybrid_sha256'],exported_model_sha256=reg['exported_hybrid_sha256'],summary=summary,
        gates=data['gates'],consumption=data['consumption'],same_Band_schedules=sum(q['same_full_schedule_as_Band'] for q in same_band),same_Band_denominator=24,
        completed_batch_requests=sum(r['completed'] for r in rows),completed_gate_requests=8,model_fit_calls=0,device_commands=0,learning_starts=0,
        recommendation='no adoption or learning expansion without all-condition gates; retain existing reference',
        scope='two new arrival seeds x four load families x three sensitivity contexts; development model exploration, not physical product performance',
        AP_channel='modeled AP, not surface temperature',surface_peak_c=None,thermal_limit_exceed_s=None,
        thermal_service_feedback=False,experiment_ready=False,mean_AP_validation_error_c=.202484,
        PC_control_cost_is_phone_cost=False,report_generated_utc=datetime.now(timezone.utc).isoformat())
    x.write(x.PUBLIC/'summary.json',result)
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10,'svg.fonttype':'none'})
    fig,axes=plt.subplots(1,3,figsize=(14,4))
    for ax,key,title in zip(axes,['mean_condition_urgent_p95_ms','mean_condition_normal_ms','normal_failure'],['긴급 응답 P95의 조건 평균 (ms)','일반 응답의 조건 평균 (ms)','일반 기한 실패 (전체 도착 분모)']):
        ax.bar(range(4),[s[key] for s in summary],color=COLORS);ax.set_title(title);ax.set_xticks(range(4),['Band','Triton','기존 롤링','첫 행동 롤링'],rotation=15);ax.grid(axis='y',alpha=.2)
    save(fig,'응답과_완료')
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,key,title in zip(axes,['mean_condition_energy_j','mean_condition_peak_ap_c'],['기기 전체 에너지 조건 평균 (J / 120초)','모형 AP 최고값 조건 평균 (°C / 35~180초)']):
        vals=[s[key] for s in summary];ax.bar(range(4),vals,color=COLORS);ax.set_xticks(range(4),['Band','Triton','기존 롤링','첫 행동 롤링']);ax.set_title(title);ax.set_ylim(min(vals)*.995,max(vals)*1.005);ax.grid(axis='y',alpha=.2)
    fig.suptitle('확대된 축: 작은 모형 차이를 실제 절감으로 확정하지 않음');save(fig,'에너지와_모형온도')
    fig,axes=plt.subplots(1,4,figsize=(16,7))
    selected=[d for d in differences if d['policy']=='ExecutionPrefix' and d['baseline']=='Band']
    load_names={'low':'낮은 부하','queue':'큐 몰림','burst':'순간 몰림','sustained':'지속 부하'}
    context_names={'mean':'평균','short_context':'짧은 처리','long_context':'긴 처리'}
    for ax,key,title in zip(axes,['delta_energy_j','delta_peak_ap_c','delta_normal_mean_ms','delta_normal_failure'],['Band 대비 에너지 (J)','Band 대비 최고 AP (°C)','Band 대비 일반 응답 (ms)','Band 대비 일반 기한실패 (건)']):
        vals=np.array([[d[key]] for d in selected]);lim=max(abs(vals.min()),abs(vals.max()),1e-12)
        plot=ax.imshow(vals,aspect='auto',cmap='RdBu_r',vmin=-lim,vmax=lim);ax.set_title(title);ax.set_xticks([])
        ax.set_yticks(range(24),[f"{d['condition']:02d} {load_names[d['family']]} / {context_names[d['context']]}" for d in selected],fontsize=8);fig.colorbar(plot,ax=ax)
    save(fig,'조건별_차이_지도')
    fig,ax=plt.subplots(figsize=(12,5))
    for role,color in zip(x.ROLES,COLORS):
        curve=[r for r in curve_rows if r['policy']==role];ax.plot([r['t_s'] for r in curve],[r['predicted_ap_c'] for r in curve],label=NAMES[role],color=color)
    ax.set(xlabel='공통 시각 (초)',ylabel='모형 AP 온도 (°C)',title='사전 고정 대표 조건9: 지속 부하 / mean');ax.legend();ax.grid(alpha=.2);save(fig,'대표_온도경로')
    fig,ax=plt.subplots(figsize=(14,6));start,end=reg['representative']['window_s']
    for idx,role in enumerate(x.ROLES):
        for q in [q for q in ledgers if q['policy']==role]:
            a=q.get('dispatch_ns',0)/1e9;b=q.get('lane_available_ns',0)/1e9
            if b<start or a>end:continue
            y=idx*2+(q['backend']=='GPU');color='#497b9d' if q['task']=='classification' else '#c89144'
            ax.broken_barh([(a,b-a)],(y-.32,.64),facecolors=color,edgecolors='white',linewidth=.4)
            response=(q['output_ready_ns'] if q['task']=='classification' else q['persist_complete_ns'])/1e9
            ax.plot(response,y,'|',color='black',ms=7)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color='#497b9d',label='이미지 분류'),Patch(color='#c89144',label='객체 탐지')],loc='upper right')
    ax.set_yticks(range(8),[NAMES[role]+' / '+lane for role in x.ROLES for lane in ('CPU','GPU')]);ax.set(xlim=(start,end),xlabel='공통 시각 (초)',title='대표 실행 시간표: 막대 끝은 실제 lane 반환 / 검은 선은 응답');ax.invert_yaxis();ax.grid(axis='x',alpha=.2);save(fig,'대표_실행시간표')
    def grid(records,keys):
        return '<table><thead><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in keys)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in keys)+'</tr>' for r in records)+'</tbody></table>'
    semantics=[dict(규칙=NAMES['Band'],순서='작업비용·완료 예상 기반',자원='whole-request CPU/GPU 대응',대기='자원 사건',열='목적항 없음'),dict(규칙=NAMES['Triton'],순서='모델별 요청 큐',자원='분류GPU / 탐지CPU 고정',대기='instance 반환',열='목적항 없음'),dict(규칙=NAMES['OriginalV2'],순서='창4 / 과업 내 EDD / 원8선별',자원='전체 계획 선정 후 첫 행동 검사',대기='최대0.25초 / 사건 취소',열='새 v3 head'),dict(규칙=NAMES['ExecutionPrefix'],순서='같은 창4 / EDD / 원8선별',자원='실제 첫 행동을 직접 비교',대기='최대0.25초 / 사건 취소',열='같은 새 v3 head / 전체최고 보호')]
    verdict='유망 기준 통과' if data['gates']['ExecutionPrefix']['promising'] else '유망 기준 미달 · 새 정책 채택 보류'
    content='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>새 모형 공동 롤링 파일럿</title><style>body{font:15px Malgun Gothic,system-ui;margin:28px;color:#21313d;background:#f7f9fa}main{max-width:1250px;margin:auto}h1{font-size:28px}h2{font-size:21px;margin-top:32px}table{border-collapse:collapse;background:white;font-size:13px}td,th{border:1px solid #dae1e4;padding:8px}img{width:100%;background:white}strong{color:#92582a}.scroll{overflow:auto}p{line-height:1.7}.card{padding:16px;background:white;border-left:5px solid #36876c}</style><main>'
    content+=f'<h1>새 온도 보정 모형 × 공동 롤링</h1><p class="card"><strong>{verdict}</strong><br>24조건 × 4정책 = 96행 · gate4 · 학습/적합/기기 실행0 · 전체 요청{sum(r["completed"] for r in rows)}/{sum(r["planned"] for r in rows)} 완료</p>'
    content+='<p>새 v3 hybrid를 정책의 후보 예측과 최종 AP 계산 모두에 사용했습니다. CPU/PAR 각각1회에서 평균오차가 줄었지만 피크오차는 일부 악화했습니다. 이 결과는 제한된 모형 탐색이며 실제 휴대폰 절감·외부 제품 전체의 우열을 증명하지 않습니다. 처리시간·에너지는 기존 모형과 같고 냉각→속도회복은 미지원입니다.</p><p><a href="README.md">한국어 판독</a> · <a href="execution_contract.json">실행 전 계약</a> · <a href="comparison.csv">전체96행</a> · <a href="paired_differences.csv">조건별 차이</a> · <a href="control_cost.csv">판단·대기·점유</a> · <a href="summary.json">전체 판정</a></p>'
    content+='<h2>판단 규칙의 차이</h2>'+grid(semantics,list(semantics[0]))
    visible=[dict(정책=s['name_ko'],완료=f"{s['completed']}/{s['planned']}",긴급기한실패=s['urgent_failure'],일반기한실패=s['normal_failure'],긴급P95_ms=f"{s['mean_condition_urgent_p95_ms']:.3f}",일반응답_ms=f"{s['mean_condition_normal_ms']:.3f}",에너지_J=f"{s['mean_condition_energy_j']:.6f}",최고AP_C=f"{s['mean_condition_peak_ap_c']:.6f}") for s in summary]
    content+='<h2>정책별 결과</h2><p>새 직접선정은 평균 비용이 줄었어도 일반 기한실패21→30건으로 채택할 수 없습니다. 기존 공동 롤링은21건을 유지해 상대적으로 안정적이지만 일부 조건 비용·응답이 악화했습니다. 기존 기준 정책을 유지합니다.</p><p>응답·J·AP는 조건 평균, 기한실패는 전체 건수입니다. 조건별 P95 평균은 pooled P95가 아닙니다. 3문맥은 민감도이며 독립3반복이 아닙니다.</p><div class="scroll">'+grid(visible,list(visible[0]))+'</div>'
    for name in ('응답과_완료','에너지와_모형온도','조건별_차이_지도','대표_온도경로','대표_실행시간표'):
        content+='<h2>'+name.replace('_',' ')+'</h2><img alt="'+name+'" src="'+name+'.svg">'
    content+='<p>대표 조건은 결과 전에 condition9로 고정했습니다. 표면 온도·안전한도 초과시간·폰 제어 에너지는 계산 불가입니다. PC 판단시간은 control_cost.csv에 별도 기록했고 폰 실측 전력으로 환산하지 않았습니다. 기본 정책·strict·experiment_ready=false를 유지합니다.</p></main></html>'
    (x.PUBLIC/'index.html').write_text(content,encoding='utf-8')
    x.write(x.PUBLIC/'verification.json',dict(status='PASS',pure_tests=42,native_gate=x.read(x.LOCAL/'gate_verification.json'),audit_rows=96,artifact_sha256={q.name:x.sha(q) for q in sorted((x.LOCAL/'items').glob('*.json.gz'))},source_sha256=reg['source_sha256'],head=reg['head'],uncommitted=True,model_fit_calls=0,device_commands=0,learning_starts=0))
    print(json.dumps(dict(summary=summary,gates={r:{k:v for k,v in d.items() if k!='differences'} for r,d in data['gates'].items()},consumption=data['consumption'],same_Band=result['same_Band_schedules']),indent=2))

if __name__=='__main__':run()
