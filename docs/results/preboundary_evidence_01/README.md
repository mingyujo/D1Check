# 실제 근거: 초기정보 누락과 기준전력 구간의 활동 변화

- [결과·근거·확인된 다음 질문](../../PREBOUNDARY_EVIDENCE_RESULTS_20261010.md) / [화면](index.html)
- [등록된 한 초기화 변경](registration.json) / [확보량·같은anchor](run_v1/availability.csv) / [복원pre 입력](run_v1/expanded_pre.json)
- [12세션 AP 오차](run_v1/AP_metrics.csv) / [지역초기상태](run_v1/initial_states.csv) / [역할별 평균](run_v1/combined_readout.csv)
- [후보계수로 바뀌지 않는 유휴J](run_v1/idle_energy_attribution.csv) / [4C0의 CPU/전력](run_v1/matched_C0_CPU_context.csv) / [trace export hash](run_v1/trace_evidence_inventory.json)
- [부하 전 선택규칙 등록](preonly_choice_registration.json) / [적용·실패 포함](run_v1/preonly_choice.csv) / [원자료 hash](run_v1/source_inventory.json) / [검증](verification.json)

```powershell
python -B -m unittest tools.test_d1_preboundary_evidence -v
python -B docs/results/preboundary_evidence_01/run_example.py --opt-in --output output/preboundary_C0.json
python -B docs/results/preboundary_evidence_01/plot_results.py --output output/preboundary_figures
```

공유 입력과 기존 Python/NumPy/Matplotlib만으로 기록AP 예제·그림을 재현한다. extractor의 원자료 의존은 `source_inventory.json`의36파일이며 원본hash로이전v6/v7재사용자료를찾았다. raw thermal/conditioning/Perfetto대용량CSV·키·APK·기기식별값은공유하지않는다. trace분석은이미검증한export를읽은요약이고새TraceProcessor나기기명령은실행하지않았다.

초기화 후보는예측전입력만더사용한다. 계수재보정·현재기기gate·모형정확도PASS가아니다. 계수/β/τ와최종AP anchor가동일한상태에서원짧은pre와등록회복pre를비교했다. 관측postAP는점수산출에만썼다. AP개발6악화와확인6개선/peak악화를동시에보존하며주사용모형은유지한다.

세번째행동인부하전한표본선택은정식추정이아닌별도pre-only검사로추가등록했다. 이규칙도전량보존하고확인6의미미한개선/중요C0선택실패로미채택했다. 새holdout길이·window·threshold를반복탐색하지않는다. 전역계수fit0·데이터AP경로36이다. 지역상태는정적입력24종·선택단계36회와진단저장을위한같은초기화재계산24회를구분해총84호출로기록했다. [계산량](run_v1/state_computation_counts.json)에시험/예제의추가5호출도분리했다.

결론은AP 초기정보활용의개선근거와에너지기준전력의실제활동변동이다. 미래CPU를알았다고가정하거나CPU seconds를J로바꾸지않는다. 원자료·기본/RL/strict·experiment_ready=false 보존·ADB/기기/실측/설치/빌드/새계획/claim0이다.
