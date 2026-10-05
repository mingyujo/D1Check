# CPU_URGENT/B2 기록 일정 직접 비교 — 2026-10-02

## 실행 전 고정

사용자는 연결·실측·필요한 수정과 후속 진행을 승인했다. 기존 모형/진단을 반복하지 않고 저장 queue/seed201/실현 간섭1.5의 CPU_URGENT와 B2_PC를 **CPU→B2→B2→CPU** 순서로 비교한다. 원래 예정 도착0–4.6초·backend·dispatch 하한을 유지하고 실제 실행시간을 강제하지 않는다. 미래 일정이 주어진 재생이며 온라인 정책/종단간 모형 검증이 아니다.

두 정책당2세션은 순서를 뒤집은 두 기술적 비교쌍이다. 사전 쌍은(0,1),(3,2); B2−CPU 각각·평균·범위를 보고하며 통계적 정밀도나 우월성 PASS를 부여하지 않는다. 다른 초기 AP/배터리/이력은 함께 기록한다. 결과를 보고 계수를 맞추거나 유리한 창을 고르지 않는다.

기존 설치 APK는 B2 배정만 허용했다. 새 opt-in `recorded-policy-comparison-v1`은 CPU_URGENT의 두 작업 CPU 배정과 기존 B2 배정을 명시적으로 구분한다. 기존 버전의 B2 검사는 보존했다. 공통 실행 엔진의 과거 태그 RECORDED_B2_REPLAY_V1은 호환 태그이며 실제 배정 정책은 source_policy다. 4세션 모두 같은 새 프로젝트 서명 APK/4resident/8warmup을 사용한다. 계측·lifecycle·AP observe-v2·worker·cleanup 의미는 유지한다.

연결은 사용자 제공 정보로 1회 페어링·지정 IP 연결에 성공했다. 현재 IP와 mDNS 두 transport가 있어 새 opt-in만 명시 transport의 현재 온라인/model/fingerprint를 확인한다. 이후 명령은 같은 transport에 고정하며 다른 연결을 끊거나 자동 전환하지 않는다. 사전 연결 기록의 SM_A245N 대 SM-A245N 비교는 PC 표기 비교 오류였으며 원문 getprop의 SM-A245N·hardware·fingerprint는 기대값과 일치한다. 원본 false 판정도 수정하지 않고 이 정정을 분리한다. 무선 원인 해결/장시간 안정성 보장은 아니다.

## 정확한 예약과 중단

| 항목 | 상한 |
|---|---:|
| 세션/본 요청/warmup/총 추론 | 4 / 96 / 32 / 128 |
| runtime/별도 적격성 추론 | 16 / 0 (8warmup에 품질 확인 포함) |
| staging/파일 | 4 / 28 |
| 설치본 pull/APK push/설치 | 각1 (동일본 생략) |
| 고정 baseline/common/cooling | 세션당30/120/60초, 합840초 |
| 설치 preflight 포함 예약 | 600초 |
| 세션 stage/poll/recovery/cleanup | 120/485/50/45초 = 700초 |
| 세션 사이 대기 | 90초×3 |
| 전체 Run | 600+700×4+90×3 = 3,670초 |
| ADB | 13,000; 세션별 누적 관찰한도3,200·정리100명령 예약 |
| 재시도/대체/추가 | 0 |

ADB 산식의 보수적 회수 가능 슬롯은4×3,200+200이다. 세션 poll485초에서 listing은 sleep0.25초 기준≤1,940회, thermal 묶음은≥2초 간격×3명령≤729회, screen≥10초≤49회이며 실제 직렬 명령 지연 때문에 대체로 더 적다. warmup/승인/staging/회수/cleanup은 남은 슬롯과 전역 cap을 공유한다. 슬롯이나 회수 예약이 부족하면 중단한다. 최대시간은 예상시간/완주 보장이 아니다. 별도 연결 준비7명령 timeout합82초는 Run 밖 기록; 누적 작업 예약3,752초·13,007명령, PC 빌드/사용자 대기 공백은 별도다.

기존 비충전/배터리/BAT/thermal/화면/memory/품질 gate를 유지한다. AP 개발 하한은 실행 gate가 아니며 numeric AP 유효성·신선도는 검사한다. 새 실행에서 확인 전까지 현재 환경은 미검증이다. Activity를 떠나는 명령/설정 변경/자동 재연결은 없다. 첫 실패는 해당 계획 종료·증거 보존·단일 정리; 같은 plan 재실행 없음. 사용자의 수정 허용은 기준 완화나 무원인 반복을 뜻하지 않는다.

## 판독 범위

