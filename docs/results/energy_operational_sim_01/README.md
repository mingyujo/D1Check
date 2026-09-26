# ENERGY-OPERATIONAL-PAIR-01 PC 연결 재현

원래 수집 HEAD `cf7aa263b96ac06f5b7f4a4eb3d5afbe6629d1ff`의 A24 4세션만 사용한다. 공유 파일은 [동결 PC profile](frozen_profile.json), [동결 평가 명세](evaluation_spec.json), [확인 오차](confirmation_evaluation.json), [raw 재생 결과](raw_replay.json), [비교 CSV](comparison.csv), [그림](tradeoff.png)이다. 한국어 해석은 [연결 보고서](../../ENERGY_OPERATIONAL_SIM_CONNECTION_20260926.md)에 있다. 원시 로그·APK·모델·키는 Git에 없다.

원본 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_run_v1`, 계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_plan_v3/collection_plan.json`이 같은 PC에 필요하다. 이 Windows 경로는 팀원이 GitHub에서 바로 열 수 있는 링크가 아니다. 계획 SHA-256은 `4d0bd250029f8fb46c7f989775f63cf75714c4e681522a6c056e58ef0f900ed5`, 원 개발 동결 SHA-256은 `1dc5766aef4299300acf87fa6d92db0ec54830155d6d8fb02170a901a9f28881`. 별도 PC profile SHA-256은 `b58c2ca3852cfb4959c65f4dd47c0547454260d6045a0cd87f51487ac1b10772`, 평가 명세 SHA-256은 `383a50c50b4a38e10863d4d1072277790e48385b72284534bd24da48f2f0d763`. profile은 개발 파일 2개만 읽으며 평가 명세를 먼저 저장한다. 이번 연결의 모형 구조는 확인 결과 요약을 본 뒤 작성됐다는 한계가 남는다.

저장소 루트에서 PC 전용으로 실행한다. `freeze`→`evaluate` 순서를 지키고, `--output`은 **새 경로**로 지정한다. `replay`는 원시 자료와 기존 validator의 일치 검사이고 예측 검증이 아니다. `report`의 그림 생성에 matplotlib가 필요하다.

```powershell
$plan = 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_plan_v3/collection_plan.json'
$run = 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_run_v1'
$out = 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_sim_reproduce_new'
python -m unittest tools.test_d1_energy_operational_sim -v
python -m tools.d1_energy_operational_sim freeze --plan $plan --run $run --output "$out/frozen"
python -m tools.d1_energy_operational_sim replay --plan $plan --run $run --output "$out/raw_replay.json"
python -m tools.d1_energy_operational_sim evaluate --plan $plan --run $run --profile "$out/frozen/frozen_profile.json" --spec "$out/frozen/evaluation_spec.json" --output "$out/confirmation_evaluation.json"
python -m tools.d1_energy_operational_report --plan $plan --run $run --evaluation "$out/confirmation_evaluation.json" --output "$out/summary"
```

이번 검증(2026-09-26 KST, 출발 HEAD 위 값과 새 코드 미커밋 상태): PC unit 6건 통과, 4/4 raw 세션의 기존 phase/metric 재생 일치, 개발 전용 profile·명세 동결 후 확인 2세션 오차 산출, 그림 수동 확인. Android 기기 명령·새 추론 0. 숫자에 대한 PASS 기준 없음. `experiment_ready=false` 유지.
