# 비동시 도착 앱 내부 스케줄링 확장

- 작업 ID: `ARRIVAL-EXT-01`, protocol `arrival-scheduler-v1`, 개발 pilot `arrival-development-pilot-v1`.
- 2026-09-23 기준: 설계·PC 구현·빌드 검증과 A24 smoke·개발용 pilot 완료. 독립 평가와 새 본 시뮬레이션은 아직 실행하지 않았다.
- 기준 HEAD `f2f559c03cd4146818dda232bf548d26afbe2af2`, 당시 작업 트리 clean, 새 브랜치 `feature/arrival-scheduling-20260923`.
- 기존 `support-constrained-simulation-v1`의 `SIMULATION_PLAN_READY`와 동결 receipt `32968a7f66f58f4d1b74087d2dcfafd21c729ba20b8f6705bc9d3521f8b6d9bc`를 변경하지 않는다. 기존 PC 결과는 고정 offset 0의 제한 모형이며 이번 도착 실험의 결과가 아니다. 이전 `C:/Users/LG/Documents/D1Check_Simulation_Plan/run_20260922_support_v1/FINAL_REPORT.md`에는 본 시뮬레이션 실행 0으로 기록되어 있고 현재 별도 본 실행 산출물은 확인되지 않았다.
- 실제 pilot 계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_plan_v2/pilot_plan.json`, SHA-256 `a3ba8ca0cf33c695d089b9ae548c851c8eea1adc6c9b8ca20900496f5746664e`. 새 APK `benchmark-runner-modelProbe-arrival-v2.apk` SHA-256 `1a8448abe1c78432870f1848676de61faefa83f64c9a6a3732d79f7a121f3612`; 고정 pilot에서만 설치·실행했다. 첫 v1 APK/plan은 미실행 개발 draft로 별도 보관하고 v2 표본과 합치지 않는다.

## 연구 질문과 증거 경계

일반 분류·탐지 요청이 실행 중일 때 긴급 요청이 들어오면, 일반 작업의 지연·완료 손실을 제한하면서 긴급 응답을 개선할 수 있는가? 이는 A24의 한 앱에서 합성 도착을 실제 두 모델 추론으로 재생하는 질문이다. 통역·OCR·OS 전체 스케줄링, 실사용 도착률, 다른 기기, 열스로틀링 조건으로 일반화하지 않는다. 기존 모델·canonical PNG·adapter·원시 inference 타이머를 재사용한다. EfficientDet exact binary의 비배포 연구 한계를 유지하며 저장소와 APK에 추가하지 않는다.

기존 동결 시뮬레이터는 배치 시작 전 제한된 action만 허용하며 새 staggered overlap은 `OUT_OF_SUPPORT`다. 새 실측이 나온 뒤에도 기존 결과를 소급 변경하지 않는다. 새 실측 기반 시뮬레이션을 만든다면 별도 protocol과 독립 평가에서 정책 **순위와 같은 세션의 paired 개선량**까지 검증한다. 개별 service-time 오차만 맞는 모델을 정책 검증 완료로 보지 않는다.

## 공통 자원과 정책

새 Activity는 기존 v3/v4 Activity와 별도 프로세스 경로·출력 root를 쓴다. 분류 CPU/GPU와 탐지 CPU/GPU의 네 adapter를 모든 정책에서 **같이 resident**로 만든 뒤 각 runtime에 warmup 두 건씩 수행한다. CPU/GPU worker 각 하나, CPU `cpu_threads=1`, 최대 동시 추론 2건이다. CPU 작업끼리 및 GPU 작업끼리는 직렬이고 추론 중 선점하지 않는다. 네 runtime의 A24 메모리 admission은 미검증이므로 첫 smoke 실패 시 뒤의 pilot을 실행하지 않는다. setup·warmup은 workload 시간에서 제외하지만 별도 증거로 보존한다.

| 정책 | 실제 선택 | 비교 의미 |
| --- | --- | --- |
| `CPU_FIFO` | CPU 한 lane, 이미 도착한 요청의 입력 순서 | 공통 기준 |
| `CPU_URGENT` | CPU 한 lane, 실행 중 건 완료 후 urgent 우선 | 순서 효과 |
| `CONDITIONAL` | urgent 우선 순서를 공유하고, 현재 빈 lane·CPU 추정 잔여시간·도착한 queue와 고정 개발 추정치로 CPU/GPU 예상 완료를 비교 | GPU 보조 배정 효과 |
| `FIXED_SPLIT` | urgent CPU, normal GPU | 구현된 보조 대조군, 19세션 최소 pilot에는 미포함 |

추정 service(ms)는 이전 A24 warm solo 관측의 반올림값: 분류 CPU 97/GPU 250, 탐지 CPU 558/GPU 1063. 이는 **개발용 입력**이며 새 workload에서 검증된 미래 service가 아니다. 정책 함수에는 아직 도착하지 않은 trace, 평가 요청의 실제 미래 service·성공 여부, 사후 KPI가 전달되지 않는다. 선택 계산 시간 `policy_compute_ns`는 dispatch 이전에 발생하므로 예정 도착 기준 응답시간에 포함한다. GPU adapter의 실제 full delegation은 실기기 로그에서 재검증해야 하며 요청의 `actual_backend` placeholder만으로 통과시키지 않는다.

## 도착·완료·안전 계약

단일 `SystemClock.elapsedRealtimeNanos()`에서 workload 시작, 예정 도착, 발생기 callback의 실제 도착, queue 진입, dispatch, 실행 시작, output-ready, fsync+rename+readback 완료, terminal, worker release를 기록한다. ScheduledExecutor는 worker와 분리되어 완료를 기다리지 않는다. 요청별 `arrival_lag_ns=actual−scheduled`를 보존하고 **모든 요청 100ms 이내**를 pilot 품질 gate로 고정한다. 초과해도 원자료를 폐기하거나 새 도착 시각으로 deadline을 늘리지 않는다. 초과 세션은 incomplete로 남기고 대응 block을 성공 표본으로 취급하지 않는다.

긴급 완료는 output-ready, 일반 완료는 durable result 저장 완료다. 응답은 완료−**예정 도착**, 보조 응답은 완료−실제 도착, queue wait는 실행 시작−queue 진입이다. soft deadline 이후 완료는 `succeeded`와 `late_success=true`를 함께 남긴다. 실행 실패 `failed`, admission 거절 `rejected`, 종료 시 미완료 `unfinished`를 구분한다. 이번 pilot은 hard expiry를 사용하지 않아 `expired=0`이 설계상 예상되지만 분석 분모에서는 terminal 유형을 빠뜨리지 않는다. 분모는 예정된 전체 요청이고 종료 시 대기 요청을 삭제하지 않는다. workload 마지막 도착 뒤 최대 100초 drain, 앱 watchdog 120초, host 관찰 125초다. makespan은 workload 시작부터 마지막 worker release까지, throughput은 성공수/makespan이다.

기존 `android-low-memory-resident-v1` admission을 runtime 생성 전·workload 전·각 실행 전에 적용하고 500ms memory/thermal/battery 시계열을 저장한다. thermal status 0만 허용한다. 측정 간 120초 냉각, 대응 block 내 시작 battery temperature 차이 ≤1°C를 고정한다. 이 조건이 불만족하면 해당 시도·원인을 기록하고 중단한다. 표본 PSS와 thermal status 0을 절대 메모리 안전이나 스로틀링 부재로 해석하지 않는다.

## 개발 pilot: 예산 승인 전 고정 제안

기존 확장 실측 예산은 확인되지 않았다. 권장 예산은 **정확 19세션, 평가 요청 130건, runtime warmup 152건, 총 시도 상한 19, device retry 0**이다. 첫 1세션은 4요청의 낮은 부하 smoke다. 뒤의 18세션은 3정책×6개의 같은-workload 대응 묶음이다: 분류 urgent/탐지 normal burst 3독립 block(각 8건), 탐지 urgent/분류 normal burst 1block(8건), 낮은 부하 1block(4건), queue 부하 1block(6건). burst는 일반 요청 0/150/300ms에 이어 긴급 450/500ms가 도착한다. queue는 일반 0/200/400ms 뒤 긴급 600ms, low는 0/3000/6000/9000ms다. 하나의 기존 canonical PNG와 검증 모델을 모든 정책에 같은 ID·도착·입력으로 재생하므로 새 이미지 다양성의 근거는 아니다.

각 대응 묶음의 정책 순서는 두 번의 3정책 순환으로 균형화한다. 새 세션 ID는 정책별로 고유하고 요청 ID는 묶음 안에서 동일하다. 모든 정책은 동일 네 runtime 상주, 두 번씩 warmup, thread 수와 저장 경계를 사용한다. 긴급 2000ms·일반 8000ms는 **engineering deadline scenario**이며 실제 UX SLA가 아니다. session 당 120초 상한, 묶음 사이 포함 각 세션 사이 120초 cooling이다. 예상 기기 점유는 준비·전송을 포함해 약 45~55분, 세션 시간 상한과 고정 cooling을 모두 사용하면 **74분 + 전송·설치 5~15분(권장 예약 90분)**이다. 성능이 유리할 때까지 추가 측정하거나 실패 세션을 대체하지 않는다.

앱 데이터 삭제·패키지 제거는 계획에 없다. 새 APK는 기존 APK SHA `68e55aefdceb91e569e0d55ff0a18af0658163106589852325cb9ad5626fa62e`를 `C:/Users/LG/Documents/D1Check_Arrival_Extension/legacy_apk/benchmark-runner-modelProbe-68e55aefdceb.apk`에 보관한 후 별도 이름으로 고정한다. 설치는 `adb install -r`이며 앱 데이터 유지가 불가능하다는 사실이 발견되면 자동 진행하지 않는다. 기기 출력과 실패·시도 ledger는 새 `arrival-scheduler-v1` 경로에만 둔다. 연결 해제 시 기존 attempt와 기기 출력부터 회수하고 같은 session ID를 재실행하지 않는다.

## A24 개발용 pilot 결과

고정 plan/APK hash와 `SM-A245N` fingerprint를 확인하고 2026-09-23 KST 02:33~03:17에 19/19세션을 실행했다. 평가130/130건과 warmup152건, 총시도19/retry0이며 세션 오류와 실패·거절·만료·미완료·늦은 성공은 모두 0이다. 최대 arrival lag 5.252ms, thermal status 전 구간0, paired 시작온도 최대차0.7°C, memory admission225/225 admit, sampled peak PSS 최대437.6MiB였다. 모든 세션에서 GPU 2 instance full delegation과 cleanup을 검증했고 종료 후 앱 프로세스 부재를 확인했다.

주 classification-urgent burst 3블록에서 CPU 긴급 우선은 FIFO 대비 urgent P95를 `-1217.5±15.8ms` 줄이는 대신 normal 평균 응답을 `+104.1±5.4ms` 늘렸다. 조건부 정책은 CPU 긴급 우선 대비 urgent P95 `-11.2±6.7ms`, normal 평균 응답 `-630.4±27.9ms`, makespan `-1.245±0.024s`였다. 주 조건의 GPU 배정은 normal 탐지 7건이고 urgent 분류는 CPU였으므로 큰 urgent 개선은 우선순위 효과, 일반 지연·makespan 개선은 GPU 보조 병행 효과로 해석한다. 모든 deadline 지표는 포화(urgent miss0%, normal on-time100%)여서 정책 구분 근거가 아니다.

상세 원시 경로는 `C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_run_v2`, 분석·간트·KPI SVG·hash inventory·보고서는 `C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_analysis_v3/FINAL_REPORT.md`다. 이는 기능과 paired 변동성 개발 자료이며 독립 평가·우수성·다른 기기 일반화의 증거가 아니다.

pilot SD와 종전 10% 참고 최소효과를 계획식에 적용하면 계산 반복 수는 두 대비 모두 1이어서 계약 하한 5가 지배한다. 정책 순서 균형을 위해 주 burst 6블록과 보조 3블록, 총9 paired block/27세션을 권장한다. 제안 plan은 `C:/Users/LG/Documents/D1Check_Arrival_Extension/independent_evaluation_plan_v1_proposal/evaluation_plan.json`, SHA-256 `9e826188a25ecc9ca33404995cc1e45238f00f539fbb3c41eabfcdb8295cf3c3`, 평가198/warmup216/retry0, 예상65분·예약120분이다. 상태는 `proposed_not_approved`이고 실행하지 않았다.

후속 simulation 검증은 pilot만 개발 입력으로 사용하고 독립 평가 원시 결과를 열기 전에 평가 9블록의 요청별 시간·정책 순위·paired KPI 차이 예측을 별도 hash로 동결한다. 실측 후 개별 시간 오차와 함께 정책 순위 일치 여부, `CPU_URGENT−CPU_FIFO` 및 `CONDITIONAL−CPU_URGENT` paired 개선량 오차를 보고한다. 독립 평가를 simulator 재보정에 사용하지 않는다. 이 simulation 생성·실행도 별도 승인 대상이다.

## 분석과 후속 독립 평가

pilot 보고: urgent 예정 도착 기준 완료 P95(nearest rank)와 전체 urgent 도착 기준 위반율, normal 완료 평균 응답과 전체 normal 도착 기준 기한 내 완료율, 전체 완료율·makespan·throughput, arrival lag, 정책 계산비용, terminal 수, sampled thermal/memory. n=2 긴급/세션 P95는 사실상 최댓값에 가깝고 모집단 tail의 안정적 추정이 아니다. burst의 독립 대응 block은 3개뿐이므로 pilot은 기능·변동성 추정이며 우수성 판정 자료가 아니다. 누락/실패 세션을 숨기지 않고 incomplete pair로 보존한다. 간트·KPI 그래프는 원자료 read-only 후처리로 생성한다.

pilot 뒤 주 비교 `CONDITIONAL−CPU_URGENT`, 순서 비교 `CPU_URGENT−CPU_FIFO`의 **block별** 차이 표준편차를 산정한다. 사용자 승인 최소 의미 효과 Δ와 손실 한계가 동결되면 `ceil((1.96+1.282)^2 s_pair^2/Δ^2)`를 시작점으로 하되 독립 평가 5~9 block 범위에서 정한다. 9를 초과하면 underpowered로 보고 목표·예산 재결정 전 실행하지 않는다. 요청 수를 독립 세션 수로 계산하지 않는다. 평가 전 최소 효과·normal 허용손실·deadline·정책 코드/임계값·분석 seed·고정 세션 수·기술 실패 처리와 최대 예산을 새 manifest에 동결한다. 종전 참고값인 긴급 P95 10% 개선·일반 기한 내 완료율 2%p 이내 감소는 사용자 승인 판정값이 아니다. 독립 평가와 새 본 시뮬레이션은 별도 승인 전 실행하지 않는다.

## 실제 CLI와 재개

저장소 cwd `C:/Users/LG/AndroidStudioProjects/D1Check-model02b`. 고정 계획은 이미 생성됐으며 같은 경로에 대한 generate 재실행은 거부된다. 아래 첫 명령은 별도 경로 재현용이다. dry-run과 read-only preflight는 pilot 예산 승인 전에 가능하다.

```powershell
python -B -m tools.d1_arrival_plan generate --source-plan "C:/Users/LG/Documents/D1Check_Telemetry_V4/resume_20260920T160724Z/smoke_plan_v2/plan.json" --apk "C:/Users/LG/Documents/D1Check_Arrival_Extension/new_apk/benchmark-runner-modelProbe-arrival-v2.apk" --output "C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_plan_reproduction"
python -B -m tools.d1_arrival_plan dry-run --plan "C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_plan_v2/pilot_plan.json"
python -B -m tools.d1_arrival_device preflight --plan "C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_plan_v2/pilot_plan.json" --adb "C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe"
```

**19세션 예산 승인 후에만** 아래 실행 명령을 사용한다. `--approved-cap`은 스크립트 상한 확인값이지 승인 자체가 아니다. 실패하면 `recover`로 기존 output만 읽고 원래 실패를 지운 재시도는 하지 않는다.

```powershell
python -B -m tools.d1_arrival_device run --plan "C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_plan_v2/pilot_plan.json" --expected-plan-sha256 a3ba8ca0cf33c695d089b9ae548c851c8eea1adc6c9b8ca20900496f5746664e --apk "C:/Users/LG/Documents/D1Check_Arrival_Extension/new_apk/benchmark-runner-modelProbe-arrival-v2.apk" --adb "C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe" --output "C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_run_v2" --approved-cap 19
python -B -m tools.d1_arrival_analysis --plan "C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_plan_v2/pilot_plan.json" --results "C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_run_v2" --output "C:/Users/LG/Documents/D1Check_Arrival_Extension/pilot_analysis_reproduction"
```

## 현재 재개 경계

완료된 `pilot_run_v2`에 run 명령을 다시 사용하지 않는다. read-only 확인은 `python -B -m tools.d1_arrival_plan dry-run --plan "C:/Users/LG/Documents/D1Check_Arrival_Extension/independent_evaluation_plan_v1_proposal/evaluation_plan.json"`로 재개한다. 독립 평가 run 명령은 외부 최종 보고서에 고정했지만 27세션 예산과 판정값 별도 승인 전 실행하지 않는다.
