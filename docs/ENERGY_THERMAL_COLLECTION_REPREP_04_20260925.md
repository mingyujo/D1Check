# ENERGY-THERMAL-COLLECT-04 — 수정 sampler 정식 수집 PC 재준비

2026-09-25, 시작 `919f908654ada1829c6a2c9beee77740c52cff14` / clean. 목적은 같은 작업량의 **실제 직렬 대조와 두 CPU/GPU 병행 배정**을 개발4→설정 동결→확인4로 비교할 새 계획을 준비하는 것이다. 이번에는 ADB·설치·추론·설정 변경을 하지 않았다. 과거 [COLLECT-03 부분 종료](ENERGY_THERMAL_COLLECT03_RESULTS_20260925.md)와 [sampler 직렬 부하 진단](ENERGY_SAMPLER_LOAD_DIAG_RESULTS_20260925.md)의 원본/소비 기록은 보존하고 정식 표본에 포함하지 않는다. 진단 1회 성공은 병행·반복 안정성 검증이 아니다.

## 계보와 실행 경로

- 새 ID `ENERGY-THERMAL-COLLECT-04`, 외부 계획 `energy_collection_plan_v7`, 미생성 출력 `energy_collection_run_v4`, 미생성 소비 registry `energy_collection_registry/ENERGY-THERMAL-COLLECT-04`. 생성 도중의 plan_v6은 코드 identity 확정 전 PC 초안이라 `SUPERSEDED_BEFORE_EXECUTION.json`으로 표시했고 실행/claim 0이다.
- 새 계획은 종료된 COLLECT-03 계획/receipt와 완료된 진단 plan/receipt/claim의 SHA-256을 `lineage`에 결합한다. `prior_and_diagnostic_samples_excluded=true`; 원표본 혼합·중단 계획 재개가 아니다.
- 수정 [빌드 receipt](ENERGY_SAMPLER_PC_20260925.md)와 같은 APK SHA-256 `2874a97f93c21816fea683bd6403326443dd9c15e682919c4087788d22670931`, signer 인증서 SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`, 동일 package/versionCode 1. APK 포함 source hash가 빌드 receipt와 일치하여 **APK 재빌드 없음**. host 준비 코드만 새 namespace/lineage로 개정했다. 현재 설치본 해시·서명은 실행 직전 preflight로 다시 확인하며 이번에는 기기 조회하지 않았다.
- 새 개발/확인 전부 `energy-screen-filter-v1` 축소 조회·동일 2초 timeout/재시도 0을 쓴다. 구 547KB 전체 덤프 부분 결과와 관측 방법이 달라 합치지 않는다. 수정 sampler의 `energy-state-snapshot-v1`은 active/resident/phase를 짧은 공통 lock에서 복사한다. 센서·adapter 호출·저장은 lock 밖이다.

## 병행 경로와 PC 검증 범위

| pair | 직렬 대조 | 병행 | 적용 gate |
|---|---|---|---|
| CC_DG | 분류 CPU 678건 → 탐지 GPU 192건 | 각 lane 첫 호출 동시 dispatch 시도, lane 내부 순차 | 같은 단계 CC_DG 직렬의 적격성·품질/GPU 증거·baseline AP ±0.5°C |
| CG_DC | 분류 GPU 678건 → 탐지 CPU 192건 | 동일 방식 | 같은 단계 CG_DC 직렬의 동일 gate |

두 pair 모두 CPU/GPU 각각 전용 single-thread executor를 사용하고, 생성·호출·해제는 lane 소유 thread에서 이루어진다. scheduler는 `Future` 완료 후 실제 `lane_available`을 기록하고 inflight에서 제거한 뒤 다음 배정을 허용한다. 두 lane이 active일 때 sampler는 같은 snapshot/실패 sidecar 경로를 사용한다. failure는 예외·stack·thread·단계·시간을 남기고 중단/부분 회수/cleanup으로 이어진다. host는 앞선 **같은 단계 직렬 적격 세션** 없이는 병행 staging을 시작하지 않는다. API 호출 overlap과 한쪽만 남는 tail을 따로 검사하며 GPU kernel 동시 실행은 주장하지 않는다.

변경된 lineage/병행 gate·두 pair의 완료 실패 판독에 대한 Python 신규 3테스트 통과. Android source는 수정하지 않았고 [수정 APK 빌드 receipt](ENERGY_SAMPLER_PC_20260925.md)의 Kotlin core 6·snapshot 8 테스트와 직렬 실기기 1세션 결과를 해당 버전 근거로 재사용했다. 병행 실기기 동작은 **미검증**이다. 구체적인 추가 결함이 발견되지 않아 별도 병행 진단을 관행적으로 넣지 않았다. 상세 대상·명령·hash는 외부 `energy_collection_reprep_pc_v2/verification.json`을 따른다.

## 동결 계획·예산

개발은 CC_DG 직렬→병행→CG_DC 직렬→병행, 확인은 CG_DC pair→CC_DG pair로 순서를 바꾸되 각 pair의 직렬을 병행 앞에 둔다. 각 세션은 4 resident runtime·warmup 8·적격성 2·동일 입력의 작업 870건, CPU thread 1이다. 개발4 모두 적격일 때만 **개발 자료**의 조건별 구간 평균 기기 전체 전력/AP 경험적 값을 동결하고 hash를 남긴다. 확인4의 signed/absolute 오차만 기록하며 재보정하지 않는다. 정확도 허용폭이 없어 성능/절감 PASS는 부여하지 않는다.

| 항목 | 상한·산식 |
|---|---:|
| 세션 | 개발4＋확인4 = 8, 조건별 독립 세션 각 단계 1 |
| 진단 요청 | 8×(870작업＋2적격성) = 6,976 |
| warmup / 총 명시적 추론 | 8×8 = 64 / 6,976＋64 = 7,040 |
| runtime / staging | 8×4 = 32 / 8회×(6파일＋manifest) = 56파일 |
| APK 전송·설치 | 각각 최대1, 정확히 같은 설치본일 때만 생략 |
| 재시도·대체·추가 | 모두 0 |
| 고정 관측 | 8×(120초 resident baseline＋480초 공통창＋180초 cooling) = **104분** |
| timeout 합산 예약 | 설치10분＋동결10분＋8×(단계별 23분20초) = **206분40초**. 평균 예상 아님 |
| 전체 hard 상한 | 설치10분＋8×세션25분＋동결10분 = **220분**; 환경·회수·cleanup·냉각 포함 |

23분20초의 단계별 예약은 세션 staging/gate 120초, launch 20초, 앱 setup/warmup 150초, eligibility 30초, host arm 3×60초, baseline 120초, **post-work wait를 포함하는 공통 480초**, cooling 180초, close/전환 15초, 회수 60초, cleanup 45초의 합이다. host poll 1,220초와 앱 watchdog 1,200초는 앱 단계에 **겹치는 제한**이라 추가 합산하지 않는다. 실제 코드의 세션 hard 1,500초에는 단계별 예약보다 100초 여유가 있다. 206분40초는 각 예약이 모두 발생한다는 예측도, 정상 평균시간도 아니다. 진단 902.5초를 8배해 예상시간으로 사용하지 않는다. 배터리 완주 가능성은 미확인이다.

## dry-run과 남은 실행 gate

최종 `collection_plan.json` SHA-256 `a1399e2ffc5579f948ff4c7e6ec5637417f6baee947132b76cfcb42d75696719`. manifest8개/작업6,960건, APK/source/서명/입력·참조 해시, seed `2026092502`, 순서·gate·timeout·분석/동결 기준을 `-Action Check`로 검증해 `PC_READY_DEVICE_UNVERIFIED`, device commands 0을 얻었다. 이전 v5와 예산·screen·acceptance·analysis·입력/참조가 같음을 별도 대조했다. 새 run/registry는 아직 생성되지 않았다.

실행 승인은 **이번 작업에 포함되지 않는다**. 향후 실행 직전 현재 transport serial의 동일 A24/hardware/fingerprint, 설치본 package/version/signer/정확한 APK hash, 비충전 배터리 시작·실행 중 ≥20%·≤35°C, thermal0, awake/interactive·밝기81·수동0·5시간 설정, memory admission을 확인해야 한다. 각 병행 전에는 같은 단계 직렬 적격성·품질·실제 overlap·baseline AP gate를 다시 통과해야 한다. 실패·조회 불가·시간 부족이면 `stopped_no_resume`로 회수/cleanup 후 중단하며 재실행하지 않는다. 설정을 바꾸거나 기준을 완화하지 않는다.

PC에서 실행한 명령:

```powershell
python -B -m unittest tools.test_d1_energy_collection.EnergyCollectionTest.test_new_formal_lineage_excludes_stopped_and_diagnostic_samples tools.test_d1_energy_collection.EnergyCollectionTest.test_both_parallel_pairs_keep_distinct_lanes_and_reject_failed_completion tools.test_d1_energy_collection.EnergyCollectionTest.test_parallel_session_requires_same_stage_serial_before_staging
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_plan_v7/RUN_AFTER_APPROVAL.ps1' -Action Check
```

**별도 실행 승인 이후에만 가능한 명령**(현재 설치본/환경 gate는 실행기에서 재확인):

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_plan_v7/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<실행 직전 확인한 A24 transport serial>'
```

기존 독립 평가 FAIL·부분 결과·40개 동결값·20개 null·종료 계획과 `experiment_ready=false`는 유지한다. S26/NPU는 별도 협업이고 A24 계수를 전용하지 않는다.
