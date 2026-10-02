# 준비 이력 AP 후보의 독립 확인 준비

2026-10-02 · [고정 판독 계약](analysis_contract.json) · [계획/해시/예산](plan_summary.json) · [PC 검증](verification.json) · [후보의 기존 평가](../ap_preparation_memory_01/README.md)

**판정: 평균·최고오차 개선의 전이를 확인할 가치는 있다.** 준비 반응을 분리한 `ap-preparation-memory-v1`을 새로운 자료로 확인하되, 이미 미재현인 후기 상승까지 해결했다고 판단하는 실험은 아니다. 현재 제한된 일정/서비스 시뮬레이터를 사용하는 데 필수 실측도 아니다. 이번 사용자 ‘진행’에 따라 확인 경로를 PC에서 완성했다. 상태는 **PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED**, 실제 기기 Run·출력·소비 registry는 없다.

## 한 번에 확인할 질문

같은 네 runtime·8warmup 뒤, resident 상태에서 **공통창 시작 후 35초 또는 65초**에 동일 burst201 CG_DC 24요청을 허용한다. baseline30초를 합치면 부하 전 관측 가능 구간은 약65/95초다. 기존 기록의 온도값을 맞추거나 유리한 순간을 고르지 않는다. 새 온도 조건·주변 온도·추가 가열·추가 warmup도 만들지 않는다.

첫 확인은 기존 준비 시간에서의 새로운 실행, 두 번째는 준비에서 남은 반응이 30초 더 경과한 상태로의 전이다. 준비 이력의 차이는 **등록된 수동 유휴 경과시간**이며 서로 다른 warmup이나 강제 가열이 아니다. 동일 AP나 동일 내부 열 상태를 보장하지 않는다. 단순히 이전 B2를 두 번 더 실행하는 대신, 후보가 실제 사용하는 부하 전 AP 초기화의 전이를 비교한다.

| 고정 항목 | 값/해석 |
|---|---|
| 순서 | `confirmation_preidle35` → `confirmation_preidle65`, 결과로 순서 변경 없음 |
| 입력 | 기존 burst·seed201·B2 저장 요청, 분류GPU＋탐지CPU |
| 예정 도착 | 기존0–4.840초, 이전 완료와 무관하게 유지 |
| 실행 허용 시각 | 기존 +35초: 35.000300–46.260403초; +65초: 65.000300–76.260403초 |
| 실제 일정 | 기기에서 실제 수행한 dispatch→lane_available, PC 시간·간섭1.5를 강제하지 않음 |
| 모형 | 기존 β/상태 기울기, 후보 τ30초/γ0 고정; 개발·계수 적합0 |
| 세션별 초기화 | 부하 전 AP만으로 E/H; 마지막 부하 전 AP를 T로 사용. E는 주변 온도 아님 |
| 기본 관측 | baseline30/common120/cooling60초, 세션마다210초 |
| 분모 | 각24개 전체 요청, 미완료/실패/누락 포함; 조건당 독립 세션1개 |

후보 SHA-256: `d885b87c32d7df5b812b4cd85dcdae5230f47c9bd16d7ae2807df427b26c1466`. 이전 후보/원래 모형·자료는 byte 단위 보존했다. 이번에 새 후보를 적합하지 않으며 이미 본 다섯 세션을 새 확인 분모에 합치지 않는다.

## 사전 판독과 종료 기준

원 실행은 기존 정상 종료/회수/cleanup/품질·센서 검증을 통과해야 한다. 추가로 첫 세션의 부하 전 AP ≥55초·15표본·공백≤10초, 온전한 조회 괄호·수치 rank와 부하 후 coverage를 검사한다. 실패하면 두 번째를 시작하지 않는다. 자료가 불충분하면 임의의 기준값·0을 넣지 않는다.

