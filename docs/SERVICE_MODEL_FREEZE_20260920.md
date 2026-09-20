# SERVICE-MODEL-FREEZE — SIM-01_INCOMPLETE

2026-09-20, 시작 `c507f40`, `feature/pre-simulation-ready-20260919`. 이번 작업은 기존 31 session(29 profile/233요청 + raw 진단2)의 재분석이다. 새 실기기 실행·본 scheduling simulation·formal 실험은 없다. 이전 보고서와 artifact를 보존한다.

상세 보고서와 모든 수치/명령/해시: `C:/Users/LG/Documents/D1Check_Decode_Resolution/service_model_freeze_20260920T100651Z/FINAL_REPORT.md`. 최종 bundle은 같은 디렉터리의 `service_model_v1/`이다. `model_bundle*` 디렉터리들은 구현 중 생성물을 보존한 것이며 최종 계약으로 사용하지 않는다.

## 모델과 독립성

- 전체 평균, task/backend 평균, 초기 상태 분리, 전환 포함, co-run 상태 포함, session block empirical resampling의 6개 후보를 비교했다. 임시 선택은 `initial_state_mean`: cell별 cold 첫 호출 / 초기 직후 / warm 분리. 최종 승인 모델은 **없다**.
- calibration 24 session/206요청을 session 전체 제외 교차검증(LOSO)한다. 기존 holdout 4 session/20요청, 사후 진단1 session/7요청은 별도다. 29 session 모두 이미 결과를 확인했으므로 새 독립 holdout으로 재명명하지 않는다. seed `20260920`은 fold 순서를 정하며 과거 목적 분할을 유지한다. 정확한 UUID는 `split.json`에 있다.
- acceptance v1은 calibration 내 동일 상태의 session 간 mean/median/P95 차이 Q95의 2배: WAPE/분포 상대오차 ≤43.1914%, MAE ≤432.808616ms. nominal 90% empirical interval 포함률 ≥90%, 지원율100%, 상태별 calibration session≥2, cell별 새 holdout session≥2·warm 관측≥20. 전체와 cell/priority/state/pair 각각을 확인하며 누락 상태를 통과시키지 않는다.
- 이 값은 측정 변동성 기반의 **넓은 engineering 기준**이다. 실제 연구에 충분한 예측 정밀도·deadline 판별력을 보장하지 않는다. 기존 holdout 결과를 본 뒤 수치를 완화하지 않았으며, 향후 아직 수집하지 않은 session에만 사전 기준으로 쓸 수 있다. 이미 확인한 과거 holdout을 사전 동결 검증으로 소급 주장하지 않는다.
- 임시 후보 calibration LOSO: MAE54.59ms/WAPE7.61%/포함률82.52%. 포함률 기준 실패. 과거 holdout MAE29.67ms/WAPE3.71%/포함률90%는 소급 진단일 뿐이다. 전환/co-run 후보는 각각4/24요청의 상태를 LOSO에서 예측할 독립 반복이 없다. 복잡한 모델의 낮은 오차만 보고 선택하지 않는다.
- 선택 후보는 전환을 cold에 합친다. 그 결과 classification GPU→CPU의 LOSO 상대오차598.69%, 전환4행의 coverage0이다. 전체 WAPE가 작아도 이 후보를 실제 전환에 사용할 수 있다는 뜻은 아니다. 과거 holdout에도 초기 직후 두 상태의 interval miss와 분류 cold 분포 P95 차이71.76%가 있다(실측 cold1건이라 P95 안정성 없음).
- 단순 cold boolean은 부족하다. 기존 74.57% 오차는 첫 **non-cold(두 번째)** 분류 CPU 요청381.316923ms에서 발생했다. cold 첫 호출774.244ms와 혼동하지 않는다. 추가 warmup 진단에서 초기 직후195.28ms가 관측되어 상태 분리로도 변동성이 남는다. 원시값을 제거하지 않는다. JIT/GC 인과는 미확인이다.
- calibration의 두 번째 호출 간격에서 4.154692ms~26.078520001s 공백을 발견했다. 기하중간값329.162905ms를 후보 구분점으로 삼았으며 공백 구간의 동작은 검증하지 않았다. 시간 간격은 요청 실행 전 이력만 사용하고 현재 요청 latency를 feature로 쓰지 않는다.