동일120초 전체 전류·전압 적분 J(raw=mA 조건부, 절대 정확도 미인증), 초기/최고/변화 AP, 실제 lane 점유와 전체24분모의 urgent output_ready/normal persist_complete 응답·deadline 성공을 판독한다. 결측은 null이다. 원래 동결 상태식은 필요할 경우 짧은 전환 진단에만 사용하며 기본/strict 지원을 확대하지 않는다. 부하 전55초 관측을 요구하는 preload 후보는 이번 즉시 부하 일정에 적용하지 않는다. 동적 모형의 미지원 AP 최고/후기·정책 비용 예측을 새 관측과 혼동하지 않는다. experiment_ready=false 유지.

## PC 검증

관련 Python13검사: 저장 두 일정·예산·한 transport 고정/선택 대상 소실 차단·4세션 실제 host 진입 fake·첫 poll/설치 실패·중복 정리 방지·소비 재실행 차단·기존 bundle 대표 회귀 통과. Android10검사(기존 lifecycle callback3, contract3, replay4) skip0/failure0. 기존 완료 원문으로 새 판독/그림 경로를 실행해145.621340369J·24요청·전체 상태120초를 재현했다. mock/PC 통과를 실기기 안정성으로 쓰지 않는다.

APK·계획 해시와 실행 결과는 아래에 기록한다. 기존 raw·freeze·소비 계획은 보존한다.

## 동결 완료

- plan SHA `c359f03781bc18c8c6b36a51184442d196477a2e9dca00d3de794f860a05f319`
- APK SHA `74e8065d10bdfac01c4fbda77afeac196986501b9534bf02d1dd5b0ad541ee6e`, 프로젝트 signer `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`, package `com.example.d1check.benchmarkrunner.modelprobe`/versionCode1.
- APK: 외부 `recorded_policy_compare_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`; source 대응 build_receipt 보존.
- plan: 외부 `energy_recorded_policy_compare_plan_v1/collection_plan.json`; 실제 PS Check 및 Device.call 차단 Check 통과·기기0·미소비 확인.
- 실행 명령: 해당 폴더 `RUN_AFTER_APPROVAL.ps1 -Action Run -Approved -Serial <이번에 확인한 IP transport> -ExpectedPlanSha256 c359f03781bc18c8c6b36a51184442d196477a2e9dca00d3de794f860a05f319`. serial은 공개 공유물에서 제외한다.

## 실제 결과 — 네 세션 정상 완료

Run/PowerShell/Python exit0, `completed_descriptive_only`. 실제1,279.649초(약21분20초)/상한3,670초, ADB3,386/13,000. 본96/warmup32=128추론·runtime16, 입력staging4회/28파일·설치본pull1·APK push1·데이터 보존 설치1. 재시도/대체/추가0. 사전 연결7명령을 합하면 총3,393명령이다. 연결 준비 timeout예약82초/PC 빌드·대기 공백은 Run과 구분한다.

| 순서 | 기록 정책 | 공통120초 J | 초기→최고 AP °C | urgent P95 ms | normal 평균 ms | 마감 충족 | 실제 병행 s |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | CPU_URGENT | 146.153062 | 30.1→31.4 | 640.713 | 4527.994 | 18/24 | 0.000000 |
| 2 | B2_PC | 136.955141 | 30.2→31.4 | 357.952 | 4157.662 | 20/24 | 1.633877 |
| 3 | B2_PC | 145.800139 | 30.5→31.5 | 313.261 | 4165.905 | 20/24 | 1.576581 |
| 4 | CPU_URGENT | 147.411580 | 30.6→32.0 | 640.591 | 4555.612 | 18/24 | 0.000000 |

전 세션 전체24요청의 시작·반환·output_ready·persist_complete·worker_release·lane_available를 각각24개 확인했다. 실패/미완료/미확인 본 요청0. runtime 반환4/warmup 반환8도 세션별 확인했다. 숫자상 request_return0은 이 경로가 `host_inference_return`을 쓰기 때문이며 반환0이라는 뜻이 아니다. 독립 세션4개, 센서·요청 개수를 독립 반복으로 세지 않는다.

**B2−CPU 사전 두 쌍의120초 J 차이:** −9.197922J와 −1.611441J, 평균−5.404681J. CPU 평균146.782321J/B2 평균141.377640J로 이 네 관측의 평균차는 약−3.682%다. 그러나 B2 두 관측 자체의 차이8.844999J가 평균 정책차보다 크고 초기 AP/배터리/이력도 달라, 안정적인 절감률·통계적 우월성·인과 효과로 판정하지 않는다. 순서 역전은 모든 비선형 시간·이력 효과를 제거하지 않는다.

