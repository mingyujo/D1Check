# S26 운영·수정 인계

최신 정본: **MULTI001_G004 3240환경·전수감사·분석·화면 검증 완료, 정책 우위/물리 예측 타당성 미입증**. [결과·AP 외삽 경계](MULTIRESOURCE_COMPARISON_KO.md), [재개·파일 지도](docs/G004_HANDOFF_KO.md). 새 RL0.

원PC 경로/전량 복원/연결 의존성과 실패 복구는 [G004_HANDOFF](docs/G004_HANDOFF_KO.md)에 있다. 원 생산3240·전수감사 완료물을 다시 돌리지 않는다.

최신 엔진은 experiments/multiresource_v1/source/MULTI001_G004이며 src/는 과거 SIM002다. multi_simulator가실제슬롯·공유CPU·진행, multi_actions/nominal_rollout이공개명목배정, multi_timing/midpoint_work/multi_cost가시간·온도·비용이다. PACKET.json.gz가봉인입력이다.

새개선은새source/output/budget/DEV/평가에등록한다. START내구저장→raw→prepared→row→terminal을지키고소비된미저장identity/FAIL을대체seed로메우지않는다. 실제worker/명령/생성/계보와공동잠금을확인한다. live원장읽기는FileShare.ReadWrite|Delete 규약을쓴다.

상태열람은node cli/s26.cjs verify/replay, 화면은serve --view latest다. API-J는배터리단위가정, AP는HAL이며피부온도/실측3자원/실기기순절감을인증하지않는다. 동결원수치·기한·분모·기존평가/자동화/다른작업을보존한다.
