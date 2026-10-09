# 후속 J/AP 오차 토론: 시뮬레이터·정책·모형 인터페이스 AI 검토

> 최초 실행전 권고는 하단의 **후속 AP 반론과 20fit 제한 대조**였다. energy-only 10fit 의견을 보존했고, root가 동일 AP basis의 계수5 재추정을 추가 제안한 뒤 두 동료와 직접 토론해 조건부 허용으로 수정했다. 실행전 검토기록은 그대로 보존했다.

> **최종 결과 판정은 맨 아래 round4를 따른다.** parent가20fit·35평가를 완료했으며 E_U/AP_C를 평가전에 동결했다. 이검토자의추가fit은0이다. 후보는전체업그레이드미채택,주권고는기존zero-offset+기존LOAD_SLOW 유지다. 새candidate는hash/조건을명시한전이진단계산으로만사용한다.

2026-10-10. **AI 검토이며 사람 전문가 인증이 아니다.** 기준 HEAD `29af09df041ae413aa547aa1df22d755b9b39a3f`, `feature/arrival-scheduling-20260923`. 최신 zero-offset 문서·코드·저장 결과와 관련 기존 자료를 읽었다. 이 노트 외 파일을 수정하지 않았으며, 별도 RL 작업의 STATUS/PLAN/DECISIONS·소스·설정·출력·프로세스는 변경하지 않았다. 새 fit·정책/전체 배치·ADB·실측·설치·빌드는 0회다.

## 판단

**세션 중심화로 p4를 추정하는 가설은 시도할 가치가 있다. 그러나 같은13 자료의 비중심화 대조가 반드시 필요하며, 두 추정법 모두 무부하 배경변동을 해결하지 못한다.** 중심화13과 현재 macro4만 비교하면 자료 확대와 추정법 변경을 혼동한다. root의 후속안인 동일13/동일5초/동일세션가중치의 비중심화·중심화 두 경로, source-group 제외4+최종1씩 **최대10fit**을 유한한 대조로 권고한다. 현재 이 fit을 실행하거나 성과를 확정한 것은 아니다.

이번 비교는 **J를 추가 개선할 수 있는가**라는 새 질문이다. AP는 고정 LOAD_SLOW이므로 이번 두 energy 경로에서 새 AP 오차 감소는 수학적으로 생기지 않는다. 새 J개선+기존 AP개선 유지가 확인되면 제한적인 공동 비악화는 가능하지만, ‘J/AP 모두 추가 감소 완료’라고 부르지 않는다. 새 p4를 기존 AP proxy에 강제로 넣어 새로운 AP 성과를 만드는 것은 허용하지 않는다.

## 최신 실체와 남은 오류

`d1_energy_ap_zero_offset.py`는 실제 개발4의 LOSO4+최종1로 p4를 추정했고 별도 비용API를 구현했다. 예측은 `P50*(hi-lo)+exposure·p4`, δ=0이다. AP의 원 proxy/계수는 불변이다.

- LOAD 같은 J/AP 관측창37.4174..2554.5103초: J signed −23.060→−6.187J, AP MAE0.43731→0.17296°C. 등록600초 J −15.151→+2.081J. 전체 평균만이 아닌 국소5/10초 잔차와 상쇄도 공개했다.
- 과거29 참고120초 J MAE5.522→5.144J이지만10악화다. 과거개발3 평균은 악화했다. AP 과거13악화는 그대로다.
- 기존 지속4짝 A의 차이 MAE6.322→6.219J, 부호오판2/4 유지. B17은 저장 forecast의 비용투영만이며 J MAE6.118→5.681J/6악화다. 새로운 일정/응답 예측 검증은 아니다.
- C0와 순수 유휴에서는 state exposure=0이므로 p4를 바꿔도 예측은 P50만 남는다. 중심화/비중심화 모두 C0의 미래 배경J 오차를 줄일 수 없다.

고정 API는 명시적 opt-in의 macro6만 제공한다. 일반 도착·RL·strict 지원으로 확대되지 않았다. 결과를 보고 지원 profile/온도/이력을 고르지 않는다.

## root 가설의 정확한 의미

세션j의 고정5초 bin k에서 관측 에너지와 상태 점유를 다음처럼 쓴다.

```text
Y_jk = observed_J_jk - 5*P50_j
X_jk = 실제 네 상태의 점유시간 vector

비중심화: p>=0, Σ_j (1/n_j) Σ_k (Y_jk-X_jk·p)^2 최소화
중심화:   p>=0, Σ_j (1/n_j) Σ_k ((Y_jk-mean_jY)-(X_jk-mean_jX)·p)^2 최소화

동결 후 예측: E(lo,hi)=P50_j*(hi-lo)+exposure(lo,hi)·p
예측 시 세션의 미래 mean_Y/offset은 사용하지 않음
```

