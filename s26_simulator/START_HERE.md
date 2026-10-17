# S26 재개는 이 문서부터 · 2026-10-17

**채팅 기억 대신 이 폴더의 기록을 기준으로 이어간다.** 먼저 이 문서와 [AGENTS](AGENTS.md)를 읽고, [STATUS](STATUS.md)·[최신 결과](STATE_AWARE_COMPARISON_KO.md)를 확인한다. 구체적인 미완료 작업은 [NEXT_STEPS](docs/NEXT_STEPS.md), 실행·저장 규약은 [HANDOFF](HANDOFF.md)에 있다.

2026-10-17 최신 정본: **MULTI001_G004 3,240건 실행·독립 전수 감사 PASS**, 분석/HTML 생성 완료. 화면 QA 최초 실행은 실패 보존 중이므로 전체 완료는 아니다. 이전 STATE 결과는 역사다. [현재 정본·복원·미완료 작업](docs/G004_HANDOFF_KO.md)부터 읽는다.

## 목표와 사용자 결정

- 고정 납기 **긴급 0.8초 / 일반 2초**, 전체 128요청의 납기와 전량완료를 먼저 지키고 열·에너지를 함께 최소화한다. 실패·지연·미완료를 분모에서 빼지 않는다.
- 기존·신규 실측을 연결한 **하나의 공통 S26 엔진**을 개발한다. 실측으로 식별하지 못한 부분도 근거 있는 예측/전이 가정을 쓸 수 있지만 관측과 구분하고 한계·감도를 검증한다.
- 주방향은 사건 기반 **롤링+ATC+RL**이다. 현재는 시뮬레이터와 정책 차이 검증이 먼저이며, 최신 통합 엔진의 새 RL은 아직 0회다. 충분한 이점이 없으면 산업공학의 제약 최적화/탐색/MPC 등 다른 방식도 사용자 승인 범위다.
- 기본 비교군은 **FIFO/FCFS와 EDF**다. 과거의 자체 제작 MOBILE_DEADLINE_ENERGY를 널리 쓰이는 모바일 정책으로 다시 소개하지 않는다. BAND는 사용하지 않는다.
- 모든 정책에 같은 정보·자원 후보·납기·입력과 실제 마스크를 준다. 우리 정책의 개선 폭을 키우는 것이 목표지만, 물리계수·기한·분모를 결과에 맞춰 바꾸거나 비교군을 불리하게 만들어 격차를 키우지 않는다.

## 지금까지 완료된 것

계산 결과/실행 코드의 Git 기준은 **`30e16dd02c372492006552deb1cc4216f144b4a1`**이다. 이 시작 문서와 상태 정리는 그 이후 문서 커밋이다. 브랜치는 **`codex/s26-simulator-handoff-20261016`**, 작업 입구는 이 `s26_simulator/` 폴더다. [당시 업로드·원격 재다운로드 검증](evidence/STATE001_PUBLICATION_VERIFIED.json)을 보존했다.

최신 실험 **STATE001_G001**은 현재 전달 AP·공개 점유/과거 앱 단계로 자원 후보의 J/열 비용을 예측한다. 기존 명목 배정(STATIC)/새 상태 배정(STATE) × FIFO/EDF/ATC의 6군을 비교했다. 물리 계수는 그대로다.

| 같은 STATE 배정기 · 경쟁24조건/각128요청 | 전128건 납기 충족 | 평균 API-J | 평균 AP35~180 |
|---|---:|---:|---:|
| FIFO | 10/24조건 | 184.109736 | 32.472098℃ |
| EDF | 24/24조건 | 184.275174 | 32.472116℃ |
| 롤링+ATC | 24/24조건 | 184.275174 | 32.472116℃ |

