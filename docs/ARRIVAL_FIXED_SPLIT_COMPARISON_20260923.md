# ARRIVAL-FIXED-01: 고정 분리 대조군 추가 측정 준비

2026-09-23. 계획·PC 준비 완료, **실측 승인 대기 / 새 실측 0회**.
시작 HEAD `5736876a123a399cbeff3c86f1f999244bdc34e1`,
브랜치 `feature/arrival-scheduling-20260923`, 시작 worktree clean.
새 plan protocol은 `arrival-fixed-split-comparison-v1`; 앱 artifact schema는 기존 `arrival-scheduler-v1`을 재사용한다.

## 질문과 기존 판정

조건부 배정이 단순 고정 분리보다 어떤 부하·지표에서 얼마나 유리하거나 불리한가?
동일하거나 나쁜 결과도 유효하다. 고정 분리는 urgent CPU를 비워 두는 대신 normal을 더 느린 GPU에 제한할 수 있으므로 긴급/일반 지연의 상충이 가능한 **가설**이다. 우월성을 전제하지 않는다.

기존 27세션/198요청/216 warmup 평가와 `conditional_joint_primary_pass=false`를 보존한다.
기존 urgent 10% 최소효과 기준은 변경하지 않는다. 새 자료와 기존 자료를 주 비교 표본으로 합치지 않는다.
기존 low·queue는 각각 n=1 block이어서 확정적 부하별 근거가 아니다.
이번 계획은 과거 결과 공개 후 정한 새 전향적 **효과 추정 연구**이며 과거 성공 기준의 재시험/완화가 아니다.

## 정확한 세 정책과 자원

| 정책 | 도착한 큐에서만 적용하는 규칙 |
|---|---|
| CPU_URGENT (U) | urgent 우선, 같은 우선순위는 ordinal/id 순. CPU가 비었을 때만 다음 작업 선택. 실행 중 작업은 비선점. |
| FIXED_SPLIT (F) | **urgent→CPU, normal→GPU**. 해당 lane이 바쁘면 다른 lane으로 넘기지 않는다. ordered queue를 순회하므로 urgent가 CPU를 기다리는 동안 실행 가능한 normal은 GPU에서 시작할 수 있다. task 이름이 아닌 priority 기준. |
| CONDITIONAL (C) | 같은 urgent 우선 큐. 예측 CPU 완료=현재 CPU 잔여 추정+현재 큐의 앞 작업 CPU 추정 합+후보 CPU 추정. GPU가 비었고 GPU 추정이 더 짧으면 GPU. CPU가 비고 GPU가 바쁘거나 CPU 예측≤GPU 추정이면 CPU. 동률 CPU. |

`ArrivalPolicy.kt` 기존 구현 그대로다. 추정 ms는 classification CPU97/GPU250, detection CPU558/GPU1063.
CPU 잔여 추정은 `max(0, dispatch시각+기존 CPU 추정−현재시각)`이며 실제 미래 완료시간이 아니다.
정책 인자는 이미 도착해 enqueue된 Ticket 목록·lane 가용성·잔여 추정·개발 추정값뿐이다.
도착 generator는 전체 trace를 예약하지만 policy에 미래 trace/결과를 전달하지 않는다. 정책·추정·threshold·앱 코드 변경 없음.

세 정책 모두 CPU threads=1, lane별 worker=1, 최대 동시 추론=2(CPU/GPU 각1),
분류/탐지×CPU/GPU **4 runtime 모두 resident**, 각 runtime warmup2(세션당8), 동일 모델·이미지·preprocessing이다.
U의 실제 실행 동시성은1, F/C는 최대2. U도 사용하지 않는 GPU runtime을 상주·warmup하므로 상주 메모리 기준을 맞춘 비교이며, 최소 메모리 CPU 전용 제품과 비교하는 것이 아니다.
F/C도 같은 runtime 구성이다. 배정에 따른 활성 메모리/간섭은 결과로 보고한다.
CPU 대비 GPU 보조 배정 효과는 F−U, C−U로, 고정 대비 조건부 배정 차이는 C−F로 기술한다.
후자는 이 특정 규칙 두 개의 차이이며 모든 적응형 정책의 우월성이나 overlap의 인과 효과가 아니다.

기존 APK `new_apk/benchmark-runner-modelProbe-arrival-v2.apk`, SHA
`1a8448abe1c78432870f1848676de61faefa83f64c9a6a3732d79f7a121f3612`를 재사용한다.
새 APK 빌드/덮어쓰기 없음. 기기는 `SM-A245N`, fingerprint
`samsung/a24ks/a24:16/BP2A.250605.031.A3/A245NKSS9EZB5:user/release-keys` 고정.