중심화에서는 세션마다 일정한 nuisance가 Y에 더해져도 제거된다. P50가 실제 해당 fit 구간의 background 평균과 일정하게 다르면 그 차이를 state p4에 흡수하는 문제를 줄일 수 있다. 이는 상수 nuisance 가설이며 시간에 따라 달라지는 background와 작업 상태/순서의 상관을 제거하지는 못한다.

출력 계수는4개지만 학습에서13개의 세션 평균/절편을 투영해 제거한다. **전체 학습 자유도가4개뿐인 것은 아니다.** 학습 nuisance는 forecast 가능한 계수로 전달하지 않고, heldout 세션의 post-W/mean_Y로 절편을 추정해 예측에 넣지 않는다. 추정 미사용 데이터를 가운데 맞춘 뒤 높은 정확도라고 보고하면 목표 누설이다.

centered X와 Y는 음수가 자연스럽다. 비음수 제약은 p에만 적용하며 X/Y를0으로 자르지 않는다. 같은 상태가 계속 꽉 차서 모든 X행의 합이 상수인 자료만 있으면 공통 전력수준이 소거되어 rank가 부족할 수 있다. 이번 자료에는 idle·단독·병행 변화가 있다. 동료 identification AI의 design-only 계산은 centered13 rank4/정규화 condition 약1.198, old3 약1.329/history6 약5.619/macro4 약1.295를 확인했다. 이는 수치 계산 가능성이지 순수 부품W·미래오차한도 인증이 아니다.

## 개발13 재사용: 타당한 범위와 전이 위험

개발13은 old arrival3 + history30초3 + history180초3 + macro4다. 두 history 묶음은 한 프로토콜의 초기이력 차이므로 **4개 source-group, 3개 프로토콜**이다. 이를4개 독립 날짜/통제된 실측 block 또는 동일조건13반복으로 부르지 않는다.

identification AI는 native13의 device/model/runtime/tensor/input/execution/comparator·CPU1·4resident core가 같음을 직접 대조했다고 공유했다. 기존 개발9 호환성 기록도 같은 core를 확인한다. 다만 관측 조건은 다르다.

| 차이 | 해석 |
|---|---|
| old/history resident baseline30초 vs macro120초 | pre50 창이 같아도 준비·숨은 이력은 다름 |
| common120초 vs600초, cooling60초 vs180초 | loss의 시간 규모·순서와 평가 horizon이 다름 |
| online-power-phase-audit-v1 vs resident-identification-power-v1 | 모두900ms이나 동일 계측 비용/동일 관측조건 인증은 아님 |
| APK5c284…/3840…/57d232… | logger·conditioning·실행 경로 변형을 보존해야 함 |
| history의 conditioning CPU96 + recovery30/180 | C0도 조건화 이력은 있고 평가창 본작업은0 |
| macro의 854/854/857/853 본 요청 | 원 실제 완료/lane를 사용. 600초 예정점유나 최대호출수로 바꾸지 않음 |

따라서 ‘13개를 같은측정법으로 합쳤다’가 아니라 **같은 core 작업의 multi-protocol 비용 전이 가설**로 등록해야 한다. hard gate는 모델/입력/정밀도/런타임/CPU/resident, W 단위·raw bracket·clock origin·상태/lane 정의의 의미가 일치하는지다. APK·prep·collector 변형은 명시한 source-group 검증 대상으로 남긴다. 변형 때문에 target의 의미가 달라지거나 단위/원점/실제lane를 재현할 수 없으면 pooling 전 중단한다. 단지 version 문자열이 다르다는 이유로 동일조건이라고 하거나, 모든 차이를 중심화가 지웠다고 단정하지 않는다.

**작업수/표본수:** legacy96 요청 세션과 macro 약854 요청 세션을 동일 loss에서 요청 수로 가중하면 macro가 지배한다. 원안처럼 세션별 bin 수로 정규화한 동등가중을 유지한다. 센서 bins/요청을 독립13보다 많은 반복으로 계산하지 않는다. history 두 C0는 centered X=0으로 p4 식별에 기여하지 않지만 배경/검증 분모에서 보존한다. conditioning의 요청은 부하전 이력이며 이번 fit의35초 이후 노출에 넣지 않는다.

**회수·경계:** 검증된 canonical cache와 원 validation/cleanup 근거를 재사용한다. dispatch→execution→output→persist→worker_release→lane_available의 실제 순서와 pair→solo drain을 보존한다. 원 failed/stopped 자료를 성공 세션으로 합치지 않는다. 고정 fit bins는 legacy35..120초, macro35..635초의 완전5초 bins다. tail이 길다는 이유로 임의 추가 train 구간을 만들지 않는다. 전체냉각 끝이 센서가 덮이지 않으면 full-J는null, 덮인prefix만 별도 표기한다. 모든 추정법은 같은 유효행/같은 관측 경계를 사용한다.

