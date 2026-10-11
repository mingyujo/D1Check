# M5 — S26 상태 분리 12세션 · 품질 연결 · 지속 ABBA 4세션 (레포 원장 사본)

정본 원장 = OneDrive `D1_ondevice\sim\out_statesplit\freeze_statesplit.txt` (append only). 여기는 커밋 시점 요약.

## 결과 전 고정 (커밋 ① · ②)

- 등록: `d1sim/docs/상태분리_사전등록_v2.md` (717bc4e5…) · `d1sim/docs/지속감속_확인_사전등록_v1.md` (fd197584…) — 커밋 ① `9ed096f`.
- 앱 변경 = 검증부만 (기존 APK 는 짝/홀 요청열 · 실험 ID 표 고정이라 상태 분리 요청열을 거부): `MixreqContract.M5_EXPERIMENTS` (S26-STATESPLIT-01 · 522 · 120 s · index 0..11 / S26-SUSTAIN-ABBA-01 · 3,000 · 720 s · index 0..3) · `StatesplitPlan.kt` · `RequestPlan.requireDerived` / `SessionManifest.validate` 분기 1개씩. 엔진 · 런타임 · 정책 · 계약 키 · 기존 표 무변경.
- Q1 = `InputListActivity` / `InputListEngine` (세션 경로와 따로 · 같은 RuntimeSpec · CompiledModelRuntime · Q20 canonical 텐서 · Q20 결과 형식 · png_check 1장).
- Q2 = quality-runner (`origin/s26-quality20` `5857152` 경로 체크아웃) + `d1_q2_gpu_precision` (NONE · FP32 · FP16).
- 호스트: `statesplit_common` (실행 때 mixreq_common 표에 2행 추가 · 파일 무변경) · `statesplit_plan` · `statesplit_validate` (규칙 3 창만 [35, 150) s) · `statesplit_session` (SOC · 시작 SKIN 띠 → mixreq_session 그대로) · `statesplit_driver.ps1` · `statesplit_readout` (판정 없음) · `quality20/m5_quality.py` (Q1 · Q2 실행 · q20_judge import · Q3 기준).
- 시간축: 요청 = 공통창 35.0 ~ 119.9 s (S1 · S2 · S3) · S4 쉼 = drain + 냉각 앞부분 · phases 기존 그대로.
- split: manifest `split` = confirmation (앱 뜻 = 실제 세션) · 등록의 dev / confirm = `analysis_split`.
- 계획: `plan_v4ss/plan.json` e4536960… (12 + 스모크 1) · `plan_abba/plan.json` febd3a75… (A B B A, plan_v3s 00 · 01 복사, 바뀐 키 = experiment_id · session_id · session_index · pair · requests[].request_id).
- APK: request-runner `c2e78939…` · quality-runner `d90f374e…` (커밋 안 함).
- 계산 · 판정 (등록 §2 · ABBA §2) = Cowork. 이 세션은 readout 까지.