- FIFO는 총35건 지연, 전군 미완료0. 실제 순서 경쟁384회에서 ATC는 FIFO와 달랐지만 EDF와 같았다. 기존 대조 포함48조건의 EDF/ATC 물리 궤적도 동일해 **EDF 대비 추가 절감0**이다.
- 같은 ATC에서 새 배정기는 기존 배정기 대비 J **0.2761% 감소**, 평균 AP **0.095057℃ 증가**, 최고 AP **1.825049℃ 증가**다. 부하별 J 효과도 반전한다. **열·에너지 공동개선은 아직 미입증**이다.
- 주비교의 분류4,608건 모두 GPU/NPU 전망을 계산했고 GPU를 선택했다. 모두 GPU의 예측 J가 낮고 열면적은 높았는데 가중합이 GPU를 선호했다. 강제 GPU 고정은 아니며, 열 악화 금지 제약도 아직 없다.
- 실행300(P0 12+주비교288) START/PREPARED/COMPLETE·환경FAIL0. 전수3,891,272검사·300 저장 비용 재적분·후보 전망35,430회/공개 입력 연결 PASS. 보존된 최초 감사35건을 포함한 실제 비용 재적분 소비는335건이다. ZIP3개를 다시 풀어900파일 길이/SHA 검증, CLI383검사, 원격 복제본 전체 SHA 확인까지 끝났다. **이300건을 다시 돌릴 필요는 없다.**

## 최신 파일은 어디 있는가

