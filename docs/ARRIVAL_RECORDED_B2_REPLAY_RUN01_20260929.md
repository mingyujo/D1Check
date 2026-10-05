# 저장 B2 일정 재생 1회: 공식창 전 앱 종료

후속 [Activity lifecycle·소유권 PC 판독](ARRIVAL_RECORDED_B2_LIFECYCLE_PC_20260929.md)에서 앱 실패와 host force-stop의 선후를 대조했다. 최초 `onDestroy` trigger는 구 APK 기록만으로 미확정이며 원본·소비 상태는 변경하지 않았다.

**판정: `stopped_no_resume`, 1세션 시도·0세션 완료.** 승인된 `energy_ap_recorded_b2_plan_v3`(SHA-256 `52b0a21be884722b41a80b54ca0a874558a3a38aed3aeb85e89e247c7a830d5c`)를 `Check` 후 한 번 실행했다. 앱은 4개 runtime 생성과 8회 warmup을 모두 반환하고 host의 warmup arm을 수신했으나, resident baseline 시작 약 21.82초 뒤 `lifecycle_cancelled/null`을 기록했다. 공식 baseline 30초, 시작 직전 numeric AP gate, 24개 본 요청, 공통 120초 창에 도달하지 못했다. **에너지·AP 오차, 실제 병행, 정책 성능은 미산출**이며 해당 계획은 재실행하지 않는다.

## 소비와 종료

| 항목 | 실제 / 승인 상한 | 근거·한계 |
|---|---:|---|
| 세션 | 1시도·0완료 / 1 | `attempt.json`, `FINAL_RECEIPT.json` |
| runtime·warmup·본 작업 | 반환 4/4 · 8/8 · 시작 기록 0/24 | `progress.jsonl` 85개 유효 record; 누락된 기록을 무조건 실제 호출 0으로 단정하지 않음 |
| 명시적 추론 | 확인된 반환 8 / 최대 32 | warmup 8, 적격성 0, 본 작업 시작 기록 0; runtime은 추론 횟수에서 분리 |
| staging | 1회·7파일 / 1회·7파일 | 원본 입력 해시 확인·7개 파일 전송 |
| 설치본 확인·APK push·설치 | host pull 1/1 · push 1/1 · 설치 1/1 | 설치 전후 패키지·서명·후보 SHA `2af45f68…5b544` 일치; 전송/설치 후 앱 적격성으로 확대하지 않음 |
| ADB 명령 | 실행기 207 + 현재 transport 선택 1 = **208/3,200** | 203개 정상 반환, 4개 의도된 `test -e` 부재 exit 1; timeout·연결 소실 기록 0 |
| 전체 시간 | **93.547/1,300초** | 설치 경로 45.422초 포함; 회수·host cleanup 포함 |
| 회수·종료 | archive 6파일 회수, 앱 실패 `cleanup.json`, host cleanup 1회 완료 | 앱은 오류 상태에서 runtime 정리를 시도. 사후 대상 패키지 force-stop 및 `ps -A` 부재 확인은 별도 사실 |

기기 선택은 현재 목록의 단일 A24 transport에서 했으며 이후 실행 명령은 그 transport에 고정했다. 설치 전 환경 gate와 세션 전 환경 gate는 통과했고 설치본 SHA를 검증했다. 준비 중 host AP 표본은 마지막 30.4°C였지만 **실제 작업 시작 AP가 아니며**, 시작 gate 실패·통과로 판정하지 않는다. 공식창이 열리지 않았으므로 준비·회수 기간의 전류 표본을 전체 120초 에너지로 적분하지 않는다.

## 오류의 선후와 원인 범위

앱 원본 `session_failure.json`은 `ArrivalEnergyActivity.healthy()`에서 `stopped: lifecycle_cancelled/null`을 기록한다. 현재 Activity의 `onDestroy()`가 미완료 세션의 stop 값을 설정하는 경로가 있지만, 무엇이 `onDestroy()`를 촉발했는지는 기록되지 않았다. 사용자 조작, Android lifecycle 관리, 다른 외부 사건 중 하나로 확정하지 않는다. host는 앱의 실패·cleanup 파일을 **먼저 회수**한 뒤 대상 패키지에 세션 종료용 force-stop을 보냈다. 따라서 이 사후 force-stop은 앞선 취소의 원인이 아니다. 설치 gate의 별도 force-stop은 세션 launch 전에 수행됐다.

실행기의 원본 `FINAL_RECEIPT.json`에는 앱 실패 대신 누락된 `summary.json`의 `FileNotFoundError`가 최상위 오류로 남았다. 앱 자체의 최초 오류와 stack은 원본 `session_failure.json` 및 progress에 보존됐으며 회수 archive SHA는 `f17dd152c314e6e80e99f5e91747c68323e18d3bfbd2986582ba6ebeeb6743eb`이다. PC에서 `validate()`가 실패한 `cleanup.json`을 먼저 판독하도록 최소 수정하고, 성공 summary가 없는 fixture 테스트를 추가했다. **실행 당시 코드 해시·원본 receipt·동결 모형은 소급 변경하지 않았다.** 현재 코드의 판독 변경은 소비된 계획을 다시 Check하거나 Run하는 근거가 아니다.

## 판독·재현·범위

[작은 요약](results/energy_ap_recorded_b2_01/run01_summary.json)은 원본을 가리키는 별도 파생물이다. [대시보드](results/arrival_policy_screen_01/dashboard.html)는 저장 PC 일정과 실제 시도·결측을 분리해 표시한다. 원본은 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_run_v3/FINAL_RECEIPT.json`(SHA-256 `45f0ae99ea99e3d97bde3438bf2116e6627cd9cc2238cacaafd1aa7be81e394a`)과 같은 폴더의 `00_5891be99-066e-503f-bbf6-474f095e9ce4/artifacts.tar`에 보존했다. 결과를 보기 위한 읽기 전용 PC 판독 명령:

```powershell
python -B -m tools.d1_arrival_recorded_replay_analysis --session 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_run_v3/00_5891be99-066e-503f-bbf6-474f095e9ce4' --frozen 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json' --output 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_run_v3/analysis_readout'
```

`analysis_readout/summary.json`은 `not_evaluable`과 J/AP `null`을 반환했다. 출력이 이미 있으면 위 명령을 새 출력 폴더로 지정해야 하며 원본을 덮어쓰지 않는다. 동결 계수·기존 확인·FAIL·queue24 미소비 계획·`experiment_ready=false`는 유지한다. 재생 실패를 모형 예측 실패나 B2의 실기기 응답 성능으로 해석할 수 없다.

**다음 PC 행동 하나:** 회수된 lifecycle·Activity 시작/종료 기록과 host 화면 관측의 시간축을 대조해 `onDestroy()` trigger를 구분할 수 있는지 판정한다. 동일 세션 재실행이나 새 측정은 이 분석의 일부가 아니다.

검증: 2026-09-29, 실행 기준 HEAD `847b612a5aa6d7712e326553ff829479cfb365e2`, 실행 뒤 소스 변경 전 원본 보존. `python -B -m unittest tools.test_d1_arrival_recorded_replay -v` 8건 PASS, `git diff --check` PASS. PC fixture는 실제 Activity 종료 원인의 검증이 아니다.
