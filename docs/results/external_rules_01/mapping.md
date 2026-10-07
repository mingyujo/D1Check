# 외부 판단 규칙의 사전 대응표

2026-10-07. EXTERNAL-RULES-11. 성능 결과를 열기 전에 고정한다. A는 입력·행동 의미를 유지한 규칙 재현, B는 실행 단위 또는 자원을 바꾼 제한적 재현, C는 현재 환경에서 핵심 행동을 보존할 수 없는 비교 보류다. 외부 앱 전체를 실행한 실험이 아니다.

| 원래 개념 | 우리 엔진의 대응 | 유지되는 부분 | 변경·생략되는 부분 | 비교 가능한 주장·수준 |
|---|---|---|---|---|
| Ente Android `DeviceHealthPolicy` | 별도 외생 상태 snapshot의 허용/거부 함수 | 배터리 `<20%`, BAT `>42°C`, 건강 good, 열 nominal/light/moderate, 관측 나이 120초 이하·미래 관측 거부, Android 열 unsupported 예외 | 실기기 센서 수집 대신 합성 신호. AP와 BAT를 연결하지 않음 | 같은 상태 입력에서 허용 판정 A. 실기기 건강 예측 검증 아님 |
| Ente `ComputeController`의 사용자 활동 | 마지막 활동 뒤 Android 기본15초 timer, 건강/차단/초기확인과 AND | 활동마다 timer 재설정, override false, 건강 변경/주기 갱신으로 재판단 | foreground Ente gallery에 한정. stream/lock/다운로드/네트워크·사진 선택은 제외 | 시작 허용 핵심 A, 아래 작업 대응을 포함한 일정 비교 B |
| Ente 다음 이미지 분석 시작/일시정지 | normal 탐지 요청의 시작만 허용, urgent 분류는 원래대로 | 대기 요청 유지, 실행 중 요청 비선점, 새 작업 시작 전에 재검사 | 사진의 얼굴/CLIP 묶음을 탐지 whole-request로 대응. urgent는 Ente ML 대상에서 제외. 이미지 중간 pause를 요청 내부에 삽입하지 않음 | 같은 EFT 하위 배정에서 배경 시작 허용 효과 B. Ente 전체·원 사진 pipeline 성능 비교 불가 |
| Band 기본 HEFT, reserve=false | `BAND_HEFT_WHOLE_REQUEST_ADAPT_V1` | 전체 도착 FIFO window, model/progress 중복 검색 제거, worker wait+expected 최소 실행계획, 그 최솟값이 가장 큰 요청 우선, 최선 worker가 바쁘면 yield하며 예상 대기를 증가, idle에 배정 | 단일 unit subgraph를 whole-request 5단계로 대응. CPU/GPU 두 worker와 검증된 CG_DC만 허용. subgraph 연결/전송·DSP/NPU·worker 내부 큐 없음 | 자원 범위·단위가 다른 B. Band 논문 전체 알고리즘의 재현이나 성능 아님 |
| Band 비용 예측·갱신 | 개발 평균 전체 lane 점유시간을 초기 expected로, 완료된 lane 점유시간만 EMA alpha=.1 | expected와 실현값 구분, 완료 뒤만 갱신, 원 기본 smoothing .1 | 원 subgraph Invoke 시간 대신 전체 5단계 점유시간. 원 microsecond integer EMA를 ns integer로 대응 | 동일 축약 단위에서 온라인 예측갱신 B. 실제 subgraph 프로파일 없음 |
| Band SLO | HEFT 주 비교는 원 API의 SLO 미지정 경로, 우리 기한은 사후 서비스 평가 | 모든 예정 요청을 보존·실행 | Band 최소 여유시간 LSF의 예상 초과 early-drop을 우리 전량 완료 문제에 이식하지 않음 | HEFT의 무SLO 경로 B. LSF는 C·성능 비교 보류, 조건 진단만 수행 |
| MediaPipe Tasks LIVE_STREAM | 비교 보류 | busy일 때 새 frame을 무시하는 실제 규칙 확인 | 요청 전량 완료·일반 저장 요구와 목적이 다름 | C. drop을 제거하고 MediaPipe 이름을 붙이지 않음 |
| LiteRT SchedulingInfo | 비교 보류 | priority/UID/group metadata 전달 API 확인 | 독립 CPU/GPU 요청 선택 정책을 확인하지 못함 | C. 실행 API를 스케줄러로 만들지 않음 |
| Android NPU Manager | 비교 보류 | 모델 load 승인/unload·앱 우선순위·vendor HAL 조정 기능 공식 문서 확인 | 현재 NPU 메모리/선점·모델 load 상태/기기별 J/AP 모형 없음. 확인 문서에 구체적인 정책 임계값·큐 선택 규칙이 모두 제시되지 않음 | C. 공개 기능 존재와 이 엔진의 재현 가능성은 별개 |

