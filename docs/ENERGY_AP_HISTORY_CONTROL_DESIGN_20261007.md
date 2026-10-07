# 배경 소비·부하 이력 분리 수집 설계 — 2026-10-07

**권고: 개발6 → 절차·계수 동결 → 별도 확인6, 최대12세션의 한 캠페인.** 단순 무부하/부하 반복이 아니라 같은 등록 사전부하 뒤 고정 회복시간을 바꾼다. 현재 상태는 **PC 구현·서명 APK·실행 계획 Check 완료, 실측 미승인·미소비**다. 아래 초기 설계와 구별해 10/8 구현 결과를 함께 보존한다. 이 문서는 실측 승인이나 기존 종료계획 재개가 아니다.

[설계JSON](results/history_control_plan_01/design.json) · [PC검사](results/history_control_plan_01/check.json). 착수09ab32e, 원모형 SHA5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2 유지.

## 기존 측정과 다른 점

[기존 배경 대조4](results/online_policy_study_01/background_identification_pc_v1/README.md)는 C0_PRE/CPU와 PAR/C0_POST가 서로 다른 중단block에 걸쳤다. 초기전력 입력창 오류는 이미 수정했으며 양의 배경AP 보정gamma는0, CPU활동과 전력잔차의 연관도 일관되지 않았다. 이를 다시 같은 설정으로 반복하는 것을 해결책으로 삼지 않는다. [추가 견고한 계수](MODEL_ROBUST_GAIN_20261007.md)도 지속8에서 악화했다.

새로 조작하는 항목은 **사전 등록된 동일CPU부하 이후의 회복시간30/180초**다. 기존 잠재 잔열30초 시간상수에서1/6배 시간상수에 해당하는 구분용 설계값이며 실제 물리상수·평형도달 보장이 아니다. 실제 잔열이 이 시간에 사라진다고 전제하지 않는다. 목표는 사전AP가 비슷해도 등록된 과거부하 이력이 추가 예측정보인지 확인하는 것이다. 같은 AP를 만들기 위한 가열/온도대기/추가warmup은 없다.

## 12세션 구성

|자료역할|회복pause|목표 구간|세션|
|---|---|---|---:|
|개발|30초|무부하C0 / CPU96 / PAR96|3|
|개발|180초|무부하C0 / CPU96 / PAR96|3|
|동결 후 별도 확인|30초|무부하C0 / CPU96 / PAR96|3|
|동결 후 별도 확인|180초|무부하C0 / CPU96 / PAR96|3|

개발순서: 짧은C0→짧은CPU→짧은PAR→긴PAR→긴CPU→긴C0. 확인은 역순. 완전무작위나 순서효과 제거를 주장하지 않으며 block/순서/직전세션/중단이력을 보존한다. 각조건 개발1·확인1은 식별 대조와 별도실행 예측 확인의 최소구성이지 분산·tail·반복안정성 증명이 아니다. CPU/PAR차이 질문을 제외하면8세션으로 축소할 수 있으나 이번 권고는 실제 정책차이까지 판독하기 위해12다.

모든 세션은 동일 resident/runtime4, warmup8 뒤 **conditioning CPU96**을 먼저 실행한다. 입력은 기존 separated confirmation96(분류/탐지교대, 도착35초부터350ms간격, 기한기존값), CPU_URGENT_ONLINE_V1. conditioner 공통120초 종료시 모든 요청·lane가 끝나지 않으면 중단한다. 요청을 강제로 감속하거나 목표 병행을 만들지 않는다.

conditioner120초 → 고정pause30또는180초 → 기존 목표관측210초(준비30+공통120+냉각60). 목표CPU/PAR는 같은96요청 입력이며 C0만0요청이다. 같은runtime를 계속 보유하고 단계 사이 재생성·추가warmup0. pause는 **conditioner 창 종료 기준**이다. 실제 마지막lane부터 목표 첫dispatch까지는 나머지conditioner 유휴+pause+목표준비30+공통내35초 등을 포함하므로 이를30/180초 실제냉각이라고 쓰지 않는다. 두 origin과 연속 Android monotonic시각을 함께 저장한다.

## 관측·환경