## 최소 추정·선택 절차: 최대10fit에서 닫기

1. 원 input/cache/hash·roster13·세션별 구간·4source-group·노출state·same-unit/clock/lane gate를 고정한다. 중복 sustained8은 기존 panel처럼 제거한다. 동료의 native core 대조를 재사용하며 포괄 재감사를 반복하지 않는다.
2. 비중심화와 중심화를 같은13, 같은 bins, 같은 session weights, p>=0, P50 forecast로 비교한다. 각 경로 old3/history30x3/history180x3/macro4 제외4fit + 최종13fit1 =5, 합10fit 상한이다. 같은경로의13LOSO를 추가 독립검증처럼 붙이지 않는다. 새 λ/weights/offset/τ/window를 탐색하지 않는다.
3. 중심화의 순효과는 **같은 source-excluded 사례의 중심화−비중심화**에서 판독한다. 현재 macro4 zero-offset과 비교하는 값은 자료확대 효과까지 포함한 별도 historical 비교다. 센서 적분·nuisance 제거가 좋아졌다는 산술만으로 forecast J가 좋아졌다고 하지 않는다.
4. 선택은 source-group 제외 개발 결과에서 사전에 정한 J 전체창/단기창/최악/방향 기준으로 한다. seen 평가20/long2에서 잘 맞는다는 이유로 개발 gate 실패 경로를 승자로 바꾸지 않는다. 둘 모두 gate실패면 기존 경로 유지/미채택으로 종료하고 자동 재fit하지 않는다.
5. 별도 새 version/hash/receipt에 추정법·training nuisance 처리·fit call 수를 남긴다. 원 zero-offset/AP/기본/RL 후보와 결과를 덮어쓰지 않는다. 지금은 제안이며 이 노트에서fit0이다.

macro제외fold는 반드시 보존한다. history GPU단독 점유0.471/0.547초, 합1.018초는900ms 센서 정도의 길이에 불과하고 macro의 약60초 단독 노출보다 실용 정보가 약하다. rank4여도 계수 불안정/전이가 실패할 수 있다. 이를 사후 fold제거·추가GPU병행 미측정값·S26계수·정규화 튜닝으로 숨기지 않는다.

## 평가 분모와 A/B: 여기서 가장 쉽게 틀리는 부분

기존 zero-offset의 ‘archive29’에는 이번에 새 학습으로 들어가는 old development9가 있다. 새로운 역할은 **개발13 + 추정미사용20 + 긴2 =35**다. 전체35 원행은 유지하지만 개발13은 source-excluded 예측 또는 최종 in-sample을 명시하고,20+긴2는 학습미사용의 사후 평가로 표시한다. 이미 모든 자료를 본 구조선택이라 fresh blind는 아니다.

old29 평균과 new20 평균을 직접 차감해 ‘정확도 개선’으로 보고하면 분모가 다르다. 동일 사례·같은 창에서 원식/current zero-offset/noncenter13/center13을 비교하고 조건별 악화·오차를 공개한다.

**저장B17도 모두 새 heldout이 아니다.** old development3은 이번 train13에 포함되므로 energy 계수는 source-excluded CV로 별도 표시해야 한다. 그3의 기존 B 서비스시간 추정은 원래 개발에 사용됐던 이력이 있으므로 에너지CV가 종단간 독립확인으로 바뀌지 않는다. 나머지B14는 confirmation6+sustained8의 추정 미사용 저장비용투영이다. 35전체에서 B가 없는18(history12+macro4+long2)은null/미기록이며 실제 미래lane로 대체하지 않는다.

A는 실제 미래lane가 주어진 조건부 비용, B는 저장 forecast lane의 비용투영이다. 동일 initial/P50·같은 head·같은 horizon을 유지하고 `B-A` 비용차와 `A-observation` 잔차를 분리한다. 이번에는 새로운 서비스 모델·스케줄러·도착·응답을 생성하거나 열→처리시간을 만들지 않는다.

0..120과 future35..120을 같이 유지한다. 초기관측을 포함한0..35 회계를 과거보다 유리하게 바꿔 전체120초 개선으로 섞지 않는다. macro는 등록35..635, work span, idle/recovery, 같은 J/AP 공통query창을 별도 보고한다. 모든 AP 표본을 end까지 보간하거나 sensor null을0으로 채우지 않는다.

## 정책 차이와 동시 출력 인터페이스

