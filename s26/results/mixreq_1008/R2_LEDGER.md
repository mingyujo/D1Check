# R2 혼합 요청 측정 — 원장 (레포 사본, `D1_ondevice\sim\out_mixreq\freeze_mixreq.txt` 와 같은 내용)

> 작업 클론 `C:\Users\rhoyo\AndroidStudioProjects\D1Check_mixreq` · 브랜치 `s26-mixreq` · 시작 HEAD `2de4d59` = `origin/s26-mixreq`.
> 표기 [P] 실측 · [D] 인용 · [E] 추정 · `미확인`. 주소 · 시리얼은 `<IP:PORT>` · `<SERIAL>`. KPI (응답 · P95 · 겹침 초 · 열 Δ · J) 는 readout 전에 이 파일에 쓰지 않는다.

## Cowork 10/8 20:4x 결정 (영훈) — 결과 전 고정

1. 기준 자료 = **조민규 2차 zip `S26_mixreq_handoff_1008`** (PNG · anchors 원본 · A24 탐지 CPU warmup 2회 · host 분류 · 탐지 참조). R1 의 PC 참조 (`local_inputs\reference_pc\`) 는 보조 기록으로만.
2. **조민규의 등록 확인 없이 진행한다.** 등록 §9 그대로 — 첫 R2 세션 (블록 A index 0) 시작 시각까지 확인이 없으면 결과 지위 = "S26 부록 관측". 세션은 확인을 기다리지 않는다. XDEV-02 완료라고 쓰지 않는다.
3. 조민규 `02_scope_and_reporting.txt` 의 조건 중 등록에 없는 것 (NPU AOT 컴파일 설정 · 버전 연결 — 전체 컴파일 로그 `미확인` · cosine 의 0-norm · 비유한 처리 · top-1 동률 규칙) 은 **이번에 손대지 않는다** — 보고서 "남은 것" 에 한 줄씩.
4. `local_inputs\` · `local_models\` 상태는 영훈이 모른다 → 0단계에서 이 세션이 직접 SHA 로 확인한다 (결과: 아래 0단계).

## 0단계 (2026-10-08 20:4x KST) [P] — 상세 `results\S26_MIXREQ_1009\r2_preflight.txt` (git 밖)

- 영훈 답: ① 케이블 안 꽂음 (SOC 는 adb: 94 · 방전 중) ② 실내 약 24~27 ℃ ③ 마감 "10/10 오전 더 늦게" (구체 시각 미지정 — 06:00 넘기는 세션은 시작 전 원장에 적는다)
- git: HEAD `2de4d59` = `origin/s26-mixreq` · index.lock 없음 · 작업 트리 clean · 이 PC 에 드라이버 · 감시 · keepawake 프로세스 0 (유휴 powershell 셸 6개뿐)
- 등록 동결: `git show 20967fb:d1sim/docs/혼합요청_사전등록_v1.md` SHA-256 `edf9e594c66b695104698c52ded8ff5c869f70946ee886bc42364ef99c862e28` (34,452 B) ✔
- git 밖 입력 7개 (device_inputs.json host_path) 전부 존재 · bytes · SHA 일치 ✔ (PNG `3e8b925f…` · anchors `e095e869…` · 분류 `6c7ab0a6…` · 탐지 `40338edf…` · AOT `311e4aac…` · 라벨 `e697a491…` · `f8803ef7…`) · `reference_pc.json` 있음 ✔
- APK: `request-runner\build\outputs\apk\debug\` 없음 (R1 끝 build 삭제) → `local_inputs\apk\request-runner-debug_fb240791.apk` 14,439,196 B SHA-256 `fb2407911a5ee036b52e9bdb259d5e1bb1e8b16082ed9afad92eb576dd8fb230` ✔ — 이것을 설치 · 다시 빌드 안 함
- 디스크 C: 여유 18.2 GB ✔
- 테스트: `test_mixreq.py` 29 passed ✔ · `e2e_selftest.py` 첫 실행 FAIL (9) = round-trip 산출물 없음 (R1 끝 `request-runner\build` 삭제) → `gradlew :request-runner:testDebugUnitTest` (exit 0) 로 재생성 뒤 **E2E PASS** ✔ (측정 코드 변경 0 · APK 재빌드 아님 — 단위 시험 산출물만)
- 폰 (읽기만): 기기 하나 `<IP:PORT>` SM-S942N (무선, IPv4) · request-runner **미설치** · npu-runner 설치본 `5ac485e3…` 그대로 ✔ · 원래 값 brightness_mode 0 · **brightness 127** · screen_off_timeout 600000 · airplane 1 · wifi_on 2 · zen_mode 1 · 배터리 level 94 · status 3 · 27.3 ℃ · powered 전부 false · HAL AP 27.5 · BAT 27.2 · SKIN 29.3 · status 0 · /data 여유 64.5 GB
  - 원복 값 (이 세션): **밝기 127** (P1i 보고의 31 과 다름 — 0단계 실측이 기준) · screen_off_timeout 600000

## 1-1. 2차 zip 검증 · 복사 (20:5x) [P]

- `S26_mixreq_handoff_1008\` → `local_inputs\a24_handoff_1008\` (git 밖, ignored 확인) · `manifest.json` SHA-256 `d93e097811c7cd4d0b9be617cbab1d14750396f4113a593da8247292db762f70` (24 파일 · head a081d55e · `s26_registration_reviewed: false`)
- `py -3 -B -I verify_bundle.py` (폴더 안) → `PASS: file bytes/SHA, 192 requests, 19206x4 anchors, exact A24 warmup extraction; no device/inference` rc 0 · 독립 Get-FileHash 대조 24/24 일치
- **입력 PNG `3e8b925f…` (937,799 B) · anchors `e095e869…` (1,438,467 B) = 조민규 2차 zip 원본과 바이트 동일** = `device_inputs.json` 값 → 계획 · device_inputs 그대로. **"A24 와 다름: 입력 PNG 바이트" 아님.**
- 기록만 [D manifest.checks]: A24 탐지 CPU warmup (2회 같은 값) vs host 참조 차이 score ≤ 3.6e-7 · box ≤ 8.9e-5 px. 판정은 아래 도구가 S26 폰 출력으로.
- A24 탐지 CPU warmup 기준 (`a24_reference/detection_cpu_warmup.json` `da66b968…`): 세션 `fd107fbf-…` · records 2 (source_list_index 4 · 5) · person 0.69621015 [372.136, 24.473, 576.728, 321.459] · bicycle 0.55899900 [-11.355, 12.291, 495.527, 470.614] · 두 record 디코드 비트 동일 · raw SHA 같음 · input_tensor `e1ce665b…`
- host 분류 참조 (`host_classification_reference/reference.json` `c9ae61f2…`): `reference.results` top-5 = crash helmet 518 0.213422 · mountain bike 671 0.112495 · disk brake 535 0.057235 · tricycle 870 0.055073 · moped 665 0.054486 · raw `0df3d535…` (= R1 PC 참조와 같은 값 · 같은 raw SHA)

## 1-2. A24 대조 도구 `s26\tools\mixreq\mixreq_a24_compare.py` (20:5x ~ 21:0x) [P]

- 파일 SHA-256 `c1e43ecec4c7946e77e680b39682b550cae962e3dd31843959cd61a1984b0a81`
- S1 읽기 = `mixreq_validate.load_session` + warmup.json key/index/result (`mixreq_smoke.s1_checks` 와 같은 방법) · 비교 = `mixreq_validate.compare_detection` · `compare_classification` import (새 해석 0)
- ① 탐지 = S26 `detection_CPU` warmup 2회 각각 vs `records[0].result.results` (A24 허용 개수 · 순서 · 라벨 · |Δscore| ≤ 1e-3 · box ≤ 2 px) · 기록만 입력 텐서 `e1ce665b…` 일치 여부 · S26 raw SHA · records[1] 대조 · 두 record 동일 여부
- ② 분류 = S26 `classification_CPU` warmup 1회차 top-5 vs `reference.json` → `reference.results` (label · class_index · |Δscore| ≤ 1e-3) · 기록만 텐서 `603328d0…` · RGB `ca6c2e2b…` · raw == `0df3d535…`
- `--selftest` 15 사례 전부 기대대로 (A24 record 그대로 → PASS · score +2e-3 FAIL · +5e-4 PASS · box +3 px FAIL · +1.5 px PASS · 검출 +1/−1 FAIL · 라벨 FAIL · 순서 FAIL · 분류 순서 · score · index FAIL · 2회차만 다름 FAIL · warmup 부족 FAIL) → SELFTEST PASS
- 실제 2차 zip 파일 읽기 확인: PC round-trip (가짜 backend) 폴더에 돌려 FAIL (기대 — 가짜 출력) · 크래시 0 · handoff 메타 정상 읽힘
- `test_mixreq.py` 29 passed (변경 없음)
- 커밋 ① = (아래 줄에 커밋 뒤 추가)

- 커밋 ① = `3417f85ff845f40f322bdded17ea3fa811271ec2` (2026-10-08 20:52:38 +0900) · PAT 0 · 바이너리 0 · push 는 끝에

## 2-1. 설치 · 설정 (10/8 20:5x) [P]

- `adb install -r local_inputs\apk\request-runner-debug_fb240791.apk` → Success · 기기 `pm path` 경로 `sha256sum` = `fb2407911a5ee036b52e9bdb259d5e1bb1e8b16082ed9afad92eb576dd8fb230` ✔ · `settings put system screen_brightness 0` · 비행기 1 · zen_mode 1 · brightness_mode 0 확인

## 2-2. 스모크 첫 실행 (10/8 20:53:39 ~ 20:53:45) — 설정 검사 거부 [P]

- S1 · S2 ×3 전부 rc 3 `phone settings mismatch` — `settings_before.brightness = '1'` (스크립트는 `'0'` 만 통과). 기기 산출물 0 · host 로그만 (`results\S26_MIXREQ_SMOKE_1009\`, 보존 — 다시 하는 스모크는 `_r2`).
- 원인 [P 20:5x ~ 21:0x]: **S26 은 화면이 Awake 면 `screen_brightness` 0 을 5 ~ 15 s 안에 1 로 되돌린다** (Dozing 이면 0 유지 · t+0 · t+1 · t+5 = 0 → t+15 = 1). `dumpsys display mScreenBrightness=0.0` — 0 이든 1 이든 **표시 밝기 float 는 같은 최소값**. 에너지 C 보고의 "03:37 에 1 로 바뀌어 있었음 (원인 미상)" 과 같은 현상 → 에너지 C 도 실제로는 1 이었을 가능성 [E].
- **영훈 결정 (10/9 00:4x)**: 스모크 · 드라이버에 `--allow-settings-mismatch` 를 전달한다 — `mixreq_smoke.py` 에 `--allow-settings-mismatch` 인자 (pass-through) · `mixreq_driver.ps1` 에 `-AllowSettingsMismatch` 스위치 추가 (운영 스크립트 · 측정 코드 `mixreq_session.py` · 앱 · `mixreq_validate.py` · `mixreq_readout.py` · `plan_v1` 수정 0). 세션마다 `host\session_log.json` `settings_before` 에 실제 값이 남는다. 보고서 · 결과 문서에 **"등록 §3-5 와 다름 — 밝기 설정값 1 (폰이 0 → 1 되돌림 · 표시 float 0.0 = 최소 · A24 81)"**.
- 잠금화면: `isKeyguardShowing=true` (PIN — `wm dismiss-keyguard` 불가) → 영훈이 직접 해제 (00:43 `isKeyguardShowing=false` · 전면 런처 · Awake). 측정 중 잠금 해제 유지 필요 (화면 꺼짐은 스크립트의 86400000).

## 2-2. 스모크 재실행 (10/9 00:45:21 ~, `results\S26_MIXREQ_SMOKE_1009_r2`, `--allow-settings-mismatch`) [P]

- S1 (`S1_warmup_only_blockN`, sid `962ea966-…`) 00:45:22 ~ 00:45:53: 게이트 rc 0 (SKIN 28.9 · AP 27.0 · BAT 26.8 · status 0 · SOC 83 · plugged False) · `settings_before` brightness `'1'` (기록) · 입력 7개 push + SHA 확인 · `am start` rc 0 · observe done · 산출물 pull (warmup.json 45,865 B · progress.jsonl · summary.json) · `validated.json` eligible False (warmup_only 라 요청 규칙이 FAIL — 설계대로 · 판정에 안 씀) · `npu_contract.json` passed True (첫 값 — 기록만 · 숫자는 smoke_report 에서)
- S2 세 정책: (아래 smoke_report 뒤 추가)

## 2-3. A24 대조 (10/9 00:4x, `mixreq_a24_compare.py` `c1e43ece…` → `results\S26_MIXREQ_SMOKE_1009_r2\a24_compare.json`) [P]

- **verdict PASS** (`a24_detection` PASS · `classification` PASS) → R2 진행 조건 충족 (등록 §11-1 ①②)
- ① 탐지: S26 `detection_CPU` warmup 0 · 1 각각 vs A24 `records[0]` — 개수 2 · 라벨 person · bicycle 같음 · |Δscore| **0.0 · 0.0** · box 최대 차 **8.6e-6 · 4.4e-5 px** (허용 1e-3 · 2 px) · 입력 텐서 SHA == A24 `e1ce665b…` ✔ · S26 raw SHA ≠ A24 raw (엔진 다름 · 기록만) · 두 A24 record 디코드 비트 동일
- ② 분류: S26 `classification_CPU` warmup 0 top-5 vs host 참조 `reference.results` — label · index 5/5 같음 · |Δscore| ≤ **3.6e-7** (허용 1e-3) · 입력 텐서 `603328d0…` ✔ · 디코드 RGB `ca6c2e2b…` ✔ (S26 폰 BitmapFactory 에서 처음 확인) · raw 출력 SHA ≠ host 참조 `0df3d535…` (기록만 — 비트 동일은 요구 아님)
- S2 (00:45:53 ~ 00:58:28, `smoke_report.json` `decisions` = ["블록 A 미실행 — PAR 병행 검증 실패 (등록 §3-3)", "블록 N 미실행 — PAR-NPU 병행 검증 실패 (등록 §3-3)"]):
  - `S2_CPU_URGENT_ONLINE_V1` rc 0 · 짧은 판 유효 · (a)~(d) 전부 통과 (겹침 0 = CPU 기대값)
  - `S2_B2_PARALLEL_ONLINE_V1` rc 1 · 유효성 실패 사유 `5_overlap` 하나 (`overlap_ns_raw 0` · foreign_lane_rows 0) · (a) (c) (d) 통과 · **(b) 겹침 > 0 실패**. 진단 [P, KPI 아님 — lane busy 구간 (dispatch → lane_available) 만]: 분류 GPU lane ≈ 70 ~ 80 ms · 탐지 CPU lane ≈ 240 ~ 250 ms · 도착 간격 400 ms → 두 lane 이 동시에 바쁜 순간이 구조적으로 없다 (어느 lane 도 400 ms 를 넘지 않는다). 이식 오류가 아니라 **S26 이 A24 요청 정의 (400 ms 교대 도착) 에서 포화되지 않는 것** [E 해석 — A24 는 긴급 P95 CPU 422 ms 로 겹침 22 s].
  - `S2_S26_NPU_PARALLEL_V1` rc 1 · 기기 산출물 없음 — 앱이 `runtime_setup` 에서 3 s 만에 `stopped: environment/screen_off` (`session_failure.json` · `cleanup.json` · logcat D1MIX `session_failed`). **원인 = 운영**: 앞 세션 (PAR) 끝 00:56:34 에 스크립트가 `screen_off_timeout` 을 600000 (10 분) 으로 원복 → 마지막 사용자 입력 (00:43 잠금 해제) 뒤 10 분이 이미 지나 화면이 바로 꺼지고 잠금 (Dozing · keyguard) → 00:58:07 `am start` 때 `interactive != true`. S1 · S2 CPU · PAR 은 10 분 창 안이라 살았다 (00:53 경계). 연결 · 측정 코드 문제 아님.
  - S1 `evidence_classification_NPU` false = 조건 `no_dispatch_failure_in_common_window` 가 `common_window_lines null` (warmup_only 에는 공통창이 없다) 로 false — 검증기의 warmup_only 한계 (기록만). 나머지 조건 전부 true: DispatchDelegate 1/1 = AOT 표 (dispatch 1 · non 0) · ENN 로드 줄 (`SetGenAiPerfConfigFromSoc`) 러너 PID · NPU 구간 실패 줄 0 · 다른 delegate 교체 0.
  - S1 기록: 5 runtime 생성 (CPU · GPU · NPU · detCPU · detGPU 전부 ok, 00:45:32.58 ~ 33.96) · warmup 10 · `detection_GPU` 생성 **됨** (LITERT_CL 263/263) · classification_GPU LITERT_CL 62/62 · GPU vs CPU §4-6 통과 (분류 · 탐지) · 텐서 · RGB SHA ✔ · NPU 계약 첫 값 (기록만): top-1 518 = CPU · cosine 0.9999935 · top-5 순서 같음 · 최대 |Δ| 9.3e-4 · FP32 허용식 위반 4 · 비트 동일 아님 · passed true (2회 같음) · `top -H` 관측 행 0 (host `top_h.txt` 3,990 B — 파서가 행을 못 셈 · "설정 1 / 관측 `미확인`")
- **운영 조치 (01:0x)**: `screen_off_timeout` 을 R2 내내 86400000 으로 둔다 (세션 스크립트는 세션 시작 값을 읽어 끝에 그 값으로 "원복" 하므로 86400000 이 유지된다) · R2 끝에 0단계 값 600000 으로 되돌린다 · 폰 잠금 해제는 영훈. 스모크 S2 만 한 번 더 (`--only S2`, 새 폴더 `_r3`) — PAR-NPU 는 운영 원인 (화면 꺼짐) 이라 재시도 · PAR 은 같은 자리에서 한 번 더 관측.
- 03:11 adb `device not found` 1회 → `adb disconnect` → `adb connect` (같은 주소) 복구. S2 재실행 1차 (`_r3`, 03:11:39) 는 세 세션 전부 **rc 5** — 스모크 sid 가 고정 (`S26-MIXREQ-01-SMOKE/<index>`) 이라 기기 산출물 폴더 `<sid>/a1` 이 `_r2` 실행에서 남아 있어 거부 (호스트 폴더만 새로 만든 것으로는 부족). 조치: `_r2` 호스트 사본 파일 수 (57 · 57 · 4) = 기기 파일 수 확인 뒤 **기기의 S2 스모크 폴더 3개만** (`files/mixreq/<sid>` · `sessions/<sid>`) 삭제 (S1 `962ea966…` 은 유지) → S2 재실행 2차 `_r4` 03:13:00 시작 (`--only S2 --allow-settings-mismatch`). `_r3` 폴더는 거부 기록 (session_log 만) 으로 보존.
- **S2 재실행 2차 (`_r4`, 03:13:00 ~ 03:27:44) [P]** — `decisions` = ["블록 A 미실행 — PAR 병행 검증 실패 (등록 §3-3)", "블록 N 미실행 — PAR-NPU 병행 검증 실패 (등록 §3-3)"] (두 번째도 같은 사유 → 멈춤 · 보고)
  - `S2_CPU` rc 0 · 짧은 판 유효 · (a)~(d) 통과 (게이트 SKIN 28.4 · AP 26.5 · BAT 26.1 · SOC 76)
  - `S2_PAR` rc 1 · 24/24 succeeded · 자원 배정 GPU/CPU ✔ · 위임 증거 PASS (classification_GPU LITERT_CL 62/62 · detection_GPU 263/263) · `detection_GPU` 생성 ✔ · **겹침 0** (`overlap_ns_raw 0`) → (b) 실패 (게이트 SKIN 29.1 · SOC 76)
  - `S2_PAR-NPU` rc 1 · 24/24 succeeded · 배정 NPU/CPU ✔ · 위임 증거 PASS (classification_NPU DispatchDelegate 1/1 = AOT 표 · ENN 로드 · 실패 줄 0) · **NPU 계약 PASS** (warmup 0 · 1: top-1 518 = CPU · cosine 0.9999935 · 최대 |Δ| 9.3e-4) · **겹침 0** → (b) 실패 (게이트 SKIN 29.5 · SOC 75). 화면 꺼짐 문제는 재발 없음 (86400000 유지).
  - 진단 (KPI 아님 — lane busy 구간 dispatch → lane_available, 24요청 스모크): 탐지 CPU 233 ~ 247 ms · 분류 GPU 65 ~ 87 ms · 분류 NPU 58 ~ 82 ms · CPU 직렬 세션 분류 CPU ≈ 60 ms. 어느 lane 도 도착 간격 400 ms 를 넘지 않아 두 lane 이 동시에 바쁜 순간이 없다. **이식 오류가 아니라 A24 요청 정의 (192 · 400 ms 교대) 가 S26 에서는 포화 부하가 아님** [P 스모크 2회 일관 · E 해석]. 겹침을 만들려면 부하 (간격 · 요청 수 · 모델) 를 바꿔야 하고 그것은 새 등록 판 (조민규 02_scope §1 "부하를 바꾸면 새 버전").
- **R2 결론 (등록 §3-3 · §11-3 그대로)**: 블록 A · 블록 N 모두 **미실행 — 병행 검증 실패 (b)** · 본 세션 0 · inventory 16행 `not_attempted` · 판정 (Q1 · Q3) 없음 · KPI 없음. 조민규 등록 확인: R2 첫 세션이 없으므로 "본문/부록" 지위 판단 대상 결과가 없다 (스모크 결과는 등록상 판정 밖 · 진단).
- 원복 (03:28): brightness 127 (0단계 값) · screen_off_timeout 600000 · 비행기 1 · 방해 금지 1 유지 · 앱 프로세스 없음 · keepawake 28484 stop (20:53:40 ~ 03:28:45) · 감시 프로세스 0 · 폰 SOC 75 · 케이블 없음.

## 4부. readout · 보고 (10/9 03:3x ~ 03:4x) [P]

- 커밋 ② = `280d7639a444ee4eaf56b6a168c8243140278e7f` (03:30:51) "s26: 혼합 요청 R2 스모크 S1 · S2 (A24 대조 PASS · 병행 검증 실패 → 두 블록 미실행)" — `R2_smoke/` 404 파일 2.9 MB (logcat 제외 · PAT 0 · 바이너리 0) · smoke/driver 플래그 pass-through.
- readout 1회 (`--source-commit 280d763…` · `--apk-sha256 fb240791…`) → 세션 0 · 블록 A "쌍 부족 — 기술만" · 블록 N "유효 PAR-NPU 세션 없음 — 기술만" · inventory 16행 `not_attempted` · `R2_readout/` 사본 (PAT 0).
- 결과 문서 `D1_ondevice\sim\혼합요청_결과_v1.md` · 보고서 `D1_ondevice\작업결과_1008_R2_혼합요청.md` → 사본 `R2_reports/` (커밋 ③ SHA 는 OneDrive 판에만 §13 으로 추가 — 사본은 커밋 직전 판).
- 판정 4줄: Q1 미실행 (병행 검증 (b) 겹침 0) · Q3 미실행 (같음) · 결과 지위 = 판정 대상 없음 (조민규 확인 없음 → 있었다면 부록 관측) · 무효/재시도 = 본 세션 0 / 0 (스모크 재실행 3회는 운영 사유).
