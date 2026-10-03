# GPU 페이싱 사전 등록 — v1 (2026-10-04 03:2x KST, 5단계 측정 전 동결)

> 질문: 조여진 GPU 가 d10 으로 **60 s 쉰 뒤** d100 으로 돌아오면 **얼마나 빨리 다시 조이나** (M1 의 "유예" 비용 · v1 이 못 낸 "뜨거운 재조임"). 1런 · pilot.
> 이 파일이 든 커밋 SHA·시각이 동결 증거. 측정 뒤에는 고치지 않는다 — 바꿔야 하면 `_v2`. 표기: [P] 실측 · [D] 인용 · [E] 추정 · [P-시뮬] 모형 출력 · `미확인`.
> 근거: `프롬프트_밤측정_1003.md` 1-B-2 · `M1M2_사전등록_v1.md` §2 (회복 규칙) · `스로틀곡선_사전등록_0928.md` 1-1 (진입) · `스로틀모형_v1.md` §6 (v1 이 못 낸 것) · `M1_결과_1002.md` · `M2_결과_1002.md`.

## 0. 체인 [P]

- 새 파일 **`D1Check_v4\tools\chains\gpu_pacing_v1.json`** — `m1_recovery_gpu_v1.json` 을 복사해 구간만 바꿈 (모델 `models/mobilenet_v1_1.0_224.tflite` · `lcg-unit` · `gpu_precision FP32` 요청 · per_segment 그대로). 기존 체인 파일 무변경.
- 구간: 0 `cold_ref_d10` GPU d10 60 s → 1 `heat_d100` GPU d100 600 s → 2 `rest_d10` GPU d10 60 s → 3 `reheat_d100` GPU d100 300 s · **Σ 1020 s**. chain_id `gpu_pacing_v1`. (P1b-2 는 끝나지 않았다 — 일정은 프롬프트 1-B-2 그대로, 바꾸지 않는다)
- `py tools\npu_chain.py validate` (03:1x): segment_count 4 · total 1020 · **canonical SHA-256 `1aa06fd8418699ba337c7a160a2a5bc6a1b0dccf4d52d8368d487d62c61e6b5b`**
- orchestrator `--dry-run` (03:1x, 실제 `$env:ANDROID_SERIAL`, 출력 스크래치 — 커밋 안 함): exit 0 · `chain_id gpu_pacing_v1` · `total_duration_s 1020` · `max_inference_spans 400000` · 체인 SHA 위와 같음 · 1 슬롯 `npu-d100-r001`

## 1. 명령 (5단계) — `D1Check_v4` 폴더에서

```bat
py tools\d1_experiment_orchestrator.py --serial <IP:PORT> --npu-chain tools\chains\gpu_pacing_v1.json --duration 1020 --npu-max-inference-spans 400000 --runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --logger-keep-files-open --analyze-timeout-seconds 600 --cooling-min-seconds 600 --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261003 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3 --output-dir C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_GPUpace_1003
```

### 기한 인자 — `측정절차_연쇄모드_0928.md` §4 식으로 다시 계산 [E]

