# 같은 PPO learner32→512 학습량 비교

**세 seed 모두512까지 실제학습했지만, 새 확인48조건에서Band 대비추가우위는확인하지못했다.** 개발점 성적은비단조였고새자료로같게일반화되지않았다. 원전조건 판정은모두FAIL이며수렴완료·강화학습 일반실패를뜻하지않는다.

[오프라인 결과 화면](index.html) · [상세 방법·보고서](../../OVERNIGHT_RL_AMOUNT_20261011.md) · [전체1008행](comparison.csv) · [정책 요약](summary.csv) · [조건별 대응 차이](paired_differences.csv)

| 확인48 정책 | 일반 기한 실패 | 긴급P95 조건평균 ms | 에너지 조건평균 J | 최고AP 조건평균 °C |
|---|---:|---:|---:|---:|
| 리스트 L0 |45|356.273|152.348137|30.465906|
| Band 판단규칙 대응 |42|361.862|152.285040|30.463676|
| Triton 판단규칙 대응 |42|405.056|152.767088|30.482239|
| 같은 후보 비학습 Rule |45|356.273|152.197866|30.456615|
| PPO seed11/23 각각512 |45|356.273|152.292797|30.463565|
| PPO seed37,512 |45|356.273|152.302553|30.463689|

각정책3168/3168완료·긴급기한실패0. 신규2688환경/1440학습·177408/177408요청·native실패0·호스트저장실패1보존·기기/fit/NPU/seed교체/보상튜닝0다. 원32 actor/critic/Adam/RNG/승수/커서를그대로연장했고, 누적64/128/256/512의개발24를세seed 모두평가했다. 신규확인4도착seed×4부하×3문맥48은최고seed/checkpoint선정없이terminal512 세개를사용했다.

그림은 쉬운한국어명과원단위를사용했다. [학습량](01_learning_amount.png) · [확인KPI](02_final_kpi.png) · [조건 지도](03_condition_map.png) · [시간표/AP](04_schedule_ap.png) · [실제학습지표](05_learning_activity.png). 시간표는 각정책 아래CPU/위GPU, 파랑분류/주황탐지이며막대끝은actual AVAILABLE다. 대표는결과전에고정한첫확인seed/sustained/mean 조건9다. AP는내부모형채널이고표면온도·안전한도가아니다. 작은차이는실기기절감으로확정하지않는다.

[학습update/gradient/λJ/entropy](learning_updates.csv) · [episode 비용](learning_episodes.csv) · [checkpoint별선택](training_diagnostics.json) · [정확일정비교](schedule_equivalence.csv) · [판단/대기/자원](decisions.csv) · [추가실패요청](added_service_failures.csv) · [첫입력alias검산](initial_input_aliases.json) · [부하별차이](family_differences.csv) · [기술적4seed구간](descriptive_intervals.csv).

terminal512에서cooling은모두0, resource-wait는11/23 각86회·37은72회다. NoWait는두대기를함께막고, 일반45를42로줄이지못했다. 같은burst/22 요청의3비용문맥이Band보다늦었고, 최초기록분기는앞분류를Band GPU/PPO CPU로배정하는차이였다. 이를냉각의추가실패라고전제하지않는다. 원L0 참조/개별긴급응답 admission/미래도착불명·후속CPU보호의차이를후속기전검사대상으로남긴다.

[실행계약](execution_contract.json) · [입력생성계획](input_plan.json) · [정책ID/구조](policy_definitions.json) · [소스원형과host수정](source_identity.json) · [모형/원32동일버전](runtime_versions.json) · [15archive 전체상태비교](checkpoint_roundtrip.json) · [최종검증](verification.json) · [그림검증](figure_verification.json) · [브라우저검증](browser_verification.json).

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -X utf8 -m unittest tools.test_d1_overnight_rl_amount tools.test_d1_overnight_rl_host -v
python -B -X utf8 -m tools.d1_overnight_rl_check
python -B -X utf8 -m tools.d1_overnight_rl_artifact_check
```

공유checker는clean clone에서원PT/gz가없어도읽기검증만한다. 완료실험재분석은로컬자료가있을때 `python -B -X utf8 -m tools.d1_overnight_rl_report report`다. 본실행은 `tools.d1_overnight_rl_amount register`/`run`이며동일task 재등록·clock/상한초기화는금지한다. 학습cap은1440/1440로닫혔고남은native384를자동재개하지않는다. source_versions는실행한host driver의원byte를보존하므로line-ending 정리대상이아니다. raw/PT/전체학습trace는로컬 `output/overnight_rl_20261011_v1` 보존·비공유이며compact seed/generator/SHA만공유한다. 이문서의누적13009/2989는원10321/1549＋이번RL만이며다른동시작업은통합보고에서별도합산한다.
