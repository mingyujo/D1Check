# 에너지 4계수 후보 + 고정 AP 비용 API

제안만 남기지 않고 개발4의 세션 제외 추정·최종 추정5회와 기존35세션 평가를 완료했다. 새 에너지 후보와 고정 LOAD_SLOW를 별도 opt-in으로 계산한다. 기존 기본/RL/strict는 보존한다.

- [결과·한계·정확한 창](../../ENERGY_AP_ZERO_OFFSET_RESULTS_20261010.md) / [대시보드](index.html)
- [추정 전 등록](registration.json) / [개발 잔차·rank](preflight.json) / [동결 receipt](run_v1/fit_receipt.json) / [후보](run_v1/candidate.json)
- [모든J창](run_v1/energy_errors.csv) / [같은 J/AP 창](run_v1/matched_joint_errors.csv) / [AP 역할](run_v1/AP_evidence.json)
- [과거 그룹](run_v1/archive_groups.csv) / [악화](run_v1/retained_worsening.csv) / [상쇄·bin 포함시간](run_v1/cancellation.csv) / [전체 bins](run_v1/sensor_resolution_bins.csv)
- [저장 예정일정 B 비용](run_v1/stored_B_energy_errors.csv) / [B 요약](run_v1/stored_B_summary.json) / [CPU/PAR 차이](run_v1/paired_errors.csv)
- [기존 기록의 초기정보 가용시각](preload_availability.json) / [6맥락](recorded_contexts.json) / [guarded 예제](run_v1/guarded_examples.json) / [검증](verification.json)

```powershell
# fit/기기 없이 개선 비용 API를 호출한다. 출력은 새 파일이어야 한다.
python -B docs/results/energy_ap_zero_offset_01/run_example.py --opt-in --window matched --output output/zero_offset_LOAD_example.json
python -B -m unittest tools.test_d1_energy_ap_zero_offset -v
# 별도 재현. 기존 완료 run_v1을 덮거나 반복 소비하지 않는다.
python -B -m tools.d1_energy_ap_zero_offset --action fit --output output/zero_offset_reproduce
python -B -m tools.d1_energy_ap_zero_offset --action evaluate --output output/zero_offset_reproduce
python -B docs/results/energy_ap_zero_offset_01/plot_results.py --output output/zero_offset_figures
```

PC 환경은 기존 Python311/NumPy/Matplotlib 및 한글 글꼴을 사용한다. 분석과 예제에는 저장소의 작은 공유 입력·CSV만 필요하다. `preload_availability.json`은 기존 원journal에서 얻은 evidence 요약이며 현재기기 조회나 하드웨어 갱신시각 보장이 아니다. 원journal은 기존 external root에 보존하고 공유하지 않았다.

`guarded_examples.json`의 개발4 에너지는 최종후보의 in-sample API 동작 예제다. 개발LOSO 에너지는 `energy_errors.csv`를 사용한다. 고정 AP 개발 재생도 in-sample이며 이미 저장된 AP LOSO 검증과 구분한다. 새 에너지의 긴2 평가는 이미 결과를 본 자료의 사후 평가다.

수치평가 완료 뒤 NumPy 정수 CLI 직렬화 오류가 발생했다. [오류](run_v1/CLI_OUTPUT_FAILURE.json), 원 추정 [소스](frozen_sources/d1_energy_ap_zero_offset.py), [수정 hash/AST 불변](source_amendment.json)을 보존했다. 완료 수치·candidate·registration은 불변이며 다시 학습하지 않았다. 초기 잔차표 오류도 [보존](preflight_reporting_failure.json)했다.

원자료·원모형·AP후보·기본/RL/strict·experiment_ready=false 유지. 전체 정확도PASS/정책 우월성/새 독립 확인은 아니며 기기·ADB·설치·실측·빌드0회다.