## 동일 workload와 두 가지 예산

모두 urgent=분류, normal=탐지, 기존 동일 이미지. 시간 단위 ms.

| 조건 | normal 예정 도착 | urgent 예정 도착 | 세션 요청 normal/urgent |
|---|---|---|---|
| burst (주 조건) | 0,150,300,550,700,850 | 450,500 | 6/2 |
| low | 0,6000 | 3000,9000 | 2/2 |
| queue | 0,200,400,800,1000 | 600 | 5/1 |

| 항목 | 최소 탐색안 (권장) | 더 정밀한 안 |
|---|---:|---:|
| 조건별 독립 paired block | 각3 | 각6 |
| 총 block | 9 | 18 |
| 조건별/정책별 세션 | 각3 | 각6 |
| 정책별 세션 | 9 | 18 |
| 총 세션/시도 상한 | **27** | **54** |
| 평가 요청 | **162** | **324** |
| urgent / normal 전체 | 45 / 117 | 90 / 234 |
| 정책별 평가 요청 (urgent/normal) | 54 (15/39) | 108 (30/78) |
| warmup 호출 | **216** | **432** |
| 초기 cooling + 세션 사이 cooling | 2+26×2=54분 | 2+53×2=108분 |
| 정상 진행 예상 최소~최대 총 기기 예약시간 | **65~80분** | **130~160분** |
| 강제 host 실행 상한 | **150분 + 최종 cleanup 최대45초** | **300분 + 최종 cleanup 최대45초** |
| 시작 배터리 / 세션별 하한 | 55% / 30% | 80% / 30% |
| 실기기 retry / 실패 대체 / 추가 세션 | **0 / 0 / 0** | **0 / 0 / 0** |

시간은 cold setup·staging·회수·warmup·cooling을 포함하는 예약 추정이다. 과거27세션 약64분(52분 cooling)의 PC 기록을 참고했으며 F 실측시간은 아직 없다.
예상 범위는 보장이 아니며 느린 연결/안전 gate로 일부만 측정하고 종료될 수 있다.
150/300분은 실행기가 감시하는 상한이고 넘어가면 새 세션 없이 종료한다. Python 파일 I/O나 OS 정지까지 포함한 hard real-time 보장은 아니다.
세션당 watchdog120초, host 완료 poll125초, ADB 명령 기본30초/push90초/install120초/회수 파일45초(잔여 host 상한으로 제한).

**두 안은 대안이지 27+54세션 승인이 아니다.** 최소안 결과를 보고 정밀안의 나머지를 자동 추가하는 절차는 없다.
정밀안을 선택하면 처음부터 새 54세션 계획 전체를 고정한다. 최소안을 실행하면 정밀안은 이번 승인으로 실행하지 않는다.

## 순서·환경·중단

seed `2026092303`은 결정론적 rotation/UUID namespace에 고정한다. 런타임에서 순서를 무작위로 다시 뽑지 않는다.
U/F/C 세션을 각 block 안에서 연속 실행하되 세션 사이 동일120초 cooling을 둔다.
최소안의 block 순서는 아래와 같다. 숫자는 replicate(0부터).

| block 순번 | 조건 | 정책 순서 |
|---:|---|---|
| 1 | burst0 | U F C |
| 2 | low0 | F C U |
| 3 | queue0 | C U F |
| 4 | low1 | C U F |
| 5 | queue1 | U F C |
| 6 | burst1 | F C U |
| 7 | queue2 | F C U |
| 8 | burst2 | C U F |
| 9 | low2 | U F C |

정밀안은 여기에 burst3(U C F), low3(C F U), queue3(F U C), low4(F U C), queue4(U C F), burst4(C F U), queue5(C F U), burst5(F U C), low5(U C F)를 더한다.
최소안은 조건별 각 정책이 각 period에 한 번씩, 정밀안은 두 번씩 나오며 6개 permutation을 모두 사용한다.
최소안의 방향별 carryover는 완전 균형이 아니다. 정밀안은 조건 내 정책 순서 방향도 균형화한다.
정확한 세션 UUID/순서/이미지/모델 hash는 각 plan과 `execution_order.csv`에 기록한다.

