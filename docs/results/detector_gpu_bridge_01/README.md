# 탐지 GPU 시간 자료 재사용과 현재 비용 공백

## 2026-10-06 추가 완료: 호환 자원 backfill의 실제 PC 경로

[새 비교 화면](compatible_backfill_v2/index.html), [동일 seed 대조](compatible_backfill_v2/paired_comparisons.csv), [등록](compatible_backfill_v2/registered_before_run.json), [검증](compatible_backfill_verification.json). 시작 HEAD `dd89aea5506afa86ddd6ad06ccc8ef7a3730c505` 이후의 PC 수정이며, 아래 이전64계산과 구분한다.

분류는 CPU에 두고 탐지만 빈 CPU/GPU에 배정하는 `CLASS_CPU_DETECTOR_BACKFILL_PC_V1`을 별도 opt-in으로 연결했다. 실제 도착 큐·우선순위·4초 aging을 사용하며 미래 도착이나 실현 처리시간을 받지 않는다. 같은 종류의 CPU/GPU 동시 점유를 금지하고, worker_release가 아니라 실제 lane_available 이벤트까지 busy를 유지한다. 앞 요청이 합법 자원을 사용할 수 없을 때 뒤의 호환 요청을 배정한다. **뒤 작업이 앞 작업의 미래 응답을 전혀 늦추지 않는다는 예약 보장은 없다.** EASY 또는 보수적 backfilling 원 알고리즘의 완전 재현이 아니다.

동일 CAL03 시간 프로필·기존 입력8개·seed623001/623002·간섭 가정1.0/1.5를 유지했다. 새16계산/768요청, 저장 정적48계산은 재사용했다. 이 입력은 이미 본 자료이므로 사후 개발/소프트웨어 평가다. 현재 실측 기반 EFT의 서로 다른 시간 프로필과 원 지연값을 직접 비교하지 않았다. 제어 비용도 기존 PC phase 설정이며 실기기 제어 비용 검증은 아니다.

| 입력·간섭 | 새 후보 기한/도착 | CPU 직렬 / 고정 CG_DC 기한 | 새 후보 긴급 P95(ms) | 새 후보 일반 평균(ms) | 판독 |
|---|---:|---:|---:|---:|---|
| low·1.0/1.5 | 각각96/96 | 각각96/96 / 96/96 | 159.200 | 622.788 | CPU 직렬과 동일, DG 사용0 |
| queue50·1.0 | 96/96 | 96/96 / 96/96 | 833.204 | 1,876.743 | CG_DC 대비 긴급−51.475ms / 일반+718.595ms |
| queue50·1.5 | 96/96 | 96/96 / 96/96 | 947.637 | 2,299.275 | CG_DC 대비 긴급−227.284ms / 일반+942.740ms |
| queue75·1.0 | 96/96 | 96/96 / 96/96 | 971.197 | 1,151.824 | CPU 직렬 대비 긴급 동일 / 일반+101.414ms |
| queue75·1.5 | 96/96 | 96/96 / 96/96 | 971.829 | 1,253.165 | CPU 직렬 대비 긴급+0.632ms / 일반+202.756ms |
| burst50·1.0 | 60/96 | 56/96 / 74/96 | 950.028 | 7,564.673 | 전체 서비스 실패 |
| burst50·1.5 | 46/96 | 56/96 / 33/96 | 8,641.780 | 7,341.746 | 전체 서비스 실패·긴급 악화 |

각 행은2seed합계96도착, P95/일반평균은 사례별 지표의 평균이고96표본을 합친 P95가 아니다. 새16사례 중12사례가48/48기한을 충족했다. 탐지GPU배정94건, 미측정 같은 종류 병행0초다. 모두 PC 시간 진단이며 새 실측이 아니다.

