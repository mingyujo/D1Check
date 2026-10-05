# AP 두 이력 일괄 확인02 — 실행·판독

**두 확인 세션·회수·고정 판독 완료**, `completed_descriptive_only`. 고정 AP 후보의 MAE는 0.450/0.405°C였으나 후기 재상승을 재현하지 못했다. 기존 W식의 공통120초 에너지는 +7.01/+9.47% 과대 예측했다. 모형 전체 완성·정확도 PASS·정책 우월성 판정은 아니다. [공유 화면/CSV/그림](results/ap_bundle_confirmation_01/run02/index.html).

2026-10-02, 착수 HEAD `1352872fbd264b3711ff6c3764d5f4b9200026ae`/작업 트리 clean·실제 원격 일치. 사용자 “실측 진행하자”와 “문제 있으면 알아서 해결하면서 실측 끝내놔”로 기존 두 이력 확인의 새 실행을 진행했다. 종료된01은 재개하지 않았다. [기존 측정/판독 계약](AP_BUNDLE_CONFIRM_RUN01_20261001.md)과 [고정 분석 계약](results/ap_bundle_confirmation_01/analysis_contract.json)을 그대로 사용했다. 현 APK/모형 계수·부하·센서·gate·timeout·순서 변경 없음. PC 실행 ID만 별도 edition2로 연결했다.

## 실행 전 동결

`ENERGY-AP-BUNDLE-CONFIRM-02`, 계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_bundle_confirm_plan_v2/collection_plan.json`, SHA `f11992add4461070605f953f531193c3858767865bf609c8a1a50248b9d03f89`. 출력 `energy_ap_bundle_confirm_run_v2`, registry `ap_bundle_registry/ENERGY-AP-BUNDLE-CONFIRM-02`는 기기 작업 전 존재하지 않았다. [검증 대상·소스/APK/manifest/freeze 해시](results/ap_bundle_confirmation_01/run02/pre_execution_verification.json).

기존 APK `3d8ea871103c1350fb74e444c310be02ba8b3999cd6537691e75b457de4e94c2`/기존 프로젝트 서명, 원래 모형 `35ed6987…034c54`/preload 후보 절차 `8507adc1…bc7ec5`를 재사용한다. PC 관련10검사·실제 PowerShell Check 통과, Check 기기0. old01 host parent/child 종료·registry stopped 및 원본14파일 보존을 PC에서 확인했다. 새 ID별 session/request ID를 제외한 등록 요청·budget은01과 동일하다. 현재 기기/설치본/환경은 Run 내부에서 새로 확인한다.

| 항목 | 실행 상한 |
|---|---:|
| 개발/확인 | 0/2 (한 pulse→두 half-pulse, 조건당1세션) |
| 본 요청/warmup/적격성/총 추론 | 48/16/0/64 |
| runtime/staging/파일 | 8/2/14 |
| 설치본 pull/APK push/설치 | 1/0/0 |
| baseline/common/cooling | 30/120/60초씩, 고정 합420초 |
| preflight/각세션/세션간 자연대기 | 600/700/90초 |
| 각세션 stage gate/poll/회수/cleanup | 120/485/50/45초 |
| 전체/ADB | 2,090초/6,600명령 |
| 재시도/대체/추가 | 0/0/0 |

조회·잔여시간/종료 예약·설치본 불일치 시 중단·현재 transport 한 개 선택·소유자 회수/cleanup 규칙은01 계약 그대로다. 환경 gate는 배터리≥20%·비충전·BAT≤35°C·thermal0·고정 화면·memory/8warmup 품질이며 numeric AP는 유효/신선 조건이다. 32.5–34.0°C는 모형 개발 범위 표시이고 실행 하한으로 재사용하지 않는다. 측정 중 대상 Activity 유지가 필요하며 host가 다른 화면을 열거나 설정을 바꾸지 않는다.

## 판독 고정

후보 β/상태 기울기·식은 고정, 각 세션 baseline 이후/첫 dispatch 이전 AP(≥15개/span≥55초/gap≤10초)의 유효 유휴 기준만 사용한다. 시작 AP와 실제 lane 일정의 조건부 진단이며 부하 후 AP/current를 예측 입력으로 사용하지 않는다. J는 정확한0–120초/원래 동결 W·raw=mA 조건부, AP는 첫 dispatch→냉각 끝 유효표본에서 평가한다. 후기 방향은 [90,115]/[120,145]/[150,175]초 고정·bracket 없으면 null이다. strict/default/accuracy_pass/policy_rank/experiment_ready=false를 승격하지 않는다. 열모형 전체/온라인 정책/독립 변동성 증명이 아니다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_bundle_confirm_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_bundle_confirm_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -ExpectedPlanSha256 'f11992add4461070605f953f531193c3858767865bf609c8a1a50248b9d03f89'
python -X utf8 -B -m tools.d1_ap_bundle_readout --plan '<energy_ap_bundle_confirm_plan_v2/collection_plan.json>' --output '<새 PC 판독 폴더>'
```

