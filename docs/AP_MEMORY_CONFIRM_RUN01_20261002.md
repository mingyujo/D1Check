# 준비 이력 AP 후보: 두 새 확인 세션 완료

2026-10-02 · 실행 기준 HEAD `4c8be6678cceb684c76ce4de14852f0e806719ee`

**두 세션 모두 completed_descriptive_only.** 사용자 ‘잘못입력한거야 실측 진행하자’ 승인으로 준비된 plan_v1만 한 번 실행했다. 기존 τ30초/γ0 후보의 AP MAE는 0.179/0.190°C이며 이전 preload 후보의 0.545/0.370°C보다 작았다. 새 자료에서 확인한 평균·최고오차 개선이지만, 후기 재상승의 크기·일반 동적 정책 비용·정확도 PASS까지 입증한 것은 아니다. 추가 적합·추가 실측은 없다.

[화면·그림](results/ap_memory_confirmation_01/run01/index.html) · [오차 CSV](results/ap_memory_confirmation_01/run01/metrics.csv) · [작은 결과](results/ap_memory_confirmation_01/run01/summary.json) · [보존·검증](results/ap_memory_confirmation_01/run01/verification.json) · [사전 설계](results/ap_memory_confirmation_01/README.md)

## 실행과 실제 소비

계획 `ENERGY-AP-MEMORY-CONFIRM-01` SHA `7013bcfe99b922d44c6d78801935c182dc6e525e4df60b1577ecafbb9108cfbd`. Check 기기 명령0, 설치 없는 Run1회, 재시도0. 계획에 남은 `not_approved`는 준비 시점 동결 필드이며 이번 사용자 승인을 반영하려고 원본을 변경하지 않았다. 이제 registry의 claimed/completed와 최종 receipt가 존재하므로 **소비·완료, 재실행 금지**다.

| 항목 | 실제 | 승인 상한 |
|---|---:|---:|
| 개발 / 확인 | 0 / 2 | 0 / 2 |
| 본 요청 | 48 | 48 |
| warmup / 별도 적격성 추론 | 16 / 0 | 16 / 0 |
| 총 명시적 추론 / runtime | 64 / 8 | 64 / 8 |
| staging / 파일 전송 | 2 / 14 | 2 / 14 |
| 설치본 host pull | 1 | 1 |
| APK push / 설치 / 빌드 | 0 / 0 / 0 | 0 / 0 / 0 |
| ADB 명령 | 1,698 | 6,600 |
| 실행·회수·cleanup 전체 | 581.796944초 | 2,090초 |
| 등록 고정 관측 | 420초(각30+120+60) | 420초 |
| 재시도 / 대체 / 추가 | 0 / 0 / 0 | 0 / 0 / 0 |

전역 preflight22.072초, 첫 세션234.020초, 등록 자연 대기90초 이후 두 번째 세션을 진행했다. 고정 관측420초를 전체 소요시간으로 표현하지 않는다. 공통창 앱 종료 시각은120.083493/120.075497초지만 **J 적분은 계획된 정확한120초**다. 본 요청48개 모두 시작·반환(`host_inference_return`)·output_ready·저장·worker_release·lane_available가 기록됐고 미완료0이다. 구형 이벤트 이름 `request_return`이0인 것을 반환0으로 해석하지 않는다.

현재 단일 transport와 동일 A24, 설치본 패키지/버전/프로젝트 서명/해시를 실행기 내부에서 확인했다. 설치본 SHA `74e8065d10bdfac01c4fbda77afeac196986501b9534bf02d1dd5b0ad541ee6e` 일치. 두 세션 시작 배터리67%, BAT27.2/27.7°C, 비충전 및 기존 화면·메모리·warmup 품질 gate 통과. 관측 thermal0. 개발 AP 하한을 실행 gate로 추가하지 않았고 설정 변경·재연결·추가 가열은 없었다.

## 고정 모형과 판독 경계

