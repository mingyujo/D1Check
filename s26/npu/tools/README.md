# s26/npu/tools

| 파일 | 어디서 | 무엇 | 관문 |
|---|---|---|---|
| `s26_npu_precheck.bat` | Windows PC, 폰 연결(USB 가능) | 기기 읽기 전용 점검. ENN 서비스·public libs·심볼(의존 트리)·플랫폼 LiteRT 유무·NNAPI 프로브 로그 → `..\device\11~13_*.txt` | G0 ✅ PASS (9/19) |
| `s26_npu_symbols.py` | 어디서나 (표준 라이브러리만) | ELF64 동적 심볼 검사. `libenn_public_api_cpp.so` + `libenn_user.samsung_slsi.so` 를 함께 주면 dlsym 의존 트리 기준으로 판정. `--json` | G0, G2 |
| `s26_npu_aot_compile.py` | **Linux x86_64** (Colab / WSL2) | MobileNet FP32/INT8 → E9965 AOT 컴파일 + `DISPATCH_OP` 검사 + manifest. nightly 패키징 버그(flatbuffers 심볼) shim 자동 적용 | G1 ✅ PASS (9/19) |
| `build_litert_samsung.sh` | **Linux x86_64** (Colab / WSL2), 30~90분 | LiteRT 소스에서 `libLiteRtDispatch_Samsung.so` + `run_model` CLI (arm64) Bazel 빌드 → `litert_samsung_arm64/` | G2 |
| `s26_npu_run_model.bat` | Windows PC, 폰 연결 | `run_model` 로 NPU fp32·int8 + CPU 대조 스모크 → `..\results\G3_run_model_*.txt` | G3 |

## 실행 순서

```
G0  s26_npu_precheck.bat                                    → 11_npu_precheck.txt / 12_enn_symbols.txt  VERDICT: PASS
G1  (Colab) !pip install -q ai-edge-litert-nightly ai-edge-litert-sdk-samsung-nightly
            !python s26_npu_aot_compile.py --model mobilenet_v1_1.0_224.tflite --model mobilenet_v1_1.0_224_quant.tflite --out compiled_e9965
            compiled_e9965/ 를 zip 으로 받아 ..\artifacts\compiled_e9965\ 에 (성공 실행분으로 덮어쓰기)
G2  (Colab 새 노트북) build_litert_samsung.sh 업로드 → !bash build_litert_samsung.sh 2>&1 | tail -40
            /content/litert_samsung_arm64/ 를 zip 으로 받아 ..\artifacts\litert_samsung_arm64\ 에
            (원본 mobilenet_v1_1.0_224.tflite 도 ..\artifacts\ 에 복사 — CPU 대조용)
G3  s26_npu_run_model.bat                                   → results\G3_run_model_<ts>.txt 를 Claude 에게
```

## 주의

- `..\device\*.so` 는 삼성 벤더 바이너리 사본, `..\artifacts\ENNDelegate_*.zip` 은 삼성 라이선스물 → **GitHub 에 올리지 말 것**
- Colab 은 탭을 닫거나 90분 방치하면 VM 이 사라진다. G2 는 시작 후 브라우저를 켜 둔다
- `build_litert_samsung.sh` 기본은 LiteRT `main`(= 컴파일러와 같은 코드선). G3 에서 모델/디스패치 버전 오류가 나면 `!bash build_litert_samsung.sh v2.2.0`
