# ADB host 분석 및 확인 전용 후속 계획

2026-09-25, 시작 `fefe913`/작업 브랜치 clean. **PC 조사·최소 host 보완·검증·실행 준비 완료, 실기기 실행 미승인·미실행**. 새 작업 ID `ARRIVAL-CONFIRM-FOLLOWUP-01`. 기존 [RECOVERY-02/COLLECT-03 종료 결과](ARRIVAL_INSTALL_RECOVERY_20260924.md)를 재개하지 않는다.

## 확인한 사실과 원인 한계

| 항목 | 관측·코드 근거 | 해석 한계 |
|---|---|---|
| 실행 ADB | 이전 host 명령의 절대 경로 `C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe` | 실패 당시 실행파일 hash/환경 전체는 미기록 |
| 현재 버전/PATH | SDK source.properties37.0.1, 보존 adb.log의 버전37.0.1-15733141/프로토콜1.0.41. 현재 PATH의 adb.exe는1경로 | 과거 다른 도구가 다른 ADB를 사용하지 않았다는 증거는 아님. adb version 명령도 이번에는 실행하지 않음 |
| server 주소 | 실패 stderr가127.0.0.1:5037 접속 실패/10060, 명령에-H/-P없음 | 당시 ADB관련 환경값 미기록. 현재 server override환경은없지만 과거 값으로 전용하지 않음 |
| 현재 프로세스 | SDK adb.exe PID2388, parent16440, 생성일9/23, `adb -L tcp:5037 fork-server server`; 5037 listener 소유PID2388 | 현재 관측이지 실패 순간의 응답·프로세스 상태 아님 |
| 공유 server 종료 | 해당 수집 경로는 `legacy.Device.call`의subprocess.run. 비정상exit에서decode/500문자stderr를예외로저장. timeout은직접client kill/wait 경로 | 당시client PID·원시stderr·정밀명령시각 미기록. daemon 내부 원인 미확정 |
| cleanup | 앱 package에am force-stop→ps→thermal 조회. 이 경로에kill-server/start-server/taskkill없음 | 외부도구/OS의서버종료·일시적응답정지 여부는 미확인 |
| 다른 복구 경로 | RecordedProcess의timeout 시taskkill/PID/T/F는자식트리를대상으로함 | 자동생성daemon이자손이면종료될잠재위험. 그러나이번실패는legacy수집경로이고앞선복구22명령에timeout없어원인으로확정불가 |
| 병렬·충돌 | 수집runner는순차호출. 현재관련조회에서Studio프로세스는없음 | 실패당시다른PC도구활동은미기록. IDE/다른ADB충돌은가능성만있음 |

보존된 `%TEMP%/adb.log`는9/25 01:51:31에끝나고 실패02:35를포함하지않는다. 01:25/01:33의TLS/transport실패는앞선별도시점이며이번5037오류와동일원인으로연결하지않는다. host현재프로세스/포트는OS읽기전용조회로확인했고ADB호출·server시작/종료/재연결·기기명령은0이다. SDK파일SHA `b4a6b455702684652cccf7b46258b29e653538904359a58fd4931cf3ef286b3f`를새계획에고정했다.

시간 순서(KST, 모두host UTC기록에서같은방식으로변환): 이전확인3번째cleanup02:32:53.869 → 120초냉각 → 실패시도02:34:53.873 → 화면gate02:34:54.472 → staging오류02:35:24.591 → 증거수집02:35:24.766 → hostcleanup02:35:25.448. 약30.7초는시도시작부터오류까지이며labels push단독시간이아니다. 입력순서의일부성공후labels전송에서오류가났지만명령별원시증거가없어세부전송시간을복원하지않는다.

**직접 원인 범위는 PC ADB server 접속 실패**다. 휴대폰 무선 단절, 개발자 옵션, GPU, native crash를 원인으로 확정하지 않는다. 일시적인 server 응답 정지·client 시작/연결 race·외부 도구 충돌 등은 후보이며 현재 자료로 구분하지 못한다.

## 최소 host 보완

