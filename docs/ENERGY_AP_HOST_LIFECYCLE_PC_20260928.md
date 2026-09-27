# ENERGY-AP-HOST-LIFECYCLE-PC-01 — 종료 소유권과 1회 복구

**판정:** COLLECT-04에서 Python/PowerShell이 왜 끝났는지는 여전히 미확정이다. 마지막 ADB client의 정상 반환 뒤 최상위 receipt가 없는 원본만으로 상위 도구 종료, Python crash, 취소, 전원·절전 문제를 구분할 수 없다. 이번 변경은 향후 실행의 종료 식별과 1회 회수 경로를 PC에서 구현·검증한 것이며 원래 실패를 재현하거나 해결했다고 주장하지 않는다. 기존 `ENERGY-AP-STATE-COLLECT-04`의 원본·registry·`stopped_no_resume`와 `experiment_ready=false`는 불변이다.

## 실제 소유 구조와 기록

| 계층 | 소유·관측·증거 | 종료 때의 한계 |
|---|---|---|
| PowerShell `RUN_AFTER_APPROVAL.ps1` | 새 실행의 `host_run_id`, parent PID·UTC 시작, Python exit code·UTC 종료, stdout/stderr 파일 | wrapper가 강제 종료되면 `end.json`을 보장하지 않음 |
| Python 수집기 | 단일 소비 claim, child/parent PID·생성시각·실행 파일·명령줄을 첫 원자적 checkpoint에 고정, 단계·30초 poll 생존 기록, 예외 stack·receipt | 강제 종료·디스크 장애에는 `finally`를 보장하지 않음 |
| ADB client | Python의 `ObservedDevice`가 한 명령씩 직접 시작하고 부분 출력·PID·시각·exit/timeout·종료 처리를 저장 | client 결과는 Android 앱 종료 증거가 아님 |
| Android 앱 | 별도 1,800초 watchdog, 진행 journal·`cleanup.json` | watchdog의 `killProcess`는 앱 `finally`·cleanup 기록을 보장하지 않음 |

`d1_energy_host_lifecycle.py`는 단순 PID나 오래된 heartbeat만으로 사망을 판정하지 않는다. Windows CIM의 생성시각·실행 파일·명령줄까지 checkpoint와 비교한다. child와 parent 중 하나라도 동일 프로세스로 살아 있으면 복구 기기 명령을 막는다. 조회 실패·신원 누락도 `identity_unconfirmed`으로 막는다. PID 재사용은 원래 프로세스가 끝났다는 근거일 뿐 다른 프로세스를 종료할 근거가 아니다. PC 재부팅 후 monotonic 비교가 불가능하거나 남은 원 계획 시간이 60초 미만이면 자동 회수는 차단된다. 다른 실행을 정지시키지 않도록 기기 fingerprint/하드웨어 식별 후, 앱 프로세스가 있으면 Activity와 대상 session ID가 현재 `dumpsys`에 함께 보일 때에만 host force-stop을 허용한다. 소유권을 확인하지 못하면 상태 미확인으로 남긴다.

복구는 `d1_energy_host_recovery.py`의 **별도 단일 output claim**이 소유한다. 원래 수집 ID를 다시 실행하거나 요청·warmup을 발생시키지 않는다. 호출 반복은 기존 receipt를 읽고, claim만 남았으면 `claimed_unconfirmed`으로 끝낸다. 남은 시간이 충분하면 작은 manifest/progress/cleanup prefix를 먼저 회수하고, 45초 host cleanup 예약을 앞세운 뒤 archive를 시도한다. 원래 receipt에 성공 cleanup이 있거나 앱 프로세스 부재가 확인되면 force-stop을 반복하지 않는다. 회수·cleanup·receipt 실패는 각각 별도 오류로 남긴다. 원래 예외 stack을 후속 오류가 덮지 않는다. **강제 종료·PC 전원 상실·절전·네트워크 단절의 cleanup 성공은 보장할 수 없다.**

## 승인 전 최소 기기 진단 후보

