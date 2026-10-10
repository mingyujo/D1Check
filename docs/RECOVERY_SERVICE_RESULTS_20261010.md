# 회복 이력과 5phase 처리시간 — 기존 자료 PC 판독

2026-10-10 · RECOVERY-SERVICE-PC-01 · 시작 HEAD `728d7739fa34e2850541a81d1fe32af9e5aa49a5`

**기존 자료에서 고정 처리시간의 국소 오차는 줄일 수 있었지만, 냉각에 따른 속도 회복 함수는 확인하지 못했다.** 시작 AP 후보는 같은 자료의 고정시간 대조보다 악화해 미채택했다. 현재 기본 일정 엔진/RL에는 온도→5phase 연결을 추가하지 않았다. 이는 A24에 스로틀이 없다는 인증도, 추가 실측으로 반드시 회복 효과를 찾는다는 보장도 아니다.

[그림·전량 CSV](results/recovery_service_01/run_v1/index.html) · [결과 열람 전 규칙](results/recovery_service_01/README.md) · [등록](results/recovery_service_01/registration.json) · [후보 동결](results/recovery_service_01/run_v1/development_freeze.json)

## 사용 자료와 시간 경계

- 기존 이력 통제 개발6/이미 본 확인6, 고유 완료 12세션을 재사용했다. 후속 CPU/PAR 부하 세션은 각각4개이며 C0 4개는 준비/AP 대조다. 준비1,152＋후속768＝1,920요청을 전량 추출했다. 부분/실패 시도는 완료 표본에 중복 포함하지 않았으며 기존 FAIL/종료 계획을 수정하지 않았다.
- 기존 등록 해시와 일치하는 요청·준비 요청·history boundary·AP·progress 60파일을 검증하고 원 manifest 12개도 새 해시로 고정했다. APK `3840bfb…8768be`, 두 모델·입력 PNG·전처리/tensor·runtime·1 CPU thread·900ms power sampler·준비 요청열이 12개에서 동일함을 검사했다. 별도 프로토콜인 옛 COLLECT05 3,174요청 결과와 계수를 pooling하지 않았다.
- 준비96요청 이후 runtime 재생성/추가 warmup은0이다. 등록된 회복30/180초 이후 **resident baseline 약30초＋target 첫 부하까지35초**가 더해져 실제 마지막 준비 lane 해제 이후 첫 dispatch는 약95/245초다. “부하 직후 정확히30/180초의 회복 속도”를 잰 것으로 쓰지 않는다.
- 5phase는 기존 모델 그대로 `dispatch→execution_start→output_ready→persist_complete→worker_release→lane_available`다. phase2는 전처리＋실제 invocation＋출력 준비를 포함한다. `host_inference_start→return`과 `execution_start→host_inference_start`를 따로 분석했다. phase 합계는 실제 lane 점유이며 큐 대기/종단간 응답시간과 다르다.
- Android monotonic ns를 동일 원점에서 차분했다. AP는 current HAL numeric AP의 원문 값과 대조하고 조회 전체가 dispatch 이전에 끝난 마지막 표본만 연결했다. 요청/AP 누락0, 최초 부하 전 조회 반환 기준 age0.242–2.269초/괄호 최대0.270초, 회복 AP 중앙 간격2.535–2.580초/최대 공백3.820초다. 조회의 신선도는 센서 내부 갱신시각의 보증이 아니다. host wall clock으로 경계를 이동하지 않았다.
- 입력/역할/분모와 처리시간 추출은 [공유 입력](results/recovery_service_01/run_v1/inputs.json)에 보존했다. 기기 serial/fingerprint는 공유하지 않는다. `summary.json.independent_target_sessions=8`은 고유 부하 세션의 집계 이름이며 통계적 독립성을 인증하지 않는다. 연속 실행의 이전 열 이력·실행 순서는 통제되지 않았다.

## 회복기간 차이에서 확인한 사실

후속 부하 전 AP는28.4–29.0°C다. **개발에서180초 조건은30초보다0.3°C 높았고, 확인에서는0.2–0.5°C 낮았다.** 따라서 등록 회복기간을 실제 냉각량으로 대신 쓸 수 없다. 특히 확인180_C0는 준비 끝→후속 기준 AP가+0.4°C여서 모든 긴 회복이 냉각한 것도 아니다.

아래는 같은 정책/task/backend의 **실제 invocation 평균** 비교다. 각 역할·정책의 회복기간 비교는 세션 쌍1개이고 각 cell에는48요청이 있다. 요청과 ordinal 구간을 독립 실측 반복으로 세지 않는다.