설치 `-r`로 앱 데이터 보존. uninstall/clear 필요 시 중단한다. 매 세션 force-stop 후 실험 프로세스 부재 확인,
새 UUID의 input/output/staging 경로 부재, 동일4runtime 생성·8warmup·resident 초기 상태를 적용한다.
충전하지 않는 무선 ADB 상태를 요구한다(AC/USB/Wireless powered=false). 설정을 바꾸거나 충전을 제어하지 않는다.
thermal status0, 배터리≤35°C, paired block 첫 시작과 온도차≤1°C, 위 배터리 하한을 만족해야 한다.
runtime 생성 전·workload 전·각 요청의 기존 V4 memory gate와 thermal500ms 표본을 보존한다.
회수 후 모든 환경 표본 thermal0/low_memory=false/admit, delegate proof, artifact identity/hash, 배정 규칙과 종료 cleanup을 검증한다.
PSS는 표본 최대/평균이며 true peak나 에너지 측정이 아니다.

도착은 완료를 기다리지 않는 monotonic 예정시각 예약이며 lag 허용100ms를 유지한다.
첫 기술적 실패·연결 중단·환경/메모리/도착 지연 gate 실패·실패/거절/만료/미완료 요청에서 남은 실행을 중단한다.
단순 성능 저하나 late success 자체를 보고 조기 중단하지 않는다. warmup/setup 실패도 보존한다.
`attempt.json` 생성부터 **시도1 소비**로 보수적으로 계산한다(실제 Activity 시작 전 gate 실패도 포함).
초기 설치/식별 단계 실패는 session 시도0과 root/console 오류를 보존한다. 재시도나 실패 세션 대체는 없다.

새 run root가 이미 있으면 장치 접근 전에 실행을 거부한다. 재연결 후 `recover`만으로 기존 UUID의 파일을 회수하며 Activity를 재시작하지 않는다.
회수 성공도 이번 run의 실패를 지우거나 다음 세션 자동 실행을 허용하지 않는다. 로컬 파일 내용 충돌은 덮어쓰지 않고 중단한다.
프로세스 cleanup 실패도 오류로 남기고 다음 세션을 금지한다. ADB 단절로 cleanup 자체가 불가능하면 부재를 PASS로 기록하지 않는다.
기기/PC 원본과 staging은 삭제하지 않는다. source files·APK·plan·Android/host 코드 hash 변화는 새 실행 전 거부한다.

## 통계·지표·margin

주 비교 **burst의 C−F**, 주 지표 **긴급 세션 최댓값**과 **일반 평균응답** 두 개다.
각 block의 상대차 `(C−F)/F` 두 지표에 각각 양측97.5% paired t CI를 사용한다(Bonferroni family95%).
음수는 지연 개선, 양수는 악화다. 주 가설의 성공/실패 결합 판정이나 새 최소효과 기준은 만들지 않는다.
절대차 ms는 효과 해석용 pointwise95% CI. 나머지 조건/대비/지표도 pointwise95% 탐색 분석이며 다중 비교의 확정적 우월성 주장을 하지 않는다.
U−F, C−U, C−F의 세 대비를 조건별로 모두 보고한다. 좋은 조건만 선택하거나 조건을 섞어 평균 효과를 만들지 않는다.
모든 block의 원값·paired 차이·부호/순위를 공개하고 동률을 유지한다. n3/n6 t CI의 정규성/독립성 가정과 작은 n의 한계를 명시한다.
재표집을 주 CI에 쓰지 않으므로 요청 재표집으로 n을 늘리는 절차는 없다.

긴급 지연은 **예정 도착→output_ready**, normal은 **예정 도착→persist_complete**이다.
burst/low의 urgent2건 nearest-rank P95는 **세션 최댓값**, queue urgent1건은 그1건이다.
표의 이름에 `urgent_session_max_ms (2 requests; queue:1)`를 쓰며 모집단 P95의 정밀 추정으로 해석하지 않는다.
pooled P95를 추가하면 별도 기술값으로만 표시하고 paired CI에 사용하지 않는다.
normal 세션 평균은 각 세션의 성공 normal 응답 평균이며 조건 내 세션을 동일 가중한다.
makespan은 workload_start→마지막 기록 worker_release, throughput은 해당 세션 성공수/makespan, 정책 집계는 세션별 값 평균이다.
큐/요청을 종료 시 삭제하지 않는다. 실제 코드의 drain `done.await(100초)`는 **모든 도착 예약 직후** 시작한다(마지막 도착+100초가 아님).
watchdog/cleanup까지의 실제 wall duration도 별도 보고한다. 미완료 요청은 planned denominator에 남기고 latency를 0으로 대체하지 않는다.

