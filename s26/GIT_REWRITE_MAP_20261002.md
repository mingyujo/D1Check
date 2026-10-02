# 로컬 커밋 해시 대응표 (2026-10-02)

`s26-measure` 에는 9/15 커밋 `dcde411` 뒤로 **push 하지 않은 로컬 커밋 23개**가 있었다. 첫 push 전에 그 23개를 다시 써서 아래 두 가지를 뺐다. 내용·작성자·날짜·메시지는 그대로이고 **해시만 바뀌었다.**

1. **바이너리 5개** — git 기록에서만 뺐다. 파일은 영훈 PC 의 같은 경로에 그대로 있다. 팀 공유 경계(모델·컴파일 바이너리는 저장소에 넣지 않는다)와 우리 규칙(`npu/artifacts` 커밋 금지)에 맞춘 것이다
2. **문서 안의 무선 adb 주소와 기기 시리얼** — `<IP:PORT>` · `<SERIAL>` 로 바꿨다. 9/15 이전에 이미 push 된 파일은 이 단계에서 건드리지 않았고, 이 표 다음 커밋들에서 따로 정리했다

작업 기록(로컬 문서·회신·사전 등록)에 적힌 **옛 해시는 이 표로 새 해시를 찾는다.** 예: 스로틀 모형 v0 고정 커밋 `402acab` → 아래 표의 해당 줄. 옛 커밋은 영훈 PC 의 백업 브랜치 `backup/s26-measure-before-push-1002` 에만 있다 (push 하지 않음).

## 뺀 바이너리

| 경로 | 크기 (B) | SHA-256 | 출처 |
|---|---:|---|---|
| `npu-runner/src/main/jniLibs/arm64-v8a/libLiteRtDispatch_Samsung.so` | 559,960 | `f08656a642c46e7b06b64fbe1e0800de9e73b0b69c1641b87995562b4a16840f` | LiteRT main@9380426b 소스 빌드 (`s26/npu/tools/build_litert_samsung.sh`, provenance `s26/npu/artifacts/litert_samsung_arm64/README.md`) |
| `npu-runner/src/main/assets/models/mobilenet_v1_1.0_224_Samsung_E9965.tflite` | 8,901,712 | `1415b2c87d01b67a9380b8f912e2b4ef4561502105b06f313332c97c1c8cb5cf` | MobileNet V1 FP32 AOT (`Samsung_E9965`, 2.3.0.dev20260917) — APK 에 들어가는 사본 |
| `npu-runner/src/main/assets/models/mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite` | 4,605,104 | `36c75e6acdb711628f2486c7880a9c84fe1dc94c986d4f8dc53eb94ee773e5fa` | MobileNet V1 INT8 AOT — APK 에 들어가는 사본 |
| `s26/npu/artifacts/compiled_e9965/mobilenet_v1_1.0_224_Samsung_E9965.tflite` | 8,901,712 | `1415b2c87d01b67a9380b8f912e2b4ef4561502105b06f313332c97c1c8cb5cf` | G1 컴파일 출력 원본 (`compiled_e9965/aot_manifest.json`) |
| `s26/npu/artifacts/compiled_e9965/mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite` | 4,605,104 | `36c75e6acdb711628f2486c7880a9c84fe1dc94c986d4f8dc53eb94ee773e5fa` | G1 컴파일 출력 원본 (`compiled_e9965/aot_manifest.json`) |

다시 만들 때 같은 nightly·같은 소스 리비전이 아니면 해시가 달라질 수 있다. 측정 기록의 모델·dispatch 해시(`model_sha256`, `npu_dispatch_lib_sha256`)는 위 값과 대조한다.

## 커밋 대응 (오래된 순, 시각 KST)

