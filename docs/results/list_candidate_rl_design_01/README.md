# 리스트 후보 + RL 보정 선택: 설계 근거와 검증

`LIST-CANDIDATE-RL-DESIGN-01` · 2026-10-09 · **설계 완료, 정책 구현·학습·시뮬레이션 실행 전**

[추천 설계와 수식](../../LIST_CANDIDATE_RL_DESIGN_20261009.md)에서 구조·목적·범위·후속 예산을 설명한다. [논문 대응](research_mapping.md)은 출처의 개념과 D1Check가 제안한 변경을 구분한다.

| 파일 | 의미 |
|---|---|
| [design_contract.json](design_contract.json) | 원소스·모형 hash, 56/28특징, 8슬롯 행동, 목적, 보존 계약과 미실행 예산 제안 |
| [prior_list_inventory.json](prior_list_inventory.json) | 기존 성공3조건 원장 읽기: 과업내FIFO/192완료, 판단의도 없음. 새 정책 성능 자료가 아님 |
| [verification.json](verification.json) | 검증 명령·시각·HEAD/미커밋·정적 검사 결과와 한계 |
| [artifact_manifest.json](artifact_manifest.json) | 공유 문서·계약·검증기 원본 바이트의 SHA-256 |

재현 명령(저장소 루트):

```powershell
python -B -X utf8 -m tools.d1_list_candidate_rl_design_check
```

확인한 것은 180개 추상 후보 상태의 지원/용량/중복/유한지연, 3개 보상 합, 특징/파라미터 수, 원소스/공유물 hash와 예산 산술이다. **실제 엔진의 이벤트·원자commit·온라인 정보 누출·학습 성능을 검증한 것이 아니다.** 그 검증은 작은 구현 gate에 남아 있다.

이번 환경·학습·기기 실행은 모두0이다. 기존6,517환경/641학습을 유지한다. 원모형 AP는 표면온도가 아니며 별도 중단된 실측을 재실행하거나 그 부분 자료를 사용하지 않았다. 새 후보 공간의 표현 가능성과 기존 모형의 개선 여지가 확인돼야 후속 학습을 진행할 수 있다.
