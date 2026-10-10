"""Meeting-only offline authoring from completed, source-linked evidence.

No simulation, learning, fitting, ADB, installation or network calls. Drafts
stay private. --final requires terminal RL/device evidence or an explicit root
terminal-status note with a real source, never inventing missing outcomes.
"""
from __future__ import annotations
import argparse,csv,hashlib,html,json,math,os,re,statistics,subprocess
from html.parser import HTMLParser
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'docs/results/overnight_meeting_20261011'
DRAFT=ROOT/'output/overnight_meeting_20261011_draft'
VERSION='overnight-meeting-evidence-v1'
IE='docs/results/overnight_ie_20261011'
FLEX='docs/results/overnight_ie_flex_20261011'
RL='docs/results/overnight_rl_20261011'
DEVICE='docs/results/overnight_device_20261011'
REFERENCE='docs/results/overnight_reference_gap_20261011'
MODEL='docs/results/simulation_model_v3_expert_01/hybrid_v2'
SHARED_MODEL='docs/results/rolling_hybrid_pilot_07/model.json'
PILOT='docs/results/rolling_list_rl_pilot_08'
TERMINAL={'completed','blocked','stopped','partial','budget_stopped'}
CORE_SLIDES=(1,3,4,6,7,8,10,13,14,15)
E=html.escape

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def number(value,digits=3,signed=False):
    if value is None:return '미확정'
    if not math.isfinite(float(value)):raise ValueError('nonfinite evidence')
    return format(float(value),('+' if signed else '')+f'.{digits}f')
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

class Evidence:
    def __init__(self,folder):self.folder=folder;self.sources={}
    def path(self,relative):
        p=(ROOT/relative).resolve()
        if not p.is_relative_to(ROOT):raise ValueError('source must remain in repository workspace')
        return p
    def record(self,relative,required=True):
        p=self.path(relative)
        if not p.exists():
            if required:raise FileNotFoundError(relative)
            return None
        self.sources[p.relative_to(ROOT).as_posix()]=dict(sha256=sha(p),bytes=p.stat().st_size)
        return p
    def json(self,relative,required=True):
        p=self.record(relative,required);return json.loads(p.read_text(encoding='utf-8')) if p else None
    def csv(self,relative,required=True):
        p=self.record(relative,required)
        if not p:return None
        with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    def link(self,relative,label=None):
        self.record(relative)
        url=os.path.relpath(self.path(relative),self.folder).replace('\\','/')
        return f'<a href="{E(url,quote=True)}">{E(label or relative)}</a>'
    def cite(self,*paths):return '<div class="source">근거: '+' · '.join(self.link(p) for p in paths)+'</div>'

def normalize_status(value):
    if value and str(value).startswith('completed'):return 'completed'
    if value and str(value).startswith('stopped'):return 'stopped'
    if value in TERMINAL:return value
    return 'in_progress'

def model_snapshot(evidence):
    local=evidence.path(MODEL+'/summary.json');shared=PUBLIC/'supporting_evidence/model_validation.json'
    if local.exists():
        raw=json.loads(local.read_text(encoding='utf-8'));mode=raw['comparison']['modes']['B_fixed_original_service'];cost_file=evidence.path(MODEL+'/cost_scores.csv')
        with cost_file.open(encoding='utf-8-sig',newline='') as f:
            cpu={q['model']:q for q in csv.DictReader(f) if q['mode']=='B_fixed_original_service' and q['policy']=='CPU_URGENT_ONLINE_V1'}
        return dict(version='sanitized-model-forward-validation-v1',
            original_local_provenance=dict(repository_relative_path=MODEL+'/summary.json',sha256=sha(local),original_file_shared=False,cost_scores_relative_path=MODEL+'/cost_scores.csv',cost_scores_sha256=sha(cost_file)),
            frozen_model=dict(shared_path=SHARED_MODEL,sha256=sha(evidence.path(SHARED_MODEL))),
            comparison=dict(primary_mode='B_fixed_original_service',modes=dict(B_fixed_original_service=dict(overall=mode['overall'],by_policy=mode['by_policy'])),
                scope=raw['comparison']['scope'],validated_sessions=raw['comparison']['validated_sessions'],original_V3_joint_pass=raw['comparison']['original_V3_joint_pass']),
            confirmed_completed_requests=raw['confirmed_completed_requests'],confirmed_timely_requests=raw['confirmed_timely_requests'],
            limitations=dict(surface_temperature_verified=False,thermal_service_feedback=False,absolute_energy_calibrated=False,
                sessions_per_policy=1,CPU_max_error_original_c=float(cpu['original']['max_absolute_error_c']),CPU_max_error_hybrid_c=float(cpu['hybrid']['max_absolute_error_c']),CPU_peak_error_original_c=float(cpu['original']['peak_abs_error_c']),CPU_peak_error_hybrid_c=float(cpu['hybrid']['peak_abs_error_c'])),
            interpretation='original local numeric result extracted without raw/private paths; thermal head only, original service/energy identity; not policy saving')
    if shared.exists():return evidence.json(shared.relative_to(ROOT).as_posix())
    raise FileNotFoundError('model validation snapshot unavailable; preserve original source or shared supporting_evidence')

def detect_results(evidence,overlay):
    old=evidence.json(PILOT+'/summary.json')
    ie=evidence.json(IE+'/summary.json');flex=evidence.json(FLEX+'/summary.json')
    model=model_snapshot(evidence)
    rl=evidence.json(RL+'/result.json',False)
    device=evidence.json(DEVICE+'/summary.json',False)
    states=dict(rl=dict(status='in_progress',reason='같은 learner 연장과 새 확인 결과가 아직 확정되지 않았습니다.'),
                device=dict(status='in_progress',reason='동결 일정 ABBA 실측 결과가 아직 확정되지 않았습니다.'))
    if rl and rl.get('verification',{}).get('status')=='PASS':
        assert all(q['completed']==q['planned'] for q in rl['summary'])
        if not any(q['scope']=='confirmation' and q['policy'].startswith('PPO') for q in rl['summary']):raise ValueError('RL final comparison missing')
        states['rl']=dict(status='completed',reason='동일 learner 연장·새 확인·원장 검증 완료',source=RL+'/result.json')
    if device:
        device_status=normalize_status(device.get('status'))
        if device_status=='completed' and not all(evidence.path(DEVICE+'/'+f).exists() for f in ('requests.csv','pairs.csv')):device_status='in_progress'
        states['device']=dict(status=device_status,reason='실측 수집 상태와 정책 우월성은 별도 판정',source=DEVICE+'/summary.json')
    if not overlay and (PUBLIC/'evidence_snapshot.json').exists():
        archived=evidence.json((PUBLIC/'evidence_snapshot.json').relative_to(ROOT).as_posix())
        for name in ('rl','device'):
            old_state=archived['states'].get(name,{})
            if states[name]['status']=='in_progress' and old_state.get('status') in TERMINAL and old_state.get('terminal_note_source'):
                overlay[name]=dict(status=old_state['status'],reason=old_state['reason'],source=old_state['terminal_note_source'])
    for name in ('rl','device'):
        custom=overlay.get(name)
        if not custom:continue
        status=custom.get('status')
        if status not in TERMINAL|{'in_progress'}:raise ValueError('invalid status '+name)
        source=custom.get('source');proof=evidence.json(source) if source else None
        if not proof:raise ValueError('explicit terminal note requires source JSON')
        if status=='completed' and states[name]['status']!='completed':raise ValueError('overlay cannot turn incomplete experiment into completed')
        if status!='completed' and not custom.get('reason'):raise ValueError('terminal limitation requires concrete reason')
        states[name].update(status=status,reason=custom.get('reason',states[name]['reason']),terminal_note_source=source)
    ie_used=evidence.json(IE+'/consumption.json');flex_used=evidence.json(FLEX+'/consumption.json')
    ref_summary=evidence.json(REFERENCE+'/summary.json',False)
    ref_used=evidence.json(REFERENCE+'/consumption.json',False) if ref_summary else None
    ref_added=ref_used['native_starts'] if ref_used else 0
    base=old['consumption'];native=learning=None
    if rl and states['rl']['status']=='completed':
        native=base['cumulative_native']+ie_used['native_starts']+flex_used['native_starts']+ref_added+rl['verification']['new_native']
        learning=base['cumulative_learning']+rl['verification']['new_learning']
    totals=dict(base_native=base['cumulative_native'],base_learning=base['cumulative_learning'],
        IE_added_native=ie_used['native_starts']+flex_used['native_starts'],IE_added_learning=0,
        posthoc_reference_diagnosis_native=ref_added,posthoc_reused_data_not_independent_confirmation=True,
        RL_added_native=rl['verification']['new_native'] if native is not None else None,
        RL_added_learning=rl['verification']['new_learning'] if learning is not None else None,
        cumulative_native=native,cumulative_learning=learning,
        terminal_main_learning=sum(int(q['policy'].split('_')[-1]) for q in rl['summary'] if q['scope']=='confirmation' and q['policy'].startswith('PPO')) if native is not None else None,
        old32_main_already_in_base=96,device_sessions_not_PC_environments=True,
        scope='current CPU/GPU experiment lineage only; not all historical project training',base_consumption_source=PILOT+'/summary.json',
        added_native=(ie_used['native_starts']+flex_used['native_starts']+ref_added+rl['verification']['new_native']) if native is not None else None)
    for field,value in overlay.get('expected_consumption',{}).items():
        if field not in ('cumulative_native','cumulative_learning') or totals[field]!=value:raise ValueError('root consumption check does not match actual completed sources '+field)
    return dict(old=old,ie=ie,flex=flex,model=model,rl=rl,device=device,states=states,consumption=totals,reference_gap=ref_summary,
        reference_focus=evidence.json(REFERENCE+'/matched_history_focus.json') if ref_summary else None,
        reference_late=evidence.json(REFERENCE+'/late_request_gap.json') if ref_summary else None)