전체 계획/시도/실제 도착/성공/실패/거절/만료/미완료/관측 불가를 각각 보고한다.
성공률은 실제 도착 기준과 전체 예정 요청 기준(미실행·관측 불가는 성공으로 계산하지 않음)을 구분한다.
late success는 성공의 부분집합으로 표시한다. deadline 위반율은 전체 도착 urgent, normal on-time은 전체 도착 normal을 분모로 한다.
실패가 있으면 성공 조건부 latency를 명시하고 완전한 pair 기술값만 보조 보고하며 주 CI는 산출 불가로 둔다. 원인과 빠진 pair를 숨기지 않는다.
urgent2초/normal8초는 UX SLA가 아닌 시나리오다. 과거 모두0% 위반은 차별성 근거가 아니다.

정책 비용은 요청별 기록된 `policy_compute_ns` 합/분포이며 성공적으로 dispatch 대상을 선택한 호출만 기록된다.
빈 큐/선택 불가 호출은 별도 계측되지 않으므로 총 정책 CPU 비용이라고 부르지 않는다. 모든 dispatch 지연은 응답시간에 포함된다.
worker_release timestamp 뒤 event fsync와 dispatch callback이 있어 실제 다음 선택 가능시점과 간극이 있다.
이 구간을 완전히 계측한 lane 점유라고 주장하지 않는다. 기존 inference timer는 변경하지 않는다.

과거 burst C−U n6의 paired SD는 urgent **6.126ms**, normal **10.979ms**이다.
이 SD가 C−F에도 같다는 **검증되지 않은 가정**에서 양측97.5% t 반폭은 n3 약21.95/39.33ms, n6 약7.91/14.18ms다.
상대차 SD는 urgent1.4635pp/normal0.5293pp이며 같은 가정의 주 CI 반폭은 아래 외부 `precision_reference.json`에 계산한다.
F의 SD/평균, low·queue 변동성은 아직 알 수 없어 실제 정밀도/검정력을 보장하지 않는다. n3는 각 조건의 분산을 처음 관측하면서 period를 균형화하는 최소안이고 n6는 더 많은 순서/변동성 확인이다.

**권장: 이번에는 동등성·비열등성 margin을 채택하지 않는 효과 추정안.**
사용자 가치·허용 비용과 F 분산 근거가 없어 합리적인 수치 margin을 확정할 수 없다. 단순 비유의는 비슷함의 증거가 아니다.
후속 정식 비열등성에는 urgent 허용 증가(%, ms)와 normal 최소 이득/허용 손실을 UX 근거와 함께 정하고 별도 표본 설계를 해야 한다.
과거 normal10% 손실 기준은 비교대상/질문이 다른 이번 C−F에 자동 전용하지 않는다. 이번 승인 질문은 **27세션 추정안 또는 54세션 추정안 중 예산 선택 하나**다.

## 시뮬레이션과 범위

원본 arrival/queue/exec/output/persist/release/environment를 보존하므로 이 trace 내 배정/대기/관측 overlap의 기술에 재사용 가능하다.
종단간 응답을 서비스시간으로 넣어 대기를 중복 계산하지 않는다. 새 자료로 임의 도착 분포·overlap 인과 효과·미측정 순서의 서비스 모형이 검증되는 것은 아니다.
본 시뮬레이션/새 holdout/다기기/역할반전/새 모델/열부하 실험은 이 예산에 없다.
A24·현재 분류/탐지 모델과 입력·resident·비선점·관측 thermal0 범위이며 통역/OCR/OS 전체 스케줄링/에너지 일반화는 하지 않는다.

## 구현·검증·산출물

기존 `d1_arrival_plan.py`에 새 plan protocol/generate-fixed-comparison 분기만 추가하고 기존 manifest schema/실행기/정책을 재사용했다.
두 plan의 source reference는 기존 evaluation plan SHA
`9e826188a25ecc9ca33404995cc1e45238f00f539fbb3c41eabfcdb8295cf3c3`이다.
새 ID는 기존/두 대안 간 disjoint. validator는 정책·순서·예산·source code·모델/이미지·APK·manifest 전체 동일성을 검증한다.
기존 실행기의 품질 gate 전 validated 기록과 cleanup 오류 후 계속 진행 문제를 수정했다. 기존 계약/완료 결과를 재판정하지 않는다.

