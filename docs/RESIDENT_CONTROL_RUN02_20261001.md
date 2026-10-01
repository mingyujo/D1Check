# Resident 대조 실행 02 — preflight 로컬 쓰기 실패와 PC 마무리

**ENERGY-AP-RESIDENT-CONTROL-02는 소비·stopped_no_resume이다. 아래 실행 전 기록은 이력이며 Run 대상이 아니다. 공간 확보 후 재개한 이번 작업은 PC 검증·기록·Git 반영만 수행했다.**

## 기존 화면 timeout 조사

plan_v1의 화면 조회 34건 중 정상 33건은 중앙값 0.531초, nearest-rank P95 0.594초, 최대 0.610초였다. 정상 출력 76바이트에는 producer 완료 marker가 있었고, 실패 명령 1229의 57바이트에는 marker가 없었다. 2초 timeout은 제한에 걸린 관측이며 실제 완료 지연이 아니다. 인접 client 1,240건의 실행 중첩은 0쌍, 실패 spawn 약 0.015초·대기 약 1.985초였다. stdout/stderr는 파일에 직접 기록하므로 PIPE 미배출 deadlock 경로는 없다.

**화면 조회 내부 timeout 원인은 미확정이다.** 무선·기기·OS 원인이나 재현된 수집 결함으로 확정하지 않는다. producer/marker, screen 10초 주기·2초 timeout, thermal 2초·listing 0.25초, 앱 1초 sampler를 유지했다. 이 조사와 이번 별도의 저장 공간 실패를 혼동하지 않는다. [조회 표](results/resident_control_design_01/run02/prior_screen_commands.csv), [진단](results/resident_control_design_01/run02/screen_diagnosis.json).

## 실행 전 동결 이력

사용자의 “진단하고 다시 실측 진행해”를 별도 C→L 계획 1회 승인으로 적용했다. plan_v1의 실패·registry를 초기화하지 않았다. edition 처리로 새 ID/출력/registry를 분리하고, post-run 판독의 성공/부분 receipt 필드 차이와 미기록 분모 처리를 보완했다. Android·부하·센서·회수 경로는 바꾸지 않았다. [당시 PC 검증](results/resident_control_design_01/run02/preparation_verification.json)은 이후 수정의 검증으로 전용하지 않는다.

- ID: `ENERGY-AP-RESIDENT-CONTROL-02`
- 계획: `energy_ap_resident_control_plan_v2/collection_plan.json`
- 계획 SHA-256: `5073b2b95bf772db5ca89b8977f819b2403a797f739bc52d151ee9751352fde7`
- 재사용 APK SHA-256: `3d8ea871103c1350fb74e444c310be02ba8b3999cd6537691e75b457de4e94c2`
- 기존 프로젝트 인증서 SHA-256: `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`
- 출력: `energy_ap_resident_control_run_v2`; registry: `resident_control_registry/ENERGY-AP-RESIDENT-CONTROL-02`

예산은 C0→L24 2세션, runtime 8·warmup 16·본 요청 24·총 40추론, 별도 적격성 0, staging 2회·14파일, 설치본 pull/APK push/설치 각각 최대 1회였다. 고정 관측 30＋120＋60초/세션, 세션 간 90초. preflight 600＋세션 700×2＋90=2,090초, ADB 6,600명령(정리 예약 100). 세션 700은 stage 120＋poll 485＋회수 50＋cleanup 45의 합산 예약이다. 재시도·대체·추가 0. 정상 예상시간·완주 보장이 아니다.

준비된 PowerShell Check는 기기 명령 없이 통과했고, Run은 한 번만 호출했다. 당시 명령은 종료된 계획의 실행 이력이므로 이 보고서에 재실행 명령으로 제공하지 않는다.

## 실제 실행 결과

설치본 확인 단계의 host pull에서 종료됐다. 명령 0000은 목록, 0001은 모델, 0002는 fingerprint, 0003은 패키지 경로, 0004는 설치본 pull이었다. 목록의 단일 transport 선택 후 명령을 고정했다. 불필요한 식별값은 공유 결과에서 제외했다.

명령 0004는 2026-10-01 03:00:38.672→03:00:40.949 UTC에 실행됐고 host monotonic 경과 2.282초, exit 1/nonzero_exit였다. timeout이 아니다. stderr에 `cannot write ... installed-base.apk: Input/output error`와 26% 진행 출력이 있었다. stdout 0바이트를 전송 0바이트로 해석하지 않는다. 로컬 부분 파일은 28,966,912바이트이며 SHA-256은 `8d46b36d42ef236bef45f581f64b950b5d010898cc5cdfd3440f15c7daf5f40b`다.

직후 C: 여유 공간이 0바이트였다. **공간 고갈과 명시적인 로컬 쓰기 실패가 확인됐으며, 무선이나 원격 파일 오류는 입증되지 않았다.** 화면 timeout과 다른 실패 경계다. 부분 APK는 설치본 전체 동일성 검증에 사용할 수 없다.

