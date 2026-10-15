# A24 전류 API 반응 진단 — 별도 소규모 파일럿

**최신 실제 결과:** 별도APP1회·6반복·543.475초·전류3,246조회,누락/충전0으로완료·회수했다. CPU관측반응약0.2~0.4초,GPU3회중1회검출이며순수센서지연은미확정이다. [원자료·CSV·그림·보고서](../../../results/a24_revision02_20261015/current_response_diag_01/README.md). 시간보정0·NN0,기존APK/179소스불변을확인하고 [미시도CONFIRM복귀](../confirm40_after_current_diag_20261015/README.md)로이어갔다. 아래 실행0문장은 사전등록시점 이력이다.

2026-10-15. 사용자 지시: 현재 조건을 마친 뒤 전류 반응 진단을 추가하고 남은 실측을 이어간다. CONFIRM 둘째 방문은 혼합 BASE 회수 후18:23:57 KST, 활성 APP0의 조건 경계에서 host만 중지했다. 원179소스·시간창·APK는 바꾸지 않았다. 현재 확인9/40,1,272요청 전량완료·출력PASS,총50/81소비·31미시도다. AP 적격 여부는 기존 최대10초 공백 기준으로 별도 검산한다.

## 사전 고정 범위

[PLAN.json](PLAN.json)에 **별도 진단 APP 최대1시도, 재실행·대체0**을 등록했다. 기존81회는 원래 DEV/CONFIRM의 예산으로 보존하고, 이번 사용자 추가 지시의 진단1회는 별도 원장에서 센다. 따라서 이후 총 실행 수를 보고할 때 진단을 숨기지 않는다. CONFIRM ID·입력·정책·계수·관측창을 바꾸거나 완료/부적격 세션을 다시 측정하지 않는다.

- 설치 패키지 `com.example.d1check.currentdiagnostic`: 기존 측정 앱과 별개다. 모델·이미지·NPU·주파수 변경·전력 제한을 사용하지 않는다.
- 부하: CPU 한 스레드의 산술 반복, GPU GLES3의256×256 offscreen 셰이더 반복 후 `glFinish`. 실제 추론이 아니며 이 결과를 모델·정책 성능으로 쓰지 않는다. GPU 컨텍스트는 전체 진단 동안 유지한다.
- 준비 후30초 안정 대기, 유휴 조회 간격900→200→100→100→200→900ms 각20초, 부하 반복6개, 최종30초 꼬리다. 계획시간543초에 GPU 준비·파일 회수 시간이 추가된다.
- 반복은 CPU100ms→GPU200ms→GPU100ms→CPU200ms의 개발4개와 CPU200ms→GPU200ms의 검증2개다. 부하10초/후대기30초, 전대기는20/23/18/22/19/21초로 고정했다. 두 검증 반복은 독립적인 새 기기 세션이 아니다.
- 모든 시각은 앱의 `elapsedRealtimeNanos`로 기록한다. 전류 API 시작·끝, 평균전류 API 시작·끝, 부하 시작·끝과 일부 batch 경계를 남긴다. `glFinish` 반환은 GPU 명령 완료 경계이고 실제 전력 상승 시각은 미확인이다.
- 원전류와 평균전류의 API단위는µA이나 설치 펌웨어의 단위 경로는 여전히 미검증이다. 단위 변환·전하량 보정·J 검증을 하지 않는다. 이 진단에는 최소 배터리10%/비충전/화면ON/배터리≤35℃/시스템 심각 열 상태 차단을 적용한다.
- 시간창은 기존 기기20:02/작업20:07 KST를 유지한다.543초 일정과 회수 여유를 위해 시작 시 최소900초를 요구하며, 단절 시 동일 등록 기기만 최대20분·종료시각 안에서 기다린다. 모호한 설치·APP 시작을 자동 재전송하지 않는다.

## 결과 확인 전 고정한 계산

