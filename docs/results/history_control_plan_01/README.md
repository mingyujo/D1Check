# 이력 통제 수집: PC 구현 완료·실측 미승인

[한국어 계약·정확 예산·승인 후 명령](../../ENERGY_AP_HISTORY_CONTROL_DESIGN_20261007.md) · [PC 검증과 APK/계획 바인딩](implementation_check.json).

개발6→한 후보 동결→확인6. 최대2,016추론, runtime48, 19,557초, ADB91,400명령. 실제 소비/결과가 아닌 준비 예산이다. 개발 gate가 실패하면 확인은 수행하지 않는다. 기기·Run·claim0, 기본/RL/strict/experiment_ready=false 유지.

`design.json`과 `check.json`은 최초 설계 시점(실행 미준비)의 기록이다. 현재 상태는 implementation_check와 최종 외부 계획의 Check를 따른다. APK·원자료·개인 기기 식별정보는 Git 밖에 있다.

```powershell
python -X utf8 -B -m unittest tools.test_d1_history_control tools.test_d1_background_activity_plan tools.test_d1_energy_device_lifecycle_cleanup
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_control_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check
```

## 최신: 20분 복구 대기와 조건부 보완 실행

[6시간 캠페인 최종 계약](../../ENERGY_AP_HISTORY_RECOVERY_PC_20261008.md) · [검증/새 hash](recovery_check.json). 실행 대상은 `energy_ap_history_recovery_plan_v2` wrapper. 미승인·미소비, 기기0. 첫 앱 실패·적격개발0인 경우에만 새 block1회 보완 가능하며 일반적인 모든 오류 자동수정/재측정 보장은 아니다.

## v2 실제 실행 종료

첫 세션 listing timeout으로 stopped_no_resume, 적격개발/확인0. [실제 결과·부분 기록·재현](run_v2/README.md). 후보/J/AP 오차는 null이며 v2를 재실행하지 않는다.
