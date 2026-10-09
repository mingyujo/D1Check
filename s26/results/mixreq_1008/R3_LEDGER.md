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

## 1-5. 커밋 ② · push (04:40) [P]

- 커밋 ② = `e2bedf1e8441cd991da6fa2d0d6dbe52c79c1e58` (2026-10-09 04:40:19 +0900) "request-runner · s26/tools/mixreq: v2 (간격 200 ms · 규칙 5 · 무조건 실행) + 계획 v2 (v2 블록 전)" — 34 파일 (+522 / −76: 코드 10 · plan_v2 23 · 원장 1) · patch · 메시지 PAT 0 · 바이너리 0 · logcat 0
- **push `03f271a..e2bedf1 s26-mixreq -> s26-mixreq`** · origin = HEAD · 트리 clean (local_inputs · results 는 git 밖)

## 2-1. 폰 준비 (04:40 ~ 04:41) [P]

- plugged 0 ✔ · `settings put system screen_off_timeout 86400000` · `screen_brightness_mode 0` · `screen_brightness 0` (15 s 뒤에도 0 — 화면이 꺼져 있어서; Awake 면 1 로 되돌아간다, R2 §7)
- `adb install -r local_inputs\apk\request-runner-debug_v2.apk` → Success · 기기 `pm path` sha256sum = **`591cae72…`** ✔ (= 1-4 빌드) · npu-runner `5ac485e3…` 그대로 ✔
- **화면 꺼짐 · 잠금 (04:41)**: `mAwake=false` · `isKeyguardShowing=true` — 0단계 (04:2x) 에는 켜져 있었음; 원래 `screen_off_timeout` 600000 (10 분) 이 86400000 을 넣기 전에 만료. PIN 이라 스크립트가 못 푼다 → 영훈에게 "잠금 풀어 주세요" 한 줄 · 풀릴 때까지 30 s 폴링 (스모크는 그 뒤)
- 04:41 ~ 05:3x 잠금 대기 (30 s 폴링 · 2 분마다 KEYCODE_WAKEUP) — 풀리지 않음 · SOC 80 → 77 · adb 연결 유지. 영훈 호출 5회 (채팅).
- 05:3x adb 끊김: `device not found` → disconnect/connect 실패 (10060 응답 없음) · PC Wi-Fi 같은 망 유지 (주소 대역 같음 — 원장에는 <IP:PORT>) → 1 분마다 connect + `adb mdns services` 로 포트 탐색 · 영훈에게 잠금 해제 + 무선 디버깅 주소 한 줄.
- 05:4x ~ 06:3x adb 재연결 반복 (1 분마다 connect · mDNS 는 같은 주소 캐시 · ping 무응답 · PC Wi-Fi 같은 망) — 미복구. 영훈 호출 (잠금 해제 + 주소) 채팅 5회. 그동안 보고서 뼈대 (`작업결과_1009_R3_혼합요청v2.md` §3 · §4 · §10) · 결과 문서 뼈대 (`sim\혼합요청_결과_v2.md` §0 · §1) 작성 — 결과 절은 비워 둠.
- 06:4x ~ 07:4x adb 재연결 반복 계속 — 미복구 (connect 10060 · mDNS 캐시 같은 주소). 영훈 호출 채팅 매 8 분. 폰 측 원인 미확인 (잠금 뒤 Wi-Fi 절전 또는 폰 이동 [E]).
- 07:4x ~ 08:4x adb 재연결 반복 계속 — 미복구 (3 시간째). 영훈 호출 채팅 매 8 분 계속.
- **17:4x 복구 [P]** (PC 시계 — 앞 줄의 '09:3x' 추정은 틀렸다, 마지막 폴링 09:34 뒤 영훈 답이 17:4x 에 왔다): 영훈 (17:4x 채팅) "화면 잠금을 처음에 안 걸었어?" → 답: 0단계엔 풀려 있었고 원래 10 분 타임아웃이 1부 중 만료돼 잠김 (운영 사고 — 0단계에서 86400000 을 넣었어야 했다) · 영훈이 새 무선 디버깅 주소 (학교망 172.30.x 대역 → 원장 `<IP:PORT>`) 를 줌 — 준 포트는 끝 두 자리가 달라 거부 (10061), `adb mdns services` 로 실제 포트 확인 → connect 성공 · PC 도 같은 망 (172.30.x). 폰: 잠금 해제 · `screen_off_timeout` 86400000 유지 · 밝기 1 · 비행기 1 · zen 1 · **SOC 88** (다시 충전됨) · BAT 31.3 · HAL AP 32.3 · BAT 30.9 · SKIN 32.8 (게이트 상한 초과 → 첫 세션 게이트가 냉각 대기) · request-runner v2 설치본 유지 (확인은 세션 스크립트가 다시).
- 잠금 · 끊김 대기 합계 04:41 ~ 17:45 (약 13 시간; adb 끊김 05:3x ~ 17:4x · 재연결 폴링은 09:34 까지, 그 뒤 영훈 답 대기) · 세션 시작 0 · 측정 코드 변경 0. 스모크 v2 시작 **17:45:39** (pid 기록 `results\S26_MIXREQ_SMOKE_1009v2\smoke_pid.txt`).

