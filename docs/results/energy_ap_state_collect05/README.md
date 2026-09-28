# COLLECT-05 부분 진단 공유물

[결과 보고서](../../ENERGY_AP_STATE_COLLECT05_RESULTS_20260928.md) · [timeout PC 감사와 후속 계획](../../ENERGY_AP_CONFIRM_FOLLOWUP_PC_20260928.md) · [ADB 집계 JSON](adb_audit.json) · [요약 JSON](summary.json) · [확인 1세션 그림](confirmation_path.svg) ([PNG](confirmation_path.png)) · [공통창 에너지 CSV](confirmation_energy_path.csv) · [AP 경로 CSV](confirmation_ap_path.csv)

개발3·확인1 완료 뒤 다섯 번째 시도에서 중단된 자료다. CSV/그림은 **확인 DC_DG 한 세션의 사후 부분 진단**이며 완성된 독립 검증이나 임의 도착 정책 시뮬레이터 적격성이 아니다. 에너지 J는 A24 raw=mA의 조건부 해석이고 절대 정확도는 미인증이다. 원본·APK·모델은 Git에 없다.

```powershell
python -B -m tools.d1_energy_ap_collect05_partial --run-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5' --output docs/results/energy_ap_state_collect05
```

재생성에는 외부 `energy_ap_state_run_v5`의 `FINAL_RECEIPT.json`, `development_freeze.json`, 완료 4세션의 `validated.json`이 필요하다. 스크립트는 원본을 쓰지 않고, 저장된 확인 오차와 재계산 오차가 다르면 중단한다.

```powershell
python -B -m tools.d1_energy_ap_adb_audit --run-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5' --output docs/results/energy_ap_state_collect05/adb_audit.json
```

ADB 집계는 host 명령 지연과 종류만 다룬다. 개별 transport/원격 경로를 공유 JSON에 넣지 않으며 client 대기시간을 기기 소비 에너지로 환산하지 않는다.
