# 결과 자료

발표 파일은 [발표자료.pdf](../presentation/발표자료.pdf)입니다. 저장된 실험 결과와 다른 표기는 아래에 구분했습니다.

## 발표자료 정정 사항

- 13·14쪽 A24: 최신 입력의 BC는 전체 2,047/2,048건(99.9512%), 긴급 1,279/1,280건(99.9219%)이 정시입니다. 전체·긴급·일반 100%는 `TEACHER_MATCH` 교사규칙 결과입니다.
- 13쪽의 정시 2,045건·EDF 대비 소비 1.12% 감소 등은 앞선 `A24_S26_JOINT_20261022_01` 입력의 BC 결과입니다. 최신 입력의 100% 결과와 합칠 수 없습니다.
- 13쪽 A24 소비의 단위 표기는 J*입니다. API-J는 S26에서 사용하는 표기입니다.
- 8쪽 온도 오차는 기존 측정 pool의 그룹 분리 개발 평가입니다. 새로운 독립 기기 실측 검증을 뜻하지 않습니다.

## 원자료 위치

| 내용 | 경로·조건 |
|---|---|
| 기본 CPU/GPU 전력·완료 1회 소비 | `a24/docs/results/energy_thermal_pc_01/condition_energy_summary.csv` — MobileNet, 100% duty, 60초, 조건별 5회 중앙값 |
| A24 보완 교사 100%·동일 입력의 BC 비교 | `a24/a24_simulator/results/A24_S26_MATCHED_BC_20261022_01/SUMMARY.json`, `RESULT.json` — `PRIMARY`, 9정책×4입력 |
| A24 앞선 BC 결과 | `a24/a24_simulator/results/A24_S26_JOINT_20261022_01/CONF_POLICY_TABLE.csv` — `N512_B8_L25`, 전체 99.8535%·긴급 99.7656% |
| A24 입력 민감도 | `a24/a24_simulator/results/A24_S26_SENSITIVITY_20261022_01/` — 저장 160회 자료의 분석 |
| S26 주 결과 | `s26/s26_simulator/publications/rolling_atc_bc_candidate_20261021/FOUR_POLICY_DATA.json` — 4정책×4입력, `raw_path`로 원자료 연결 |
| S26 확장 32입력 | `s26/s26_simulator/experiments/bc_service_refinement_20261020/ANALYSIS.json`와 원시 결과 — EDF 비교, 악화 조건 포함 |
| A24 온도 예측 | `a24/a24_simulator/results/A24_THERMAL_DIRECTION_20261021_02/` |
| S26 온도 예측 | `s26/s26_simulator/experiments/thermal_direction_causes_20261022/` |

A24 교사규칙의 정의는 결과 폴더의 `TEACHER_MATCH_CONTRACT.json`, 안전여유는 `RISK_CALIBRATION.json`에 있습니다. 입력·코드 버전은 `a24/a24_simulator/experiments/a24_s26_matched_bc_20261022/OPERATION.json`에 기록했습니다.

공개 파일의 경로·크기·SHA-256은 `data/FILES.json`을 기준으로 확인합니다. 원 실험의 매니페스트는 당시 경로와 상태를 보존한 기록이므로 현재 공개 폴더와 일부 경로가 다릅니다.