기존4 CPU/PAR짝은 policy ID로 방향을 확인한 동일120초 `PAR−CPU` 차이를 A/B 각각 평가한다. 오차는 `(Jhat_PAR-Jhat_CPU)-(J_PAR-J_CPU)`다. 현재 zero-offset의 2/4 부호오판을 같은짝에서 다시 검사하며 평균 개별J만 낮아지는 경우와 분리한다. 그룹별 J MAE·5/10초 MAE·최악·부호상쇄·짝 delta MAE/부호를 같이 남긴다. 사후4짝 최대를 미래 universal bound로 쓰지 않는다.

두 추정법은 forecastP50가 같아 **세션별 pre50의 정책 baseline 차이는 그대로**다. p4 변화는 상태 노출차에만 작용한다. C0/순수idle J도 같다. 정책차가 background/이력/제어비용 때문에 뒤집힌 경우 중심화로 task p를 깨끗하게 추정해도 해결되지 않는다. 2/4가 유지되면 ‘개별비용 일부개선·정책차 미판정’으로 닫는다.

새 head를 쓰는 opt-in 경로도 macro6의 device/CPU1/4resident·준비/pre-AP·actual profile/state/time·APK/관측variant·P50[-20,30]·read-return<35 계약을 유지한다. 같은35 이전 입력 cutoff, head별 ID/hash, actual/storedforecast 구분, window/coverage, scope 밖 이유를 반환한다. API밖이면 J/AP/순위는null이다. 이전29 사후 진단 숫자가 있다고 API가 일반도착을 지원하는 것으로 처리하지 않는다. 기존 default/strict/RL에 자동 전달하지 않는다.

AP LOAD_SLOW는 에너지 source-group holdout과 같은 정보 역할이 아니다. macro4에서 이미 학습한 최종AP를 고정 재생하므로 macro 에너지holdout 점수와 함께 표시할 때 AP는 in-sample 재생이다. 긴2의 AP는 원래 사전고정 확인이었지만 새 energy 비교는 사후다. 이를 하나의 새로운 공동 독립확인으로 묶지 않는다.

## 다른 최소 구조와 데이터로 못 줄이는 항목

더작은 대안인 ‘각 macro active와 인접idle의 local contrast’는 state 정보를 활용할 수 있지만, 어떤 idle/window를 고를지와 잔열/배경오염 가정이 늘어난다. energy AI도 전체고정bin 중심화보다 이 대안을 우선 추천하지 않았다. 원 fixed13 전체세션 중심화가 이번 한정비교에서는 더 명확한 대조다.

끝까지 남을 수 있는 구체적 오류는 다음과 같다.

- 미래의 시간변화 background: pre50는 fixed이고 training constant nuisance만 제거하므로 C0/회복 idle 오차 불변.
- state와 시간변화 residual의 상관: source순서가 A/B인 macro와 conditioning history의 차이를 상수절편으로 모두 제거할 수 없음.
- 짧은 GPUsolo/혼합bin의 센서 resolution: 수백ms 요청별 ground-truth J를 만들지 못함. 개별request 서비스·전체도착 성공률과 sensor-level J/AP 검증을 구분.
- old AP13악화 및 fast/slow 물리/τ 식별: APhead 불변이므로 이 작업으로 새 개선이 생기지 않음.
- 실제 policy controller의 비용/초기이력 차이: 저장B17 비용투영이나4기존짝으로 독립 온라인효과를 인증하지 못함.

이 공백을 이유로 가능한 p4 전이 비교를 포기할 필요는 없다. 하지만 추정법이 실패하면 즉석 time-varyingδ/τ/새window/추가관측 진단으로 늘리지 않는다. 개발 gate와35전체같은창·조건별 악화·B17·짝4 결과를 끝까지 기록하고 부분개선/미채택/판별불가로 종료한다. 필요 추가실측은 후보동결 후 두head·실제lane·서비스분모·baseline readiness를 함께 확인하는 명시적 질문으로만 새 설계해야 한다. 이번에계획/실행/예산을 추가하지 않는다.

## 실제 토론과 반론 후 수정

root와 두 AI(`/root/energy_thermal_review`, `/root/identification_validation_review`)에게 독립1차요지를 직접 보냈고 질의·답변을 교환했다.

1. **1차:** centered13 한 family +4source-group 제외/final5fit, pre50/C0/유휴 문제는남는다고 제안.
2. **root 반론 수용:** centered13 vs macro4는 자료확대와중심화효과혼동. 동일13 비중심화 대조를 추가해2추정법/최대10fit로 권고를 수정. 두동료모두동의.
3. **identification 반론 수용:** 4source-group은3프로토콜+history2gap, native core가 같아도 baseline·APK·collector·length는 다름. 900ms동일을동일측정조건으로승격하지않음. 13개역할이동·B17중newtrain3분리를합의.
4. **energy 반론 수용:** centered negative X/Y clip금지, macro제외fold의 weakGPU정보를사후제거금지, seen20결과로개발선택뒤집기금지, training nuisance자유도별도명시. adjacentidle대조는추가창가정때문에추천보류.
5. **root에 유지한 반론:** AP 고정이면 이번 energy대조가AP추가감소를검증하는단계는아니다. 새에너지proxy를주입해동결AP확인을조용히바꾸지않는다. 새J개선+기존AP유지와두출력새학습성과를구분해야한다.