동일모델/input/resident/화면 내용·밝기 설정을 유지하고 기존 battery/비충전/BAT/thermal0/메모리/품질gate를 승계한다. 수치기준은 최종 바인딩할 원계약에서 검증하며 이 설계에서 완화하지 않는다. numeric-ap-observe-v2의 유효성/신선도와 모형시작범위를 구분한다. 개발범위 밖AP는 외삽진단이며 실행안전을 새로 인증하지 않는다.

900ms전력 sampler와 기존 약3초AP관측, 실제dispatch/return/output/persist/worker_release/lane해제를 연속기록한다. 목표120초의 총량뿐 아니라 conditioning/pause/목표부하/냉각을 따로 적분한다. 초기상태 식별에 필요한 conditioning 이전 AP기록도 확보해야 한다. AP조회주기는 센서내부갱신주기가 아니다. 짧은병행독립전력계수 식별은 이번 목표가 아니다.

기존Perfetto CPU/process/frequency/loss/clock 경로는 가능한한 재사용하되 **전세션 같은 설정**이어야 한다. tracer비용을 임의로 빼지 않는다. CPU활동만으로 GPU/무선/외부앱 에너지를 귀속하지 않는다. 시스템조회추가가 필요하면 종류/주기/예산과 계측변경을 먼저동결한다. 원격로그에서 개인PID/식별값은 공유제외. 주변온도 계측이 없으면 null, 시작AP를 주변온도 대체값으로 쓰지 않는다.

## 후보와 확인 경계

원동결 모형을 모든세션의 기준으로 유지한다. 신규 AP후보는 기존 연속식 T′=−β(T−R)+k·u+H, H′=−H/30+g·u/30에서 **등록 conditioning 이력까지 연결하고 g≥0 하나만 적합**한다. β/k/30초와 상태입력은고정, R/H초기는 conditioning이전 관측으로기존방식추정한다. 이미실패한 후보를 채택하는 것이 아니라 새통제이력에서 이항이식별되는지묻는다. 임의시간상수탐색·주변온도생성·확인결과에따른재적합0.

개발6으로 적합하고 짧은/긴 이력 block을 통째로 제외하는 진단을 한다. 수치적으로미식별, 계수의block불안정, 어느이력에서든 방향/경로오차가기준보다악화하면 확인6은 진행하지않는다. 구체적 기계판독·초기화실패·수치안정 기준은 실행기동결전에PC구현해야 한다. 이 규칙은 후보선택이며 사후정확도PASS숫자가아니다. 적격시계수/절차/입력/코드SHA를동결하고 확인6은한번만수행한다. 확인자료의부하후AP/전력으로재적합하지않는다.

에너지는 기존전력식을 유지하고 두회복이력의 C0 기준·부하후잔차·CPU/PAR짝차이를 측정한다. **새자료가있다고 배경변동을 미래에예측가능하다고전제하지않는다.** 에너지보정은 새구조를 즉석추가하지않고 식별가능성판독까지만이번완료범위로둔다. 원인이외생·비관측이면 오차하한/적용제한이결과다. 이계획이 J와AP모두감소를보장하는것은아니다.

A 실제일정조건부 예측이 주분석, B 예정도착→기존동결일정→비용은 별도보조다. 무부하와정책세션을같은실현배경인것처럼빼지않으며 통제된조건대조로만쓴다. 세션표본을독립반복수로늘리지않는다.

## 판독과 종료

자료적격성: 원본전류/전압/AP공백·단위·시계/단계/lane·warmup·runtime·호출분모·trace loss·cleanup. 누락0채움금지. 예정요청의실패/미완료/미확인유지. 기준밖구간삭제금지.

정확도: 같은120초J부호/절대/상대오차, 전후부하분해와상쇄, 누적잔차. AP절대/초기대비변화/MAE/최대/피크/가열냉각/이력별잔차. CPU/PAR의관측차이와예측차이오차는별도보고한다. 허용폭근거없으므로임의PASS나작은정책우월성확정금지.

종료결론은 후보확인개선/특정이력만개선/식별불충분/외생배경으로개선미확인 중하나다. 확인이악화하면같은캠페인에서후보수정·재확인하지않는다. 실패시증거회수·소유한앱cleanup예약후중단하며 자동재연결·설정변경·대체/재시도0. 원본실패를지우지않는다.

## 최초 설계 시점의 예산과 미준비 상태 (10/7 기록 보존)

