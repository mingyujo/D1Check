# 배경 활동 Run03 — 2세션 적격, PAR 준비 조회 timeout 후 종료

> 2026-10-03 PC 정정: 이 문서의 과거 J 결과는 10~30초 초기화로 보존한다. 동결 모형의 −20~30초 계약 복원과 선택된 적격 네 세션의 정정값은 [후속 판독](../background_identification_pc_v1/README.md)을 따른다. 과거 수치 재현에는 `--legacy-preload-window`를 추가한다. AP·원자료·실행 판정은 변경하지 않았다.

v4는 stopped_no_resume다. C0_PRE·CPU96 2/4 자료만 적격이며 PAR 준비 중 run-as ls가 3.003초 timeout에 걸렸다. 마지막 C0는 미시도다. 실제 전송 단절·GPU 결함·앱 자체 실패는 확인되지 않았다. 직전 listing 0.12–0.20초 성공, timeout client root reaped, 직후 동일 transport 회수/대상 앱 force-stop·ps 부재 확인이 성공했다. 다른 연결을 해제하거나 reconnect하지 않았다.

[작은 수치](metrics.csv) · [원래 receipt 소비 요약](consumption.json) · [부분 분석](summary.json) · [경로](paths.png)

|조건|관측120초 J|조건부 예측 J|예측−관측 J|AP MAE °C|AP 최대오차 °C|
|---|---:|---:|---:|---:|---:|
|C0_PRE|132.338|142.793|+10.455|0.152|0.274|
|CPU96|165.025|171.192|+6.168|0.203|0.843|

AP 점수창은 common35초→회수 cooling 종료이며 에너지120초와 다르다. summary의 정확한 창을 따른다. 시작 AP와 프로토콜은 기존 strict 개발 범위 밖; 사후 기술 분석/조건부 실제 일정 계산이며 독립 확인·정책 우월성/정확도 PASS는 아니다. 예측에 사용한 것은 세션 부하 전 전력/AP와 동결 계수/실제 일정이며 미래 전력/AP를 넣지 않았다. 계수 적합·후보 채택0, experiment_ready=false 불변.

## trace 수정의 실제 결과

RING_BUFFER와 producer flush5초로 두 설정 플래그가 없어졌다. C0·CPU는 공식 TP 5SQL/BOOTTIME/8CPU/5초24bin 전체 coverage 통과, unknown CPU 시간0. benchmark/tracer/other CPU초는 각각 C0 7.845/6.189/42.132, CPU96 47.569/5.981/46.244다. CPU초를 앱별 J 또는 원인으로 해석하지 않는다. 주파수 관측 있음; GPU/무선 귀속 없음. 파일 flush/buffer 변경 비용도 whole-device J에 포함되며 임의 보정하지 않는다.

PC 검사기는 모든 행×모든 bin 반복을 교차 bin만 누적하는 방식으로 최적화했다. 기존 적격 두 trace와 모든 bin 수치가 완전히 동일하며 집계2.4/5.3초로 재현했다. 40초 deadline 체크도 집계 중 수행한다. 필수 관측·3초 timeout·조회 주기 변경0. 실패 세션의 완전한 common_boundary 부재는 전체 trace 계산 불가로 명시하며 앞선 ADB 오류를 덮지 않는다.

## 소비와 종료

v4 본96+warmup24=확인 추론120/runtime12/staging3·21/설치본pull1/tracepull3/APKpush·설치0/ADB1803(선택1 포함)/누적 기기작업817.657초. 실패 PAR 부분 progress112행에 본 시작0이며 완전한 원본 부재로 추가 호출을 성공/0으로 확정하지 않는다(미확인 상한96 별도 보존). 최초4세션 계획의 완료 분모를 줄이지 않는다. 앱 정상 cleanup2/host cleanup3/최종 대상 ps 부재. 실패 PAR 앱 정상 cleanup은 미확인, host force-stop과 구분한다. trace 자기 key 종료/회수3, 원격 삭제0. parent 종료 receipt 보존, 상세 host_identity=null 한계도 유지한다.

원본: `C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_run_v4/FINAL_RECEIPT.json`. 별도 `background_activity_run_v4_pc_analysis/raw_inventory.json`, partial_readout_v2. 원본과 소비 registry 수정0. 최초 PC 판독 시 frozen plan의 상대 manifest 경로를 잘못 지정한 실패는 별도 빈 partial_readout로 보존; 원래 plan_v4 경로로 정상 재현했다.

재현:
```powershell
python -B -m unittest tools.test_d1_background_activity_plan tools.test_d1_background_activity_result
python -B -m tools.d1_background_activity_result --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v4/collection_plan.json --exports C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_run_v4 --output '<새 PC 분석 폴더>' --allow-partial
```

## 남은 실행 — 이동 때문에 claim 전 보류, 실패가 아님

사용자는 추가 수정·새 실측을 승인했으나 “5분 뒤 이동”을 알려 새 v5는 Run/기기 조회/claim0으로 보류했다. 기존 v4를 재개하지 않는다. 완료 C0·CPU를 반복하지 않는 **별도 개발 subset PAR96→C0_POST**이며 실패 PAR의 준비/열 이력과 시간 간격을 보존한다. 원래 v4 완주나 같은 독립 확인 block으로 합치지 않는다.

- 새 ID BACKGROUND-ACTIVITY-DEVELOPMENT-05; 계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v5/collection_plan.json`.
- SHA292609c7e9e2d0c4eb54bc2579e223fddaf402f7dc453f0dd2c53a343b84f04a. 미소비, 출력/registry 없음. 기존 종료 receipt·두 validated 파일 hash를 계획에 결합.
- 개발2/확인0/본96+warmup16=112/runtime8/staging2·14/설치본pull1/tracepull2/APK0/설치0/retry·대체·추가0/ADB6618(선택1 포함). 고정420초, 간격90초. 총2402초=선택15+preflight425+2×936+90. runner 시간·명령 cap에서 선택 예약15초/1명령을 미리 제외한다. 예약은 정상 예상시간이나 완주 보장이 아니다.
- APK9d8d55c2…73fd932, 동결 model5682082a…72db2/원래freeze19637bf1…b825 불변. 현재 기기/설치본/비충전/BAT·thermal·화면·메모리 gate는 재개 시 실행기가 새로 확인한다. 자동 reconnect/추가 warmup/가열/설정 변경 없음.
- PC15검사와 실제 PowerShell Check 통과. 필수 gate·3초 timeout 유지. 이번 순서 변경/시간·실패 준비 이력은 모형 개발·사후 판독에 표시해야 한다. 새 계획 성공만으로 gamma 채택/독립 확인을 진행하지 않는다.

연결과 충분한 시간이 확보된 다음 아래 Check 후 현재 확인한 transport로 기존 승인 범위에서 한 번 실행한다. 지금은 실행하지 않았다.
```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v5/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v5/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 확인한 A24 transport>' -ExpectedPlanSha256 '292609c7e9e2d0c4eb54bc2579e223fddaf402f7dc453f0dd2c53a343b84f04a'
```


## 이후 재개 결과

위 v5 미소비 보류는 이동 당시 기록이다. 이후 재개에서 v5는 staging client의 host daemon 연결 오류로 종료됐고 별도 v6가 남은 개발2를 완료했다. [최신 결과·소비·별도 block](../background_activity_run04/README.md). 기존 v4 실패와 분모를 보존한다.
