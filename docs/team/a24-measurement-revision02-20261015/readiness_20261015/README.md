# A24 나머지 실측의 사전 오류 점검 — 본실측0

2026-10-15 사용자 지시: 시간이 부족하므로 실측은 시작하지 않고, 연결한 폰과 나머지 실측 설정에서 처음 연결 때 같은 오류가 생길 부분을 확인한다. 이 보고서는 실측 승인이나 새 확인 계획이 아니다.

## 확인 결과

| 항목 | 결과 | 의미 |
| --- | --- | --- |
| 연결/기기 | PASS | 등록 A24 한 대·모델·물리 identity·fingerprint 일치 |
| 설치 APK | PASS | 기기 base.apk SHA가 검증된 로컬 APK와 일치. 기존 정적 서명 검증에 연결되며 재설치하지 않음 |
| 앱 권한 | PASS | 기존 격리 패키지의 run-as 조회와 파일 읽기 가능 |
| 기존 입력 | PASS | 모델2개·labels2개·anchors·승인PNG 및 기존 manifest의 SHA 모두 일치 |
| 기존 owner | 없음 | 기존/격리 앱의 base/model_probe/a24_preparation 6개 프로세스 조회, 활동 중 owner 없음 |
| 공간 | 여유 있음 | 기기 약69GiB,노트북 약18.6GiB. 장기 수집량 보장이나 원물 삭제 지시가 아님 |
| 화면 설정 | 읽기 확인 | 수동밝기81/255,자동밝기0,timeout2147483647ms. 설정 변경0 |
| 배터리 | 현재 충전 중 | SOC90%,AC powered=true. 준비 조회는 가능하지만 본실측의 비충전 조건에는 부적합 |
| 온도 | 읽기 가능 | Current HAL AP31.2℃ 단발 조회. 준비 후 안정 gate/실제 표면온도 검증을 뜻하지 않음 |
| Perfetto | CLI 존재 | v49.0와 help 출력 확인. help는stderr/exit1이며 출력부재나 trace실패로 오인하지 않음. 추적 세션은 시작하지 않음 |
| 전체 설정 | PC PASS |64manifest·256runtime binding·8,832예정 요청의 실제 앱 parser 검산. 모든 복사본은mock=true/execution_authorized=false |
| 동작 검산 | PC PASS |parser1+binding3+순서/WAIT/병행 scheduler11+실제 worker 반환3=18개 PASS. 기기에서 실제 동작한 증거가 아님 |
| 원장 | 변화 없음 |기존 registry91파일 SHA 전후일치,새START/claim·원장소비0 |

기기 조회는 enumeration1+등록기기 읽기29=30명령이다. **앱 시작·설치·파일전송·워밍업·추론·본측정·Perfetto 시작·START/claim·세션소비는 모두0**이다. 배터리/온도는 단발 조회만 했으며 연속 측정이나 gate 대기는 수행하지 않았다. 기기 조회는13:18:05 KST에 끝났고 이후에는 PC 검사만 수행했다.

## 미리 발견한 차단 원인

1. **옛 미결합 템플릿을 그대로 사용하면 안 된다.** 첫 PC 검사에서 현재SOC10 계약 대비 옛 기본SOC20,과거APK/DEVICE_UNVERIFIED 상태를 잡았다. 당시18검사 중parser1 실패를 보존했다. 현재조립기의 동일 기기/APK 결합값과SOC10을 사용한 **실행 불가 PC 복사본64개**를 만들어 기존의 같은 검사를 강제 재실행했고18개 PASS다. 원 템플릿·본 controller·파서 판정은 바꾸지 않았다. 승인 sidecar를 만들지 않았으며 이 복사본으로 기기를 시작할 수 없다.
2. **현재 REV02 host adapter는 C252 DEV 전용이다.** `tools/d1_a24_revision02_control.py`의 `check_authorization`은 stage=DEV와recipe=C252만 허용한다. L64/M128 및CONFIRM은 기기 실행 전에 차단된다. APK/기본 scheduler의 해당 기능과 새 개정 host 경로의 준비 완료는 서로 다르다. 이 제한을 풀어 실측하거나 과거 실행기를 대신 켜지 않았다.
3. **새 독립 확인40 계약은 아직 필요하다.** 원8군×5독립블록40세션을 잔여예산 때문에24세션으로 대체하지 않는다. 개정 시작 조건을 쓸 새 확인의 계획·순서·ID·초기기준/앱밖냉각·분석/예측없음·예산을 먼저 고정하고 새host경로를PC검증해야 한다. 새40은 미확정 제안이며 현재실행권한0이다. 잔여31로 새40을 수행하려면 최소9슬롯이 추가로 필요하고 개발 추가분은 별도다.

## 나머지 8군의 준비 수준

| 군 | 기존 입력/실제 parser·기본 동작의 PC 검사 | 새 REV02 실측 경로 |
| --- | --- | --- |
| L64 BASE/PAIR_G | PASS | host연결/새묶음계약 미완료 |
| C252 CPU/GPU | PASS | 기존 묶음04 완료·종료,새창/ID 없이 재실행 금지 |
| M128 BASE/ORDER/PAIR_G/WAIT200 | PASS | host연결/새묶음계약 미완료 |

실제 런타임 초기화·워밍업·준비 후 시작 gate·실제 FIFO/EDD/WAIT/병행·부하 중 통신/원물 회수의 새경로 검증은 이번에 하지 않았다. 과거 기기 결과가 있더라도 미구현 새경로의 검증으로 전용하지 않는다. 새 독립확인에 앞서 필요한 작은 기능 검증은 별도 범위에서 수행해야 한다.

전류 단위 불일치로J계산불가,HAL AP와표면온도의 차이,한 승인 이미지 반복,기존 실패/원물보존,실측33시도/31미사용,`experiment_ready=false`는 그대로다. 연결/정적 검사 통과가 이후 모든 실측 오류가 없다는 보장은 아니다.

[검산 기록](VERIFICATION.json) · [읽기전용 기기 결과](DEVICE_READ_ONLY_RESULT.json) · [전체 실측 재개 안내](../MEASUREMENT_RUNBOOK.md) · [원래 계획](../../a24-laptop-measurements-20261014/PLAN.md)

## PC 재현

`A24_MANIFEST_PREFLIGHT_DIR`에는 기존 원본이나 새 실행허가가 아니라 **현재APK/기기에 결합한mock=true·execution_authorized=false PC전용64복사본**을 지정한다. 개인 원물·기기 식별자는 Git에 넣지 않는다.

```powershell
$env:A24_MANIFEST_PREFLIGHT_DIR='<PC전용64manifest폴더>'
.\gradlew.bat --offline --no-daemon --max-workers=2 -PenableA24Preparation=true -Pa24MeasurementIsolation=true :benchmark-runner:testA24PreparationUnitTest --rerun --tests 'com.example.d1check.benchmarkrunner.A24ActualManifestPreflightTest' --tests 'com.example.d1check.benchmarkrunner.A24PreparationSchedulerTest' --tests 'com.example.d1check.benchmarkrunner.A24WorkerReturnTest' --tests 'com.example.d1check.benchmarkrunner.A24MeasurementBindingTest'
```

환경변수 경로는 Gradle 입력으로 추적되지 않으므로 `--rerun`으로 실제 검사했다. 기존UP-TO-DATE를 새검사PASS로 전용하지 않는다. 이 명령은ADB/기기/네이티브모델을 실행하지 않는다. 이번 검사의 private명령로그·실패XML·최종XML·복사본·원물경로는ignored `output/a24_readiness_only_20261015/`에 보존한다.