urgent P95는 두 쌍에서282.761/327.330ms 감소, normal 평균은370.333/389.707ms 감소, 마감 충족은두 쌍 모두+2건이다. 24개 모두 완료했지만 CPU6건/B2 4건은 마감 미충족이며 분모에서 빼지 않았다. 저장 PC 일정의 서비스 방향과 실제 재생 방향이 일치한 제한 근거다. 원래 예정 dispatch가 입력이므로 온라인 B2/예정 도착부터 생성한 종단간 예측의 독립 검증은 아니다.

AP 최고 차이는0.0/−0.5°C, 공통창 마지막 유효 표본−승인 초기 변화 차이는−1.0/+0.1°C로 후자는 방향이 다르다. 초기 AP30.1/30.2/30.5/30.6°C는 모두 원래 개발 시작 범위 밖이다. AP observe-v2의 실행 적격과 원래 모형 지원은 구분한다. 배터리 기록은47→46/46→46/46→45/45→45%; 이는 조건 설명이며 SOC 감소율/사용시간 모형 검증이 아니다.

## 시뮬레이션에 연결한 완료 범위

기존 저장 일정의 서비스 비교 + 실측 기록 일정의 관측 비용 비교 + 동적 비용 모형의 지원 차단을 함께 제공한다. 강한 정적 배정 B2는 이 queue201 기록 사례에서 두 쌍 모두 더 많은 마감 충족과 낮은120초 관측 J를 보였다. 이 제한된 연구 결과는 사용할 수 있다. **새로운 임의 일정의 J/AP 예측·AP 후기/최고·열 피드백 처리시간·일반 정책 우월성은 여전히 미검증**이다. 기존 동결식이나 기각 AP 후보를 재보정하지 않았고 기본/strict/experiment_ready=false 불변이다. 이번 직접 비교를 모형 정확도 PASS로 승격하지 않는다.

앱 정상 cleanup4·회수4(각58파일/prefix error0), 소유자의 host force-stop은 세션별1회다. 설치 preflight의 정리1회를 별도로 포함해 총5회이며 각각 이후 ps에서 대상 프로세스 부재를 확인했다. parent/child는 PID+생성시각+명령 식별로 exited, 정상 receipt/registry completed다. 관측된 연결 소실/timeout/lifecycle_cancelled0이며, 과거 원인 해결이나 미래 안정성 보장은 아니다. 종료 후 새로운 기기 조회를 하지 않았다.

## 보존·재현

- 원본 `D1Check_Arrival_Extension/energy_recorded_policy_compare_run_v1/FINAL_RECEIPT.json`, `host_commands/`, `host_checkpoints/`, 각 세션 artifacts/thermal/recovery/cleanup.
- 외부 PC 판독 `recorded_policy_compare_readout_v1/`, 전체 raw inventory는 외부에만 보존. invoke stdout/stderr/exit는 `recorded_policy_compare_invoke_v1/`.
- [공유 화면](results/recorded_policy_comparison_01/run01/index.html) · [세션CSV](results/recorded_policy_comparison_01/run01/sessions.csv) · [사전 쌍 차이](results/recorded_policy_comparison_01/run01/pairs.csv) · [소비·검증](results/recorded_policy_comparison_01/run01/verification.json) · [재현 명령](results/recorded_policy_comparison_01/README.md).
- 기존 계획/모형/원자료·새 실행 소스/manifest/plan/APK 해시 보존. plan_v1은 완료·소비됐으므로 다시 실행하지 않는다.

**다음 PC 작업 하나:** 팀과 이 제한된 관측 결론을 검토한다. 이번 승인 작업의 실측·분석·본문 연결은 완료했으며, 같은 측정 반복이나 새 후보 탐색을 자동 추가하지 않는다.

최종 보존 검증: 원본17,489파일/128,223,056바이트 inventory. 명령 nonzero13건은 모두 사전 `test -e`의 기대 부재(exit1); 실제 timeout/비정상 client 종료0. AP 전체 관찰에는 warmup 승인 중11.97–16.34초 공백이 있으나 공통120초의 최대 공백은별도 검증에서10초 이내이며 누락0 채움은 하지 않았다. 센서221표본/host AP87표본은 각 세션 전체 준비·관측·냉각을 포함한다. 조회 주기는센서 하드웨어 갱신 주기의 증거가 아니다. 소비 후 Check는 기기0으로 거절, 기존 AP 후보 freeze도 불변.

공통창 AP는 각46표본, endpoint 포함 최대공백2.835/2.795/2.800/2.845초다. AP 변화량은 공통창 마지막 유효 표본과 승인 초기값의 차이이며, 정확히120초 endpoint를 새로 보간한 값이 아니다. J는계약상120초 endpoint까지적분했다.