| 정책·작업 | 개발180−30 추론시간 | 확인180−30 추론시간 | 확인 초기 AP 차 |
|---|---:|---:|---:|
| CPU · 분류 CPU | +0.672% | −0.276% | −0.5°C |
| CPU · 탐지 CPU | −0.220% | +0.735% | −0.5°C |
| PAR · 분류 GPU | +1.390% | **+3.275%** | −0.2°C |
| PAR · 탐지 CPU | −0.092% | −0.780% | −0.2°C |

CPU 분류의 온도/처리시간 방향은 두 block에서 맞지만 차이가 작고, 다른 cell은 일관된 보편 회복식을 지지하지 않는다. PAR 분류 GPU는 더 낮은 시작 AP에서도 평균197.708→204.182ms로 느려졌다. 이 결과는 냉각이 GPU를 느리게 한다는 인과 주장도 아니다. 실제 추론 겹침 비율은 같은 비교에서 약−0.025로 달라졌고 이전 이력·시간순서·배경 상태가 남는다.

모든5phase/실제 invocation/응답의 전량 차이는 [recovery_contrasts.csv](results/recovery_service_01/run_v1/recovery_contrasts.csv), 동일 ordinal의 네 구간은 [ordinal_contrasts.csv](results/recovery_service_01/run_v1/ordinal_contrasts.csv)에 있다. AP·경과시간·실제 추론 겹침을 나눈16개의 기술적 연관은 양4/음12였다. AP와 경과시간 상관은0.891–0.952로 높아 가열 중 시간경과를 AP 원인으로 분리하기 어렵다. 이 회귀계수를 예측 함수로 사용하지 않았다.

## 후보 구현과 대조

결과를 읽기 전에 구조 하나를 고정했다. 정책×task/backend별로 개발 두 세션을 같은 가중으로 평균한 고정5phase 대조를 만들고 다음만 더한다.

```text
phase2(T_pre) = 개발평균 phase2 × exp(gain × (T_pre − 개발평균 T_pre))
gain = max(0, 개발 두 AP 값과 log(세션 평균 phase2)의 기울기)
다른 phase = 같은 개발 자료의 고정 평균
```

후보의 초기 AP는 실제 첫 dispatch 이전 표본이다. 미래 AP/전류/완료시간/실제 겹침을 예측 입력으로 주지 않았다. 후보는 target 중 고정 벡터를 반환하므로 **냉각 중 처리속도 회복을 연속 전파하는 모형이 아니다.** 수치 계산 가능성과 동적 회복의 근거를 구분한다.

개발4세션에서4개 cell 기울기를 한 번 추정한 뒤 후보 파일/해시를 저장하고 확인4를 평가했다. gain은 CPU 분류0.019618/°C, CPU 탐지0(비제약 −0.005456), PAR 분류0.062162, PAR 탐지0.015479다. 두 개발점만 있어 기울기의 잔차 자유도0이고 한 회복기간을 제외한 교차개발에서는 식별 불가다. 확인은 이미 열람한 자료의 **사후 전이 평가**이며 새로운 독립 확인이 아니다.

| 확인4세션·8 cell 평균 요청 MAE | 기존 동결 | 같은 개발 고정시간 대조 | 시작 AP 후보 |
|---|---:|---:|---:|
| phase2 | 12.693ms | **9.165ms** | 9.335ms |
| 5phase 합계 | 12.931ms | **10.400ms** | 10.687ms |

고정시간 대조의 lane 점유 MAE 감소는19.6%이고8/8 cell에서 기존 동결보다 작았다. 이는 새 동일 프로토콜 개발자료로 시간 평균을 재보정한 효과이며 냉각/온도 모형의 효과가 아니다. 원동결·현재 기본 timing context/RL은 교체하지 않았다.

AP 후보는 고정 대조 대비5/8 cell에서 악화,1개 개선,2개 동일이었다. 개발 초기 AP 범위 밖 확인 cell은4/8이고 외삽 진단으로 공개했다. 범위 안에서도 PAR의 두 cell은 악화했다. 따라서 “범위 밖만 문제”라고 판정하지 않으며 후보 미채택으로 종료한다. 조건별 최대오차/모든 phase는 [prediction_errors.csv](results/recovery_service_01/run_v1/prediction_errors.csv)에 있다. 최선 cell/seed만 남기거나 다른 구조를 추가 탐색하지 않았다.

