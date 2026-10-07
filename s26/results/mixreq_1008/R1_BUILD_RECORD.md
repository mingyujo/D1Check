# R1 (2026-10-08) 빌드 · 시험 기록 — S26 혼합 요청 (`:request-runner`)

> 작업 클론 `D1Check_mixreq` · 브랜치 `s26-mixreq` · 등록 `d1sim/docs/혼합요청_사전등록_v1.md` SHA `edf9e594…` 커밋 `20967fb`.
> 폰 명령 0 · 혼합 요청 실행 0. 보고서 = OneDrive `D1_ondevice\작업결과_1008_R1_혼합요청개발.md`. 표기 [P] 실측.

## APK (debug, 기본 debug 키) [P]

- `request-runner/build/outputs/apk/debug/request-runner-debug.apk` — **14,439,196 B · SHA-256 `fb2407911a5ee036b52e9bdb259d5e1bb1e8b16082ed9afad92eb576dd8fb230`** (04:42 KST, `gradlew :request-runner:assembleDebug`, 소스 = 커밋 ②③ + 호스트 커밋 전 트리; APK 는 커밋하지 않는다)
- 안에 모델 없음 (전부 `/data/local/tmp/mixreq/`) · `lib/arm64-v8a/libLiteRtDispatch_Samsung.so` = `f08656a6…` (npu-runner 와 같은 파일)
- 설치: `adb -s $env:ANDROID_SERIAL install -r <apk>` — 측정 앱 `com.example.d1check.npurunner` 는 건드리지 않는다

## 시험 [P]

| 시험 | 결과 | 시각 |
|---|---|---|
| `gradlew :request-runner:testDebugUnitTest` | **32 / 32** (RequestPlan 4 · PolicyStudy 4 · ImageContract 5 · Decoders 6 · EventLog 5 · SessionRoundTrip 8) | 04:4x (3회 연속 통과) |
| `py -m pytest s26/tools/mixreq` | **29 passed** | 04:4x |
| `py -3 s26/tools/mixreq/e2e_selftest.py` | **E2E PASS** — 6 사례 (blockA_cpu · blockA_par · blockN_cpu · blockN_parnpu 적격 · blockN_npu_create_fails · blockA_plugged 부적격) + 음성 증거 변형 5 (gpu_partial · gpu_other_delegate · no_enn · npu_zero · npu_failure → 규칙 7 만 FAIL) · NPU 계약 PASS (가짜 출력) · readout 블록 A/N 각 1쌍 "쌍 부족 — 기술만" · A24 식 대조 match · inventory 16행 (not_attempted 10) | 04:45 |
| 회귀 `gradlew :npu-runner:testDebugUnitTest --rerun` | **61 / 61** (기준 61) | 04:46 |
| 회귀 `py -m pytest tools` | **243 passed · 1 failed** (기준과 같은 1건: `test_d1_representative_tensors` CRLF fixture 아티팩트) | 04:39 |
| 회귀 `py -m pytest d1sim/tests` | **93 passed** (기준 93) | 04:39 |
| `git diff --stat origin/s26-measure -- npu-runner benchmark-runner app telemetry-contract tools gradle` | **빈 diff** (기존 파일 변경 0 · `settings.gradle.kts` +4 줄만) | 04:41 |

e2e 의 logcat 은 **합성** (D1MIX 표시 + 동결 정규식 패턴 줄) — 정규식 · 창 자르기 · 규칙 배선만 검사한다. 실기기 로그 패턴은 R2 스모크 S1 에서 처음 본다.

## 계획 v1 [P]

- `s26/results/mixreq_1008/plan_v1/plan.json` SHA-256 `a733041ca269dd6a9f313b34f28de92ba6449af2877a1e971727fcde84776708` · 세션 16 (A 0~7 · N 8~15) + 스모크 4 (S1 warmup_only 블록 N · S2 CPU · PAR · PAR-NPU) · 호출 3,216 / 스모크 108 · 두 번 생성 바이트 동일
- 재생성: `py -3 s26/tools/mixreq/mixreq_plan.py --out <dir> --cls-model local_models/efficientnet_lite0.tflite --det-model local_inputs/public/efficientdet_lite0.tflite --aot-model npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite --png local_inputs/canonical_v123/00575b9132bb3746.png --anchors local_inputs/reference_pc/anchors.json --cls-labels local_inputs/reference_pc/labels_without_background.txt --det-labels local_inputs/reference_pc/labels.txt`

## git 밖 입력 (R2 가 클론에 두어야 하는 것 — SHA-256) [P]

| 파일 | SHA-256 |
|---|---|
| `local_models/efficientnet_lite0.tflite` (18,582,189 B) | `6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0` |
| `local_inputs/public/efficientdet_lite0.tflite` (13,836,895 B) | `40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58` |
| `npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite` (10,033,376 B) | `311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31` |
| `local_inputs/canonical_v123/00575b9132bb3746.png` (937,799 B) | `3e8b925feafbfe5fdd4efb9d7911f445a3212100fa73744f6fd855cf6160f1ab` |
| `local_inputs/reference_pc/anchors.json` (1,438,467 B) | `e095e869203d5f5442583712e1546aac8f5112512b1a98925165fe17b455c3bc` |
| `local_inputs/reference_pc/labels_without_background.txt` | `e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f` |
| `local_inputs/reference_pc/labels.txt` | `f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2` |
| `local_inputs/reference_pc/reference_pc.json` (PC 참조 — S1 대조용) | 생성물 (make_reference_pc.py) |
| `request-runner/src/main/jniLibs/arm64-v8a/libLiteRtDispatch_Samsung.so` | `f08656a642c46e7b06b64fbe1e0800de9e73b0b69c1641b87995562b4a16840f` |
