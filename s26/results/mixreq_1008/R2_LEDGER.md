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