- [d1_adb_observed_client.py](../tools/d1_adb_observed_client.py): 새 후속 경로만 사용. 각client호출전기존127.0.0.1:5037 smart socket의host:version을최대1초내읽는다. ADB를spawn하지않는준비조회이며응답없음/프로토콜불일치/환경override시client를시작하지않는다. 준비실패를retry·server재시작으로숨기지않는다.
- 명시한serial·실행파일·주소·관련환경·명령intent, UTC/monotonic, 실제client PID/exit/timeout, stdout/stderr원시bytes, 종료대상을보존한다. intent와실제Popen성공을구분한다. 첫호출과오류시OS프로세스/포트snapshot을최대2초남은예산내기록하며조회불가도보존한다. 키/비밀번호/ADB_VENDOR_KEYS내용은저장하지않는다.
- [d1_recorded_process.py](../tools/d1_recorded_process.py)의새root_only옵션은이번host client만kill/reap하고공유daemon/자손을종료하지않는다. 기존경로의기본옵션과과거실행의의미는보존한다. Future/native중단을보장하는기능이아니다.
- server확인과실제ADBclient실행사이의race는남는다. client내부의자동server동작을완전히통제한다고주장하지않으며stderr의daemon시작/kill징후도실패로기록한다. 명시적kill-server/start-server/reconnect, 연결방식전환, 자동retry는없다. server부재시실행자가별도로준비해야한다.
- 기존 [수집runner](../tools/d1_arrival_collection_device.py)를재사용한다. plan claim은초기device preflight이전, session intent는server/단일기기/앱정지조회이후이며Activity launch marker는입력staging완료뒤다. 어떤단계실패든새계획도전체종료한다. stage별소비와오류를보존한다.
- Android/모델/입력·worker/GPU소유권/정책·동기journal상태는변경없음. APK재빌드없음. 새host TCP/파일/OS관측부담은전체시간에포함되며기존host와동일계측조건이라고하지않는다. 앱의성능구간에서이를임의차감하지않는다.

## 기존 확인과 누락 조건

개발6개와동결SHA `e4cb73aa1045f4b6ff5a17aa500862799c6f55bb07de5ab36e2fba580b683023`은그대로재사용한다. 원래계획은10시도/9완료/실행전실패1/미시도2, 진단36/48·warmup72/96·추론108/144로종료상태를유지한다.

| 조건 | 이전 확인 | 이번 후속 | 역할 |
|---|---|---|---|
| 고정분리·큐직렬 E | 적격1세션/4요청 | 반복안함 | 동결대비기술통계, 날짜가다른병행자료와인과paired비교불가 |
| CPU큐 D | 적격1세션/4요청 | 반복안함 | 큐준비/callback·lane구간의관측 |
| 고정분리·단독 C | 적격1세션/4요청 | 반복안함 | task/backend별단독관측 |
| 고정CPU·단독 B | staging실패,Activity0 | 새1세션 | shadow/고정CPU기록·cost확인 |
| active CPU·단독 A | 미시도 | 새1세션 | 실제strict CPU fallback판단/dispatch확인 |
| 고정분리·병행 F | 미시도 | 새1세션 | 탐지normalGPU+분류urgentCPU의한정overlap확인 |

순서B→A→F, 원seed2026092402·도착trace·이미지·CPUthread1·resident4·warmup순서(C_CPU2/C_GPU2/D_CPU2/D_GPU2)유지. 각세션진단4개(탐지normal2/분류urgent2)와warmup8회. 새UUID만부여한다. 긴급output_ready/일반persist_complete, 실제lane_available를구분한다. 미래도착/미래완료값을정책에주지않는다.

후속병행gate는**원개발6개·기존확인3개의불변hash/검증/cleanup + 당일B/A두직렬세션적격·cleanup + 현재memory/thermal/thread조건**이다. 원래의동일phase앞5세션gate와다른새계획의명시적조건이다. 완료된5조건을다시측정하지않으며두직렬세션에서도4runtime/8warmup을수행해당일backend초기상태를확인한다. F에서2쌍의hostAPI overlap이없으면실패/coverage미충족이며추가요청을만들지않는다. 당일GPU직렬대조가없어새F와과거E의차이를인과간섭효과로사용할수없다.

## 예산·소비·중단

**승인 전 실행 금지 제안: 3세션·진단12·warmup24·runtime생성12·명시적추론36·설치0·retry/대체/추가0. 예상9~15분, 합상한1800초(30분).** 작은표본의기술적수집가능성/경계/추정차이확인이목적이며반복안정성·tail·검정력을보장하지않는다.

