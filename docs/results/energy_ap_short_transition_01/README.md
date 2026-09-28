# A24 CC_DG 짧은 상태 전환 1세션

[대시보드](dashboard.html) · [에너지/AP 경로 SVG](paths.svg) ([PNG](paths.png)) · [판정 JSON](summary.json) · [블록 CSV](blocks.csv) · [상태 CSV](states.csv) · [에너지 CSV](energy_path.csv) · [AP CSV](ap_path.csv)

별도 `ENERGY-AP-SHORT-TRANSITION-DIAG-01`의 10~20초 상태 블록 36개와 공통창 말미의 완료 후 유휴를 표시한다. 개발 3세션 동결 모형은 변경하지 않았다. **시작 AP 32.3°C가 동결 모형의 개발 관측 하한 32.5°C보다 낮아 모형 예측은 unsupported**다. 저장된 점선과 차이는 식을 범위 밖에서 계산한 탐색 외삽이며 예측 오차 검증이나 사후 범위 확대가 아니다. 같은 모델/입력이라도 APK·세션 제어·host 관측이 다른 프로토콜 전이 자료다. 임의 도착·1초 안팎의 요청·정책 절감·배터리 잔량/수명에는 적용하지 않는다.

원본과 재현 의존성은 Git 밖에 있다.

- 계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_short_transition_plan_v1/collection_plan.json`, SHA-256 `16fd8b08dd0f8ec3b5ea8909ddf84434c5406f7f69cbf215cafb1f3d2e50913d`.
- 원본: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_short_transition_run_v1/FINAL_RECEIPT.json` 및 동일 폴더의 `00_*` 세션 원본·`host_checkpoints`·`host_commands`.
- 기존 개발 동결 파일: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json`, SHA-256 `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`.

저장소 루트에서 PC 재현(기기 명령 0회):

```powershell
python -B -m tools.d1_energy_short_transition_report --run C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_short_transition_run_v1 --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_short_transition_plan_v1/collection_plan.json --frozen C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_short_transition_reproduce_NEW
```

공유 파일만으로 화면·CSV를 열 수 있다. 원본 재적분에는 위 외부 파일이 반드시 필요하며 APK·키·모델·원시 journal은 Git에 포함하지 않았다. 전류 raw=mA 해석은 조건부이고 J 절대 정확도는 미인증이다. AP는 `mName=AP,mType=0` 센서이며 BAT/표면 온도나 공식 안전 한도가 아니다. 센서 표본 수를 독립 세션 수로 세지 않는다.