합의는 위 유한대조·데이터역할·범위·실패종료조건까지다. centered13이 실제로 더좋은지, source전이가 안정적인지, policy2/4를고치는지와AP추가보완구조는 미확정이다. 결과를 이미 본 자료에서 반복후보를 늘려 성공모형을 고르는 합의는 하지 않았다.

## 근거·검증 대상

- `docs/ENERGY_AP_ZERO_OFFSET_RESULTS_20261010.md`, `tools/d1_energy_ap_zero_offset.py`의 design/train/evaluate/forecast.
- `docs/results/energy_ap_zero_offset_01/run_v1/{candidate.json,energy_errors.csv,matched_joint_errors.csv,paired_errors.csv,stored_B_summary.json,retained_worsening.csv}` 및 registration/preload_availability/recorded_contexts.
- `tools/d1_joint_model_refinement.py:32` panel/role/dedup, `docs/JOINT_MODEL_REFINEMENT_RESULTS_20261008.md`, `docs/results/joint_model_refinement_01/{contract.json,compatibility.json}`.
- canonical `model_refinement_01/inputs.json.gz`, `history_model_refinement_01/inputs.json.gz`, `resident_identification_run_01/recorded_v3/inputs.json.gz`의13개role/경계/B저장여부.
- `docs/RESIDENT_IDENTIFICATION_RESULTS_20261009.md`, `docs/ENERGY_AP_HISTORY_CONTROL_DESIGN_20261007.md`의실제요청·conditioning·runtime/회수근거.

이번 명령은 UTF-8 문서/소스/CSV 읽기와 `python -B -c` 표준gzip/json/pathlib를 사용한 roster/role/관측·일정끝/B유무 확인뿐이다. 동료의design-only SVD/native core대조는그검토근거로표시했으며포괄감사/fit을재실행하지않았다. 테스트·Android빌드·실기기 PASS를새로주장하지않는다. 기준HEAD와미커밋RL문서/소스가있는작업트리를구분하고이노트만작성했다.

## 후속 AP 반론 — 동일 basis의 계수5 추가 대조는 조건부 허용

root는 첫 ‘AP 고정이면 추가 감소 불가’ 반론을 수용하고, AP도 기존LOAD_SLOW의 **exact basis와 시간계수는 유지하고 학습계수5개만** 다시 비교할 것을 제안했다. 이는 새energy proxy를 주입하거나 새τgrid를 탐색하는 제안과 다르다. 사용자 요청인 AP 추가오차 감소를 직접 시험하는 제한된 가설이므로 근거 없는 모형 확장으로 기각하지 않는다.

고정할 것은 원 β≈0.0459325203/s, preparationτ30초, slowτ1920초, pre-only RH 초기화, fast4 state basis, 기존 동결 전력proxy로 만든 slow1 basis다. S(35)=0의 기존 추가변화 의미도 보존한다. 새AP candidate/version/hash를 따로 만들며 원AP 후보를 바꾸지 않는다.

```text
원 exact AP basis: AP(t)=A_pre(t)+X_fast4(t)·theta_fast4+X_old_proxy_slow(t)*theta_slow

AP training target = observed_AP - A_pre
noncenter: 위 target과 원5열X를 동일session가중으로 NNLS(theta>=0)
center:   target와 원5열X를 각각 세션 내 평균제거 후 NNLS(theta>=0)
forecast: A_pre + 원(raw)X·theta
          training/heldout nuisance mean을 더하거나 미래AP로 맞추지 않음
```

initial AP 자체를 가운데 맞추면 안 된다. **APobs−A_pre 잔차**를 중심화해야 fixed 초기화와 candidate 효과를 구분할 수 있다. 음의 centered X/target은 정상이며 clip하지 않는다. 학습에서13 nuisance mean을 제거하되 forecast로 전용하지 않는 점은 E와 같다.

energy/identification AI의 rank-only 계산은 AP13의5열과4source 제외설계가 noncenter/center 모두 rank5임을 확인했다. 정규화 condition은 전체 약1.816/1.397, macro 제외 약3.627/2.730다. 하지만 centered slow 정보의 약93.3%가macro에서 온다. 좋은 수치rank는 짧은Arrival에서 slow를 실용적으로 식별했다는 증거가 아니다. C0의 fast/slow basis는0이므로 θ5를 바꿔도 C0 AP는 A_pre로 남는다.

