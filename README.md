# D1Check

스마트폰에서 분류·탐지 AI 요청의 CPU/GPU 배정과 시작 시점을 조절하며 응답·완료 요구, 기기 전체 에너지와 AP 온도의 상충을 연구한다. A24는 개발·주평가 기기이며 S26/NPU 협업은 기기별 근거로 구분한다.

최신 진행 상황은 **`feature/arrival-scheduling-20260923`** 브랜치에서 읽는다. 2026-09-30 현재 고정 작업 묶음의 실측 상충·저장된 정책의 서비스 비교·조건부 모형 진단을 확보했으며 동적 정책의 에너지·열 우월성은 아직 미입증이다. `experiment_ready=false`.

- [팀원용 최신 안내·담당 경계·필요 파일](docs/team/README.md)
- [현재 상태와 다음 행동](docs/PROJECT_STATUS.md)
- [연구 결과·논의 초안](docs/ENERGY_AP_RESULTS_DISCUSSION_DRAFT_20260930.md)
- [에너지·AP 결과 화면](docs/results/ap_simulation_closure_01/readout/index.html): 저장소를 내려받아 브라우저에서 열기
- [계획](docs/PROJECT_PLAN.md) · [결정 기록](docs/DECISIONS.md)

현재 준비된 A24 CG_DC 전이 확인1은 **미승인·미소비**다. 실행 계약·코드·작은 입력/결과는 저장소에 있으며 실제 로컬 계획/서명 APK/모델/대용량 원자료는 별도 확보가 필요하다. 정확한 실행 상태·파일·해시는 팀 안내를 따른다. 종료된 계획을 다시 실행하지 않는다.
