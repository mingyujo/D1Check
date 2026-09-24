# ARRIVAL-TIMING-CAL-03 — 동기 진단기록 없는 시간 보정 후보 / 미실행·미승인

2026-09-24. ARRIVAL-STALL-OBS-DIAG-01의 통합 경계 성공 후 PC에서만 준비했다. 이전 CAL-01/02 registry 및 종료상태를 재사용하지 않는다. 진단 승인으로 이 계획을 실행할 수 없다.

- 목적: 단독 task×backend×priority 8조건의 시간 경계 수집·초기 중앙값 기술. 새16세션(개발8→자료품질 확인→추정 규칙/범위/값 동결→확인8), 진단64(조건당4), warmup128(세션당8), 총explicit192, runtime64, 평가0. retry/대체/추가0. phase당 설치≤1, 합≤2. 초기32분 cooling 포함 예상45~60분, 실행/cleanup 합상한121.5분(phase3600+cleanup45 각각2). 중간PC검토/충전 대기는 별도다.
- 기기/모델/입력/seed2026092401/순서/완료 경계와 fit 중앙값·최소·최대 규칙은 [기존 시간 계약](ARRIVAL_TIMING_CALIBRATION_20260924.md)을 유지한다. 새로운 ID와session/output/registry/hash로 기존 결과와 분리한다.
- 앱/서명/APK는 성공 진단과 동일. manifest에서 `failure_diagnostic_contract`/scope/performance_excluded가 없으므로 동기 failure journal은 생성하지 않는다. 일반 timing trace/warmup trace는 기존 메모리 buffer→종료 flush이고 결과 persist는 측정할 본래 비용이다. 모든 I/O가 제거됐다고 주장하지 않는다. 실패시 최종trace가 없으면 호출 수/구간이 미확인일 수 있으며 partial/host증거를 회수하고 보정 fit을 차단한다.
- 추가 gate: 각 세션 시작 전 power의 `mWakefulness=Awake`와 `mHalInteractiveModeEnabled=true`를 read-only 확인. 화면을 자동으로 켜거나 해제하지 않는다. 기존battery/thermal/memory/서명/연결 gate에 추가하며 완화 없음. 이는 과거 실패 원인 확정이 아니라 sleep 상태를 보정 지원 조건에서 분리하는 설계다. gate는 그 순간만 증명하며 전 구간 awake를 보장하지 않는다; 환경자료/긴 지연/timeout도 남긴다.
- 새CAL-03 host poll에는125초 절대deadline을 적용한다. runtime30/watchdog120·원phase3600·cleanup45 유지. 실패/자료누락/overflow/환경이탈/solo위반 즉시 종료, 실패/미시도 분모보존, 다음phase금지. 새로운 값이 유리한지로 종료 여부를 고르지 않는다.
- 첫 보정세션부터 4요청이므로 lane_available 뒤 실제 후속재사용·순서와 solo 조건을 검증한다. 이번 진단1요청 성공만으로 그 위험을 PASS 처리하지 않는다. 모든8조건/실제lane재사용/비동기기록 품질은 미검증이다.
- 개발32요청은 독립32세션이 아니라 조건당1세션의상관4개다. 확인자료로 재조정하지 않는다.8×5=40관측슬롯의 초기중앙값도 적응형판단비용·busy overrun잔여·병행간섭·tail을 검증하지 않는다. 기존20null/UNKNOWN_OVERRUN/experiment_ready=false 유지.
- APK/source일치·apksigner·16manifest·null/N/A분리·PC dry-run PASS. 관련15테스트PASS(후속provenance/새ID·미소비·sync없음·awake gate·기존fit/freeze 포함). ADB/설치/실측0, raw측정합성0. 실행 코드의 기존sample품질/GPU delegate proof gate도 그대로 유지한다. 이번 진단의 `native_gpu_verified=false`를 뒤집지 않는다.

## 실제 경로와 명령

외부 Windows root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`는 GitHub에서 열 수 없다. `timing_cal03_plan_v1`에 plan/16manifests/승인후script, `timing_cal03_pc_v1`에 followup_binding/DRY_RUN/source snapshot/검증기록을 보존한다. source snapshot은 진단 실행당시host와 이후calibration 준비host를 구분한다.

```powershell
# PC 검증만, ADB 없음
python -B -m tools.d1_arrival_timing_calibration check --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_plan_v1/calibration_plan.json
# 별도 새16세션 예산 승인 이후에만
& C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_plan_v1/RUN_AFTER_NEW_APPROVAL.ps1 -Serial '<A24>' -Phase development -ApprovedCAL03
# 개발8개 모두 유효한지 검토한 뒤 write-once 동결
python -B -m tools.d1_arrival_timing_calibration fit --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_plan_v1/calibration_plan.json --run C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_run_v1/development --output C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_fit_v1.json
& C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_plan_v1/RUN_AFTER_NEW_APPROVAL.ps1 -Serial '<A24>' -Phase confirmation -ApprovedCAL03
python -B -m tools.d1_arrival_timing_calibration confirm --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_plan_v1/calibration_plan.json --run C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_run_v1/confirmation --freeze C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_fit_v1.json --output C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_confirmation_v1.json
```

추가 진단을 별도로 늘리지 않는다. 다음 최소행동은 이 후보의새예산과awake조건 검토·승인이다. 승인전 기기실행 금지.

Plan SHA-256 `b184dea24918cefe476ca7b48543a3674ad45fa6f1c6bff152d84d2b40b9d635`; APK `9019b85d527fcbcd49e49741bf1fd1bcb274281434032f13dc60bb471e2bf2c0`. 계획 상태 `proposed_budget_not_approved`.
