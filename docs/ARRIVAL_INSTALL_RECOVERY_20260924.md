# 설치 증거 보존·ARRIVAL-COLLECT-02 준비

## 2026-09-24 승인 실행 결과 — 배터리 gate 중단

`bceec84`/clean에서 미소비·해시·예산 확인 후 승인 스크립트를1회 호출했다. **배터리50%가 시작 기준55%보다 낮아 복구 preflight에서 종료됐다.** 복구시도1/verified0, 후보push0·install0, 수집phase claim0·개발0/6·확인0/6·진단0/48·warmup0/96·명시적추론0/144, retry/대체/추가0. 총12세션 미시도이며 실패세션1로 계산하지 않는다. 정확한APK 동일성에 따른 설치생략이 아니라 gate실패로 미진입한 것이다.

- 단일SM-A245N·동일fingerprint·설치본/후보의package/version1/signer일치 확인. 읽기 전용 기존APK 회수1회86.390초는 후보push 예산과 구분한다. 배터리50%/31.3°C/비충전. 배터리 이후 설치 전thermal/awake/설정gate와 앱memory admission은 미실시다.
- 명령12개 모두정상반환, 부분stdout/stderr·시간·exit를보존했다. 새timeout없음. 실패후hash조회에서기존설치APK9019b85d…2c0유지. 이것은과거설치timeout원인해결증거가아니다.
- hostcleanup/프로세스부재/cleanup thermal0확인. 앱session cleanup은미시작N/A. 화면/시스템설정변경없음. 복구91.156초, workflow92.297초(회수·조회·cleanup 포함), 최초기기조회tool wall상한0.495초를합쳐도92.792초. cooling/수집0, 승인600/6090초이내.
- 동결/확인/비용표본/PC연결없음. 병행차단·experiment_ready=false·기존40값/20null/FAIL/부분결과·과거원인미확정보존. PC시험/빌드반복없음.

복구 `install_recovery_run_v1/receipt.json`과통합 `collection_recovery_workflow_v1/stopped.json`으로 **소비·종료, 재개금지**다. 수집registry가없어도이통합계획을다시실행하지않는다. 아래명령과미승인표시는준비당시이력이다.

외부root의 `collection_recovery_execution_v1/FINAL_REPORT.md`, `FINAL_RECEIPT.json`, `REPRODUCE.py`(PC읽기전용), `GIT_FINAL.json`에종료보고·전체분모·명령별시간·원본hash를보존한다. 원본은 `install_recovery_run_v1/commands/000..011`과preflight/receipt, workflow claim/stopped다. Git에는문서만반영한다.

다음최소행동: **충전해시작55%이상에여유를확보하고비충전상태를준비**한뒤새식별자/출력/소비계획을PC에서준비한다. 현계획reset/재실행·자동추가설치/수집은하지않는다. 새자료가확보되기전B2/B3/P·독립평가의근거는늘지않았다.

2026-09-24, 시작 `b4c6e23`/feature/arrival-scheduling-20260923/clean. **PC 구현·검증·실행안 준비 완료. 새 기기 작업 미승인·미실행.** 복구 ID `ARRIVAL-INSTALL-RECOVERY-01`, 수집 ID `ARRIVAL-COLLECT-02`. 이전 [COLLECT-01](ARRIVAL_INTEGRATED_COLLECTION_20260924.md)은 설치1회 timeout·세션0·종료 상태 그대로이며 재개하지 않는다.

## 확인한 사실과 원인 한계

기존 host는 `Device.call`에서 `subprocess.run([...adb, -s, serial, install, -r, apk], capture_output=True, timeout=120)`을 호출했다. 기본 streaming 여부를 명시하는 옵션은 없었다. CAL-03 성공 출력에는 `Performing Streamed Install / Success`가 있지만 이번 실패는 출력이 보존되지 않아 같은 실제 전송 모드를 사용했는지도 관측으로 확정하지 않는다.

