# ENERGY-AP-PUSH-OBSERVE-01 실행 전 보류

**결과: 기기 명령 전에 보류.** 이번 승인은 계획 SHA-256 `423ee55d98c6ef8ed5bea9ea3b1f5357a3d4806fb66c398dded922deff138f9a`의 관측용 push 1회와 동시에 **현재 설치본 확인·환경 gate를 17개 ADB 명령/420초 안에 포함**하도록 요구한다. 동결 계획과 `tools/d1_apk_push_observed.py`에는 이 두 gate가 없다. 계획을 바꾸거나 별도 조회를 더해 승인 범위를 초과하지 않았다.

| 확인 항목 | 실제 상태 |
|---|---|
| Git | 착수 `1e99d389a47235de75fdea3171cd85c8421e6e6b`, `feature/arrival-scheduling-20260923`, clean, upstream 동일 |
| 계획 | 외부 `energy_ap_push_observed_plan_v1/diagnosis_plan.json`; `python -m tools.d1_apk_push_observed check --plan <계획 경로>` 통과, 후보 106,092,116-byte APK SHA·ADB/소스 해시·17명령/420초 상한 일치 |
| 소비 | 계획 출력 `energy_ap_push_observed_run_v1` 부재, 실행 claim/registry 없음; push·pull·설치·추론 및 이번 새 ADB 조회 모두 0 |
| 준비된 실행기 | 문서의 `python -m tools.d1_apk_push_observed run --plan ... --expected-sha256 ... --approved`; 별도 PowerShell 스크립트 없음 |
| 실제 preflight | `devices -l`, model/fingerprint/hardware serial, **새 원격 대상 부재**, `df -k`의 6명령. 설치본 해시·비충전/배터리·thermal·화면 조회 및 생략 규칙 없음 |
| 이후 최대 | push 1 + 크기 조회 8 + 마지막 stat 1 + 조건부 SHA 1 = 11명령; preflight 6명령과 합쳐 최대 17명령 |

이번 지시대로 설치본·환경을 따로 조회한 후 동결 실행기를 돌리면 최악에 17명령을 넘는다. 조회를 기존 6개에 끼워 넣거나 probe를 줄이면 계획·코드 해시가 달라지므로 이번 승인과 동일한 계획으로 주장할 수 없다. 현재 후보 설치 여부, A24 transport·배터리·온도·thermal·화면 상태는 **이번에 조회하지 않아 미확인**이다. 과거 환경값은 전용하지 않았다. 따라서 원격 크기 표본·client 결과·SHA 판정도 생성되지 않았다.

외부 PC preflight 원본: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_push_observed_preflight_v1\PREFLIGHT_RECEIPT.json`, SHA-256 `6c65b1ad4f374bb9ab1830ff773acb0256accff1f7f300cefc5e269e5a81f09a`. 이는 **실행 receipt가 아니라 사전 차단 기록**이다. 기존 진단 출력/원자료·중단 계획·FAIL·`experiment_ready=false`를 보존한다.

다음 작업 하나: 현재 설치본 동일성·환경 gate·후보가 이미 설치된 경우의 생략을 **명시적으로** 포함하고, 모든 조회·최종 SHA·cleanup의 최악 명령 수와 시간을 다시 검증한 **별도 동결 계획**을 PC에서 준비한다. 이 문서만으로 새 계획의 실기기 실행이나 예산 확대를 승인한 것은 아니다. 같은 120초 push를 다시 시작하지 않는다.
