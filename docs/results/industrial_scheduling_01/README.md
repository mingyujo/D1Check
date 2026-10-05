# 산업공학 스케줄링의 제한 PC 비교

## 전체 입력 후속 판정 — 2026-10-06

아래의 첫8요청 시험에서 끝내지 않고 [전체48요청 ATC·병목·beam·offline 비교](../method_followup_01/README.md)와 [분류CPU 고정/탐지CPU·GPU 호환 backfill](../detector_gpu_bridge_01/compatible_backfill_v2/index.html)을 완료했다. 예전 “다음 전체48요청”은 현재 완료된 역사적 제안이며 재실행 대상으로 삼지 않는다.

우리 문제의 대응은 요청=작업, CPU/GPU=서로 다른 처리시간을 가진 자원, 예정도착=release, 응답기한=due date, lane해제=자원반환이다. 요청은 선택한 자원에서5단계를 수행하므로 다공정 job-shop 전체와 같지 않다. 병행 간섭·전류/AP 상태 이력도 일반 독립 기계 가정과 다르다. 제조 방법의 이름을 붙였다는 이유로 기존 이론의 성능 보장을 가져오지 않는다.

| 방법 | D1Check에 쓸 부분 | 확인한 경계·결과 |
|---|---|---|
| ATC | 처리시간·기한여유·우선순위로 도착 큐 정렬 | 지각 비용 중심 원리. 전체queue에서 J 감소/AP 증가·긴급응답 손해; hard deadline 보장 없음 |
| 병목 중심 배정 | 탐지CPU 수요를 보호하고 분류 배정을 조정 | 기존3cell에서 용량 상충을 설명. DBR 투입제어 전체 구현 아님; 공동 절감 후보 미확보 |
| 호환 backfill | 앞 요청이 쓸 수 없는 빈 자원을 뒤 요청에 배정 | 실제L까지 소유권 유지·미측정 같은 종류 병행 차단. 과거시간16사례에서12전기한 충족이나 응답 상충/과부하 실패·현재 J/AP null |
| offline 혼합정수 일정 | 동일 입력에서 순서·배정·유예의 가능성을 보는 참고 | 모든 미래를 아는 격자 일정; 최적성 미입증, 온라인 정책으로 채택하지 않음 |
| 기한 우선·Pareto 판독 | 전 도착 서비스 조건을 먼저 검사하고 J/AP/응답 상충을 표시 | 현재 권고하는 비교 방법론. 임의 가중치·미확인 비용·사후 PASS 없이 목적별 결과를 보존 |

