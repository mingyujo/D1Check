# 선행연구와 D1Check의 기여 경계

## 2026-10-06 산업공학 공정 스케줄링의 적용 후보

후속 사용자 진행 승인으로 [제한 적용·최종 결과](results/industrial_scheduling_01/README.md)를 완료했다. 아래는 실행 전에 작성한 조사/권고다. ATC·CPU 병목과 큐 보호, offline 참고 일정을 구현했으나 기본정책 채택/실기기 우월성 확인은 아니다. 작은 burst의 J 감소/긴급 지연 상충과 AP 열 판독 한계가 남는다.

**결론:** 적용할 가치가 있다. 가장 가까운 문제는 작업별 처리시간·허용 자원이 다른 비선점 병렬기계 배정에 도착·기한·병행 호환성·열 이력을 추가한 것이다. 여러 공정을 CPU→GPU 순서로 그대로 옮기는 일반 job shop은 아니다. 아래는 **후보 권고이며 구현·성능 확인·기본 채택이 아니다.**

### 공정과 앱의 대응

| 공정 개념 | D1Check 대응 | 유지할 경계 |
|---|---|---|
| 주문·납기 | 요청·예정 도착·응답 기한 | 투입을 늦춰도 원래 도착·기한·전체 예정 요청 분모와 대기시간 유지 |
| 대체 설비 | 모델별 CPU/GPU 허용 경로 | 현재 요청 프로필은 분류 CPU/GPU·탐지 CPU. 탐지 GPU/S26 NPU 자동 추가 금지 |
| 설비 점유 | dispatch→lane_available | 응답·output_ready·저장·worker_release·lane 해제를 혼동하지 않음 |
| 설비 간 간섭·이력 | task×backend 병행 및 연속 AP/잔열 상태 | 모든 CPU+GPU를 합치지 않음. A24 열→처리시간 미식별; S26 별도 근거 |

근거: [요청 실행·비용 코드](../tools/d1_empirical_request_policy.py), [조건 탐색](results/scheduler_conditions_01/README.md), [대안 비교](results/scheduler_alternatives_01/README.md). `place`는 같은 backend 또는 미지원 병행 충돌을 피하고, `score`는 공통창의 resident 기준 전력과 상태별 추가전력을 적분한다.

### 방법별 적합성