## 지원·품질·공통 제약

| Cell | Backend/decoded 동등성 | 기존 solo warm 평균 |
| --- | --- | ---: |
| classification CPU | PASS_EQ / actual CPU | 94.90ms |
| classification GPU | PASS_EQ / full GPU | 235.33ms |
| detection CPU | PASS_EQ / actual CPU | 554.97ms |
| detection GPU | PASS_EQ / full GPU | 1,068.72ms |

- A24는 **관측한 solo에서 CPU 우세**다. 모든 조건에서 GPU가 지배당한다는 결론은 아니다. GPU normal + CPU urgent co-run의 CPU service는 matched solo보다2.18% 느렸다. 반대 배치의 GPU urgent service는9.51% 낮았으나 긴급 작업은 GPU에서 실행됐다. CPU-only 직렬 대조가 없어 CPU urgent 개선·전체 완료율 개선을 입증할 수 없다.
- CPU→GPU/GPU→CPU prepare는 분류517.66/24.63ms, 탐지1,135.42/504.23ms, 각각 한 관측이다. service에 이미 포함되어 이중 가산하지 않는다. task 전환·동일 backend contention은 별도 근거가 없고 일반화하지 않는다.
- 준비 계약은 fallback 금지, thermal status0만, 최대 in-flight1, 실행 승인 co-run 빈 목록이다. 관측된 두 cross-backend pair를 증거로 남기되 독립 검증 전 병행 실행 승인으로 바꾸지 않는다.
- sampled peak PSS314,184kB(500ms 표본)를 실제 최대 메모리로 부르지 않는다. calibration 기반 guard 후보340,066kB/headroom25,882kB는 독립 측정·가용 메모리 admission 검증 전 수용 limit가 아니다. 온도를 에너지로 해석하지 않는다.
- raw numerical, decoded, 실제 task accuracy, scheduling quality preservation을 구분한다. 20장 동등성은 ground truth가 아니다. 부분 GT15/28은 mAP가 아니며 classification 실제 정확도는 미검증이다. simulation에 정확도를 만들어 넣지 않고 같은 모델/입력/전처리/decoder 및 허용오차를 통과한 cell만 사용한다. 정확도 미확인 자체를 임의 수치로 보충하지 않는다.
- deadline은 `calibration_pending`, 값은 null이다. task/priority/state별 calibration service와 response의 Q50/Q95를 후보 grid로 제안한다. 동일 도착의 CPU 직렬·가능한 혼합 실행 대조에서 성공/미스가 모두 나타나는 구간인지 검증하고 공통 평가 목표를 사전 고정해야 숫자를 동결할 수 있다. 모든 긴급 요청이 쉽게 성공하도록 deadline을 늘리지 않는다.
- terminal states는 succeeded/failed/rejected/expired/cancelled/unfinished다. 전체 도착 분모와 완료 응답 P95를 함께 보존한다. FIFO CPU-only / feasible fixed GPU / static mapping / EDF / proposed interface 모두 같은 입력 hash에 결합한다. 이는 준비 인터페이스이며 새 정책 실행 또는 개정4.4 B0~B3 의미 재정의가 아니다.

## 산출물과 검증 방법

`tools/d1_service_model.py`와 `tools/d1_service_model_generate.py`는 분석·검증·no-op만 지원한다. JSON schema는 `tools/schemas/service-model-preparation-v1.schema.json`. frozen artifact 또는 READY를 발행하는 경로는 없다. 관측 자료 전체·split·6후보·사전 기준·선택 근거·오차/분위수/포함률·공통 입력·baseline 결합·source hash closure를 외부 bundle에 둔다.

