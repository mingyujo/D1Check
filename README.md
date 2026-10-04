# D1Check

스마트폰에서 분류·탐지 AI 요청의 CPU/GPU 배정과 시작 시점을 조절하며 응답·완료 요구, 기기 전체 에너지와 AP 온도의 상충을 연구한다. A24는 개발·주평가 기기이며 S26/NPU 협업은 기기별 근거로 구분한다.

최신 진행 상황은 **`feature/arrival-scheduling-20260923`** 브랜치에서 읽는다. 2026-10-04 현재 등록된192요청 CPU/PAR의 실제 온라인8세션과 동결 모형의 일정·에너지·AP 예측을 대조했다. 두 정책 모두 기한을 충족했고 병행의 긴급 응답 개선을 관측했다. 작은 에너지·열 차이에 의한 정책 우열은 미판정이며 `experiment_ready=false`다. 과거24요청 기록 재생·고정870건·조건부 AP 경로도 별도로 보존한다.

- **[발표 담당자용 문안·그림·표·시연 순서](docs/results/final_presentation_01/README.md)**
- [팀원용 최신 안내·담당 경계·필요 파일](docs/team/README.md)
- **[시뮬레이터 시작 화면](docs/results/simulator_workbench_01/index.html)** · [CLI 사용법·재현·지원 범위](docs/results/simulator_workbench_01/README.md)
- **[최신192요청 실측·예측 결과와 PC 재현](docs/results/online_policy_study_01/overnight_sustained_run01/README.md)**
- [현재 상태와 다음 행동](docs/PROJECT_STATUS.md)
- [연구 결과·논의 초안](docs/ENERGY_AP_RESULTS_DISCUSSION_DRAFT_20260930.md)
- [에너지·AP 결과 화면](docs/results/ap_simulation_closure_01/readout/index.html): 저장소를 내려받아 브라우저에서 열기
- [계획](docs/PROJECT_PLAN.md) · [결정 기록](docs/DECISIONS.md)

CG_DC 전이 확인·두 AP 이력 확인과 CPU/B2 네 세션은 이미 종료됐으며 재실행 대상이 아니다. 시뮬레이터는 저장소의 작은 입력/결과만으로 PC에서 실행하며 기기·APK·대용량 원자료가 필요 없다. 실제 기기 계약·소비 상태는 STATUS를 따르고 종료된 계획을 다시 실행하지 않는다.
