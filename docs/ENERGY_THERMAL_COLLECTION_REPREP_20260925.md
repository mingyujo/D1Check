# ENERGY-THERMAL-COLLECTION-REPREP-03 — 직렬/병행 수집 재준비

2026-09-25, 시작 `bfd8594988cad107c50a6cb9ed0d58c5249d7047`, 작업 브랜치 `feature/arrival-scheduling-20260923`, 시작 clean. 기존 수집 프로세스 없음과 COLLECT-02 registry의 stopped 상태를 확인했다. 이번 작업은 PC 준비만이며 **새 계획은 미승인·미실행**이다. 기존 계획을 재개하지 않는다.

## 확인·변경

실제 `d1_energy_collection_device.gates/poll`은 `d1_energy_screen.snapshot`을 이미 공유한다. 진단 전용 구현을 수집기에 새로 이식할 필요는 없었다. 두 경로 모두 bytes→UTF-8→필수 화면 두 값 및 producer 종료표시 단일성/0 검사다. 비정상 client exit/timeout은 ObservedDevice에서 예외로 전달되어 gate를 통과하지 못한다. 새 조회 2초, 직전 snapshot 종료 후 최소10초, 재시도0, 조회 불가 중단은 유지한다. 상태 위반과 query_unavailable은 별도 기록한다.

수집 배터리는 bytes.decode→기존 문자열 parser로 이미 연결되어 있었다(조회5초). 진단은 strict decode 후 동일 parser(조회2초)다. 수집 thermal은 bytes.decode→logger parser, 진단은 bytes regex다. 설정 조회는 양쪽 모두 decode 후 문자열 비교다. 이 차이는 기존 계약 그대로이며 bytes를 문자열 parser에 직접 넘기는 결함은 수집 경로에서 발견되지 않았다.

새 `ENERGY-THERMAL-COLLECT-03` / plan_v5 / run_v3 / 별도 registry를 준비했다. 새 session UUID와 기기 설치 임시 경로를 분리하고 계획에 `energy-screen-filter-v1` 관측 계약을 명시·검사한다. 모델·입력·APK·조건·순서·seed·gate·분석/동결 기준·timeout·작업량은 v4와 대조해 동일함을 확인했다. Android 변경·APK 재빌드 없음. APK source/hash/프로젝트 signer를 PC에서 재검증했다.

기존 전체 dumpsys 전송(완료31회 중앙547,581bytes)과 필터 전송(무추론32회 각각76bytes)은 관측 방식이 다르다. **새 개발4·확인4 모두 같은 필터**를 사용한다. 옛 중단 세션을 새 비교 표본에 합치거나 누락분만 보충하지 않는다. 내부 dumpsys 생성 비용 감소·부하 안정성·과거 timeout 해결은 미입증이다. 옛 부분125.4J/314.2J는 조건부 단위 해석과 불완전 관측의 한계를 유지한다.

## PC 검증

- 저장된 실제 ADB 반환 bytes를 transport에서 반환하고 **실제 collection gates/identify/battery/thermal/screen/settings 및 cleanup 함수**를 실행했다. parser를 mock하지 않았다. 과거 서로 다른 조회의 fixture를 조합한 소프트웨어 검증이며 현재 기기 상태를 뜻하지 않는다.
- 6사례: 실제 원문 gate/cleanup, 주입 timeout, 비정상 client exit 전달, producer marker 실패, 화면 상태 위반, 실제 cat 오류를 cleanup JSON으로 오인하지 않는 부분 회수. 실패 조회 재호출 없음, cleanup deadline 복원 확인. 비정상 exit/상태 변형은 fault injection이며 실기기 실패 재현이 아니다.
- 관련 collection/screen 24테스트 통과: 시간 경계·overlap/tail·분모·부분 호출 불확실성·설치 실패의 유한 cleanup·회수 실패·경로 탈출·승인/소비 차단·부분 stdout timeout 등을 포함한다. 무관한 전체 테스트/빌드 없음.
- 실제 생성 script `-Action Check` 통과. APK/서명/입력/manifest/source hash 검증, 새 run/registry 부재 확인. ADB/설치/앱/실측/설정 변경/소비 claim은 모두0.
- 검증 대상 파일 hash·명령·시점·시작 HEAD와 미커밋 여부: [작은 검증 기록](results/energy_collection_reprep_03/verification.json). 상세 원문 출처 hash는 외부 `energy_collection_reprep_pc_v1/fixture_verification.json`.

## 조건·예산