- 작업1755초에설치본회수/서명검사·server/device/environment gate·입력준비·냉각·앱호출·관측·회수10초예약을포함하고최종cleanup45초를확보한다. 초기120초+사이2×120초=냉각360초(6분). PC최종분석은마지막기기cleanup뒤별도이며추가기기호출없다.
- session당staging전체최대150초를새로명시하고기존개별push90초를유지한다. APKpull180초/일반명령30초/launch30초/Future30초/watchdog120초/poll125초를늘리지않는다. 모든명령은남은절대deadline과client정리최대5초에제한된다. 다음launch/poll/회수165초확보불가시시작하지않는다.
- 정확한설치APK/서명/package/version이기존후보와일치해야하며설치0이다. 다른APK거나확인불가면전체중단한다. 배터리시작55/이후30%·비충전·35°C이하·thermal0·밝기81수동/기존5시간timeout·Awake/interactive·앱memory admission을유지한다. 시스템설정/화면조작/연결방식전환없음.
- 최초plan claim은preflight실패도소비한다. server/device준비조회실패는session intent이전이면0세션이지만plan은종료한다. intent이후staging실패는실패세션으로보존하고Activity/호출0또는확인된범위를별도표시한다. 미확인호출은0으로채우지않는다.
- 오류시부분산출물·host증거회수최대10초, 이후남은상한내cleanup45초. server가없으면client를시작하지않으므로기기cleanup이미확인일수있으며그대로기록한다. 안전cleanup을위해daemon을자동재시작하지않는다. nativecrash/강제종료에서앱finally실행을가정하지않는다.

## 동결·판독·결합 범위

원개발자료와동결은읽기전용hash로묶고후속을보기전에유지한다. 기존/새확인자료는동결값대비조건별median/min/max/n·오차로만기술한다. 계획/날짜/host버전/순서를붙여구분하고원래실패·미시도분모를삭제하지않는다. 새3개성공을기존계획의6/6완주로쓰기금지. 선택적후속확인이며새로운완전독립정책평가가아니다. 조건별독립세션1, task별2상관요청, CI/p값/정밀tail/사후허용폭없음.

기술적성공은새3세션모두기존validator의기록·시간·배정·원시backend/hostGPU근거·완료·memory/thermal·cleanupgate를통과하고원동결hash가그대로인경우다. 새수치정확도PASS기준을만들지않는다. 실패시확보된부분과미확인범위를보고하며추가수집0.

성공하면active CPU fallback과한정병행조건의추가관측/PC재현근거를확보한다. 조건/host버전표시를갖춘관측기술통계설정이나원자료재생입력은검토가능하지만, 적응형GPU선택의검증·임의도착병행허용·인과간섭계수·정책우월성을자동허용하지않는다. PC병행차단해제는한정조건모델의적용구간/오차·독립확인요건을검토한뒤별도개발판정이필요하다. **experiment_ready=false, 기존40값/20null/FAIL/부분결과보존.** B2사전선정/B3-P차별성/최종평가설계는남는다.

## 준비 파일과 명령

외부root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`:

- 최종 `confirmation_followup_plan_v3/collection_plan.json` SHA `3de26b4ebbd5dcc1f0b497c5e5c47a5052a65db604b02295b1425589df0e4bb3`, manifests3, RUN_AFTER_APPROVAL.ps1. v1/v2는PC보완중의미실행초안이며실행대상이아니다.
- 예정출력 `confirmation_followup_run_v1`, registry `collection_execution_registry/ARRIVAL-CONFIRM-FOLLOWUP-01`: 미생성. 개발용phase/새fit없음.
- `confirmation_followup_pc_v1`: 원인분석/보존adb.log/현재OS조회/환경/테스트/최종source snapshot/검증기록. 로컬원자료는GitHub에포함하지않는다.

```powershell
# PC 전용: ADB/서버접속/기기명령/소비 없음
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/confirmation_followup_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check
# 별도 새 예산 승인 후에만. 현재는 실행하지 않는다.
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/confirmation_followup_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<당일 확인한 동일 A24 serial>'
```

실행결과는공유runner의attempt/launch/host_commands/context+client receipts·artifacts/validated/cleanup/stopped와새followup_analysis.json에남는다. [도구](../tools/d1_collection_followup.py)와[PC테스트](../tools/test_d1_collection_followup.py)는실제구현이다. 검증은신규13건+직접영향기존7건=20건, source별기록을외부에보존한다. mock/PC통과는실제ADBdaemon복구·GPU/native성공검증이아니다. 이번작업의ADB/기기명령·설치·추론·server시작/종료/재연결·본simulation은모두0이다.
