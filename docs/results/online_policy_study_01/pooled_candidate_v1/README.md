# 배경 전력 후보: 미채택

## 2026-10-03 최소 배경 전력 후보 판독 완료

기존 적격13세션(개발3·이미 본 확인6·계측대조4)으로 사전등록한 pooled resident 후보 하나를 평가했다. 새 독립 확인이 아니다. AP·처리시간 항과 기존 동결본은 변경하지 않았다. 5초 창·정책별 동일 가중·세션 전체 제외 평가를 사용했으며 모든 식별 행렬은 rank5였다.

- 120초 에너지 평균 절대차: 기존7.117586J → 후보 세션제외5.307220J.
- 최대 절대차: 기존17.871248J → 후보19.447192J. 사전 조건인 최대오차 비악화를 위반했으므로 **미채택·추가 확인 실측으로 진행하지 않음**이다. 기준을 결과에 맞춰 바꾸지 않는다.
- 가장 큰 후보 오차는 기존 개발 병행 세션이다. 관측150.175774J 대비 후보169.622966J이며 기존식150.426768J였다. 이 세션을 제거하거나 잘못된 자료로 단정하지 않는다. 세션 간 배경·계측 프로토콜·이력 차이를 일정한 배경항 하나로 설명할 수 있다는 근거가 부족하다. 행렬 rank는 물리 계수의 안정성이나 원인 식별을 뜻하지 않는다.
- 후보의 전체자료 적합 resident는1.116311837W다. 이 값은 주변조건과 무관한 물리 유휴 전력으로 인증된 것이 아니다. 후보JSON의 확인 pending 범위 표시는 가능 범위 메타데이터이며 실제 실행 결정은 summary의 advance=false가 우선한다.

**지금 사용 가능한 범위:** 기존 등록96요청·세 정책의 일정/응답 예측과 조건부 AP 경로 및 관측 정책 비교는 재현 가능하다. 작은 에너지 차이나 AP 최고값 차이의 우열은 미판정이다. 후보 실패를 열 모형 전체 부재나 원래 목표 불가능으로 확대하지 않는다. 기존 strict/default/experiment_ready=false 유지.

**다음 작업 하나:** 고정된24분류/72탐지 혼합에서 각 상태 점유의 식별 기여를 산출하여, 동일 세션 단순 반복 대신 CPU 분류·GPU 분류·실제 병행을 구분할 최소 입력의 필요 여부를 결정한다. 추가 모형 가족 탐색이나 이 후보의 즉시 재확인은 하지 않는다.

재현(외부 원본 필요, 출력은 새 경로):
```powershell
python -B -m tools.d1_pooled_energy_candidate --archive C:/Users/LG/Documents/D1Check_Arrival_Extension --output output/pooled_candidate_fresh
python -B -m tools.d1_pooled_energy_candidate --archive C:/Users/LG/Documents/D1Check_Arrival_Extension --output output/pooled_candidate_fresh --render-existing --share output/pooled_candidate_share
python -B -m unittest tools.test_d1_pooled_energy_candidate tools.test_d1_online_policy_study -q
```

외부 의존: online_policy_study_run_v4의 model_freeze/development_cases/confirmation_cases, online_power_sampling_plan_v2 및 해시 결속된 첫2·후속2 세션의 validated/thermal/artifacts. 원본 경로·해시 상세는 외부 pooled_energy_candidate_pc_v1/source_inventory.json에 보존한다. 개발·확인 모두 이미 본 자료라는 사실을 CSV에 기록했다. 세션제외 평가는 새로운 독립 확인이 아니다.

검증: 후보2+기존 경계8=10건 통과(실제9.486초), 분석13세션/39행, 동결557fbe 불변, 기존 AP/처리시간 항 불변. 본 PC 후보 단계 기기 명령·추론·APK·새 계획·claim0. 직전 실측의520추론/4144명령은 삭제하거나0으로 바꾸지 않는다.
