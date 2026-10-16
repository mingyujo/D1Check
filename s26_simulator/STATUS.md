# S26 현재 상태 · 2026-10-17

**처음 재개할 때는 [START_HERE](START_HERE.md)를 읽는다.** 목표는 긴급0.8초/일반2초 납기·전량완료를 지키면서 열·에너지를 함께 줄이는 것이다. 주방향 롤링+ATC+RL, 시뮬레이터 검증 선행·새 RL 후순위다.

## 완료

- 계산 코드/결과 기준 commit: `30e16dd02c372492006552deb1cc4216f144b4a1`, branch `codex/s26-simulator-handoff-20261016`. 이 재개 문서 정리는 이후 문서 커밋이다.
- 최신 실험 `STATE001_G001`: 현재 전달 AP·공개 점유/과거 앱 단계 전망 배정기. STATIC/STATE×FIFO/EDF/ATC, 기존 대조2+경쟁 부하2·초기3·공통draw4. P012+주비교288=300 START/PREPARED/COMPLETE·환경FAIL0.
- 전수3,891,272검사/300 저장 비용 재적분·후보 전망35,430회/공개 입력 연결 PASS. 최초 감사35건을 포함한 실제 비용 재적분335건은 별도 감사 소비다. ZIP3개/900파일 재압축해제 SHA, CLI383검사, GitHub 원격 복제본 SHA 확인 완료.
- 이전 명목 배정 공정비교/동률 원인 진단, SIM002/V4, 과거 별도 RARL/IE·전체 실측/정정 계보도 보존했다. 기존 Release core ZIP은 `190072a` 시점으로 최신 실험을 포함하지 않는다.

## 확정 결과와 현재 장애

경쟁24조건(각128요청 U112/N16)에서 STATE 배정기의 EDF와 ATC는 전128건 납기24/24조건·평균184.275174 API-J·AP32.472116℃로 같다. FIFO는35건 지연/전량 납기10/24조건, 미완료는 전군0이다. 순서 경쟁384회에서 ATC와 EDF의 선택은 같았고 기존 대조 포함48조건 물리 궤적도 동일해 EDF 대비 추가 절감0이다.

같은 ATC에서 새 STATE는 기존 STATIC 대비 J0.2761% 감소 대신 평균 AP+0.095057℃/최고+1.825049℃다. 부하별 J 부호도 반전한다. 주비교 분류4,608건 모두 GPU의 낮은 예측J/높은 열면적을 가중합이 선호했다. **공동개선판 채택 보류, 물리 목표 달성 미확정**이다.

R21 재현 MAE는 API-J 약37.53J/AP 약0.612℃이며 조건부 단계 보완 모형은 아직 미채택이다. 현재 J는 배터리 API 단위 가정, AP는 센서 예측이다. 긴급 탐지의 단계 전이와 정책 계산의 모바일 지연/J 미반영도 남아 있다. 최신 통합 엔진의 새 RL은0이며 과거 엔진의 학습과 구분한다.

## 파일과 검증 입구

- [결과/원인/한계](STATE_AWARE_COMPARISON_KO.md), [최신 코드·입력·CSV·원자료·감사](experiments/state_aware_v1/). 정책은 그 안 `source/state_actions.cjs`·`state_cost.cjs`, plant도 같은 source 폴더다.
- `src/`·`data/engine_packet.json.gz`·`web/index.html`은 SIM002/V4 기준판이다. 최신 STATE 실험과 혼동하지 않는다.
- `node cli/s26.cjs verify` 및 `node cli/s26.cjs replay --comparison state-aware-v1 --bank COMPETE_A`로 저장 결과를 확인한다. 새 환경/학습0이다.
- [업로드/원격 검증 당시 영수증](evidence/STATE001_PUBLICATION_VERIFIED.json), 현재 배포 파일 SHA는 `CORE_MANIFEST.json`이다.

## 다음 최대3 · 아직 미완료

1. 열 악화를 허용하는 비용 가중합/한 단계 후보 전망을 보완하는 제약 배정·큐 전체 탐색을 별도 새 개발/평가 등록에서 검토한다.
2. 기존+신규 실측의 단계 전이·비용/열 예측 정확도와 미채택 보완 모형을 검증한다. 계수로 격차를 인위 확대하지 않는다.
3. 환경 검증 후 최신 엔진의 롤링+ATC+RL을 새 입력/DEV선정/동결/평가 계보에서 학습·비교한다. 현재 평가로 재선정하지 않는다.

상세는 [NEXT_STEPS](docs/NEXT_STEPS.md). 인계 당시 총예약121206/137712·미예약16506·전역START28179, STATE300/cap320·원SIM512잔12다. 복제본의 새 예산이 아니므로 다음 실행 전 실제 PID·모든 원장/다른 기기 예약·공동 잠금·ownheavy1/global Python leaves2/관련볼륨8GiB를 다시 확인한다. 원V2 EP814 미저장/FINAL·CAUSAL·NODGPU gate, 다른 작업/WIP, 자동화 PAUSED를 보존한다.

이전 상태 문서 전체는 [보존본](docs/history/STATUS_BEFORE_RESUME_GUIDE_20261017.md)에 있다. 이번 갱신은 재개 문서/파일 지도 정리이며 새 정책환경·NN·fit·물리 재적분0이다.
