# 반복 중단 검토와 제한된 운영 비교 후보

## 결론: 운영 비용을 포함하는 한 조합의 전향적 비교를 권고한다

**발열·배터리·응답 성능을 함께 평가하는 목표를 유지한다.** 현재 확인할 수 있는 것은 직렬 부하의 조건부 에너지와 준비·냉각 경로다. COLLECT-04/05 모두 병행 본 부하 전에 중단했으므로 병행의 손익은 아직 판정할 수 없다. 기존 FAIL, 종료 계획, 40개 동결값, 20개 null, `experiment_ready=false`는 바꾸지 않는다.

이번에는 **ENERGY-OPERATIONAL-PAIR-01** 후보를 구현했다. 첫 직렬 관측값에 후속 병행을 맞추는 실험을 반복하지 않고, 한 조합 CC_DG의 고정 준비·동일 작업량 처리·고정 냉각을 포함한 운영 결과를 기술한다. 직렬→병행 개발 block과 병행→직렬 확인 block, 총4세션이다. 단기 직렬 적격성 확인은 매 세션 안에서 수행하므로 비교 표본의 순서와 분리한다. **동일 초기 열 상태의 인과효과 실험으로 부르지 않는다.** 이번에는 PC 준비만 했으며 기기 실행·설치·ADB 호출은 0이다.

질문 A(동일 초기 상태의 직렬/병행 효과)는 보류한다. 공통 AP 목표 대역, 환경과의 관계, 내부 잔열의 동등성을 정할 근거가 없다. 질문 B(준비·대기·냉각을 포함한 운영 결과)의 제한된 관측을 먼저 권고한다. A의 gate를 완화해 과거 실패를 통과시키는 변경이 아니다. B에서도 불리한 결과·시작 상태 차이·미완료를 그대로 보고하며 절감/정책 PASS는 부여하지 않는다.

## 확인한 실제 상태와 원자료

- 시작 HEAD `3773f26ef463730b46eeee6930de8962bd510ebd`, 작업 브랜치 `feature/arrival-scheduling-20260923`, clean. fetch 후 origin과 차이0. 다른 worktree의 master는 건드리지 않았다.
- PC 프로세스 조회에서 ADB 공유 daemon과 Gradle daemon은 있었으나 Python 수집 프로세스는 없었다. 종료/재시작하지 않았다. registry의 COLLECT-02~05는 `stopped_no_resume`, sampler 진단은 완료 상태다.
- 대상은 `energy_collection_run_v4` 두 시도, `energy_collection_run_v5` 두 시도, `energy_sampler_load_run_v1` 한 시도의 receipt, progress, thermal 원문, 검증 요약이다. 160세션 분석·과거 전체 감사는 재실행하지 않았다.
- 5세션 HAL 원문 **1,064개**를 실제 `parse_thermalservice`로 읽어 저장 AP/status와 일치시켰다. 분석 입력 경로·SHA는 외부 `energy_design_review_pc_v1/review.json`에 남겼다. 기기 uptime bracket과 앱 elapsedRealtimeNanos의 동일 기기 시간축만 사용한다. PC wall clock을 직접 빼지 않는다.

## 온도 경로와 중단 이유

