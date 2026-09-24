# CAL-03 실행 결과와 사전 고정 규칙 — 2026-09-24

> **개발8·확인8 완료, 진단64·warmup128, 실패/재시도0.** 아래 실행 전 규칙은 당시 기록이며 결과는 문서 뒤의 승인 실행 종료 결과를 따른다. 소비 계획 재실행 금지.

시작8fdb90d, clean/작업브랜치 일치. 사용자 승인16세션/64진단/128warmup, 개발8→동결→확인8, 설치phase당1(총2), retry/대체/추가0, 실행/cleanup합7290초를 유지한다. v1은미소비로보존하고, 화면이탈 관측과host source를 고정한v3를실행한다. session목록·순서·seed·모델/입력·APK·추정통계량·timeout·총예산 변경없음.

## 화면과 환경

시작 조회: 동일A24/fingerprint, Awake=true/interactive=true, 밝기설정81, 수동mode0, 화면꺼짐18000000ms(5시간). 사용자설정의관측값이며실제휘도/nits아님. 시스템설정/화면조작은수행하지않는다. 세션중앱기존FLAG_KEEP_SCREEN_ON과이미설정된5시간으로유지한다. 이는보정지원환경이며과거원인해결증거가아니다.

각세션gate에서power·밝기/mode/timeout을검사하고, launch이후poll첫시점/매10초/완료marker시점/회수후power를조회한다. settings는gate/회수후만조회한다. 명령당2초와기존125초poll절대상한안에서수행, 실측동기journal없음. host조회가CPU/ADB/system_server에부하를더할수있고각snapshot의host시작끝/원문을보존한다. 표본사이연속awake를입증하지않는다. 알려진이탈/설정변경/조회실패즉시실패종료·회수·cleanup, 임의화면켜기/반복조작/설정변경/재시도없음.

## 적격성과 동결

개발8세션·진단32·warmup64 전체가유효해야fit가능. 각요청event/result/hash/trace·예정도착·실제도착·D/A/S/O/P/L순서·urgent O/normal P응답경계·실제AVAILABLE뒤다음요청배정/시작을확인한다. 각cell4요청으로후속재사용최대3쌍, phase합24쌍. 관측부재를추가요청으로메우지않는다. 혼합/실패/late/거절/overflow/누락/solo위반·환경이탈/cleanup실패는fit차단. 앱메모리admission·thermal·기존GPU proof/입출력 gate 유지.

8조건×5구간의4상관관측에대해중앙값/min/max를ns로산출한다. 조건당독립세션1, 요청4를독립반복으로세지않음. priority별응답적용/N/A와관측missing구분,고정경로D→A는adaptive전용불가. UNKNOWN_OVERRUN/기존20null/experiment_ready=false유지.

확인전write-once fit에plan/source/원자료/화면증거·validated/hostcleanup hash를동결하고, confirmation claim이fit hash를고정한다. 이후확인자료는fit에사용하지않음. **확인 적격 기준은8세션·32요청·64warmup과동일기록/환경/cleanup gate 모두통과**이다. 오차는각값에대해actual−동결median(ns)와초과건수/4,세션수1을보고한다. 기존계약에는예측정확도의숫자허용폭이나coverage PASS가없으므로사후임의기준을추가하지않는다. performance_pass=null. 큰오차도삭제/재보정/추가실측하지않고그대로보고한다. '확인자료유효'와'정확도입증'은다르다.

## 시간과 중단

phase당작업3600초+cleanup45초,합121.5분. runtime30/watchdog120/poll125불변. launch전155초+증거10초잔여없으면시작금지. 실패회수최대10초,cleanup절대상한phase시작+3645초. 고정cooling120초·배터리phase시작55%/이후30%·unplugged≤35°C·thermal0·앱종료조건유지. timeout을늘려성공을만들지않음.

v3 host변경직접관련20테스트통과(새화면5+보정15), APK코드/서명불변·manifest/dry-run검사. 계획/실행경로는같은외부root timing_cal03_plan_v3 및 timing_cal03_run_v1이다. 기존v1/종료CAL계획/원본은변경하지않는다.

