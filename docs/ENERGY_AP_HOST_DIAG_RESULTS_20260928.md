# ENERGY-AP-HOST-DIAG-01 — 동일 APK 준비·통제 종료 진단 결과

**결과: 계획한 범위의 진단 완료.** plan_v7을 한 번 실행해 runtime·warmup·직렬/병행 적격성 및 고정 resident 온도 준비를 통과했다. 공식 baseline과 본 부하는 시작하지 않았다. 원 실행 소유자가 준비 성공 직후 `probe` arm 없이 host `force-stop`을 요청했고, 앱 관련 프로세스 부재와 부분/전체 증거 회수를 확인했다. 앱 자체 정상 종료·cleanup은 확인하지 못했다. 이 결과는 COLLECT-04의 원인 해결, 장시간 host 안정성, 에너지·AP 모형 적격성의 증거가 아니다.

## 동일성·예산·진행

- 착수 HEAD `27d6fcd447f5ce283cf80b5178620af808def5f0`, clean/upstream 동일. 승인 계획 `energy_ap_host_diag_plan_v7/diagnostic_plan.json` SHA-256 `a6c65b0d7547ad99aaab21508f510841b4fa3729119faf07dd0effc7db20decf`. 기기 명령 없는 `-Action Check`에서 APK/서명·소스·입력·manifest·예산·미소비 상태를 검사했다. 출력/registry가 없음을 확인한 뒤 `-Action Run -Approved`를 **한 번** 호출했다.
- 실행기는 현재 한 대의 A24 transport·fingerprint·하드웨어 식별, 설치본 SHA `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf` 및 계약상 배터리·비충전·온도·thermal·화면·메모리 gate를 통과했다. 이전 설치 receipt만으로 현재 상태를 대신하지 않았다. 전송·설치 fallback은 없었다.
- Python 실행 **254.843/1,500초**, PowerShell 진입부터 종료까지 **256.243초**. ADB client **359/3,000**, cleanup 전 2,900 한도 미도달. 설치본 host pull **1/1**, staging **1/1회·7/7파일**, APK push/설치 **0/0**. runtime 생성 **4/4**, warmup **8/8**, 적격성 **4/4**(직렬2·병행2), 총 명시적 추론 **12/12**. 공식 baseline·본 부하 **0/0**, 재시도·대체·추가 세션 **0**.
- ADB 기록 359개 중 설치본 pull 1, staging push 7, Activity 시작 1, 계획된 host force-stop 1이다. 경로 부재 검사 3개는 기대한 exit 1이었고 그 외 ADB client의 실패/timeout은 기록되지 않았다. host `poll_alive` 4개, thermal 50표본, 화면 poll 12회, progress heartbeat 8개가 보존됐다. 준비 판정은 **120.275초·AP 표본 43개**의 고정 관측이며, 평형 도달을 주장하지 않는다.

## 종료·회수 판정

PowerShell 시작/종료 기록의 `host_run_id`가 같고 Python exit code는 0이다. 첫 checkpoint에 parent/child PID 외에 생성시각·실행 파일·명령줄이 저장됐으며 종료 후 두 PID의 프로세스 부재를 PC에서 확인했다. 19개 checkpoint가 `temperature_preparation_waiting` → `poll_alive` → `temperature_preparation_ready` → `diagnostic_preparation_observed` → `host_cleanup_start/returned` → `stopped_no_resume`를 기록한다. 원 소유자가 직접 `shared.cleanup`을 호출했으므로 활성 host에 대한 외부 orphan 복구 차단과 충돌하지 않았다. 외부 복구기는 호출하지 않았다.

`host_cleanup.status=completed`는 `am force-stop` 반환, 앱 프로세스 부재 조회, 종료 시 thermal status 0을 포함한다. 종료 전 manifest/progress 작은 회수와 종료 후 단일 archive 회수는 수행됐고 archive에는 **12개 파일**, progress에는 **311개 완전한 기록**이 있다. runtime 4·warmup 8·적격성 4의 시작/반환이 대응하고, 공식 baseline/load 기록은 없다. 회수 때 `cleanup.json` 조회는 `No such file or directory` 문자열을 반환해 JSON 판독 오류로 **독립 기록**됐다. archive에도 해당 파일은 없다. 준비 단계에서 host가 통제 종료한 이 설계에서 앱 자체 cleanup은 `unconfirmed`이며 host cleanup 성공으로 대체하지 않는다. 원래 앱 journal의 미기록 호출 가능성을 일반적으로 0이라고 단정하지 않지만, 이번 회수 기록에는 누락·부분 줄이 없고 승인된 12회가 모두 반환됐다. 범용 `progress_consumption`의 `load.actual_started_upper=1680`은 원 정식 수집의 기계적 상한으로, 이번 진단의 승인 작업량 0이나 실제 호출을 뜻하지 않는다.

출력/소비 registry는 이 단일 계획에 대해 `stopped_no_resume`로 남는다. 재실행하지 않는다. 원본은 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_host_diag_run_v1/FINAL_RECEIPT.json`, 같은 폴더의 `host_checkpoints/`, `host_commands/`, `00_*/artifacts/`와 `energy_ap_host_diag_plan_v7/host_entry_*/start.json`·`end.json`에 있다. 대용량 APK pull·전체 로그/원자료는 외부 폴더에만 둔다. 공유 [작은 요약](results/energy_ap_host_diag_01/summary.json)에는 불필요한 transport/PID를 넣지 않았다.

## 재현·다음 행동

실행에 사용한 명령은 `& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_host_diag_plan_v7/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved`다. **이는 실행 기록이지 재실행 안내가 아니다.** 결과 확인은 아래처럼 원본만 읽는다.

```powershell
Get-Content 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_host_diag_run_v1/FINAL_RECEIPT.json' -Encoding utf8 | ConvertFrom-Json | Select-Object status,elapsed_seconds,adb_command_slots,preparation,host_cleanup,recovery,app_cleanup
```

**다음 행동 하나:** 이번에 확인된 host 기록·통제 종료·회수 경로를 유지하는 **새 정식 수집 계획을 PC에서 별도로 준비·검증**한다. 이번 진단의 완료를 근거로 기존 COLLECT-04나 종료된 계획을 재개하거나 6세션 실측을 자동 시작하지 않는다. COLLECT-04의 우발 종료 원인과 장시간 실행, 앱 자체 정상 cleanup은 여전히 미검증이다. 기존 FAIL·원자료·동결값과 `experiment_ready=false`를 유지한다.
