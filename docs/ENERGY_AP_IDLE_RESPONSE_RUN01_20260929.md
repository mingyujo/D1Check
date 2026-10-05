# A24 저온 resident AP 반응: 개발 1세션·동결·확인 1세션 실행 결과

**판정:** 승인한 `ENERGY-AP-IDLE-RESPONSE-01`을 한 번 실행해 두 세션 모두 `completed_descriptive_only`와 자료 적격성을 얻었다. 개발 후 추정 **절차**는 확인 전에 동결했다. 별도 후보는 원래 동결식의 저온 절대 AP 외삽 오차를 크게 줄였지만, 확인 세션의 마지막 부하 후 AP가 한동안 높아졌다가 돌아오는 반응을 재현하지 못했다. 정확도 PASS·정책 선택 적격성·strict 지원 확대는 **미판정**이다. 동결 모형·기존 사후 후보·원자료·FAIL·`experiment_ready=false`는 보존한다.

## 동일성, gate, 소비

- 계획 SHA-256 `b6622fcad140146bf92460c99637d2224450aaf79f5648645675df1b730114ed`. [PC 계획 계약](ENERGY_AP_IDLE_RESPONSE_PLAN_PC_20260929.md)의 두 manifest와 서명 APK SHA-256 `747ce77e07c7c79f7c7d912d0ff749cf230e0c0483f4a160784fe549043f6180`을 Check했다. 실행기의 현재 A24/fingerprint·설치본 서명/패키지/버전·환경 gate가 통과했다. 동일 설치본이어서 APK 전송·설치 **0**. 현재 transport 하나에 후속 명령을 고정했고 자동 재연결·설정 변경·추가 warmup을 하지 않았다.
- 비충전 BAT는 preflight/개발 68%·27.7°C, 확인 직전 68%·28.4°C였다. 이는 AP와 별개의 환경 기록이다. 두 공식창 시작 HAL numeric AP는 **28.1°C, 28.7°C**로 사전 등록한 저온 연구 층(<32.5°C)에 속한다. 이를 안전 인증이나 기존 동결 모형 지원 범위로 해석하지 않는다.

| 항목 | 승인 상한 | 실제 확인 |
|---|---:|---:|
| 세션 | 개발 1＋확인 1 | 각 1 완료 |
| 본 요청 / warmup / 명시적 추론 | 48 / 16 / 64 | 48 / 16 / 64 |
| runtime / staging | 8 / 2회·14파일 | 8 / 2회·14파일 |
| 설치본 host pull / APK push / 설치 | 각 ≤1 | 1 / 0 / 0 |
| ADB 명령 | ≤6,600 | **총 1,627**: 실행기 1,626＋선택 전 `devices -l` 1회 |
| 총 시간 | ≤2,120초 | 628.032초(설치 확인·세션 간 대기·회수·cleanup 포함) |
| 재시도·대체·추가 | 0 | 0 |

세션당 계획 고정 관측은 baseline30＋공통120＋cooling60=210초로, 전체 시간 예상이나 보장은 아니다. 두 세션 모두 요청 24개가 끝났고 공통창 미완료 0개다. 진행 기록에는 각 runtime4·warmup8·lane 해제24가 확인되며 요청별 시작/반환/output_ready/persist/worker_release/lane_available 경계를 회수했다. 개발 246.844초, 확인 240.906초는 각 세션의 host 시작부터 적격성 완료까지의 경과시간이다. ADB client 기록에는 앱 staging push 14회가 있고 **APK push는 없다**. 명령 결과의 비정상 exit 6건은 계획상 존재·부재 조회 등과 함께 원본에 남겼으며, 전체 실행기는 성공 receipt를 기록했다. 명령 무응답/timeout은 관측되지 않았다.

앱 `cleanup.json`은 두 세션 모두 `completed`, sampler 실패 `null`이다. 설치 확인 단계와 각 세션 후 host는 대상 앱을 force-stop하고 `ps -A`로 프로세스 부재를 확인했으며 host cleanup은 모두 `completed`다. **앱 정상 cleanup**, host force-stop, 프로세스 부재는 서로 다른 증거다. 완료 receipt SHA-256 `b5e3d15022978d4cd4610957d4eafcd63526256ff8d16e9c9f2d8caf82d648ac`; 실행 출력과 registry는 소비·종료 상태이며 재실행하지 않는다.

