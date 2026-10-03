# EffNet × NPU d100 600 s 결과 — 2026-10-04 밤 (EfficientNet-Lite0 AOT, 1런)

> 판정 = 고정 `sim\throttle_curve_0928.py` (SHA `31822678…`) `analyze --duration 600 --duty 100` (`--equilibrium` 없이) + `sim\night1003_judge_npu600.py` SHA `cc7d1559302dfa947b33cb216cbcb29c47a4d65c074eca0f918997d9e180f91f` (03:29:54, selftest 16/16 — N1300_1002 진입 470 · 1계단 300 재현) · 사전 등록 `sim\NPU600_EffNet_N1300r2_사전등록_v1.md` · 커밋 `5d7681a` 03:31:41.
> EffNet 규칙: 1계단 SKIN 38.3 · AP 42.5 / 2계단 SKIN 40.0 · AP 44.2 의 ±0.5 ℃ 안(넷 다) → "계단 온도대 = 모델 무관 (1런)", 밖 → "모델 의존 후보".
> 표기: [P] 실측 · [D] 인용 · [E] 추정 · `미확인`. 원시 `D1Check_v4\results\S26_EffN600_npu_1003` (git 무시). 출력 `sim\out_1003\EffN600_analyze.json` · `EffN600_effnet_rule.json`.

## 1. 결과 — **FAILED (안전 비상 중단) — 인용 금지** [P `results\S26_EffN600_npu_1003\experiment_manifest.json`]

- 게이트 07:42:08 대기 0 s (HAL SKIN 31.6 · AP 30.6 · BAT 29.8 · SOC 48) · orchestrator 07:43:29 시작 · safety_preflight ok (BAT 29.5 · SOC 48 · plugged 0) · stable 컨디셔닝 07:48:21 통과 · 러너 시작 07:48:22 (baseline 60 s → load ≈ 07:49:22~).
- **07:59:13 `emergency_runner_force_stop` → `EmergencyAbort: emergency safety abort during load from sparse_dumpsys: battery_temperature_emergency`** (BAT 기본 한도 42 ℃ [D 1002 §6 "BAT 42 기본"]). 호스트 감시 CSV: 07:58:43 BAT 41.9 · 07:58:58 **42.0** · 07:59:13 **42.2** (SKIN 42.8 · AP 47.4 · status 2) — 끝 thermalservice 표본 BAT 42.2 · SKIN 42.9 · AP 47.5 · PA 48.6. 중단 시각은 load 시작 ≈ 591 s 뒤 — **600 s 부하의 마지막 ~9 s 를 남기고** 끊겼다 [E ±5 s].
- 러너 JSONL 회수 없음 (`runs\…\gpu\` 비어 있음, failure_cleanup 만) → **지연·계단 자료 없음**. 사유가 러너 쪽(비상 중단)이므로 캡처 결손 런 규칙 해당 없음 — **FAILED, 인용 금지** (프롬프트 규칙).
- 호스트 SKIN 감시(45 ℃) 발동 0 · orchestrator 가 먼저 멈췄다 (설계대로 — npu-runner force-stop 확인: 중단 뒤 `pidof npurunner` 없음, 08:00 SKIN 40.3 · BAT 40.3 로 식는 중).
- **이 밤 안전 비상 1회** (세션 종료 조건 2회 미달). 꼬리(8단계)는 SOC 42 < 46 으로 어차피 조건 밖.

## 2. 왜 BAT 가 42 에 닿았나 — 기술 (반대 해석 전) [E]

- 어젯밤 N1300 (MobileNet AOT d100 1300 s): BAT 최고 40.9 · 600 s 시점 BAT ≈ 38~39 [P NPU1300_결과]. 오늘 M1-NPU (a)(b) 600 s 끝 BAT 41.6 / 41.7 (status 2) — **MobileNet 도 오늘은 BAT 41.7 까지 올랐다** (어젯밤보다 ~2 ℃ 높은 시작 BAT 27.8~29.4 · 세션 후반 잔열 [E]).
- EffNet AOT 는 MobileNet 보다 추론당 무겁고(C2 ×1.10 지연) 전력이 같거나 높을 수 있다 (`미확인`) → 같은 600 s 에 BAT +0.5 더 → 42 도달. 시작 BAT 29.8 (게이트) · 세션 7번째 시간대(07:4x) · SOC 48.
- **판정 불가**: 계단 온도대 비교(§2 규칙)·1-1 진입·끝 60 s 배율 모두 자료 없음 → "판정 불가 (자료 없음 — 안전 중단)". EffNet × NPU 600 s 는 **다음 밤** — BAT 시작 ≤ 28 (밤 앞쪽) 또는 길이 450 s 로 (사전 등록 `_v2` 필요).

## 3. 어젯밤 설치본·오늘 다른 칸과의 정합

- NPU d100 600 s 가 **BAT 42 근처**까지 가는 것은 오늘 세 런(M1-NPU a·b 41.6~41.7 · EffNet 42.2)이 공통 — `--emergency-max-android-thermal-status 3` 는 안 걸렸고(status 2) **BAT 42 기본 한도**가 먼저 걸렸다. 다음 밤 NPU 600 s 급 칸은 BAT 한도와 시작 BAT 를 사전 등록에 적을 것 (P3/영훈).
