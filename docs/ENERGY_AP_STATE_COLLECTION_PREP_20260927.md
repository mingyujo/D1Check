# 에너지·AP 상태 모형 수집 준비 — 2026-09-27

**판정: PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED.** A24의 현재 두 모델·같은 입력·CPU 1 thread·네 resident runtime에 한정한 **반복 실행 구간(regimen)의 기기 전체 평균 전력**과 **AP 온도 전환**을 식별·확인하는 새 계획이다. 요청 한 건의 에너지, 순간 joint 전력, 임의 도착의 예측 정확도나 정책 절감을 이 자료만으로 주장하지 않는다. 기존 4세션/144분은 세 번째 병행 상태 및 순서가 다른 별도 확인이 빠져 있어 채택하지 않았다. 기존 동결값·FAIL·부분 원본·종료 계획은 변경하지 않았고 `experiment_ready=false`다.

## 식별 대상과 근거

A24의 기존 완료 운영 비교 4세션은 CC_DG 직렬/병행 고정 870건을 개발·확인 각 1세션씩 기록했다. 개발 병행의 실제 양 lane 점유는 108.420초/공통 480초, 확인은 108.224초였다. 이는 연속된 108초 joint 상태나 GPU kernel 겹침을 뜻하지 않는다. 분류 CPU·탐지 GPU·resident idle의 구간 평균 전력과 CC_DG episode 전력은 재사용할 수 있지만, CG_DC와 탐지 CPU＋GPU에 복사하지 않는다. 기존 전류는 약 1초, AP는 약 2.65초 간격이며 요청보다 느릴 수 있다. 아래 90~120초 구간에서 기대하는 AP 표본 수 34~45개는 명목 계산이며, 실제 수·gap·상태 점유를 적격성으로 검사한다.

| 대상 | 기존 근거 | 새 개발 관측 / 확인 관측 | 추정·식별 위험 |
|---|---|---|---|
| resident idle | CC_DG 고정 구간의 조건부 W | 각 세션 baseline 120초, 구간 사이 30초×2, load 말미 120초와 post-work 120초, 냉각 180초 / 다른 순서 | 준비·화면·잔열·주변온도 미측정. baseline과 이후 idle을 같은 평형이라고 가정하지 않음 |
| 분류 CPU, 탐지 GPU 단독 | 기존 고정 직렬 구간 W | CC_DG 각각 90초 / 확인에서는 역순 | 250ms cadence 사이 idle·기록 비용 포함. 순간 요청 전력 아님 |
| 분류 GPU, 탐지 CPU 단독 | 처리시간 근거만, W/AP 미측정 | CG_DC 각각 90초 / 역순 | 각 모델·backend 직접 확인 필요 |
| CC_DG | 기존 고정 묶음 joint 점유·episode W | 양 lane을 120초 동안 250ms cadence로 호출 / pair 먼저 실행 | 실제 overlap과 한쪽 잔여를 분리; 짧은 joint 호출은 센서로 직접 분해 불가 |
| CG_DC (고정 B2 배정) | 도착 trace의 점유시간만 | 같은 방식 120초 / pair 먼저 | CC_DG 대칭 전용 금지, GPU delegate·memory·품질 gate 필요 |
| 탐지 CPU＋탐지 GPU (B3 주요 상태) | PC trace의 점유시간만 | 같은 방식 120초 / pair 먼저 | 같은 모델 두 runtime 병행 적격성·실제 overlap 확인 필요 |
| AP 가열·냉각/잔열 | CC_DG episode 경로, 동적 계수 미식별 | 동일 AP 센서의 모든 전환과 baseline·냉각 연속 기록 / 순서 변경 예측 | 0.1°C 해상도·주변온도 부재·세션 효과. 행렬 rank·양의 시정수·잔차 확인 실패 시 계수 null/중단 |

개발 순서는 CC_DG→CG_DC→탐지 CPU＋GPU, 확인은 역순이다. 각 세션의 기술 적격성 serial probe와 parallel probe는 정식 표본에 합치지 않는다. 개발/확인 모두 동일한 고정 resident 준비 120초와 공식 baseline 한 번을 사용한다. 과거 첫 직렬 온도에 병행만 맞추는 anchor를 적용하지 않는다. 시작 AP·배터리·순서·준비 에너지/시간을 그대로 보고하며, 역순만으로 교란이 제거됐다고 주장하지 않는다.

