# M6 — S26 같은 APK 정책 대응 · 게이지 진단 · 초기 잔류열 냉각 — 사전 등록 v3 (2026-10-12 · Cowork · 폰 측정 0 · 결과 전)

> **v2 → v3 (영훈 결정 10/12 · 측정 전)**: 배터리 기준만 바꾼다 — 실행 시작 SOC 하한 50 → **30** (어제 M5 ABBA 가 SOC 60 기준에 걸려 끊김) · 블록 안에서 30 아래로 내려가면 충전 후 이어서 (표시) · 화면 끄기 방지 86400000 을 M6-A · M6-B 사이에도 유지. 나머지는 v2 글자 그대로. v2 (`c376554f…`) 는 쓰지 않는다.
> **v1 (`74e7d583…`) 은 쓰지 않는다** (측정 · 커밋 0). v1 → v2 (영훈 결정 10/12 · 측정 전): ① 확인 블록 = **조민규 모형 동결 SHA 를 받은 뒤 새로 측정** (v1 의 "동결 전 측정 · 봉인" 폐기) ② 세 규칙의 준비 조건을 같게 — 새 블록 `M` (상주 runtime 5개 공통) ③ 부하 B 를 L 과 같은 요청 수 (100) 로 ④ 냉각 K 를 엔진 무변경 꼴 (요청 0 · 창 780 s) 로 ⑤ 센서 갱신 관측 런 E-T 추가 ⑥ 기존 자료 사전 계산 (`M6_사전계산_1012.md`) 을 설계 근거로 공개.
> 출처: 조민규 S26 추가 요청 (10/12 카톡) 1 · 2 · 3 · 문서 — **빠짐없이**. 단 "독립 전력/전하 기준 대조 자료" 와 "API/드라이버 갱신주기 · 해상도 · 필터/보정 · 센서 지연의 근거 문서" 는 **없음** 으로 답하고 만들지 않는다 (장비 · 공개 사양 없음 — A24 도 같은 API · 같은 한계 [D 그의 `ARRIVAL_ENERGY_ANDROID_PREP_20260926.md` · `S26_REQUIRED_MATERIALS_20261011.md`]). 대신 **관측** 으로 갱신 · 해상도 · 반복 변동 · 센서 값 변화 간격을 만든다.
> 하지 않는 것: 판정 이름 · 모형 적합 · 정책 우열 판정 (조민규가 개발 자료로 식 · 계수 · 초기화 규칙 동결 → 확인 자료로 ΔJ · 온도 평가) · 장시간 CPU 감속 · NPU 제어 · 새 NPU 지원 · 미지원 병행 · 3건 동시 실행 · 냉각 대기 정책 · PPO APK.
> 표기: [P] 실측 · 기록 · [D] 문서 · [E] 추정 · `미확인`. 이 파일은 한 글자도 고치지 않는다 (고치면 `_v4`).

## 0. 결과 전에 본 것 (설계 근거 · 기존 자료만 · 새 측정 0)

`M6_사전계산_1012.md` (Cowork · GitHub `s26-mixreq` `21cba44` · `s26-statesplit` `9c857f1` 의 R3 16 · R4C 16 · SS 12 세션):
- 기존 power_sample 간격 0.900 s · current_raw 는 표본의 97.5 ~ 99.2 % 에서 바뀜 · **charge_counter 와 전압은 약 30.6 s 마다 (그 배수) 만 바뀜 · charge_counter 계단 4,275 µAh (≈ 61 J)** · 5 ~ 115 s 창에 1 ~ 4 번 갱신 → R4C 8쌍 ΔE_int 와 ΔE_cc 부호 일치 **3/8 재현** (조민규 값과 같음).
- 좌표: 공통창 원점 = `common_start` · 첫 예정 도착 +35.000 s · `common_boundary` 는 창 밖 시각을 null 로 둔다 · SS 창 밖 lane_available = CPU 6 ~ 8 · GPU/NPU 1 (조민규 값과 같음) · R3 · R4C 마지막 73.5 s.
- 준비 (runtime 생성 + warmup) ≈ 4 s · 그동안 5.7 ~ 8.6 W · AP 최고 34.9 ~ 39.9 ℃ → 원점 AP 28.6 ~ 31.7. **R4C idx 0 (B2) baseline 중 앱 추론 없는 구간 (−16 ~ −10 s) 에 9 ~ 20 W · AP 36.1 → 원점 31.5 · 34 s 뒤 27.4** (원인 `미확인`).
- HAL (호스트 dumpsys) 읽기 간격 ≈ 2.3 s · 값 최소 변화 0.1 ℃ · 값 변화 간격 중앙 AP 2.6 · SKIN/BAT/PA 3.5 s.
- 부하 L · B 를 R3 점유 표본으로 돌려 본 마지막 완료 [E]: L ≈ 74.9 s · B ≈ 72.3 ~ 72.6 s (1.6 배 느려져도 ≤ 73.4 s).
- 현재 APK 는 요청표를 고정 유도식과 비교 · 블록 A (4 runtime: C · G) / N (5: C · N) 이라 세 규칙의 상주 집합이 다르다 [P 코드 `8bd3d76`].