def final_guard(data):
    pending=[k for k,v in data['states'].items() if v['status'] not in TERMINAL]
    if pending:raise ValueError('공유 최종본은 종료 근거가 필요합니다: '+', '.join(pending)+'; 초안은 private에 생성할 수 있습니다.')

def kpi_table(rows,delta=False):
    out=['<table><thead><tr><th>정책</th><th>완료/예정</th><th>긴급 기한<br>위반</th><th>일반 기한<br>위반</th><th>조건별 긴급P95<br>평균 ms</th><th>'+('평균 ΔJ' if delta else '평균 J')+'</th><th>'+('평균 Δ최고 AP °C' if delta else '평균 최고 AP °C')+'</th></tr></thead><tbody>']
    for q in rows:
        name=q.get('name',q.get('name_ko',q['policy']));j=q.get('mean_delta_J') if delta else q.get('mean_J',q.get('mean_energy_j'));ap=q.get('mean_delta_AP') if delta else q.get('mean_AP',q.get('mean_peak_ap_c'))
        out.append(f'<tr><td>{E(name)}</td><td>{q["completed"]}/{q["planned"]}</td><td>{q["urgent_failure"]}</td><td>{q["normal_failure"]}</td><td>{number(q["mean_urgent_p95_ms"])}</td><td>{number(j,6,delta)}</td><td>{number(ap,6,delta)}</td></tr>')
    return ''.join(out)+'</tbody></table><p class="metric-note">위반은 늦은 완료이며 실행 오류와 다르다. 전량 완료와 양립한다. P95 평균은 조건별 P95의 평균이며 전체 요청 pooling P95가 아니다.</p>'

def bullets(values):return '<ul>'+''.join('<li>'+E(v)+'</li>' for v in values)+'</ul>'
def cards(values):return '<div class="cards">'+''.join(f'<div><strong>{E(a)}</strong><p>{E(b)}</p></div>' for a,b in values)+'</div>'
def diagram(values):
    width=1160;cell=(width-20)/len(values);out=[f'<svg class="diagram" viewBox="0 0 {width} 120" role="img" aria-label="'+E(' → '.join(values))+'">']
    for i,v in enumerate(values):
        x=10+i*cell;out.append(f'<rect x="{x}" y="25" width="{cell-28}" height="68" rx="10" fill="#e5edf6"/><text x="{x+(cell-28)/2}" y="63" text-anchor="middle" font-size="18" fill="#173654">{E(v)}</text>')
        if i<len(values)-1:out.append(f'<text x="{x+cell-25}" y="65" font-size="18">→</text>')
    return ''.join(out)+'</svg>'