개발 구간은 `solo_a 90 → idle 30 → solo_b 90 → idle 30 → pair 120 → idle 120`; 확인은 `pair 120 → idle 30 → solo_b 90 → idle 30 → solo_a 90 → idle 120`이다. 두 경우 모두 뒤에 공통 600초 창까지 resident wait가 이어진다. 각 lane은 시작 시각 기준 250ms cadence로 호출하되, 미완료 호출이 있으면 같은 lane에서 겹치지 않는다. 구간당 lane 512회, 전체 세션 1,680회가 하드 상한이다. 완료 작업 수는 결과로 기록하며 조건 간 같다고 가정하지 않는다. 단독·실제 두 lane 점유·한쪽만 남는 시간·idle을 dispatch→실제 `lane_available`로 분할한다. host API overlap을 GPU kernel 동시 실행으로 부르지 않는다. pair의 실제 양 lane 점유가 5초 미만이면 적격성 실패다. 5초는 모형 정확도 기준이 아니라 **계획한 joint 상태가 거의 없었던 실행을 제외하는 사전 관측 최소치**다. 해당 경계 근처의 순간 W는 여전히 미식별이다.

## 보정·동결·확인 계약

개발의 유효 전류/전압 표본을 최대 2.5초 gap으로 사다리꼴 적분하고, 각 구간의 **계측된 시간에 대한 기기 전체 평균 W**를 구한다. current raw는 A24에서 mA로 해석할 가능성이 가장 크지만 절대 J 정확도는 인증되지 않았다. 충전, 양의 전류, sentinel, 0/결측 전압은 0으로 채우지 않고 제외한다. 평균 W에는 해당 구간의 resident idle·callback·파일 기록 부담이 함께 들어 있으며 idle을 다시 더하지 않는다. 이 평균은 정해진 250ms 반복 방식의 계수이고 임의 요청별 순간 상태 비용이 아니다.

AP는 `dT/dt = a_regimen − β(T−30°C)`의 공통 양의 β와 구간별 기울기부터 시도한다. 30°C는 수치 기준점이며 주변온도·안전 기준이 아니다. 개발의 세션별 연속 AP 표본을 사용하고, 행렬 rank·특이값 비율·β 범위(시정수 10~1,000초) gate를 만족하지 못하면 열 계수는 **미식별**로 멈춘다. 평형에 도달하지 않은 90~120초 구간을 정상상태 평형 측정이라고 부르지 않는다. 전력→온도 계수를 독립적으로 보정하지 않으며 thermal throttling도 만들지 않는다. AP는 `dumpsys thermalservice`의 `mName=AP,mType=0`, °C로 고정한다. BAT·SKIN·잔량·사용시간은 검증 대상이 아니다.

개발 3세션 적격성 확인 후 구조·계수·입력 변환·분석 코드 및 계획 해시를 `development_freeze.json`과 receipt에 동결한다. 확인 3세션은 다른 블록 순서로 실행하고 재보정하지 않는다. 첫 AP가 개발의 **관측 온도 전체 범위** 밖이면 예측을 unsupported로 반환한다. 시작 AP가 개발의 시작 범위 밖이나 전체 관측 범위 안이면 그 한계도 보고한다. 확인 오차는 공통창의 관측 **coverage와 동일한 시간**에서 예측−관측 J 및 절대오차, 누적 J 경로 MAE/최대오차, AP 경로 MAE/최대오차·최고온도 오차와 연구용 30°C 초과 시간 오차다. 결측 시간의 J를 0으로 대체하지 않는다. 결과에 맞춘 정확도 PASS·허용폭은 없다. 조건당 개발/확인 1독립 세션으로 변동성·모집단 정확도·정책 선택 충분성은 판정할 수 없다. 기존 확인 결과를 본 뒤 만든 후속 설계이므로 완전한 사전등록 독립 검증도 아니다.

## 실행 경계·정확한 상한

