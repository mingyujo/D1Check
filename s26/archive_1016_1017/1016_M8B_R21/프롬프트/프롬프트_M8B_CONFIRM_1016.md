# 프롬프트 M8-B — CONFIRM 5블록 (95세션) · 동결 v2 → CONFIRM 판 드라이버 → C1 ~ C5 연속 (영훈 10/15 23:2x 지시: 기다리지 말고 끝까지)

**작업 클론 = `C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6` · 브랜치 `s26-m8` · HEAD `ac6dde94a` 이상 · 원장 `D1_ondevice\sim\out_m8\prep_ledger.txt` 이어서 append.**
**APK = 설치본 v2 `37960e25c5948f661f2f5b47a90a4356be1b3712706d34679e71a14842ced6ea` — 재설치 금지 · 앱 변경 0.**
**정본**: 조민규 답 전부 (`조민규_답_1014_*` · `1014c` · `1015_계약값` · `1015b` · `1015c` · 21:xx · 22:xx 정정) · 등록 v2 ~ v5 · 동결 v1 `CONFIRM_FREEZE_S26_1016.json` (`deedfc1be65354a0ef05ffacb07cefe7e939e6cc0a53d560493e5632eeb4023f`) · `작업결과_1015_M8_DEV.md` §6 · §8 · 추가지시 1 ~ 4.

## 왜 기다리지 않는가 (DEV 보고 §8 "조민규 부족 항목 답 뒤" 를 바꾼다)

- 조민규 14일 22:1x: "CONFIRM 도 실측 범위 · 후보 · 설정 · 지표 · 분석 기준과 SHA 를 동결한 뒤 진행 · **실측 허가를 다시 받으라는 뜻 아님** · 우리 쪽 자료가 부족하면 항목을 알려 주고 **다른 진행 가능한 작업은 계속**".
- 15일 01:5x #8 · 10:0x #8: 그의 **사전 수치예측 · 허용치 · ATC/PPO 인계물은 없다 → 채우지 말고 고정 처방 실측은 계속** · 사후 비교를 예측 검증이라 부르지 않음.
- 15일 10:0x #8 · 19:3x 끝: "CONFIRM 전에 비교쌍 · 분모 · 서비스 70~100 · E0~180 · AP35~180 · peak · 180 잔열 · 납기손해 · 미완료 · **블록 단위 신뢰구간 · 선정/다중 비교 규칙을 파일로 봉인해 줘** · … · 이후 CONFIRM 도 파일/입력/비교쌍/분모/**추정식**과 새 계약을 먼저 고정해서 이어가 줘".
- → **CI 방법 · 다중 비교 규칙은 그가 우리에게 봉인하라고 한 것** (동결 v1 이 `missing_from_partner` 로 둔 것은 분류 오류). 이쪽에서 정해 v2 로 봉인하고 진행. 그의 몫으로 남는 것은 **수치 예측 · 허용치 · ATC/PPO** 뿐이고, 그건 CONFIRM 측정을 막지 않는다 (측정 · 자료는 같고 판정만 그 값이 올 때 붙음).

## 영훈이 할 일

- 폰 충전 (지금 SOC 22) → 세션이 "케이블 뽑으세요" 하면 뽑기. 무선 디버깅 IP:PORT = `________________` (PC 와 폰 같은 Wi-Fi · 개발자 옵션 무선 디버깅 켜 둔 채).
- 폰 · PC 그 자리 (덮개 열림 · 절전 끔 · Wi-Fi 자동 전환 끔). 잠금 해제 요청이 오면 풀어 준다.
- 블록 묶음 · 동결 v2 · 드라이버 SHA 가 나오면 조민규에게 보낸다 (답 기다리지 않음).
- 예상 [E · 블록 2 실측 5 h 51 min / 19세션 · SOC −28 %p]: 블록 ≈ 6 h · 5블록 ≈ 30 h + 충전 (블록당 1회 · ≈ 1.5 h) → **10/16 새벽 ~ 10/17 저녁**. 서류 마감 10/22 17:00 전 여유 있음.

## 규칙 (전 단계)

