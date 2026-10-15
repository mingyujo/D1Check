# 나머지 8군·독립 확인40 경로의 PC 사전 준비

2026-10-15. 사용자가 나머지 경로 연결을 실측 전에 준비할 수 있는지 요청했다. 기존 측정 소스·결과·실패를 보존하고 **별도 host adapter와 실행 불가 계획 초안**을 구현·검증했다. 기기 조회·설치·앱시작·워밍업·추론·실측·START/claim·세션소비는 이번 작업에서 모두0이다.

## 구현한 경로

| 범위 | 연결한 내용 | 현재 상태 |
| --- | --- | --- |
| L64 BASE/PAIR_G | 같은64건·FIFO·C_GPU/D_CPU,직렬/지원병행 | PC 경로·mock 검사 완료 |
| C252 CPU/GPU | 같은252건·FIFO·직렬,분류 자원만 변경 | 별도 suite경로 PC 검사 완료,기존묶음04는 보존 |
| M128 BASE/ORDER/PAIR_G/WAIT200 | 같은128건·순서/병행/200ms대기 처치 | PC 경로·mock 검사 완료 |
| 새 CONFIRM | 8군×5독립블록=40세션·5,720예정 요청 | 실행 불가 초안·앱 parser 검사 완료 |
| 초기 기준 | recipe×독립블록별15개 기준,첫준비후안정창봉인/같은묶음공유 | 순수 계산·mock 검사 완료 |
| 군간 대기 | MATCH_FIXED군은 앱밖냉각→공통준비→같은gate 재검사 | PC 경로·mock 검사 완료 |
| 확인 동결 | 정확계획/소스/APK·새시간창·예산·분석·예측또는명시적없음·원시도이력·새기능검증 증거의SHA 결합 | 누락/변경/미승인 시 실행전차단 |

`tools/d1_a24_revision02_suite.py`는 초안 생성과 향후 `run_registered_session` 호출 경로를 제공한다. `tools/d1_a24_revision02_suite_control.py`는 기존 C252 host의 수명주기를 별도 파일로 보존한 확장판이다. 원래 파일을 수정하거나 기존 source SHA를 새 의미로 바꾸지 않았다. 앱·모델·도착·기한·FIFO/EDD·지원병행·WAIT·응답/실제 lane반환·계수는 그대로다. 새 Kotlin 파일은 PC파서검사 전용이며 APK를 교체/재빌드하지 않았다.

새 host는 작업을 선점하거나 주파수/전력을 제어하지 않는다. 탐지GPU는 기존공통준비용일 뿐 요청후보가 아니다. NPU·학습·새모델·추가이미지는 없다.

## 이번에 검증한 것

- Python39 PASS: 새 suite18개와 기존REV02관련21개. 새18개에는 8군 전체mock실행·예정분모·저널close,40/5블록/15기준,DEV와CONFIRM의seed/ID분리,대기와기준소유자/SHA,새시간창·예산·동결·분석파일변경·다른기기자료/PC자료의기기증거대체 차단이 포함된다. 이미시도된ID는냉각조회전부터차단하고,정상회수후입증된자기빈프로세스만정리하도록연결했다.
- 실제 앱의 Kotlin parser1 PASS: 새40개manifest·160runtime binding·5,720요청·15개기준그룹을 강제재검사했다. 모든manifest가mock=true·execution_authorized=false·PC_ONLY_NOT_APPROVED임을 함께 검사했다.
- 기존171개측정소스/원161개·APK바이트·사용자원작업파일을 보존한다. [검산기록](VERIFICATION.json)의 현재175파일SHA가 이번PC검증대상이다.
- 새 비교군들은 기존기본 scheduler와 동일한 요청경계·원물검산·실제반환처리를 사용한다. mock의 임의시간·완료결과는 기기성능이나 새로운 시뮬레이션 결과가 아니다.

개발 중 mock fixture의 arm필드/검산반환필드 이름을 바로잡았고, 새 reference하위폴더가 없을 때 생성하도록 새host를 보완했다. 판정·기한·허용폭을 완화하지 않았다.

## 실행을 허용하지 않는 상태

