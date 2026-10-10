# 공동 롤링 리스트와 PPO 보정 선택 결과

**3seed 강화학습과 대기 제거 평가를 완료했다. 같은 후보 비학습 선택기를 RL이 일관되게 넘지 못해 새 채택은0이다.**

[오프라인 화면](index.html) · [설계·결과 보고서](../../ROLLING_LIST_RL_PILOT_20261011.md) · [336행](comparison.csv) · [조건별 차이](paired_differences.csv) · [학습·gradient·승수](learning_updates.csv) · [마스크·대기·판단시간](control_cost.csv) · [원장 동일성](schedule_equivalence.csv) · [전량검증·checkpoint SHA](verification.json) · [실행 전 계약](execution_contract.json).

| 정책 | 일반 기한실패 | J120 조건평균 | 최고AP 조건평균 °C |
|---|---:|---:|---:|
| 리스트 L0 |18|152.320683|30.457548|
| Band 대응 |18|152.281267|30.455470|
| Triton 대응 |18|152.734779|30.473534|
| 기존 공동 롤링 |21|152.056558|30.430118|
| 같은 후보 비학습 Rule |18|152.196508|30.454863|
| PPO seed11, 학습32 |18|152.281267|30.455470|
| PPO seed23, 학습32 |21|152.096099|30.450481|
| PPO seed37, 학습32 |21|152.096099|30.450481|

각정책/단계1584/1584완료·긴급684실패0·일반900분모유지다. 비학습Rule은서비스를유지하며Band보다평균J0.084759J/AP0.000607°C감소했지만일부조건은악화했다. PPO11의이번24실행원장은Band와exact동일이다. PPO23/37은Rule보다평균J0.100409J/AP0.004383°C감소하지만기한실패3건이늘었다. 같은후보Rule대비RL추가효과와기존방법론전체보완효과를구분한다.

각seed32episode/4update/Adam48step으로실제actor학습을했고λJ는0이아니었다. 16→32에서11/23의이번KPI는같고37은비용감소/기한손실쪽으로바뀌었다. 짧은학습이며수렴완료·RL일반실패를주장하지않는다. 정확한final actor/critic/Adam/RNG/승수/cursor·빈partial을local에보존하고12episode archive의nonemptyAdam/partial4로추가4를학습해원16과exact를확인했다.

대기제거후전3seed가L0의기한실패18로돌아오면서비용이득도없어졌다. 이평가는냉각과자원대기를함께제거했으며routing/후속도달상태도달라져단일대기의인과효과가아니다. 전seed유망기준미달이라조건부열특징제거72와추가본학습은0이다. 다음검토질문은관측이부족한첫대기와미도착CPU전용작업의위험이다.

## 구조·실행 범위

실측기반v3최종열head/원5phase·전력/CPU·GPU·CG_DC최대2·기한1.5/6·J120/AP35..180은유지한다. 창4/과업내EDD/원mean선별8에서L0＋최대7실행prefix를만든다. 새리스트L0가기본/복귀/학습참조/예측후속이며Band는평가군이다. 같은상태56/후보8×28/물리·예측허용을Rule/PPO가공유한다. 기존자체PyTorchmasked PPO를재사용하고새schema로새weights를학습했다. 빈slot·미지원/사용중lane은차단하고미래도착/실제잔여비용/실제내부온도는입력하지않는다.

공개큐작업량/최근도착/기한·다음기한/누적대기/모형추정열이입력이며대기는요청누적.25,Dbacklog<2,관측CPU-Dρ<1일때허용한다. 예측mask는실제서비스보장이아니다. 냉각→속도회복·표면온도·안전한도·절대전력교정·폰제어J는미지원이다. 미세한AP차이를실기기절감으로확정하지않는다.

학습826010001..008×4부하/회전문맥32·seed11/23/37,개발826020101/102×4부하×3문맥24다. 3문맥은민감도이며독립3반복이아니다. 최종독립확인0·개발자료선정이며원strict/기본/experiment_ready=false유지다. 기존825…결과와현재826…결과의실패건수를직접전후효과로비교하지않는다.

472/572환경·100/104학습(96본＋4resume)·실패0·30,896전량완료·기기/fit/NPU0,누적10321/1549다. 순수14/공유2/native4/472raw·28,339 snapshot·학습표본1574/전3archive·resume PASS다. 원예산/clock과기존결과·weights·모형개발·사용자변경/다른worktree는보존한다.

```powershell
python -B -X utf8 -m tools.d1_rolling_list_rl_check
python -B -X utf8 -m unittest tools.test_d1_rolling_list_rl tools.test_d1_rolling_list_rl_run tools.test_d1_rolling_list_rl_check -v
python -B -X utf8 -m tools.d1_rolling_list_rl_report
```

공유검사는실행모듈import/예산·환경·학습생성없이LF/CRLF만인정하고모형/source/입력을검사한다. 보고서재현은local `output/rolling_list_rl_20261011_v1`의완료gz가필요하다. PT/gz/원시대용량/모델binary는공유하지않는다. 라이브러리버전은종료후같은설치본에서기록했고별도version-lock은없으므로장래복구전대조가필요하다.

PPT그림5종PNG/SVG와모든학습단계·seed의조건별CSV를저장했다. 현재추천은기존기준유지,자체발전후보는같은후보비학습Rule이다. RL확대는서비스손실원인과필요예산을별도고정한후검토할사항이며이번자동시작범위가아니다.
