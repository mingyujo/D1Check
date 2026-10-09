# LOAD_SLOW 명시적 AP 진단 경로

[적용 범위·차단·기존 악화·검증](../../AP_TAIL_SCOPE_PC_20261009.md) · [결과 화면](index.html) · [고정 계약](scope.json).

- 최종 PC 산출물: `run_v4`. 개발4＋새 장시간2의 등록된 실행 맥락만 허용한다. 기존29의 도착·이력 대조와 모든 strict/RL/정책 순위 사용은 이 경로에서 차단한다.
- 기존 숫자가 계산된 것, 맥락 일치, 독립 확인, 정책 차이 판별은 서로 다르다. 원식·기본 시뮬레이터·RL·strict·experiment_ready=false는 유지한다.
- 개선·악화35개 오차를 재사용했고 악화13개를 숨기지 않았다. 추가 물리계수 fit·환경 실행·기기 명령0.

```powershell
python -B docs/results/ap_tail_scope_01/run_example.py --opt-in --output output/ap_tail_scope_LOAD.json
python -B -m unittest tools.test_d1_ap_tail_scope -v
```

예제는 이미 수집한 실제 LOAD_A 일정이다. 현재 기기 확인이나 새 측정이 아니다. pre-only 초기화와 실제 일정만 예측에 사용하고 이후 관측 AP는 오차 계산에만 사용한다. 원6 manifest가 필요한 전체 검사 재현 명령은 보고서를 따른다.
