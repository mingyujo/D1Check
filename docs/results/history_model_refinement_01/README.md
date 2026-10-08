# 새 이력 자료 모형 보완 — 특정 조건만 개선

[한국어 결과](../../HISTORY_MODEL_REFINEMENT_RESULTS_20261008.md) · [화면/그림](index.html) · [100행 전체](session_errors.csv) · [세션묶음별 비교](comparison.csv) · [개발 동결](candidate_freeze.json) · [계약](contract.json).

새이력개발6으로제한된두후보구조를적합/선택한뒤확인6+기존지속8을사후평가했다. 결과는AP일부개선/개발선택실패, 에너지지속개선/확인악화이며기본모형을유지한다. 전부이미열람한자료로새독립맹검·정확도PASS·정책우월성아님. 기기/ADB/학습/정책시뮬레이션0.

원모형SHA5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2. A조건부실제lane일정을이용하며B도착/응답모형은변경하지않았다. 초기입력은부하전AP와전력뿐이다. 에너지0..120초·AP실제post35표본창/냉각까지. 유휴기준은주변온도가아니고최고AP는표면온도/센서사이물리최고보장이아니다.

`AP_RIDGE`는개발에서원λ0을유지한뒤고정한비영λ.1의미채택진단, `E_CONTROL`은개발통과후확인악화한후보다. `COMBINED_DIAGNOSTIC`은두출력의단순조합이고별도개발후보가아니다. `FIXED_G_SAME_INPUT`은기존실패g를동일한fresh초기입력에적용한미적합보조비교다.

공유입력 `inputs.json.gz`에는새12와기존지속8의작은수치시계열/상태구간을담았다. 모델binary·APK·키·기기식별값은없다. `source_inventory.json`이외부원자료60필수파일hash와이전공유입력hash를연결한다. 원본재수집없이저장소에서재현가능하다.

```powershell
python -X utf8 -B -m unittest tools.test_d1_history_model_refinement -v
# 항상 새 출력 경로; 원 결과 덮어쓰기 거부
python -X utf8 -B -m tools.d1_history_model_refinement --output output/history_refinement_reproduction
python -X utf8 -B -m tools.d1_history_refinement_readout --output output/history_refinement_reproduction
```

NumPy·matplotlib과한글폰트Malgun Gothic를사용한다. 재현fit은등록자료/절차를그대로계산하는것이며평가후새후보탐색이아니다. 초기추출은외부`energy_ap_history_recovery_run_v7/primary`를읽었고모든원 J/AP와동결결과를대조했다. 원본이없어도공유입력으로후보계수·선택·100행을재현한다. 미식별/nonpositive/결측은unavailable이며0채움이없다.

`windows.csv`:5초bin상태혼합/에너지잔차. `initial_states.csv`:초기R/H와조건수. `preload_sensitivity.csv`:단일AP표본+.05°C의결정론적감도이며정확도/신뢰구간아님. `sustained_pairs.csv`:기존4쌍차이오차. `nominal_contrasts.csv`:새회복조건별순차CPU/PAR대조, 인과효과아님. `paths.json.gz`:관측/예측/잔차경로. 원동결/strict/RL/experiment_ready=false불변.
