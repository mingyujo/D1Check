# 작업 후 유휴 전력·AP 상승의 PC 판독 — 2026-10-03

**관측 상승은 확인했으나 원인은 특정하지 못했다.** benchmark 작업 지연·잔여 요청·host 조회량 급증·관측된 충전/화면/thermal gate 위반으로는 설명되지 않는다. 그렇다고 외부 앱/OS/통신/숨은 열 이력을 원인으로 확정하거나 기록되지 않은 native/시스템 작업을 없었다고 하지 않는다. 원인 식별에 필요한 동시 프로세스별 실행/주파수/시스템·통신 활동 기록은 원본에 없다. 같은 로그를 다시 감사해 이 구분을 해결할 수는 없다.

계수·원자료·이전 결과는 그대로다. 이번에 해결한 것은 **오차의 시간·실행 경계 확인과 계산값의 과도한 정책 선택 사용 방지**이며, 에너지·AP 예측 실패 자체를 수정한 것은 아니다. 새 실측·새 계획·APK·확인 재적합·세션 제외 0회.

## 비교 경계와 관측

원본 `separated_power_run_v4/confirmation`의 6개 세션 전체를 같은 코드로 판독했다. 아래 두 CPU는 동일 정책/등록 입력의 첫 번째와 마지막 확인이다. 시점·배터리·초기 열 이력은 같지 않다. 비교 구간75–120초는 둘 모두 마지막 lane 해제 뒤인 공통 구간이며 전체120초 결과를 대체하지 않는다. SER의75–120초에는 약80초까지 작업이 남으므로 같은 '유휴'로 부르지 않는다.

|관측|첫 CPU|마지막 CPU|
|---|---:|---:|
|마지막 실제 lane 해제|73.081초|72.767초|
|전체120초 J|153.149|197.713|
|75–120초 J|46.551|82.138|
|75–120초 power 표본|50|50|
|lane 해제 후~120초 활성/대기 표본|0/0 (53표본)|0/0 (53표본)|
|75–120초 host 명령|119|120|
|동 구간 thermal/screen 조회|15/4|15/4|
|동 구간 누적 client 대기|22.687초|22.455초|
|전체120초 host 명령 실패|0|0|
|최대 power 표본 간격(기록 전체)|0.939초|0.960초|
|공통창 최대 sensor read 폭|0.077초|0.170초|

75–120초 에너지 차이35.586J는 두 전체120초 관측 차이44.564J의 약79.9%다. 이는 산술적 분해이며 원인 기여율이 아니다. 마지막CPU의 조건부모형−관측 오차−35.819J와 두 세션 관측 차이35.586J도 서로 다른 값이다. 이를 빼서 모델을 '보정'하지 않았다.

마지막CPU의 AP는 공통96.578초 관측32.9°C에서99.197초 관측36.0°C로 바뀌고102.137/105.132초에도36.0°C가 반복된다. 이전 보고서의105.132초는 최고값이 기록된 시각 중 하나이며 **처음 관측된 최고값은 약99.197초**다. 반복된 HAL 값은 내부 센서 갱신 시각을 뜻하지 않는다. SKIN/PA도31~34°C대에서 변화했다. 전류는 75–120초 −1121~−182raw, 전압3711mV였고 첫CPU는−673~−165raw/3728mV였다. raw=mA 해석은 기존 조건부 계약이며 절대 정확도는 미인증이다.

마지막CPU charge counter는 해당 구간 1052000→1048000raw, 첫CPU는1172000에 머물렀다. 계단형·지연된 값이므로 이 짧은 창의 독립 에너지 검증이나 단위 보정으로 사용하지 않는다. 유효 전력 표본이 연속이며 AP/SKIN/PA 변화도 관측돼 단일 결측을0으로 채운 오류는 아니다. 다만 센서 지연·정확도와 전화기 전체의 숨은 활동은 이 기록으로 분리되지 않는다.

앱 표본의 plugged=0, thermal status=0, interactive=true, memory admit와 host 화면sample_pass가 유지됐다. 이는 관측 조건 통과이며 배경 활동 부재나 열 안전성 인증이 아니다. BatteryManager BAT 값과 HAL BAT 값은 서로 다른 기록이므로 동일 센서처럼 합치지 않는다. 공통75–120초 앱 journal에는 power_sample만 있고 추가 추론/Activity 이동/cleanup 이벤트는 없다. 냉각 phase는 약120.12초, 앱 종료는약180.25초이므로 뒤의 cleanup을 앞선 상승 원인으로 연결하지 않는다.

## 시계와 판독 한계

앱 lane/power는 monotonic nanosecond. power는 sensor-read 시작/끝 중점이며 read 폭을 보존한다. AP는 /proc/uptime으로 감싼 HAL 조회 중점/불확실성이다. host 명령은 host monotonic start/end로 기록되어 직접 같은 시계로 취급하지 않는다. 저장된 uptime 응답의 host client 구간 중점과 device uptime을 연결해 국소 보간했다. 최대 반구간+uptime10ms 양자화는0.354초이며 실제 온도 센서 내부 지연의 상한은 아니다. host5초 bin 경계의 명령 몇 개는 이동할 수 있어 인과관계 또는 정밀 비용 추정에 사용하지 않는다. 누적 client 대기는 기기 CPU 비용이 아니다. 직접 wall clock 정렬/임의 에너지 창 이동은 없다.

