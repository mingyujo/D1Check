# 이력 통제 실측·원동결 모형 전이 확인 최종 결과 — 2026-10-08

**적격 개발6·원모형 별도 확인6, 총12자료 확보·PC 분석 완료. 원모형 유지, 새 잔열 g 후보는 미채택.** 오류를 수정하면서 완료된 자료를 재사용했고 원v2~v6의stopped_no_resume/FAIL/미확인 기록을보존했다. 최초v2/v5 계획이완주했다고바꾸지않는다. 최종v7은completed_descriptive_only이다. [대시보드](results/history_control_plan_01/run_v7/index.html) · [오차·소비 요약](results/history_control_plan_01/run_v7/summary.json) · [재현](results/history_control_plan_01/run_v7/README.md).

## 완료 범위와 연구 판정

새 잔열항g는개발6에서1회추정했고 g=0.16229091917947994이다. 회복30/180초block 교차확인에서기존원모형보다평균AP오차가커 v5 개발gate가실패했다. 개발전체에서원APMAE0.169°C/후보0.265°C, 교차held-history 평균원0.169°C/후보0.267°C다. 후보를고치거나기준을낮추지않았다.

사용자 최신 “알아서수정하며계획마무리”승인아래 남은예정확인6을 **원동결모형의 별도프로토콜전이 확인**으로등록했다. 원모형은새개발6으로계수적합하지않았고β/k/g0/모형SHA5682082a는그대로다. 기존원모형을유지할선택은개발결과를본뒤이뤄졌으며확인자료는선택/적합에사용하지않았다. 실패한g는고정된보조비교로만봉인했다. 선택ORIGINAL_FROZEN·fit0를확인전UTC20:05:09(v6)봉인했고, 복구후v7에서도같은값을재봉인했다. 최종freeze SHA `8bae0c6991ecc679e97056aa3baba5e291abf3885d79a0ee0a0eb958f0f69507`.

확인6의원모형AP MAE평균**0.260°C**, 최대절대오차**1.077°C**, 최고온도오차절대최대**0.507°C**, 시작대비변화량MAE평균0.321°C. 보조g의AP MAE**0.295°C**/최대절대**1.383°C**/최고온도오차절대최대0.806°C/변화량MAE0.306°C다. 변화량의일부개선과절대경로악화를분리하며후보를채택하지않는다. 원모형은30초C0에서냉각방향오류1/6, 보조g는0/6이었다. 이방향차이만으로후보정확도PASS를주지않는다.

기존계수의공통target120초에너지는확인6 **절대오차평균3.913J**, signed평균+0.685J, 최대절대9.682J. 후보는AP만변경하므로J예측은같다. 개발J MAE5.104J/signed평균−3.447J였으며조건/자료역할이다르므로“개발보다J오차를줄였다”는독립개선주장으로쓰지않는다. 기존다른부하의4.624J등과도직접우열비교하지않는다.

|확인 조건|관측 J|예측 J|예측−관측 J|상대오차|원 AP MAE|원 AP 최대오차|보조 AP MAE|
|---|---:|---:|---:|---:|---:|---:|---:|
|180_C0|115.758|118.522|2.764|+2.388%|0.339|0.458|0.249|
|180_CPU|139.385|143.580|4.195|+3.010%|0.234|1.077|0.238|
|180_PAR|150.872|141.190|-9.682|-6.417%|0.181|0.849|0.212|
|30_PAR|146.538|148.898|2.360|+1.610%|0.202|0.838|0.238|
|30_CPU|149.361|149.415|0.054|+0.036%|0.247|0.770|0.594|
|30_C0|121.906|126.326|4.421|+3.626%|0.359|0.516|0.242|

## 정보 경계·오차 상쇄

모든결과는 **A. 실제실행일정이주어진 조건부 비용예측**이다. B. 예정도착부터일정/응답/비용을만드는종단간예측은이번확인이아니다. 원모형은target부하전AP(−30~+35초미만)와유휴전력(−20~+30초)을초기입력으로쓴다. target작업은35초이후시작하며그후AP/전류를예측입력으로사용하지않는다. J그림0~120초중초기유휴구간은초기전력관측과겹쳐순수session-start-open-loop예측이라고하지않는다. AP오차는초기입력구간을제외한각실제query시점약35~180초(target+cooling)이며각정확시점/표본수는metrics.csv에있다. 최고온도오차도이판독창내관측최고값기준이다.