### 최종 등록 상한: E/AP 각2추정법, 총20fit

| head | 자유롭게 다시 추정하는 계수 | 고정 | fit 상한 |
|---|---|---|---:|
| E noncenter13 | p4≥0 | P50/δ0/actual exposure·구간·가중치 | 4source 제외+final1=5 |
| E center13 | p4≥0 | 위와 같은 것, 세션mean 제거 규칙 | 5 |
| AP noncenter13 | theta5≥0 | A_pre/β/preptau30/τ1920/old proxy·query·가중치 | 5 |
| AP center13 | theta5≥0 | 위와 같은 것, residual mean 제거 규칙 | 5 |
| 합계 | 2head×2추정법 | grid/새window/λ/추가fit0 | **20** |

10fit 한도를 유지한 것처럼 AP를 몰래 더하지 않는다. 위20을 사전에 명시해 새등록해야 한다. 이는 현재 수행한fit수0과 별개인 후속 승인된 작업의 권고 상한이다. AP도 roster13, 원실측query/브래킷·실제일정의 full available AP 구간, 같은 session normalization을 고정한다. E5초 bins와 AP원query는 각head target의 원관측방식이며 임의로 서로 바꾸거나 샘플수로13독립세션을 늘리지 않는다.

### 선택 규칙: head별로 사전 동결, 평가22 이후 변경금지

추천은 **head별 개발 선택**이다. E는source-excluded의 동일사례 raw J 전체/단기/최악 기준으로 noncenter/center 중한경로를 선택하고, AP는source-excluded의 raw 절대MAE·최대·최고·회복방향 기준으로 한경로를 선택한다. 원/current head도 기준 대조로 유지한다. 같은source fold에서유리한추정법을각각골라섞는 새coefficient후보는 만들지 않는다.

이 방식은 E/AP의 물리수식을 결합하지 않으므로 J와°C에 새 임의가중α를 붙인 ‘균형 score’를 만들 필요가 없다. headwise 선택을 사전에 명시하고 나면 최대4조합 중평가22에서잘맞는조합을 고르는 별도 탐색을 하지 않는다. E/AP 각각 선택된 hash를 동결하고 같은35의 공통창에서 두출력 공동개선/상충을 보고한다. 한head가 개발 gate를 실패하면 그head는 원고정/미채택으로 남으며 ‘두head 추가개선완료’로 처리하지 않는다. 둘모두 실패하면추가fit없이종료한다.

AP에서 shape/centered training MSE가 줄어도 절대온도 오차가 커질 수 있다. 핵심 성공판정은 ν=0의 원(raw) 예측에서 같은query의 MAE·최대절대·최고차이·냉각방향이다. 불리한 group/조건/late구간을 제외하거나 ν를heldout에서재추정해성과를만들지 않는다. 기존AP13악화를원행에남기고새AP의개선/악화도같은사례와창으로비교한다. 새‘정확도 허용폭’을 평가후만들지 않는다.

### OOF와 근거 경계를 더 엄격히 표기

β/preparation/τ1920/원전력proxy는 과거 개발·이미본macro자료에 기반해 고정된 prior다. 특히 τ1920은macro결과로 선택된경계값이다. 따라서 이번 source-excluded APθ5 예측은 **고정basis에조건부인새계수 제외예측**이지 feature/시간계수 선택을포함한완전새OOF나물리τ 독립검증이아니다. macro 제외fold가좋아져도이기록을지우지않는다.20+long2 평가역시새후보선택시이미본사후평가다.

APhead에새energy p4를주입하지 않는다. fixedLOADSLOW예측을변경했다면새APθ candidate의사후성과로표시하고,앞선long2의원AP동결확인을새θ에도그대로전용하지않는다. 새C0·새로깅version·다른기기·다른열이력을검증완료로부르지않는다.

### API와 B 비용투영의 한계

현재 `d1_energy_ap_zero_offset.forecast`는 원 `d1_ap_tail_scope.forecast`를 호출하여 기존AP 후보를 계산한다. 새APθ를단순candidate파일교체나원scope hash갱신으로끼우지않는다. 후속구현은 새bundle의E/AP 각modelID/hash와동결선택receipt를명시적으로검증하는별도진입이필요하며원scoperules/predictor/원결과는보존해야한다.

macro6의기존 opt-in 조건은 유지한다. 같은계약이여도새AP가정확도인증된것은아니다. 이외profile/RL/strict요청은API의J/AP/null 차단을유지하고, 내부35사후 진단 숫자와실제API지원표를분리한다. 새p4와새APθ가다른source자료에잘맞았다는이유로scope를넓히지않는다.

