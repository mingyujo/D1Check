# COLLECT-04 host 종료·receipt 공백 PC 진단

**결론:** 원래 host Python/PowerShell이 왜 종료됐는지는 현존 기록으로 확정할 수 없다. 다만 마지막 ADB client의 성공 뒤 정상 종료·실패 receipt 없이 host 기록이 끊겼고, PC 장애 주입으로 **실패 처리의 2차 예외가 원래 예외를 덮고 두 종료 receipt를 모두 남기지 않는 결함**을 재현했다. 이 결함은 수정했지만 COLLECT-04에서 실제 발생했다는 stack은 없다. 새 실측 계획·APK·Android 코드는 만들거나 변경하지 않았다.

## 원본 경계와 계층별 판단

입력은 [COLLECT-04 종료 보고](ENERGY_AP_STATE_COLLECT04_RESULTS_20260928.md), 기존 `energy_ap_state_plan_v4/RUN_AFTER_APPROVAL.ps1`, 외부 `energy_ap_state_run_v4/host_commands`, `energy_ap_state_rescue_v4/RESCUE_RECEIPT.json` 및 소비 registry다. 원본·사후 주석은 수정하지 않았다. 시각은 UTC다.

| 계층 | 확인 사실 | 현재 판정 |
|---|---|---|
| PowerShell 진입 | `-Action Run -Approved`는 Python을 직접 호출하고 `$LASTEXITCODE` 비정상 시 일반적인 `Failed; no automatic retry/resume`만 던진다. 당시 원본 script는 child PID·정확한 exit code·stdout/stderr를 별도 파일에 남기지 않았다. PC 가짜 Python exit 17도 같은 일반 오류를 낸다. | 원래 Python exit code와 stderr는 미보존. PowerShell 문구 자체가 원인을 식별하지 못한다. |
| Python 최상위 | `main()`은 `run()`을 호출하고 반환될 때만 결과를 출력한다. `run()`은 세션 내부의 `BaseException`을 잡아 회수/cleanup/receipt를 시도한다. | 실제 `FINAL_RECEIPT.json`과 정상 `stopped.json` 모두 없다. 예외 handler 진입 여부·host PID는 미확인. |
| 세션·온도 준비 | preflight/첫 개발 세션의 runtime4·warmup8·적격성4 반환을 확인했다. 앱 journal은 `temperature_preparation` 진입 후 AP/전력 표본을 계속 남겼고 공식 baseline·load·앱 cleanup 기록은 없다. | 온도 조건 미충족 판정이나 앱 실패의 증거가 아니다. host가 그 단계에서 관측을 멈춘 사실만 확인된다. |
| subprocess | 원래 host ADB client 결과 377개가 모두 기록됐고 374개 exit 0, 3개는 계획된 파일 부재 `test -e` exit 1이다. 마지막 client PID 18304, `run-as ... ls`는 `2026-09-27 16:17:46.054` 시작·약 0.094초 뒤 exit 0, stdout 360 byte·stderr 0이다. `d1_recorded_process.py`는 pipe 대신 파일로 stdout/stderr를 회수하고 client timeout/종료 결과를 기록한다. | 남은 client timeout·비정상 exit·pipe drain 정체의 증거가 없다. 마지막 client 이후 Python/PowerShell 수명은 기록되지 않았다. |
| 시간·외부 실행 도구 | claim→마지막 client 128.210초. 이 경로의 온도 준비 gate는 최대 360초, host poll은 최대 1,800초, 앱 watchdog도 1,800초다. 별개 arrival timing runner의 125초 상한은 이 호출 경로가 아니다. 같은 도구 진입 방식의 **기기 없는** 가짜 Python을 140.516초 유지해 정상 종료한 PC 확인도 있다. 별도 PC에서 PowerShell parent만 종료하면 7초짜리 가짜 Python child는 계속 실행됐다. | 일률적인 125초 도구 제한이나 기존 125초 코드 경로를 원인으로 볼 근거가 없다. 개별 외부 종료 가능성은 남으며 parent 단독 종료 시 child가 살아남는 경로도 있다. 실제 Codex 도구가 process tree를 어떻게 종료했는지는 미기록이다. |
| Windows | 해당 시간대 Application Error/Windows Error Reporting에서 관련 오류를 확인하지 못했고, 현재 원 실행 PID는 없다. 원래 Python PID·process exit event는 저장되지 않았다. | Python crash, 사용자/도구 종료, OS 강제 종료 중 어느 것도 확정 또는 배제할 수 없다. |

앱은 host가 떠난 뒤에도 gate arm을 기다릴 수 있다. 앱 자체 1,800초 watchdog은 `killProcess`이므로 `finally`와 `cleanup.json`을 보장하지 않는다. 이번 별도 rescue는 앱 내부 cleanup 없이 원본을 회수하고 host force-stop·프로세스 부재를 확인했다. host가 통째로 죽으면 Python `except/finally`도 실행되지 않는다. 자동 외부 watchdog을 추가하면 실행 소유권·이중 cleanup 문제가 생겨 이번에는 도입하지 않았다.

