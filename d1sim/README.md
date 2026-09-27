# d1sim — D1 시뮬레이터 v0 (우리 층)

**탐색용. 합성 워크로드. 검증 전.** 조민규 엔진과 무관한 새 층 (근거: `산공학회\D1_ondevice\작업결과_0926_평가층.md` §10 — 그의 엔진은 NPU lane·열 되먹임 불가).

| 파일 | 역할 |
|---|---|
| `throttle.py` | 스로틀 모형 v0 (M-A2, SKIN 구동 2노드). **고정 커밋 `402acab`** — 바꾸면 v1 |
| `profile.py` · `profiles/device_profile_S26.yaml` | 프로파일 (값·status·source). null = 마스크 |
| `env.py` | 이벤트 기반, 한 번에 한 작업. 구조 변형 `variant` |
| `workload.py` | S0 대조 · S1 백그라운드 적체 + FG · S2 연속 스트림 + FG. seed 개발 1–10 / 검증 51–60 / 독립 61–65 |
| `policies.py` | 고정 3 · 최단 지연 · NPU Manager 근사 · 우리 v0 |
| `kpi.py` | KPI + 보존 검사 |
| `run_compare.py` | 정책 × 시나리오 × 변형 × seed → CSV |
| `tools/` | 원시 추출(읽기 전용) · 스로틀 피팅 · headroom 분석 |
| `docs/` | 산공학회\D1_ondevice\sim\ 문서 미러 |

```
py -m pytest d1sim/tests -q -p no:cacheprovider
py d1sim/tools/extract_traces.py && py d1sim/tools/fit_throttle.py
```
