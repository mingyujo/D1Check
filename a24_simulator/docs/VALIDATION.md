# 실제 검증과 보존한 실패

## 현재 수정본

| 범위 | 실제 결과 |
|---|---|
| 납기·부하 설계 | Node664 assertions PASS, 기본12·확장36조건/작업×우선순위 교차/기한 순서 역전/창 범위 |
| 진단·자원 단위 검사 | Python4 tests PASS, 에너지 기저 보존·동일 일정·lane 충돌·외삽 산술 |
| 모형 이전 | 원 timing/AP digest 그대로 구성, 새 기기 측정/새 물리 적합0 |
| 새 PPO | TRAIN64·Adam update8·optimizer step99·actor SHA 변경, DEV24에서 EP32 선정 |
| 평가 | 14조건×7정책=98환경 완료, 평가로 재선정0 |
| 저장 결과 독립 검산 | Node20,943 checks PASS: 모든 요청·납기·AVAILABLE·반개구간 자원 점유·AP 사다리꼴·J*·null·소비·원95개 소스 핀 |
| 저장 NN/Adam 재현 | 7,898frames·31,848 checks PASS: 입력·마스크·선택 logprob·critic,64개 에피소드 after CP와8회 optimizer update/행동·셔플 RNG 정확 일치, 새 환경0 |
| 폴더 이동 | 별도 clean copy에서959개 로컬 객체 해시 검증·151개 runtime source/input 핀이 전부 복사 폴더 안으로 해석됨, 같은 timing/AP/선정 network digest·원 입력 경로 접근0 |
| 실제 브라우저 | UI_QA_02 밝음/어둠×360/736/1280의6뷰·20 assertions,12조건·7정책·일정 동일성/활동창/타임라인, JS/console/외부요청/overflow0·원장 SHA 불변·새 환경0 |

소스와 결과 SHA는 `models/TRAINING_OPERATION_V2.json`, `TRAINING_COMPLETE.json`, `results/INDEPENDENT_SAVED_AUDIT.json`, `TRAINING_REPLAY_AUDIT.json`, `UI_QA_02/RESULT.json`, `PACKAGE_MANIFEST.json`에 있습니다. 형식·산술 PASS를 기기 정확도/에너지 절감 PASS로 쓰지 않습니다.

## 실패와 정정

- 최초 portable preflight는 테스트 입력 ordinal 누락으로 실패했습니다. 모형 구성 후 공개 요청 검증 단계이며 환경 START0입니다. 입력 검증을 거친 preflight에서 같은 원 모델 digest를 확인했습니다.
- TRAIN001은 START guard의 필수 식별 필드 누락으로 kernel 진입 전 FAIL1입니다. 원 operation/source/원장과 실패 seed20261101을 보존했습니다. 새 V2 wrapper·namespace와 새 train seeds20261301…에서만 실행했습니다. guard를 완화하지 않았습니다.
- UI_QA01은 수동 편집 화면의 RL 선택 목록에 새 checkpoint 옵션이 빠진 것을 차단했습니다. 원 index/server를 보존하고 별도 index_v2/server_v2로 수정했습니다. 원95개 학습 source pin은 그대로이며 새 UI2개를 추가 봉인했습니다. 실제 계산 START0입니다.
- 과거 G001 P0 FAIL·unsupported20·미시도·raw 불완전·scalar output-hash 검사기 오류 등은 전체 보존본과 docs/history에 남아 있습니다. 새 결과로 덮거나 환급하지 않았습니다.

## 무엇을 아직 검증하지 못했는가

교정 실측 J·현재 D_GPU·새 병행 상호작용·설치 APK/delegate·출력 품질·새 독립 실기기 정책 효과는 미검증입니다. 새 학습 한 seed64episode는 수렴/알고리즘 우수성의 증명이 아닙니다. EVAL의 NN argmax/logprob/critic는 실행 중 감사했고, 학습 경험64개는 별도 저장 재현했습니다. 모든 EVAL decision의 별도 NN tensor 파일을 저장한 것으로 쓰지는 않습니다.
