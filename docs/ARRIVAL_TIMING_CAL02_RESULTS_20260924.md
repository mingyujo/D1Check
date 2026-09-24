# ARRIVAL-TIMING-CAL-02 — 설치 성공, 첫 세션 기록 불완전으로 종료

2026-09-24. **STOPPED_INCOMPLETE_REQUIRED_ARTIFACTS_NO_RETRY**. 시작 branch `feature/arrival-scheduling-20260923`, HEAD `b4cc659c5fc9b5274f5a3716d44d0efd92e848b0`, clean. 사용자 승인 범위는 개발8→검토·동결→확인8, 총16세션·진단64·warmup128, retry/대체/추가0, 실행+cleanup 상한121.5분이었다.

## 동일성·설치·환경

- plan SHA `31558f9c1d3c62b8d1d4e9f0b8713274bee6a1700e4a8c59c2c4ae5aabc5a7a6`, APK SHA `85c5fd0ab578d48e8af3e2abdda4c836939c5a330631d39dc4df61bd6d3e7ff6`. 현재 소스·16manifest·입력/build receipt/서명 identity 일치. 변경 없는 PC 테스트·과거 서명 원인 조사 반복 없음.
- 동일 `SM-A245N`, fingerprint `samsung/a24ks/a24:16/BP2A.250605.031.A3/A245NKSS9EZB5:user/release-keys`, 단일 무선 ADB. 실행 전 배터리76%, 충전 분리,29.0°C, thermal0, 앱 전체 process 부재. 시스템 Free RAM1,442,998KiB, status moderate. 이것은 앱 내 runtime memory admission PASS를 뜻하지 않는다.
- 서명 preflight1회 통과, 실패0. `install -r`1회 성공, 설치 실패0. 설치본 package `com.example.d1check.benchmarkrunner.modelprobe`, versionCode1, APK byte hash가 apksigner 검증된 후보와 일치하여 signer `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565` 확인. 앱 삭제·데이터 초기화 없음. 종료 뒤 기존 arrival 결과 디렉터리69개 존재도 확인했다(내용 전체 재감사를 뜻하지 않음).
- 사용자 추가 요구인 설치 후 확인은 외부 `approved_phase.py`로 기존 runner의 install 성공 반환 직전에 **읽기 전용 APK SHA/package/version gate만** 추가했다. 동결 코드/APK/추론/정책 경로는 수정하지 않았다. 실패는 기존 runner 중단/cleanup에 전파하도록 구성했으며 wrapper 원문과 hash를 receipt에 보존한다.

## 첫 세션의 실제 증거

세션 `78ac4f07-821d-5722-b191-57433ee048b9`, index0, classification/GPU/urgent. KST11:34:13.406550 launch_attempt, am start 결과 Status ok·COLD, PID19830. 앱은11:34:15.153에 session_start를 기록했다.

- 로그는 네 runtime의 생성 과정에 진입했음을 보여 준다. 마지막 관련 기록은11:34:22.572의 두 번째 GPU runtime 준비 부근 OpenCL 로그다. 이후 warmup/진단 완료 근거는 없다. 이 사실만으로 GPU driver hang, 간섭, 메모리 거절 또는 특정 코드 deadlock을 확정하지 않는다.
- host는 계획의125초 완료 poll 뒤 원본 회수/검증으로 진행했으나 필수 `decision_trace.json`이 없어서 FileNotFoundError로 중단했다. 기기 출력과 회수본에는 **manifest.json 하나만** 있다. warmup_trace/requests/environment/summary/cleanup/failure/watchdog도 없다.
- crash buffer에 보인09-19 오류는 과거 PID이며 이번 실패 원인으로 쓰지 않는다. 이번 ApplicationExitInfo는11:36:22.066 PID19830의 USER REQUESTED/FORCE STOP, 즉 host cleanup에 의한 종료를 기록한다. 앱 내부120초 watchdog이 종료 기록을 남기지 못한 이유도 미확인이다.
- host cleanup11:36:22.464389 완료, 모든 해당 앱 프로세스 부재·thermal0 확인. phase_attempt11:31:06.469371부터 cleanup까지315.995018초. 선행 서명 preflight까지 포함하면 약6분으로121.5분 상한 이내다. 정확한 preflight 시작 monotonic receipt는 없어 전체 시간을 소수점 단위로 확정하지 않는다.

