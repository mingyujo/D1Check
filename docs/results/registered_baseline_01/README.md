# 등록회복 전체 기준전력: 국소 개선·전체 교체 보류

[결과](../../REGISTERED_BASELINE_RESULTS_20261010.md) / [화면](index.html) / [일차 계약](analysis_contract.json) / [이차 사후 계약](secondary_readout_contract.json) / [검증](verification.json).

개발6·회복시간 block 제외2＋최종1회로 pre CPU/전력 계수 하나를 추정했다. 이미 본 확인6의 작업 후 유휴 절대J 평균2.921→2.176. 기존 δ=0 계수의 전체120초 평균4.564→4.000이지만 원식3.913보다 높고 최악/정책 차이 악화가 있어 기본 교체를 보류한다. AP·RL·strict·experiment_ready=false 불변, 기기0.

- `run_v1/pre_inputs.json`, `pre_bins.csv`, `availability.csv`: registered recovery 뒤90/240초의 pre 입력·실제 일정·경계. 미래 센서/전력/CPU는 없으며 일정은 조건부 예측용이다.
- `run_v1/candidate_{30,180,final}.json`: development-only3fit, 계수1개, 기존4전력계수/모형/AP는 별도 유지.
- `run_v1/energy_errors.csv`, `energy_curves.csv`, `summary.csv`, `feature_ranges.csv`: 전량/결측/부호/상쇄/악화/관측 밖 특성 표시. 유리한 세션을 제외 선택하지 않는다.
- `readout_v1/fixed_head_*.csv`: 원계수와 δ=0 계수×기준값3종의 사후 분해. 새 후보 선택·재추정은 없다.
- `readout_v1/policy_difference_errors.csv`: CPU−PAR 차이 오차, 같은 초기조건의 인과효과로 해석하지 않는다.
- `joint_v1/all_sessions.csv`, `summary.csv`: 기존 고정 LOAD_SLOW AP의 초기정보 비교를35..120초에서 다시 점수화해 J0..120과 결합한 사후 표. 원 동결 AP 식 비교가 아니며 good ID 선택기·새AP fit/재생0이다.
- `figures/*.png/svg`: 모든 세션, C0 잔차의 상쇄 및 반례, 정책 차이 악화. 실제 새 기기 측정이 아니다.

공유 저장소만으로 추정 없이 재현:

```powershell
python -B -m unittest tools.test_d1_registered_baseline -v
python -B docs/results/registered_baseline_01/run_example.py --opt-in --output output/registered_baseline_example.json
python -B docs/results/registered_baseline_01/readout.py --output output/registered_baseline_readout
python -B docs/results/registered_baseline_01/joint_readout.py --output output/registered_baseline_joint
python -B docs/results/registered_baseline_01/plot_results.py --output output/registered_baseline_figures
```

각 출력은 새 경로여야 한다. 예제의 power head는 일차 평가의 기존 δ=0으로 명시 고정한다. live CPU 수집/전달 기능은 없으며 CSV는 종료 후 export였다. `readout`은 raw data root가 없으면 원본 해시 재확인 개수를0으로 표시하며 데이터/관측을0으로 대체하지 않는다.7 unit검증은 실기기 검증이 아니다.

실제로 사용한 원본 의존 분석 명령:

```powershell
python -B -m tools.d1_registered_baseline --action prepare --external-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension' --output docs/results/registered_baseline_01/run_v1
python -B -m tools.d1_registered_baseline --action run --output docs/results/registered_baseline_01/run_v1
python -B docs/results/registered_baseline_01/readout.py --output docs/results/registered_baseline_01/readout_v1 --external-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension'
```

run_v1은 완료되어 차단된다. 의도적인 원본 재현에는 별도 새 출력·데이터 루트를 지정한다. 우선 공유 예제로 확인하며 정식 추정을 불필요하게 다시 하지 않는다.

원본은 `../cpu_prebaseline_01/run_v1/source_inventory.json`의12 source_locations와해시를 따른다. 각 폴더의 `artifacts/{history_boundary,conditioning_requests}.json`, `trace_export/{sched,clock,loss,cpu}.csv`, `trace_export/{audit,export_binding}.json`가 필요하다. raw 검증에는 `thermal.jsonl`, `system_activity.pftrace`도 필요하다. 정상 source와반대 역할을임의대체하지않는다. APK/키/모델binary/대용량원본/기기식별값은공유하지않았다.

공통창 적분은 기존 raw=mA 해석, 전압과2.5초 최대 표본공백 규칙을 그대로 따른다. 절대 에너지 정확도 미인증·사후 분석·진단 외삽·기기별 계수 비혼합을 유지한다.
