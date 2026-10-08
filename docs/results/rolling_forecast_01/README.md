# 10초 관측 갱신 예측

[결과 보고서](../../ROLLING_FORECAST_RESULTS_20261008.md) · [화면/그림](index.html) · [840개 창](window_errors.csv) · [60개 세션/방식 행](session_errors.csv) · [계약](contract.json).

20기존실행×14발행시점×3고정방식. 계수적합/학습/정책시뮬레이션/기기0. 실제미래lane일정이주어진조건부A비용예측이고미래관측AP/전력은입력하지않는다. 값유지비교만미래일정을필요로하지않는다. 모든결과이미본자료의사후평가다.

- AP:35..175초의14×10초창. 가용after_ns이전관측만입력, 해당미래창안의실제query bracket에서평가. 확인평균0.258→0.156°C이나확인최대1.077→1.380°C.
- J:35..115초의8×10초창. 과거가용끝점으로만보정. 확인개별창MAE0.870→1.268J악화.
- 합산J:8번갱신예측의80초합순오차는3.891→0.632J이나상쇄/지속관측을포함한다. 120초전체·35초에한번의80초예측과다르다. `common_120s_forecast_error=null`.
- 전달:Android AP조회끝/앱sample기록가용proxy만재현했다. host전달완료·센서내부갱신·현재앱numericAP읽기·추가계측비용은미검증. 기본/strict/RL/experiment_ready=false불변.

저장소공유입력으로재현한다. 새출력폴더를사용한다. 외부원본/기기연결은불필요하다.

```powershell
python -X utf8 -B -m unittest tools.test_d1_rolling_forecast -v
python -X utf8 -B -m tools.d1_rolling_forecast run --output output/rolling_forecast_reproduction
python -X utf8 -B -m tools.d1_rolling_forecast_readout --output output/rolling_forecast_reproduction
```

`inputs.json.gz`는같은20세션의작은수치/가용시각/실행구간이다. 원본40파일hash와이전입력hash는source_inventory.json에있다. NumPy/matplotlib·Malgun Gothic사용. raw재추출은exportsubcommand로가능하지만원공유입력덮어쓰기를거절한다.

`snapshots.csv`:시점별입력prefix/나이/보정량. `segment_summary.csv`:유휴/전환창사후집계(창은독립세션아님). `partial_totals.csv`:80초순오차/절대구간오차합. `past_future_residual.csv`:과거/미래잔차진단. `ap_paths.csv`:각시점의예측조각이며연결된한번의180초예측이아니다. fit/미래관측누출/지원확대/임의정확도PASS0.