| 인자 | 계산 | 값 (M1 출발점과 같음) |
|---|---|---|
| 예상 추론 수 | 구간 1 GPU d100 600 s: 식은 ~80 s 동안 ~400/s (2.5 ms [P M1 `ref30 2.499 ms`]) ≈ 32k + 조여진 520 s ~200/s (5.1 ms [P M1 ×2.04]) ≈ 104k → ~136k · 구간 3 d100 300 s (뜨거운 시작 ~200/s) ≈ 60k · d10 두 구간 120 s × 10 % × ~400/s ≈ 5k → **≈ 200k** (M1 1200 s 가열 실측 262,222 [P M1_judge] 의 비율로도 ~130k+60k) | 상한 **400,000** (2.0×) |
| `--runner-timeout-seconds` | 60 baseline + 1020 + flush (~200k 줄, 6b 83만 줄 ~1 분 [E] 비례 ~15 s) ≈ 1,100 s → ×1.8 ≈ 1,980 s | **2700** (2.5×, M1 값 유지) |
| `--logger-exit-timeout-seconds` | 200k 줄 ÷ 843~10,587 줄/s [P 1-7-2] = 19 s~4 분 | **1800** (M1 값 유지) |
| `--analyze-timeout-seconds` | 200k ÷ 201k × 16.8 s × 2.8 ≈ 47 s | **600** |
| `--cooling-min-seconds` | logger 배출을 냉각이 흡수 (0928 방식) | **600** |
| 시간·배터리 | 1020 s + 안정 대기·baseline·냉각 600·분석 ≈ 0.55 h · GPU d100 600 s ≈ 5~6 %p [P M2 H 팔 660 s 5~6 %p] + 300 s ≈ 2.5 + d10 ≈ 0.5 → **~8 %p** (프롬프트 표 ~6 %p) | SOC 조건 ≥ 41 (프롬프트) |

## 2. 판정 (숫자로 지금) — 고정 스크립트 `sim\night1003_judge_pacing.py`

