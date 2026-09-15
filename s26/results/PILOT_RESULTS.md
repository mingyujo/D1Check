# S26 파일럿 측정 결과

기기 `SM-S942N` (Exynos 2600, `s5e9965`) · Android 16 / SDK 36
지문 `samsung/m1sksx/m1s:16/BP4A.251205.006/S942NKSS4AZHA_OKR4AZHA:user/release-keys`
모델 `mobilenet_v1_1.0_224_float`, SHA `D95B3C5E…CFBB`, LiteRT 1.4.2
측정일 **2026-09-13** · 무선 adb, 미충전

원본은 `results/`에 있고 `.gitignore`로 저장소에 올라가지 않는다. 이 문서가 요약이자
근거의 색인이다.

---

## 1. 한 줄 결론

S26에서 **CPU·GPU 측정 파이프라인이 관통**됐다. GPU는 LiteRT 내장 허용목록이
거부했으나 실제로는 전 노드가 GPU에서 실행됐고, 최고 등급으로 검증됐다.
NPU는 NNAPI 경로가 막혀 있어 별도 설계가 필요하다.

---

## 2. 실행한 런

| # | 설계 | 자원 | 종료 | 추론 수 | 부하 길이 | 폴더 |
|---|---|---|---|---|---|---|
| 1 | 스모크 (수동 UI) | CPU/4 | `count_complete` | 1,000 | 9.67 s | `results/fa3a5ee8-…` |
| 2 | 파일럿 CPU 단독 | CPU/4 | `duration_complete` | 14,094 | 60.00 s | `results/S26_cpu_60s` |
| 3 | 파일럿 (GPU 실패) | GPU | `run_error` | 0 | — | `results/S26_pilot_60s` |
| 4 | 파일럿 CPU | CPU/4 | `duration_complete` | 13,106 | 60.00 s | `results/S26_pilot_60s_1` |
| 5 | 파일럿 GPU | GPU | `duration_complete` | 20,290 | 60.00 s | `results/S26_pilot_60s_1` |

런 3은 실패 기록으로 보존한다. 근거: [`../device/12_gpu_failure.txt`](../device/12_gpu_failure.txt)

---

## 3. 지연시간

### CPU(4스레드) vs GPU — 같은 세션, 60초 지속부하

| | CPU/4 | GPU | 비 |
|---|---|---|---|
| 평균 | 4.574 ms | **2.945 ms** | **1.55×** |
| 중앙값 | 4.658 ms | 2.898 ms | 1.61× |
| p95 | 5.088 ms | 3.268 ms | 1.56× |
| 최소 | 3.858 ms | 2.529 ms | |
| 최대 | 9.270 ms | 7.599 ms | |
| 처리량 | 218.4 inf/s | **338.2 inf/s** | 1.55× |

### 재현성 — 같은 설정 CPU 런 두 개

| | 런 2 | 런 4 | 차이 |
|---|---|---|---|
| 평균 | 4.254 ms | 4.574 ms | **7.5 %** |
| 추론 수 | 14,094 | 13,106 | 7.0 % |

**같은 설정에서 7.5 % 차이가 난다.** 조건 간 차이를 주장하려면 반복이 최소 3회는
필요하다. 반복 1회 설계는 노이즈와 신호를 구분하지 못한다.

### 부하 지속시간이 지연시간을 바꾼다

| | 런 1 (9.7초 버스트) | 런 2 (60초 지속) |
|---|---|---|
| 평균 지연 | **9.655 ms** | **4.254 ms** |
| AP 온도 | 30.5 → 31.0 ℃ | 28.4 → 43.6 ℃ |
| 평균 전류 | 0.42 A | 2.02 A |
| 처리량 | 103 inf/s | 235 inf/s |

설정(CPU, 4스레드)은 동일하고 **부하 길이만 달랐는데 지연시간이 2.27배** 차이났다.
짧은 버스트는 거버너 부스트를 받지 못한 것으로 보인다.

전류 샘플링이 1 Hz라 9.7초 구간의 근거는 얇다. **가설로 두고 duration을 축으로
확인해야 한다.** 사실이라면 "모델×자원당 지연은 상수"라는 가정이 2배 이상 틀린다는
뜻이고, 시뮬레이터 설계에 직접 영향이 있다.

---

## 4. 발열 거동 — 런 2 (CPU/4, 60초)

