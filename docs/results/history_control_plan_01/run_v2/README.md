# 이력 통제 캠페인 v2 — stopped/partial

[한국어 결과 보고서](../../../ENERGY_AP_HISTORY_RECOVERY_RUN02_20261008.md) · [요약](summary.json) · [호출/clock 시간축](timeline.csv) · [명령 종류/지연](command_delays.csv) · [실행 경계](execution_boundary.png)

적격 개발0/6·확인0/6, 후보 동결/새 J/AP 오차는 null. 104 추론의 durable 기록과 conditioning120초 경계만 확보했다. target 유휴반응·병행 평가·정확도 PASS 없음. 원모형과 기본/RL 환경을 변경하지 않는다.

## 재현

저장소 루트에서 실행한다. Python311의 기존 numpy/matplotlib을 사용한다.

```powershell
python -X utf8 -B docs/results/history_control_plan_01/run_v2/reproduce.py --raw '<원본 energy_ap_history_recovery_run_v2 폴더>' --output output/history_recovery_readout
```

원자료 의존성: primary/FINAL_RECEIPT.json, frozen_collection_plan.json, original_model_freeze.json, installation/installation_receipt.json, host_commands/*/client/{result.json,stdout.bin}, 첫00_* 세션의 failure_prefix/{progress.jsonl,conditioning_common_boundary.json,conditioning_requests.json,*.invalid.bin}, start_ap_gate/host_approval.json, failure_host_cleanup.json, root claim.json/primary_campaign_receipt.json. 활동모형의 정확한 파일은 frozen plan의 activity_model.path/SHA를 읽는다. 개인 절대 경로가 필요한 원본과 모형 위치는 plan 바인딩에서 확인하며 원문·기기 식별정보는 공유하지 않는다.

CSV/요약은 원본 재현. 두 패널 clock origin은 다르며 직접 정렬하지 않았다. PNG/SVG는 실패 진행 경계이며 실측–예측 정확도 그림이 아니다. null은 계산 불가, 0을 대신 넣지 않는다.