보조memory모형은conditioning전AP와전체등록이력으로전파해원모형의fresh target초기입력보다긴forecast를한다. 초기화/정보량차이를숨기지않고, 성능차이를“잔열기제가없다”로단정하지않는다. deltaAP그림은첫scored표본대비변화량을보는원인분해이며예측을사후평행이동해채택한모형이아니다.

30초CPU확인의총J차이+0.053569J(0.035865%)에는 pre+0.367020/load−1.479371/post+1.165919J의**98.2% 산술적상쇄**가있다. 전체오차가작다고경로가정확하다고하지않는다. 180초PAR은총−9.681819J이며부하−4.298346J/이후−4.580520J가같은방향이라상쇄가없다. 구간은센서가판독할수있는부하span/완료후유휴이며개별요청·혼합표본의순간전력을정밀식별하지않는다. [구간잔차](results/history_control_plan_01/run_v7/energy_parts.csv).

실제CG_DC target병행점유는개발12.931/13.068초·확인13.068/12.802초다. CPU조건은동일CPU lane직렬, C0는target요청0/유휴120초다. backend/task를임의의CPU+GPU로합치지않는다. 현재자료는짧은병행전력계수를독립적으로정밀식별한것이아니며원whole-device계수의aggregate예측을평가한다. 초기AP before-conditioning 범위는28.4–29.3°C였고현재gate/개발범위/모형strict지원은구분한다. AP센서정확도·current raw=mA(1000uA/raw)해석·절대J정확도는여전히미인증이다.

## 오류 수정과 실행 경계

1. v2는승인후listing3초무출력timeout. 내부원인미확정·동일transport후속회수성공. v3는진행listing최소2초/한정1gap으로분리했고필수환경을삭제하지않았다.
2. v3첫C0 앱정상완료였으나PC가cooling끝0.393초전류까지요구해power gap. 실제conditioning→target+120초는완전했다. 공식필수창과cooling full J=null을분리해원자료를재판독/재사용했다. 창이동·외삽·0채움0.
3. v4화면2초무출력timeout은실제화면꺼짐과구분. v5새환경unknown lease1/session은최근관측이있을때만10초안fresh thermal/화면복구필수, 앱환경증거/후속coverage도검사했다. v5~v7에서는해당lease실사용0이라실기기오류회복능력을검증했다고하지않는다.
4. v5데이터6적격이나g개발gate실패. 이실패를보존하고원모형확인목적의새v6로진행했다. 모형오류를프로그램오류로포장하거나g를다시맞추지않았다.
5. v6다음준비에서PClocalhost5037 server_probe1초timeout/client미실행. 서버동일PID/후속동일protocol정상. v7은PCprobe에한해최대2gap/각1회재확인, deviceclient는한번만실행. daemon재시작/자동reconnect/기기command재시도0. 실제v7 재확인사용0.
6. 최종소비대조에서 **v7 세부추론 예산808 대 실제manifest/소비904(+96)**를발견했다. 첫재사용확인을PAR로가정한계획산술이잘못됐고실제첫확인은C0였다. Check가남은roster와예산동일성을검사하지못한PC결함이다. 원계획byte와초과기록은보존하고새generator에roster합/세션/runtime/staging검사를추가했다. 실제잘못된계획은새검사에서실행전거부되고corrected904fixture는통과한다. **전체2328상한을넘지않았지만세부상한과달랐으므로완전한예산준수라고보고하지않는다.** 중간진행설명의일부조건명도실제manifest와달랐으며최종CSV/표는원문순서로정정했다.

각완료자료는read-only로복사/hash/manifest를재검사했고raw원본·원FAIL·소비registry를초기화하지않았다. 앱정상cleanup/host force-stop/프로세스부재는각각원문에있다. 종결계획을재개한것이아니라새ID들과불변자료를연결했다. 개발/확인모형파일·기존COLLECT-05/DC_DG·기본/RL/strict/experiment_ready=false불변.

