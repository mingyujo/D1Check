# A24 전류·전하량 불일치 조사

**원자료의 불일치는 재현됐다. 앱 저장·CSV 변환·시간 적분의 중복 단위 변환은 발견되지 않았다. 기기가 전류를 mA로 반환한다는 가설은 유력하지만, 설치 펌웨어의 실제 단위와 정확도는 아직 검증되지 않았다. 검증된 에너지 J는 계속 미판정이다.** 응답·AP 확인은 사용자의 별도 승인대로 진행하며 이번 조사 때문에 실행 중인 앱을 수정하지 않았다.

[진단 화면](index.html) · [동일 구간 검산](published_CSV_recalculation.csv) · [전체 199구간](intervals.csv) · [원물 SHA](source_inventory.csv) · [중복·회수본 처리](lossless_copy_selection.csv) · [검증](verification.json).

[보존 센서 원물 ZIP](existing_sensor_raw.zip)에는 무손실 선택한38세션의 events·ready·summary·close 중 존재하는144파일을 바이트 그대로 넣었다. [멤버별 SHA](existing_sensor_raw.sha256.json)로 검산할 수 있다. 모델·APK·개인 경로·기기 일련번호가 든 전체 target manifest는 제외했다. ZIP은 새 실행이나 실패 재분류가 아니다.

## 단위가 다른데 왜 비교하는가