| 방법·1차 출처 | 적용 가능한 부분 | 기존 시도와 차이·제약·우선순위 |
|---|---|---|
| TOC/DBR·Workload Control — [Thürer 외, IJPE 2017](https://www.sciencedirect.com/science/article/pii/S0925527317301196), DOI 10.1016/j.ijpe.2017.03.025 | 병목 또는 전체 자원의 작업량을 기준으로 투입 조절. 탐지 CPU의 남은 점유시간·기한을 보고 분류의 CPU/GPU 배정·순서 조절 | **유력한 온라인 후보.** 고정 token rate와 달리 현재 CPU 필수 수요 반영. 탐지 무조건 우선/분류 무조건 GPU가 아니며 기존 큐 서비스 보호 재사용. DBR 원 알고리즘 재현이 아닌 원리 적용 |
| ATC — [Vepsäläinen·Morton, Management Science 1987](https://pubsonline.informs.org/doi/10.1287/mnsc.33.8.1035), DOI 10.1287/mnsc.33.8.1035 | 처리시간·납기 여유·지연 가중치를 결합해 현재 큐의 우선순위 결정 | **작은 추가 비교 후보.** LLF/EFT와 일정이 실제 다른지 확인. 우리 응답 기한과 점유 종료의 차이를 반영. 가중치는 결과 전에 고정. ATC 자체는 J/AP 절감 규칙이 아님 |
| CONWIP/Kanban — [Spearman·Woodruff·Hopp, IJPR 1990](https://www.tandfonline.com/doi/abs/10.1080/00207549008942761), DOI 10.1080/00207549008942761 | 완료에 따라 투입하며 공정 내 재공 제한 | **현재 우선순위 낮음.** 이미 최대 두 lane·병행 제약. 대기열에 따른 추가 메모리/전력 효과는 미식별. active 개수 제한은 중복 또는 서비스 악화 가능. 투입 전 대기도 응답에 포함 |
| MILP/CP 기반 작은 일정 최적화 — [OR-Tools 공식 예제](https://developers.google.com/optimization/scheduling/job_shop) | 배정·시작·중복·선후 제약을 함께 다뤄 작은 입력의 개선 여지/상충 기준 생성 | **온라인 후보 전에 확인할 가치.** 미래 도착을 아는 offline 참고값은 배포 정책 아님. 예제의 makespan 목적만으로 우리 J/AP·호환성·응답 경계를 해결하지 못함. 시간 제한 탐색이면 최적성 증명 없이 최적해로 부르지 않음 |
| Rolling horizon·다목적 일정 | 짧은 예측에서 첫 행동 실행, 서비스 제약 아래 J 최소 또는 AP 최소 | MPC·목적별 선택은 이미 시험. 이름만 바꿔 반복하지 않음. 열/서비스 한도는 요구로 사전 고정; 공동 우승 강요 금지 |
| 에너지형 flexible job shop — [Shen 외, EJOR 2023](https://www.sciencedirect.com/science/article/pii/S0377221723002679), DOI 10.1016/j.ejor.2023.03.041 | 우리에게는 자원 선택·실제 단독/병행 점유시간 변경이 J를 바꾸는 경로 | 해당 논문의 시간대별 전기요금 절감을 J 절감으로 전용하지 않음. 미측정 unload/재적재·DVFS·전원 off 절감은 기본 모형에 넣지 않고 명시적 가정 탐색으로만 분리 |

DBR/WLC 논문은 병목 강도에 따라 유리한 방식이 달라지는 결과를 보고한다. D1Check 효과 증명이 아니라 병목 유무별로 평가할 이유다. 출판사 공개 초록/preview 범위이며 상세 파라미터 재현은 아니다. ATC도 공식 초록, CONWIP은 원 논문 공개 요약/도입, 에너지 논문은 공개 초록 범위로 확인했다. 접근 범위를 넘는 우월성 주장을 하지 않는다.

### 에너지·열을 바꾸는 행동과 다음 PC 작업

현재 J는 고정 common window의 resident 전력에 상태별 추가전력×점유시간을 더한다. **동일 상태별 총 점유시간을 유지한 채 순서만 바꾸면 J는 같다.** 순서·유예는 AP 경로/최고값을 바꿀 수 있지만 기한 비용이 생긴다. J 개선은 자원 선택·병행 점유 구성·처리시간 등이 바뀌어야 한다. 전원을 끄는 공장식 절감을 현재 모형이 이미 표현하지는 않는다.

새 규칙은 기존 상태·계수로 시험 가능하다. 새로운 물리 현상까지 넣는 계산은 가정 탐색과 실측 기반 결과를 분리한다. 기존 token/JIT/PAIR·LLF/backfill/MPC·RL/학습 선택기의 결과는 재사용하고 전체 배치를 반복하지 않는다. [기존 PAIR 보호](results/pair_service_guard_01/README.md)는 국소 큐 보호이며 미래 서비스 보장은 아니다.

권고하는 다음 PC 작업 하나는 **작은 저장 입력의 일정 탐색 기준과 ATC·CPU 병목 인지 후보의 제한 비교**다. offline 탐색으로 개선 여지를 먼저 확인하고 같은 입력의 온라인 EFT와 비교한다. 작은 부분 입력임을 표시하고 전체48요청 결과로 확대하지 않는다. 온라인 입력은 현재 도착 큐만 사용; 미래 도착/실현 처리시간 누설 금지. 동일 처리시간 시나리오·초기 열 이력·J/AP 창·전체 분모를 유지한다.

기한 위반·실패·미완료, 긴급 P95, 공통창 J, 최고AP/열부담, 결정 계산시간을 따로 보고한다. 현재 제어 계산 추가 에너지0 가정도 표시한다. 개선 여지가 없거나 서비스와 상충하면 그대로 종료하며 결과에 맞춰 새 물리계수·후보를 계속 추가하지 않는다. 목표는 새로운 이름의 규칙이 아니라 **정책으로 줄일 수 있는 차이와 그 원인이 되는 결정**이다.

검증: 2026-10-06, 기준 HEAD `8cf5aa32ec5753a00ad73d8e4841032a98bb4c46` + 이번 문서 diff. `place`/`score`, token/PAIR, LLF/backfill/MPC 구현과 저장 결과를 대조했다. 문서 상대 링크와 `git diff --check` 확인. 코드·시뮬레이션·학습·기기 실행 없음. 계수/strict/experiment_ready=false·기존 FAIL·사용자 파일·다른 worktree 보존. 후보 채택이 아니므로 DECISIONS에 정책 채택으로 기록하지 않는다.

## 2026-10-06 보완 — 열 인지 선행연구와 현재 구현 대응

이 절은 최신 요청별 PC 후보를 대상으로 한다. 아래 9/22 비교는 당시 범위의 기록으로 보존한다. 새 문헌 비교는 우월성·독창성 인증이나 새 정책 채택이 아니다. [팀원 조사와 정정](BACKGROUND_EVIDENCE_AND_USE_CASES_20261004.md), [발표 안내](results/final_presentation_01/README.md).

### 입력·행동·목적·검증 범위

| 대상 | 입력/상태 | 결정 행동 | 목적·서비스 조건 | 확인 범위·우리와의 관계 |
|---|---|---|---|---|
| Tan·Cao, TMC 2024 | 열 상태를 고려한 모바일 NPU 기기 scheduling | GPU/NPU 활용의 열 인지 배정; HBS/DRLS의 상세 규칙은 원문 재확인 필요 | 과열을 피하며 처리시간·정확도 절충 | [소속 대학 서지·초록](https://pure.psu.edu/en/publications/thermal-aware-scheduling-for-deep-learning-on-mobile-devices-with/), DOI 10.1109/TMC.2024.3379501. 이번 PDF 접근 실패. 팀원이 전달한 67°C/600→200MHz/10→2fps는 이번에 검증하지 못함. 기기 차이·RL 비필수는 기술적 신규성 아님 |
| Sung 외, USENIX ATC 2023 | DNN 특성, CPU/GPU 이용률·메모리 등 환경 관측 | 앱별 DQN이 실행 구성 선택; CPU thread/NNAPI 선호 등 | 지연×전력 비용, 기한 초과 벌점 | [공개 본문](https://www.usenix.org/system/files/atc23-sung.pdf) §3–4, §6. 여러 앱이 각자 선택하는 분산 조율. **기한을 이미 고려**한다. 우리 단일 앱의 중앙 요청 큐와 구분. 본문 관련 절 확인이며 전체 재현 아님 |
| Zhou 외, Play It Cool, ICML DyNN Workshop 2022 | 열 상태에 따른 실행 조건 | 모델 크기 전환 | 지연–정확도 절충 | [저자 공개 초록](https://arxiv.org/abs/2206.10849). 고정 모델·동일 작업량을 유지하는 우리 범위와 다름; 우리 방식의 우월성은 아님 |
| D1 조건·목적별 선택표 | 사전 지정 부하 조합과 개발 비용 | 기한 적격 정책 중 energy/thermal 모드로 선택 | energy: 평균J→최고AP; thermal: 최고AP→AP면적→J | [구현](../tools/d1_scheduler_condition_selector.py), [결과](results/scheduler_conditions_01/README.md). 27중17선택 가능,10불가 보존. 새seed PC 평가이며 온라인 부하 식별·폰 절감 아님 |
| D1 요청별 예측 배정·유예/MPC | 현재 도착 큐·lane·개발 처리시간·모형 상태 | 합법 자원·즉시/제한 유예 후 첫 행동 실행 | 기한과 비용의 국소 예측 비교 | [요청 후보](results/empirical_request_policy_01/README.md), [MPC 등](results/scheduler_alternatives_01/README.md). 이후 도착·예측오차로 전역 서비스/J/AP 보장 안 됨. 기본 채택하지 않음 |
| D1 PAIR 기한 보호 | 현재 도착 큐와 long_context 처리시간 추정 | PAIR 제안이 EFT보다 어느 요청의 예측 지각을 늘리면 EFT로 전환 | 현재 큐의 상대 서비스 보호 | [구현](../tools/d1_pair_service_guard.py), [결과](results/pair_service_guard_01/README.md). 해당 조건576/576, 새seed −0.560587J/+0.225968°C. WCET·미래 기한 보장·실기기 효과 아님 |

### 발표에 사용할 차별성의 범위

> 열 인지 배정, 앱 수준 다중 DNN 조율, 모델 전환은 이미 연구되어 있다. D1Check는 고정된 두 모델과 동일 작업량 조건에서 요청의 자원·실행 시점을 바꾸고, 기한 충족과 기기 전체 공통창 에너지·AP의 상충을 실측 기반 모형으로 비교한다. 기기별 지원 조건과 실패 분모를 보존하며, 선택 규칙의 PC 결과와 실기기 효과를 구분한다.

이는 구현·평가 범위 설명이지 최초성 증명은 아니다. EDF/LLF/EFT/backfill/token bucket/MPC는 기존 원리의 프로젝트 적용이다. 현재 큐 보호도 새로운 이론 보장으로 표현하지 않는다. RL을 시험했으나 최종 필수·기본정책으로 채택하지 않았다는 사실과, RL 미사용을 차별성으로 삼는 주장은 다르다.

### 바로 활용할 것 / 이번에 추가하지 않을 것

- 발표: R4·R10·R3 비교표와 위 범위 문장. 주 방법은 조건·목적별 선택 규칙, 요청별 보호는 좁은 PC 보완 결과로 구분한다.
- R10의 보상 기반 기한 유도와 우리 별도 큐 보호의 구조 차이는 설명 가능하다. 동일 행동/입력/측정 경계에서 재현하지 않았으므로 성능 우열은 비교하지 않는다.
- S26 열 이력→처리율 자료의 관련 선행연구로 R4를 연결하되 A24에 계수를 전용하지 않는다. S26 구현/검증 완료 여부는 담당 원본 확인을 따른다.
- 새 DQN/HBS 구현·학습·시뮬레이션·실측 없음. 논문 구현을 축소 이식했을 때 원 알고리즘 재현이라고 부르지 않는다. 기존 정책별 저장 결과를 재사용한다.

검증: 2026-10-06, 기준 HEAD da5d798f9e109c5c2a4b0ab82578f9a873ad4ed6 + 이번 문서 diff. 위 두 구현의 선택/지각 판정과 기존 README 수치를 대조했다. 외부 자료는 연결된 원문/공식 문서의 해당 범위만 확인. 문서 상대 링크와 git diff --check 확인; 코드·수치 변경이 없어 전체 테스트/배치 재실행 없음. 기기 명령0, experiment_ready=false 유지.

후속 `support-constrained-simulation-v1`에도 아래 문헌 근거를 적용한다. 후속 범위는 배치 시작 전 layout 선택이며 일반 온라인 동적 배정의 차별성을 입증하지 않는다.

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
