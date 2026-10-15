# 준비 후 기준 묶음04 — 분류 CPU/GPU 대응 파일럿

두 조건 모두 예정252건을 서비스창 안에 기한 내 완료했고 출력252건씩 검산을 통과했다. 12:55:25에 회수·저널 close·실제 lane 반환을 확인하고 실행기를 종료했다. 추가 조건은 실행하지 않았다.

| 조건 | 완료/예정·기한 내 | 긴급 P95 | AP 평균35~180초 | 관측 최고AP | START 직전AP |
| --- | --- | ---: | ---: | ---: | ---: |
| 분류 GPU |252/252·100%|273.369ms|29.4666℃|30.0℃|28.6℃|
| 분류 CPU |252/252·100%|116.581ms|29.8679℃|30.4℃|29.0℃|

**이 한 쌍에서는 CPU 응답이 빠르다. GPU의 AP 읽기값은 평균 약0.401℃ 낮지만, 시작 읽기값도 이미0.4℃ 낮았다. 열 절감 효과로 판정할 수 없다.** 두 군 모두 봉인한28.6±0.5℃ gate를 통과했지만 내부 잔열·DVFS·주변환경까지 같은 것은 아니다. AP 평균에서 각 시작 읽기값을 단순히 빼면 GPU0.8666/CPU0.8679℃다. 이는 설명용 값이며 열량·동적 보정·인과효과 추정이 아니다.

에너지는 전류 API/charge counter 단위 불일치로 **J 계산불가**다. AP는 HAL 읽기값으로 실제 표면온도/센서 cache age는 미검증이다. 대응1쌍이므로 신뢰구간은 null이다. 요청252건이나 센서 읽기를 독립 반복으로 세지 않는다. CPU/GPU의 포괄적 우열·제품 에너지 절감·최종 스케줄러 검증을 주장하지 않는다.

첫 GPU공통준비 뒤 최초 안정60초 기준28.6℃를 본요청 전에 봉인했다. CPU는 앱 밖 냉각 뒤 공통4runtime/8warmup을 수행하고 같은 기준SHA의 gate를 다시 통과했다. 준비·냉각의 실제 wall time은 [시작 상태/종료 검증](INITIAL_STATE_AND_CLOSURE.json)에 남겼다. 본측정0~180초 밖 준비·냉각의 에너지를0으로 처리하지 않는다.

입력은 같은 승인 이미지와 분류252건·FIFO·직렬·WAIT0,도착35+i×0.3332초·상대기한2.2초다. 완료량/실패/미완료252분모,출력품질,실제 AVAILABLE 반환을 검산했다. 단일 이미지의 출력 일치이지 전체 정확도 검증은 아니다. 탐지 요청/혼합 병행/EDD/WAIT효과는 이 쌍에 없다. `service_nonworsening`의 기존 엄격한 P95 조건은 GPU에서false이며 판정을 완화하지 않았다.

대표 시간표는 성적과 무관하게 각 군의 첫16건이다. 실측 소스는 커밋94337e6과 runtime171파일SHA가 일치했고 원161/본 controller/APK는 보존했다. 원사용자 미커밋12파일·다른worktree HEAD 보존도 확인했다. 정확한 manifest·서명·원장·tar·이벤트·출력은 로컬 보존하며 모델/APK/키/개인 target·경로를 공개하지 않는다.

[오프라인 화면](index.html) · [세션](sessions.csv) · [전체 예정504건](requests.csv) · [대응 차이](paired.csv) · [AP 원읽기 시각](reported_AP.csv) · [사전 계약](../../../team/a24-measurement-revision02-20261015/prepared_block04/README.md) · [전체 실측 재개 안내](../../../team/a24-measurement-revision02-20261015/MEASUREMENT_RUNBOOK.md)

재분석은 개인 원물과 새 출력 폴더가 필요하다:

```powershell
python -B tools/d1_a24_measurement_report.py <job.json> <ANALYSIS_CONTRACT.json> <새분석폴더> --stage DEV
python -B tools/d1_a24_revision02_figures.py <새분석폴더>
```

이 명령은 기기를 호출하지 않는다. 종료된 시간창·완료/실패ID는 재측정하지 않는다. 이번은 개발 파일럿이며 독립 확인 완료/수치 예측모형 정확도 PASS/검증J/experiment_ready=true로 승격하지 않는다.
