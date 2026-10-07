# 공개 규칙의 열·에너지 비교 — Triton 요청 단위 적용

2026-10-07 · EXTERNAL-RULES-12 · 완료 · 기기 실행/추가 학습0

**이번 Triton 5설정은 기한·전량을 유지하면서 J와 AP 부담을 함께 줄이는 개선을 보이지 않았다.** 동시2건 허용은 같은 하위 배정의 제한 해제와 전48조건 일정이 같았다. 동시1건 제한은 큐/버스트에서 온도 최고값을 낮추기도 했지만 J가 증가했고 기한을 만족하지 못했다. 지속 부하에서는 미완료까지 발생했다. 이 결과는 Triton 제품 전체의 성능 판정이 아니다.

[오프라인 비교 화면](index.html) · [사전 대응표](mapping.md) · [고정 출처](sources.json) · [전체 원형 CSV](results.csv) · [요약 CSV](policy_summary.csv) · [같은 조건 차이](paired_differences.csv) · [대표 판단 차이](representative_differences.csv)

## 실제로 가져온 규칙

NVIDIA Triton core commit `3af839d613da6995051f9bcfab00efe2eac87d4c`의 `src/rate_limiter.cc/.h`를 확인했다. [원 코드](https://github.com/triton-inference-server/core/blob/3af839d613da6995051f9bcfab00efe2eac87d4c/src/rate_limiter.cc) · [공식 설명](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/rate_limiter.html).

- 모델별 specific FIFO 요청 큐와 인스턴스 가용 상태를 사용한다. 완료 실행 횟수 × max(priority,1)이 작은 staged 인스턴스가 앞선다. 원 기본 priority1이며0도1로 취급한다.
- 요청 제출 → stage → 즉시 자원 확보를 시도한다. 대기 전체를 모아 새 목적함수를 최적화하지 않는다. 자원이 없으면 heap top을 유지한다.
- Release에서 횟수를 증가하고 자원을 반환한다. 해당 모델의 다음 요청을 먼저 restage하고 최종 allocation attempt를 수행하는 순서를 보존한다.
- 원 규칙은 AP/에너지·실행 비용 예측을 직접 사용하지 않는다. 이번은 그 일정의 열·에너지 효과를 기존 공통 모형으로 평가한다.

whole-request 적용은 **B·제한적 재현**이다. 분류GPU·탐지CPU 각1개 인스턴스, batching/cache/취소 비활성, 원 서버 종료 대신5단계 후 실제lane 반환을 인스턴스Release에 대응했다. 동시 사건은 기존 엔진의 CPU release→GPU release→도착ordinal 순서다. 원 서버의 비동기 실행·IPC·일반 여러 인스턴스 heap 동점을 재현했다고 주장하지 않는다. 최대2개 staged 인스턴스의 동점은 먼저stage된 항목이다. 동작·입력·생략·출처byte SHA는 mapping/sources/contract에 결과 전에 고정했다. 코드 귀속과 BSD-3-Clause 조건은 [NOTICE](NOTICE.md), [LICENSE](TRITON_LICENSE.txt)를 따른다.

## 비교 입력과 설정

- 이전 external_rules_01의 seed610810001..004·low/queue/burst/sustained·mean/short_context/long_context, 총48조건을 그대로 재사용했다. 세 문맥은 개발5단계 전체 벡터의 평균/짧은/긴 문맥이며 독립 기기 표본이 아니다. 이미 결과를 본 자료이므로 새로운 독립 확인시험도 아니다.
- Triton 제한 해제1개 + 동시1/2건 × 동일priority/분류우대priority의4개, 신규240환경·15,840예정 요청. 분류우대는분류1·탐지2의 실험 설정이고 엄격 긴급 우선이나 원 기본값이 아니다. capacity1/2는 공통token의 명시적 설정이며 실측 메모리량/전력 한도라고 부르지 않는다.
- 기존 CPU/SPLIT/EFT/SHARED_EDF/SHARED_EFT/자체2규칙/Band의384완료 행·25,344논리 요청을 소스/입력/모형SHA와 원 ledger 대조 후 재사용했다. 최종624행·13정책/설정·41,184논리 예정 요청이다.
- rate-off와의 비교는 하위 배정 고정으로 limiter 효과를 분리한다. 다른 정책과의 전체 결과 비교에는 큐 순서·대기·CPU/GPU 배정 차이가 함께 포함되므로 limiter 하나의 인과효과라고 부르지 않는다.
- 긴급 output_ready1.5초/일반 persist_complete6초, lane는 이후lane_available에서 재사용한다. J0..120초·AP35..180초·시작 상태·실현 벡터seed201 동일. 모든 요청을 보존하고 만료/drop으로 이득을 만들지 않는다.
- A24 분류CPU/GPU·탐지CPU와 검증된 classification_GPU+detection_CPU만 지원한다. S26/NPU/탐지GPU 계수를 섞지 않았다. 기본/strict/experiment_ready=false 유지.

## 주요 수치

아래는 지속12조건의 평균이다. P95는 조건별P95의 평균이며 전체 요청 pooling P95가 아니다. 완료·기한은 전체 예정 요청 분모다.

| 규칙 | 전량·전기한 조건 /12 | 완료 /2,304 | 기한 충족률 | 긴급P95 평균 ms | J120 평균 | AP최고 평균 °C |
|---|---:|---:|---:|---:|---:|---:|
| Triton 제한 해제 |12|2,304|100%|294.055|184.825489|32.502813|
| Triton 2건·동일 또는 분류우대 |12|2,304|100%|294.055|184.825489|32.502813|
| Triton 1건·동일 |0|2,193|31.0764%|11,486.491|187.355767 **부분작업**|계산 불가|
| Triton 1건·분류우대 |0|2,219|64.1493%|883.471|187.043551 **부분작업**|계산 불가|
| 강한 예상 응답 우선 |12|2,304|100%|294.055|183.394217|32.417201|
| Band 요청 적용 |12|2,304|100%|294.055|183.262545|32.395441|
| 우리 에너지·AP 규칙 |0|2,304|95.0087%|1,948.794|182.507506|32.444316|
| 우리 큐 에너지·AP 규칙 |0|2,304|97.5260%|1,720.781|182.906747|32.361148|

- 저부하12조건: Triton5설정은 일정·서비스·J/AP 모두 동일, 전량·전기한. 큐/버스트에서는 제한 해제도 이미 전기한 미충족이다. 조건 지도에서 자기 대조군이 빨간색인 것은 서비스 요구 미충족을 나타내며 자신보다 악화했다는 뜻이 아니다.
- 동시2건 두설정은 각각48조건 모두 제한 해제와 요청별일정이 동일했다(합96대조). 이 환경에는 이미 모델당1개 인스턴스가 있고2token이 병행을 추가로 제한하지 않는다.
- 동시1건은 큐/버스트에서 J평균 각각+0.545032J. 동일 배분의 AP최고는 각각−0.065343/−0.060411°C지만 기한미충족과 에너지증가를 동반한다. 분류우대도 같은 J증가와 작은AP감소의상충이다. 안전 한도 초과 시간은 모형미지원으로null이다.
- 지속에서는 동일배분이+2.530277J, 분류우대+2.218061J이고 미완료111/85건이다. 전체 작업을 처리한 온도최고/AP180은 계산불가로 남긴다.35..120부분경로가 낮아도 완전작업열감축이라고 부르지 않는다.
- 우리규칙은 Triton고정병행보다 J가 낮지만 지속기한을 지키지 못한다. 우리큐규칙의AP도낮지만 서비스손실이있다. 강한EFT/Band 적용은 기한을 지키면서 이 Triton고정인스턴스 조건보다J/AP가낮다. 이를 실제제품 우열로 확대하지 않는다.
- J/AP면적/최고값의동시비악화+하나이상엄격감소를 기한·전량충족과함께 요구한 적격공동개선은 Triton5설정 모두0. 결과후 설정조정/선택0.

## 판단 차이가 생기는 위치

대표는 최소seed/mean의queue와sustained로 사전에 정했고 결과후 교체하지 않았다. [전체대표ledger·AP](representatives.json)와 대표차이CSV를 보존했다.

Triton의 차이는 주로 resource token 대기와 모델 간 실행기회 배분이다. CPU/GPU는 고정했으므로 이 비교 안의 비용 변화는 장치 선택의 결과가 아니다. 동일배분의 완료횟수 우선이 짧은긴급분류의 기한을 직접 지키지는 못한다. 분류우대는 지속긴급P95를 낮추지만 일반요청평균은6,090.058→9,031.173ms로 증가했다. 가중치가 서비스목표를 자동충족하지않는다.

동결모형에서 분류GPU·탐지CPU의 단독추가전력은각0.472884/0.712926W, 병행추가전력은0.887812W다. 단독합은병행보다0.297998W 크므로, 동일 실행시간/관측창에서 겹침을없애면 J가증가하는경향이있다. 이는개발모형의수치관계이며하드웨어인과확정이아니다. 독립 선점/전송/스케줄러 소비전력과 실제주파수반응은없다.

## StarPU 보류와 근거 경계

StarPU 공식mirror `356c8e443d75dfec0eb9d00a95b92d6b3fb1b486`의 DMDA를검토했다. 원점수는예상끝시각·데이터전송·taskenergy 및일부idle연장비용이고기본alpha/beta1·gamma1000µs/J·idlepower0이다. [원코드](https://github.com/starpu-runtime/starpu/blob/356c8e443d75dfec0eb9d00a95b92d6b3fb1b486/src/sched_policies/deque_modeling_policy_data_aware.c).

현재 모형은 상태별 기기 전체 추가전력이다. 병행값은 단독합과 다르며 원 task energy에 그대로 귀속시킬 수 없다. 별도 전송·데이터 상주·prefetch의 측정과 모형도 없다. 독립 worker별 큐가 선택할 수 있는 모든 동시 조합은 현재 엔진의 지원 범위와 맞지 않는다. 이를 해결하려고 미측정 비용0·임의 에너지 분배·새 자체 ranking을 붙이지 않았다. **이번은 C·성능 보류이며 공개 알고리즘 부재·영구 재현 불가능·StarPU 실패를 뜻하지 않는다.** 가정 입력을 사전 정의한 탐색 B는 별도 설계가 필요하다.

J/AP 계수는 기존 A24 개발 실측을 기반으로 하지만 새 trace 결과는 PC 모형 탐색이다. 개발 energy fit RMSE0.928991J는 독립 정책 차이의 오차 상한이나 보장 구간이 아니다. 작은 차이는 모형 오차보다 확실한 기기 개선으로 주장하지 않는다. 제어 overhead의 차등0은 기존 가정이며 PC callback 시간만 측정했다. 사용자 활동/BAT 합성 입력은 이번 Triton에서 사용하지 않는다.

## 검증·실행량·재현

- 원조건8사례·엔진3사례·집계3사례·공유재현I/O2사례, 총16관련검증. 엔진fixture6환경20예정요청, 본비교240환경15,840예정요청. **이번실제246환경/15,860예정요청**, 학습/기기0. 환경400상한이하. 최초5pilot은240행에포함하며재계산0, 실패본실행0.
- 새240행의모든J/AP 재계산차이0. 재사용384ledger와최종41,184논리요청의분모·단계·동일lane중복·실제해제·온라인도착시점검사통과. 원19파일·사용자9파일SHA유지. [감사](integrity_verification.json), [테스트](tests_verification.json).
- 화면필터624전체/156부하/12단일정책·13/52요약그룹·미완료部分J/AP계산불가·차이기준교체통과. 그림6개PNG/SVG와공유CSV/대표기록으로재생성한PNG일치를검사했다. [화면검증](dashboard_verification.json), [공유재현](shared_reproduction_verification.json).
- 본배치UTC14:06~14:07에완료. 보수적UTC13:45기산3시간상한·마지막20분예약을유지했다. 전체조사/구현작업과순수배치시간을혼동하지않는다.완료receipt에원시실행ledger와SHA를남겼다.

저장소루트에서관련시험:

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -m unittest tools.test_d1_triton_rules tools.test_d1_triton_report -v
```

공유자료만으로그림/화면재생성(환경0):

```powershell
python -B -m tools.d1_triton_report --shared --output output/external_rules_20261007_figures
```

새별도폴더에240환경재현(명시적으로실행할때새장부생성,원캠페인예산/결과불변):

```powershell
python -B -m tools.d1_triton_reproduce --folder output/external_rules_20261007_reproduction
```

동일재현폴더재호출은저장된240조건을재사용한다.코드/계약drift는거부한다.원날짜/원예산을새대화로초기화하는명령이아니다.재현폴더의new_results.csv를이번results.csv의origin=new_triton과대조하되PCcallback실행시간열은host환경에따라달라진다.원학습·기기명령은포함하지않는다.

PPT그림: [판단차이](01_판단규칙차이.png), [같은요청시간표](02_같은요청시간표.png), [응답·완료](03_응답과완료.png), [에너지·온도](04_에너지와온도.png), [온도경로](05_같은시작온도경로.png), [전체조건지도](06_전체조건지도.png). 코드명과값의원형은CSV에보존했다.
