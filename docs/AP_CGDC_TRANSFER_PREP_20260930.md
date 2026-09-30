# CG_DC의 다른 기록 일정 전이 확인 — 실측 전 준비 완료

착수 HEAD `06bce390ed3923f88b084eead1258a94c59a9261`, clean worktree. 사용자의 “일단 실측전까지”에 따라 **PC 준비만** 수행했다. 기존 저온 후보·동결 모형·종료 계획·원자료는 그대로다. 상태는 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`; 기기/Run/claim0, `experiment_ready=false`.

## 이번 한 세션의 목적과 종료점

[이미 완료한 AP 판독과 지원 경계](AP_SIMULATION_CLOSURE_PC_20260930.md#6-저온-ap-출력의-pc-연결-2026-09-30)를 재사용한다. 기존 유휴2세션 확인 MAE0.417521°C는 유휴 중 상승→하강 형태나 다른 일정의 정확도를 보장하지 않는다. 원래 W도 유휴2세션에서 +20.090/+11.305J 잔차가 있다. 새 모형을 만들거나 그 결과를 다시 맞추지 않는다.

**권고안 하나:** 저장 `burst/seed201/B2_PC/예측·실현 간섭1.5`를 다른 실행의 전이 확인으로 재생한다. 이미 저장된 연구용 서비스 guard에서 이 사례의 B2가 적격임을 확인했고, J/AP가 잘 맞는 입력을 검색하지 않았다. queue 자료와 다른 도착·실행 간격이며 두 모델/입력/네 resident/배정은 유지한다. [공유 일정](results/energy_ap_cgdc_transfer_01/schedule.json)과 [판독 계약](results/energy_ap_cgdc_transfer_01/analysis_contract.json)을 실행 전에 고정했다.

| 확인할 질문 | 입력/관측 | 판독과 종료 기준 |
|---|---|---|
| 기존 후보가 다른 짧은 부하 뒤 AP 반응을 설명하는가 | 기존 β·상태별 기울기 차이 고정. 부하 전 AP만으로 세션의 유효 유휴 기준을 계산 | 부하 후 관측과 고정 식의 MAE/최대오차·부호 잔차·유휴 방향·진단 최고값 차이를 산출. 결과가 나빠도 재맞춤/추가 실행 없음 |
| 작은 전체 J 차이에 상쇄가 있었던 문제가 다른 일정에도 나타나는가 | 전류/전압 전체120초와 실제 dispatch→lane 해제 | 원래 W의 전체창·누적·부하 전/부하/부하 후 잔차. 부분 J를 전체로 승격하거나 상쇄를 인과 증명으로 사용하지 않음 |
| 실제 CG_DC 병행·이탈이 어떤 형태인가 | 24예정 요청 전부의 시작/반환/output/persist/worker/lane | 실제 단독/병행/유휴 점유. 병행을 유지시키기 위한 지연·추가 요청 없음. 짧은 병행 W를 별도 식별했다고 하지 않음 |

개발0·새 확인1이다. 원래 개발3 모형 SHA `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`, 기존 후보 절차 freeze SHA `8507adc10485940c36853786ba39a4f42439a9fbd3d71a5da1c7d55e2cbc7ec5`를 그대로 참조한다. service guard는 원본 일정의 선정 근거이지35초 대기 입력의 서비스 적격성 판정이 아니다. 후보의 새 전역 적합계수0, 부하 후 AP/current는 예측 입력0이다. 이미 본 기존 확인 자료를 새로운 독립 표본으로 세지 않는다. 새 관측은 고정 절차의 별도 전이 확인이 될 수 있으나 독립 변동성 추정은 아니다.

실측 완료의 의미는 **유효한 한 세션의 고정 절차 오차 산출**, 또는 실패/부적격의 명확한 종료 기록이다. 정확도 허용폭·정책 선택 충분성은 근거가 없으므로 `null`. 이 세션으로 시뮬레이션 전체 완료, 온라인 B2, 열 제약 충족, DC_DG 짧은 전환, 정책 J/AP 순위가 검증됐다고 하지 않는다. 결과를 본 뒤 추가 모형·확인 세션을 자동 만들지 않는다.

## 시간·초기조건·정보 경계

도착은 APK가 요구하는 원래 burst 격자 **0–4.840초**를 유지하고 PC 실행 허용 시각만 **+35초** 옮긴다. 이전 요청 완료에 따라 도착을 늦추지 않는다. 첫 release35.000300초다. deliberate 대기로 원래 서비스/기한 의미가 바뀌므로 B2 응답 성능 확인은 하지 않는다. 30초 baseline＋공통창 첫35초 유휴로 약65초의 부하 전 관측을 확보한다. 부하 전 표본≥15·span≥55초·gap≤10초, 조회 bracket 전체가 실제 baseline 시작 이후/첫 dispatch 이전이어야 한다. 표본 확보 실패는 기준 완화 없이 후보 계산 불가다.

원본 PC 간섭1.5는 일정 생성 조건이다. APK에 감속·추가 sleep·온도 맞추기용 추론을 넣지 않는다. 저장 일정상 CG_DC는2.486460초, 전체 유휴108.113002초, 마지막 lane은46.891498초다. **계획 단계의 PC 점유**이며 실기기 병행/완료를 보장하지 않는다. 이런 짧은 부하의 AP 몇 표본으로 병행 전력 계수를 정밀 식별하지 않는다.

공통120초에는 실행 허용 전35초 유휴가 포함되므로, 실행 허용 시각을 지연하지 않았던 과거 queue120초와 총량을 직접 비교해 정책 자원 우열로 해석하지 않는다. 후보 AP 평가는 첫 실제 dispatch부터 실제 cooling 종료까지다. 정보 시점 이전 후보 곡선은 내지 않는다. 분석은 회수 후 수행하는 **부하 전 관측＋실제 일정 조건부 재구성**이며 세션 시작 전에 일정/온도를 독립 예측한 것이 아니다. 과거 APK/센서/AP 표본/host 조회 주기는 같지만 도착 패턴·실행 허용 시각·열 이력이 바뀌므로 프로토콜 전이로 보고한다.

기존 `numeric-ap-observe-v2`를 사용한다. 올바른 HAL AP의 유효성·조회 신선도/앱 시작 승인≤3초를 유지하되32.5–34.0°C는 모형 개발 시작 범위 표시이며 실행 안전 하한이 아니다. 범위 안이어도 짧은 상태 전환은 strict 지원 밖이다. 범위 밖 기존식 계산은 외삽, 후보는 새 초기조건 전이 진단이다. 유효 유휴 기준을 주변온도나 숨은 내부 열 상태로 부르지 않는다. 미래 AP나 측정 전력을 피드백하지 않는다.

## 구현·실행 전 gate와 예산

`tools/d1_ap_transfer_confirmation.py`는 저장 CSV의 일정/점유 일치, 고정 입력/모형/APK/코드 identity, 새 manifest/Check와 사후 readout을 연결한다. 기존 single-use arrival 실행기에는 **Check 선택 분기4행만** 추가했다. 초기화→warmup/품질 승인→baseline→시작 AP 승인→부하→냉각→앱 정상 종료/회수/host cleanup을 그대로 사용한다. 기존 후보 파일·Android·취소·sampler·strict·기본 simulator는 변경하지 않는다. Run/registry가 존재하면 재실행을 차단한다.

| 항목 | 제안 상한 |
|---|---:|
| 세션 / 본 작업 / warmup / 추가 적격성 / 총 명시적 추론 | **1 / 24 / 8 / 0 / 32**. 품질 확인은 warmup 결과를 재사용 |
| runtime / 입력 staging | **4 / 1회·7파일**(모델/입력6＋manifest1) |
| 설치본 host pull / APK push / 데이터 보존 설치 | **각≤1**. 정확히 같은 설치본이면 APK push·설치0 |
| 고정 관측 | baseline30＋공통120＋cooling60＝**210초**. 공통창 안35초를 중복 가산하지 않음 |
| 설치본/preflight·배포 예약 | **600초**, pull180·push120·설치120·원격 SHA5·설치본 SHA10 등의 timeout은 여기에 중첩 |
| 세션 예약 | stage/gate120＋poll485＋회수50＋cleanup45＝**700초** |
| 전체 | **1,300초(21분40초)**. 정상 예상시간/배터리 완주 보장 아님 |
| ADB / 종료 명령 예약 | **≤3,200 / 마지막100명령**. 예약에 도달하면 새 관찰 중단 |
| 재시도·대체·추가 세션 | **0 / 0 / 0** |

ADB 계산은 기존 주기를 유지한다. poll 상한485초에 listing `floor(485/.25)+1=1,941`, HAL AP(type0)는 uptime전/thermal/uptime후 3명령×`(floor(485/2)+1)=729`, 화면(power 필터)은 `floor(485/10)+1=49`, 합계**2,719**다. 이는 각 client 시간0을 가정한 보수적 최대이며 정상 예상 명령 수가 아니다. 조건부 preflight/배포≤28, session gate＋설치본 hash16, staging33, launch1, warmup/start AP 승인10, 회수4＋cleanup3, 실패 prefix7로 **추가≤102**, 전체 산술상≤2,821이다. cap3,200과 마지막100 예약보다 작다. 실제 명령 시간·조회 지연에 따라 관찰 횟수는 감소하며 정상 count는 실행 전 정확히 예측할 수 없다. server smart-socket 사전 확인은 기존 client 경로의 host 통신이며 ADB 명령과 별도다. 새 polling/재접속/heartbeat 명령을 추가하지 않는다.

환경 gate는 원 계약의 현재 동일A24·hardware/fingerprint·설치본 package/version/hash/signer, 배터리≥20%·비충전·BAT≤35°C·thermal0·화면Awake/interactive·밝기81/자동밝기0/꺼짐18,000,000ms·host/app memory·GPU delegate/출력 품질이다. 현재 기기를 읽지 않았으므로 전부 **실행 직전 미검증**이다. 기존 selector는 온라인 target가 하나여야 한다. 여러 transport가 보이면 자동 해제/전환하지 않고 시작을 막는다. 승인 후 현재 transport를 지정하며 다른 기기/앱/설정/daemon은 변경하지 않는다.

예외·관측 timeout(기존 listing3초)·환경 부적격·sampler/품질/메모리·잔여시간 부족이면 기존 회수와 단일 host cleanup으로 종료한다. 활동 중 앱의 lifecycle 취소는 유지하며 Activity를 떠나는 명령을 넣지 않는다. 앱 자체 cleanup과 host force-stop·프로세스 부재는 별도 사실이다. host 전원 상실/native hang/연결 상실에도 종료·회수를 보장하지 않는다. 외부에서 새 앱 실행/중복 회수를 하지 않는다. 전체1300초는 준비된 실행기의 명령/종료 예약이며 GUI나 상위 도구 강제 종료까지 벽시계 보장이 아니다.

## 계획·명령·검증

외부 계획 [collection_plan.json](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_cgdc_transfer_plan_v2/collection_plan.json>) SHA **`e18268538174f49e98789dcf191318dbf5b57cdbc2a7f2cb1b4aaa4c449f3234`**. 새 ID `ENERGY-AP-CGDC-TRANSFER-02`, 출력 `energy_ap_cgdc_transfer_run_v2`, registry `ap_transfer_registry/ENERGY-AP-CGDC-TRANSFER-02`는 **아직 생성하지 않았다**. 이번 PC 작업의 v1 초안은 도착+35초가 Android contract에서 거절되는 것을 발견해 **미소비·실행불가 초안으로 보존**했고, v2가 유일한 권고안이다. 앱이 요구하는 원래 도착·작업/우선순위·기한 계약을 보존해 최소 수정했다. 기기 실행 실패나 stopped_no_resume로 기록하지 않는다. 소비된 v6와 최근 inrange 계획은 그대로이며 queue24 미소비 계획을 실행 대상으로 바꾸지 않는다.

재사용 APK SHA **`747ce77e07c7c79f7c7d912d0ff749cf230e0c0483f4a160784fe549043f6180`**, `arrival_b2_ap_observe_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`. 프로젝트 인증서 SHA `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`, package `com.example.d1check.benchmarkrunner.modelprobe`, versionCode1. 로컬 signer 검증·Android source 대응 PASS, 빌드/전송/설치0. 이 APK의 기록 재생은 C_GPU/D_CPU만 허용한다. DC_DG/B3까지 지원한다고 표현하지 않는다.

```powershell
# 이번에 실행한 실제 진입 Check: 기기 명령0
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_cgdc_transfer_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Check
# 별도 실측 승인 후에만 (지금 미호출):
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_cgdc_transfer_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 유일한 동일 A24 transport>' -ExpectedPlanSha256 'e18268538174f49e98789dcf191318dbf5b57cdbc2a7f2cb1b4aaa4c449f3234'
# 적격 종료 자료를 회수한 뒤에만:
& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B -m tools.d1_ap_transfer_confirmation readout --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_cgdc_transfer_plan_v2/collection_plan.json' --output '<새 PC 분석 폴더>'
```

[검증 요약·공유 입력](results/energy_ap_cgdc_transfer_01/README.md): Python 신규6＋변경 경계의 기존3검사＝**9건 PASS**, 실제 Android ArrivalEnergyContract.validate→ArrivalRecordedReplay.validate/choose JVM 검사 **1건 PASS**. 실제 runner 진입에서 새 Check 선택·한 session/단일 회수/cleanup·개발 재동결과 조기 종료의 부재, 소비 계획 재실행 거절, bracket/표본/cutoff/unsupported 차단, 전체120초 적분과 구간합 보존, 부하 후 AP 변경 시 예측 불변을 검사했다. 초안의 도착 이동 결함을 발견한 뒤 JVM 검사에서 원래 burst 도착＋지연 release는 통과하고, 도착+35초는 거절됨을 실행 확인했다. Activity 전체 callback/기기 동작 검사가 아니라 실제 순수 contract/선택 함수 경계다. Android 본문 compile은 UP-TO-DATE, 테스트 소스만 추가했다. PowerShell→Python→실제Check도 PASS. fake/축약 PC 검사이며 실기기/장시간/연결 안정성 증명이 아니다. 전체 배치·과거 분석·APK 빌드를 반복하지 않았다.

**다음 행동 하나:** 이 한 세션의 별도 실측 예산 승인 여부를 결정한다. 이번 요청에서는 준비까지만 완료했으므로 ADB·Run·설치·추론은 시작하지 않는다. 후보가 맞더라도 DC_DG/최고온도 제약/정책 순위의 공백은 남고, 맞지 않으면 그 한정 진단 결과로 종료한다.

## 실측 후 PC 판독과 그림 자동화 (2026-09-30)

착수 HEAD `db039458b4962524d9e55381c2f8dad0e026a905`, clean worktree 및 실제 원격 HEAD 일치에서 이어갔다. 실행 전 계약·계획·APK·Android·고정 readout 소스는 바꾸지 않고 `tools/d1_ap_transfer_report.py`를 별도 PC 어댑터로 추가했다. 관련 테스트7건은 **이번 미커밋 두 Python 파일**을 대상으로 실행했다. [소스 SHA·검증 요약](results/energy_ap_cgdc_transfer_01/report_automation_verification.json).

적격 원자료가 생긴 뒤 저장소 루트에서 아래 명령 한 번으로 판독과 대시보드를 만든다. 명령에 ADB/실행 API가 없으며 기기 작업을 시작하지 않는다. output은 기존 실행/계획/registry와 분리된 **새 PC 경로**여야 한다.

```powershell
& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B -m tools.d1_ap_transfer_report --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_cgdc_transfer_plan_v2/collection_plan.json' --output 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_cgdc_transfer_readout_v1'
```

정상 출력: `report.json`(점수·해시·진단 상태), `timing.csv`(24건 예정 도착/release·PC 경계·실제 dispatch/output/persist/worker/lane), `data/*.csv`, `lanes/energy/ap.png` 및 SVG, `index.html`, `inventory.json`(단일 실행의 원본 파일 크기·SHA). HTML은 상대 링크로 CSV·그림·분모를 연결한다. 공유할 때 raw inventory의 세션 경로와 오류 파일의 개인 절대경로는 별도 검토해야 한다. 원자료/키/APK는 이 HTML에 넣지 않는다.

자료가 부적격하거나 없으면 `not_evaluable`, 점수null·사유·error stack·inventory만 남고 비교 그림0개다. CLI는 종료코드2를 반환한다(현재 PowerShell 도구에서 native nonzero가1로 표시될 수 있음). 처리 코드의 예상 밖 오류는 `processing_error`; 그림 실패는 `rendering_failed`로 별도 기록하며 수치 판독과 혼동하지 않는다. 재실행·회수·cleanup·소비 claim을 하지 않고 기존 실패 receipt를 그대로 둔다. 기존 output을 덮어쓰지 않는다. 기록 없음은 호출0/앱 실패 확정이 아니다. data CSV 생성 뒤 후속 검사가 실패하면 data는 검토용 중간 산출물이며 최상위 report 상태가 우선한다.

경계 검증: CSV의120초 J·상태구간 적분·부하 전/부하/유휴 합계·AP residual/MAE/max가 요약과 일치해야 한다. 원래 forecast는0/120초를 이미 포함하므로 전체 J 요약 오류는 확인되지 않았다. 마지막 센서 midpoint가119.5초인 fixture에서는 유효한119.5–120.5초 표본 bracket으로 관측120초 적분이 가능했다. 누적 경로에120초 끝점을 추가하되 원래 `frozen_reader_energy_path.csv`와 `endpoint_completion.json`을 보존하고 요약 점수/창/계수는 바꾸지 않는다. 센서 gap을0으로 채우거나 유리한 시각으로 창을 이동하지 않는다. 누적 적분의0초 J=0은 초기 적분 조건이며 결측 센서 대체값이 아니다.

AP 그림/점수는 첫dispatch 이후~실제 냉각 끝, J는 정확한 공통120초다. preload AP는 후보의 유효 유휴 기준 입력이며 주변온도 실측값이 아니다. 초기 AP 범위 안/밖, 짧은 전환 strict 미지원, raw=mA 조건부/절대 정확도 미인증을 표시한다. 후보·원래식 차이는 진단이며 accuracy_pass/정책순위=null, 최고/한도/정책 비용 지원은 승격하지 않는다.

검증 명령:

```powershell
& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B -m unittest tools.test_d1_ap_transfer_report -v
```

7건 PASS: 실제 CLI→고정readout→CSV/SVG/PNG/HTML·원본 불변, 실패receipt/중복output 차단, 전류gap/AP누락 null, 시간/분모/backend/CSV 점수 불일치 차단, 보호 경로·예상 밖 코드 오류, 렌더링 오류 별도 receipt, 불규칙 창 끝120초 적분 보존. 실제 ADB 클래스는 AssertionError로 격리했다. 그림 미리보기는 외부 `ap_transfer_report_pc_v1/fixture/preview`에 **PC TEST FIXTURE - NOT MEASURED**로만 보존했고 AP/lane PNG를 육안 확인했다. 미래 실측 그림을 공유 대시보드에 게시하지 않았다. 전체 과거 테스트/Android 빌드/배치는 반복하지 않았다.

현재 미실행 실제계획으로 CLI를 검증한 결과 `FINAL_RECEIPT.json` 부재로 예상한 not_evaluable·null·그림0이었다. 이는 실행 실패가 아니며 **실제 run output/registry는 여전히 없음**이다. 별도 PC 결과는 `ap_transfer_report_pc_v1/unexecuted_plan_readout`에 보존했다. 실제 PowerShell Check PASS, 계획 SHA `e18268538174f49e98789dcf191318dbf5b57cdbc2a7f2cb1b4aaa4c449f3234`, 개발3 freeze/후보 freeze 그대로. 기기 명령·Run·설치·추론·APK 빌드0. 이 자동화는 실측 후 수작업을 줄였으며 아직 새 전이 정확도를 확인한 것은 아니다.
