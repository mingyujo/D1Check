# M8 묶음 (prep) — S26 새 계약 (M8-apk) · 준비 완료 (측정 · 설치 · 스모크 0 · 수행 표시 없음)

- 만든 시각: 2026-10-14T23:35:10 · 등록 `5126d318107e001c7ca40ff12175f9042d8236097cc4f5013bc1192c41e5c182` (d1sim/docs/M8_사전등록_v1.md) · APK `fb9141396cffa5b646e93c0928567ba01e8d2ae6b187bd10ad39c37a579a526c` · 서명 `6394e51f94c71bd6e9cc5d76ff66e503583c1dca7d50f7ed175dd2e444cfcd32` · source `875384e73`
- 계약: 정책 7 (FIFO/EDD × SERIAL/PAIR × CPU/CG/CN · WAIT 인자) · bank 4 (L64 · C252 · M128 · SMOOTH128 · µs · 기한 0.8/2) · 응답 = urgent output_ready / normal readback (priority) · baseline 60 · cooling 90 · 120 s 뒤 dispatch 0 · 준비 role (RECENT) · NO_RUNTIME
- 게이트: SOC 시작 하한 20 · 상한 없음 (영훈 운영 결정 · 조민규 40~80 은 참고 열) · Tref 제안 v1 (TREF_DAY_IDLE_MEDIAN_V1 · ± 0.5 · 기울기 0.1 · 10 min → PRESTART_REJECT 원장)
- 단위 · 부호: 앱 current_raw µA (방전 음수 · 기기 스케일 미검증) · charge_counter µAh · voltage mV · host HAL ℃ 0.1 · 2.3 s · 갱신 시각 미제공 · 같은 gauge = 독립 기준 아님 · 앱/host 분리 (이어붙임 0 · host J180 계산 0)
- 분모: planned (완료만 남기지 않음) · PRESTART_REJECT 는 계획 coverage 분모 (START 와 구분) · 실패/미완료/재시도/충전/안전정지 소비 보존 · a2 재사용 0 · 쓴 ID 재사용 0


## 폴더
- `docs/` 계약표 v1 · 등록 v1 · contract_questions · A부 파생표 (derived_1014) · 원장 사본 · schedule_m8 · detection_gpu_evidence · instrumentation check
- `plans/` plan_m8* (plan.json · manifests · smoke · device_inputs · projection 없음 — bank 는 M8Plan 식) · plan_m8/blocks.json (DEV seed 20261014 · 순서 · CONFIRM 설계)
- `tools/` m8_* · coverage_check.py · 실행 명령 = m8_driver.ps1 머리 주석 · lock = results/S26_M8_driver.lock · 종료 = 드라이버 kill → 세션 프로세스 트리 taskkill /T
- `app/` git diff --stat aaa7b87f -- request-runner/ · 영역별 diff · 시험 결과 (회귀 = 기존 계약 / 새 계약 시험 구분) · 빌드 명령 · 시각 · APK SHA · 서명 (APK 바이너리 없음)
- `results/` 없음 (prep = 측정 0)

- 주소 · 시리얼 0 (PAT 검사) · *.apk 없음