동결v3 plan SHA-256 `9f7224e066f0ac0278523f617d8305b28696108ef8f0caee69625eb6f5cc8400`. 실제명령은`timing_cal03_plan_v3/RUN_APPROVED_CAL03.ps1`의development/confirmation단계로분리한다.

PC???v2??????10???????v3?????. v1/v2??????????????/????0??. v3??????????????????????.


## 승인 실행 종료 결과

**개발·동결·확인 수집 및 분석 완료. 예측 정확도·정책 성능 PASS가 아니다.**

| 단계 | 시도 | 완료 | 실패 | 미시도 | 진단 요청 | warmup | 후속 lane 재사용 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 개발 | 8 | 8 | 0 | 0 | 32 | 64 | 24쌍 |
| 확인 | 8 | 8 | 0 | 0 | 32 | 64 | 24쌍 |

업데이트 설치2회, 명시적 추론192회(진단64+warmup128), retry·대체·추가0. planned64요청 전부 사용했고 실패·거절·만료·late success·제외0이다. 앱 cleanup16/16, host cleanup 및 프로세스 부재16/16을 확인했다. 소비 registry에 두 phase의 complete/consumed와 completed_budget을 보존했으며 재실행하지 않는다.

각 phase의 preflight 폴더 생성 UTC→complete UTC 기준 개발1305.856초, 확인1299.716초, 합 약 **43.43분**이다. 승인상한121.5분 이내이며 중간 PC 검토/동결 시간은 별도다. 이 근사값은 같은 host 벽시계 기준이며 Android 시각과 직접 빼지 않았다.

### 동결·오차·표본의 의미

개발 적격성 확인 후, 확인 실행 전에 8조건×5구간=40개 초기 관측 슬롯의 중앙값/min/max와 원자료·화면 증거 hash를 write-once로 동결했다. 확인 claim의 freeze hash와 종료 후 동일성을 검증했다. 각 조건은 **개발 독립세션1·상관요청4 / 확인 독립세션1·상관요청4**다. 확인 자료로 값을 재조정하지 않았다.

주요 서비스 구간 S→O(실행 시작→output_ready)의 값은 다음과 같다. 입력 준비·host inference API·후처리를 포함하며 GPU kernel 시간은 아니다. 각 행의 확인 오차는 actual−동결 개발 중앙값이다.

| task/backend/priority | 개발 중앙값 ms | 확인 오차 min~max ms | 중앙값 초과/4 |
|---|---:|---:|---:|
| classification_CPU_normal | 96.407 | -3.998 ~ +4.090 | 2 |
| classification_CPU_urgent | 94.094 | -2.028 ~ -0.665 | 0 |
| classification_GPU_normal | 240.138 | -6.410 ~ -0.231 | 0 |
| classification_GPU_urgent | 237.666 | -12.521 ~ -3.619 | 0 |
| detection_CPU_normal | 553.166 | -6.739 ~ -0.493 | 0 |
| detection_CPU_urgent | 548.513 | -1.525 ~ +10.681 | 3 |
| detection_GPU_normal | 1054.499 | -20.395 ~ +1.610 | 1 |
| detection_GPU_urgent | 1072.072 | +7.223 ~ +32.270 | 4 |

S→O 최대 절대오차는32.270ms이며 detection_GPU_urgent의 확인4건 모두 중앙값보다 길었다. 다른 구간의 최대 절대오차는 D→A 2.294ms, A→S 15.462ms, O→P 17.979ms, P→L 1.510ms다. 이는 조건별 관측 중 최댓값의 기술이며 미래 상한/coverage 보장이 아니다. 40개 전 구간·조건의 개발 median/min/max와 확인 signed error/4건 초과 수는 외부 FINAL_REPORT와 원래 ns 단위 JSON에 보존했다.

자료 적격성 기준은 개발/확인 모두 통과했다. 기존 계약에 수치 정확도 허용폭은 없으며 `performance_pass=null`을 유지했다. 작은 오차만 골라 성공을 선언하거나 큰 오차를 제외하지 않았다. 5초 deadline 위반0은 정책 우수성 근거가 아니다.

