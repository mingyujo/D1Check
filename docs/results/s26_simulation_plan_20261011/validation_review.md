# S26 시뮬레이션 계획 — 검증·데이터 계약 검토

2026-10-11. 역할: 검증 설계·자료 계약·성공 판정. 시작 HEAD `8175aac95c82fa70860e07e2e7566797b92b7736`와 다른 WIP를 확인했다. **계획·읽기 전용 검토이며 fitting·실기기·배치 실행은 0**이다. 이 파일만 작성했고 기존 계획·코드·원자료·desktop/RL 작업은 수정하지 않았다. 통합 제안은 [S26_SIMULATION_PLAN_20261011.md](../../S26_SIMULATION_PLAN_20261011.md)를 따른다. 아래 수치와 한도는 별도 표시한 관측 사실을 제외하면 **후속 사전 등록을 위한 제안**이다.

## 1. 현재 가용 결론과 검토 한계

- GitHub에 S26 시뮬레이터가 이미 있다. 기존 `d1sim` 환경·정책 평가·v3 예측·profile/throttle 및 버전별 model-error/GPU-holdout 경로를 재사용하는 방향이 적절하다. 과거 README v0의 “검증 전” 문구를 현재 모든 버전의 판정으로 확대하지 않는다. 이번 검토는 전체 엔진 실행·기존 모든 holdout의 수치 재현을 수행하지 않았다.
- R3/R4C/R4S는 새 모델을 만들기 전에 원결과·원장까지 이미 본 자료다. R4C의 원래 `split=confirmation`은 보존하지만, 새 family·계수를 선택한 뒤 같은 R4C를 **새 blind 독립 확인**이라고 부르면 안 된다. 새 모델의 R4C 판독은 held-from-fit 사후 전이 평가다.
- 기존 S26 분류·단일자원 시뮬레이터와 최신 두 모델 mixed 요청 자료는 서로 다른 계약이다. 자료가 Git에 있다는 사실은 그 자료가 기존 엔진에 자동 통합됐다는 뜻이 아니다.
- CPU/GPU/NPU 실행 근거, 출력 품질, 간섭·병행 지원, 에너지 적격성, 예측 정확도, 정책 효과는 각각 다른 gate다. 하나의 PASS로 다른 칸을 채우지 않는다.
- 원격 자료는 아래 고정 HEAD의 원장·품질 판정·대표 manifest/requests·관련 코드/트리 일부를 읽었다. **전량 raw 감사나 전량 판독은 미실행**이다. R4S 전체 roster·모든 실패 prefix·모든 모델 오차 수치를 독립 재계산했다는 주장은 하지 않는다.

검토 원격 버전은 measure `0a0749890fba2452c5907433c6bea476a2da7e24`, mixreq `21cba44faa5fff1fb9703b590aa536a6207f8de5`, quality20 `5857152ad8244c41975843ded77dd33024f38f2d`다. 토큰·민감 logcat·기기 주소를 공유하거나 거대한 clone을 만들지 않았다.

## 2. 1차 의견 → 반박 → 2차 합의

