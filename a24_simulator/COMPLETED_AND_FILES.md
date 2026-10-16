**요청 수 확장 완료:** [48~3,072개 비교/파일 안내](docs/LONG_SCALE_COMPARISON.md) · [장시간 결과표](results/LONG_SCALE_REPORT_20261017_01/REPORT.html). 최대12.23분을 계산했고 EDF 기저 비중67.97→48.46%입니다. 고정RL 대비 차이/납기/손해를 모두 보존했으며 장시간은 미검증 외삽입니다. 기존서버/모형/NN·소비511/512 불변, 별도24예약 중19START·정상18/실패1·예약/주기조회OFF.

# 최신 추가 완료: 입력 선택 경쟁·비용 모형

[완료 내용/정확 파일/API](docs/COMPETITION_COST_DEVELOPMENT.md) · [새 비교 화면](results/COMPETITION_COST_REPORT_V2_20261017_01/REPORT.html). 새 입력24목록/실제고정8, 비용35·상대전류71세션 적합/검증, portable CostObserver, NN/SHA/산술/Chrome 전수 검증을 추가했습니다. 공유511/512·잔1, 예약OFF입니다. 기존 학습·모형·자료와 실패는 아래 이력과 함께 보존합니다.

# A24 시뮬레이터 — 완료 범위와 파일 위치

**최신 보완·학습 비교:** [긴급 납기 보호＋48요청 RL과 EDF](docs/PROTECTED48_COMPARISON.md) · [24조건 비교 화면](results/PROTECTED48_V2_20261016_01/index.html). 보완 RL은 새24조건 1152/1152 정시(기존RL1146), EDF 대비 총소비−0.04347%·작업증분−0.19978%·평균AP−0.005461℃이며 큰 폭 공동목표0/24입니다. 새학습64·DEV선정EP24·고정모형 유지·검산/NN재생/실화면PASS·예약OFF입니다. 아래 이전 버전은 보존합니다.


2026-10-16 기준. 아래 경로는 모두 이 `a24_simulator/` 폴더 기준입니다.

**최신 추가 완료:** 모바일 변형 대신 비선점 EDF(CPU 우선 동률 처리, 최단 예상 응답 선택 없음)14환경을 실행하고 기존 RL14조건과 동일 작업 구간으로 검산했습니다. [비교 설명](docs/EDF_COMPARISON.md) · [결과 화면](results/EDF_CPU_FIRST_20261016_01/index.html) · [실행 소스](experiments/edf_cpu_first_20261016/). 아래7정책 자료는 이전 버전 보존본입니다.

## 완료된 범위

- **자료 통합:** 기존 39세션과 M8 76세션, 총 115 관측 세션을 통합 모형의 출처로 연결했습니다. 수신 ZIP·원문 입력·SHA·중복 관계와 과거 결과를 보존했습니다.
- **통합 시뮬레이터:** 분류·탐지 모두 CPU/GPU를 선택하는 네 경로, 최대 두 요청의 병행, 비선점 자원 점유와 AVAILABLE 반환을 구현했습니다. 같은 처리시간·병행·AP 온도·조건부 에너지 모형에서 정책을 비교합니다.
- **화면과 실험 구성:** 혼합 요청 목록 직접 편집, 기본 12조건 일괄 비교, 요청별 일정·납기·AP 온도·조건부 에너지·peak·잔열·동일 일정 진단을 구현했습니다.
- **정책:** 롤링＋ATC＋RL, WAIT 제거, 고정 경로 직렬 FIFO, 자유 배정 FIFO, EDD, ATC, 모바일 지향 규칙의 7개 정책을 연결했습니다.
- **학습·평가:** 새 네 경로 PPO의 TRAIN 64회·DEV 24회를 완료하고 DEV에서 EP32를 선정했습니다. 이후 14조건 × 7정책, 98개 평가 실행을 완료했습니다.
- **검증·게시:** 저장 결과 산술·자원 점유 20,943검사, 신경망·Adam·RNG 재생 31,848검사, 별도 폴더 실행 및 브라우저 6뷰 검사를 완료했습니다. 실행 코드·핵심 데이터·선정 정책·결과와 대용량 과거 기록의 Release 연결을 게시했습니다.

완료는 구현·학습·소프트웨어 검증 범위입니다. RL의 정시 완료는 635/640, EDD·ATC·모바일 규칙은 각각 640/640으로 RL 추가 우위는 미입증입니다. J*는 조건부 모형값이며 교정 실측 J는 미확정입니다. AP는 내부 센서 온도이고, 탐지 GPU·일부 병행 조합은 전이·외삽 예측입니다. 상세 판정은 [현재 결과](docs/CURRENT_RESULTS.md)와 [모형 설명](docs/MODEL_CARD.md)에 있습니다.

## 파일 위치

