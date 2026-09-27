# A24 고정 CC_DG 모형 연결 v2

[대시보드](dashboard.html) · [시간축 그림 SVG](confirmation_paths.svg) / [PNG](confirmation_paths.png) · [확인 오차 CSV](confirmation_errors.csv) · [시간축 CSV](confirmation_paths.csv) · [개발 상태 전력 JSON](development_state_power.json) · [지원/계보 JSON](support.json). 한국어 판독은 [보고서](../../ENERGY_AP_MODEL_BRIDGE_PC_20260927.md)다. 그림·표 수치는 코드에서 생성했으며 수작업 입력하지 않았다.

저장소 루트에서, 이 PC에 외부 원본이 있는 경우만 재현한다. 다른 컴퓨터에는 원본 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_run_v1`과 계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_plan_v3/collection_plan.json`이 없으므로 Git 공유 파일만 열 수 있고 원본 재계산은 불가능하다. 원본을 가짜 입력으로 대체하지 않는다. 기존 `frozen_profile.json`과 `evaluation_spec.json`은 개발 전용·동결 파일로 그대로 읽는다.

```powershell
python -m unittest tools.test_d1_energy_model_bridge_v2 tools.test_d1_arrival_energy_research tools.test_d1_energy_operational_sim -v
python -m tools.d1_energy_model_bridge_v2 --profile docs/results/energy_operational_sim_01/frozen_profile.json --spec docs/results/energy_operational_sim_01/evaluation_spec.json --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_plan_v3/collection_plan.json --run C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_run_v1 --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_model_bridge_reproduce_NEW
```

`--output`은 아직 존재하지 않는 새 폴더다. 기존 Git 결과를 덮어쓰지 않는다. PC 테스트는 적분 경계·결측·지원 차단과 이전 집계의 대표 회귀만 확인하며, 기기 안정성이나 다른 도착의 예측 정확도는 검증하지 않는다. 신규 출력의 확인 오차는 요약 결과를 이미 알고 시작한 **사후 진단**이다. AP 30°C는 그림용 연구 축이고 안전 한도가 아니다. J는 raw=mA 조건부 기기 전체 소비다.