| 비교 | 기존 CAL-03 성공 | COLLECT-01 실패 |
|---|---|---|
| APK | 9019b85d…2c0,106,026,524bytes | d8db6963…34bc,106,042,908bytes |
| 크기 차이 | 기준 | +16,384bytes(약0.0155%) |
| 설치 명령/timeout | adb install -r /120초 | 동일 옵션/120초 |
| 설치 receipt 간격 | 개발29.839초, 확인29.545초 | 120.026초 후 timeout |
| 장치/패키지/서명 | 같은 A24·package/version1·프로젝트 signer | preflight에서 일치 확인 |
| 환경 | 같은 비충전·화면·thermal gate 계약 | 55%/31.1°C/thermal0/awake 확인 |

무선 전송률·패킷 손실·패키지 매니저 내부 상태를 동일하게 통제하거나 기록하지 않았다. 작은 APK 증가가 원인이라는 근거가 없다. 기존 설치본이 남았다는 사실만으로 전송 실패를 단정하지 않는다. GPU 또는 CAL-02 정지 원인과 연결하지 않는다.

확인된 **host 기록 결함**: `subprocess.run` timeout은 실행한 직접 자식 프로세스를 kill/wait한 뒤 `TimeoutExpired`를 올리는 경로지만, 호출자는 `repr(error)`만 저장했다. 예외의 stdout/stderr 속성과 직접 자식 종료 시점·exit code를 저장하지 않았다. 성공한 경우에만 install_result가 생성된다. subprocess.run의 직접 자식 종료를 전체 자식 트리 또는 기기 패키지 작업 종료 보장으로 확대할 수 없다. 이전 출력은 지금 복원할 수 없다.

이전 claim→설치75.180초는 서명 검사·설치 APK 회수·환경 조회를 합친 구간이다. 각 세부 비용은 기존 기록으로 분리할 수 없다. 설치→중단120.026초, 중단→host cleanup receipt0.687초, 합195.893초. 최종 읽기 전용 조회까지283.200초에 PC 대기가 포함되며 조회 자체는0.593초다. 원래 receipt와 일반 unknown 표기는 수정하지 않았다.

## 구현한 최소 보완

- [d1_recorded_process.py](../tools/d1_recorded_process.py): shell 없이 argv 실행, 비밀값 없는 표시 명령·UTC/monotonic 시작/종료·timeout 원인·PID/exit code를 기록한다. stdout/stderr를 처음부터 별도 바이너리 파일에 연결해 정상 반환 이전의 부분 bytes를 보존한다. PIPE drain 교착을 피한다. 프로그램 내부에서 아직 flush하지 않은 출력·강제 PC 종료/디스크 장애까지 복구한다고 주장하지 않는다.
- timeout/host 중단 시 실행한 host client 트리를 Windows `taskkill /PID /T /F`로 제한 종료하고 직접 자식을 reap한다(최대5초). 실패/미확인은 명시하며 기존 ADB server에 kill-server를 보내지 않는다. 정상 반환을 자손 전부 종료의 증거로 삼지 않는다. host client 종료가 기기 내부 pm 작업을 취소한다는 보장은 없다.
- [d1_collection_recovery.py](../tools/d1_collection_recovery.py): 새 복구에만 RecordedDevice를 사용해 preflight·전송·pm·설치 후 조회·cleanup의 각 명령 출력/시간/실패를 보존한다. 기존 종료 실행의 코드·receipt 의미는 바꾸지 않는다. 설치 실패와 조회 실패를 분리한다.
- 새 설치 방법은 **adb push → 원격 SHA-256 → adb shell pm install -r → 설치본 SHA-256**이다. `/data/local/tmp/d1check-arrival-install-recovery-01/candidate.apk` 새 경로만 쓰며 기존 경로가 있으면 중단한다. 모델/키를 전송하지 않는다. 임시 APK는 증거로 남기고 사용자 데이터·원본을 삭제하지 않는다.
- 이 방법은 기존 streamed install과 다르다. 약106MB의 별도 staging 전송·원격 저장/해시 비용이 추가되고, 어느 명령까지 성공했는지 구분할 수 있다. pm 내부의 세부 단계는 만들어 기록하지 않는다. 설치 timeout120초를 늘리는 수정은 아니다.
- 서명/기기/환경 preflight에서 **현재 설치본 APK bytes·package·version·signer가 후보와 모두 동일**하면 전송·설치를 생략한다. 단순 인증서 일치나 package 존재만으로 생략하지 않는다. post SHA 조회까지 성공해야 복구 verified다. SHA가 후보와 같으면 이미 PC apksigner로 검증한 동일 bytes의 package/version/signature에도 연결된다.
- 복구 성공 receipt는 collection plan hash와 원 증거 해시·cleanup 성공을 묶는다. 수집 시작 전 이를 검증하고 각 단계에서 현재 설치 APK의 정확한 동일성을 다시 preflight한다. **수집 단계 설치0**, 설치 불일치 시 중단한다. 직접 phase CLI로 전체 시간 상한을 우회하는 실행도 차단했다.

