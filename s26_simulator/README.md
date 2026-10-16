# S26 시뮬레이터·정책 인계 폴더

**새 담당자·새 채팅은 [START_HERE.md](START_HERE.md)부터 읽으세요.** 현재 목표·사용자 결정·완료/미완료·최신 코드/데이터 위치·검증 명령·예산/보존 조건을 한곳에 정리했습니다. 이전 단계 설명보다 START_HERE와 STATUS의 최신 기록을 먼저 적용합니다.

**현재 상태 반영 비교:** [새 배정기·순서 경쟁 결과](STATE_AWARE_COMPARISON_KO.md)를 추가했습니다. 6정책×4부하×3초기×4draw와P0로300환경을등록·실행·검산했습니다. 기존고정부하와긴급탐지경계전이가정(U112/N16)을분리하며새RL/fit0입니다. 전체물리정확도·실기기순절감은미확정입니다.

**동률 원인 전수 추적 추가:** [왜 같은 선택인가](SAME_CHOICE_DIAGNOSIS_KO.md). 실행 가능 복수 후보1,551회가 모두같은 종류·기한·ATC점수였고, 공통 배정기는분류4,608건모두NPU를선택했습니다. 현재 비교는동일배정기하의순서비교입니다. 새환경/학습0, 18,082별도검사PASS.

**이 폴더 하나가 작업 입구입니다.** 최신 실행 코드·모형·요청표·저장 결과·시각화·원자료 다운로드/복원 도구와 과거 계보를 함께 제공합니다. 원 PC의 `C:/Users/...` 폴더 없이 현재 화면 열기, 저장 결과 확인, 소스 수정이 가능합니다.

**상태 배정 보완 전의 동일 자원 비교:** [FIFO·EDF·롤링 ATC 공정 비교 결과](FAIR_RESOURCE_COMPARISON_KO.md). 세 정책 모두 CPU/GPU/NPU를 선택하게 맞춘48조건에서는 납기100%·평균200.352058 API-J·평균AP32.396312℃로 같았고, 실제 물리 궤적도 모두 일치했습니다. 우리 정책의 추가 절감은0입니다. 새104환경과 재사용48건의1405515검사/152비용재적분PASS입니다. 상세 source·원자료ZIP·144조건/96쌍별CSV는 `experiments/fair_resource_v1/`에 있습니다. 아래 배포본 설명과 V4 화면의 고정GPU 비교는 당시 참고 결과로 보존합니다.

최신 상태 배정 비교는 `node cli/s26.cjs replay --comparison state-aware-v1 --bank COMPETE_A`로 확인합니다. 이전 명목 배정 비교는 `--comparison fair-resource-v1`로 보존했습니다.

다른 사람에게 보낼 설명은 [인계 전달문](HANDOVER_MESSAGE_KO.md)에 정리했습니다. 완료 범위·파일 위치·화면 확인·원자료 복원 방법을 담았습니다.

## 바로 보기

