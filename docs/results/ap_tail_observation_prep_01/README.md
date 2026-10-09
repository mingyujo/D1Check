# 긴 resident C0·부하 회복: PC 준비, 미승인·미소비

[한국어 계약·예산](../../AP_TAIL_OBSERVATION_PREP_20261009.md) · [준비 화면](index.html) · [입력표](roster.csv) · [계획·소스 SHA](plan_summary.json) · [검증](verification.json).

C0→LOAD_A 한 block, 각 baseline120/common600/cooling1920초. 새 측정이 아니라 계획이다. 기존 동결식·주후보 LOAD_SLOW·원인 대조 CLOCK_SHIFT를 사전에 고정했다. 적합0·기본/RL/strict/experiment_ready=false 유지. 긴 C0는 공통 시각 드리프트와 부하 의존을 구분할 정보를 주며 물리 원인·τ 식별을 보장하지 않는다.

## PC 재현

```powershell
python -B -m unittest tools.test_d1_ap_tail_observation_plan.TailPlanTests -v
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Check
```

Run은 별도 승인 후에만 가능하며 [정확한 명령·현재 기기 gate](../../AP_TAIL_OBSERVATION_PREP_20261009.md)를 따른다. 최종 SHA `e4aec38289084840df0a54a9c2322354bda1e6c83388bd47e85a7d95641e6f68`. plan_v1은 미소비 PC 초안으로 보존하며 실행하지 않는다.

APK는 기존 프로젝트 서명이다. 개인 PC의 입력/모델/대표 이미지/참조 출력/SDK 도구가 Check의 외부 의존이므로 공유 요약만으로 다른 PC에서 실측을 실행할 수 있다고 주장하지 않는다. 모델·APK·키·대용량 원본·기기 식별정보는 Git에 넣지 않는다. 긴 회복 전력의 끝 미관측은 전체J/오차 null과 coverage로 보존한다.