## 1. APK 하나 (이번 E · K · P 전부)

1. 새 APK `M6` 하나. 바꾸는 것 = **(a) 계약/검증**: 실험 ID 표 행 (`S26-M6-P` · `S26-M6-K` · `S26-M6-E` · 각 `-SMOKE`) · 블록 `M` (키 = 기존 블록 N 의 5개 · 허용 정책 = 3개 · 준비 상한 = 블록 N 값) · 요청표 유도 `M6Plan` (§3-2 · §4) **(b) 진단 진입점**: `GaugeDiagActivity` (별도 Activity · 기존 runtime 생성 · 실행 함수를 호출만).
2. 바꾸지 않는 것 (`8bd3d76` 대비 diff 0 · 파일 목록으로 증명): `SessionEngine` · `SessionActivity` · `PolicyStudy` · `Runtimes` · `ImageContract` · `Decoders` · `EventLog` · `Json` · `BatterySampler` · 모델 · 입력 이미지 · LiteRT 2.2.0 · `numThreads=1` · GPU FP32 요청 · 단계 상수 (baseline 30 · drain 30 · cooling 60 · 표본 900 ms) · 정지 규칙.
3. 회귀: 기존 `plan_v3c` B2 매니페스트 1세션 → 계약 키 · requests 열 · 단계 · power_sample 키 R3 와 같음 · 긴급 P95 70 ~ 80 ms. 벗어나면 측정하지 않는다.

## 2. 측정 E — 게이지 진단 (개발 단계에 · 판정 없음)

1. **E1 · E2 · E3** (같은 꼴 3회): `GaugeDiagActivity` — **무부하 60 s** (앱 전면 · 분류 CPU runtime 상주 · 추론 0) → **연속 부하 120 s** (분류 CPU · 같은 모델 · `numThreads=1` · 간격 없이 연속) → **쉼 120 s**. 같은 시계 (`elapsedRealtimeNanos`) 로 목표 20 ms 마다 `CURRENT_NOW` · `CURRENT_AVERAGE` · `CHARGE_COUNTER` · `ENERGY_COUNTER` (미지원이면 기록) · `EXTRA_VOLTAGE` (sticky) · 읽기 전 · 후 시각 · 구간 표식. 앱에서 `/sys/class/power_supply/battery/{current_now,voltage_now,charge_counter}` 읽기 가능 여부 1회 (가능하면 같은 폴링에 추가).
2. **E-T** (1회 · E3 뒤): E 와 같은 꼴 + 기기 쪽 셸 반복 (`/proc/uptime` + `dumpsys thermalservice` 의 `Current temperatures from HAL` 블록 + 읽을 수 있으면 `/sys/class/thermal/thermal_zone*/{type,temp}`) 을 쉬지 않고 → 센서 값 변화 간격을 2.3 s 보다 촘촘한 읽기로 관측. 반복 자체의 부하는 E-T 에만 있다 (E1 ~ E3 게이지 값과 섞지 않는다).
3. 계산 (Cowork · 측정 뒤 · 정의 고정 · 숫자 기술만): E-a 필드별 값 변화 간격 (중앙 · 사분위 · 최빈, 10 ms 칸) · E-b 0 아닌 최소 |Δ| · 정수 Δ 최대공약수 · 빈도 상위 3 · E-c 부하 시작/끝 → current_now 가 무부하 중앙 + 5 × MAD 를 처음 넘는 시각 · 부하 마지막 60 s 중앙의 90 % 도달 시각 (끝도 대칭) · E-d current_avg 와 RMSE 최소인 current_now 뒤쪽 이동평균 창 (1 ~ 60 s) · E-e 구간별 ∫ current_now·V dt vs Δcharge_counter·V (계단 수) — **같은 gauge · 정확도 근거 아님** · E-f 3회 범위 · E-T: 센서별 값 변화 간격 · 최소 Δ · 읽기 간격. HAL 이 갱신 시각을 주지 않으면 「실제 갱신 시각 미확인 — 읽기 시각 기준」 · 지연 `미확인`.
4. 유효: plugged 0 · 화면 켜짐 · 시작 SKIN 29.5 ~ 31.5 · 폴링 간격 중앙 ≤ 25 ms (실제값 기록) · 안전 멈춤 없음. 무효 1회 재시도 · 무효 기록 보존.

