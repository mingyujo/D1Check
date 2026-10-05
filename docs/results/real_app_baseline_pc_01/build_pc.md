# Ente 원본 계측 연결 — 2026-10-04

기준 D1Check HEAD `451c93e78d62beb2bd1586eb50028e3dface12a2` + 이번 변경. [후보 선정](README.md)의 후속 구현이며 정책 변경·기기 실행이 아니다.

## 실제 구현

Git 밖 `C:/Users/LG/Documents/D1Check_Arrival_Extension/ente_baseline_build_pc_v1/upstream`에 Ente commit `a492f9db8e67def81d5f17c687f69b5778ec0df3`를 detached checkout했다. mobile/rust를 확보하고 원문4파일을 Git blob SHA-256으로 다시 확인했다. 이전 원문 캐시는 불변이다.

`tools/d1_ente_trace_overlay.py`는 정확한 원문 해시·단일 삽입 경계를 요구하며 새 출력 폴더만 만든다. 그 결과를 별도 Ente checkout의 두 원본 파일에 적용하고 관측 helper 하나를 추가했다. Ente 원문과 바이너리는 D1Check 저장소에 넣지 않는다. 외부 checkout의 기존 라이선스는 유지한다.

| 삽입 위치 | 기록 의미 | 기록만으로 알 수 없는 것 |
|---|---|---|
| runAllML 진입/반환 | 요청 시도와 원래 disposition | 전체 사진 품질·완료 분모 |
| admission_passed | 선행 조건을 통과해 원래 exclusive 경로로 이동 | lock 획득·실제 indexing 시작 |
| indexing_enter/returned | fetch/index 함수 호출 직전과 반환 | 사진별 성공, 내부에서 처리된 실패, 실제 추론 횟수 |
| MlRunControl.requestStop | 최초 latched 중단 사유 | OS 외부 종료 원인 |
| release_requested/returned | 기존 compute 반환 호출 전/후 | 앱 프로세스 부재·센서 종료 |

`--dart-define=D1_BASELINE_TRACE=true`일 때만 로그를 쓴다. 기본은 비활성이다. 기존 Logger 경로로 JSON을 내보내며 파일·사진·계정 식별정보를 추가하지 않는다. Stopwatch monotonic 시각, isolate 안의 control 객체 ID, 순번을 사용한다. **control ID는 전체 시스템 세션 ID가 아니다.** 같은 control을 재사용한 호출은 run_enter 순번으로 구분하고 다른 process/isolate 로그를 임의 합치지 않는다. host wall clock과 자동 정렬하지 않는다.

isolate당 이벤트 최대2048 + overflow 표지1건이다. overflow/순번 누락/종료 기록 부재는 완전한 trace가 아니다. 동기식 로깅 오류는 별도 counter로 남기고 원래 결과를 대체하지 않지만, 로그 sink 자체의 비동기 실패·프로세스 강제 종료·전원 상실 시 내구성을 보장하지 않는다. 종료 로그 부재를 성공으로 처리하지 않는다. 이벤트 직렬화/Logger 비용은 0이 아니므로 계측 ON/OFF 비교가 필요하다. 센서 polling·sleep·retry·추론·설정 변경은 추가하지 않았다.

15초 timer, 건강 gate, consent, force, process lock, 원래 retry, callback 호출 및 catch/finally는 유지했다. `run_return=completed`를 모든 사진 완료로 승격하지 않는다. 아직 workload 분모/품질·UI 반응·실제 J/AP 계측은 연결하지 않았다. 기존 D1 정책을 실제 앱에 포팅한 상태도 아니다.

## PC 검증 경계

- Python5건: 원문에서 관측문과 passthrough만 제거하면 바이트 정규화 후 원래 코드로 복원됨, 기존 catch/finally 보존, 삽입 경계 모호성 차단, 원문 해시 불일치 시 출력 없음, 기존 출력 덮어쓰기/원문 변경 차단.
- 실제 고정 원문의 `MlRunControl` + helper를 Dart로 실행했다. logging1.3.0 사용. analyze 통과, 계측 OFF/ON 모두 통과. 최초 stop reason, 중복 stop callback, 이미 중단된 control에 callback 연결, 원래 callback 예외의 동일 객체 전파, 반환 객체 동일성, 시각 순서, 이벤트 상한/overflow를 확인했다.
- 최종 overlay_v2의 ml_service/ml_run_control/helper 3파일을 실제 앱 workspace에서 분석해 `No issues found!`를 확인했다. 초기 import 문제46건은 수정했으며 린트를 완화하지 않았다.
- **전체 MLService/Flutter lifecycle/indexing/native 모델 실행 검증은 아니다.** Python 삽입 검사가 Dart 전체 앱 컴파일을 대신하지 않는다. 기기 명령·추론·실측0.

## 재현

```powershell
python -B -m tools.d1_ente_trace_overlay --source-dir '<고정 원문4파일 폴더>' --output-dir '<존재하지 않는 overlay 폴더>'
python -B -m tools.test_d1_ente_trace_overlay '<고정 원문4파일 폴더>' -v
```

