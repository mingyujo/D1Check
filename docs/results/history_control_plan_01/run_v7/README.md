# 이력 통제 원모형 전이 확인 — 최종12자료

[한국어최종보고서](../../../ENERGY_AP_HISTORY_FINAL_RESULTS_20261008.md) · [대시보드](index.html) · [조건별metrics](metrics.csv) · [누적소비](summary.json) · [물리세션](physical_sessions.csv)

개발6/원모형별도확인6・모형coeff불변. 새g0.162는개발gate실패후미채택・사전고정보조비교. 원모형은새개발자료로재적합하지않았다. 실제일정조건부A・부하전AP/유휴power입력이며새online B검증이나정책효과가아니다. J0~120초/AP약35~180초・각정확APquery시점과표본수를metrics.csv에표시한다. rawcurrent=mA해석은조건부, 절대J정확도미인증.

## 공유 파일

- metrics.csv/aggregates.json: 개발과확인・원모형과미채택g구분, 모든조건악화포함.
- sessions.csv: 실제target유휴/CG_DC점유・cooling전류미coverage/nullable fullJ.
- energy_parts.csv: pre/loadspan/post잔차. 30초CPU의+0.054J는큰오차상쇄가있다.
- ap_paths/energy_paths.csv, paths/residual/delta_ap_{development,confirmation}.png: 절대경로/부호잔차/각첫scoredAP대비진단delta. delta는사후보정모형아님.
- physical_runs/sessions.csv:원계획실패/동일sessionID read-only복사중복제거. v7세부808→904 예산차이를 summary/보고서에서공개한다.

## 재현

저장소루트・기존Python311/numpy/matplotlib로실행한다. ADB・fit・새model선택없다.

```powershell
python -X utf8 -B docs/results/history_control_plan_01/run_v7/reproduce.py --raw '<원본 energy_ap_history_recovery_run_v7>' --output output/history_final_reproduction
```

최종run_v7만으로조건별예측은재현하며sourceplan의activity_model.path는repo의`docs/results/online_policy_study_01/overnight_sustained_run01/model.json` SHA5682082a다. 모델파라미터/고정g/목적/계수동결은원history_candidate_freeze/receipt와모형hash를검사한다. physical ledger를완전히재현하려면동일상위폴더에run_v2~run_v6도필요하다. 각FINAL_RECEIPT, host_commands/*/context/client/start, sessions input_manifest/artifacts또는failure_prefix/progress를읽는다.

최종run_v7의존: primary/frozen_collection_plan/FINAL_RECEIPT/original_model_freeze/history_candidate_freeze/history_freeze_receipt/installation, 모든00~11 input_manifest/validated/artifacts(progress/cleanup/request/conditioning_request/common/history_boundary)/thermal.jsonl・root claim/parent_receipt. 대용량trace/모델binary/키/기기식별원문은Git에넣지않았다. 차단/미회수/nullable값을0으로채우지않는다. conditionalframe예측이므로실측미래lane시각은A입력이며B 예측능력을뜻하지않는다.

`contrast_diagnostic.csv`는명목조건을맞춘순차CPU/PAR의차이예측오차진단이다. 초기조건차이・비무작위배치를정책짝효과로해석하지않는다. 확인180초에서부호가달라소수J순위만으로정책선택하지않는다.
