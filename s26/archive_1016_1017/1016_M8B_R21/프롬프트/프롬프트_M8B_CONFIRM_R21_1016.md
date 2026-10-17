# 프롬프트 M8-B (축소판 R21) — CONFIRM 7군 × 3블록 = 21슬롯 · 주결과 = 에너지 · 열 차이와 납기 · 완료량 교환관계 (조민규 10/16 정정안)

> **이 파일이 `프롬프트_M8B_CONFIRM_1016.md` (95세션판 · SHA `c9554f9b…`) 를 대신한다.** 옛 파일은 지우거나 고치지 않는다 (원장에 "대체됨" 한 줄).
> 정정안 원문 = `D1_ondevice\조민규_답_1016_21슬롯_목적정정.txt` (SHA-256 `1dc9f5b58b518f145b33ed6bf8d0216aa9e40e9ba490e0af996d40c31e6ac257`) — 문구가 갈리면 원문이 정본.

**작업 클론 = `C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6` · 브랜치 `s26-m8` · HEAD `ac6dde94a` 이상 · 원장 `D1_ondevice\sim\out_m8\prep_ledger.txt` 이어서 append.**
**APK = 설치본 v2 `37960e25c5948f661f2f5b47a90a4356be1b3712706d34679e71a14842ced6ea` — 재설치 금지 · 앱 변경 0.**
**정본**: 조민규 답 전부 (`조민규_답_1014_*` · `1014c` · `1015_계약값` · `1015b` · `1015c` · 21:xx · 22:xx · **1016 정정안**) · 등록 v2 ~ v5 · 동결 v1 `CONFIRM_FREEZE_S26_1016.json` (`deedfc1be65354a0ef05ffacb07cefe7e939e6cc0a53d560493e5632eeb4023f`, **바이트 보존**) · `작업결과_1015_M8_DEV.md` §6 · §8.

## 무엇이 바뀌나 (95판 대비)

| 항목 | 95판 | R21 (이 판) |
|---|---|---|
| 군 · 블록 | 19군 × 5블록 = 95 | **7군 × 3블록 = 21슬롯** · 새 세션 추가 0 |
| 주결과 | 서비스 · 응답 (ΔJ · AP = 조민규 계산 · 이쪽 계산 0) | **같은 블록 기준군 대비 ① J0~180 ② AP35~180 시간 평균 · 관측 peak ③ AP180 · AP180−AP0 잔열** + 같이 반드시: 긴급/일반 · 전체 완료 · 정시율 · svc70/80/90/95/100 · 응답 P95 · 납기 손해 · 실패 · 미완료 |
| 보조 | — | J0~120 · J35~180 · 실제 병행/WAIT dose · 입장 · 배정 지연 |
| 반복 단위 · CI | 블록 n = 5 · t (df 4) | 블록 **n = 3** · 블록별 d_b 3개 전부 + 평균 · 중앙값 · 최소 · 최대 · 부호 k/3 · t (df 2) 구간은 **기술용**으로만 병기 · "통계적 최소 · 유의성 보장 아님" 명시 · 요청 128건 ≠ 반복 128 |
| 에너지 | 표본만 | S26 자체 원자료로 단위 · 부호 · 갱신 · 적분 일관성 판정 → 적격이면 **"등록 단위 가설 아래 gauge 추정 J"** · 아니면 raw 보존 · **에너지 미판정** (AP · 응답은 따로) |
| 앞 축소안의 "시간 동작만 · J/AP 는 성공 조건 제외" | — | **주목표로 쓰지 않는다** (철회). 시간 · 큐 · 병행 · WAIT 기록 = 에너지 · 열 차이의 원인 설명 기반 |

**유지 7군** (각 3블록): `M128_BASE` · `M128_ORDER` · `M128_PAIR_G` · `M128_WAIT200x16` · `M128_NPU_SERIAL` · `SMOOTH128_BASE` · `SMOOTH128_PAIR_G`.
**바꾸지 않는 것**: 입력 · 모델 · 기한 (긴급 800 / 일반 2,000 ms) · 응답 경계 (priority) · AVAILABLE · 비선점 · 최대 2건 · WAIT 설정 · **v5 게이트** · 계측 창 · 안전 · SOC (시작 ≥ 20 · 상한 없음 = 기존 영훈 결정 그대로) · 거절 한도 · 유효/재시도/자리 비움 규칙 (동결 v1 `exclusion_rules`).
**제외 12군** (`L64_*` 2 · `RECENT_*` 6 · `M128_PAIR_N` · `M128_WAIT200x12` · `M128_WAIT1000x12` · `SMOOTH128_ORDER`): CONFIRM 미실행 → **"미완료 — R21 축소로 CONFIRM 안 함 (DEV 2/2 만)"**. 이미 소비한 것이 있으면 전체 이력에 남긴다.
**시간 · 충전 · gate 대기를 줄이려고 기준을 완화하지 않는다.**

