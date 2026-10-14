# A24 실측 준비 오류와 현재 검증 범위

2026-10-15. PC 준비 종료 뒤 사용자가 실제 측정을 승인했다. SOC 10% 이상, 같은 기기 연결 복구 최대 20분을 적용한다. 원 64슬롯과 입력·모델·기한·작업량은 보존하며 실패 슬롯을 재실행하거나 바꾸지 않는다. 이전 PC 준비 보고서의 기기 명령 0회는 그 보고서 작성 시점의 기록이다.

## 준비 과정에서 확인된 실패

| 슬롯 | 실제 원인 | 처리 |
| --- | --- | --- |
| I1 | 무선 APK 설치가 기존 30초 timeout 초과; 실패 원장 경로가 Windows 길이 제한 초과 | 전송 timeout을 300초로 분리, 새 원장을 짧은 별도 폴더에 보존 |
| I2 | 기존 설치 앱과 노트북 APK의 서명 불일치 | 기존 앱·데이터 보존, `.a24measurement` 별도 패키지 도입 |
| I3 | 새 패키지 미설치의 `pm path` exit 1을 오류로 취급 | 빈 결과·stderr 없음일 때 미설치로 처리하는 회귀검증 추가 |
| I4 | 원래 파서는 소문자 논리 `device_id`를 요구하지만 실제 하드웨어 serial을 대문자로 전달 | 논리 ID와 대소문자를 유지하는 물리 serial을 분리; 18개 target 필드 고정 |
| F1 | 앱 준비 전 idle reference27.6℃와 공통 상주/워밍업 후 안정 상태28.5℃가 다름 | gate 거절 보존; 본 요청0인 고정600초 준비 마지막60초 median28.5℃로 prepared-state reference v2 기록 |
| F2 | `exec-out cat`의 미생성 failure.json ENOENT가 host exit0/stdout으로 와 오류 파일로 오인 | 원장FAIL 보존; 같은 실행에 읽기전용으로 붙어 완료/원자료 회수; 정확한 ENOENT만 미생성으로 처리하고 권한 오류·변형 JSON은 거절 |

네 슬롯은 본측정 START 전에 거절됐다. I4의 앱 준비 실패도 원자료·cleanup·journal 종료 증거로 보존했다. 네 슬롯의 재시도와 대체는 0이다. 이 기록은 스케줄링 성능 실패가 아니다. I의 상주/비상주·Perfetto off/on 효과를 성공한 네 회로 비교할 수 없으며 해당 계측 비교는 미완료다.

실제 기기 환경을 PC mock으로 충분히 대표하지 못한 준비 검증의 한계가 드러났다. 이후 실제 기기 값을 반영한 64개 manifest·256개 모델 binding·8,832개 예정 요청을 앱의 동일 Kotlin 파서로 PC에서 검증했다. 이 검사는 native 모델 실행을 하지 않으며 실기기 품질 검증과 구분한다.

## 확인된 범위

- APK `eab8e4491372e96af800ca6f474faf1d25dae0bd46ebaaddea45b271ba5b883e`, 89,815,355 bytes. 별도 package 설치 후 기기 APK SHA 일치 확인. v2 서명 SHA `35ce1c7ca713d9c541df7381cfd7212f3bf79cc9b6bf55d08f7ed2716b0e18f3`.
- 관련 JVM 28개 PASS 뒤, 실제 manifest 전용 JVM 1개 PASS. 최신 host 제어 50개·연결 4개·조립 2개·새 오프라인 분석 3개 PASS. 정확한 ENOENT와 권한 오류 구분, cleanup 뒤 마지막 journal close 지연/누락 검사가 포함된다. 각각 검사한 버전과 원로그는 개인 실행 폴더에 보존한다.
- F1 준비에서 네 runtime과 각 2회, 총 8회 실제 워밍업 추론 관측. 승인 이미지/tensor SHA 일치. 분류 GPU 62/62·탐지 GPU 263/263 node 위임 로그 관측. 탐지 GPU는 상주/워밍업만 하며 본 요청 후보가 아니다. GPU 내부 정밀도는 미확인이다.
- 워밍업 출력은 기존 CPU reference의 같은 label·순서·decoded score 0.001/box 2px 계약 안에서 일치했다. CPU raw output SHA는 reference와 같았고 GPU는 달랐다. 전체 raw tensor 수치 비교나 이미지 다양성·보편 정확도 검증을 주장하지 않는다.
- F1 준비 AP는30.2→28.5℃, 마지막60초 25읽기에서 median28.5℃/slope0으로 관측됐다. 최초 reference27.6℃와 prepared reference28.5℃를 별도 버전으로 보존한다. 기존 제안의 Tref±0.5℃·60초 기울기 0.1℃/분·최대 10분 대기를 유지하고 같은 신규 gate를 이후 군에 공통 적용한다.

## 첫 본측정의 회수 결과

