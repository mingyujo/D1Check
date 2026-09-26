# ENERGY-OPERATIONAL-PAIR-01: CC_DG 직렬·병행 운영 비교

## 판정

승인된 `energy_operational_plan_v3`을 한 번 실행하여 개발 2세션과 동결 후 확인 2세션을 모두 완료했다. 네 세션은 각각 동일한 분류 CPU 678건·탐지 GPU 192건을 완료했고, 품질·시간 경계·기록 적격성 검사를 통과했다. 병행은 두 block에서 작업 완료가 약 122~126초 빨랐고 완료시점까지의 **조건부 기기 전체 에너지 추정**이 낮았다. 그러나 AP 최고온도는 병행에서 1.2~1.9°C 높았고, 480초 공통 관측 에너지의 방향은 개발(-36.255J)과 확인(+4.559J)에서 달랐다. 따라서 동일 초기 열 상태의 인과효과, 일관된 운영 에너지 절감, 정책 우월성 또는 시뮬레이터 예측 정확도 PASS는 부여하지 않는다.

## 실행·증거

- 출발 HEAD `9e9668b2fce104c6bb1713f727d3cc543a4c5e77`, 브랜치 `feature/arrival-scheduling-20260923`, 착수 worktree clean. 계획 SHA-256 `4d0bd250029f8fb46c7f989775f63cf75714c4e681522a6c056e58ef0f900ed5`. 후보 APK SHA-256 `86d3fac6504104214fbd4d6b43533a0ec420a051920c2d29ae74ed90c8373e3f`, signer SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`. `-Action Check`는 `PC_READY_DEVICE_UNVERIFIED`를 반환했고 source·manifest·입력·서명 동일성을 검사했다.
- 실행 직전 A24 `SM-A245N` / 하드웨어 serial `R59W802RW5F` / 계약 fingerprint 일치. 배터리 46%, 비충전, 27.5°C, thermal 0, Awake·interactive, 밝기 81·수동 모드 0·화면 timeout 5시간. 설치본은 서명·package가 호환되지만 해시가 달라 전송·설치 각 1회 후 계획 APK와 동일한 설치본 해시를 확인했다. 세션 내 배터리 표본 범위 38~46%, 배터리 온도 26.8~27.4°C, thermal 0; 화면 관측은 세션별 87/87 `sample_pass`다. 드문 host 표본 사이의 상태까지 관찰한 것은 아니다.
- 개발 순서 직렬→병행, 확인 순서 병행→직렬. 개발 두 세션의 적격성을 확인한 뒤 `development_freeze.json` SHA-256 `1dc5766aef4299300acf87fa6d92db0ec54830155d6d8fb02170a901a9f28881`을 확인 자료 열람 전에 동결했다. 확인 자료로 재보정하지 않았다.
- 실제 소비: 4/4세션 완료·실패 0·미시도 0, 작업 3,480/3,480, 적격성 16/16, 진단 3,496/3,496, warmup 32/32, 명시적 추론 3,528/3,528, runtime 16/16, staging 4회·28파일, 전송 1/1·설치 1/1, 재시도·대체·추가 0. 전체 host 경과 3,847.922초(64.132분)/8,640초(144분). 고정 관측 계약 60분. 세션별 앱 `summary`·`cleanup`, host 회수·cleanup, `require_stopped` 및 종료 thermal 0이 확인됐다.
- 외부 원본·receipt·동결 설정: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_run_v1/`. registry: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_registry/ENERGY-OPERATIONAL-PAIR-01/completed.json`. 이 계획은 소비 완료이며 재실행하지 않는다. 공유용 세션 요약은 [sessions.csv](results/energy_operational_pair_01/sessions.csv). 원본·APK·모델은 Git에 포함하지 않는다.

## 동일 경계의 결과

`J`는 A24 raw 전류의 **mA 해석 가설**로 적분한 기기 전체 값이다. 절대 에너지 정확도는 미인증이다. 각 block의 정책별 독립 세션은 하나이고 870개 요청·약 1Hz 센서 표본을 독립 반복으로 세지 않는다. 병행 겹침은 CPU/GPU **host API 호출 구간**이며 GPU kernel 동시 실행의 증거는 아니다.

| block·순서 | 조건 | 완료 870건까지 초 | 완료까지 J | 480초 공통창 J | 준비→냉각 관측 J¹ | baseline AP / 부하 시작 / 부하 최고 / 냉각 종료 °C | host API 겹침 초 |
|---|---|---:|---:|---:|---:|---|---:|
| 개발 1 | 직렬 | 326.085 | 578.384 | 758.842 | 1268.557 | 27.7 / 27.7 / 31.2 / 27.5 | 0 |
| 개발 2 | 병행 | 203.628 | 398.583 | 722.588 | 1210.631 | 27.5 / 27.3 / 32.4 / 27.8 | 11.827 |
| 확인 1 | 병행 | 202.755 | 410.482 | 730.999 | 1207.745 | 27.8 / 27.9 / 32.8 / 28.0 | 11.302 |
| 확인 2 | 직렬 | 329.073 | 553.822 | 726.440 | 1207.008 | 27.8 / 27.6 / 30.9 / 28.2 | 0 |

¹ 준비→냉각은 runtime·warmup 뒤 고정 resident 준비부터 공식 baseline·부하·남는 공통창·냉각 끝까지의 **관측 coverage 에너지**다. 각각 미계측 0.423/0/0.059/0.055초가 있어 완전한 적분값이 아니다. 더 넓은 세션 시작→마지막 앱 이벤트 관측값은 1292.166/1233.641/1231.933/1234.056J이며 미계측 0.737/0.242/0.383/0.316초가 남는다. 초기 gate 이전과 host cleanup 이후는 측정하지 않았으므로 전체 운영 에너지 합계를 만들지 않는다.

| 병행−직렬 | 완료시간 | 완료까지 J | 공통창 J | 준비→냉각 관측 J | AP 최고온도 | 긴급 output_ready P95 | 일반 persist_complete 평균 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 개발 | -122.456초 (-37.55%) | -179.801J (-31.09%) | -36.255J (-4.78%) | -57.926J (-4.57%) | +1.2°C | -121.885초 | +0.447초 |
| 확인 | -126.319초 (-38.39%) | -143.341J (-25.88%) | +4.559J (+0.63%) | +0.737J (+0.06%) | +1.9°C | -126.249초 | +0.365초 |

각 세션의 정상 요청 완료 678/678, 긴급 완료 192/192, 실패·미완료·미확인 요청 0이다. 긴급 P95는 192개 **완료된 요청의 세션 내 경험 분위수**다. 서비스 deadline이 이 고정 작업 계약에 정의되지 않아 기한 위반율과 서비스 PASS는 산출하지 않는다. 긴급 P95의 직렬/병행 절대값은 개발 314.900/193.015초, 확인 317.967/191.719초다. 일반 평균은 개발 54.276/54.723초, 확인 54.160/54.526초다. 실제 UI 끊김·대화형 서비스 효과는 측정하지 않았다.

기기 전체 에너지에서 **각 세션의 resident baseline 평균전력**을 뺀 추가 소비 추정은 완료까지 개발 직렬/병행 199.686/171.353J, 확인 193.010/178.079J다. 공통창은 개발 201.301/186.899J, 확인 200.086/180.810J다. baseline 전력이 조건별로 달라 이 값은 동일한 외부 idle 기준의 절감량이 아니다. 더 빠른 병행은 480초 창에서 작업 후 대기가 길다(개발 276.365초, 확인 277.195초 대 직렬 153.932/150.924초). 이 대기 비용을 공통창에서 제외하지 않았다.

설치 단계의 host 경과는 44.453초, 세션별 host 경과는 946.031/947.985/961.391/947.969초다. 세션 시작 뒤 마지막 앱 이벤트까지의 표본 구간에는 초기화·gate·warmup 일부가 **관측된 범위에서만** 포함된다. 설치, 앱 기록 전 host gate, 마지막 이벤트 뒤 host 회수·cleanup의 에너지는 계측되지 않았고 추정값도 만들지 않았다. host와 앱의 서로 다른 시계를 빼서 빈 구간 시간을 산출하지 않는다. 그러므로 위 `준비→냉각`과 `세션 prefix` 값은 전체 운영 에너지가 아니다.

AP 경로는 고정 준비 시작→끝, baseline, 부하, 작업 후 대기, 냉각을 구분해 원본 `validated.json`의 `phases`에 저장됐다. 준비 시작 AP는 개발 직렬/병행 29.4/29.2°C, 확인 병행/직렬 29.1/29.1°C였고, 공식 baseline 중앙값은 27.7/27.5/27.8/27.8°C다. 동일한 AP 값이 내부 열 상태 동일을 보장하지 않으며, 개발·확인 모두 날짜·순서·잔열 교란을 한 반복으로 분리할 수 없다.

## 동결 확인·적용 범위

확인 세션의 개발 동결 대비 단계 평균전력 오차(확인−개발, W)는 병행 준비/baseline/부하/대기/냉각 `-0.033/+0.030/+0.067/-0.016/-0.049`, 직렬 `-0.046/-0.065/-0.091/-0.029/-0.089`다. 같은 단계 AP 종료온도 오차(°C)는 병행 `+0.4/+0.5/+0.4/+0.5/+0.2`, 직렬 `-0.1/0/-0.1/+0.3/+0.7`이다. 사전 정확도 허용폭이 없으므로 오차는 **기술값**이지 PASS가 아니다. 관측 최대값을 안전 상한이나 population tail로 쓰지 않는다.

PC 시뮬레이터에는 이 CC_DG·resident·고정 작업묶음·관측 경계의 **사후 trace 재생과 조건부 초기 모형 입력**으로만 연결 가능하다. 이번 실행만으로 시뮬레이터의 기본 계수·병행 허용 범위를 바꾸지 않았다. 분류 GPU＋탐지 CPU 역방향, 다른 모델·입력·priority·부하·offset/duty, 반복 냉각, 동시 실행의 열 인과계수, 현재 정책의 에너지 최적화와 실제 서비스 제약 충족은 여전히 미측정/미검증이다. 이번 원본으로 독립 예측 검증을 선언하지 않는다. 기존 CAL-03 40개 동결값·20개 null·기존 FAIL·부분 결과·종료 계획은 변경하지 않았고 `experiment_ready=false`를 유지한다.

## 재현

이미 소비된 계획의 `-Action Run`은 다시 실행하지 않는다. 원본 판독은 다음처럼 **읽기 전용**으로 한다. `validated.json`은 실행기가 원본 이벤트·품질·전류·온도 경계를 검증해 생성한 세션별 결과다.

```powershell
$root = 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_run_v1'
Get-Content "$root/FINAL_RECEIPT.json" -Raw | ConvertFrom-Json | Select-Object status,sessions,diagnostic_requests,warmup,explicit_inference,elapsed_seconds,experiment_ready
Get-FileHash "$root/development_freeze.json" -Algorithm SHA256
Get-ChildItem $root -Directory | Where-Object Name -Match '^0[0-3]_' | ForEach-Object {
  $v = Get-Content (Join-Path $_.FullName 'validated.json') -Raw | ConvertFrom-Json
  [pscustomobject]@{phase=$v.phase;condition=$v.condition;work=$v.work_requests;seconds=$v.metrics.equal_work.duration_s;work_J=$v.metrics.equal_work.full_energy_j;fixed_J=$v.metrics.common_window.full_energy_j;peak_AP=$v.phases.load.ap_peak_c;overlap_s=$v.validation.host_api_overlap_ns/1e9}
}
```

분석 파일: 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_operational_analysis_v1/FINAL_REPORT.md`; 공유 CSV는 위 링크. 보고서와 CSV는 새 실측이나 재보정 없이 회수된 원본에서 파생했다.