def build_slides(e,d):
    slides=[]
    def add(title,body,notes,sources=()):
        slides.append(dict(number=len(slides)+1,title=title,body=body+e.cite(*sources) if sources else body,notes=notes,sources=list(sources)))
    states=d['states'];status='최종 연구 브리핑' if all(v['status'] in TERMINAL for v in states.values()) else '검증 결과 확정 대기 초안'
    counts=d['consumption'];count_note=('이번 추가 '+str(counts['added_native'])+'환경 / '+str(counts['RL_added_learning'])+'학습. 현재3learner terminal 본학습 '+str(counts['terminal_main_learning'])+'에피소드(기존96 포함). 기기 세션은 별도 장부.' if counts['cumulative_native'] is not None else '이번 IE 완료'+str(counts['IE_added_native'])+'환경·학습0. RL 연장 최종 소비는 결과 확정 후 합산한다.')
    add('온디바이스 AI의 CPU/GPU 자원 스케줄링', '<p class="lead">실측 기반 시뮬레이션으로<br>기한을 지키며 열·에너지 부담을 줄일 선택을 찾는다.</p>'+cards([('주제','한 Android 앱 안의 분류·탐지 요청'),('방법','실측 → 모형 검증 → 산업공학 리스트·롤링 → RL → 기기 확인'),('현재 묶음',status)])+'<p class="metric-note">'+E(count_note)+'</p>',
        '모델 정확도를 높이는 프로젝트가 아니라 앱 내부 요청의 순서·CPU/GPU 배정·실행 시점을 선택하는 연구입니다. 연구 자료 묶음의 완료와 새 정책 우월성 입증의 완료를 구분해 설명합니다.',('docs/OVERNIGHT_COMPLETION_20261011.md',))
    add('실제 문제: 같은 자원을 두 작업이 나눠 쓴다',cards([('긴급 분류','결과가 빨리 필요한 이미지 분류'),('일반 탐지','저장까지 완료해야 하는 객체 탐지'),('결정할 것','무엇을 먼저, CPU/GPU 어디에, 지금 실행할지')])+bullets(['자원 배정은 응답·전체 완료량·에너지·열 경로를 함께 바꿀 수 있다.','같은 작업을 덜 처리하거나 기한을 놓쳐 얻은 비용 감소는 개선으로 판정하지 않는다.']),
        '분류·탐지는 자원 배정 문제를 검증하는 예시입니다. 실제 사용자 로그는 없으므로 이번 도착은 사전 고정한 합성 trace입니다. 시장 규모나 모든 휴대폰의 온디바이스 구조를 수치로 주장하지 않습니다.',('docs/MULTITASK_EXPERIMENT_PROTOCOL.md','docs/BOUNDED_EMPIRICAL_RESULTS_20260921.md'))
    add('범위와 KPI를 먼저 고정했다',cards([('지킬 것','전체 예정 요청·출력 품질·긴급 P95·기한'),('줄일 것','같은 AP 채널의 최고값과 공통창 에너지 J'),('이번 자원','A24 분류 CPU/GPU · 탐지 CPU · 검증된 CG_DC 병행')])+bullets(['기한 1.5초/6초는 engineering scenario이며 사용자 SLA가 아니다.','표면 온도는 미확인이다. AP를 최고 표면 온도의 달성값으로 바꾸지 않는다.','선점·주파수 제어·전력 제한·NPU 확장은 이번 비교에 추가하지 않았다.']),
        '사용자가 원래 제시한 표면 온도 목표와 현재 측정 가능한 AP 지표 사이의 공백을 숨기지 않습니다. 기기별 자료를 혼합하지 않았고 NPU 자료는 별도 범위로 보존합니다.',(IE+'/execution_contract.json','docs/OVERNIGHT_COMPLETION_20261011.md'))
    add('실측 근거와 품질의 의미',cards([('기본 실측','30세션·480호출 · 출력 동등성 480건'),('시간 분해','CAL-03 개발8+확인8 · 본64·warmup128'),('별도 독립 평가','27세션·198요청 · 우선순위 효과와 조건부 정책 FAIL 보존')])+bullets(['고정 모델·입력·전처리·decoder를 유지했다. 일반 데이터셋 정확도나 mAP로 전용하지 않는다.','과거 우선순위 평가와 이번 열·에너지 정책 평가의 기한·자료·판정을 합쳐 전후 개선이라고 부르지 않는다.']),
        '30세션/480호출은 제한된 resident/thermal0 실측입니다. CAL-03 자료 적격 통과는 모든 예측 정확도 통과가 아닙니다. 과거 198요청의 조건부 정책 주 판정 FAIL도 유지합니다.',('docs/BOUNDED_EMPIRICAL_RESULTS_20260921.md','docs/ARRIVAL_CAL03_EXECUTION_20260924.md','docs/ARRIVAL_EXTENSION_POST_ANALYSIS_20260923.md'))
    add('응답 완료와 자원 반환을 분리한다',diagram(['배정','실행 시작','출력 준비','저장 완료','worker 해제','lane 반환'])+cards([('분류 응답','OUTPUT_READY에서 완료'),('탐지 응답','PERSISTED에서 완료'),('재사용','실제 AVAILABLE 이후에만 허용')])+bullets(['고정 5phase 점유 벡터로 실행한다. 같은 시각의 연속 배정도 용량을 지킨다.','미완료·실패·기한 초과를 전체 예정 요청 분모에서 지우지 않는다.']),
        '빠른 출력 준비를 lane 반환으로 착각하면 유령 병행과 성능 이득이 생깁니다. 처리 종료·저장·worker 해제·lane 반환을 각각 보존하는 것이 시뮬레이션의 핵심입니다.',('tools/d1_arrival_explore.py',IE+'/verification.json'))
    modes=d['model']['comparison']['modes']['B_fixed_original_service']['overall'];a,b=modes['original'],modes['hybrid']
    add('새 열 모형: 평균 오차는 줄었고 한계는 남았다',cards([('AP 평균 MAE',f'{number(a["mean_AP_MAE_c"],6)} → {number(b["mean_AP_MAE_c"],6)} °C'),('J120 절대오차',f'{number(a["mean_J120_abs_j"],6)} → {number(b["mean_J120_abs_j"],6)} J'),('확인 범위','새 CPU/PAR 각각 1회 · 192요청')])+ '<img class="chart" src="figures/01_모형검증.png" alt="새 독립 두 세션의 모형 오차"/>'+bullets(['원 에너지·서비스 예측을 유지했다. CPU 최대·피크 오차는 악화했다.','냉각에 따른 속도 회복은 없다. 작은 정책 AP/J 차이를 실제 절감으로 확정할 수 없다.']),
        '같은 미래 예정 요청으로 예측한 B를 주로 비교합니다. 실제 미래 점유를 넣는 A는 조건부 진단입니다. 첫 v3의 AP/J 동시 감소 FAIL을 유지하고, 별도 hybrid 동결 뒤 새 2회로 확인했습니다.',('docs/ROLLING_HYBRID_PILOT_20261011.md',d.get('model_support_source',SHARED_MODEL)))
    add('산업공학 구조: EDD·ECT + 공동 롤링',diagram(['현재 공개 큐','최대4요청','순서·자원·대기','첫 행동 실행','도착/반환 재계획'])+cards([('EDD','빠른 납기 요청을 먼저 검토'),('ECT','가용 자원과 예상 점유를 반영'),('공동 롤링','≤72계획 → mean 선별8 → 세 문맥 평가')])+bullets(['분류는 CPU/GPU에 유연하고 탐지는 CPU 전용이다. 자원 호환성과 납기 여유를 함께 고려한다.','미래 도착을 보고 전체 최적 일정을 짜는 방식이 아니다. 현재 요청의 첫 행동만 실행한다.'])+'<p class="callout">설명용 예시: 분류1건+탐지1건<br>CPU 순차 ↔ 분류GPU+탐지CPU를 검토하고 첫 배정만 실행한다.<br>새 요청이 오면 다시 계획한다. 냉각 대기 중 몰림은 기한 위험이다.</p>',
    # The example explains the implemented control unit; it is not a result.
        '예시: 현재 분류1건+탐지1건이 있다. 분류CPU→탐지CPU 순차와 분류GPU+탐지CPU 병행을 비교한다. 선택한 첫 배정(가능한 동시 쌍)만 실행한다. 새 요청이 도착하면 다시 계산한다. 잠깐 냉각을 기다리던 중 새 탐지가 몰리면 기한이 나빠질 수 있으므로 미관측 초기 대기를 보수적으로 제한한다. 산업공학 기여는 병렬 자원 배정·납기·호환성·반복 재계획의 대응과 정량 검증이며 전역 최적해를 주장하지 않는다.',('docs/ROLLING_EXPERT_REVIEW_20261010.md','tools/d1_rolling_joint_thermal.py'))
    add('강한 비교군도 출처의 판단 규칙을 옮겼다',cards([('Band 대응','largest-shortest 요청·예상 비용·busy worker yield·관측 EMA'),('Triton 대응','고정 요청·CPU/GPU 자원 제약과 RateLimiter 판단 흐름'),('비교 범위','같은 엔진·같은 입력의 제한적 규칙 대응 B')])+bullets(['Band subgraph를 전체 모델 요청으로 바꾨다. 원 Band와 동일 알고리즘·제품 실행이라고 부르지 않는다.','Triton 서버 전체를 돌린 결과가 아니다. Ente 시작 허용과 자원 배정도 서로 다른 제어 대상이다.']),
        '이름을 붙인 임의 FIFO가 아니라 출처 기반 판단 흐름을 옮겼습니다. 실행 단위와 자원 범위가 달라 외부 제품보다 우월하다는 주장은 하지 않습니다. 기준이 강하면 새 정책이 이를 못 넘는 것도 유효한 연구 결과입니다.',('docs/results/external_rules_01/README.md','docs/REQUEST_TRITON_THERMAL_ENERGY_PC_20261007.md'))
    add('리스트 보완: 무조건 기다리는 문제를 줄였다',cards([('같은 후보 Rule','공통 리스트에서 예측 AP·J로 선택'),('R1','도착 부하를 아직 모르면 냉각 대기 금지'),('R2','현재 요청 모두의 예상 응답도 L0보다 늦추지 않음')])+bullets(['관측 부하·CPU 전용 작업량·요청별 누적 대기를 쓰지만 미래 도착을 알지는 못한다.','요청마다 추가 냉각 대기 ≤0.25초. 새 도착·실제 AVAILABLE·timer에서 재판단한다.']),
        'R1/R2는 새로운 계수나 기한을 넣은 방식이 아니라 기존 선택기의 위험을 분리한 작은 보완입니다. 알고리즘 숫자를 늘리는 대신 실제 반례를 고쳤습니다.',(IE+'/execution_contract.json','tools/d1_overnight_ie_policy.py'))
    add('확인①: R1은 서비스 손실을 막았지만 교체 기준은 미달',kpi_table(d['ie']['confirmation'],True)+'<p class="callout">평균 비용 감소와 엄격한 전 조건 통과는 다르다.<br>R1: 원 Rule의 일반 기한 위반 42→40 · 비용 비악화 35/48 · 최종 채택 없음.</p><p class="metric-note">4개 도착 seed×4부하×3민감도 문맥. 48번의 독립 실측이 아니다.</p>',
        '새 확인48의 seed828110101..104입니다. R1은 Band와 같은 일반 실패40건이고 기존 Rule42건의 추가 실패를 막았습니다. 13조건의 비용 악화를 평균으로 상쇄하지 않았습니다. 온도 차이는 아주 작고 실제 절감이 아닙니다.',(IE+'/summary.json',IE+'/confirmation_verdict.json',IE+'/confirmation_comparison.csv'))
    add('확인②: P95 유연성을 열어도 공동 개선은 자동으로 생기지 않았다',kpi_table(d['flex']['confirmation'],True)+'<p class="callout">P95 유연성: 에너지 감소·AP 증가의 상충. 원 판정 FAIL 유지.</p><p class="metric-note">확인①과 다른 4개 도착 seed. 세 문맥은 민감도이며 독립 시행이 아니다.</p>',
        '확인①과 다른 새 seed828120201..204입니다. 실패40/42를 전후 개선으로 비교하지 않습니다. 과거+현재 도착/소유 미응답의 P95를 쓰며 개별 lateness는 보호했습니다. 실제 누락 후보는 CPU가 바쁠 때 GPU 즉시 실행 대신 CPU 반환을 기다리는 자원 대기였습니다.',(FLEX+'/summary.json',FLEX+'/execution_contract.json',FLEX+'/expert_review.md'))
    oldrows=[q for q in d['old']['summary'] if q['policy'] in ('Band','Rule','PPO11_32','PPO23_32','PPO37_32')]
    add('RL은 실제로 학습했다: 짧은 3seed 파일럿',kpi_table(oldrows)+'<p class="callout">각32에피소드·4update. 최종 actor/critic/Adam/RNG를 보존했다.</p>'+bullets(['seed11은 개발24 일정이 Band와 동일. seed23/37은 비용 감소와 기한 손실이 상충했다.','32에피소드를 수렴 완료 또는 RL 일반의 실패로 해석하지 않는다.']),
        '기본·복귀·학습 참조는 L0이고 Band는 비교군입니다. 자체 PyTorch masked PPO가 실제 후보 슬롯을 선택했습니다. EDD/ECT를 이름만 보상에 붙인 구조가 아닙니다. 행동 마스킹은 물리 불가능과 예측 위험의 구분이며 미래 기한 보장이 아닙니다. 이번 새설계3learner는 과거PPOv2와 별도이며 소실된 과거 학습 상태의 연장 또는 프로젝트 전체학습수로 표시하지 않습니다.',(PILOT+'/summary.json',PILOT+'/verification.json','tools/d1_rolling_list_rl.py'))
    if states['rl']['status']=='completed' and d['rl']:
        rr=[q for q in d['rl']['summary'] if q['scope']=='confirmation' and (q['policy'] in ('Band','Triton','Rule') or q['policy'].startswith('PPO'))]
        gates=d['rl']['confirmation_gates'];passed=sum(bool(gates[k]['promising']) for k in gates if k.startswith('PPO'))
        body=kpi_table(rr)+f'<p class="callout">같은 learner 32→64→128→256→512 · 최종 유망 기준 {passed}/3seed 통과</p>'
        notes='전체 actor·Adam·RNG와 원 알고리즘·보상을 유지한 학습량 비교입니다. 최고 seed 하나를 골라 대표하지 않고 세 terminal512를 모두 평가했습니다. 실제 Adam 각768step/gradient가 발생했습니다. 개발24에서 seed11/23은 Band KPI와 같았지만 새 확인48에서는 세 PPO 모두 일반45건 vs Band42건입니다. 이는 비단조 학습과 일반화 제약이지 학습 미실행·수렴 완료·RL 일반의 실패를 뜻하지 않습니다. L0 자체도45건이며 서비스 학습참조 L0와 강한 최종 비교군 사이의 격차를 구분합니다. NoWait는 냉각 대기와 자원 대기를 함께 제거하므로 비용 변화를 냉각만의 효과로 분리하지 않습니다. 기본/복귀는 L0이며 외부 Band로 복귀한 것이 아닙니다.'
        notes+=' NoWait가 제거하는 것은 명시적 냉각·자원 대기 후보이며, 실제 AVAILABLE까지 기다리는 불가피한 대기는 유지한다.'
        body+='<p class="metric-note">이번 추가학습 '+str(counts['RL_added_learning'])+'회. 3learner terminal 본학습량 '+str(counts['terminal_main_learning'])+'회에는 기존32×3=96이 포함된다. 기저 소비에96을 다시 더하지 않는다.</p>'
        sources=(RL+'/result.json',RL+'/verification.json',RL+'/checkpoint_inventory.json')
    else:
        body='<p class="lead">이번 연장 결과: '+E(states['rl']['status'])+'</p>'+bullets([states['rl']['reason'],'승인된 목표는 동일3learner terminal32→64→128→256→512다.','완료되지 않은 학습·최종 확인·미완성 checkpoint 수치를 최종 성능으로 제시하지 않는다.'])
        notes='이미 완료한32×3 학습과 이번 연장 과제를 구분합니다. 실제 학습 소비·최종 평가가 확정되지 않았으면 예정1440 학습을 완료로 읽지 않습니다.';sources=(RL+'/execution_contract.json',)
        if states['rl'].get('terminal_note_source'):sources+=(states['rl']['terminal_note_source'],)
    add('같은 설정으로 더 학습하면 개선되는가?',body,notes,sources)
    if d['device']:
        out=['<table><thead><tr><th>순서/원 정책</th><th>완료/예정</th><th>긴급/일반<br>기한 위반</th><th>긴급 P95 ms</th><th>조건부 J</th><th>최고 AP °C</th><th>초기 AP °C</th></tr></thead><tbody>']
        for q in d['device']['sessions']:
            out.append(f'<tr><td>{q["index"]}: {E(str(q["source_policy"]))}</td><td>{q.get("completed") if q.get("completed") is not None else "미확정"}/{q["planned"]}</td><td>{q.get("urgent_failures") if q.get("urgent_failures") is not None else "미확정"}/{q.get("normal_failures") if q.get("normal_failures") is not None else "미확정"}</td><td>{number(q.get("urgent_p95_ms"))}</td><td>{number(q.get("energy_j_conditional_mA"))}</td><td>{number(q.get("ap_peak_c"))}</td><td>{number(q.get("initial_ap_c"))}</td></tr>')
        body=''.join(out)+'</tbody></table><p class="callout">고정 계획 재생 · 온라인 Band/롤링/RL 직접 운영 효과가 아니다.</p><p class="metric-note">실측 J/AP 최고: 공통0..120초. PC J0..120/AP35..180과 온도 창이 다르다. 정책별2회·초기AP·전류 단위에 따른 조건부 J를 함께 본다. 미세 PC 차이와 기기 변동을 직접 전후 개선으로 합치지 않는다.</p>'
        sources=(DEVICE+'/summary.json',DEVICE+'/requests.csv',DEVICE+'/pairs.csv')
    else:
        body='<p class="lead">실측 결과: '+E(states['device']['status'])+'</p>'+bullets([states['device']['reason'],'같은96요청/350ms·Band/Rule의 동결 계획 ABBA4를 고정했다.','원 PC는35초 공통 시작이다. 상대 원점 export를 바로잡고 roundtrip 검사했다.'])
        sources=(DEVICE+'/execution_contract.json',IE+'/device_export_common0_contract.json')
        if states['device'].get('terminal_note_source'):sources+=(states['device']['terminal_note_source'],)
    add('A24 확인: PC 계획과 실제 실행의 차이를 본다',body,
        '기기에서는 사전 고정한 CPU/GPU와 실행 시점을 재생하며 busy lane는 실제 AVAILABLE까지 기다립니다. 원 정책의 온라인 판단 코드를 실행한 것은 아닙니다. PC AP35..180과 실측0..120의 관측 표본 최고는 다른 창입니다. 실제35..180초의 최초 경계와 마지막0.68..1.64초가 완전히 관측되지 않았으므로 정확한 연속180초 최고는 계산 불가입니다. 초기AP·순서반전·정책별2회와 전류 mA해석의 조건부J를 표시하며 절대 에너지 교정·실제 우월성은 미확정입니다.',sources)
    add('추천과 아직 확정하지 않은 것',cards([('앱 기본','기존 앱 설정 유지. 새 정책 최종 채택0.'),('자체 발전 후보','리스트 후보+RL 방향에서 R1을 연구 후보기반으로 남긴다.'),('강한 비교군','Band 요청 대응은 강한 기준선이다. 우리 정책의 기본으로 채택한 것은 아니다.')])+bullets(['평균 모형 J/AP 감소와 엄격한 모든 조건 우위를 함께 보고한다.','정책의 기본·복귀·학습 참조는 리스트 L0이며 Band는 비교군이다.','회의용 연구 묶음 완료와 새 열·에너지 정책 확립·전체 SUBMIT-02 완료를 구분한다.']),
        'Band 기본+롤링을 새 자체 방법론으로 채택하지 않았습니다. 연구 방향은 리스트 후보+RL이며 R1은 그 비학습 발전 후보입니다. RL 새 결과의 원 기준 통과 여부를 확인하고, 엄격한 최종 대체 기준 미달은 그대로 남깁니다. 실제 앱의 기존 기본은 바꾸지 않았고 공개 제품 전체와 승패를 말하지 않습니다.',(IE+'/confirmation_verdict.json',FLEX+'/confirmation_verdict.json','docs/OVERNIGHT_COMPLETION_20261011.md'))
    add('한계와 다음 작업을 구체적으로 남긴다',bullets(['열→처리시간 회복 효과: 같은 입력·경합의 실제 감속과 유휴 회복 전후를 독립 계측해야 한다.','표면 온도: AP와 별개 측정 채널·장비·교정이 필요하다. AP를 표면값으로 바꾸지 않는다.','실제 온라인 정책: 동결 계획 재생과 별도로 판단 지연·제어 비용·같은 조건 반복을 확인해야 한다.','대표성: 합성 trace·고정 입력·기기 한정 범위이며 다른 앱/기기/모델로 자동 일반화하지 않는다.','배포: EfficientDet exact binary의 license/NOTICE 귀속이 미확인이다. 모델을 Git/APK/팀 공유물에 넣지 않는다.']),
        '마지막 제한은 연구 probe가 가능하다는 것과 재배포 승인이 다르다는 의미입니다. 추가 측정은 어떤 주장을 검증할지 목적을 먼저 고정해야 합니다. 지금 숫자 개선을 위해 계수·SLA·완료량·지원 범위를 바꾸지 않았습니다.',('docs/MODEL_02_INVENTORY.md','docs/RECOVERY_SERVICE_RESULTS_20261010.md','docs/ROLLING_HYBRID_PILOT_20261011.md'))
    if d.get('reference_gap'):
        ref={q['policy']:q for q in d['reference_gap']}
        body=cards([('같은 확인 자료 재사용','R1/Flex만 새96환경. 원480행 SHA 재사용.'),('일반 기한 위반',f'Band {ref["Band"]["normal_violation"]} · L0/R1/Flex {ref["L0"]["normal_violation"]}'),('같은 공개 상태','GPU분류+CPU탐지는 물리허용, 예측응답 제약으로 차단')])+bullets(['35.165초 최초 분기: L0는 분류CPU, Band 대응은 분류GPU+탐지CPU.','현재 긴급2건의 P95는 최댓값이므로 P95 유연성 보완도 같은 후보를 막는다.','대표 조건은 냉각·자원 대기0. 추가 위반을 냉각 때문이라고 단정할 수 없다.'])+'<p class="callout">학습참조 L0의 서비스 비악화와 최종 Band 대비 서비스 비악화는 다르다.<br>물리적 불가·예측 제약·선택을 구분해야 한다.</p>'
        note='이미 본 확인자료를 재사용한 사후기전 진단이며 새 독립 확인이나 최종 채택 성공이 아닙니다. 첫 분기 전 배정과 관측 phase 콜백이 같은 것을 확인했고 실제 원 encoder 전체와 물리/예측 마스크를 검사했습니다. 긴급 예측 241.818→379.693ms는 1.5초 기한 안이지만 L0보다 느려 차단됩니다. 뒤 D22 응답은 L0계열6.303초 vs Band5.973초, 추가 CPU점유330.433ms는 사후회계이며 정책에 미래값을 주지 않았습니다. 이 상태의 원인을 모든 차이의 유일 원인으로 확대하지 않습니다. 다음 별도 설계에서는 L0참조와 최종 KPI의 대응, 긴급 P95 여유와 CPU전용 작업의 호환성을 검토해야 하며 이번 판정·목표·정책은 바꾸지 않았습니다.'
        body+='<p class="metric-note"><a href="figures/06_같은상태_배정과기한.png">같은 상태의 배정·뒤 요청 기한 그림</a></p>'
        review=REFERENCE+'/expert_review.md'
        sources=(REFERENCE+'/README.md',REFERENCE+'/matched_history_focus.json',REFERENCE+'/verification.json')+((review,) if e.path(review).exists() else ())
        add('사후 기전 진단: 학습과 별개로 검토할 제약',body,note+' 해당 동일 상태·현재 허용 규칙에서의 차단이다. 이전 행동으로 다른 상태에 도달할 개선 가능성까지 부정하지 않으며, 예측 P95가 최종 전체 P95나 서비스 보장은 아니다. 마스크를 즉시 풀면 모든 KPI가 개선된다는 뜻이 아니다.',sources)
    faq=[('산업공학 기여는 무엇인가?','납기 순서·예상 점유·자원 호환성·제약·rolling horizon을 앱 내부 비선점 CPU/GPU 배정에 대응하고 실제 근거로 평가했다. 새로운 일반 최적 알고리즘을 입증한 것은 아니다.'),
        ('왜 기본 정책이 좋은가?','검증된 자원이 적고, 빠른 자원 선택과 CPU/GPU 병행이 이미 많은 이득을 만든다. 예측 위험·미관측 미래를 고려하면 남은 안전한 차이가 작다.'),
        ('RL을 실제로 돌렸나?',('3seed 각각512에피소드·64update·Adam768step의 masked PPO를 실제 학습했다. 기존32에서 같은 최종 actor/critic/Adam/RNG를 이어 추가1440에피소드를 수행했다. 개발 동률이 새 확인에서 일반화되지는 않았고 세 seed 모두 원 기준 미달이다.' if states['rl']['status']=='completed' else '3seed 각각32에피소드 masked PPO를 실제 학습했다. actor/critic/Adam/RNG·재개 동일성을 검사했다. 이번 연장 최종 결과는 종료 근거를 따로 확인한다.')),
        ('얼마나 돌리면 수렴하나?','정해진 횟수만으로 수렴이나 전역 최적을 보장할 수 없다. 학습량 효과는 비단조일 수 있다. 복수 seed·학습량별 원 KPI의 안정성과 확인 자료를 본다. NoWait는 냉각·자원 대기를 둘 다 제거한 진단이다.'),
        ('AP는 표면 온도인가?','아니다. 동일 AP 채널의 모형/실측 지표다. 평균 모형 오차 감소도 표면 온도·안전 한도·속도 회복 검증이 아니다.'),
        ('왜 추가 실측을 하나?','작은 모형 AP/J 차이가 실제 실행·관측에서도 나타나는지 확인하기 위해서다. 이번 고정 계획 재생은 온라인 판단 효과와 구분한다.'),
        ('무엇을 추천하나?','기존 앱 기본은 유지하고 리스트 후보+RL 방향에서 R1을 자체 발전 후보로 남긴다. Band는 강한 비교군이며 우리 기본으로 채택한 것이 아니다. 최종 RL은 복수 seed·서비스·실측 범위를 함께 본다.'),
        ('가장 큰 한계는 무엇인가?','미관측 미래 도착, 제한된 자원·trace·초기 상태, 냉각→속도 연결 미지원, 표면/절대 에너지 교정·온라인 기기 효과·모델 배포 라이선스 공백이다.')]
    for offset in (0,4):
        body=''.join('<h3>'+E(a)+'</h3><p>'+E(b)+'</p>' for a,b in faq[offset:offset+4])
        add('질의응답 '+('①' if offset==0 else '②'),body,'질문에 수치만 답하지 말고 같은 입력·원단위·증거의 범위를 함께 설명합니다.',('docs/OVERNIGHT_COMPLETION_20261011.md',))
    for s in slides:s['core']=s['number'] in CORE_SLIDES
    return slides,faq