개발 AP 범위 안인 확인180의4 cell/2세션만 분리해도 lane MAE는 고정대조9.896→AP후보9.912ms로 악화한다. [전체/범위 안/밖 분해](results/recovery_service_01/run_v1/ap_scope_comparison.csv)는 같은 분모에 세 모형을 대조하며 범위 밖을 지운 전체 성과로 보고하지 않는다. 초기 AP 범위 안이 동적 회복/정책 적용 지원을 의미하지 않는다.

실제 호출 가능한 opt-in 함수는 `tools.d1_recovery_service.predict`다. 개발 AP 범위 밖은 기본 null, `diagnostic_extrapolation=True`일 때만 별도 계산하며 미측정 cell/미식별 gain도 null이다. `application_allowed=false`, `supported=false`, `accuracy_pass=null`이고 기존 simulator/RL에는 연결하지 않았다.

## 기존 자료로 끝낸 것과 남은 조건

**완료:** 기존 회복 이력의 실제5phase·추론/전처리 구분·AP 신선도·겹침·순서 대조, 고정 대조와 AP 후보 구현/동결/사후 전량 평가, 후보 미채택, 재현 API/CSV/4그림. 새 일정 생성·AP/J 재적합·정책 배치·RL 학습은0이다.

**미완료:** A24 냉각→처리속도 회복의 동적 함수, 그 함수가 바꾸는 일정/응답/J/AP의 종단간 검증. 현재 저온 자료만으로 관측되지 않은 고온 감속이나 이력 의존 계수를 만들 수 없다. 기존 COLLECT05의 더 높은 AP 자료에서도 단일 AP 법칙의 방향이 일관되지 않았다는 [기존 판독](results/ap_preparation_memory_01/README.md)을 그대로 재사용했다.

이 기능을 실제 지원하려면 필요한 추가 근거는 **같은 모델·입력·runtime/resident·경합 조건에서 실제 감속이 관측된 상태와 유휴 회복 뒤 동일 요청 탐침의 단계별 처리시간**이다. 시작 AP만이 아니라 준비/부하/유휴 이력과 실제 lane/invocation, numeric AP 조회 괄호를 함께 남겨야 한다. 여러 온도를 무조건 채우거나 같은 B2를 반복할 목적이 아니다. 감속/회복이 관측되지 않으면 그 범위는 고정시간 가정으로 남겨야 하며 없는 회복 이득을 학습시키지 않는다.

반복 수/정확도 허용폭/실행시간은 이번 자료만으로 확정하지 않았다. 기존 APK에 이 탐침이 가능한지와 안전한 범위의 감속 관측 유무가 선행 조건이다. **이번에 새 기기 실행기/계획/claim을 만들지 않았다.** 다음 행동 하나는 위 동일 요청의 감속·회복을 구분할 최소 계측 조건을 정하는 것이다. 기존 AP/J 오차 초기화 작업은 별도이며 이 결과로 해결 또는 실패 처리하지 않는다.

## 검증과 재현

- 새 경계7검사 통과: 5phase/invocation 분리·합계 보존·반환 전 AP/age·겹침 union·개발/확인 분리·동일 세션 가중·외삽 opt-in/누락·음/미식별 gain·ordinal 전체분모.
- 첫 테스트1개는 오래된 표본 age를 검사하면서 더 최근 표본이 있는 fixture를 잘못 사용했다. 최신 반환시각+10초를 기준으로 fixture를 수정해 경계를 그대로 검사했다. 물리 모형/기준 변경이 아니다. 전체 과거 테스트는 반복하지 않았다.
- 실제288 오차행 재계산 최대차0,1,920개의5phase 합계 최대차2.274e−13ms, 확인 미래 AP/처리시간/겹침 변조에도 개발 후보 불변. 원모형 SHA `5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2` 불변.
- 검증 대상은 시작 HEAD＋이번 미커밋 소스 해시이며 등록/receipt/readout verification에 기록했다. PC 통과를 실기기 thermal feedback 검증으로 표현하지 않는다. 기기 명령·ADB·설치·실측·APK 빌드0이다.

```powershell
python -B -m unittest tools.test_d1_recovery_service -v
python -B -m tools.d1_recovery_service_report --output docs/results/recovery_service_01/run_v1
```

수치 재분석은 [README](results/recovery_service_01/README.md)의 별도 출력 경로 명령을 따른다. `registration.json`에 고정된 소스/숫자 입력에서만 계산하며 기존 출력이 완료됐으면 덮어쓰지 않는다. 원본/모형/FAIL/소비 계획·기본/RL/strict/experiment_ready=false·사용자 STATUS14행·다른 worktree를 보존했다.
