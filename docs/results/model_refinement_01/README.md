# 기존 실측 모형 후보: 사후 평가

[판정](../../MODEL_REFINEMENT_EXISTING_DATA_20261007.md) · [화면](index.html). 개발3/평가14, 후보3 모두 기본채택하지 않음.

저장소 루트의 기존Python/numpy/matplotlib 환경에서 실행한다. 새 출력경로가 필요하다.

```powershell
python -B -m unittest tools.test_d1_model_refinement -v
python -B -m tools.d1_model_refinement analyze --inputs docs/results/model_refinement_01/inputs.json.gz --output output/model_refinement_reproduce_v1
```

공유 센서·일정 축약본(압축164KB)만 사용해 동일개발3 적합과136A/B평가를 재현한다. 새정책/학습/기기호출이 아니다. 계약은 contract.json. 이미 본 확인자료이므로 사후평가다.

그림만 재생성: `python -B -m tools.d1_model_refinement plot --output <결과폴더>`. 해당폴더PNG/index.html을 다시쓰므로 별도복사본에서 사용한다.

원본대조:

```powershell
python -B -m tools.d1_model_refinement audit-raw --external C:/Users/LG/Documents/D1Check_Arrival_Extension --output output/model_refinement_raw_reproduce_v1
python -B -m tools.d1_model_refinement extract --external C:/Users/LG/Documents/D1Check_Arrival_Extension --output output/model_refinement_extract_reproduce_v1
```

필요원본: separated_power_run_v4의development/confirmation_cases.json 및 *_evaluation.json, 실제출처separated_power_run_v1/v2/v4의9세션progress/requests/common_boundary/thermal, sustained_confirmation_plan_v1/collection_plan.json과sustained_confirmation_run_v1의8세션. 정확한 상대경로/SHA는 source_inventory.json/raw_cache_audit.json.

- session_errors.csv: 같은창J부호/절대/상대·부하전/중/후·AP MAE/최대/피크/방향. A/B별도. post_ap_mae는120초까지, whole_cooling_ap_mae는마지막AP까지.
- comparison.csv/condition_comparison.csv: 블록·정책별 평균과 악화. 센서표본≠독립실행.
- windows.csv:5초J구간과실제상태혼합. paths.csv.gz:모든A/B누적J/AP/잔차CSV압축, 결측0대체없음.
- paired_errors.csv:지속4쌍정책차이오차. 인과효과/미래오차한도 아님.
- candidates.json/development_loso.csv:별도계수·개발제외선택, 기본승격없음.
- inputs.json.gz:기기식별값/request UUID제외 재현입력. 실제센서 및 동결도착/실제일정. 모형바이너리 아님.
- data_audit.csv:표본간격·공백·반복값·bracket·적분재현. 조회주기≠센서내부갱신주기.
- 그림은조건부A. 회색35초~마지막lane은부하가존재할수있는전체구간이며 내부유휴/병행은windows.csv.

원모형SHA5682082a…·기본/RL/strict/experiment_ready=false불변. raw=mA조건부·절대에너지미인증.
