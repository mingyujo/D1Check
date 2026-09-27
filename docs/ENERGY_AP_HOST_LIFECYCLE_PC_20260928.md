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

### 2026-09-28 실행 전 명령 예산 재검토

`tools/d1_energy_host_diagnostic.py`의 실제 호출 경로를 기준으로 **3,000은 정상 예상치가 아닌 hard cap**이다. `ObservedDevice.sequence`는 client 시도마다 1 증가하며, 2,900에 도달하면 cleanup 전 새 client를 시작하지 않는다. 아래 계산은 각 주기에서 첫 조회를 하나 더 허용한 보수적 상계다. 조건 불충족으로 조기 중단하면 해당 단계 이후 명령은 쓰지 않는다.

| 단계·명령 종류 | 정상 완주 시 산식 | 900초 poll 최악 상계 |
|---|---:|---:|
| 설치본 preflight: 기기 식별 3, `pm path` 1, host pull 1, 환경 gate 14, 설치본 `pm path`/SHA 2 | 21 | 21 |
| 세션 전 환경 gate 14, 설치본 경로/SHA 2 | 16 | 16 |
| staging: 경로 부재 검사 3, 디렉터리 생성 2, 7파일 × (push·복사·SHA·이동 4) | 33 | 33 |
| Activity 시작 | 1 | 1 |
| poll: `ls`로 준비 파일/예상 밖 cleanup 감지, 루프 끝 1초 대기 | 실제 poll 길이에 따름 | 901 |
| poll: AP/thermal 한 표본 = uptime 앞·thermalservice·uptime 뒤 3명령, 최소 2초 간격 | 3 × 표본 수 | 3 × 451 = 1,353 |
| poll: 화면 `dumpsys power`, 최소 10초 간격 | 실제 표본 수 | 91 |
| poll: progress 마지막 줄, 시작 후 15초 및 thermal 표본 index 5의 배수에서 최대 1회 | 실제 heartbeat 수 | 90 |
| gate: warmup ready/결과/PID/logcat/arm 5, 직렬 적격성 ready/목록/결과 2/arm 5, 병행 적격성 ready/목록/결과 2(준비 성공 시 arm 안 함) 4 | 14 | 14 |
| 통제된 종료 전 작은 파일 3, host `force-stop`/프로세스 부재/thermal 3, 종료 후 작은 파일 3/단일 archive 1 | 최대 10 | 10 |
| **합계** | **poll 약 204초라는 예시에서 약 650명령** | **2,530명령** |

정상 예시의 poll 약 204초는 **과거 중단 기록에서 준비 gate 직전까지 약 84초를 관측한 뒤 이번 고정 resident 120초를 더한 조건부 계산**이다. 완주 실측이 없어 정상 평균이나 명령 수 분포는 모른다. 이 길이에서 `ls` 약 205회, thermal 최대 103표본/309명령, 화면 약 21회, heartbeat 약 20회, gate 14회, poll 밖 최대 81회를 더해 약 650회다. 900초 상계의 cleanup 전 2,523회는 2,900회보다 377회 적고, 전체 2,530회는 3,000회보다 470회 적다. 시간/명령 상한은 서로 독립이며 여유가 실행 성공을 보장하지 않는다.

원래 정식 수집기는 같은 `poll`에서 루프 끝 **0.25초** 대기를 사용했다. COLLECT-04 첫 세션의 보존된 host 명령 기록에서는 `ls` 177회가 약 83.8초 동안 기록됐고 간격 중앙값은 약 0.375초였다. 이번 진단은 **1초** 대기로 최대 약 1회/초이며, thermal 2초·화면 10초·heartbeat 약 10초 이상 간격은 원래 경로와 같다. `ls`는 gate 파일과 예상 밖 `cleanup.json`을, heartbeat는 진행 시각을, thermal/화면은 서로 다른 환경 상태를 확인한다. 같은 값을 반복 수집하는 중복 조회는 확인되지 않았다. resident 대기 중 `ls`가 thermal보다 잦지만 앱의 예기치 않은 종료를 즉시 구별하는 계약상 관측이므로 단지 명령 수를 줄이기 위해 없애지 않았다. 시간 창·조회 경로·소스 해시를 바꾸지 않아 plan_v7을 재생성할 필요도 없다.

### 동일 APK 진단의 판독 범위와 종료 소유권

| 판독 항목 | 이번 계획의 증거·판정 |
|---|---|
| 준비 중 host 지속·기록 | PowerShell 시작/종료, Python 첫 checkpoint·30초 `poll_alive`, ADB client별 시각/exit, 앱 `progress.jsonl`·AP/화면 관측으로 확인 가능. 상위 host가 갑자기 사라지는 상황의 재현이나 장시간 안정성 증명은 아님 |
| 소유자에 의한 host 요청 종료 | `runner.poll`이 120초 준비 적격성을 반환하면 `probe`를 **arm하지 않고** 같은 Python `run`의 `finally`에서 `shared.cleanup`을 한 번 호출한다. `force-stop` 명령/반환을 확인할 수 있음. 앱의 자발적 종료와 다름 |
| 증거 회수·앱 프로세스 부재 | 종료 전 작은 prefix와 종료 후 작은 prefix/단일 archive를 별도로 기록. `shared.cleanup`의 `require_stopped`가 앱 관련 프로세스 부재를 조회한다. 회수 실패·조회 실패는 별도 오류/미확인으로 남음 |
| 앱 자체 정상 종료·cleanup | **확인 불가.** 현재 APK는 준비 단계의 자발적 정상 종료가 없고 진단은 공식 baseline 전에 host가 멈춘다. `cleanup.json`이 없으면 `unconfirmed`이며 host cleanup 성공으로 대체하지 않음 |

활성 parent 또는 child 차단은 **외부 orphan 복구기** `d1_energy_host_recovery.check/run`에만 적용된다. 원 실행기의 소유자 통제 종료는 이 검사에 종속되지 않고 직접 `finally`에서 시행한다. 외부 복구는 실행 ID와 PID·생성시각·실행 파일·명령줄을 대조하고 parent/child 둘 다 종료된 것이 확인된 뒤에만 별도 단일 claim을 만든다. 살아 있는 원 실행기의 느린 준비를 orphan으로 간주하지 않는다. 따라서 동일 APK 진단만으로도 COLLECT-04의 공백 중 **host가 준비 중 계속 기록하는지, 요청한 종료·회수·부재 확인이 이어지는지**를 좁혀 확인할 수 있다. 앱 자체 cleanup과 우발적인 상위 프로세스 종료 원인은 남는다. 이 범위를 위해 새 APK는 필요하지 않다.

관련 PC 재확인: 착수 HEAD `b1ff42805a2a118b280f159efd9c0c0ce11777aa` clean/upstream 동일 상태에서 `python -B -m unittest tools.test_d1_energy_host_lifecycle.LifecycleTest.test_diagnostic_session_stops_before_baseline_and_consumes_once tools.test_d1_energy_host_lifecycle.LifecycleTest.test_active_run_blocks_device_and_claim tools.test_d1_energy_host_lifecycle.LifecycleTest.test_exact_process_identity_and_parent_child_independence -q`는 3/3 통과했다. plan_v7 `RUN_AFTER_APPROVAL.ps1 -Action Check`는 기존 해시 `a6c65b0d...b20decf`, 미소비 상태·기기 명령 0회를 확인했다. **판정: 이 한정된 host 지속·통제 종료·회수 진단은 PC 준비 완료, 현재 기기 gate는 미검증이며 실행은 아직 승인되지 않았다.**

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
