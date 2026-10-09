# AP 느린 꼬리·유휴 기준 식별 — 예측개선/시간상수미확정

[한국어결과](../../AP_TAIL_IDENTIFICATION_RESULTS_20261009.md) · [최종화면](run_v2/index.html) · [최소근거명세(실행계획아님)](minimum_evidence.json).

주후보는부하별동결증분전력을누적한느린항+fast4,시간연동기준변화는대조다. 새개발4 MAE0.756→직전0.498→이번0.279°C,최근14는0.329→0.308°C. 전체29는거의같고13악화. τ1920상한·물리원인/독립확인미완료,기본/RL/strict/experiment_ready=false유지·기기0.

## PC 재현

```powershell
python -B -m unittest tools.test_d1_ap_tail_identification.TailTests -v

# 저장된 profile로 재적합 없이 복구(새 출력 경로).
python -B -m tools.d1_ap_tail_identification --recover-profiles docs/results/ap_tail_identification_01/run_v1 --output output/ap_tail_reproduction

# 같은등록10fit/70profile을처음부터재현하려는경우에만:
python -B -m tools.d1_ap_tail_identification --output output/ap_tail_full_reproduction
```

run_v1의계산값을남기고np.bool_ 직렬화실패를수정했으며run_v2 복구추가fit0이다. 33원입력은기존공유GZip3개/원model.json 상대경로이고개인PC의새기기원본/ADB/네트워크를요구하지않는다. registration에모든입력SHA와시각을기록했다. 모델변경·보상튜닝·τ추가탐색으로결과를맞추지않는다.

추가slow state0은작업시작이후의추가효과이지실측내부열이0이라는뜻이아니다. R_pre를주변온도로부르지않는다. common120 J는바꾸지않았고AP는각원래후반관측창에서비교한다. 원power꼬리coverage null과실제교집합power계산은별도파일이다. 미래관측AP/전류는예측입력아니다.
