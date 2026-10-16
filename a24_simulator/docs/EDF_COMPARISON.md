# 비선점 EDF와 롤링＋ATC＋RL — 같은 작업 구간 비교

2026-10-16 사용자 요청으로 모바일 변형 규칙을 대신할 비교군을 **EDF_CPU_FIRST**로 정했습니다. 기존 모형·선정 RL·원 결과는 보존했습니다.

## 정책과 비교 계약

- 현재 도착하여 대기 중인 요청의 절대 납기 → 도착시각 → ordinal → request ID 순으로 선택합니다.
- 빈 CPU/GPU에 배정하고, 둘 다 비어 있으면 CPU를 우선합니다. 두 작업 모두 CPU/GPU가 가능합니다.
- 예상 응답시간·처리시간·에너지·온도는 EDF의 요청/경로 선택에 사용하지 않습니다. 물리 시뮬레이션의 처리시간 예측과 정책 선택은 구분합니다.
- 비선점, 자원당 1건, 최대 두 요청, AVAILABLE까지 소유합니다. 자발적인 WAIT는 없습니다.
- 이전 EDD는 최단 예상 응답 경로를 사용했으므로 이번 EDF와 다릅니다. Linux/Android OS EDF를 재현했다고 주장하지 않습니다.

기존 기본12＋stress2의 14조건·640요청과 같은 입력·초기 이력·잠재 seed를 사용했습니다. EP32 RL의 정확한 저장14행은 재사용하고 EDF14환경만 새 등록·실행했습니다. 새 학습/선정/모형 적합/원격 조회/기기 명령/추가 전역 예약은0입니다.

작업 구간은 **첫 도착 ~ 마지막 도착＋15초**로 각 조건에서 미리 정합니다. 두 정책에 동일하며 조건별 평균 길이는31.526초입니다. 두 정책 모두640요청의 자원을 이 구간 안에 전량 반환했습니다. AP는 정확 구간 끝점을 선형 보간하여 시간 적분 평균을 구했습니다. 아래 수치는 조건에 같은 가중치를 준 평균입니다.

## 결과

| 지표 | 롤링＋ATC＋RL | EDF CPU 우선 | RL−EDF |
|---|---:|---:|---:|
| 공통 기저 J* | 37.970028 | 37.970028 | 0 |
| 작업 증분 J* | 11.131626 | 10.484419 | +0.647207 · +6.173% |
| 기저 포함 총소비 J* | 49.101654 | 48.454447 | +0.647207 · +1.336% |
| 구간 평균 AP ℃ | 26.833545 | 26.858513 | −0.024968 |
| 조건별 구간 최고 AP의 평균 ℃ | 26.961780 | 26.994212 | −0.032432 |
| 구간 끝 AP ℃ | 26.912349 | 26.930136 | −0.017787 |
| 정시/전체 | 635/640 | 640/640 | −5건 |
| 응답 미완료 | 0 | 0 | 0 |
| 총 지각시간 초 | 1.984042 | 0 | +1.984042 |

RL은 평균 AP가 소폭 낮지만 에너지와 납기가 불리했습니다. 조건별로 부호가 달라 전체 평균을 모든 조건의 개선으로 해석하지 않습니다. 이전35~180초 AP 평균과 이번 작업 구간 평균은 다른 지표입니다. J*는 교정 실측 에너지가 아니며, AP도 표면온도가 아닙니다. D_GPU와 일부 병행 외삽·실측J/오차/CI null·실기기 RL 미검증을 유지합니다.

## 파일과 검증

- [비교 화면](../results/EDF_CPU_FIRST_20261016_01/index.html): 평균/14개별 조건·에너지 분해·동일 시간축 AP·납기·구간 밖 미완료 표시.
- [RESULT.json](../results/EDF_CPU_FIRST_20261016_01/RESULT.json), [METRICS.csv](../results/EDF_CPU_FIRST_20261016_01/METRICS.csv): 모든 조건/정책/요청·손해·경로와 집계.
- [policy.py](../experiments/edf_cpu_first_20261016/policy.py): 새 EDF 선택기와 공통 구간 관측.
- [OPERATION.json](../experiments/edf_cpu_first_20261016/OPERATION.json), [run_comparison.py](../experiments/edf_cpu_first_20261016/run_comparison.py): 원 소스/입력/CP SHA와14환경 등록·원장·실행.
- [COMPLETE.json](../results/EDF_CPU_FIRST_20261016_01/COMPLETE.json): EDF14 START/PREPARED/COMPLETE, FAIL0. 이전292＋14=306/512·잔여206, 새 전역 예약0.
- [TEST_RESULTS.json](../experiments/edf_cpu_first_20261016/TEST_RESULTS.json): 순수12검사. [INDEPENDENT_AUDIT.json](../results/EDF_CPU_FIRST_20261016_01/INDEPENDENT_AUDIT.json): 저장28행·에너지/열 적분·실제EDF 배정·분모5,168검사 PASS. [UI_QA_02/RESULT.json](../results/EDF_CPU_FIRST_20261016_01/UI_QA_02/RESULT.json): 실제Chrome 14조건·6뷰·39검사, JS/원격/overflow0·추가환경0 PASS.

첫 UI_QA는 Playwright 번들 실행파일 부재로 브라우저 실행 전에 종료했으며 FAILURE와 소스를 보존했습니다. 설치된 Chrome을 명시한 UI_QA_02에서 실제 검증했습니다. 환경 실행 실패/재실행은 없습니다. EDF 완료14와 기존 RL14는 자동 재실행하지 않습니다. 예약과 GitHub 주기조회는 OFF입니다.
