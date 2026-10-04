# EffN420 결과 — 2026-10-05 밤 (EfficientNet-Lite0 AOT × NPU d100 420 s, CompiledModel, run-only span)

> **판정 스크립트 동결 (결과 열기 전)**: `sim\night1004_judge_effn420.py` SHA-256 `ff991d1ca56b0a71a4c1381df2c8fc62752cf69d516f07be227620aff77d0a0e` (고정 2026-10-05 01:43, selftest 15/15) — `night1003_judge_npu600.py` (`cc7d1559…`) import → 고정 `throttle_curve_0928.py analyze --duration 420 --duty 100` (`31822678…`, **--equilibrium 없이**) · 커밋 `bc2bac7` 01:43:53. **비교 범위는 스크립트 고정 전에 `freeze_1004.txt` 에 먼저 적었다** (MobileNet 계단 진입 [최소, 최대] ± 0.3 ℃).
> 사전 등록 `sim\밤1004_사전등록_v1.md` §7 (= `NPU600_EffNet_N1300r2_사전등록_v1.md` §2 규칙의 `_v2`, `c80f9e1`). 명령 = v1 §0 7단계 명령에서 `--duration 420` · `--seed 20261004` · 폴더만.
> 표기: [P] 실측 · [D] 인용 · [E] 추정 · `미확인`. 원시 `D1Check_v4\results\S26_EffN420_npu_1004` (git 무시). 판정 `sim\out_1004\EffN420_analyze.json` · `EffN420_effnet_rule.json` · 범위 `EffN420_mobilenet5_range.json`.
> 모형 예측 없음 (unsupported — EffNet NPU 전력 자료 없음, P1c 동결 그대로). 자료의 역할: pilot·개발 자료.

## 0. 한 줄 (조건부 — 1런, 시작 SKIN 31.0)

EffNet AOT × NPU d100 420 s: **1계단 140 s (SKIN 37.6 · AP 41.7) · 2계단 (1-1 진입) 280 s (SKIN 39.8 · AP 44.0)** — 네 값 모두 MobileNet 범위 안 (1계단 SKIN [37.3, 38.6] · AP [41.4, 42.9] · 2계단 SKIN [39.5, 40.3] · AP [43.7, 44.6]) → **"계단 온도대 = 모델 무관 (1런)"** [P]. 10/4 밤 600 s 판은 BAT 42.2 비상 중단이었고, 이번 420 s 판은 끝 BAT 40.4 로 완주했다.

## 1. 실행 · 조건 [P]

- 게이트 05:13:25 (대기 0 s · HAL SKIN 31.3 · AP 30.2 · BAT 29.5 · status 0 · SOC 50) → 최종 dry-run exit 0 · `model_expected` SHA `311e4aac…` 일치 → orchestrator 05:13:25 ~ 05:39:31 KST (0.44 h; 예산 0.35 h) [P `cell_EffN420_log.txt`]
- 슬롯 `completed` · attempts 1 · **valid** · failed_checks 없음 · `duration_complete` · load 420.000 s · 추론 **453,913** (1,081 /s; 상한 1 M 의 45 %) · 안전 비상 **0** · 호스트 SKIN 감시 발동 0
- run_metadata: `model_sha256` **`311e4aac…`** (설치본 자산 = 체크아웃 자산 — "설치본 자산 불일치" 아님) · engine `litert-compiled-model` · LiteRT 2.2.0 · dispatch `f08656a6…` · 모델 분할 `dispatch_ops 1 · non_dispatch_ops 0 · PASS` · 입력 `lcg-rgb-127-128` · run-only span · 모델 init 99.7 ms
- 1-6 보존 5항목 **전부 OK** [P 고정 analyze]: ① duty 99.995 % ② 건수 JSONL = merged = run_summary = file_summary 453,913 ③ 텔레메트리 (d1check 432 s 에 4 s 간격 1회 — 판정 무관) ④ 자원 dispatch 1 · ENN 1 · dispatch 실패 0 · GPU/XNN 0 ⑤ 전력 plugged ≠ 0 표본 0
- load_start HAL SKIN **31.0** (밴드 29.1~31.6 안) · AP 30.0 · BAT 29.1 · 끝 SKIN 41.5 · AP 45.9 · **BAT 40.4** · status 최대 1 (282 ~ 553 s) · 실내 23 ℃ (영훈, 측정값 아님) · 비행기 모드 꺼짐 · 설치본 `5ac485e3…`

