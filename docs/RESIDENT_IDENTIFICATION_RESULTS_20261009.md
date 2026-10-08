# Resident 에너지·AP 식별 실행 결과 — 2026-10-09

**개발 4세션은 정상 완료·회수됐다. AP 식별 gate가 실패해 모형 동결과 확인 4세션은 미진행이며, 계획은 `stopped_no_resume`이다.** 연결 소실·lifecycle_cancelled·추론 실패가 원인이 아니다. 새 모형의 독립 확인이나 시뮬레이터 오차 감소 완료를 주장하지 않는다.

## 실행·보존

- 사용자 `실측가보자` 승인으로 최종 plan_v3만 Check 후 Run 1회. Check는 기기0/미소비/동일성 PASS였다. 현재 온라인 A24 transport 1개를 선택해 고정했고 모델/하드웨어/fingerprint·환경·설치본 gate는 실행기 안에서 확인했다. 이전 transport 값을 재사용하지 않았다.
- 실행 대상 plan SHA `2cb32c36c45345273a033f4c28f5f39c8daec540209e62e804349c07be17ac1f`, 설치 후보 SHA `57d2320c35c3cfaf52a2a127460007809bed21e23b2c2b05a8efb30bd699cb20`/기존 프로젝트 서명. APK 전송1·데이터 보존 업데이트1·설치본 pull1. 재빌드0.
- KST 10/9 01:31:48경→02:48:51, 원 host receipt 경과 **4,622.687초(77분2.687초)**. UTC·host monotonic·Android monotonic을 원본에 보존했다. AP는 Android uptime bracket으로 정렬하고, host/app 절대시각을 같은 clock처럼 비교하지 않는다.
- 실행 코드 기준 HEAD `4d87c1be1c27aac614ea5c305aa57f5769c990df`+사용자 STATUS 변경. 실행 중 완료된 별도 정책 commit `00cde90`은 보존한다. 이번 측정이 그 정책의 효과 확인을 뜻하지 않는다.
- plan_v1/v2·과거 종료 계획·원자료·FAIL은 보존. 이번 plan_v3는 소비·종료됐으며 재실행 불가. 기존 기본 모형/RL/strict/`experiment_ready=false` 유지.

## 승인 대비 실제 소비

| 항목 | 승인 최대 | 실제 |
|---|---:|---:|
| 세션 | 개발4+확인4 | 개발4 정상, 확인4 미시도 |
| 본 작업 | 6,288 | 3,418 |
| 적격성 | 24 | 16 |
| warmup | 64 | 32 |
| 총 명시적 추론 | 6,376 | 3,466 |
| runtime | 32 | 16 |
| staging / 파일 | 8 / 56 | 4 / 28 |
| 설치본 host pull / APK push / 설치 | 각1 | 각1 |
| ADB | 34,728 | 실행기7,349+외부 transport 선택1=7,350 |
| 실행·회수·cleanup | 19,070초 | 4,622.687초 |
| 고정 관측 | 5,580초 | 개발4×900=3,600초 |
| 별도 준비 유휴 / 세션간 대기 | 720 / 630초 | 480 / 270초 |
| 재시도·대체·추가 | 0 | 0 |

[소비·실행/수정 코드 해시](results/resident_identification_run_01/consumption.json). 성공 검증된 전체 journal의 시작/반환/lane_available로 호출 수를 확정했다. 미시도 세션의 관측값은 null이며, 결측을 0으로 채우지 않았다. 시간 상한과 고정 관측을 정상 예상시간으로 혼동하지 않는다.

내부 ADB client 7,349개 모두 종료: 정상 return7,336, 예상된 `test -e` 경로부재(exit1)13, timeout0. listing1,587/중앙0.094초·최대0.672초. AP 조회1,601·clock anchor3,192. 누적 client 대기913.599초는 기기 CPU 비용이 아니다. 연결 소실 증거는 없으며 무선 디버깅 스위치가 계속 켜져 있었다는 별도 증명은 아니다.

## 자료 적격성·예측 경계

