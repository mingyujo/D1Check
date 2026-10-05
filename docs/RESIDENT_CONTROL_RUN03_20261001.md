# Resident 무부하 대조 실행03 결과 — 2026-10-01

**C 무부하와 L 등록 부하 두 세션 모두 정상 완료·회수했다.** 상태는 `completed_descriptive_only`, 계획03은 소비·종료됐으며 재실행하지 않는다. 모델 적합·독립 확인·정확도 PASS·정책 우월성 판정은 수행하지 않았다. [공유 화면](results/resident_control_design_01/run03/index.html), [고정창 CSV](results/resident_control_design_01/run03/windows.csv), [검증](results/resident_control_design_01/run03/verification.json).

## 실행과 동일성

사용자 “진행하자”를 직전 동결 계획03의 1회 실행 승인으로 적용했다. 착수 HEAD `0e8e18ffb0416963c18b416a7a030479945660df`, 현재 작업 브랜치·실제 원격 HEAD 일치·clean이었다. 다른 worktree를 변경하지 않았다. 실행 중 소스 변경은 없고 STATUS 진행 기록만 갱신했다. 실제 PowerShell Check 통과 후 Run 1회, host exit0, registry `completed.json`을 보존했다. APK 재빌드·재서명·추가 진단 없음.

- 계획 `energy_ap_resident_control_plan_v3/collection_plan.json`, SHA-256 `2e9b3fcd6eaa02b6ce820cd34a4b660125b70cb4c35328e804303623ea7bf6d8`.
- 재사용 APK SHA-256 `3d8ea871103c1350fb74e444c310be02ba8b3999cd6537691e75b457de4e94c2`, 설치본 host pull1로 동일성을 확인해 후보 push/설치를 생략했다. 패키지·버전·프로젝트 인증서 확인은 원본 installation 기록에 있다.
- 실행 소스95개·입력 파일·두 manifest·계획·APK 해시 불변. 원래 에너지/AP freeze `35ed6987…034c54`, AP 후보 freeze `8507adc1…cbc7ec5` 불변.
- 원본은 외부 `energy_ap_resident_control_run_v3`; 판독 전 inventory 7,923파일/114,841,442바이트를 판독 후 전체 재대조해 모두 불변. 키·APK·모델·원자료·transport 식별정보는 저장소에 넣지 않는다.

## 승인 대비 소비

| 항목 | 상한 | 실제 |
|---|---:|---:|
| 세션 | 2 | 시도2·정상 완료2 |
| runtime 생성 | 8 | 시작8·반환8 |
| warmup | 16 | 시작16·반환16 |
| 본 요청 | 24 | C0＋L24, 모두 성공 |
| 총 명시적 추론 | 40 | 40 |
| 별도 적격성 추론 | 0 | 0; warmup 품질 검사 |
| staging | 2회·14파일 | 2회·14파일 |
| 설치본 host pull | 1 | 1, 완전 회수 |
| 후보 APK push/설치 | 각각1 | 각각0, 동일 설치본 생략 |
| 고정 관측 | 420초 | 각 baseline30＋common120＋cooling60 수행 |
| 세션 사이 예약 대기 | 90초 | 계약대로 수행 |
| 전체 예약 | 2,090초 | **679.531초(11분19.531초)** |
| ADB 명령 | 6,600 | **1,543** |
| 재시도·대체·추가 | 0 | 0 |

L 본 요청의 시작/output_ready/persist_complete/worker_release/lane_available는 각각24, 성공24·미완료0이다. runtime/warmup도 durable 이벤트 시작·반환을 확인했다. 1,543 client 기록 중 returned1,537/nonzero_exit6: 6건은 새 실행 경로의 `test -e` 부재 확인이다. timeout·관측된 연결 소실·lifecycle_cancelled는 없다. 출력0을 전송0의 증거로 사용하지 않았다. 추가 사후 기기 명령0.

## 환경과 실제 상태

