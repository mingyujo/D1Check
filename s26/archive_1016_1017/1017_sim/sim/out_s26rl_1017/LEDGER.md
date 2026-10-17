# LEDGER — S26 RL 1017

## 2026-10-17 16:54:22 사전 등록 고정 (학습·DEV·EVAL 실행 0)
- 999cb9efb70c05a405d1259c472ccd3ad95beb21e76b4a5d6461337b12d9823e  PREREG_S26_RL_1017.md
- f699360a7d8594af1fa0f1141141d9d973a5098c25a276d97f41f87bd35378d0  rl_lab.py
- 3963460841be7d0a8013bf48f8938003fee890cc6ce4dfc7ddbe795ff503a102  rl_server.cjs
- 320e085a1d8346365b5c7d0d6fd8636f2836a5563813f796df5c94c50fd84d58  lab.cjs
- 5d91caac15c0a1156c0c919ca977fa3063f028d2bc3a4e2e9c6666679b3de170  /home/claude/work/a24/a24_simulator/reference/rolling/policy_bridge.py
- be5af6fc338f2d8ceac5a111eab155c700e8468830469a8a6033feac805fe0da  /home/claude/work/a24/a24_simulator/reference/rolling/learner.py
- engine branch d23fbd1 (s26) · 9e04b4b (a24)
- 16:54:34 문구 정정 (부하 개수 '10' → '9', 크기 숫자 그대로) · 실행 0 상태 · 새 SHA e8949a6b47d3e904e6f9ffbd4d8580c527297668b5b32f3b4c0cd238e8de7095
- 16:55:07 학습 시작 · train.py 500dcf49e430040b… · seeds 46101 46103 46107 × 512
- 17:24:29 학습 완료 3 seed · 체크포인트 EP000/064/128/256/512 · evaluate.py 368881f4da15abab… judge.py 9cece05b80b10ba0… (DEV·EVAL 실행 전 고정)
- 17:38:48 DEV 선정 완료 (EVAL 실행 전): 46101 → EP256 · 46103 → EP512 · 46107 → EP256. EP0 은 세 seed 동일 (actor 마지막 층 0 초기화 → 첫 합법 행동, 대조군). DEV 서비스 부족 EP0 0.148 → 선정 0.078~0.083
- 18:05:58 EVAL 1회 완료 · judge.py 판정: EVAL H1 미확인 (0/3 seed — 생성 부하 중 6C2D 56쌍이 용량 안이라 전 정책 100 %, 과부하 표본 오지정) · H2 미확인 · H3 모형 오차 안 · HELD H1 확인 3/3 · H2 미확인. 사후 분해 (등록 판정 아님) = 결과 문서 §3. JUDGEMENT.json 607e5c8da0b14025…
- 18:11:32 결과 문서 §3 자원 비율 문장 정정 (seed 별 25/96/100 % NPU)
