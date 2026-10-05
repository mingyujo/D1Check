# S26 담당자 회신·사전 등록 검토·텐서 인계 — 2026-10-06

상태: PC 검토·기존 입력 포장 완료. 새 기기 실행 승인·정책 효과 PASS 아님. 읽은 S26 원격 HEAD `5d98fe752491992595bb821ca48decb7640e5933`; 원 브랜치 merge/수정 없음. 검토 대상 [등록 v1](https://github.com/mingyujo/D1Check/blob/5d98fe752491992595bb821ca48decb7640e5933/d1sim/docs/정책비교_사전등록_v1.md) (등록 commit `589a75b`)와 [export](https://github.com/mingyujo/D1Check/tree/5d98fe752491992595bb821ca48decb7640e5933/s26/exports/20261005/). 원자료 전체를 재판독하거나 모형을 검증한 것은 아니다.

## 1. 담당자에게 전달할 결론

EfficientNet-Lite0 FLOAT32 원본 SHA `6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0`를 정책 비교·폰 확인 대상으로 고정하는 방향을 채택했다. MobileNet V1은 열 모형 개발·민감도 자료로 분리한다. 등록 v1의 NPU AOT SHA `311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31`는 원본과 다른 artifact다. 원본 동일성·변환 provenance·실행 정밀도·품질·모델 간 열 전이를 각각 확인해야 한다. 문서에 FP16은 추정으로 적혀 있으므로 확인 전 사실로 승격하지 않는다.

**등록 v1을 공동 검토 통과로 승인하지 않는다. 아래 항목을 v2에 명확히 한 뒤 평가할 것을 권고한다.** 이미 실행했다면 v1 결과는 보존하고, 같은 결과를 v2의 새 독립 확인으로 바꾸지 않는다. 검토 기한까지 무응답이었다는 사실은 승인 근거가 아니다. 현재 읽은 커밋은 정책 시뮬 실행0으로 적혀 있지만 이후 현황은 담당자 확인이 필요하다.

## 2. v2 수정 요청 — 새 측정 추가 요청이 아님

| 우선/위치 | 확인한 내용 | 필요한 수정·판독 경계 |
|---|---|---|
| 필수 §2·5 기한 | FG 기한1.5초를 정의하지만 가드는 기준선P95 대비 허용 악화뿐. BG는300초 d100 작업 묶음의 slack 기반 긴 기한이며 요청128추론 chunk다 | 기준선 자체의 서비스 부적격과 상대 비악화를 분리. FG 전체 예정 분모의 on-time/실패/미완료 및 절대 기한 조건을 명시. BG는 A24 일반6초와 동일 서비스가 아님을 선언하고 묶음/청크의 기한 상속을 고정. 임의 허용폭을 이번 회신에서 대신 만들지 않음 |
| 필수 §4 oracle | 미래를 아는5³ 상수duty 조합 최저값을 '열 비용 하한'으로 표현 | 적응형 ours를 포함하지 않는 제한 탐색집합의 최저값은 전체 정책의 하한이 아니다. '미래정보를 사용한 제한 상수duty 참조 최저값'으로 변경. 회수율은 전역 달성가능 여지 회수율이 아닌 참조 정규화 차이이며1초과도 오류라고 단정하지 않음. 진짜하한이 필요하면 포함관계/완화 근거 별도 필요 |
| 필수 §9 폰 확인 | FG 도착이 없는 BG duty 체인 재생, 작업비0.95만 요구 | BG 부하율 재생의 열 반응 확인으로 제한. 온라인 정책·FG1.5초·전체 서비스 가드의 폰 검증 아님. 0.95는 동일 작업량이 아니며5%미완료/작업량차를 표시. 동일 작업량 효과를 주장하려면 동일 예정량·완료량 및 완료/tail 경계를 고정 |
| 필수 §1·7 모델 전이 | MobileNet 모형을 EffNet에 전용; GPU는60초자료, NPU1런 근거 | 모형 내 탐색은 가능하나 전이 가정 표기. 해당 조건의 열·감속 모형 미확인이면 폰효과/독립 예측검증 결론을 보류. MobileNet 자료와 EffNet 정책 확인을 합치지 않음 |
| 중요 §4 pace-rand | ours의 실현duty분포에서 표본추출하면서 '평균이같다'고 표현 | 기대 평균만 같고 실제 평균은 다를 수 있음. 실제duty·작업량 차이 보고 또는 동일multiset 순열 방식 등을 결과 전 고정. ours 결과를 사용하는 사후 대응 대조군이지 독립온라인정책이 아님 |
| 중요 §6·9 선택 | 홀드아웃에서 효과가 큰1~2조건을 폰확인으로 선택 | 새 폰 데이터는 새 관측이나 조건은 홀드아웃 성과로 선택됨. 전체조건 분모와 선택이력 보존; 일반 조건의 효과/무편향 평균 아님. seed는 도착표본 반복이지 독립기기세션 수가 아님 |
| 중요 §3·5 수치 기준 | 개발seed CV와1°C/60초를 screening에 사용 | 검정/기기오차/물리안전 기준으로 쓰지 않음. CV=sd/mean의비율→% 또는%p 변환,mean0/null,성공표본만의P95,기준선선정 범위와동률을 코드에서 고정. fixed-prio와'가장강한기준'의 역할 구분 |
| 중요 §0·11 우선순위 | 미접근 공유문서가 정본, 코드는추후동결 | 판정을 바꿀 수 있는 외부 미동결 문구를 우선시키지 않음. 평가전에 실행코드·입력·모형·판독·기준선hash와문서버전을 하나로 고정 |

위는 범위·논리 검토다. 생성기/정책 코드 전체 실행 검증 또는 S26 실기기 검증을 대신하지 않는다. 새 단순 정책이나 RL 학습을 추가하도록 요청하지 않는다.

## 3. 대표 입력 전달 — 준비 완료, 전송은 별도

- GitHub: [20개 대응 manifest](s26_interface_20261006/tensor_manifest.json), [검증·zip 해시](s26_interface_20261006/verification.json), [CPU 참조·출처](s26_interface_20261004/quality_reference.json), [기존 전처리·7경계](S26_SCOPE_AND_INTERFACE_20261004.md).
- Git 밖 zip: `C:/Users/LG/Documents/D1Check_Arrival_Extension/s26_quality_handoff_20261006_v1/s26_quality_inputs_v1.zip`
- 3,807,484 bytes, SHA-256 `3bf4659997c2ccd188563d4ee0cdf42c174ebaf175ad58eaab3d28128dd8dcdd`.
- 구성43파일: input20 + CPU raw출력20 + 참조JSON + manifest + README. 모델·이미지·APK·키·기기식별정보 없음. 텐서는 기존파일 byte복사, CPU출력은 기존JSON의float32복원으로 해시 일치. **새전처리/추론0**. 아직 팀원에게 전송한 것은 아님.
- 각 입력602,112bytes=`1×224×224×3×4`, little-endian float32 NHWC RGB. canonical-sRGB PNG→Q16 half-pixel bilinear round-half-up stretch224→`(RGB-127)/128`; crop/padding없음. **수신 후 resize/정규화를 다시 하지 않는다.**
- sample_id로 canonical이미지SHA·원본SHA·출처/저작자/라이선스·inputSHA·CPUoutputSHA가 연결된다. 참조출력은 Softmax `[1,1000]`,0기반labels. 대표20장은 ImageNet 정답 정확도 corpus가 아님.

수신 검증: zip SHA를 먼저 대조하고, 압축해제 뒤 manifest의각input/output bytes/hash와참조JSON hash를검사한다. 기존 참조JSON은 `python -B -m tools.d1_s26_quality_handoff --bundle docs/team/s26_interface_20261004/quality_reference.json`으로 검증 가능하다. 실제 입력파일 hash도 별도 검사해야 한다.

### 품질 기준 회신

CPU CompiledModel부터 기존 CPU reference와 대조하고 NPU의입력dtype와실행정밀도를분리한다. raw finite/shape/label순서는필수. 기존FP32허용식 `abs(diff)<=1e-4+1e-3*abs(ref)`는기존경로용이며FP16에자동적용하지않는다. top1일치율·top5집합겹침·cosine·최대/평균수치오차를이미지별로보고,top5순서동일과집합겹침을구분한다. 별도FP16합격선은**결과 전**근거와함께등록;근거없으면지표만보고PASS보류. 결과보고tolerance완화금지. 정답정확도·20장밖일반화아님.

## 4. export 확인·추가 원본 요청 범위

읽은 최신export에는 `sensors/`, `c2_sensors/`, `c2/`가 이미Git에있다. 전달메시지의'센서전부Git밖'과달라서이미있는파일을중복요청하지않는다. 단전기적분재현용원시러너JSONL 등은밖에있으며1Hzexport만으로J재현가능하다고하지않는다. 필요한런이특정될때 inventory SHA로요청한다. 민감logcat은그대로공유하지않는다.

export README의귀속30PASS/11재사용미판정/4FAIL은확인했다(원logcat독립재판독아님). CPU XNNPACK 범주누락의parser FAIL과실제추론실패를구분. 다음규칙으로기존로그를재판독하면사후분석으로표시하고원FAIL보존. EffN600 안전중단·missing, C2부적격도유지한다.

## 5. 전달 분량·현재 완료 경계

본문2쪽+부록1쪽·발표2장에동의. 그림1=동일모델/경계의열이력과처리율,그림2=실제로확인된정책또는BG재생효과,표=모형전이/서비스/품질/J의완료·미확인. FG없는재생이면전체정책확인처럼그리지않는다. 10/11측정동결/10/12초안/10/13대조는협업일정이며추가실행승인이아니다.

검증2026-10-06: 기존참조20/입력20해시일치·20CPU출력float32복원일치·zip43파일roundtrip통과. [기록](s26_interface_20261006/verification.json). 링크/diff검사. 모델계수/기본정책/strict/experiment_ready=false불변. 기기·설치·APK빌드·추론·학습·새시뮬0. 사용자PDF/HTML보존. S26 브랜치는읽기만했다.