def figures(folder,d):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    path=folder/'figures';path.mkdir(parents=True,exist_ok=True)
    q=d['model']['comparison']['modes']['B_fixed_original_service']['overall'];fig,axes=plt.subplots(1,2,figsize=(10,3.5))
    axes[0].bar(['원모형','온도 보정'],[q['original']['mean_AP_MAE_c'],q['hybrid']['mean_AP_MAE_c']],color=['#7692ad','#177f71']);axes[0].set_ylabel('AP 평균 절대오차 (°C)')
    axes[1].bar(['원모형','온도 보정'],[q['original']['mean_J120_abs_j'],q['hybrid']['mean_J120_abs_j']],color=['#7692ad','#177f71']);axes[1].set_ylabel('J120 절대오차 (J)')
    fig.suptitle('새 CPU/PAR 각1회 · 같은 에너지·서비스 유지 · 최악/피크는 별도');fig.tight_layout();fig.savefig(path/'01_모형검증.png',dpi=150);plt.close(fig)
    for data,name,title in [(d['ie']['confirmation'],'02_리스트_새확인.png','확인① 48조건 · 평균 감소와 전조건 FAIL을 구분'),(d['flex']['confirmation'],'03_P95유연성_새확인.png','확인② 48조건 · 다른 seed · 에너지/AP 상충')]:
        rs=[q for q in data if q['policy'] not in ('Band','Triton','L0')];fig,axes=plt.subplots(1,2,figsize=(10,4));labels=[q['name'].replace(' 리스트','') for q in rs]
        for ax,field,unit in zip(axes,('mean_delta_J','mean_delta_AP'),('Band 대비 평균 ΔJ (J)','Band 대비 평균 Δ최고 AP (°C)')):
            ax.bar(range(len(rs)),[q[field] for q in rs],color=['#187c71' if q[field]<0 else '#c87864' for q in rs]);ax.axhline(0,color='#293b4d',lw=.8);ax.set_xticks(range(len(rs)),labels,rotation=10);ax.set_ylabel(unit);ax.grid(axis='y',alpha=.2)
        fig.suptitle(title);fig.tight_layout();fig.savefig(path/name,dpi=150);plt.close(fig)
    if d['rl'] and d['states']['rl']['status']=='completed':
        allrows=[dict(q,scope='development') for q in d['old']['summary'] if q['policy'].endswith('_32')]+[q for q in d['rl']['summary'] if q['scope']=='development' and q['policy'].startswith('PPO') and int(q['policy'].split('_')[-1])>32]
        fig,axes=plt.subplots(2,2,figsize=(10,6))
        for seed in (11,23,37):
            rs=sorted([q for q in allrows if q['policy'].startswith(f'PPO{seed}_')],key=lambda q:int(q['policy'].split('_')[-1]))
            for ax,key,label in zip(axes.flat,('normal_failure','mean_urgent_p95_ms','mean_energy_j','mean_peak_ap_c'),('일반 기한 위반 (건)','조건별 긴급P95 평균 (ms)','전체 에너지 평균 (J)','최고 AP 평균 (°C)')):
                ax.plot([int(q['policy'].split('_')[-1]) for q in rs],[q[key] for q in rs],marker='o',label=f'seed {seed}');ax.set_title(label);ax.set_xlabel('같은 learner 누적 에피소드');ax.grid(alpha=.2)
        axes[0,0].legend();fig.suptitle('같은24 개발조건 · 3seed 모두 · 수렴 보장 아님');fig.tight_layout();fig.savefig(path/'04_RL학습량.png',dpi=150);plt.close(fig)
    if d['device'] and d['states']['device']['status'] in TERMINAL:
        rs=d['device']['sessions'];fig,axes=plt.subplots(1,2,figsize=(10,4))
        for ax,key,label in zip(axes,('energy_j_conditional_mA','ap_peak_c'),('실측 조건부 J · mA 해석 (J)','실측0..120초 최고 AP (°C)')):
            for q in rs:
                value=q.get(key)
                if value is not None:ax.bar(q['index'],value,color='#447ba5' if q['index'] in (0,3) else '#c5855d')
                else:ax.text(q['index'],0,'미확정',ha='center')
            ax.set_xticks([q['index'] for q in rs],[f'{q["index"]} '+('Band' if q['index'] in (0,3) else 'Rule') for q in rs]);ax.set_ylabel(label)
        fig.suptitle('동결계획 ABBA · 온라인 정책 효과 아님 · 초기AP/단위/창 제한');fig.tight_layout();fig.savefig(path/'05_기기고정계획.png',dpi=150);plt.close(fig)
    if d.get('reference_focus'):
        focus=d['reference_focus'];urgent=focus['urgent_prediction'];late=next(q for q in d['reference_late'] if q['context']=='mean')
        fig,axes=plt.subplots(1,2,figsize=(11,4.2))
        values=[urgent['L0_P95_ms'][0],urgent['Band_like_bundle_P95_ms'][0]]
        axes[0].bar(['L0 분류CPU','분류GPU+탐지CPU'],values,color=['#447ba5','#c5855d'])
        axes[0].axhline(urgent['C1_deadline_ms'],color='#ad5045',ls='--',label='시나리오 기한1500ms')
        axes[0].set_ylim(0,1750);axes[0].set_ylabel('현재 긴급2건의 예측 P95 (ms)');axes[0].set_title('물리 허용 pair · 응답 예측 제약으로 차단')
        axes[0].legend(loc='upper left')
        for i,value in enumerate(values):axes[0].text(i,value+35,f'{value:.3f}ms',ha='center')
        values=[late['L0_response_ms']/1000,late['Band_response_ms']/1000]
        axes[1].bar(['L0계열 CPU배정','Band 대응 배정'],values,color=['#c5855d','#447ba5'])
        axes[1].axhline(6,color='#ad5045',ls='--',label='일반 기한6초');axes[1].set_ylim(0,7.6)
        axes[1].set_ylabel('뒤 요청 D22의 모형 응답 (초)');axes[1].set_title('같은 mean 조건 · 냉각/자원대기0');axes[1].legend(loc='upper left')
        for i,value in enumerate(values):axes[1].text(i,value+.08,f'{value:.6f}초',ha='center')
        fig.suptitle('동일 공개 상태 사후 진단 · 최종 P95 보장/실폰 burst 검증 아님')
        fig.tight_layout();fig.savefig(path/'06_같은상태_배정과기한.png',dpi=150);plt.close(fig)

