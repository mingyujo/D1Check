# 기존 시스템 판단 규칙의 재현과 동일 조건 비교

2026-10-07, EXTERNAL-RULES-11. [오프라인 비교 화면](results/external_rules_01/index.html) · [사전 대응표](results/external_rules_01/mapping.md) · [공유 계약·명령](results/external_rules_01/README.md).

**완료: Band의 요청 단위 제한적 적용은 지속 도착12조건에서 전량·기한을 유지하면서 강한EFT보다 모형J/AP를 소폭 줄였다. 우리 두 열·에너지 규칙은 같은 조건에서 기한을 모두 지키지 못했다. Ente 시작 허용은 일부 합성 상태에서 큰 지연·미완료를 보였다.** 실제 외부 제품·실기기 성능 우열은 이 결과로 판단하지 않는다.

## 가져온 규칙과 확인한 원 출처

**외부 시스템 전체를 이식하지 않고, 공개 코드에서 확인한 두 판단 흐름만 실행했다.** Ente Android의 건강·활동에 따른 ML 시작 허용, Band 기본 HEFT의 요청/worker 배정이다. 상태 predicate의 조건은 그대로 표현할 수 있지만 실행 단위와 자원이 달라 일정 비교는 둘 다 제한적 재현 B다.

| 시스템·버전 | 실제 원 규칙 | 우리 환경에서의 대응 |
|---|---|---|
| Ente `df443fdf479141c8f51152bb371371bb01e4111f` | 건강과 활동 종료·compute 차단 여부를 AND. Android 마지막 활동 후15초. 배터리20% 이상, BAT42°C 이하, good health, OS thermal nominal/light/moderate. 관측나이2분 이하. 건강 요청 timeout5초/갱신1분 | 원 상태 판정은 A. normal 탐지 시작에만 gate를 붙이고 urgent 분류는 유지한 작업 대응 B. 아래 자원 배정은 원 EFT로 양쪽 동일 |
| Band `8600d4960ccb6f121221f6d252da8dbef2db160b` | 기본 HEFT reserve=false. FIFO window에서 model/progress 중복 검색 제거. request별 최단 예상계획을 찾고 그 시간이 가장 큰 요청을 선택. 최선 worker가 busy면 예상 대기를 늘리고 yield하여 다른 요청 확인 | subgraph를 하나의5단계 whole-request로, 자원을 검증된 A24 CPU/GPU로 축약한 B. source Invoke expected를 전체 lane 시간으로 바꾸고 완료 관측 뒤EMA .1 |

