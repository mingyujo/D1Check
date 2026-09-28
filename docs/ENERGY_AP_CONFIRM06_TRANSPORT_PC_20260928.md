# CONFIRM-06 연결 소실과 잔류 프로세스 확인

2026-09-28 UTC, `feature/arrival-scheduling-20260923`, 착수 HEAD `32379427600b7fe2c408d496a86e46b14114cb25`에서 원본을 읽고 동일 A24에 제한된 읽기 전용 조회만 했다. 원 실행·회수 receipt, 소비 registry, 동결 모형은 변경하지 않았다. 이 문서는 연결 실패를 모형 예측 실패로 취급하지 않는다.

## 현재 앱 상태

재연결 후 `adb devices -l`에는 `172.20.10.2:37337` (`transport_id:91`) 한 건이 온라인이었다. 이 경로의 model·fingerprint·하드웨어 serial은 승인된 A24와 일치했다. 이 serial에 고정해 `pidof`, Activity/프로세스 상태, 해당 세션의 `progress.jsonl`·`cleanup.json`을 읽었다. 앱 프로세스 PID 4888은 있었지만 `EnergyCollectionActivity`와 해당 세션 ID는 Activity 목록에 없었다. Android의 프로세스 기록은 `curProcState=19`, `cached=true`, `empty=true`, `currentHostingComponentTypes=0x0`이었다. 종료 journal은 앞서 회수한 500행과 SHA가 동일하고 마지막 사건은 `app_cleanup`이다. `cleanup.json`은 원래 gate 예외 때문에 `failed` 상태를 유지한다.

따라서 **이전 세션이 계속 본 작업을 수행한다는 증거는 없고, 남은 PID는 캐시된 잔류 프로세스로 보는 것이 가장 잘 맞는다.** 이 시점의 snapshot만으로 모든 다른 앱 내부 작업의 부재를 보장하지는 않는다. PID 존재만으로 추론 중이라고 판단하지 않았다. 소유권이 불명확한 다른 작업을 보호하기 위해 앱 force-stop은 하지 않았다. 사용자 측에서 다른 작업이 없음을 확인하고 대상 벤치마크 패키지만 종료하도록 명시적으로 승인하면 그 범위에서만 종료할 수 있다. 재측정·재연결·ADB 서버 재시작은 하지 않았다.