## 영훈이 할 일

- 폰 충전 (마지막 SOC 22) → 세션이 "케이블 뽑으세요" 하면 뽑기. 무선 디버깅 IP:PORT = `________________`.
- 폰 · PC 그 자리 (덮개 열림 · 절전 끔 · Wi-Fi 자동 전환 끔). 잠금 해제 요청이 오면 풀어 준다.
- 블록 묶음 · 동결 R21 · 드라이버 SHA 가 나오면 조민규에게 보낸다 (답 기다리지 않음 — 그가 "추가 승인 필요 없음").
- 예상 [E · 블록 2 = 19세션 5 h 51 min · SOC −28 %p 에서 비례]: 블록 ≈ 7세션 ≈ 2 ~ 2.5 h · 3블록 ≈ 7 h + 블록 앞 유휴 1,200 s ×3 + 충전 1회 안팎. M128 은 무거운 군이라 블록당 SOC 는 비례보다 클 수 있음 (실측으로 기록).

## 규칙 (전 단계 · 95판 그대로)

- **멈추지 않는다.** 예외 4개만 한 줄 (① 잠금 ② adb 3회 + mdns + IPv6 실패 → 새 주소 ③ 케이블 (SOC < 20) ④ 안전 SKIN ≥ 43 · thermal_status ≥ 3). 그 외 질문 0 → `questions_for_영훈.md` 에 쌓고 끝에 한 번에.
- 시간대 · 날짜로 대기하거나 미루지 않는다 (기록만 · 편차 표기).
- **R21 3블록 = 한 계약 판** (v5 게이트 · CONFIRM 판 드라이버 commit · 동결 R21) — 블록 안 · 사이 변경 0.
- 강제 START 0 (사람 개입) · v5 의 누적 1,800 s 자동 강제는 등록 규칙이므로 그대로 쓰되 **사람 개입 · 강제 gate · 자동 WAIT 횟수를 각각 별도 열**로.
- 정책 비교군 Perfetto OFF · 원본 덮어쓰기 0 · PAT 0 · APK 커밋 0 · push 는 `s26-m8` 만.

## 0단계 — 상태 확인 · 분기 (폰 0 · 맨 먼저)

1. 원장 · 드라이버 lock · 기기 `/sdcard/Android/data/.../` 와 호스트 세션 폴더에서 **CONFIRM START 수**를 센다 (95판 C1 ~ C5 label · index 500 ~ 539 · 200 ~ 214 · 그 밖 CONFIRM index 전부).
2. 원장에 한 줄: `[R21 정정안 적용 YYYY-MM-DD HH:MM:SS] 정정안 SHA 1dc9f5b5… · 95판 프롬프트 c9554f9b… 대체 · CONFIRM START 수 = n · 실행 중 세션 = (있으면 label)`.
3. **분기 A (START = 0)** → 1단계 ~ 끝 (새 개정 ID · 새 manifest 로 21슬롯 등록).
4. **분기 B (START ≥ 1 또는 실행 중)** →
   - 실행 중 세션은 끝까지 두고 그대로 저장 · 계수 · 이미 소비한 실패 / 미저장 START 도 그대로 (성공 행으로 다시 채우지 않음).
   - **새 21회를 더 돌리지 않는다.** 95판 C1 ~ C3 안의 7군 슬롯 (아래 표) 대응과 상대 순서를 유지하고, 남은 7군 슬롯만 진행. 제외 12군과 C4 · C5 슬롯은 더 START 하지 않음 (이미 소비한 것은 전체 이력에 그대로).
   - 동결 R21 · 분석 계약은 "분기 B" 표시로 같은 내용 봉인 (2단계). 이미 START 한 행에 새 판정 규칙 소급 0.

## 1단계 — 21슬롯 표 (분기 A · 새 개정 ID `M8_CONFIRM_R21_v1`)

슬롯 = 동결 v1 `confirm_plan.order_precomputed` 의 C1 ~ C3 에서 7군만 골라 **상대 순서 그대로** (새 무작위 0 · 블록 번호 = R1 ~ R3).

