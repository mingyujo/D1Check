# ENERGY-SCREEN-OBSERVE-01

사용자 승인: 별도1진단·화면최대32회·전체기기 준비/조회/회수/cleanup480초, 조회2초 유지, 설치/앱/runtime/warmup/추론/설정변경/재시도/대체/추가0. 이전 수집은 stopped_no_resume 그대로다.

사전 고정: 기존 수집과 같이 직전 화면 snapshot 종료 후 **최소10초** 지나 다음 화면을 조회한다(시작간격10초 고정이 아님). 다른 수집의thermal/listing 혼합은 재현하지 않는다.31간격310초+화면 client최대64초+gate/기록/명령 overhead가 소요되며 전체480초 제한과 마지막60초 정리 예약을 적용한다. 따라서 지연이 쌓여 예약이 부족하면32회를 강행하지 않고 중단한다. 마지막 조회 뒤 불필요한10초 대기는 없다. 준비60초, 이후 hard deadline으로 제한한다.

동일A24 fingerprint/hardware serial·앱 미실행 확인 후 각 조회 전 배터리≥20%/비충전/≤35°C/thermal0, 첫/마지막 화면조회에서 밝기81/manual0/timeout18000000을 읽는다. 화면 두 상태는32회 예산 안의 각 신규 조회에서 검사한다. 별도 사전 power조회로32회를 초과하지 않는다. 중간 설정변경은 연속 확인하지 못한다. 다른 실측 프로세스가 없을 때만 진행한다.

producer exit0·유일한 두 필수상태·정상client종료만 성공이다. 부분 정상문자열을 timeout 성공으로 바꾸지 않는다. 실패하면 단일client 종료/기록 후 종료하며 앱/daemon을 종료하거나 설정을 쓰지 않는다. 원문stdout/stderr·exit/시각은 host_commands, 상태판정은screen_observations, 분모는attempt/FINAL_RECEIPT다.

PC 준비9테스트 통과(새runner2+기존screen7). PC mock 성공은 기기성공 아님. 계획 `Documents/D1Check_Arrival_Extension/energy_screen_observe_plan_v1/plan.json`, 실행script `RUN_AFTER_APPROVAL.ps1`; source hash 고정, 출력/registry 신규1회용이다. 실행 명령은 이 script의 `-Action Run -Approved -Serial <현재 A24 transport serial>`이다. Check는ADB없음.

성공 범위는 무추론 환경의 필터/종료표시/상태판독·시간기록 확인뿐이다. 이전 부하31조회와 latency 비교는 조건불일치 기술통계다. 내부dumpsys생성비용·부하중안정성·이전원인해결·에너지절감/모형보정에 쓰지 않는다. experiment_ready=false와 기존FAIL/부분에너지/동결값 유지.

## 실행 결과 — 준비 단계 host 결함으로 종료

2026-09-25 사용자 승인으로 별도 계획1개를 claim하고 실행했다. 동일A24 모델/serial/fingerprint 및 앱 프로세스 부재는 확인했다. 첫 배터리 조회 원문은90%·비충전·29.2°C였으나, wrapper가 bytes를 기존 문자열 regex parser에 전달해 `TypeError: cannot use a string pattern on a bytes-like object`를 발생시켰다. **환경 gate 통과 판정 전에 중단**됐으며 thermal/화면 상태와 설정은 이번 실행에서 미확인이다. 이는 화면 query timeout이나 기기 상태 위반이 아니라 새 host runner의 구현 결함이다.

- 진단 claim1/종료1, 화면 조회 시도0/32·성공0/32. 지연 중앙값/최대/출력량 통계는 **미산출**이며0초로 쓰지 않는다.
- 설치·앱 시작·runtime·warmup·추론·설정 변경·재시도·대체·추가 모두0.
- claim→종료 기록3.141초, 전체480초 이내. 시작한 read-only ADB client는 반환/정리 확인. 앱/daemon을 종료하지 않았다.
- plan/registry `stopped_no_resume`. 수정 후 다시 실행하지 않았고 새계획/registry도 만들지 않았다.

## PC 수정과 검증

배터리 원시bytes 파일을 보존한 채 UTF-8 strict decode 후 기존 battery_gate에 전달하도록 한 줄 수정했다. 초기9테스트의 runner 모의검증은 environment를 mock해서 이 경계를 놓쳤다. 실제 legacy parser를 사용하는 bytes 입력 및 기준미달 차단 회귀테스트를 추가하여 **10건 통과**했다. mock 성공 출력32행은 실기기 조회32회가 아니다. 실제 실행값은0회다.

실행 당시 미커밋 runner는 external `executed_runner.py`에 보존했고 원plan source hash와 일치함을 확인했다. 수정후 source hash는 검증JSON에 별도로 기록했다. 종료plan은 수정하지 않는다. APK·화면 필터·2초timeout은 변경하지 않았다.

이 실행에서는 수정된 필터의 기기 명령 자체를 실행하지 못했으므로 상태판독·producer marker·기기시간·부하중안정성 모두 미검증이다. 이전31회와 비교할 새 latency가 없다. 에너지/발열 보정에 사용하지 않는다. 기존 stopped 수집/FAIL/부분125.4J·314.2J/40값/20null/experiment_ready=false 보존.

## 근거·다음 최소 행동

외부 로컬 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_screen_observe_plan_v1/` 및 `energy_screen_observe_run_v1/FINAL_RECEIPT.json`, `00_battery.txt`, `identity.json`, `host_commands/`, `executed_runner.py`. [작은 receipt](results/energy_screen_observe_01/receipt.json), [PC 검증/hash](results/energy_screen_observe_01/verification.json).

PC 재현: `python -B -m unittest tools.test_d1_energy_screen_observe tools.test_d1_energy_screen -q`.
과거 실행 명령: `powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_screen_observe_plan_v1/RUN_AFTER_APPROVAL.ps1 -Action Run -Approved -Serial adb-R59W802RW5F-yZ5QCN._adb-tls-connect._tcp` — **소비된 계획이므로 재실행 금지**.

다음 최소 행동은 별도 승인하에 수정본의 같은 무추론 화면진단만 새ID/계획으로 확인하는 것이다. 이번 승인으로 재시도하거나 전체8세션 수집을 진행하지 않는다.
