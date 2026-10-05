# 분리 부하 개발·동결·독립 확인 결과 — 2026-10-03

개발 3세션과 독립 확인 6세션을 확보했다. 앞선 두 중단을 지우지 않고 적격 개발 CPU/PAR를 재사용한 뒤 새 계획에서 SER 개발→동결→확인 6을 완료했다. **일정·응답 정책 비교는 실제 자료로 가능하지만 작은 에너지·열 차이의 정책 순위는 미확정**이다. 마지막 CPU 확인의 부하 종료 후 전력·AP 상승은 예측되지 않았다. 그 세션을 제외하거나 계수를 다시 맞추지 않았다. original goal의 에너지·열 정책 선택 정확도까지 완료한 것은 아니다.

## 실행과 오류 처리

Run01은 listing 3초, Run02는 thermalservice 2초의 silent client timeout으로 중단했다. 연결/OS/기기 내부 원인은 미확정이다. Run02의 실제 경계는 warmup 승인 후 resident baseline이었다. 첫 설명의 'warmup 승인 전'은 progress 원본으로 정정했다.

새 opt-in `precommon-observation-gap-v3`는 **공식창 승인 전** 읽기 전용 listing/thermal bracket의 출력 없는 timeout, client 종료 확인, 남은 시간 조건이 모두 맞을 때 세션당 총 1회만 관측누락으로 보존한다. 다음 정규 poll의 새 환경 관측이 성공하기 전에는 승인하지 않는다. 명시적 연결 실패·환경 부적격·두 번째 누락·공식창 승인 후 오류는 중단한다. 원래 stack/result를 먼저 보존한다. timeout/기본 주기·앱 gate·APK·부하·모형 수식은 유지했다. 이는 제한된 읽기 재확인 허용이며 세션 재시도 0과 구분한다. 실행 후 사후 완화가 아니다. 실제 성공 Run04에서 누락 허용 사용은 0회이므로, 새 복구 분기의 실기기 작동을 검증했다거나 timeout 원인을 해결했다고 하지 않는다.

plan_v1/v2는 stopped_no_resume. plan_v3는 미소비 초안으로 보존하며 실행하지 않았다. 새 plan_v4 SHA `a631fa2edab1f65f763fbb4d3115637116e7674130ca784ce49c3b5269105a95`는 1회 완료했다. 소스 출처는 외부 `separated_power_source_v2`와 `separated_power_source_v4`로 구분한다. 재사용 APK SHA `5c284190db34b4ea4392ef5125a8618cf2dc85274f9214d2579676ca48a3ba4c`; 이번 작업 Android 변경·빌드·APK 전송·설치 0회.

|Run04 항목|동결 상한|실제|
|---|---:|---:|
|새 개발/확인 세션|1 / 6|1 / 6 완료|
|본 요청 / warmup / 명시적 추론|672 / 56 / 728|672 / 56 / 728|
|runtime / staging 파일|28 / 49|28 / 49 (7회)|
|설치본 pull / APK push / 설치|2 / 0 / 0|2 / 0 / 0|
|ADB 명령|22,800|4,681|
|고정 관측|1,470초|7×210초 계획 경계 완료|
|전체 예약|6,730초|2,262.958초|

개발 275.214초/684명령, 확인 1,935.917초/3,997명령. root 시간에는 중간 동결·준비가 포함된다. 정상 소요시간을 상한과 혼동하지 않는다.
이번 턴 Run02+04 실제 합계는 시도 9/완료 8, 본 768+warmup72=840 확인된 추론, runtime36, staging9·63파일, pull3, APK0, ADB5,462, 작업시간2,671.763초다. Run01까지 누적은 시도11/완료9, 본864+warmup88=952, runtime44, staging11·77, pull4, push/설치 각1, ADB6,339/3,100.751초다. PC 수정·대기 공백은 별도다. 중단 2세션의 terminal 미회수 때문에 각각 본 0–96의 보수적 미확인 범위가 남으며, 기록된 본 시작 0을 실제 0 확정으로 바꾸지 않는다.

