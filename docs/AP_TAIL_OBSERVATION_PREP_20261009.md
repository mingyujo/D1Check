# AP 긴 무부하 대조·부하 회복 — PC 실행 준비

**실제 후속 결과:** plan_v2를 승인1회 실행했으나 C0 종료 경계 결함으로 중단·소비됐다. 수정 후보는 PC에서 준비했으며 기존 계획을 재개하지 않는다. [결과·수정](AP_TAIL_OBSERVATION_RUN01_20261009.md).

2026-10-09 · ENERGY-AP-TAIL-OBSERVATION-01 · **미승인·미소비, 기기 명령0**

같은 네 resident 구성의 긴 C0와 등록 부하 뒤 긴 회복을 한 block으로 준비했다. 기존 AP 후보의 느린 꼬리가 작업 이력에 따른 것인지, 작업과 무관한 시간 경과 기준 변화인지 구분할 정보를 추가한다. 같은 B2를 반복하거나 기존 모형을 재보정하는 실행이 아니다. 새 실측이나 오차 감소 결과는 없다.

[준비 화면·재현](results/ap_tail_observation_prep_01/README.md) · [분석 계약](results/ap_tail_observation_prep_01/analysis_contract.json) · [예산·해시](results/ap_tail_observation_prep_01/plan_summary.json) · [PC 검증](results/ap_tail_observation_prep_01/verification.json).

## 정보 공백과 모형 경계

[완료한33세션 판독](AP_TAIL_IDENTIFICATION_RESULTS_20261009.md)을 재사용했다. 부하연동 fast4+slow1 주후보는 새개발4 제외평가 MAE0.279°C로 개선했으나 시간상수1920초가 탐색 상한이다. Clock 대조도 비슷하게 맞았다. 기존 C0의 부하 시작 경계 이후143–145초는 같은 프로토콜의 긴 대조가 아니며, macro 부하후 AP268–270초만으로 느린 시간상수나 열 원인을 확정할 수 없다.

기존 LOAD_SLOW·CLOCK_SHIFT의 **최종 계수를 그대로 고정**하고 원동결식과 비교한다. 이번 기본 분석에는 적합0·τ 탐색0·확인후 후보교체0이다.1920초는 현재 상한 격자의 참고 관측 길이이며 진짜τ·평형·특정 정밀도를 보장하지 않는다. 미식별이면 그 상태로 종료한다. 새 자료를 이후 별도 개발에 사용하면 같은 자료를 그 새 모형의 독립 확인이라고 하지 않는다.

C0는 공통 시간 변화와 부하 의존을 구분할 수 있지만, 부하가 유효 유휴 기준을 바꾼 효과와 숨은 열 상태의 효과는 여전히 동등하게 설명될 수 있다. 주변 온도·내부 온도·숨은 초기 상태를 만들지 않는다. 고정 C0→부하 순서는 순서·환경·잔열 교란을 완전히 없애지 않으며 반복 변동성을 증명하지 않는다.

## 고정 입력과 실제 진입

|순서|역할·조건|baseline / common / cooling|본작업 최대|
|---|---|---|---:|
|0|확인 대조 C0_LONG|120 / 600 / 1920초|0|
|1|확인 LOAD_A_LONG|동일|1,200|

LOAD_A는 기존 DEV_A와 같은 분류CPU60초→유휴90초→탐지CPU60초→유휴90초→분류GPU60초→유휴90초→CG_DC60초→잔여90초다. C0는600초 전체가 명시적인 무부하 블록이다. 둘 다 같은runtime4·warmup8·적격성4·별도 준비120초를 유지한다. C0는 추론 전체0이 아니라 **본작업0·준비 추론12**다.

새 `energy-ap-tail-observation-v1` / `tail-observation-regimen-v1` opt-in을 기존 EnergyCollectionActivity의 runtime·worker·sampler·lifecycle·회수 경로에 연결했다. 기존1800초 계약은 그대로이며 새 경로에만 watchdog3540초, 냉각1920초, C0를 허용한다. 등록 버전·정확한 블록·호출 상한·창 길이를 초기화 전에 확인한다. LOAD 입력 누락을 C0로 인정하지 않는다.

250ms cadence·실제 시작/반환/output_ready/worker_release/lane_available와 한쪽만 남은 병행 tail 의미는 유지한다. 새 과업·인위적 감속·임의 가열·추가warmup·온도 선택 대기는 없다. Activity 유지 조건과 onDestroy 취소를 보존했다. watchdog이 native hang/전체 프로세스 정지를 항상 끝낸다고 주장하지 않는다.

## 환경·계측·판독

동일 A24/fingerprint/하드웨어값·현재 transport·APK/프로젝트 서명·모델/입력·resident를 향후 승인된 Run에서 확인한다. 여러 연결이 있어도 한 transport로 고정한다. 다른 연결 해제·자동 전환/재연결·daemon 재시작·설정 변경은 없다.