APK·Android 정책/계측/모델은 변경하지 않았다. `integrated_collection_apk_v1`의 빌드 receipt에 있는 Android source와 현재 source 대응, APK SHA-256, PC apksigner/package/version을 확인했다. 동일 APK를 다시 빌드하지 않았다. 변경은 host 복구·수집 연결과 관련 테스트/문서뿐이다.

## 한 번의 승인으로 실행할 새 통합안

| 구간 | 상한·소비 기준 |
|---|---|
| 복구 preflight·서명/설치본·환경 조회 | 200초. 새 복구 claim은 읽기 전용 gate 이전, 실패해도 재개 금지 |
| 새 APK 전송·원격 hash | 150초. push timeout120초, 나머지는 경로 검사/생성/hash/host client 종료. transfer intent 최대1 |
| 패키지 설치 | 125초. pm install timeout120초+client 종료 최대5초. install intent 최대1 |
| 설치 후 또는 실패 후 identity 조회 | 60초. post query가 실패하면 재조회하지 않고 실패를 보존 |
| 복구 cleanup | 45초. 앱 force-stop·프로세스 부재·thermal 확인. 식별 불가면 임의 기기를 종료하지 않고 미확인으로 기록 |
| 복구 기록/행정 예약 | 20초. 위 합계600초=10분, 각 stage는 남은 절대 deadline으로도 제한 |
| 개발 수집 | 2700초 작업(회수10초 예약 포함)+cleanup45초 |
| 확인 수집 | 2700초 작업(회수10초 예약 포함)+cleanup45초 |
| 전체 | **6090초=101.5분**, 복구·개발·확인 및 모든 기기 조회/회수/cleanup의 상한. 중간 PC 동결 경과도 다음 단계의 남은 시간에 반영. 최종 기기 종료 후 PC 결과 분석은 별도이며 추가 기기 작업 없음 |

수집의2700초에는 해당 단계 설치본 재검사, 입력 staging, cooling, 앱 실행, 관측, 정상/부분 회수, 검증과 세션별 cleanup을 모두 포함한다. 냉각은 기존대로 단계별 최초120초+사이5×120초, 합24분이다. 전체 예상은 약35~50분이며 무선/설치 상태에 따른 운영 추정일 뿐 보장이 없다. 정확히 같은 APK여서 설치를 생략하면 더 짧아질 수 있지만 예산을 추가 세션으로 전용하지 않는다.

최대 **설치1·APK전송1·세션12(개발6→동결→확인6)·진단48·warmup96·명시적추론144·runtime48**. retry·대체·추가0. 복구에서는 앱 실행·warmup·추론0이다. 다음 전체2745초를 확보할 수 없으면 수집 단계를 시작하지 않는다. 환경 이탈·연결/조회/출력/설치/적격성 실패는 즉시 종료하며 timeout 연장·설정 완화·재시도하지 않는다.

