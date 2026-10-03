# M1-NPU (NPU 스로틀 회복) 사전 등록 — v1 (2026-10-03 18:52 KST, 측정 전 동결)

> 형식은 `M1M2_사전등록_v1.md` §2 (GPU M1) 를 따르되 **NPU 는 조임 폭이 ×1.1 안팎이라 "≤ ×1.10 = 회복" 기준을 못 쓴다** → 기준을 새로 정한다 (아래 §2). 이 파일이 든 커밋 SHA·시각이 동결 증거. 측정 뒤에는 고치지 않는다 — 바꿔야 하면 `_v2`.
> 표기: [P] 실측 · [D] 인용 · [E] 추정 · [P-시뮬] v1 예측 (`v1_예측_밤1003.md`). 폰·adb 호출 0 (이 세션).

## 0. 체인 (4-1) [P]

- 파일 **`D1Check_v4\tools\chains\m1_recovery_npu_v1.json`** (새 파일, 기존 체인 무변경) — `d1-npu-chain-v1`, per_segment, NPU 구간 필드는 `m2r_heated_npu_to_gpu_v1.json` 의 NPU 구간 그대로 (`models/mobilenet_v1_1.0_224_Samsung_E9965.tflite` · `lcg-unit`)
- 구간: 0 `cold_ref_d10` NPU d10 60 s → 1 `heat_d100` NPU d100 600 s → 2 `probe_d10` NPU d10 **600 s** (R-skin 이면 해제에 수 분 [P-시뮬 130~180 s]) · Σ **1260 s**
- `py tools\npu_chain.py validate` (18:22): segment_count 3 · total 1260 · **canonical SHA-256 `d477c29791378a8df5f9d610f655a76bc5387227f15056a9846731b06a870a61`**
- orchestrator `--dry-run` (18:23, `--serial 0.0.0.0:0` 가짜값, 출력은 스크래치 — 커밋 안 함): exit 0 · `config/npu/chain/chain_id m1_recovery_npu_v1` · `total_duration_s 1260` · `max_inference_spans 1500000` · 1 슬롯 `npu-d100-r001`
- 명령 (`프롬프트_밤측정_1002.md` 7단계 M1 원형에서 체인 파일 · `--duration 1260` · 상한 · 폴더명 · 기한 인자만 바꿈):

```bat
py tools\d1_experiment_orchestrator.py --serial <IP:PORT> --npu-chain tools\chains\m1_recovery_npu_v1.json --duration 1260 --npu-max-inference-spans 1500000 --runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --logger-keep-files-open --analyze-timeout-seconds 600 --cooling-min-seconds 600 --mode pilot --resources NPU --warmup 20 --repeat 1 --seed <밤 프롬프트 seed> --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3 --output-dir C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_M1_npu_1003
```

- 기한 인자 (절차서 `측정절차_연쇄모드_0928.md` §4 식) [E]: 예상 추론 ≈ NPU d100 600 s **71만** [P 6b H 712k·710k] + d10 660 s × 10 % × ~1,250/s ≈ **8만** [E] ≈ 79만 → 상한 1,500,000 의 53 % · 러너 ≈ 60 + 1260 + flush(~80만 줄, 6b 83만 줄 ~1분 [E]) ≈ 1,400 s → **2700 (1.9×)** · logger 배출 80만 줄 ÷ 843~10,587 줄/s = 76 s~16 분 → **1800** (6b H 와 같음) · analyze 80만 ÷ 201k × 16.8 s × 2.8 ≈ 190 s → **600** · 냉각 최소 600 (M1 과 같음). 배터리 ≈ 6b H 팔(660 s) 5~6 %p + d10 660 s ~1 %p ≈ **7 %p** [E] · 시간 ≈ 0.6 h (냉각 포함)

## 1. 공통 규칙 (M1M2 v1 §1 글자 그대로)

