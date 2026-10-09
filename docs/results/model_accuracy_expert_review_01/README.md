# 에너지·AP 모형 개선 토론

세 관점 AI의 독립 검토·직접 반론·재토론3차와 기존 자료의0fit 진단이다. 전문가 자격 인증·새 실측 결과·새 모형 채택이 아니다.

- [결론·해결 순서·조건부 실측](../../MODEL_ACCURACY_EXPERT_REVIEW_20261010.md)
- [결과 화면](index.html), [구체적 후속 계획](consensus_plan.json)
- [세 검토 기록·hash](review_manifest.json), [에너지·열](reviews/energy_thermal_review.md), [식별·확인](reviews/identification_validation_review.md), [시뮬레이션·정책](reviews/simulation_policy_review.md)
- [성분·최근20초 초기화 진단](diagnostics_02/energy_component_diagnostics.csv), [같은 시계의 전력창](diagnostics_02/canonical_power_windows.csv)
- [고정 AP 빠른/느린 항 분해](diagnostics_02/AP_component_diagnostics.csv), [LOAD 같은 J/AP 창](diagnostics_02/LOAD_A_LONG_matched_window.json)
- [CPU/PAR 차이](diagnostics_02/paired_difference_diagnostics.csv), [그룹별 악화 포함 요약](diagnostics_02/summary.json), [검증](verification.json)

`diagnostics_01`은 주 검토자가 새로 만든 초안의 정책 방향 처리 오류까지 보존한 이력이다. 최종 정책 차이는 ID로 방향을 고친`diagnostics_02`만 사용한다. [수정 사유](diagnostics_01/diagnostic_correction.json). 원모형·원자료의 오류였다고 표현하지 않는다.

```powershell
python -B -m unittest tools.test_d1_model_accuracy_expert_diagnostics -v
python -B -m tools.d1_model_accuracy_expert_diagnostics --output output/model_accuracy_expert_reproduce
python -B docs/results/model_accuracy_expert_review_01/plot_results.py --output output/model_accuracy_expert_figures
```

작은 공유 입력과 CSV만 필요하다. 진단은 기존 저장 후보 p4/δ와 개발fold를 읽고, AP 고정 재생2회만 한다. 물리 계수fit·정책환경 배치·기기 명령0회다. NumPy/Matplotlib와 한글 글꼴은 기존 PC 분석 환경을 사용한다. 출력 폴더는 새 경로여야 하며 종료·소비된 기기 계획과 무관하다.

이번 해법은 조건부 A 비용 예측의 제한 개선이다. 향후 입력부터의 종단간B·정책 차이·전 기기 적용·절대J 인증으로 승격하지 않는다. 기존 에너지/AP 계수·기본/RL/strict/experiment_ready=false를 보존한다.