## 개발→동결→확인의 자료 경계

동결 원본 `development_freeze.json` SHA-256은 `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`이다. 개발은 부하 전 HAL AP **26표본·64.425초**만으로 세션별 유효 유휴 기준 `E=27.729°C`를 산출했고, 이 절차·분석 코드·구조·개발 적격성 기록을 **2026-09-29 14:31:37 UTC**, `ap_model_freeze.json` SHA-256 `8507adc10485940c36853786ba39a4f42439a9fbd3d71a5da1c7d55e2cbc7ec5`로 확인 시작 전에 고정했다. 확인은 다른 두 묶음 순서의 부하 전 **26표본·64.305초**에 똑같은 추정식을 적용해 자기 세션의 `E=28.348°C`를 입력받았다. 두 `E`는 주변 온도도 숨은 열 상태도 아니다.

예측은 **실행 후 PC에서** 실제 lane 일정, 공식창 시작 AP, 각 세션의 부하 전 AP로만 만든 *실제 일정 조건부* 계산이다. 부하 후 AP·전류는 예측 입력이 아닌 비교 목표다. 시작 전에 미래 일정·응답까지 예측한 온라인 정책 평가가 아니다. 원래 동결식도 같은 AP 표본과 실제 일정에 적용했으며 저온 시작과 짧은 전환 때문에 **외삽 진단**으로만 표시했다. 후보의 확인 결과를 보고 계수·β·유휴 기준 추정 구간을 조정하지 않았다.

| AP 판독, 첫 dispatch 이후~cooling 종료의 동일한 54표본/세션 | 개발 | 확인 |
|---|---:|---:|
| 공식창 시작 AP / 부하 전 유효 기준 | 28.1 / 27.729°C | 28.7 / 28.348°C |
| 원래 동결식 AP MAE / 최대 절대오차 | 6.038 / 6.629°C | 5.461 / 6.103°C |
| 별도 후보 AP MAE / 최대 절대오차 | 0.488 / 0.849°C | 0.418 / 0.851°C |
| 원래 동결식 최고 AP 부호 오차 | +5.378°C | +5.203°C |
| 별도 후보 최고 AP 부호 오차 | −0.503°C | −0.621°C |
| 마지막 lane 해제 후 관측 AP 변화 | −1.200°C | **0.000°C** |
| 같은 구간 후보 AP 변화 | −1.039°C | **−0.719°C** |
| 공통 120초 관측 에너지 | 135.618J | 144.565J |

두 모형의 **시작 대비 AP 변화량 오차 MAE는 같은 시작 AP를 빼므로 각각 위 절대 AP MAE와 수치가 같다**. 확인의 마지막 lane 해제는 공식창 시작 후 72.053초다. 그 후 첫 AP 표본은 73.886초·28.8°C, 관측 최고 29.7°C 표본은 76.516초, 마지막 178.111초는 28.8°C다. 후보는 해당 첫·마지막 표본에서 29.073→28.354°C로 단조 냉각을 예측한다. 즉 **총 MAE 개선에도 부하 후 지연된 AP 상승 형태는 남는다**. 약 2.4–3.3초의 AP 관측 간격상 4.46초는 마지막 lane 해제부터 *관측 최고 표본까지*의 간격이지 내부 열 지연의 정확한 시간상수가 아니다. 개발 마지막 부하 후에는 관측·후보 모두 냉각 방향이었다. 확인 1세션으로 독립 예측 오차 수치는 얻었지만 조건 간 변동성과 정책 차이의 판별력은 추정할 수 없다.

실제 120초 lane 상태는 개발 `detection_CPU` 9.550초, `classification_GPU` 0.159초, `CG_DC` 1.678초, idle 108.614초; 확인은 각각 10.613·1.004·0.847·107.536초다. 병행 길이는 AP/전류 센서 해상도보다 짧아 이 자료로 독립 병행 전력 계수를 식별하지 않는다. 두 세션의 에너지 총량 차이는 부하 순서·초기 조건이 다른 *서술적 관측*이며 정책 절감량이 아니다. A24 raw 전류=mA 해석과 절대 에너지 정확도 미인증을 유지한다. AP 비교 54표본/세션의 최대 간격은 개발 3.300초·확인 3.325초이며, 원래 센서의 내부 갱신 주기를 이 숫자로 확정하지 않는다.

