# EDD+ECT를 기본으로 하는 보정 RL 설계

**기본은 EDD 요청 순서와 ECT 자원 선택, 학습은 그 판단의 열·에너지 보정이다.** 이전 설계를 통합한 현행 설계이며, 새 controller 구현·학습·성능 검증은 아직 0이다.

[전체 설계와 핵심식](../../EDD_ECT_RESIDUAL_RL_DESIGN_20261008.md) · [기계 계약](design_contract.json) · [검토 결과](DESIGN_REVIEW.md) · [설계 검증 기록](verification.json).

RL은 기한 안에서 다른 요청, CPU/GPU, 분류GPU+탐지CPU 묶음, 짧은 냉각 대기를 선택한다. EDD+ECT의 자원 대기는 원래대로 남기고 추가 냉각은 별도로 제한한다. SHARED_EFT의 강제 aging은 상속하지 않는다. 예측 후속계획도 EDD+ECT와 같은 판단이어야 한다.

기존 EDD+ECT는 주96조건에서 Shared/Band보다 모형 AP는 낮지만 J는 높았다. 따라서 EDD+ECT 자체 개선과 강한 비교군 대비 적격성을 함께 요구한다. 원 EDD→필터 prior→학습 없는 greedy→RL을 구분해 필터 효과를 RL 성과로 돌리지 않는다.

| 항목 | 이번 수정 |
|---|---|
| 기본·fallback·예측 suffix | `IE_EDD_ECT_LANE_PC_V1` |
| 학습 참조 | EDD+ECT, SHARED_EFT, Band |
| 고정 검증 참조 | 위3개와 강한 Triton |
| 관측·후보·행동 | 109 / 68 / 32slot |
| 현재 실제 추가 실행 | 환경0 / 학습0 / 기기0 |
| 현재 누적 소비 | 환경2,825/20,000, 학습0/6,144 |
| 조건부 후속 제안 | 환경16,488, 모든 학습6,144 이내 |
| 실제 다음 단계 | 학습 없는 prototype와 A/B/C/D 검증 |

표의 후속 숫자는 옛 안을 교체하는 제안이다. 새 참조 비용·최종17정책 목록을 포함했고, 환경 누적 최대19,313으로 계산했다. 신규 seed·학습 시간은 아직 null이며 새로 실행 허가를 만든 문서가 아니다. 강한 기준 대비 개선 신호가 없으면 학습0을 유지한다.

AP는 모형 AP이며 표면온도가 아니다. 현재 APK numeric AP stream, 모바일 제어 비용, S26/NPU는 이 설계의 검증 범위에 들어오지 않는다. 원모형·기본정책·strict·experiment_ready=false와 이전 결과는 보존한다.

공유 파일만으로 설계의 참조 SHA·schema·예산·수식 검증:

```powershell
python -B -m tools.d1_edd_ect_residual_design_check
```

이 명령은 원시 실행 폴더나 학습 라이브러리를 요구하지 않으며 엔진을 시작하지 않는다. PASS는 문서/계약의 일관성이지, 새 정책 동작이나 A/B/C/D 통과를 뜻하지 않는다.