**새 기본 정책으로 채택하지 않는다.** 큐의 긴급/일반 응답 상충과 버스트 기한 실패가 남았고, 현재 DG/CC_DG 증가 전력·AP 전환 항은 계속 null이다. 과거 고정 상태의 존재는 현재 짧은 요청 비용이나 예측 정확도 확인과 다르다. 이 결과만으로 새로운 DG 실측을 우선 실행하거나 원래 열·에너지 공동 절감을 완료했다고 판정하지 않는다.

첫 실제 `python -m` 실행은 `__main__`과 canonical 모듈의 Controller 타입 불일치로 첫 사례의 이벤트 실행 전에 중단됐다. [실패 기록·등록·정확한 당시 소스](compatible_backfill_v1/PC_FAILURE.json)를 보존하고, CLI를 canonical 함수로 연결해 별도 v2에서 실행했다. 자료 파싱의 `start_ns`를 실제 `execution_start_ns` 필드로 고친 것은 후처리 결함이며 일정이나 계수를 다시 맞추지 않았다.

기존 이벤트 본문은 변경하지 않았다. opt-in 식별·검사·라우팅만 추가했음을 실행 전 원본 byte snapshot과 정확한 변환 검사로 확인한다. 기존 CPU_URGENT/B2/B3의 대표 경로 결과 전체가 원본과 일치한다. 옛 등록 해시를 현재 해시로 덮어쓰지 않으며, 다른 이벤트 본문 변경은 재집계에서 거부한다. 기존 모형·기본 backend 마스크·strict·미소비 queue24·`experiment_ready=false`는 유지한다. Android 수정·APK 빌드·기기 명령·새 기기 계획·claim0.

```powershell
# 저장된 gzip ledger 재집계·그림; 새 시뮬레이션 없음
python -m tools.d1_compatible_timing_report
python -m unittest tools.test_d1_compatible_timing_backfill tools.test_d1_compatible_timing_report -v
# 본 시간 탐색을 새 PC 폴더에서 재현할 때만 16계산 수행
python -m tools.d1_compatible_timing_backfill --output output/compatible_backfill_reproduction
python -m tools.d1_compatible_timing_report --root output/compatible_backfill_reproduction
```

공유 입력·시간 벡터·기존 정적 ledger·원 이벤트 source snapshot을 저장소에서 읽는다. 본 재현과 회귀 fixture를 실측 독립 세션 수로 집계하지 않는다. gzip 재집계는 event simulate를 차단한 테스트에서도 통과했다. 최종 신규13검사+관련23회귀=36통과, 별도 실제 CLI와 그림 검수는 검증파일에 기록했다. 현재 권고는 지원되는 EFT와 기한 우선/Pareto 상충 판독을 유지하는 것이다.

아래는 이전 시간 자료 연결 작업의 원 보고이며 그대로 보존한다. 이전의 “새 정책을 만들지 않았다”는 해당64계산 단계에 대한 설명이다.

2026-10-06, 시작 HEAD `865f7617414258951f3289e5efd04f633a3b30c7`의 후속 PC 작업이다. [집계 화면](index.html), [전체 표](timing_groups.csv), [대표 일정](timing_reference.png). 새 실측·모형 fitting·전력/열 가정·기기 계획·소비 claim은 없다.

## 결론과 이번에 끝낸 것

**탐지 GPU의 시간 자료가 없는 것이 아니라, 현재 짧은 요청 모형에 전이됐다는 근거와 J/AP 항이 없는 상태다.** 과거 CAL03의 dispatch→start→output→persist→worker_release→lane_available 원본 경계를 확인했다. 현재 기기에서 다시 확인한 것은 아니다. GPU delegate 판정도 과거 host 검증의 `verified_full`에 연결된다. 기존 동결 계수·기본·strict·`experiment_ready=false`를 바꾸지 않았다.