|항목|최대 설계량|
|---|---:|
|세션|개발6+확인6=12|
|conditioning 요청|96×12=1,152|
|목표 본요청|96×8=768|
|warmup|8×12=96|
|별도적격성추론|0|
|총명시적추론|2,016|
|runtime|48|
|staging 계획|12회·84파일|
|설치본pull / APK push / 설치|각최대1 (동일설치생략)|
|관측·등록pause|5,220초=87분|
|세션사이고정90초×11|990초=16.5분|
|고정부분합|6,210초=103.5분|
|재시도/대체/추가|각0|

고정합에는 APK검증/전송/준비warmup/gate/회수/cleanup/PC동결시간이 빠져 있다. **총6시간은 제안 예약상한이며 검증된 실행상한/예상완료시간이 아니다.** 과거700초 또는936초세션상한을새연속history단계에그대로전용하지않는다. ADB최대수·전체강제상한·최종staging구성은null로둔다.

실행전에끝낼구체적차단4개:
1. 같은resident의conditioning→고정pause→목표관측, 두origin·호출상한·lifecycle/중복cleanup·종료예약을 기존앱에 opt-in구현/테스트. 현재manifest는단일공통창이므로 기존러너무수정실행불가.
2. 최장510초등록관측과실제준비/회수를포함해watchdog·trace현재600초상한/64MiB·AP조회/ADB예산/저장공간을코드산정.6시간예약을넘으면자동증액하지않고계획재판정.
3. 연속history후보·세션/block제외·동결/확인gate·초기관측/누락/미래누출차단을PC검증.
4. 필요APK변경만기존키서명후소스/APK/manifest/계획/실행기SHA바인딩. 이번에는빌드/설치/Run없고후보APK정확경로는미정.

현재Check는 **설계조합과산술만통과**한다. 실기기실행명령을제공하지않으며이전RUN스크립트로대체하지않는다. 새실행폴더/claim도만들지않았다. 사용자지시가계획작성인이번에는실측미승인상태를유지한다.

```powershell
python -B -m tools.check_history_control_design
```

**다음행동하나:** 위4개경계를하나의PC구현작업으로마치고, 소스·APK·정확상한을묶은최종실행계획을동결한다. 중간작은기기진단을추가하는것이아니라전체통합수집의실행경로를완성하는작업이다.


## 10/8 구현 결과와 최종 실행 계약

앱 `registered-history-control-v1`을 opt-in으로 추가했다. 기존 단일창·onDestroy 취소·runtime/worker 소유권과 정상/실패 cleanup은 유지한다. 4 runtime·8 warmup을 한 번만 수행하고, 같은 sampler·dispatch/lane worker로 두 120초 창을 수행한다. 요청 ID는 단계마다 다르며 서로 중복을 금지한다. 창 종료 시 미완료가 있으면 다음 단계로 넘어가지 않는다. conditioner/target의 Android elapsedRealtimeNanos origin·회복·baseline 경계와 실제 lane 해제를 별도 기록한다.

앱 watchdog 900초, trace 1,000초/128MiB로 별도 등록했다. 기존 경로의 watchdog 480초/trace600초·64MiB 기본값은 유지한다. host 반복 관측은 listing 최소0.25초·3초 timeout, thermal 관측 시도 간격2초(실제 client 지연 포함), 화면10초를 유지한다. 전력900ms와 trace flush/write5초를 유지하되 더 긴 기록·단계 이벤트가 추가되므로 **새 계측 프로토콜**이다. 비용을 기존 데이터에서 임의 차감하지 않는다. trace는 같은 설정으로 conditioning부터 목표창 끝까지 CPU coverage/loss/clock를 검사하며 자동 종료 후에도 원본을 보존한다. CPU 활동만으로 전체 에너지 원인을 귀속하지 않는다.

**numeric AP gate는 conditioning 직전 한 번**이며 observe-v2 신선도≤3초를 유지한다. 목표 부하 직전 두 번째 handshake를 추가하지 않았다. 목표 baseline과 초기35초 AP는 기존 host 관측으로 사후 자료 적격성을 확인하며, 해당 경계의 실시간 numeric AP 보장을 주장하지 않는다. 앱 내부 thermal/메모리 감시와 host 환경 관측은 계속된다. 연결 소실·필수 조회 오류는 기존 bounded 중단/회수 경로를 따른다. native hang·OS 정지에서 소프트웨어 watchdog이나 host 예약이 실제 벽시계 종료를 절대 보장하지 않는다.

