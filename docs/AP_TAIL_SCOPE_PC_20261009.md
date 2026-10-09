# LOAD_SLOW 별도 AP 평가 범위 — 2026-10-09

**별도 opt-in AP 진단 경로를 구현했다. 기본 모형·strict·RL 환경은 교체하지 않는다.** 등록 부하와 같은 실행 구성을 가진 개발4＋장시간 확인2는 계산을 허용하고, 기존29의 도착·이력 대조 일정은 이 후보 경로에서 차단한다. 좋아진 사례만 골라 범위를 만든 것이 아니다.

## 네 층위의 판정

| 층위 | 현재 근거 |
|---|---|
| 수식이 숫자를 반환 | 이전33＋새2의 저장된 진단 결과가 존재 |
| 이번 진단 입력 계약과 일치 | 등록 macro 개발4＋장시간 C0/LOAD_A2; 총6 |
| 독립 실행에서 예측 확인 | 실행 전 고정 후보의 C0 1＋LOAD_A 1 block; 장시간 프로토콜 전이 진단 |
| 오차·변동성 대비 정책 차이 판별 | 미완료; 이번 범위 통과를 정책 우월성으로 사용하지 않음 |

`diagnostic_AP_only`는 계측 지원·정확도 인증이 아니다. 기존 후보의 `application_allowed=false`, `strict_support=false`, `accuracy_pass=null`, `experiment_ready=false`를 그대로 보존한다. 원식5682082a…/후보파일aa28410d…은 byte 단위로 불변이다. τ1920은 아직 식별되지 않았고 주변 온도·내부 열 상태·열→처리시간 계수를 만들지 않았다.

## 허용 계약과 차단

새 API: [d1_ap_tail_scope.py](../tools/d1_ap_tail_scope.py), 고정 계약: [scope.json](results/ap_tail_scope_01/scope.json).

| 항목 | 별도 진단 계산 조건 |
|---|---|
| 기기·엔진·모델·입력 | 동일 A24, Interpreter/LiteRT1.4.2 및 기존 FLOAT32/GPU strict 계약; 모델·입력·tensor·runtime 계약 hash 일치 |
| CPU·resident | 실제6 manifest의 CPU1스레드, 분류CPU/GPU＋탐지CPU/GPU4resident; 다른 구성 차단 |
| 준비 이력 | warmup8·적격성4, 고정 준비120초·baseline120초·cadence250ms·sampler900ms·정상 수집 검증/cleanup 근거 |
| 초기 입력 | 기존 pre-only R/H, 고정β·준비τ30·추가 느린 변화 S(35)=0; 부하 전 마지막 AP26.5–28.8°C |
| 상태 | 유휴·분류CPU·탐지CPU·분류GPU·분류GPU＋탐지CPU만 허용; task/backend 조합을 합치지 않음 |
| 짧은 등록 macro | DEV_A/DEV_B, 원60초 부하＋90초 유휴 순서·공통 종료635·후반180초 |
| 긴 확인 | C0_LONG 전 구간 무부하, LOAD_A_LONG은 DEV_A 순서·공통 종료635·후반1920초 |
| 시간·전환 | 원시계0부터 빈틈 없는 실제 lane 일정·35 이전 부하 금지·등록 진입/이탈 순서·실제 끝을 넘는 query 금지 |
| 사용 목적 | 명시적 opt-in의 실제 일정 조건부 AP만; 예정 도착부터의 B/strict/RL/정책 순위 사용은 차단 |

26.5–28.8°C는 **이 후보 개발 관측 맥락에 대한 PC 검사**다. 기기 실행 안전 기준이나 새 실측 gate가 아니다. 개발 시작 범위를 넓히거나 모델 계수를 바꾸지 않았다. 전환 후 native drain의30초 여유는 기존 경계 검사에서 상속한 제한이지30초 전환 일반화의 정확도 보장이 아니다. APK57d2320c…의 원 개발 프로토콜과 APK703d09d5…/완료 화면proto의 새 긴 프로토콜을 별도 variant로 검사한다.

부하 전 AP 수준·추세로 R/H를 초기화하지만 그 값은 주변 온도나 측정된 내부 온도가 아니다. 같은 프로토콜·초기 AP라도 외부 이전 부하·숨은 열 상태·날짜 차이는 남는다. 데이터 계약 일치와 모든 초기 이력에 대한 검증을 혼동하지 않는다.

범위 밖은 `prediction_ap_c=null`이며0으로 채우지 않는다. 에너지·응답 예측도 이 API에서는null이다. 기존 에너지 회계/서비스 엔진은 그대로 사용할 수 있으나 AP 후보 확인을 J 개선 또는 열 피드백 검증으로 확대하지 않는다. 원 계수2파일과 계산 구현9파일을 확인하며 코드 해시는 CRLF/LF만 정규화한다. 실제 대상 기기·설치본·환경 확인은 호출자가 원 수집 근거로 증명해야 한다. 공유 context 예제는 과거 기록용으로서 현재 기기의 gate가 아니다.

## 기존 개선과 악화 모두 보존

