# 추가 실측 필요성 및 무부하 대조 최소 설계

## 계획03 실행 완료 — 2026-10-01

사용자 “진행하자” 승인으로 아래 plan_v3를1회 실행했다. **소비·completed_descriptive_only**, C/L 두 세션 정상 완료·회수. [실제 결과·고정창·예산](RESIDENT_CONTROL_RUN03_20261001.md). 40추론/1543명령/679.531초, APK push/설치0, 재시도0. **아래 미승인/미소비/Run 명령은 준비 당시 이력이며 현재 재실행 대상이 아니다.**

## 새 실행 계획03 준비 완료 — 2026-10-01

사용자의 “계획 ㄱㄱ”에 따라 공간 검사 수정본을 새 계획에 고정했다. **이번 범위는 PC 준비이며 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`, 미승인·미소비다.** Run/기기 명령/실행 출력/consumption claim은0이다. plan_v1/v2는 stopped_no_resume로 보존하고 재실행하지 않는다. 아래 plan_v1 준비 설명은 과거 이력이다.

### 목적·역할·중단 기준

같은4resident·8warmup 준비를 거친 **C무부하0요청 → L등록 CG_DC24요청**을 한 쌍으로 관측해, 부하가 없어도 생기는 W/AP 시간 변화와 부하 후 변화를 기술적으로 대조한다. 기존 burst·seed201·B2 기록 입력의 도착 및 release+35초, 실제 lane 경계, baseline30/common120/cooling60초를 유지한다. PC 간섭계수나 lane 점유를 실제 기기에 강제하지 않는다. 기존 완료 C와 새 L을 합쳐 한 대조쌍으로 만들지 않는다.

고정 분석창은 공통0–120초, 부하 전5–30초, 후기90–120초, 냉각후기150–180초다. 해당창에 부하가 남거나 센서 bracket/간격 조건을 충족하지 못하면 null로 남기고 창을 바꾸지 않는다. power 최대공백2.5초/AP10초, L lane은90초 이전 해제 조건을 유지한다. 전체120초 관측J/원래 동결식 진단, 두 arm의 전후 W/AP 변화 및 변화 차이, 실제 lane·호출 분모를 산출한다. 조건당1세션·고정순서의 구조 판별용 개발 자료이며 독립 확인/인과 귀속/정확도 PASS/정책 순위 판정은 아니다. 새 후보 적합·재보정은 자동 수행하지 않는다.

첫 연결·환경·품질·메모리·sampler·시간·회수 실패 시 쌍을 중단하며 다음 세션/재시도/대체/추가를 시작하지 않는다. 기존50초 회수·45초 cleanup 예약과 최종100명령 reserve를 유지한다. 앱 cleanup/host force-stop/프로세스 부재를 구분하고, 확인 불가능한 종료는 미확인으로 남긴다.

### 정확한 상한

| 항목 | 계획03 상한 |
|---|---:|
| 세션 | C1＋L1＝2 |
| runtime 생성 | 8 |
| warmup | 16 |
| 본 요청 | C0＋L24＝24 |
| 별도 적격성 추론 | 0; 기존 warmup 출력 품질 검사 |
| 총 명시적 추론 | 40 |
| staging | 2회·14파일 |
| 설치본 host pull | 최대1 |
| 후보 APK push·설치 | 각각 최대1; 동일 설치본 검증 시 생략 |
| 고정 관측 | 세션당210초, 합계420초 |
| 세션 사이 대기 | 90초 |
| preflight/설치 예약 | 600초 |
| 세션 예약 | 700초＝stage120＋poll485＋회수50＋cleanup45 |
| 전체 예약 | 600＋700×2＋90＝**2,090초(34분50초)** |
| ADB | **최대6,600명령**, 최종 정리100명령 예약 |
| 재시도·대체·추가 | 0 |

2,090초는 정상 예상시간이나 완주 보장이 아니다. poll485 안의 baseline·공통창·냉각 및 개별 timeout은 다시 더하지 않는다. screen10초/timeout2초, thermal2초, listing0.25초/timeout3초, 앱1초 sampler, start AP 대기30초, APK push120초를 기존 경로대로 유지한다.

### 동일성·현재 환경 확인 경계

- ID `ENERGY-AP-RESIDENT-CONTROL-03`
- 계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_plan_v3/collection_plan.json`
- 계획 SHA-256 `2e9b3fcd6eaa02b6ce820cd34a4b660125b70cb4c35328e804303623ea7bf6d8`
- APK `C:/Users/LG/Documents/D1Check_Arrival_Extension/resident_control_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`
- APK SHA-256 `3d8ea871103c1350fb74e444c310be02ba8b3999cd6537691e75b457de4e94c2`; 재빌드·재서명 없음.
- package `com.example.d1check.benchmarkrunner.modelprobe`, versionCode1, 프로젝트 인증서 SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`.
- 소스95개·두 manifest·실행 스크립트·입력·분석 계약·APK/build receipt·원래 freeze를 고정했다. 원래 freeze `35ed6987…034c54`, 기존 AP 후보 `8507adc1…cbc7ec5` 불변.
- 출력 예정 `energy_ap_resident_control_run_v3`, registry 예정 `resident_control_registry/ENERGY-AP-RESIDENT-CONTROL-03`: **미생성**.

plan_v2 대비 실행 소스 차이는 새 edition을 허용한 계획 생성기와 claim 전 최소 host 공간 검사다. 두 manifest는 새 실행/세션/요청 ID를 제외하면 의미가 같다. 측정 부하·APK·환경 gate·관측 주기·timeout·분석 기준을 바꾸지 않았다. 공간 검사는 후보 APK 106,108,500바이트 이상의 여유를 claim/기기 명령 전에 요구한다. PC 검사 당시 free12,327,342,080바이트였으나 실제 실행 직전에 다시 확인한다. 이 검사는 설치본 크기 차이·전체 로그 저장량·실행 중 공간 감소의 보장이 아니다.

현재 기기 상태는 이번에 조회하지 않았다. 실행기는 현재 온라인 transport가 정확히 하나인지 확인하고 동일 A24 모델·하드웨어 식별·fingerprint, 설치본 해시·서명·패키지·버전, 배터리·비충전·BAT온도·thermal·화면·메모리·warmup 품질/GPU를 기존 계약대로 확인한다. numeric AP 유효성·신선도는 필수이고32.5–34.0°C는 모형 개발 범위 판정이며 새 실행 하한이 아니다. 화면·무선 디버깅·충전 등 설정을 자동 변경하거나 연결을 강제 복구하지 않는다. 대상 Activity 유지 조건을 따르며 앱을 떠나게 하는 명령을 추가하지 않는다.

### 재현·승인 후 실행 명령

```powershell
# PC Check, 이번에 실제 수행 완료; 기기 명령0
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check

