# 분리 개발·혼합 확인 계획

## 2026-10-03 현재 프로토콜 분리 부하·혼합 확인 경로 PC 준비

**PC_READY_DEVICE_UNVERIFIED / HOST_STORAGE_BLOCKED / 미소비.** 기존 후보 미채택을 번복하지 않는다. 현재 남은 공백은 반복96요청에서 약하게 관측된 분류 전력 항과, 짧은 부하전 배경 추정의 전이 변동이다. 새 자료를 보기 전에 입력·추정·판독을 고정했다. 신규 정책·RL·기기 설정 변경은 없다.

개발3은 기존CPU_URGENT/B2_PARALLEL/B2_SERIAL 각각1세션이다. 각96요청을 분류32(35초부터100ms 간격), 탐지32(55초부터), 교대32(85초부터)로 분리한다. 확인6은 같은 정책의 정방향/역방향 각1회로, 분류/탐지 교대96개를35초부터350ms 간격에 제출한다. 모두48분류/48탐지이며 이전24/72혼합과 별도 입력이다. 예정 도착은 실제 완료와 독립이고 실제 추론·lane 점유를 PC시간에 맞추지 않는다. 기존 priority와1500/6000ms 마감은 유지하므로 미준수도 전체96분모로 보고한다.

옛 동결 처리시간으로 수행한 **계획용**6일정은 마지막lane68.879–99.962초다. 개발3의 점유설계 조건수10.156/rank5로 이전온라인13의119.523보다 분리된다. 이는 새실측·정확도PASS나 실제120초 완주 보장이 아니다. 입력을 여러개 시험해 오차가 작은 것을 고른 것이 아니며 새로운 혼합/대기는 실제서비스시간을 바꿀 수 있다. 기존 엔진은 기본 경로에서 이 입력을 계속 차단하고 명시적 계획/새연구 모드에서만 허용한다.

추정은 실제 개발 일정의5초창35–120초에서 부하전[-20,30]50초 평균전력을 뺀4상태 증가분 NNLS1회다. 기존20초 입력을50초로 늘려 표본을 확보하지만 미래배경이 일정하다는 보장은 없다. 전후유휴/중간유휴 잔차와 배경변화를 별도 보고하고 후속관측으로 과거예측을 보정하지 않는다. AP는557fbe의계수/초기입력 절차 그대로, 서비스5단계 평균만 개발3에서 추정한다. 개발3 적격·rank4가 아니면 확인을 차단한다. 모형/설정/코드 해시를 확인 전에 동결하고 확인으로 재적합하지 않는다. 개발/확인전류·AP는 실제일정조건부와 예정도착종단간 예측을 분리해 평가한다. 정확도 임의PASS·정책우월성·기본/strict승격0, experiment_ready=false 유지.

|승인된 자율작업 안에서 동결한 새 계획 상한|값|
|---|---:|
|개발/확인|3/6 (총9)|
|본 요청/warmup/총추론|864/72/936|
|추가 적격성 추론|0 (기존 warmup/품질 경로)|
|runtime/staging/입력파일|36/9/63|
|설치본 host pull|2 (개발·확인 각각최대1)|
|APK push/설치|각1, 동일본이면 생략|
|고정 관측|9×210=1890초|
|개발block/동결/확인block 상한|2880/180/5250초|
|전체예약 상한|8310초 (138분30초)|
|ADB|29200 (9800+19400)|
|재시도/대체/추가|0|

상한 산식은각block `600+n×700+(n−1)×90`, 명령 `200+n×3200`이다. 세션700초에는stage120/poll485/회수50/cleanup45가 포함된다. 기존timeout·환경기준 그대로이며 주기900ms power/기존hostpoll을 유지한다. 실제 소요시간 예상이나 완주 보장이 아니다. 개발후 확인 전체예약을 남기지 못하면 시작하지 않는다. rootRun은claim/기기명령 전에2GiB 가용공간을 요구한다. 이는2개설치본pull 약212MB, 원자료/host명령/회수/여유를 위한 운영예약이며 자료량을 정밀추정한 값이 아니다.

