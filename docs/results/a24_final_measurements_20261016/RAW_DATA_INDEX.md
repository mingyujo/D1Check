# 완료·실패를 함께 보존한 A24 원자료

원확인40·개정4·실패보완12·경로확인2·새기준6의 **64등록 / 58정상 / 본요청7,912완료·8,456예정**을 묶었다. MAIN 전 실패5·미실행1도 원장에 남겼다. 각 ZIP의 `FILE_SHA256.json`이 원멤버 바이트와 SHA를 고정한다.

미완료 블록 안에서 완성된 하위 비교군을 별도 ZIP으로도 제공하므로 **ZIP의 조건 수를 단순 합산하지 않는다.** 유일한 전체 분모는 `attempts_all.csv`의 세션64개다. 입력·모델·텐서 SHA와 정확한 소스 목록도 포함한다.

개인 식별 설정·모델·승인 이미지·APK·키·전체 시스템로그 및 일부 바이너리는 제외 사유와 SHA를 ZIP 안에 기록했다. 공개 manifest는 식별 정보를 뺀 파생 설정이며 원본 private manifest와 같다고 주장하지 않는다. 별도 Perfetto 원본 ZIP은 아래 링크로 제공한다. Jnull/AP HAL·물리표면 미검증/experiment_ready=false다.

[전체 원장](../a24_measurement_share_20261016/final_registered_families_01/attempts_all.csv) · [원자료 설명](../a24_measurement_share_20261016/final_registered_families_01/README.md) · [소스 목록](../a24_measurement_share_20261016/final_registered_families_01/SOURCE_CATALOGS.json) · [원본 Perfetto ZIP](../a24_measurement_share_20261016/perfetto_path_repair_raw_trace_01/README.md)