## 사전 고정 사항

- 원본: Ente `df443fdf479141c8f51152bb371371bb01e4111f`, Band `8600d4960ccb6f121221f6d252da8dbef2db160b`. 코드별 URL·SHA·위치는 `sources.json`에 기록한다. Band 논문(2022)과 현재 코드(2023 이후)를 같은 버전으로 합치지 않는다.
- Ente 기본 생성자 값은 20%,42°C,최대관측나이2분. 설정 가능한 생성자 파라미터이지만 소스에 수치 허용 범위 검사가 없다. Android 활동15초/iOS5초는 플랫폼 상수. Ente gallery의 저장 설정 미지정 interaction override는 false이고 local-gallery 기본은 true다. 이번은 Ente gallery/override=false만 사용한다.
- Band window 기본 INT_MAX, reserve=false는 기본 HEFT 생성 경로. EMA .1, 허용범위[0,1], window>0. 요청 우선 동점은 FIFO 첫 항목(`largest < latency`), backend 동점은 열거상 마지막 후보(`min >= total`), 우리 CPU0/GPU1 순서에서 GPU. LSF의 `std::sort` slack 동점은 원 코드에서 안정 순서 미지정이다.
- 성능 비교는 자원 배정과 시작 허용을 분리한다. 결합 실험은 수행하지 않는다. 자원 비교는 모두 즉시 허용이고 원래 CPU/SPLIT/EFT/SHARED_EDF/SHARED_EFT/ENERGY_AP_REQUEST/ARRIVED_QUEUE_J_PEAK_AREA와 Band adapter다. 강한 동적 대조는 SHARED_EFT이며, 정적 CPU/SPLIT 두 배정과 비교해 고정 배정의 손익도 함께 확인한다. 시작 허용 비교는 항상 허용 EFT와 Ente gate+같은 EFT다.
- trace는 기존 생성기의 4개 부하·3개 전체 시간문맥·4개 새로운 합성 seed. 새 seed는 독립 실기기 holdout을 뜻하지 않는다. 정책 조정/개발 후보 선택0. 작은 fixture·첫 조건 pilot 뒤 계약 범위를 그대로 완료한다.
- 상태 시나리오는 quiet healthy, 간헐 활동[36,50]초, 지속 활동30~110초/10초 간격, 배터리19→20%/60초, 배터리19% 지속, BAT43→42°C/60초, thermal serious→moderate/60초다. 그 외 BAT30°C/80%/good/nominal·매60초 fresh snapshot. 숫자는 threshold 경계 민감도를 위한 합성이며 사용자 행동/배터리 변화의 실측 분포가 아니다. 상태 변화의 전력 비용은 미지원·추정하지 않는다.
- 동일0~120초 J, AP35~180초. 미완료면 J는 공통창 부분 처리 비용으로 남기고 완전 작업 절감 주장 차단, AP180은 null·35~120 partial 경로 별도. AP의 검증된 안전 온도 한도 없음: 한도 초과 시간 null. 유휴 기준 초과면적은 안전 한도가 아니다.
- 대표 시간표는 최소 seed/queue/mean의 EFT와 Band, 시작 허용은 최소 seed/low/mean/간헐 활동의 두 정책으로 결과와 무관하게 고정한다. 모든 조건은 CSV로 공개한다.
- source adapter는 기존 empirical opt-in callback ABI `EFT_REFERENCE`를 사용하지만 public ID와 출력 경로를 분리한다. 기존 engine/model/기본/strict는 수정하지 않는다. controller 시간·기기 에너지는 미측정이며 기존 PC 차등 overhead0 가정을 표시한다.
