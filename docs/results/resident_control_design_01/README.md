# 최신 실행03 — C/L 두 세션 정상 완료

[결과 보고서·원본·재현](../../RESIDENT_CONTROL_RUN03_20261001.md) · [화면·그림·CSV](run03/index.html) · [검증](run03/verification.json).

plan_v3 소비·completed_descriptive_only. 40추론/1543명령/679.531초, 동일 설치본으로 APK push/설치0. C/L120초 J124.545817/137.005431, 전후 W 변화 차이−0.202361W. 한 쌍의 구조 개발 자료·외삽 진단이며 독립 확인/인과/정확도 PASS 아님. L 냉각후기 결측 null. 원본·두freeze·experiment_ready=false 유지. 아래 미승인/미소비 문구는 준비 당시 이력이다.

# 무부하 대조 — 새 계획03 PC 준비 완료

[계획·예산·승인 후 명령](../../RESIDENT_CONTROL_MEASUREMENT_PLAN_20261001.md#새-실행-계획03-준비-완료--2026-10-01) · [PC검증·해시](plan03/verification.json).

plan_v3는 **미승인·미소비·기기 미검증**이다. C0→L24/40추론/2,090초/ADB6,600/재시도0, 기존 서명APK 재사용. 실제PS Check 통과, Run/실행 출력/claim0. 새 실측 결과는 없다. 기존 종료 계획은 아래 이력으로 보존한다.

# 이전 실행02 — preflight 중단

[최신 결과 보고서](../../RESIDENT_CONTROL_RUN02_20261001.md) · [소비/종료 화면](run02/index.html) · [완료 검증](run02/completion_verification.json).

plan_v2는 설치본 host pull의 로컬 쓰기 실패·C: 여유 공간0으로 소비·stopped_no_resume. 세션/추론0, 새 에너지/AP 결과 없음. 공간 확보 후 PC 검증·Git만 완료했으며 종료 계획은 재실행하지 않는다.

# 이전 실행01 — C 완료/L 부분 중단

실행01은 [실행 결과](../../RESIDENT_CONTROL_RUN01_20261001.md)와 [그림·CSV](run01/index.html)이다. plan_v1은 승인1회 소비·stopped_no_resume이며 재실행하지 않는다. L전체창/C–L 차이는 null이다.

## 준비 당시 기록

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
