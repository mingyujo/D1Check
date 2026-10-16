# RL 제외: 롤링+ATC / EDF / FIFO

이번 사용자 요청은 같은 A24 모형/입력에서 RL을 실행하지 않고 세 규칙의 열·총소비·작업 증분·납기를 비교하는 것입니다. 최대3,072개, 자동예약/주기GitHub조회OFF를 유지합니다.

## 롤링과 EDF의 관계

세 정책은 같은 사건 기반 엔진을 사용합니다. ENQUEUE/처리 단계/AVAILABLE 사건에서 공개 ready 큐·점유를 갱신하고 다음 실행 가능 배정을 선택합니다. EDF는 현재 절대 납기가 가장 이른 요청을 매번 고르므로 이 의미의 동적 재선택은 이미 있습니다. ‘롤링’은 ATC만의 독점 기능이 아닙니다.

미래 구간 전체의 여러 일정을 비교하고 첫 행동만 실행하는 다단계 rolling-horizon/MPC 최적화는 이번 세 정책 어디에도 없습니다. 기존 rolling+ATC+RL에서도 이번에 제거한 것은 학습 제어이며, 본 비교의 ATC는 아래 순수 명목 규칙으로 정확히 정의합니다.

|정책|요청·자원 선택|기준 코드|
|---|---|---|
|롤링+ATC|모든 현재 ready×빈 CPU/GPU에 native ATC점수, 긴급w2/일반w1, 명목 처리시간·납기 기반 공동선택|`../../src/interactive_kernel.py`의 `_rule_action('ATC')`; 여기 `rules.py` alias|
|EDF|절대 납기→계획 도착→ordinal→ID; 빈 자원 CPU 우선|`../edf_cpu_first_20261016/policy.py`|
|FIFO|계획 도착→ordinal→ID; ready에 들어온 요청만, 빈 자원 CPU 우선|여기 `rules.py`|

ATC식은 `log(w/p_occupancy) − max(deadline−now−p_response,0)/(2×mean_p_occupancy)`입니다. EDF/FIFO는 최단 예상 응답 경로를 사용하지 않습니다. ATC는 명목 시간으로 자원도 선택하므로 ATC와 나머지의 격차를 요청 순서만의 인과효과로 해석하지 않습니다.

열·에너지 prior/NN 잔차/학습/자발적 WAIT는 없습니다. 물리적으로 자원이 모두 바쁠 때의 RESOURCE_WAIT는 실제 AVAILABLE까지의 대기이며 새로운 냉각 행동이 아닙니다. 두 작업 모두 CPU/GPU, 최대2자원, 비선점·AVAILABLE까지 점유입니다.

FIFO의 도착순은 이번 workload의 **계획 도착 시각** 기준입니다. 실제 queue-entry 순서와 같은지 여부는 saved 감사의 `planned_FIFO_vs_queue_entry_head`로 별도 남깁니다. 요청의 실제 ready 이전에 실행하지 않습니다.

## 입력·모형·범위

- 앞선48/96/192/384/768/1536/3072 입력, 같은48사이클·분류/탐지50:50·긴급25%·도착률/상대납기를 그대로 사용합니다.
- 잠재 표본 key도 이전 EDF와 같습니다.384개는 앞선 실패와 분리한20261782 key, 나머지는20261781입니다. 정책 결과를 보고 새 seed/부하를 고르지 않았습니다.
- `shared_exact.py`의 입력 생성/산술 함수는 이전 장시간 소스와 AST동일을 검사했습니다. 처리시간·병행·AP·상태 비용/기저 계수는 변경하지 않았습니다.
- 같은 작업창은 첫 도착35초~마지막 도착+15초. 배출30초/+180초 AP는 별도이며 미완료·미응답을 누락하지 않습니다.
- EDF7개는 이미 완료된 정확저장본을 재사용합니다. 연결 검증용 EDF48 P01개만 새로 실행하여 요청 시각/AP/전체 metrics 정확동일을 확인합니다.
- 새 ATC7+FIFO7+P01=15START, 별도16예약(전역121246/137712)입니다. 이전공유511/512·장시간19/24의 여유를 자동소비하지 않습니다. 이번 NN실행/학습/fit/실기기0입니다.

J*는 기존 전력 투영의 조건부 미교정 비용입니다. D_GPU 등 미관측 비용상태는 전이와0~2배 증분 민감도(통계CI 아님)를 유지합니다. 210초 밖 장시간·초기 이력·실제 GPU/품질·온도→시간/전력 피드백은 미검증입니다. 실측J/에너지오차/CI null·물리목표 미입증을 그대로 둡니다.

## 파일과 검증

|파일|역할|
|---|---|
|`INPUTS.json`|앞선7입력과 잠재 key|
|`BUDGET_RESERVATION.json` / `OPERATION.json`|새 예산/소스/EDF저장본 SHA고정|
|`rules.py`|ATC native alias·FIFO CPU우선, 명목 query를 반복 계산 없이 기록하는 감사 hook|
|`shared_exact.py`|기존 입력/같은 창/AP/비용 함수 그대로|
|`run_rules.py`|자원/예산/공유lock·START 선기록·서비스 결과 선저장·raw/SHA/terminal·EDF P0|
|`test_rules.py` / `PURE_TEST_RESULT.json`|순수18검사·환경0·NN모듈 import/실행0|
|`audit_rules.cjs`|별도 JS로 시각/자원/정시·미완료/인과 비용/AP적분·ATC최대점수·EDF/FIFO선택 검산|
|`independent_arithmetic.inc`|이전 독립 산술 함수의 원문 추출 보존|
|`report_rules.cjs` / `qa_rules.cjs`|실제결과 화면과 Chrome6뷰 검증|
|`../../results/RULES_NO_RL_20261017_01/`|각raw/준비prediction·성공/실패 원장·P0/결과/감사/화면|

최신 수치·완료 판정은 `../../docs/RULES_NO_RL_COMPARISON.md`와 출력의 실제 `COMPLETE/AUDIT/UI_QA`를 함께 확인합니다. 작성된 소스나 진행 로그만으로 완료를 주장하지 않습니다. **소비한 OPERATION 재실행·실패 자동재시도·무저장 identity 재수집을 하지 마세요.** 추가 실험은 새로운 source/input/output/예산을 등록해야 합니다.

ATC의 평균 점유시간은 현재 실행 가능한 요청×자원 후보 전체에서 계산하며, 임의로 튜닝한 계수가 아닙니다. 현재 동결 엔진의 원식과 동일합니다.