## 2-2. 스모크 v2 · A24 대조 (17:45:39 ~ 18:04:26, `results\S26_MIXREQ_SMOKE_1009v2`, `--allow-settings-mismatch`) [P] — 기록만 (등록 v2 #3 · #5)

- S1 (`S1_warmup_only_blockN`, sid `f1edca70-…`) 17:45:40 ~ 17:48:01: 게이트 첫 판 FAIL (SKIN 32.4 · AP 31.5 · BAT 30.4) → 120 s 뒤 PASS (31.2 · 30.0 · 29.2 · SOC 88 · plugged False) · 기기 APK `591cae72…` ✔ · 5 runtime 생성 · warmup 10 · 텐서 `603328d0…` ✔ · RGB `ca6c2e2b…` ✔ · CPU top-5 = PC 참조 ✔ · 탐지 CPU = PC 참조 (A24 허용) ✔ · GPU vs CPU §4-6 분류 · 탐지 ✔ · `detection_GPU` 생성 ✔ · GPU 증거 PASS (분류 · 탐지) · NPU 증거 FAIL = `no_dispatch_failure_in_common_window` 하나 (warmup_only 에 공통창 없음 — R2 와 같은 검증기 한계, 기록만) · **NPU 계약 첫 값 PASS**: top-1 518 = CPU · cosine 0.9999935 · 최대 |Δ| 9.3e-4 · FP32 허용식 위반 4 · 비트 동일 아님 (2회 같음; R2 v1 APK 와 같은 값) · `top -H` 관측 행 0 (파서 한계 그대로)
- **A24 대조 (`mixreq_a24_compare.py` `c1e43ece…` 무변경 → `a24_compare.json`): verdict PASS** — 탐지 warmup 0 · 1 각각 vs A24 record0: 라벨 person · bicycle 같음 · |Δscore| 0.0 · box 차 8.6e-6 · 4.4e-5 px · 입력 텐서 == A24 ✔ · raw ≠ (엔진 다름, 기록만) / 분류 top-5 5/5 · |Δscore| ≤ 3.6e-7 · raw ≠ 참조 (기록만). → v2 #5 꼬리표 "이식 대조 FAIL" 해당 없음.
- S2 (`decisions` [] · `observations` [] — v2 는 기록만이지만 셋 다 (a)~(d) 통과):
  - `S2_CPU_URGENT_ONLINE_V1` (sid `f6d1ec00-…`) 17:48:04 ~ 17:53:23 rc 0 · 유효 · 겹침 0 (CPU 기대) · 게이트 30.7 · 29.4 · 28.6 · SOC 88
  - `S2_B2_PARALLEL_ONLINE_V1` (sid `ca4fc718-…`) 17:53:26 ~ 17:58:46 **rc 0 · 유효** · 24/24 · 배정 GPU/CPU ✔ · 증거 PASS · **겹침 0.435 s** (12 쌍 ≈ 36 ms 씩 [E 계산]) · 게이트 30.2 · 28.8 · 28.0
  - `S2_S26_NPU_PARALLEL_V1` (sid `6b009117-…`) 17:58:49 ~ 18:04:08 **rc 0 · 유효** · 24/24 · 배정 NPU/CPU ✔ · NPU 증거 PASS · **NPU 계약 PASS** (top-1 같음 · cosine 0.9999935 ×2) · **겹침 0.420 s** · 게이트 29.7 · 28.2 · 27.4 · SOC 87
  - 진단 (KPI 아님 — lane busy dispatch → lane_available, 24요청): 탐지 CPU 중앙 237 ~ 239 ms [231 ~ 250] · 분류 GPU 68.8 [63 ~ 84] · 분류 NPU 63.3 [57 ~ 74] · 분류 CPU (직렬 세션) 51.8 [50 ~ 78] — v1 스모크와 같은 크기. 200 ms 간격에서 탐지 CPU (≈ 238 ms) 가 다음 분류 도착을 넘겨 겹침이 생김 (등록 v2 §0 [E] 예상 ≈ 41 ms/쌍 과 같은 자리).