| 항목 | 승인 상한 | 실제 소비 |
|---|---:|---:|
| 세션 시도/완료 | 2 | 0/0 |
| runtime/warmup/본 요청/총 추론 | 8/16/24/40 | 0/0/0/0 |
| staging/파일 | 2/14 | 0/0 |
| 설치본 host pull | 1 | 1, 부분 실패 |
| 후보 APK push/설치 | 1/1 | 0/0 |
| ADB 명령 | 6,600 | 5 |
| 전체 실행 시간 | 2,090초 | 8.360초 |
| 재시도/대체/추가 | 0 | 0 |

두 세션은 미시도이며 공식 관측·새 에너지/AP 오차가 없다. 0추론 판단은 단순한 로그 부재가 아니라 전체 명령 기록에 앱 launch가 없고 preflight에서 종료한 경계에 근거한다. 환경·품질 gate와 설치본 해시/서명 전체 검증에는 도달하지 않았다. 앱 cleanup·host force-stop은 앱을 시작하지 않아 해당 없음이고, 현재 앱 프로세스 부재는 조회하지 않았다. pull client는 비정상 exit를 반환했다. 최종 receipt와 stopped registry가 존재하며 재개할 수 없다.

## 공간 확보 후 PC 수정·검증

사용자 중지 요청 후 공간 확보를 기다렸고, 사용자 재개 요청에 따라 남은 PC 작업만 완료했다. 수집기 resident-control 진입에서 **후보 APK 바이트 수만큼의 최소 로컬 여유 공간을 claim·출력 생성·기기 명령 전에 검사**하도록 보완했다. free=0·부족이면 소비 없이 차단한다. 이 검사는 전체 로그 저장 예약이나 실제 설치본 크기·장시간 안정성 보장이 아니다. 설치본이 다른 크기일 가능성과 실행 중 공간 감소는 여전히 남는다.

이 수정은 plan_v2가 소비된 뒤 추가했으며 이번 기기 실행에서 검증됐다고 표현하지 않는다. frozen 실행 소스와 현재 수정 소스가 다르므로 종료 계획을 다시 Check/Run하여 재사용하지 않는다. PC 판독은 초기 실패 receipt에서도 미시도·cleanup 해당 없음·관측 null을 보존하고 허위 비교 그림을 만들지 않도록 보완했다. 첫 오류와 설치 단계 receipt를 별도로 보존했다.

```powershell
python -X utf8 -B -m unittest tools.test_d1_energy_screen tools.test_d1_resident_control_plan -v
python -X utf8 -B -m tools.d1_resident_control_report --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_plan_v2/collection_plan.json' --output 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_report_v2_reproduce'
```

관련 테스트 **14건 통과·실패/건너뜀 0**. 실제 Run 진입의 공간 부족→claim/기기 명령 전 차단, 실패 후 두 번째 세션 금지·소비 계획 재실행 차단, 원래 오류·부분 회수·단일 cleanup, 화면 marker/bytes/timeout 경계를 확인했다. 실제 원본 재판독은 명령 5건·launch 0·두 관측창 null·그림 없음·부분 APK 해시 불변을 확인했다. fake/PC 검증이며 실기기 연결·센서·장시간 안정성 검증은 아니다. Android/APK 변경·재빌드 없음. 기존 두 freeze와 후보 APK 해시 불변을 확인했다.

원본 30파일(28,981,719바이트)의 inventory는 별도 분석 폴더에 저장했고 판독 전후 내용 해시가 같았다. 원본·소비 registry·과거 FAIL·기존 C완료/L부분 자료를 보존했다. 이번 재개에서 기기 명령·설치·추론은 **0회**다. 공간 확인값과 검증 소스 해시는 [완료 검증](results/resident_control_design_01/run02/completion_verification.json)에 기록했다. 해당 시점 free 2,143,064,064바이트는 당시 값이며 지속 여유 보장이 아니다.

## 경로와 다음 경계

- [작은 공유 요약](results/resident_control_design_01/run02/summary.json), [결과 화면](results/resident_control_design_01/run02/index.html)
- 원본 receipt: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_run_v2/FINAL_RECEIPT.json`
- 별도 설치 receipt: 같은 원본의 `installation/installation_receipt.json`
- PC 최종 판독/inventory: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_report_v2_final`
- 과거 화면 조사: `C:/Users/LG/Documents/D1Check_Arrival_Extension/resident_control_screen_pc_v1/diagnosis.json`

모형·strict·기본 경로·experiment_ready=false는 유지한다. 이번 작업으로 대조 수집이나 새 모형 확인이 완료된 것은 아니다. 향후 실측은 공간 검사를 반영한 별도 ID의 새 계획과 승인이 필요하며, 이번에는 계획 생성·실측을 추가하지 않았다.
