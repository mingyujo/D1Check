# CG_DC 기록 일정 전이 확인1 — 완료, 모형은 진단 범위 유지

2026-10-01(KST), 착수 HEAD `b578d1022d0640c3ad593781e455620384b346c2`, clean worktree·실제 원격 HEAD 일치. 사용자의 “실측 진행하자” 승인으로 [준비한 계약](AP_CGDC_TRANSFER_PREP_20260930.md)의 `ENERGY-AP-CGDC-TRANSFER-02`/plan_v2만 한 번 실행했다. Check는 기기 명령0으로 통과했고 계획·APK·실행 코드·모형·timeout·gate를 바꾸지 않았다. 계획은 이제 **소비·완료, 재실행 불가**다. 미소비 v1 초안·queue24 및 과거 종료 계획은 보존한다.

## 관측·시간 경계

원래 burst/seed201/B2_PC 도착0–4.840초와 backend를 유지하고 release만35초 지연했다. 실제 추론시간을 PC 간섭1.5에 맞추지 않았다. 본 요청24건 모두 시작·host inference 반환·output_ready·persist·worker_release·lane_available를 기록했고 실패/미완료0이다. warmup8과 runtime4의 시작/반환도 확인했다. 앱 정상 cleanup·58파일 회수·host 정리·프로세스 부재를 확인했다. lifecycle_cancelled·연결 소실·sampler 실패는 관측되지 않았다. 이는 무선 디버깅 설정 유지나 과거 종료 원인 해결의 증명이 아니다.

실제 공통창 경계는120.006481853초였고 **에너지 분석창은 사전 고정한 정확한0–120초**다. 시작 AP28.3°C는 numeric-ap-observe-v2의 유효·신선도 조건을 통과했으며 원래 개발 시작32.5–34.0°C 밖이다. 조회 종료→공통창 시작0.207502초, 조회 시작→공통창 시작0.457502초. 센서 내부 측정시각은 제공되지 않는다. 시작 배터리79%·비충전·BAT27.8°C·thermal0, 화면/밝기/꺼짐·메모리·GPU/품질 gate를 기존 실행기로 확인했다. AP 범위 밖이라는 이유로 환경 기준을 완화하거나 가열하지 않았다.

| 120초 실제 상태(dispatch→lane_available) | 관측 초 |
|---|---:|
| resident idle | 108.373726 |
| 탐지 CPU 단독 | 9.800960 |
| 분류 GPU＋탐지 CPU(CG_DC) | 1.466752 |
| 분류 GPU 단독 | 0.358563 |

host inference 호출 구간의 겹침0.910225초는 **lane 점유 겹침1.466752초와 다른 경계**다. GPU native kernel 동시성은 이 기록만으로 확정하지 않는다. PC 예정 병행2.486460초보다 짧고, release 대비 dispatch 최대 지연38.955ms·PC 대비 lane 해제 최대 절대차199.662ms를 기록했다. 짧은 병행의 독립 전력 계수를 정밀 식별한 자료로 사용하지 않는다. [예정/실제 경계 CSV](results/energy_ap_cgdc_transfer_01/run01/timing.csv).

## 에너지: 작은 총오차는 재현되지 않음

| 정확한 공통120초 | J |
|---|---:|
| 관측, raw=mA 조건부 | 135.146493 |
| 원래 동결 W의 실제 일정 조건부 계산 | 155.730344 |
| 예측−관측 / 절대차이 | +20.583851 / 20.583851 |
| 상대차이 | +15.230770% |

| 구간 | 초 | 관측 J | 동결식 J | 예측−관측 J |
|---|---:|---:|---:|---:|
| 부하 전 | 35.008859 | 38.681622 | 42.901026 | +4.219404 |
| 첫 dispatch→마지막 lane 해제 | 11.897290 | 19.144707 | 23.257670 | +4.112964 |
| 부하 후 resident idle | 73.093851 | 77.320164 | 89.571648 | +12.251483 |

세 구간 모두 양의 잔차로 이번에는 과거 B2 +1.062J처럼 부하/유휴 오차가 상쇄되지 않았다. 유휴 기여가 크다는 것은 산술적 분해이며 네트워크·주변·전류 단위·전력식 전용 중 특정 원인을 입증하지 않는다. 실측 전력을 예측 입력으로 사용하거나 보정계수를 만들지 않았다. 전체 기기 J의 조건부 단위 해석·절대 정확도 미인증을 유지한다. 조건이 다른 과거 총량을 자원 우열로 비교하지 않는다.

## 기존4세션 유휴 전력 대조 — 추가 PC 분석 완료