저장B17에는같은frozeninitial과각head를 적용해비용만투영할수있다. old3의train역할/서비스모형개발이력,나머지14의추정미사용·사후역할,미저장18의null은유지한다. AP최고/면적/경로의policy 차이도비용투영 진단이며B서비스모델이나실제controller를검증한것이아니다. 새로운arrival/응답/열→처리시간을생성하지않는다.

### 실제 추가 토론과 최종 동의/미확정

root의AP후속질문을두AI에직접전달하고답변했다. energy AI는samebasis5θ의논리타당성/rank5를확인하면서mean을버리는trainingloss가절대AP를악화시킬수있고4조합의사후선택을금지해야한다고반론했다. identification AI도residualcentering·ν0예측·priorτ의조건부OOF·C0항등·macro slow정보지배를강조했다. 이반론을선택규칙/표기에반영해 **20fit동일자료제한대조를조건부허용**한다고root에직접회신했다.

현재합의는고정basis두head/두추정법·같은13·4group/final·20상한·head별사전선택·22사후전량평가·기본/RL/strict/원자료보존까지다. APθ5가정말더좋아지는지, E/AP각head의선택경로,macro제외전이,policy부호2/4개선은미확정이다. grid확대/새proxy/heldoutmean/유리group제외/실패뒤추가fit에합의하지않았다. 이번노트작성에서도fit0·batch0·기기0이며다른파일을변경하지않았다.

## Round4 — 실제20fit·35평가 후 판정과 사용조건

최종 결과에 대해 root와 두 AI에게 직접 반론을 보냈다. `session_contrast_cost_01/run_v1/selection.json`, `fit_receipt.json`, `receipt.json`, `summary.csv`, `paired_errors.csv` 및 새`d1_session_contrast_cost.py`의selector/forecast를 읽었다. parent가 수행한fit20과이검토자의fit0을구분한다. 평가후selector·계수·창을바꾸거나추가fit하지않는다.

### 최종 판단

**root의전체정확도업그레이드미채택/주권고zero-offset+원LOAD_SLOW유지에동의한다.** 새E_U/AP_C는일부창의실제개선이있어버릴자료가아니지만, 전체평가AP·정책차·긴LOAD J가악화하므로범용교체/정책사용을정당화하지못한다. 새explicit API가숫자를계산할수있다는것과채택은별개다.

| 동일평가·동일창 | prior → 새선택head | 판독 |
|---|---|---|
| held20 J0..120 MAE | 5.458883→5.384677J, 11/20악화 | 평균약1.36%감소,전조건개선아님 |
| held20 matched AP MAE | 0.343926→0.350781°C, 12/20악화 | 평균약1.99%악화 |
| LOAD등록600 J/AP | signed+2.080884→+0.988489J / AP0.186150→0.166706°C | 같은창양출력엄격개선 |
| LOAD matched full J/AP | signed−6.186783→−7.120730J / AP0.172962→0.128586°C | J절대오차악화/AP평균개선 |
| LOAD냉각 AP평균 | 0.168639→0.116568°C | 평균오차개선 |
| LOAD냉각 AP변화량 | 관측−0.700/old−0.6329/new−0.5670°C | 변화량오차약0.0671→0.1330°C로악화 |
| 지속4짝 A J차이 MAE | 6.2185→6.8991J, 부호오판2/4유지 | policy판별추가개선실패 |
| C0 J/AP | 기존과같음 | 고정pre와zero basis의구조적한계 |

held20의J120과APmatched는서로다른시간창이다. 그두평균을한개의같은창공동정확도라고묶지않는다. 기존archive29평균도여기newheld20평균과직접차감하지않는다.35분모는개발13+추정미사용20+긴2이며모두이미본자료의사후후보평가다. 긴2를새blind확인으로쓰지않는다.

### root판정에보탠반론: selector는채택gate가아니다

실제selector는source-equal mean(E는absJ/duration, AP는pathMAE)을우선하고worstsession동일metric을동률해소에쓴다. 두새추정법중E_U/AP_C를고른것이며 **prior대비비악화gate도최악절대오차보장도아니다.** AP개발키는C의mean0.296267<U0.372037인반면worstsessionMAE는C0.891189>U0.888031이다. 또한‘worstsessionMAE’는시간별최대절대오차와다른metric이다.

따라서‘개발선택완료→모형정확도채택완료’의연결을거부한다. 결과를본뒤UC나oldhead를새승자로바꾸면평가정보로재선정한것이다. **주권고prior유지는새selector를수정한것이아니라새후보의adoption을거절한판정**이므로정당하다. E_U/AP_C와그hash/선택receipt는그대로보존한다.