과거 자료만으로 모든 탐지를 GPU로 보내는 것이 좋다는 결론도 나오지 않았다. 같은 과거 시간 벡터의 정적 CC_DG는 queue 50%에서 일반 지연과 기한 위반을 늘렸다. 기존 4-cell EFT 참고는 일부 시간 개선을 보이지만 **분류 CPU+분류 GPU의 미측정 병행**을 사용하므로 지원된 새 정책으로 승격하지 않는다. 계산하지 못한 J/AP는 모든 행에서 null이다.

## 원자료와 현재 계약 대응

[추출·출처 해시](run_v1/timing_evidence.json), [미식별 항](run_v1/requirements.json). 원본은 외부 `D1Check_Arrival_Extension/timing_cal03_run_v1/`이며 개발/확인 각각 네 cell의 한 독립 세션×4상관 요청, 총32요청이다. 셀은 분류 CPU/GPU 긴급, 탐지 CPU/GPU 일반이다. 각4개 요청을4독립 세션으로 계산하지 않는다.

| 항목 | 확인 사실 | 재사용 경계 |
|---|---|---|
| exact 모델·입력 | 개발 vector와 원본 bytes/입력 tensor SHA 일치; 두 모델 SHA가 현재와 일치 | 모델 파일/전처리 근거 재사용 가능 |
| runtime·resident | LiteRT1.4.2, CPU thread1, GPU strict 설정과 네 runtime resident의 기록이 일치 | 동일 설정 기록이지 모든 엔진 비용 동일 인증은 아님 |
| W/L 경계 | 실제 worker_release와 lane_available 필드 존재, 5단계 순서/벡터 일치 | W가 없다는 기존 우려는 제거; 응답과 점유를 구분 |
| APK·프로토콜 | 과거 APK와 현재 APK SHA 불일치; 과거는 고정 단독4요청 | 새 요청 준비/기록/간섭 비용의 전이는 미확인 |
| 과거 전력/AP | 고정 반복 상태 평균값이 보존돼 있음 | 현재 baseline 대비 요청 증가분/짧은 전환 항으로 복사하지 않음 |
| 현재 DG/CC_DG | 서비스 전이, 추가 W, AP 전환은 null | 현재 동결 3-cell 모형에 자동 추가하지 않음 |

lane 전체 길이의 기술 평균은 과거 개발/확인 순으로 CC 172.640/156.052ms, CG 320.513/296.195ms, DC 624.373/610.549ms, DG 1,135.914/1,111.902ms다. 한 세션 내4개 값의 평균이며 보편 tail/WCET가 아니다. 원 요청별 벡터를 보존해 단계를 따로 중앙값 내 합치는 오류를 피했다. 과거 A→S 준비 비용과 현재 경로가 다르므로 이 값을 현재 비용으로 동일시하지 않는다.

현재 코드 제한도 확인했다([파일·해시·행](code_boundary.json)). 앱은 `EnergyCollectionCore.KEYS` 네 runtime을 만들고 두 번씩 warmup하며 DG runtime 자체가 없는 것은 아니다. 그러나 **현재 online study의 `ArrivalPolicyStudy.choose`는 탐지를 항상 CPU로 선택**한다. recorded replay의 `validate`도 CPU_URGENT 또는 기존 B2 배정만 허용해 DG를 계획 파일에 적는 것만으로 실행되지 않는다. PC 실측 기반 요청 경로의 `CELLS/backends/STATES` 또한3cell만 허용한다. 따라서 현재 상태에서 단순 manifest 변경으로 새 배정을 실행할 수 있다고 안내하지 않는다. 해당 확장에는 별도 opt-in 배정/검증 경계의 최소 구현이 먼저 필요하며, 이번에는 Android 수정·빌드를 하지 않았다. 오래된 CAL03 경로의 DG 성공과 현재 study의 정책 허용을 구분한다.

## 시간 전이 탐색의 고정 범위와 결과