새 session/request UUID·출력/registry를 사용한다. 이전 계획과의 parent hash를 기록하며 과거 install1·0세션 기록을 숨기지 않는다. 복구 output과 workflow claim은 별도다. 수집 phase claim/attempt/Activity/호출 완료는 기존처럼 구분한다. 설치 복구가 검증되지 않으면 수집 phase 자체를 claim하지 않는다. 이후 단계 preflight 실패는 phase claim과 session attempt0을 구분한다.

동일 A24/서명·배터리 시작55%/이후30%·비충전·35°C이하·thermal0·현재5시간 screen timeout/밝기81수동/awake와 기존 앱 admission을 유지한다. 이번 후보는 화면 설정 변경을 하지 않는다. 승인 시 화면 유지 조건이 다르면 자동 수정하지 않고 실행 전 차이를 해결해야 한다.

수집 조건 A/B/C/D/E/F, 개발ABCDEF/확인EDCBAF, seed2026092402, task·priority·도착·warmup·병행 안전 gate와 분석/동결 규칙은 [기존 수집 설계](ARRIVAL_INTEGRATED_COLLECTION_20260924.md)와 같다. 모델별 입력·배정은 유지하고 session/request 식별자만 새로 만들었다. 설치 문제가 해결돼도 수집 적격성·GPU 병행·정확도·정책 성능 PASS가 아니다.

## PC 검증과 실행 준비 파일

[test_d1_collection_recovery.py](../tools/test_d1_collection_recovery.py)15건+기존 collection13건, 합28건 통과(27건 묶음 및 추가 workflow1건, skip0). 변경 위험에 맞춰 비정상 exit·부분 stdout/stderr·실제 PC Python 자식/손자 timeout 종료·실행파일 부재, 조회 실패, exact APK 생략, 전송/설치 실패 no retry, post 조회 재시도 없음, 복구 증거 변조, 설치 전 collection 차단, 전체 deadline 우회 차단, 개발 동결 전 확인 금지·workflow 재개 금지와 workload/UUID 대응을 검증했다. PC mock은 실제 GPU/무선/pm 복구 성공 증거가 아니다. Android/전체 빌드·기존 실측 감사를 반복하지 않았다.

외부 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`:

- `collection_recovery_plan_v1/recovery_plan.json`: SHA `c98dc6f280ff8431f6506ff0a375af64821b3fa609ed219a1dbd319124198ff4`.
- 같은 폴더 `collection_plan.json`: SHA `1a0352c1a6a8e5fd5c00cd4c53ee7b7bbce867f62cfb1ecaa0340ce98d8e48aa`, manifests12, RUN_AFTER_APPROVAL.ps1.
- `install_recovery_pc_v1/FINAL_REPORT.md`, VERIFICATION.json, tests.log, workflow_test.log, REPRODUCE.ps1.
- 실행 예정: `install_recovery_run_v1`(설치 복구), `collection_recovery_workflow_v1`(통합 claim/동결/확인/종료), `integrated_collection_run_v2` 및 `collection_execution_registry/ARRIVAL-COLLECT-02`(수집). 준비 시 모두 미생성이다.

```powershell
$script='C:/Users/LG/Documents/D1Check_Arrival_Extension/collection_recovery_plan_v1/RUN_AFTER_APPROVAL.ps1'
& $script -Action Check # PC only
# 새 통합 예산 승인 후에만; 성공 gate는 같은 호출 안에서 자동 진행:
& $script -Action Run -Approved -Serial '<당일 확인한 A24 serial>'
```

실제 CLI는 `python -B -m tools.d1_collection_recovery check/run --plan ...`이다. Run은 복구→개발6→회수 hash/기술통계 동결→확인6→확인 차이 보고까지 수행한다. 한 번 실패하면 같은 계획을 다시 실행할 수 없다. PC check는 소비 기록·가상 실측을 만들지 않고 ADB도 호출하지 않는다.

**experiment_ready=false** 유지. 새 표본 없이 PC 병행 차단을 해제하지 않는다. 기존40값/20null·FAIL/부분결과/종료계획 불변. 다음 필요한 외부 결정은 이 새 통합 예산의 승인 한 번이며, 이번 작업에서 실행하지 않았다.
