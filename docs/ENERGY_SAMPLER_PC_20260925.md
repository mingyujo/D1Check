# ENERGY-SAMPLER-PC-01 — COLLECT-03 예외의 PC 재현·보완

시작 `bb38b1db2b65d97c55c8e216b1cd892fe670b7d8`, `feature/arrival-scheduling-20260923`, clean. ADB·설치·기기 조회·실측·설정 변경0. 과거 COLLECT-03은 stopped_no_resume로 보존한다.

## 결론과 원인 수준

**수정 전 실제 Kotlin `active.toMap()` 표현의 결함을 PC에서 제어된 스레드 교차로 재현했다.** ConcurrentHashMap size가1이라고 관측된 뒤 다른 스레드가 마지막 항목을 제거하면 Kotlin singleton 변환 경로가 빈 iterator의 next를 호출해 NoSuchElementException을 발생시킨다. 테스트는 실제 ConcurrentHashMap을 사용하고 size getter에 latch만 삽입하여 이 순서를 강제한다. 반복 stress로 우연히 잡은 결과가 아니다.

**이것이 과거 COLLECT-03의 정확한 발생 지점이었다고 확정하지 않는다.** 원본에는 sampler catch의 예외 종류만 있고 stack이 없다. 원본9407행/cleanup/receipt를 대조했으며 원 diagnostic647~872 등 보수적 범위와 기록상654 host inference 성공은 소급 변경하지 않는다. 화면23/23성공·부분139.1J/191.8J·단위/미완료 한계도 그대로다.

| 공유 상태/경로 | 수정 전 소유권·위험 | 이번 처리 |
|---|---|---|
| active put/remove | setup scheduler가 dispatch/실제 Future 완료 후 갱신, sampler 및 lane admission이 toMap 읽기 | 동일 짧은 lock 아래 갱신·복사, 실제 완료 기반 해제 불변 |
| runtimes put/get/keys/close 순회 | CPU/GPU owner가 생성 후 put, worker get, sampler keys, closeLane filterKeys/values | 같은 상태 lock으로 참조/목록 복사 후 사용·close는 원래 owner executor에서 lock 밖 수행 |
| phase | setup 갱신, volatile 단독 읽기; map들과 원자적 아님 | active/resident와 동일 lock의 snapshot에 phase 포함; event가 sample의 캡처 phase를 덮어쓰지 않음 |
| peak/interactive | 동일 snapshot에서 반복 조회하여 값이 달라질 수 있음 | peak와 interactive를 한 번 읽어 gate와 저장 필드가 같은 값을 사용 |
| inflight/remaining/next/completed | setup 한 스레드에 한정, keys.toList 후 자체 수정 | 변경 없음. sampler가 이 컬렉션을 읽지 않음 |
| 이벤트 seq/JSON/queue | event synchronized, detached payload 직렬화, bounded writer | sample은 detached map만 전달. 실패 sidecar/cleanup은 active를 다시 읽지 않음 |
| stop/progress failure | atomic; sampler는 문자열만 보존 | detached exception 증거 게시→stop→별도 실패 파일, 기록 실패도 별도 보존 |

다른 NoSuchElement 경로도 확인했다. runtime.getValue는 키 미존재 시 예외가 가능하지만 정상 setup 반환 이후 해당 key만 사용하며 sampler가 호출하지 않는다. runtimes keys는 생성 동안 추가만 되고 cleanup까지 제거되지 않는다. V4Gate는 수치 조건식이고, JSON 변환은 주어진 Map/Iterable 순회이며 빈 first/single 호출이 없다. EnergyProgress는 nullable poll을 검사한다. Android memory/battery/power API 내부 예외는 PC로 배제할 수 없다. `snapshot()`과 event/JSON 어느 지점의 예외였는지는 과거 stack 부재로 미확정이다.

## 최소 수정과 계측 의미

새 `EnergyObservedState`는 active·resident keys·phase·version·monotonic capture 시간을 하나의 짧은 잠금에서 복사한다. 잠금 안에는 작은 메모리 갱신/복사·clock 읽기만 있고 파일 쓰기·추론·센서 조회·ADB·runtime 생성/해제는 없다. 외부에 mutable 원본 map을 노출하지 않는다. CPU/GPU 생성·사용·해제 thread는 바꾸지 않았다.