## 3. 측정 P — 같은 APK 정책 대응 12세션

1. 규칙 3개 (기존 그대로): `CPU_URGENT_ONLINE_V1` (C) · `B2_PARALLEL_ONLINE_V1` (G) · `S26_NPU_PARALLEL_V1` (N). **세 규칙 모두 블록 `M`** — 상주 runtime 5개 (`classification_CPU` · `classification_GPU` · `classification_NPU` · `detection_CPU` · `detection_GPU`) · 같은 준비 · warmup.
2. 부하 2개 — 둘 다 **100건 (분류 urgent 50 · 탐지 normal 50)** · 기한 1.5 s / 6 s · open-loop · 같은 이미지 · 시각 = 공통창 원점 기준:
   - **L 낮은 혼합**: i = 0 … 99 · 예정 도착 35,000 + 400 i ms (35.0 ~ 74.6 s) · 짝 = 분류 · 홀 = 탐지.
   - **B 밀집 · 버스트**: 버스트 k = 0 … 9 · 버스트 안 j = 0 … 9 · i = 10k + j · 예정 도착 35,000 + 4,000 k + 50 j ms (35.0 ~ 71.45 s) · j 짝 = 분류 · 홀 = 탐지.
   - 같은 부하의 세 규칙은 요청표의 (ordinal · 종류 · 우선순위 · 예정 도착 · 기한) 이 같다 (request id 는 기존처럼 세션 id 에서 uuid5 유도). 이 다섯 열만 뽑은 JSON 의 SHA 를 부하마다 원장에 (세 규칙 같아야 함).
3. 단계 = 기존 (준비 → warmup → baseline 30 → 공통창 120 → drain ≤ 30 → cooling 60).
4. 시작 조건 (P · K · E 같게): 비행기 · 방해 금지 · 화면 켜짐 (`screen_off_timeout` 86400000 · 잠금 없음) · 밝기 수동 최소 · plugged 0 · 게이트 SKIN ≤ 32 · AP ≤ 32 · BAT ≤ 30 · **준비 시작 SKIN 29.5 ~ 31.5** (20분 기다려도 안 되면 진행 · 표시) · 세션 사이 ≥ 90 s · **실행 시작 SOC 30 ~ 90** (블록 · 묶음 시작 전에 90 까지 충전 → 분리 뒤 20분 + 게이트) · **다음 실행 전 SOC < 30 이면 그 자리에서 충전 (90 까지 · 분리 뒤 20분 + 게이트) 하고 순서 그대로 이어간다 — 그 뒤 실행에 `블록 안 충전` 표시 (무효 아님)** · 앱 안 정지 (SOC < 20) 는 기존 계약 그대로 · **화면 끄기 방지 `screen_off_timeout` 86400000 은 M6-A 시작부터 M6-B 끝까지 유지 (실행마다 값 확인 · 중간 원복 금지)** · 측정 PC 같은 자리.
5. 블록 · 순서 (거울 · 결과 전 고정):
   - **개발 D** (idx 0 ~ 5): L-C · B-G · L-N · B-C · L-G · B-N
   - **확인 K** (idx 6 ~ 11 · 동결 뒤): B-N · L-G · B-C · L-N · B-G · L-C
6. 유효 (세션마다):
   - V1 계획 100건 전부 dispatch · 전부 terminal 기록 (성공 · 실패 · 기한 미충족).
   - V2 **`common_boundary` 의 lane_available null 0 · 모든 `lane_available` 이벤트 < 원점 + 120.000 s** (= 120 s 에 전부 실제 AVAILABLE).
   - V3 power_sample 결측 · drain = 기존 R3 규칙 · V4 C 세션 겹침 0 · N 세션 NPU 계약 PASS · V5 안전 멈춤 없음 · 화면 · plugged 유지.
   - 무효 → 그 자리 1회 재시도 · 두 번 무효 → `invalid_twice` (순서 유지). **무효 시도 폴더 · 이유를 지우지 않는다.** 기한 미충족은 유효성 아님.
7. 측정 쪽 산출: 세션 폴더 전부 (기존과 같은 꼴: `progress.jsonl` · `common_boundary.json` · `requests.json` · 요청별 event/result · `summary.json` · `manifest.json` · `start_check.json` · `warmup.json` · host `hal.csv` · `session_log` · `phone_watch` · `top_h` · `validated.json`) + 세션 표 (시작 SKIN · AP · BAT · SOC · 밝기 · 직전 실행 · 간격) + readout JSON. **J · 열 지표 · 정책 비교 계산은 측정 쪽에서 하지 않는다.**