### 환경·관측 영향·미검증 범위

- 동일 A24·fingerprint·APK/서명·입력 조건으로16세션을 수행했다. 밝기설정81/수동0/화면 꺼짐18000000ms를 유지했으며 시스템 설정이나 화면 조작을 수행하지 않았다. 앱의 기존 FLAG_KEEP_SCREEN_ON과 기존 사용자 설정을 사용했다.
- 화면96표본 모두 Awake/interactive 통과, 설정 변경 증거 없음. 세션 전 배터리62~66%,31.4~32.7°C, unplugged/thermal0, 앱 memory admission 및 실행 중 환경 gate 통과. 화면 표본 사이의 연속 상태나 모든 하드웨어 스로틀링 부재를 입증하지 않는다.
- host snapshot 누적 경과43.310초는 조회·host 저장 비용이다. 순수 기기CPU 시간/에너지가 아니며 서비스시간에서 빼지 않았다. sparse ADB/power 관측이 포함된 환경이라는 한계를 유지한다.
- 동기 failure journal은16세션 모두 비활성화됐고 해당 파일은 생성되지 않았다. 일반 timing/warmup trace와 필요한 result/event persist는 남아 있다. 진단용 동기 기록 시간을 fit에 섞지 않았다.
- 이전 lane_available 뒤 후속 요청 도착·dispatch·execution_start의48쌍을 관측했다. 이는 이번 단독·고정 backend 경로의 scheduler lane 재사용이며 병행 부하의 재사용 보장이 아니다.
- 새40슬롯은 priority를 나눈 오프라인 초기 관측이다. 기존20null 설정을 대체하지 않는다. 고정 경로 D→A를 적응형 정책 비용으로 전용할 수 없고, busy 초과의 잔여시간 분포·병행 간섭·다른 입력/기기·tail은 미검증이다. UNKNOWN_OVERRUN/experiment_ready=false 유지.
- CAL-02 및 과거 통합 진단 정지 원인은 여전히 미확정이다. 기존198요청 FAIL·fixed-split 부분 결과·종료 계획·과거 미확인 소비량은 그대로 보존한다.

### 산출물과 재현

외부 로컬 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`:

- `timing_cal03_run_v1/`: 개발/확인 원본, DEVELOPMENT_REVIEW, FREEZE_RECEIPT, FINAL_RECEIPT, FINAL_REPORT.
- `timing_cal03_fit_v1.json`: 확인 전 동결값, SHA `f4f55b65756ed965e6f69e70f6e6d50ce30576c45911aae83afa5944314106fb`.
- `timing_cal03_confirmation_v1.json`: 동결값 대비 확인 오차와 입력 hash.
- `timing_cal03_analysis_v1/`: 전40슬롯 결과표·SUMMARY·VERIFICATION·재현 script.
- `timing_cal03_execution_preflight_v1/`: 실행 전 gate/화면설정·동결 규칙·PC20건 및 예약보완 후6건 검증 로그·execution_source_v3.

원본은 GitHub에 포함되지 않는다. 공유 가능한 후처리 코드는 [d1_cal03_report.py](../tools/d1_cal03_report.py)다.

```powershell
# PC 후처리 재현만. --output은 새 폴더여야 하며 원본/동결값을 수정하지 않는다.
python -B -m tools.d1_cal03_report --root C:/Users/LG/Documents/D1Check_Arrival_Extension --output C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_analysis_reproduced_v1
```

실제로 수행한 fit/confirm 명령은 같은 v3 plan, development/confirmation run, 위 fit/confirmation 경로를 사용했다. 확인 자료가 공개된 이후 fit을 재생성해 대체하지 않는다. 앞의 실행 스크립트는 이미 소비된 단계이며 재실행 명령이 아니다.

다음 최소 행동은 PC에서 새 priority별 단독 관측을 현행 시간 계약에 연결할 범위와 적응형 D→A 미측정·UNKNOWN_OVERRUN 처리 요건을 명시하는 것이다. 정책 실측 준비 완료로 승격하거나 후속 측정을 자동 실행하지 않는다.