| 구분 | 경로 | 내용 |
|---|---|---|
| 시작 문서 | [README.md](README.md) | 설치·실행·전체 구조 |
| 현재 상태 | [CONTINUE.json](CONTINUE.json), [docs/HANDOFF.md](docs/HANDOFF.md) | 현재 상태·예산 스냅샷·인계 기록 |
| 결과·모형·검증 설명 | [docs/CURRENT_RESULTS.md](docs/CURRENT_RESULTS.md), [docs/MODEL_CARD.md](docs/MODEL_CARD.md), [docs/VALIDATION.md](docs/VALIDATION.md) | 비교 결과·가정·검증 범위 |
| 현재 화면 | [src/index_v2.html](src/index_v2.html), [src/app.js](src/app.js), [src/bulk.js](src/bulk.js) | 요청 편집·정책 비교·일괄 실험 |
| 서버·실행 | [src/server_v2.cjs](src/server_v2.cjs), [tools/serve.py](tools/serve.py), [tools/start_windows.ps1](tools/start_windows.ps1) | 로컬 서버와 시작 도구 |
| 요청·납기·부하 | [src/bulk_design.cjs](src/bulk_design.cjs) | 기본 조건·요청 구성·seed 설계 |
| 모형·정책 연결 | [src/lab_backend.py](src/lab_backend.py) | 실행·결과 집계·저장 |
| 사건 기반 실행 | [src/interactive_kernel.py](src/interactive_kernel.py) | 5단계 처리·대기열·자원 점유·AVAILABLE |
| 시간·에너지·열 모형 | [src/four_route_model.py](src/four_route_model.py), [src/thermal_four_route.py](src/thermal_four_route.py) | 네 경로 처리시간·조건부 에너지·AP 온도 |
| 정책·학습 구현 | [src/policy_bridge_four_route.py](src/policy_bridge_four_route.py), [reference/rolling/learner.py](reference/rolling/learner.py) | ATC 후보·RL 입력·마스크·WAIT·PPO |
| 결과 진단 | [src/diagnostics.py](src/diagnostics.py) | 작업창·기저/활동 증분·동일 일정 |
| 통합 모형 의존 코드 | [reference/model_integration/](reference/model_integration/) | 현재 모형의 입력·계산 라이브러리 |
| 선정 정책 | [models/PPO_FOUR_ROUTE_EP032.pt](models/PPO_FOUR_ROUTE_EP032.pt) | 현재 선정된 체크포인트 |
| 학습 계약·완료 근거 | [models/TRAINING_OPERATION_V2.json](models/TRAINING_OPERATION_V2.json), [models/TRAINING_RESULT.json](models/TRAINING_RESULT.json), [models/TRAINING_COMPLETE.json](models/TRAINING_COMPLETE.json) | 동결 설계·DEV 선정·실행 종료 |
| 전체 평가 결과 | [results/FOUR_ROUTE_V2_EVAL.json](results/FOUR_ROUTE_V2_EVAL.json) | 14조건 × 7정책의 수치·요청별 실행·온도·손해 |
| 화면용·이전 결과 | [results/current/](results/current/), [results/previous_four_route/](results/previous_four_route/) | 현재 저장 결과와 이전 결과 보존본 |
| 실행·감사 기록 | [results/RUN_RECEIPTS.jsonl](results/RUN_RECEIPTS.jsonl), [results/INDEPENDENT_SAVED_AUDIT.json](results/INDEPENDENT_SAVED_AUDIT.json), [results/TRAINING_REPLAY_AUDIT.json](results/TRAINING_REPLAY_AUDIT.json) | START·완료·실패와 저장 결과 검산 |
| 수신 원자료 | [data/raw/](data/raw/), [data/RAW_ARCHIVES.json](data/RAW_ARCHIVES.json) | 받은 ZIP·원본 이름·SHA·중복 연결 |
| 실행 입력·출처 | [data/objects/](data/objects/), [data/CORE_MANIFEST.json](data/CORE_MANIFEST.json), [data/PATH_MAP.json](data/PATH_MAP.json) | 원문 입력·해시 객체·과거 경로 대응 |
| 과거 자료 출처 | [data/OLD_SOURCE_PROVENANCE.json](data/OLD_SOURCE_PROVENANCE.json), [docs/history/](docs/history/) | 기존 입력의 근거 경계와 과거 문서 |
| 대용량 보존본 | [data/HISTORY_ARCHIVE.json](data/HISTORY_ARCHIVE.json), [data/TRAINING_ARCHIVE.json](data/TRAINING_ARCHIVE.json) | Release ZIP 주소·크기·SHA. 전체 과거 기록 약 912MB, 이번 학습 기록 약 189MB |
| 검증·자료 도구 | [tests/](tests/), [tools/](tools/) | 현재 검사·자료 추출·실행 도구 |
| 패키지 해시 | [PACKAGE_MANIFEST.json](PACKAGE_MANIFEST.json) | 패키지 파일별 크기·SHA |