새 `d1_resident_idle_comparison`은 기존 원문 power/요청/경계를 읽어 같은 정확한120초와 첫 dispatch→마지막 lane 해제를 사용했다. B2·유휴 개발·확인·이번 전이의 전체 관측 J는 각각154.696404/135.617969/144.565095/135.146493으로 기존 수치를 재현했다. 원래 유휴 계수는 **1.225433421W**다. 다음 값은 세션별 부하 후 lane-free 구간 평균이며 새 계수가 아니다.

| 자료(모두 이번 비교에서는 사후 분석) | 시작 AP / 배터리 / BAT | 부하 후 유휴 초 | 관측 평균 W | 원래식−관측 J | 경계 혼합 표본 제외 평균 W |
|---|---|---:|---:|---:|---:|
| 기존 queue B2 | 29.9°C / 68% / 29.6°C | 107.986506 | 1.231219 | −0.624711 | 1.227498 |
| 유휴 개발 | 28.1°C / 68% / 27.7°C | 72.984592 | 1.045868 | +13.105484 | 1.046593 |
| 유휴 확인 | 28.7°C / 68% / 28.4°C | 47.946535 | 1.057693 | +8.042581 | 1.058204 |
| 이번 burst 전이 | 28.3°C / 79% / 27.8°C | 73.093851 | 1.057820 | +12.251483 | 1.055108 |

마지막 열은 각 유휴 상태 안의 첫·마지막 power 표본 중간시각으로 잘라 **lane 경계를 가로지르는 적분 구간을 제외**했다. 제외 시간은 각 구간 약0.95–1.10초이며 전체120초와 다른 분모다. 이를 하드웨어 갱신 시각 보장이나 독립 유휴 계수 식별로 표현하지 않는다. 부하 전 유휴의 같은 평균은 개발1.101813/확인1.203490/이번1.101035W, 확인 부하 사이20.998초 유휴는1.209794W다. 유휴인 사실만으로 기기 소비가 동일하지 않았고 이번 차이는 단순히 짧은 전환 경계 혼합만으로 사라지지 않았다.

[모든 구간·분모 CSV](results/energy_ap_cgdc_transfer_01/run01/idle_comparison/idle_power.csv), [맥락·원문 해시](results/energy_ap_cgdc_transfer_01/run01/idle_comparison/summary.json), [평균전력 그림](results/energy_ap_cgdc_transfer_01/run01/idle_comparison/idle_power.png). 입력·이전 부하·AP/BAT·배터리·수집 시점이 다른4세션이며 원인을 온도/네트워크/주변에 귀속하거나 세션별 W를 보편 계수로 치환하지 않는다. 새로운 계수 적합0·기기 명령0·strict 불변이다. 부하 후 유휴 잔차의 부호·크기가 달라 B2의 작은 총오차는 정책 차이의 허용 한도가 될 수 없다.

## AP: 고정 후보의 다른 일정 전이, 형태 한계는 남음

평가창은 첫 실제 dispatch **35.008859002초부터 냉각 종료180.062298472초까지**, AP50표본이다. 전체 AP81표본·power222표본을 회수했다. 부하 전 조건부 입력은 AP25표본/span65.36초, 최대 gap3.485초; 점수 구간 최대 gap3.340초로 계약의 coverage 기준을 통과했다. 준비 중 더 큰 AP 공백은 평가창의 coverage로 주장하지 않는다. power 간격 중앙0.999828초·최대1.044251초는 조회/기록 간격이며 하드웨어 갱신주기 증명이 아니다.

| AP 진단 점수 | 기존 동결식 | 기존 preload 후보 |
|---|---:|---:|
| MAE °C | 5.831406 | 0.463463 |
| 최대 절대차이 °C | 6.152643 | 0.777654 |
| 진단 최고값 예측−관측 °C | +5.197609 | −0.512576 |
| 부하 후 첫/마지막 관측 변화 °C | −1.000000 | −1.000000 |
| 대응 예측 변화 °C | −0.364896 | −1.011915 |

기존 β·상태 기울기 차이·추정 절차 freeze를 유지하고 이번 **부하 전** AP만 허용된 유효 유휴 기준 입력으로 사용했다(E=27.918695°C, 주변온도 실측 아님). 부하 후 AP/current로 계수·기준을 다시 맞추지 않았다. 회수 후 실제 일정 조건부 재구성이므로 세션 시작 전 종단간 예측이 아니다. 관측은29.6°C에서 냉각한 뒤28.3→28.7°C로 재상승, 마지막28.6°C였다. 후보의 단조 완화식은 이 후반 형태를 표현하지 못한다. 낮은 MAE만으로 최고/한도 보장·기본 simulator 채택·정책 판별력을 선언하지 않는다. 확인1은 독립 세션 변동성 추정이 아니다.

## 예산·종료·회수

