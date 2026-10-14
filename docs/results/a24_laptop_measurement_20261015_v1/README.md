# A24 독립 확인 중단시점의 부분 회수 (2026-10-15 06:49)

이 폴더는 전체 실측 완료 보고서가 아니다. 확인3번째가 초기 AP gate 초과로 시작 전 거절되어 자동 실행이 중단된 시점의 스냅샷이다. 2정상/1거절/37미시도를 보존하며, 후속 진행 결과와 구분한다.

원 계획 I4→F4→DEV16→CONFIRM40. 확인 정상 회수 **2/40**, 예정 요청 **5720건**을 모두 requests.csv에 보존했다. 실패 슬롯 재실행·대체와 추가 세션은0이다.

[독립 확인 대시보드](confirmation/index.html) · [개발 대시보드](development/index.html) · [기능 대시보드](functional/index.html)

실제 CPU/GPU 모델 추론·요청 흐름과 HAL AP 읽기값의 비교다. 미해결 전류 단위 때문에 검증 에너지 J는 계산 불가이며, AP는 검증된 표면 온도가 아니다. 이 결과로 에너지 절감·새 모형 예측 정확도·정책 채택을 선언하지 않는다.

## 독립 확인의 8군

| 조건 | 규칙 | 정상 세션 | 긴급 기한 내/예정 | 일반 기한 내/예정 | 세션 긴급 P95 평균(ms) | 세션 AP 평균의 평균(℃) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 분류 252건 | 분류 CPU (CPU) | 1 | 252/1260 | 0/0 | 115.110 | 29.695 |
| 분류 252건 | 분류 GPU (GPU) | 0 | 0/1260 | 0/0 | 계산 불가 | 계산 불가 |
| 저부하 64건 | 직렬 기준 (BASE) | 1 | 32/160 | 32/160 | 274.025 | 29.600 |
| 저부하 64건 | 병행 허용 (PAIR_G) | 0 | 0/160 | 0/160 | 계산 불가 | 계산 불가 |
| 혼합 128건 | 직렬 기준 (BASE) | 0 | 0/480 | 0/160 | 계산 불가 | 계산 불가 |
| 혼합 128건 | 납기순 EDD (ORDER) | 0 | 0/480 | 0/160 | 계산 불가 | 계산 불가 |
| 혼합 128건 | 병행 허용 (PAIR_G) | 0 | 0/480 | 0/160 | 계산 불가 | 계산 불가 |
| 혼합 128건 | 200ms 대기 (WAIT200) | 0 | 0/480 | 0/160 | 계산 불가 | 계산 불가 |

기한 내/예정 분모는 정상·실패·미시도를 포함한 전체5블록의 예정 요청이다. P95/AP 평균은 정상 회수 세션에서 계산하고 누락을 채우지 않는다. 표의 P95 평균은 요청을 합친 P95가 아니다. 전체 계획 분모·미시도·실패는 각 attempts.csv와 requests.csv, 조건별 결과는 sessions.csv를 함께 확인한다. 조건을 평균내어 서비스 악화를 숨기지 않는다.

같은5블록의 차이와 미보정95% Student-t 구간은 confirmation/paired.csv 및 paired_intervals.csv에 있다. 작은 반복의 탐색적 구간이며, 누락을 보간하거나 유리한 일부 조건을 고르지 않았다. 대표 시간표·AP 경로는 성적과 무관하게 처음 완전한 M128 BASE/PAIR_G 공통블록이다.

## 해석 범위와 미완료

- I4는 START 전 실패하여 유휴/상주 및 Perfetto 계측 비교는 미완료다. F1 gate 거절, F2 원장 FAIL·같은 원실행252건 읽기전용 회수, DEV1 통신 PRESTART 거절도 보존한다. DEV는15/16 정상 회수다.
- 개발의 저부하 L64는 두 규칙 모두 실제 병행0인데 AP 차이가 관측됐다. 센서 갱신/cache age와 외부 부하가 미확인이라 작은 AP 차이를 정책 효과로 확정하지 않는다.
- 임의1000배 전류 보정, 온도→에너지 환산, 다른 기기 계수 전용은0이다. 외부 전력계 및 AP/표면 센서 검증은 별도 후속 과제다.
- 승인된 같은1이미지를 반복하며 decoded score0.001/box2px reference만 검산한다. 보편 출력 정확도나 전체 raw tensor 수치 일치를 뜻하지 않는다.
- 이번 작업은 실측 원자료 확보다. 데스크톱 EP813/814·학습·시뮬레이션·S26/NPU·기존 정책과 strict/experiment_ready=false는 변경하지 않았다.
- 이전 APK eab8e449…5b883e와 확인 APK6fbe5c08…0bfd8b를 구분한다. 확인에서 앱단위 KEEP_SCREEN_ON만 추가했으며 모델/입력/기한/작업량/온도 gate·계수는 그대로다.

## 동결·재현

[분석 계약](../../team/a24-laptop-measurements-20261014/CONFIRM_ANALYSIS_CONTRACT_V10.json) · [소스161개 SHA](../../team/a24-laptop-measurements-20261014/MEASUREMENT_SOURCE_V10.json) · [동결](../../team/a24-laptop-measurements-20261014/CONFIRM_FREEZE_V10.json) · [오류·제한](../../team/a24-laptop-measurements-20261014/MEASUREMENT_PROGRESS.md)

개인 원물·모델·입력·서명키는 로컬에 보존했다. 공유물은 원물에서 파생된 작은 CSV·그림·분석 JSON이며 원자료 자체를 대체하지 않는다. 모델 재배포·개인 경로·기기 serial은 포함하지 않았다.

다음 명령은 보존된 job/config와 원물을 사용해 PC 분석만 재현하며, 실측·START·NN 호출을 하지 않는다. 기존 결과를 덮어쓰지 않도록 새 출력 폴더를 지정한다.

```powershell
python -B tools/d1_a24_measurement_report.py output/a24_measurement_20261015_v1/job_confirm_v10.json output/a24_measurement_20261015_v1/confirm_analysis_contract_v10.json output/a24_measurement_20261015_v1/confirmation_reproduction --stage CONFIRM
```
