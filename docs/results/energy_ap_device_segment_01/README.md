# ENERGY-AP device segment diagnostic: PC 준비 자료

- 계약: [ENERGY_AP_DEVICE_SEGMENT_PC_20260928.md](../../ENERGY_AP_DEVICE_SEGMENT_PC_20260928.md)
- 외부 계획: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_device_segment_diag_plan_v3\collection_plan.json`
- 계획 SHA-256: `5ec12e31b90a17f6f56fdd38d077f0b244e4a19c2bf2ba99635343570ca09068`
- manifest SHA-256: `6d33cfc82ffd17422f6123d4f232f681120cb4f4ed2b6b8e429fdf2787d710d5`
- 외부 APK: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_autonomous_build_v1\build\_benchmark-runner\outputs\apk\modelProbe\benchmark-runner-modelProbe.apk`
- APK SHA-256: `7589b96f18076c4bf7d178f3ae58c45c4e88348ef7f797ec5de60699d2e9c00d`; 서명은 기존 프로젝트 signer와 일치한다. APK/키/모델은 공유하지 않는다.
- 새 실행 출력: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_device_segment_diag_run_v3` (미생성)
- 소비 registry: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_collection_registry\ENERGY-AP-DEVICE-SEGMENT-DIAG-03` (미생성)

PC `Check` (기기 명령 0회):

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check
```

승인 전에는 `Run`을 호출하지 않는다. 제한된 진단과 나중의 read-only 회수는 각각 별도 승인 대상이다. 후자는 원 host의 종료·원 session manifest·앱 terminal 증거를 요구하며 세션을 재시작하지 않는다.

별도 진단 승인 후 실행 명령:

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved
```

연결 실패 후 read-only 회수가 별도 승인된 경우에만 사용할 명령:

```powershell
python -B -m tools.d1_energy_ap_autonomous_diag recover-stopped --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_plan_v3/collection_plan.json' --adb 'C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe' --expected-sha 5ec12e31b90a17f6f56fdd38d077f0b244e4a19c2bf2ba99635343570ca09068 --output 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_run_v3_read_only_recovery' --approved
```

`recover-stopped`는 원 host의 종료 확인·동일 기기·원 manifest·앱 terminal 자료가 없으면 성공 판정을 하지 않으며, 재호출은 별도 claim으로 막는다.
