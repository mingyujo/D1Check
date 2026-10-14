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

## 추가 (D-1 스모크 뒤 · 2026-10-15 01:4x) — 고친 APK `m8c`

| 항목 | 값 [P] |
|---|---|
| 변경 | 스모크 1 (M128 BASE) 앱 power 마지막 표본 209.5 s (< 210) → `SessionEngineM8`: cooling 90 뒤 common + 210 s + 표본 2개 (실시간 1.8 s) 까지 연장 대기 (`M8_POST_T0_MIN_SECONDS` 210 · summary `cooling_extended_ns`) · 커밋 `2c6bf2b6` + `18c40bbb` (M8 행만 · 기존 행 무변경) |
| 빌드 | 깨끗한 빌드 01:45:57 (55 s) + 01:52 (50 s) → **같은 SHA `6193344011cc266868221722cf55ea2402da786df3d21186909601291e62c862`** · 14,666,996 B · 서명 `6394e51f…` 같음 |
| 시험 | `M8RoundTripTest` 7/7 (01:46 ~ 01:51) — 앱 마지막 표본 ≥ common + 21 s (×1/10) 포함 · 1차 (여유를 time_scale 로 줄인 판) 1 실패 → 실시간 여유로 고침 |
| 첫 APK `fb914139…` 로 한 것 | 회귀 2 · 스모크 (M128 BASE · WAIT200x16 · PAIR_G a2 · RECENT · IDLE · L64) — 동작 확인용 (앱 coverage 는 209.5 s) · P0 부터는 `61933440…` (설치 1회 · 그 뒤 재설치 금지) |

## 추가 2 (조민규 01:5x 8항목 v2 · 2026-10-15 02:3x) — v2 APK `m8v2`

| 항목 | 값 [P] |
|---|---|
| 변경 (M8 행만 · 기존 행 무변경 · `SessionEngine.kt` diff 0 유지) | `Request.offsetNs` (M8 ns 예정 도착 · 기존 행 = ms × 10⁶ 보조 생성자) · `M8Plan` (SMOOTH128 `35e9 + floor(i×15×537155000/127)` ns · `WaitArgs(waitMs, firstNBursts, nominalTotalMs)` · 537.155 정확 평균 상수 · 프로필 SHA) · `PolicyStudy.plannedWaitMs` (cap 제거 · 묶음당 1회 전량) · `SessionEngineM8` (ns 도착 · wait 이벤트 nominal/overrun · summary) · `SessionManifest` (`offset_ns` · `nominal_total_ms`) · 시험 3 파일 (+7 시험) |
| 빌드 | 깨끗한 빌드 02:34:39 (36 s) + 02:35:15 (39 s) → **같은 SHA `37960e25c5948f661f2f5b47a90a4356be1b3712706d34679e71a14842ced6ea`** · 14,670,296 B · 서명 `6394e51f…` 같음 (apksigner) |
| 시험 | `UNIT_TEST_RECORD.json run_v2`: M8PlanTest 8 · PolicyStudyM8Test 12 · M8RoundTripTest 9 · M6RegressionShapeTest 3 = **32/32** (02:1x ~ 02:3x) · 호스트 test_m8 · m6 · m7 · mixreq 68 passed |
| 설치 | **P0 첫 세션 전 1회 (이 APK) · 그 뒤 재설치 금지** · 설치 시각 · 기기 SHA 대조 = 원장 · 앞 APK `fb914139…` (D-1 회귀·스모크) · `61933440…` (m8c · 설치 0 · 미사용) 는 기록만 |
| APK 사본 (커밋 안 함) | `results/m8_build/request-runner-debug_m8v2.apk` (+ `_build1.apk`) |