# 이 새 계획의 실측 승인 후 한 번만 호출; 현재 transport는 실행기가 선택
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -ExpectedPlanSha256 '2e9b3fcd6eaa02b6ce820cd34a4b660125b70cb4c35328e804303623ea7bf6d8'

# 실행 종료 후 PC 고정창 판독
python -B -m tools.d1_resident_control_report --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_plan_v3/collection_plan.json' --output '<새 분석 출력 폴더>'
```

관련7테스트(새 edition2/3·소비 보존·공간 부족 실제 Run 진입·실패 후 두 번째 세션 차단·부분 회수/단일 cleanup·0요청 parser) 통과, 실패/skip0. 실제 PowerShell→Python Check와 device 생성 차단 guard를 둔 Python Check를 통과했다. 빌드 중간 파일 정리 후 APK/빌드 영수증/입력/두 freeze가 보존된 상태에서 확인했다. 소스/계획/manifest 비교와 [검증 JSON](results/resident_control_design_01/plan03/verification.json)에 대상 해시를 남겼다. PC 검증은 기기 연결/온도/장시간 안정성 검증이 아니다. 이전 화면 조회 timeout의 내부 원인은 미확정이며 이번 변경으로 해결됐다고 주장하지 않는다.

**계획 준비 완료. 다음은 새 계획03의 예산 내 실측 실행 여부 결정이다.** 이번에 Run/추론/설치/실측은 하지 않았으며 strict/default/experiment_ready=false를 유지한다.

> 현재 상태: 사용자 승인으로 plan_v1을1회 실행했고 C완료/L부분 중단으로 **소비·stopped_no_resume**다. [결과](RESIDENT_CONTROL_RUN01_20261001.md). 아래 Check/Run 명령은 준비 당시 이력이며 재실행하지 않는다.

> **최신: 구현·서명 APK·실행 계획 PC 준비 완료.** 아래 설계 당시 차단은 opt-in0요청/host0·24 판독으로 해소했다. 현재 상태는 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`이며 기기 작업은0이다. [최종 실행 준비](#실행-준비-완료-2026-10-01)의 해시·명령을 사용한다. 이전 design_plan.json은 수정하지 않은 당시 증거로 보존하며 현재 실행 계획이 아니다.

**동적 일정의 에너지 예측을 보완하려면 추가 대조 자료가 필요하다. 기존 고정 일정 재생·상충 설명을 계속하는 데에는 새 실측이 필요하지 않다.** 권고는 동일한 준비 후 무부하1＋짧은 CG_DC 부하1의 두 세션이다. 같은 B2 반복이나 미채택 후보의 확인 실험이 아니다.

착수 `aa9afffc5861915c1d3c8080f6520b158cc7680f`, clean·실제 원격 일치. 기기 작업 없음. [설계 JSON](results/resident_control_design_01/design_plan.json)과 [고정 부하 입력](results/resident_control_design_01/load_input.json)을 보존했다. 상태는 **DESIGN_CHECKED_EXECUTION_BLOCKED**다. 설계 산술 Check와 실행 가능 Check를 구분한다. 현재 APK로 실행 가능한 계획이라고 표시하지 않는다.

## 기존 자료로 끝낸 것과 필요한 한 질문

[후보 평가](RESIDENT_POWER_CANDIDATE_PC_20261001.md)의4세션·기존 원문 재현을 재사용한다. 부하 전 평균전력을 모든 이후 상태에 가산하는 후보는2개선/2악화였다. B2의 부하 전/후 유휴는1.071612/1.231219W, 유휴 확인은1.310722/1.057693W로 변화 방향도 다르다. 원래 유휴1.225433W를 모든 조건에 적용하거나 첫 유휴를 미래 유휴로 전용할 근거가 없다. AP 후보의 기존 확인 결과는 별개로 보존한다.

네 짧은 세션은 모두 준비 뒤 본 부하가 있다. 기존 장구간 개발의 baseline/중간 idle/냉각도 존재하지만 준비120초·baseline120초·250ms 반복부하·600초 창 등 프로토콜과 이력이 다르다([기존 계약](ENERGY_AP_STATE_COLLECTION_PREP_20260927.md)). 이들을 동일 준비 후 **본 부하 없는 전체120초** 대조로 취급할 수 없다. 기존 관측은 버리지 않고 시간 규모·센서·추정 한계 근거로 재사용한다.

새 질문은 “같은 준비 후 본 부하 없이도 유휴 W/AP가 변하는가, 등록 부하가 있는 세션의 전후 변화는 얼마나 다른가?”다. 정책의 대기 비용을 일정 W로 전용할 수 있는지에 영향을 준다. 네트워크·주변·전압·열 이력 중 원인을 이 두 세션으로 확정하거나 평형/시정수/병행 전력을 동시에 식별하지 않는다.

## 입력과 판독 고정

|항목|C: 무부하 대조|L: 등록 부하|
|---|---|---|
|순서/자료 역할|첫 번째, 구조 판별용 개발|두 번째, 구조 판별용 개발|
|준비|같은4 runtime·각2 warmup, 품질 확인|동일|
|resident|분류CPU/GPU＋탐지CPU/GPU|동일|
|고정 관측|baseline30＋공통120＋냉각60초|동일|
|본 작업|0건, 정상적으로120초 대기|기존 burst/seed201/B2 24건, release만+35초|
|배정|없음|분류GPU·탐지CPU, 원래 도착0–4.840초 유지|
|변경 금지|준비 생략·강제 종료로 대조 대체 금지|실제 시간을 PC에 맞추는 sleep/감속/추가 호출 금지|

순서는 실행 전 C→L로 정하며 결과에 따라 바꾸지 않는다. 같은 날/장소/기기/화면/프로토콜을 사용하되 숨은 열 상태가 같다고 가정하지 않는다. 세션 간90초 예약 대기는 온도 평형 보장이 아니다. 배터리·BAT/AP·세션 순서·이전 준비/부하·조회 시간과 명령 수를 함께 보존한다. 주변 온도를 측정하지 못하면 미측정이다. 최초 회수/cleanup 실패면 다음 세션을 시작하지 않는다.

공통창 시작을0초로 하여 **5–30초 전 유휴,90–120초 후 유휴,150–180초 냉각 말기**를 양쪽 동일한 시간창으로 고정한다. 각 창 평균 W·AP 시작/끝/변화·관측 경로, `후−전`과 두 세션의 변화 차이를 기술한다. L의 lane가90초까지 해제되지 않으면 후 유휴 비교는 부적격/null이며 창을 뒤로 옮기지 않는다. 전 유휴에 active가 있거나 C에서 요청 시작이 발견돼도 해당 대조는 부적격이다.

전류/전압 약1초 표본이면25/30초 창에 약25/30개, AP 관측 약2.5–3.5초이면 약7–12개다. 실제 count/span/gap을 보고하며 내부 센서 갱신 주기·독립 반복 수가 아니다. power gap≤2.5초·AP gap≤10초의 기존 자료 적격성 규칙을 유지하고, 구간 끝을 bracket하는 유효 표본이 없으면 계산하지 않는다. 보간은 유효 bracket 안에서만, 0 채움/구간 대체/평형 단정 없음. clock은 Android monotonic과 기존 host bracket을 이용하며 host wallclock을 직접 빼지 않는다.

전체120초 관측 J와 원래 동결식의 조건부 진단도 별도로 보존한다. AP의 원래식/기존 고정 후보는 적용 가능한 정보 시점 이후만 기술하며 부하 후 재적합하지 않는다. C에는 첫 dispatch가 없으므로 기존 후보의 dispatch 기반 진입점을 임의 생성하지 않고 후보 출력은 null이다. 시작 AP의 개발범위와 짧은 전환의 지원 여부는 각각 표시한다. 이번 쌍은 **새 모형의 독립 확인이 아니다**.

## 완료 기준과 결과별 종료

- 자료 적격성: 두 정상 완료·C 본 작업0/L 예정24 전체분모·resident/경계/센서/환경 기록·cleanup/회수 확인. 일부 실패는 부분 자료로 남기고 재실행하지 않는다.
- 과학적 산출: C의 시간 변화, L의 시간 변화, 동일 고정창의 변화 차이와 초기조건/관측 부하 차이. 고정순서·조건당1세션이므로 인과성·분산·통계적 유의성은 미판정이다.
- C도 변하면 시간 변화 없는 유휴 가정을 지지하지 못한다. L만 변해도 부하 원인을 확정하지 않는다. 둘 다 안정적이어도 과거4세션 차이의 원인 해결이나 보편적 계수 확인이 아니다. 값은 그대로 공개하고 이 쌍에서 판독을 종료한다.
- 임의 정확도 PASS/효과 크기 기준 없음. 후보 재적합·새 확인 세션·추가 반복 자동 진행 없음. 결과에 근거한 별도 모형 구조 결정이 다음 판단이며 기존 strict/default/experiment_ready=false 유지.

## 제안 예산 — 구현 후 실행 계획에서 재확인 필요

|항목|두 세션 합계 상한|
|---|---:|
|본 작업 / warmup / 별도 적격성 추론|24 / 16 / 0 (품질은 warmup 출력 재사용)|
|총 명시적 추론 / runtime|40 / 8|
|staging / 입력 파일|2 / 14|
|설치본 host pull / APK push / 업데이트 설치|각각 최대1|
|고정 관측|420초(7분)|
|배포/preflight 예약|600초|
|세션 예약|각120 stage/gate＋485 poll＋50 회수＋45 cleanup＝700초|
|세션 간 예약|90초|
|전체 예약|**600＋2×700＋90＝2,090초(34분50초)**|
|ADB / 재시도·대체·추가|최대6,600 / 모두0|

warmup/setup150초·앱480초 watchdog·AP 승인 대기30초·drain30초는 poll/app 상한에 포함되며 별도 더하지 않는다. 고정210초/세션도700초 안에 포함된다. 설치/push 각120초는600초 안이다. 회수50/cleanup45초를 먼저 예약하며 잔여 시간 또는 명령 reserve가 부족하면 새 단계 금지. 이는 **후보 예약 산술**이며 완주/배터리 보장·정상 예상시간이 아니다. 최신 같은 부하1세션 실제 실행293.138초는 참고 한 사례일 뿐 두 세션 예상시간으로 단순 배증하지 않는다.

조회는 기존 listing sleep≥0.25초, thermal/AP≥2초(3명령/회), 화면≥10초(1명령)를 유지한다. 485초의 보수적 회수 상한은 `(ceil(485/.25)+1) + 3×(ceil(485/2)+1) + (ceil(485/10)+1)＝2,723`/세션, 합계5,446이다. 나머지1,154명령을 preflight·설치·staging·gate·회수·cleanup에 배분하고 최종100명령 reserve를 보존하는 **제안 한도**다. 정상 횟수는 명령 지연/실행 길이에 따라 작아지며 전이 실측737회가 참고 사례다. 구현 시 전체 단일 counter와 단계별 실제 호출을 검증하기 전에는 이 제안 한도를 보장한다고 주장하지 않는다. 현재 조회를 줄이거나 추가 polling하지 않는다.

환경 gate는 기존 실행기의 A24/fingerprint·현재 transport·설치본/서명·비충전·배터리·BAT·thermal·화면·메모리·출력 품질을 유지한다. numeric AP 유효성/신선도는 필수이나32.5°C 개발 하한을 실행 기준으로 되살리지 않는다. 값/기준의 확정본은 새 실행 manifest와 현재 환경 확인이 필요하다. 설정 변경/자동 reconnect/다른 앱 종료/가열은 없다.

## 실행을 막는 정확한 구현 차이

1. `ArrivalEnergyActivity`가 `ArrivalEnergyContract.validate`를 호출하고 이 contract는 **정확히24건**을 요구한다. setup-only는 warmup0 조건이므로 warmup8 대조의 대체가 아니다. 기존 baseline 전 force-stop 역시 정상120초 대조가 아니다.
2. host `d1_arrival_energy_collection_device.validate/run`도24건·lane24·`24×완료세션`을 요구한다. opt-in C0/L24 분모·기존 실제 공통창/정상 cleanup·오류/timeout·명령예산 경계의 연결 검증이 필요하다.
3. 이 변경 후 **두 arm에 같은 프로젝트 서명 APK**를 써야 한다. 기존 설치 APK 해시를 후보로 복사할 수 없다. 새 source/APK/manifest 묶음이 없으므로 현재 candidate APK hash·Run 명령은 null이다.

현재 작업은 필요성 판정과 계획 설계다. Android/host 수집 코드를 임의 완화하거나 형식적 실행기를 만들지 않았다. 실행 계획으로 끝났다고 과장하지 않으며, 필요한 다음 구현은 위0요청 opt-in과0/24 집계 한 경계뿐이다. 이전 APK 자료는 프로토콜 이력 비교에 사용하고 새 쌍과 동일 block으로 합치지 않는다.

위 문단까지의 실행 차단/미구현 설명은 설계 당시 이력이다. 아래 후속 구현이 완료됐다.

## PC 검증 및 보존

`python -B -m tools.d1_resident_control_design check`는 고정 입력/근거 소스 SHA·예산·분모·차단 상태를 읽기 전용 검사한다. **실행용 Check가 아니며 Run 기능이 없다.** 관련5테스트는 실제 PC CLI, run 인자 거절, 예산/분모 변조, 실행준비 승격, 근거 drift 차단을 검사한다. 처음 산식 검증에서 floor/ceil 표기 불일치를 발견해 보수적인 ceil+초기조회 방식으로 정정했다. 실제 소요/명령 수 측정이나 기기 검증은 아니다.

계획·부하 입력·검증 기록은 [공유 폴더](results/resident_control_design_01/README.md)에 있다. 이번 실행 출력·소비 claim·ADB·APK 빌드·설치·추론0. 기존 동결본·후보·원자료·종료 계획은 그대로다. 다음 행동 하나: **기존 수집기에 0요청 대조 opt-in과0/24 host 판독을 연결해 동일 새 APK의 두 세션 실행 묶음을 완성한다.** 추가 포괄 감사나 동일 B2 재측정부터 시작하지 않는다.

## 실행 준비 완료 — 2026-10-01

사용자의 “구현 검증하고 계획 완성”에 따라 `9376003` clean에서 시작했다. `resident-control-pair-v1`을 명시한 manifest만 C0/L24를 허용한다. 기존 모드는 계속 정확히24건이다. Activity의 기존4runtime/8warmup·품질 승인·resident baseline30초·numeric AP observe-v2·공통120초·냉각60초·정상 cleanup 경로를 사용한다. 0요청이어도 공통창을 생략하지 않는다. lifecycle 취소/worker/sampler/관측 주기는 변경하지 않았다.

host는 같은 단일소비 실행기를 사용하며 두 manifest의 분모를 각각0/24로 검증하고 실제 완료 합계를 기록한다. C에서 dispatch/요청/lane 해제가 발견되면 실패다. 공통창4resident snapshot·에너지/AP 자료 적격성은 C에도 적용한다. 첫 세션 실패 시 두 번째 미시도, 원래 오류/부분 회수/cleanup 결과 보존·중복 cleanup 방지는 기존 경로다. 신규 runner가 최초 `devices -l`부터 선택·기기 식별을 수행하므로 외부 조회 없이 예산에 포함한다. **온라인 transport가 정확히 하나여야 하며** 복수/없음이면 실패한다. 다른 연결을 해제하지 않는다.

### 동결한 실행 묶음

- ID `ENERGY-AP-RESIDENT-CONTROL-01`
- 계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_plan_v1/collection_plan.json`
- 계획 SHA-256 `7c200ab73b0f3868d9dc6088cf66a626300fead4937f4d92d7f8374e2f58e135`
- APK `C:/Users/LG/Documents/D1Check_Arrival_Extension/resident_control_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`
- APK SHA-256 `3d8ea871103c1350fb74e444c310be02ba8b3999cd6537691e75b457de4e94c2`
- package `com.example.d1check.benchmarkrunner.modelprobe`, versionCode1, 프로젝트 서명 SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565` 확인. 이전 설치 APK와 다르므로 실행 시 동일성 확인 후 필요한 경우에만 데이터 보존 업데이트1회.
- source95파일·입력·분석 계약·두 manifest·build receipt·서명/원래 freeze를 Check에서 확인한다. 원래 freeze `35ed6987…034c54` 불변. 예전 AP 후보도 재적합하지 않았다.
- 출력 예정 `energy_ap_resident_control_run_v1`, registry 예정 `resident_control_registry/ENERGY-AP-RESIDENT-CONTROL-01`: **모두 미생성**, 미승인·미소비.

예산은 위 제안과 동일하게 확정했다: 세션2, C본0/L본24, warmup16, 별도 적격성 추론0(기존 warmup 출력 품질 확인), 명시적추론40, runtime8, staging2/14파일, 설치본pull/APKpush/설치 각≤1, 고정420초, 전체2,090초, ADB≤6,600, 재시도·대체·추가0. 설치/식별600＋세션700×2＋세션간90초이며 통신/설치/장시간 완주 보장은 아니다. 기존0.25/2/10초 polling과50초 회수/45초 정리 예약, 명령100개 최종 정리 reserve를 유지한다. 전체 counter가6,600에 도달하면 추가 client를 시작하지 않는다. 회수조차 불가능한 연결 소실이면 자료/종료 상태 미확인으로 남기고 자동 복구·새 실행을 하지 않는다.

```powershell
# PC Check: 이번에 실행 완료, 기기 명령0
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check

# 별도 실측 승인 후에만 사용. 현재 transport는 실행기가 선택한다.
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -ExpectedPlanSha256 '7c200ab73b0f3868d9dc6088cf66a626300fead4937f4d92d7f8374e2f58e135'

# 실행 종료 후 PC 고정창 판독, 새 출력 폴더만 허용
python -B -m tools.d1_resident_control_readout --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_plan_v1/collection_plan.json' --output '<새 분석 출력 폴더>'
```

판독기는 고정5–30/90–120/150–180초의 W/AP와 두 세션 전후 W 변화 차이·전체120초 관측J/원래식 진단을 산출한다. 센서 끝 bracket가 없거나 해당 유휴창에 부하가 남으면 null이며 창을 이동하지 않는다. 첫 dispatch가 없는 C에 기존 AP 후보 입력을 조작해 만들지 않는다. AP 후보/전체 모형의 독립 정확도 판정을 수행하는 실행이 아니다.

### 검증과 한계

- Python 변경 경계/기존 재생13건＋설계 이력 보존5건 통과. 실제 run 함수의 두 세션 합계·첫 timeout 후 다음 세션 차단·부분 회수·단일 cleanup·실제0건 parser/적분/결측 판독을 fake device와 임시 폴더로 확인했다. 설계 당시 해시는 새 구현과 달라 기존 설계 Check가 drift를 거절하는 것이 정상이며 실행 Check는 별도다.
- Android contract3＋실제 Robolectric lifecycle callback3＋기존 replay3＝9건, 실패/skip0. source/테스트 compile 및 격리 assembleModelProbe 성공. APK 서명·패키지·버전·source hash 확인. callback 테스트는 native inference를 실행하지 않는다. 새0요청210초 경로 전체의 실기기 정상 완료·센서·환경 안정성은 미검증이다.
- 실제 PowerShell→Python Check 성공, 기기 명령0. Run은 호출하지 않았다. APK/키/모델/원자료는 commit하지 않는다. 새 모드의 코드 분기 비용은 실측하지 않았으므로 같은 APK의 두 arm끼리 비교하며 기존 APK 실측과 프로토콜 차이를 표시한다.
- 독립 확인·후보 재보정·정책 순위는 추가하지 않았다. 기본 simulator·strict·experiment_ready=false 유지.

**현재 다음 행동 하나:** 위 단일 계획의 실측 예산 승인 여부를 결정한다. 승인되면 현재 기기/설치본/환경 gate를 실행기 안에서 확인하고 C→L을 한 번 수행한다.