기존Android Activity/worker/sampler/cleanup 경로에 opt-in `separated-power-input-v1` 검증만 추가했다. 별도supervisor없음, onDestroy취소/구성변경처리 불변. host는기존 개발→동결→확인 실행기에 adapter를 연결하여 원래오류/receipt/소유권/중단 경로를 재사용한다. 새 manifest는900ms/정확한입력/96호출을 검사한다. 기존모드 경계와소비계획 재실행 차단을 유지한다.

프로젝트 서명 APK 검증 완료:
- 경로 `C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`
- SHA256 `5c284190db34b4ea4392ef5125a8618cf2dc85274f9214d2579676ca48a3ba4c`
- 기존인증서 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`, 동일package/version1.
- 권위있는영수증은 `separated_power_build_v1/verified_build_receipt.json`이다. 초기SDK환경 누락은본문검증 전설정실패였고, 테스트용home에서 나온다른서명은검증거부했다. 이후문서의 `ANDROID_USER_HOME=<repo>/.android-user`로바로잡았다. 기존키변경/기기전송0. 중간 build_receipt/project_build_receipt는후보로사용하지않는다.

계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_plan_v1/study_plan.json`, SHA256 `0340473b29e03b8c5bf38d05ffcb4f3e5ed7aa7eec222b403650c34f4a6eac7f`. 원본실행출력/registry없음. `separated_power_source_v1/identity.json`에소스보존.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check
# 저장공간 예약 확보 후 기존 자율실행 승인으로 사용. 이번에는 Run하지 않음.
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -ExpectedPlanSha256 '0340473b29e03b8c5bf38d05ffcb4f3e5ed7aa7eec222b403650c34f4a6eac7f'
```

PC검증: 관련Python15(입력3/새모형·계획·공유root·저장공간4/기존8), Android8(정책입력4+실제lifecycle4)본문통과; 실제PS Check 기기0; 빌드/인증서/package/소스검증. 신규root adapter는가짜기기진입으로동결선행/중복실행차단을검증했다. 실기기 안정성·새혼합부하·에너지정확도는미검증이다.

현재C: 약128MB로기기실행을보류한다. 이미완료된빌드의재생성가능3개중간폴더삭제를시도했으나자동승인검토가 `blocked by policy`로거절해삭제0이었다. 원자료/APK/키/사용자변경은보존했다. 사용자에게C:2GiB확보를요청했으며새세션승인을다시요구한것은아니다. 공간확보뒤동일계획 Check와현재기기gate를거쳐진행한다.

## 결과 재생 연결 보완 (2026-10-03)

기존 online-policy 재생은 24:72 입력 전용이므로 새 48:48 입력에 적용하지 않는다. 별도 `tools.d1_separated_power_readout`가 모형 버전·초기 전력창[-20,30]·입력 역할·번들 해시를 확인한 뒤 기존 예측 엔진을 명시적으로 호출한다. 실행기/동결 계획/APK는 변경하지 않았다. 실측 결과가 아직 없으므로 실제 결과 번들은 생성하지 않았다.

완료된 개발3/확인6 결과를 기존 `tools.d1_online_policy_readout export --root <완료된_run> --output <새_bundle>`로 내보낸 뒤 다음 명령을 사용한다. 부분 종료 자료에 완료용 export를 호출하지 않는다.

```powershell
python -B -m tools.d1_separated_power_readout --bundle <새_bundle> --case-id <등록된_ID> --policy B2_PARALLEL_ONLINE_V1 --output <새_예측_경로>
```

PC 검증: `python -B -m unittest tools.test_d1_separated_power_readout -v` 2건 통과. 합성 fixture에서 실제 forecast/costs를 실행했으며 기기 안정성·정확도 검증은 아니다. 미래 관측 입력 무시, 잘못된 버전/역할/해시/누락 바인딩 차단을 확인했다. 검증 기준 HEAD abf63cc + 이번 신규 재생/테스트 파일. 실제 PowerShell Check 재실행은 같은 계획 SHA0340473b…ac7f, 기기 명령0으로 통과했다.

C: 여유 약121MiB로 필수2GiB 예약 미충족: Run/claim/기기 명령0, 계획은 미소비 보류이며 stopped로 바꾸지 않았다. 사용자 공간 확보 응답 대기.