- 밝기 설정값 세션 중 1 (v2 #7 허용) · `screen_off_timeout` 86400000 유지 · 화면 켜짐 · 잠금 없음 · 재시도 0 · 비상 0.
- **첫 v2 블록 세션 시작 시각 = 18:05:11 (블록 A index 0)** — 조민규 등록 확인 없음 → 결과 지위 = S26 부록 관측 (등록 v2 §3) 확정.

## 2-3. 블록 A (`mixreq_driver.ps1 -Block A -PlanDir …\plan_v2 -ResultsRoot …\S26_MIXREQ_1009v2`, 18:05:11 ~) [P]

- 드라이버 pid 기록 `driver_pid_blockA.txt` · keepawake 시작 · index 0 (CPU) 게이트 즉시 PASS → 18:05:15 `am start` → warmup 게이트 ARM. (스모크 끝 18:04:08 → 첫 세션 18:05:15 = 67 s — 90 s 최소 간격 표식 `last_session_end.txt` 가 results root 별이라 스모크 → 블록 경계에는 걸리지 않았다. 등록 §4 유효성 규칙 아님 · 기록만.)
- 18:07 운영 메모: 블록 A 감시를 잠깐 `tail -F` 로 걸었다가 (규칙 위반) 1 분 안에 중단 · 고아 tail.exe 1개 종료 → 30 s 폴링 (`sed -n` 새 줄만) 으로 교체. 드라이버 · 세션 영향 0.
- **블록 A 끝 18:46:50 — 8/8 유효 (rc 0) · 재시도 0 · invalid_twice 0 · 연결 사고 0 · 비상 0 · 블록 안 충전 0** (index 0 CPU 18:05 → 7 PAR 18:46 · 세션당 약 5.4 분 · 게이트 대기 전부 0 s · SKIN 29.6 ~ 31.0 · SOC 87 → 82). KPI 는 readout 전까지 적지 않는다 (겹침 초는 유효성 기록으로만 validated.json 에 있음).
- **블록 N 시작 18:47** (충전 없이 바로 — 무조건 완주 절) · 같은 드라이버 `-Block N` · 같은 results root.
- **블록 N 끝 19:29:54 — 8/8 유효 (rc 0) · NPU 계약 8/8 PASS (CPU 세션 포함 계산) · 재시도 0 · invalid_twice 0 · 연결 사고 0 · 비상 0 · 블록 안 충전 0** (index 8 CPU 18:47 → 15 PAR-NPU 19:29 · 게이트 대기 전부 0 s · SKIN 30.7 ~ 30.8 · SOC 81 → 76). **16세션 전부 유효 · 2부 완료.**

## 3-1. 원복 (19:30 ~ 19:31) [P]

- 드라이버 N 종료 확인 · keepawake stop 19:30:39 · mixreq/watch 프로세스 0 · 앱 프로세스 없음 · `screen_off_timeout` → **600000** · `screen_brightness` → **127** (모드 0) · 비행기 1 · 방해 금지 1 켠 채 (다음 = Q20) · SOC 76 · BAT 28.9 · HAL AP 29.7 · BAT 28.8 · SKIN 31.0 · 화면 꺼짐 (잠금 없음) · 케이블 없음.

## 3-2. readout 한 번 (19:31) [P]

- `mixreq_readout.py --plan plan_v2/plan.json --results results\S26_MIXREQ_1009v2 --out …\readout --apk-sha256 591cae72… --source-commit e2bedf1e… --a24-compare results\S26_MIXREQ_SMOKE_1009v2\a24_compare.json` → rc 0 · 세션 16 · skipped 0 · slots valid 16 / invalid_twice 0 / not_attempted 0 · `a24_compare_fail` false.
- **Q1 (블록 A) = "병행이 긴급 응답을 줄였다" (4쌍) · Q3 (블록 N) = "NPU 병행이 긴급 응답을 줄였다" (4쌍) · tags 없음 (겹침 0 세션 0 · NPU 계약 실패 0 · 이식 대조 PASS)** · Q2 표 이름 "간격이 다른 이식 (S26 200 ms · A24 400 ms) — 나란히 기술만". 숫자 (쌍별 Δ · P95 · 열 · J) 는 보고서 · 결과 문서로 (readout 파일이 원본).

## 3-3. 결과 사본 · 문서 (19:3x ~ 19:5x) [P]

- 레포 사본: `R3_smoke/` (S1 + S2 ×3 · smoke_report · a24_compare · gate · stdout) · `R3_blocks/` (16세션 device + host (logcat 제외) + validated + npu_contract · 드라이버 로그 · state · gate · keepawake · r3_preflight) · `R3_readout/` (readout.json · inventory · metrics · files_inventory) — 6,727 파일 · 약 55 MB · PAT 0 · logcat 0.
- 문서: OneDrive `sim\혼합요청_결과_v2.md` (한계 · 반대 해석 먼저 · v1 결과 §0 보존 · 판정 · KPI 표 · Q2 표 · 결론 문장) · `작업결과_1009_R3_혼합요청v2.md` (1 ~ 14) → 사본 `R3_reports/` (커밋 ③ SHA 는 OneDrive 판 §14 에만).
