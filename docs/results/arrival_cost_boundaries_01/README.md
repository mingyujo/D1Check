# 기존 trace 기반 비용 경계

[한국어 판독](../../ARRIVAL_COST_BOUNDARIES_PC_20260927.md) · [오프라인 대시보드](dashboard.html) · [입력 SHA-256](SOURCE_HASHES.json)

기존 low/queue/burst·seed201–205·실현 간섭 1/1.5/2의 PC 응답 및 사후 회계 CSV를 재사용했다. `state_durations.csv` 135행과 `pair_boundaries.csv` 135행은 일정 고정 전력 민감도다. `boundary_summary.csv` 27행은 5 seed 요약이다. `representative_states.csv`·`representative_ap.csv` 각 9행은 저장된 seed201·실현1.5의 단계별 경로·AP 스트레스 가정에 한한다. 전력·열은 실측 보정되지 않았으며 물리적 가능 범위를 지정하지 않는다.

```powershell
python -m tools.d1_arrival_cost_boundaries
python -m unittest tools.test_d1_arrival_cost_boundaries -v
```

다른 간섭 조건의 AP 표를 0으로 채우지 않고 대시보드에서 `계산 불가`로 표시한다. 이 계산은 Android/ADB·추론 또는 기존 315조합 시뮬레이션 재실행을 하지 않는다.

검증 기록(2026-09-27 03:16 KST, 착수 HEAD `44ea7b0`, 이번 작업 미커밋 상태): 위 생성 명령으로 135/135/9/9/27행 생성, 관련 unittest 2건 통과. 저장된 seed201 단계 trace의 idle·단독·병행 합과 전 seed 회계 CSV의 역산이 일치했다. Node VM에서 오프라인 JS의 queue/1.5 표시와 burst/2 전환 시 지원하지 않는 AP·세부 trace의 `계산 불가` 표시를 확인했다. 브라우저 실제 렌더나 실기기 안정성 검증은 아니다.