| R블록 | 순서 (원 C 슬롯 label) |
|---|---|
| R1 (= 원 C1) | C1-03 `M128_PAIR_G` → C1-05 `M128_ORDER` → C1-09 `M128_WAIT200x16` → C1-14 `SMOOTH128_PAIR_G` → C1-16 `M128_BASE` → C1-17 `M128_NPU_SERIAL` → C1-18 `SMOOTH128_BASE` |
| R2 (= 원 C2) | C2-00 `M128_WAIT200x16` → C2-04 `SMOOTH128_PAIR_G` → C2-07 `SMOOTH128_BASE` → C2-09 `M128_BASE` → C2-13 `M128_PAIR_G` → C2-14 `M128_NPU_SERIAL` → C2-15 `M128_ORDER` |
| R3 (= 원 C3) | C3-03 `M128_WAIT200x16` → C3-05 `M128_BASE` → C3-09 `SMOOTH128_BASE` → C3-10 `M128_NPU_SERIAL` → C3-11 `M128_ORDER` → C3-13 `SMOOTH128_PAIR_G` → C3-16 `M128_PAIR_G` |

- 각 슬롯 행: `revision_id = M8_CONFIRM_R21_v1` · `origin_slot` (원 label · index · session_id) · 새 label `R{b}-{pos}-{arm}`. **index · session_id 는 원 C 슬롯 값 그대로** (95판에서 START 0 이므로 미소비 · 1:1 추적용) → 기기 · 호스트에 그 index 의 a1 폴더 없음 확인. 있으면 멈추지 말고 분기 B 로.
- 새 manifest (슬롯 21 · 원 index · 블록 · 순서 · 계약 SHA) → SHA 원장. 95판 계획 · manifest 원본 무변경.

## 2단계 — 동결 R21 (폰 0 · CONFIRM 첫 START 전 · 커밋 · push)

`s26/results/m8_prep/CONFIRM_FREEZE_M8_R21_v1.json` (+ OneDrive `sim\out_m8\CONFIRM_FREEZE_S26_R21_v1.json`) = 동결 v1 를 **부모 (SHA deedfc1b…)** 로 참조 · v1 무변경 · 아래를 담는다:

1. **범위**: 21슬롯 표 · 유지 7군 · 제외 12군 상태 · 정정안 SHA · 적용 시각 (0단계 원장 줄) · 분기 A/B.
2. **비교쌍 (사전 지정 · 사후 선택 0)**: 같은 블록 같은 R 안에서 1:1 — M128: BASE↔ORDER · BASE↔PAIR_G · BASE↔NPU_SERIAL · BASE↔WAIT200x16 / SMOOTH128: BASE↔PAIR_G / 도착 모양: SMOOTH128_BASE↔M128_BASE · SMOOTH128_PAIR_G↔M128_PAIR_G. (v1 쌍 중 제외군 쌍 = "R21 미실행" 표시.) 한쪽이 무효/빈 자리면 그 블록 쌍 제외 · n 을 적음 · 대체 0.
3. **주결과 정의 (세션별 → 같은 블록 기준군 대비 Δ)**:
   - **J0~180** = ∫ W dt, W = −current_raw(µA) × voltage(mV) / 10⁹ · 앱 power_sample · common 0 ~ 180 s · 사다리꼴 · 경계 = 양측 표본 선형 (gap ≤ 2.5 s 일 때만) · 구간 안 gap > 2.5 s 면 null (보간 0) · **에너지 적격 (4) 일 때만 값** · 표기 "등록 단위 가설 아래 gauge 추정 J".
   - **AP35~180 시간 평균** = HAL AP (온도 센서 · **표면온도 아님** · SKIN 과 구분) 35 ~ 180 s 사다리꼴 / 145 s · 경계 = 양측 표본 선형 (gap ≤ 5 s) · 안 되면 null. **관측 peak** = [35, 180] 안 실제 HAL 표본 최대 (보간값 아님).
   - **AP180 · AP180 − AP0 잔열**: AP0 · AP180 = 각 시점 양측 표본 선형 (gap ≤ 5 s) · 없으면 null. (v1 의 "AP(180) − AP(35)" 는 v1 정의로 보존 · R21 주결과는 **AP180 − AP0** · 둘 다 열 이름을 나눠 기록.)
   - **같이 반드시 (주결과와 한 표)**: 긴급 / 일반 / 전체 별 완료 수 · 정시율 · svc70/80/90/95/100 (분모 planned) · 응답 P95 (긴급 output_ready · 일반 readback 성공) · 납기 손해 (late 수 · 비율 · 넘긴 ms 합) · failed · undispatched · unfinished · 미완료 세션.
   - **보조**: J0~120 · J35~180 (같은 규칙) · 실제 병행 겹침 (dose s) · WAIT 명목 / planned / 실제 dose / 초과량 / cut · 입장 지연 · 배정 지연 분포.
