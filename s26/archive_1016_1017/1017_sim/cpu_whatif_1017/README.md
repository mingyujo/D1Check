# CPU what-if (2026-10-17 21:5x, Cowork 클라우드 · 이 세션)

목적: "CPU 1스레드라서 시뮬레이터가 CPU 를 안 고르나" 확인. 결과 문서 = 프로젝트 `claude/1017_CPU다중스레드측정_타당성평가.md`.

- 엔진: 조민규 `codex/s26-simulator-handoff-20261016` HEAD `b0b1c7df1775fcae3ba2944ed5df6d800382b4cc` 의 `s26_simulator/` — 무수정 · packet 파일 무수정 (메모리 안에서만 바꿈).
- 정책: `ROLLING_ATC_ROUTE_V2` · WAIT 끔 · stream 260016200 · 시나리오 R1-4-M128_BASE · R2-2-SMOOTH128_BASE.
- 변형: CPU 경로 템플릿의 `inference_s` 를 배율로 줄임 (명목값이 템플릿 잔차로 정규화되어 BASE 계수만 바꾸면 효과 0 — 확인함). 단위시간 전력은 1스레드 그대로 (CPU 에 유리한 가정).
- 결과: 모든 변형에서 분류 CPU 선택 0 / 96 (`whatif_output.txt`, 열 = [점유 ms, J 대리, AP 대리]).
- `whatif_pairs.cjs`: 정책 쪽 PAIRS 에 CPU 짝을 넣으면 엔진 `legal()` 이 "Invalid dynamic action" 으로 거부 (`whatif_pairs_output.txt`) → 엔진 쪽도 고쳐야 함.

실행: `S26SIM=<레포>/s26_simulator node whatif.cjs R1-4-M128_BASE`
표기: 전부 [시뮬]. 판정 아님 · 사전 등록 없음 (진단용 탐색).