실행기가 현재 단일 transport와 동일 A24·설치본을 확인했다. C 시작 배터리67%/BAT26.7°C, L66%/BAT27.6°C, 비충전 및 화면·thermal·메모리·warmup 품질 gate 통과. numeric AP 시작은 C27.3°C/L27.7°C, 조회 bracket0.290/0.260초. 두 시작값 모두 동결 개발 범위32.5–34.0°C 밖이며 실행 하한으로 사용하지 않았다. 조회 신선도는 센서 내부 갱신시각 보장이 아니다.

C 공통120초는 resident idle이다. L은 원래 burst·seed201·B2의 도착/backend와 release+35초를 유지했고, PC 간섭계수1.5를 기기 감속으로 구현하지 않았다. 실제 lane 상태는 다음과 같다.

| L 상태 | 공통120초 내 시간 |
|---|---:|
| resident idle | 108.435658초 |
| 탐지 CPU 단독 | 9.758400초 |
| 분류 GPU＋탐지 CPU | **1.455957초** |
| 분류 GPU 단독 | 0.349986초 |

실제 lane 해제 기준으로 분류했으며 host inference 겹침이나 제출 간격을 병행 시간으로 대신하지 않았다. 짧은 병행만으로 별도 병행 전력 계수를 정밀 식별하지 않는다. [상태 경계](results/resident_control_design_01/run03/states.csv)와 [lane](results/resident_control_design_01/run03/partial_load_lanes.csv)를 공유했다.

## 고정창 전력·AP 판독

창을 사후 이동하지 않았다. power 최대공백2.5초/AP10초, resident4·부하 부재 조건을 적용했다. 공통0–120초는 두 arm 모두 전력·AP bracket 유효, power 각120표본이다. app monotonic origin에 sampler snapshot/read 중간시각을 정렬하고 host AP bracket을 기존 변환으로 정렬했다. app common 종료가 실제120초를 약간 넘었어도 분석 끝은 정확히120초다.

| 창 | C 평균W | L 평균W | C AP 평균°C | L AP 평균°C |
|---|---:|---:|---:|---:|
| 부하 전5–30초 | 0.971881 | 1.195793 | 27.308924 | 27.769377 |
| 후기90–120초 | 0.989955 | 1.011505 | 27.381254 | 28.073750 |
| 냉각후기150–180초 | 1.130933 | null | 27.541410 | null |

전력 표본 수는 pre25/late30/cooling30이다. L 냉각후기는 마지막 power 표본179.823839초라 **0.176161초 결측**, AP 끝 bracket도 없다. 세션 정상 완료와 특정 고정창 자료 부적격은 별개다. 이 창의 J/W/AP는 null이며 다른 창으로 대체하거나 결측0을 채우지 않는다. C 마지막 표본180.006405초는 끝을 bracket한다.

C의 pre→late 평균W 변화는 **+0.018073W**, L은 **−0.184287W**, 변화 차이 L−C는 **−0.202361W**다. AP 평균 변화는 C+0.072329°C/L+0.304373°C다. C 무부하에서도 시간에 따른 W/AP 변화가 있고 L의 전후 변화는 달랐다는 기술적 관측이다. C의 후기→냉각후기 평균W도0.989955→1.130933으로 증가해 부하 없는 시간 변화가 단조롭지 않다.

조건당1독립 세션·고정 C→L 순서이며 L의 사전 W가 이미 C보다0.223911W 높았다. 배터리·초기 AP·준비와 이전 부하 이력·주변/네트워크 조건이 같다는 증거가 없다. 따라서 −0.202361W를 부하의 인과효과나 보편 보정계수로 사용하지 않는다. 반복 안정성·숨은 열 상태·주변 온도·유휴 평형/시정수는 식별하지 않았다.

## 공통120초 에너지와 동결식 진단

| arm | 관측J | 동결식J | 예측−관측J |
|---|---:|---:|---:|
| C 무부하 | 124.545817 | 147.052011 | +22.506194 |
| L 등록 부하 | 137.005431 | 155.685079 | +18.679647 |

L−C 관측 총량 차이는12.459615J이나 서로 다른 초기조건을 가진 한 쌍이므로 순수 작업 추가 에너지로 해석하지 않는다. 이 J는 고정 공통120초의 기기 전체 전류·전압 적분이며 준비·baseline·전체 기기 실행의 총에너지가 아니다. raw=mA 해석은 조건부이고 절대 에너지 정확도 미인증이다.

