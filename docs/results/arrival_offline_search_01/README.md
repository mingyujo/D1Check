# ARRIVAL-OFFLINE-SCHEDULE-PC-01 재현

[한국어 판독](../../ARRIVAL_OFFLINE_SCHEDULE_PC_20260927.md) · [통합 대시보드](../arrival_policy_screen_01/dashboard.html) · [사전 고정 설정](CONFIG.json) · [출처 해시](run_v1/SOURCE_MANIFEST.json)

`CONFIG.json`은 low/queue/burst의 기존 24요청 합성 규칙에서 시간순 2/3요청을 자르는 규칙, seed301, 세 가정 profile, 응답 손실 0/250/500ms, 250ms 대기 격자·최대500ms, 사례별 노드/벽시계 예산을 결과 열람 전에 고정했다. 기존 24요청 결과는 작은 사례의 비교 정책으로 사용하지 않았다. 세 사례 모두 열거 `complete`이며 `run_v1/witnesses.csv`의 `optimality_proven=True`는 **해당 사례의 제한된 이산 행동 공간**에만 해당한다.

저장소 루트에서 새 출력 경로로 재현한다. 출력이 이미 있으면 덮어쓰지 않는다.

```powershell
python -X utf8 -m tools.d1_arrival_offline_search --output C:\temp\d1_offline_replay
python -X utf8 -m unittest tools.test_d1_arrival_offline_search tools.test_d1_arrival_explore tools.test_d1_arrival_policy_screen -v
```

`run_v1/comparisons.csv`: 4개 온라인 기준과 제약 없는 offline 최저 에너지 일정의 절대 지표. `witnesses.csv`: 질문 A/B에서 기준별·허용폭별 에너지 또는 AP 최소 발견 일정, 적격 일정 수, 응답 손실, 완전 탐색 상태. `pareto.csv`: 요청별 응답·완료/위반·에너지·AP 축의 비지배 일정. `actions.csv`·`requests.csv`·`thermal_paths.csv`: 제약 없는 offline 에너지 일정과 기준 정책의 선택·요청 시각·공통창 경로. `selected_*`: 각 허용폭 최저 일정의 같은 기록. `comparison.svg`: 사례별 에너지/AP 절대값. `RUN_SUMMARY.json`: 사례/행 수. 수치는 `CONFIG.json`과 CAL-03 개발 입력·기존 B2 동결값으로 정해진 PC 모형 안의 결과이며 실기기 독립 표본은 0이다.

대시보드 재현은 저장된 작은 결과만 읽는다. 기존 24요청 배치나 offline 탐색을 다시 실행하지 않는다.

```powershell
python -X utf8 -m tools.d1_arrival_policy_screen --attach-offline
```

복사한 `docs/results/arrival_policy_screen_01/repro_bundle` 폴더만으로도 `python -X utf8 reproduce.py --bundle . --output .`을 실행하면 동일 HTML이 생성된다. 번들 SHA-256 검사를 통과해야 하며, 작은 CSV·설정·SVG만 포함한다. 실제 탐색을 다시 실행할 때는 저장소의 Python 코드와 `docs/results/arrival_explore_20260925/input_bundle`의 CAL-03 파생 `estimates.json`/`realizations.json`, `freeze_before_evaluation.json`이 필요하다. `SOURCE_MANIFEST.json`의 SHA-256으로 연결을 확인한다.

데이터는 가정 기반 PC 탐색이다. 기기 전체 상태 전력은 미측정 W, AP는 모형 온도이며 BAT/표면/안전 온도가 아니다. Offline 탐색의 미래 정보와 초소형 요청 수를 일반 Android 정책의 우월성·정확성으로 읽지 않는다. 기존 종료 실측·원자료·FAIL·`experiment_ready=false`는 영향받지 않는다.

검증 기록: 2026-09-27 13:30 KST, 착수 HEAD `b017c68e41193052d0644c9a073c255698c86774`의 clean worktree에서 이번 변경을 작성했다. 위 탐색은 세 사례에서 각각 `complete`/미탐색 prefix0을 기록했고 선택한 일정 모두 기존 엔진 재생에서 ledger·에너지/AP가 일치했다. 관련 `unittest` 26건 통과, 로컬 Chrome headless 기본 화면·burst/500ms 필터의 한국어 표·타임라인·경로 렌더 확인. 상대 경로 번들을 외부 임시 폴더에 복사해 생성한 HTML과 저장소 HTML의 SHA-256이 일치했다. 이 검증 대상은 이번 미커밋 코드/설정이며 실기기 실행은 0회다.