| 쟁점 | 1차 의견 | 상호 반박과 최종 합의 |
|---|---|---|
| 개발/평가 분리 | 원자료를 개발과 확인으로 구분 | 같은 run의 12요청·부하창·회복창을 서로 다른 fold에 넣으면 초기 열 이력과 세션 상태가 공유된다. **pair/day/session 전체를 묶고**, 기존 확인은 사후 전이로 표시한다. |
| 서비스 | 고정 경계·정책별 서비스부터 재생 | 온도→response 직접 fitting은 queue·시간·누적 점유·CPU 전후처리와 교락된다. S0 고정 phase, S1 시간 또는 누적 점유 **한 변수**까지. 온도→service S2는 별도 원인 분리 자료가 필요한 후속으로 보류한다. |
| 열 | pre anchor와 간단한 반응부터 | R4S 유효 표본 최고가 비슷하다고 전역 38.1°C clip을 넣으면 실패 prefix의 더 높은 관측을 숨긴다. AP/SKIN 별도 T0/T1, 실패 prefix 보존, 2RC/ML 동시 탐색은 현재 후보에서 제외한다. |
| 에너지 | S26 pre baseline와 상태 전력 | A24 prelate/τ30 보정은 다른 기기에 자동 전용할 수 없다. E1 즉시 등록을 보류하고 E0만 제한 진단한다. E_int/E_cc는 같은 fuel-gauge의 내부 교차검사이며 외부 절대 교정이 아니다. |
| 실패·불균형 | 유효 세션의 완성 창 분석 | valid-only 평균은 가장 뜨거운/느린 실패를 제외할 수 있다. 전체 slot·attempt·준비/중지·미완료를 남기고, N 유효짝2/A4의 불균형을 공개한다. 결측 full-window 목표값을 0이나 예측으로 채우지 않는다. |
| 품질 | Q20 실행/출력 확인 | quality-runner의 별도 APK와 request-runner가 완전히 같다는 근거가 아니다. GPU 실제 정밀도/NPU FP16 합격선 보류를 유지하고 **연구 관측 재생과 승인된 정책 후보 mask를 분리**한다. |
| 기존 엔진 | d1sim 재사용 | old MobileNet 열구조·CPU4·FG/BGchunk의 검증을 새 CompiledModel CPU1·두 모델 mixed 계약에 전용하지 않는다. 소스 재사용과 프로파일 전이를 구분한다. |

열 역할의 시간/누적 점유 대조, 에너지 역할의 powersample-only·C2 제한에 동의한다. 추가 반론은 다음 두 가지다.

1. 짝 bootstrap/CI가 좁더라도 단위 오류·공통 측정 bias가 사라지는 것은 아니다. 에너지 내부 채널의 정책 차 부호가 다르거나 변화가 계측 불확실 범위 안이면 정책 J 방향은 보류한다.
2. 오래된 온도·처리율 모형의 반응을 새 요청의 response에 바로 연결하면 실제 queue/저장·lane 해제 오차를 열 효과로 설명할 위험이 있다. 미래 실제 점유·후반 AP·실제 마지막 완료를 B 예측 입력으로 사용하지 않는다.

## 3. 기존 S26·최신 mixed·우리 A24의 차이

| 비교 항목 | 기존 S26 d1sim 주경로 | 최신 S26 R3/R4 mixed 자료 | 우리 A24 v3 hybrid |
|---|---|---|---|
| 작업 단위 | FG EfficientNet 1추론 / BG 128추론 chunk | 실제 분류·탐지 요청, 각 세션192 예정 요청 | 실제 분류·탐지 요청, 해당 확인96 요청 |
| 자원 | NPU 또는 GPU 단일자원, one-at-time·비선점 | CPU/GPU 또는 CPU/NPU의 기록된 배정·겹침 | CPU/GPU, 검증된 조합 최대2 병행 |
| 실행기·프로필 | v22 MobileNet 열구조＋EffNet g_m, CPU4 Interpreter 및 CompiledModel G/N 프로필 | 대표 request-runner 코드: CompiledModel2.2.0, CPU1 설정, 별도 APK·resident A4/N5 | A24 Interpreter계열/현재 adapter, 기존 서비스·p4 고정 |
| 열과 처리시간 | 상태 slowdown/열 피드백 경로 있음 | 피드백 법칙 새 확인 필요; 온도/호출/queue를 분해 가능 | AP head만 보정, 열→service 피드백 없음 |
| 기한·도착 | FG1.5초/BGburst 단위 기한 | 분류1.5초/탐지6초, 대표 간격200ms | 분류1.5초/탐지6초, 해당 mixed 확인350ms |
| 측정 경계 | 모델의 run-only/추론 chunk와 정책 모델 정의 | 예정/실제 도착·queue·dispatch·start·host call·output·persist·worker·lane | output-ready/persist 응답과 lane_available까지5phase |
| 검증 해석 | 버전별 기존 평가 근거를 각각 귀속 | 이미 본 원자료의 새 fitting/전이 판독은 사후 | AP 평균 개선·원 E/P95 예측 동등, 최대/피크 등 악화도 공개 |

