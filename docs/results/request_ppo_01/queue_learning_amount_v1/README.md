# PPO 학습량 진단 결과와 재현

2026-10-07. [한국어 보고서](../../../REQUEST_PPO_LEARNING_AMOUNT_PC_20261007.md) · [그림](index.html) · [원 계약](analysis_contract.json) · [원 검증](verification.json).

기존6개 실행은 각1,024episode/128update, 최종192조건/2,112행 평가를 완료했다. 최종optimizer·RNG 누락으로 정확한 연장은0회였다. 새 상태 보존 코드는 과거 상태를 복구하지 않는다. 학습량 부족·수렴·강화학습 일반의 실패를 확정하지 않는다.

손상된 한국어 원문을 추정하지 않고 JSON·CSV·코드에서 확인되는 사실을 UTF-8로 재작성했다. 손상 원문은9e1975b에 보존한다. 최신 별도 승인 재학습은 [새 연구](../rules_rl_amount_v1/README.md)를 따른다.

- training_curve.csv:768update의 rollout/optimizer 표본·WAIT·학습 지표. 전체 환경transition은 미기록이다.
- validation_curve.csv:6실행×5시점=30행의 주24조건 검증.
- seed_accounting.csv:episode·선택update·적격성·누락 상태.
- policy_results.csv:11정책×주/과부하2층=22행. 같은 입력SHARED_EFT와 대응한다.
- PNG5종:transition·episode·seed·EFT 상충·소비. fixture는 효과 증거가 아니다.
- checkpoint_inventory.json:원 checkpoint/정확한 연장 차단. 대용량 원본은output에 있다.

원본 없이 공유 CSV에서 그림만 재현:

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/LG/AppData/Local/Programs/Python/Python311/python.exe' -B -m tools.d1_queue_ppo_learning_amount --action PlotShared --output output/queue_ppo_learning_amount_figures_reproduce_v1
```

원 checkpoint 검사와 읽기 전용 재분석(새 출력·학습0):

```powershell
& 'C:/Users/LG/AppData/Local/Programs/Python/Python311/python.exe' -B -m tools.d1_queue_ppo_learning_amount --action Check
# CHECK_BLOCKED_MISSING_STATE가 당시 자료의 정상 판정이다.
& 'C:/Users/LG/AppData/Local/Programs/Python/Python311/python.exe' -B -m tools.d1_queue_ppo_learning_amount --action Analyze --output output/queue_ppo_learning_amount_analysis_reproduce_v1
```

Check는 학습 상태를 재초기화하지 않는다. Analyze는 기존 결과만 판독한다. 원budget_stopped·후속completed·동결 모형/원자료/기본/strict/experiment_ready=false를 보존한다.
