# ENERGY-AP-IDLE-RESPONSE-01: 두 세션의 조건부 AP 판독

[실행·판정 보고서](../../../ENERGY_AP_IDLE_RESPONSE_RUN01_20260929.md) · [작은 요약](summary.json) · [AP 표본별 비교](ap_paths.csv) · [SVG](ap_comparison.svg) · [PNG](ap_comparison.png)

개발 1세션에서 부하 전 AP로 유효 유휴 기준을 추정하는 절차를 동결한 뒤, 다른 두 묶음 순서의 확인 1세션에 같은 절차를 적용했다. 두 세션 모두 저온 시작으로 원래 동결 AP 식의 **외삽 진단**이며 strict 지원 또는 정책 우월성 확인이 아니다. 후보는 각 세션의 부하 전 AP와 사후 확보한 실제 lane 일정에 조건부인 오프라인 예측이다. 부하 후 AP는 비교 목표로만 사용했다.

원본은 저장소 밖 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_idle_response_run_v1`에 보존한다. 아래 명령은 원본·동결 파일을 읽고 **새 출력 경로**에 결과를 재생성한다. ADB를 호출하지 않는다. 원본 없이 공유 CSV/그림만으로 새 계수나 적격성을 다시 인증할 수 없다.

```powershell
python -B -m tools.d1_ap_idle_response_readout `
  --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_idle_response_plan_v1/collection_plan.json' `
  --run-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_idle_response_run_v1' `
  --frozen 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json' `
  --output 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_idle_response_readout_reproduction_v1'
```

`ap_paths.csv`의 `actual_phase`는 실제 lane 점유로 구분한 사후 **서술용** 분리다. 원래 실행기 결과의 `work` 표기는 첫 dispatch부터 마지막 lane 해제까지의 포괄 구간이므로 확인 세션의 두 부하 사이 유휴를 포함한다. 이 보조 분리는 동결 추정식·계수·확인 세션의 예측을 변경하지 않는다. AP 관측 약 2.4–3.3초 간격의 독립 표본을 독립 세션 반복으로 간주하지 않는다.
