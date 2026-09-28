# A24 상태 모형의 CG_DC 프로토콜 전이 진단

[오프라인 대시보드](dashboard.html) · [에너지/AP·잔차 SVG](paths.svg) ([PNG](paths.png)) · [요약·지원 경계](summary.json) · [구간별 잔차](blocks.csv) · [누적 에너지](energy_path.csv) · [AP 경로](ap_path.csv)

이 결과는 개발3세션에서 동결한 `energy-ap-state-regimen-fit-v1`의 **실제 CG_DC 블록 일정 조건부 사후 예측**이다. 새 APK DIAG-04 1세션은 프로토콜 전이 자료이며 정식 확인 block이 아니다. 24요청 합성 도착의 종단간 예측이나 정책 선택의 검증 자료가 아니다. AP 시작32.6°C를 입력하고 이후 관측 전류·온도는 예측에 사용하지 않았다. 실제 상태/전환 시각은 사후 입력이므로 예측 대상에서 빠진다.

공유 파일만 있으면 대시보드·곡선·숫자를 열고 확인할 수 있다. 원본에서 다시 적분하려면 이 PC의 다음 **외부 원본**이 필요하다. Git에는 APK·모델·원시 sampler/journal·동결 원본을 넣지 않는다.

- `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json` — SHA-256 `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`, 개발 동결 원본.
- 같은 `energy_ap_state_run_v5`의 개발 `01_*`와 기존 확인 `03_*`의 `artifacts/manifest.json`, `validated.json`.
- `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_run_v4/00_*`의 `validated.json`, `artifacts/manifest.json`, `artifacts/progress.jsonl`, `thermal.jsonl`.

저장소 루트에서 PC 재현(기기 명령 0회):

```powershell
python -m tools.d1_energy_ap_regimen_transition --run C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_run_v4 --development-run C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5 --frozen C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_transition_reproduce_NEW
python -m unittest tools.test_d1_energy_ap_regimen_transition tools.test_d1_arrival_energy_research -v
```

새 빈 출력 폴더에 재현해 기존 공유물을 덮어쓰지 않는다. 원본 해시·동결 SHA·상태 순서·모델/입력/runtime·개발 시작 AP 범위를 검사한다. 동일한 폴더에 HTML·CSV·SVG/PNG가 생성된다. `summary.json`은 계수의 작은 공유 사본을 포함하지만 분석은 위 byte 동결 파일을 요구한다. 전류 raw=mA는 조건부 해석이며 절대 J 정확도 미인증. AP는 Android `Current temperatures from HAL`의 `mName=AP,mType=0`이고 BAT·표면·공식 안전온도가 아니다.

[기술 판단·후속 측정 범위](../../ENERGY_AP_REGIMEN_TRANSFER_PC_20260929.md) · [기존 COLLECT-05 개발/확인 자료](../energy_ap_state_collect05/README.md) · [통합 정책 탐색](../arrival_policy_screen_01/dashboard.html)