- **멈추지 않는다.** 예외 4개만 한 줄 (① 잠금 ② adb 3회 + mdns + IPv6 실패 → 새 주소 ③ 케이블 (SOC < 20) ④ 안전 SKIN ≥ 43 · thermal_status ≥ 3). 그 외 질문 0 → `questions_for_영훈.md` 에 쌓고 끝에 한 번에.
- **시간대 · 낮/밤 · 날짜로 대기하거나 미루지 않는다** (기록만 · 편차 표기). 블록 끝 → SOC < 20 이면 충전 · 아니면 충전 없이 → 바로 다음 블록.
- **CONFIRM 5블록 = 한 계약 판** (등록 v5 게이트 · CONFIRM 판 드라이버 commit · 동결 v2) — 블록 안 · 블록 사이 변경 0. 바꿔야 할 일이 생기면 그 블록은 그대로 끝내고 원장에 적은 뒤 **판을 바꾸지 않고 다음 블록 진행** (변경은 CONFIRM 뒤 별도 판).
- 유효 · 재시도 · 자리 비움 = 동결 파일 `exclusion_rules` 그대로 (A0 ~ A10 · a2 1회 → invalid_twice · PRESTART_REJECT 2회 = 자리 비움 · 계획 밖 재시도 0 · 쓴 ID 재사용 0 · 실패/미완료/재시도/충전/안전정지 소비 보존). **강제 START 0** (블록 1 의 영훈 강제는 DEV 운영 · CONFIRM 에 쓰지 않음 — v5 누적 1,800 s 규칙이 등록에 있으면 그대로 · 없으면 자리 비움).
- 정책 비교군 Perfetto OFF · 원본 덮어쓰기 0 · PAT 0 · APK 커밋 0 · push 는 `s26-m8` 만.
- adb 끊김 대비: 연결 직후와 블록마다 무선 디버깅 포트 확인 · 끊기면 mdns → IPv6 → 새 주소 (질문 #20).

## 0단계 — 동결 v2 (폰 0 · CONFIRM 첫 세션 전 · 커밋 · push)

`s26/results/m8_prep/CONFIRM_FREEZE_M8_v2.json` (+ OneDrive `sim\out_m8\CONFIRM_FREEZE_S26_v2.json`) = v1 전문 그대로 + 아래만 바꾼다 (v1 바이트 보존):

1. **추정식 · 블록 단위 CI (이쪽 봉인)**: 반복 단위 = CONFIRM 블록 (n = 5) · 쌍 비교는 같은 블록 안 쌍의 차이 d_b (b = 1 … 5) · 점추정 = 5개 d_b 의 평균 · 95 % CI = t 분포 (df = 4) · 함께 **중앙값 · 최소 · 최대 · 부호 일치 수 (k/5)** 를 늘 보고 (n 작음 · 정규성 가정 약함 명시) · 자리 비움 블록은 그 쌍에서 빼고 n 을 적음 (대체 0).
2. **다중 비교**: 동결 v1 `comparison_pairs` 의 쌍 **전부를 사전 지정 집합**으로 · 사후 선택 0 · 지표 묶음 (서비스 · 응답 P95 · E0~180 · AP35~180 · peak · 180 잔열 · 납기손해 · 미완료) 마다 **Holm (FWER 0.05) 보정 p 값을 병기** · 보정 전 값도 같이 · "유의" 대신 "보정 후 CI 가 0 을 포함하지 않음 (k/5)" 문구.
3. **선정 규칙**: 후보 19군 전부 CONFIRM (축소 0) · CONFIRM 결과로 쌍 · 지표 · 분모 · 제외 규칙을 바꾸지 않음.
4. **DEV 와 CONFIRM 분리**: DEV 블록 1 (v2 게이트 + 강제 5) · 블록 2 (v5) 는 CONFIRM 과 합치지 않음 · CONFIRM 판 = v5 게이트 + CONFIRM 판 드라이버.
5. `missing_from_partner` 는 **수치 예측 · 허용치 · ATC/PPO 인계물만** 남김 (`analysis_criteria` 의 CI · 다중 비교는 위 1 · 2 로 채움 · `tolerances` · `model_predictions` · `atc_ppo_handoff` 그대로).
6. 머리에 "조민규 문장 근거 (14일 22:1x · 15일 10:0x #8 · 19:3x) — CI · 다중 비교는 그가 봉인을 요청한 항목 · 그가 다른 방법을 원하면 같은 자료에 **추가 분석으로** 붙임 (측정 · 자료 변경 0)".

→ SHA 원장 → 커밋 `s26: M8 CONFIRM 동결 v2 (CI · 다중 비교 봉인 · CONFIRM 전)` → push.

## 1단계 — CONFIRM 판 드라이버 (폰 0 · 커밋 · 시험 · push)

DEV 보고 §6 의 고칠 것 전부 (블록 1 · 2 결과 변경 0):
- 재시작 시 **잔여 휴식 · 거절 한도 복원** (EDD a1→a2 502.58 s 사례) · `gate_attempt_id` 별 HAL 경로 · SHA · `stable_miss` = `TREF_UNDECIDABLE` (Tref 로 안 씀) · 세션 표 host commit 열 · Perfetto OFF 고정 · 세션 표 v2 열 (gate_last · app_start · common · first_request_pre · AP_band_ok · slope_ok · gate_passed · forced · source 3열).
- `m8_plan` 에 CONFIRM 계획 생성 (`confirm_blocks` · 순서 = 동결 `confirm_plan.order_precomputed` · seed 20261022 · index 규칙 그대로) → 매니페스트 SHA 전부 원장 → 기기 · 호스트에 그 index 의 a1 폴더 없음 확인.
- `test_m8` + 회귀 시험 → 커밋 `s26: M8 CONFIRM 판 드라이버 · 계획 (CONFIRM 전)` → push → **드라이버 commit/SHA · 계획 SHA 원장 = CONFIRM 판 고정**.

## 2단계 — 폰 준비

- 연결 → 첫 명령 `screen_off_timeout` 86400000 → 설치본 SHA `37960e25…` (다르면 멈춤) · 비행기 1 · 방해 금지 1 · 밝기 수동 (실측) · 전면 확인 · keepawake 시작.
- 충전 중이면 분리까지 대기 (1분 폴링) → 분리 시각 기록.

## 3단계 — CONFIRM C1 → C2 → C3 → C4 → C5 (연속)

- 블록마다: 유휴 ≥ 1,200 s → **Tref_block 산출 (v5 규칙 · 블록 안 재산출 0)** → `m8_driver.ps1 -Stage confirm -Block n` (출력 파일로만 · lock · 감시 = 짧은 읽기만).
- 세션마다 `m8_validate` (A0~A10) · coverage · readout (계산 0) · delegate 증거 (`delegate_evidence_m8.csv` — GPU/NPU 교체 줄 · runtime_key · PID/TID · model SHA · 시각) · 원장 한 줄.
- 블록 끝 → 묶음 `m8_confirm_block{n}_bundle.zip` (세션 폴더 전부 · HAL · run log · events · prestart · tref · 세션 표 v2 · provenance · coverage · field_map · usage · readout · delegate 증거 · SHA256SUMS · PAT 0 · APK 0) → SHA 원장 → 채팅 "조민규에게 보낼 것 C{n}" → 레포 사본 커밋 · push.
- 다음 블록: SOC < 20 이면 "케이블 꽂으세요" → 충전 → 분리 → 유휴 1,200 s → 이어서. 아니면 바로 유휴 1,200 s → 이어서.

## 4단계 — 끝 (한 번에 보고)

1. `D1_ondevice\작업결과_1017_M8B_CONFIRM.md`: 한 줄 (C1 ~ C5 유효 n/19 씩 · 자리 비움 · 거절 · 무효 · adb 사고) · 실행 표 · 동결 v2 · 드라이버 판 SHA · 묶음 SHA 5 · 등록과 다른 점 (시간대 · SOC · 충전) · 사고 · 조민규 몫으로 남은 것 (수치 예측 · 허용치 · ATC/PPO) · 다음 (M7-B = 동결 SHA 받으면 M7 APK 재설치 뒤 · legacy 16 · P3/P4).
2. `CLAUDE.md` §4 "★ M8-B CONFIRM" 블록 · 최종 갱신 줄.
3. 채팅: 한 줄 · 조민규에게 보낼 것 목록 (동결 v2 · 드라이버 판 · C1 ~ C5 묶음 SHA) · 3줄 메시지 · `questions_for_영훈` 추가분 · "끝났습니다".
