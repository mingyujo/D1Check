# ENERGY-THERMAL-COLLECTION-PREP-02 준비 결과

PC 준비 완료, **실기기 미실행·새 예산 승인 필요**. 작업 브랜치 `feature/arrival-scheduling-20260923`용이며 기본 브랜치 상태가 아니다. [전체 계약](../../ENERGY_THERMAL_COLLECTION_PREP_02_20260925.md), [조건표](conditions.csv), [예산](budget.json), [검증 대상](verification.json).

- 새 `EnergyCollectionActivity`/`energy-thermal-collection-v2`: resident4·thread1, 두 배정 각각 실제 직렬 묶음과 병행 묶음. 고정 요청870/세션, 적격성2, warmup8.
- 개발4→동결→확인4, 진단6976·warmup64·총추론7040·runtime32. APK전송/설치 각≤1(동일 설치본 생략), retry/대체/추가0. 고정관측104분, 단계 예약 소요 추정 약207분, **회수/cleanup 포함 상한220분**.
- Python17 및 Kotlin6 관련 테스트, 최종 APK 컴파일·서명·manifest/입력/source 결합·PowerShell Check 통과. mock 통과는 native/GPU/실기기 적격성 검증이 아니다.
- 기존 정책/결과·40동결/20null·experiment_ready=false 유지. 임의 offset/duty/다른 입력/priority·고온 효과는 미지원이다.

## 로컬 전용 준비 파일

아래 Windows 경로의 APK/원본/계획은 GitHub에 포함되지 않는다. 키와 모델 바이너리를 공유하지 않는다.

- 계획/manifest/script: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_plan_v4/`
- APK: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_build_v5/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`
- 상세 검증/보고서: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_pc_v2/`
- 미래 출력: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_run_v2` (현재 생성 안 됨)
- registry: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_registry/ENERGY-THERMAL-COLLECT-02` (현재 생성 안 됨)

최종 plan SHA-256: `32ca541e9696aabb78431c82696893342f34304bfb4c423661698755f0578f9e`.
APK SHA-256: `1e58655af1ede00062277669c718fd0881f5aadba31c0ed122445b7d0990d8e7`.
프로젝트 signer SHA-256: `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565` (개인키 아님).

## 실제 확인한 PC 명령

저장소 루트에서:

```powershell
python -B -m unittest tools.test_d1_energy_collection -v
powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_plan_v4/RUN_AFTER_APPROVAL.ps1 -Action Check
```

Kotlin 대상은 `:benchmark-runner:testModelProbeUnitTest --tests com.example.d1check.benchmarkrunner.EnergyCollectionCoreTest`, APK 대상은 `:benchmark-runner:assembleModelProbe`다. 로컬 SDK/JBR와 격리 init-script `tools/arrival_timing_isolated_build.gradle`, `-PenableModelProbe=true`를 사용했다. 소스 해시·명령·결과는 외부 build_v5의 build_receipt.json/build.log에 보존했다. SDK 경로가 없었던 첫 빌드 실패도 남겼다. 마지막 host JSONL prefix 보완은 APK를 다시 만들지 않고 plan_v4에 새 source hash를 결합했다. 기존160세션 재분석·전체 실험 배치는 실행하지 않았다.

## 새 승인 후 명령 — 이번에는 실행하지 않음

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_plan_v4/RUN_AFTER_APPROVAL.ps1 -Action Run -Approved -Serial '<현재 확인한 A24 transport serial>'
```

유일한 A24 hardware serial/fingerprint, 설치본 서명/hash, ≥20%·비충전·≤35°C·thermal0·memory·awake/interactive·화면81/manual/기존timeout gate가 필요하다. 설정을 자동 변경하지 않는다. baseline 온도 matching·GPU 위임·probe 실제 overlap·품질·기록 gate 실패는 전체 중단이며 재개/추가세션은 없다.

성공 시 session summary→개발 동결 hash→확인 오차/최종 receipt를 생성한다. 정확도 허용폭은 미확정이므로 수집 적격성만 판정하고 절감·정책 우월성 PASS를 부여하지 않는다. 조건당 각 단계1독립세션이며 요청수는 독립 표본수가 아니다.
