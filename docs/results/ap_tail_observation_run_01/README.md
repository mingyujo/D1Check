# 긴 C0·부하 회복 Run01 — 중단·경계 수정

[한국어 보고서](../../AP_TAIL_OBSERVATION_RUN01_20261009.md) · [종료 화면](run_v2/index.html) · [실제 소비](run_v2/consumption.json) · [경계·부분 관측](run_v2/failure_boundary.json) · [수정 검증](verification.json).

C0600초 뒤 잘못 적용한 tail 검사로 중단했다. C0의1920초 회복과LOAD_A는 미진행이다. 본작업0/준비12/runtime4/ADB1588/927.703초, 원 plan_v2 stopped_no_resume. 예측오차/정확도PASS가 아니라 앱 구현 결함이며 연결소실/lifecycle_cancelled 기록은 없다. 새 경로 C0만 종료를 허용하는 수정과 Android13/Python5 검증·서명후보를 완료했으나 수정후보 설치/추론/추가실측0이다.

기존 모형·계수·원본·receipt·종료계획을 보존한다. 실행 경계 그림만 있으며 완성된 AP/J 비교 곡선은 없다. source/archive는 외부 원본에 있고 작은 hash inventory만 공유한다.

```powershell
python -B -m unittest tools.test_d1_ap_tail_observation_results.ResultTests -v
python -B -m tools.d1_ap_tail_observation_results --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_plan_v2/collection_plan.json --output output/ap_tail_failed_reproduction --external-adb-commands 4
```

public 산출물의 실행 경계/실패 판독을 포함한 전체 재현은 외부 artifact에 의존한다. 새 실행기를 호출하거나 소비기록을 초기화하지 않는다.