원 생성 규칙의 low/queue50%/burst50%/queue75%, 각각48요청, 새 seed623001/623002를 사용했다. 같은 ticket의 도착·기한을 유지했다. 처음부터 등록한 기존 간섭 가정1.0/1.5를 각각 예측과 실현에 사용했다. 이는 기기에서 측정한 간섭이나 새 감속 코드가 아니다. 원본에 포함된 paired 벡터를 사용하고 탐지 GPU가 유리한 시간만 골라 바꾸지 않았다.

정적 3기준×4입력×2seed×2간섭=48새 PC 계산/2,304요청. 이를 재사용하며 기존 4-cell EFT 참고16계산/768요청을 별도로 추가했다. 총64새 PC 계산/3,072요청이다. 기한 분모는 전체 도착이며 완료 후 지각 성공을 제외하지 않는다. 긴급은 output_ready, 일반은 persist_complete, 점유는 lane_available이다. J/AP 창을 계산한 것이 아니라 시간 지원을 검사하기 위한 0–120초 점유창이다.

다음은 각2seed합계96요청, P95는 **세션별 P95의 평균**이고 pooled96 P95가 아니다.

| 입력·간섭 | 기준 | 기한/도착 | 긴급 P95(ms) | 일반 평균(ms) | 해석 |
|---|---|---:|---:|---:|---|
| low·1.0 | CPU / CC_DG | 96/96 모두 | 159.200 / 159.200 | 622.788 / 1,134.053 | 탐지 GPU가 이 조건의 일반 응답을 줄이지 않음 |
| queue50·1.0 | CG_DC / CC_DG | 96/96 / 80/96 | 884.678 / 450.107 | 1,158.148 / 5,195.340 | 긴급 개선과 일반 기한 실패의 상충 |
| queue50·1.5 | CG_DC / CC_DG | 96/96 / 73/96 | 1,174.920 / 593.166 | 1,356.535 / 5,850.629 | 탐지 GPU의 긴 점유·간섭 가정 영향 |
| queue75·1.0 | CG_DC / CC_DG | 96/96 모두 | 1,175.859 / 589.892 | 787.092 / 1,563.140 | 기한은 지키지만 응답 목적이 상충 |
| queue75·1.5 | CG_DC / CC_DG | 96/96 모두 | 1,175.859 / 698.879 | 1,003.766 / 1,730.085 | 에너지·열 우열은 미계산 |
| burst50·1.0 | CPU / CG_DC / CC_DG | 56/96 / 74/96 / 60/96 | 전체 표 | 전체 표 | 어느 정적 배정도 완전 서비스가 아님 |

4-cell EFT의16사례 중 기한 전충족12, 과거 고정 상태와 호환하는 점유만 쓰는 사례4(low)다. 나머지12는 분류 CPU+GPU 병행을 쓴다. queue75·1.0은 긴급 평균647.907ms/일반948.614ms이나 두seed합계 **4.328186초의 미측정 분류 병행**이 있다. 이 구간을 빼고 나머지 J를 정책 전체 J로 표시하지 않는다. 병행 상태를 모두 같은 CPU+GPU로 합치지 않았다. 정적 기준의 `unmeasured_concurrency_s` 공란은 해당 추가 분해를 수행하지 않았다는 뜻이며 0으로 대입하지 않는다.

## 최소 해결 명세와 종료 기준

현재 강한 EFT 대비 공동 절감 후보를 얻지 못한 [전체 입력 비교](../method_followup_01/README.md)를 그대로 보존한다. **무조건 탐지 GPU를 측정하면 목표가 해결된다고 권고하지 않는다.** 다른 자원 배정의 가능성을 검증할 경우 필요한 공백은 아래다.

