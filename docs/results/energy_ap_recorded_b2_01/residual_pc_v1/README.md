# B2 외삽 잔차와 한 개 AP 후보의 PC 사후 판독

[한국어 결과 보고](../../../ARRIVAL_RECORDED_B2_RESIDUAL_MODEL_PC_20260929.md) · [통합 대시보드](../../arrival_policy_screen_01/dashboard.html)

- `summary.json`: 원본/동결 SHA·시각/센서 경계·120초/부하/유휴 산술·AP 형태 진단·후보 상태.
- `sensor_intervals.csv`: 인접 전류 표본 단위 J 잔차. `mixed`는 그 구간에 상태 전환이 포함되어 단일 상태 W의 직접 관측값이 아님을 뜻한다.
- `cumulative_energy.csv`: 0초와 **정확한 120초** 관측·동결 끝점을 포함한다. 기존 `diag_v6/energy_path.csv`의 마지막 표본 119.285초와 구분한다.
- `ap_diagnostics.csv`: 절대 AP, 시작값 대비 변화, 첫 AP 표본만 맞춰 보는 오프셋 분해, 동결/후보 잔차. 첫 표본 정렬은 예측 입력이 아니다.
- `candidate_comparison.csv`: 개발 3세션·이미 본 확인 DC_DG·DIAG-04·B2의 AP MAE. 후보 선택 후의 **사후 비교**이며 독립 확인이 아니다.
- `idle_effective_reference.csv`: 동결 β를 고정하고 긴 유휴 구간의 첫·끝 관측 AP만으로 역산한 유효 기준. 주변온도나 새로 식별한 물리 계수가 아니다.
- SVG 세 개: 절대/변화/잔차 AP, 누적 J·상쇄·센서 혼합, 후보의 유리·불리한 결과.

원본이 있는 PC에서 **새 빈 출력 경로**로 재현한다. APK·기기·동결 모형을 변경하지 않는다.

```powershell
python -B -m tools.d1_arrival_recorded_b2_residual --bundle docs/results/energy_ap_recorded_b2_01/diag_v6 --session 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_diag_run_v6/00_3b668459-14ec-59ee-81e0-e30ab635514a' --frozen 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json' --development-run 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5' --transfer-run 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_run_v4' --output '<새 빈 PC 출력 경로>'
python -B -m tools.d1_arrival_recorded_b2_residual_figures --bundle '<분석 출력 경로>' --output '<새 빈 그림 경로>'
```

공유 CSV만 있으면 두 번째 그림 명령은 원본 절대 경로 없이 실행된다. A24 전류 raw=mA와 절대 J 정확도는 조건부이며, 후보는 simulator 기본 경로에 등록되지 않았다.