이 표는 **범위·계약 차이**이며 어느 기기/엔진이 더 우수하다는 판정이 아니다. BG chunk와 탐지 한 요청의 P95, CPU4와 CPU1, 서로 다른 기기의 AP/SKIN/J를 같은 단위의 반복으로 pooling하지 않는다. A24 계수·τ·에너지 단위를 S26에 끼워 넣지 않는다.

S26 R4C 대표 manifest는 EffNet/Det의 exact SHA·CPU1·GPU `FP32` 요청 옵션, A resident4, baseline30/common120/cooling60/drain30, sampler900ms를 기록한다. **요청 옵션의 FP32와 실제 GPU 정밀도 확인은 다르다.** request-runner의 NPU 옵션은 Kotlin 요청 NPU 하나를 native `{NPU, CPU}`로 전달한다는 사실도 코드에 기록돼 있으므로 옵션 목록만으로 실제 실행 장치·전체 위임을 인증하지 않는다.

## 4. 자료 감사와 층별 계약

첫 구현 단계의 산출물은 fitting이 아니라 `inventory/contract/split`이다.

| 원본 묶음 | 보존할 분모·역할 | 새 분석에서의 취급 |
|---|---|---|
| R3 | 16세션·세션마다192 예정, A/N 각각4 pair | 개발 후보 자료. pair 전체를 fold로 묶고 원 실험 분류를 보존 |
| R4C | 16세션·192 예정, 원 confirmation 표식 | 원 확인 결과 보존, 새 모델에는 **이미 본 사후 전이** |
| R4S | 16 planned slot/18 공식 attempt, 유효14·drain-incomplete4, 별도 준비/중지2 | slot 결과와 attempt 소비를 별도. N complete pair2/A4, orphan·실패를 모두 보고 |
| Q20 | CPU/GPU/NPU 각20 결과와 실행 근거 | 품질·실행 판독용. service/열 독립 반복으로 합치지 않음 |
| 구 measure/profile | 모델·엔진·precision·CPUthreads·부하별 이력 | 기존 모형 재현/조건부 prior. 새 mixed 프로필과 구분 |

필수 inventory 키는 Git HEAD/blob 또는 실제 bytes SHA-256, session/attempt/slot/pair/day, exact 모델·입력·전처리·labels·APK·source·engine·requested/actual backend·precision 상태, resident keyset, policy·등록 파일·seed/trace·time_scale, 초기 AP/SKIN/SOC·충전·화면·직전 이력, monotonic 원점/센서 bracket, raw/summary/validator·종료/failure이다. Git blob SHA-1과 파일 bytes SHA-256을 같은 해시라고 부르지 않는다.

- manifest의 예정 request ID와 ledger를 연결한다. 다음 창의 표본을 마지막 pre 입력으로 가져오지 않는다.
- `host_inference_start/return`은 Android clock의 adapter 호출 경계다. PC host clock·순수 accelerator kernel 시간으로 해석하지 않는다. 5phase 합과 dispatch→lane 합의 보존을 검사하고 추가 CPU 전후처리 분해를 별도 제공한다.
- AP/SKIN/BAT/PA·thermal status·sample age/bracket·누락을 분리한다. status0만으로 스로틀링 부재를 증명하지 않는다.
- 전력 적분은 등록된 `kind=power_sample`만 사용한다. admission snapshot 센서 행을 다시 가산하지 않는다. raw 전류/전압/charge-counter 단위와 sign·INVALID·plug 상태·대상 창·보간 규칙을 고정한다.
- 원 `full120`과 stress `full720`을 각 manifest의 실제 시간 원점/time_scale로 재현한다. covered/missing duration과 prefix partial J를 full J와 구분한다. 미관측 tail을 0으로 채우지 않는다.
- A conditional은 실제 일정 입력, B는 예정 도착→인과적 scheduler→예측 일정 입력이다. 둘의 평균을 합쳐 정확도 개선을 선언하지 않는다.

R4C 대표 전력에는 sampler239행과 admission204행이 있고, 표본 median 약0.9001초/max 약0.9126초·snapshot 약59ms라는 역할 검토가 있다. CC의4275μAh/17100μAh 몰림과 내부 채널 불일치 때문에 오래된900초 ±126J 규칙을120/720초 창의 정밀도나 정책 차 CI로 전용하지 않는다. 이는 대표 원본/역할 판독이며 전체 run 감사 결과가 아니다.

