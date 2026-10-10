# AP와 기준전력 연결: 단순 후보 미채택·문제 분리 완료

[판독](../../AP_CONDITIONED_POWER_RESULTS_20261010.md) / [화면](index.html) / [사전 계약](analysis_contract.json) / [산술 진단 계약](attribution_contract.json) / [검증](verification.json).

개발 pre 정보만의 CPU/AP 계수2개＋같은창CPU 대조를 각각3회, 총6회 추정했다. 이미 본 확인6의 원계수120초 J MAE3.913→4.637J로 악화해 미채택한다. AP/원계수/기본/RL/strict·experiment_ready=false 불변·기기0.

- `run_v1/pre_features.json`, `pre_bins.csv`, `availability.csv`: AP·CPU·전력이 같은85/235초 구간에 존재하는 정보와 재사용한 기존AP초기상태. actual 일정은 이전registered_baseline 공유 파일을 읽기 전용으로 참조하여 중복 원본을 만들지 않았다.
- `run_v1/candidate_{MATCH_CPU,CPU_AP}_{30,180,final}.json`: 반대회복시간/최종개발 추정6개. AP slope는 부호 있는 관측관계이며 물리 계수/정확도PASS가 아니다.
- `run_v1/energy_errors.csv`, `energy_curves.csv`, `summary.csv`, `policy_difference_errors.csv`:12 전량·원/δ=0 head 모두·같은경계/부호/상쇄/악화/결측 분모. 좋은 head/ID를 선택하지 않는다.
- `readout_v1/AP_CPU_arithmetic.csv`: CPU 기울기 변경과 AP 항의 정확한 산술 분해.
- `readout_v1/C0_oracle_attribution.csv`: 미래 실측AP를 사용한 **진단전용 값**,4C0만 계산. 실행 전 예측·후보·선택 입력이 아니다. loaded AP를 무부하경로에 대입하지 않는다.
- `covariate_v1/C0_covariate_oracle.csv`: 기존 미래 other CPU 비율도 진단에만 대입한4C0 전량. 두 관측값을 알아도 남는 잔차이며 새 예측/후보가 아니다.
- `readout_v1/drift_and_baseline.csv`:35..120 평균과 post-lane 평균의 창을 명시·같은 post-lane 창 예측 평균 별도. 최초표/source는 `source_snapshots/`에 보존, 정식 J값/계수는 변경0.
- `readout_v1/feature_ranges.csv`: 관측 개발범위 밖 입력도 제외하지 않고 공개한다. scope를 넓힌 판정이 아니다.
- `figures/*.png/svg`: 전량 오차, 두C0의AP반응/누적잔차, 진단전용미래AP 대입. 새실측·정책효과 그림이 아니다.

```powershell
# 새 출력 경로만 사용; 아래는 fit/기기0
python -B -m unittest tools.test_d1_ap_conditioned_power -v
python -B docs/results/ap_conditioned_power_01/run_example.py --opt-in --output output/ap_conditioned_power_example.json
python -B docs/results/ap_conditioned_power_01/readout.py --output output/ap_conditioned_power_readout
python -B docs/results/ap_conditioned_power_01/covariate_attribution.py --output output/ap_conditioned_power_covariates
python -B docs/results/ap_conditioned_power_01/plot_results.py --output output/ap_conditioned_power_figures
```

실제로 사용한 분석 명령:

```powershell
python -B -m tools.d1_ap_conditioned_power --action prepare --output docs/results/ap_conditioned_power_01/run_v1
python -B -m tools.d1_ap_conditioned_power --action run --output docs/results/ap_conditioned_power_01/run_v1
python -B docs/results/ap_conditioned_power_01/readout.py --output docs/results/ap_conditioned_power_01/readout_v1
```

run_v1은 소비된PC분석이며 자동재실행을 차단한다. 고의적 재현에는 별도새출력을 지정한다. 기존 결과를 이용하는 공유 예제를 우선한다. 전체 분석도 이미 공유된 작은 입력만 필요하며 새raw trace export·기기 명령이 없다.

필수 파일은 `../registered_baseline_01/run_v1/{pre_bins.csv,pre_inputs.json,candidate_*.json}`, `../preboundary_evidence_01/run_v1/{expanded_pre.json,initial_states.csv}` 및 registration의 원식/AP/δ=0과 기존 공유 입력이다. 초기R/H를 다시 맞추지 않고 기존결과/마지막AP·시각과 일치시켰다. β/prepτ30을 고정한 no-target-work 경로는 실제loadedAP의 보편적 예측이나 주변온도 인증이 아니다.

Android BOOTTIME 상대축·기존 current raw=mA·10초 AP/2.5초 전력 gap 규칙을 유지한다. CSV전달은 종료 후이며 실시간 feature 수집/전달은 미구현이다. A24 절대J 미인증·사후평가·기기별계수비혼합, 모델binary/APK/키/대용량원본/기기식별값 공유0을 유지한다.
