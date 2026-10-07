# 이력 통제 야간 캠페인: 복구·보완 실행 PC 준비 — 2026-10-08

**실측 전 준비 완료·미승인·미소비.** 기존 [12세션 설계](ENERGY_AP_HISTORY_CONTROL_DESIGN_20261007.md)의 모형·입력·gate·앱은 그대로 두고 외부 parent가 수집 child, 복구 대기, 제한된 보완 실행을 소유한다. 이번에는 기기 명령·Run·claim0. [PC 검증·해시](results/history_control_plan_01/recovery_check.json).

## 실행 대상과 보존

- 새 캠페인: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v2/campaign_plan.json`
- SHA-256: `7daa7326c419a8bc9c851c9ac3d701c48ede8a08735876f6dea7607d8a313ace`
- 기본 child: 같은 폴더의 `primary_plan/collection_plan.json`, SHA `2e25aa64d908cde413fc0b5f8b989458551ff501806b5f62188f7d436b662620`.
- 새 실행 출력은 `energy_ap_history_recovery_run_v2`이며 현재 존재하지 않는다. 서로 다른 실행 ID·session UUID를 사용한다.
- 기존 `energy_ap_history_control_plan_v1`의 byte와 미소비 상태는 보존한다. host 코드가 갱신됐으므로 이전 hash binding의 실행을 강제로 허용하지 않는다. 새 wrapper만 실행 대상으로 한다.
- APK는 기존 서명본 `history_control_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`, SHA `3840bfb161b038ae61f34cd4215f8fe88bc511ec4e5f87cccc3b58e02c8768be`를 재사용한다. Android 변경·APK 재빌드·설치0. 기존 프로젝트 인증서/패키지/source 대응을 PC Check에서 재확인했다.

## 정상 경로

Check → 현재 기기·설치본·환경 gate → 개발6 → 후보 g 동결 → 별도 확인6 → 원본 회수·조건부 AP/J 분석 → PC 그림/보고서/Git 마무리. 개발 부적격·식별 실패·사전 등록 검증 실패면 확인0회로 종료한다. 관측이 기대와 다르다는 이유로 gate나 계수를 바꾸지 않는다. 확인 자료를 개발로 되돌려 반복 적합하지 않는다.

모형·실험 의미는 기존 계약 그대로다. AP는 등록 conditioning 이력으로 후보의 개선 가능성을 확인하고, 에너지는 기존 계수의 잔차·상쇄를 분해한다. 새 에너지 계수 독립 확인은 이 계획의 완료 주장이 아니다. 기본 시뮬레이터/RL/strict/experiment_ready=false 불변.

## 연결 소실 정책

- 원 수집 실행은 기존 계약대로 중단·회수·cleanup을 시도하고 `stopped_no_resume`를 남긴다. 새 parent는 동기식 subprocess를 소유하며 실제 child 종료와 client 반환 기록을 확인한다. 출력 대기 종료를 child 종료로 간주하지 않는다.
- stderr에 closed/device-not-found/offline 등 연결 실패 근거가 있는 경우에 한해 동일 transport의 `get-state`를 최대20회, 시작 간격60초로 조회한다. **캠페인 누적 대기 최대1,200초, 복구 대기 경로1회**다. 알 수 없는 실패를 무조건 연결 소실로 바꾸지 않는다.
- 각 조회 timeout3초, client/server/reap 예약을 포함한 deadline을 사용한다. 기존 server가 없으면 관측 client가 자동 시작하는 경로를 피한다. connect/pair/ADB daemon 재시작/설정 변경/transport 전환은 없다. 다른 endpoint로 복구된 경우 이 계획에서 자동 선택하지 않는다.
- 복구 시 모델·하드웨어 식별·fingerprint와 원래 session manifest SHA를 대조한다. 앱 cleanup terminal 파일이 없으면 active/unknown으로 기록하고 원본을 임의 회수하거나 force-stop하지 않는다.
- 종료 증거가 있으면 process 존재 여부를 따로 기록하고, 읽기 전용 회수1회만 한다. **최대120초·20명령**, 같은 원본은 별도 recovery 폴더에 보존한다. 앱 실행·추론·설치·force-stop·trace stop은0. trace는 원 host가 회수한 증거만 사용하며, 이 사후 경로에서 두 번째 trace 종료를 요청하지 않는다.
- 복구되어도 원 실행 receipt를 완료로 변경하거나 다음 세션을 자동 이어붙이지 않는다. 회수된 자료는 별도 판독 자료다. 원본 실패와 후속 회수 오류를 각각 남긴다.

## 앱 오류 수정 후 보완 실행: 정확한 허용 범위

**임의의 앱 오류를 자동으로 고치는 프로그램은 아니다.** 에이전트/운영자가 오류를 판독하고 재현 가능한 코드 결함을 수정한 뒤, 실행기는 증거·검증·예산 gate를 검사한다. 단순 lifecycle 취소·사용자 조작 가능성·원인 미확정이나 모형 오차는 보완 실측 사유가 아니다.

보완 실행 조건은 모두 충족해야 한다.

1. 기본 child는 종료돼 있고 `stopped_no_resume`이다. launch1회, 세션 시도≤1, **적격 개발 세션0**이며 durable `session_failure.json`이 있다.
2. 별도 review 파일에 원 receipt SHA, `cause_status=reproduced_code_defect`, 원인·최소 수정, 계측 의미 불변 판단, 관련 테스트 명령/통과 결과와 수정 소스 identity를 기록한다.
3. 기존 모형·분석·입력 JSON·protocol·trace 관련 보호 hash와 호출/시간 예산을 바꾸지 않는다. APK 변경이 필요한 경우 프로젝트 서명 빌드 receipt와 source/서명/패키지를 다시 확인한다.
4. 캠페인 처음 시작부터 경과한 시간에 수정·빌드·대기도 포함한다. 남은 시간이 **새 전체 블록19,557초+마무리600초 이상**일 때만 새 ID로 보완 계획을 생성한다.
5. 기존 실패는 그대로 두고 새로운 개발6→동결→확인6을 최대1회 수행한다. 기존 자료와 다른 APK 자료를 동일 block으로 합치지 않는다. 보완에서 다시 실패하면 재실측0.

이 제한 때문에 **두 번째 이후 세션의 앱 결함은 수정할 수 있어도 이번 캠페인에서 자동 재실측하지 않는다.** 적격 자료를 안전하게 이전하고 부분 실행을 동결 계수와 묶는 절차가 현재 검증돼 있지 않기 때문이다. 이를 해결됐다고 표시하지 않는다. 성공 세션을 무조건 전체 재수집하지도 않는다.

`prepare-repair`와 `repair-run` 경로는 구현·fixture 검증돼 있다. 실제 오류·수정 APK가 아직 없으므로 구체적인 보완 계획/해시를 지금 만들어내지 않는다. 첫 캠페인의 시간·소비 장부는 새 계획이나 CLI 호출로 초기화되지 않는다. child 직접 Run은 parent permit·process parent PID·nonce·plan SHA·남은 시간 확인에서 차단한다.

## 예산

|항목|정상 기본 실행|보완 포함 캠페인 상한|
|---|---:|---:|
|세션 시도|12|13 (실패 첫세션1 + 새블록12)|
|본 요청(conditioning 포함)|1,920|2,016|
|warmup|96|104|
|총 명시적 추론|2,016|2,120|
|runtime 생성|48|52|
|staging|12회·84파일|13회·91파일|
|설치본 pull/APK push/설치|각1|각2|
|trace host pull|12|13|
|ADB|91,400|99,240|
|기본 실행 예약|19,557초|같은 크기의 새 블록을 남은 시간 안에서만 허용|
|연결 대기|—|누적1,200초·20조회·1회|
|추가 읽기 전용 회수|—|120초·20명령·1회|
|전체|—|**21,600초(6시간), 마지막600초 마무리 예약**|

2,120=정상2,016+첫C0 세션 최대104(조건부하96+warmup8). 99,240=정상91,400+실패 첫 세션 여유7,800+대기/회수40. 이후 세션에서 실패한 경우 보완 자격이 없으므로 이 최대치를 초과하는 반복 구조가 없다. 미기록 호출은0으로 확정하지 않고 해당 첫 세션의 등록 상한을 보수적으로 잡는다.

19,557+1,200+120+600=21,477초여서 정상 예약과 대기/회수/마무리는6시간 안에 들어간다. 그러나 수정·재빌드·보완 블록까지 최악 시간을 전부 더하면 들어가지 않는다. **상한을 모두 소진하면서 완주를 보장하는 계획이 아니며**, 시간 부족이면 보완 진입을 거부한다. OS/native hang/기록 실패까지 실제 벽시계 종료가 보장된다는 뜻도 아니다. PC 재부팅/시계 불연속은 새 작업을 차단한다.

## 검증과 실행 명령

새 대기·소유권·repair gate10건 + 기존 통합/trace/cleanup26건 = **Python36건 통과**. fake clock으로20분/20회 상한, 복구 즉시 종료, clock reset 차단, 원 child active/미회수 client 차단, 동일 기기·terminal evidence/읽기 전용 회수, 직접 child 실행 차단, 늦은 실패/모형 실패의 repair 금지, 시간 부족 시 process 생성0을 검사했다. 실제 Android 경로는 이전 APK의 PC 검증 범위만 유지하며 신규 실기기 연결 내성 검증은0이다.

```powershell
# PC Check — 이번 작업에서 수행, 기기 명령0
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Check