- 후보 SHA `d885b87c32d7df5b812b4cd85dcdae5230f47c9bd16d7ae2807df427b26c1466`, 원래 freeze `35ed6987…c54`, 이전 preload freeze `8507adc1…ec5`. 원본 네 계약/모형 및 실행 소스103파일의 해시를 대조했다. 계수·구조·판정 변경0.
- 부하 허용 +35/+65초, 동일 burst201 CG_DC 요청24개씩. 실제 PC 미래 일정 재생이며 온라인 B2나 예정 도착부터의 종단간 예측 검증이 아니다.
- 새 후보의 E/H는 **각 세션 부하 전 AP만**으로 초기화했다. 입력 길이63.935/92.965초, 표본26/37개, 마지막 입력의 조회 끝33.201/62.666초는 실제 첫 dispatch35.008/65.007초보다 앞이다. E27.831/28.093°C는 유효 기준이며 주변 온도 실측이 아니다. 부하 후 AP를 계수·초기화에 사용하지 않았다.
- 분석은 회수 후 실제 lane 일정에 조건부로 계산했다. AP 평가는 아래 실제 유효 표본 창이며 공통120초 전체 오차로 바꿔 부르지 않는다. 조건당 독립 세션1개다. 이미 본 개발/사후 평가 세션을 새 독립 확인 분모에 합치지 않는다.
- 공통 시작 AP27.4/27.9°C, 부하 직전 anchor27.4/28.0°C를 구분한다. 원래 개발 범위32.5–34.0°C 밖이므로 원래 동결식은 외삽 진단이다. 이번 후보의 독립 오차 관측도 strict 지원 확대나 보편 오차 한도는 아니다.

| 부하 허용 | AP 비교창(공통 시작 기준) / 표본 | 기존 preload MAE | 새 후보 MAE | 새 최대 절대오차 | 새 최고온도 부호오차 |
|---|---|---:|---:|---:|---:|
| +35초 | 35.630767–179.800767초 / 56 | 0.544909 | 0.178596 | 0.737337 | −0.121397 |
| +65초 | 67.615707–177.655707초 / 43 | 0.370485 | 0.189876 | 0.700567 | −0.303239 |

단위 °C, 부호는 예측−관측. 기존 preload 최대오차0.757744/0.922040°C, 최고오차−0.556174/−0.507743°C도 같이 보존했다. 새 후보 부하 구간 MAE0.353525/0.202935°C(5/4표본), 부하 후 유휴0.161446/0.188536°C(51/39표본). 길이·초기조건이 다른 두 세션의 MAE 차이를 대기시간의 인과 효과로 해석하지 않는다.

고정150–175초 방향창에서 첫 조건은 관측+0.100°C / 후보+0.001121°C / 기존−0.006934°C다. 두 번째는 관측−0.039493°C / 후보−0.023056°C다. 표본 양자화·endpoint 보간을 포함한 기술값이며 후보가 후기 미세 상승의 크기까지 재현했다고 말할 수 없다. 두 번째 절대 최고온도도 과소 예측했다. 새 데이터로 재보정하거나 다른 후보를 선택하지 않았다. `accuracy_pass=null`, strict/default/experiment_ready=false 유지.

## 실제 점유·센서와 별도 에너지 진단

실제 lane CG_DC 겹침1.334590/1.391242초, 추론 호출 경계 겹침0.899889/0.933597초를 구분했다. 첫 dispatch→최종 lane 해제는35.008448–46.884999초 /65.007372–76.904128초다. 짧은 병행만으로 별도 병행 전력 계수를 정밀 식별하지 않는다.

세션 전체 전력 snapshot222개씩, 중앙 간격1.000492/1.000269초, 최대1.013963/1.017294초. host AP 기록87개씩, 중앙 간격2.5825/2.600초다. 준비를 포함한 전체 host AP 최대 공백10.410/9.975초와 실제 초기화/평가창의 적격성 검사를 구분한다. 등록된 초기화·부하 후 창은 공백≤10초와 coverage/rank 조건을 통과했다. 조회 간격이 센서 내부 갱신 주기임을 보장하지 않는다.

| 정확한120초 | +35초 | +65초 |
|---|---:|---:|
| 관측 J | 144.098982 | 140.797012 |
| 원래 동결 전력식 J | 155.634915 | 155.676591 |
| 예측−관측 J / 상대오차 | +11.535933 / +8.006% | +14.879580 / +10.568% |
| 부하 전 / 부하 / 부하 후 유휴 오차 J | +0.385351 / +3.078369 / +8.072213 | +8.713314 / +1.737843 / +4.428423 |

