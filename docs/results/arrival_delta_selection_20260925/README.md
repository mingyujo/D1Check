# δ에 따른 정책 선택 — 사후 탐색

[한국어 보고서](../../ARRIVAL_DELTA_SELECTION_20260925.md)를 먼저 읽는다. 기존 입력 checkpoint `b7a4695`의 [absolute.csv](../arrival_service_review_20260925/absolute.csv)를 재사용한다. **시뮬레이션·실측·튜닝 0회**, `experiment_ready=false` 유지.

| 파일 | 내용 |
|---|---|
| [thresholds.csv](thresholds.csv) | 12조건×5정책의 기준 위반 건수/분모, 정확한 위반율 차이와 진입δ, 절대 성능 |
| [intervals.csv](intervals.csv) | 모든 진입 경계의 가용 후보·최저 긴급P95 후보·동률·일반평균·완료율·긴급위반 |
| [interval_table.md](interval_table.md) | 12조건을 사람이 읽을 수 있는 정확한 구간 표 |
| [delta_zero.csv](delta_zero.csv) | δ0의 선택·CPU 기준 분모 |
| [global_policies.csv](global_policies.csv) | 정책 하나를 전조건에 고정할 때의 최소δ·조건별P95·최악값 |
| [global_intervals.csv](global_intervals.csv) | 전조건 제약 충족 집합; minimax 열은 미채택 기술통계 |
| [P_comparisons.csv](P_comparisons.csv) | P 대 CPU/δ0최선의 절대 지연·위반 건수 차이·간섭 가정 |
| [delta_steps.png](delta_steps.png), [SVG](delta_steps.svg) | 허용폭과 사후 최선 긴급P95의 계단 |
| [receipt.json](receipt.json), [VERIFICATION.json](VERIFICATION.json) | 입력/코드 hash·선택 규칙·검증 시점/대상 |

`*_exact`의 분수는 %p 경계의 정확한 값이다. 구간은 왼쪽 포함·오른쪽 제외이며 오른쪽 빈칸은 이후 동일하다. δ0은 탐색점이며 사용자 서비스 기준으로 채택하지 않았다. 후보는 이전 주 비교의 CPU 긴급우선·고정분리·선정B2·B3·P다. 기존 B2 재선정이 아니며 제거군/FIFO로 최종 비교를 대체하지 않는다.

선택 목적은 **일반 위반 증가 제약 아래 긴급 P95 최소**다. 이전 분석의 일반평균 제약이나 긴급 위반율 우선 정렬을 추가하지 않는다. 동률은 전부 남긴다. 모든 조건의 최선은 사후 oracle 참고이며 배포 가능한 적응 정책이 아니다.

각 조건·정책은 5모델반복×24=120요청, 일반90/긴급30(urgent_heavy60/60)이다. 긴급P95는 반복별6/12건 최댓값의 평균이다. 전요청 완료·미완료0이지만 실패 과정은 미모델링이다. 실측 세션 CI·새 평가·열/에너지 결과는 아니다.

저장소 파일만 있으면 다음으로 재현할 수 있다. 새 출력 경로를 사용한다.

```powershell
python -B -m unittest tools.test_d1_arrival_delta_selection -v
python -B -m tools.d1_arrival_delta_selection --output C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_delta_selection_reproduced_v1
```

외부 최초 산출은 `C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_delta_selection_v1`이며 여기에는 작은 파생 결과만 공유했다. 원 실측·원 시뮬레이션 결과·기존 분석을 덮어쓰지 않았다.