문헌 대조는 [Vepsalainen·Morton(1987), 출판사 초록](https://pubsonline.informs.org/doi/10.1287/mnsc.33.8.1035)에서 작업별 납기·지각 비용을 다루는 우선순위 원리를 확인했다. [Feitelson·Weil(1998), 저자 소속기관 초록](https://cris.huji.ac.il/en/publications/utilization-and-predictability-in-scheduling-the-ibm-sp2-with-bac-13/)은 EASY가 첫 대기 작업을 늦추지 않으며 보수적 backfill은 모든 대기 작업을 보호하는 차이를 명시한다. 우리 새 후보에는 그 예약 보장이 없으므로 정확한 EASY/보수적 backfill 재현으로 쓰지 않는다. 2026-10-06 확인; 이번에는 해당 초록 범위를 넘는 세부 성능 수치를 가져오지 않았다.

**현재 권고는 EFT를 강한 기준으로 유지하고, 기한 조건 아래 에너지 또는 AP의 목적별 상충을 평가하는 것이다.** 알고리즘을 반복 탐색하면 실제 공동 절감이 반드시 나온다고 보장하지 않는다. 저장된 고정split 대비 목적별 PC 개선과 EFT 대비 공동 개선 미확보는 서로 다른 결과다. 새 정책 채택·실기기 효과·전체 프로젝트 목표 달성은 별도 미완료다.

2026-10-06. **병목 기반 배정과 ATC를 구현·비교했다.** 작은 burst에서 공통창 에너지는 줄지만 긴급 응답이 늦어진다. 열 절감·새 기본정책 채택·실기기 우월성은 확인하지 않았다. [대시보드](run_v2/index.html) · [대표 그림](run_v2/burst_mean.png) · [문헌/기존 시도 대응](../../RELATED_WORK_GAP.md).

## 고정한 입력과 평가 경계

- 이미 본 `supervised_selector_01/run_v1/local_ledgers.jsonl`의 seed123001/EFT/mean 입력만 추출했다. 성과로 입력을 골라내지 않고 저부하 `g1.2_c0.5_b1`, queue `g0.45_c0.5_b4`, burst `g0.15_c0.5_b8`의 **첫8요청**으로 제한했다. 모두 분류5/탐지3이다. `class_share=.5`는 원48요청의 비율이며 이8요청에서50%라는 뜻이 아니다. 원48요청 전체와 같은 결과로 합치지 않는다.
- [공유 입력](inputs.json)은 원 id·ordinal·도착·기한을 보존하며 완료와 독립이다. 추출 SHA/원분모48/출처 메타를 보존했다. 새 seed 홀드아웃·독립 확인은 아니다.
- [실행 전 계약](contract.json): ATC 가중치 긴급4/일반1(6/1.5 기한비의 **휴리스틱**, 측정 지연비용 아님), k2, 병목·큐 보호 규칙, beam32, 대기 후보0/.25초, 탐색당20초/전체900초를 고정했다. 결과를 보고 계수·파라미터·후보를 바꾸지 않았다.
- 세 처리시간 문맥 mean/short_context/long_context에서9사례. 온라인 EFT/ATC/병목27계산과 offline 에너지/AP 참고 일정18재생, 최종 **45계산·360요청**, 모두 완료/기한 충족. 온라인은 정책별72요청이며 서로 다른 독립 세션이 아니다.
- 공통 J는0–120초, AP는35–180초. 처리시간 추정은 개발 문맥 평균; short/long은 전체5단계 벡터를 유지한 PC 실현 민감도이며 WCET가 아니다. 현재 PC 제어 계산의 추가 시간/에너지0 가정은 유지한다.
- 계수는 기존 `online-policy-model-v1`, model SHA `5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2`; 초기자료 SHA `42f603120e0f3db18243ef9f3053179039dc6138ce31f37df2c91ac2bf45d18d`. 입력은 기존 preload26표본·anchor33.9955초/AP29.1°C·유효 유휴 기준29.686795°C·잔열−0.012657°C/s·resident 기준전력1.113046W. 유휴 기준은 주변 온도 실측값이 아니다.

## 실제 구현

1. `ATC_QUEUED_GUARD_V1`: 현재 도착 큐의 합법 즉시 배정 후보를 작업 가중치/총 lane 점유시간 및 응답 기한 여유의 지수항으로 정렬한다. 긴급 응답은 output_ready, 일반은 persist_complete로 계산한다. backend별 earliest response와 실제 lane 보유를 구분하며 aged4초 요청을 우선 고려한다. 원 ATC의 그대로 재현이 아닌 이종 자원/응답 경계에 맞춘 적용이다.
2. `CPU_BOTTLENECK_GUARD_V1`: 도착한 탐지의 필수 CPU 수요가 있으면, 도착 큐의 EFT 후속 일정을 예측해 탐지 지각→필수 CPU 점유 종료→J→최고AP 순으로 즉시 행동을 고른다. 탐지가 없으면 EFT를 유지한다. 모든 탐지 우선/분류 GPU 강제가 아니며 원 DBR 공정 투입 제어 전체의 재현도 아니다. 요청 도착·기한을 바꾸지 않는다.
3. 두 후보는 기존 PAIR 보호와 같은 **요청별 long_context 예측 지각이 현재 EFT 행동보다 커지지 않는 검사**를 적용한다. 예측상 악화되는 후보는 거부하고 EFT로 돌아간다. 이미 관측된 응답은 미래 실패로 다시 집계하지 않으며 active overrun은0으로 간주하지 않는다. 추가적인 자발 대기는 없다. 미래 도착·실현 처리시간은 온라인 callback에 전달하지 않는다.
4. Offline은 미래 도착과 해당 문맥의 처리시간을 아는 constructive beam 탐색이다. 분기에는 배정·순서·0/.25초 release 이후 대기를 허용하고 에너지/최고AP 기준의 두 반쪽 beam을 유지한다. 온라인 일정을 incumbent로 포함했다. 탐색은8,400노드/7,248절단/timeout0; **최적성 증명이나 하한이 아니다.** 선정된 두 일정은 helper 계산만으로 끝내지 않고 기존 이벤트 엔진에서 재생했다.

## 결과 — mean 문맥, EFT 대비

| 입력/방법 | 기한 | J 차이 | 긴급P95 차이 | 일반평균 차이 | 판독 |
|---|---:|---:|---:|---:|---|
| low: ATC/병목 | 각각8/8 | 0 | 0 | 0 | EFT와 같은 실제 lane 일정 |
| queue: ATC | 8/8 | 0 | 0 | 0 | EFT와 동일 |
| queue: 병목 | 8/8 | −0.043247J | 0ms | −110.144ms | 병행0.590371→0.895200초 |
| burst: ATC/병목 | 각각8/8 | −0.135488J (−0.10014%) | +417.101ms | −343.291ms | 두 후보가 같은 lane 일정, 응답–에너지 상충 |
| burst: offline AP 참고 | 8/8 | +0.080746J | −279.226ms | +514.156ms | 최고AP 차이−0.000079°C, 열 개선 근거 아님 |

short/long도 같은 방향이다. burst J −0.135153~−0.135835J, 긴급P95 +394.208~+439.994ms; queue 병목 J −0.041896~−0.044598J. 최종45계산 중 서비스360/360. 5개 긴급 요청의 nearest-rank P95는 최댓값이므로 정밀 tail 추정으로 쓰지 않는다. [모든 차이](run_v2/comparisons.csv), [원 수치](run_v2/results.csv), [요청별 변화](run_v2/request_deltas.csv).

### J 감소의 구체적 경로

burst/mean에서 EFT는 분류 CPU3/GPU2, 두 후보는 GPU5이다. 탐지3개는 모두CPU다. 합법 병행은0.590371→1.524147초로 증가하고, 마지막 lane 해제는37.380148→36.865211초로 빨라지지만, 긴급P95는915.563→1332.664ms로 느려진다. "전체 완료가 빠름"과 "긴급 응답이 빠름"은 다르다.

에너지식은 `120×resident전력 + Σ상태별 추가전력×점유시간`이다. resident 기준은133.565571J로 EFT135.297368J의 약98.72%다. 작업/병행 추가분1.731797→1.596309J의7.82% 감소는 **전체 J의0.10%** 감소이며,7.82% 전체 배터리 절감으로 쓰지 않는다. [상태 점유·추가 J](run_v2/state_exposure.csv).

실행 후 부가 분석에서 기존 `d1_scheduler_alternatives.energy_lower_bound`를 그대로 적용했다. burst3문맥 모두 두 후보의 J가 이 완화 하한과1e−6J 이내로 일치했다. 이 허용폭은 **수치 반올림 검사용**이지 실측 정확도 기준이 아니다. beam 최적성 증명과 구분하며, 동일 선형 전력·고정 phase 시간·완전 작업·공통창의 한정된 문제에서 추가 J 여지가 작다는 근거다. 다른 입력/열/실기기 최적성은 아니다. [완화 하한 대조](run_v2/energy_bound_check.csv).

### AP 결과를 열 절감으로 쓰지 않는 이유

모든 AP 경로가 유효 유휴 기준29.686795°C 아래이고, 양의 degree-seconds는0이다. 공통35–180초 최고값은 **모든 사례에서180초 끝**에 있다. burst 후보의 최고AP 차이 +0.000133°C는 작업 중 차이를 거의 숨긴다. 반면 AP 경로의 최대 절대 차이는mean0.142746°C, queue 병목0.052321°C이며 burst 후보가 초기에 더 높다. 작은 최고값 차이/열부담0을 공동 열 우월성으로 읽지 않는다.

이8요청은 일정·상태 배정의 에너지 상충을 확인하기 위한 작은 입력이다. 열 관리 효과·장시간 잔열·열→처리시간을 검증하지 못했다. A24 미식별 스로틀 계수나 S26 계수를 새로 넣지 않았다. 기존 폰 확인의 J/AP 오차를 새 입력의 보편적 오차 한도로 전용하지 않으며 이0.1%를 실기기에서 판별할 수 있다고 주장하지 않는다.

## 검증과 구현 결함 수정

- 실제 이벤트 진입·콜백의 no-future prefix/비공개 lane 정보 거부, 원 도착 보존,5단계와 lane 해제, 전체 분모, guard의 개별 지각, unknown overrun, strict 차단, frozen byte/hash, 기존 EFT 결과 동일성을 검증했다.
- 참고 일정 재생 테스트에서 ns 반올림 때문에 미지원 분류CPU+분류GPU 병행이 극히 짧게 생길 수 있는 새 코드 결함을 발견했다. **실제 lane 해제/호환성 이벤트를 기다리게** 수정했다. 기존 앱·센서·물리계수와 무관한 PC replay 결함이다.
- 신설15＋관련 기존15 = **30테스트 통과**. 보고서 생성에서45개의 공통창 J/CSV/곡선/AP/기한 분모를 대조했다. frozen model/initial byte 불변. PNG 시각 확인, 상대 링크 및 diff 검증. Android/APK/기기 명령0.
- 첫45계산 `run_v1`은 로컬에 보존. 공유 재현에서18.6MB 부모ledger가 없어도 준비된8요청 입력으로 실행할 수 있도록 출처 확인만 보완하고 `run_v2`45계산을 재수행했다. 모든 일정/모형 수치는 동일하며 파라미터 재선정은 없다. **이번 본 실행 총90계산**, 최종 공유 결과45계산/20.609초. 테스트 내부 fixture 계산은 별도다.
- `run_v2/registered_before_run.json`은 실행 전 소스/입력/계수 해시, 원 출처 확인 가능 여부, 기준 HEAD `af2dd0aa03a34f0997d30db12b03d80a3e3c8e3a`와 미커밋 구현을 특정한다. 공유 시 byte 속성을 고정해 체크아웃 줄끝 변환으로 근거 해시가 바뀌지 않도록 했다.
- 후보 판단 계산은 PC에서 최대 ATC11.118ms/병목8.547ms가 들었다. 시뮬레이션의 추가 시간/에너지0 가정과 실제 실행 비용을 구분한다. 실기기 제어 비용을 측정한 값이 아니다.

## 재현

저장소의 Python/NumPy/Matplotlib 환경을 사용한다. 신경망 학습·Torch·ADB는 필요 없다. 대용량 부모ledger는 **입력 추출 출처 감사용**이며 이미 공유된 입력으로 계산/그림 재현하는 데 필수는 아니다. 파일이 있으면 SHA를 검증하고 없으면 출처 재감사는 미확인으로 기록한다. 기존 동결 입력/모형은 아래 경로의 byte를 그대로 사용한다.

```powershell
python -m unittest tools.test_d1_industrial_scheduling tools.test_d1_industrial_scheduling_report tools.test_d1_empirical_request_policy -v
python -m tools.d1_industrial_scheduling --output output/industrial_scheduling_reproduction
python -m tools.d1_industrial_scheduling_report --output output/industrial_scheduling_reproduction
```

계산 없이 공유 그림/CSV를 다시 만들려면:

```powershell
python -m tools.d1_industrial_scheduling_report --output docs/results/industrial_scheduling_01/run_v2
```

공유 records는 [압축 JSONL](run_v2/records.jsonl.gz)로 보존했으며 plain 파일이 없어도 보고서를 생성한다. 모델 계수 파일은 `docs/results/online_policy_study_01/overnight_sustained_run01/model.json`, 초기자료는 같은 폴더 `initial_inputs.json`이다. 원 APK/모델 바이너리/기기 식별값을 추가 공유하지 않았다.

## 판정과 다음 행동 하나

산업공학 원리를 이식하면 실제 일정이 달라지고 작은 J–서비스 상충을 만들 수 있다. ATC는9사례 중6개가EFT와 동일, 병목은3개 동일이며 burst에서는 두 후보가 같은 결과다. 이름이 둘이라고 독립된 개선 수단 둘을 발견했다고 주장하지 않는다. 기본정책·strict·`experiment_ready=false`는 유지하며 두 후보를 PC opt-in 분석 경로로만 보존한다.

다음 PC 행동 하나는 **queue `g0.45_c0.5_b4`의 기존 전체48요청에서 병목 후보의 서비스와 상태 점유를 저장된 EFT 결과와 대조**하는 것이다. 작은8요청에서는 긴급P95 악화 없이 일반 응답/J 개선이 있었으므로, 이를 전체 요청에서 유지하는지 확인하는 좁은 회귀다. 이번에는 아직 수행하지 않았으며 새 계수·새 학습·추가 실측을 요구하지 않는다. 같은 작은 입력의 파라미터 탐색은 반복하지 않는다.