| 질문 | 필요한 상태/근거 | 완료 판정 | 여전히 미확인인 범위 |
|---|---|---|---|
| 현재 엔진에서 탐지를 GPU로 보내 CPU 큐를 비우는 것이 서비스에 유효한가 | 같은 runtime/input/resident의 DG 요청 D/A/S/O/P/W/L; 현재 class CPU+DG admission/소유권 | 전체 도착 분모의 일정·응답·lane·실패를 보존하고 현재 DG service 전이 확인 | 새 독립 세션 변동성·임의 도착·모든 기한 보장 |
| 비용식에 DG를 추가할 수 있는가 | 동일 계측의 resident idle→DG→idle 및 CC→CC_DG→CC/idle, lane 점유와 전류/전압/AP | 증가분과 짧은 전환 항의 식별 여부/결측을 판정; 미식별 계수 null; 별도 개발 후 동결 | 1초 센서로 개별 짧은 요청 전력의 정밀 식별 |
| 이 배정이 실제 정책 선택을 바꾸는가 | 동결 후보가 사용하는 상태만으로 이루어진 별도 확인 입력/공통창 | 재보정 없이 같은 창 J/AP·응답 오차 산출; 정책 차이와 세션 변동성을 별도 판독 | 정확도 허용폭·반복 수·전체 시간은 근거 확보 전 미확정 |

사용하지 않는 DC_DG, 분류 CPU+GPU, NPU/스로틀을 함께 채우는 것은 필수가 아니다. 지금의 4-cell EFT를 그대로 채택하려면 분류 CPU+GPU까지 필요하므로 최소 확장 경로가 아니다. 분류 CPU를 유지하고 탐지 CPU/GPU를 제한적으로 선택하는 경로의 필요 자료와 구분한다. 이번에는 그 새 정책·기기 실행기·APK·계획을 만들지 않았다.

실측된 상태의 오래된 평균 W를 현재 모형의 resident 배경에 그대로 더하거나, 기존 W에서 새 idle W를 빼서 미측정 증가분을 만드는 것은 금지한다. 현재 자료만으로 에너지/AP에 유리한 DG 값을 역으로 맞추지 않는다. 같은 AP 숫자가 같은 열 이력이라는 보장도 없다.

## 재현과 검증

공유된 gzip ledger는 원 JSON byte를 그대로 압축한다. 원 uncompressed 파일이 없어도 다음 **재집계**는 가능하다. 새 본 시뮬레이션을 반복하지 않는다.

```powershell
python -m tools.d1_detector_gpu_report
python -m unittest tools.test_d1_detector_gpu_bridge -v
```

기존 원본의 출처를 다시 확인하거나 새 별도 PC 출력 폴더에 본 탐색을 재현할 때만 외부 CAL03 원본이 필요하다:

```powershell
python -m tools.d1_detector_gpu_bridge --output output/dg_timing_new --external '<D1Check_Arrival_Extension>'
python -m tools.d1_detector_gpu_reference --output output/dg_reference_new --parent output/dg_timing_new
```

공유 보고서의 등록 해시 검사는 기존 공유 결과 경로를 기준으로 한다. 새 출력과 기존 등록 파일을 섞지 않는다. callback/소스·모형이 달라지면 기존 결과의 hash를 새 값으로 덮어쓰지 않는다. 최초9검사 중 테스트 fixture의 필드명 `request_id`/실제 `id` 차이로1건 본문 오류가 있었고, 실제 입력 스키마로 고쳐9건 모두 실행·통과했다. gzip 재집계와 현재backend/병행마스크 차단을 추가한 최종12건통과. 본 시뮬레이션/계수 변경은 없다. 상세 명령·시점·대상·Git기준은 `verification.json`을 따른다.

다음 행동 하나: 탐지 GPU를 쓰는 제한 배정이 현재 engine/품질/admission에서 지원되는지와 같은 계측의 DG/CC_DG 항을 확보할 수 있는지 **위 최소 해결 명세만** 구현 범위로 판단한다. 포괄적 자료 재감사·같은B2반복·계수 채우기용 전 조합 측정으로 돌아가지 않는다. 이번에는 기기 명령·빌드·실측·기기 계획·claim 모두0이다.
