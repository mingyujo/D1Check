# C1-probe 사전 등록 v1 — GPU d100 600 s × 2 (느린 열 모드가 있는가)

> **작성·동결 2026-09-27 02:11 KST, C1-probe 실행 전.** 이 시각에 C1-probe 데이터는 한 줄도 없다 (C6 진단 스모크 실행 중).
> 결과를 본 뒤 이 문서를 고치지 않는다. 고칠 일이 생기면 `[사후]` 표시를 달고 원문을 취소선으로 남긴다.

## 1. 질문

`열구속_외삽_0926.md` 에서 30 ℃ 시작 → 38·42 ℃ 도달 시간이 두 외삽 사이에서 갈린다 (기울기 유지 2~6 분 vs 1차 fit ∞).
차이는 60 s 로는 안 보이는 **느린 모드**(배터리·섀시)의 크기다. 600 s 연속 부하 2런으로 그 존재 여부만 가른다.

## 2. 대상과 명령 (고정)

- GPU (benchmark-runner, LiteRT 1.4.2 Interpreter, `gpu-fp32-strict-v1` — 9/14 formal strict 80런과 같은 프로파일), duty 100, `--duration 600`, repeat 2, pilot 모드
- `--duration 600` 수용 확인 [D]: orchestrator `validate_cli` 가 1..3600 을 허용 (`d1_experiment_orchestrator.py` 4865행). 기본값이 이미 600
- 비교 기준(9/14 strict)과 다른 점 — 전부 기록용이며 판정에 쓰지 않는다:
  - `--accuracy-preflight optional` (pilot, 절차서 C9 와 같은 방식)
  - `--stability-timeout-seconds 2400 --cooling-timeout-seconds 2400` — 기본 900 s 는 600 s 부하 뒤 냉각 안정에 모자랄 수 있다. `stable` 의 의미(60 s 창 범위 ≤ 0.5 ℃ · 기울기 ≤ 0.2 ℃/min)는 그대로
  - `--emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3` → **thermal_status ≥ 4 에서 orchestrator 가 자동 중단** (기본은 감시 꺼짐). 배터리 온도 비상 42 ℃ 는 기본값 그대로
  - 호스트 감시 스크립트가 15 s 마다 `dumpsys thermalservice` 로 SKIN·AP·status 를 기록하고, **SKIN ≥ 45.0 ℃ 면 benchmark-runner 를 강제 종료**한다 (그 런은 안전 중단으로 기록). 이 폴링의 부하는 기록한다

```
py tools\d1_experiment_orchestrator.py --serial <IP:PORT> --mode pilot --resources GPU --gpu-profile gpu-fp32-strict-v1 --accuracy-preflight optional --duty-cycles 100 --duration 600 --warmup 20 --repeat 2 --seed 20260927 --start-policy stable --cooling-policy stable --stability-timeout-seconds 2400 --cooling-timeout-seconds 2400 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3 --output-dir C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_C1probe_gpu600_0927
```

- 시작 게이트: **SOC ≤ 90 %** 확인 후 시작 (비충전, 무선 adb). 30 % 게이트는 그대로

## 3. 비교 기준 — 기존 실측에서 지금 뽑은 값 [P]

출처: `results\S26_formal_strict` (9/14, GPU d100 5런), `s26\tools\s26_thermal_fit.py` 를 이 시각에 돌린 값. SKIN, load 0~60 s 1차 fit.
ΔT∞ = 60 s 상승 / reach60 (= 1차 fit 점근 상승).

| 슬롯 | τ (s) | 60 s 상승 (℃) | reach60 | **ΔT∞ (℃)** | 끝 기울기 40~60 s (℃/min) |
|---|---:|---:|---:|---:|---:|
| gpu-d100-r001 | 35.4 | 5.5 | 0.816 | 6.74 | 3.46 |
| gpu-d100-r002 | 35.4 | 5.7 | 0.817 | **6.98** | 3.51 |
| gpu-d100-r003 | 33.5 | 5.7 | 0.833 | 6.84 | 3.64 |
| gpu-d100-r004 | 34.6 | 5.4 | 0.823 | 6.56 | 3.27 |
| gpu-d100-r005 | 32.4 | 5.3 | 0.844 | 6.28 | 3.47 |

**ΔT∞ 범위 6.28~6.98 ℃, 최대 6.98 ℃** (`열구속_외삽_0926.md` 입력 범위 6.3~7.0 ℃ 와 일치).

## 4. 측정량 정의 (계산 전 고정)

