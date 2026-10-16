# S26 NPU 확장 설계 반영 (2026-10-11)

상태: 설계 범위 변경. 사용자 최신 지시로 S26 확장 연구에 NPU를 포함한다. 처음 CPU/GPU 설계의 NPU 제외는 그 당시 범위로 보존한다. 기존 S26-SERVICE-CONNECTION-01은 CPU/GPU 연결 결과이며, 이 문서가 그 코드의 NPU 지원 완료를 뜻하지 않는다. 이번 신규 S26 학습·시뮬레이션 실험·물리 적합·APK·기기 실행은 각각0회다.

## 공통 구조와 지원 범위

A24/S26는 같은 사건·후보·마스크·정책·평가 인터페이스를 사용하고 resource capability와 기기별 프로필을 분리한다. A24는 CPU/GPU, S26 확장판은 CPU/GPU/NPU다. 지원 자원이3개인 것과 동시 실행3건은 다르다.

| 작업/실행 조합 | A24 | S26 확장 설계 |
|---|---|---|
| 분류 CPU/GPU | 유지 | 포함 |
| 분류 NPU | 없음 | 측정 경로를 포함, 품질 승인 gate 별도 |
| 탐지 CPU | 유지 | 포함 |
| 분류 GPU+탐지 CPU | 유지 | 포함 |
| 분류 NPU+탐지 CPU | 없음 | 측정 경로를 포함, 품질 승인 gate 별도 |
| 탐지 GPU/NPU | 미지원 | 마스킹 |
| 분류 GPU+분류 NPU, 분류 CPU+다른 가속기 | 현재 지원하지 않음 | 측정 근거 없는 병행으로 마스킹 |
| CPU/GPU/NPU 3건 동시 | 없음 | 외삽이므로 마스킹 |

이전 NPU 제외를 해제하는 사용자 지시는 NPU 품질·병행·열 정확도 PASS나 3건 동시 승인으로 해석하지 않는다. 지원 physical 조합의 등록과 경로별 품질 적격성을 분리한다. 미승인 경로는 관측 재생·오차 연구에 사용할 수 있으나 승인된 운영 후보로 자동 활성화하지 않는다. 마스크는 납기·서비스 성능을 보장하지 않는다.

## 확보한 부품과 남은 근거

별도 clone의 s26-parsim `994ca614490e5f030baa6e9c951fba42d6fa052d`: a24fmt_v1/out/s26_a24fmt_model.json은 NPU_PARALLEL|classification|NPU와 NPU_PARALLEL|detection|CPU 두 셀 각각384요청의5단계 평균을 이미 제공한다. parsim_v1은 동일 문맥의 intact 단계 묶음 분포와 NPU dispatch를 제공한다. 따라서 NPU 처리시간 자료가 없어서 설계를 못 하는 상태는 아니다.

기존4셀 service-only 프로필을6셀로 확장할 자료는 있다. CPU/GPU 단독/병행과 NPU 병행의 문맥을 보존하고, NPU가 점유 중인 탐지CPU에는 NPU_PARALLEL 셀을 선택한다. 병행 세션 평균을 단독 NPU나 모든 겹침률에 옮기는 것은 연결 가정이며 새 단독 검증으로 주장하지 않는다. CPU/GPU/NPU 동시 실제AVAILABLE 소유·중복dispatch·응답 완료와 점유 종료의 분리는 그대로 유지한다.

E0/T1의6상태는 cls_CPU,det_CPU,cls_GPU,cls_NPU,det_CPU&cls_GPU,det_CPU&cls_NPU다. idle/resident baseline은 별도다. 담당자에게 이6상태를 그대로 요청한다. 현재 JSON의 증분 전력/theta는 공선·미식별 판정 때문에 사용하지 않고, 상태 분리9세션 이후 계수와 식별성/정책 짝차 검증을 확인한다. NPU 전력을 GPU 또는 A24 계수로 채우지 않는다.

NPU 품질은 request-runner와 Q20의 exact APK/source/model/input/runtime/정밀도 귀속, 명시한 FP16 허용 기준과 결과가 필요하다. GPU FP32 자료만으로 NPU 품질을 승인하지 않는다. 장시간 비교에는 CPU 감속과 NPU 제어의 적용 범위 검증이 필요하며 현재 고정 S0는 약120초 이내 탐색용이다.

## PPO 인터페이스 변경