| 자료·구간 | AP 및 시간 | 확인 범위 |
|---|---|---|
| COLLECT-04 직렬 baseline | 120.009초, 32.9→31.4°C, 중앙 **31.5°C** | 같은 HAL AP·°C·phase 안의 중앙값 |
| COLLECT-04 직렬 load / 냉각 | 327.274초 / 180.004초, 냉각32.4→32.3°C | 고정 냉각은 작업480초 관측창 이후 resident 상태 |
| 다음 시도 준비 전 / baseline 첫값 | 31.4 / 33.8°C | 중간 재가열 관측. 냉각 종료→다음 session 시작60.130초, 연속 관측 공백 존재 |
| COLLECT-04 병행 baseline | 120.043초, 33.8→32.2°C, 중앙 **32.3°C** | +0.8°C로 최종 ±0.5°C gate 중단. load 미진입 |
| COLLECT-05 직렬 준비 | 106.818초, 33.2→31.5°C | 공식 baseline 이전 별도 phase, 조건부125.052J |
| COLLECT-05 직렬 baseline / 냉각 | baseline31.5→31.9°C·중앙31.5°C / 냉각32.9→32.6°C | 마지막60초 baseline 범위31.5~31.9°C: 준비 창 통과가 이후 평형을 보장하지 않음 |
| COLLECT-05 병행 준비 | host351.176초에 중단, 126표본32.3~33.5°C | 31.25~31.75°C anchor 대역에 관측값 없음. 공식 baseline/load 없음 |

COLLECT-05 사전 규칙을 시간순 재생하면 insufficient_window21·unstable7·off_anchor98이다. 마지막 창의 범위1.0°C만이 문제가 아니다. 중간에 범위0.1°C인 창도 직렬31.5°C anchor에서 벗어났다. 회수된 앱 prefix의 미종료 준비 phase 길이351.568초와 host gate의351.176초는 끝점이 다르므로 서로 대체하지 않는다. 과거 불확실한 호출 상한은 원 receipt 그대로다.

**준비의 비대칭이 코드로 확인된다.** COLLECT-05는 모든 세션에 같은 함수가 있지만 직렬은 anchor=None, 병행은 같은 단계·pair 직렬 기준 ±0.25°C다. 또한 eligibility probe는 직렬 세션에서 직렬, 병행 세션에서 병행으로 실행된다. 따라서 runtime/warmup 횟수가 같아도 준비 부하와 통과 조건이 같다 할 수 없다. 같은 단계·pair anchor 검색은 현재 정확히1개를 요구하며 과거 PC 수정 이후 다시 틀어진 증거는 없다.

최종±0.5°C, 준비±0.25°C, 60초/20표본/범위0.3°C는 기존 전향적 설계값이었다. 센서 표기0.1°C와 표본 간격을 참고했지만 열 평형·다센서 동일성·효과 동등성 허용폭을 검증한 값은 아니다. 주변온도 미측정, 표본 간 약3초, 시각 bracket 불확실성 및 관측 공백을 보존한다. 잔열·준비 재가열·주변 변화의 몫과 도달하지 않은 냉각시간은 식별 불가다. 단순히 대기가 짧았다고 결론 내리지 않는다.

COLLECT-05 host는 앱의360초 gate timeout보다 먼저 중단하고 부분 회수 뒤 force-stop했다. 앱 `finally`/cleanup을 보기 전에 회수하거나 강제종료했을 수 있다. 앱 cleanup 부재는 host cleanup 실패나 GPU 교착의 증거가 아니다. 기존 sampler 경쟁 재현과 과거 stack 없는 예외의 동일 원인도 계속 미확정이다. 화면·환경 관측은 해당 실행에서 통과했지만 이후 안정성을 보장하지 않는다.

## 세 설계 선택지

| 선택지 | 얻는 것 | 교란·부담·판정 |
|---|---|---|
| 기존 anchor/온도 gate 유지, 준비만 일치 | A에 가까운 비교 의도와 과거 기준 보존 | 첫 직렬의 낮은 값이 이후 도달 가능한지 미확인. 대기 연장 근거 없고 반복 중단·배터리 부담 예측 불가. 지금 재수집 비권고 |
| 첫 직렬과 독립인 공통 시작 대역 사전 지정 | 양 arm의 통과 조건 대칭 | 대역·허용 폭·주변 조건 근거가 없어 **수치 미확정**. AP 같아도 내부 열 상태 동일 아님. 임의32.x°C를 채우지 않음 |
| **고정 동일 준비 + 순서 균형 + 시작 상태 전부 기록** | B의 시간·에너지·발열·응답 상충을 적은 범위에서 관측 | 시작 상태 차이·carryover는 남음. 4세션으로 회귀 보정/유의성/평형 주장 불가. **권고 후보** |

