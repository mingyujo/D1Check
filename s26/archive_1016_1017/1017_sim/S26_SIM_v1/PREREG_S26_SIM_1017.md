# S26 시뮬레이터 측정 사전 등록 v1 (2026-10-17, 실행 전 고정)
엔진: 조민규 s26_simulator (브랜치 codex/s26-simulator-handoff-20261016) 무수정. 계수·납기(0.8/2 s)·요청표(packet 봉인 M128/SMOOTH128) 그대로.
맥락: 기존 48조건과 같은 6맥락 (R1-4 R1-6 R2-2 R2-3 R3-1 R3-2 *_BASE 초기이력).
개발 표본: stream 260016200..207 (기존과 같음). 확인 표본: stream 260017300..307 (새, 한 번만).
정책(전부 CENTRAL): OWN=ROLLING_ATC_ROUTE_V2 / OWN_NOWAIT / OWN_NONPU(분류 CPU·GPU만) / FIFO_PAIR_CN / FIFO_PAIR_CG / EDF_PAIR_CG / FIFO_SERIAL_CN / FIFO_SERIAL_CG / EDD_SERIAL_CG / FIFO_WAIT_CG / FIFO_SERIAL_CPU_V2.
민감도: NO_THERMAL / LOW_SLOPE / HIGH_SLOPE × {OWN, FIFO_PAIR_CN, FIFO_PAIR_CG} (개발 표본).
가드: 128/128 완료·정시. 미충족 정책은 열·에너지 비교에서 제외(따로 표기).
지표: AP35~180 평균, AP 최고, AP180, J_API0~180.
판정(쌍 = 같은 맥락·같은 stream):
- AP: 평균 ΔAP 의 |·| > 0.18 ℃ (R21 정책 간 AP 차이 오차) 이고 같은 부호 쌍 ≥ 80 % → "차이 있음", 아니면 "모형 오차 안".
- J: 부호만. 같은 부호 쌍 ≥ 80 % → "방향 있음 (크기 미보장, R21 에서 4배 과대)". NPU 가 낀 J 대조는 "기술만" (R21 NPU J 부호 0/3).
- 확인 표본에서 같은 판정이면 "확인", 다르면 다른 대로 보고.
