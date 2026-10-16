# 2026-10-17 최신 인계 — 1·2번 보완 완료

먼저 [입력·비용 보완 완료/파일/API](COMPETITION_COST_DEVELOPMENT.md)를 읽는다. 입력 경쟁 마스크 후45.3%·cost35+native71검증·고정8·NN/SHA/산술/Chrome검사 완료, RL 공동목표 미달/실측Jnull이다. 현재511/512·잔1/child406이며 `node experiments/competition_cost_20261017/restore_budget_latest.cjs --verify-only`로 검증한다. 아래502/잔10과 이전 restore 명령은 과거 인계 스냅샷이다. 완료op/모형fit/8환경 재실행0, 원자료·CP·실패보존, 예약/주기조회OFF다.

# 이어서 작업할 사람을 위한 순서

**현재 예산 정본:** 보완 완료 뒤 공유502/512·잔10이다. 새 clone은 먼저 `node experiments/protected48_v2_20261016/restore_budget.cjs`로397 child 원장을 복원하고(이전 parent105 별도), 기존 원장이 다르면 삭제/덮기 없이 차단한다. [전체 학습/평가 경험 ZIP와 최신 파일 위치](PROTECTED48_COMPARISON.md#파일-위치와-이어서-수정할-곳)를 따른다. 아래306/잔206은 EDF 단독 비교 당시 이력이다.

**최신 보완·학습 비교:** [긴급 납기 보호＋48요청 RL과 EDF](PROTECTED48_COMPARISON.md) · [24조건 비교 화면](../results/PROTECTED48_V2_20261016_01/index.html). 보완 RL은 새24조건 1152/1152 정시(기존RL1146), EDF 대비 총소비−0.04347%·작업증분−0.19978%·평균AP−0.005461℃이며 큰 폭 공동목표0/24입니다. 새학습64·DEV선정EP24·고정모형 유지·검산/NN재생/실화면PASS·예약OFF입니다. 아래 이전 버전은 보존합니다.


최신 비교군은 [EDF_COMPARISON.md](EDF_COMPARISON.md)의 비선점 EDF입니다. `experiments/edf_cpu_first_20261016/`가 새 선택기/등록/실행이며 기존 `src/`의 모바일·EDD 구현과 7정책 결과는 원학습 재현을 위해 보존했습니다. 새 EDF14는 완료됐으므로 같은 operation을 재실행하지 않습니다. 최신 소비306/512·잔206이며 `CONTINUE.json`과 실제 runtime 원장을 확인합니다.

1. README → CURRENT_RESULTS → MODEL_CARD → VALIDATION → `models/TRAINING_RESULT.json` 순서로 읽습니다. 과거 보고는 `docs/history/`에 있습니다. 과거의 RUNNING·준비완료 문구보다 실제 COMPLETE/FAIL·현재 source SHA를 우선합니다.
2. `tools/run.py verify` 후 서버를 켭니다. 검증만으로 새 환경이 시작되지는 않습니다. 모든 조건·seed·정책의 손해와 실패를 보존합니다. 같은 일정의 정책들을 독립 효과 증거처럼 합산하지 않습니다.
3. 정책만 바꾸면 처리·열·전력 모형을 동일하게 유지합니다. 모형을 바꾸면 자료/적합/선정/확인 역할을 나누고 새 모델·출력·SHA를 등록합니다. 이미 본 확인을 다시 독립 확인이라고 쓰지 않습니다.
4. 과거 source/model/data는 `data/objects`의 해시 객체와 원 경로 맵으로 연결됩니다. 임의 절대경로 문자열 치환은 모델 식별을 바꿀 수 있습니다. 원 핀은 provenance ID로 유지하고 새 실행 registration만 현지 경로로 만듭니다.
5. 실행 중인 원 worker를 중복 시작·소스 수정·강제 중단하지 않습니다. Windows 실제 PID·생성시각·명령과 owner를 읽습니다. own Python leaf1/global2·접근 볼륨8GiB를 지킵니다. 로컬 원 작업과 같이 실행할 때 기존 shared worker.lock을 사용합니다.
6. 이 인계의 최종 child allocation407은 기존 interactive512에서 이전105를 제외한 나머지입니다. 학습 단계의256에서 미배분151을 이전한 기록은 PUBLICATION_ALLOCATION.json에 있습니다. 새 전체 예약이 아닙니다. 이전 interactive START105와 이번 START/FAIL을 합산합니다. `runtime`을 지우고 다시 실행해 소비를 환급하지 않습니다. 다른 기기/새 실험은 새 사전 등록·예산을 정합니다.
7. 중단 시 receipts의 START→PREPARED→COMPLETE/FAIL, raw/experience, before/after checkpoint, Adam, 행동/셔플 RNG, source SHA부터 확인합니다. 불완전한 회차를 같은 identity/seed로 자동 재수집하지 않습니다. 첫 TRAIN001 실패는 원 guard 필드 누락으로 표본 실행 전 차단됐고 별도 V2·새 seed에서 진행했습니다.
8. **모든 예약과 GitHub 주기 조회는 OFF입니다.** 이 폴더에는 이를 재개하는 자동화가 없습니다. GitHub 전송 스크립트·토큰도 실행 코드에 넣지 않습니다.

## 다음 연구의 우선순위

- 현재 APK에서 D_GPU와 새 병행 조합의 처리·실제 delegate/입력/출력 품질을 확인하고, 동적 간섭/초기 열 이력의 지원 범위를 넓힙니다.
- I/V/ΔQ의 같은 시간창·자료형·단위·갱신 검증 후에만 교정 J 모형을 채택합니다. 단일1000배 보정이나 기저 제거로 효과를 만들지 않습니다.
- 넓은 학습 seed·새 DEV·미관찰 실기기 확인을 확보합니다. 64episode 한 seed 결과는 충분한 학습/수렴 증거가 아닙니다.

## 현재 코드와 역사적 코드

`src/`가 현재 수정할 코드입니다. `reference/model_integration/`·`reference/rolling/`은 현재 모델/신경망의 의존 소스도 포함합니다. `reference/project_tools/`는 과거 공통 정책 구현의 맥락입니다. 전체 역사 보존본 안의 원 스크립트들은 원 등록/경로/환경을 요구하며 현재 실험을 자동 재개하는 입구가 아닙니다.