환경은 기존 비충전, 배터리 시작/운영≥20%, BAT≤35°C, thermal0, 기존 화면·메모리·품질 기준을 바꾸지 않았다. 현재 환경은 아직 조회하지 않았다. 모형 개발 시작AP 하한을 새 실행 차단에 넣지 않는다. AP 범위 밖·새 전환의 결과는 진단이며 strict 확장 또는 정확도 PASS가 아니다.

### 후보의 정보 경계와 기계 판독

기존 β/k/tau30·상태 전력은 고정한다. 개발6의 **conditioning 첫부하35초부터 회복·목표·냉각 끝까지** AP를 g 하나의 추정 목표로 사용한다. 짧은 목표창만 보고 g를 맞추는 대신 등록 이력의 가열·회복 반응도 포함한다. 세션마다 동일 가중치이며 센서 표본을 독립 세션으로 세지 않는다. 초기 R/H는 conditioning 전 baseline부터 conditioning 내 첫35초 이전 AP만 사용한다. 확인에서는 g를 고정하고 같은 초기 관측 규칙만 사용한다. 목표 부하후 AP와 전류는 평가 목표이며 후보 예측 입력이 아니다. 실제 일정 조건부 A만 구현했으며 예정 도착부터의 B는 이번 자동 판독에 포함하지 않는다.

수치 gate: g basis 제곱합>1e-12, 초기 상태 scaled condition≤1e8, g>0. 이는 수치 식별 검사이지 물리적 식별 보장이나 정확도 허용폭이 아니다. 짧은/긴 이력 각각을 통째로 제외해 다른3세션으로 g를 추정하고, 제외한 block의 목표 AP 평균 MAE가 기존 모형보다 악화하지 않으며 0.1°C 양자화 구분 가능한 가열/냉각에서 반대 방향을 내지 않아야 한다. 두 block 모두 통과해야 확인으로 간다. 조건별 오차와 계수는 모두 남기며 계수 변동성을 통계적으로 인증하지 않는다.

AP 표본 간격 최대10초, 초기 관측은 기존 최소55초/15표본·동기화 bracket 검사를 사용한다. 전류 적분 공백2.5초 초과·결측은 0으로 채우지 않는다. 회복 중 AP 누락도 검출한다. 공개 AP metrics는 목표35초 이후부터 냉각 종료의 실제 관측 표본까지이며, ΔAP는 이 공통 평가 첫 표본 기준임을 표시한다. 에너지는 목표 [0,120]초의 기존 식으로 계산하고 pre[0,35] / 실제 마지막lane까지 / 이후 유휴의 부호 있는 잔차를 합산한다. C0의 부하구간은 없으며 null인 방향을 성공으로 세지 않는다.

개발6 적격·gate 통과 뒤 별도 PC child에 최대300초를 주어 결과·동결 계수·UTC·SHA를 기록한다. 개발 근거와 코드 SHA를 매 확인 세션 전에 대조한다. 미식별·gate 실패·시간 부족이면 확인0회로 종료한다. 확인 자료로 다시 추정하는 API는 거부한다. 마지막 분석도 별도 최대300초이고 원래 오류와 로그를 보존한다. host 원래 cleanup을 재사용하므로 이미 정리한 이전 세션에 다시 force-stop하지 않는다. 중단 prefix에 두 창 경계와 history 경계를 추가했다.

### 정확한 최종 예산

|항목|상한|
|---|---:|
|세션|개발6 + 확인6 = 12|
|conditioning / 목표 요청|1,152 / 768|
|warmup / 별도 적격성 추론|96 / 0|
|총 명시적 추론 / runtime|2,016 / 48|
|staging|12회·84파일|
|설치본 host pull / APK push / 설치|각 최대1회, 동일 APK 생략|
|trace host pull|최대12회·각128MiB 미만|
|등록 관측·회복 / 세션 간 pause|5,220초 / 990초|
|설치 확인·배포|600초|
|세션당 예약|1,446초|
|개발 동결 / 최종 PC 분석|각300초|
|전체 예약|**19,557초 = 5시간25분57초**|
|ADB|**91,400명령** (설치 등200 + 세션당7,600×12)|
|재시도·대체·추가|모두0|