분석은 회수 후 **실제 일정과 부하 전 AP에 조건부인 고정식 재구성**이다. 시작 전에 미래 일정을 모두 예측한 온라인 정책/종단간 예측이 아니다. 비교 AP는 첫 dispatch 이후→냉각 끝에서 유효하게 괄호가 확보된 표본(≥20개·최대 공백10초·처음/끝 미관측≤10초)만 사용하며 정확한 시간창을 함께 출력한다. 공통120초 전체 AP 오차로 바꿔 부르지 않는다. 두 대기 조건은 평가 길이가 다르므로 MAE 차이를 이력의 인과 효과로 해석하지 않는다.

- AP 경로 MAE·최대절대오차·최고온도 부호오차, work span/후기 유휴 잔차, 고정90–115/120–145/150–175초 방향을 산출한다. 방향창의 endpoint bracket이 없으면 null이다.
- 비교 대상은 새 고정 후보와 기존 preload 후보다. 원래 동결 AP·W식의 정확한120초 J 진단은 기존 판독기를 별도로 재사용한다. 후속 비교 오류가 이미 확보한 AP 점수/원래 오류를 덮지 않는다.
- 부하 후 관측 AP로 τ/γ/E/H를 다시 맞추거나 구간/합격선을 바꾸지 않는다. 후보의 상태 초기화는 사전에 정한 부하 전 입력 처리이며 새 전역 계수 적합이 아니다.
- 자료 적격성·오차 산출·정확도 합격·정책 판별을 구분한다. 근거 있는 보편 허용오차가 없으므로 `accuracy_pass=null`; 낮은 MAE만으로 채택하지 않는다. 후기 방향과 최고/최대오차 악화도 그대로 보존한다.
- 완료점은 두 등록 조건의 고정 후보 오차 보고 또는 최초 실패에 따른 중단이다. 실패 뒤 후보 재보정/확인 추가/다른 계획 자동 실행은 없다. 반복 변동성·물리 잔열·스로틀·임의 도착·동적 정책 J/AP는 이 두 세션으로 완료되지 않는다.

## 정확한 예산과 환경

| 항목 | 최대 |
|---|---:|
| 개발/확인 | 0/2세션 |
| 본 요청/warmup/별도 적격성/총 명시적 추론 | 48/16/0/64회 |
| runtime | 8개 |
| staging | 2회·14파일(각 입력6＋manifest1) |
| 설치본 host pull | 1회 |
| APK push/설치/새 빌드 | 0/0/0회 |
| 고정 관측 | 2×(30＋120＋60)=420초 |
| 설치본 preflight | 600초(기존 필드명 installation_seconds도 같은 예약이며 이중 합산 없음) |
| 각 세션 | stage/gate120＋poll485＋회수50＋cleanup45=700초 |
| 세션 사이 자연 대기 | 90초 |
| 전체 실행/회수/cleanup | 600＋2×700＋90=**2,090초(34분50초)** |
| ADB | **6,600명령** |
| 재시도/대체/추가 | 0/0/0 |

35/65초 대기는 공통120초 안의 실행 허용 시각이므로 고정 관측에 다시 더하지 않는다. drain30초·startAP 승인대기30초 등은 기존 poll485초 안의 제한이다. 전체 상한은 정상 예상시간이 아니다. 유사한 이전 두 세션의 실제 총616.410초는 약10분 규모의 참고값이며 현재 연결·배터리 완주 보장이 아니다.

ADB 상한은 기존 조회 주기와 실제 카운터를 보존했다. poll 최대485초에서 listing0.25초당 최대1,940개(각3초 timeout), HAL AP는2초 주기당 uptime전/thermal/uptime후3개로 최대729개(각2초), 화면10초 주기 최대49개(2초), 합2,718개/세션이다. 세션당3,200 상한과 이 차이482개는 stage/품질/시작승인/회수/cleanup 여유다. 전역은2×3,200＋preflight 여유200=6,600이다. 실제 명령 소요 때문에 보통 이보다 적고 동작 실패 시 즉시 중단한다. 회수/cleanup용100개 예약 검사와 각 단계 deadline을 유지한다. 이전 두 세션 실측1,343개는 참고이며 예상 횟수를 보장하지 않는다. 새 polling·재연결·transport 전환은 없다.