CSS='''*{box-sizing:border-box}body{margin:0;background:#132537;color:#142b42;font-family:"Malgun Gothic","Segoe UI",sans-serif}.toolbar{position:fixed;bottom:15px;left:50%;transform:translateX(-50%);z-index:20;display:flex;gap:12px;align-items:center;background:#163752;color:white;padding:10px 18px;border-radius:18px;box-shadow:0 4px 14px #0005}.toolbar button{background:#e7eef5;border:0;border-radius:8px;padding:8px 13px;cursor:pointer}.slide{display:none;width:min(96vw,1330px);min-height:730px;background:#fafcfe;margin:20px auto 90px;padding:40px 52px;border-radius:10px}.slide.active{display:block}h1{font-size:34px;margin:0 0 22px;line-height:1.25}h3{font-size:23px;margin:17px 0 6px}p,li{font-size:21px;line-height:1.5}ul{padding-left:28px;margin:18px 0}li{margin:9px 0}.lead{font-size:32px;line-height:1.45;margin:30px 0}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:22px 0}.cards>div{background:#eaf1f7;border-top:5px solid #188475;padding:17px 20px;border-radius:7px}.cards strong{font-size:23px}.cards p{font-size:20px;margin:10px 0 0}.callout{background:#fff0ce;padding:16px 21px;border-left:5px solid #db9c38;font-size:23px}.source{font-size:12px;line-height:1.6;color:#53697c;margin-top:22px;word-break:break-all}a{color:#195e8b}.source a{display:inline}.notes{display:none;margin-top:22px;padding:18px;background:#e6edf4;font-size:18px;line-height:1.5}.show-notes .notes{display:block}.diagram{width:100%;margin:12px 0;font-family:"Malgun Gothic",sans-serif}.chart{width:min(100%,930px);max-height:265px;object-fit:contain;display:block;margin:10px auto}table{border-collapse:collapse;width:100%;font-size:17px;line-height:1.4;background:white}th,td{padding:12px 9px;text-align:left;border-bottom:1px solid #d2deea}th{background:#e6eef6}td:first-child{max-width:270px}.counter{min-width:58px;text-align:center}.label{font-size:13px;color:#648092;margin-bottom:12px}@media(max-width:850px){.slide{padding:28px;min-height:0}.cards{grid-template-columns:1fr}table{font-size:13px}th,td{padding:8px 5px}.lead{font-size:27px}}@media print{@page{size:A4 landscape;margin:7mm}body{background:white}.toolbar{display:none}.slide{display:block!important;margin:0;border:0;border-radius:0;width:100%;min-height:0;padding:8mm;break-after:page;page-break-after:always}h1{font-size:23pt}.lead{font-size:23pt}p,li{font-size:14pt}.cards strong{font-size:15pt}.cards p{font-size:13pt}.callout{font-size:15pt}table{font-size:10pt}th,td{padding:5px}.chart{max-height:52mm}.source{font-size:7pt}.notes{display:none!important}}'''
JS='''let slides=[...document.querySelectorAll('.slide')],requested=Number(location.hash.replace('#slide-',''))||1,coreOnly=true,current=0;function activeSlides(){return coreOnly?slides.filter(s=>s.dataset.core==='true'):slides}if(!slides.find(s=>Number(s.dataset.number)===requested)?.dataset.core.includes('true'))coreOnly=false;function show(i){let a=activeSlides();current=Math.max(0,Math.min(a.length-1,i));slides.forEach(s=>s.classList.toggle('active',s===a[current]));document.querySelector('.counter').textContent=(coreOnly?'핵심 ':'전체 ')+(current+1)+' / '+a.length;document.getElementById('appendix').textContent=coreOnly?'부록 포함':'핵심10장';location.hash='slide-'+a[current].dataset.number;window.scrollTo(0,0)}document.getElementById('prev').onclick=()=>show(current-1);document.getElementById('next').onclick=()=>show(current+1);document.getElementById('notes').onclick=()=>document.body.classList.toggle('show-notes');document.getElementById('print').onclick=()=>window.print();document.getElementById('appendix').onclick=()=>{let old=activeSlides()[current];coreOnly=!coreOnly;show(Math.max(0,activeSlides().indexOf(old)))};document.addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(current+1)}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(current-1)}if(e.key==='Home')show(0);if(e.key==='End')show(activeSlides().length-1);if(e.key.toLowerCase()==='n')document.body.classList.toggle('show-notes')});show(Math.max(0,activeSlides().findIndex(s=>Number(s.dataset.number)===requested)));'''