DEV_A/B/B/A에서 본 작업854/854/857/853을 회수했다. 각4 runtime·8 warmup·4 probe, 정상 app cleanup·host force-stop·대상 프로세스 부재 확인. host force-stop은 설치 정리1+세션별1=5회이고, 동결 실패 뒤 중복 정리0이다. 실제 host parent20012/child22176은 종료 기록과 PC 프로세스 부재로 확인했다.

시작 AP **26.5/28.0/28.6/28.8°C**. 기존32.5–34.0°C 시작 범위 밖 판정을 보존했으며 numeric-ap-observe-v2의 유효성/신선도와 실행 환경 gate를 통과했다. 낮은 온도라는 이유로 임의 가열·추가 warmup·설정 변경은 없었다.

GPU 단독 실제 점유59.972/59.964/60.472/59.989초, CG_DC 병행60.007/60.161/59.924/59.969초. CPU 단독·탐지 CPU·유휴를 별도 분류하며 detection_GPU는 resident/warmup만이다. 센서900ms, 실제 power 최대 공백0.922–0.951초. AP 최대 공백3.545–3.665초, AP 표본297/297/296/296. 조회 시각의 신선도와 센서 내부 갱신 시각 보장은 다르다.

**A: 실제 일정 조건부 비용 예측만 수행했다.** 실제 lane dispatch~release가 입력이고 부하 전 AP/preload power만 초기 입력이다. 이후 관측 AP·전력은 비교 대상이다. 예정 도착부터 일정·응답을 생성하는 B는 이번에 검증하지 않았다.

기준시각0은 공식 부하 시작35초 전이다. 에너지0–120초와 긴 기준창0–635초를 분리하며, 공식600초 부하 관측창은35–635초다. AP 오차는 실제 부하 이후부터 마지막 냉각 AP 표본까지(약35–815초)로, 120초 AP 오차라고 부르지 않는다. 전체 숫자/구간/상쇄는 [metrics.csv](results/resident_identification_run_01/recorded_v3/metrics.csv), 실제 상태는 [states.csv](results/resident_identification_run_01/recorded_v3/states.csv).

## 기존 동결 모형 진단 오차

| 개발 세션 | 120초 관측J | 예측J | 예측−관측J | 긴0–635초 차이J | AP MAE°C | AP 최대°C | 최고AP 차이°C |
|---|---:|---:|---:|---:|---:|---:|---:|
| session_00 DEV_A | 146.924 | 134.327 | -12.597 | -24.551 | 0.944 | 2.137 | -0.251 |
| session_01 DEV_B | 180.577 | 160.173 | -20.404 | -46.657 | 0.770 | 2.328 | +0.670 |
| session_02 DEV_B | 170.809 | 155.581 | -15.228 | -66.323 | 0.755 | 2.394 | +0.708 |
| session_03 DEV_A | 141.152 | 143.712 | +2.560 | +32.721 | 0.554 | 1.885 | +0.390 |

네 **개발** 세션 평균 절대 J 오차12.697J/120초(평균 절대 상대7.650%), 긴635초42.563J; AP 평균 MAE0.756°C. 이 숫자를 기존 확인14의 보편 오차한도나 새 정확도 PASS로 사용하지 않는다. 전체 에너지·유휴 비중·부하/부하후 상쇄를 분리했으며 조건별 부호가 바뀐다. A24 current raw=mA 조건부 해석/절대 에너지 정확도 미인증을 유지한다.

## AP 동결 차단과 PC 수정

첫 개발 제외예측(개발1/2/3으로 fit, 개발0 heldout)에서:

