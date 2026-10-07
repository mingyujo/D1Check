# Triton 규칙의 사전 대응과 StarPU 검토

2026-10-07 · EXTERNAL-RULES-12 · 성능 결과를 보기 전에 고정한다.

목표: 같은 기한과 예정 요청 전량을 유지하면서 공통 관측창 에너지와 AP 온도 부담을 줄이는가. 제어 방식의 유사성은 선정 필수 조건이 아니다. 이번 결과는 동일 A24 모형에서 옮긴 판단 규칙의 결과이며 외부 제품 전체 실행 또는 실기기 효과가 아니다.

| 원 개념 | 엔진 대응 | 유지 | 변경·생략 | 수준과 주장 |
|---|---|---|---|---|
| Triton ModelInstance | 분류 GPU 1개·탐지 CPU 1개 고정 인스턴스 | 인스턴스별 한 번에 한 작업 | 서버/CUDA/백엔드 이식 없음, 분류 CPU는 이 분리 실험에서 사용 안 함 | B: whole-request 인스턴스 제한적 적용 |
| specific request queue | 작업별 도착 FIFO | 실행 대상 선택 뒤에도 요청 전량 보존 | batching/cache/취소/timeout 비활성; 원 CPU/GPU 배정 최적화 알고리즘으로 부르지 않음 | B: 대기·순서·자원 점유 효과 |
| ScaledPriority | 완료 실행 횟수 × max(설정 priority,1) | 최솟값 인스턴스가 staged heap 맨 앞, 횟수는 Release에서 증가 | 동일 시각 사건은 엔진 순서 CPU release→GPU release→도착 ordinal. 원 서버의 비동기 IPC 순서 아님 | 조건식 A, 이벤트 대응 B |
| OnStage/OnRelease/AttemptAllocation | 제출·완료 callback 순서와 즉시 allocation attempt | OnRelease는 자체 다음 요청 restage 후 최종 attempt, 자원 부족시 heap top만 검사 | 모든 staged 인스턴스를 모은 뒤 한꺼번에 최적화하지 않음 | B, 소스 control flow 보존 |
| 자원 resource/count/global | 공통 실행 token, 각 인스턴스 1개 필요, 총 1/2개 | 확보 후 실행, 완료 후 반환 | 가상의 메모리/전력량으로 해석하지 않음. capacity는 이번 실험 설정 | B, 자원 제한으로 생긴 일정의 J/AP 평가 |
| instance Release | 5단계 후 실제 lane_available | 응답/저장/worker release와 분리 | 서버 Invoke 종료 대신 전체 request 종료 | B, 조기 자원 반환 없음 |
| priority queue 동점 | 최대 두 staged 항목에서 먼저 stage된 항목 | 두 원소 heap의 동일-score 비교 결과 | 일반 heap/여러 인스턴스에서 FIFO 보장하지 않음. callback 동시 순서는 엔진 규약 | B, 다인스턴스 일반화 없음 |
| Rate limit off | 같은 인스턴스·작업별 FIFO로 즉시 실행 | 자원 경쟁 제한 없음 | 기존 SPLIT의 urgent/aging 우선과 다를 수 있음 | 제한 해제 자체 대조군, 기본 설정과 제한 설정 분리 |
| StarPU DMDA worker 큐/성능·에너지·전송 모델 | 이번은 조사만 | 원 점수와 기본값은 sources.json에 기록 | 요청별 에너지 귀속·전송/prefetch 분리·허용 joint-state와 worker 독립 큐 대응 미확정 | C: 이번 성능 배치 보류; 공개 스케줄러 부재나 원 규칙의 실패가 아님 |

## 결과 전 설정

- Triton core `3af839d613da6995051f9bcfab00efe2eac87d4c`, `src/rate_limiter.cc/.h`의 동기 control flow. BSD-3-Clause 귀속을 NOTICE/LICENSE로 보존한다.
- 분류·탐지 기본 priority 각각 1. 원 0은1 취급. 이번 분류 우대는 분류1·탐지2의 명시적 설정이며 원 기본값 아님. 횟수 기반 배분이지 엄격 urgent 우선 또는 기한 보장이 아니다.
- 제한 해제 + capacity1/2 × equal/class-weight, 총5개 설정. global token이 없으면 제한 켜기 자체가 병행을 줄이지 않는다. capacity2는 그대로 별도 공개한다.
- 앞선 external_rules_01의 seed610810001..004, low/queue/burst/sustained, mean/short_context/long_context 48조건을 byte 그대로 재사용. 이미 공개된 확인자료이므로 새 독립 검증이 아니다. 튜닝·최우수 설정 선택0. 다섯 설정 전부 보고한다.
- 하위 인스턴스 고정 대조는 rate-off. 정책 전체 비교는 기존 완료 CPU/SPLIT/EFT/SHARED_EDF/SHARED_EFT/자체2규칙/Band 384행을 입력·소스·모형SHA 확인 후 재사용한다. 기존 정책 중 CPU/GPU 배정도 다른 정책과의 차이는 rate limiter만의 인과 효과가 아니다.
- J0..120초, AP35..180초. 전체 lane 완료 전 미완료가 있으면 J는 부분 작업량, AP180 null. 긴급 output_ready1.5초·일반 persist_complete6초·lane_available 경계 불변. AP 안전 온도 한도와 한도 초과 시간 null.
- 기기/ADB/학습0. 동결 A243cell·허용CG_DC·기존 에너지/AP 계수와 strict/experiment_ready=false 유지. 미지원 NPU/DVFS/선점/탐지GPU 비용 없음.
- 원 서버 overhead·메모리·전송·실제 스케줄러 전력은 계산하지 않음. 기존 PC 차등 controller overhead0 가정, PC callback 시간은 별도 측정.
- 대표는 결과와 무관하게 최소seed/queue/mean에서 rate-off와 cap1/equal, 최소seed/sustained/mean에서 rate-off와cap1/class-weight. 전체 조건을 함께 보존한다.
- 정식240환경, fixture·진단·복구 포함400환경 이하. 최초작업 시작부터 보수적 단일 벽시계3시간, 마지막20분 본실행 중단·저장 예약. 작은pilot5행은 정식행에 포함하며 재계산하지 않음.