원래 실행기 `ap_analysis/summary.json`의 `work`는 첫 dispatch부터 마지막 lane 해제까지의 **포괄 구간**이다. 확인에서 두 부하 사이 약 22초의 실제 resident idle까지 포함하므로, 별도 사후 PC 판독은 실제 lane 상태로 `occupied` 5 AP표본, `idle_between_pulses` 9, `resident_idle_after_work` 40으로 나눴다. 기존 예측·계수·원본 분석은 수정하지 않았다. 개발의 대응 표본은 occupied5·postwork idle49다. 이 분리는 센서 표본을 독립 세션으로 세는 분석이 아니다.

| 실제 phase의 AP MAE, 원래 동결식 → 후보 | 개발 | 확인 |
|---|---:|---:|
| 점유 부하 | 5.970 → 0.508°C (5표본) | 5.394 → 0.183°C (5표본) |
| 두 묶음 사이 유휴 | 해당 없음 | 5.060 → 0.437°C (9표본) |
| 마지막 부하 후 유휴 | 6.045 → 0.485°C (49표본) | 5.560 → 0.442°C (40표본) |

후보의 확인 평균 부호 오차(예측−관측)는 부하 −0.049°C, 묶음 사이 유휴 −0.405°C, 마지막 유휴 −0.429°C다. 이 phase는 **표본 시각의 lane 상태**로 붙였으며, 직전 상태의 지연된 열 반응을 그 phase의 고유 계수로 귀속하지 않는다. 작은 부하 표본 수와 AP 양자화 때문에 단독·병행 순간의 열 계수를 이 표에서 따로 식별하지 않는다.

## 지원 범위, 근거, 재현

- 얻은 근거: 같은 A24·APK·resident 구성의 사전 등록 저온 층에서 **부하 전 AP 입력을 허용한** 단순 후보가 두 다른 짧은 부하 순서의 절대 AP를 원래 동결식보다 가깝게 계산했다. **확인의 작업 후 방향/형태는 미재현**. 허용오차가 사전 정당화되지 않아 정확도 PASS는 `null`; simulator 기본·strict 마스크·정책 선택은 그대로다. 고온 개발 층, 다른 초기 조건, 임의 도착, 처리시간 열 피드백, 숨은 열 상태, 주변 온도, 병행 W는 여전히 지원하지 않는다.
- 원본: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_idle_response_run_v1/FINAL_RECEIPT.json`, 두 `00_…`/`01_…` 세션의 `artifacts`, `thermal.jsonl`, `validated.json`, `ap_analysis`, `host_cleanup.json`, `installation`, `host_commands`; 동결은 같은 원본 폴더의 `ap_model_freeze.json`. 원본·소비 registry·기존 동결 모형은 편집하지 않았다.
- 공유 가능한 [요약·AP CSV·SVG/PNG 및 재현 안내](results/energy_ap_idle_response_01/run01/README.md). 그림은 개발/확인별 실제 AP·원래 동결식·후보와 **실제 lane 점유**, 시간별 부호 있는 잔차를 보여준다. 누락값을 0으로 채우지 않았다.

```powershell
python -B -m tools.d1_ap_idle_response_readout `
  --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_idle_response_plan_v1/collection_plan.json' `
  --run-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_idle_response_run_v1' `
  --frozen 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json' `
  --output 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_idle_response_readout_reproduction_v1'
```

PC 보조 판독은 저장된 후보 AP 경로를 동결 추정식으로 재계산해 일치시켰고, 실제 lane 구간으로 phase를 다시 분류했다. 새 출력 경로에서 `summary.json`·`ap_paths.csv`가 공유본과 **byte 단위 동일**하게 재생성됐다. 이는 계측·장시간 기기 안정성·정확도 합격의 증거가 아니다. **다음 PC 작업 하나:** 이번 두 세션의 lane 해제 이후 AP 최고 표본 지연과 표본 갱신 간격을 기존 장구간 자료와 대조해, 단일 AP 상태 후보의 남은 방향 오류가 열 이력 항을 요구하는지 판정한다. 새 실측·재보정은 자동으로 하지 않는다.
