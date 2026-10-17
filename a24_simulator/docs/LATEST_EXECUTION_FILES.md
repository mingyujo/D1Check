# 2026-10-17 최신 학습·실행 저장본 위치

GitHub의 이 폴더에 13:38의 학습 시작 상태 이후 **96회 학습과223회 전체 실행**, 최종 검산·보고 파일을 추가했다. 시작 커밋 `8ea30e4e`만 보고 재학습하지 않는다. [완료 증거](../results/RL_COST_20261017_01/FINAL_HANDOFF_PROOF.json)와 [통합 보고](COST_RL_COMPARISON.md)를 먼저 읽는다.

| 필요한 자료 | 이 폴더 기준 위치 |
|---|---|
| 최신 재개 상태 | `CONTINUE.json` |
| 학습 코드·입력·예산·등록·후속 검산 소스 | `experiments/rl_cost_20261017/` |
| 모든 새 학습/평가 저장본 | `results/RL_COST_20261017_01/` |
| 223회 종결·소비 | `COMPLETE.json`, `receipts.jsonl`, `FINAL_HANDOFF_PROOF.json` |
| 선정 정책 | `PPO_COST_EP096.pt.gz`, `SELECTION_FROZEN.json` |
| 전후 network/Adam/행동·셔플RNG | `TRAIN_*.before.pt.gz`, `TRAIN_*.after.pt.gz` |
| 학습 경험·정책 입력/마스크·행동 | `TRAIN_*.experience.pt.gz`, `*.frames.pt.gz`, `*.actor_calls.json.gz` |
| 원 예측·동일 작업창 수치 | `*.prepared_prediction.json.gz`, `*.raw.json.gz`, 조건별 `*.json` |
| 통합 결과와화면 | `RESULT.json`, `REPORT_DATA.json`, `REPORT.html` |
| 실제 검산 | `NN_AUDIT.json`, `SAVED_AUDIT.json`, `UI_QA/RESULT.json` |

표의 파일명은 별도 표기가 없으면 `results/RL_COST_20261017_01/` 안에 있다. **`runtime/rl_cost_20261017_01/`은 생성하지 않았다.** 그 위치에서 찾던 경험·frames·체크포인트도 모두 위 results 폴더에 있다.

원 PC 정본은 `C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/A24-GITHUB-HANDOFF-20261016/a24_simulator`다. 이 절대 경로는 다른 PC에서 접속 가능한 네트워크 주소가 아니다. 다른 PC에서는 이 GitHub 브랜치의 최신 폴더를 받는다. 과거 operation의 원 PC 절대 경로를 새 환경에서 무작정 실행하거나, 완료된 학습/검산을 자동 재실행하지 않는다.

## 별도 로컬 백업

`C:/Users/chomg/Documents/ChatGPT/산공회/A24_RL_COST_20261017_223_COMPLETE.zip`

- 1,207,690,952 bytes, 1,446개 원파일을 멤버별 SHA256로 재검증했다.
- ZIP SHA256: `53e2fe5ea8e9f8c3ff2badd9b65e6365aa22aea415b702847465dc61f129c2ff`
- ZIP 안 `BACKUP_MANIFEST.json`에 파일별 상대경로·크기·SHA가 있다.
- 이 백업은 시작 커밋8ea30e4e에 덧붙일 최신 실행·실험·주요문서 overlay이며 전체 과거 패키지를 중복한 백업은 아니다. GitHub의 최신 제어문서가 백업 시점 문서보다 우선한다.
- [백업 영수증](../results/RL_COST_20261017_01/BACKUP_REFERENCE.json), `experiments/rl_cost_20261017/BACKUP_OPERATION_V2.json`도 보존했다. D드라이브의 느린 최초 복사는 `.partial`로 보존했으며 완료 백업으로 사용하지 않는다.

## 완료 판단

학습96/TRAIN·DEV48·새평가60·과거진단7·NN제외12=223 START/COMPLETE, FAIL0. DEV 선정EP96·12updates/606Adam이다. 저장 NN/Adam/RNG5,310,420검사, 산술633,569검사, 실제6뷰5557검사 PASS를 완료했고 여기서는 재실행하지 않았다.

이는 소프트웨어와 고정모형의 검증이다. DEV 납기기준·납기/열/에너지 공동목표는 미달이며 기존 대화형 기본정책은 교체하지 않았다. 실측J/error/CI null·폰RL 미검증을 유지한다. [남은 설계 한계](COST_RL_LIMITATIONS.md)를 읽고 후속 개선은 새 소스·예산·DEV·미사용 평가로 등록한다. 반복예약이나 신규 실측 주기조회는 켜지 않는다.