관련 Python16 PASS, ArrivalPolicy JVM7 PASS. JVM 첫 시도는 SDK 환경 미설정으로 실패했고 ANDROID_HOME을 프로세스에만 지정해 재실행 성공했다(개인 환경 파일 수정 없음).
기존198요청의 event/ledger 동일성과 새 환경 검사 호환성은 PC 읽기 전용 검증 PASS.
두 설계 manifest 생성/별도 dry-run PASS. 전체 빌드·APK 조립·ADB·설치·실측·시뮬레이션 실행 없음.
원본/기존 분석·그림/기존 plan/APK758파일 전후 SHA 보존 검증은 외부 최종 receipt에 기록한다.

외부 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`:

- `fixed_split_comparison_minimum_v2/comparison_plan.json`: SHA `9812ce6ec8d04c43e9a072bf15d712a222304ca96e2a0033d564748decaa213f`
- `fixed_split_comparison_precise_v2/comparison_plan.json`: SHA `c9b7184ce7f6e4af40f3d24875f35399aa0f2711d6e9fa088b02e22bea1c9345`
- `fixed_split_preparation_v1/FINAL_REPORT.md`, `verification.json`, `precision_reference.json`, 보존 inventory, 실행 명령/스크립트.
- 각 plan 옆 `execution_order.csv`: 전체 예정 세션 목록.
- 향후 실측 출력: `fixed_split_comparison_minimum_run_v1` **또는** `fixed_split_comparison_precise_run_v1` (현재 생성하지 않음).

이 작업 중 생성한 plan 출력 v1은 초안으로 보존한다. 연결 단절을 프로세스 부재로 오인하지 않도록
cleanup 확인을 강화한 host 코드 hash를 반영한 **출력 v2만 실행 후보**다. 두 초안 모두 실측0이며
앱 schema/정책/요청/예산은 동일하다. 이후 코드 hash가 바뀌면 validator가 실행을 거부한다.

## 실제 명령과 재개

PC 전용 재검증:

```powershell
python -B -m tools.d1_arrival_plan dry-run --plan 'C:\Users\LG\Documents\D1Check_Arrival_Extension\fixed_split_comparison_minimum_v2\comparison_plan.json'
python -B -m unittest tools.test_d1_arrival_plan tools.test_d1_arrival_fixed_comparison tools.test_d1_arrival_analysis -v
```

**새 실측 예산 승인 후에만**, 저장소 root에서 권장 최소안 실행(실제로 구현된 CLI):

```powershell
python -B -m tools.d1_arrival_device run --plan 'C:\Users\LG\Documents\D1Check_Arrival_Extension\fixed_split_comparison_minimum_v2\comparison_plan.json' --apk 'C:\Users\LG\Documents\D1Check_Arrival_Extension\new_apk\benchmark-runner-modelProbe-arrival-v2.apk' --adb 'C:\Users\LG\AppData\Local\Android\Sdk\platform-tools\adb.exe' --output 'C:\Users\LG\Documents\D1Check_Arrival_Extension\fixed_split_comparison_minimum_run_v1' --approved-cap 27 --expected-plan-sha256 9812ce6ec8d04c43e9a072bf15d712a222304ca96e2a0033d564748decaa213f
```

권장 실제 진입점은 외부 `RUN_MINIMUM_AFTER_APPROVAL.ps1`(정밀안 선택 시 `RUN_PRECISE_AFTER_APPROVAL.ps1`)로 위 CLI와 console 로그를 함께 실행한다.
두 script는 plan hash·cap·새 output을 명시하며 실측을 지금 실행하지 않는다. ADB 자동 식별은 정확히 한 online device와 위 model/fingerprint를 요구한다.
연결 중단 후에는 manifest의 실제 session-id/기기 serial을 사용해 **회수만** 한다:

```powershell
python -B -m tools.d1_arrival_device recover --adb 'C:\Users\LG\AppData\Local\Android\Sdk\platform-tools\adb.exe' --serial '<실제-무선-serial>' --session-id '<attempt.json의-session_id>' --output '<새-recovery-폴더>'
```

꺾쇠 값은 중단 시 artifact에서 채우는 인자이며 현재 실행할 완성 명령이 아니다.
새 비교 결과용 분석 CLI는 아직 추가하지 않았다. 기존 분석기의 세 정책/동결 FAIL 로직을 새 결과에 그대로 실행하면 안 된다.
측정 후 기존 session_metrics를 재사용해 위 사전 규칙을 별도 분석 분기로 구현·검증한다(새 규칙 선택이나 정책 수정은 금지).
현재 완료 판정: **계획/최소 구현/PC 검증/dry-run 완료, 새 실기기 검증 미실행, 예산 승인 대기**.
