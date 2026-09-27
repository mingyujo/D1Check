# ENERGY-AP-STATE-COLLECT-03 준비 결과

[계약·식별표·예산](../../ENERGY_AP_STATE_COLLECTION_PREP_20260927.md) · [상태별 근거 CSV](state_identification.csv) · [공유용 계획 요약](plan_summary.json). 실제 계획/manifest/서명 APK는 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_plan_v3`와 `energy_ap_state_build_v3`에 있다. Git에는 모델·APK·원자료가 없다. 그 외부 파일이 없으면 `Check`/실행을 재현할 수 없다. 이 저장소만으로 PC 계약 테스트는 가능하다.

[PC 검증 기록](verification.json)은 변경 전 HEAD, 미커밋 검증 상태, 실행 명령·결과 및 계획/APK 해시를 담는다.

```powershell
python -m unittest tools.test_d1_energy_collection tools.test_d1_energy_operational tools.test_d1_energy_state_collection -q
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check
```

`Check`는 실제 기기 현재 상태를 조회하지 않는다. 출력·소비 registry는 아직 없다. Android/host 수집 경로는 PC에서 컴파일·검증했지만 A24에서 이 새 경로의 완료·계수 식별·확인 오차는 미검증이다.
