# 저잔량·완료 화면 proto의 새2조건 block

2026-10-09 · ENERGY-AP-TAIL-OBSERVATION-04 · 실행 중, 결과 그림 없음.

사용자가 명시적으로20%미만 실측을허용했다. 앱/host 양쪽을시작·진행≥6%,≤5%중단으로별도분리했다. 기존20%계약·실패계획은그대로다. APK703d09d5…b200e에PowerSave/배터리scale기록을추가했지만설정을자동변경하지않는다. 저SOC/절전상태의영향은새프로토콜전이 한계다.

앞선 plan_v4에서화면조회producer가2초내끝나지않아host가종료됐다. Awake/interactive 부분출력은있으나완료표지가없어성공으로처리하지않았다. 후속journal회수는성공했으므로무선단절을확정하지않는다. 원실행소유권을확인해보류된첫force-stop1/프로세스부재를확인했고finalthermal조회는예산상미확인으로남겼다. 앱정상cleanup으로승격하지않는다.

새host경로는 text/history dump 대신정식protobuf에서동일두서비스상태를확인한다. 원period10초·timeout2초·화면설정/환경기준·remoteproducer exit0·필드완전성 검사와실패중단을유지한다. 필요한환경관측을삭제하거나partial/cached값으로성공시키지않는다. producer/전송형식변경의계측비용은미확인이고J에서추정해빼지않는다. APK는동일703…을재사용해재빌드하지않았다.

[AOSP schema: wakefulness3/HAL-interactive15](https://android.googlesource.com/platform/frameworks/base/+/7567b9b595c7/core/proto/android/server/powermanagerservice.proto) · [PowerManagerService의같은변수write](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android15-release/services/core/java/com/android/server/power/PowerManagerService.java).
실제A24에서binary exec-out+exit0/두상태true를확인했고0.296초였다. 이것을연결안정성보장이나장시간완료로표현하지않는다. Windows shell text의binary변환과exec-out argv quoting오류는probe로보존하고코드경계에서수정했다. 개인정보없는실제필드fixture로parser/bytes/producer미완료·corrupt/oldmode·설정검사를검증했다.

- 계획: C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_plan_v5/collection_plan.json
- SHA: dfc034918d0cca805af3623406e74cd2616d8aedd7ac5b5ed2535c4901aa1028
- APK: 703d09d585a6b208e531ea36d19254071421e505acac5e350336894a71db200e
- C0→LOAD_A 각120/600/1920초, 본1200+적격8+warm16=명시1224, runtime8/staging2·14파일/pull·push·install각≤1, 동일설치생략.
- 고정5280초=88분＋별도준비240초/사이90초, 총9050초=2h30m50s/ADB16752. reserve와정상예상을구분한다.
- FROZEN/LOAD_SLOW/CLOCK_SHIFT 사전고정·실제일정조건부A·새fit0/재시도·대체·추가0/strict·기본·experiment_ready승격0.
- 이전모든시도는독립실패/소비로보존한다. 새자료와합쳐첫계획이완주했다고하지않는다.

[최종 분석 계약](analysis_contract.json) · [동결 계획·예산·hash](plan_summary.json).

```powershell
python -B -m unittest tools.test_d1_energy_screen_proto.ScreenProtoTests -v
# 실행전Check를수행했고,Run이후에는미소비검사에거부돼야한다.
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_plan_v5/RUN_AFTER_APPROVAL.ps1' -Action Check
```