| 목적 | 폴더 안 경로 |
|---|---|
| 최신 결과와 원인·한계 | [STATE_AWARE_COMPARISON_KO.md](STATE_AWARE_COMPARISON_KO.md) |
| 최신 정책/배정기 | `experiments/state_aware_v1/source/state_actions.cjs`, `state_cost.cjs` |
| 최신 엔진 연결/단일 실행 | 같은 `source/`의 `state_simulator.cjs`, `state_case.cjs` |
| 공통 plant·시간·비용 | 같은 `source/`의 `s26_simulator.cjs`, `dynamic_cost_math_v2.cjs`, `s26_simulator_v2.cjs` |
| 입력·실측 단계·모형 계수 | `experiments/state_aware_v1/PACKET.json.gz`, `PACKET_SHA256.json` |
| 등록·계획·평가 구성 | 같은 폴더의 `REGISTRATION.json`, `CASE_PLAN.json`, `source/PLAN.md` |
| 모든 조건/쌍별 차이/경쟁 | 같은 폴더의 `SUMMARY.json`, `CASE_METRICS.csv`, `PAIRED_DELTAS.csv`, `OPPORTUNITIES.csv` |
| 300건 원시 실행/설정/검산 proof | 같은 폴더의 `raw_part_1.zip`~`raw_part_3.zip`·각 `MANIFEST.json` |
| 원장/prepared/실패/정확 복구/실제 감사 소스 | 같은 폴더의 `operations/`·`SOURCE_MAP.json`·`README_KO.md` |
| 이전 기준판과 화면 | `src/`, `data/engine_packet.json.gz`, `web/index.html` — SIM002/V4 당시 판이며 STATE 결과 화면이 아님 |
| 단계 모형 보완 후보 | `research/fit_phase_transfer_v1.py`, `models/phase_transfer_NOT_ADOPTED.json.gz` — 아직 plant에 미채택 |
| 원실측 묶음·정정·과거 RL/IE | `docs/DATA.md`·`data/ARCHIVES.json`·[기존 데이터 Release](https://github.com/mingyujo/D1Check/releases/tag/s26-handoff-20261016), 아래 복원 명령 |

`operations/sources/`는 Windows 긴 경로 오류를 피한 **동일 바이트의 짧은 운영 소스 이름**이다. `SOURCE_MAP.json`이 원경로/역할/SHA와 연결한다. 원 PC 절대경로가 든 운영 등록·감사 명령을 다른 PC에서 그대로 재실행하지 않는다. 새 호스트의 경로·의존성·원장·잠금으로 새 운영 등록이 필요하다.

## 먼저 확인할 명령 · 새 시뮬레이션 아님

최신 브랜치의 이 폴더 안에서 Node.js 20 이상으로 실행한다. 기존 Release의 `s26-simulator-core.zip`은 `190072a` 당시 판으로 최신 STATE 실험을 포함하지 않는다.

```sh
git branch --show-current
git rev-parse HEAD
git status --short
node cli/s26.cjs verify
node cli/s26.cjs replay --comparison state-aware-v1 --bank COMPETE_A
node cli/s26.cjs replay --comparison state-aware-v1 --bank COMPETE_B
# 필요한 과거 실측/학습 기록만 복원할 때
node scripts/restore-data.cjs --group measurements
node scripts/restore-data.cjs --group policy_history
# 전체 이력이 필요할 때만: --group all
```

상세 복원은 [DATA](docs/DATA.md), 실행 규약은 [HANDOFF](HANDOFF.md)를 따른다. 저장 결과 CLI와 `serve`는 새 환경/학습을 만들지 않는다. `serve`가 여는 HTML은 과거 V4 저장 화면이다.

## 미완료와 재개 조건

1. **열 악화를 허용하는 목적함수와 한 단계 후보 전망을 보완**할 필요가 있다. 열 악화 금지/에너지 제약, 준비된 큐 전체를 보는 산업공학 탐색 등은 다음 개발 후보다. 아직 구현·검증·채택한 것이 아니다. 이번에 관찰한 평가로 새 정책을 다시 선정하지 말고 새 DEV/새 평가 입력을 등록한다.
2. **물리 예측의 전이 정확도는 미완료**다. R21 재현 MAE는 API-J 약37.53J/AP 약0.612℃이며 단계 조건부 보완 모형도 미채택이다. 후보 추가의 음수 한계 J는 모형 차분으로 실제 음의 전력이 아니다. 새 경쟁 부하 U112/N16의 긴급 탐지는 기존 일반 탐지 전체 단계에서 output_ready 응답을 쓰는 전이 가정이다. 기존 대조 U96/N32와 섞어 실측 반복으로 세지 않는다. 실측8,636 단계 벡터 + 전이 view1,216개이며 중복 학습 가중0이다.
3. 위 검증 뒤 **최신 통합 엔진에 RL을 연결·학습·새 입력으로 비교**한다. 과거 RARL 4군×3seed×64 학습은 별도 엔진 이력이며 현재 RL 완료의 증거가 아니다. 현재 정책 계산의 모바일 지연/J도 아직 비용에 포함하지 않아 실기기 순절감은 미검증이다.

2026-10-17 인계 당시 총예약 **121206/137712**, 미예약16506, 마지막 전역 START28179다. STATE cap320 중300소비/20미사용, 원SIM512의 잔12는 별도다. **이는 복제본에 새로 생긴 예산이나 재시도 권한이 아니다.** 새 실행 전 최신 모든 canonical 원장·다른 A24 예약·실제 PID/명령/생성시각을 재확인한다. ownheavy1/global Python leaves2·공동 잠금·관련 모든 볼륨8GiB를 유지한다.

자동화는 PAUSED 상태를 보존한다. 소비된 미저장/FAIL identity 재수집·대체seed·원 V2 EP814 미저장/FINAL·CAUSAL·NODGPU gate 우회는 금지한다. 다른 A24/37/38/SLO70/중지27·원자료·사용자 WIP를 보존한다. 새 소스·출력·예산·DEV/평가 등록과 전수 검산 없이 이전 완료판/원장을 덮어쓰지 않는다.

## 새 담당자에게 그대로 전달할 문장

> `codex/s26-simulator-handoff-20261016` 브랜치의 `s26_simulator/START_HERE.md`부터 읽고 STATUS·AGENTS·최신 결과와 Git HEAD/CORE_MANIFEST를 확인해줘. STATE001_G001 300건 실행/전수 감사/업로드는 완료됐지만 열·에너지 공동개선은 아직 없고, 최신 통합 엔진 RL은 아직0회야. 최신 정책 코드는 experiments/state_aware_v1/source/, 입력·원자료·감사도 같은 실험 폴더에 있어. 완료 실험을 재실행하지 말고 현재 미완료 문제부터 새 등록/새 평가 계보로 이어가줘.
