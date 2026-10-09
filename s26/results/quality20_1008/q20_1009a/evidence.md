# Q20 실행 증거 — run `q20_1009a`

| backend | 증거 판정 | 규칙 | 교체 줄 | 실패 조건 | 창 (logcat 줄) | GPU 정밀도 (요청 / 로그) | available_accelerators |
|---|---|---|---|---|---|---|---|
| CPU | **PASS** | cpu-compiled-model-evidence-v1 (conditions, windowed by D1Q20 marks) | 62/62 TfLiteXNNPackDelegate | 없음 | [708, 1016] | — | ['CPU', 'GPU', 'NPU'] |
| GPU | **PASS** | gpu-compiled-model-evidence-v1 | 62/62 LITERT_CL | 없음 | [674, 1283] | FP32 / 미확인 | ['CPU', 'GPU', 'NPU'] |
| NPU | **PASS** | npu-dispatch-evidence-v1 (conditions, windowed by D1MIX marks) | 1/1 | 없음 | [669, 1036] | — | ['CPU', 'GPU', 'NPU'] |

창 = `D1Q20 runtime create_start` ~ 첫 이미지 `image_end idx=0` (생성 창 ∪ 첫 이미지 창). 증거 함수 = `s26/tools/mixreq/mixreq_validate.py` `gpu_evidence` · `npu_evidence` (import · 무변경) · CPU 는 `compiled_model_evidence.evaluate_cpu` 조건을 같은 창에 적용. ENN 로드 줄은 NPU 실행 증명이 아니라 필요조건이다 (CPU 실행에서도 찍힌다). NPU 코어 실행은 앱에서 관측할 수 없다.