# 향후 실측 승인 뒤 현재 승인 transport를 넣어 단1회. 이번 작업에서는 호출하지 않음.
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 A24 transport>' -ExpectedPlanSha256 '7daa7326c419a8bc9c851c9ac3d701c48ede8a08735876f6dea7607d8a313ace'

python -X utf8 -B -m unittest tools.test_d1_history_recovery_campaign tools.test_d1_history_control tools.test_d1_background_activity_plan tools.test_d1_energy_device_lifecycle_cleanup

# 실제 결함을 수정/검증했을 때만, 같은 캠페인의 남은 시간을 검사해 새 보완 계획 준비
python -X utf8 -B -m tools.d1_history_recovery_campaign prepare-repair --plan '<campaign_plan.json>' --build '<수정 APK build_receipt.json>' --review '<실제 원인·테스트·source_code를 기록한 review.json>'
# prepare-repair가 만든 repair_binding의 SHA/소스가 일치하고 예산이 남을 때만 실행
python -X utf8 -B -m tools.d1_history_recovery_campaign repair-run --plan '<campaign_plan.json>' --adb '<기존 adb.exe>' --serial '<동일 transport>' --expected-sha '7daa7326c419a8bc9c851c9ac3d701c48ede8a08735876f6dea7607d8a313ace' --approved
```

다음 행동은 **새 캠페인 상한으로 실측 승인 후 현재 기기 gate를 확인하는 것**이다. 추가 PC 준비 단계를 관성적으로 만들지 않는다. 다른 reserved-thermal/RL 변경과 사용자 파일은 별개로 보존한다.