## 5. 개발·선택·사후 판독의 유한 안

권고 시작점은 **R3 개발＋R4C 사후 전이＋R4S stress/실패 진단**이다. 모든 결과가 이미 알려진 만큼 가족 선택도 사후 설계라는 사실을 공개한다. 기존 simulator의 원결과는 먼저 재생하는 B0 control로 보존하고 수정 프로필에는 새 namespace를 사용한다.

| 후보 | 현재 계획에 넣는 범위 | 현재 제외 |
|---|---|---|
| S0/S1 | 정책/runtime/context별 고정 joint phase와 시간 또는 누적 점유 한 변수의 제한 보정 | 온도→response 직접 fitting, 미검증 context·동적 전환·3건 병행 |
| T0/T1 AP | pre anchor 유지 control / 양의1pole 반응 | 새2RC·ML·global clip 동시 비교 |
| T0/T1 SKIN | AP와 별도 sensor head·별도 오차 | AP 개선을 SKIN 개선으로 대체 |
| E0 | S26 pre baseline＋같은 footprint의 상태 전력, 전기 적격성 확인 전 raw-energy 진단 | A24 τ30/prelate E1의 즉시 복사·공인 J 정책 순위 |

R3의 pair8을 개발 단위로 쓸 수 있는지 inventory에서 확인한 후 leave-pair-out을 등록한다. A/N footprint가 다르면 계수·지원 행렬을 구분한다. day가 개발에 하나뿐이면 leave-day-out을 했다고 쓰지 않는다. load 조건이 여러 개 확보됐을 때만 leave-load-out을 수행하며 R4S를 개발에 넣으면 원 stress 전이를 다시 독립 확인으로 부르지 않는다.

선택한다면 외부 held pair를 내부 선택에 노출하지 않는 nested 방식이다. **제안 상한**: fitted head bundle S0/S1/T1-AP/T1-SKIN/E0 최대5개, pair8의 외부8×내부7＋최종8＋최종fit 및 외부fit을 모두 세면 캐시 없이 최대365 bundle fitting이므로 **400회 cap** 안에서만 등록할 수 있다. T0는0fit이다. decay/λ/특징 격자를 추가하면 이 산술은 더 이상 성립하지 않으므로 새 등록 없이 추가하지 않는다. rank·coverage·source drift·time cap 실패 시 기록하고 무한 재적합하지 않는다. **이번 실제 fit은0**이며 PC 시간·bundle별 내부 solver 횟수는 구현 전 별도 고정 대상이다.

## 6. 지표·성공 판정 제안

| 축 | 필수 보고 | 판정 제한 |
|---|---|---|
| 서비스 | phase MAE/ms·response MAE/ms·완료 nearest-rank P95·전체 planned 대비 completed/on-time·failed/rejected/expired/unfinished | 완료 P95만 좋아지고 미완료가 늘면 성공으로 보지 않음. predicted miss/completion count와 실제의 차이도 보고 |
| AP/SKIN | 각 sensor path MAE/°C·최대 절대오차·peak signed/abs error·load/cooling 방향·등록 threshold 초과시간 | 섭씨%·AP와SKIN 평균 합산·미측정 방향 보장 금지 |
| 에너지 | E_int/E_cc 별도 signed/abs error/J·coverage·단위/C2 상태 | 내부 채널 일치가 외부 절대 교정은 아님. 작은 ΔJ 부호 불일치/불확실이면 정책 E 방향 보류 |
| 정책 차 | 같은 pair/창의 관측 Δ와 예측 Δ, 차등 오차·sign/rank agreement·near-tie·실패 pair | 개별 세션 오차가 작다고 정책 순위를 보장하지 않음. A4/N2의 불균형·선택 편향 공개 |

Service/AP/SKIN/E의 threshold는 **audit 후, 결과 전 등록할 제안값**이다. 기존1.5/6초 연구 기한은 보존하지만 예측오차 합격선·허용 서비스 손실·AP/SKIN epsilon·J uncertainty를 지금 성능을 보고 통과 확정값으로 정하지 않는다. 목적별 head를 구분하고 단위가 다른 ms/°C/J 임의 가중 평균을 만들지 않는다.