별도 `ENERGY-AP-HOST-DIAG-01`, 상태 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`. 최종 후보는 외부 [diagnostic_plan.json](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_host_diag_plan_v7/diagnostic_plan.json>), SHA-256 `a6c65b0d7547ad99aaab21508f510841b4fa3729119faf07dd0effc7db20decf`다. 앞서 생성된 v1–v6 초안은 소스 해시가 달라 `Check`에서 거절되며 실행 후보가 아니다. 출력 `energy_ap_host_diag_run_v1`과 registry `ENERGY-AP-HOST-DIAG-01`은 **생성되지 않았다**. 과거 설치 검증 APK `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf`의 기존 Activity·worker·sampler·화면 조회·품질 gate를 사용한다. 실행 직전 현재 A24·fingerprint·설치본 해시/서명·배터리/비충전/온도·thermal·화면·메모리·GPU/품질 gate는 다시 확인해야 한다. 과거 설치 receipt가 현재 gate를 대신하지 않는다.

| 구간 | 상한·의미 |
|---|---|
| 세션·실행 | 진단 1세션, runtime 4회, warmup 8회, 적격성 4회(직렬2·병행2), 총 명시적 추론 12회. 작업 부하 0회. 기존 CC_DG의 생성→warmup→직렬·병행 적격성→resident 준비 순서 유지 |
| 입력·설치 | staging 1회/7파일. APK push/설치 0, 설치본 검증 host pull 최대 1회 |
| 관측 | resident 고정 관측 최소 120초, 준비 gate 최대 360초; AP·thermal·화면과 진행 기록. 공식 baseline·본 부하·공식 냉각 0초 |
| 시간 | preflight 최대 300초 + 세션 최대 1,200초 = **전체 1,500초(25분) hard cap**. host poll 최대 900초, 회수 최대 60초(작은 prefix 포함), cleanup 예약 45초. 정상 예상시간과 완주 배터리는 미확인 |
| 명령·중단 | ADB 최대 3,000 slots, cleanup 전 최대 2,900. 재시도·대체·추가 0. 온도 준비 미충족, 환경/품질/시간/계측/회수 오류는 중단·부분 증거 보존 |

앱은 `probe` arm 직후 바로 공식 baseline으로 들어간다. **동일 APK로 준비 단계에서 앱 스스로 정상 완료하는 경로는 없다.** 진단 host는 준비 120초 적격성이 확인되면 `probe`를 arm하지 않고 한 번 host cleanup/force-stop과 회수를 수행한다. 따라서 이 후보는 *host의 정상 종료·회수 경로와 앱 준비 단계*를 검증하지만 앱 자체 정상 cleanup의 성공까지 검증하지 않는다. 앱 cleanup이 없으면 `unconfirmed`으로 기록한다. 앱 정상 완료까지 요구한다면 진단 전용 Android 종료 경로와 새 서명 APK·설치 예산이 별도로 필요하며, 이번에는 APK를 바꾸거나 설치를 승인하지 않았다. 이는 준비 가능 범위의 명시적 제한이다. 준비 gate가 360초에 가까워져도 유리한 온도 창을 다시 고르지 않는다.

승인 전 PC Check(기기 명령 0회):

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_host_diag_plan_v7/RUN_AFTER_APPROVAL.ps1' -Action Check
```

**별도 승인 후에만** 실행할 명령(현재 transport는 실행기가 1대 A24를 확인하고 선택):

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_host_diag_plan_v7/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved
```

부모·자식이 모두 끝났는데 정상 receipt가 없는 경우에만, 같은 계획의 잔여 시간 안에서 별도 1회 복구를 검토한다. 먼저 PC `check`로 활성/미확인 여부를 판독한다. 아래 `run`은 이번 턴에 실행하지 않았으며 별도 기기 승인과 현재 기기 gate가 필요하다.

```powershell
python -B -m tools.d1_energy_host_recovery check --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_host_diag_plan_v7/diagnostic_plan.json' --output 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_host_diag_recovery_v1'
python -B -m tools.d1_energy_host_recovery run --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_host_diag_plan_v7/diagnostic_plan.json' --output 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_host_diag_recovery_v1' --adb 'C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe' --expected-sha a6c65b0d7547ad99aaab21508f510841b4fa3729119faf07dd0effc7db20decf --seconds-cap 150 --approved
```

## PC 확인과 해석

`python -B -m unittest tools.test_d1_energy_host_failure tools.test_d1_energy_host_lifecycle tools.test_d1_energy_state_collection -q` 결과 27건 중 26 통과·1건 건너뜀. 건너뛴 항목은 별도 환경변수 `D1_ENERGY_STATE_INSTALLED_PLAN`에 옛 frozen plan을 주는 테스트다. 옛 plan은 소비·종료됐고 host 소스 해시도 바뀌어 현재 후보의 Check가 아니므로 그 검사로 재실행하지 않았다. 새 `tools.test_d1_energy_host_lifecycle`은 실제 PowerShell 진입→Python fixture→진단 `run` 경계, parent만 종료 뒤 bounded child 생존, 정상 준비 관측, 예외/후속 회수·cleanup 오류, receipt fallback, 단일 claim, 오래된 PID·신원 미확인·타 앱 소유권 차단, ADB slot 상한을 검증했다. 이는 fake ADB/PC 경계 검사다. 실제 장시간 host·도구 세션 수명, Android 앱의 안정성, 네트워크 단절 후 복구 가능성은 미검증이다.

실제 PowerShell `-Action Check`는 계획·manifest·APK 서명·source/입력 해시·예산과 script 일치를 검사하고 성공했다. 기존 실측·ADB·앱·APK 빌드 0회. [작은 검증 요약](results/energy_ap_host_lifecycle_01/verification.json)을 참고한다.