위 Check/Run은 **실행 당시 명령 기록**이다. 현재 plan_v2/registry는 소비·완료 상태이며 다시 실행하지 않는다. 소비 후 실제 PowerShell Check는 exit1, Python Check는 `occupied/consumed plan; no resume`로 기기 명령 없이 거절했다. PC 판독 명령만 새 출력 폴더에 재현할 수 있다.

## 실제 실행과 소비

현재 목록에서 단일 무선 mDNS transport를 선택하고 동일 A24/fingerprint·설치본/프로젝트 서명을 실행기 내부에서 확인했다. 설치본 SHA는 기대 `3d8ea871…4e94c2`와 일치해 APK 전송·설치를 생략했다. transport 전환·자동 재연결·설정 변경·다른 앱 종료·외부 중복 ADB 조회 없음. 실제 PowerShell→Python 실행 exit0, 최종 receipt/registry 모두 완료다.

| 항목 | 상한 | 실제 |
|---|---:|---:|
| 확인 세션 | 2 | 2 정상 완료 |
| 본 요청/시작/반환/저장/worker·lane 해제 | 각각48 | 각각48 |
| runtime 생성/반환 | 각각8 | 각각8 |
| warmup 시작/반환 | 각각16 | 각각16 |
| 별도 적격성/총 명시적 추론 | 0/64 | 0/64 (warmup 품질 확인 포함) |
| staging/파일 | 2/14 | 2/14 |
| 설치본 host pull/APK push/설치 | 1/0/0 | 1/0/0 |
| ADB | 6,600 | 1,343 |
| 전체 실행·회수·cleanup | 2,090초 | 616.410435초 |
| 설치본 preflight/두 세션 | 600/각700초 | 35.681520/245.616028·241.522814초 |
| 재시도/대체/추가 | 0/0/0 | 0/0/0 |

잔여시간 gate를 통과하고 등록된 세션간 자연 대기90초를 포함해 완료했다. 고정 관측 요청은 각210초·총420초로 동일하다. 실제 common_end는 120.032/120.023초였으나 **에너지 적분·비교는 원래 계획의 정확한 [0,120]초**로 유지했다. 명령1,337건은 exit0,6건은 staging 전 새 경로의 `test -e` 부재를 확인한 예상 exit1이며 timeout/연결 소실/예외 중단은 관측되지 않았다. 로그 부재를 호출0으로 해석하지 않았고, 두 `validated.json`의24개 terminal succeeded·unfinished0과 진행 기록을 함께 대조했다. legacy `request_return`0은 실제24개 `host_inference_return`과 다른 종류다.

## 자료 적격성과 실제 일정

| 항목 | 한 묶음 | 두 반묶음 |
|---|---:|---:|
| 시작 AP / 부하 전 유효 유휴 기준 | 28.1 / 27.861085°C | 28.7 / 28.488831°C |
| AP 조회 종료→common 시작 | 0.299037초 | 0.265066초 |
| 부하 전 AP 표본 / span | 23 / 64.900초 | 23 / 63.545초 |
| 실행 전 배터리 / BAT | 56% / 27.8°C | 56% / 28.4°C |
| 실제 lane CG_DC 병행 | 1.609444초 | 0.822579초 |
| 실제 host inference 겹침 | 0.997541초 | 0.492030초 |
| idle / 탐지CPU 단독 / 분류GPU 단독 (120초) | 108.383799 / 9.794257 / 0.212500초 | 107.498567 / 10.512107 / 1.166747초 |
| 전체 power / HAL thermal 표본 | 223 / 77 | 223 / 78 |
| power 실제 중앙/최대 간격 | 1.000423 / 1.043036초 | 1.000026 / 1.040982초 |
| AP 평가 표본 / 실제 범위 | 49 / 37.325963–178.575963초 | 50 / 35.394934–179.474934초 |
| AP 평가 최대 간격 | 3.705초 | 3.630초 |

