# APK 서명 복구 준비 — ARRIVAL-TIMING-CAL-02

> 후속 승인 실행 결과: 업데이트 설치 성공 후 첫 세션 필수 기록 누락으로 **중단/재실행 금지**. 세션1/16·완료0·미시도15, 진단/warmup 실제 호출 수 미확인, fit·확인 미실행. [종료 보고](ARRIVAL_TIMING_CAL02_RESULTS_20260924.md)를 따른다. 아래 승인 대기·명령은 준비 시점 기록이며 지금 재실행하는 명령이 아니다.

2026-09-24. **서명·PC 준비 완료 / 설치·추론 미실행 / 새 계획 승인 대기**. 시작 branch `feature/arrival-scheduling-20260923`, HEAD `660532f`, 직전 종료 기록 문서3개 미커밋을 보존했다.

## 원인과 인증서

모두 applicationId `com.example.d1check.benchmarkrunner.modelprobe`, versionCode **1**, versionName1.0이다. APK SHA는 전체 파일 해시, signer SHA는 인증서 지문으로 서로 다르다. SDK36.0.0의 `apksigner verify --verbose --print-certs`, `aapt2 dump badging`으로 확인했다.

| 대상 | APK SHA-256 | signer 인증서 SHA-256 |
|---|---|---|
| 실패 calibration APK v2 | `7bf84ce9997ed1fc0866ed89c38c84a78f37d5589a04eedef28ff65f16ae11e5` | `35ce1c7ca713d9c541df7381cfd7212f3bf79cc9b6bf55d08f7ed2716b0e18f3` |
| 기존 설치 성공 arrival-v2 보관본 | `1a8448abe1c78432870f1848676de61faefa83f64c9a6a3732d79f7a121f3612` | `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565` |
| 현재 A24 설치본(읽기 전용 회수) | `1a8448abe1c78432870f1848676de61faefa83f64c9a6a3732d79f7a121f3612` | `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565` |
| 새 재서명 후보 | `85c5fd0ab578d48e8af3e2abdda4c836939c5a330631d39dc4df61bd6d3e7ff6` | `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565` |

- 키 검색은 두 경로로 제한했다. 전역 `C:/Users/LG/.android/debug.keystore`는 실패 APK의35ce 인증서, 프로젝트 `.android-user/debug.keystore`는 설치본의b253 인증서와 일치한다. 양쪽 PrivateKeyEntry가 존재하며 프로젝트 키로 후보 서명을 완료했다. 키 생성/복사/덮어쓰기 없음. 키·자격증명은 Git/보고서에 포함하지 않는다.
- Gradle modelProbe는 debug를 상속하며 signingConfig override가 없다. 격리 init script는 buildDirectory만 바꾼다. package는 호출 환경을 상속하고 ANDROID_USER_HOME을 고정하지 않았다. 현재 환경에는 그 변수가 없고 실패 APK 인증서는 전역 기본 키와 일치한다.
- [기존 09-20 복구 기록](PRE_SIMULATION_RECOVERY_20260920.md)6절은 이미 프로젝트 `.android-user`를 ANDROID_USER_HOME으로 지정해야 함을 기록했다. 원인은 **기존 전용 debug 서명 환경이 새 패키징 경로에서 보장되지 않았고 설치 전 서명 검사도 없었던 것**이다. 격리 출력 경로 자체가 새 키를 생성했다는 증거는 없다. 과거 build receipt에는 전체 환경 snapshot이 없어 당시 JVM 환경 변수값 자체는 확정 복원하지 않는다.

## 데이터 보존 후보

실패 APK의 **정확한 바이너리에 apksigner 재서명**을 적용했다. 원 APK·receipt는 불변, 새 APK·파생 receipt는 별도 root다. 기존 키는 로컬 명령으로만 참조했고 Gradle signing 설정·Android 소스·의존성·variant는 변경하지 않았다. 재컴파일/전체 빌드는 불필요하여 실행하지 않았다.

ZIP entry909개 비교: 변경은 `META-INF/MANIFEST.MF`, `META-INF/ANDROIDD.RSA`, `META-INF/ANDROIDD.SF` **3개**뿐이다. 비서명 entry906개 hash 동일, AndroidManifest·DEX·native library·resource·asset 변화 없음. ZIP 바깥 signing block은 재서명에 따라 달라진다. 후보 서명 검증과 package/version/인증서 일치는 확인했지만 **설치 성공이나 데이터 마이그레이션 성공은 미검증**이다.

