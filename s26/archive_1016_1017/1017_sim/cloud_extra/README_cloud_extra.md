# 클라우드에만 있던 시뮬 코드·결과 추가분 (10/17 · 영훈 쪽)

`../` 의 보관 커밋 (`s26-archive-1017`) 에 빠진 파일만 모았다. 전부 Cowork 클라우드 실행 · 폰 0 · 수치는 **[시뮬 예측]**.
엔진 = 조민규 S26 `codex/s26-simulator-handoff-20261016` (`src/` · `data/` 는 `b0b1c7d` 에서도 `d23fbd1` 과 동일). 엔진 파일은 수정하지 않았다.

| 폴더 | 내용 | 결과 문서 |
|---|---|---|
| `a24port/` | A24 롤링+ATC 규칙 (`rules_no_rl_20261017` ROLLING_ATC) 을 S26 실측 모형에 이식. `atc_a24.cjs` (choose() 만 덮어씀) · `judge.py` · 사전 등록 `PREREG_A24PORT_1017.md` (SHA `6c480330…`, 확인 실행 전 고정) · `runs/` (jobs · 원자료 out_*.jsonl 91회 · `JUDGEMENT.json`) | `1017_A24규칙_S26이식_결과.md` |
| `s26rl_extra/` | S26 RL 실험의 개발용 보조 스크립트 (`smoke.py` · `progress.py`) — `sim/out_s26rl_1017/code/` 에 없던 것 | `1017_S26_RL실험_결과.md` |
| `rl_port_proto_extra/` | RL 이식 시제품 학습·스모크 로그 (`train_*.json` · `smoke.json`) — `sim/rl_port_proto_1017/` 에는 코드만 있음 | `1017_S26_RL이식_가능성검토.md` |
| `vd_extra/` | 가상 기기 실행 로그 (`runs_*.out`) · 실행 전 SHA (`SHA_PRE.txt`) | `1017_가상기기_NPU쏠림없는조건_결과.md` |

A24 규칙 이식 재현:
```
LAB=<rlexp/lab.cjs 경로> S26_ROOT=<s26_simulator> node atc_a24.cjs runs/jobs_0.json out.jsonl
python3 judge.py   # 비교군·S26 규칙 값은 out_vd_1017 raw_runs.tgz 의 Ameas_B0.jsonl 를 읽는다 (경로는 코드 안 /home/claude/... 를 바꿀 것)
```
여전히 없는 것 (다른 클라우드 세션 안에만 있었음): A24 시뮬 v1 원자료 · S26 시뮬 v1 all.jsonl · 설정 탐색 · 우위조건 A24 쪽 · 과부하 작은조정 · CPU 다중스레드 what-if.