F2의 분류GPU252 요청은 전량 서비스창 안 및 각2.2초 기한 안에 완료됐다. 예정 도착부터 output-ready까지 P95는274.609ms다. 요청 누락/실패/미완료0, 최종 CPU/GPU owner0, 실제 AVAILABLE 후 재사용 및 decoded output252건 검산PASS다. F1/F2의 warmup16회와 F2 본252회, 합계268 NN 호출을 원물로 관측했다.

수집기 오류로 원장은FAIL이며 이를 COMPLETE로 고치지 않는다. 기기에서는 원래 실행이 계속되어 정상 cleanup/journal close를 남겼다. 새로운 START/claim·슬롯 재실행 없이 그 끝과269개 앱 파일을 별도 읽기전용 회수했다. 모니터링 공백과 원부분 회수를 함께 보존하며 AP 완전창 적격성은 별도로 판단한다. 후속 host에서는 마지막fsync/close 증거까지 관측·회수한 다음 COMPLETE로 기록한다.

## 계측의 제한

공식 BatteryManager 계약은 CURRENT_NOW를 µA, CHARGE_COUNTER를 µAh로 정의한다. 그러나 F1의 본측정 전 고정 스냅샷 301.517초에서 전류를 선언 단위로 적분하면 18.499µAh, charge counter 차이는 24,000µAh다. 둘의 비는 약 1,297.38이다. **같은 gauge의 단위·갱신 이력 불일치 진단이며 독립 전력 정답이 아니다.** 어느 속성이 잘못됐는지 확정하지 않고, 전류를 임의로 1,000배 보정하지 않는다. [공식 API 단위](https://developer.android.com/reference/android/os/BatteryManager#BATTERY_PROPERTY_CURRENT_NOW).

정확한 원표본은 보존하고 검증된 에너지 J와 에너지 절감 판정은 null로 남긴다. 필요한 경우 API 선언 단위의 계산값은 진단 가설로 분리한다. sysfs battery 속성은 접근 거부됐으며 우회하지 않았다. 외부 전력계는 없고 HAL AP의 독립 갱신 시각/cache age도 제공되지 않는다. AP 읽기 시각의 경로·평균·관측 최고값과 실제 표면 온도·센서 정확도를 구분한다.

데스크톱 기존 학습·EP813/EP814·NPU·원 worktree의 사용자 변경·기존 데이터는 변경하지 않는다. strict·기본 정책·`experiment_ready=false`를 유지한다. CONFIRM은 앞 단계 시도 기록과 계측/초기/분석/예측 또는 명시적 예측 없음이 동결된 뒤에만 진행한다.

## 개발 중 통신 복구 v8

DEV01 분류CPU 준비에서 로컬 ADB server의 tcp5037 응답 실패를 기록했다. 직후 같은 기기의 원부분 회수가 성공했고 앱은 본 요청START0·warmup8 뒤 준비 timeout으로 정상 cleanup/journal close를 남겼다. 이 슬롯도 재실행하지 않는다. 같은 hardware/fingerprint를 확인하는 최대20분 복구 경로를 로컬 daemon 장애·shell RPC timeout에도 적용했다. 읽기 명령만 다시 읽으며 install/push/am start/claim의 불분명한 결과는 재실행하지 않는다. PC 연결 검증6개 PASS; 기기실행의 정상화와 별도 기록한다.

## 독립 확인의 첫 중단과 후속 등록 슬롯

2026-10-15 06:48, CONFIRM01 L64 PAIR_G는 고정600초 준비 대기 뒤 AP_OUTSIDE_FROZEN_TREF_BAND로 PRESTART_REJECT됐다. AP249읽기의 범위29.1~30.9℃, 마지막읽기29.1℃로 상한29.0℃를 넘었다. 요청 START0, warmup8, cleanup DRAINED 및 journal SYNCED_AND_CLOSED를 회수했고 같은 슬롯 재측정은0이다. 첫CPU/저부하BASE 두 세션은 정상 회수됐다.

기존 배치는 실패 뒤 진단을 위해 중단한다. 첫 자동 후처리는 실측 재개 기능이 없어2정상/1거절/37미시도 부분 자료만 생성했으며, 공유 경로가 `.gitignore`의 results/ 규칙에 걸려 Git 반영도 실패했다. 중단시점 자료를 부분 스냅샷으로 표시하고, 작은 파생 결과의 명시적 경로만 반영하도록 고친다. 고정161개 실행/분석 소스 및 APK·온도 gate·계수·판정은 변경하지 않는다.

08시경 같은기기 identity와 기존앱/측정앱 owner 없음, SOC59%, 현재HAL AP27.8℃를 읽기전용 확인했다. 기존 시도 전부를 건너뛰는 원 배치로 미시도37개만 재개했으며 첫 조회에서 ADB 복구 경로로 진입했다. 연결단절20분 조건을 유지한다. 원 실패 원장을 성공으로 바꾸거나 초기 기준을 완화하지 않는다. 후속 감독은 온도 PRESTART 거절이며 종료 증거가 있는 경우에만 고정 냉각 예약 뒤 **다음 미시도 슬롯**으로 이어갈 수 있다. 불명확한 owner·다른 기기·저배터리·새 프로그램 오류에서는 시작하지 않고 근거를 보존한다.
