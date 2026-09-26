# 통합 PC 탐색: 한 파일에서 응답·에너지·AP 확인

[대시보드](dashboard.html)를 로컬 브라우저에서 직접 연다. 서버·CDN은 필요 없다. `low/queue/burst`, 실현 간섭, seed, 일반 기한 위반 허용 증가폭 δ(%p)를 선택한 다음 아래 상태별 **기기 전체 절대 전력 W**와 AP 평형온도를 바꾸면 표와 B2−B3 동률선이 즉시 갱신된다. δ는 연구용 입력이며 합의된 SLA가 아니다. 과거 화면은 [보존본](dashboard_legacy.html), 과거 5정책 [응답 CSV](policy_screen.csv)로 남겼다.

자료는 기존 24요청 동결 PC 결과 45조건의 B2·B3·CPU 135개 비용 일정이다. 기존 응답 지표와 대조한 제한 재생에서 작업×backend 공동 점유를 추출했다. FIXED_SPLIT·P는 같은 화면에 응답만 표시하고 에너지·AP는 계산 불가로 둔다. [독립 상태 일정 CSV](repro_bundle/occupancy_segments.csv)는 120초 공통창을 빠짐없이 분할한다. [5정책 응답 CSV](repro_bundle/service_metrics.csv), [가정 JSON](repro_bundle/assumptions.json), [출처·해시](repro_bundle/SOURCE_HASHES.json)를 함께 사용한다. 자세한 판독은 [한국어 보고서](../../ARRIVAL_INTEGRATED_EXPLORER_20260927.md), 기본 가정의 [대표 3조건 CSV](representative_comparisons.csv), [동률선 계수 CSV](pair_plane_examples.csv)를 참고한다.

전체 재현(저장소 루트에서, 선택된 135개 일정만 검증 재생):

```powershell
python -X utf8 -m tools.d1_arrival_policy_screen
python -X utf8 -m unittest tools.test_d1_arrival_policy_screen -v
```

저장소와 사용자 PC 절대 경로 없이 **작은 입력 번들만 복사**해서 같은 대시보드를 만들려면 `repro_bundle` 폴더 안에서:

```powershell
python -X utf8 reproduce.py --bundle . --output .
```

번들 재현은 이미 검증한 PC 일정과 응답만 표시한다. CAL-03 원자료 재분석이나 이벤트 엔진 재실행이 아니다. `SOURCE_HASHES.json`은 번들 파일을 재현 전에 검증하며 원본 모형·입력의 SHA-256도 기록한다. 해시는 Windows checkout의 줄바꿈 변환에 흔들리지 않도록 UTF-8 텍스트의 CRLF를 LF로 정규화한 값이다. `repro_bundle`은 상대 경로 파일 약 0.5 MB이고 모델·APK·키·원자료가 없다.

기본 입력 idle 1 W, 단독 2 W, 각 병행 2 W, 초기 AP 29°C, idle/단독/병행 평형 29/34/30°C, τ 60초는 **미측정 스트레스 가정**이다. 서로 다른 병행 상태를 독립 입력으로 조정할 수 있으나 이 범위를 실제 A24 범위로 해석하면 안 된다. AP는 BAT·표면 온도가 아니고 열 피드백이나 배터리 수명 모델은 없다. 시간 결과는 CAL-03 개발 자료에 기대는 PC 모형 결과다. `experiment_ready=false`와 실기기 정책 성능 미검증은 그대로다.

검증 기록: 2026-09-27 03:45 KST, 착수 HEAD `b15526a71557ba0ea7e8fc783120fcd95642e689`, 위 생성·관련 unittest 6건 및 `git diff --cached --check` 통과. 당시 새 파일과 코드·문서 변경은 staged이며 아직 commit 전이다. 로컬 Chrome에서 기본 표·동률선을 렌더하고 burst/seed203/전력 필터 조작을 확인했다. 이는 PC 화면 검증이다.
