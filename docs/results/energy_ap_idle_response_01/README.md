# 저온 resident AP 유휴 반응 — PC 계획, 실측 없음

[설계·예산·중단 규칙](../../ENERGY_AP_IDLE_RESPONSE_PLAN_PC_20260929.md) · [동결 분석 계약](analysis_contract.json) · [기존 B2 잔차 근거](../energy_ap_recorded_b2_01/residual_pc_v1/README.md)

기존 동결 β·상태별 기울기 차이를 고정하고, **부하 전** HAL AP 표본만으로 세션별 유효 유휴 기준을 구하는 별도 진단 후보다. 개발 1세션은 한 짧은 CG_DC 묶음, 확인 1세션은 두 분리 묶음이다. B2 원본 일정·온라인 정책과 다르며 기존 동결값·strict 마스크·시뮬레이터 기본 경로는 바뀌지 않았다.

외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_idle_response_plan_v1/`에 미승인 계획·두 manifest·release 일정·Check 스크립트가 있다. 현재 기기·설치본·환경은 검증하지 않았고 실행 출력·소비 registry는 없다. 저장소에는 APK·모델·키·원자료를 넣지 않는다.

```powershell
python -B -m unittest tools.test_d1_ap_idle_response tools.test_d1_arrival_recorded_replay tools.test_d1_arrival_ap_confirmation -q
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_idle_response_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check
```

실행 승인 후 자료가 생성된 경우에만 `tools.d1_ap_idle_response.analyze_session`이 세션별 실제 lane 일정과 부하 전 AP를 조건부 입력으로 삼아, **부하 후** AP 경로·잔차를 별도 출력한다. 개발 결과를 보고 β/기울기를 다시 맞추거나 확인 자료로 후보를 바꾸는 경로는 없다. 정확도 PASS·정책 우월성은 미판정이다.
