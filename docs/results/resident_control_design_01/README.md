# 무부하 대조 — 실행 계획 PC 준비 완료

최신은 [보고서의 실행 준비 절](../../RESIDENT_CONTROL_MEASUREMENT_PLAN_20261001.md#실행-준비-완료-2026-10-01)과 `execution_contract.json`/`execution_verification.json`이다. 새 서명 APK와 `energy_ap_resident_control_plan_v1` Check 완료, 기기 미검증·미승인·미소비다. 아래 design_plan은 수정하지 않은 구현 전 이력이며 현재 Run 대상이 아니다.

[필요성·예산·완료 기준](../../RESIDENT_CONTROL_MEASUREMENT_PLAN_20261001.md).

- `design_plan.json`: 미승인 설계. execution_ready=false, APK/Run=null. 실행 소비 기록 아님.
- `load_input.json`: 기존 burst/seed201/B2의 도착 유지/release+35초 입력. 새 결과를 보고 선정하지 않음.
- `verification.json`: 이번 PC 검사 결과.

저장소 루트에서:

```powershell
python -B -m tools.d1_resident_control_design check
python -B -m unittest tools.test_d1_resident_control_design -v
```

위 Check는 설계 당시 산술/해시 검사다. 후속 구현으로 소스가 바뀌어 현재는 evidence drift를 거절한다. 설계 원본을 새 소스로 덮어쓰지 않았다. 최신 실행 Check/승인 후 명령은 보고서에 있다. 확정 예산은 두 세션/40명시적 추론/2,090초/6,600명령이며 실행 승인은 별도다.