개발: 분류CPU+탐지GPU 직렬→병행→분류GPU+탐지CPU 직렬→병행. 확인: 두 pair 순서를 반대로 하되 각 pair 직렬→병행. 각 세션 분류678·탐지192의 같은 작업/입력/backend, 적격성 각1, warmup8, runtime4. host API overlap과 한쪽만 남는 tail을 구분한다. 병행 전 같은 단계 직렬 적격성, 품질/GPU 증거/실제 lane 해제를 확인한다. 개발4 적격 후에만 기존 방식으로 설정·hash 동결, 확인4에서 재보정 금지. accuracy margin은 여전히 미정이며 기록 적격성을 정확도/최적화 PASS로 바꾸지 않는다.

| 항목 | 새 계획 상한 |
|---|---:|
| 세션 | 개발4 + 확인4 = 8 |
| 진단 | 작업6,960 + 적격성16 = 6,976 |
| warmup / 총 명시적 추론 | 64 / 7,040 |
| runtime 생성 | 32 |
| 입력 staging / 파일 | 8 / 56 |
| APK 전송 / 설치 | 각각 최대1, 정확히 같은 설치본이면 생략 |
| 재시도 / 대체 / 추가 | 모두0 |
| 고정 관측 | 8×(120+480+180)초 = 104분 |
| 기존 timeout 합산 예약 | 206분40초 — 정상 예상시간이 아님 |
| 전체 hard 상한 | 220분 = 설치10 + 8×세션25 + 동결10 |

세션25분에는 gate/staging120초, launch≤20초, host poll1220초, 회수60초, cleanup45초와 여유35초가 포함된다. 앱 watchdog1200초와 host poll1220초는 겹치는 제한이며 별도 합산하지 않는다. 냉각·환경 확인·회수·cleanup·동결을 상한 밖으로 빼지 않는다. **정상 평균 소요시간과 배터리 완주 가능성은 미확인**이다.

## 남은 실행 gate·다음 행동

별도 실행 승인 후에만 현재 transport serial·동일 SM-A245N/hardware/fingerprint·설치본 서명/정확한 APK hash를 조회한다. 이번에는 현재 연결·설치본·환경을 조회하지 않았다. 시작/실행 중 배터리≥20%, 비충전, 배터리≤35°C, thermal0, Awake/interactive, 밝기81·수동0·자동꺼짐18,000,000ms(5시간)를 유지한다. 임의 설정 변경 금지. 앱 내부 memory admission·4 resident/runtime 소유권·품질·병행 적격성·pair baseline AP±0.5°C gate는 실제 실행 중 확인한다. 실패/시간 부족 시 회수·cleanup 후 stopped_no_resume, 재실행 금지.

추가 무추론 또는 별도 부하 진단을 관행적으로 넣지 않는다. 이미 무추론32조회가 완료됐으며 PC 검토에서 추가 진단으로만 해소할 새로운 결함은 발견하지 않았다. 부하 중 조회 지연은 여전히 불확실하고 새 수집의 동일2초 중단 규칙으로 다룬다. 다음 최소 행동은 **이 후보 예산의 별도 실행 승인과 실행 직전 gate 확인**이다.

기존 FAIL·부분 결과·40개 동결값·20개 null·종료계획·experiment_ready=false 보존. S26/NPU 협업 별도 유지, A24 계수 전용 없음.

## 로컬 준비 파일·명령

외부 root `C:/Users/LG/Documents/D1Check_Arrival_Extension`는 GitHub에 포함되지 않는다.
- 계획 `energy_collection_plan_v5/collection_plan.json`, manifest8개 및 `RUN_AFTER_APPROVAL.ps1`
- 새 출력 `energy_collection_run_v3` / 소비 registry `energy_collection_registry/ENERGY-THERMAL-COLLECT-03`: 아직 생성하지 않음
- 상세 PC 보고서 `energy_collection_reprep_pc_v1/FINAL_REPORT.md`
- 재사용 APK `energy_collection_build_v5/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`
- 계획 SHA-256 `8285b8d9d4d4fac9e70477d50ee6875aef3075c042e60ae71a600d3ee65cc01e`
- APK SHA-256 `1e58655af1ede00062277669c718fd0881f5aadba31c0ed122445b7d0990d8e7`
- signer SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`

PC에서 실제 확인한 명령:
```powershell
python -B -m unittest tools.test_d1_energy_collection tools.test_d1_energy_screen
python -B -m tools.d1_energy_collection_fixture_check --root C:/Users/LG/Documents/D1Check_Arrival_Extension --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_plan_v4/collection_plan.json --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_reprep_pc_v1/fixture_verification.json
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_plan_v5/RUN_AFTER_APPROVAL.ps1' -Action Check
```
fixture 출력은 신규 파일이어야 한다. fixture는 v4 gate에 대해 검증했고 새 v5의 모든 gate 값/조건이 동일함을 별도 대조했다. 실행 코드는 검증 당시 새 host 버전이다.

**향후 승인 후에만 실행할 명령(이번에 미실행):**
```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_plan_v5/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<실행 직전 확인한 A24 transport serial>'
```