## PC에서 재현한 결함과 수정

수정 전 실제 `run()` 경로에 가짜 기기를 연결해 온도 관측 예외→부분 회수 실패→host cleanup 실패→progress 요약 예외를 주입했다. 마지막 `ValueError('fixture damaged journal')`이 원래 예외를 덮었고, registry claim만 남고 `FINAL_RECEIPT.json`·`stopped.json`은 둘 다 없었다. 이는 **재현된 host 오류 처리 결함**이지 COLLECT-04의 확정 과거 원인은 아니다.

미래 계획용 수정은 다음에 한정한다.

1. 현재 host PID·parent PID·시각·plan SHA와 `preflight→session gate→staging→launch→poll/온도 준비→회수→cleanup→동결`을 원자적으로 새 checkpoint에 기록한다. 대기 중에는 30초 간격의 host 생존 checkpoint만 추가하며 기기 조회는 추가하지 않는다. 완료되지 않은 단계는 성공으로 표시하지 않는다.
2. 최초 예외의 종류·stack·thread·UTC를 먼저 붙잡는다. 부분 회수, cleanup, progress 요약의 후속 실패는 각각 독립 오류로 기록하고 원래 예외를 덮지 않는다. 종료 receipt는 같은 디렉터리의 임시 파일 fsync 뒤 rename한다. 최종 receipt 쓰기 실패 시 별도 fallback과 registry stop을 시도한다. 저장장치 전체 실패나 강제 종료에서는 둘 다 보장할 수 없다.
3. 앞으로 생성하는 PowerShell 진입 스크립트는 별도 `host_entry_*`에 wrapper 시작/종료, Python exit code, stdout/stderr **텍스트**를 남긴다. PowerShell 리다이렉션은 UTF-16 등으로 재인코딩할 수 있어 원래 child byte stream의 증거와 같지는 않다. Windows PowerShell의 native stderr를 `Stop`에서 오류로 승격해 exit 기록 전에 중단하는 PC 사례도 확인해, **child 호출 구간에서만** 이를 `Continue`로 바꾸고 exit code로 판정한다. 이미 소비한 plan_v4 script/해시는 변경하지 않았다.
4. 새 checkpoint 모듈을 향후 동결 source identity에 포함했다. 실행 단계·budget·gate·재시도0·APK 의미는 바꾸지 않았다. 수정본은 새 계획·승인이 있기 전 기기에서 실행할 수 없고, 기존 `COLLECT-04`는 계속 `stopped_no_resume`다.

## 검증 범위와 남는 공백

관련 PC fixture는 실제 `run→poll`의 온도 표본 오류, 가짜 child의 timeout/exit 7, `KeyboardInterrupt`/`SystemExit`, 회수·cleanup·journal 파싱 실패, 최종 receipt 쓰기 실패와 fallback, 소비 registry 재실행 차단을 검사한다. 실제 **rendered PowerShell→가짜 Python→실제 host run/poll fixture** 연결에서 Python exit 0/17의 기록과 stderr 보존을 확인했다. 별도 `os._exit(19)`는 마지막 checkpoint가 남고 정상 종료 receipt/cleanup은 남지 않음을 확인한다. 모두 PC의 단축 fixture이며 장시간 실기기 안정성·외부 도구 강제 종료 시 cleanup 성공을 검증하지 않는다.

[공유 가능한 PC 검증 요약](results/energy_ap_host_failure_01/verification.json)은 착수 HEAD `fda578839b0d1514acc7a923078269a8afe90c76`와 미커밋 관련 파일 해시를 묶었다. 관련 59건 중 58건 통과·1건은 외부 frozen plan 미지정으로 건너뛰었다. 검증 명령(기기 명령 0):

```powershell
python -B -m unittest tools.test_d1_energy_host_failure tools.test_d1_energy_state_collection tools.test_d1_energy_collection tools.test_d1_energy_operational -q
```

[140초 PC-only 진입 검사](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_host_lifetime_pc_v1/PC_RESULT.json>)는 PowerShell→가짜 Python이 140.516초 후 exit 0을 기록했고, `host_entry`의 시작/종료와 stdout marker도 보존했다. [parent 단독 종료 PC 검사](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_host_parent_kill_pc_v1/PC_RESULT.json>)에서는 PowerShell 종료 뒤 bounded 7초 child가 계속돼 종료 marker를 남겼다. 이 검사는 **Codex가 process tree를 종료한 방식**이나 과거 중단 원인을 밝히지 않는다. 다음 행동은 **새 기기 실행을 승인하기 전에 host 소유권 종료와 orphan 감지·수동 회수 절차를 한 번의 PC 계약으로 확정하는 것**이다. 장치에 추가 watchdog/ADB polling을 이번에 넣으면 비용·이중 cleanup·소유권이 달라지므로 보류한다. 새 6세션 수집을 권고하거나 실행하지 않는다. 기존 FAIL·부분 원본·동결값·`experiment_ready=false`를 유지한다.