기존 current/voltage/charge/temperature/thermal/admission/active/resident 필드와 단위·완료 경계를 보존했다. `observation_version=energy-state-snapshot-v1`, `state_version`, `snapshot_start_ns`, `sensor_read_end_ns`, `state_snapshot_ns`를 추가했다. **배터리·메모리·thermal 하드웨어 값 전체가 동일 순간의 원자적 표본이라는 뜻은 아니다.** 센서는 순차 조회하고 이후 소프트웨어 상태를 복사하므로 이 시간 구간 차이를 공개한다. active는 기존처럼 dispatch 이후 lane available 처리 시점까지의 상태이며 GPU kernel 점유를 뜻하지 않는다.

`EnergySamplerGuard.tick`은 Activity가 실제 호출하는 경로다. 실패하면 정상 표본을 만들지 않고 예외 클래스·메시지·stack(cause 포함)·session·phase·stage·thread ID/name·monotonic 시각을 detached 객체로 게시한다. 그 뒤 stop을 알리고 `sampler_failure.json`을 별도 동기 저장한다. 재진입은 정상 표본을 재생성하지 않는다. session catch도 `session_failure.json`에 stack을 저장한다. sidecar 저장이 실패하면 첫 예외 객체와 추가 기록 실패 stack을 메모리에 유지하고 cleanup.json에 함께 기록한다. 실패 증거 생성은 active/runtime snapshot을 재호출하지 않는다.

정상 progress는 기존 비동기 writer/1초 sync를 유지하며 동기 sidecar는 실패 경로에만 있다. 추가 lock/copy/필드의 관측 비용은 미측정이다. 저장소 자체 고장·강제종료/native crash에서는 파일 또는 finally 성공을 보장하지 않는다. 실패 파일/cleanup이 없으면 미확인이지 성공이 아니다. host는 기존 manifest/progress/cleanup 우선순위와 15초 실패 회수·45초 cleanup 예약 안에서 두 실패 파일도 회수 시도하며 회수 오류를 따로 남긴다. timeout/재시도/작업량/gate 불변. 새 host receipt는 실패 감지 시각과 최종 회수/cleanup 포함 elapsed를 분리한다. 옛 receipt는 수정하지 않는다.

수정 APK는 새 측정 계보다. 과거 부분 에너지를 새 APK의 정상 비교 표본과 합치지 않는다. 이후 정식 개발/확인에서는 같은 새 APK·관측 경로를 양쪽에 사용해야 한다.

## PC 검증·제한

수정 전 표현 재현, detached 상태/필드, snapshot 중 release 차단, adapter use/close의 lock 밖 참조, 실패 증거·stop, 기록 실패, lifecycle 취소, 저장 지연과 cleanup 증거 게시 순서를 검증했다. 기존 core의 비선점/lane 해제/직렬·병행 선택/timeout/비동기 writer 테스트도 해당 변경의 회귀로만 실행했다. Android Activity 자체의 OS API/GPU/native 안정성·실제 fsync 지연을 PC 검증으로 확인했다고 하지 않는다.

Kotlin 최종14건(새8+core6), Python20건(새 진단 예산/식별 차단·1세션 종료3+관련17)을 대상으로 한다. 실제 결과·명령·hash는 [검증 기록](results/energy_sampler_pc_01/verification.json)에 고정한다. 첫 PC 빌드/후보 v1은13건 통과 후 evidence 게시 순서를 추가 보완하여 최종 v2로 대체했으며 두 산출물 모두 보존한다. 기기 실행은 모두0이다. host 테스트 추가 중 들여쓰기 오류로 import1회 실패했고 수정 후20건 통과했다. 이는 테스트 코드 편집 오류이며 실제 기기 실행 실패가 아니다.

## 최소 후속 후보 — 별도 부하 진단1세션

무추론 반복은 이번 race가 생긴 active map의 갱신을 재현하지 못한다. 전체8세션 전에 **실패한 원래 CC_DG 직렬 세션1개**를 유지하는 것이 최소 후보다. 분류644건 부근에서 중단됐으므로 호출1~수건 smoke로 축소하지 않는다. 새 프로세스의4 resident→원래 warmup8→적격성2→baseline120초→분류678/탐지192 직렬→480초 공통창의 남은 대기→resident cooling180초를 유지한다. 원래 workload·timeout을 바꾸는 별도 축소 app 모드는 추가하지 않는다.