| 옛 해시 | 새 해시 | 시각 | 제목 |
|---|---|---|---|
| `25ad84723e1a07b74e13875200f6b18ad6ecc214` | `8edadab3d6c442fe1da291627dcb0e498c6da9d7` | 09-20 22:58 | s26/npu: S26 NPU 접근 경로 확보 — G0 통과, G1 AOT 통과, G2 dispatch 빌드, G3 셸 스모크는 HAL 초기화까지 |
| `8f6458158af2d8606715ace749862e8a0374cf76` | `daaf7989c9b73c6c05b973bceb29fb53de2e68a3` | 09-24 05:13 | s26/npu: G4 통과 — npu-runner 앱으로 S26 NPU 추론 성공, 품질 게이트 PASS |
| `88a51103760ec653a60254174cf8b1860a6b6f56` | `35214544890ad9a707df40f38dd631fdd5f1be14` | 09-24 12:48 | s26/npu: G5 준비 — 호스트 NPU 경로, G1-B 새 모델 판정, npu-runner 모델별 입력 |
| `49922da16ccf284f92318100d19378fbf06aae3f` | `4909da1481d0f4367fc4221412f1d5aac6e5d5b7` | 09-24 15:50 | npu-runner: timed-run 프로토콜 이식 — d1_auto_start, 폰 없는 라운드트립 통과 |
| `3521b9b88093b5d5202cb94912427f0774bdd5ee` | `4bc098416f19fb95faf6d6848100fd31316c7bce` | 09-25 05:17 | s26/npu: 첫 기기 timed run + NPU formal 20/20 완주, orchestrator NPU 로거 대기 300 s |
| `e27f9073b0c8e472837d30fc5c5cf6fe1cce30fb` | `07cdb07eb2f277f706e39b9ef56b6d7cb8e61c22` | 09-26 18:52 | s26: 답장 대기 중 감사 — 정밀도 각주, 80런 조건 재추출, 에너지 허용오차 사후 등록, 검출 게이트 계약 초안 |
| `bd20468ed9ef053f43f65f8d2417a83745b3dfc1` | `c06bb923e4b8f26d2a2fe94ec6bed79cde766998` | 09-26 21:07 | s26: 증거 3분법·정밀도 4열·사후감사 재표기·구현계약 단독본 |
| `a35ef84228b2aeb653556602496b56edbe2c53cb` | `a45b67abce37d5f97f4f18398eebfa298022d6c9` | 09-26 22:45 | sim_thermal: 열·에너지 평가층 v1 (합성 입력, 사전등록 포함) |
| `7141561a2db94053da5d11b8e9b818a30349ed0b` | `8e3299446113a152a3663f4a911545df0c2cf913` | 09-26 23:10 | npu-runner/tools: 모델·입력 인자 전달, run-only span, CPU 단독 timed run, 진단 필터 |
| `9bd7a62df76b7d93626a690ef54730b2f8d8eeb0` | `4eef95439e9615d511a5975f8faf85a9e3a79c84` | 09-27 00:44 | sim_thermal: 시나리오 응력 시험 — 열·배터리 구속 지도 |
| `66ea9ad5e9b95a7a842f1004604b61534bf4fe05` | `9d2070e7c36b8c8cdea6aadf4fce8276edb5034d` | 09-27 08:37 | s26: 밤 측정 C6·C1probe·C5·C4 |
| `bb55b811dea13a34a44431de39a3483ac0389641` | `71eff5562bfc59874dea5ffcf56eb7ca9e7873e2` | 09-27 18:09 | d1sim: 1단계 사전등록 — 스로틀 모형 후보 4형태 + 추출 스크립트 (피팅 전) |
| `402acab2ed068b459f922898c621c97093ec396d` | `80ca6c46318c1cbe186839633e398661194aa6b6` | 09-27 18:15 | d1sim: 1단계 — 스로틀 모형 v0 고정 (M-A2 SKIN 구동 2노드, r1 피팅) |
| `7735bbfa9f87b8d0843f04fc799904dd911ac2e0` | `2759731b487069f39beca1de6b2bb800660c4071` | 09-27 18:17 | d1sim: 2단계 — headroom 예측력 분석 (+1단계 문서 SHA 기입) |
| `52d25b7d95c92f415e03f16571f01dbf0694a466` | `0fe1a25866f295738eaa2be52681bf25eb161540` | 09-27 18:29 | d1sim: 3단계 — 시뮬레이터 골격 (profile·env·workload·policies·kpi) + 테스트 26개 |
| `6a75fe63c6ac248b7fedc343f630c14ebba78a26` | `ee43197cc0eacf2ca66995aa0e997489563f9fdb` | 09-27 18:30 | d1sim: 6-1 정책 비교 사전등록 (튜닝·본 실행 전) |
| `5181c040b6176a7662ed352c2c69a9402cac8a59` | `47087885fe9a3742738023e71d3254fc2178ac9b` | 09-27 20:10 | d1sim: 4~6단계 — 워크로드·정책·튜닝·대조군·본 실행·민감도 스윕 결과 |
| `d0b509a09776d55df71487f22fa8c16324d77cb9` | `3f622e2dfd6ede125d5aac4e9f5d5fda74e1a9fc` | 09-27 20:13 | d1sim: 7단계 — 보고서 작업결과_0927_시뮬v0 (Clarity Gate 9항목 자기 점검 포함) |
| `9e3b4e06bf1c039a386288020c322cb6982eeb01` | `73dff9949a3548ac63e1a8cbbceba15e6a43fc5f` | 09-28 07:45 | s26: 밤 측정 0928 — 스로틀 곡선 C1a·NPU·CPU·GPU d50 (+C2) |
| `3e84308e0bf31f6a484ee5fae311eb0f6fe2eac3` | `7d0f2f18e7f308bba6092470b567ca24af93fa2d` | 09-28 07:45 | s26: NIGHT_0928_RESULTS 머리의 세션 끝 시각을 실제 커밋 시각으로 |
| `dcf31381a0abbdbdc7fac915c957a758836ac2f5` | `6e693180c01e50a33b468328c8f561c5c192c62c` | 09-28 12:09 | npu-runner/tools: 연쇄 모드 · CompiledModel GPU · 자원 증거 파서 · 긴 런 한계 |
| `b763b2908de7a6750c8775b2fcbf7c20896d6647` | `c8ee42106d096486db8a5374eee616c411954b5f` | 09-28 12:13 | tools: 연쇄 보존 검사 — 구조 검사만 슬롯 무효, 시간 허용오차는 표시 |
| `50af5e3a256b6acb83df96410c98f8cfd1239857` | `4a3246cab1c7c558e1dd752dcecef17ed0ead243` | 09-28 12:31 | tools/chains: M2 반대 방향 (NPU 발열원 → GPU 피해자) 체인 2개 |