후보는 전체 현재 도착 큐 top4+oldest C/D+현재 복귀 행동 요청의 합집합≤8을 기본으로 유지한다. 각분류 요청의 CPU/GPU/NPU 단일 행동, 각탐지의CPU 행동, C_GPU+D_CPU와 C_NPU+D_CPU의 두 종류 bundle, 중복 제거한 자원 대기1행동을 구성한다. 같은 요청 중복·미지원 병행·busy owner는 mask0다. 임의 냉각 대기는 추가하지 않는다.

후보 안 분류C·탐지D, C+D≤8일 때 행동 상한은 `3C+D+2CD+1≤49`다. 현재 A24 pad32로는 부족하며 확장안 pad64를 사용한다. 마지막1은 모든 wait가 다음도착/첫AVAILABLE/관측추정timer에 함께 깨어나는 기존 계약으로 하나로 합칠 때의 상한이다. 대기 의미를 추가하면 상한을 다시 계산해야 한다. 이49는 행동 개수이고 기존 A24 ACTION_DIM49(행동 feature 차원)와 다른 숫자다.

상태에는3자원 owner/phase/현재 관측 추정, 요청별3경로 처리시간·지원/적격성, 장치 capability를 포함한다. 행동 feature의 backend 인코딩도3개로 바꾼다. 최종 state/feature 차원은 encoder 구현과 상한 검사로 확정한다. 기존198/206 state·49 action feature·32 padding을 무근거로 복사하지 않는다. 새 schema와 fresh PPO weights를 사용한다. 서비스 전용 연구와 J/AP 비용이 식별된 연구는 별도 objective/schema이며 비용 없는 값을0으로 채워 기존 weights를 쓰지 않는다.

후보 점수에는 공개 측정 기반 추정과 현재 관측 이력만 쓴다. NPU 실현 단계·미래 온도/전력·도착은 engine-private이며 온라인 PPO나 ATC에 노출하지 않는다. 학습·개발·새확인·운영의 같은 상태/후보/mask 의미를 유지한다.

## 비교 실험은 세 층으로 분리

1. A24 CPU/GPU: 기존 연구 결과를 보존한다.
2. S26 CPU/GPU: 공통 지원으로 기기 차이를 비교한다.
3. S26 CPU/GPU/NPU: 동일 S26 요청열·납기에서 NPU 자원 개방 효과를 비교한다.

각층의 FIFO/EFT, EDD, ATC, PPO에 같은 자원·품질 적격성과 원서비스 계약을 제공한다. 우리 PPO만 NPU를 쓰게 하면 정책 효과와 자원 추가 효과가 섞인다. CPU/GPU 공통 평가와 NPU 추가 평가를 한 평균으로 합치지 않는다. 규칙의 NPU on/off는 같은 규칙·요청의 비교이고, 별도 학습한 PPO의 차이는 자원 개방과 학습의 전체 효과다. 순수 하드웨어 효과라고 주장하지 않는다.

같은 절대 요청열·납기로 기기 이식성을 평가하고, 별도 기기별 부하 수준을 맞춘 조건에서 스케줄링 stress를 평가한다. 원긴급1.5/일반6초와 신규 요청별 납기를 함께 보호한다. 최종 확인을 본 뒤 NPU 정책/품질 기준/모형을 재선택하지 않는다. PC 판단시간은 phone 시간/에너지로 환산하지 않는다.

## 다음 구현 순서

1. 현재 CPU/GPU source·weights·프로필·결과를 보존하고 별도NPU schema/capability·6셀 프로필·3lane owner·지원 pair를 구현한다.
2. 분류NPU/탐지CPU 응답≠AVAILABLE, 두 pair 지원, 두 가속기/3건/탐지NPU 거부, 중복·동시 사건 CPU→GPU→NPU, 미래 정보 차단,49상한/pad64를 계약 검사한다.
3. 관측 재생용 서비스 연구와 품질 승인된 정책 후보 연구를 구분해 유한자료·seed·실행예산을 등록한다. S26 새 학습/실험은 아직 시작하지 않았다.
4. 상태분리·NPU품질/정밀도 근거 후 비용 모형을 붙이고 기기별 모형 오차와 정책 짝차를 별도 확인한다.

근거: AGENTS.md의 기기별지원/품질/3건 금지, docs/S26_SIMULATION_PLAN_20261011.md, upstream parsim_v1/{MODEL_CARD.md,rules.py,adapter.py}, a24fmt_v1/{DECISIONS_A24FMT.md,README.md,out/s26_a24fmt_model.json}. 사용자 최신 NPU 포함 지시가 초기 범위의 NPU 제외를 갱신하며 과거 결과를 소급 변경하지 않는다.