## 4. 측정 K — 초기 잔류열 냉각 (요청 0)

1. 꼴 (4회 같음 · 블록 `M` 준비 · 정책 `CPU_URGENT_ONLINE_V1` 표기 — 요청 0 이라 실행 경로 없음): 준비 → warmup → baseline 30 → **공통창 780 s 요청 0** → drain → cooling 60. 엔진 무변경 (창 길이만 실험 표 행).
2. 두 시작 조건을 같은 런에서: **W (표준 워밍업 직후 시작)** = 창 [0, 180) s — 원점까지 정책 세션과 같다 · **S (안정 시작)** = 창 [600, 780) s — 준비 뒤 600 s 상주 · 추론 0 으로 잔류열이 빠진 뒤.
3. 런: **K1 · K2 = 개발** (P 개발 블록 전) · **K3 · K4 = 확인** (동결 뒤 · P 확인 블록 뒤). 조건마다 개발 2 · 확인 2 구간 (요청한 1 + 1 보다 많다).
4. 함께 기록: power_sample · 호스트 HAL (기존과 같은 읽기) · 직전 부하 (직전 실행 종류 · 끝 시각 · 경과) · 시작 SOC · **실내 온도** (온도계가 있으면 영훈이 시작 · 끝에 읽음 · 없으면 `미기록`). 센서 갱신 관측은 E-T 로.
5. 계산 (Cowork · 기술만): 구간 S 의 시작 전 120 s AP · SKIN 기울기 \|·\| ≤ 0.1 ℃/min → "안정", 아니면 "안정 미달" 표시 (자료는 그대로).

## 5. 문서 — APK ↔ source commit 연결표

- 이미 계산 (`M6_APK커밋_연결표_1012.md` · GitHub 원격 기준 [P]): 세션 자료의 `apk_sha256` = R3 16/16 `591cae72…` · R4C 16/16 `b97a9784…` · SS 12/12 `c2e78939…` · 커밋 `e2bedf1` · `c75d085` · `8bd3d76` · 영역별 diff (전처리 · logger · worker/큐 · sampler · 정책 · runtime 변경 0).
- PC 에서 더하는 것: 세 커밋을 각각 다시 빌드한 해시 비교 (같지 않으면 「빌드 재현 미확인 — 작업 기록 · 세션 기록상 대응」, `classes*.dex` 비교 병기) · M6 행.

## 6. 개발 / 확인 구분과 전달

1. **1차 전달 (개발)**: §5 연결표 · E1 ~ E3 · E-T · K1 · K2 · P 개발 6 원자료 + 이 등록.
2. 조민규가 개발 자료로 식 · 계수 · 초기화 규칙을 고정한 파일의 SHA-256 을 보낸다 → 원장에 적는다.
3. **그 뒤에** 확인 측정: P 확인 6 · K3 · K4 → **2차 전달**. 확인 자료로 계수 · 규칙 · 기준을 바꾸지 않는다. 확인 측정은 개발과 같은 등록 · APK · 매니페스트 · 운영.
4. 동결 SHA 가 오기 전에는 확인 측정을 하지 않는다.

## 7. 반대 해석 (결과 전)

1. 20 ms 폴링 자체가 부하 · 갱신을 바꿀 수 있다 — "이 폴링에서 관측된" 값.
2. 같은 gauge 대조는 정확도 근거가 아니다 · 독립 기준 없음 → 절대 J 미인증.
3. 연속 부하는 분류 CPU 한 수준.
4. 2부하 × 3규칙 × 개발 1 + 확인 1 = 초기 확인 규모 (반복 변동 추정 불충분).
5. 부하 B 와 블록 `M` 은 기존 자료를 본 뒤 정했다 (§0).
6. 블록 `M` 의 C · G 세션은 NPU runtime 이 추가로 상주 — R3 / R4C / SS 의 C · G 와 준비 조건이 다르다 (비교는 M6 안에서만).
7. 확인 블록은 개발 뒤 다른 날일 수 있다 — 실내 · 폰 상태 차이를 시작 조건표로 남긴다.
8. 냉각 S 구간은 "준비 뒤 600 s" 로 정의한 안정이다 (안정 보장 아님 — 표시만).
9. E-T 의 촘촘한 HAL 읽기도 HAL 갱신 시각 자체는 주지 않을 수 있다.
10. 새 APK `M6` 는 앞 3종과 다른 해시 — "같은 APK" 는 M6 안에서만.