세션1,446 = 준비120 + trace시작90 + launch26 + host관측925 + 앱원본회수120 + cleanup45 + trace회수/판독120. 전체는600 + 12×1,446 + 990 + 300 + 300 + transport예약15이다. CLI는 승인된 현재 serial을 요구하고 별도 자동탐색/재연결을 추가하지 않는다. 고정103.5분에 초기준비 baseline·warmup·조회/전송·회수 시간이 추가되므로 정확한 정상 예상시간은 아직 미확인이다.

ADB 상한은 추정 소비량이 아니라 client에서 강제하는 중단 한도다. 925초 최단0.25초 listing≤3,700, thermal 시도≤463×3명령, 화면≤93×4명령, 나머지 설치확인·warmup품질·AP승인·staging·회수·trace와 여유를 합쳐 세션7,600으로 제한한다. polling은 최소500명령을 회수/cleanup용으로 남기며 실제 시간도 각각 예약한다. 모든 호출이 timeout까지 걸리면 완주 대신 중단한다. Check/시작 admission은 host 여유4GiB를 요구하며 무제한 로그 보관/OS 쓰기 성공을 보장하지 않는다.

### APK·계획·재현

- 계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_control_plan_v1/collection_plan.json`
- 계획 SHA-256: `da212cf9b2bed901c6e57855206ccdd3777f972a2879030eadeaf124b079954f`
- APK: `C:/Users/LG/Documents/D1Check_Arrival_Extension/history_control_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`
- APK SHA-256: `3840bfb161b038ae61f34cd4215f8fe88bc511ec4e5f87cccc3b58e02c8768be`
- 프로젝트 인증서 SHA-256: `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`
- package `com.example.d1check.benchmarkrunner.modelprobe`, versionCode1/versionName1.0. 격리 build_receipt의 소스별 SHA와 대조했다. 바이너리·키는 Git에 올리지 않는다.
- 현재 설치본과 일치 여부는 미확인. 새 APK는 전송/설치하지 않았다.
- 원설계 `design.json`과 설계 Check는 10/7 기록 그대로 보존하고 최종 구현 근거는 [implementation_check.json](results/history_control_plan_01/implementation_check.json)에 둔다. 새 실행 출력/registry/claim은 없다.

```powershell
# 기기 명령 없는 실제 최종 Check (이번에 수행)
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_control_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check

# 이번에는 호출하지 않음: 향후 이 예산의 실측 승인과 현재 transport 확인 후 단 1회
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_control_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 승인된 A24 transport>' -ExpectedPlanSha256 'da212cf9b2bed901c6e57855206ccdd3777f972a2879030eadeaf124b079954f'

# 관련 PC 검사
python -X utf8 -B -m unittest tools.test_d1_history_control tools.test_d1_background_activity_plan tools.test_d1_energy_device_lifecycle_cleanup
```

Android 검증은 `:benchmark-runner:testModelProbeUnitTest`에 ArrivalHistoryControlTest·ArrivalEnergyLifecycleTest·ArrivalEnergyContractTest를 지정해 12건 실행했다. 신규 단계 helper4건, 실제 lifecycle callback5건, 기존계약3건이다. Python26건에는 원본 형식의 clock/power/lane 파싱 fixture, 실제 host 진입 경로의 모사12세션, 개발동결 실패 후 확인 차단, 원래 오류·cleanup 재사용이 포함된다. **native GPU 추론이나 완전한 Android 두 창 실측을 PC에서 검증한 것이 아니다.** 관련 본문/테스트 소스 컴파일과 기존 프로젝트 서명 빌드 통과. 전체 과거 배치·RL·기기 명령0.

**완료 범위:** 실행 경로·분석/동결/차단·바인딩·PC Check 준비. **남은 한계:** 새 앱 경로의 실기기 안정성, 장시간 trace 적격성, 두 회복 이력의 구분 가능성 및 후보의 실제 예측 개선. **다음 행동 하나:** 이 한 캠페인의 실측 승인 후 현재 환경 gate를 확인해 실행한다. 추가 작은 진단이나 새 후보 탐색을 자동 연결하지 않는다.