| t(s) | 평균 ms | p95 ms | AP | SKIN | BAT | headroom | 전류 A |
|---|---|---|---|---|---|---|---|
| 0–5 | 3.920 | 4.077 | 32.8 | 29.8 | 27.3 | 0.483 | 2.77 |
| 5–10 | 3.923 | 4.072 | 42.5 | 31.4 | 27.7 | 0.522 | 2.85 |
| 10–15 | 3.924 | 4.066 | 45.9 | 32.8 | 28.4 | 0.573 | 3.01 |
| 15–20 | 3.998 | 4.189 | **48.1** | 34.0 | 29.2 | 0.616 | 2.53 |
| 20–25 | 4.194 | 4.368 | 46.2 | 34.6 | 30.0 | 0.647 | 1.98 |
| 25–30 | 4.291 | 4.432 | 44.8 | 35.0 | 30.6 | 0.662 | 1.67 |
| 30–35 | 4.356 | 4.568 | 44.5 | 35.2 | 31.0 | 0.669 | 1.61 |
| 35–40 | 4.356 | 4.543 | 44.3 | 35.3 | 31.4 | 0.677 | 1.63 |
| 40–45 | 4.466 | 4.628 | 44.1 | 35.6 | 31.7 | 0.683 | 1.51 |
| 45–50 | 4.607 | 4.793 | 44.1 | 35.7 | 31.9 | 0.688 | 1.49 |
| 50–55 | 4.550 | 4.727 | 43.9 | 35.8 | 32.1 | 0.693 | 1.43 |
| 55–60 | 4.659 | 4.813 | 43.7 | 36.0 | 32.3 | 0.699 | 1.40 |

60초 동안 **지연 +18.9 %, 처리량 −15.8 %**. AP가 15–20초에 48.1 ℃로 정점을 찍고
거버너가 끌어내려 44 ℃에 안착했으며, 전류도 3.01 A → 1.40 A로 **절반 이하**로 떨어졌다.
전형적인 boost-then-settle이다.

### 가장 중요한 관측

```
thermal_status : 0 → 0    (60초 내내 THERMAL_STATUS_NONE)
headroom_now   : 0.483 → 0.700
```

**Android는 끝까지 "스로틀링 없음"이라고 보고했는데 성능은 19 % 떨어졌다.**
`PowerManager.getCurrentThermalStatus()`만 관측하는 스케줄러는 이 구간을 통째로
놓친다. `getThermalHeadroom()`은 정직하게 움직였다. 스케줄러가 무엇을 관측해야
하는지에 대한 직접적 근거다.

### 꼬리 지연

6 ms 초과 추론이 18건(0.13 %)이었고 그중 15건이 **t=49.81–49.94 s에 집중**됐다.
0.13초짜리 정지로, 외부 프로세스 개입이나 GC로 추정된다.

---

## 5. GPU — 허용목록을 이긴 기록

### 실패했던 이유

```
delegate_init  status=error  latency=33.16 ms
java.lang.IllegalStateException: GPU delegate is not supported;
                                 GPU experiment cannot start
```

LiteRT 1.4.2에 바이너리로 내장된 기기 허용목록(`CompatibilityList`)이 Exynos 2600을
모른다. LiteRT가 이 SoC보다 먼저 빌드됐기 때문이다. 기존 코드는 이 판정을 치명적
오류로 취급해 `GpuDelegate()` 생성자에 도달조차 못 했다. 33 ms는 목록 조회 시간이다.

반증: 기기에 OpenCL이 존재한다.

```
/vendor/lib64/libOpenCL.so
/vendor/lib64/libOpenCL_samsung.so
/system/lib64/libOpenCL.so
```

대응은 [`../patches/README.md`](../patches/README.md) 패치 1 참조.

### 패치 후 실제 결과

```
gpu_compatibility_list_supported   false      ← 허용목록은 여전히 거부
gpu_compatibility_list_enforced    false      ← 강제하지 않음

gpu_delegate_created               true
gpu_delegate_type                  "TfLiteGpuDelegateV2"
gpu_delegate_kernel_count          1
replaced_nodes / total_nodes       31 / 31
full_delegate                      true
verification                       "verified"    ← 최고 등급
failure_or_fallback_evidence       []
```

**허용목록의 판정이 틀렸음이 데이터로 증명됐다.** 두 값이 한 레코드에 같이 남아 있어
나중에 누가 보더라도 무엇을 근거로 판단했는지 재구성할 수 있다.

---

## 6. CPU↔GPU 출력 동등성

GPU가 열리면서 출력 동등성 preflight가 처음 실행됐고 **통과**했다.

```
status                        "passed"
execution_integrity_status    "passed"
equivalence_acceptance_status "passed"
comparator_version            "output-equivalence-v3"
입력                          32개, lcg-float32-unit-v1, seed 305419896

argmax_match_count            32 / 32        ← top-1 전부 일치
argmax_mismatch_count         0
mean_cosine_similarity        0.99993
min_cosine_similarity         0.99966
max_absolute_error            0.010115
mean_absolute_error           0.0000201
rmse                          0.000173
```

