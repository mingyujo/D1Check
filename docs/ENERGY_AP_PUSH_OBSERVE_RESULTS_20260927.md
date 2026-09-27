# ENERGY-AP-PUSH-OBSERVE-01 결과 — 한 번의 push와 원격 SHA 확인

**결과: 이번 관측용 전송은 완료됐다.** 사용자 정정으로 직전 프롬프트의 설치본 확인·추가 환경 gate·생략 규칙 요구가 이번 전송 진단의 필수 조건에서 철회됐다. 기존 [관측 계약](ENERGY_AP_PUSH_DIAGNOSIS_20260927.md)의 A24 동일성·새 원격 경로 부재·공간 gate를 그대로 적용했다. [직전 보류](ENERGY_AP_PUSH_OBSERVE_PREFLIGHT_20260927.md)는 기기 명령 0회의 역사적 기록으로 남기며 그 상태에서 계획을 변경·소비하지 않았다.

## 계획·소비·종료

| 항목 | 동결 상한 | 실제 |
|---|---:|---:|
| 계획 | SHA-256 `423ee55d98c6ef8ed5bea9ea3b1f5357a3d4806fb66c398dded922deff138f9a` | `Check` 통과, 실행 전 출력·claim 부재 |
| 전체 | 420초 | **14.422초** (UTC 14:17:50.220~14:18:04.641) |
| ADB 명령 | 17 | **9** = A24/대상/공간 preflight 6 + push 1 + 최종 stat 1 + SHA 1 |
| 후보 APK push | 1회, timeout 180초 | **1회 정상 반환**, exit 0, client 경과 **13.469초** |
| 20초 간격 크기 조회 | 최대 8회 | **0회** — push가 첫 20초 전에 끝남 |
| 원격 최종 조회 | stat 1, 조건부 SHA 1 | 각 1회, 정상 반환 |
| pull·설치·앱 실행·warmup·추론·재시도 | 0 | **모두 0** |

계획·후보 APK SHA-256, ADB 및 실행 소스 해시·예산과 미소비 상태는 `python -m tools.d1_apk_push_observed check --plan <계획>`으로 재확인했다. 실행기는 현 무선 transport에서 단일 A24의 model/fingerprint/hardware serial을 동결 계획과 대조했다. 새 원격 대상은 실행 전 `stat`에서 부재, `df`의 가용량은 **86,635,500 1K-blocks**로 후보 106,092,116 byte보다 충분했다. 과거 transport 문자열이나 과거 기기 gate를 현재 값으로 쓰지 않았다. 전송 이외 설치본·배터리·thermal·화면 조회는 이 계약의 단계가 아니며, 이를 새로 확인한 것처럼 쓰지 않는다.

## 시각별 원격 상태와 client 증거

| UTC 시점 | 조회 | 결과 |
|---|---|---|
| 14:17:50.599~50.690, push 전 | `stat -c %s:%Y` | nonzero exit, `No such file or directory`; 현재 대상 부재 |
| push 시작 14:17:50.807 후 20~160초 | 예약한 8개 크기 조회 | **모두 미호출**. client가 13.469초에 반환했으므로 시간 조건 미도달 |
| 14:18:04.276~04.375, push 직후 | 최종 `stat` | **106,092,116 byte**, 정상 반환. mtime은 파일 전송 시각이나 진행 시각으로 해석하지 않음 |
| 14:18:04.406~04.631 | `sha256sum` | `b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf`, 로컬 후보와 일치 |

Push client는 exit **0**, stdout **0 byte**, stderr **218 byte**로 정상 반환했다. stderr에는 `1 file pushed, 0 skipped. 7.7 MB/s (106092116 bytes in 13.160s)`가 기록됐다. host wrapper의 시작·종료 및 PID·exit code는 `push/{start,result}.json`에 보존했다. client timeout/강제 종료는 없고, 사후 해당 PID가 남아 있지 않았다. 20초 전 중간 원격 크기 표본이 없는 것은 *진행이 관측되지 않은 것*이지 0바이트 또는 정지의 증거가 아니다. 동시 polling의 영향은 이번 빠른 실행에서는 발생하지 않았다.

현재 재사용 가능한 원격 staging 파일은 `/data/local/tmp/d1check-energy-ap-push-observe-01.apk`이며 위 크기·SHA가 검증됐다. 원격 파일은 삭제·이름 변경하지 않았다. **이번 시점의 완전성**만 판정했다. 앞선 두 120초 timeout의 당시 전송 진척·정지 지점·무선/기기/저장장치 원인은 여전히 미확정이다. 같은 후보가 이번에 13초대에 전송됐다는 사실만으로 과거 결함이 해소됐다거나 안정성이 입증됐다고 하지 않는다.

## 원본과 다음 경계

- 외부 계획: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_push_observed_plan_v1\diagnosis_plan.json`.
- 원본 출력/소비 claim: `C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_push_observed_run_v1\{claim.json,receipt.json,push/,commands/,final_stat/,final_sha/}`. `receipt.json` SHA-256 `76abf56a18d34d2ce6753cf3230781088b8b78ea43ccb03afe85d55f8eed5097`. 출력에는 실제 무선 transport 등 기기 식별정보가 있으므로 Git에 넣지 않았다.
- 재현 가능한 읽기 명령: `python -m tools.d1_apk_push_observed check --plan 'C:\Users\LG\Documents\D1Check_Arrival_Extension\energy_ap_push_observed_plan_v1\diagnosis_plan.json'`은 **소비된 계획이므로 재실행 거부**가 정상이다. 결과 확인은 위 `receipt.json` 및 `push/result.json`, `final_stat/stdout.bin`, `final_sha/stdout.bin`을 읽는다. 같은 `run` 명령을 다시 호출하지 않는다.
- **다음 행동 하나:** 현재 원격 경로·SHA를 재확인한 뒤 설치와 설치본 동일성 확인만 수행하는 **별도 배포 계획**을 마련한다. 이번 결과는 설치·수집 승인이나 `experiment_ready=true`의 근거가 아니다. 이전 COLLECT-03·배포 복구 종료 계획, FAIL·원자료·동결값을 보존한다.
