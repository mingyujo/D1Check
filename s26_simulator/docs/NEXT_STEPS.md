# 미완료 작업 · 2026-10-17

[START_HERE](../START_HERE.md)·[STATUS](../STATUS.md)·[최신 판독](../STATE_AWARE_COMPARISON_KO.md)을 읽고 Git HEAD/원장을 확인한다. STATE001_G001 300건은 실행·전수 감사·GitHub 업로드까지 끝났다. 이 실험 재실행이나 재감사로 시작하지 않는다. 아래는 후속 개발 과제이며 아직 구현/채택된 정책이 아니다.

## 1. 공동개선 조건과 정책 전망

현재 상태 배정기는 공개 온도·점유를 사용하지만 J+열 가중합이 열 악화를 허용한다. 분류4,608건 모두 GPU의 J 이득/열면적 악화가 교환됐고, 평균J 감소와 온도 상승이 함께 나왔다. 열 악화 금지/에너지 제약과 대기 큐 전체를 보는 제한 탐색·강건 최적화 등 산업공학 후보를 검토한다. ATC가 EDF와 같은 실제 선택을 한48조건도 보존하며 순서가 달라질 수 있는 조건과 정보/지원 마스크 한계를 구분한다.

새 정책의 source/output/budget·개발 입력·선정 규칙·완료 조건부터 등록한다. 관찰한 STATE 평가로 정책을 재선정하거나 같은 입력에서 새 성공 결과를 모으지 않는다. FIFO/EDF와 후보/공개정보/납기/부하를 동일하게 유지한다. 납기·전량완료가 깨진 절감은 개선이 아니다.

## 2. 기존·신규 실측의 물리 연결 정확도

R21 재현 API-J MAE37.53J/AP MAE0.612℃와 단계 전이 오차가 남아 있다. `research/fit_phase_transfer_v1.py`·`models/phase_transfer_NOT_ADOPTED.json.gz`는 미채택 후보다. 새 채택 전 JS/Python 동등성, whole-vector 상관·exact0·일반 readback/persist/release/AVAILABLE의 순서를 보존하고 측정 조건별 손해/오차를 함께 검토한다.

STATE packet의 측정8,636벡터와 긴급 탐지 전이 view1,216개를 독립 측정으로 중복 세지 않는다. 기존 U96/N32와 경쟁 U112/N16, API 단위 가정/AP 센서와 표면온도를 구분한다. 음수 한계 J는 회귀의 비용 차분이며 실제 음의 전력이 아니다. 전이/예측 가정은 근거·적용 범위·민감도를 명시한다. 정책 실행의 실제 모바일 지연/J 비용도 아직 미식별이다.

## 3. 검증된 환경에서 새 롤링+ATC+RL

현재 통합 엔진의 새 학습은0이다. 과거 RARL 4군×3seed×64는 별도 엔진 이력으로만 사용한다. 환경 검증 뒤 새 등록·새 학습·DEV-only 선택/SHA동결·새 평가로 비교한다. 64경험의 과거 부진을 RL 전체 불가능으로 일반화하지 않는다. 안정적 이점이 부족하면 사용자가 승인한 산업공학 핵심의 다른 방식도 검토할 수 있다.

## 실행·판독 공통 조건

- 최신 정책 소스: `experiments/state_aware_v1/source/`; 실제 운영·검산 계보: 그 안 `operations/SOURCE_MAP.json`. `src/`와 V4 HTML은 이전 기준판이다. 원 PC용 절대경로/잠금 명령을 다른 환경에서 그대로 실행하지 않는다.
- 인계 당시 총예약121206/137712·전역START28179, STATE cap320/소비300·원SIM512잔12다. 새 PC/clone마다 예산이 새로 생기지 않는다. 모든 canonical 원장과 다른 A24 예약·실제 PID·명령·생성시각을 다시 확인한다.
- ownheavy1/global Python leaves2·공동 잠금·관련 볼륨8GiB 유지. raw→prepared→row→terminal을 지키고 소비된 미저장/FAIL identity 재수집·대체seed0. 원V2 EP814/FINAL·CAUSAL·NODGPU gate 및 다른 작업/WIP·자동화 PAUSED를 보존한다.
- 모든 정책/학습seed·부하·초기이력·예측 가정에서 서비스70/80/90/95/100%, 긴급/일반/전량완료, 응답 P95·납기손해·미완료, route/겹침/WAIT, J0~180·AP35~180·peak·180잔열을 함께 판독한다. 조건부 합성 변동을 독립 폰 표본 CI나 전체 물리 불확실성으로 부르지 않는다.

이전 과제 문서도 [보존](history/NEXT_STEPS_BEFORE_RESUME_GUIDE_20261017.md)했다. 이번 문서 갱신에서 새 환경/학습/fit0이다.
