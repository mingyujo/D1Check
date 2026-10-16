# 데스크톱 Codex 전달 프롬프트 — A24·S26 ATC→PPO

2026-10-11. 아래 코드 블록 **전체**를 데스크톱 Codex에 붙여 넣는다. 실행 코드가 아니다. 이전64→512 프롬프트는 완료 실험이므로 다시 실행하지 않는다.

```text
D1Check를 GitHub에서 확보하고, 실측 기반 CPU/GPU 시뮬레이션의 새 ATC→PPO 사건 기반 온라인 스케줄러를 구현·검증·작은 파일럿·분석·문서화까지 진행하라. 한국어로 답하고 개선을 전제하지 말라. 계획 제시에 그치지 말고 가능한 PC 작업을 완료하라.

저장소: https://github.com/mingyujo/D1Check
주 브랜치: feature/arrival-scheduling-20260923
새 과제: ATC-PPO-DESKTOP-PILOT-01
A24·S26 모두 사용자 본인이 담당한다. 팀원에게 메시지를 자동 전송하지 않는다.
예정 호스트: Ryzen5 5600 / RAM 약16GB / RTX3060. 실제 OS/환경을 확인한다.

1. 확보와 최신 상태
기존 checkout이 있으면 실제 경로·브랜치·HEAD·변경·worktree·진행 프로세스/owner를 확인한다. 사용자 변경과 실행 중 작업을 보존하고 필요하면 별도 checkout/브랜치를 만든다. reset/clean/강제push나 dirty 폴더의 무조건 pull은 하지 않는다. 처음 시작이면 주 브랜치를 single-branch/shallow clone한다. 실제 원격HEAD와 소스/자료SHA를 기록한다.
먼저 AGENTS.md, docs/PROJECT_STATUS.md, docs/PROJECT_PLAN.md, docs/DECISIONS.md, docs/ATC_PPO_EVENT_DESIGN_20261011.md, docs/results/desktop_atc_handoff_20261011/README.md·publication_manifest.json·verification.json을 읽는다. S26_SIMULATION_PLAN_20261011.md와 연결된 세 역할 검토, SIMULATION_MODEL_V2.md·SIMULATION_MODEL_V3.md·SIMULATION_MODEL_V3_HYBRID_20261010.md, results/service_goal_20261011/README.md·results/desktop_amount512_20261011/README.md도 확인한다. 과거 문구와 실제 최신 구현을 구분하고 현재 목표·제약을 전체 계획에서 대조한다.
S26은 다음 고정 tree를 별도 sparse checkout 또는 필요한 하위 tree로 확보한다. 세 브랜치를 무조건 merge하지 않는다. 최신 HEAD가 달라졌으면 고정 근거와 구분한다.
- s26-measure / 0a0749890fba2452c5907433c6bea476a2da7e24
- s26-mixreq / 21cba44faa5fff1fb9703b590aa536a6207f8de5
- s26-quality20 / 5857152ad8244c41975843ded77dd33024f38f2d
주요 경로: d1sim/, request-runner/, s26/tools/mixreq/, s26/results/mixreq_1008/, s26/results/quality20_1008/. 먼저 코드·manifest·requests·progress·hal·validated·원장만 확보한다.107,032개 요청별 출력 전량 다운로드로 시작하지 않는다. GitHub recursive tree가 truncated이면 하위 tree를 확인한다.

2. 기존 정책과 새 설계
시뮬레이터·EDD+ECT·ATC·JointList/CostList·현재 masked PPO·Band/Triton adapter·학습/평가·terminal archive를 찾아 state/action/reward/event/응답/AVAILABLE/지원 범위를 정리한다. 관련 tools/d1_industrial_scheduling.py, d1_service_envelope_policy.py, d1_service_joint_rl*.py, d1_rolling_hybrid*.py 및 list_candidate/RL 모듈과 tests를 확인한다.
기존 amount512_desktop_20261011_a는 원64→512 세 PPO의 추가1,344학습·2,200환경을 완료했고 strict 채택0이다. 같은 task를 재실행하지 않는다. 기존 ZIP/원장/checkpoint/예산/clock/FAIL은 보존한다.
새 구조는 도착·실제 lane AVAILABLE·등록timer → 공개 상태 → ATC shortlist → 요청×CPU/GPU·검증 병행·자원 대기 → 물리 불가능 mask → 고정 가중치 PPO 선택 → 실행/대기 → 다음 사건 재판단이다. ATC는 후보만 추리며 PPO가 요청/실행 방법을 선택한다. 실행 중 작업은 비선점이다. 전체 미래 스케줄 탐색·MPC·CP-SAT를 운영 판단에 추가하지 않는다. 롤링은 사건마다 재판단한다는 의미다.
새 schema/정책ID/보상·mask 버전으로 fresh actor/critic/Adam/RNG를 만든다. 예전 actor/Adam의 연장이나 optimizer 리셋을 순수 학습량 비교로 표시하지 않는다. 현재 PPO는 이미 masked categorical이므로 마스킹 중복 구현을 새 알고리즘이라고 부르지 않는다. 현재 구현 보완을 우선하며 외부 MaskablePPO 사용은 실제 API/검증 부족을 확인한 경우에만 이유를 남겨 선택한다.

3. 구현 전 고정할 판단 계약
ATC 원 논문과 기존 코드 대응을 확인해 처리시간 경계·중요도·k·후보수·평균 처리시간 모집단·동점을 명시한다. 프로젝트 k=2/w=1 같은 설정을 문헌의 보편 기본값으로 부르지 않는다. 미지원 값을0으로 만들지 않는다. shortlist의 CPU-only 탐지·긴급·가능한 pair·starvation·뒤 요청 기한 C2 반례를 검사하고 필요한 공개 tail 특징을 비학습 대조군과 공유한다.
자원 반환 대기와 선택적 냉각 유예를 구분한다. 기본 대기는 다음 도착/실제 반환/등록timer에서 재판단하며 동일시각 무한WAIT/dispatch를 막는다. 냉각유예·선점·주파수·전력제한을 조용히 추가하지 않는다. response/output·persist·worker_release·AVAILABLE을 구분하고 AVAILABLE 전 재사용 금지, phase callback/timer·PAIR 둘째 실패 요청 보존을 검사한다.
물리 mask와 예측 서비스 보호를 구분한다. 기존 V1의 예측 개선후보0인 서비스 mask를 그대로 복사하지 않는다. 예측으로 미래 기한/온도가 보장된다고 주장하지 않는다. 빈 슬롯·busy lane·미지원 조합은 제거한다.
관측에는 도착한 요청 납기·예상 서비스·점유/경과시간·과거 이력·실제 관측 온도만 둔다. 미래 도착·실현 비용·실제 잔여시간·숨은 내부 열 상태는 노출하지 않는다. 원 서비스/출력/일반 완료 요구를 유지하고 열·J 목적을 별도 버전으로 기록한다. 경과시간 비용·대기 전력·할인/GAE·행동 이후 비용·종료 꼬리를 결과 전에 고정한다. 임의 SLA/온도 한계/유지 허용오차를 만들지 않는다. 보상과 원단위 KPI를 구분한다.

4. 기기별 근거와 자료 경계
A24는 동결 원 서비스/에너지＋v3 thermal-only hybrid부터 사용한다. CPU 분류/GPU 분류/CPU 탐지, 검증 CG_DC만 최대2병행이다. 탐지GPU·새모델·S26계수를 추가하지 않는다. AP는 표면온도가 아니고 온도→서비스 회복은 없다.
S26의 기존 MobileNet/CPU4/FG-BG chunk를 exact 모델/CPU1 mixed와 합치지 않는다. 모델/input/runtime/thread/resident/정밀도/7경계·품질·시각·current 단위·power_sample 중복·coverage·상태 식별을 감사한 뒤 별도 CPU/GPU profile/adapter를 연결한다. AP/SKIN을 혼합하지 않는다. GPU 실행 증거와 품질 합격을 구분하고 미검증 pair/NPU/3병행을 후보에 올리지 않는다. gate 미해결이면 그 성능/학습만 보류하고 A24 파일럿 및 S26 정적 adapter 검증은 계속한다.
manifest의 미공유 파일은 실제 raw/대용량/개인자료다. 경로만 있다고 내용이 배포됐다고 가정하지 않는다. 공개 동결 profile로 새 정책 연구는 가능하지만 원자료 재보정과 PRIVATE_RAW_REQUIRED suite는 source가 없으면 보류한다. 공유 파생본의 경로 정리에 따른 SHA와 역사적 원본 SHA를 구분하고 새 성능 검증으로 승격하지 않는다.
TFLite/APK/NPU AOT/서명키를 Git에 넣지 않는다. 기기용 모델은 exact 원URL/크기/SHA·라이선스 계약을 따른다. 이 프롬프트의 ADB/기기실행/설치/새실측/NPU학습은0이다. 필요 측정은 조건·호출수·관측창·역할·판정·예산을 문서로만 남긴다.

5. 기능 검증과 학습 상태
실제 호환 Python3.11 계열·NumPy/Torch/Matplotlib을 별도 venv로 준비하며 기존 패키지를 교체하지 않는다. CPU로 시작한다.3060은 휴대폰 GPU가 아니며 사용을 위해 임의 병렬화하지 않는다. 프로세스/thread와 wall/CPU time을 기록한다.
이관 README의 raw 없는 unit suite와 frozen-model demo부터 실행한다. PRIVATE_RAW_REQUIRED를 raw 없이 PASS/SKIP해 놓고 전체 원검증 재현으로 주장하지 않는다. 새 정책 tests는 공개 fixture로 재현 가능하게 작성한다.
ATC 선택 변화·호환성·마스크·대기 유지/취소·동일시각 사건·요청 보존·lane 용량·시간 진행·전체 분모·기존 baseline 불변을 수작업 사례로 검사한다. 실제 gradient/Adam·독립 seed RNG·승수/normalizer·일시중지 재개 동일성을 검사한다. learner별 최종 actor/critic/Adam/RNG/승수/설정/cursor/소비/active clock을 원자 보존하고 best-validation actor와 terminal actor를 구분한다. REQUEST_STOP은 안전 경계에서 저장하며 재개 때 예산·seed·clock을 초기화하지 않는다.

6. 작은 개발 파일럿
첫 실행 전에 settings/seed/trace/모형SHA/후보·보상·mask/비교군/개발·확인 분할/환경수/계산시간 계약을 파일로 고정한다. 현재 새 학습 등록은0이다. low/burst/sustained와 검증 초기상태를 포함하며 새 seed는 기존 registry와 대조한다. 이미 본 자료를 새 확인으로 쓰지 않는다.
새 전달용 실행 상한: 총 환경1,536·실제 학습384에피소드·누적활성240분·마지막10분 저장. 과거 예산 재개가 아니라 이 새 과제의 제한이다. A24 먼저, S26은 gate 통과 시에만 실행하며 기기별 독립 학습seed11/23/37×최대64=192를 넘지 않는다. fixture/native smoke/대조/평가도 환경 상한에 포함한다. 모형 재적합·대량 튜닝·본학습 자동확대0이다. 이미 소비한 양을 차감하고 상한에서 저장·종료한다.
비교군은 실제 프로젝트 Band/Triton 제한적 재현, EDD+ECT, 같은 shortlist·행동·입력·물리mask의 비학습 선택기, 새 PPO3seed로 최소 구성한다. 같은 trace·실현 비용·기한·초기·자원·관측창으로 비교한다. 기존 Joint/Cost/PPO512 과거 성적을 새 seed의 직접 대응 비교로 합치지 않는다. DQN/GNN/SAC/HEFT/CP-SAT 등 일괄 추가0이다.
유망 PPO만 남은 예산에서 NoWait 또는 열정보 제거 한 축을 제한 평가한다. 행동/mask 범위 효과와 학습 효과를 분리하며3seed 모두 보고한다. 최고 seed만 고르지 않고64회 결과를 수렴/강화학습 일반 실패로 판정하지 않는다.

7. 결과와 공유
긴급P95·기한위반, 일반 기한내/전체완료·실패·미완료, 동일창 whole-device J, 같은 온도채널 peak/경로/근거 있는 기준초과시간, 판단시간·대기·병행·점유·실제 wall/CPU time을 조건별로 공개한다. 서비스 악화·미완료로 얻은 절감은 우위가 아니다. 서비스 유지 아래 열 개선형/에너지 개선형/공동 개선형/상충/동률을 구분한다. 모형 오차보다 작은 차이를 실제 개선으로 확정하지 않는다.
원단위 KPI로 검토한 후보·조건 안의 추천을 선정한다. RL과 같은 후보 비학습 선택기가 동률이면 단순한 방법을 우선한다. 전역최적/외부제품우월/실기기절감을 주장하지 않는다.
새 ID에 README/사전계약/CSV 원장/3seed 학습로그/checkpoint metadata/한국어 그림/오프라인HTML/verification/재현명령을 보존하고 STATUS/PLAN/DECISIONS를 갱신한다. 원자료/결과/checkpoint/기본/strict/experiment_ready=false는 유지한다. 같은 task가 있으면 원장·상태로 재개하고 중복 실행하지 않는다.
일반 코드/경로/파서/문서 오류는 원인을 기록하고 수정·관련검증 후 계속한다. 기준완화·미지원 계수·실기기 실행·optimizer 리셋으로 우회하지 않는다. 막힌 부분이 있어도 가능한 PC 작업을 완료한다. 작은 공유 코드·설정·보고서만 authorized branch에 commit/push하고 실제 원격HEAD를 확인한다. 진행량·저장상태·남은 불확실성을 간결하게 보고하라.
```

이 상한은 작은 파일럿 범위이며 수렴 예산이 아니다. 프롬프트 게시 PC에서는 새 ATC 구현·학습·기기 작업을 시작하지 않는다. 실제 데스크톱 실행 계약과 소비는 이후 별도로 기록한다.
