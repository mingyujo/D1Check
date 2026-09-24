# ARRIVAL PC 탐색 v3 공유 결과

[한국어 결과·계약](../../ARRIVAL_FOLLOWUP_AND_EXPLORATION_20260925.md)을 먼저 읽는다. 작업 브랜치는 `feature/arrival-scheduling-20260923`이다.

- `input_bundle/`: CAL-03 개발 수치의 작은 파생 설정/공동 구간 벡터. 모델·이미지·원시 로그는 없다. 조건당 독립세션1/상관요청4이며 확률분포로 검증되지 않았다.
- `contract_before_development.json`, `development_selection.json`, `freeze_before_evaluation.json`: 개발/평가 구분·B2 선정·고정 가정. 성공 기준 또는 실제 기기 최적 B2가 아니다.
- `summary.csv`: 2모드×12조건×8정책, 지표의5반복 평균/min/max. `paired_effects.csv`: 반복 내 P 상대차, `representative.csv`: 사전 지정 queue/seed201 간트의 ns 시간 경계.
- `policy_comparison`, `sensitivity`, `gantt`: PNG/SVG. 오차막대는 모델반복 범위이며 CI가 아니다. 간트는 실기기 로그가 아닌 시뮬레이션이다.
- `plot_receipt.json`: 수치 불변인 대기 stripe 표시 수정의 출처.

```powershell
python -B -m tools.d1_arrival_explore_batch --bundle docs/results/arrival_explore_20260925/input_bundle --output ./arrival_explore_reproduction
```

출력 폴더가 이미 있으면 거절한다. 위 명령은 개발126+평가960의 한정 PC 실행이며 ADB를 호출하지 않는다. 원 실행의 외부 경로/provenance와 달라 receipt/hash는 달라질 수 있지만 같은 엔진·cells·벡터·seed의 metrics는 동일해야 한다. 외부 원자료에 접근할 수 없는 팀원도 이 숫자 입력으로 PC 결과를 재생성할 수 있다.

현재 P의 우월성은 입증되지 않았고 여러 조건에서 손해다. strict 모드도 새로운 도착/큐로의 전이는 가정이며, 순수 실측 모드는 별도 observed bridge의 정확한 trace 재생뿐이다. `experiment_ready=false`를 유지한다.