공개 초안과 개인PC복사본은 **실행 불가**다. CLI는 초안을 쓰기만 하며 기기실행 옵션·ADB client 생성·허가 sidecar 발급 기능이 없다. suite control의CLI도PC상태만 출력한다. 함수 호출도 별도 실제 승인/정확파일/기한관리client 없이는 기기나원장을 만들기 전에 거절한다.

1. 새40은 원64예산 중 잔여31보다 **최소9슬롯이 더 필요**하다. 실제 기능검증/개발을 추가하면 그만큼 별도예산이 더 필요하다. 이번에 만든DEV8은 **소프트웨어호환검사용fixture**이며 기기8회실행안이나추가예산승인이 아니다.
2. 새개정경로의 실제 기능검증은 DEVICE_UNVERIFIED다. 기기검증자료는 모든8군·해당소스/APK·mock=false·실제NN기록을 요구한다. 이번PC결과를 그 증거로 넣으면차단한다. 이 요구를 채우기 위한 측정은 이번에 시작하지 않았다.
3. 최종 확인40의 시간창/예산/실행계획·분석·초기조건·예측 또는 명시적 부재는 아직 동결하지 않았다. 옛 확인2회를 새40에 합치지 않으며 실패를 삭제/대체하지 않는다. 실제시작 전에 미완료항목을 닫아야 한다.
4. 현재승인은PC준비뿐이다. 이전13:20시간창은종료됐고 재사용할수없다. 향후 실행에서는 충전분리·같은기기/화면·SOC10%이상·상태/부하를 다시 확인한다. 앞선단발AP값을새시작기준으로전용하지 않는다.

J계산불가·표면온도미검증·HAL cache age미확인·한승인이미지반복·experiment_ready=false를 유지한다. 같은기준허용폭통과가실제시작값/내부잔열까지같음을보장하지않으므로실제시작AP도별도보고한다. 앱밖냉각이력·경과시간을보존하며대기소비를0으로가정하지않는다.

## 준비된 파일과 재현

[확인40 초안](CONFIRM_PLAN_DRAFT.json) · [확인40 준비수치](CONFIRM_PREPARATION.json) · [DEV8 PCfixture계획](DEV_PC_FIXTURE_PLAN.json) · [미동결 초기조건](INITIAL_STATE_DRAFT.json) · [미동결 확인요건](CONFIRM_REQUIREMENTS.json) · [실제 소스175개SHA](SOURCE_SHA256.json)

개인 원물은 ignored `output/a24_revision02_suite_pc_20261015/`에 있다. 공개물에는 모델/APK/키/개인target·기기식별자·실행허가를 넣지 않는다.

```powershell
# PC 단위/mock 검사. 물리기기명령0.
python -B -m unittest discover -s tools -p 'test_d1_a24_revision02*.py' -q

# 항상 새폴더/새ID. 현재APK·기기에결합한PC전용템플릿이필요하다.
python -B tools/d1_a24_revision02_suite.py --output <새PC초안폴더> --templates <PC전용64템플릿폴더> --plan-id A24R02-SUITE-PC-NEW-CONFIRM --stage CONFIRM

# 생성한40개실행불가초안을실제앱parser로검사한다. 기기/네이티브모델은실행하지않는다.
$env:A24_SUITE_MANIFEST_DIR='<새PC초안폴더>\manifests'
.\gradlew.bat --offline --no-daemon --max-workers=2 -PenableA24Preparation=true -Pa24MeasurementIsolation=true :benchmark-runner:testA24PreparationUnitTest --rerun --tests 'com.example.d1check.benchmarkrunner.A24SuiteManifestPreflightTest'
```

향후 실행을 위한순서: 새범위·예산/시간창확정 → 새경로실제기능검증 → 원시도이력/분석/예측또는없음/초기조건/입력/소스 동결 → 새확인40실행허가결합 → 각군기준통과시작. 어느단계도 이번PC준비완료로 대체하지 않는다. 현재배치실행명령은 발급하지 않는다.

[실측 재개 안내](../MEASUREMENT_RUNBOOK.md) · [앞선 기기 읽기전용 점검](../readiness_20261015/README.md) · [최초 계획](../../a24-laptop-measurements-20261014/PLAN.md)
