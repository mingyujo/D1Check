# ENERGY-SCREEN-OBSERVE-02 — 무추론 화면 조회32회 완료

## 결과

시작 `4c08a79`/clean, `feature/arrival-scheduling-20260923`. 최신 사용자 승인으로 새ID/plan_v2/run_v2/registry를 사용했다. 기존 OBSERVE-01 및 에너지 수집 stopped_no_resume를 보존하며 재개하지 않았다.

**32시도/32성공/실패0/미시도0**, 총335.297초(5분35.3초)/상한480초. 설치·앱 실행·runtime·warmup·추론·설정 변경·재시도·대체·추가0. 시작한 client는 모두 반환·정리됐으며 앱/ADB daemon 종료를 하지 않았다. 최종 상태 completed_observation_only다.

| 항목 | 이번 무추론 필터 조회32회 | 이전 부하 중 완료31회 |
|---|---:|---:|
| 지연 중앙값 |0.578초|0.422초|
| 지연 최대 |0.828초|0.687초|
| 출력 바이트 |각76|중앙547581|
| timeout |0/32|전체32시도 중1|

이번 지연은 더 짧지 않았다. 전송 출력은 줄었지만 부하·시간·host 명령 구성이 달라 paired 속도/에너지 비교가 아니다. 모든 exit code0·stderr0·Awake/interactive=true·producer exit marker0이 실제 원문에서 확인됐다. 전체 관측 중간의 연속 상태나 향후 성공률을 보장하지 않는다.

## 실행 전 경계 검증

bytes→UTF-8 strict decode→실제 legacy battery parser 수정 확인. 기존 OBSERVE-01의00_battery.txt와 에너지 실행 host_commands의 실제 thermal/settings stdout.bin을 반환하는 읽기전용 transport 재생으로 **실제 environment/screen parser 경로**를 통과시켰다. thermal은bytes regex, 설정은decode 후 문자열 비교여서 같은 형식 오류가 없었다. 화면 원문 필터와 종료marker의 PC 재생은 합성marker였고, 이번 실기기32회에서 실제marker를 별도로 확인했다. 파서를 우회하는 mock만으로 승인하지 않았다. 수정되지 않은 기존10테스트는 반복하지 않았고 plan 생성·Check 및 source hash 결합을 새로 확인했다.

## 조건과 간격

동일 SM-A245N/hardware R59W802RW5F/fingerprint 일치, 앱 프로세스 부재 확인. transport는 기존 wireless ADB 그대로다. 배터리88~89%·비충전·29.1~29.2°C, 매조회전 thermal0. 첫/마지막 밝기81/manual0/자동꺼짐18000000ms 확인, 설정변경 없음. 앱 memory admission은 앱을 시작하지 않는 이 진단의 대상이 아니다.

기존 수집처럼 직전 snapshot **종료 후 최소10초**를 적용했다. 실제 query_start−직전host_end는10.000~10.031초. 첫준비60초, 전체480초, 마지막60초 정리예약·각client2초를 유지했다. 추가 사전 power 조회 없이 승인32회 안에서 화면gate를 확인했다. 관측 구간 밖 및 첫/마지막 사이 설정 변경은 지속 검증하지 않았다.

## 검증 범위와 다음 행동

검증된 것은 **이 무추론1회 실행에서** 새 device-shell quoting/grep·필수상태·producer종료marker·시간/exit/원문 보존·client 종료가 동작했다는 점이다. 과거 timeout 원인 해결·부하중안정성·dumpsys 내부생성비용 감소·에너지절감/열보정·정책우월성은 검증하지 않았다. 이전125.4J/314.2J의 단위/불완전 한계·기존FAIL/부분결과/40값/20null·experiment_ready=false 유지.

다음 최소 행동은 추가 기기 실행이 아니라 **에너지 수집 재준비 여부의 PC 검토**다. 새 관측 방식이 실제부하에서 아직 미검증임을 명시하고, 관측오버헤드가 다른 예전 부분자료를 새로운 보정자료와 동일 표본으로 합치지 않는 조건과 새 예산을 먼저 검토한다. 전체8세션 자동 재수집이나 추가 진단을 실행하지 않는다.

## 근거·명령

[조회별 CSV](results/energy_screen_observe_02/queries.csv), [작은 결과](results/energy_screen_observe_02/SUMMARY.json), [PC 원문경계·hash 검증](results/energy_screen_observe_02/verification.json).
외부 로컬 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`:
- `energy_screen_observe_plan_v2/plan.json`, `RUN_AFTER_APPROVAL.ps1`
- `energy_screen_observe_pc_v2/verification.json` 및 실제기록 replay 결과
- `energy_screen_observe_run_v2/FINAL_RECEIPT.json`, `identity.json`, 각환경원문, `screen_observations`, `host_commands`
- `energy_screen_observe_registry/ENERGY-SCREEN-OBSERVE-02/finished.json`

실제 실행 명령(완료됐으므로 다시 실행하지 않음):
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_screen_observe_plan_v2/RUN_AFTER_APPROVAL.ps1 -Action Run -Approved -Serial adb-R59W802RW5F-yZ5QCN._adb-tls-connect._tcp
```

PC 결과 재확인(기기 명령 없음):
```powershell
python -B -c "import json;from pathlib import Path;r=json.loads(Path('C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_screen_observe_run_v2/FINAL_RECEIPT.json').read_text());print({k:v for k,v in r.items() if k!='query_clients'})"
```

plan_v2 SHA-256: `d7251b6205f0b86e3b6fa0047decd1a0c3a032d57136cf2e8b4b439f6b35fe26`。기존v1 원본/receipt/실행당시소스는 불변이다.
