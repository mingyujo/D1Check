# S26 가상 기기 × 롤링+ATC+RL — 재현 묶음 (영훈 · 2026-10-17)

엔진 = 조민규 `codex/s26-simulator-handoff-20261016` 의 `s26_simulator/` (src · data 복사본). 엔진 물리·계수 파일은 수정하지 않았다. 바꾼 곳은 `code/*.diff` 세 개뿐이다.
- `rolling_action_v2.cjs`: 우리 규칙 선택기에 (1) 경로 가중치 옵션 `variant` (2) RL 잔차 옵션 `rl` 추가. 옵션을 안 주면 원본과 같은 결과 (확인함).
- `s26_simulator.cjs`: 비교군용 "빈 자원 채우기" (`*_BACKFILL_*`) 추가. 기존 정책 결과는 원본과 바이트 같음 (확인함).
- `s26_simulator_v2.cjs`: 지원 정책 목록에 `EDF_PAIR_CN_V1` · `FIFO_BACKFILL_CN_V1` · `EDF_BACKFILL_CN_V1` · `FIFO_BACKFILL_CG_V1` 추가.
- 가상 기기 k: `run4.cjs` / `rltrain2.cjs` 가 실행 때 `packet.timing.coef` 중 이름이 `AP:` 로 시작하는 항만 k 배 (파일은 그대로).

재현 (Node 20+, s26_simulator 를 복사한 폴더에 diff 적용 = simcopy):
```
node rltrain2.cjs <simcopy> train '["D25_g0.537155_c6d2_B","D25_g0.65_c6d2_B","D25_g0.8_c5d3_B","D25_g0.65_c5d3_B"]' 3.0 500 rl2_b.json   # TH0=3 SEED=22
node run4.cjs <simcopy> <jobs.json> <out.jsonl>   # jobs 형식 = results 의 id 필드 참고
```
