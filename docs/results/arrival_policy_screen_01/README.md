# 통합 PC 탐색: 한 파일에서 응답·에너지·AP 확인

[저장 135개 일정의 전체 예정 요청 기준 응답·완료 판독](../../ARRIVAL_SERVICE_CHOICE_PC_20260930.md)은 화면의 기존 서비스 결과를 별도 CSV로 고정한다. 사전 선정 queue/201/1.5에서 B2·B3는 둘 다 기한 내20/24이며 긴급 P95와 일반 평균의 방향이 다르다. 실측 기반 J/AP 순위는 여전히 null이다. [작은 공유 결과](../arrival_service_choice_01/README.md).

2026-09-29 새 lifecycle APK의 별도 B2 재생은 [시작 AP gate 중단](../../ARRIVAL_RECORDED_B2_REPLAY_RUN02_20260929.md)이다. 28.8°C가 사전 범위 32.5–34.0°C 밖이어서 공식창·본 요청이 없으며, 화면 맨 위의 [작은 요약](../energy_ap_recorded_b2_01/run02_summary.json)은 J/AP를 `null`로 둔다. 아래 기존 plan_v3 lifecycle 취소와 별도 사건이다.

2026-09-29 기록 재생 1회 중단: 화면 맨 위에 저장 queue/seed201/B2의 **원본 PC 일정·예정 기기 재생 입력**과 [중단 결과·조건부 판독 계약](../energy_ap_recorded_b2_01/README.md)을 연결했다. runtime4·warmup8 뒤 resident baseline에서 앱이 취소되어 실제 작업 일정·120초 J/AP 오차는 공란이다. 기존 가정 기반 순위와 섞지 않는다.

2026-09-29 실측 기반 지원 검사: 저장된 CPU_URGENT·B2·B3의 135개 일정 중 **전체 120초 J/AP를 동결 A24 모형으로 지원하는 사례는 0개**다. [정책·입력별 판정](measured_support_01/support_status.csv), [첫 차단](measured_support_01/first_blockers.csv), [전체 차단](measured_support_01/all_blockers.csv), [대표 일정](measured_support_01/representative_schedule.svg), [해제 조건](../../ARRIVAL_MEASURED_SUPPORT_BOUNDARY_20260929.md)을 함께 본다. 저장 일정·응답은 PC 결과, 화면에서 조작하는 비용은 탐색 가정, 동결 모형의 도착 예측 검증은 미완료다. 아래 기존 번들 재현 명령은 가정 기반 화면을 만들며 이 실측 지원 판정은 별도 읽기 전용 명령으로 재현한다.

```powershell
python -X utf8 -B -m tools.d1_arrival_measured_support --frozen C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json
```

최신 추가: 맨 아래 **같은 과거, 다른 미래: 첫 배정 진단**에서 queue/burst 개발 사례와 후속 분기를 고르면 시각0 관측 snapshot, CPU/GPU 첫 행동의 응답·기한 위반·공통120초 에너지·AP, 이후 배정·대기 이유를 본다. 첫 배정만 바꾼 결과와 미래 정보를 사용한 완전 offline 일정을 구분한다. 분기 확률과 실측 전력·AP 근거가 없으므로 새 온라인 규칙이나 종합 우승을 표시하지 않는다. [계약·CSV·재현](../arrival_information_check_01/README.md), [차이 SVG](repro_bundle/information_branch_deltas.svg)를 함께 본다.

최신 추가: 같은 HTML 아래쪽의 **작은 사례 offline 일정 탐색**에서 사례·정책·요청별 연구용 응답 손실 0/250/500ms·에너지/AP 지표·시간축을 고를 수 있다. 이는 [별도 계약과 결과](../../ARRIVAL_OFFLINE_SCHEDULE_PC_20260927.md)의 첫 2/3요청에 한정되며 기존 24요청 결과와 섞지 않는다. 0손실에서는 열·에너지 후보보다 나은 일정이 없고, 손실을 허용할 때만 일부 차이가 나타난다. 발견 일정은 미래 정보·미측정 상태 W/AP 가정을 사용하므로 실제 배포 가능 정책으로 읽지 않는다. [작은 결과·재현](../arrival_offline_search_01/README.md)과 [대표 SVG](repro_bundle/offline_comparison.svg)를 함께 본다.

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