| 항목 | 후보 상한 |
|---|---:|
| 계획 / 세션 | ENERGY-SAMPLER-LOAD-DIAG-01 / 1 |
| 개발·확인·동결 | 모두0, 진단 전용 |
| runtime | 4 |
| 작업 / 적격성 / 진단 | 870 / 2 / 872 |
| warmup / 총 명시적 추론 | 8 / 880 |
| 입력 staging | 1회·7파일 |
| APK 전송 / 업데이트 설치 | 각각 최대1, 정확히 같은 새 APK면 생략 |
| 재시도·대체·추가 | 모두0 |
| 고정 관측 | 120+480+180=780초(13분) |
| 설치·서명/환경/확인/cleanup | 600초 |
| 세션 gate/staging·실행·회수·cleanup | 1500초 |
| 전체 상한 | 2100초(35분) |

35분은 예약 상한이지 평균 예상시간이 아니다. 세션 staging/gate120초, launch≤20초, host poll1220초, 회수60초, cleanup45초·여유35초; 앱 watchdog1200초와 hostpoll은 겹치므로 중복 합산하지 않는다. runtime/호출30초, setup150초, probe30초, 각host arm60초, load480초, 화면조회2초 모두 유지한다. 기기/배터리≥20%·비충전·≤35°C/thermal0/awake/밝기81·수동0·5시간/memory/품질/서명 동일성 gate를 완화하지 않는다. 현재 기기 상태·설치본은 이번에 조회하지 않았다.

성공 기준: 원래 870작업과2적격성/8warmup의 완전한 시작·완료·실제 lane 해제, 순서/품질/동일성/기존 기록 적격성 gate, 새 state snapshot 필드·시간구간·active⊆resident 확인, sampler/session 예외 없음, 정상 앱/host cleanup·프로세스부재. 성공해도 한 직렬 세션에서 새 경로가 동작했다는 범위다. 병행 안정성·반복 안정성·과거 원인 해결·에너지 절감·정식 보정 PASS는 아니다.

실패/조회 불가/시간 부족이면 기존 중단·부분회수·cleanup 후 종료하며 재실행하지 않는다. stack 증거가 없으면 원인 미확정으로 유지한다. **진단 자료는 정식 개발/확인 표본으로 사후 전용하지 않는다.** 성공 시에만 다음 정식 수집 준비의 필요조건을 검토하며 새8세션 계획이나 실행은 자동 진행하지 않는다.

## 준비 파일과 명령

외부 root `C:/Users/LG/Documents/D1Check_Arrival_Extension`(GitHub 미포함):
- 최종 APK/빌드·테스트: `energy_sampler_build_v2/build_receipt.json`, `build.log`, 격리 `build/`
- 최종 계획/manifest/script: `energy_sampler_load_plan_v2/`
- 미생성 실행 root `energy_sampler_load_run_v1`, registry `energy_collection_registry/ENERGY-SAMPLER-LOAD-DIAG-01`
- PC 보고서/검증: `energy_sampler_pc_v1/`
- v1 APK/계획은 PC 후보 이력이고 새 코드 identity와 맞지 않아 실행 대상이 아니다.

```powershell
python -B -m unittest tools.test_d1_energy_collection
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_sampler_load_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Check
# 아래는 별도 승인과 실행 직전 gate 확인 후에만 가능. 이번 작업에서는 미실행.
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_sampler_load_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<동일 A24의 현재 transport serial>'
```

기존 FAIL·부분 결과·40값·20null·종료계획·원본·experiment_ready=false와 S26/NPU 별도 협업을 유지한다.

최종 계획 SHA-256 `2fae1bf99d59ccade283e8ff2f8022cf2a025b9b7fe8b1c23d9f925c44e7fa84`, APK SHA-256 `2874a97f93c21816fea683bd6403326443dd9c15e682919c4087788d22670931`. 프로젝트 signer `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`, package/versionCode 유지. Kotlin14/Python20 및 최종 Check 통과, 새 run/claim 없음.
