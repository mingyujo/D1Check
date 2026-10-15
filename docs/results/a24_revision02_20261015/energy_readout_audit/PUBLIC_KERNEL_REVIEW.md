# 사용자 제시 공개 커널의 단위·counter 경로 확인

**전류의 mA 반환과 SOC 환산 counter가 함께 작용한다는 설명은 공개 코드와 부합한다. 다만 이 소스는 A245F용 공개 사본이며 현재 A245N 설치 펌웨어의 드라이버·Health HAL과 동일하다는 증거는 아니다.** 공식 J 미판정은 유지한다. 진행 중인 확인 앱·계약·판정은 수정하지 않았다.

2026-10-15 사용자 제시 URL을 실제로 읽고, 움직이는 main 대신 커밋 `fd72e6702f511743b72a76a8c5fe732a4044805b`에 고정했다. [파일별 URL·SHA](PUBLIC_KERNEL_REFERENCE_SHA256.json)를 제공한다. 커널 전체를 공유물에 복사하지 않았다.

| 경로 | 실제 확인한 동작 | 입증 범위 |
| --- | --- | --- |
| [sec_battery.c](https://github.com/Shell-Sh0ck/A245F-U5-Kernel/blob/fd72e6702f511743b72a76a8c5fe732a4044805b/kernel-5.10/drivers/battery/common/sec_battery.c#L6563), 6563~6574 | CURRENT_NOW/AVG를 mA 지정으로 요청하고 그 반환값을 그대로 상위 property에 넣음 | 이 공개 코드의 배터리 property 경로 |
| [sm5714_fuelgauge.c](https://github.com/Shell-Sh0ck/A245F-U5-Kernel/blob/fd72e6702f511743b72a76a8c5fe732a4044805b/kernel-5.10/drivers/battery/fuelgauge/sm5714_fuelgauge/sm5714_fuelgauge.c#L1917), 1917~1929 | µA 지정이면 내부 전류에1000을 곱하고, 다른 지정이면 내부 전류를 그대로 반환 | µA/mA 요청을 구분하는 실제 분기 존재 |
| 같은 파일1965~2006 | SOC 스케일링 뒤 값을0~1000으로 제한해 raw_capacity에 보관하고 표시 정수%에는10으로 나눔 | counter에 쓰이는 값은0.1% 단위의 잔량 추정값이며 별도 정밀 coulomb 적분 증거가 아님 |
| 같은 파일2105~2108 | CHARGE_COUNTER를 설정 Capacity와 raw_capacity의 곱으로 만듦 | 이 경로는 정밀 소비 전하 적분 API가 아니라 SOC 환산 구조 |
| [sm5714_fuelgauge.dtsi](https://github.com/Shell-Sh0ck/A245F-U5-Kernel/blob/fd72e6702f511743b72a76a8c5fe732a4044805b/kernel-5.10/arch/arm64/boot/dts/mediatek/sm5714_fuelgauge.dtsi#L26), 26 | 설정 Capacity=4000 | 이 설정이 실제 로드될 경우 SOC 한 단계당 counter4000, SOC100%에서4,000,000이라는 구조 |

표의4000은 코드 설정값이다. 이를 현재 기기의 실제 배터리 용량·열화 상태·실제 µAh 정확도로 인증하지 않는다. 다른 device tree의 재정의나 빌드 분기, 다른 driver 선택 가능성도 현재 설치 버전 확인 전에는 남는다.

보존된38세션을 직접 추가 집계하면 정수 counter 표본16,331개가 **모두4000의 배수**다. 이 공개 코드의0.1% SOC 단위를 적용한 `counter/40000`과 같은 표본의 표시 배터리% 차이는 최소0/중앙0.5/최대1.0%포인트다. 이는 SOC 환산 구조와 매우 잘 맞는 관측이다. 식별 가능한 installed driver·HAL의 동일성이나 실제 전하량 정확도를 직접 증명한 것은 아니다. 숫자는 원물의 단순 분포 검사이며 계수를 fitting하거나 J로 변환하지 않았다.

따라서 다음 판단이 타당하다.

1. 전류가 mA 원값이면 µA와의1000배는 단위 변환이지만, 현재 앱까지 그 단위로 전달된다는 확인이 먼저 필요하다. 관측된1210배를 맞춤 계수로 쓰면 안 된다.
2. SOC 환산 counter는 독립적인 정밀 소비량 기준이 아니다. mA로 해석한 전류 적분과 counter가 완전히 일치하지 않는다는 이유만으로 전류 경로를 부정하거나 그 비율을 다시 보정계수로 삼을 수 없다.
3. 측정시간을 늘리면 계단 양자화의 상대 영향은 줄 가능성이 있지만 SOC 모델·스케일링·갱신 지연·offset이 사라진다고 보장할 수 없다.
4. 남은 핵심은 현재 A245N 펌웨어의 실제 driver→Health HAL→BatteryManager 변환이다. 공개 A245F 소스, 다른 모델 사례, 그럴듯한 전력 규모만으로 이 마지막 경계를 확인한 것으로 표시하지 않는다.

사용자 제공 분석의22세션·9,243표본 수치는 별도 분석 범위다. 이 저장소 조사38세션·199구간과 합산하거나 같은 표본 집합이라고 가정하지 않았다. 이번에 독립적으로 대조한 것은 제시 커널의 실제 경로와 단위·계산 구조다. 후속 실제 서비스 버전 조사는 비교 실측이 모두 닫힌 뒤 읽기 전용 범위에서 수행하며, 권한 차단을 우회하거나 실행 중인 앱에 새 센서를 넣지 않는다.

## 일반 Android16 경로와 설치 버전의 구분

공식 AOSP `android-16.0.0_r1`의 [HealthServiceWrapperAidl.java](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/health/HealthServiceWrapperAidl.java)는 CURRENT_NOW 처리에서 Health 서비스의 microamp 명칭 메서드 반환값을 property에 그대로 넣는다. [BatteryManager.java](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/android/os/BatteryManager.java)의 getIntProperty는 조회 결과를 정수로 전달하며 sentinel 처리 외 별도 단위 환산을 하지 않는다. 공식 원본을 직접 확보해 AOSP mirror와 바이트 SHA가 같은지도 확인했다. [파일·라인·SHA](PUBLIC_FRAMEWORK_REFERENCE_SHA256.json).

이는 **일반 AOSP 경로에서는 vendor Health 서비스가 µA 계약을 맞춰야 한다**는 근거다. 현재 삼성 framework·Health 서비스 바이너리를 그 일반 소스와 동일하다고 선언하는 근거는 아니다. 정확한 HAL의 실제 unit 변환과 그 입력 sysfs 경로는 남은 확인 항목이다. 인터페이스 이름에 Microamps가 들어 있다는 것만으로 실제 반환값의 단위를 검증한 것으로 처리하지 않는다.

## 확인 종료 후 실제 설치 버전 조회

새 확인4군의 close·회수·소유 프로세스 종료 뒤에만12개 읽기 전용 명령을 실행했다. 실제 Health 프로세스는 `vendor.samsung.hardware.health-service`이며 커널은 **6.12.23-android16-5-abA245NKSS9EZB5-4k**다. 참고 A245F 사본의 kernel-5.10과 커널 계열부터 다르다. 유사한 vendor 로직이 이식됐을 수는 있지만 동일 source/동작이라고 선언할 수 없다.

`/vendor/bin/hw` 목록은 Permission denied로 차단됐다. 이를 다른 경로·root·su로 우회하지 않았고 바이너리도 확보하지 못했다. 따라서 실제 서비스 ELF의 SHA나 내부 단위 변환은 확인하지 못했다. [설치 버전·제한 기록](INSTALLED_HEALTH_METADATA.json)을 보존한다. 전체 프로세스 목록·물리적 기기 식별자가 있는 감사 로그는 private로 둔다.

이번 후속12명령과 새 확인 전9명령, 총21개 진단 조회에서 추가APP·워밍업·추론·START·claim·세션 소비·설정 변경은 모두0이다. 남은 단위 확인은 정확한6.12 A245N vendor driver/Health 구현의 공개 근거 또는 제조사 설명이 필요하다. 지원되지 않는 경로를 임의로 인증하거나 현재 승인 확인40을 진단 재실측에 전용하지 않는다.
