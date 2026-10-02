# s26/device — 원본 수집 로그

수집일 **2026-09-13** · 기기 `SM-S942N` (`<SERIAL>`) · USB, 읽기 전용
수집 도구: [`../tools/s26_collect.bat`](../tools/s26_collect.bat), [`../tools/s26_probe_npu.bat`](../tools/s26_probe_npu.bat)

해석 결과는 [`../docs/S26_DEVICE_PROFILE.md`](../docs/S26_DEVICE_PROFILE.md)에 정리돼 있다. 이 폴더는 **그 근거가 되는 원본**이다. 값을 고치거나 지우지 말 것.

| 파일 | 내용 | 이 로그로 확정된 것 |
|---|---|---|
| `00_devices.txt` | `adb devices -l` | serial `<SERIAL>`, model `SM_S942N` |
| `01_getprop_full.txt` | `getprop` 전체 | SoC `s5e9965`(Exynos 2600), SDK 36, fingerprint |
| `02_getprop_key.txt` | 핵심 프로퍼티 발췌 | 기기 판별 어댑터에 넣을 값 |
| `03_thermalservice_1~3.txt` | `dumpsys thermalservice` ×3 (5초 간격) | **AP/BAT/PA/SKIN 그대로 존재** → 센서 일반화 불필요, SKIN SEVERE 42.0℃, headroom 임계표 |
| `04_thermal_zones.txt` | `/sys/class/thermal/` | SELinux로 읽기 불가 확인 → HAL 경로만 사용 |
| `05_battery.txt` | `dumpsys battery` | **전류 µA·방전 음수 확정**, 배터리 ≈4,315 mAh |
| `06_battery_sysfs.txt` | `/sys/class/power_supply/` | 읽기 불가 확인 |
| `07_packages_nnapi.txt` | 패키지 + `libneuralnetworks.so` 표준 경로 | 표준 경로에는 없음 (APEX로 이동 — `10_`에서 확인) |
| `08_misc.txt` | CPU/메모리/전력 | **10코어** 2.76×6 / 3.26×3 / 3.80×1, ARMv9 SVE2·SME2 |
| `10_npu_runtime.txt` | NPU·NNAPI 런타임 조사 | NNAPI APEX에 존재·public 등재, **NNAPI HAL 없음**, Samsung ENN 스택 public 노출, `/dev/npu0~1` 노드 존재 |

## 주의

- `01_getprop_full.txt`는 **SIM·통신사·라디오 관련 120줄을 제거한 판**이다. 측정과 무관하고 개인 상용 단말이라 뺐다. 파일 머리말에 그 사실이 적혀 있고, 무삭제 원본은 로컬 `산공학회\D1_ondevice\measure\s26\device\`에 있다.
- `06_battery_sysfs.txt`가 거의 비어 있는 건 **수집 실패가 아니라 그 자체가 결과**다. Samsung이 sysfs를 막아둔 것을 확인한 기록이다.
- `04_thermal_zones.txt`도 같은 이유로 경로만 있고 값이 없다.
- `10_npu_runtime.txt`의 §4·§7에는 `grep -i npu`가 `i-npu-t`를 잡아 **`input` 관련 항목이 섞여 있다**. 판정 시 무시할 것.

## 재수집

같은 기기·같은 조건에서 다시 뽑으려면:

```
cd s26\tools
s26_collect.bat <SERIAL>
s26_probe_npu.bat <SERIAL>
```

기기가 하나만 연결돼 있으면 serial은 생략 가능하다. 결과는 이 폴더에 덮어쓰기 된다 — **덮기 전에 기존 파일을 날짜 붙여 보관할 것.**