## 소비량·분모

| 구분 | 실제 기록 |
|---|---|
| preflight | 1회 통과 / 실패0 |
| 설치 | 시도1 / 성공1 / 실패0 |
| phase | 개발 소비1·실패1, 확인 미소비 |
| 세션 | 시도1/16, 검증 완료0, 기술적 실패1, 미시도15 |
| Activity | 시작1 |
| 진단 요청 | 계획64. 성공 증거0. 실패 세션의4건은 실제 호출 수 미확인(0~4); 미시도15세션의60건은 미실행 |
| warmup | 계획128. 완료 증거0. 실패 세션의8회는 실제 호출 수 미확인(0~8); 미시도15세션의120회는 미실행 |
| retry·대체·추가 | 모두0 |

실제 호출0이라고 확정하거나 미실행을 성공으로 처리하지 않는다. raw가 없어서 실패/거절/만료/late success의 요청별 구분도 미확인이다. 도착/실행 수의 공백을 manifest 예정값으로 채우지 않는다. 원래16/64/128 분모는 유지한다.

## 추정 동결·확인 결과

개발8세션 완전성과 필수 기록 조건을 충족하지 못해 **fit을 생성/동결하지 않았고 확인8세션을 소비하지 않았다.** 아래 오차는 0이 아니라 계산 불가다.

| 조건 | 개발 | 동결 추정값 | 확인 오차(다섯 구간 모두) |
|---|---|---|---|
| classification/GPU/urgent | 첫 세션 기술적 실패 | 없음 | 계산 불가·확인 미실행 |
| classification/GPU/normal | 미시도 | 없음 | 계산 불가·확인 미실행 |
| classification/CPU/urgent | 미시도 | 없음 | 계산 불가·확인 미실행 |
| classification/CPU/normal | 미시도 | 없음 | 계산 불가·확인 미실행 |
| detection/GPU/urgent | 미시도 | 없음 | 계산 불가·확인 미실행 |
| detection/GPU/normal | 미시도 | 없음 | 계산 불가·확인 미실행 |
| detection/CPU/urgent | 미시도 | 없음 | 계산 불가·확인 미실행 |
| detection/CPU/normal | 미시도 | 없음 | 계산 불가·확인 미실행 |

기존20 null과 `experiment_ready=false`, UNKNOWN_OVERRUN 유지. 새40관측 슬롯도 확보되지 않았다. runtime memory admission 시계열과 GPU 전체 gate도 검증되지 않았다. 이번 근거가 지지하는 범위는 **동일 A24에 서명 호환 업데이트 설치 및 host의 bounded 중단/cleanup**이다. 안정된 tail·단독 서비스 추정·병행 간섭·정책 우수성 근거는 없다.

## 산출물·재개 제한

공통 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`:

- `timing_cal02_execution_v1`: approval/identity/environment preflight, 외부 wrapper, 설치 후 검증, logcat·ApplicationExitInfo·원격 출력 목록, FINAL_REPORT/FINAL_RECEIPT/GIT_FINAL.
- `timing_calibration_recovery_development_run_v1`: phase/install/attempt/launch/error/recovery/host_cleanup/stopped. artifacts와partial에는 같은 manifest만 있으며 원본을 수정하지 않았다.
- `timing_calibration_recovery_development_run_v1_preflight_80d6807ed93f4ddf868158c070561ab0`: 설치 전 서명 preflight·당시 설치 APK 보관본.
- `timing_calibration_execution_registry/ARRIVAL-TIMING-CAL-02`: development_consumed/stopped. 확인 consumed 없음.

실행 이력(재실행 금지):

```powershell
python -B C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal02_execution_v1/approved_phase.py --phase development
```

다음 필요한 작업은 **runtime 초기화/실패 종료의 진행 지점과 기록 유실 원인을 PC에서 진단하고, 후속 수정이 필요하면 별도 버전으로 준비하는 것**이다. 이번에는 코드 수정·설치 재시도·추가 측정 없이 종료한다. CAL-02 남은15세션이나 CAL-01/fixed-split 미실행분을 재개하지 않는다. 기존198요청 FAIL·부분 결과·원자료/APK/동결 계획 보존. 관련 문서만 local commit, push/merge 없음.