NIST의 [block 설계 원칙](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm)은 nuisance를 통제·기록하고 block 안에서 비교하는 근거다. 이번 고정 AB/BA는 무작위 배정 실험이 아니며, 각 순서1block이라 순서효과와 날짜/단계효과를 분리 추정할 수 없다. [AOSP Thermal HAL](https://source.android.com/docs/core/power/thermal-mitigation)의 sensor/status 관측을 내부 전체 열 상태 측정으로 확대하지 않는다.

## 완료한 PC 구현과 검증 범위

- 기존 collection 기본 분기·COLLECT-05 gate는 유지하고 `operational_only`와 새 experiment ID로 분리했다. 네 runtime과 worker 소유권, short snapshot lock, 요청 비선점·실제 lane 해제를 유지한다.
- 모든 후보 세션은 runtime4→warmup8→**직렬 적격성2→host 품질 확인→병행 적격성2→host 품질/overlap 확인**을 동일하게 거친다. 순서가 병행 선행이어도 긴 직렬 표본을 기술적 gate로 요구하지 않는다. short probe 통과는 긴 병행 안정성 증거가 아니다.
- 이후 **고정 resident 준비120초**를 관측하고 공식 baseline120초는 한 번만 수집한다. 120초는 기존 baseline/관측 주기를 재사용한 동일 노출 길이이며 평형 도달시간 추정이 아니다. 창을 다시 골라 온도를 맞추지 않는다. 유효 AP/status·시각·gap·표본수와 기존 안전 gate는 유지한다. 준비 중 온도기울기를 이유로 기다림을 무한 연장하지 않는다.
- 새 운영 질문에는 AP±0.5/±0.25 matching을 적용하지 않으며 `null/N/A`로 고정한다. 작은 열 신호도 유효한 기술 결과로 남기고 시간상수 적합은 하지 않는다. 이것은 별도 estimand 변경이고 과거 COLLECT-04/05 결과와 합치지 않는다.
- **회수 결함 보완:** prefix의 cleanup 파일 조회/JSON 실패 하나가 archive 회수 전체를 막는 경로를 확인했다. 새 후보에 한해 오류·원문을 보존한 뒤 원래 bounded archive1회를 시도한다. 기한은 늘리지 않으며 cleanup가 없으면 정상 완료 검증은 계속 실패한다. 과거 cleanup 부재의 원인을 이 결함으로 소급 확정하지 않는다.
- `observed-energy-ledger-v1`은 초기화/gate/phase 사이 비용을 별도 구간으로 포함하고 겹치지 않게 분할한다. 작업 persist 완료까지, 고정480초 창, session 시작부터의 회계를 구분한다. **창끼리 더하지 않는다.** 원시 적분합과 partition 합은 동일, 끝점·cleanup 미측정은 null이다. 병행 power를 더하거나 열계수를 새로 fit하지 않았다.
- 관련 Python40건, Kotlin core7건, 새 APK compile/서명 및 새 plan Check를 검증 대상으로 삼는다. PC transport mock은 상태 전이/동결/실패 회수 검증이며 실제 Android/ADB 안정성 검증이 아니다. 최종 결과·소스 식별은 [작은 검증 기록](results/energy_design_review_01/README.md)을 따른다.

## 에너지·열 연결과 주장 범위

| 근거 | 연결 가능 | 미지원 |
|---|---|---|
| MobileNet A24/S26 과거 보정 | 기존 기기·조건·sensor 범위의 상태 기반 조건부 모형, 사후 내부 확인 | 새 두 모델/새 resident/병행 전용, 절대 전력 인증 |
| sampler 진단·COLLECT-04/05 완료 직렬 | **관측 trace 직접 재생**, 상태 구간 전력 적분·AP 경로·준비 비용 | 자료 통합한 새 독립 확인, 직렬 계수로 병행 예측 |
| COLLECT-05 미완료 준비 | 회수된 prefix의 소비량·온도·탈락 비용 | cleanup 이후 에너지, 미완료를 절감으로 계산 |
| 현재 두 모델 병행 본 부하 | 기존 제한된 시간 자료와 short probe는 별도 유지 | 긴 병행 에너지·가열/냉각 계수, 임의 offset/duty |
| PC 가정 모드 | 명시적 W/열계수 입력과 연속 온도 전이 | 실측 기반 정책 순위·에너지/열 개선 PASS |

새 재생에서 COLLECT-05 직렬 작업완료557.844J/고정창730.957J는 원값과 일치했다. session 시작→작업완료의 관측분은845.900J(처음0.247초 누락), 마지막 앱 이벤트까지1229.369J(총0.826초 누락)다. 중단 세션은 마지막 회수 이벤트까지420.046J(처음0.291초 누락), 그 안의 미종료 준비 구간401.951J다. **기기 전체·A24 raw mA 가설·관측분**이며 이전125.4J/314.2J 등 부분값도 그대로다. full operation energy는 cleanup/host 이후 미관측 때문에 null이다. 초기화 전·host cleanup 동안의 에너지를0으로 채우지 않는다. 준비·짧은 호출별 값은1Hz 보간 회계이고 직접 요청별 전력 측정이 아니다.

발열·배터리·응답을 함께 판단하려면 새 병행의 실제 완료량/host API overlap, 같은 부하의 기기전류/AP 곡선이 필수다. API overlap은 GPU kernel overlap이 아니다. 정책의 일반 서비스 허용 손실·절감 최소효과는 아직 미확정이며 이번 데이터로 사후 선정하지 않는다. 새 후보는 분류 normal/탐지 urgent 고정 backlog870건이므로 자연스러운 사용자 도착분포·UI 성능이나 최종 서비스 제약 충족을 검증하지 않는다.

## 권고 후보 하나와 정확한 예산

**CC_DG만** 선택한다. 성공한 직렬 경로와 동일 작업량을 사용하고 새 장기 병행 비용이라는 핵심 공백 하나를 다룬다. CG_DC를 추가하면 기기/thermal 모형이 없는 또 다른 배정까지 부담이 늘어나므로 이번에는 미지원으로 남긴다. 선택은 병행이 유리할 것으로 기대해서가 아니다.

| 단계 | 순서 | 역할 |
|---|---|---|
| 개발 block | CC_DG 직렬→병행 | 조건별 구간 평균전력·AP 관측 끝점·응답/완료시간 기술값 고정 |
| 동결 | 입력·규칙·개발 설정 hash 저장 | 확인 표본 열람 전에 고정, 정확도/효과 허용폭 없음 |
| 별도 확인 block | CC_DG 병행→직렬 | 고정값의 signed/absolute 오차와 역순 block contrast 보고, 재조정 없음 |

조건당 개발1·확인1 독립 세션이다. 4는 한 조합의 두 순서와 자료 분리를 갖추는 최소 구조이고 검정력 계산 결과가 아니다. 두 block의 손익 방향이 다르면 **운영효과 불안정/미판정**으로 종료한다. 방향이 같아도 제한된 관측 일치일 뿐 우월성·독립적 인과·반복 안정성 PASS는 아니다. 실패하면 incomplete pair와4세션 분모를 남기고 전체 중단, 교체/추가 없음. 새로운 효과를 얻을 때까지 gate/설정을 바꾸지 않는다.

| 소비·시간 | 후보 상한 |
|---|---:|
| 세션 | 개발2+확인2 = **4** |
| 작업 | 4×(분류678+탐지192) = **3,480** |
| 적격성 | 매 세션 직렬2+병행2 = **16** |
| 진단 / warmup / 총 명시적 추론 | **3,496 / 32 / 3,528** |
| runtime / staging | **16 / 4회·28파일** |
| APK 전송·설치 | 각각 최대1, 설치본 hash·서명 완전 일치 시 생략 |
| 재시도·대체·추가 | **0** |
| 고정 관측 | 4×(준비120+baseline120+공통work480+cooling180) = **60분** |
| 작업별 timeout 합산 예약 | 설치600 + 4×(gate/staging120+앱시작20+host poll1580+회수60+cleanup45) + 동결600 = **8,500초 = 141분40초** |
| hard 전체 상한 | 600 + 4×1860 + 600 = **8,640초 = 144분** |

app watchdog1560초는 host poll1580초 안에 포함하며 더하지 않는다. call30초, setup/warmup 공통150초, 각 적격성 workload30초, host arm gate60초, 준비 최대360초(후보 고정120초 후 첫 유효 관측에서 arm,350초 전 중단), 부하480초, 화면조회2초를 유지한다. added serial gate/probe의 최악 예약도 기존 준비360 대비 고정120의 여유 안에 있고 watchdog을 늘리지 않는다. 상한은 정상 예상시간이 아니다. 실제 시작/종료 평균과 배터리 완주 가능성은 미확인이다. 잔여시간이 세션1860초보다 적으면 다음 세션을 시작하지 않는다.

기존 화면·통신·observer·resident4 구성, CPU thread1, 모델·입력·품질/위임·memory 조건을 고정한다. 비충전, 배터리≥20%, 배터리온도≤35°C, thermal0, Awake/interactive, 밝기81/수동0/자동꺼짐5시간은 실행 시 새로 검증한다. 임의 설정 변경·안전 gate 완화는 없다. AP 센서 누락/NaN/thermal 위반/간격>10초/bracket uncertainty>2초·host timeout이면 중단한다.

준비·대기·baseline은 운영 비용으로 별도 제시하고 load 에너지만 절감값으로 쓰지 않는다. 모든 표본에서 setup 시작~회수 마지막까지 측정된 비용을 추가 보고한다. cleanup 끝점 미측정 때문에 전체 운영 **에너지 총량**을 확정할 수 없는 한계를 숨기지 않는다. exact whole-operation Joule 인증이 목표라면 연속 외부관측이 별도로 필요하지만 이번 비교의 필수 전제나 새 장비 구매 요구로 확대하지 않는다.

## 재현과 다음 행동

실측 후보 `energy_operational_plan_v3` / run `energy_operational_run_v1` / registry `ENERGY-OPERATIONAL-PAIR-01`는 새 namespace이고 **실행 미승인**이다. 원 run/registry는 생성하지 않았다. APK는 새 운영 적격성 순서를 구현했으므로 별도 빌드했으며 기존 APK는 덮어쓰지 않았다. 정확한 hash/서명과 dry-run은 공유 검증 기록을 따른다.

```powershell
python -B -m unittest tools.test_d1_energy_operational tools.test_d1_energy_collection
python -B -m tools.d1_energy_replan_review --root C:/Users/LG/Documents/D1Check_Arrival_Extension --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_design_review_REPRO_NEW
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check
# 아래는 새 실행 승인 이후에만 사용한다. 이번에는 실행하지 않았다.
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<실행 직전 확인한 A24 transport serial>'
```

사용자가 결정할 한 가지는 **질문 A의 동일 초기 상태 주장 없이, 질문 B의 위4세션 운영 비교를 새144분 상한으로 실행할지**다. 거부하거나 엄밀한 A가 필수이면 공통 시작 상태 근거가 부족하므로 실행 차단 상태를 유지한다. 더 높은 온도 대역이나 긴 대기를 임의로 넣은 대안을 자동 실행하지 않는다. S26/NPU 별도 협업은 유지하며 A24 계수를 전용하지 않는다.