## 2. 판정 (사전 등록 §7 글자 그대로) [P `EffN420_analyze.json` · `EffN420_effnet_rule.json`]

| 항목 | 값 |
|---|---|
| ref (처음 30 s 중앙, run-only) | 0.82594 ms |
| 1계단 (+4.5 % 유지 첫 칸) · 그 HAL 표본 | **140 s** · SKIN **37.6** · AP **41.7** (status 0) |
| 2계단 = 1-1 진입 (+10 %, 칸 + 뒤 3칸) · HAL 표본 | **280 s** · SKIN **39.8** · AP **44.0** |
| 기준 범위 (MobileNet, [최소, 최대] ± 0.3 ℃) | 1계단 SKIN [37.3, 38.6] · AP [41.4, 42.9] (3런 — 6b H1·H2 는 1계단 온도가 판정 JSON 에 없어 뺐다, 사전 등록 지시대로) · 2계단 SKIN [39.5, 40.3] · AP [43.7, 44.6] (5런) |
| **규칙 결과** | **넷 다 범위 안 → "계단 온도대 = 모델 무관 (1런)"** |
| 계단 폭 (기술) | 1계단 수준 ×1.082 · 2계단 첫 120 s ×1.112 · 끝 60 s ×1.113 (MobileNet +9 % / +12~13 % / +12 % [D]) |
| 잠정 전력 (기술) | 처음 30 s 5.26 W vs MobileNet 3런 평균 5.44 W → **비 0.97** · 끝 60 s 전력 비 0.90 (4.74 W) — 단위 가정·비율만 |

- 처리율: 453,913 / 420 s = 평균 1,081 /s [P]. run-only 지연은 처음 30 s 0.826 ms → 끝 60 s 0.919 ms (×1.113) [P].

## 3. 반대 해석 (NPU600 v1 §2 목록) — 가장 강한 것부터

- **전력이 거의 같아서 온도대가 같게 나온 것일 수 있다** — 처음 30 s 전력 비 0.97. 사전 등록의 메모 "H-load 라면 전력이 다르면 진입 온도도 달라질 수 있다" 를 시험하려면 전력이 다른 모델이 필요하다. 이 1런은 "전력이 비슷한 다른 모델에서 계단 온도대가 같다" 까지만 [E].
- **1런** — 미배제. 범위는 MobileNet 런들 (1계단 3런 · 2계단 5런) 의 퍼짐 ± 0.3.
- **시각 비교가 아니다** — 1계단 140 s · 진입 280 s 는 같은 밤 NI300 (130 · 260 s, 밴드 안 시작) 과 가깝고 N50P (370 s · 없음, 밴드 아래 시작) 와는 멀다 — 시각은 시작 상태에 크게 좌우된다 (기술만).
- 시작 SKIN 31.0 (밴드 안) · SOC 50 (세션 후반) · 실내 온도 측정값 아님.
- span: run-only (N1300 · M1 과 같음, 6b H 는 write+run+read) — 온도대 비교에는 영향 작음 [E].

## 4. 10/4 밤 600 s 판과의 관계

- 10/4 밤 EffNet × NPU 600 s: **FAILED — `battery_temperature_emergency` (BAT 42.2) 부하 끝 ~9 s 전** · 자료 없음 · 인용 금지 [D `NPU600_EffNet_결과_1003.md`]. 이번 420 s 판은 끝 BAT 40.4 · status 최대 1 로 완주 — 사전 등록 §7 의 축소 (600 → 420 s) 가 의도대로 BAT 한도를 피했다 [P]. 시작 BAT 29.1 (10/4 판 29.5 [D]).
