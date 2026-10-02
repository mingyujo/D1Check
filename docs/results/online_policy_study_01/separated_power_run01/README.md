# 분리 부하 연구 Run01: 개발1 완료·두 번째 준비 중 중단

2026-10-03 KST. 실행 기준 HEAD d6a40c0, 계획 SHA0340473b29e03b8c5bf38d05ffcb4f3e5ed7aa7eec222b403650c34f4a6eac7f. 공간 확보 후4.14GB를 확인하고 Check/Run 각1회 수행했다. 계획/실행 소스/timeout/환경/분석 계약을 바꾸지 않았다.

## 결과와 소비

개발 CPU_URGENT 1개 적격 완료, B2_PARALLEL 준비 중 중단, B2_SERIAL 미시도. 계수 동결0·확인0/6. 원 계획은 stopped_no_resume이며 재개하지 않는다. 성공1개는 독립 확인이 아니라 개발 자료로 보존한다.

|항목|실제|원 상한|
|---|---:|---:|
|세션 시도/완료|2/1|9|
|runtime 시작/반환|8/8|36|
|warmup 시작/반환|16/16|72|
|본 요청 시작/반환/output/persist/worker/lane 기록|각96|864|
|명시적 추론 확인|112|936|
|staging/파일|2/14|9/63|
|설치본 pull/APK push/설치|1/1/1|2/1/1|
|ADB|877|29200|
|root 전체 시간|428.988초|8310초|
|재시도/대체/추가|0|0|

두 번째의 마지막 회수 기록은 warmup_gate이며 본 시작 기록0, host warmup 승인 전이다. 정상 terminal/cleanup이 없으므로 미기록을 완전한0회 증거로 쓰지 않는다. 보수적으로 두 번째 본 요청 미확인 범위0–96(발생 주장 아님), 총 추론 확인112/보수적 상한208로 구분한다. 나머지 개발1·확인6은 launch하지 않았다.

## 중단과 종료 증거

host 명령0866 `shell run-as <대상패키지> ls <동일세션>`가3초 제한에서3.004107초/exit1로 종료됐다. stdout/stderr0B, 해당 client PID만 종료·reaped; 공유ADB daemon을 건드리지 않았다. 직전0865 동일조회0.276079초 성공, 직후0867 manifest회수0.237416초 성공. 지속적 연결 소실·무선원인·GPU실패·앱정지를 입증하지 않는다. 원래 stack/단계·후속 파일별 recovery_error 모두 원본에 있다.

첫 앱 cleanup completed. 두 번째 앱 cleanup 미회수/미확인. host 세션 cleanup2회 및 설치 후 cleanup1회는 별도 기록. 마지막0874 force-stop 성공,0875 ps에서 대상패키지 부재,0876 thermal status0. 이후 기기조회0. host 실행 도구 exit1 및 당시 Python/PowerShell PID 부재를 확인했다. 앱 자체 정상 종료와 host 종료를 합치지 않는다.

## 확보한 첫 세션

공통[0,120]초 관측165.372829J(raw=mA 조건부·절대 정확도 미인증). 초기 AP32.6°C, post35~cooling AP53표본/최고34.1°C. 본96/96완료, persist 기준 마감54/96. 초기50초 전력1.204400W. 실제 마지막lane97.626601초. 공통120초 상태는 유휴82.224401초/분류CPU7.930381초/탐지CPU29.845218초/병행0이다. 전력모형4항은1세션으로 식별하지 않으며 새예측/오차/정책순위/정확도PASS를 만들지 않았다. 기존AP·전력동결본/strict/experiment_ready=false 보존.

[관측 그림](development_0.svg), [상태 CSV](occupancy.csv), [세션 CSV](sessions.csv), [명령 시각·지연](commands.csv), [검증](verification.json). 그림은 유효한 첫 세션 관측만이며 확인/예측 그림이 아니다.

## 원본과 재현

원본: `C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_run_v1/FINAL_RECEIPT.json` (SHA de75c48a46e112e3a6c975ea7b19b36c99ec39b7561e3eb32f59bdcff9abeb74). 전체 inventory는 외부 `separated_power_readout_v1/raw_inventory.json`. 키/APK/원본/기기식별값은 저장소에 포함하지 않는다.

```powershell
python -B -m tools.d1_separated_power_partial --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_plan_v1/development/collection_plan.json --output <새_PC_출력>
```

실행 소스는 변경하지 않았고 부분판독 모듈만 추가했다. 실제 원문에서120초상태합/적분종점/96lane해제/명령877개/동결·확인 미진입을 검증했다. 다음 PC 작업은 성공한 개발1을 해시로 보존하면서, 반복된 준비 listing timeout을 연구 진행 실패와 구분할 수 있는 관측/중단 경계를 검증하는 것이다. 같은 계획을 재실행하거나 timeout을 즉석 연장하지 않았다.
