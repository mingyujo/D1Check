# 서비스 비교 결과 묶음

[한국어 해석·공정성·권고](../../ARRIVAL_SERVICE_COMPARISON_20260925.md)를 먼저 읽는다. 기준 소스는 `7402a0a6973ad19148be3ee3d406eb282e8410b2`; 후처리 버전은 `arrival-service-review-v2`다. 모든 결과는 사후 PC 분석이며 실기기 우월성/실패율/정밀 tail의 증거가 아니다.

| 파일 | 내용 |
|---|---|
| [service_tables.md](service_tables.md) | explore 12조건×5주요정책의 절대값·분모와 P 상대차 |
| [absolute.csv](absolute.csv) | 2모드×12조건×8정책, 5반복 평균·범위·계획/도착/완료·기한 분모 |
| [service_comparison.csv](service_comparison.csv) | 주요5정책과3대조의 절대값·대조 절대값·paired 상대차·분모를 한 파일로 결합 |
| [relative.csv](relative.csv) | 같은 seed 상대차 평균, 절대차, 위반율 차이 |
| [dominance.csv](dominance.csv) | 지연2지표/위반율 포함의 표본 지배·상충, 반복별 관계 |
| [constraint_boundaries.csv](constraint_boundaries.csv) | CPU 긴급우선 대비 필요한 일반평균 손실%·위반증가%p |
| [sensitivity.csv](sensitivity.csv) | 사후 허용값 격자의 후보 선택, 새 기준 채택 아님 |
| [trace_summary.csv](trace_summary.csv) | 대표 반복만의 일반P95·대기·backend·선택없음·비용예산 |
| [decision_cases.json](decision_cases.json) | 당시 P 상태/후보와 같은 상태 B3 선택. 반사실적 성능값 아님 |
| [trace_replay_summary.json](trace_replay_summary.json) | 대표 선정 규칙·추가3재생의 기존CSV 일치 |
| [receipt.json](receipt.json), [VERIFICATION.json](VERIFICATION.json) | 입력/엔진·검증 코드 hash와 변경 경계 |
| [tradeoff.png](tradeoff.png), [SVG](tradeoff.svg) | 긴급P95와 일반평균의 상충, 5모델반복 평균 |
| [constraint_map.png](constraint_map.png), [SVG](constraint_map.svg) | CPU 기준 서비스 제약에 따른 선택 경계 |

각 정책·조건 분모120=24×5, urgent30/normal90(urgent_heavy60/60). 완료120, 미도착/미완료0. 실패/거절/만료 **과정은 미모델링**이므로 해당0을 현실 실패율로 읽지 않는다. 긴급P95는 반복별6/12건의 최댓값을5개 평균한 값이다. 일반P95는 전체배치 미저장→빈칸이며 대표trace에만 있다. 오차범위는 모델 min/max이고 실측 세션 CI가 아니다.

원본 `arrival_explore_batch_v3`와 확인 실측 원본은 Windows 외부 폴더에 보존되어 GitHub에는 없다. 이 폴더에는 작은 파생 수치·그림만 공유한다. 전체 재현은 원본 접근이 필요하다. 새 output 경로를 사용한다.

```powershell
python -B -m unittest tools.test_d1_arrival_service_review -v
python -B -m tools.d1_arrival_service_review --source C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_explore_batch_v3 --bundle docs/results/arrival_explore_20260925/input_bundle --output C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_service_review_reproduced_v1
```

기존 전체배치·B2선정·실측을 실행하지 않는다. 저장 trace가 없는 손실최대조건의B2/B3/P만3개재생해 기존지표일치를검사한다. 원 후처리v1의 제거군 이름 중복을v2에서수정했고 수치변경/추가시뮬레이션은없다. 원정책·동결40값·기존20null·FAIL·종료계획은불변이고 `experiment_ready=false`다.