- power design rank5와 AP load rank2/numerical rank3은 충족했다. 단, AP beta **0.22966260154/s**가 사전61grid의 상한(기존beta0.04593252031×5)에 붙어 `beta_boundary=true`였다. rank가 있다는 사실은 안정적인 물리 계수 식별을 보장하지 않는다.
- beta 상한 부근 training MSE0.593501→0.593203→0.592929, 동시에 g3.962→4.232→4.517. 상한 안의 안정적인 최적값을 확인하지 못했다. 참 냉각률이 상한보다 반드시 크다거나 센서 결함이라고 단정하지 않는다.
- 해당 차단 후보의 첫 heldout AP MAE0.944→1.018°C/최대2.137→2.258°C로 악화했다. J 절대오차는12.597→4.119J/120초와24.551→2.407J/635초로 감소했지만, 단 한 개발 제외예측이고 AP gate 실패 후보다. 정식 동결/독립 확인/기본 채택 없음.
- 기존 수식의 상태 가열 입력은 `u=slope(state)-slope(resident_idle)`이고, 고정 상태 비율에 공통k/g·고정30초 잔열항을 적용한다. 새 상태별 반응과 이 고정 비율의 적합성은 다음 PC 분석 대상이다. 검색 상한 확대만으로 해결됐다고 처리하지 않는다.

원 오류는 `AP model unidentified; no confirmation`. 후속 optional sampler_failure/session_failure 파일은 정상 종료로 존재하지 않아 회수 parser 오류2개가 별도로 남았다. app cleanup의 sampler_failure/error는 null이다. 이 회수 오류를 원래 앱 오류로 바꾸지 않았다.

추가 `progress_summary_error`는 loop가 확인 index4로 넘어간 뒤 이전 개발 세션에 다음 세션의600회 상한을 적용한 host 결함이었다. 원본 last work853은 개발 상한1200 이내다. 종료 후 **current_entry를 현재 폴더에 결합**하는3행 최소 수정과 실제 host 진입 회귀를 수행했다. APK·앱 동작·모형·gate·timeout 변경0. 원본 receipt는 고치지 않고 별도 corrected prefix 요약을 남겼다.

검증: 관련 host8 PASS+신규 host 진입1 PASS. 신규 fixture 최초 실행은 manifest의 protocol 누락으로 본문 경계에 못 갔고, 실제 manifest 필드만 보완한 뒤 통과했다. 원오류 보존/확인 미시도/cleanup4번 유지/다음 상한 미사용을 검사한다. 출력 원자료 fixture·적분 분할·활성 실행 최종게시 차단·공유 clock 그림 수치 불변·portable 첫fold 계수/점수 정확 재현 PASS. 모형/plan/APK 해시 불변, 실행 종료 뒤 host 파일 하나만 변경됐다. 실기기 실행 소스와 수정 소스를 [소비 기록](results/resident_identification_run_01/consumption.json)에 분리했다.

## 산출물·종료

- [결과 화면](results/resident_identification_run_01/recorded_v3/index.html) · [전체8세션 분모](results/resident_identification_run_01/recorded_v3/sessions.csv) · [실측–기존 모형/구간 오차](results/resident_identification_run_01/recorded_v3/metrics.csv) · [곡선CSV](results/resident_identification_run_01/recorded_v3/curves.csv).
- [상한 profile와 첫 제외예측 진단](results/resident_identification_run_01/diagnostic/first_fold.png) · [계수/점수](results/resident_identification_run_01/diagnostic/first_fold.json) · [61grid CSV](results/resident_identification_run_01/diagnostic/beta_profile.csv). 차단 후보이며 동결 모형이 아니다.
- 원본 receipt: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_resident_identification_run_v3/FINAL_RECEIPT.json`; 같은 root에 artifacts·journal·thermal·host_commands·checkpoint 보존. host_entry는 plan_v3 폴더, registry는 외부 resident_identification_registry/ENERGY-AP-RESIDENT-IDENTIFICATION-02에 각각 종료 증거를 보존. 작은 공유 입력/원본 파일 SHA와 [재현 명령](results/resident_identification_run_01/README.md)을 제공한다. 키·APK·모델 바이너리·대용량 원본·기기 식별정보는Git제외.

**다음 PC 작업 하나:** 확보한 개발4자료로 AP 상태별 가열입력 비율과 고정30초 잔열항의 잔차를 분리해, 기존 공동 k/g 구조를 유지할 수 있는지 판정한다. 같은 실측 반복·확인 gate 완화·추가 기기 계획 자동 생성은 하지 않는다. 이번 계획의 확인4는 미완료이며 새 모형/정책 우열도 미확정이다.