공통창 host 명령은 uptime·thermal·listing·screen뿐이다. 조회 종류/빈도가 유사하므로 '추가 명령 급증'이라는 설명은 기록상 뒷받침되지 않는다. 동일 조회의 실제 기기 비용이 항상 같다는 결론이나 ADB의 영향을0으로 두는 결론은 아니다.

[그림](post_idle.svg) · [6세션 요약](summary.json) · [5초창·명령](windows.csv) · [원시 필드 축약 전력](power.csv) · [HAL 온도](thermal.csv) · [lifecycle](lifecycle.csv) · [직접 읽은 원본 해시](source_hashes.json).

## 시뮬레이터 보완

`tools.d1_separated_power_readout`의 기본 기술적 재생 수치는 유지했다. 반환값/결과에 `decision_support`를 추가해 다음을 구분한다.

- 수치 계산 가능: 등록 모형과 입력·preload 초기값으로 예정 도착 또는 실제 일정 조건부 계산.
- 정책 선택: 에너지/AP의 미래 배경 변화 오차 상한·확률은 `null`. 관측된 최대오차를 다음 세션의 보편적 오차 한도로 전용하지 않음.
- `--purpose energy-ap-policy-selection`은 근거 부족 오류로 계산/출력 생성을 막음. 기본 `descriptive`는 계산값과 `withheld_unvalidated_background_variation`을 함께 반환.
- 우열 보류는 정책 동등성 증명이 아님. 별도 서비스 제약·응답 관측 결과는 보존. 임의의 정확도 PASS·기본/strict 확대·experiment_ready 승격 없음.

이 검사는 큰 열·전력 오차를 고친 모델이 아니라 **아직 예측하지 못하는 부분을 정책 결정에서 숨기지 않는 경계**다. 특정 확인세션의 미래 AP/전류를 guard 또는 forecast 입력에 넣지 않는다. 안정적으로 보인 다섯 세션만 골라 허용하지 않는다. 현재 한 세션의 사후 잔차를 학습한 후보도 만들지 않았다.

## 지금 가능한 결론과 남은 해결 조건

등록48:48 혼합 입력에서 CPU/PAR의 마감 충족과 PAR의 응답 개선, SER의 마감 미충족은 보고할 수 있다. J/AP 예측은 가정과 실제 오차를 동반한 제한 계산이다. 작은 차이를 모두 판별할 필요는 없지만, 이번처럼 큰 차이를 만드는 숨은 소비/열 입력에 대해서는 일반화된 절감 효과를 주장할 수 없다.

원인별 모형을 만들려면 현재 기록에 없는 **동시 활동의 관측 또는 사전 통제 근거**가 필요하다. 전력 잔차만으로 시스템/통신 전력계수를 새로 맞출 수 없고, AP만으로 해당 열원과 잔열을 분리할 수 없다. 새 변수가 없는데 같은 확인 배치를 반복하는 것은 이 식별 문제를 해결하지 않는다. 이번에는 새 실행기를 만들거나 추가 실측을 권고·실행하지 않는다. 다음 연구 결과물은 서비스 제약과 에너지·열 판정 유보를 분리한 정책 비교 본문이며, 일반적인 절감 예측 완료로 표현하지 않는다.

## 검증·재현

6개 관련 테스트: 시계 구간/외삽금지·명령 목적 분리·적분 분할/결측null·실제 재생/미래입력 배제·자료역할/해시 차단·에너지/AP 정책선택 차단. 원본6세션/144창 적분합 일치, 실 CLI 예측162.21600018297715J는 기존 마지막CPU 값과 일치, 정책선택 모드 실패 및 출력 미생성 확인. 모형5682082a…와 원본freeze19637bf1… 바이트 불변. PC 자료 축약 초기판의 준비 표본에 waiting_requests 필드가 없어서 KeyError가 발생해 해당 필드를 null로 보존하도록 고쳤다; post-lane 활성/대기 검사는 원본의 필수 필드를 사용했고 기기/기존 결과에는 변경이 없다. [검증](verification.json).

```powershell
python -B -m unittest tools.test_d1_post_idle_diagnosis tools.test_d1_separated_power_readout
python -B -m tools.d1_post_idle_diagnosis --root C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_run_v4 --output output/post_idle_fresh
python -B -m tools.d1_separated_power_readout --bundle docs/results/online_policy_study_01/separated_power_final --case-id confirmation_5_CPU_URGENT_ONLINE_V1 --policy CPU_URGENT_ONLINE_V1 --purpose descriptive --output output/cpu_guarded_fresh
```

그림은 공유 CSV만으로 `from tools.d1_post_idle_diagnosis import plot; plot('docs/results/online_policy_study_01/post_idle_pc_v1')` 재현 가능. 전체 host 국소화 재현에는 위 외부 원본이 필요하다. 사용자 식별값/전체 stdout/원본은 Git에 넣지 않는다. 이번 기기 명령·실측·새계획·claim·후보적합0.
