# 장시간 C0 → LOAD_A 확인 결과

두 조건 모두 정상 종료·회수·진단 자료 적격성 검증 완료. 후보는 실행 전에 고정했고 새 자료 fit·추가 실측은0회다.

- [한국어 보고서](../../../AP_TAIL_OBSERVATION_RUN05_20261009.md)
- [곡선·소비 화면](index.html), [AP 오차](metrics.csv), [에너지·결측](energy.csv), [세션](sessions.csv), [실제 상태](states.csv)
- [해시·호출·PC 재현 확인](verification.json), [원자료 해시 inventory](inventory.json)

AP MAE(공통＋회복의 확보 표본): C0 원식/LOAD_SLOW0.0908°C·CLOCK_SHIFT0.8726°C, LOAD_A 원식0.4371°C→LOAD_SLOW0.1728°C. 이 결과는 실제 일정 조건부 장시간 전이 진단이다. τ 식별·정확도 PASS·정책 우월성·strict 확대·기본/RL 모형 교체가 아니다.

## 다른 PC에서 수치 재현

저장소 root에서 Python 및 프로젝트 분석 의존성(numpy 등)이 준비된 경우 실행한다. 이미 존재하는 출력 폴더를 덮어쓰지 않는다.

```powershell
python -B docs/results/ap_tail_observation_run_05/run_v6/reproduce.py --output output/ap_tail_v6_reproduced
```

작은 `inputs.json.gz`의 부하 전 초기 입력·실제 일정과 평가 센서값을 사용한다. 이후 AP·전력은 평가 대상이며 예측 입력으로 전달하지 않는다. 원식과 후보 JSON 해시를 확인하고 18 AP행·6 에너지행을 재생성한다. 이번 확인에서는 모든 필드가 원 CSV와1e-9 이내 일치했다. 기기 명령·fit은0이다.

## 전체 원자료 판독 재현

원자료 `D1Check_Arrival_Extension/energy_ap_tail_observation_run_v6`의 FINAL_RECEIPT.json, 두 세션의 validated.json·artifacts·thermal.jsonl·host_cleanup.json과 plan_v6 및 소비 registry가 필요하다. 정확한 PC 명령은 한국어 보고서에 있다. 기기 재실행 명령이 아니다.

공통600초 전체 J는 적분했고, 냉각 끝 미관측0.350/0.578초로 전체 냉각 J/오차는 null이다. 부분 에너지를 전체 에너지로 사용하거나 누락을0으로 채우지 않는다. 센서 표본은 독립 세션이 아니며 C0/LOAD는 각각 한 block이다. A24 raw=mA는 조건부·절대 정확도 미인증이다.