### 주의 — top-5는 다르다

```
numerical_tolerance_result        "outside"   (atol 1e-4 / rtol 1e-3 초과)
combined_tolerance_is_diagnostic  true        진단용이지 합격 기준 아님
mismatch_count                    922 / 32,032 원소

top5_set_match_count              25 / 32
ordered_top5_match_count          16 / 32
```

GPU 델리게이트가 내부적으로 fp16을 쓴다(`precision_loss_allowed: true`,
`actual_fp16_execution: "unknown_not_exposed_by_litert_api"`).

**top-1은 32/32 완벽히 일치하지만 top-5 순서는 절반만 같다.** 지연·발열 측정에는
문제없다. 그러나 **task accuracy를 비교 지표로 쓴다면 CPU와 GPU를 같은 것으로
취급해서는 안 된다.** 보고서에 반드시 명시할 조건이다.

---

## 7. NPU — 현재 막혀 있음

NNAPI 디바이스가 **하나뿐이고 그것이 CPU 소프트웨어 구현체**다.

```json
{"index":0,"name":"nnapi-reference","type_number":2,"type_name":"CPU",
 "feature_level":1000008,"reference_cpu":true}
```

`feature_level: 1000008`은 NNAPI Feature Level 8, 즉 최신이다. **런타임은 멀쩡한데
삼성이 NNAPI용 NPU 드라이버를 등록하지 않았다.**

한편 하드웨어와 벤더 스택은 존재한다.

| 계층 | 상태 |
|---|---|
| NPU 장치 노드 `/dev/npu0~1`, `unpu_`, `dsp_` | 존재. 단 `crw-------` `system:system` → 일반 앱 접근 불가 |
| NNAPI 런타임 (APEX, public 등재) | 존재 |
| NNAPI 벤더 드라이버 | **없음** (`lshal`에 neural HAL 없음) |
| Samsung ENN (`libenn_public_api_cpp.so` 등 20개) | 존재, public 노출 |
| `com.samsung.android.aicore`, `com.google.android.aicore` | 설치됨 |

NPU로 가는 유일한 통로는 Samsung ENN이고, 공식 접근 경로는 LiteRT Next의
`CompiledModel(model, Accelerator.NPU)`다. 기존 `Interpreter` + 델리게이트와는
**다른 실행 엔진**이라 델리게이트 교체 수준이 아니라 엔진 추가 작업이다.

미검증 위험 셋:

1. Exynos 2600용 NPU 런타임이 Play for On-device AI로 실제 배포 중인지
2. 사이드로드 앱이 그 런타임을 획득할 수 있는지
3. 같은 float32 아티팩트 그대로 실행 가능한지 — 재컴파일이 필요하면 CPU/GPU 숫자와
   직접 비교가 깨진다

근거: [`../device/10_npu_runtime.txt`](../device/10_npu_runtime.txt),
[`../device/09_nnapi_probe.txt`](../device/09_nnapi_probe.txt)

---

## 8. 정식 측정의 실제 제약 — 배터리

측정 중 실측 평균 전류 **2.02 A**, 배터리 4,315 mAh, 정식 에너지 자격 SOC 30–90 %.

```
가용 용량       60 % × 4,315 mAh              = 2,589 mAh
런 1회 (600초)  load 2.0 A × 600 s            =   337 mAh
                baseline + cooling            ≈    30 mAh
                                              ─────────────
                                                  367 mAh

한 충전당 가능 런 수                          ≈ 7 런
```

**충전 중에는 안전 게이트가 런을 거부한다.** 정식 측정은 한 번에 완주할 수 없고
`--resume`으로 배터리 단위로 쪼개 돌려야 한다.

| 설계 | 런 수 | 벽시계 | 필요 충전 |
|---|---|---|---|
| 저장소 예시 (16조건 × 5반복, 600초) | 80 | ~21 h | ~11회 |
| 경량 (4조건 × 3반복, 300초) | 12 | ~2.5 h | 1회 |

또한 이 기기는 **실사용 단말**이다. 측정 중에는 사용할 수 없다.

---

## 9. 미해결

- [ ] 스레드 축 상한 — 1/2/4 이후 8을 넣을지는 스케일링 곡선을 보고 결정
- [ ] A24와의 설계 정합 — 조민규 측 정식 측정 명령줄 확보 필요
- [ ] 부하 지속시간이 지연시간에 미치는 영향 (§3) 을 축으로 검증
- [ ] 전류 단위 2단계 정식 검증 — 1초 균일 샘플링 적분 vs charge_counter 차분
- [ ] LiteRT Next `CompiledModel` NPU 경로 타당성
- [ ] `formal_gpu_valid`가 S26에서 항상 false (SM-A245 하드코딩) — exports-v2 GPU 자격
