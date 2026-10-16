# S26 전체 실측 요청과 우선순위

사용자 요청으로 핵심·후속 실측을 한 전달문에 모았다. 기존87세션 문서·템플릿·ZIP은 그대로 보존하며 새 통합 요청은 [S26_ALL_REQUEST.txt](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_ALL_20261014/S26_ALL_REQUEST.txt)다. 이 문서는 측정 카탈로그·설계 제안이며 기기 실행 등록이나 APK/입력 패키지가 아니다. 작성·정적 검산만 했고 실측·NN·환경·기기명령·외부 전송은0이다.

| 우선순위 | 요청 범위 | 세션 제안 |
| --- | --- | ---: |
| P0 | 실행기·계측/기능, 기존 L-G/L-C100 전력 오차 재현 | 기존 핵심에 포함된10 + 추가16 |
| P1 | 분류 경로·순서·지원 병행·WAIT200 | DEV22 + 새확인55 |
| P2 | 동일량 버스트/균등 도착, 최근CPU/idle 이력, 같은12개 trigger의 WAIT200/1000 | 추가56 |
| P3 | 열 회복/성능, 전환/첫 호출, 상주/unload/recreate, 밀도/작업비율/기한, 동결 정책 조합 | 기능 확인 후 별도 고정 |
| P4 | 탐지GPU, 필요시 탐지NPU·CPU thread 설정 | 품질/경로 admission 후 별도 고정 |

세션 수를 산정한 부분은87+56+16=159이며 선행/개발54·독립확인105다. P3/P4가 빠져 있으므로159를 전체 요청의 완주 상한으로 부르지 않는다. P0의 계측/기능10은 기존87에 포함돼 중복 합산하지 않는다.159세션의 t=0 이후210초 본 관측은9시간16분30초, 사이90초 단순 예약은13시간13분30초이며 사전 기록·준비·온도 회복·회수는 추가다.

P2-A SMOOTH128은3군×7블록21, P2-B recentCPU는3군×7블록21, P2-C는 WAIT200x12/WAIT1000x12 각7로14다. 이전200x16과1000x12의 차이를 대기 길이 한 요소 효과로 말하지 않도록 같은 trigger 대조를 추가했다. 기존 큰 전력 오차 재현16은 L-C/L-G 각DEV3·CONFIRM5의 별도 모듈이다.

P2를 채택하면 P1과 같은 DEV/CONFIRM 블록에 배치하고 순서를 함께 무작위화한다. 이후 다른 날 추가할 때는 동시대 기준군의 새 소비를 포함해야 한다. recentCPU의 기준은 같은60초 idle 준비이며 gate는 준비 전, 이후 상태는 관측한다. 순위와 범위는 확인 결과 전에 동결한다.

P3/P4도 무엇을 비교하고 무엇을 반환해야 하는지 전달문에 적었다. 현재 API·계측·품질과 정책 adapter가 확인되지 않아 허구의 정밀 세션 수나 완료 판정을 붙이지 않았다. runtime 재생성은 hardware sleep/wake와 구분하며, 최근CPU·AP 관측만으로 DVFS/열계수의 단독 원인을 확정하지 않는다. task×priority 교차는 응답 경계 계약부터 확인한다. 고정 처방 재생과 공개관측에 반응하는 온라인 정책도 구분한다.

전체 항목표는 [PRIORITY_MATRIX.csv](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_ALL_20261014/PRIORITY_MATRIX.csv), 설계 상태는 [REQUEST_CATALOG.json](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_ALL_20261014/REQUEST_CATALOG.json), 전달 묶음은 [S26_ALL_HANDOFF.zip](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_ALL_20261014/S26_ALL_HANDOFF.zip)이다. 상세 검산·해시는 [QA.json](C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/ROLLING-ATC-RL-37/V2_MEASUREMENT_ALL_20261014/QA.json)을 따른다.

원 GEN002·CAUSAL·CHOICE·NODGPU 소스/계수/원장/모델과 기존 예약111334/137712·자동확인 완료 조건은 변경하지 않는다. 이 요청은 S26 담당자 전달문 작성이며 원래의 A24 측정 계획64세션을 수정하거나 새 기기 작업을 시작한 것이 아니다. 검증 대상 HEAD는12d64923be824ce4c88fca074fbe38820f5a7d25, 미커밋 WIP와 공통 문서의 무관한 bytes를 보존한다.


## GitHub 전달판 게시 — 2026-10-14

사용자 승인으로 [담당자용 폴더](https://github.com/mingyujo/D1Check/tree/codex/s26-measurement-request-20261014/docs/team/s26-scheduling-measurements-20261014)와 [초안PR4](https://github.com/mingyujo/D1Check/pull/4)를 만들었다. 요청/우선순위/전달문/README/manifest5파일만 게시하고 원격blob SHA를 원바이트와 대조했다. 공개본의 수정은 게시상태와 미공유 로컬참조 이식뿐이다. commit `1f18dd9d01f1d3d33de4146efecd06b5f97817b9`, 증거는 V2_MEASUREMENT_GITHUB_20261014/PUBLICATION_RECEIPT.json이다. 원요청/ZIP·기본branch·로컬HEAD·원실험은 보존했고 담당자 직접 전송·기기/NN/새환경 실행은0이다.
