# 간섭 예상/실현 및 에너지·AP 별도 PC 진단

[오프라인 진단 탭](diagnostic.html)은 서버·CDN 없이 로컬 파일로 연다. [기존 결과 탭](../arrival_visualization_01/dashboard.html)과 분리되어 있으며 기존 `sensitivity.csv`·동결 P·B2·CAL-03 설정을 덮어쓰지 않는다. [한국어 판독과 한계](../../ARRIVAL_INTERFERENCE_ENERGY_DIAGNOSTIC_20260927.md).

| 자료 | CSV/설정 | PNG / SVG |
|---|---|---|
| 사전 진단 격자·출처 | [CONFIG.json](CONFIG.json) · [SHA-256](SOURCE_HASHES.json) | — |
| 5정책과 P 예상 3값의 seed별 지표 | [interference_metrics.csv](interference_metrics.csv) · [P−B3 쌍차](interference_paired.csv) · [요약](interference_summary.csv) | [low](interference_heatmap_low.png) / [SVG](interference_heatmap_low.svg), [queue](interference_heatmap_queue.png) / [SVG](interference_heatmap_queue.svg), [burst](interference_heatmap_burst.png) / [SVG](interference_heatmap_burst.svg) |
| 예상 맞음에도 남는 대표 대기·배정 | [queue/seed201 결정 기록](representative_queue_decisions.json) | — |
| 전력 선형식·상대차·대수적 경계 | [energy_boundaries.csv](energy_boundaries.csv) | [에너지 선](energy_power_lines.png) / [SVG](energy_power_lines.svg), [seed별 경계](energy_crossings.png) / [SVG](energy_crossings.svg) |
| AP 초기값·pair 평형 스트레스 | [ap_sensitivity.csv](ap_sensitivity.csv), [대표 경로 차이](ap_path_representative.csv) | [AP 최고](ap_stress.png) / [SVG](ap_stress.svg), [경로](ap_path_representative.png) / [SVG](ap_path_representative.svg) |

heatmap의 칸은 같은 평가 seed 5개의 P−B3 평균과 최소/최대다. 기한 미충족률은 예정 요청 전체 분모, 미완료는 별도 필드다. 병행 전력 그림은 idle1W/단일2W를 고정한 seed별 선이며, 전체 idle/단일 짝의 차이는 CSV에 있다. AP는 열 피드백이 없는 사후 1차 모형이다. 2–3W, 초기29/31°C, 병행 평형30/42°C는 실측 범위나 신뢰구간이 아니다. 고정870건 episode 평균을 상태별 전력으로 전용하지 않았다.

저장소 루트에서:

```powershell
python -m tools.d1_arrival_diagnostic --config docs/results/arrival_diagnostic_02/CONFIG.json --output docs/results/arrival_diagnostic_02
python -m unittest tools.test_d1_arrival_diagnostic tools.test_d1_arrival_energy_sensitivity tools.test_d1_arrival_visualize -v
```

첫 명령은 기존 외부 실측이나 Android를 호출하지 않고 Git의 동결 CAL-03 입력·기존 평가 도착을 사용한다. 이 진단에서는 explore PC 조합315개만 실행했으며 과거 전체960평가·126개발 배치를 반복하지 않았다. 출력 재생은 새 결과의 계산 일관성 확인이며 독립 실기기 검증이 아니다. `experiment_ready=false`다.
