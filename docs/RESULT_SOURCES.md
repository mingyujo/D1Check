# 발표 수치와 원자료 대응

첨부 PDF는 원본을 보존했습니다. 아래 표가 현재 공개된 저장 자료의 정책·조건을 구분하는 안내입니다. 수치를 맞추기 위해 원시 결과를 변경하지 않았습니다.

| 내용 | 공개 자료 위치 | 주의점 |
|---|---|---|
| 기기별 CPU/GPU 기본 전력·1회 소비 차이 | `a24/docs/results/energy_thermal_pc_01/condition_energy_summary.csv` | 기본 MobileNet·100% duty·60초·조건별 5회 중앙값. 현재 두 모델/NPU 실험과 다름 |
| A24 최신 교사규칙 전체/긴급/일반 100% | `a24/a24_simulator/results/A24_S26_MATCHED_BC_20261022_01/SUMMARY.json`와 `RESULT.json` | `PRIMARY`, `TEACHER_MATCH`. 안전여유 보완 교사이며 NN을 사용하지 않음 |
| A24 동일 최신 입력의 기존/재학습 BC | 같은 폴더의 전체 9정책·각 원시 결과 | 기존 BC와 재학습 BC 모두 전체 99.9512%. 교사 100%와 구분 |
| A24 앞선 발표용 수치 | `a24/a24_simulator/results/A24_S26_JOINT_20261022_01/CONF_POLICY_TABLE.csv` | `N512_B8_L25`, BC 전체 99.8535%·긴급 99.7656%, 최신 draw와 혼합 금지 |
| A24 입력규모·구성비 민감도 | `a24/a24_simulator/results/A24_S26_SENSITIVITY_20261022_01/` | 기존 160회 자료의 후속 분석. 과부하·구성별 손해 포함 |
| S26 4방법 주 결과 | `s26/s26_simulator/publications/rolling_atc_bc_candidate_20261021/FOUR_POLICY_DATA.json` | FIFO·EDF·RR·OURS×4입력, 각 `raw_path`와 해시로 연결 |
| S26 확장 32입력·악화 조건 | `s26/s26_simulator/experiments/bc_service_refinement_20261020/ANALYSIS.json`와 원시 결과 | 개발 자료에서의 EDF 비교. 105%·32건 묶음·분류75%에서 역효과 |
| A24 온도 모형 개발 평가 | `a24/a24_simulator/results/A24_THERMAL_DIRECTION_20261021_02/` | 그룹 분리 개발 평가. 정책 적용 검증과 구분 |
| S26 온도 모형 개발 평가 | `s26/s26_simulator/experiments/thermal_direction_causes_20261022/` | 같은 pool 후속 OOF 개발 비교. 독립 기기 검증 아님 |

A24 최신 참고 비교의 정책 계약은 `TEACHER_MATCH_CONTRACT.json`, TRAIN 안전여유는 `RISK_CALIBRATION.json`, 소스·입력 고정 기록은 `a24/a24_simulator/experiments/a24_s26_matched_bc_20261022/OPERATION.json`에 있습니다. 고부하·보조 입력과 BC 비교군도 같은 결과 폴더에 보존합니다.

과거 실험의 매니페스트·봉인은 당시 원래 경로와 초안 문서를 가리킬 수 있습니다. 초안 문서는 비공개 백업에 있고, 현재 공개 파일의 완전성은 최상위 `data/FILES.json`으로 확인합니다. 원래 매니페스트와 과거 상태 표시는 출처 기록으로 원바이트를 유지했습니다.
