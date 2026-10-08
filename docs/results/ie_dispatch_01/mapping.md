# 산업공학 배정·순서 규칙의 PC 대응

결과 확인 전에 고정한다. 작업 ID `IE-DISPATCH-PC-01`. 기존 ATC/CPU 병목 탐색, StarPU/Band 제품 및 SHARED_EFT와 서로 다른 정책이다.

| 원 개념 | 우리 대응 | 유지 | 변경·생략 | 가능한 주장 |
|---|---|---|---|---|
| ECT: 가장 이른 완료를 제공하는 기계에 배정 | 현재 도착한 선두 요청을 CPU/GPU 중 예상 **lane_available**가 가장 이른 자원에 배정 | 자원 가용 시각+처리시간의 완료 비교 | 5단계 전체 점유를 처리시간으로 대응, 호환 병행 제약 추가, 장래 예약 없이 공개 event마다 재판단 | 제한적 B. 같은 모형의 ECT 원리 적용 비교 |
| FIFO 순서 | 도착 시각, ordinal, ID 오름차순 | 선착순 | 동점은 우리 평가 계약 | ECT의 자원 선택과 순서 효과 분리 |
| SPT 순서 | 지원 자원별 평균 5단계 시간의 **최솟값**이 작은 요청 먼저 | 짧은 처리시간 우선 | 이종 자원의 처리시간 축약은 명시적 적용 설정. 원 논문의 유일한 SPT 정의라고 주장하지 않음 | 이 SPT 축약을 사용한 제한적 B 비교 |
| EDD 순서 | 절대 응답 기한(도착+1.5초/6초) 오름차순 | 가까운 기한 우선 | 공장 작업 완료 납기와 달리 응답 완료/자원 반환을 별개 평가 | 제한적 B. 응답 기한 기반 순서 비교 |

정책: `IE_FIFO_ECT_LANE_PC_V1`, `IE_SPT_ECT_LANE_PC_V1`, `IE_EDD_ECT_LANE_PC_V1`.
세 정책의 하위 자원 선택은 동일 ECT. SPT/EDD를 독립 자원 배정 알고리즘이라고 부르지 않는다.

- 관측: 도착한 요청의 작업/우선순위/기한, 공개 lane의 request/phase/since/dispatch, 고정 mean 처리시간. 실제 문맥의 미래 처리시간·미래 도착·실측 AP 피드백은 사용하지 않는다.
- 시점: 기존 엔진의 요청 도착·공개 phase·가용 자원·등록된 wait timer. 최선 자원이 미래에 풀리면 예상 시작까지 기다리되 새 event가 오면 재판단한다. 이미 선택한 장래 작업의 예약은 유지하지 않는다.
- 순서 동점: 도착, ordinal, ID. 자원 ECT 동점 CPU. 생산 규칙의 출처에 없는 동점 규칙은 원 값으로 표시하지 않는다.
- 기한 초과: 작업을 버리거나 취소하지 않는다. aging/긴급 가중치/추가 SLA guard/온도 guard/자발적 냉각 대기 없음. FIFO/SPT의 지연·기아 가능성은 결과에 포함한다.
- 실제 점유 lane에는 배정하지 않는다. 평균 예상 종료를 초과한 실행은 비용을 0으로 채우지 않고 다음 실제 공개 event를 기다린다.
- 비선점 whole-request, 최대2건. 분류CPU/GPU·탐지CPU만 허용하며 병행은 기존 지원 분류GPU+탐지CPU뿐이다.
- 비용 예측: 기존 mean 5단계, 갱신 없음. energy/AP 계수·worker release/lane 재사용 경계·120초 전량 요구·0..120초 whole J·35..180초1초 grid AP 고정. 표면 온도/미지원 기기/NPU 비용은 계산하지 않는다.
- 엔진 opt-in ABI 식별자는 기존 EFT_REFERENCE를 사용하되 공개 정책 ID·파일·결과를 분리한다. 엔진과 기존 정책 소스는 수정하지 않는다.
- 제조현장 배포 효과·StarPU 전체·정확 HEFT·물리 절감을 재현했다고 주장할 수 없다. 최고 AP는 모형 AP이며 표면 온도가 아니다. PC 제어시간을 폰 에너지/지연으로 바꾸지 않는다.

## 원 출처와 접근 경계

1. *Heuristics for scheduling unrelated parallel machines*, Computers & Operations Research 18(3), 1991, 323–331. ECT heuristic과 비선점 이종 병렬기계 문제의 원 논문. <https://doi.org/10.1016/0305-0548(91)90034-O>. 공식 출판사 검색 색인의 초록 확인, 상세 본문 직접 열기는 403. 원 논문의 미확인 pseudocode/동점/현업 도입 사례를 채우지 않았다.
2. *Evolving dispatching rules using genetic programming for solving multi-objective flexible job-shop problems*, Computers & Industrial Engineering 54(3), 2008, 453–473. SPT/EDD 및 작업 순서·기계 선택 구분. <https://doi.org/10.1016/j.cie.2007.08.008>. 공식 출판사 검색 색인에서 본문 발췌 확인, 직접 열기 403. 해당 GP 알고리즘 전체는 재현하지 않는다.

출판 버전/DOI가 버전 식별자다. 공개 제품 코드의 commit은 해당 없음. 위 단순 규칙의 판단 조건만 사용하며 결과 뒤 임계값·seed·규칙 변형 탐색은 0회다.