부하 전 마지막10초의 방전 방향 원전류 중앙값, 부하 마지막4초의 중앙값, 부하 종료 후 마지막10초의 중앙값을 쓴다. 각 구간 최소5개 조회가 필요하다. 상승량이 양수이고 전대기 중앙절대편차(MAD)의3배를 넘을 때만 반응 시각을 계산한다. 이는 기술적 반응 검출 규칙이며 센서 오차 범위나 통계적 유의성 기준이 아니다. 끝4초를 정상상태라고 보장하지 않는다.

상승10%·50% 및 하강50%를 처음 충족하는 연속 두 조회의 첫 시각을 기록한다. 두 조회 사이가 요청 주기의2.5배를 넘으면 연결하지 않는다. 전류 누락·충전 표본이 있는 반복은 수치를 메우지 않는다. 반응 미검출은0초가 아니다. 상승·하강은 실제 소비 변화와 센서/HAL/API 효과가 합쳐진 반응이며 순수 센서 지연으로 명명하지 않는다.

유휴6구간의 원전류·실제 조회 간격·조회 함수 스레드 CPU시간도 남긴다. CPU시간은 JSON 직렬화·파일 flush를 제외하므로 전체 수집 비용으로 부르지 않는다. 짧은 순차 구간만으로 조회 부하와 시간에 따른 배경 소비 변화를 완전히 분리할 수 없다. 같은 반환값의 연속 길이도 센서 실제 취득 주기로 단정하지 않는다.

**이 파일럿에서는 CONFIRM 전류를 이동시키거나 새 보정을 적용하지 않는다.** CPU/GPU·조회 주기·검증 반복에서 얼마나 일관적인지 보고한다. 합성 부하 반응이 일정하더라도 실제 추론 전류의 정확한 지연과 절대 J 정확도는 별도 검증 대상이다. 결과가 불명확하면 공통 관측창과 조건부 에너지 해석을 유지한다.

## 구현·PC 검증과 재현

소스: `tools/a24-current-diagnostic/`, `tools/d1_a24_current_response_diagnostic.py`, `tools/d1_a24_current_response_analysis.py`. 독립 Gradle 프로젝트이므로 기존 측정 빌드·모델·앱 데이터는 교체하지 않는다. AGP9.3.2/Gradle9.5.0/SDK37/Java11 타깃, 외부 런타임 의존성0이다. 디버그 서명은 기존 로컬 개발 키이며 키 자체는 공유하지 않는다.

```powershell
$env:PYTHONPATH='tools'
python -B -m unittest test_d1_a24_current_response -v
.\gradlew.bat -p tools/a24-current-diagnostic :app:assembleDebug --offline --no-daemon --max-workers=2
python -B tools/d1_a24_current_response_diagnostic.py <PRIVATE_JOB.json>
# 아래 명령만 실제 등록 기기의 별도 진단1회를 소비한다. 기존 ID로 재실행 금지.
python -u -B tools/d1_a24_current_response_diagnostic.py <PRIVATE_JOB.json> --execute-authorized
python -B tools/d1_a24_current_response_analysis.py <RECOVERED_ROOT> <NEW_ANALYSIS_OUTPUT>
```

PC10검사는 계획 변경 차단, 알려진 계단 반응, 반응 없음·희소 표본·외딴 peak·큰 공백, 배율 변화, 재연결 후 읽기 회수와 모호한APP 무재전송을 검산했다. APK 빌드·v2서명 확인이 통과했다. **이 기록 시점에는 아직 진단 앱 실기기 실행0이다.** PLAN 생성 스크립트의 괄호 오류는 PC/APP0에서 수정했고 미완성 계획이나 실패한 측정을 만든 적은 없다. 실제 실행 후 원물·종료·SHA·해석은 별도 결과 보고서로 갱신한다.

근거: [Android BatteryManager](https://developer.android.com/reference/android/os/BatteryManager#BATTERY_PROPERTY_CURRENT_NOW). API 반환값에 센서 실제 취득 시각이 함께 제공되지 않는다.