동결식은 실제 상태·전환시각을 입력으로 사용한 **외삽 진단**이다. 이후 관측 전력·AP를 예측 입력으로 넣지 않았다. 시작 AP 지원과 짧은 전환 지원을 분리하며 strict_supported=false/accuracy_pass=null을 유지한다. AP 그림은 관측 경로이고 이번에 AP 후보를 적합하거나 예측 오차를 독립 검증하지 않았다. 기존 모형/후보/default/strict/experiment_ready=false 불변이다.

## 종료·회수 및 PC 검증

두 앱 `cleanup.json` completed, 세션 summary/validated 정상 완료를 먼저 확보했다. 이후 원 실행 소유자의 host cleanup completed와 대상 패키지 force-stop을 각각 수행했다. 기존 preflight 정리1＋세션 종료2로 force-stop 총3명령이며 중복 재시도가 아니다. 뒤따른 기존 `ps -A`0022/0781/1541 stdout에서 대상 프로세스 부재를 확인했다. 마지막 기록 시점 L thermal status0, 현재 HAL AP28.3°C/BAT28.2°C다. cached 과거 온도를 현재값으로 대신하지 않았다. host Run exit0이며 이 사실을 지금도 계속 유지되는 기기 상태 보장으로 확대하지 않는다.

판독기의 기존 C만 누적 에너지를 출력하던 그림을 C/L 모두로 보완했다. 0/120초 행은 적분 경계이며 센서 표본을 만든 것이 아니다. 지원 없는 상태/공백/부분 경로는 null로 유지한다. generic mapper가 붙이던 queue 메타데이터는 실제 manifest의 burst/seed201로 바로잡았고 상태·시각·고정창 수치는 변경하지 않았다. 최초 판독 폴더를 보존하고 새 출력에 재현했다. 실행 코드/계약은 바꾸지 않았다.

관련4테스트(전체 기기 전력 중복 합산 방지·정확한 경계·미지원 상태·공백/겹침/부분 경로) 통과, 실패/skip0. 종료 plan_v1의 원문을 새 PC 분석 폴더에 재생해 C의 원래 고정창 불변·L전체창/쌍 비교null 보존을 확인했다(기기0). 원문 재현으로 두 arm 고정창/동결식 수치 불변, CSV120초 끝값과 summary 일치, 원본7,923해시와 실행 소스95·APK·두freeze 불변을 확인했다. 그림은 실제 회수 자료이며 mock 장시간 검증을 뜻하지 않는다.

## 재현과 다음 PC 작업

외부 원본 의존 파일은 `FINAL_RECEIPT.json`, 각 세션 `validated.json`/`input_manifest.json`/`thermal.jsonl`/`start_ap_gate/host_approval.json`/`host_cleanup.json` 및 artifacts의 `progress.jsonl`/`requests.json`/`cleanup.json`/`common_boundary.json`/`manifest.json`, host_commands 결과다. 완전 inventory는 외부 `energy_ap_resident_control_report_v3_inventory_before.json`; 원본 receipt는 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_run_v3/FINAL_RECEIPT.json`.

```powershell
python -B -m unittest tools.test_d1_resident_control_report -v
python -B -m tools.d1_resident_control_report --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_control_plan_v3/collection_plan.json' --output '<새 분석 출력 폴더>'
```

공유 CSV/summary/그림은 개인 PC 원자료 없이 열 수 있다. full 재분석은 원본과 동결 계획의 의존 파일이 필요하다. 기존 외부 판독 폴더 `energy_ap_resident_control_report_v3` 및 보완 `energy_ap_resident_control_report_v3_shared`를 보존한다.

**다음 PC 작업 하나:** 이 완전 C/L 쌍과 기존4세션을 이용해 유휴 전력의 시간·이력 의존성을 식별 가능한 범위에서 분석하고, 기존 일정 상수 보정 후보를 다시 채택할 근거가 있는지 판정한다. 이번 결과만으로 새 계수를 맞추거나 기본 시뮬레이터를 바꾸지 않았고 추가 실측은 자동 시작하지 않는다.
