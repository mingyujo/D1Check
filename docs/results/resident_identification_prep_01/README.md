# 에너지·AP 식별/확인 PC 준비

**2026-10-09 실행 후 상태:** 사용자승인으로plan_v3는소비·종료됐다. 개발4 정상/동결 AP 상한 gate 실패/확인4 미시도. [실행결과](../../RESIDENT_IDENTIFICATION_RESULTS_20261009.md). 아래 준비 당시 미승인/미소비 기록과해시는역사적근거로보존한다. 재실행하지않는다.

[한국어 계약·예산·승인후명령](../../RESIDENT_IDENTIFICATION_PREP_20261008.md) · [분석계약v2](analysis_contract_v2.json) · [8개입력](roster.csv) · [작은계획요약](plan_summary.json) · [검증](verification.json).

현재상태는 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`,미승인·미소비다. 최종실행대상은 `energy_ap_resident_identification_plan_v3` 하나이며v1/v2는소비되지않은PC초안이다. 기존FAIL/stopped계획과구분한다. 새실측결과·성능그래프가없다.

개발4개는동일4resident/60초부하·90초idle의A/B/B/A,확인2개는다른순서30초부하,나머지확인2개는기존Arrival경로96/192혼합요청이다. 계수식별·개발예측gate·hash동결후에만확인으로진행한다. 현재모형/기본/RL/strict/experiment_ready=false를교체하지않는다.

PythonPC 검증:

```powershell
python -B -m unittest tools.test_d1_resident_identification_plan tools.test_d1_energy_host_failure -v
```

Android관련검증은기존SDK/JBR와프로젝트Gradle환경에서 `:benchmark-runner:testModelProbeUnitTest --tests com.example.d1check.benchmarkrunner.EnergyResidentIdentificationTest --tests com.example.d1check.benchmarkrunner.EnergyStateCalibrationTest --tests com.example.d1check.benchmarkrunner.ArrivalRecordedReplayTest`를사용했다. APK는기존격리 `tools.d1_arrival_timing_calibration_device.package`로빌드하고기존프로젝트키의인증서를대조해서명했다. 키/APK/모델을복사·공유하지않는다.

Check는기기명령0회다. 외부계획은모델/입력/참조출력/툴체인/APK 해시에묶이므로정확한외부파일의존성이있다. 공유검증에는필요한source/명령/도메인예산만기록하며기기fingerprint·하드웨어serial·원PID는제외한다. 기기연결복구·추가회수·새계획실행을자동수행하지않는다.