| 항목 | 실제 / 상한 |
|---|---:|
| 세션 / 본 요청 | 1/1 · 24/24 |
| warmup / 명시적 추론 / 추가 적격성 | 8/8 · 32/32 · 0/0(warmup 품질 재사용) |
| runtime / staging / 파일 | 4/4 · 1/1 · 7/7 |
| 설치본 host pull / APK push / 설치 | 1/1 · 0/1 · 0/1(동일 설치본 확인) |
| ADB | 실행736＋최초 선택1＝**737/3,200** |
| 실행기 시간 | **293.138/1,300초** |
| 최초 선택 포함 활성시간 / 시작부터 종료까지 벽시계 | 295.266초 / 309.503초, 모두1,300초 안 |
| 고정 관측 / 재시도·대체·추가 | 210초 / 모두0 |

host force-stop 총2회는 **설치본 검증 후 launch 전 정리1＋앱 완료 후 세션 정리1**이며 같은 세션 종료의 중복 cleanup이 아니다. 앱 자체 cleanup completed가 먼저 있었고 사후 host 정리에서 프로세스 부재를 확인했다. 종료 조회 HAL AP28.8°C·BAT28.4°C·thermal0. 최상위 도구 종료코드0, PC에서 해당 child 부재 확인. 이후 기기 조회·추론·추가 회수0. ADB nonzero3건은 새 staging 경로 부재를 확인한 `test -e`의 예상 exit1이며 timeout·연결 오류가 아니다.

## 원본·재현·검증

- 원본 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_cgdc_transfer_run_v2/FINAL_RECEIPT.json`, 원본 inventory/host 명령/앱 artifacts·소비 registry 보존. private 식별정보·APK·모델은 공유하지 않는다.
- 최초 선택/host 소유권/종료 기록: 외부 `ap_cgdc_transfer_start_20260930T155509Z`. selection receipt의 run_called=false는 조회 당시 사실이며 후속 EXECUTION_END에 실제1회 호출·exit0을 기록했다.
- [공유 HTML](results/energy_ap_cgdc_transfer_01/run01/index.html), [소비/검증 요약](results/energy_ap_cgdc_transfer_01/run01/summary.json), [점수](results/energy_ap_cgdc_transfer_01/run01/report.json), [CSV·그림 안내](results/energy_ap_cgdc_transfer_01/run01/README.md). 공유 inventory는 공유 파일만 포함하고 private raw inventory는 외부에 둔다.
- 계획 SHA `e18268538174f49e98789dcf191318dbf5b57cdbc2a7f2cb1b4aaa4c449f3234`, 원래 freeze `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`, 후보 freeze `8507adc10485940c36853786ba39a4f42439a9fbd3d71a5da1c7d55e2cbc7ec5`, APK `747ce77e07c7c79f7c7d912d0ff749cf230e0c0483f4a160784fe549043f6180` 모두 불변. bound 소스98파일도 일치, APK 재빌드0.
- 실제 Run→회수→고정 report의 CSV/점수·구간 J 합계·24요청 경계·cleanup/프로세스 부재·98소스/freeze 해시·소비 후 Check 거절(기기 명령0)을 확인했다. AP/J/lane 그림3개 육안 검토 완료. 과거 전체 테스트/가정 정책 배치는 반복하지 않았다.
- 유휴 비교 관련3테스트(구간 J 보존·경계 혼합 배제·결측 null·미지원/시간 공백 차단) PASS, 실제4세션 원문 재생·기존 J 수치 재현·고정 파일 불변·유휴 그림 확인 완료. 코드/원문/그림 해시는 공유 inventory와 `idle_comparison/summary.json`에 있다. PC 시험은 연결 안정성/계측 절대 정확도 검증이 아니다.

```powershell
# PC 재판독만. 기존 output을 덮어쓰지 않고 다른 새 폴더를 지정한다.
& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B -m tools.d1_ap_transfer_report --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_cgdc_transfer_plan_v2/collection_plan.json' --output '<새 PC 판독 폴더>'
# 기존4세션 원문 유휴 대조. 기기 실행·계수 적합 없음.
& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B -m tools.d1_resident_idle_comparison --source-root 'C:/Users/LG/Documents/D1Check_Arrival_Extension' --frozen 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json' --output '<다른 새 PC 비교 폴더>'
& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B -m unittest tools.test_d1_resident_idle_comparison -v
```

**다음 PC 작업 하나:** 이번 고정 절차 전이 확인과 유휴 전력의 조건 전용 한계를 기존 연구 결과·논의 본문에 반영한다. 이번 결과에 맞춘 재적합·새 측정·정책 튜닝은 자동 시작하지 않는다. DC_DG 짧은 전환·온라인 정책·열 최고/한도·정책 J/AP 판별력·strict·`experiment_ready=false`는 미완료 상태를 유지한다.