4. **에너지 적격 규칙 (S26 자체 원자료 · A24 단위 · 배율 가져오기 0 · DEV 근거로 지금 봉인)**:
   - 가설: current_raw µA · voltage mV · 방전 음수 · W = −I × V / 10⁹ · 전하 Q_int = ∫(−I_µA) dt / 3600 [µAh] vs ΔQ_cc = charge_counter 감소 [µAh].
   - DEV 38 세션 (블록 1 · 2 원자료 · 계산은 이번이 처음이면 원장에 "DEV 로 규칙 봉인 · CONFIRM 자료 미열람") 에서: 부하 중 current_raw 부호 비율 · 전압 범위 · 각 필드 값 변화 간격 (읽기 주기 · 값 변화 간격 · 센서 갱신 시각 미제공을 따로) · 세션별 Q_int / ΔQ_cc 비 r (구간 = 앱 power 첫 ~ 마지막 유효 표본 중 charge_counter 계단 경계 사이 · 계단 크기 실측 기록) 분포를 표로.
   - 판정 (단위 · 배율 가설 확인용 · 정밀 교정 아님): 부하 중 방전 음수 ≥ 95 % · 전압 3,000 ~ 4,600 mV · DEV r 중앙값이 0.8 ~ 1.25 → **"단위 가설 적격"**. 아니면 **"미확정 — raw 보존 · 에너지 미판정"** (×1000 등 임의 보정 0). CONFIRM 세션별: r 이 같은 범위 + J 창 coverage 통과일 때만 J 값 · 아니면 그 세션 J = null + 사유.
   - 문구 고정: "두 값이 맞아도 내부 배터리 gauge 끼리의 정합 · 외부 전력계 교정 아님".
5. **창 · 경계 · 결측 (유지 + 명시)**: 사전 60 s · 이후 210 s · J0/120/180 · AP35/180 양측 표본 · gap · 결측 규칙 = v1 `settings.coverage` 그대로 + **AP0 점 추가 (HAL 양측 · gap ≤ 5 s)**. 원자료 구분 열: `common_boundary.start_ns` · 계획 offset / scheduled binding · 앱 power 원파일 · SHA · 시계 · 첫/끝 표본 시각 · 연속 HAL 원파일 · SHA · 시계 · 읽기 시작/끝 (또는 완료 상한) · "센서 갱신 시각 미제공". **이웃 세션 이어붙임 · 결측 보간 · tail 외삽 0.**
6. **추정 · 다중 비교**: 반복 단위 = R블록 (n ≤ 3) · d_b 3개 전부 공개 · 평균 · 중앙값 · 최소 · 최대 · 부호 k/3 · t (df = 2) 95 % 구간 = 기술용 · Holm (FWER 0.05) 보정 p 를 지표 묶음마다 보정 전 값과 병기 · "유의" 대신 "보정 후 구간이 0 을 포함하지 않음 (k/3)" · 머리말: "3블록은 통계적 최소나 유의성 보장이 아니다 · 요청 128건을 독립 반복으로 세지 않는다".
7. **초기 상태 기록 (조정 0)**: 슬롯마다 gate 결과 · Tref_block · 시작 AP · 120 s 기울기 · resident 상태 · 직전 세션 (arm · 끝 시각) · 직전 휴식 s · SOC 시작/끝 · 충전 여부 · 시간대 · 블록 안 충전. 군별 보정 · 재정렬 · 대체 0 · 남은 초기 편차는 표에 그대로.
8. **주장 경계 (`claims_boundary`)**: R21 로 검증했다고 하지 않는 것 = RECENT 열 이력 메커니즘 · CPU/NPU 전체 경로 · NPU 병행 (PAIR_N) · 최적 WAIT · resident 재생성 → **"미완료"**. 조민규 쪽 REFINE26/RISK 조건부 예측은 이쪽 판정 아님 · 사전예측 없던 세션을 "사전예측 검증" 이라 부르지 않음 · `model_predictions` · `tolerances` · `atc_ppo_handoff` = missing_from_partner 그대로 (채우지 않음).
9. 머리말: "조민규 1016 정정안 (SHA 1dc9f5b5…) — 앞 축소안 '시간 동작만' 철회 · 주목표 = 스케줄링별 에너지 · 열 차이와 납기 · 완료량 교환관계".

→ SHA 원장 → 커밋 `s26: M8 CONFIRM R21 동결 (7군×3블록 · 주결과 J/AP · 에너지 적격 규칙 · CONFIRM START 전)` → push.