[Ente 건강 코드](https://github.com/ente/ente/blob/df443fdf479141c8f51152bb371371bb01e4111f/mobile/apps/photos/lib/services/machine_learning/device_health_policy.dart), [활동·요청 코드](https://github.com/ente/ente/blob/df443fdf479141c8f51152bb371371bb01e4111f/mobile/apps/photos/lib/services/machine_learning/compute_controller.dart), [Band HEFT](https://github.com/mrsnu/band/blob/8600d4960ccb6f121221f6d252da8dbef2db160b/band/scheduler/heterogeneous_earliest_finish_time_scheduler.cc), [원 expected·EMA](https://github.com/mrsnu/band/blob/8600d4960ccb6f121221f6d252da8dbef2db160b/band/latency_estimator.cc). 관련 파일의 SHA·정확한 symbol 위치는 [sources.json](results/external_rules_01/sources.json)에 기록했다. Band 논문2022의 모든 세부 동작을 이 현재 코드 버전과 동일하다고 단정하지 않는다.

Ente 생성자20%/42°C/최대관측나이는 바꿀 수 있는 설정값이나 원 코드에 수치 허용 범위 검사가 없다. Android15초/iOS5초는 플랫폼 상수이며 이번에 iOS는 사용하지 않았다. Ente gallery의 저장 설정 미지정 override=false를 사용하며 local-gallery의 기본true와 구분한다. BAT missing·건강 unknown은 거부한다. Android thermal unsupported라도 BAT 온도·건강이 알려져 있으면 thermal 입력만 예외 처리하고, 나머지 배터리 제약은 그대로 유지한다. snapshot이 미래이거나 너무 오래됐으면 거부한다.

Band 원 window는 INT_MAX/설정은 양수, EMA 기본 .1/허용[0,1]이다. job 우선순위의 정확한 동점은 FIFO 첫 항목, subgraph 후보 비용 동점은 열거의 마지막 항목이다. 이번 CPU0/GPU1 열거에서는GPU가 동점에 선택된다. 실제 lane 점유는 예상 시간이 지났다는 이유로 해제하지 않고 관측된 반환을 기다린다. 원 subgraph 이어실행·전송 비용·DSP/NPU·worker 내부 큐/예약은 재현하지 않았다. 이 변경은 핵심 실행 구조를 바꾸므로 Band와 동일 알고리즘이라고 부르지 않는다.

## 조사했지만 주 비교에 넣지 않은 규칙

| 대상 | 확인한 사실 | 보류 이유 |
|---|---|---|
| Band 최소 여유시간 LSF | `deadline−now−shortest expected plan` 정렬. 예상 SLO 초과면 kSLOViolation으로 보내며 planner가 early-drop. slack 동점의 std::sort 안정 순서는 원 코드에서 미지정 | 우리 일반 작업 전량 완료 요구를 바꿈. drop을 없앤 임의 정책을 Band LSF로 만들지 않음 |
| MediaPipe Tasks LIVE_STREAM | busy일 때 새 입력 frame을 무시하는 실제 흐름 제어가 있음 | frame 최신성 목적과 일반 작업 저장·전량 완료의 제어 대상 차이 |
| LiteRT SchedulingInfo | priority/UID/group의 검증과 전달 API를 현재 소스에서 확인 | 독립 CPU/GPU 요청 선택 규칙을 확인하지 못함. API에 우리 임의 스케줄러를 붙이지 않음 |
| Android NPU Manager | Android17+ 모델 load 승인/unload, 앱 priority와 vendor HAL 선점 조정 기능이 공식 문서에 있음 | NPU 메모리/load/선점 행동·기기별 J/AP 모형·현재 trace 입력 없음. 구체 정책 구현 commit과 모든 임계값도 이번 감사에서 미확인 |

[Band LSF](https://github.com/mrsnu/band/blob/8600d4960ccb6f121221f6d252da8dbef2db160b/band/scheduler/least_slack_first_scheduler.cc)와 [planner drop 처리](https://github.com/mrsnu/band/blob/8600d4960ccb6f121221f6d252da8dbef2db160b/band/planner.cc), [MediaPipe 공식 동작 문서](https://developers.google.com/edge/mediapipe/solutions/vision/object_detector/python), [LiteRT 현재 코드](https://github.com/google-ai-edge/LiteRT/blob/419b0551260255bb80d00eb5e0e72753c4ec18a9/litert/runtime/compiled_model.cc), [NPU Manager 공식 문서](https://source.android.google.cn/docs/core/perf/npu-manager?hl=en).

자료 부족과 접근 오류를 구분했다. 필요한 Ente/Band 코드는 공식 저장소에서 commit에 고정해 확보했다. 일부 raw/API 접속 timeout은 같은 공식 GitHub contents API로 복구했다. AOSP/문서 일부 web open은 실패했지만 공식 NPU Manager 문서의 기능 설명은 확인했다. 구체 NPU 정책 미확인을 단순 API 부재나 권한 거부라고 해석하지 않으며 접근 제한을 우회하지 않았다.

## 동일 조건과 근거 경계

- 결과 전 `mapping.md/contract.json/inputs.json/sources.json`을 고정했다. 기존 생성기의 seed610810001~4, low/queue/burst/sustained, mean/short_context/long_context의48조건이다. seed는 합성입력 차이이며 독립 실기기 holdout이 아니다. 정책·조건 선택/튜닝0.
- 자원 비교8정책384행: 순차CPU, 고정분류GPU/탐지CPU, 기존EFT, 공유EDF, 강한공유EFT, 우리에너지AP, 우리큐에너지AP, Band요청adapter. 모든 시작 허용은 즉시이며 기존 설정을 유지한다. 시작 허용 비교672행: 7개합성상태×같은EFT의항상허용/Ente gate. 결합 실험0.
- Ente 상태는 활동 없음,36·50초 활동,30~110초10초마다활동,배터리19→20%/60초,배터리19% 지속,BAT43→42°C/60초,OS serious→moderate/60초다. 다른 상태는80%/BAT30°C/good/nominal,60초마다fresh. 실제 사용자 분포·배터리 방전/발열 모델이 아니라 원 threshold 경계의 합성 민감도다. 상태 변화의 전력 비용을0으로 측정한 것으로 채우지 않았다. 이 외생 부하 비용은 모형 지원 밖이며 정책의 차등 제어비용0은 기존 PC 탐색 가정이다.
- 모델 의미·input·기한·worker/lane 반환·전력/열 계수는 유지했다. 현재모형은 A24 분류CPU/GPU·탐지CPU와 분류GPU+탐지CPU 병행만 지원한다. S26 순차3backend·열 이력의 별도 근거를 이 모형의 NPU나 공동 J/AP 계수로 전용하지 않는다.
- 분류 도착→output_ready1.5초, 탐지 도착→persist_complete6초. 응답 이후 저장·worker release·lane available까지 점유를 유지한다. J는0~120초 공통전체기기, AP는35~180초. 미완료는 공통창 부분처리 J를 남기되 완전작업 절감을 인정하지 않고 AP180은null/35~120 partial경로만 보고한다. AP 유휴 기준 초과면적은 안전 한도가 아니며 AP 안전한도·초과시간은null이다.
- 시간벡터·에너지/AP 계수는 동결 개발 자료에서 얻었지만 새 큐/대기 일정으로 옮기는 것은 모형 가정이다. AP→처리시간 스로틀·BAT·상태변화 부하·기기별controller 비용을 추정하지 않는다. 작은 J/온도 차이의 실기기 유효성은 미입증이다.

## 검증과 소비 기록

원 source 조건의 수작업14검증과 최초10조건 pilot을 먼저 통과했다. Band의 긴 작업 우선·busy yield·동점/중복, Ente의 threshold·timer 재설정·healthy AND·미지원 신호, 공개lane 반환 뒤EMA·no-future/private lane 거부·원EFT 일정 보존·미완료와 비선점을 검증했다. 원 외부 runtime을 직접 실행한 동등성 시험은 아니며 출처의 분기와 수작업 결과를 대조한 수준이다.

198행 저장 후 감사가 기존 엔진의 절대/상대 시각 독립 반올림1ns 차이에서 실패했다. 해당 조건만1환경 진단으로 재계산해 원 엔진 응답·기한은 보존하고 감사표현만 수정했다. 2ns를 거부하는 경계1검증과 부분J/전체분모/null AP의2검증을 추가했다. 등록1,056개 비교 범위와 실패/진단을 포함한 실제1,057환경은 구분한다. fixture4환경은 별도이며 기기·ADB·설치·실측·RL0.

두 번째 중지 확인 시 내부2,400초 시간검사로777행에서 이미 종료한 사실을 보존했다. 최신 사용자 재개 지시에 따라777개 SHA와 원정책/입력/모형을 확인하고 남은279행만 별도1,200초 운영구간에서 수행했다. 원 실험 범위·종료 이유·소비는 초기화하지 않았다. 공유 재현 I/O와 캐시0재계산 시험을2환경으로 확인했다. 총18개의 서로 다른 관련 검증, fixture6환경, 본비교 실패/진단 포함1,057환경, 이번 총1,063환경·새학습/기기0이다.

## 실제 동일 조건 결과

자원 비교384행의25,344예정 요청은 모두 lane 반환까지 완료했다. 시작 허용672행의44,352예정 요청은 미완료도 포함했다. 논리적1,056행/69,696예정 요청의 전체 분모를 보존했다. 아래 P95는 조건별 완료 긴급 응답P95의 평균이며 pooled P95가 아니다.

### Band 요청 단위 적용과 강한 규칙

저부하12조건에서 Band·강한EFT의 보고 지표는 동률이다. 지속 도착12조건에서는 둘 다2,304/2,304요청 전량·기한을 충족했다. Band−강한EFT의 대응 차이는 다음과 같다.

| 지표 | 12조건 평균 차이 | 조건별 범위 |
|---|---:|---:|
| 공통120초 전체기기 에너지 | −0.131672J | −0.182034~−0.073323J |
| AP35~180초 최고 | −0.021760°C | −0.058613~−0.003157°C |
| 유휴 기준 초과면적 | −1.817722°C·s | −2.680764~−1.207932°C·s |
| 긴급 완료 응답P95 | 0ms | 0ms |
| 일반 완료 응답 평균 | −0.020195ms | −0.242335~0ms |
| 실제 합법 병행 시간 | −0.278860초 | −0.531449~−0.196295초 |

모든12조건에서 J·최고AP·면적의 계산값이 함께 감소했다. 전체기기J 평균183.394217→183.262545로 약0.0718%의 작은 모형 차이다. 기기 제어 비용·계수 오차·새 정책의 독립 직접 측정 근거가 없으므로 실기기 개선으로 인증하지 않는다. 병행 시간을 무조건 늘리는 것이 이 모형의 목적과 같지 않다는 결과도 남긴다.

같은 지속 도착에서 완료된 우리 규칙을 포함한 결과는 다음과 같다. 모든 정책의 작업 자체는2,304/2,304완료했지만 기한 준수는 달랐다.

| 규칙 | 전량·기한 조건 /12 | 요청 기한 준수 | 긴급P95 평균 ms | 일반 응답 평균 ms | 전체120초 J | 최고AP 평균 °C |
|---|---:|---:|---:|---:|---:|---:|
| 순차CPU | 9 | 99.653% | 858.137 | 1,757.463 | 185.386414 | 31.744142 |
| 고정분류GPU/탐지CPU | 12 | 100% | 294.055 | 912.669 | 184.825634 | 32.502813 |
| 기존EFT | 12 | 100% | 294.055 | 977.115 | 183.564394 | 32.303229 |
| 공유EDF | 12 | 100% | 294.055 | 912.669 | 183.394217 | 32.417201 |
| 강한공유EFT | 12 | 100% | 294.055 | 912.669 | 183.394217 | 32.417201 |
| 우리에너지AP | 0 | 95.009% | 1,948.794 | 4,165.488 | 182.507506 | 32.444316 |
| 우리큐에너지AP | 0 | 97.526% | 1,720.781 | 3,963.720 | 182.906747 | 32.361148 |
| Band요청단위적용 | 12 | 100% | 294.055 | 912.649 | 183.262545 | 32.395441 |

우리 규칙들의 더 낮은J는 기한 손실과 함께 해석해야 한다. 순차CPU는 열이 낮지만 기한 손실과 높은J가 있다. 저부하에서는 모든8정책이12조건을 충족했으나 우리에너지AP의 긴급P95 평균1,386.578ms는 강한EFT/Band156.180ms보다 길었다. 큐 밀집·버스트의24조건에서는 Band와강한EFT 모두 전량 기한 충족0이다. 이 과부하 층의 비용 차이를 적격 정책 전체의 우월성으로 합치지 않았다.

### 차이는 실제로 어디에서 발생했는가

사전 고정 대표는 seed610810001/queue/mean이며, 시간표의 대조는 등록된 기존EFT다. Band는 분류GPU3→6건·병행0.914488→1.828977초로 바뀌었다. normal 기한 미준수3→2건, 일반응답4,094.366→3,699.682ms/J141.993716→141.863975로 줄었지만 긴급P95294.055→390.858ms·최고AP30.410273→30.476843°C로 늘었다. 대표의 이 상충도 그대로 보존하며, 좋은 지속 조건으로 대표를 다시 고르지 않았다.

첫 다른 배정에서 기존EFT는 분류요청3의 CPU 예상 응답이 빠르다는 이유로35.621737초 CPU를 기다렸다. Band의 longest-shortest/yield 흐름은35.613263초 그 분류를GPU로 보내고, 기다리던 탐지를35.621737초 CPU에 시작했다. 우선순위·자원 선택·busy-best 우회가 실제 일정 차이에 관여한다. 지속 조건의 EMA·배정·타이밍 변화도 함께 포함되므로 구성요소 제거 실험 없이 한 요소만의 인과 효과로 단정하지 않는다. [대표별 요청 차이37행](results/external_rules_01/representative_differences.csv)와 대표 결정/EMA 기록을 보존했다.

### Ente 시작 허용과 같은 하위 EFT

활동없음·건강 시나리오는48조건 모두 같은 EFT lane 일정이었다. 저부하의12조건/288예정 요청에서는 다음과 같다.

| 합성 상태 | 완료 | 기한 준수 | 긴급P95 평균 ms | 일반 응답 평균 ms | 해석 |
|---|---:|---:|---:|---:|---|
| 활동없음·건강 | 100% | 100% | 156.180 | 619.471 | 항상허용 EFT와동률 |
|36·50초 활동 | 100% |29.167% |156.180 |20,168.652 | BG가65초까지미뤄짐·완료손실없으나큰지각 |
|10초마다계속활동 |25% |25% |156.180 |계산불가 | 일반요청216/216미실행 |
|배터리19→20%/60초 |100% |21.875% |5,589.687 |17,422.502 | 허용후오래된BG의aging도영향 |
|배터리19%지속 |25% |25% |156.180 |계산불가 | 일반요청216/216미실행 |
|BAT43→42°C/60초 |100% |21.875% |5,589.687 |17,422.502 | 같은시간에허용되므로배터리회복과동일일정 |
|OS serious→moderate/60초 |100% |21.875% |5,589.687 |17,422.502 | 같은허용시각의조건진단 |

36·50초 활동의 하위EFT 자원 배정은 동일하게 두고 start gate만 바꿨다. 원0~120초 J는 평균142.123292로 사실상 같지만, AP 최고는30.205468→30.538561°C로 높아졌다. 늦게 모아서 처리하면 이 모형에서 최고AP가 항상 낮아지지 않는다. 긴급 요청을 gate에서 제외했어도 허용 후 오래된 일반 큐의 기존aging이 우선권을 얻어 일부 상태에서는 긴급도 지연됐다. urgent 자체의 gate 제외가 전체 서비스 보장을 뜻하지 않는다.

계속활동/저배터리지속의 J134.144914는 약7.978377J 적지만 전체 요청75%를 하지 않은 값이다. 동일 완료량 절감으로 인정하지 않으며 AP180도null이다. Ente의 원래 지연가능 사진 indexing 목적을 우리1.5/6초·전량 요구와 바꿔 비교한 B 수준이므로 Ente 제품이 실패했다는 결론으로 쓰지 않는다.

## 최종 검증·공유물·종료 범위

18관련검증,1056행/69696요청의원도착·응답/L/lane 중복·지원상태 감사,첫seed264묶음J/AP재계산 최대차이0,항상허용EFT 전상태 같은일정·quiet gate48조건같은일정,원13소스/모형·사용자9파일SHA 확인을 완료했다. 절대/상대 응답시각 표현 차 최대1ns는 원 엔진값을 그대로 보존한 감사 기록이다. 외부 runtime 실행 동등성·물리정확도 PASS와 구분한다.

그림8개 PNG/SVG, 전체CSV, 조건별차이, 대표기록과 오프라인HTML을 공유한다. [판단 표](results/external_rules_01/01_판단규칙.png), [자원 시간표](results/external_rules_01/02_자원시간표.png), [시작 허용 시간표](results/external_rules_01/02_시작허용시간표.png), [응답/완료](results/external_rules_01/03_응답완료비교.png), [J/AP 차이](results/external_rules_01/04_에너지열비교.png), [AP 경로](results/external_rules_01/05_온도경로.png), [조건 지도](results/external_rules_01/06_조건지도.png), [시작 허용 상태](results/external_rules_01/07_시작허용조건.png).

미완료는 명시적으로 보류한 LSF/MediaPipe drop 비교와 LiteRT/NPU의 미확인·미지원 규칙, 원 subgraph/전체 제품 및 독립 실기기 검증이다. 이번 PC 조사·제한 adapter·고정 비교·시각화는 완료 범위다. 기준 정책·동결 모형·strict·experiment_ready=false를 유지하며 새 자체 정책·보상 튜닝·학습·실측을 추가하지 않는다. 재현 명령은 [README](results/external_rules_01/README.md)를 따른다.
