# 남은 독립 확인23회 실행 준비

**PC 준비 작업이며 새 실측을 시작하지 않는다.** 실제 측정은17/40회·2,352본요청 완료, 정식 예산58/81·23회 남음이다. 완료·실패 원장과 APK·179개 핵심 소스·전체40계획은 그대로 보존한다.

다음은 블록3 L64 PAIR_G, 세션 `2f15f739-0a34-58d3-b8e9-24a739bc6d8c`다. 첫 BASE가 동결한 **27.1℃**를 동일 파일·SHA로 인계한다. 다른 날·이동 뒤에도 현재 온도로 다시 고르지 않는다. 기존 MAIN의 ±0.5℃·60초 이력·최대공백10초·기울기0.1℃/분·최대600초는 유지한다. 조건이 맞지 않으면 거절을 보존하며 임계값을 완화하지 않는다.

[남은 순서](PENDING_SESSIONS.csv) · [공개 준비 상태](PREPARATION_STATUS.json) · [PC 검증](PC_VERIFICATION.json) · [기준 온도 원파일](CARRY_REFERENCE.json) · [파일 SHA](FILES_SHA256.json)

PC 결과: **23개 실제 manifest/authorization 조립 PASS, 관련 기능·회귀27검사 PASS.** 연결 폰 읽기 확인은16명령, 등록 신원·설치APK SHA 일치·남은 경로 충돌0·소유 프로세스0·SOC83%·밝기81/수동/Awake다. **현재 충전 중**이므로 실측 전 비충전 상태로 바꾼 뒤 다시 확인해야 한다. 설치·설정 변경·워밍업·추론·계측·START/claim·세션 소비는 모두0이다. [기기 읽기 영수증](DEVICE_READONLY_VERIFICATION.json) · [검증 버전과 수정 기록](VERIFICATION.md).

## 준비한 경로와 기능

- 별도 실행기: `tools/d1_a24_confirm_remaining.py`. 기존 C3 실행기·BoundedClient와 동결 실측 controller를 사용하며, 남은 prefix·이전 방문별 APP/원물/비소비 거절·원장·입력·온도 기준 인계를 추가 검증한다.
- 로컬 준비 job: `output/a24_confirm23_ready_20261015_v2/job.json`. `preparation_only=true`, 시간창 `execution_authorized=false`, 종료 시각은 빈값이다. 실제 실행을 시도해도 기기 명령 전에 차단한다.
- 초기 PC 검증 산출물과 보완 전 버전도 `output/a24_confirm23_ready_20261015/`에 보존했다. 실행 시에는 **v2**만 사용한다.
- 완료 17개 ID는 다음 scope에 포함하지 않는다. 동일 ID의 불명확한 APP 전송은 소비로 남기고 자동 재전송하지 않는다. 과거 C3/C4의 실행 전 거절과 C5의 최초 실제 APP를 별도 방문으로 확인한다.
- 이미 실행된 폴더·원장·방문 명령은 재사용하지 않는다. 새 사용자 시간창에 새 방문 이름을 부여한다. 이동 시 `STOP_AFTER_CURRENT.json`으로 다음 APP만 막고 현재 조건을 close/회수한다.
- 새 APP21분·MAIN5분 여유와 마지막5분 저장을 유지한다. PC의 가상 시간·가상 reference는 설정 검산용이며 실기기 검증이 아니다. 검산 후 실행 가능한 scratch 파일은 제거하고 해시·결과만 남긴다. 원 모델·입력은 삭제하지 않는다.

## 기기 읽기 전용 점검

사용자가 “폰도 연결해놨으니까 준비하면서 필요하면 참고”라고 허용해 별도 읽기 점검을 마련했다. 기기 신원·현재 설치 APK SHA·배터리·화면·소유 프로세스·남은 세션의 remote 입력/결과 폴더 충돌만 확인한다. 설치·push·APP·워밍업·추론·START/claim·계측·설정 변경은 하지 않는다.

점검 시각의 연결·화면·충전 여부는 다음 측정 시점에 달라질 수 있다. 따라서 실제 시작 전 동일 조건을 다시 확인하며, 이 점검을 MAIN 온도 적격이나 에너지 정확도 PASS로 표시하지 않는다. 시작을 위한 새 시간창도 별도로 필요하다.

## 명령

```powershell
$env:PYTHONPATH='tools'
python -B -m unittest test_d1_a24_confirm_remaining test_d1_a24_confirm_after_diagnostic test_d1_a24_confirm_one_more -v

# PC 조회만 한다. 아래 job은 측정 실행이 차단돼 있다.
python -B tools/d1_a24_confirm_remaining.py inspect output/a24_confirm23_ready_20261015_v2/job.json

# 필요할 때 새 폴더에 읽기 전용 점검 영수증을 기록한다.
python -B tools/d1_a24_confirm_remaining.py device-check output/a24_confirm23_ready_20261015_v2/job.json output/a24_confirm23_device_check_NEW
```

실제 측정을 시작하라는 지시와 사용 가능한 시간창을 받은 뒤에만 아래 절차를 사용한다. `<새_방문폴더>`에는 영문·숫자·밑줄·하이픈을 사용하고, 종료 시각은 날짜와 `+09:00` 시간대를 명시한다. 기기 종료와 작업 종료 사이에는 최소5분을 남긴다. 방문 등록 자체는 PC 작업이며 기기를 실행하지 않는다.

```powershell
python -B tools/d1_a24_confirm_remaining.py bind-window output/a24_confirm23_ready_20261015_v2/job.json output/<NEW_VISIT> --device-stop <YYYY-MM-DDTHH:MM:SS+09:00> --work-stop <YYYY-MM-DDTHH:MM:SS+09:00>

# 새 시간창 등록과 재검산 후, 실제 시작 지시가 있을 때만 실행한다.
python -u -B tools/d1_a24_confirm_remaining.py execute output/<NEW_VISIT>/job.json --execute-authorized
```

짧은 창에는 `bind-window --max-sessions N`으로 원래 순서의 앞 N개만 등록할 수 있다. 나머지 ID를 버리거나 총40 규모를 줄이는 뜻이 아니다. 종료 뒤 새 원물·APP intent·START·close를 대조해 전역 소비 원장을 갱신하고 다음 방문을 준비한다. 원래17회와 별도 전류 진단1회, 기존 실패·미완료는 합쳐 숨기지 않는다.

에너지J 미판정, AP는 HAL 읽기값·표면온도 미검증, `experiment_ready=false`, S26/NPU·데스크톱 학습·원 worktree 사용자 변경은 유지한다. [실측 전체 안내](../MEASUREMENT_RUNBOOK.md) · [원자료 블록 공유](../../../results/a24_measurement_share_20261015/README.md)