같은 day/실행 block 안의 pair bootstrap은 그 계보의 제한적 불확실성이다. 192요청·여러 시간창을192회 독립 실험으로 세지 않는다. pair2는 정밀도·일반 우월성 판정에 부족하다. 예를 들어 독립·교환가능 sign 가정 아래 모두 같은 방향이어도 pair2의 단측 exact sign 확률은0.25, pair4는0.0625다. 이는 표본 한계 설명이며 이번 데이터의 p-value 계산이나 새로운 합격 기준이 아니다.

## 7. 품질 mask와 새 실측 발동 gate

Q20 CPU는 기존 FP32 참조 일치, GPU는 실제 정밀도 미확인, NPU는 FP16 합격선 미등록으로 품질 PASS 보류다. NPU top1 20/20·top5 순서19/20·최소cosine0.9999554 등의 관측 지표는 남기되 현재 결과를 겨우 통과시키는 tolerance를 사후 만들지 않는다. warmup의 단일 입력 계약 PASS도20입력 품질 확정이 아니다.

1. **관측 재생 층**: 원래 시행한 runtime·조합을 품질 pending 태그와 함께 시간/열 관측으로 재생할 수 있다. 이를 배포 후보 허용으로 바꾸지 않는다.
2. **정책 후보 층**: request-runner exact source/APK와 입력·전처리·compiled 옵션·실행 장치·precision·출력 계약을 연결한다. 품질/병행/안전/완료 gate를 통과한 조합만 후보 mask에 넣는다. quality-runner와의 완전한 동일성은 추가 증거가 필요한 부분이다.
3. **새 확인 발동**: 초기/회복 혼동, 후반 서비스 잔차, load/cooling 방향 실패, 작은 정책 차의 식별 부족 중 하나를 특정하고 그 원인을 분리하는 사전 질문이 있어야 한다. 기존 원데이터 재생으로 해결될 질문이면 새 측정을 자동 추가하지 않는다.

모형·head·지원 행렬·공개 입력·새 workload·오차 기준·공통 창·중단/누락·예산을 동결한 뒤, **ABBA4는 한 비교의 최소 전향 확인 제안**이다. 각 arm2회/완전pair2이며 유의성·모든 부하/세자원 순위 재현을 보장하지 않는다. 품질 승인된 비교부터 수행하고, CPU/NPU 비교는 NPU gate 뒤 별도 제안으로 둔다. GPU와NPU 직접 비교에는 같은 resident footprint와 같은 workload가 필요하다.

세션192요청·runtime당2warmup을 그대로 유지하는 **산술 제안**이면 A resident4의 ABBA4는 본768＋warmup32=800추론/runtime16, N resident5는 본768＋warmup40=808추론/runtime20이다. 추가20장 품질 검사·설치·staging·재시도는 포함하지 않은 값이다. manifest stage caps150＋60＋30＋120＋30＋60초와 arm간90초를 단순 합치면4회2070초지만 이는 전체 wall-clock/ADB 예약이 아니다. 실제 전송·preflight·종료·저장 여유와 활성시간 상한/ADB·namespace·소비 registry는 **후속 구현·등록에서 계산할 미확정값**이다. 이번 새 기기 실행 승인/예산/Run은0이다.

## 8. PROJECT_PLAN 대조와 최종 표현

이번 문맥에서 최신 `PROJECT_STATUS`·`PROJECT_PLAN` 상단의 desktop/overnight/RL/v3 후속, S26 관련 절과 DECISIONS의10/4·10/6 결정·인계 문서를 읽었다. 이전 문맥에서는 개정4.4 본문·단계/성공·축소 판정과 당시 범위 규정을 읽었다. 그러나 **현재1524행 PROJECT_PLAN의 변경 후 전체를 줄 단위로 끝까지 재확인한 것은 아니다.** 최신 전체 대조 완료로 표시하지 않으며, 미확인 범위는 다른 날짜별 작업 이력의 전량 대조다.

