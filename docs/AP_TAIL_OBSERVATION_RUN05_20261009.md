# 긴 AP 유휴·부하 회복 재개 — 2026-10-09

사용자의 `C0부터 재개` 지시에 따라 중단된 시계를 이어 붙이지 않고 새 ID에서 C0부터 시작했다. 이 문서는 현재 실행의 근거와 종료 후 판독을 기록한다. 기존 plan_v2/v3/v4/v5와 부분 자료는 보존한다.

## 실행 전 동결

- ID: `ENERGY-AP-TAIL-OBSERVATION-05`.
- 계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_plan_v6/collection_plan.json`.
- 계획 SHA-256: `d5d4edfca4819b34595ac12c62e9d5c28e4fe2bae22f473a0636c0b55f0b7059`.
- 분석 계약: `results/ap_tail_observation_prep_05/analysis_contract.json`. 실제 파일의 해시는 계획에 고정했다.
- 재사용 APK SHA-256: `703d09d585a6b208e531ea36d19254071421e505acac5e350336894a71db200e`. 기존 프로젝트 서명·패키지·버전·소스 대응은 Check에서 확인했다. 이번 재빌드 0회.
- 원식 SHA-256: `5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2`.
- 후보 파일 SHA-256: `aa28410d701c9810001a4e6c176823e7d2b446f46f980ebeab3ff14f4540cc84`.
- Check: `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`, 미소비, 기기 명령 0회. 계획 파일의 미승인 표기는 실행 전 메타데이터이며 사용자 실행 승인·Run의 소비 기록과 구분한다.
- 검증 대상: 착수 HEAD `6ca596c4728f6c6e21224b57421ec50005e47ffa`＋명시적으로 등록한 ID05 경로와 관련 테스트의 미커밋 변경. 모델·APK·분석법·조회 주기·timeout은 변경하지 않았다.

## 질문과 예산

같은 4resident에서 C0_LONG → LOAD_A_LONG을 고정 순서로 관측한다. 무부하의 공통 시간 변화와 등록 부하 후 잔열 반응을 비교하며 `FROZEN`, `LOAD_SLOW`, `CLOCK_SHIFT`만 적용한다. 새 자료로 계수 추정·후보 선택·시간상수 grid 확대를 하지 않는다.

| 항목 | 상한 |
|---|---:|
| 세션 | 2 |
| runtime | 8 |
| warmup / 적격성 / 본 작업 | 16 / 8 / 1,200 |
| 총 명시적 추론 | 1,224 |
| staging / 파일 | 2 / 14 |
| 설치본 host pull / APK push / 설치 | 각 1 |
| 고정 baseline·공통·냉각 | 세션당 120＋600＋1,920초 |
| 고정 관측 합계 | 5,280초 |
| 전체 예약 | 9,050초 |
| ADB | 16,752 |
| 재시도·대체·추가 세션 | 0 |

고정 관측과 전체 timeout 예약을 정상 예상시간 또는 실제 벽시계 종료 보장으로 표현하지 않는다. 앱 watchdog은 3,540초이며 native hang·프로세스 정지를 항상 종료하는 보장은 없다.

저전량 사용자 승인에 따른 별도 계약: 시작·진행 ≥6%, ≤5% 중단. 비충전·BAT ≤35°C·thermal 0·화면·메모리·품질 조건은 유지한다. 절전 상태는 기록하며 설정을 바꾸지 않는다. numeric AP는 값·센서·단위·조회 신선도를 확인하고 32.5–34.0°C 개발 범위는 실행 하한으로 재적용하지 않는다.

## 판독 경계

- 실제 일정 조건부 예측 A이며 예정 도착부터의 종단간 예측 B는 아니다. 관측 부하 전 AP와 사전 정의된 전력 기준만 초기 입력으로 쓰고 이후 AP·전류는 평가 대상으로만 사용한다.
- 원 모형 시계의 등록 공통창 `[35,635]` 600초, 회복 `[635,실제 종료]`, 참고 `[0,120]`을 분리한다. 참고창에는 부하 전 35초가 포함된다.
- 전체 구간 끝을 센서가 덮지 않으면 전체 J와 오차는 null이고 실제 덮인 J·시간만 보고한다. 결측·끝점 외삽·0 채우기를 하지 않는다.
- 시작 AP·이력·저SOC·APK·관측 producer·장시간 범위의 전이/외삽을 별도로 표시한다. 시간상수 식별, 물리 원인, 정확도 PASS, 반복 안정성, 정책 우월성은 자동 완료하지 않는다.
- 앱 cleanup, host force-stop, 프로세스 부재, host parent/child 종료를 분리한다. 실패·회수·cleanup 오류를 원래 오류에 덮어쓰지 않는다.

## 실행과 결과

**두 조건 모두 완료했다.** 원 receipt는 `completed_regimen_diagnostic_only`이며 새 자료 fit은 0회다. C0와 LOAD_A의 앱 cleanup·host cleanup·원자료 회수·적격성 검증이 모두 통과했다. parent1164/child9120은 실제 프로세스 조회에서 부재했다. 연결 소실·lifecycle_cancelled는 이번 기록에서 관측되지 않았다. 이를 과거 원인 해결 또는 단절 내성 검증으로 확대하지 않는다.

### 실제 소비

| 항목 | 실제 / 상한 |
|---|---:|
| 세션 | 2 / 2 |
| runtime | 8 / 8 |
| warmup / 적격성 | 16 / 16, 8 / 8 |
| 본 작업 | 857 / 1,200 |
| 총 명시적 추론 | 881 / 1,224 |
| staging / 파일 / 설치본 pull | 2 / 14 / 1 (각 상한 이내) |
| ADB | 내부9,029＋현재 transport 선택1 = 9,030 / 16,752 |
| 전체 실행·회수·cleanup | 5,837.765초 / 9,050초 |
| APK push / 설치 | 0 / 각1 |
| 재시도·대체·추가 세션 | 0 |

설치본 해시가 후보와 같아 재전송·설치를 생략했다. 최대 호출 슬롯과 실제 완료 호출을 구분한다. 등록 부하는 고정 시간 안의 실제 처리율로 수행하므로 상한1,200을 채우기 위한 추가 호출·감속·sleep·연장이 없다. C0의 본 작업은0이며 LOAD_A가857회를 수행했다. 나머지343상한 슬롯을 실행 실패 또는 예정 요청의 미완료로 분모에 넣지 않는다.

원 journal의 dispatch·request_start·output_ready·worker_release·lane_available는 C0 각4(적격성), LOAD_A 각861(적격성4＋본857)로 일치했다. warmup 시작/반환은 각각8, runtime 시작/반환은 각각4다. 정상 자료 검증과 함께 확인했으며 기록 없는 호출을0으로 가정하지 않았다. LOAD_A의 본 호출은 CPU분류240 / CPU탐지98 / GPU분류194 / 병행분류226＋탐지99다.

ADB 결과는 returned9,023 / exit1 6이다. exit1은 새 세션 입력·출력·tmp 경로의 사전 부재를 확인한 `test -e`이며 기기 실패가 아니다. timeout·추가 재시도는0이다. host force-stop은 설치본 preflight 정리1＋정상 세션 뒤 각1=3회이며 대상 앱만 처리했다. 종료 후 프로세스 부재와 앱의 정상 cleanup을 별도로 확인한다. journal에는 onCreate와 cleanup 후 finish_requested가 남았고 이후 callback 전체가 저장됐다고 보장하지 않는다.

### AP 확인 결과

원 모형 시계 `[35,635]` 공통창＋`[635,약2555]` 회복의 확보된 AP 표본을 사용한다. baseline 전체까지 포함한 MAE가 아니다. 표본은 독립 반복이 아니며 각 조건은 한 실행 block이다.

| 조건·모형 | 공통＋회복 MAE °C | 최대 절대오차 °C | 최고온도 오차 °C | 회복 MAE °C |
|---|---:|---:|---:|---:|
| C0 / FROZEN = LOAD_SLOW | 0.0908 | 0.3978 | −0.3769 | 0.1141 |
| C0 / CLOCK_SHIFT | 0.8726 | 1.1326 | +0.7660 | 0.9802 |
| LOAD_A / FROZEN | 0.4371 | 1.8990 | +0.2134 | 0.4036 |
| LOAD_A / LOAD_SLOW | 0.1728 | 1.2343 | +0.2005 | 0.1686 |
| LOAD_A / CLOCK_SHIFT | 0.5736 | 1.3750 | +0.2015 | 0.6866 |

LOAD_A에서 사전 고정 LOAD_SLOW의 경로 MAE가 약60.5% 줄었다. 공통600초 MAE도0.5437→0.1862°C, 회복 MAE도0.4036→0.1686°C다. 관측 회복 변화량−0.700°C에 대해 FROZEN−0.077°C / LOAD_SLOW−0.633°C / CLOCK_SHIFT+0.264°C로, 느린 부하 항이 이번 회복의 방향과 크기를 더 잘 설명했다. 다만 전환의 최대 오차1.234°C는 남는다.

C0는 AP 초기28.2°C·관측 최고28.6°C·표본 첫/끝28.2→28.5°C, LOAD_A는 초기28.5°C·최고33.2°C·첫/끝28.5→28.8°C다. C0 후반에도0.3°C 변화가 있어 공통 조건 이동을 완전히 배제할 수 없다. 사전 고정 CLOCK_SHIFT는 두 조건 전체 경로에서 더 큰 오차를 보였다. **이는 특정 공통 clock 가설보다 등록 부하 의존 항을 지지하는 확인 근거이며, 물리적 열 상태나 τ=1,920초의 유일 식별은 아니다.** 한 고정 순서의 C0→LOAD block으로 순서·주변 조건·이력 교란이나 반복 변동성을 없애지 못한다.

두 초기값 모두 기존32.5–34.0°C 밖이다. 후보 개발 자료의 부하 전 마지막 AP26.5–28.8°C 안에 있어도 긴 지평·새 APK·관측 방식의 전이 진단을 strict 지원으로 승격하지 않는다. 이전 사후 평가에서 악화한 조건들도 그대로 유효하며 이번 한 block으로 전체 후보 우수성을 선언하지 않는다.

### 에너지·센서·실행 상태

| 조건 / 원 모형 시계의 창 | 관측 J | 기존 예측 J | 예측−관측 J | 상대차이 |
|---|---:|---:|---:|---:|
| C0 / `[35,635]`600초 | 600.1445 | 586.9969 | −13.1476 | −2.1907% |
| LOAD_A / `[35,635]`600초 | 751.0277 | 735.8769 | −15.1508 | −2.0173% |
| C0 / `[0,120]`참고창 | 118.9587 | 117.3994 | −1.5593 | −1.3108% |
| LOAD_A / `[0,120]`참고창 | 151.3626 | 140.2714 | −11.0912 | −7.3276% |

에너지식은 변경하지 않았다. 참고창에는 등록 시작 전35초가 포함되므로600초 결과와 섞지 않는다. 냉각 전체 J와 오차는 두 조건 모두 null이다: C0 끝0.350초, LOAD_A 끝0.578초의 전력이 없다. LOAD_A의 덮인1,919.510초 관측1,891.406J 역시 전체 냉각J가 아니다. A24 raw=mA 해석은 조건부이며 절대 정확도는 미인증이다.

- AP 평가 표본 C0 881 / LOAD_A 923, 전력 표본3,094 / 3,092. AP 최대 간격3.98 / 4.86초, 전력 최대 간격0.918 / 0.928초. 조회 간격이 센서 내부 갱신 주기라는 보장은 없다.
- LOAD_A 실제 점유: 분류CPU38.511초, 탐지CPU60.237초, 분류GPU59.982초, 분류GPU＋탐지CPU59.966초. 작업 종료 이후 모두 resident 유휴다. 600초의 나머지381.304초는 유휴다. 예정 블록 길이와 실제 lane 점유를 구분한다.
- 관측된 AP 및 이후 전류는 예측 입력이 아니다. 부하 전 AP28.2/28.5°C와 사전 고정 초기화·실제 일정만 사용했다. 실제 battery·절전·환경 이력은 원 journal에 보존한다.
- C0 배터리64→64%, LOAD_A64→61%, 절전false, BAT 최고29.1/29.3°C였다. 저전량 opt-in 계약을 사용했지만 실제 저전량에서의 성능 확인은 아니다. 시작 AP 조회 span0.490/0.280초, 조회 종료→실제 시작0.215/0.268초, 조회 시작→실제 시작0.705/0.548초로 신선도3초 안이다. 이는 조회 신선도이며 센서 내부 갱신시각 보장은 아니다.

### 산출물·재현·종료 기준

[실제 곡선·잔차·소비 화면](results/ap_tail_observation_run_05/run_v6/index.html) · [세션별 AP 오차](results/ap_tail_observation_run_05/run_v6/metrics.csv) · [J 및 결측](results/ap_tail_observation_run_05/run_v6/energy.csv) · [분석 입력](results/ap_tail_observation_run_05/run_v6/inputs.json.gz).

[검증 요약](results/ap_tail_observation_run_05/run_v6/verification.json): 고정 소스163파일·APK·원식·후보 해시 불변, 호출 경계 일치, 작은 공유 입력으로18 AP행＋6 J행의 모든 수치를1e-9 이내 재현했다. 원 자료 판독기 수치와 별도로 대조했고 C0/LOAD AP 그림의 축·라벨·잔차·실제 상태 표시를 확인했다. 새 ID 경계 테스트1건과 Check(기기0회)가 실행 전 통과했으며 과거 전체 테스트·APK 빌드는 반복하지 않았다. 작업 중 다른 정책/RL 작업의 HEAD가 진행됐으나 동결된 소스163파일은 바뀌지 않았다.

원자료 의존 재현(새 출력 폴더 사용, 기기 명령·fit 0):

```powershell
& 'C:/Users/LG/AppData/Local/Programs/Python/Python311/python.exe' -B -m tools.d1_ap_tail_observation_results --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_plan_v6/collection_plan.json' --output 'output/ap_tail_reproduce_v6' --external-adb-commands 1
```

이번 완료 범위는 두 장시간 조건의 관측·고정 모형 확인·회수·오차 산출이다. 기본/RL/strict/experiment_ready=false는 변경하지 않는다. 새 후보 fit·추가 실측·새 계획은0이다. 다음 PC 작업 하나는 **기존 악화 조건과 이번 장시간 확인을 함께 반영해 LOAD_SLOW의 별도 opt-in 평가 지원 경계를 고정하는 것**이다.

### C0 완료 체크포인트

- 세션 실행 2,857.391초. runtime4 / warmup8 / 적격성4 / 본 작업0.
- 전체 AP 경로 MAE: FROZEN = LOAD_SLOW 0.0908°C, CLOCK_SHIFT 0.8726°C. 최대 절대오차는 각각 0.3978°C / 1.1326°C. 무부하에는 LOAD_SLOW의 추가 부하 항이 0이어서 FROZEN과 같은 예측이다.
- 등록600초: 관측600.1445J, 예측586.9969J, 예측−관측−13.1476J(−2.1907%). 참고120초: 관측118.9587J, 예측117.3994J, 차이−1.5593J.
- 냉각 전체1,920.1567초의 전력은1,919.8066초만 덮었다. 끝0.3501초가 비어 전체 냉각J/오차는 null이다. 덮인 구간의 관측1,901.3524J를 전체 값으로 바꾸지 않는다.
- 현재 자료는 장시간 전이 진단이며 정확도 PASS·τ 식별·후보 채택이 아니다. C0 결과를 보고 예정된 LOAD_A나 후보를 바꾸지 않았다.

원본: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_run_v6`.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_tail_observation_plan_v6/RUN_AFTER_APPROVAL.ps1' -Action Check
# Run은 이미 1회 호출했다. 소비된 계획은 다시 실행하지 않는다.
```

다른 사용자 변경·worktree·정책/RL 작업은 보존한다. 기본 시뮬레이터·RL·strict·experiment_ready=false는 그대로다.
