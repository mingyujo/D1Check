# Q20 입력 수신 검증 — 등록 §1 ①~⑤ (2026-10-09 18:3x KST · 판정기 커밋 전 · 출력 값 열람 0)

> 등록 `d1sim/docs/품질20장_사전등록_v1.md` blob `48b593828af36a1b98830dde9d8da0224ce5b881185f69cdaa5d9ede8317d670` (커밋 `a56ebbf`) = OneDrive 원본 SHA 동일 [P].
> 보관 (등록 §1): `D1_ondevice\quality_inputs_1006\s26_quality_inputs_v1.zip` (zip 사본) + `quality_inputs_1006\extracted\` (풀린 폴더). Git · APK 에 넣지 않는다.
> 이 표에는 해시 · 크기 · 구조만 있다. 참조 출력 **값** 은 판정기 (`s26/tools/quality20/q20_judge.py`) 가 커밋된 뒤 2부에서만 읽는다.

## 검증 결과 [P] — 전부 통과

| 단계 | 검사 | 결과 |
|---|---|---|
| ① | zip SHA-256 = `3bf4659997c2ccd188563d4ee0cdf42c174ebaf175ad58eaab3d28128dd8dcdd` · 3,807,484 B · 43 파일 | **일치** |
| ② | manifest (`tensor_manifest.json`, 23,033 B, SHA `46bef120…`) 의 파일 42개마다 bytes · SHA (input 20 · reference 20) | **42/42 일치** |
| ③ | 참조 JSON (`quality_reference.json`, 506,444 B) SHA = manifest `quality_reference_sha256` `148e3be8065659b2d305d03a10924ac657a1ee8b4a5a17b14613c584e2cc66f4` | **일치** |
| ④ | input 파일 SHA 를 manifest 와 무관하게 다시 계산 (hashlib) → manifest 값과 비교 | **20/20 일치** |
| ⑤ | input 각 602,112 B = 1×224×224×3×4 | **20/20** |
| 보조 | `references/<id>/output_0.f32le` (4,000 B) SHA = manifest `reference_sha256` = JSON `reference.raw_output_sha256` · raw 바이트 = JSON `output_float32` 1000개 비트 동일 (값 미출력 · 기계 비교만) | **20/20** |
| 보조 | JSON `reference.input_tensor_sha256` = manifest `input_sha256` · `model_sha256` = `6c7ab0a6…` (CPU/GPU 계약 모델) · `label_sha256` = `e697a491…` (`labels_without_background.txt`, R1 build record 와 같은 값) | **20/20** |

manifest 머리: schema `s26-tensor-transfer-v1` · shape `[1,224,224,3]` · dtype float32 · endianness little · layout NHWC_RGB · preprocessing "canonical-sRGB; Q16 half-pixel bilinear round-half-up stretch224; (RGB-127)/128; no crop/padding" · `new_inference 0` · `device_commands 0` · role `engineering_equivalence_not_ground_truth` [D 그의 manifest].
README (347 B): "existing tensors copied byte-for-byte; CPU outputs reconstructed from existing JSON, not new inference … Do not normalize or resize inputs again … Register NPU precision quality criteria before evaluation." [D]

참조 생성 조건 [D JSON `reference`]: runtime `ai-edge-litert` **2.2.0** · `cpu_threads 1` · `deterministic_invocations 3` · decoder `class_index_offset 0` · ordering "score descending then class index ascending" (= 판정기 동률 규칙) · 출력 tensor `Softmax` float32 `[1,1000]` · 입력 `images` float32 `[1,224,224,3]` · status `engineering_reference_not_ground_truth`.

## 구조 (manifest 순서 = 참조 JSON 순서 ✔) — 해시 · 크기만

| # | sample_id | 클래스 | input B | input SHA-256 (재계산) | ref B | ref SHA-256 |
|---|---|---|---|---|---|---|
| 0 | `00575b9132bb3746` | Bicycle | 602112 | `603328d02dfc2b1aa356b26b0f14b9e70f8cdb80609c89fd171bcf4c3ff85462` | 4000 | `0df3d53519e40f8e86e683866a00a1083f7b90c53a6b0625b52fe2b065926103` |
| 1 | `00e9084d1bc8e0ea` | Bicycle | 602112 | `4bd152ac63e7aefe3a645540235a349b934d58cd2788f7fb89953e180be6d141` | 4000 | `b91d1524a3a9d4c492c6e880198a973d3b0e1aadfe557e4b91152977da7f503a` |
| 2 | `020feca9b536f1fe` | Bicycle | 602112 | `a7d2dcab83b8ee0819018e3857c8c17cf8172585869e3151021e2d5b3bde945b` | 4000 | `4ba15956c6b1539b19574d3346f349fab6209afa29887c8fa1b22acd2a872d3a` |
| 3 | `049b2fae5ca8aa8b` | Bicycle | 602112 | `c0b7e4f4d45f8587789c5ccb6bd605bb37d9571883b7637c4442749cb069f961` | 4000 | `41df8830d8e86da19c00a425f93337f197ee947ae308f270fd32e1a2f2359148` |
| 4 | `001083f05db4352b` | Car | 602112 | `321fe7dffb53d9c5f2fcef1ff209731796a2df8be2d69f3a36a7ed5813110184` | 4000 | `96a9ff75b264193087dab12598a7b467653ecea2bbcafe5fd88a7888d80217f5` |
| 5 | `001a794d1865ee47` | Car | 602112 | `524ccbfa6edfe5866ab8bbbe18389f173a5351e248f943d2790f3c2a7c135128` | 4000 | `0af35ef92ebab88bfffca3986c5aefabe21a27be4d24d7247eea22825963a649` |
| 6 | `001a809ad40a2f84` | Car | 602112 | `de18ad3fb92b485765e30d33fb3e732acbf4bfb6413a9d2dbc396cfaa3fb76fd` | 4000 | `f221b0ffdcfdb942df5396a81c95ff1355af83f1ede1bb4169e0308c1c01fedd` |
| 7 | `0022e32008e479cb` | Car | 602112 | `6c21673409a026c4848752cf33b62f71cc1c37171b1d2fbca9100590d6a2827c` | 4000 | `b3d831d80fe687699c0ead3b650c79f31c128a5882c83eb1882764ee8f9e8a8d` |
| 8 | `0060dfb7f9a468b5` | Cat | 602112 | `49ed00b5ade9e0de0a6d061c1890db9bf1c12e06566b2d3c3b222f74351d7d7a` | 4000 | `2f8331b7c7682a6d846c13733a76c6896b8134931655b4a0e39995256b8b12ca` |
| 9 | `00bdb008eb688497` | Cat | 602112 | `e763358cf73c36db0994eb05a2cdac386d8ab8b51fca5041c8a7bc8602997f0d` | 4000 | `411598543c0b00b8e8204b00126a4bf7e0744c59bfdd9fb7d8ef792f1bbcaa2b` |
| 10 | `02fcc80210b7cd5b` | Cat | 602112 | `e669e5f7ab1402bcd0be6919563b5d1048a69055b5f1c9eb6d0287fd4ab92e3b` | 4000 | `564140f5f96dac11eb8fd37b9998b6f0607612c41be474a62b935fbedbccbe8d` |
| 11 | `039beb511fd1e7f7` | Cat | 602112 | `162e0ccbca561fa1c888998dda84215e8c69588da61c2571c1087c3eef95123e` | 4000 | `d7de78cdb16674b4aaa8a063b506ecf3fe1052c768ecf248330a60dd7aa81d2b` |
| 12 | `0007cebe1b2ba653` | Dog | 602112 | `eab85c9342b9f131b445e1e1c5c91888fb8f4881567af57260c9328445a578cf` | 4000 | `1e1a45097121c85f343d769f7eb70fb3dbd7615a818566e7dbded6d3ca844f64` |
| 13 | `0007d6cf88afaa4a` | Dog | 602112 | `6243bc3d78dd967ba3d450aa2e2dd7e5d10b2d28cc96032e2c9b58f095f7f116` | 4000 | `9753e69e9c6c1b8839c97892f8a2025853ef5acc9cc3d6d56261716d25d6f800` |
| 14 | `0008e425fb49a2bf` | Dog | 602112 | `79d933fb9aa10843ea54cce9f352dbd2423375285364012edb8767652aae121f` | 4000 | `e00523f918023442a84f883e2e1cfa1e93f0b506a0439995bee3cbc98d76e97d` |
| 15 | `000c4d66ce89aa69` | Dog | 602112 | `f112e62d6bd110acb4fc52d2f1bdb3082744c78edae90d14fe124a7cd5e0da65` | 4000 | `0f8411ab4fc4728a44c311a95ef550510f6ba72fa5603f39fe4f55015f3e4f8a` |
| 16 | `010d42acb7498094` | Horse | 602112 | `43e2c73bc3b7ed25db7f0593e6a3736c405bc836fdf8050ce9bc740510d989b6` | 4000 | `908bf0571d8edd4fa746eb65ea42f2def456036243ad5fd4a23dca3f136c8fb5` |
| 17 | `027cffb13d932cf2` | Horse | 602112 | `cb08219da556aae457ec26d4dc017ec29e6d8c7c035fe9f66bd07453ac9a6e4d` | 4000 | `e80784810c70913eb87d14b08a6cc24273ef9c3a7cebd0e197686ae996d09d61` |
| 18 | `02b7e70979560df7` | Horse | 602112 | `78b033708a1335d56d715b37d69d45300ce3590f4e53de3a1f5bb2b562b868e2` | 4000 | `0d10cf81b96e3af5d5b17ba516b7f0fcfbab631f1598a958c442b5d67164cf9f` |
| 19 | `0354aba2fc6c5903` | Horse | 602112 | `5092104b63a4e8960a7276b4d051490f379c20493c3ff57d3c510e8b8bc70ec2` | 4000 | `f0238f8f47f8993120c2bc0b29a17e08cad7e47553d39e18fcba1b0c47681c2b` |

5 클래스 × 4 = 20 (등록 §4 "top-1 일치는 변별력이 제한적"). sample 0 `00575b9132bb3746` = 혼합 요청 (R1 · R2) 의 도착용 1장과 같은 텐서 (`603328d0…`, 그 쪽 PC 참조 raw `0df3d535…` 와도 같은 값 — R1 보고서 §4) [D].

## 판정기가 2부에서 다시 확인하는 것 (fail-closed · `q20_judge.load_reference`)

zip 안 `quality_reference.json` SHA = 등록값 · 참조 raw SHA = manifest = JSON · raw = `output_float32` 비트 동일 · `class_index_offset 0` · label SHA `e697a491…` · model SHA `6c7ab0a6…` · 입력 텐서 SHA 일치 · 출력 메타 float32 `[1,1000]`. 하나라도 어긋나면 멈춘다 (새 해시를 받지 않는다). 1부에서 이 loader 를 한 번 돌려 20장 전부 통과함을 확인 (값 출력 0).