비충전·배터리≥20%·BAT≤35°C·thermal0·화면81/manual/timeout18000000ms·메모리/품질 기준을 유지한다. Numeric AP 유효성과 실제 부하 시작의 조회 전후 Android 단조시각/3초 신선도를 확인한다. 이전32.5–34.0°C gate는 이번 실행 하한이 아니다. 현재 후보의 새개발4 부하전 마지막 AP26.5–28.8°C 맥락과도 구분하며 온도 지원을 자동 확대하지 않는다.

앱은 numeric AP를 직접 읽지 못한다. 시작 승인 이후 host AP는 관측이며 결측/공백을 자료 적격성으로 따로 판정한다. 앱 thermal/BAT/화면/메모리 감시를 numeric AP의 동등값으로 보지 않는다.

900ms sampler·최소2초 host AP/listing·최소10초 화면/heartbeat·30초 host checkpoint를 유지한다. 긴 관측과 기록도 기기전체 소비에 포함되며 새APK/프로토콜 비용을 추정해 빼지 않는다. 센서 내부 갱신과 조회 주기는 다르다. A24 current raw=mA의 조건부J 해석과 절대 정확도 미인증을 유지한다.

예측은 **실제 일정 조건부A**다. 부하전 AP로 기존 R/H 초기화와 pre W를 구성하며 이후 AP/전류는 정답으로만 사용한다. 예정 도착부터의 종단간B·온라인 정책·열→처리율은 이번 질문이 아니다. 새APK·긴 관측·초기AP·상태/전환 지원을 따로 보고하며 수식 계산을 strict 지원으로 승격하지 않는다.

Android elapsedRealtimeNanos와 host /proc/uptime bracket으로 정렬한다. AP bracket≤4초/불확실성≤2초/공백≤10초/시작·끝 미관측≤10초를 검사한다. 기존 모형 clock의t=35가 실제 common 시작,635가 끝,약2555가 냉각 끝이다. reference120은0..120(**부하전35초 포함**), 등록600초는35..635, 회복은635..실제끝이다.

원자료·journal·lane 구간·AP 오차/방향을 보존한다. sampler 종료 때문에 마지막 전력 표본 뒤가 빠지면 회복 전체J와 예측오차는null, covered J/시간·누락을 보고한다. 끝을 외삽하거나 부분 합계를 전체로 표시하지 않는다. 등록600초 전력은 뒤의 냉각 표본으로 경계 coverage를 확인한다.

## 중단·종료

- C0 gate/앱/회수/자료 적격성이 실패하면 부하 세션을 시작하지 않는다. 예산 부족도 다음 세션을 차단한다.
- 연결 소실/실패는 기존 단일시도 중단·부분 회수 규칙을 따른다. 자율 구간이 활성일 가능성이 있으면 강제 종료/성공을 임의 확정하지 않는다.20분 복구 대기·추가 회수·재시도는 승계하지 않았다.
- 앱 cleanup·host force-stop·프로세스 부재와 원오류/회수/요약 오류를 분리한다. 중복 cleanup을 막고 새 경로 preflight의 정지/소유권 gate 실패 시 앱을 임의 정리하지 않는다.
- 완료는2조건의 적격 기록과 사전고정 comparator 오차·방향·미식별 보고다. 근거 없는 정확도PASS·정책 절감·모든 초기 온도 지원·물리 기제 완성을 조건으로 만들지 않는다.

## 코드에서 산출한 예산

|항목|상한 또는 고정시간|
|---|---:|
|세션|C0＋부하=2|
|본작업 / 적격성 / warmup / 명시적 추론|1,200 / 8 / 16 / **1,224회**|
|runtime / staging / 파일|8 / 2 / 14|
|설치본 host pull / APK push / 데이터보존 업데이트|각최대1회, 동일 설치본이면push/install 생략|
|고정 관측|각2,640초, 총**5,280초=88분**|
|별도 고정 준비 / 세션 사이|240초 / 90초|
|설치확인·배포 / PC후처리 예약|600초 / 600초|
|세션 예약|각3,880초=gate·staging120＋launch20＋poll3600＋회수60＋cleanup45＋검증35|
|전체 누적 예약|**9,050초=2시간30분50초**|
|ADB 총상한 / 일반 단계 상한|**16,752 / 16,652명령**|
|재시도 / 대체 / 추가|0 / 0 / 0|

명령 산식은 세션별 listing1801＋thermal5403(3명령×1801)＋screen361＋heartbeat361＋게이트/준비/staging/회수300=8226, cleanup예비50씩과 설치예비200이다. iteration 후 최소2초 대기로 조회를 제한하며16,752명령을 모두 소비할 목표로 보지 않는다.

개별timeout은 listing/heartbeat3초·thermal/화면2초·파일pull10초·arm5초·launch20초·archive35초·설치본pull180초·APKpush180초·install120초 등 기존 경계를 따른다. stage는 기존 개별 상한과120초 deadline을 쓴다. 앱 단계 timeout/고정시간 합계3360초＋cleanup예비45초=3405초로 watchdog3540초 안에 있다. hostpoll3600초와 회수/정리예약은 그 뒤를 포함한다.

