# SIM-MODEL-V3-EXPERT-CONFIRM-01-LOW-BATTERY-01

2026-10-10. 사용자 “배터리20%미만으로내려가도그냥계속진행” 지시에 따라 새 확인의 배터리 조건을 명시 개정한다. 20% 하한의 준비계획2c6cd53…은 claim/실측 전이며 보존하고 실행하지 않는다. 개발동결56a663bc…/모형82838f2d…와 기존λ·alpha·gain/개발검증은 바꾸지 않는다.

## 배터리·APK

- host 시작/진행 최소는6%로 낮춘다. native는 기존manifest 기본20%를 유지하며 `low_battery_diagnostic_version=model-v3-arrival-low-battery-v1`와 `battery_min_percent=6`가 함께 명시된 진단만6%를 허용한다. 잘못된버전/설정·level≤5·scale≠100·결측은거절한다.
- 샘플에 실제잔량·scale·최소잔량·절전모드를 기록한다. 20%미만 실제 구간이 생기면 기존20%이상 조건과 구분하며, 낮은SOC/절전에서 같은속도·같은전력관계를 전제하지 않는다. 비충전·BAT≤35°C·thermal0·메모리·화면·모델/입력/출력 동등성/측정창은 유지한다.
- ArrivalEnergyActivity의 sampler 종료를 확인한 후 journal을 닫는다. 기존 v2에서 확인했던 종료경합과 같은 유형을 차단하는 cleanup 수정이며 추론/작업/냉각 관측이 끝난 뒤에만 영향을 준다.
- native 고정20%가 있어 APK 수정이 필요하다. 새 격리APK/프로젝트동일서명/새manifest targetSHA·별도실험ID로4회를 수행한다. 기존과 APK가 다르므로 동일APK 확인이라고 표시하지 않는다. core model/runtime/input/CPU1·실측요청·타이머·sampler900ms는 유지한다.

## 한도·판정

기존새4/본384＋warmup32=416/runtime16/staging4·28파일/순서CPU-PAR-PAR-CPU·추가반복0을 유지한다. 필요한 APK 전송1/설치1로 원설치0을 개정하고 설치600초를 더해 새 기기clock 상한5130초로 한다. 설치전/후 점검과 종료예약을 포함한 ADB5904/정상5704는 기존명세의 reserve 안이다. 새 source/빌드/계획SHA를 동결해 run직전 검증한다.

새 확인을 보고 모형을 재적합/선택하지 않는다. 계수동결 이후바뀐 것은 사용자 지시의 환경하한·그native지원/종료확인뿐이다. 이자료는 개정된 환경/새APK의 독립확인이며 이전동일환경의엄격재현으로부르지않는다. 비교대상 원모형/v2/v3를 같은실측·사전입력·일정별로 평가하고 절대에너지교정/정책우월성/타기기일반화와구분한다.