단독/병행은 실제 dispatch→lane_available로 분류했다. host 추론 겹침과 lane 점유를 같은 값으로 취급하지 않는다. 각24개 도착·release·dispatch·응답·저장·worker/lane 경계는 공유 `actual_request_timing.csv`,49개 실제 상태 구간은 `actual_states.csv`에 보존했다. 시간은 공통창 Android monotonic 시작을0으로 변환했으며 host wall clock과 직접 혼합하지 않았다.

두 세션 모두 비충전/thermal0·고정 화면·memory 및 warmup 품질 기준을 통과했다. HAL 전체 최대 공백19.150/14.715초는 각각 common 시작 이전 [-60.929,-41.779]/[-57.110,-42.395]초 준비 구간에 있다. 이를 숨기지 않으며, 후보에 사용한 preload 및 부하 후 평가 표본은 별도로 사전 coverage 기준을 통과했다. HAL AP 조회 주기와 하드웨어 내부 갱신 주기는 같다고 보장하지 않는다. 초기 AP는 원래 개발32.5–34.0°C 밖이며 짧은 전환도 기존 strict 미지원이다. 관측 적격성과 모형 지원은 별도다. 짧은 병행으로 독립 병행 전력 계수를 식별하지 않는다.

## 고정 모형 판독

후보의 식·β·상태 기울기는 실행 전 freeze 그대로이고 부하 후 AP로 재보정하지 않았다. E는 세션별 **부하 전 AP로 산출한 유효 유휴 기준**이며 주변 온도/숨은 내부 상태의 실측값이 아니다. 실제 시작 AP·실제 lane 일정과 preload AP를 사용한 회수 후 조건부 재구성이다. 실행 전에 모든 미래 경로를 예측한 온라인 정책/종단간 검증으로 표시하지 않는다. 각 이력의 새로운 독립 세션은1개이고, APK/protocol은 원래747계열 후보 개발과 분리된3d8 전이 확인이다.

| 출력 (예측−관측) | 한 묶음 | 두 반묶음 |
|---|---:|---:|
| 정확한120초 관측 J | 145.621340 | 142.351264 |
| 원래 W식 예측 J | 155.826510 | 155.834602 |
| J 부호/절대 차이 | +10.205170 / 10.205170 | +13.483338 / 13.483338 |
| J 상대차이 | +7.008018% | +9.471878% |
| 원래 AP식 MAE | 5.911910°C | 5.350159°C |
| 고정 preload 후보 AP MAE | 0.449945°C | 0.404970°C |
| 후보 AP 최대절대차이 | 1.015364°C | 0.691399°C |
| 후보 진단 최고 AP 차이 | −0.617139°C | −0.360659°C |

AP 평가 절차의 범위는 첫 dispatch35.006610/35.010016초→cooling 끝180.124749/180.096923초다. 위 MAE/최대/최고 값은 그 안에 확보한 유효 표본만으로 산출했고 첫/끝 결측 구간을 채우지 않았다. 최고 차이는 **기술적 진단 점수**일 뿐 지원된 안전 최고온도/한도초과 시간 예측이 아니다.

| 고정 방향창 (초) | 한 묶음 관측 / 후보 Δ°C | 두 반묶음 관측 / 후보 Δ°C |
|---|---:|---:|
| 90–115 | +0.100000 / −0.110623 | −0.027887 / −0.230895 |
| 120–145 | 0.000000 / −0.027914 | 0.000000 / −0.058018 |
| 150–175 | +0.200000 / −0.007028 | +0.100000 / −0.014669 |

전체 부하 후 유휴의 첫/끝 유효 AP 표본 변화는 한 묶음 관측−1.000/후보−1.064639°C, 두 반묶음 관측+0.100/후보−0.744975°C다. 첫 이력의 전체 냉각 방향이 맞아도 모든 후기 창 방향이 맞는 것은 아니며, 두 이력의 유휴 반응 차이를 단일 평균 MAE로 감추지 않는다.

