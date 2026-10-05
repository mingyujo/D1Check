# Resident 대조 실행 01 — C 완료/L 부분 중단

2026-10-01, 실행 소스 HEAD `86a56fad01bf00c4ac1063cbefcc98cfd950c3a1`. 사용자 “실측 ㄱㄱ” 승인으로 `ENERGY-AP-RESIDENT-CONTROL-01`만 한 번 실행했다. **C 무부하 세션 정상 완료, L 등록 부하 세션은 화면 조회 timeout으로 중단·stopped_no_resume.** 재시도·대체·추가 실행·새 계획 없음.

## 계획과 실제 소비

[준비 계약](RESIDENT_CONTROL_MEASUREMENT_PLAN_20261001.md#실행-준비-완료-2026-10-01). 계획 SHA `7c200ab73b0f3868d9dc6088cf66a626300fead4937f4d92d7f8374e2f58e135`, APK SHA `3d8ea871103c1350fb74e444c310be02ba8b3999cd6537691e75b457de4e94c2`. Check 기기 명령0, 실행기 내부에서 현재 online transport 하나·동일 A24/fingerprint·서명·환경 확인. 초기 배터리75%, 비충전/BAT29.3°C/thermal0. 데이터 보존 업데이트 설치 후 동일 SHA 검증. 설정·화면·ADB daemon 변경/재연결 없음.

| 항목 | 승인 상한 | 확인 소비 |
|---|---:|---:|
| 세션 | 2 | 시도2 / 정상완료1 |
| runtime 생성/반환 | 8 | 8/8 |
| warmup 시작/반환 | 16 | 16/16 |
| 본 요청 | 24 | L24 / C0 |
| output_ready / persist / worker_release / lane_available | 각24 | 각24 durable event |
| 명시적 추론 / 별도 적격성 | 40 / 0 | 40 / 0 |
| staging | 2 / 14파일 | 2 / 14파일 |
| 설치본 pull / APK push / 설치 | 각1 | 각1 |
| ADB | 6,600 | 1,240 (0000–1239, 선택·정리 포함) |
| 전체 예약 | 2,090초 | 477.671초 |
| 재시도 / 대체 / 추가 | 0 | 0 |

설치·검증43.796초는 전체에 포함. 세션당 baseline30/common120/cooling60초는 정상 전체 예상시간이 아니다. C validated host 구간231.875초, 사이 대기90초. L의 최종 요청 result/품질 요약은 미회수라 반환 event24개를 세션 정상 완료로 승격하지 않는다. 기록 부재를0으로 채우지 않는다.

## 실패·종료 경계

`host_commands/1229/client/result.json`: filtered `dumpsys power` 화면 관측, UTC02:32:10.410618–02:32:12.409241, host monotonic 경과2.0초 timeout/exit1. stdout57바이트에는 `mWakefulness=Awake`와 `mHalInteractiveModeEnabled=true`만 있고 필수 종료 marker가 없다. stderr0은 내부 원인/전송량 증거가 아니다. root client는 종료·회수, 공유 ADB daemon은 종료하지 않았다.

직전 listing2개 및 이후 회수·force-stop·ps·thermal은 반환됐다. **error: closed/device not found나 연결 소실은 관측되지 않았다.** 2초 제한에 걸린 사실만 확정되며 명령 내부 지연 원인은 미확정이다. timeout 연장·반복 조회를 하지 않았다.

C artifacts10파일 정상 회수. L failure_prefix/progress540레코드(부분 줄0)·manifest·thermal 확보. common_end/최종 requests/cleanup 등은 유효 JSON으로 회수되지 않아 미확인/회수 실패다. 누락을 앱 실패로 확정하지 않는다. 최종 receipt는 중단 상태, 실패 host cleanup은 별도 파일에 성공 기록이 있다.

C app cleanup completed/sampler failure 없음. L app cleanup 미확인. owner force-stop1237/ps1238은 exit0, 정확한 대상 패키지 프로세스 부재 확인. 최종 Current temperatures from HAL AP30.7°C/BAT29.5°C/thermal0 (Cached 값 제외). host 실행 도구는 exit1. 이후 기기 재조회 없음.

## 관측과 분석 범위

[공유 화면](results/resident_control_design_01/run01/index.html), [요약](results/resident_control_design_01/run01/summary.json). 둘 다 구조 판별용 개발이며 독립 확인 아님.

C 시작 AP29.6°C, 조회 bracket0.22초, 조회 종료→실제 common 시작0.184552초. L host 승인 AP29.9°C/bracket0.19초, common_start event는 확보했지만 accepted 파일은 미회수. 두 값은 개발 시작32.5–34.0°C 밖이며 numeric-ap-observe-v2 관측 허용/strict PASS 미승격.

| C 고정창 (실제 common origin 기준) | J | 평균W | 전력 표본 | AP 평균°C |
|---|---:|---:|---:|---:|
| pre5–30초 | 32.392870 | 1.295715 | 25 | 29.713025 |
| late common90–120초 | 33.427816 | 1.114261 | 30 | 29.698014 |
| common0–120초 | 145.578444 | 1.213154 | 120 | 29.693385 |
| late cooling150–180초 | null | null | 30 | 29.760675 |

C common 종료 event는120.092589초지만 원래120초 창을 유지했다. 전체창 전력 bracket은 완전하다. 냉각은 마지막 전력179.174238초로0.825762초 부족하여 J/W=null, 창 축소/0채움 없음. AP는 별도 유효 bracket으로 계산한다.

C pre→late W **−0.181454W**: 본 작업 없이 시간 변화가 존재한다는 근거다. AP 평균은 거의29.7°C. 원인·부하의 순효과·범용 보정계수는 식별되지 않는다. 조건당1세션/고정순서/주변 미측정 한계 유지.

동결 resident W1.225433의120초 계산147.052011J 대 관측145.578444J, **+1.473566J (+1.012215%)**. 낮은 시작/새 프로토콜의 진단 산술이며 strict 예측 정확도/AP PASS가 아니다. 계수·후보 재적합 없음.

L 회수 전력 경로는60.167795초까지다. dispatch→lane_available event는35.005483–46.977172초, event 기반 CG_DC 병행 약1.509597초. 최종 행의 정확한 lane_available_ns 대신 callback 후 event mono_ns를 사용한 **부분 점유 추정**이며 host inference 겹침과 구분한다. 짧은 병행으로 전력 계수를 추정하지 않는다. **L전체120초 에너지/AP 비교·late window·C–L 차이의 차이=null.**

앱 origin·lane event·sensor midpoint·thermal의 기기 monotonic bracket을 상대초로 계산했다. host UTC/monotonic은 명령 시각이며 직접 앱 시계에서 빼지 않는다. HAL 내부 갱신시각은 미제공, 조회 신선도와 구분한다. 전류 raw=mA는 A24 조건부 해석/절대 에너지 정확도 미인증.

## 보존·PC 검증·재현

원본 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_run_v1/FINAL_RECEIPT.json`, artifacts/failure_prefix/host cleanup, `resident_control_registry/ENERGY-AP-RESIDENT-CONTROL-01`은 수정하지 않았다. 별도 `energy_ap_resident_control_report_v1/raw_inventory.json`에 원본6,337파일의 크기·해시를 보존했다. 개발 freeze/AP 후보 freeze/기존 FAIL/종료 계획/strict/default/experiment_ready=false 유지.

새 PC post-run 어댑터만 추가, 실행95파일 불변. [16개 증거 검사](results/resident_control_design_01/run01/verification.json): 계획/APK/입력/두 freeze 불변, C120초 적분, 부분L/null·냉각 결측, 소비·프로세스 부재·기존 분석 덮어쓰기 거절·CSV 범위. 실제 원본에서 검사했으며 신규 실기기/장시간 안정성 테스트는 아니다. PNG 직접 검토, L누락은 음영 표시. 과거 전체 테스트·빌드 반복 없음.

```powershell
# PC 전용; output은 존재하지 않는 새 경로. Run 아님.
python -X utf8 -B -m tools.d1_resident_control_report --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_plan_v1/collection_plan.json --output C:/Users/LG/Documents/D1Check_Arrival_Extension/resident_control_reproduce_unique
```

원본 receipt·C artifacts/progress/requests/common_boundary/cleanup·L failure_prefix/progress/manifest·각 thermal/start_ap_gate/host cleanup·host_commands 필요. 공유 CSV·그림 열람은 외부 원본 불필요.

**다음 PC 작업 하나:** 1229 partial stdout/marker와 인접 화면 조회의 지연·subprocess 종료 경계 비교. 종료 계획 재개/새 측정/즉석 timeout 변경/모형 적합은 하지 않는다.