## 명목조건 비교의 차이 예측 진단

동일role/회복시간의CPU와PAR을대조하되, 순차측정·초기조건차이가있어무작위짝정책효과로해석하지않는다. 확인180초의PAR−CPU는관측+11.487J/조건부예측−2.390J로부호가달랐고차이예측오차−13.877J였다. 확인30초는관측−2.823J/예측−0.517J, 차이오차+2.306J였다. 실제조건이같다는정책우열이아니라동일각조건의예측잔차가정책차이판독에미치는진단이다. 작은J이득을단순순위로단정할수없다는근거로쓴다. [차이진단CSV](results/history_control_plan_01/run_v7/contrast_diagnostic.csv).

## 소비·종료

실제독립physical15회시도중정상완료12・불완전3이다. 같은sessionID의복사7회/6회등은추가실측으로세지않았다. 완료cohort: conditioning1152＋target768＋warmup96=2016추론, 모든1920work의start/return/output_ready/persist/worker_release/lane_available각1920.

|항목|등록누적상한|실제/미확인|
|---|---:|---|
|physical 세션|15|15시도/정상12/불완전3|
|추론|2328|durable2236시작/2235반환, 실패PAR prefix밖92이하추가가능성보수적예약|
|runtime|60|60시작/반환기록|
|warmup|120|120시작/반환기록|
|staging|15회·105파일|15회·105파일|
|ADB|99240|12827intent/12826client실행기록(1local사전실패)|
|설치본hostpull|2|2|
|APKpush/설치|각2|각1, 새APK재빌드0|
|tracepull|15|15 (완료12+부분3)|
|연결소실대기/추가회수|20분/120초 각1|실사용0|
|원v3 시작부터총6시간|21600초|11784.782초=3시간16분24.8초, 수정・대기포함|

최초v2의251.720초와그이후v3시작전PC준비는별도기록이며위clock의재개라고표현하지않는다. 각후속plan은v3원clock을승계해수정시간/대기를초기화하지않았다. v7 새실제904추론・5세션/runtime20・staging35파일/ADB4643, 과거1112추론/7완료자료를재사용해cohort2016/12를구성한다. [실제누적ledger](results/history_control_plan_01/run_v7/physical_runs.csv) · [고유세션ledger](results/history_control_plan_01/run_v7/physical_sessions.csv).

마지막앱cleanup completed(에러/sampler오류null), 원host force-stop/ps부재확인/trace회수완료. parent/child프로세스부재를PC에서확인했다. 마지막원관측AP29.0/BAT29.3/SKIN30.1°C/thermal0이며그후기기조회/설정변경0. 동일IP endpoint고정, 다른mDNS연결을해제하지않았다. 실제무선단절은이번기록에서확인되지않았고복수transport를원인으로단정하지않는다.

## 지원·완료와 다음 행동

완료: 정식입력/동일resident/등록이력/실제lane조건부원모형의전이오차와구간잔차, 냉각방향1/6남음, 새잔열후보미채택, 필요자료12확보・모형/원자료보존・PC오류보완. 실패g를기본에자동채택하거나확인후재보정하지않았다. 현재가능한것은이번A24모델/입력/CPU또는CG_DC/초기조건/관측protocol 범위의재생과조건부cost평가다.

미완료: 임의도착전체/online정책/열→처리시간feedback/작은J·작은AP정책차이분별/절대에너지교정・배터리SOC/사용시간/BAT 모형이다. 모델이수치를낼수있음・자료지원・독립전이오차산출・정책차이분별은다르다. 정책우열/accuracyPASS/strict지원확대・experiment_ready=true는선언하지않는다.

**다음PC행동하나:** 이번12조건잔차를기존정책비교의J/AP 차이와함께표시해, 큰효과만구분가능한범위를산출한다. 같은실측반복・새후보탐색・추가기기계획은자동시작하지않는다.

원본root는 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_run_v2`~`run_v7`이며최종원 receipt `run_v7/primary/FINAL_RECEIPT.json`, 최종parent `run_v7/primary_campaign_receipt.json`이다. 검증・그림・재현・정확지표시각/자료역할은[공유README](results/history_control_plan_01/run_v7/README.md)를따른다.