CSS+=' .metric-note{font-size:16px;line-height:1.45;color:#4c6378}'

def input_schema():return dict(version=1,
    rl=dict(status='completed|blocked|stopped|partial|budget_stopped|in_progress',source='relative/path/to/real_terminal_evidence.json',reason='미완료라면 구체적 이유; completed는 실제 final result/verification 있을 때만 허용'),
    device=dict(status='same enum',source='relative/path/to/real_terminal_evidence.json',reason='동일 규칙'),
    publication_rule='final requires terminal evidence for both; incomplete states are labelled and no KPI invented',
    automatic_sources=dict(rl_result=RL+'/result.json',device_summary=DEVICE+'/summary.json'),numeric_overrides_allowed=False,
    expected_consumption=dict(cumulative_native='optional integer guard; computed actual completed data must equal',cumulative_learning='same guard, no override'))

def validate_generated(folder):
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.values=[]
        def handle_starttag(self,tag,attrs):
            self.values.extend(v for k,v in attrs if k in ('href','src') and v and not v.startswith('#'))
    parser=Links();text=(folder/'index.html').read_text(encoding='utf-8');parser.feed(text)
    for value in parser.values:
        target=(folder/value).resolve()
        if not target.is_relative_to(ROOT) or not target.is_file():raise ValueError('offline link unresolved '+value)
    manifest=json.loads((folder/'generation_manifest.json').read_text(encoding='utf-8'))
    tracked={v for v in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0') if v}
    prefixes=tuple(p+'/' for p in (IE,FLEX,RL,DEVICE,REFERENCE,PUBLIC.relative_to(ROOT).as_posix(),DRAFT.relative_to(ROOT).as_posix()))
    allowed={'tools/d1_overnight_meeting.py','tools/d1_overnight_ie_policy.py','docs/OVERNIGHT_COMPLETION_20261011.md'}
    for name in manifest['source_sha256']:
        if name not in tracked and name not in allowed and not name.startswith(prefixes):raise ValueError('unshared source dependency '+name)
    if re.search(r'[A-Za-z]:[\\/]Users[\\/]',text):raise ValueError('private path in presentation')
    return dict(status='PASS_offline_links_and_whitelist_closure',links=len(parser.values),core_slides=10,appendix_slides=manifest['slide_count']-10)

def generate(final=False,overlay_path=None):
    folder=PUBLIC if final else DRAFT;e=Evidence(folder);overlay=e.json(Path(overlay_path).resolve().relative_to(ROOT).as_posix()) if overlay_path else {}
    d=detect_results(e,overlay)
    if final:final_guard(d)
    folder.mkdir(parents=True,exist_ok=True);support=folder/'supporting_evidence/model_validation.json';write(support,d['model']);d['model_support_source']=support.relative_to(ROOT).as_posix()
    if overlay_path:
        original=Path(overlay_path).resolve().relative_to(ROOT).as_posix();e.sources.pop(original,None)
    for name,state in d['states'].items():
        original=state.get('terminal_note_source')
        if original:
            source=e.path(original);e.sources.pop(original,None)
            note=dict(status=state['status'],reason=state['reason'],original_local_only_provenance=dict(repository_relative_path=original,sha256=sha(source)),numeric_KPI_overrides=False,unfinished_results_not_completed=True)
            target=folder/f'supporting_evidence/{name}_terminal_note.json';write(target,note);state['terminal_note_source']=target.relative_to(ROOT).as_posix()
    e.record('tools/d1_overnight_meeting.py');e.record(SHARED_MODEL);slides,faq=build_slides(e,d);figures(folder,d)
    (folder/'presentation.css').write_text(CSS,encoding='utf-8')
    appendix_count=len(slides)-len(CORE_SLIDES)
    content=''.join(f'<section class="slide" id="slide-{s["number"]}" data-number="{s["number"]}" data-core="{str(s["core"]).lower()}"><div class="label">D1Check · {"핵심10장" if s["core"] else "부록"+str(appendix_count)+"장"} · 실측 기반 CPU/GPU 스케줄링 · {"공유 최종본" if final else "PRIVATE 초안"}</div><h1>{E(s["title"])}</h1>{s["body"]}<aside class="notes"><strong>발표자 노트</strong><br>{E(s["notes"])}</aside></section>' for s in slides)
    page='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>D1Check 오전 연구 브리핑</title><link rel="stylesheet" href="presentation.css"></head><body>'+content+'<nav class="toolbar"><button id="prev">이전</button><span class="counter"></span><button id="next">다음</button><button id="appendix">부록 포함</button><button id="notes">노트 N</button><button id="print">인쇄</button></nav><script>'+JS+'</script></body></html>'
    (folder/'index.html').write_text(page,encoding='utf-8')
    briefing=['# D1Check 오전 회의 브리핑','', '온디바이스 AI의 CPU/GPU 자원 스케줄링을 실측 기반 시뮬레이션으로 비교한 연구다. 모델은 검증용 예시이며 목적은 기한·전체 완료량·품질을 유지하면서 AP 열 지표와 에너지 부담을 줄일 선택을 찾는 것이다.','', '## 핵심 결론','', '원래 Rule의 추가 서비스 손실을 막은 R1을 연구 발전 후보로 남긴다. R1은 새 확인48에서 Band와 일반 실패40건이 같고 원 Rule42건보다 적지만, 13조건에서 비용이 악화해 엄격한 최종 채택은 보류했다. 별도 P95 유연성 확인은 다른 seed48이며 평균 J 감소·AP 증가의 상충이다.','', 'RL 상태: **'+d['states']['rl']['status']+'** — '+d['states']['rl']['reason'],'기기 상태: **'+d['states']['device']['status']+'** — '+d['states']['device']['reason'],'', '서로 다른 비교 자료의 실패40/42나 과거 서비스 수치를 직접 전후 개선으로 합치지 않는다. 평균 감소·원 기준 FAIL을 같이 보고한다. AP는 표면 온도가 아니고, 작은 모형 차이는 실제 절감의 확정 근거가 아니다.','', '## 발표 흐름','']
    for s in slides:briefing.extend([f'{s["number"]}. **[{"핵심" if s["core"] else "부록"}] {s["title"]}** — '+s['notes'],'   근거: '+', '.join(s['sources'])])
    briefing.extend(['','## 핵심 FAQ',''])
    for question,answer in faq:briefing.extend(['**'+question+'**',answer,''])
    briefing.extend(['## 재생성','', '```powershell','python -B -X utf8 -m tools.d1_overnight_meeting --check','python -B -X utf8 -m tools.d1_overnight_meeting','python -B -X utf8 -m tools.d1_overnight_meeting --final','# 중단/부분 종료는 root가 실제 근거 JSON을 연결한 overlay로 명시한다.','python -B -X utf8 -m tools.d1_overnight_meeting --final --overlay output/meeting_terminal_note.json','```','', '기본 초안은 private output에만 저장하며 최종만 이 공유 폴더에 쓴다. 재생성은 조사·학습·시뮬레이션·실측·기기 명령·모형 재적합을 실행하지 않는다.'])
    (folder/'BRIEFING.md').write_text('\n'.join(briefing)+'\n',encoding='utf-8')
    notes=['# 발표자 노트','', f'권장: 핵심10장 약10분, 부록{appendix_count}장은 질문 때 사용. 기본 화면은 핵심만 이동하며 부록 포함 버튼으로 전체{len(slides)}장을 연다. 화살표/PageUp·PageDown 이동, N 노트 토글, 인쇄는 모든 슬라이드를 출력한다.','']
    for s in slides:notes.extend([f'## {s["number"]}. {s["title"]}','',s['notes'],'', '근거: '+', '.join(s['sources']),''])
    (folder/'SPEAKER_NOTES.md').write_text('\n'.join(notes),encoding='utf-8');write(folder/'input_schema.json',input_schema())
    snapshot=dict(version=VERSION,generated_utc=datetime.now(timezone.utc).isoformat(),shared_final=final,states=d['states'],
        IE_confirmation=d['ie']['confirmation'],Flex_confirmation=d['flex']['confirmation'],
        posthoc_reference_gap=d.get('reference_gap'),
        RL_confirmation=[q for q in d['rl']['summary'] if q['scope']=='confirmation'] if d['rl'] and d['states']['rl']['status']=='completed' else None,
        device_sessions=[{k:q.get(k) for k in ('index','source_policy','planned','completed','urgent_failures','normal_failures','urgent_p95_ms','energy_j_conditional_mA','ap_peak_c','initial_ap_c')} for q in d['device']['sessions']] if d['device'] else None,
        slide_count=len(slides),core_slides=CORE_SLIDES,source_sha256=e.sources,consumption=d['consumption'],simulation_learning_device_fit_calls=0)
    write(folder/'evidence_snapshot.json',snapshot)
    (folder/'README.md').write_text(f'# 오전 회의용 오프라인 연구 브리핑\n\n[index.html](index.html)을 브라우저에서 열고 화살표로 핵심10장을 이동한다(약10분). 부록 포함 버튼은 전체{len(slides)}장, N은 발표자 노트, 인쇄는 전체 슬라이드다. 외부 라이브러리·네트워크 없이 열린다.\n\n[짧은 브리핑](BRIEFING.md) · [발표자 노트](SPEAKER_NOTES.md) · [근거·숫자 snapshot](evidence_snapshot.json) · [모형 확인의 sanitized 근거](supporting_evidence/model_validation.json) · [추가 종료 상태 입력 계약](input_schema.json)\n\n새 비교 자료의 평균 감소와 엄격한 원판정 미달을 함께 보여준다. 기기 재생은 온라인 정책 효과가 아니며, AP는 표면온도가 아니다. 완료되지 않은 결과를 완료로 표시하지 않는다. 원사용자 모형 원본은 공유하지 않고 최소 수치·원source SHA를 따로 추출했으며 실제 동결 모형은 기존 공유 model.json을 참조한다. 사후96환경 진단은 부록이며 새 독립 확인이 아니다.\n',encoding='utf-8')
    outputs={p.relative_to(folder).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in folder.rglob('*') if p.is_file() and p.name!='generation_manifest.json'}
    write(folder/'generation_manifest.json',dict(version=VERSION,output_scope='shared_final' if final else 'private_draft',source_sha256=e.sources,output_sha256=outputs,slide_count=len(slides),pending=[k for k,v in d['states'].items() if v['status'] not in TERMINAL],data_readout_only=True))
    write(folder/'link_verification.json',validate_generated(folder))
    return dict(output=folder.relative_to(ROOT).as_posix(),shared_final=final,slides=len(slides),states=d['states'],native_learning_device_fit_starts=0)

def check():
    assert number(None)=='미확정' and number(0)=='0.000'
    try:final_guard(dict(states=dict(rl=dict(status='in_progress'),device=dict(status='completed'))))
    except ValueError:pass
    else:raise AssertionError('pending result published as completed')
    final_guard(dict(states=dict(rl=dict(status='blocked'),device=dict(status='partial'))))
    e=Evidence(DRAFT);d=detect_results(e,{})
    from unittest.mock import patch
    import sys
    original_exists=Path.exists;unshared=(ROOT/MODEL/'summary.json').resolve()
    def portable_exists(path):return False if path.resolve()==unshared else original_exists(path)
    portable_folder=DRAFT if (DRAFT/'supporting_evidence/model_validation.json').exists() else PUBLIC
    if (portable_folder/'supporting_evidence/model_validation.json').exists():
        with patch.object(sys.modules[__name__],'PUBLIC',portable_folder),patch.object(Path,'exists',portable_exists):
            portable=model_snapshot(Evidence(DRAFT))
        assert portable['comparison']==d['model']['comparison']
    assert d['ie']['confirmation'][0]['normal_failure']==40
    assert next(q for q in d['ie']['confirmation'] if q['policy']=='R1')['normal_failure']==40
    assert next(q for q in d['ie']['confirmation'] if q['policy']=='Rule')['normal_failure']==42
    assert next(q for q in d['flex']['confirmation'] if q['policy']=='Band')['normal_failure']==42
    slides,faq=build_slides(e,d);assert len(faq)==8 and len(slides)==18+bool(d.get('reference_gap')) and sum(s['core'] for s in slides)==10
    assert all(s['sources'] for s in slides)
    return dict(status='PASS',checks=['unknown_not_zero','pending_publish_rejected','partial_terminal_honest','source_group_numbers_separate','10core_8FAQ_sources_present_posthoc_appendix_separate','portable_model_without_unshared_original'],native_learning_device_fit_starts=0)

def main():
    p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');p.add_argument('--overlay');p.add_argument('--check',action='store_true');a=p.parse_args()
    print(json.dumps(check() if a.check else generate(a.final,a.overlay),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