구간 창 = `segment_start.detail.start_ns` ~ `segment_end.detail.end_ns` · 전환 창 제외 · 지연 = 러너 JSONL `latency_ns` (write+run+read) · 10 s 칸 = 구간 시작 기준 [10k, 10k+10) 에 시작한 추론 전수 중앙 · 온도 = thermalservice HAL 1 s 표본 · `formal_npu_valid` False 정상 · 공변량(설치본 · SOC 구간별 · 실내 온도 시작·끝 · 시작 SKIN 밴드 29.1~31.6).

## 2. 판정 (먼저 숫자로)

- **`ref_d10`** = 구간 0 추론 전수 지연 중앙. **A3 기준 안정** = 구간 0 의 10 s 칸 배율이 전부 ±5 % 안 (NPU d10 은 어느 엔진으로도 잰 적 없다 — 불안정이면 "기준 불안정" 표시하고 판정은 한다)
- **완전 회복** = 구간 2 의 첫 10 s 칸 k 로서 **칸 k 와 뒤 3칸(40 s)의 중앙이 모두 ≤ `ref_d10` × (1 + δ)**, 결과 = 10k s. **δ = 0.03** — 근거 [E, 지금 정함]: 이미 본 가열 자료의 1계단 폭 +8.5~+9.3 % (N1300 310~460 s 1.085~1.0997 · 6b H 1계단 수준 1.086~1.091 [P `스로틀모형_v1.md` §3 ③ level]) 의 **1/3**. 식은 NPU d100 10 s 칸 잡음은 RMS 0.232 % · 최대 ×1.004 [P 스로틀곡선_사전등록_0928 1-1] 로 δ 의 1/13~1/7 이라 잡음으로 δ 를 넘지 않는다. d10 의 잡음은 `미확인` → A3 가 잡는다. 구간 2 끝(마지막 검정 가능 k = 56)까지 없으면 **"570 s 안 미회복 (오른쪽 중도절단)"**
- **둘째 계단 해제는 정의하지 않는다** — 두 계단 수준 차가 +9 % vs +12~13 % 로 **~3 %p = δ 와 같다**. 칸 잡음·SOC 표류가 그 안에 들어와 "2계단에서 1계단으로 내려왔다" 와 "1계단 수준 안 흔들림" 을 못 가른다. 대신 **기술만**: 칸 배율 ≤ 1.06 이 된 첫 칸(= "1계단 수준 이하")을 적되 판정으로 쓰지 않는다
- **모양** (M1M2 v1 §2 와 같음): 첫 칸 → 회복 칸 감소의 ≥ 50 % 가 한 칸 사이 → 계단형, 아니면 점진형
- 가열 구간(1): 1-1 진입(+10 %) · 1계단 시각(+4.5 % 유지 첫 칸, `fit_throttle_v1.py step1_time` 과 같은 정의) · 540~600 s 배율 · 진입 온도 → 6b H1·H2·N1300 과 나란히 (3런 → 4런째). **v1 예측과의 비교 규칙**: 1계단·2계단 시각 오차 > 20 s 면 "AP 노드 하위모형 기각 (홀드아웃)" · 진입 SKIN 39.8~40.0 · AP 44.2~44.3 안이면 "트리거 = 온도대 유지"

## 3. 해제 순간의 SKIN·AP 와 세 가설 — 규칙을 미리

해제 칸 k 의 시작에 가장 가까운 HAL 표본 (SKIN_k · AP_k). 1계단 문턱 [P 3런]: **SKIN ≈ 38.3 · AP ≈ 42.5~42.7** (N1300 290~310 s · 6b 230~250 s).

