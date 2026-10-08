# R3 혼합 요청 v2 — 원장 (레포 사본, `D1_ondevice\sim\out_mixreq\freeze_mixreq.txt` 끝의 R3 절과 같은 내용)

> 작업 클론 `C:\Users\rhoyo\AndroidStudioProjects\D1Check_mixreq` · 브랜치 `s26-mixreq` · 시작 HEAD `03f271a` = `origin/s26-mixreq` (R2 끝).
> 표기 [P] 실측 · [D] 인용 · [E] 추정 · `미확인`. 주소 · 시리얼은 `<IP:PORT>` · `<SERIAL>`. KPI (응답 · P95 · 겹침 초 · 열 Δ · J) 는 readout 전에 이 파일에 쓰지 않는다.
> 우선순위: 프롬프트 R3 > 등록 v2 (`8e8e1104…`) > 등록 v1 (`edf9e594…`) > R2 보고서 §9 > CLAUDE.md.

## 영훈 결정 (10/9 04:05 · 04:14) — 결과 전 고정

1. **"1번 · 본측정 무조건 (10/9 04:05)"** — 부하를 바꾼 등록 v2 (도착 간격 200 ms) 로 가고, 스모크 · A24 대조 · 병행 검증 결과와 무관하게 블록 A 8 + 블록 N 8 = 16세션을 돈다 (등록 v2 #3 · #5).
2. **무조건 완주 (04:14)**: 폰 마감 적용 안 함 · 블록 사이 충전 없음 (`CHARGE NEEDED` 때만) · 연결 끊김은 재연결 반복 · 안전 비상만 그 세션 `stopped`. 측정을 그만두는 결정은 영훈만 한다.
3. 결과 지위 = **S26 부록 관측** (등록 v2 §3 — 조민규 확인 없음 + 병행 검증 실패여도 실행). v1 결과 (R2 · 겹침 0 · 16 미실행) 는 보존.

## 0단계 (2026-10-09 04:1x ~ 04:2x KST) [P] — 상세 `results\S26_MIXREQ_1009v2\r3_preflight.txt` (git 밖)

- git: HEAD `03f271a` = origin · 트리 clean · R2 드라이버 · 감시 · keepawake 프로세스 0 (유휴 셸뿐)
- 등록 v2 OneDrive SHA-256 `8e8e1104ff3591098b7aba22bd42a1494eaeafed8ff6aaf63e638070a20806f0` ✔ (6,532 B · LF) · 레포 v1 `edf9e594…` ✔
- git 밖 입력 7/7 SHA 일치 · `a24_handoff_1008` manifest `d93e0978…` ✔ · v1 APK 사본 `fb240791…` ✔ · 디스크 C 17 GB
- 폰 (읽기만): SM-S942N 하나 · SOC **80** · plugged 0 (04:11 ~ 04:17 짧은 AC 충전 73 → 80 뒤 빠짐 — 영훈 진술 "75 · 케이블 빠짐" 과 다름, 기록만) · 밝기 모드 0 · 밝기 **1** · `screen_off_timeout` 600000 · 비행기 1 · zen 1 · HAL AP 28.5 · BAT 28.3 · SKIN 30.0 · status 0 · 잠금 해제 · request-runner v1 `fb240791…` 설치 · npu-runner `5ac485e3…` 그대로
- **원복 값 (3부)**: 밝기 127 (R2 0단계 원래값 — 04:2x 실측 1 은 R2 뒤 바뀐 값) · `screen_off_timeout` 600000

## 1-1. 등록 v2 커밋 ① [P]

- `d1sim/docs/혼합요청_사전등록_v2.md` ← OneDrive 바이트 그대로 (SHA `8e8e1104…` · `git show HEAD:…` 도 `8e8e1104…`)
- 커밋 ① = `672bb3f68a8f8ece2483c37bfcaa824264c49c49` (2026-10-09 04:24:55 +0900) "d1sim: 혼합 요청 사전 등록 v2 — 간격 200 ms · 본측정 무조건 (v2 블록 전)" · PAT 0 · 바이너리 0
- K1 (uuid5, v2 네임스페이스): `S26-MIXREQ-02/0` sid = `25a97307-6261-5c0a-b608-fa7a0566bca3` · `/1` `57796f65-279c-5995-8a6a-e3291f80177a` · `/8` `c4fe0a73-7aca-5684-9b06-67cc120373b1` · `/15` `7b3badf4-aae4-5011-84f8-64e34692e10e` · 스모크 `S26-MIXREQ-02-SMOKE/0` `f6d1ec00-ce61-52a4-a14b-a4face78e590` (Python `uuid.uuid5(NAMESPACE_URL, …)`, 04:2x)

## 1-2. 코드 v2 (등록 v2 #1 · #2 · #4 · #5 · #6 · #9 만) — R3 가 결과 전에 정함

1. **readout 판정 꼬리표 우선순위** (한 블록에 여러 꼬리표가 동시에 해당할 때 `judgment` 에 쓰는 이름): ① "이식 대조 FAIL — 기술만" (v2 #5, Q1 · Q2 · Q3 전부) > ② "NPU 출력 계약 실패 — 기술만" (v1 §6 Q3 ①) > ③ "병행 겹침 없음 — 기술만" (v2 #3) > ④ "쌍 부족 — 기술만" (v1 §6) > ⑤ 방향 판정. 해당하는 꼬리표는 전부 `tags` 에 남긴다. 근거: 더 바깥 조건 (이식 · 계약) 이 안쪽 (겹침 · 쌍 수) 보다 먼저 결과의 지위를 정한다.
2. **v2 판별** = manifest/plan `experiment_id` 가 `S26-MIXREQ-02` 또는 `S26-MIXREQ-02-SMOKE` (`mixreq_common.registration_version`) → 규칙 5 · 스모크 decisions · readout 꼬리표가 v2 분기. v1 ID 는 v1 규칙 그대로 (R2 산출물 재검증 결과 불변).
3. **드라이버 v2**: 같은 자리 두 번째 무효 → `invalid_twice` 기록 · 다음 index · rc 5 (시도 폴더 잔존) 도 시도 1 이면 재시도 경로 · 연결 문제 = rc 2 · 3 · 4 (게이트 스크립트 실패 · 기기/adb · 멈춤) 가 한 자리의 최종 결과인 자리가 **연속 3** → `CONNECTION x3` 멈춤 → 재연결 뒤 `-StartIndex` · 설정 불일치 허용 기본 켬 (`-StrictSettings` 로만 끔) · `CHARGE NEEDED` (rc 6) 는 그 자리에서 멈춤 (충전 → `-StartIndex`).
4. plan v2 의 `registration` = v2 (파일 · SHA · 커밋 ① · 시각) · `registration_v1` 에 v1 을 같이 둔다 (inventory `registration_commit` 은 v2 커밋).

## 1-2 ~ 1-4. 코드 v2 · 시험 · 빌드 · 계획 v2 (04:2x ~ 04:4x) [P]

- 바뀐 파일 (그 밖 변경 0 · `git diff --stat 03f271a -- npu-runner benchmark-runner app telemetry-contract tools gradle` 빈 diff ✔):
  - 앱 `request-runner/src/main/java/MixreqContract.kt`: `STEP_MS` 400 → **200** · `EXPERIMENT_ID` `S26-MIXREQ-02` · `SMOKE_EXPERIMENT_ID` `S26-MIXREQ-02-SMOKE` · 머리 주석 한 줄 (기존 주석 · docstring 무변경) · `src/test/java/RequestPlanTest.kt` K1 기대값 = v2 sid · request_id (Python uuid5) · 오프셋 35,000 + 200·i (끝 73,200 · 스모크 끝 39,600) · v1 sid 는 "그대로" 로 함께 확인
  - 호스트 `mixreq_common.py`: 같은 상수 셋 + `registration_version()` (v2 = `-02` / `-02-SMOKE` · v1 = `-01*` · 그 밖 오류) + 등록 v2 (파일 · SHA · 커밋 ① · 시각) · v1 은 `REGISTRATION_V1_*` 로 보존 · `mixreq_plan.py`: 하드코딩 없음 (상수 따라감) · plan/manifest `registration` = v2 · `registration_v1` · `registration_version` · `step_ms`
  - `mixreq_validate.py` 규칙 5: v2 → CPU 겹침 0 만 유효 조건 · PAR / PAR-NPU 는 `overlap_s` · `overlap_zero` 기록 (foreign lane 은 여전히 실패) · v1 ID 는 v1 규칙 그대로 · `validated.json` 에 `registration_version`
  - `mixreq_smoke.py`: `record_decision()` — v1 = `decisions` · v2 = `observations` 에 "기록만 — 실행 차단 아님 (등록 v2 #3 · #5)" · `v2_note`
  - `mixreq_driver.ps1` (ASCII + CRLF 139줄): 기본 plan_v2 · results `S26_MIXREQ_1009v2` · 두 번째 무효 → `invalid_twice` 기록 · 다음 index · 연결 문제 (rc 2 · 3 · 4) 가 앱 시작 전이면 시도 소모 없이 폴더 옆으로 (`_pre<attempt>_<HHmmss>`) · adb 1 분마다 disconnect/connect 최대 600 s · 연속 3회 → `CONNECTION x3` 멈춤 · 설정 불일치 허용 기본 켬 (`-StrictSettings` 로 끔) · rc 5 = 시도 소모 → 다음 attempt · rc 6 = `CHARGE NEEDED` 멈춤
  - `mixreq_readout.py`: `--a24-compare <json>` (FAIL → Q1 · Q2 · Q3 "이식 대조 FAIL — 기술만") · 꼬리표 `tags` + 우선순위 (원장 1-2 ①) · v2 유효 PAR / PAR-NPU 중 겹침 0 → "병행 겹침 없음 — 기술만" · Q2 표 이름 v2 "간격이 다른 이식 (S26 200 ms · A24 400 ms) — 나란히 기술만" + 같은 정의 한 줄 (v1 스모크 24요청 · 겹침 0) · notes 에 결론 접미 "도착 간격 200 ms (A24 400 ms 의 절반 · v1 스모크 뒤 설계)" · `slots` (valid / invalid_twice / invalid_once / not_attempted) · inventory `reason` 에 `slot=…`
  - `test_mixreq.py` (+5) · `e2e_selftest.py` (v2 겹침 0 PAR · v1 ID 회귀 · a24 FAIL · Q2 이름)
- 시험 [P] (전부 기대대로):
  - K1 ~ K6 `gradlew :request-runner:testDebugUnitTest --offline --rerun-tasks` → **32 / 32** (RequestPlan 4 · PolicyStudy 4 · ImageContract 5 · Decoders 6 · EventLog 5 · SessionRoundTrip 8, 127 s) — K6 round-trip 산출물이 v2 ID · 200 ms 로 재생성됨
  - `py -3 -m pytest s26/tools/mixreq` → **34 passed** (29 + v2 5: 규칙 5 v2/v1 · 스모크 기록만 · readout 꼬리표 2종 · slot · 드라이버 dry-run 8세션)
  - `py -3 -X utf8 s26/tools/mixreq/e2e_selftest.py` → **E2E PASS** (6 사례 + 음성 5 + v2: 겹침 0 PAR = 유효 · overlap_s 0 / 같은 산출물 v1 ID = `5_overlap` FAIL / readout 블록 A "병행 겹침 없음 — 기술만" (n 1) / a24 FAIL → A · N · Q2 전부 "이식 대조 FAIL — 기술만" / Q2 이름 v2). ※ `-X utf8` 없이는 마지막 print 가 cp949 로 깨진다 (기능 아님)
  - **v1 회귀**: R2 `_r4` S2 세 세션을 새 검증기로 다시 → CPU 유효 · PAR `5_overlap` · PAR-NPU `5_overlap` (R2 와 같음 · `registration_version` 1) ✔ · R2 readout 을 plan_v1 로 다시 → 판정 · inventory 17줄 바이트 동일 ✔
  - 회귀: `:npu-runner:testDebugUnitTest` **61 / 61** · `py -m pytest tools` 220 passed · 23 skipped · 1 failed (CRLF `test_d1_representative_tensors` — 기준과 같은 1건; 수집 244 = 기준 243+1) · `d1sim/tests` **93 passed**
- 빌드 [P]: `gradlew :request-runner:assembleDebug --offline` → `request-runner-debug.apk` **14,439,200 B · SHA-256 `591cae72886aebe6a051d7b0fe311aa38b8127e21ba0b519851b7784229d986d`** (04:38) · 안에 모델 0 · `lib/arm64-v8a/libLiteRtDispatch_Samsung.so` 559,960 B · 사본 `local_inputs\apk\request-runner-debug_v2.apk` (커밋 안 함)
- 계획 v2 [P]: `s26/results/mixreq_1008/plan_v2/` plan.json SHA-256 **`cdf627325f6bcb92d8231c6d8e717eef5fc726a0d0b9848139348b9b8218c77a`** · 16 manifest + 스모크 4 · 두 번 생성 바이트 동일 · 호출 3,216 / 스모크 108 · 오프셋 35,000 ~ 73,200 ms (스모크 39,600) · `device_inputs.json` = v1 과 바이트 동일 ✔ · 입력 인자 = v1 과 같음
- dry-run [P]: 드라이버 `-DryRun -SkipGate` (pytest 안, 임시 results) 8세션 completed · 스모크 `--dry-run --skip-gate --allow-settings-mismatch` S1 + S2 ×3 rc 0 · `decisions` [] · `v2_note` 있음