고정 관측88분은 정상 전체 소요시간이 아니다. 정상 예상은 관측88분＋준비4분＋사이1.5분에 setup/품질/설치·회수의 실제시간을 더한 형태다. 개별timeout의 합계나9050초 예약은 OS 정지/host suspend/native hang에도 벽시계 종료를 보장한다는 뜻이 아니다.

## APK·최종 계획

APK: `C:/Users/LG/Documents/D1Check_Arrival_Extension/ap_tail_observation_signed_v1/benchmark-runner-modelProbe.apk`,106,203,985B.

- APK SHA `dd55b04d1f91be1f30ce894afdb0d80b2ec8815f1a938a6903836d568e675497`
- 기존 프로젝트 인증서 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`
- package `com.example.d1check.benchmarkrunner.modelprobe`,versionCode1/versionName1.0
- 기존 설치 계열57d2320c… APK와 소스가 다르다. 격리 build_v1/source_snapshot·adjacent build_receipt에 출처를 보존하고 서명 전후860개 비서명ZIP payload 동일을 확인했다. 전송/설치0.

계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_plan_v2/collection_plan.json`.

- 계획SHA **`e4aec38289084840df0a54a9c2322354bda1e6c83388bd47e85a7d95641e6f68`**
- 분석계약SHA `486e2bbabda761f070814c568fded2f54c8ab5d10b8bf2dd7e801151c7914825`
- 사전동결후보SHA `aa28410d701c9810001a4e6c176823e7d2b446f46f980ebeab3ff14f4540cc84`
- 원동결모형SHA `5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2`
- 원본 실행스크립트SHA `2017d7207e1de4093ff4ed85b4e2e1db258da50cf198430eca37998ab387b148`

```powershell
# PC Check 수행 완료: 기기0,claim0,Run0
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Check

# 위 전체 예산의 별도 승인 및 현재 A24 transport 확보 후에만:
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 확인한 A24 transport>' -ExpectedPlanSha256 'e4aec38289084840df0a54a9c2322354bda1e6c83388bd47e85a7d95641e6f68'
```

기존 foreground PowerShell parent/child wrapper·runID·host_entry start/end·stdout/stderr·Python checkpoint를 재사용했다. detached 실행 구조는 만들지 않았다. 최종plan_v2 하나가 실행 대상이다. v1은 Windows CRLF 변환 때문에 원본 script SHA 검사 보완 전 초안으로 남겼고 소비/FAIL/stopped로 기록하지 않았다. v2는UTF-8/LF 원본을 쓰고 byte SHA까지 확인한다. 기존 소비plan_v3와 다른 종료계획은 재개하지 않는다.

## PC 검증과 보존

새Python12, 기존 관련host9, 기존artifact reader1을 검증했다. 실제host 진입을 mock Device로 격리해 정상2세션·첫실패시 다음미시도·cleanup 재사용·consumed 차단·원오류/receipt/checkpoint를 확인했다. 실제C0 parser·빠진block/금지load·창끝결측null·미래AP/전력 누출·긴구간 연속성도 검사했다.

Android 새4＋기존regimen4＋실제lifecycle callback2=10개가 테스트본문까지 통과했다. compile/assembly/기존프로젝트서명·패키지/버전/해시/비서명payload 검증을 통과했다. 최초Kotlin public/internal 오류는 새객체를internal로 제한했고, fixture의100초 산술오류/희소query 공백은 실제 경계에 맞춰 수정했다. assertion/gate는 완화하지 않았다. 초기FAIL로그와 PC초안을 외부에 보존했다.

mock/Robolectric는 실기기 긴 실행/연결/계측비용 검증이 아니다. 원모형·기본/RL/strict·experiment_ready=false·원자료/FAIL/종료계획·사용자STATUS14행·개인파일/다른worktree를 보존했다. 착수HEAD51505bff, 검증 대상은 미커밋 소스 SHA로 특정했다. 다음행동 하나는 최종2조건 block의 별도 실측승인 여부 결정이며 이번에는 실행하지 않았다.

## 2026-10-09 실행 승인 이후 연결 gate

사용자가 지정 주소의 연결과 최종2조건 실측을 승인했다. Check는 기존 SHA/미소비/코드·APK·모형 동일성으로 통과했지만 연결1회는 stdout `failed to connect`를 반환했고, 현재 목록 확인1회에는 온라인기기가 없었다. ADB client exit0은 연결성공 증거가 아니다.

**Run·claim·설치·세션·추론0, ADB2명령.** 계획은 미소비로 유지하고 stopped_no_resume/실측실패로 기록하지 않는다. 재연결/daemon재시작/설정변경/다른계획 실행은 하지 않았다. 현재 접속주소 또는 필요한 페어링 정보를 기다리며 이미 주어진 실측 승인은 유지한다. 기기 연결소실 원인·포트 변경·사용자 조작은 미확정이다. [작은 gate 요약](results/ap_tail_observation_prep_01/connection_gate_20261009.json).