사전 고정된 endpoint bracket으로 계산했으며 창 이동/끝 외삽/누락0 채움은 없다. 두 후기 표본 창에서 작은 재상승이 관측됐지만 후보는 냉각을 예측했다. 양자화/조회 시각 불확실성이 있고 보편 유의성 기준이 없으므로 이 차이를 물리 원인 확정이나 통계적 안정성으로 표현하지 않는다. 평균 오차 개선과 후기 방향 미재현이 함께 남는다.

120초 J 잔차를 pre/load/post idle로 분해하면 한 묶음 **+0.039001/+2.471236/+7.694933J**, 두 반묶음 **+3.424245/+6.343308/+3.715785J**다. 구간합은 전체 차이와 일치하며 이번 두 세션의 큰 구간들에서는 반대 부호 상쇄로 전체 차이가 줄어든 결과가 아니다. 두 부하 이력/초기조건의 J 총량을 자원·정책 우열로 해석하지 않는다. raw=mA 해석의 조건부 성격·절대 에너지 정확도 미인증은 유지한다.

**완료 범위:** 등록된 두 이력에서 변경 없는 후보 절차의 새로운 AP 오차와 후기 방향을 확인했고 원래 W식의 진단 차이를 확보했다. 현 A24/4resident/CG_DC/저온·단기 이력의 조건부 진단 근거다. 후기 열 방향/최고/한도·미래 유휴 W·동적 정책 J/AP 순위의 근거는 아직 부족하다. 후보의 기본 경로 채택·strict/experiment_ready=true 승격·계수 적합/추가 세션 없음. 과거 고정870건 비교와 저장 서비스 일정의 제한 범위는 그대로다.

## 종료·보존·검증

두 앱 `summary.json` completed→cooling phase_end→app_cleanup completed/error null/sampler_failure null→finish_requested 기록을 회수했다. 이후 원 소유자의 host 정리가 각각 `force-stop`677/1340(exit0)→`ps -A`678/1341(exit0·대상 패키지 부재)로 한 번씩 수행됐다. 앱 정상 cleanup, host force-stop, 프로세스 부재는 서로 다른 사실이다. parent/child는 실행 ID·시작시각/명령 근거로 모두 exited, registry completed 및 정상 최종 receipt 존재. 관측된 lifecycle_cancelled/연결 소실 없음은 앞으로의 모든 실행 안정성이나 과거 원인 해결을 뜻하지 않는다. 종료 후 새로운 기기 명령은 추가하지 않았다.

- 원본: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_bundle_confirm_run_v2/FINAL_RECEIPT.json`, 각 세션 `artifacts/`, `thermal.jsonl`, `recovery.json`, `host_cleanup.json`, root `host_commands/`·`host_checkpoints/`. 회수58파일씩, prefix_errors0.
- PC 판독·전체 inventory: `C:/Users/LG/Documents/D1Check_Arrival_Extension/ap_bundle_run02_pc_20261002/readout/`. 원본6,993파일/115,676,781바이트를 해시 재대조했다. 설치본 APK가 포함돼 Git에는 올리지 않는다.
- 공유: [화면](results/ap_bundle_confirmation_01/run02/index.html), [점수](results/ap_bundle_confirmation_01/run02/metrics.csv), [고정 방향](results/ap_bundle_confirmation_01/run02/fixed_directions.csv), [작은 결과/소비](results/ap_bundle_confirmation_01/run02/summary.json), [최종 검증](results/ap_bundle_confirmation_01/run02/verification.json). 원본 명령/기기 식별정보/키·APK·모델은 제외했다.
- PC10검사 PASS·skip0, 실제 PS Check/Run와 실제 분석 CLI exit0. source/두freeze/APK/manifest/plan·old01 핵심18파일 불변, CSV/점수·120초·구간합·AP 잔차·4그림 육안 확인. 소비 후 Check 거절도 확인했다. 추가 빌드/Android 수정0, 분석 기기 명령0.

**다음 PC 작업 하나:** 이번 고정 후보의 두 이력 점수를 제한 시뮬레이터 결과 본문에 반영하고, 후기 방향·최고·동적 J/AP 순위를 미판정으로 유지한 평가를 마무리한다. 추가 실측·후보 재적합을 자동 시작하지 않는다.