```powershell
python -m tools.d1_service_model analyze --source C:/Users/LG/Documents/D1Check_Decode_Resolution/resume_20260920T090545Z --output <새 외부 디렉터리> --seed 20260920
python -m tools.d1_service_model validate --output <생성 디렉터리>
python -m tools.d1_service_model no-op --output <생성 디렉터리>
python -m unittest tools.test_d1_service_model tools.test_d1_service_profile tools.test_d1_sim_prepare
```

같은 source·seed에서 candidate model/input hash는 동일하다. 생성 시각·외부 경로는 provenance의 실행 기록이므로 별도다. 재사용 UUID/요청/측정 fingerprint, 이미 본 holdout, 오래된 시각, 모델/기준 변경, source/artifact hash 변경, baseline 입력 drift를 거부한다. 예측하지 못한 상태를 다른 cell로 채우지 않는다. no-op은 dispatch0/가상완료0/정책비교null이다.

코드 checkpoint `a4460ea`, receipt 누락 보강 `80a1adf`. 최종 targeted47건(새37+관련10), 전체 Python295건(293 PASS/기존 skip2), compileall·schema·validator·no-op·동일 실자료 재생성 결정론 PASS. source closure981파일, 이전278파일 audit·Android/APK 불변 확인. JVM/build/lint/logger/isolation을 다시 실행하지 않았다. 준비 input SHA `3840b437d8b2b8c704187b52f43f93e8c5c18aeade0a056ce743fad344bfdec6`, 후보 model SHA `300be49c35a191018ddb09479ba7c389ae6aeea3fcf39f3026b93dd16ba78f34`이며 frozen 승인 해시가 아니다.

## 최소 다음 측정

한 번에 전체 실험을 재실행하지 않는다. 아래 수는 **통과 보장 수가 아니라 부족한 독립 반복을 확보하는 최소 설계**다. 모델이 실패하면 기존 holdout을 calibration으로 전환한 새 버전에서 원인을 해결하고 또 다른 untouched holdout이 필요하다.

1. 먼저 calibration 보강: 두 task의 CPU→GPU→CPU 전환 각1 session, 두 co-run pair 각1 session(합계4). 기존 각1에 독립 반복을 더한다. 동일 backend 병행은 계속 금지하므로 당장 측정하지 않는다. 기존233요청과 이미 본 holdout은 개발 증거로 유지한다.
2. 이 보강만으로 모델/간격 범위/예측구간·acceptance/입력/recipe를 v2로 잠근 **다음** untouched holdout을 수집한다. 네 solo cell 각2 session(8), 두 task 전환 각2(4), 두 co-run pair 각2(4): 합계16. solo는 각 첫 호출+직후 호출+warm≥20, 기존20 verified image·두 priority를 포함하고 요청 수≤48/실행120s를 유지한다. 간격의 미측정 범위로 일반화하지 않으며 지원하려면 보강 calibration에 해당 간격이 필요하다. 같은 backend/model의 전환 직후 followup 자료도 보강 recipe에 포함한다.
3. GPU의 요청 수준 이익과 deadline 구간 확인을 위해 같은 arrival/image/priority의 CPU-only 직렬 control 최소2 session을 별도로 확보한다. 위 paired co-run과 대응시키고 실행 순서를 사전 고정한다. CPU urgent/GPU normal 대조만으로 GPU urgent 이익을 주장하지 않는다. 이들도 bounded profile이며 formal 정책 비교가 아니다. 전 과정에서 PSS 시계열·thermal0·실제 가용 메모리/admission 정보를 회수한다. 가용 메모리 관측이 현 probe에 없다면 그 최소 관측만 추가하고 관련 검증을 수행한다.

즉, 전체 전환/co-run 범위를 유지할 때 현재 계획상 최소22개 추가 bounded session(4 calibration +16 새 holdout +2 serial control)이 필요하다. solo만 제한적으로 검증하는 다음 단계는8개 untouched session이지만 그것만으로 전체 SIM-01_READY가 되지는 않는다. cold/transition P95는 이 최소 반복으로 통계적으로 안정됐다고 주장하지 않으며 필요 시 더 많은 사전 고정 반복을 요구한다. deadline/control·간격·메모리·포함률이 미완이면 INCOMPLETE를 유지한다.
