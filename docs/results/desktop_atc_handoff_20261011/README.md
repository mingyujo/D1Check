# GitHub 이관 — A24·S26 새 ATC→PPO

2026-10-11. 로컬에 남은 공유 가능한 프로젝트 자료와 **데스크톱 Codex용 프롬프트**를 게시한다. 이번 이관에서 새 ATC 구현·본학습·실측은 하지 않는다.

- [전체 복사 프롬프트](../../DESKTOP_ATC_PPO_PROMPT_20261011.md)
- [새 설계와 구현 전 계약](../../ATC_PPO_EVENT_DESIGN_20261011.md)
- [S26 통합 계획](../../S26_SIMULATION_PLAN_20261011.md)
- [공유 파일·원본/공유 SHA·제외 이유](publication_manifest.json)
- [이관 검증](verification.json)

## 공유 범위

A24 v2/v3 코드·unit tests·동결 모형·CSV/그림/오프라인 보고서, 계측 종료 수정과 Kotlin tests, S26 계획·세 역할 토론·검증 기록, 기존 미공유 작은 연구 그림/분석물을 추가한다. 사용자 WIP·HTML/PDF·다른 worktree·원자료는 보존한다. 원격 데스크톱512 결과도 유지한다.

개인 절대경로가 있는 분석 JSON은 **공유 파생본에서만** 저장소 상대경로로 바꾸고 원본/공유 SHA를 함께 남긴다. 숫자·모형 계수·설정은 동일하다. 역사적 등록 SHA는 당시 원본을 가리키며 지금 공유 byte SHA와 같은 것으로 표시하지 않는다. 원본 재보정/FAIL 변경은 없다.

공유 Python 사본의 외부 원자료 경로는 `D1CHECK_ARRIVAL_EXTENSION` 또는 현재 사용자의 Documents 아래를, ADB는 `D1CHECK_ADB` 또는 PATH를 사용한다. 이들은 과거 실행기를 이식 가능하게 하는 locator 수정이며 이번에 기기를 실행하는 허가가 아니다. 예측 API test는 같은 도착 전 공개 정보·예정 티켓을 담은 `tools/fixtures/simulation_model_v3_prediction_public.json`을 사용한다. 원자료가 필요한 전체 개발 입력 loader를 공개 fixture로 대체한 것은 아니다.

APK/TFLite/NPU AOT/서명키/venv/캐시/사용자 문서와 대용량 원 ledger·checkpoint는 새로 추가하지 않는다. 기존 승인·게시된 자체 terminal64 세 상태 ZIP은 유지한다. 미공유는 manifest에 이유를 남기며 모든 raw가 GitHub에 있다고 주장하지 않는다.

## 원자료 없이 가능한 검증

호환 Python3.11 계열·NumPy/Torch/Matplotlib을 격리 환경에 준비하고 루트에서 실행한다. 실제 출판 검증 환경은 verification.json을 따른다.

```powershell
python -B -X utf8 -m unittest tools.test_d1_simulation_model_v2 tools.test_d1_simulation_model_v2_campaign tools.test_d1_simulation_model_v2_report tools.test_d1_simulation_model_v3 tools.test_d1_simulation_model_v3_campaign tools.test_d1_simulation_model_v3_energy tools.test_d1_simulation_model_v3_prediction tools.test_d1_simulation_model_v3_thermal -v
python -B -X utf8 -m tools.d1_simulation_model_v2_demo --model docs/results/simulation_model_v2_01/run_v1/model.json --output output/atc_handoff_frozen_demo --mode mean
```

기존 demo 출력은 덮어쓰지 않는다. 이는 원 모형 재생·기능검증이며 새 정책 성능 확인은 아니다.

`test_d1_simulation_model_v3_inputs`, `test_d1_simulation_model_v3_report`, `test_d1_simulation_model_v3_hybrid_report`는 로컬 원실측/collection plan이 필요한 **PRIVATE_RAW_REQUIRED** suite다. 전체 재보정/이 suite 재현은 raw 없이 불가하다. 없는 input을0/fixture로 채워 원자료 재현 PASS를 만들지 않는다. 새 ATC와 A24 동결 모형 정책 파일럿은 전체 raw 없이 가능하다.

## S26 확보와 평가 경계

주 브랜치만 받으면 S26 근거가 모두 모이지 않는다. 다음 고정 tree를 별도 확보하며 무조건 merge하지 않는다.

| 자료 | 브랜치 | 고정 커밋 |
|---|---|---|
| 기존 d1sim | s26-measure | 0a0749890fba2452c5907433c6bea476a2da7e24 |
| 최신 mixed | s26-mixreq | 21cba44faa5fff1fb9703b590aa536a6207f8de5 |
| 품질20장 | s26-quality20 | 5857152ad8244c41975843ded77dd33024f38f2d |

둘 다 사용자가 담당하되 profile/계수/품질/지원/센서/시각은 기기별로 유지한다. GPU 품질·mixed7경계·시각/단위/에너지 검증 전 S26을 같은 승인 행동 공간으로 취급하지 않는다. 기존 NPU는 보존하고 새 CPU/GPU PPO에 자동 추가하지 않는다.

원64→512는 [완료 결과](../desktop_amount512_20261011/README.md)의 추가1,344학습·2,200환경·세 strict FAIL을 따른다. 이전 프롬프트를 재실행하지 않는다. 새 ATC→PPO는 별도 schema/정책/초기 학습이다. 기본/strict/experiment_ready=false와 과거 소비·실패를 유지한다.
