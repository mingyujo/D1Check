# BUILD_RECORD_M8 — M8-apk 빌드 기록 (2026-10-14 · 브랜치 `s26-m8` · 커밋 B-2 `875384e73` (앱) 뒤 · 설치 0 (D-1 에서))

| 항목 | 값 [P] |
|---|---|
| 소스 | `s26-m8` 커밋 `875384e73` (앱) — `aaa7b87f` (M7 APK `878b10b7…`) 대비 `APK_M8_AREA_DIFF.json`: 계약/검증 (MixreqContract +76/−4 · SessionManifest +55/−3 · RequestPlan +4/−1 · **M8Plan 새 +145**) · 정책 (PolicyStudy +71/−0 · chooseM8 추가만) · 엔진 (SessionActivity +22/−5 분기 · **SessionEngineM8 새 +605** · **SessionEngine.kt diff 0**) · 전처리 · 디코드 · logger · runtime · sampler · 빌드 diff 0 |
| 빌드 명령 | `request-runner/build` 삭제 → `JAVA_HOME=C:\Program Files\Java\jdk-25` · `./gradlew --no-daemon :request-runner:assembleDebug` (gradle 9.5.0 · AGP 9.3.2 · Kotlin 2.2.10 · LiteRT 2.2.0 · `libLiteRtDispatch_Samsung.so` f08656a6 · debug keystore `~/.android/debug.keystore`) |
| 빌드 1 | 2026-10-14 23:30:44 ~ 23:31:24 (38 s) → `request-runner-debug.apk` SHA-256 **`fb9141396cffa5b646e93c0928567ba01e8d2ae6b187bd10ad39c37a579a526c`** · 14,665,736 B |
| 빌드 2 (깨끗한 재빌드) | 23:31:38 ~ 23:32:42 (1 m 2 s) → **같은 SHA** `fb914139…` (바이트 같음 · 빌드 재현 2/2) |
| 서명 | `apksigner verify --print-certs` (build-tools 36.0.0): Signer #1 certificate SHA-256 **`6394e51f94c71bd6e9cc5d76ff66e503583c1dca7d50f7ed175dd2e444cfcd32`** = M6 `6a4da1ac…` · M7 `878b10b7…` 와 같음 |
| M7 APK 와 항목 비교 (`m6_apk_compare.py` · `results/m8_build/compare_m7_m8.json`) | 항목 84 = 84 · 다른 항목 **`classes3.dex` 1개만** · META-INF 차이 0 · 리소스 · `.so` · classes.dex · classes2.dex 같음 (M7 ↔ M6 와 같은 꼴) |
| APK 사본 (커밋 안 함) | `results/m8_build/request-runner-debug_m8.apk` (+ `_build1.apk`) · 바이너리는 묶음 · 레포에 넣지 않음 (SHA 만) |
| 단위 시험 | `UNIT_TEST_RECORD.json` — 1차 86 중 79 · 유휴 재실행에서 M8PlanTest 6/6 · M6RegressionShapeTest 3/3 (기대값 오류 고침) · 새 계약 시험 22/22 · 기존 round-trip 의 'post-window drain incomplete' (sustained03 · 02C · statesplit) = 호스트 타이밍 (기준 커밋 worktree 대조 `results/m8_build/unit_base_aaa7b87f.log`) |
| 호스트 시험 | `test_m8.py` 8/8 (round-trip 산출물 있을 때) · 7/8 + skip 1 (깨끗한 빌드 뒤) · 기존 `test_m6` · `test_m7` · `test_mixreq` 66/66 |
| 설치 | **0** (D-1 에서 1회 · 그 뒤 재설치 금지 · 설치본 M7 `878b10b7…` 가 교체됨 → M7-B 는 M7 APK 재설치 필요 · questions_for_영훈 #1) |
