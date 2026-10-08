# 에너지 관측 보정 감쇠: 후보 미채택

[결과](../../ROLLING_ENERGY_SHRINK_RESULTS_20261008.md) · [그림/화면](index.html) · [20세션별 결과](session_errors.csv) · [480계산행](window_errors.csv) · [개발 봉인](candidate_freeze.json) · [추정 전 계약](contract.json).

단일alpha를개발6에서MAE최소로추정:0.2626883124. 개발회복제외gate실패·선택alpha0로원모형유지. 후보는전량보정의악화를완화했지만확인10초MAE원0.870→0.922J·지속0.844→0.856J로증가했다. 합산80초순오차감소는보존하되120초전체예측개선으로쓰지않는다. 평가전체이미본자료의사후평가·기기/학습/정책환경0.

원rolling의같은가용prefix/과거10초/SensorScale/state조건을유지한다. 미래관측은평가입력만, 실제미래일정은A조건으로주어짐. B도착/일정/응답·AP모형/기본/RL/strict는변경하지않는다. 가능한모든개선의불가능성이나보편오차한도는판정하지않았다.

저장소공유입력으로새경로에재현한다. 원자료/기기접속불필요.

```powershell
python -X utf8 -B -m unittest tools.test_d1_rolling_energy_shrink -v
python -X utf8 -B -m tools.d1_rolling_energy_shrink --output output/rolling_energy_shrink_reproduction
python -X utf8 -B -m tools.d1_rolling_energy_shrink_readout --output output/rolling_energy_shrink_reproduction
```

의존데이터4개hash는contract.json/source_hashes에있다. NumPy/matplotlib/Malgun Gothic사용. 기존계수/원파일덮어쓰기는없고생성출력도새폴더만허용한다. 동결utc/hash는재현 시달라도계수·선택·CSV는같다. 原proxy 가용시각한계를보존하며app/host실제수신지연을확인한것은아니다.
