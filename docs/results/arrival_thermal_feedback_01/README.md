# 온라인 에너지·AP 후보 PC 결과

- [통합 대시보드](../arrival_policy_screen_01/dashboard.html): 아래쪽의 별도 “온라인 에너지·AP 피드백 후보”에서 단계·low/queue/burst·가정 profile·seed를 고른다. 위쪽 전력 슬라이더는 기존 고정 일정의 **사후 회계**이고 아래쪽 결과를 재실행하지 않는다.
- `CONFIG.json`: 결과 열람 전 고정한 합성/가정/비교 행렬. 모든 전력·AP 평형/한도는 미측정 스트레스 입력이다.
- `run_v1/SOURCE_MANIFEST.json`, `freeze_before_confirmation.json`, `FINAL_RECEIPT.json`: 입력·B2 동결·개발→확인 순서·0 device session.
- `run_v1/metrics.csv`: 192개 정책×시나리오×profile×seed PC 실행의 계획 분모·응답·120초 에너지·AP.
- `run_v1/summary.csv`, `paired_differences.csv`: 조건별 두 seed 요약과 CPU/B2/B3 대비 같은 seed 차이.
- `run_v1/decision_trace.csv`, `assignment_differences.csv`: 새 정책의 배정·대기·fallback 근거와 기존 정책의 dispatch 차이.
- `run_v1/decision_cost_stress.csv`: 이미 본 개발 seed에만 5 ms 판단 비용을 적용한 사후 스트레스.
- [대표 SVG](run_v1/comparison.svg): 결과 전에 정한 queue/thermal_cap/확인 seed301 한 조건. 유리한 조건 선정 그림이 아니다.

명령: `python -m tools.d1_arrival_thermal_feedback_batch --dry-run`; 전체 재계산이 필요한 경우 기존 출력을 덮어쓰지 말고 `python -m tools.d1_arrival_thermal_feedback_batch --output <새-폴더>`; `python -m tools.d1_arrival_thermal_feedback_analysis`; `python -m tools.d1_arrival_policy_screen --attach-thermal`. 작은 상대 경로 번들은 `../arrival_policy_screen_01/repro_bundle`을 별도 폴더로 복사하고 그 안에서 `python reproduce.py --bundle . --output ..`로 HTML을 byte-identical하게 재현한다.

[판독·한계](../../ARRIVAL_THERMAL_FEEDBACK_PC_20260927.md): PC 모형 탐색 결과이며 현재 두 모델의 기기 전체 전력·열 상태는 실측으로 보정되지 않았다. AP는 BAT가 아니고 실기기 절감/열 한도 PASS는 없다. 새 정책은 Android에 구현되지 않았고 `experiment_ready=false`다.