## 개발과 확인 분리

48분류/48탐지·96요청 프로토콜. 개발은 분류32→탐지32→혼합32 블록, 확인은 350ms 간격 혼합96이다. 처리시간/실제 lane을 인위적으로 맞추지 않았다. CPU→PAR→SER→SER→PAR→CPU 순서를 보존했다. 다른 시점·초기조건 및 준비 관측 프로토콜 차이를 기록한다.

개발 3의 5초 상태 점유 설계행렬 rank4, 조건수4.7418. 별도 동결 증가전력 W는 분류CPU0.584429, 분류GPU0.472884, 분류GPU+탐지CPU0.887812, 탐지CPU0.712926이다. 개발 5초창 적합 RMSE0.928991J는 독립 정확도 증거가 아니다. 유휴 배경은 부하 전[-20,30]초 관측 평균으로 초기화한다.

새 freeze SHA `19637bf11814e473922c482e752942fb486e4cc74fd74694e6ecf15ee322b825`, UTC `2026-10-02T19:23:36.095557+00:00`, 확인 preflight 이전. AP는 기존 `557fbe5be8a9c9ba5f5911d44d1c19611710cbe5b80e015d1b965b777357bcf2` 그대로다. 확인 자료로 재적합 0, 세션 제외 0. 관측 pre35 AP·부하 전 전력은 허용 초기 입력이고 이후 AP·전류·실현 처리시간은 예정 도착 예측에 넣지 않았다. 실제 일정 조건부 계산은 별도 출력이다.

## 독립 확인 오차

에너지는 공통 0–120초 전체, AP는 부하 시작 35초부터 냉각을 포함한 약180초까지 유효 관측 시각이다. AP 오차를 120초 전용 오차로 표현하지 않는다. 예정 도착 예측 결과:

|확인 순서|관측 120초 J|예정 도착 예측−관측 J (%)|AP MAE / 최대 °C|마감 충족|
|---|---:|---:|---:|---:|
|0_CPU_URGENT_ONLINE_V1|153.149|+4.354 (+2.843%)|0.271 / 0.752|96/96|
|1_B2_PARALLEL_ONLINE_V1|154.805|+3.758 (+2.428%)|0.436 / 1.172|96/96|
|2_B2_SERIAL_ONLINE_V1|153.015|+1.753 (+1.146%)|0.311 / 0.771|61/96|
|3_B2_SERIAL_ONLINE_V1|156.459|+6.004 (+3.838%)|0.151 / 0.643|61/96|
|4_B2_PARALLEL_ONLINE_V1|154.774|-4.737 (-3.060%)|0.227 / 1.315|96/96|
|5_CPU_URGENT_ONLINE_V1|197.713|-35.497 (-17.954%)|0.927 / 4.213|96/96|

실제 일정 조건부 에너지 오차는 같은 순서 +4.272, +3.479, +1.879, +6.064, −5.033, −35.819J다. 일정 예측 오차를 제거해도 마지막 실패가 유지된다. [전체 수치](summary.csv), [실제/예측 일정·J·AP](index.html), [5초 전력 잔차](residuals/five_second_power.svg), [상쇄](residuals/cancellation.csv).

확인 초기 AP는30.2/30.2/30.3/30.5/30.5/30.9°C. 실제 PAR 겹침은12.884/12.797초. CPU/PAR는 두 번 모두96/96 마감 충족, SER는61/96(예측62/96), 긴급48개는 모두 충족했다. PAR 긴급 P95는 CPU보다456–469ms 짧았다. 이는 등록 입력의 두 독립 실행 결과이며 임의 도착 전체/정책 우월성 일반화가 아니다.

## 남은 모델 실패 경계