런마다 `exports-v2\thermal_timeseries.csv` 의 SKIN, `phase == load`, `load_relative_s` 사용 (기존 도구와 같은 정의):
- **600 s 상승** = 마지막 load 표본 SKIN − 첫 load 표본 SKIN (`s26_thermal_fit.py` 의 `load_rise` 와 같은 식)
- **끝 기울기** = `load_relative_s ∈ [580, 600]` SKIN 의 OLS 기울기, ℃/min
- 스로틀 시점 = load 중 `thermal_status` 가 처음 ≥ 1 이 된 `load_relative_s` (텔레메트리 표본 기준, 호스트 감시 로그로 교차 확인)

## 5. 판정 (수치 고정)

| 판정 | 조건 |
|---|---|
| **느린 모드 있음** | 600 s 상승 > **7.98 ℃** (= ΔT∞ 최대 6.98 + 1.0) — **두 런 모두** |
| **1차 fit 이 맞음** | 600 s 상승 ≤ 6.98 ℃ (ΔT∞ 범위 상한 이하) **그리고** 끝 기울기 \|·\| ≤ 0.2 ℃/min (§11-1 동결 기준) — **두 런 모두** |
| **판단 보류** | 두 런이 갈리거나, 위 어느 쪽도 아님 (예: 6.98 < 상승 ≤ 7.98, 또는 상승은 범위 안인데 기울기 > 0.2) |

- 600 s 상승이 ΔT∞ 범위 **하한 6.28 ℃ 미만**이어도 "1차 fit 이 맞음" 쪽 조건(≤ 6.98)에 포함한다 — 느린 모드가 없다는 방향이므로
- **스로틀**: 판정은 스로틀 여부와 무관하게 위 수치로 낸다. 단 스로틀(status ≥ 1, 또는 GPU 주파수 저하가 지연 급증으로 보이는 시점)이 걸렸으면 그 시점 이후는 등온·정전력 가정이 깨지므로 **gain 산정에서 제외**하고, "느린 모드 있음/없음" 판정에 "스로틀 이후 전력 변화 포함" 각주를 단다. 스로틀 온도·시점은 별도 결과로 적는다
- **안전 중단 (thermal_status ≥ 4 또는 SKIN ≥ 45 ℃)** 으로 600 s 를 못 채운 런은 판정에 쓰지 않는다. 대신 중단 시점 SKIN 이 이미 7.98 ℃ 상승을 넘었으면 그 사실을 "느린 모드 있음 쪽 증거"로 별도 기록한다 (판정 표에는 넣지 않음)

## 6. C1(장시간 열) 결정 규칙 (미리 고정)

- **느린 모드 있음** → C1 필요. 축소안 C1a(GPU·NPU d100 × 1800 s × 2) 로 느린 τ 를 식별하는 것을 제안
- **1차 fit 이 맞음** → 전체 C1 불필요. 38·42 ℃ 는 30 ℃ 시작 d100 연속으로 "도달 못 함" 쪽을 채택 (단 34 ℃ 시작 분기는 그대로)
- **판단 보류** → C1a 1 조건(GPU d100 1800 s × 1) 만 추가

## 7. 42 ℃ 도달 여부 답 (규칙)

30 ℃ 근처 시작 기준, 600 s 안 SKIN 최고값 ≥ 42 ℃ → "d100 10 분 안에 42 ℃ 도달" [P]. 아니면 600 s 시점 끝 기울기로 외삽한 도달 시간을 [E] 로만 적는다.

## 8. [추가 2026-09-27 02:24 KST — C1-probe 데이터 전, §1~7 불변] 절대 온도 시작 게이트

- 시작 직전: plugged == 0 · SOC 30~90 % · HAL SKIN ≤ 32.0 ℃ · AP ≤ 32.0 ℃ · BAT ≤ 30.0 ℃. 못 넘으면 idle 냉각·2 분마다 재확인, 대기 시간 기록 (측정절차_잠금해제_0926.md §0)
- 각 런 load_start SKIN 이 기존 formal 밴드 29.1~31.6 ℃ 밖이면 그 런에 표시한다. 판정 수치(§5)는 상승량이라 시작 온도로 바꾸지 않는다
- 온도는 Current temperatures from HAL 만. Cached temperatures(옛 값 고정)는 쓰지 않는다

## 9. [정정 2026-09-27 02:48 KST — C1-probe load 데이터 전] preflight off

- §2 의 ~~`--accuracy-preflight optional`~~ → **`--accuracy-preflight off`**. 이유: 0927 규칙(측정절차 §0) — preflight 가 폰을 데울 수 있고, C1-probe 는 열 pilot 이라 정확도 검증이 목적이 아니다
- 02:48:36 에 optional 로 한 번 띄웠다가 preflight(약 10 s)만 끝난 상태에서 02:48:46 중단 → `results\S26_C1probe_gpu600_0927_ABORTED_0248` (부적격, 보존). load 슬롯은 시작되지 않았다
- 재실행 전 온도 게이트를 다시 통과한다. 나머지 §1~8 불변