## 3단계 — CONFIRM 판 드라이버 · 분석 계약 (폰 0 · 커밋 · 시험 · push)

- 95판 1단계의 고칠 것 전부 그대로: 재시작 시 잔여 휴식 · 거절 한도 복원 · `gate_attempt_id` 별 HAL 경로 · SHA · `stable_miss` = `TREF_UNDECIDABLE` · 세션 표 host commit 열 · Perfetto OFF 고정 · 세션 표 v2 열.
- **R21 계획 입력** (`--plan-file` = 1단계 manifest) · 드라이버가 21슬롯 밖 index 를 거부하는 검사 · 슬롯 표에 `revision_id` · `origin_slot`.
- **세션 표 새 열**: 2단계 7 의 초기 상태 · 사람 개입 / 강제 gate (자동 1,800 s) / 자동 WAIT 횟수 각각 · WAIT 명목 / 실제 dose / 초과량.
- **분석 계약 `m8_readout_r21.py`** (기존 readout 무변경 · 새 파일): 2단계 3 ~ 6 그대로 (J · AP · 잔열 · 서비스 · 보조 · 에너지 적격 · Δ · d_b · 요약). 단위 시험 = 경계 양측 · gap 초과 → null · 보간 0 · 부호 · µAh 계산 · 계단 경계 · Holm.
- 커밋 `s26: M8 CONFIRM R21 드라이버 · 분석 계약 (CONFIRM START 전)` → push → **드라이버 · 분석 계약 commit/SHA · manifest SHA 원장 = R21 판 고정**. 원장 한 줄로 "정정안 적용 시각 ↔ 동결 R21 SHA ↔ 드라이버 · 분석 commit ↔ (뒤에) 첫 적용 START 시각" 연결.

## 4단계 — 폰 준비

- 연결 → 첫 명령 `screen_off_timeout` 86400000 → 설치본 SHA `37960e25…` (다르면 멈춤) · 비행기 1 · 방해 금지 1 · 밝기 수동 (실측) · 전면 확인 · keepawake 시작.
- 충전 중이면 분리까지 대기 (1분 폴링) → 분리 시각 기록.

## 5단계 — R1 → R2 → R3 (연속)

- 블록마다: 유휴 ≥ 1,200 s → Tref_block (v5 · 블록 안 재산출 0) → `m8_driver.ps1 -Stage confirm -Block n` (R21 manifest · 출력 파일로만 · lock · 감시 = 짧은 읽기만). **첫 R1 슬롯 START 시각을 원장 연결 줄에 채움.**
- 세션마다 `m8_validate` (A0 ~ A10) · coverage (AP0 포함) · `m8_readout_r21` · delegate 증거 · 원장 한 줄 (소비 · 실패 · 재시도 포함).
- 블록 끝 → 묶음 `m8_confirm_r21_block{n}_bundle.zip` (세션 폴더 전부 · HAL · run log · events · prestart · tref · 세션 표 · manifest · 소비/실패 원장 발췌 · provenance · coverage · field_map · readout_r21 · 에너지 적격 표 · delegate 증거 · 버전/SHA · SHA256SUMS · PAT 0 · APK 0) → SHA 원장 → 채팅 "조민규에게 보낼 것 R{n}" → 레포 사본 커밋 · push.
- 다음 블록: SOC < 20 이면 "케이블 꽂으세요" → 충전 → 분리 → 유휴 1,200 s. 아니면 바로 유휴 1,200 s → 이어서.

## 6단계 — 끝 (한 번에 보고)

1. `D1_ondevice\작업결과_1016_M8B_CONFIRM_R21.md`: 한 줄 (R1 ~ R3 유효 n/7 씩 · 자리 비움 · 거절 · 무효 · adb 사고) · 실행 표 · **주결과 표 (쌍별 d_b 3개 · 요약 · k/3 — 에너지 적격/미판정 표시)** 와 **같은 표의 서비스 · 납기 · 미완료** · 보조 표 · 에너지 적격 표 (DEV · CONFIRM) · 초기 상태 편차 표 · 동결 R21 · 드라이버 · 분석 SHA · 묶음 SHA 3 · 등록과 다른 점 · 사고 · 미완료 경계 (2단계 8) · 조민규 몫 (수치 예측 · 허용치 · ATC/PPO).
2. `CLAUDE.md` §4 "★ M8-B CONFIRM R21" 블록 · 최종 갱신 줄.
3. 채팅: 한 줄 · 조민규에게 보낼 것 목록 · 3줄 메시지 · `questions_for_영훈` 추가분 · "끝났습니다".