- 개발4의 기존 사후 LOSO MAE: 원식0.7558→LOAD_SLOW0.2792°C. fold별 후보이므로 최종 고정본의 독립 확인으로 쓰지 않는다.
- 과거29의 사후 평균 MAE: 원식0.3217→LOAD_SLOW0.3228°C. 13/29 악화: 원개발3·확인4·sustained5·history1. [전체 비교](results/ap_tail_scope_01/run_v4/retained_errors.csv)·[악화13](results/ap_tail_scope_01/run_v4/retained_worsening.csv).
- 새 LOAD_A: 원식0.4371→고정 LOAD_SLOW0.1728°C. C0는원식과동일0.0908°C. 새 경로의 두 전체 예측 곡선은 기존 확인 CSV와1e−12 이내 일치했다. 추가 fit은0이다.
- 기존29는 개선16과 악화13 모두 같은 등록 profile/시간 계약 검사에서 차단한다. 표준화 cache의 `common_end_s`가 없는 경우에는 **시계 필드 미기록**이라고 표시하며 실제 불일치로 단정하지 않는다. 이 필드를 복원해도 도착·이력 대조 profile은 이번 macro 계약과 다르므로 자동 허용되지 않는다.

평가 세션·block 단위로 비교했고 센서 표본을 독립 반복으로 합치지 않았다. 서로 다른 평가 층위의35개를 한 평균으로 섞지 않는다. [세션별 검사](results/ap_tail_scope_01/run_v4/scope_audit.csv)·[그림](results/ap_tail_scope_01/run_v4/retained_session_errors.png).

## 실제 사용·재현

저장된 LOAD_A의 AP 재생 예제(새 출력 파일을 사용):

```powershell
python -B docs/results/ap_tail_scope_01/run_example.py --opt-in --output output/ap_tail_scope_LOAD.json
```

확인된 출력: `diagnostic_AP_only`, `AP_MAE_c=0.17283198541445108`, `device_commands=0`, `fit_calls=0`, `strict_support=false`, `accuracy_pass=null`.

임의 JSON API 진입은 `python -B -m tools.d1_ap_tail_scope --case <실제일정.json> --context <검증근거.json> --opt-in --output <새파일.json>`이다. 후보가 아닌 원 모형의 기본 예측과 구분한다. opt-in 없이 계산을 반환하지 않는다. 부하 후 AP/전류·전력·segment의 부가 센서 필드를 제거하고 pre(t/AP/시각 bracket), 실제 상태/시간, query만 숫자 함수로 넘긴다. 원 계산 오류·stack을 보존하며 예상 밖 예외를 성공으로 바꾸지 않는다.

전체 범위 표 재현(원6 manifest/검증 근거가 필요, PC0기기):

```powershell
python -B -m tools.d1_ap_tail_scope_report --external-root C:/Users/LG/Documents/D1Check_Arrival_Extension --output output/ap_tail_scope_reproduced
python -B docs/results/ap_tail_scope_01/plot_errors.py --results output/ap_tail_scope_reproduced
```

이 명령은 원35개 오차를 재사용하고6개 AP 계산 진입만 확인한다. 정책 시뮬레이터 전체 배치·RL 학습·새계수 fit은 실행하지 않는다.

## 검증과 완료 범위

- `python -B -m unittest tools.test_d1_ap_tail_scope -v`: 13건 통과. 초기 AP경계/결측·비정상값·prep 이력·CPU1/4와bool 오인·S26/다른resident·미지원 task쌍·잘못된 순서/시간·미기록 시계·C0 부하·명시적 opt-in·원 stack·모형/구현 변경·사후 관측 입력 차단을 포함한다.
- 35행/분모·악화13 보존, 원 확인1804 AP표본과 새 API 값 일치, 실제 예제 진입 성공. 기기/ADB/설치/추론/실측/새 계획/소비claim/환경 시뮬/학습/물리계수 fit은 모두0이다.
- PC 초안 생성 실패2건은 별도 FAIL로 보존했다: inventory의 `raw_files` 중첩 처리, CPU4라는 초안 가정을 실제6 manifest의 CPU1로 정정. 원자료·모형·결과를 손대거나 오류가 작아지도록 허용조건을 고치지 않았다. run_v3은 준비 이력 필드 보완 전의 PC 중간 산출물이고 최종은run_v4다.
- 검증 대상: HEAD90782a2＋이번 새 scope/API/report/test의 미커밋 변경. 정확한 SHA·시점·검증 결과는 [verification.json](results/ap_tail_scope_01/verification.json)에 남긴다. 사용자 STATUS14행과 다른 정책/RL 작업·worktree를 보존한다.

**이번 작업은 완료했다.** 등록된 부하 일정의 보조 AP 재생에는 새 API를 사용할 수 있다. 일반 도착 정책·RL 비용 모형으로의 채택, 작은 정책 차이 판별, τ/물리 원인 확인은 이번 완료 범위에 포함되지 않는다. 같은 실측을 자동 반복하거나 새 실행 계획을 만들지 않는다.