[Android 규정](https://developer.android.com/reference/android/os/BatteryManager)은 `CURRENT_NOW`를 µA, `CHARGE_COUNTER`를 µAh로 정의하며 방전 전류는 음수다. 전류와 전하량을 그대로 비교한 것이 아니다. 다음처럼 **같은 µAh로 변환한 뒤** 비교했다.

```text
Q전류(µAh) = Σ[-(I앞 + I뒤)/2 × (t뒤_ns - t앞_ns)/1e9] / 3600
Q전하(µAh) = 같은 첫 표본의 counter - 같은 마지막 표본의 counter
```

물리적으로 센서가 새로 갱신된 시각은 모른다. 동일한 읽기 구간을 쓰는 것과 물리적인 측정 시각까지 같다는 것은 구분해야 한다. [AOSP 계측 문서](https://source.android.com/docs/core/power/device)는 기기별 측정 해상도·갱신 주기가 연료계 하드웨어와 드라이버 설정에 달려 있음을 설명한다. 해당 문서의 Nexus 수치나 센서 오차를 A24에 전용하지 않았다.

## 사용자 제시 300초 구간 검산

원본은 기존 [W1 CSV](../window01/battery_API_unvalidated.csv)이며 SHA-256은 `a46ab2c86bdbb3f6285d2756a0b3730547e5737cbe19c6aab4fb3352ec0233cb`다. 센서 334표본의 시작·끝 시간, 전류·전압·전하량·충전 원값이 `events.jsonl`과 전부 일치했다.

| 항목 | 결과 |
| --- | ---: |
| 첫~마지막 실제 표본 간격 | 299.699345787초 |
| API 명시 단위로 전류를 적분한 전하량 | 19.8300454156 µAh |
| 같은 끝점의 전하량 감소 | 24,000 µAh |
| 두 값의 비율 | 1,210.28467142 |
| 관측 전하 변화 | 4,000씩 6회 |
| 전하 변화 사이 간격 중앙값 | 60.30300985초 |
| 표본 최대 간격 | 0.925951153초 |
| 충전·결측·양의 전류 표본 | 모두 0 |

1,210은 이 구간의 불일치 비율이며 보정계수가 아니다. `×1000`, `×1210`을 원자료·공식 J에 적용하지 않았다. 별도 Decimal 사다리꼴 적분과 기존 적분기가 수치오차 1e-12 이내에서 일치했다. 이 허용치는 수치 구현 검사이며 센서 오차 허용치가 아니다.

## 원값 → 저장 → 분석 추적

| 단계 | 실제 코드와 확인 내용 |
| --- | --- |
| 시각 | `A24PreparationActivity.kt`: `SystemClock.elapsedRealtimeNanos()`, 읽기 전후 ns 기록 |
| API | 같은 파일 `batterySample`: `getIntProperty(CURRENT_NOW/CHARGE_COUNTER)` 원정수, 미지원 sentinel만 null. 전압은 sticky battery intent 원값으로 갱신 나이 미확인 |
| JSON | `event` 및 `ModelProbeArtifacts.kt`: 숫자를 JSONObject에 그대로 넣고 UTF-8 flush; 전류·전하량의 곱셈·나눗셈 없음 |
| CSV | `d1_a24_measurement_report.py`: 원 event 필드를 복사. 공개 334표본은 원정수 exact 대조 PASS |
| 시간 적분 | `d1_a24_measurement_analysis.py`: ns→초 한 번. 이번 별도 검산에서 전류×초/3600과 동일 끝점 counter 차이 비교 |
| 에너지 | 기존 조건부 식은 µA×mV/1e9×초. 단위 미검증 gate 때문에 공식 J는 null이며 이 식의 결과를 검증 J로 승격하지 않음 |

파일별 SHA는 [소스 추적](source_trace.json)에 남겼다. 정적 코드 추적과 특정 구간 원정수 대조를 구분한다. 모든 원물의 모든 필드가 독립적으로 교정됐다는 뜻이 아니다.

## 다른 구간에서도 확인한 것

기존 유휴·CPU·GPU·혼합·사전거절 자료 41개 경로를 조사했다. 동일 세션 복사본 3개는 완전 동일 또는 원본의 정확한 앞부분임을 바이트로 입증해 긴 무손실 회수본 하나만 집계했다. 원물 삭제·실패 상태 수정·유리한 결과 선택은 없다. 38세션·199구간 중 198구간은 산술 진단 가능, 1구간은 표본 부족이다. 앱의 무추론 구간도 포함하지만 이를 휴대폰 전체의 전기적 유휴라고 부르지 않는다.

37개 충분한 전체 기록 구간에는 충전·결측·2.5초 초과 gap이 없었다. 원물 시각으로 서로 겹치지 않는 기록 약 14,663초를 합치면 전류의 명시 단위 적분 합 951.648826618µAh, counter 감소 합 912,000µAh로 비율 958.33670414다. **연속 4시간 시험이 아니라 사이 공백을 제외한 여러 구간의 합**이다. 이 합산은 mA 반환 가설을 지지하는 규모 차이지만 교정이나 독립 검증은 아니다.

| 자료 묶음 | 충분한 전체 구간 수 | counter 감소 / 명시 단위 전류 적분 |
| --- | ---: | ---: |
| 기존 A24M15 | 24 | 866.1711 |
| REV02 W1 | 2 | 1,206.0857 |
| REV02 W3 | 1 | 993.6034 |
| REV02 W4 | 2 | 838.5440 |
| 새 DEV8 | 8 | 1,285.5534 |

개별 전체 구간 비율은 약 355~1,660이다. 이 변동만으로 고정 단위 오류를 배제할 수는 없다. 전하량의 거친 계단과 갱신 지연이 함께 작용할 수 있다. 특히 새 DEV GPU의 공통 0~180초에는 전류가 계속 음수인데 counter 변화가 0이다. 짧은 창의 counter 감소를 곧바로 정확한 소비량으로 사용할 수 없다. 이 자료는 원인 탐색에 사용했으므로 새 독립 검증 자료라고 하지 않는다.

## 기기에서 읽기 전용으로 확인한 것과 한계

DEV 종료 후, 새 확인 전에 등록 기기에서 9개 읽기 전용 ADB 명령을 수행했다. 앱 시작·워밍업·추론·START·claim·추가 세션 소비·설정 변경은 모두 0이다. 시스템 battery dump에도 `current now=-164`, `charge counter=3672000`, SOC91%, 전압 원값4209가 보였다. 앱 CSV가 도입한 배율 문제로만 설명하기 어렵다는 근거이며, 서로 다른 시각의 값이나 같은 계통의 gauge를 독립 기준으로 취급하지 않는다.

`/sys/class/power_supply`와 battery 노드 목록은 Permission denied였다. health/batteryproperties dump는 빈 출력이라 단위를 입증하지 못했다. root·su·권한 우회는 하지 않았다. 설치된 정확한 A24 펌웨어의 전류 단위 계약을 입증하는 제조사 드라이버 근거도 현재 확보하지 못했다. 접근 제한과 공개 근거 미확보를 구분한다. 개인 식별자·사용 이력이 섞인 전체 시스템 dump는 공유하지 않는다.

## 남은 원인과 다음 조치

1. 전류 mA 반환 / counter µAh 가설: 유력하지만 미확정. 설치 펌웨어와 일치하는 드라이버·HAL 단위 근거 또는 제조사 확인을 확보해야 한다. 다른 Samsung 모델 사례만으로 자동 보정하지 않는다.
2. counter의 해상도·업데이트 지연·내부 추정 여부: 관측된 4,000 단위 계단을 물리적 정확도나 실제 coulomb-count 해상도로 단정하지 않는다.
3. 향후 별도 진단 버전은 int/long `CURRENT_NOW`, `CURRENT_AVERAGE`, `CHARGE_COUNTER`, 지원 시 long `ENERGY_COUNTER`, 읽기 전후 시각·미지원 sentinel·환경을 그대로 보존하도록 준비할 수 있다. 현재 동결 앱에는 넣지 않는다. 같은 gauge API 간 일치도 독립 교정은 아니다.
4. 단위 후보가 확인되면 진단에 쓰지 않은 별도 긴 구간의 여러 부하에서 변환식을 고정해 확인한다. 정확도 기준은 독립 계측 근거에서 정한다. 외부 기준이 없다면 내부 일관성 확인과 실측 J 검증을 구분한다. 새 진단·계측에 필요한 실행 예산은 남은 확인40 예약을 몰래 소비하지 않는다.

단위 오류만 확인되면 보존한 원값을 새 분석 버전으로 재계산할 가능성은 있다. 센서가 기록하지 않은 변화나 알 수 없는 갱신 시각을 사후 생성할 수는 없다. 현재 정책의 열·에너지 공동 개선이나 에너지 절감 완료를 주장하지 않는다.

## 재현

```powershell
$env:PYTHONPATH='tools'
python -B -m unittest test_d1_a24_energy_unit_forensics test_d1_a24_energy_readout_audit test_d1_a24_suite_report_context test_d1_a24_confirm_registered_window
# private inventory는 경로만 포함하며 저장소에 올리지 않는다. 새 출력 폴더를 사용한다.
python -B tools/d1_a24_energy_unit_forensics.py output/a24_energy_unit_forensics_20261015/private_inventory.json output/energy_recheck_new --reference-csv docs/results/a24_revision02_20261015/window01/battery_API_unvalidated.csv
python -B tools/d1_a24_energy_diagnostic_plot.py docs/results/a24_revision02_20261015/window01/battery_API_unvalidated.csv output/energy_plot_new
```

2026-10-15, 실행 기준 `8ce0a70` + 새 분석 스크립트 미커밋 SHA 대상. 관련 순수 검증 14개 PASS. 조사 스크립트와 사전 진단은 측정 중인 핵심 179파일·APK·정책·MAIN gate를 변경하지 않는다.