외부 공통 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`:

- `timing_signature_recovery_v1`: 회수 APK, 인증서/키 비교, apksigner/badging, 후보 identity, PC 로그, read_only_preflight, FINAL_REPORT/FINAL_RECEIPT.
- `timing_calibration_resigned_apk_v1`: 새 APK·build_receipt.json(원 APK/빌드 연결)·zip_entry_comparison.json(entry별hash).
- `timing_calibration_recovery_plan_v1/calibration_plan.json`: 새 후보 SHA **`31558f9c1d3c62b8d1d4e9f0b8713274bee6a1700e4a8c59c2c4ae5aabc5a7a6`**.

## Preflight와 소비 경계

`tools/d1_apk_identity.py`는 apksigner 유효 서명/단일 signer, package/versionCode를 추출한다. 계획에 도구hash·후보identity를 결합한다. 정확한 기기/fingerprint 확인 후 `pm path`와 APK `pull`만 사용한다. 앱 실행/설치/force-stop/기기 파일 쓰기 없음.

- 동일 signer/package 및 versionCode 비하향만 허용. signer rotation/복수 signer, split APK, 설치본 부재, 조회 실패는 확인 불가로 차단한다. Android 설치 조건 전체를 재현하는 검사는 아니다.
- 새 run: 소비/중단 여부 확인 → 읽기 전용 preflight → phase claim → install_attempt → install_result → 세션 attempt. preflight 실패는 새 receipt에 원인·install0/session0/phase_consumed=false를 남긴다. 자동 반복 없음. 설치 실패는 claim 이후이므로 phase 소비·종료다.
- CAL-01의 claim-before-install 소비·중단 기록은 불변이다. 구 plan은 당시660532f 재현 자료이며 현재 코드hash gate를 우회하여 재사용하지 않는다. CAL-02도 소비/중단되면 다른 output으로 재실행할 수 없다.
- run 내 preflight의 기기 회수시간은 각 phase3600초 wall budget에 포함한다. PC plan/hash 검사는 실행 전 검사다. cleanup 합상한121.5분 유지. 원래45~60분은 예약 추정이며 무선 APK 회수 때문에 더 걸릴 수 있다.
- 실제 동일 A24에서 **PREFLIGHT_COMPATIBLE_NOT_INSTALLED**, 설치0·phase소비0·세션0. 이 결과는 향후 배터리/thermal/memory admission/초기 상태 gate를 대신하지 않는다.

## 후보 예산과 명령

새 ID **ARRIVAL-TIMING-CAL-02**, seed2026092401. parent CAL-01 plan SHA `a340a6c61e4eb4a85591ce226965495627ebd6751c3db4075b7b558a9d0553a2`와 원 stopped hash를 recovery binding에 연결했다. 입력/모델/CPUthread1/네 runtime resident/단독 concurrency1/0·5·10·15초 도착/조건 순서는 같다. 새16세션 UUID 및 `timing_calibration_execution_registry/ARRIVAL-TIMING-CAL-02`를 사용한다.

**미승인 후보:** 개발8세션32진단64warmup → 기록 품질 검토·중앙값/규칙/지원 범위 동결 → 확인8세션32진단64warmup. 총16/64/128, retry·대체·추가0, cooling120초×16, 합상한121.5분. 실패 시 보존·종료, 확인 자료 재적합 금지. 기존20null·experiment_ready=false·작은표본/tail/간섭/정책 우수성 제한 불변. CAL-01 미시도16세션의 자동 재개가 아니다.

PC 검사(실측 없음):

```powershell
python -B -m tools.d1_arrival_timing_calibration check --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_calibration_recovery_plan_v1/calibration_plan.json
python -B -m unittest tools.test_d1_apk_identity.SigningTest -v
```

**아래는 승인 이후에만 사용하며 현재 미실행이다.** 실행 직전 실제 연결/환경 gate를 다시 확인한다. 실패 시 같은 명령 재시도 금지.

```powershell
$base='C:/Users/LG/Documents/D1Check_Arrival_Extension'
$plan="$base/timing_calibration_recovery_plan_v1/calibration_plan.json"
$hash='31558f9c1d3c62b8d1d4e9f0b8713274bee6a1700e4a8c59c2c4ae5aabc5a7a6'
$adb='C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe'
$serial='adb-R59W802RW5F-yZ5QCN._adb-tls-connect._tcp'
python -B -m tools.d1_arrival_timing_calibration run --plan $plan --phase development --output "$base/timing_calibration_recovery_development_run_v1" --adb $adb --serial $serial --approved-total-cap 16 --expected-plan-sha256 $hash
# 개발8 전체 완료와 기록 품질/추정 가능성 검토 뒤에만 아래 진행.
python -B -m tools.d1_arrival_timing_calibration fit --plan $plan --run "$base/timing_calibration_recovery_development_run_v1" --output "$base/timing_calibration_recovery_fit_v1.json"
python -B -m tools.d1_arrival_timing_calibration run --plan $plan --phase confirmation --output "$base/timing_calibration_recovery_confirmation_run_v1" --adb $adb --serial $serial --approved-total-cap 16 --expected-plan-sha256 $hash --freeze "$base/timing_calibration_recovery_fit_v1.json"
python -B -m tools.d1_arrival_timing_calibration confirm --plan $plan --run "$base/timing_calibration_recovery_confirmation_run_v1" --freeze "$base/timing_calibration_recovery_fit_v1.json" --output "$base/timing_calibration_recovery_confirmation_report_v1.json"
```

## 검증과 남은 조건

PC10 PASS: 새7(인증서/파일hash 구분, package/version/mismatch/unknown 차단, 읽기 전용/0소비, 중단 선차단, 설치실패 소비 구분, 새plan UUID/예산/무ADB) + 직접 영향 회귀3. 검증 대상660532f+이번host변경; `PC_TESTS_FINAL_V2.txt`와 receipt에 명령·시점·test hash가 있다. 최초 회귀에서는 앞당겨진 차단 오류문구 기대값1건 실패했고 수정 중 들여쓰기 오류도 발생했다. 둘 다 수정하여 최종10개 통과, 초기 로그 보존. 전체 Kotlin/Gradle/실험 감사 반복 없음.

새 plan/16manifest dry-run 통과. APK·keystore·원자료·캐시 커밋 없음. 다음은 후보의 **별도 실행 승인**과 최신 환경 gate 확인이다. 앱 제거·데이터 초기화·applicationId 변경을 자동 대안으로 삼지 않는다. 기존198요청 FAIL·fixed-split 부분 결과·모든 종료 기록 보존.
