# ENERGY-MEMORY30-01 — 고정 30초 잔차 평균 후보

[화면](index.html) · [전체 결과·악화 조건](../../POWER_RESIDUAL_STRUCTURE_RESULTS_20261008.md) · [선행 진단](../power_residual_structure_01/README.md) · [검증·해시](verification.json).

**특정 조건에서만 개선했고 기본 적용은 보류했다.** 개발 6세션에서 alpha 0.518654를 고정해 확인 6세션과 기존 지속 8세션에 적용했다. 개발 교차 선택 기준을 충족하지 못해 실제 선택 alpha는 0이다. 진단용 후보와 선택된 기본 경로를 구분한다. 자료는 모두 이미 열람한 사후 평가이며 센서 표본을 독립 세션으로 세지 않는다.

| 자료 | 원→후보 개별 10초 MAE J | 원→후보 합산 80초 순오차 J | 개별 악화 |
|---|---:|---:|---:|
| 확인 6 | 0.869570→0.847558 | 3.891405→2.149668 | 3/6 |
| 지속 8 | 0.843705→0.853802 | 4.614531→2.717514 | 4/8 |

합산 값은 35–115초의 8회 순차 예측을 합친 것이다. 발행마다 과거 관측이 추가되므로 한 번에 만든 미래 80초 예측이나 전체 120초 오차가 아니다. 미지원·제외 구간은 0으로 채우지 않는다. 실제 미래 lane 일정이 주어진 조건부 A이며 온라인 정책/B 예측이 아니다.

## PC 재현 명령

저장소 루트에서 실행한다. 공유된 이전 `rolling_forecast_01`·현재 `power_residual_structure_01`·계약의 모형 JSON과 Python/NumPy/Matplotlib만 필요하다. 새 출력 경로를 지정한다.

```powershell
python -X utf8 -B -m tools.d1_power_residual_structure --output output/power_structure_repro
python -X utf8 -B -m tools.d1_energy_memory30 --output output/energy_memory30_repro
python -X utf8 -B -m tools.d1_power_structure_readout
python -X utf8 -B -m unittest tools.test_d1_power_residual_structure -v
```

첫 명령은 공유된 입력으로 진단을 새 출력에 재현한다. 두 번째 명령은 계약 해시가 고정된 공유 진단 표를 읽고 개발 전용 적합·평가를 새 출력에 재현한다. 세 번째는 저장된 공유 결과로 이 폴더의 화면과 두 PNG를 다시 만드는 명령이며 계수 적합은 하지 않는다. 새 재현 결과를 원본 공유 결과에 덮어쓰지 않는다.

- `contract.json`: 후보 구조 1개, 과거 30초, horizon 10초, 개발/평가·비악화 선택 규칙·불변 조건.
- `candidate_freeze.json`: 개발 6세션 적합과 회복 이력 제외 교차평가. 평가 전에 저장한 UTC·계약 SHA. 재현 UTC만 달라지는 것은 정상이다.
- `window_errors.csv`: 20×8×4방식=640행. 원모형, 이전 10초 전량, 이전 10초 감쇠, 현재 30초 후보.
- `session_errors.csv`: 20×4방식=80행. 개별 오차와 부호 상쇄를 포함한 합산 오차를 별도 표시.
- `comparison.csv`: 3자료×4방식=12행. 모든 세션과 악화 개수를 포함.
- `summary.json`: 공식 후보 적합 3회(전체 개발+두 교차), 기본 적용/strict/정확도 합격/정책 우월성은 미채택·미판정.

`tools.d1_energy_memory30.predict(case, frozen, now, alpha)`는 실제 예측 진입이다. 지정된 35,45,…,105초만 허용하고 가용 과거 30초 평균을 사용한다. 160창의 진입 결과를 CSV와 대조했다. 미래 관측 변조와 평가 정답 변조를 분리해 테스트했다.

원모형 SHA `5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2` 불변. AP·기본 시뮬레이터·RL·strict·experiment_ready=false 유지. 기기 명령·ADB·실측·정책 환경·학습·APK·새 claim은 0이다. 전류 raw=mA는 기존 조건부 해석이며 절대 에너지 정확도를 인증하지 않는다.