최종 외부 `control_harness_v2/lib/services/machine_learning`에는 overlay_v2의 `ml_run_control.dart`, `d1_baseline_trace.dart`를, harness 루트에는 `tools/ente_trace_control_check.dart`를 `check.dart`로 배치했다. pubspec의 name은 `photos`, SDK는 `>=3.10.0 <4.0.0`, logging은 `1.3.0`이며 lock을 보존했다. 아래 dart는 전용 Flutter 폴더의 `bin/cache/dart-sdk/bin/dart.exe`를 사용한다.

```powershell
dart pub get
dart analyze
dart run check.dart
dart -DD1_BASELINE_TRACE=true run check.dart
```

Flutter는 원본이 요구하는3.47.2(tag commit `d3b14c876900e553bc736ca19295fc09e3853e8e`)를 외부 전용 폴더에 설치했다. 초기 배포 목록404는 잘못 구성한 URL의 결과였으며 네트워크 전체 차단 근거가 아니다. Git checkout의 긴 Windows 경로 문제는 **이번 새 SDK 저장소에만** core.longpaths를 적용해 복구했다. 사용자 Git 설정/다른 worktree/보안 설정은 바꾸지 않았다.

원본 CI의 의존성/생성/빌드 순서는 mobile에서 `flutter pub get --enforce-lockfile`, rust에서 `cargo codegen frb photos`, photos 앱에서 independent APK 빌드다. 앱 구동 명령 `flutter run`은 이번에 사용하지 않는다. 원본 회사 서명키를 갖고 있다고 가정하거나 D1Check 키로 대체하지 않는다. 이번 환경의 최종 실행 결과는 [검증 기록](build_verification.json)을 따른다.

## 확인한 빌드 환경 문제

- Flutter3.47.2/Dart3.13.2와 Rust1.99.0/Cargo1.99.0을 위 외부 폴더에 확보했다. Rust는 `--no-modify-path --profile minimal`, 프로젝트 전용 CARGO_HOME/RUSTUP_HOME을 사용했다. 사용자 PATH·기존 D1 빌드 버전은 변경하지 않았다.
- 첫 pub get은 Ente packages fork의 긴 iOS 파일 경로에서 checkout에 실패했다. 다음 실행에서 의존성 다운로드가 끝났지만 해당 캐시는 요청한 `e6f7518...` 대신 `92552b1...` HEAD에 머물렀고 video_player_avfoundation pubspec도 없었다. 따라서 그 중간 결과를 성공으로 인정하지 않았다.
- 실패 캐시 전체를 외부 `failed_pub_checkout_preserved`에 보존하고, 정확한 commit을 긴 경로 지원으로 새 checkout했다. 현재 해당 cache HEAD는 `e6f7518a2ea4b31cf44e7bd6f44b35b1d66b2085`, 변경0이다. lockfile의 버전·ref를 바꾸지 않았다. 불완전한 캐시를 읽던 첫 전체 분석은 소유권을 확인해 중지했으며, 그때 나온 analysis server crashed는 **이 작업의 의도적 중지 결과**다.
- Flutter 후처리는 `Building with plugins requires symlink support`와 Windows Developer Mode 안내로 exit1. 별도 임시 디렉터리에서 symlink 생성도 WinError1314로 실패했다. **휴대폰 개발자 모드/ADB 문제가 아니라 Windows 빌드 권한 문제**다. OS 설정·ACL·보안 기능은 바꾸지 않았다. dependency 다운로드 완료와 Flutter 후처리 완료를 구분한다.
- APK 패키징 성공·원앱 indexing 성공·실제 앱 대비 절감은 아직 주장할 수 없다. Windows symlink 권한이 확보되면 같은 잠금 파일과 보존된 checkout에서 이어간다. 새 실측 계획이나 claim은 만들지 않는다.
- 실제 앱 파일 분석에서 처음 추가한 상대 import의 순서/형식 문제46건을 발견했다. 원앱의 package import 규칙에 맞게 삽입 위치를 고친 overlay_v2를 적용했다. v1과 그 receipt는 외부에 보존하고 최종5개 Python 검사·Dart ON/OFF 검사 모두 v2에 다시 적용했다. assertion이나 원앱 lint 기준은 완화하지 않았다.
- Rust 코드 생성기 자체는 컴파일됐으나 `cargo expand` 단계에서 C: 여유가 약1.2GB로 급감했다. 소유권이 확인된 이번 codegen 프로세스 트리만 종료했다. 바인딩 생성 완료로 기록하지 않는다. 이후 여유는 약7.4GB로 회복됐다. `rust/target`에서 관측한 재생성 가능한 산출물은2,691,133,666바이트이며 그 추가 삭제는 자동 승인 검토가 `blocked by policy`로 거부해 보존했다. 다른 경로/수단으로 삭제를 재시도하지 않았다.

**다음 행동 하나:** 휴대폰이 아니라 **충분한 디스크 공간과 symlink 생성 권한이 있는 Windows PC 빌드 환경을 확보한 뒤**, 이 고정 checkout의 원앱 빌드를 재개한다. 현재 여유만으로 전체 native/APK 빌드에 충분하다고 인증하지 않는다. 원본 소스/실측 자료 삭제나 Windows 보안 설정 변경을 자동 수행하지 않는다.
