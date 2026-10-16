# S26 시뮬레이터·정책 인계 전달문

2026-10-16 비교 갱신: [동일 자원 FIFO·EDF·롤링 ATC 비교](FAIR_RESOURCE_COMPARISON_KO.md)를 추가했습니다. 현재48조건에서 세 정책의 납기·열·에너지는 모두 같았으며 우리 정책의 추가 감소는0입니다. 코드·144개 조건/96개 쌍별 결과·원자료ZIP·독립 감사 근거는 `experiments/fair_resource_v1/`에 있습니다. 아래는 `190072a` 최초 배포본 설명입니다.

S26 시뮬레이터·스케줄링 정책 개발 자료를 인계드립니다.

- **GitHub 폴더:** [s26_simulator](https://github.com/mingyujo/D1Check/tree/codex/s26-simulator-handoff-20261016/s26_simulator)
- **작업 브랜치:** `codex/s26-simulator-handoff-20261016`
- **기술·자료 기준:** 2026-10-16 배포본, 커밋 `190072a`
- **폴더만 다운로드:** [s26-simulator-core.zip](https://github.com/mingyujo/D1Check/releases/download/s26-handoff-20261016/s26-simulator-core.zip)
- **원자료·과거 학습 기록:** [S26 데이터 Release](https://github.com/mingyujo/D1Check/releases/tag/s26-handoff-20261016)

목표는 **긴급 0.8초·일반 2초의 납기와 전량완료를 우선하면서 열·에너지를 최소화하는 것**입니다. 주정책은 롤링+ATC+RL이며 산업공학 기반 최적화 방법도 검토 범위에 있습니다.

현재는 **공통 시뮬레이터와 자동 자원배정 구현·수치 검산을 마쳤고, 실측 예측 정확도를 보완하는 단계**입니다. 최신 통합 엔진에서의 RL 학습은 아직 시작하지 않았습니다.

## 완료된 내용

- 기존 실측과 신규 M8·R21 자료를 연결하여 처리시간·병행·열·전력·온도에 따른 처리속도 변화를 계산하는 공통 엔진을 구현했습니다. 추론 시간 81,736건, 처리 단계 표본 8,636개, 비용 자료 원장 228세션 후보를 연결했으며 적격성·결측은 구분합니다.
- 현재 주정책 `ROLLING_ATC_ROUTE_V2`는 미학습 롤링+ATC 규칙입니다. 분류 요청마다 CPU/GPU/NPU를 비교하고 탐지는 CPU를 사용합니다. 검증된 분류 GPU/NPU와 탐지 CPU 조합만 최대 2건 병행하며 비선점·실제 자원 반납을 지킵니다.
- 최신 48조건에서는 조건별 128요청 모두 완료·납기를 충족했습니다. 분류가 모두 NPU로 선택됐지만 자원을 고정한 것은 아닙니다. 후보·마스크·선택 근거를 기록했습니다.
- 공통 엔진 500환경의 저장·원장 검산과 최신 HTML 화면 검증을 완료했습니다. 환경 FAIL은 0이며 별도 관리·감사 과정의 실패도 보존했습니다.
- 과거 별도 엔진의 RL 4군×3seed×64경험과 IE 비교, 경험·체크포인트·실패 기록을 보존했습니다.
- 인계 자료의 공개 다운로드·SHA·폴더 단독 검증을 완료했습니다. 근거는 `evidence/HANDOFF_VERIFICATION.json`과 Release의 [PUBLISH_VERIFICATION.json](https://github.com/mingyujo/D1Check/releases/download/s26-handoff-20261016/PUBLISH_VERIFICATION.json)에 있습니다.

## 현재 결과의 해석 범위

현재 결과는 모형 안에서의 예측입니다. R21 실측 재현 오차가 **API 에너지 MAE 약 37.53J, 평균 AP 온도 MAE 약 0.612℃** 남아 있습니다. API 추정 에너지는 외부 전력계 교정값과 구분하며 AP 온도도 표면온도와 구분합니다.

준비·반환·해제 등의 조건부 단계 보완 모형은 104회 적합했지만 **현재 엔진에 아직 적용하지 않았습니다.** 구현·수치 검산 PASS가 실기기 독립 정확도나 프로젝트 목표 달성 완료를 뜻하지 않습니다.

기존 FIFO/EDF 참고 결과는 자원 선택 범위가 현재 자동배정 정책과 다릅니다. 해당 표의 차이를 순서 정책의 공정한 우위로 해석하지 않습니다. 과거 RL 학습본도 최신 엔진의 RL 성과와 구분합니다.

## 파일 위치

아래 경로는 모두 `s26_simulator/` 기준입니다.

| 파일·폴더 | 내용 |
|---|---|
| `README.md` | 설치·실행·데이터 복원의 시작점 |
| `STATUS.md` | 완료 범위, 현재 결과·오차와 개발 상태 |
| `HANDOFF.md` | 수정 위치와 실행 계약 |
| `docs/ARCHITECTURE.md`, `docs/POLICIES.md` | 공통 엔진 구조와 정책·자원 배정 규칙 |
| `docs/ENGINE_API.md` | 엔진 호출 방법과 입력·출력 연결 |
| `src/s26_simulator.cjs` | 공통 물리·처리 진행·응답·자원 반납 |
| `src/dynamic_cost_math_v2.cjs` | AP 온도·API 전력 계산 |
| `src/rolling_action_v2.cjs` | 요청 순서·CPU/GPU/NPU 선택·WAIT 판단 |
| `src/s26_simulator_v2.cjs` | 정책 연결과 공개 관측·배정 로그 |
| `src/run_resource_case_v2.cjs` | 등록된 단일 실행의 결과 저장기 |
| `data/engine_packet.json.gz` | 현재 엔진이 사용하는 모형·표본·요청표·초기 이력 |
| `models/` | 시간·AP·전력 모형. `phase_transfer_NOT_ADOPTED.json.gz`는 아직 적용하지 않은 단계 보완 모형 |
| `research/` | 시간·단계·비용 모형 적합, Python 기준 계산·감사 코드 |
| `web/index.html` | 최신 시뮬레이터 화면 |
| `data/cached_view_data.json.gz` | 화면에 사용하는 저장 결과 240조건 |
| `evidence/RESOURCE_AUDIT.json` | 최신 자원배정 검산 결과 |
| `evidence/MODEL_ACCURACY.json` | 실측 재현 오차와 분석 |
| `docs/history/` | 기존 실측 수신·정정·모형·RL/IE 개발 보고 |
| `CORE_MANIFEST.json`, `data/CORE_PROVENANCE.json` | 인계 파일 SHA와 원본 출처 |
| `scripts/restore-data.cjs`, `data/ARCHIVES.json` | 대용량 자료 다운로드·검증·복원 |

`src/`는 수정할 작업 복사본이며 원자료·과거 결과·동결 증거는 별도로 보존되어 있습니다. 과거 운영 스크립트의 절대경로와 현재 상대경로 실행 코드는 `HANDOFF.md`에서 구분합니다.

## 화면과 저장 결과 확인

Node.js 20 이상이 필요하며 현재 화면·CLI에는 별도 npm 설치가 필요 없습니다. 수정 전 기준본을 확인하는 명령입니다.

```sh
git clone --single-branch --branch codex/s26-simulator-handoff-20261016 https://github.com/mingyujo/D1Check.git
cd D1Check/s26_simulator
node cli/s26.cjs verify
node cli/s26.cjs replay --policy ROLLING_ATC_ROUTE_V2 --bank ALL
node cli/s26.cjs serve
```

브라우저에서 **http://127.0.0.1:8788** 을 엽니다. `web/index.html`을 직접 열어도 됩니다. 화면과 `replay`는 저장 결과 확인용이며 새 시뮬레이션이나 학습을 실행하지 않습니다.

## 원자료와 과거 학습 기록 복원

같은 저장소의 Release에 **60,878파일, 원본 약 25.9GB**를 보관했습니다. 내용 중복 제거·압축 후 다운로드 크기는 약 3.36GB입니다. 파일별 원래 이름과 SHA를 유지합니다.

```sh
node scripts/restore-data.cjs --group current
node scripts/restore-data.cjs --group measurements
node scripts/restore-data.cjs --group policy_history
# 전체 자료가 필요하면
node scripts/restore-data.cjs --group all
```

| 복원 후 위치 | 내용 |
|---|---|
| `archive/work/<작업ID>/` | 과거 소스·운영 코드 |
| `archive/outputs/<작업ID>/` | 원장·실행 결과·모형·학습 경험·체크포인트·감사 |
| `archive/incoming/` | 담당자에게 받은 원 ZIP·정정·동결 파일 |
| `archive/views/` | 과거 HTML |

복원 도구는 자료·캐시 외에 8GiB의 여유 공간을 남기며 다른 내용의 기존 파일을 덮어쓰지 않습니다. 모바일 모델 바이너리·설치 라이브러리·캐시의 제외 내역은 `docs/DATA.md`와 `data/ARCHIVES.json`에 있습니다.