세 부분의 합은120초 전체와 일치한다. 이번 에너지 차이는 세 부분이 모두 양수다. 서로 다른 대기·초기조건의 총 J 차이로 정책 우열을 판정하지 않는다. AP 후보 개선은 이 전력식 오차를 수정하지 않는다. 전류 raw=mA 해석의 조건부 성격·절대 에너지 정확도 미인증을 유지한다.

## 종료·원본·PC 검증

앱 정상 cleanup2, 각58파일 회수(총116), host 소유자 force-stop각1회(총2) 후 ps에서 대상 부재 확인. 최종 host PowerShell/Python도 exit0 이후 부재를 PC에서 확인했다. 추가 기기 확인·외부 복구0. timeout0, 관측된 연결 소실0, lifecycle_cancelled0. 명령 exit1 여섯 건은 staging 전 새 경로 `test -e` 부재 검사이며 재시도나 transport 실패가 아니다.

checkpoint에 실행ID·부모/자식PID·계획hash가 있으나 `host_identity` 필드는 null이다. 로컬 프로세스 생성시각과 실행 도구의 exit0/부재 관측을 함께 보존했다. 완전한 외부 orphan 식별 기록이 있다고 과장하지 않으며 이번 외부 복구는 수행하지 않았다.

원본 루트: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_memory_confirm_run_v1`. `FINAL_RECEIPT.json` SHA `56423ed6499d36226533e4a7bf5b556c1cd040ce446cf0552f6357b0078d8195`. 원본8,778파일 inventory는 별도 `ap_memory_confirm_run01_verification/raw_inventory.json`에 보존했다. 실행 계획·registry·원본을 분석 과정에서 수정하지 않았다.

PC 결과: `ap_memory_confirm_run01_pc`, 검증: `ap_memory_confirm_run01_verification`(같은 외부 루트). 실행 전에 이미 완료한14테스트를 반복하지 않았다. 이번에는 실제 PS Check/Run, 실제 고정 판독 CLI, 원문 요청/소비/명령 검증, CSV·그림 MAE/적분/부분합/상태시간 일치와 이미지 확인을 수행했다. 분석 기기명령0. 이전 PC 테스트는 이전 기준 결과로만 링크한다.

공유 출력에서 legacy `actual_states.csv`의 기본 `scenario=queue` 문구를 전용하지 않고 실제 manifest의 burst201을 보고했다. 시간·상태 수치는 그대로 내보내고 불필요한 기본 메타데이터 열만 제외했다. 에너지 경로의 원본 CSV는 센서 시각까지만 있으므로 공유 그림에는 이미 계산된 정확한0/120초 경계값을 추가했다. 새 센서값을 외삽하거나 기존 결과를 수정한 것이 아니다. 최초 그림의 endpoint assertion 실패는 외부 `ap_memory_confirm_run01_render_partial`에 남겼고, 출력 수정 뒤 검증을 통과했다.

재현(모두 PC, 출력은 없는 별도 폴더):

```powershell
python -X utf8 -B -m tools.d1_ap_memory_confirmation_readout --plan 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_memory_confirm_plan_v1/collection_plan.json' --output output/ap_memory_confirm_reproduce
python -X utf8 -B docs/results/ap_memory_confirmation_01/render_run.py --source output/ap_memory_confirm_reproduce --output output/ap_memory_confirm_share
```

원자료가 없는 팀원은 공유 CSV/summary/그림으로 판독을 확인할 수 있다. 전체 재계산은 계획의103개 소스·동결4파일·각 세션 manifest/requests/progress/start_ap/common_boundary/thermal/validated와 receipt가 필요하다. 원본 저장 위치만 바꾸면 hash 계약이 달라질 수 있으므로 원본을 임의 편집하지 않는다.

**다음 PC 행동 하나:** 이 두 독립 AP 확인 결과와 후기/전력 오차 한계를 제한 시뮬레이터 결과 본문에 통합한다. 이번에 후보 기본 채택·정책 순위·추가 실측으로 자동 진행하지 않는다.
