# 첫 선택의 정보 경계 진단

[`CONFIG.json`](CONFIG.json)은 실행 결과 전에 고정한 2사례×6분기×2첫 행동=24재생 계약이다. [`run_v2`](run_v2)는 절대 지표(`branch_metrics.csv`), CPU−GPU 짝 차이(`branch_deltas.csv`), 첫 시점 온라인 snapshot(`first_snapshots.json`), 이후 결정(`decisions.csv`), 사후 실현시간(`posthoc_first_realization.csv`), 기존 offline 참고값(`prior_offline_reference.csv`), 그림(`branch_deltas.svg`), 출처 SHA-256(`SOURCE_MANIFEST.json`), 판정(`RUN_SUMMARY.json`)을 담는다.

저장소 루트에서 새로운 출력 경로를 지정해 재현한다.

```powershell
python -X utf8 -m tools.d1_arrival_information_check --output "$env:TEMP/d1_arrival_information_replay"
python -X utf8 -m unittest tools.test_d1_arrival_information_check -v
python -X utf8 -m tools.d1_arrival_policy_screen --attach-information
```

도구 입력은 동결 CAL-03 파생 자료와 기존 offline witness다. 출력 경로는 존재하지 않아야 한다. 전체 offline 탐색은 재실행하지 않는다. 통합 화면은 [dashboard.html](../arrival_policy_screen_01/dashboard.html)의 맨 아래 “같은 과거, 다른 미래” 구역이다. 팀원은 상대 경로 소형 번들만 복사한 뒤 그 폴더에서 `python -X utf8 reproduce.py --bundle . --output .`로 화면을 재생성할 수 있다. 이 재생성은 저장된 결과의 시각화이며 새 시뮬레이션이 아니다.

PC가정 기반 진단이다. 시각 0의 관측 정보와 사후에만 아는 후속 도착/실현시간을 구분한다. 새 온라인 규칙·확인 사례 실행은 사전 gate 실패로 없다. 기기 실행 0회, `experiment_ready=false`.