- **SHA-256 `516116b4297b5a036250d076b31cfe010c22d1e7a398944f662fd97724e083c7`** · 고정 **2026-10-04 03:21:01 KST** · 양방향 합성 시험 **16/16 PASS** (`sim\out_1003\night1003_judge_pacing_selftest.txt`) · 레포 사본 `s26\tools\night_1003\`. 구간 추출은 `m1m2_judge_1002.py` (SHA `ea282d4a…`) import — 복사·수정 없음. 손 계산으로 판정하지 않는다.
- **`ref_d100`** = 구간 1 의 처음 30 s 추론 전수 중앙 (식은 d100 — 1-1 과 같은 정의). `ref_d10` = 구간 0 전수 중앙, A3 (10 s 칸 ±5 %) 로 기준 안정성 표시.
- **구간 1 진입** = 1-1 (+10 %, 그 칸 + 뒤 3칸) → M1 1002 (80 s) · M2 H1·H2 (60~100 s) 와 나란히 — **재현성, 기술만**.
- **구간 2 회복** = `M1M2_사전등록_v1.md` §2 규칙을 60 s 탐침에: ref = 구간 0 `ref_d10`, 칸 k + 뒤 3칸 ≤ ×1.10 → 10k s, **마지막 검정 k = 2**. 없으면 **"검정 가능 범위(≤ 20 s) 안 미회복 — 중도절단"**.
- **재조임 시각** = 구간 3 의 첫 10 s 칸 k 로서 **칸 k 와 뒤 3칸이 모두 ≥ `ref_d100` × 1.10** → 10k s. 첫 칸부터면 **"즉시(0 s)"**, 300 s 안에 없으면 **"재조임 없음"**.
- **분류 (미리)**: 재조임 **≤ 20 s → "60 s 휴지로는 재조임을 못 늦춘다"** · **≥ 60 s → "60 s 휴지가 재조임을 늦춘다 (페이싱 후보)"** · **30~50 s → "중간"**.
- **보조 (기술만)**: 재조임 칸의 SKIN·AP · 구간 3 의 240~300 s 배율 vs 구간 1 의 540~600 s 배율 · 구간 2 끝 SKIN·AP · 구간별 시작 SOC · 전환 창 길이.
- 1차 조건 = `validate_chain_result` valid (슬롯 재시도 규칙 1회). 캡처 결손 런 규칙 적용. 출력 `sim\out_1003\GPUpace.json` (결정적).

## 3. 반대 해석 (결과 전 목록)

1. **재가열 시작 온도가 식은 출발보다 높아 일찍 조이는 것은 측정하려는 기제 자체다** — 온도로 설명되는지(재조임 칸 AP ≈ 42 근처인가 [P 6b 뜨거운 GPU 10 s 뒤 ×2 · M2 GPU 피해자 시작 SKIN 41]) 와 시간으로 설명되는지를 같이 적는다
2. d10 휴지는 idle 이 아니다 — "10 % 부하 아래 60 s 휴지" 조건
3. 전환 창 잔재 — 첫 칸만으로 판정하지 않는다 (칸 k + 뒤 3칸)
4. SOC 하락 — 구간별 SOC 기록 (이 칸은 세션 후반, SOC 40 %대 [E])
5. 1런 · 이 설치본 · 실내 온도 1회 기록

## 4. 모형 예측 — v1 (P1b-2 미완 → 이 세션이 d1sim 코드 수정 없이 산출, 5단계 전 동결) [P-시뮬]

- 스크립트 `sim\predict_pacing_v1_1003.py` (SHA `4940907b5412b4e7bd59f668e4b2810635dbfbd667613d0cfe6de306b7a14a80`) — `d1sim.throttle_v1` 과 `d1sim/profiles/throttle_v1_*.json` 을 **읽기만** (predict_night_1003.py 의 params()·duty_flags 와 같은 방식), 모형 = v1 M-P r3 커밋 `3050e09` (미완). 출력 **`sim\out_1003\night_1003_prediction_v1_pacing.json`** SHA `b4ada83969b0ac5a4efb337e1fef51e224f4fab4a792ec7859a359e2215767f8` (03:21:01, 레포 사본 `s26\results\night_1003\`).
- P1b-2 의 `v1_예측_페이싱_1003.md` · `v2_예측_밤1003.md` 는 **없다** (0단계 확인) → v2 페이싱 대조 없음.

| 칸 | 시작 29.5 | 시작 30.5 | 이 차이면 v1 의 이 부분이 틀린 것 (v1 §5 기준) |
|---|---|---|---|
| 구간 1 진입 (1-1) | **70 s** | 70 s | > ±10 s → GPU CM 제어기 진입 |
| 구간 1 540~600 s 배율 | ×1.962 | ×2.084 | > ±10 % → 깊이 |
| 구간 1 끝 SKIN · AP · status | 38.6 · 41.2 · 0 | 38.9 · 41.2 · 0 | SKIN > ±0.5 → 열 모형 |
| 구간 2 (휴지 60 s) 회복 | **검정 범위(≤ 20 s) 안 없음 — 중도절단** (모형 회복 30 s, M1-GPU 예측과 같음) | 같음 | 실측이 ≤ 20 s 면 v1 T_off placeholder 가 낮은 것 (M1-GPU 와 같은 결론) |
| 구간 2 끝 SKIN · AP | 36.6 · 36.7 | 37.1 · 37.2 | 기술 |
| **재조임 시각** | **40 s** (SKIN 40.4 · AP 46.2) | **30 s** (40.3 · 45.5) | > ±10 s → **v1 적분 제어기 K** (식은 진입 60~90 s 와 뜨거운 재진입 10 s 를 한 K 로 못 낸다 — `스로틀모형_v1.md` §6). 실측 ≤ 20 s 면 v1 은 재조임을 늦게 내는 것 (반홀드아웃 6b "뜨거운 재조임 10 s" 와 같은 방향) |
| **분류** | **"중간"** | "중간" | 실측 "못 늦춘다" 또는 "페이싱 후보" 면 틀림 |
| 구간 3 240~300 s 배율 | ×1.986 | ×2.111 | > ±10 % → 깊이 |
| 구간 3 끝 SKIN · AP | 38.8 · 41.3 | 39.1 · 41.3 | 기술 |

- 비교 열 = 실제 시작 SKIN 에 가까운 쪽. 시작 SKIN 이 [28.3, 31.6] 밖이면 "적용 범위 밖 (unsupported)". cmp = `night1003_judge_pacing.py cmp --pred … --judge …`.

## 5. 금지

- 결과 보고 규칙·문턱·분류 경계를 바꾸지 않는다 · 체인 JSON 은 이 파일 하나만 (기존 무변경) · 실제 주소·시리얼 금지 · 사전 등록 커밋 전에는 5단계를 시작하지 않는다
