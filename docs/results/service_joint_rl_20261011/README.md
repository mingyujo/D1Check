# 공동 서비스 리스트 기반 새 PPO

재현 경계: 이번 실행은 **초기화 seed가 다른 세 모델＋공유 round-robin sampling RNG**이며 독립적인 세 학습 stream이 아니다. 원실행 bytes는 변경하지 않았다. 각 archive의 전체 복원 PASS를 전체 세 learner 중지/연속학습 동일성으로 확대하지 않는다. desktop 연장은 전learner payload＋마지막 session RNG＋case/next-seed 커서를 함께 보존해야 한다. 별도의 독립3stream 실험은 같은64의연장이 아니라새fresh 설계다.

**세 seed 모두64까지 새로학습했지만최종채택기준은모두FAIL이다.** 같은후보의기준이던JointList도Band 대비긴급P95를악화시켰고, 새PPO는속도를유지하면서J/AP를악화시키거나JointList에머물렀다. 기존512의수렴/알고리즘실패판정이아니다.

[오프라인 화면](index.html) · [원단위48조건](comparison.csv) · [요약](summary.csv) · [선택성](selection_diagnostics.json) · [실제학습](learning_updates.csv) · [6archive복원](checkpoint_roundtrip.json) · [원판정](original_gate.json).

- 신규500/512환경·192/192학습·실패0·기기/fit/NPU0. 3seed11/23/37 각각32→64,최종8update·Adam96이다. 같은32개발mean8·64개발24·833110101..104확인48을모두사용했다. 최고seed선정0·기존32/512weights재사용0이다.
- 새로운schema와objective는6critic/56state/8×28architecture 및원PPOsettings/gamma1을유지한다. 학습참조·예측후속·기본·복귀는새JointList다. 원상태벡터의`is_L0`열이름은호환alias이며새slot0 JointRef의flag를뜻한다. 순수알고리즘우열비교로해석하지않는다.
- 5cost 순서는 `[J−JointRefJ, absolute incomplete count, absolute urgent failure count, absolute normal failure count, positive(P95−JointRefP95)/1500]`다. absolute와relative excess를더해두번계산하지않는다. excess는진단만기록하고기존rawcount1/1J/1500ms scale을유지했다. AP는기존telescoping 주보상이며새JointRef에정렬한다.
- 확인48은정책별3168/3168완료·urgent실패0·normal42다. seed11/37은P95354.076ms(=Band),J152.572742/AP30.466348로Band J152.269130/AP30.454384보다악화한다. seed23은JointList와동일한P95398.753ms/J152.273043/AP30.454179로P95가악화한다. 원zero-epsilon 조건별gate·완료량·기한계약은유지했다.
- 각seed의허용된예측AP/J 공동비악화+한축개선슬롯은0이다. mask전후는11/37 각906→0,23은866→0이다. seed11/37 비참조선택각404,23은0이며λJ/gradient/Adam이작동했어도허용된예측개선선택이없는구조와분리해읽는다. source/가중치를V2 후보에조용히전용하지않는다.
- 등록뒤snapshot표시1줄 `admissions[0]=JointList_reference` 변경을발견해26native/학습0 경계에서멈췄다. 원bytes exact SHA로보존하고state/candidate/mask/forecast/행동/보상변경0인수정계약을기록해재사용했으며clock/cap/seed 초기화0다. 등록의imported-module closure에서빠졌던`__main__`runner도원실행bytes/추가SHA로보완했다. 원예산·원FAIL은보존한다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -X utf8 -m unittest tools.test_d1_service_joint_rl_cost -v
python -B -X utf8 -m tools.d1_service_joint_rl_check
python -B -X utf8 -m tools.d1_service_joint_rl_report report
```

checker는소스줄바꿈을LF 정규화해검증하되 [원등록](execution_contract.json)·[표시/호스트보완](label_only_revision.json)의raw SHA를덮지않는다. [소스 원형](source_versions/)·[정책/learner 검증](verification.json)과별도raw/PT는보존했다. 재분석에는로컬 `output/service_joint_rl_20261011_v1`이필요하다. AP는모형내부채널이고표면온도·안전한도·냉각에의한speed회복이아니다. 온라인candidate/actor의폰제어비용과실측절감은검증하지않았다.

기존overnight 학습CSV의서비스λ컬럼라벨오류는 [정정표](../overnight_rl_20261011/learning_updates_corrected_labels.csv)와[원본SHA/매핑](../overnight_rl_20261011/learning_channel_labels_erratum.json)에따로남겼다. 원CSV/수치/weights는수정하지않았고J열/에너지활동결론은원래정확했다.
