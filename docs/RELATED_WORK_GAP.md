# 선행연구와 D1Check의 기여 경계

2026-09-22 확인. PC 계획 `pc-simulation-plan-v1`의 문헌 근거다. 논문 성능 수치를 D1Check의 예상 성능으로 전용하지 않는다. 아래는 지정된 여섯 연구의 비교이며 전체 최신 문헌에 대한 독창성 증명은 아니다.

## 1차 자료 비교

| 연구·원래 서지 | 이번에 확인한 1차 자료·위치 | 이미 다루는 문제·기술 | D1Check와의 차이 및 중복 |
| --- | --- | --- | --- |
| Band: Coordinated Multi-DNN Inference on Heterogeneous Mobile Processors, MobiSys 2022, DOI `10.1145/3498361.3538948` | [공식 프로젝트](https://github.com/mrsnu/band), [연구진 소속 대학의 논문 초록](https://snu.elsevierpure.com/en/publications/band-coordinated-multi-dnn-inference-on-heterogeneous-mobile-proc/), [프로젝트 페이지](https://band.snu.ac.kr/) | subgraph 분할, 이종 프로세서의 동적 multi-DNN scheduling, SLO를 고려한다. Android API와 backend 조정이 이미 있다. | D1Check는 graph를 분할하지 않는 전체 요청 비선점 배정. Android에서 CPU/GPU를 선택한다는 사실은 차별성이 아니다. ACM 원문 접근 실패로 세부 알고리즘·실험 설정은 `external_verification_pending`; 공식 초록/코드만 확인한 범위를 넘지 않는다. |
| CARIn: Constraint-Aware and Responsive Inference on Heterogeneous Devices for Single- and Multi-DNN Workloads, TECS 2024, DOI `10.1145/3665868` | [저자 원문](https://arxiv.org/html/2409.01089v1), §3~4, 특히 §4.3.3~4.3.4 | 사용자 SLO와 다목적 최적화, RASS 구성 집합, 환경에 따른 모델/processor switching. | 다목적·기기별 프로파일·상태 적응 자체가 상당히 중복된다. D1Check는 모델 품질·graph를 고정하고 요청 큐·일반 서비스 손실·provenance를 검증하려는 좁은 후보다. 단순히 black-box라고 더 새롭다고 주장할 수 없다. |
| Miriam: Exploiting Elastic Kernels for Real-time Multi-DNN Inference on Edge GPU | [저자 원문](https://arxiv.org/html/2307.04339v1), §5~7 | CUDA elastic kernel 생성과 runtime kernel 조정으로 mixed-critical DNN 경합 및 응답/throughput 상충을 다룬다. | D1Check는 kernel 변환 없이 Android runtime 밖의 요청 경계만 제어한다. 긴급/일반 보호의 필요성은 이미 알려졌다. 플랫폼·제어 단위가 달라 직접 성능비를 만들 수 없다. |
| Pantheon: Preemptible Multi-DNN Inference on Mobile Edge GPUs, MobiSys 2024, DOI `10.1145/3643832.3661878` | [저자 제공 원문 PDF](https://www.cs.cityu.edu.hk/~zhenjili/2024-MobiSys-Pantheon.pdf), pp.1~4, §3 | GPU stream 우선순위와 chunk 단위 preemption, 남은 deadline에 따른 실시간 요청 보호. | D1Check는 실행 중 추론을 선점하지 않는다. 논문의 mobile edge GPU를 Galaxy A24에서 같은 API로 실행 가능하다는 근거로 사용하지 않는다. deadline-aware scheduling 자체는 기여가 아니다. |
| Deep Learning Inference on Heterogeneous Mobile Processors: Potentials and Pitfalls | [저자 원문](https://arxiv.org/html/2405.01851v1), §3.1~3.4 | 모델·기기·runtime·경합·환경에 따라 병렬 방식 성능이 달라지고, 단독 실행이 더 유리할 수 있음을 실증한다. | A24의 CPU solo 우세나 co-run 상충관계는 이 일반 현상의 새로운 발견이 아니다. D1Check는 현재 exact 모델/입력/runtime의 calibration 값을 직접 확보해야 한다. |
| MobiSR: Efficient On-Device Super-Resolution through Heterogeneous Mobile Processors, MobiCom 2019, DOI `10.1145/3300061.3345455` | [저자 원문](https://arxiv.org/html/1908.07985v1), §3 | 모델 압축·품질/지연 설계 탐색, patch 난이도에 따른 model-engine 배정. | 기기별 측정과 작업에 따른 이종 배정은 기존 방법이다. D1Check는 서로 다른 두 task의 모델/정밀도를 유지하고 urgent/normal 서비스 지표를 비교한다. |

원래 제목과 DOI를 보존했다. Band는 원문 미확인과 공식 자료 확인을 구분한다. 나머지 다섯 건은 원문에 접근해 위 기술 내용과 위치를 확인했다. 검색 결과 요약이나 블로그를 기술 근거로 쓰지 않았다.

## 비신규성과 기여 후보

이미 알려진 배경은 GPU가 모든 모델·기기에서 항상 빠르지 않다는 점, multi-DNN 자원 경합, 긴급 응답과 throughput/makespan의 상충, 작업·기기·runtime에 따른 배정 차이, priority/deadline-aware scheduling의 필요성이다. 위 문헌은 각기 다른 범위에서 이 배경을 다룬다. 모든 논문이 모든 명제를 각각 증명했다는 뜻은 아니다.

**A24 실측의 역할은 calibration이다.** 현재 A24·모델·runtime 조건에서 PC 시뮬레이션에 사용할 서비스시간, setup/active 상태, 관측된 resident dispatch 영향, 동시 실행 간섭, 메모리 및 열 제약의 경험분포를 확보한다. 동적 unload/reload 전환은 측정되지 않았으므로 그 분포까지 확보했다고 쓰지 않는다.

D1Check의 후보 기여는 상용 Android 한 앱에서 OS·driver·kernel·DNN graph를 수정하지 않는 전체 요청 제어, 긴급 P95와 일반 서비스 손실을 함께 보는 의사결정, 기기별 empirical calibration과 memory/thermal/실패 제약, 입력부터 결과까지 추적 가능한 재현 계약이다. 특히 co-run을 선택하거나 거부하는 **정량 규칙과 적용 영역**을 강한 기준정책 대비 입증해야 한다. 현재는 효과도 독창성도 확정되지 않았다. provenance의 충실성은 연구 신뢰도를 높이지만 그것만으로 새로운 scheduling 알고리즘이 되지는 않는다.

직접 측정이 필요한 값은 exact A24 서비스·setup·release·동시 실행 시계열·메모리 admission과 출력 동등성이다. 선행논문의 타 기기 수치로 채울 수 없다. 반대로 그 값을 측정했다는 사실만으로 임의 큐 순서·도착률에서의 반사실적 서비스시간이 식별되지는 않는다.

금지 주장: 세계 최초, GPU가 항상 느리다는 증명, 모든 스마트폰/온디바이스 AI 일반화, 미측정 에너지·배터리 개선, 선행 시스템 대비 미실행 성능 우위. NPU·강화학습·모델 압축을 현재 기여에 추가하지 않는다.
