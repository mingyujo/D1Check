# 전력 반복값과 잔차 지속성 판독

[한국어 결과·후보 판정](../../POWER_RESIDUAL_STRUCTURE_RESULTS_20261008.md) · [후보 화면](../energy_memory30_01/index.html).

기존 20세션에서 기록된 전류·전압의 반복 양상과 과거 잔차의 지속성을 분석한다. 원본 전기 표본 3,357행을 작은 CSV로 공유하며 기기 식별정보는 포함하지 않는다. 공통 0–120초 내부 2,664표본 중 전류 반복 인접 쌍은 10/2,644개다. 기록 간격 약 0.9초를 센서 내부 갱신 주기로 인증하지 않는다.

개발 6세션의 과거 30초→다음 10초 잔차 상관 0.229는 과거 10초의 0.115보다 높았다. 이는 후보를 시험할 기술적 근거이며 독립 표본·물리 원인·정확도 합격이 아니다. 확인 6세션·기존 지속 8세션은 이미 본 사후 평가 자료다.

| 파일 | 역할 |
|---|---|
| contract.json | 10/30초 비교·고정 발행·개발 근거 조건을 진단 전에 기록 |
| electrical_samples.csv | 기존 앱 진행 기록에서 추출한 전기 표본·기록상 가용 시각 |
| raw_source_hashes.json | 20개 원본 progress.jsonl의 익명 역할 ID와 SHA |
| telemetry.csv / current_holds.csv | 세션별 간격·반복·같은 값의 관측 길이 |
| residual_5s.csv | 35–120초 5초 잔차 340행 |
| past_features.csv | 20세션×8발행의 과거 잔차와 다음 10초 사후 정답 |
| sessions.csv / groups.csv | 세션 단위 분산·상관, 세션 간 차이와 기술적 집계 |
| summary.json | 진단 단계의 근거 판정. candidate_fitted=false는 다음 별도 단계와 구분 |
| structure.png | 고정 10초/30초의 변동과 다음 창 상관 |

## PC 재현

저장소 루트에서 Python·NumPy·Matplotlib를 사용한다. Git의 이 폴더, `rolling_forecast_01/inputs.json.gz`와 계약에 지정된 작은 이전 결과·모형 JSON으로 재현하며 ADB나 개인 PC 경로가 필요하지 않다. 출력은 존재하지 않는 경로를 지정한다.

```powershell
python -X utf8 -B -m tools.d1_power_residual_structure --output output/power_structure_repro
python -X utf8 -B -m unittest tools.test_d1_power_residual_structure -v
```

원본 추출의 출처는 외부 `energy_ap_history_recovery_run_v7/primary`의 12개 세션과 `sustained_confirmation_run_v1`의 8개 세션 내 `artifacts/progress.jsonl`이다. 시작 경계는 각각 `target_start_ns`와 `start_ns`, 시계는 앱 monotonic이다. 정규화된 작은 재현 입력은 이미 공유했다. 원본 전체·기기 명령 없이 수치 판독을 재현할 수 있다.

예측 입력은 `past_available_s ≤ start_s`인 과거 표본만 사용한다. CSV의 미래 잔차/관측 J는 평가 정답이며 후보의 개발 이외 계수 적합이나 평가 시점 예측 입력에 쓰지 않는다. 미래 실제 일정이 주어진 조건부 계산은 예정 도착부터의 종단간 예측과 구분한다.