**최신 실험을 포함하려면 `codex/s26-simulator-handoff-20261016` 브랜치의 이 폴더를 받으세요.** [기존 s26-simulator-core.zip](https://github.com/mingyujo/D1Check/releases/download/s26-handoff-20261016/s26-simulator-core.zip)은 `190072a` 시점의 동결 배포본으로, 뒤의 동일 자원·진단·상태 배정 실험은 포함하지 않습니다. 기존 Release 원자료는 아래 복원 명령을 쓰며, 최신 상태 배정 300건의 raw/config/proof ZIP 3개는 `experiments/state_aware_v1/`에 함께 있습니다.

필수: **Node.js 20 이상**. 현재 코드와 화면에는 별도 npm 라이브러리가 필요 없습니다.

```sh
cd s26_simulator
node cli/s26.cjs verify
node cli/s26.cjs replay --comparison state-aware-v1 --bank COMPETE_A
node cli/s26.cjs serve
```

마지막 명령 후 **http://127.0.0.1:8788** 을 엽니다. 이 HTML은 SIM002 V4의 과거 저장 화면이며 최신 STATE 결과는 위 보고/CLI로 확인합니다. `web/index.html`을 직접 열어도 됩니다. 화면은 저장된 예측을 재생합니다. 클릭·`replay`·`verify`·`serve`는 새 시뮬레이션 환경이나 학습을 실행하지 않습니다.

## 지금 어디까지 됐나

2026-10-16 인계 시점:

- 목표: **긴급 0.8초·일반 2초 납기와 전량완료를 먼저 지키면서 열·에너지 최소화**. 우리 정책의 절감 폭을 키우되 물리계수·납기·요청 분모를 결과에 맞춰 바꾸지 않습니다.
- 기존·신규 실측을 연결한 **공통 엔진 하나**입니다. 추론 시간 81,736건, 전체 처리 단계 표본 8,636개, 비용 자료 원장 228세션을 사용합니다. 포함 조건·중복·결측·계약 차이는 [데이터 설명](docs/DATA.md)을 봅니다.
- 분류는 **CPU/GPU/NPU를 요청마다 비교**합니다. 탐지는 CPU만 지원합니다. 검증된 `분류 GPU + 탐지 CPU`, `분류 NPU + 탐지 CPU`만 최대 2건 병행합니다. 비선점이며 응답과 자원 반납은 별도입니다.
- 최신 정책은 **미학습 롤링+ATC 자동 자원배정**입니다. 48조건 모두 128건 전량·납기를 충족했고 현재 입력/모형에서는 분류가 모두 NPU로 선택됐습니다. NPU 고정이나 선택 비율 강제는 없습니다. 모든 후보·실제 선택이 원자료에 남습니다.
- 이 엔진에서 **새 RL 학습은 아직 0회**입니다. 과거 별도 엔진의 4군×3seed×64경험 학습본과 IE 비교를 보존하지만 최신 엔진의 RL 성과로 재명명하지 않습니다.
- 공통 엔진 기존 444 + 자원배정 검증 56 = **500 START/PREPARED/COMPLETE, 환경 FAIL 0**. 별도 관리/검산 실패는 보존했습니다. 자원배정 감사는 개별 56건 저장 증거를 확인하고 요약 집계를 수리한 최종 452,636검사 PASS입니다.
- **물리 정확도·프로젝트 목표 완료는 미확정**입니다. 기존 R21 재현 오차는 API 에너지 MAE 37.53J, 평균 AP MAE 0.612℃입니다. 준비·반환·해제 단계의 조건부 보완 모형은 적합했지만 엔진에 아직 채택하지 않았습니다.

**다음 사람이 먼저 읽을 문서:** [STATUS](STATUS.md) → [HANDOFF](HANDOFF.md) → [다음 작업](docs/NEXT_STEPS.md) → [구조](docs/ARCHITECTURE.md) → [정책](docs/POLICIES.md).

## 폴더 구성

| 경로 | 용도 |
|---|---|
| `src/` | SIM002의 기존 공통 물리·시간·비용·명목 자원배정 소스. 보존된 기준판 |
| `experiments/state_aware_v1/` | 최신 상태 배정/6정책 코드·입력 packet·300 raw/config/proof·원장·독립 감사·조건별 결과 |
| `models/`, `data/engine_packet.json.gz` | 현재 동결 수식/계수, 전체 단계 표본과 21개 실측 요청/초기이력. 단계 보완 미채택 모형은 별도 이름 |
| `data/cached_view_data.json.gz` | 192개 기존 참고 결과 + 48개 자동배정 결과, 요청별 실제 저장 궤적 |
| `web/index.html` | 최신 자동 자원배정 화면, 단독 파일로도 열림 |
| `evidence/` | 최신 전수 감사·실패·목표/오차·화면 QA·스크린샷 |
| `research/` | 통계 적합·독립 감사·화면 템플릿의 연구 코드. 과거 절대경로는 `archive/` 원본 증거에서 보존 |
| `docs/history/` | 실측 수신·정정·모형·RL/IE·정책 선택의 기존 한국어 보고 |
| `scripts/restore-data.cjs`, `data/ARCHIVES.json` | 같은 GitHub Release에 올린 원자료·중간본·학습 원장/경험·체크포인트 전체 복원과 SHA 검증 |
| `archive/` | 원자료 복원 후 생성. 과거 `work/`, `outputs/`, `incoming/`, `views/` 구조를 폴더 내부에 보존 |
| `CORE_MANIFEST.json`, `data/CORE_PROVENANCE.json` | 인계 파일 SHA, 원본 경로·SHA 및 압축 전후 관계 |

## 원자료·과거 학습 기록 받기

일반 Git 파일의 크기 제한 때문에 큰 자료는 **같은 저장소의 [S26 데이터 Release](https://github.com/mingyujo/D1Check/releases/tag/s26-handoff-20261016)** 에 있습니다. 이 폴더의 도구만으로 받고 검증·복원합니다. Git LFS 결제나 별도 클라우드 계정은 필요 없습니다.

```sh
node scripts/restore-data.cjs --group current
node scripts/restore-data.cjs --group measurements
node scripts/restore-data.cjs --group policy_history
node scripts/restore-data.cjs --group history
# 전부 받으려면
node scripts/restore-data.cjs --group all
```

원본·중간본·이전 결과를 삭제하지 않고 **내용 SHA로 중복 저장만 제거**했습니다. 파일별 원래 이름과 SHA를 유지하여 복원합니다. 원자료 전체를 복원하려면 디스크 여유가 충분해야 하며 도구는 복원 크기 외 **8GiB**를 남깁니다. 임의 기존 파일을 덮어쓰지 않습니다. [포함·제외·라이선스 경계](docs/DATA.md)를 확인하세요.

다운로드가 끊기면 해당 `.cache/*.part` 파일을 확인한 뒤 그 파일만 제거하고 같은 명령으로 다시 시작합니다. 완료된 pack은 SHA를 다시 확인해 재사용하고 이미 같은 내용으로 복원된 파일도 재사용합니다. `--verify-only`를 붙이면 blob을 검증하고 전체 원자료를 디스크에 풀지 않습니다. `--filter <경로 일부>`로 선택 경로만 복원할 수도 있습니다.

## 수정·새 실행

기준판은 `src/`, 최신 상태 배정 구현은 `experiments/state_aware_v1/source/`입니다. 원본 등록/감사/과거 결과는 `evidence/`와 다운로드 아카이브에 그대로 두세요. [개발 절차](HANDOFF.md)에 따라 새 소스 세대·예산·DEV·평가 입력을 등록한 뒤 실행합니다. `src/run_resource_case_v2.cjs`는 **등록된 작업자가 호출하는 저수준 실행기**이며 기록 없이 새 결과를 만드는 진입점으로 사용하면 안 됩니다. 이 인계 자체에서는 새 정책 환경·NN·fit을 실행하지 않았습니다.

최신 모형·입력이 달라진 상태에서 이전 체크포인트를 그대로 최신 RL이라고 부르지 마세요. 납기/완료량을 희생한 절감, API 추정J를 외부 계측J로 표시하는 것, 평균 곡선을 실제 한 번의 일정으로 표시하는 것도 금지합니다.