마지막 CPU는 실제 마지막 lane 해제72.767초 뒤에도 전력이 높았다. 75–120초 관측 에너지는82.138J로 첫 CPU의46.551J와 달랐다. 마지막 lane 이후 평균1.797949W, 첫 CPU1.039177W. AP 최고36.0°C는 공통105.132초의 benchmark resident 유휴에서 관측됐다. benchmark lane 유휴는 전화기 전체 유휴를 의미하지 않는다. 해당 세션의 5초 잔차는 양+5.622/음−41.441/합−35.819J이며 절대합47.064J다. 사전 배경 평균을 유지하는 전력모형과 동결 AP 입력만으로 이 상승을 예측하지 못했다. 외부 앱·OS·사용자·잔열 중 하나를 원인으로 확정할 기록은 부족하다.

첫 다섯 세션도 임의 PASS로 분류하지 않는다. 순차 실행의 초기조건/배경 차이와 오차가 작은 정책 J 차이를 넘어설 수 있다. 현재 사용할 범위는 등록 A24 두 모델·resident·48:48 입력에서의 일정/응답 비교와 오차가 함께 표시된 제한적 J/AP 예측이다. 미검증 입력·throttling·S26·정밀 절감·작은 열 차이의 정책 순위로 확대하지 않는다. 기본/strict/experiment_ready=false 유지. 새 후보 탐색·확인 재보정·추가 실측은 하지 않았다.

## 종료·증거·검증

Run04 앱 정상 cleanup7, 회수7, host force-stop7 및 프로세스 부재를 구분해 확인했다. 마지막 confirmation host_commands3994 force-stop 반환0,3995 ps 반환0이며 대상 package 부재,3996 thermal 반환0. parent/child도 종료됐다. 이는 계획 종료 시 관측이며 현재 기기 상태를 재조회하지 않았다. 이전 중단 앱 cleanup 미확인은 그대로 보존한다.

PC 실제 poll의 warmup/baseline/common 승인 경계·원래 오류·후속 root/동결·소비 차단 등12검사 통과. 입력/모형/현재 실행 소스110파일 동일성, 144개 5초창 합과 전체 J 보존, AP 수치 재계산, 공유CLI 결과 일치를 검증했다. PC fake 검증은 실기기 연결 안정성 보장이 아니다. 검증 HEAD bf0d7a8 + 이 커밋의 변경이며 원본 실행 소스 해시는 계획에 동결돼 있다. 결과 readout의 AP 재계산 초안은 기존 coverage 검사에 막혀 저장된 적격 평가 경로를 재사용하도록 고쳤다; 기기 실행·동결 분석 결과 변경은 없다.

외부 원본 기준 폴더는 `C:/Users/LG/Documents/D1Check_Arrival_Extension`. 완료 receipt: `separated_power_run_v4/FINAL_RECEIPT.json`; 중단 receipt: `separated_power_run_v1`와 `separated_power_run_v2`. [원본 inventory 요약](inventory_summary.json), [검증](verification.json). 원본·APK·키·전체 host 로그는 Git에 넣지 않는다.

개인 PC 원본 없이 예정 도착 예측 재현:

```powershell
python -B -m tools.d1_separated_power_readout --bundle docs/results/online_policy_study_01/separated_power_final --case-id confirmation_0_CPU_URGENT_ONLINE_V1 --policy CPU_URGENT_ONLINE_V1 --output output/separated_cpu_replay
python -B -m unittest tools.test_d1_preparation_observation tools.test_d1_separated_power_followup tools.test_d1_separated_power_study
```

원본 잔차 재현(출력은 새 디렉터리):

```powershell
python -B -m tools.d1_separated_power_results --root C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_run_v4 --output output/separated_residuals
```

다음 PC 작업 하나: 이미 회수된 마지막 CPU의 작업 종료 후 전력·열 상승을 시간·센서·host 관측으로 더 국소화하여, 정책 비교에서 배경 변동을 예측하지 못하는 조건을 명시한다. 같은 확인 배치를 자동 반복하거나 이 실패를 제외한 순위를 만들지 않는다.

후속 PC 판독: [작업 후 유휴 상승·정책 사용 경계](../post_idle_pc_v1/README.md). 기존 수치와 원본은 변경하지 않았다.