새 ID `ENERGY-AP-STATE-COLLECT-03`; [계획 및 6 manifest](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_plan_v3/collection_plan.json>), [실행 스크립트](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_plan_v3/RUN_AFTER_APPROVAL.ps1>). 계획 SHA-256 `b717df5c51c27f1f8a0f4d08604203b0c89b9d61fd054c96e794bc9537a59f02`; APK SHA-256 `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf`; signer SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`. 키/APK/외부 모델 파일은 Git에 넣지 않는다. 빌드 v1은 잘못된 전역 debug 서명으로 폐기했다. plan_v1/v2는 분석 coverage 경계와 탐지 CPU＋GPU 적격성 호출 분모 정정 때문에 폐기한 **미실행 초안**이며, v3만 실행 후보이다.

| 항목 | 새 승인 전 후보 상한 |
|---|---:|
| 세션 | 개발 3 → 동결 → 확인 3, 총 6 |
| 부하 호출 | 세션당 최대 1,680, 총 10,080 |
| 기술 적격성 / warmup / 명시적 추론 | 24 / 48 / 총 최대 10,152 |
| runtime / staging | 24회 / 6회·42파일(각 manifest＋원본 6) |
| APK 전송·설치 / 재시도·대체·추가 | 각 최대 1회(설치본 동일 시 0) / 모두 0 |
| 고정 관측 | 세션당 준비120＋baseline120＋공통600＋냉각180 = 1,020초; 총 **102분** |
| 세션별 예약 | 2,100초. gate120＋host poll1,800＋회수60＋cleanup45＋PC 검증35＋launch20=2,080초, 여유20초. 하위 앱 watchdog1,800초는 host poll에 중첩 |
| 전체 상한 | 설치/전송600＋세션 6×2,100＋동결600 = **13,800초 / 230분** |

102분은 완주시간이 아니다. 준비·gate·runtime·warmup·staging·회수·동결이 추가된다. 230분은 timeout 합산 **최대 예약**이지 정상 평균 예상시간이 아니다. 배터리 완주 가능성은 미확인이다. 이 상한은 이전 4세션/144분 후보보다 86분 크다. 새 제3 병행 상태의 개발·확인 2세션, 공통600초 및 추가 관측/회수 예약을 포함한 결과이며 기존 예산을 재사용하지 않는다. 화면 조회 timeout 2초·재시도 0을 유지한다. 앱 watchdog·host poll·개별 ADB timeout을 다시 더하지 않는다.

환경은 실행 직전 같은 A24 serial/fingerprint, 프로젝트 서명·설치본 정확한 APK, 배터리 시작/진행 중 ≥20%, 비충전, BAT ≤35°C, thermal status 0, Awake/interactive, 수동 밝기81·화면 timeout 5시간, memory admission, GPU delegate 증거, 두 병행 조합 각각의 serial/parallel 품질·메모리 적격성을 현재 상태로 확인한다. 기존 조회값은 재사용하지 않는다. 실패·timeout·coverage 부족·미식별·중단 시 부분 기록과 불명 호출 상한을 보존하고 회수·앱/host cleanup을 구분한다. 새 계획은 자동 재시도·새 계획 생성·중단 계획 재개를 하지 않는다.

PC 검증: 프로젝트 서명 격리 APK 빌드, 관련 JVM 테스트, Python 46건(기존 수집 경로 회귀 포함), 실제 A24 `thermalservice`·전류 기록의 작은 parser fixture, 계획/manifest/source/APK/서명 해시 검사와 `-Action Check` 통과. 이는 **기기 현재 적격성·6세션 완주·AP 계수 식별 성공의 증거가 아니다.** ADB·설치·앱 실행·추론 0회, 실행 출력과 소비 registry는 생성되지 않았다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check
# 새 실측 예산 승인 후, 실제로 확인한 A24 serial로만:
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 A24 transport serial>'
```

다음 한 행동은 새 **230분·10,152회 상한의 실기기 실행 여부**를 별도 결정하는 것이다. 실행 전 기기 gate가 실패하거나 배터리·열 상태로 전체 예약을 감당할 수 없으면 시작하지 않는다.