이번 추가 조회는 초기 `adb devices -l` 1회와 선택 serial의 기록형 읽기 전용 명령 8회, **총 9회**다. 외부 조사 원본은 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_confirm06_process_check_v1/`에 보존한다. `PROCESS_CHECK.json`의 `adb_commands:7`은 마지막 `dumpsys activity processes` 이전의 중간 checkpoint로, 최종 합계가 아니다.

## 두 transport와 실패 경계

| 시점 | 실제 기록 | 해석 한계 |
|---|---|---|
| 실행 전 첫 보류, 02:31 UTC | `10.80.3.177:45677`만 `offline`, 온라인 0대. 이때 Run/claim 0 | 사용자가 알린 두 경로가 이 조회에 동시에 보이지 않음 |
| 본 실행 시작, host slot 0000 | mDNS `adb-R59W802RW5F-yZ5QCN._adb-tls-connect._tcp` 한 건 온라인, `transport_id:89`. 실행기가 이 serial을 선택하고 후속 ADB 명령을 `-s`로 고정 | 다른 경로의 동시 상태는 이 목록에서 확인되지 않음 |
| slot 0607, 02:54:15.260 UTC | 선택 mDNS 경로의 `run-as ... ls`, exit 0, 1.094초, stdout 360 byte. 종료 02:54:16.347 | 명령 하나의 성공이며 이후 연결 보장 아님 |
| slot 0608, 02:54:16.631 UTC | 같은 경로의 `exec-out cat /proc/uptime`, exit -1/`4294967295`, 0.328초, stderr `error: closed` | 2초 timeout 아님. 닫힌 내부 위치·원인은 미확정 |
| slots 0609–0614 | 같은 경로의 회수와 host force-stop 시도에서 `device not found` | 선택한 transport가 사라졌음. 다른 경로로 자동 전환하지 않음 |
| 약 02:56:41 UTC 단일 회수 | `adb devices -l` 온라인 0대 | 실패 순간에 다른 경로도 사라졌는지는 기록 없음 |
| 사용자 재연결 뒤 이번 조회 | `172.20.10.2:37337`, `transport_id:91`, 동일 model/fingerprint/하드웨어 serial | 같은 물리 A24의 **다른 ADB endpoint**. 원래 mDNS 경로가 왜 사라졌는지 증명하지 않음 |

실패 직전 slot 0603–0606도 반환됐고 0607은 이전보다 느렸지만, 이것만으로 연결 품질 저하나 기기 과부하를 확정하지 않는다. slot 0608의 client/ADB server·무선 링크·mDNS·기기 daemon 중 어디에서 `closed`가 시작됐는지는 로그로 구분되지 않는다. `host_after_failure`의 server 프로세스 조회는 2초에 걸려 `query_timeout`이며 부분 출력에 ADB server PID 2388만 있다. 이 시각의 별도 ADB server 로그는 실행 원본과 사용자 Temp에서 확인되지 않았고, Temp의 `adb.log`는 9월24일 수정본이다. 같은 시간대 Windows Application 오류 기록에도 `adb.exe` 오류 항목은 발견하지 못했다. 이는 server가 정상이라는 증거가 아니다. 원 실행은 실패 시 다른 transport를 목록 조회하지 않았으므로 **선택 경로만 사라졌는지, 두 경로가 모두 사라졌는지 미확인**이다. 두 경로가 존재했다는 사용자 관측을 원인으로 승격하지 않는다. 다른 경로로 실행 중 자동 이동하는 것도 세션/clock/동일성 계약을 깨므로 허용하지 않는다.

## host ADB 의존 경계

실제 코드 `tools/d1_energy_collection_device.py`의 `poll()`은 대략 2초마다 AP 조회를 위해 ADB `cat /proc/uptime` 두 번과 `dumpsys thermalservice` 한 번, 대략 10초마다 화면 조회, 매 poll에서 `run-as ... ls`로 앱 준비/종료 파일을 확인한다. 필요할 때 heartbeat·gate 결과를 읽고, `warmup`·`serial_probe`·`probe`·`baseline` ready 파일 검증 후 `.arm`을 ADB로 쓴다. Android `EnergyCollectionActivity.gate()`는 해당 arm이 없으면 기본 60초 뒤 실패한다. 이번에는 baseline 약120.055초 완료 후 host가 `baseline.arm`을 보내지 못했고 앱은 `baseline_gate`에서 약61.13초 후 제한시간 예외를 기록했다. 따라서 본 작업 0회이며 `CG_DC`·`CC_DG` 확인 자료가 없다.

기기 앱의 1초 power sampler와 앱 journal은 일시적인 host 연결 소실에도 일정 구간 남을 수 있다. 반면 AP 온도는 host ADB 조회에 의존하며, gate 전 연결이 없으면 부하로 진행하지 않는다. baseline arm 이후에도 host가 사라지면 앱 내부 부하가 한동안 실행될 가능성은 코드상 있으나, host AP 관측·환경 gate·실패 회수가 끊겨 현 계약의 적격 완료로 간주할 수 없다. 이것은 **실시간 ADB가 측정과 단계 진행의 단일 의존점**이라는 설계상 사실이지, 연결 소실 원인이나 새 프로토콜의 타당성 검증은 아니다. host 조회 방식·arm 방식의 변경은 계측 조건과 실패 경계를 바꾸므로 동결 확인 두 조건에 조용히 적용할 수 없다.

기존 개발 3세션·동결 모형·DC_DG 확인 결과는 유지한다. 이번 시도는 적격성 4＋warmup 8의 명시적 추론 12회, 본 작업 0회, `CG_DC`·`CC_DG` 미완료이며 `stopped_no_resume`다. 확인 오차와 정책 판단은 계산할 수 없다. `experiment_ready=false`를 유지한다.

**다음 행동:** 앱의 다른 작업이 없음을 사용자가 확인한 뒤, 필요하면 **대상 벤치마크 패키지만** 종료하도록 명시적으로 승인한다. 연결 소실의 내부 원인과 실패 순간 다른 경로 상태는 현재 기록으로 미확인이며 새 측정은 보류한다. 향후 수집 설계를 검토할 때에는 실시간 ADB arm/센서 조회 의존을 계측 프로토콜 변경으로 다룬다.

근거: `energy_ap_state_confirm_run_v1/host_commands/0000,0607–0614/client/`, `energy_ap_state_confirm_recovery_v1/RECOVERY_RECEIPT.json`, `energy_ap_state_confirm_postfailure_audit_v1/artifacts/progress.jsonl`, 위 `process_check_v1/`, [CONFIRM-06 결과](ENERGY_AP_CONFIRM06_RESULTS_20260928.md), `tools/d1_energy_collection_device.py:69–205`, `EnergyCollectionActivity.kt:90–97,169–185`.

## 2026-09-28 03:34 UTC 사용자 승인에 따른 대상 앱 종료

사용자가 해당 벤치마크 앱에서 다른 작업을 시작하지 않았다고 확인하고 **이 패키지만 force-stop 1회**를 명시적으로 승인했다. 새 `adb devices -l`에서 온라인 transport는 `172.20.10.2:37337` 한 건이었고, 이 경로의 현재 fingerprint·하드웨어 serial·모델 `SM-A245N`이 계획의 동일 A24와 일치했다. `pm path`로 코드 상수의 정확한 패키지 `com.example.d1check.benchmarkrunner.modelprobe` 설치를 확인하고, `pidof ...:model_probe`에서 기존 PID 4888을 확인했다.

`adb -s <현재 확인한 transport> shell am force-stop com.example.d1check.benchmarkrunner.modelprobe`를 **한 번** 호출해 exit 0을 받았다. 이어서 같은 transport의 `pidof` 조회에서 패키지 본체와 `:model_probe`가 모두 exit 1·출력 없음으로 **프로세스 부재를 확인**했다. 현재 조회·종료·사후 확인은 총 ADB 9명령, 03:34:21.953–03:34:25.251 UTC 약3.30초였다. 이는 과거 앱 자체 cleanup 성공을 소급 확인하는 결과가 아니라, 현재 사용자가 승인한 host 종료와 사후 프로세스 부재다. 다른 앱·ADB daemon·기기 설정은 변경하지 않았고 설치·추론·실측·계획 재개는 0회다.

명령별 stdout/stderr·exit·시간과 단일 종료 claim은 기존 외부 진단 경로 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_confirm06_process_check_v1/authorized_force_stop_01/`의 `RECEIPT.json` 및 `commands/`에 보존했다. 이 종료로 앞 절의 transport 원인 미확정이나 CG_DC/CC_DG 확인 미완료 상태는 바뀌지 않는다.