확인한 범위에서는 이번 제안이 공통 연구 목표와 충돌하지 않는다. 다음 경계는 계속 필요하다.

- S26-THERMAL-SCOPE-02의 별도 기기 절·A24/S26 계수/엔진 분리를 유지한다. 최신 two-model mixed 자료의 존재가10/4 제출 범위 변경이나 XDEV-02 완료를 자동 의미하지 않는다.
- S26-CONTRACT-MODEL-03의 EfficientNet 주대상/MobileNet 개발·민감도 분리를 유지한다. 새 request-runner의 두 모델 관측은 별도 계약으로 다룬다.
- 기존 A24 hybrid AP 평균 확인·J/P95 동등성과 S26의 새 예측 정확도/정책 효과를 합치지 않는다. 표면온도·에너지/열 절감·강한 B2/B3 대비 정책 우월성은 각각 별도 증거다.
- desktop·RL의 종료 소비·배치·학습 과제는 이번 S26 계획에 포함하지 않는다. 기본/RL/strict/experiment_ready=false와 원FAIL·실패·부족한 pair를 보존한다.

최종 표현은 “**기존 S26 d1sim을 재사용하되 최신 mixed CPU1·두 모델·실제 경계에 대한 새 profile/검증 계약을 준비했다. 기존 자료의 조건부·사후 평가와 새 prospective 확인을 분리했고, 품질/J gate와 미완료를 보존했다**”가 적절하다. 이번 작업을 새 모형 검증 완료·실측 승인·정책 우월성으로 표현하지 않는다.

## 근거 경로

- [S26 범위·입력·7경계 인계](../../team/S26_SCOPE_AND_INTERFACE_20261004.md), [10/6 계약 모델·FP16 품질 기준](../../team/S26_REPLY_AND_INPUT_HANDOFF_20261006.md), [프로젝트 계획](../../PROJECT_PLAN.md).
- [기존 d1sim README](https://github.com/mingyujo/D1Check/blob/0a0749890fba2452c5907433c6bea476a2da7e24/d1sim/README.md), [기존 정책 평가 sim](https://github.com/mingyujo/D1Check/blob/0a0749890fba2452c5907433c6bea476a2da7e24/d1sim/policy_eval_v2/sim.py), [GPU holdout 판정 코드](https://github.com/mingyujo/D1Check/blob/0a0749890fba2452c5907433c6bea476a2da7e24/d1sim/gpu_holdout_v1/judge_gpuho.py). 해당 경로·버전별 근거이며 새 mixed 계약의 PASS가 아니다.
- [R3 원장](https://github.com/mingyujo/D1Check/blob/21cba44faa5fff1fb9703b590aa536a6207f8de5/s26/results/mixreq_1008/R3_LEDGER.md), [대표 R4C manifest](https://github.com/mingyujo/D1Check/blob/21cba44faa5fff1fb9703b590aa536a6207f8de5/s26/results/mixreq_1008/R4C_blocks/S26_MIXREQ_00_B2_PARALLEL_ONLINE_V1_a1/device/manifest.json), [대표 requests](https://github.com/mingyujo/D1Check/blob/21cba44faa5fff1fb9703b590aa536a6207f8de5/s26/results/mixreq_1008/R4C_blocks/S26_MIXREQ_00_B2_PARALLEL_ONLINE_V1_a1/device/requests.json), [CompiledModel runtime](https://github.com/mingyujo/D1Check/blob/21cba44faa5fff1fb9703b590aa536a6207f8de5/request-runner/src/main/java/Runtimes.kt), [원 readout·powersample selector](https://github.com/mingyujo/D1Check/blob/21cba44faa5fff1fb9703b590aa536a6207f8de5/s26/tools/mixreq/mixreq_readout.py).
- [Q20의 등록된 판정](https://github.com/mingyujo/D1Check/blob/5857152ad8244c41975843ded77dd33024f38f2d/s26/results/quality20_1008/q20_1009a/q20_judgement.md).
- [Cawley·Talbot, JMLR2010](https://jmlr.org/papers/v11/cawley10a.html): 후보 선택의 과적합과 평가 편향을 분리하는 근거. 논문 수치를 S26 합격선으로 복사하지 않는다.