| 가설 | 예측 | 기각 규칙 (하나만) | v1 변형 예측 [P-시뮬, 시작 29.5/30.5] |
|---|---|---|---|
| **H-skin** 해제 ≈ SKIN 이 1계단 문턱 아래 | SKIN_k ≤ 38.3 + 0.5 · 해제까지 수 분 | **SKIN_k ≥ 38.8 이면 기각** | R-skin: 해제 130 / 180 s, SKIN_k 37.3 / 37.4 |
| **H-ap** 해제 ≈ AP 가 1계단 문턱 아래 | AP_k ≤ 42.5 + 0.5 · 탐침에서 AP 는 30 s 안에 46 → 41 로 떨어진다 [P-시뮬 · P M1 GPU AP −2.8 ℃/20 s] → 해제 ≤ 40 s | **AP_k ≥ 43.0 이면 기각** | R-fast(T_off 42.0): 해제 40 / 50 s, AP_k 40.2 |
| **H-timer** 온도와 무관하게 수십 초 안 | 해제 ≤ 60 s · SKIN_k 는 아직 39~40 (문턱 위) | 해제 > 60 s 이면 기각 | (R-fast 와 같은 시각) |

- **미리 선언**: 해제가 ≤ 40 s 면 **H-ap 와 H-timer 는 못 가른다** (둘 다 그 범위를 예측) — "H-skin 기각, H-ap/H-timer 보류" 로만 적는다. 가르려면 AP 가 문턱 위에 더 오래 머무는 설계(가열 뒤 d50 탐침 등)가 필요 — 다음 밤
- 해제가 100~200 s 이고 SKIN_k ≈ 37~38.8 이면 H-skin 유지 (R-skin). 해제 40~100 s 사이면 세 가설 중 어느 것도 사전 예측과 맞지 않는다 → "미분류" 로 적고 사후 가설은 [E]
- 2런 (A안 ×2): 두 런의 해제 시각 차 ≤ 20 s 면 "재현", 아니면 "1런씩 보고"

## 4. 반대 해석 (M1_결과_1002 §1 그대로 + 추가) — 결과 전에 목록

1. 회복이 온도가 아니라 **시간(정책 타이머)** 으로 온다 → §3 규칙 (≤ 40 s 면 못 가름 선언)
2. 탐침 d10 도 부하다 — "10 % 부하 아래의 회복" 이지 idle 회복이 아니다 → 조건으로 적는다
3. **NPU d10 은 1 s 가동마다 클럭이 다시 오른다** (가동 1 s 안의 첫 추론들이 느릴 수 있다 [E]) → 같은 d10 인 `ref_d10` 과만 비교 · A3 로 d10 기준 자체의 안정성을 본다 · 보조: 각 가동 초의 첫 10 추론 중앙 vs 나머지 (기술만)
4. 가열 600 s 중 SOC 하락이 전력 한도를 바꿨다 → 구간별 SOC 기록, 2런 비교
5. 실내 온도 변화 → 시작·끝 기록
6. **NPU 는 1계단 폭이 δ 의 3배라 "완전 회복" 이 1계단 해제와 같다** — 2계단만 풀리고 1계단이 남는 상태는 δ 로 못 잡는다 (§2 둘째 줄 이유) → 기술만
7. 전환 창(NPU→NPU, 모델 재사용, warmup 20) 뒤 탐침 첫 칸이 전환 잔재일 수 있다 → 첫 칸만으로 판정하지 않는다 (칸 k + 뒤 3칸)

## 5. M1-GPU 2런째

- 판정 = `M1M2_사전등록_v1.md` §2 **그대로** (새 사전 등록 없음). v1 예측(`v1_예측_밤1003.md` §1)과 비교하는 규칙 한 줄: **회복 시각 실측이 예측 30 s 와 ±10 s 안(20~40 s)이고 계단형이면 "v1 ⑥ 유지(2런)", 아니면 ⑥ 기각** · 가열 진입·배율은 ±10 s·±10 % (v1 §5)
- 1런째(20 s · 계단형)와 2런째 차 ≤ 10 s 면 "재현"

## 6. 금지

- 결과 보고 δ·규칙을 바꾸지 않는다 · 폰·adb 는 밤 세션 · 체인 JSON 은 이 파일 하나만 · 실제 주소·시리얼 금지
