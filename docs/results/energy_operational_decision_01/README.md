# 고정 CC_DG 의사결정 탐색의 작은 산출물

[한국어 보고서](../../ENERGY_OPERATIONAL_DECISION_PC_20260926.md), [단계별 오차 분해 CSV](energy_error_decomposition.csv)·[JSON](energy_error_decomposition.json), [제약 미설정 예시 입력](query_no_service_limits.json)·[출력](decision_no_service_limits.json). 원본 APK·모델·원시 로그·키는 포함하지 않는다. 원본 4세션과 동결 설정의 경계는 [이전 연결 README](../energy_operational_sim_01/README.md)를 따른다.

PC 전용 입력 profile SHA-256 `b58c2ca3852cfb4959c65f4dd47c0547454260d6045a0cd87f51487ac1b10772`, 확인 평가 JSON SHA-256 `1984b97a9ab5b83808dc14ff3e0b6868f1e02d8741fe153d602f8e6579ec41a9`. 예시 초기 AP `29.1°C`는 이미 관측된 확인 세션 값이다. `null`인 서비스 기한·AP 한도는 **미정**을 뜻한다. 테스트의 가상 한도는 서비스 요구가 아니다.

저장소 루트에서 실행한다. `decompose`에는 같은 PC의 외부 저장 원본 경로가 필요하다. `decide`는 Git의 작은 동결 profile/평가 파일만으로 실행된다. 아래 `$out`은 없는 새 출력 경로로 지정한다. 기존 실행 계획·소비 registry는 건드리지 않는다.

```powershell
$profile = 'docs/results/energy_operational_sim_01/frozen_profile.json'
$evaluation = 'docs/results/energy_operational_sim_01/confirmation_evaluation.json'
$query = 'docs/results/energy_operational_decision_01/query_no_service_limits.json'
$plan = 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_plan_v3/collection_plan.json'
$run = 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_run_v1'
$out = 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_decision_reproduce_new'
python -m unittest tools.test_d1_energy_operational_decision -v
python -m tools.d1_energy_operational_decision decompose --profile $profile --evaluation $evaluation --plan $plan --run $run --output "$out/energy_error_decomposition.json" --csv "$out/energy_error_decomposition.csv"
python -m tools.d1_energy_operational_decision decide --profile $profile --evaluation $evaluation --query $query --output "$out/decision_no_service_limits.json"
```

새 서비스 한도를 검토하려면 예시 query를 **복사한 뒤** `max_work_completion_s`, `max_load_ap_peak_c`를 해당 실제 요구에 맞춰 기입한다. 두 확인 arm에 공통으로 기록된 초기 AP 29.1°C만 허용하며 새 온라인 상황의 자동 선택은 아니다. 부하 시작 기준 완료·AP 센서·공통480초 조건부 J 이외의 지표는 지원하지 않는다. 단일 확인오차 민감도는 통계적 보장이 아니다.

2026-09-26 KST PC 검증 대상: 출발 HEAD `3106425755107a0a4781522cc5255574750d3642` + 새 코드 미커밋 변경. 새 unit 4건 통과, 저장된 확인 2세션에서 분해 항등식·40.774J 차이 대조 통과, 제약·범위 상태 분기 확인. 원본 실측·전체 배치·ADB·추론 재실행 0. 실기기 검증/PASS 없음.