이번E승자는UNCENTERED이다. 따라서‘세션중심화로J/AP둘다개선했다’라는결론은틀리다. E의새자료13재추정성과와AP의center추정성과를각각같은13통제대조에서해석해야한다. 원macro4대비차이는자료확대효과도포함한다. AP_C는개발우위가held20전이로이어지지않았다. source-group제외개발이최종계수의같은성능을보장하지않으며, 이미고정된τ/proxy의선택편향과프로토콜차이도남는다.

LOAD600개선만으로fullhorizon개선이나열안전판정을주장하지않는다. 냉각의평균거리와변화량은다른metric이며이번에는한쪽만좋아졌다. ‘방향은맞았으니회복을해결했다’라고정리하지않는다. 이상쇄/전이실패를새τ·ν·late보정으로즉석수정하지않는다.

### 새API는어디까지정당한가

실제`forecast`는①새registration/20model/selection hash검증, ②원`zero_offset.forecast`의macro6guard·opt-in통과, ③새선택E/APfinal의raw예측을수행한다. 학습nuisance/미래AP평균은사용하지않고새energyproxy도AP에주입하지않는다. 반환값에`model_bundle=session_contrast_cost_01`, 선택head, source hashes, nuisance미사용, already-seen posthoc가있다. 이구조는기존기본을바꾸지않는 **명시적전이후보진단계산**으로타당하다.

정당한사용조건은기존등록macro6의A조건부재생이다: 같은device/model/input/runtime/CPU1/4resident, 준비/preAP/실제상태·시간·APK/관측variant, P50[-20,30]과read-return<35, finiteactual/query범위와coverage를확인하고새bundle/각선택hash를명시해야한다. 범위밖/opt-in없음/hash변경/초기정보미확인은null/blocked이며,실제미래일정이주어진조건부계산임을표시한다.

사용목적은고정candidate곡선/같은창오차의재생·비교와600/full/recovery상충설명이다. 새policy승자·AP안전limit·에너지절감·현APK온라인실행·B종단간지원·strict확대에쓰지않는다. API가J600과전체APquery곡선을같이반환할수있으므로caller는같은창지표를구할때APquery도명시적J창으로제한해야한다. 반환status를‘두출력600accuracyPASS’로읽히게하면안된다.

데이터13을학습에썼다고API를모든13프로토콜/새arrival로확장하지않는다. 현재코드는원macroguard를상속한다. B17은별도저장일정비용투영/old3개발역할+held14이며API의새도착지원이아니다. 미기록18은null로유지한다. policy짝4의관측초기이력/제어비용을통제한새실측효과로승격하지않는다.

### 독립확인과실패종료

현재실패한후보를반드시새실측으로확인할필요는없다.35결과와선택동결·반례·사용범위를정리하면이유한대조는종료할수있다.새계수/τ/grid/창/조합을계속늘리지않는다.

새독립실행이필수인질문은미래등록macro에새head를전용할때의같은horizon J/AP예측확인,또는실제CPU/PAR정책차를판별하려는질문이다. 전자는동결head와준비·pre정보가용·실제lane·서비스분모·J/AP공통창·회복변화량을한block에서확인해야하며후자는같은arrival의정책짝·순서·초기이력·실제제어비용을추가로구분해야한다. 목적없이macro2와policy4를합쳐자동6실행을만들지않는다. 이번에는새계획·실측·추가fit0이다.

### 실제round4대화와합의

identification AI와energy AI에게selector≠adoption, APmean선택과worst/절대최대의차이,API의macro6진단한계,LOAD600/full/냉각변화량상충을직접전달했다. 두AI는root의zero+기존LOAD주우선유지·새explicitdiagnostic API·전체미채택에동의했고, E선택이U인점을‘centering공동성공’으로쓰지말라는반론과평가후window별head자동선택금지를강조했다. 이를받아이번정리를작성했다.

최종합의는**새계수/selector불변·reselect0/추가fit0·35모두보존·주권고prior유지·새candidate전이진단만허용**이다. C0/background, AP과거전이악화, 작은정책차이판별은미해결로남긴다. 부분600개선을전체업그레이드로확대하지않고,결과가불리하다는이유로이번비교를없던일로만들지도않는다.

round4근거: `session_contrast_cost_01/run_v1/{selection.json,fit_receipt.json,receipt.json,summary.csv,AP_errors.csv,paired_errors.csv}`, `registration_v2.json`, `tools/d1_session_contrast_cost.py:123`/`:221`. 직접확인은문서·코드·저장CSV읽기뿐이며20fit는parent가완료한결과다. 이검토자는본노트append외변경·재fit·배치·기기·RL간섭0이다. 현재확인HEAD는`29af09df041ae413aa547aa1df22d755b9b39a3f`다.