| 자료 역할 / 블록 | 정상/등록 | ZIP 크기 | 원자료 ZIP | SHA-256 |
|---|---:|---:|---|---|
| EXTRA4 / REBASE_M128_01 | 2/4 | 674,401 B | [EXTRA4_DEV_REBASE_M128_01.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/EXTRA4_DEV_REBASE_M128_01.zip) | `8c635a7f875ee19055530db800a6373e5a567e1283cf2da4643efec658079d46` |
| NEW6 / NEW_L64 | 2/2 | 275,303 B | [NEW6_DEV_NEW_L64.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/NEW6_DEV_NEW_L64.zip) | `4e1ba2f9e6a259d7147f9a738fe56be1fe70cd127d913a7123ba7dd9cc418b51` |
| NEW6 / NEW_M128 | 4/4 | 915,319 B | [NEW6_DEV_NEW_M128.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/NEW6_DEV_NEW_M128.zip) | `7a7f482b557d0184ff1baf44264dd639c054a44cc19d3709780474a6245a45e5` |
| ORIGINAL40 / R02CONFIRM01 | 8/8 | 2,005,876 B | [ORIGINAL40_CONFIRM_R02CONFIRM01.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/ORIGINAL40_CONFIRM_R02CONFIRM01.zip) | `6bdfd6f0ef7fc20389dc8ef35b07cb8b26ce26514ed72198c9df4b35bb692a1f` |
| ORIGINAL40 / R02CONFIRM02 | 8/8 | 2,013,328 B | [ORIGINAL40_CONFIRM_R02CONFIRM02.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/ORIGINAL40_CONFIRM_R02CONFIRM02.zip) | `d7aafe4d6e74bb6d1074aa6adb64bf7dd7e5292e2e9e7b91127a7ad5f26c6679` |
| ORIGINAL40 / R02CONFIRM03 | 6/8 | 1,802,779 B | [ORIGINAL40_CONFIRM_R02CONFIRM03.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/ORIGINAL40_CONFIRM_R02CONFIRM03.zip) | `b6c6448c9d53031acbd44280e79456b0d2486b4075e9799d12ef3d48f4737744` |
| ORIGINAL40 / R02CONFIRM03 / C252 | 2/2 | 815,487 B | [ORIGINAL40_CONFIRM_R02CONFIRM03_C252.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/ORIGINAL40_CONFIRM_R02CONFIRM03_C252.zip) | `7d28027fe8d5afa7ab807411bba05a82ffa2ae366f6248a161c5cc2137357035` |
| ORIGINAL40 / R02CONFIRM04 | 7/8 | 1,876,371 B | [ORIGINAL40_CONFIRM_R02CONFIRM04.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/ORIGINAL40_CONFIRM_R02CONFIRM04.zip) | `2ef4a3e452b310c41d3c43c8fbd753c760293ca1addb4eb936424d3c85542502` |
| ORIGINAL40 / R02CONFIRM04 / C252 | 2/2 | 813,354 B | [ORIGINAL40_CONFIRM_R02CONFIRM04_C252.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/ORIGINAL40_CONFIRM_R02CONFIRM04_C252.zip) | `e22f6711cc578d555fa3d999682876088dc36154198837df9bbf3915b50fae4d` |
| ORIGINAL40 / R02CONFIRM04 / M128 | 4/4 | 912,379 B | [ORIGINAL40_CONFIRM_R02CONFIRM04_M128.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/ORIGINAL40_CONFIRM_R02CONFIRM04_M128.zip) | `ee716a9aa5824218ac7ce08a60fa80fe937070b12dc68e3662a60f6a8bc259c5` |
| ORIGINAL40 / R02CONFIRM05 | 8/8 | 2,012,275 B | [ORIGINAL40_CONFIRM_R02CONFIRM05.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/ORIGINAL40_CONFIRM_R02CONFIRM05.zip) | `f181697fbaf490a91b7cf0c6fbb5b67483b2838a124319fc9e5df5daf93df25f` |
| SUP12 / C9_ORDER | 1/1 | 233,883 B | [SUP12_DEV_C9_ORDER.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/SUP12_DEV_C9_ORDER.zip) | `43f9b45b9070d67cfef82728f40442c93df47da5016dc8167ea7c5d0f9ddb4bc` |
| SUP12 / DEV_CPU | 1/1 | 407,698 B | [SUP12_DEV_DEV_CPU.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/SUP12_DEV_DEV_CPU.zip) | `2ed99876a653800395c17bcb17e01332a0dde2eb5f4355d2ef878cb3b48f0a4b` |
| SUP12 / F_CPU | 1/1 | 403,828 B | [SUP12_DEV_F_CPU.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/SUP12_DEV_F_CPU.zip) | `5f943de8ff1b6ae97c9c5051a3c00eea54e9344ae6b6389968e292bf1d0d2386` |
| SUP12 / I_RESIDENT | 1/1 | 44,493 B | [SUP12_DEV_I_RESIDENT.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/SUP12_DEV_I_RESIDENT.zip) | `d157568c37ccc767ca375ebd2258e9f7228e821ad6c73307de9974d4a646539f` |
| SUP12 / I_UNRESIDENT | 1/1 | 34,810 B | [SUP12_DEV_I_UNRESIDENT.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/SUP12_DEV_I_UNRESIDENT.zip) | `7b109e6b1d4fd773e41dcfd834d8d0a722fc115f22c8153811dcf9205ce26817` |
| SUP12 / OLD_CONFIRM_PAIR | 1/1 | 142,957 B | [SUP12_DEV_OLD_CONFIRM_PAIR.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/SUP12_DEV_OLD_CONFIRM_PAIR.zip) | `d27ba333566036695861e0d5b7287441e833f48f09c78275c9ca2c67bd88672f` |
| SUP12 / OLD_CONFIRM_STOP | 1/1 | 232,397 B | [SUP12_DEV_OLD_CONFIRM_STOP.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/SUP12_DEV_OLD_CONFIRM_STOP.zip) | `8103d12c69a6ffcb8cd269a42b3dd170009b10107d6d7ba19e5d63208e3739ff` |
| SUP12 / R2_PAIR | 1/1 | 229,535 B | [SUP12_DEV_R2_PAIR.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/SUP12_DEV_R2_PAIR.zip) | `b4f8c9a02e6ba708540b1e97b7afcaf0d32830939b56db22652814a8422ce51e` |
| SUP12 / TRACE | 1/2 | 169,339 B | [SUP12_DEV_TRACE.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/SUP12_DEV_TRACE.zip) | `907925a8dd686f2d458d7fe157083711aee41aacd6c94c780018bb2108face97` |
| SUP12 / W1_CPU | 1/1 | 406,551 B | [SUP12_DEV_W1_CPU.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/SUP12_DEV_W1_CPU.zip) | `c3a9a590eac5ffe97730d6f8a9f4255e571a926fc6dc18f675aeada0ce2f34cd` |
| SUP12 / W3_GPU | 1/1 | 413,186 B | [SUP12_DEV_W3_GPU.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/SUP12_DEV_W3_GPU.zip) | `2a7fb1c5e1c26c9bcfd0879cfbe8a63752ce8d3507def3f1ea312c750c2d0aa4` |
| TRACE2 / TRACE_REPAIR | 2/2 | 178,393 B | [TRACE2_DEV_TRACE_REPAIR.zip](../a24_measurement_share_20261016/final_registered_families_01/blocks/TRACE2_DEV_TRACE_REPAIR.zip) | `8694387ef22618ca313e1135312ee73f675b42c62c226db7b43e6abba092705f` |
