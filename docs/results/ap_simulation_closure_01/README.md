# AP 모형 판정과 제한 시뮬레이션 연결

[한국어 판정](../../AP_SIMULATION_CLOSURE_PC_20260930.md). 새 실측이 아니라 기존 8세션의 상대시간·센서 관측과 저장된 정책 결과를 읽는 PC 분석이다. 기존 동결 모형과 후보를 재적합하지 않는다.

- [AP 유휴 구간 CSV](readout/ap_idle_windows.csv): 실제 lane 합집합 뒤 10초 이상 idle. 조회 bracket 전체가 idle 안인 표본만 방향 판독. 샘플 최고 지연은 물리 시간상수가 아님.
- [센서 간격 CSV](readout/sensor_cadence.csv): 조회 간격·값 변화 관측 간격, 내부 갱신 주기는 null.
- [에너지 CSV](readout/energy_accounting.csv): 원래120초 전체와 마지막 release 분할의 오차; raw=mA 조건부 J.
- [정책별 지원 CSV](readout/policy_support.csv): 저장된 queue/201/1.5 3정책. 지원 밖 J/AP·rank=null.
- [기존 고정 CC_DG 선택 결과](readout/summary.json): 같은870건, 480초의 회고적 `TRADEOFF`. 동적 정책이나 독립 정확도 PASS가 아님.
- [관측 SVG](readout/idle_observation.svg) / [PNG](readout/idle_observation.png): 기존 AP 표본만 표시. 선은 표본 연결이며 실제 내부 센서 보간을 뜻하지 않음.

`inputs.json`은 AP 값·Android 상대시각·조회 bracket·lane-free 구간·적분 요약만 포함한다. 원문이나 하드웨어 식별자는 공유하지 않는다. 각 세션의 원본 validated/thermal/progress/requests 해시를 보존한다. role과 data_role을 구분하고 CG_DC 전이 자료는 정식 confirmation이 아닌 `protocol_transfer_posthoc`다. 원래 개발3 동결과 확인 전 후보절차 동결 SHA도 들어 있다.

저장소 루트에서 다음 명령으로 **새 출력 경로**에 재현한다. 첫 명령은 외부 원자료 없이 동작하고 새 simulator 배치를 돌리지 않는다.

```powershell
python -X utf8 -B -m tools.d1_ap_simulation_closure evaluate --output "$env:TEMP/d1-ap-closure-reproduce-new"
python -X utf8 -B -m unittest tools.test_d1_ap_simulation_closure tools.test_d1_ap_idle_response tools.test_d1_energy_operational_decision -v
```

원문→공유 입력 재생이 필요할 때만:

```powershell
python -X utf8 -B -m tools.d1_ap_simulation_closure extract --external 'C:/Users/LG/Documents/D1Check_Arrival_Extension' --output "$env:TEMP/d1-ap-closure-input-new.json"
```

필요 외부 원본은 `energy_ap_idle_response_run_v1`의 완료2세션, `energy_ap_recorded_b2_diag_run_v6`의 완료1세션, `energy_ap_state_run_v5`의 validated가 있는 개발3/확인1, `energy_ap_device_segment_diag_run_v4`의 완료1세션이다. 각 세션 `validated.json`, `thermal.jsonl`, `artifacts/progress.jsonl`, 도착 세션의 `artifacts/requests.json`, 유휴 세션의 `ap_analysis/summary.json`이 필요하다. 원래 `energy_ap_state_run_v5/development_freeze.json` 및 `energy_ap_idle_response_run_v1/ap_model_freeze.json` SHA를 고정 검사한다. 원본 없어도 작은 입력에서 보고서는 재현되지만 원문 byte 검증을 새로 했다고 주장하지 않는다.

`readout/summary.json`은 기존 `energy_operational_sim_01` profile/evaluation과 `arrival_policy_screen_01/measured_support_01/support_status.csv` 해시를 기록한다. 신규 분석의 검증 대상·재현 일치·수정 전 HEAD는 `validation.json`에 기록한다. 원래 결과와 모형은 보존하고 `experiment_ready=false`다.
