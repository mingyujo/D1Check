# 무부하 대조 설계 — 실행 차단 상태

[필요성·예산·완료 기준](../../RESIDENT_CONTROL_MEASUREMENT_PLAN_20261001.md).

- `design_plan.json`: 미승인 설계. execution_ready=false, APK/Run=null. 실행 소비 기록 아님.
- `load_input.json`: 기존 burst/seed201/B2의 도착 유지/release+35초 입력. 새 결과를 보고 선정하지 않음.
- `verification.json`: 이번 PC 검사 결과.

저장소 루트에서:

```powershell
python -B -m tools.d1_resident_control_design check
python -B -m unittest tools.test_d1_resident_control_design -v
```

Check는 설계 산술/해시만 확인하며 ADB를 import/호출하지 않는다. 현재 APK/host가0요청 대조를 지원하지 않아 **실측 실행 명령은 제공하지 않는다**. 두 세션/40명시적 추론/2,090초/6,600명령은 구현 후 재검증할 제안 예산이다. 이미 실행 가능한 계획으로 혼동하지 않는다.