현재 A24·fingerprint·단일 online transport, 설치본 SHA/패키지/서명, 배터리≥20%·비충전·BAT≤35°C·thermal0·memory·8warmup 품질/GPU 증거는 **Run 직전 내부 절차로 확인**한다. 화면은 밝기81/자동밝기0/timeout18,000,000ms, Awake/interactive 관측 기준을 유지한다. 설정을 변경하지 않는다. numeric AP 유효성·조회 신선도(기존3초 조건)는 필수이며 개발32.5–34.0°C는 지원 범위 표시이지 실행 하한이 아니다. 대상 Activity를 유지해야 한다.

이번에는 최근 배포된 기존74e APK를 재사용한다. 747/3d8 계열로 만든 후보 자료와 **APK 프로토콜 전이**라는 점을 함께 표시한다. 현재 설치 상태는 이번 PC 작업에서 조회하지 않았다. 불일치/확인 불가이면 전송·설치 fallback 없이 중단한다. 연결이 끊기면 기존 회수/소유자 종료 계약을 적용하고 미확인 상태를 성공으로 표시하지 않는다. 앱 cleanup·host force-stop·프로세스 부재는 별도 기록한다.

## 계획·Check·이후 실행 명령

외부 계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_memory_confirm_plan_v1/collection_plan.json`

계획 SHA-256: `7013bcfe99b922d44c6d78801935c182dc6e525e4df60b1577ecafbb9108cfbd`

기존 프로젝트 서명 APK: `recorded_policy_compare_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk` (외부 자료 루트 기준), SHA `74e8065d10bdfac01c4fbda77afeac196986501b9534bf02d1dd5b0ad541ee6e`. 패키지 `com.example.d1check.benchmarkrunner.modelprobe`, versionCode1, 프로젝트 인증서 SHA `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`. 로컬 APK/소스 출처/인증서 검증 완료이며 전송·설치하지 않았다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_memory_confirm_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check
# 두 확인 세션 실행이 승인된 뒤에만, 한 번:
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_memory_confirm_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -ExpectedPlanSha256 '7013bcfe99b922d44c6d78801935c182dc6e525e4df60b1577ecafbb9108cfbd'
# 종료 후, 존재하지 않는 별도 PC 출력 경로:
python -B -m tools.d1_ap_memory_confirmation_readout --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_memory_confirm_plan_v1/collection_plan.json' --output output/ap_memory_confirmation
```

실행기 자체가 현재 단일 transport를 선택한다. 위 스크립트에 임의 Serial 인자를 추가하지 않는다. 복수/부재로 선택 불가이면 중단하며 외부 중복 조회나 reconnect를 하지 않는다. 실행 출력은 `energy_ap_memory_confirm_run_v1`, 소비 기록은 `ap_memory_registry/ENERGY-AP-MEMORY-CONFIRM-01`로 별도다. **둘 다 아직 존재하지 않는다.** 구 계획은 재개하지 않는다.

## PC 검증

관련14검사(새6＋기존 bundle8), 실제 PowerShell→Python Check, ADB 프로세스 실행 차단을 건 Check 통과. 실제 공용 Run 함수에 가짜 Device를 주입해 정상2세션·첫 poll 실패·설치본 불일치·첫 AP 부적격·정리1회·원래 stack 보존을 검사했다. Android/장시간/무선 안정성 검증이 아니다. 앱 코드·APK 빌드 변경0이다.

기존 bundle02 두 원문을 **복사한 PC fixture**로 실제 판독 CLI를 통과시켰다. 후보 MAE0.2477597656/0.1460578397°C가 직전 사후 분석과 일치했다. 이는 새 확인 결과가 아니다. 부하 후 AP 제거 fixture는 null/부적격, 계획 폴더 내부 출력은 쓰기 전에 거절했다. 원본 근거38파일·모형3개 hash 불변. 새 후보의 적합 함수를 호출하지 않는 경로와 미래 목표 AP 변경 시 예측 불변을 검사했다.

**다음 행동 하나:** 이 두 확인 세션을 실행할 때 해당 계획의 예산과 현재 기기 gate를 적용한다. 이번 완료 범위는 계획·동결·PC 실행/판독 준비이며 기기 실행은 포함하지 않았다.
