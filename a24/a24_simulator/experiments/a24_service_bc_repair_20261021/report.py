"""Saved-only Korean report writer."""
import json,sys
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'a24_simulator/results/A24_SERVICE_BC_REPAIR_20261021_01'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def write(n,s):
    with (O/n).open('x',encoding='utf8',newline='\n') as f:f.write(s.rstrip()+'\n')
names={'FIFO_DYN':'FIFO','EDF_DYN':'EDF','RR_DYN':'RR','TEACHER_OLD':'기존 교사','BC_OLD':'기존 신경망 BC','TEACHER_FAIR':'보완 교사','BC_FAIR':'보완 비용회귀 모방'}
a=read(O/'ACCOUNTING.json');d=read(O/'DIAGNOSTICS.json');py=read(O/'AUDIT_PY.json');js=read(O/'AUDIT_JS.json');m=read(O/'MODEL.json')
def pct(s):return 100*s['on']/s['n'] if s['n'] else 0
def table(rows,pattern=False):
    out=['|요청/초|'+('도착 패턴|' if pattern else '')+'정책|예측 소비 J*|평균 AP ℃|전체 정시 %|긴급 정시 %|일반 정시 %|긴급 P95 초|일반 P95 초|미응답/미완료|','|---:|'+('---|' if pattern else '')+'---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for x in rows:
        s=x['service'];v=x['common'] if pattern else x
        out.append(f"|{x['load']}|"+({'uniform':'균등','burst':'8건 묶음'}[x['pattern']]+'|' if pattern else '')+f"{names[x['policy']]}|{v['J']:.3f}|{v['AP']:.3f}|{pct(s['ALL']):.3f}|{pct(s['U']):.3f}|{pct(s['N']):.3f}|{s['U']['P95']:.6f}|{s['N']['P95']:.6f}|{s['ALL']['missing']}/{s['ALL']['incomplete']}|")
    return '\n'.join(out)
main=[x for x in a['aggregates'] if x['policy'] not in ('TEACHER_OLD','BC_OLD')]
old=[x for x in a['aggregates'] if x['policy'] in ('TEACHER_OLD','BC_OLD')]
deltas=['|요청/초|비교 대상|소비 절감 J*|소비 절감 %|전체 정시 변화 %p|긴급 정시 변화 %p|일반 정시 변화 %p|긴급 P95 변화 초|','|---:|---|---:|---:|---:|---:|---:|---:|']
for x in a['deltas']:
    if x['policy']!='BC_FAIR' or x['reference']=='TEACHER_FAIR':continue
    deltas.append(f"|{x['load']}|{names[x['reference']]}|{x['energy_saving_J']:+.3f}|{x['energy_saving_percent']:+.3f}|{x['all_on_change_pp']:+.3f}|{x['urgent_on_change_pp']:+.3f}|{x['normal_on_change_pp']:+.3f}|{x['urgent_P95_change_s']:+.6f}|")
assert len(a['rows'])==28 and len(a['aggregates'])==14 and all(x['teacher_BC_requests_actions_trace_exact'] for x in d['matched'])
write('REPORT_KO.md',f'''# 일반 요청 보호·모방 오차 보완 후 같은 S26식 입력 비교

2026-10-21 · A24-SERVICE-BC-02 · HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf + 로컬 미커밋/미게시.

보완판은 4건/초에서 기존 BC보다 전체 정시 89.083→94.271%, 일반 정시 92.299→99.531%로 개선했다. 같은 조건 EDF보다 소비 30.192J*/2.188%·평균 AP 0.585℃ 감소, 전체 정시 +3.042%p·긴급 +13.169%p·긴급 P95 0.157초 감소다. 일반 정시는 EDF보다 9건/0.248%p 낮고 일반 P95는 0.354초 길다. 일반 요청 밀림은 크게 줄었으나 해소 보증은 아니다.

## 요청한 다섯 정책

{table(main)}

1건/초는 두 패턴 합계1,200건(U312/N888), 4건/초는4,800건(U1,177/N3,623). 균등·8건묶음 두 패턴의 J*/AP는 평균, 정시율은 도착건수 합산, P95는 완료 응답을 합친 nearest-rank 값이다. 모든28행 미응답/미완료0이며 지각은 정시율에 남긴다. 두 패턴을 추가 반복/독립표본으로 간주하거나 통계적 유의성을 주장하지 않는다.

S26식 입력은 앞선 요청평가의 예정 도착·분류/탐지 구성·기한·입장지터·양경로 잠재작업을 exact 재사용한다. 실제기기 S26의 성능/계수를 A24에 대입한 것은 아니다. 기존 A24 ORIGINAL/CPU3·GPU1/beta.25·600초 공급을 유지했다. FIFO/EDF/RR은 기존 현재상태 최소예측응답 장치배정이며 RR은 C/D요청군 교대·군내FIFO·비선점이다. 각 case의7정책이 모두 끝나는 같은 창으로 소비/AP를 다시 계산했다. J*는 미교정 모형의 예측 소비이며 실측 J/실기기 절감이 아니다.

## 개선 전 두 정책도 보존

{table(old)}

보완 비용회귀 모방의 비교 대상 대비 개선·악화다. 소비 절감은 비교 대상에서 보완판을 뺀 값이며 음수는 소비 증가다. 정시율/P95 변화는 보완판에서 비교 대상을 뺀 값이며 정시 음수는 악화, P95 양수는 지연 증가다.

{chr(10).join(deltas)}

## 실제로 무엇을 보완했는가

교사/모방 모델 공통으로 예측 전체 지각 건수→긴급 지각 건수를 사전식 최소화하고, 그 후보 안에서 여유시간이 다음 최대WAIT+물리tick 이내인 아직 정시 가능한 일반 요청의 즉시배정을 보호한다. 남은 후보의 소비·열·평균/최대 상대지각·미완료·응답비용을 비교하며 지각량의 기존 min(5) 포화를 제거했다. 이는 공개 명목예측의 판단이며 실제 최적/EDF비 비악화 제약이 아니다. 원 물리/ATC후보/롤링 EDF후속/공통예측창/기존 유휴WAIT필터는 유지했다.

**보완 모방 모델은 기존50특징 신경망 BC를 재학습한 모델이 아니다.** 원망 cec00807은 보존하고, 새 TRAIN의 후보별 교사비용을 학습하는6특징 비용회귀형 모방/정책증류를 별도로 만들었다. TRAIN6궤적768요청/1,496상태/8,456후보의 RMS정규화 최소제곱1회다. 가상42℃2궤적은 같은 TRAIN요청/표본의 온도가정 대조이며 독립 실측자료 추가가 아니다. EVAL학습/epoch/optimizer/seed탐색0이다.

TRAIN 호환모방100%, EVAL {py['learned_EVAL_choices']:,}선택에서 새교사와 행동·요청별응답·물리trace가 모두 동일했다. 교사선택 덮어쓰기 없이 학습 계수로 선택했지만, 선형 교사식을 같은 비용 특징으로 배우므로 이렇게 되는 것이 예상된다. **BC의 교사 대비 별도 최적화 성과/계산 절감은 없다.** 정책 개선은 새 서비스 규칙과 교사 재현의 결합 결과이며 둘의 기여를 추가 ablation으로 분리하지 않았다.

TRAIN에서 미완료비율 특징이 항상0이어서 유효rank5/6이고 그 계수는 식별되지 않아0이다. EVAL에서도 해당 특징 비영0건이므로 이번 동일성은 성립하지만 미완료 후보가 생기는 새 조건의 정확모방은 미검증이다. 공통 동점허용1e-8, EVAL 최대 점수잔차 {py['EVAL_max_teacher_score_error']:.3g}, 최대교사최솟값차 {py['EVAL_max_teacher_regret']:.3g}다.

## 검증과 실행 기록

새 TRAIN6+실제fit1+EVAL8=15 START/COMPLETE15, 환경FAIL/SKIP0. 기존20완료를 재실행하지 않고 저장재사용했다. 마지막 배치 인덱스 검사에서 FEATURE_NAMES 튜플/JSON배열의 형식차이 AssertionError1건이 있었고 원오류/소스를 보존했다. 모든 궤적 전후 deepcopy불변 검사와 fit영수증 모델SHA가 통과했으며 저장자료만으로 인덱스를 복구했다. 과학재시도0이다.

순수14·입력준비1,540, 독립JS {js['checks']:,}(물리 {js['independent_math_checks']:,}/선택 {js['decision_checks']:,}), 별도Python/50자리Decimal의 입력결합 {py['source_request_bindings']:,}·TRAIN상태1,496/후보8,456·학습계수 재계산 오차 {py['independent_normal_equation_max_coefficient_error']:.3g}, 원망/새모형/소스 불변 PASS다. 소프트웨어 고정모형 검증이며 실제 물리정확성의 검증은 아니다.

[전체 패턴28행](ALL_ROWS_KO.md) · [남은 원인과 모든 손해](INTERPRETATION_KO.md) · [원 집계/전체 차이](ACCOUNTING.json) · [일반요청 지각 상세](REMAINING_LATENESS.json) · [실행 오류 보존/저장복구](SAVED_FINALIZATION_RECOVERY.json) · [완료·재개](CONTINUE_RUNNING.md).
''')
write('ALL_ROWS_KO.md','# 패턴별7정책28행\n\n균등/8건묶음·각600초·1/4건/s. 아래 정시율은 각행의 모든 도착 분모이며 J*/AP는 같은case7정책 공통창이다. 기존20행 저장재사용+새EVAL8행=28행이며 새TRAIN6은 아래 평가표와 별도다. 모든 환경은 완료했고 마지막 배치 인덱스 검사의 형식 오류는 원기록을 보존했다.\n\n'+table(sorted(a['rows'],key=lambda x:(x['load'],x['pattern'],list(names).index(x['policy']))),True)+'\n\n[집계와 판정](REPORT_KO.md) · [집계 원자료/창/분모](ACCOUNTING.json)\n')
qtable=['|요청/초|패턴|정책|일반 큐평균 초|일반 큐P95 초|일반탐지 큐평균 초|일반탐지 큐P95 초|정책WAIT 초|일반임박보호 호출|','|---:|---|---|---:|---:|---:|---:|---:|---:|']
for x in d['rows']:
    if x['policy'] not in ('EDF_DYN','BC_OLD','TEACHER_OLD','BC_FAIR'):continue
    n=x['groups']['N']['queue'];dn=x['groups']['D_N']['queue']
    qtable.append(f"|{x['rate']}|{x['pattern']}|{names[x['policy']]}|{n['mean']:.6f}|{n['P95']:.6f}|{dn['mean']:.6f}|{dn['P95']:.6f}|{x['policy_WAIT_s']:.6f}|{x['guards'].get('normal_protection_calls',0)}|")
write('INTERPRETATION_KO.md',f'''# 판정: 일반 요청 밀림과 모방 오차

2026-10-21 · 알려진 S26식 benchmark에서의 A24 수정 비교, 새독립확인/실기기효과/자동채택0.

## 개선과 대가

4건/초에서 기존BC 대비 일반정시3,344→3,606(+262), 긴급932→919(−13), 전체4,276→4,525(+249)다. 소비는12.711J*/0.951% 증가하고 AP0.254℃ 증가했다. 긴급P95는1.720624→1.488037초로0.232587초 감소했다. 일반정시99.531%는FIFO99.724/EDF·RR99.779%보다 낮으며, 일반P95는2.511174초로EDF2.157115초보다0.354059초 길다. 따라서 모든 기준에서 더좋다는 판정은 하지 않는다.

4건/초 EDF와비교하면 전체정시+146건=긴급+155/일반−9건이다. 균등은 전체2250→2301(+51), 묶음2129→2224(+95)다. 같은요청의 손익은 [DIAGNOSTICS.json](DIAGNOSTICS.json)의 matched에 모두 보존했다. 묶음 일반은 EDF정시→새지각11건·EDF지각→새정시3건으로 순−8이며 균등−1과합쳐−9다. 긴급도 개별손실이 있어 합계 개선만으로 모든요청 개선을 주장하지 않는다.

1건/초는 기존BC보다 전체1187→1192(+5)·소비−0.631J*/.068%, EDF보다1191→1192(+1)·소비−8.970J*/.953%다. 반면 기존교사1197→1192(−5), 소비+2.628J*/.283%로악화다. 새교사의 저부하 긴급 최적성은입증되지않았다. 균등1건/초는정시100%/FIFO·EDF·RR·기존BC·보완2정책 소비응답동일이며개선은묶음에서생겼다. 저부하 긴급P95는EDF보다0.033451초/일반P95는0.188310초길다.

## 일반 요청 지연이 줄어든 연결고리

기존교사는정규화한긴급/일반지각률12:6 가중합과지각량포화로전체정시건수손해를소비/긴급이득과교환할수있었다. 새교사는공개명목예측전체지각건수→긴급건수를먼저비교하며, 같은서비스후보중정시가능한일반요청의배정여유가작으면즉시배정을보호한다. 오래미룬요청의상대지각도계속증가한다. 새BC는그교사를비용회귀로재현하므로구망의잘못된WAIT/요청순서선택이새교사와일치한다.

{chr(10).join(qtable)}

4건/초 일반임박보호는균등129/묶음378회다. 정책WAIT는자원이이미작업중인시간과겹칠수있으므로전부유휴낭비로해석하지않는다. 두보완평가모두예측800step축소0/공개32초과0이고 BC의선택은교사와100%같다. 이범위에서는남은손해를BC오분류/예측cap때문이라고설명할수없다. 규칙묶음과모방모델을함께바꿨으므로개별규칙의인과기여는분리실험하지않았다.

## 일반 지각17건이 남는 이유

보완4건/초 일반지각은균등1/묶음16건이다. 실제선택경로의비경합·무열 private작업을배정시각에더했을때이미늦는것은1건이고, 나머지16건은실제열/CPU경합에의한진행량저하가더해져야지각한다. 이는그요청의선택경로/실제배정에대한사후분해이며더이른배정이불가능했다는증명이아니다.

배정시공개명목롤링은17건중8건을정시로예측했으나실제로지각했고9건은이미지각을예측했다. 고정명목과private작업차이·후속CPU경합·EDF예측후속과실제정책재호출차이가남아있어예측서비스최선이실제정시제약이되지않는다. 일반임박보호도현재정시가능하고서비스최선후보안에있을때만작동하므로이미늦은요청/충돌하는요청모두를구제하지않는다. [17건별시각/배정예측/큐](REMAINING_LATENESS.json)에전량보존했다. 미래latent를정책에노출하거나실기기계수를새로맞추지는않았다.

## 모방 결과의 정확한 의미

원50특징36후보 행동분류망 cec00807을개선해수렴시켰다는결과가아니다. 해당망과원자료는그대로두고같은산업공학스케줄링판단의후보별6공개비용을회귀하는별도모방모델을학습했다. TRAIN1496상태/8456후보와가상42℃조건을포함했고EVAL상태학습0이다. 학습후의효과는교사식재현이며 BC가교사보다좋은정책을발견한것이아니다.

같은선형비용특징으로선형교사식을학습하므로현재문제에서는직접교사를써도동일결과다. 모방을위해둘다롤링계산이필요하므로추론속도·제어에너지절약증거도없다. 미완료비율은TRAIN/EVAL모두0으로미식별계수0이며그범위밖정확성은미검증이다. 원망을새모델로자동교체하지않았다.

## 검증・오류 보존과 제한

독립JS/Decimal/출처·공통창·서비스·선택검산PASS다.15 START모두정상과학종료후마지막배치저장검사에서튜플/배열형식차이오류가났고 [원오류](BATCH_FAILURE.json)/[저장복구](SAVED_FINALIZATION_RECOVERY.json)를보존했다.각episode의in-memory전후불변과fit영수증SHA불변을확인해재실행0으로인덱스를복구했다. 최종소스는실행중변경0이다.

기존비교결과를본후설계한수정이므로새holdout검증이아니다. A24 C_CPU원세션공유·가상CPU3·미교정전력·단순열/경합가정·모델제어비용누락은유지한다. 좋은benchmark성적을실기기절감/일반성/최적성으로확장하지않는다. 추가튜닝/ablation/PPO/실측/자동실험·채택/게시0이다.

[집계14행과요청한5정책](REPORT_KO.md) · [모든28행](ALL_ROWS_KO.md) · [완료·재개](CONTINUE_RUNNING.md).
''')
write('CONTINUE_RUNNING.md',f'''# A24-SERVICE-BC-02 완료·재개

현재는실행종료다. TRAIN6+BCfit1+EVAL8=15 START/COMPLETE15·환경FAIL/SKIP0, 마지막배치JSON형식비교오류1은원기록보존/저장인덱스만복구했고과학재시도0이다. 기존20평가저장재사용·새환경14이며완료한실험을재시작하지않는다.

기준branch codex/a24-simulator-handoff-20261016, HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf. 모든새코드/결과는로컬미커밋/미게시,새교사/모방모델자동채택0이다. 로컬예약합산137906+15=137921은전호스트census/사용자직접숫자상한이아니다.

[판정](INTERPRETATION_KO.md) · [요청한5정책/14집계행](REPORT_KO.md) · [28행](ALL_ROWS_KO.md) · [독립JS](AUDIT_JS.json) · [독립Decimal/학습출처](AUDIT_PY.json) · [요청손익/큐/가드](DIAGNOSTICS.json) · [남은17일반지각](REMAINING_LATENESS.json) · [원실행오류](BATCH_FAILURE.json) · [저장인덱스복구](SAVED_FINALIZATION_RECOVERY.json) · [최종봉인](FINAL_PROOF.json) · [재확인](FINAL_RECHECK.json).

새교사는전체예측지각건수→긴급건수·일반임박보호·비포화지각비용,새모델은TRAIN후보6비용의회귀형모방/정책증류다. 원50특징행동분류망재학습성공이아니다.1496 TRAIN상태/8456후보·1least-squaresfit,미식별미완료비율특징0/유효rank5다.4EVAL에서11438선택/요청응답/trace가교사와exact같아BC별도성능이득0이다.

4건/s 기존BC비일반정시3344→3606(+262)·전체4276→4525(+249),긴급932→919(−13),소비+12.711J*/.951%다.EDF비소비−30.192J*/2.188%·전체정시+146/긴급+155/일반−9,긴급P95−.156637초·일반P95+.354059초다.1건/s에서는기존교사보다전체5건/소비손해도있다.모든평가미응답/미완료0이며실기기절감/새holdout/최적성은미입증이다.

다음은보고서/변경diff검토와사용자질문응답이다.자동추가학습/실험/원identity재시작/물리fit/PPO/실측/게시를예약하지않았다. 후속실험은새입력/소스/유한범위/identity로별도등록한다.
''')
print('REPORTS_WRITTEN',len(a['rows']),len(a['aggregates']),flush=True)
