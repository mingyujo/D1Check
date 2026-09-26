# 기존 PC 결과의 정책 후보 선별

[오프라인 대시보드](dashboard.html) · [45행 비교 CSV](policy_screen.csv) · [입력 해시](SOURCE_HASHES.json) · [한국어 판독](../../ARRIVAL_POLICY_CANDIDATE_SCREEN_20260927.md)

입력은 기존 `../arrival_diagnostic_02/interference_metrics.csv`다. low/queue/burst × 실현 간섭 1/1.5/2 × 기존 평가 seed 201–205에서 기존 P 예상 간섭 1.5와 네 기준 정책을 정렬했다. 새 이벤트 시뮬레이션, 새 seed, Android 실행은 없다. 각 조건의 5 seed 평균 비지배와 seed별 비지배 횟수를 구분한다. 미보정 전력·AP는 기존 진단 CSV/그림으로 연결하고 실측 값으로 승격하지 않는다.

```powershell
python -m tools.d1_arrival_policy_screen
python -m unittest tools.test_d1_arrival_policy_screen -v
```

`dashboard.html`은 CDN·서버 없이 로컬에서 열 수 있다. 입력 CSV의 SHA-256은 `SOURCE_HASHES.json`에 있다. 연구용 기한·모형 병행 지원과 실기기 검증의 경계는 상위 보고서를 따른다.

검증 기록(2026-09-27 02:55 KST, 착수 HEAD `0b97271da92b`, 이번 변경 staged 상태): 위 생성 명령으로 기존 CSV에서 45행 생성, 위 unittest 3건 통과, `git diff --cached --check` 통과. Node VM에서 포함된 JS를 오프라인으로 실행해 기본 queue/1.5 표와 burst/2 필터 전환을 확인했다. 실제 브라우저 렌더·휴대폰 검증으로 확대 해석하지 않는다.
