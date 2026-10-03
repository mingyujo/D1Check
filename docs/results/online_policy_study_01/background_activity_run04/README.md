# 배경 활동 Run04 — 남은 PAR·C0 개발2 완료

사용자의 재개와 추가 실행 승인으로 v5를 한 번 실행했으나 입력 staging에서 host localhost5037 연결 오류가 발생했다. 앱 launch0·추론0. v5는 stopped_no_resume로 보존했다. 같은 daemon 식별이 전후 유지되고 후속 동일 transport cleanup은 성공했으나 내부 원인은 미확정이다. timeout이 아닌 rc1/21.125초/timeout30초다. stdout0을 전송0으로 해석하지 않는다. gate·timeout·APK·측정 코드를 바꾸지 않고 별도 ID의 **campaign retry 1회 v6**를 실행해 PAR96→C0_POST 개발2/2를 완료했다. 계획 내 retry0, 추가 자동 실행 없음. daemon restart·reconnect·설정 변경0.

[대시보드](index.html) · [정확한 수치](metrics.csv) · [v6 분석](summary.json) · [별도 block 연결](combined_summary.json) · [소비](consumption.json) · [v5 실패](v5_failure.json) · [검증](verification.json) · [그림](paths.png)

## 결과와 범위

|block/조건|관측120초 J|조건부 예측 J|예측−관측 J|AP MAE °C|최대오차 °C|
|---|---:|---:|---:|---:|---:|
|이전 v4 C0_PRE|132.338|142.793|+10.455|0.152|0.274|
|이전 v4 CPU96|165.025|171.192|+6.168|0.203|0.843|
|이번 v6 PAR96|153.440|150.563|−2.877|0.225|0.638|
|이번 v6 C0_POST|129.789|143.740|+13.951|0.157|0.271|

에너지창은 common0–120초, AP 점수창은 common35초부터 cooling의 마지막 AP까지다(PAR178.123초, C0_POST179.757초). PAR 시작 AP28.9°C와 C0_POST29.5°C 모두 원래 개발32.5–34.0°C 밖이다. AP 보간 경계값과 gate 직접 시작값은 summary에서 구분한다. A24 전류raw=mA 조건부 해석이며 절대 J 정확도 인증 없음.

PAR 실제 classification_GPU+detection_CPU 병행13.050866초, 탐지CPU 단독17.198399초, 분류GPU 단독0.705280초, resident idle89.045454초. 96/96 반환·저장·lane 해제 확인. 전체 도착 분모 서비스 성공률1.0, 응답P95644.649ms. 이번 실행의 관측이며 정책 우월성 판정은 아니다.

두 trace는 공식 TP 5SQL/BOOTTIME 일치/8CPU/24개5초bin 전체 coverage·loss 검사를 통과했다. 120초 CPU초 benchmark/tracer/other는 PAR48.925/6.087/51.760, C0_POST7.904/6.143/46.742, unknown0이다. CPU초는 앱별 J·GPU/무선 에너지·원인 귀속이 아니다. sampler self CPU와 scheduler CPU의 집계 방식도 다르다. 추적/host 관측 부하는 전체 기기 에너지에 포함되며 임의 보정하지 않았다.

**앞선 v4 C0·CPU 두 적격 자료와 이번 v6 두 자료를 사용할 수 있게 됐지만 v4의 4세션 계획이 완주한 것은 아니다.** 별도 수집 시점·준비/실패 이력·block을 유지한다. 이번 자료는 개발 자료이며 독립 확인0, gamma 적합/채택0이다. 예측 입력은 동결 계수와 이 세션의 부하 전10–30초 전력/AP 및 실제 일정이다. 미래 AP/전력을 피드백하지 않은 조건부 계산이며 세션 시작 전 무관측 종단간 예측이 아니다.

유휴 양쪽에서 +10.455/+13.951J 과대 예측, CPU +6.168J, PAR −2.877J다. 시스템 활동을 실제로 관측하는 공백은 해결됐다. CPU 활동과 J/AP 잔차의 관계·독립 확인은 미완료다. 시간·초기 AP·프로토콜이 다른 두 부하의 총J를 직접 정책 우열로 쓰지 않는다. model/default/strict/experiment_ready=false 유지. 정책 튜닝·추가 실측·독립 확인 자동 실행 없음.

## 소비와 종료

|항목|v6 상한|v6 실제|
|---|---:|---:|
|세션|2|2|
|본/warmup/총 추론|96/16/112|96/16/112|
|runtime|8|8|
|staging/입력파일|2/14|2/14|
|설치본 pull/trace pull|1/2|1/2|
|APK push/설치|0/0|0/0|
|ADB (선택 포함)|6618|1669|
|runner+선택 작업초|2402|735.433|

고정 관측420초·세션 사이90초. runner733.725초+선택1.709초. PowerShell 진입/종료까지 wrapper wall735.724초+선택=737.432초도 보존했다. v5는 ADB68/142.983초/설치본pull1/입력파일push7(완주 staging 아님)/추론0/trace0. 두 실행 누적 추론112/ADB1737/receipt 작업878.416초이며 별도 소비 계획이다. v5 실패를 지우지 않는다. PC 분석·두 실행 사이 공백은 기기작업과 별도다.

v6 앱 정상cleanup2, host 대상 force-stop2, 저장된 최종ps 대상 부재2, 자기 trace key 종료/회수2. 원래 앱 실패·후속 정리 실패 없음. Python/PowerShell exit0·종료시간 보존, 이후 PC 원래 parent/child PID 조회에서 부재 확인. 현재 연결 확인용 추가 ADB0. 원격 삭제0. v5 앱 cleanup은 launch0으로 해당없음이며 host force-stop/ps 부재와 구분한다.

원본: `C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_run_v6/FINAL_RECEIPT.json`, host_checkpoints·명령·artifacts·trace_export·trace_recovery 보존. 원본8762파일189741068byte. 외부 `background_activity_run_v6_pc_analysis/raw_inventory.json` SHA6c38ebd86265df9c2daac3c69e8b5e4de62d869164efd98375eddd01208382ba. v5 원본/failure_summary 별도 보존. 소비 registry 수정0.

## 동결·검증·재현

v6 planSHA c6996d55c98b741caf470c59fbac140eb23df25e99a6e488dc3d0db7efb39092. APK9d8d55c2…73fd932, activity model5682082a…72db2, 기존 development freeze35ed6987…034c54 불변. 빌드0. 변경은 factory 새 ID/output/v5 receipt campaign_retry 결합과 PC 공유 출력뿐이다. 과거 전체 테스트/빌드 반복0. 실제 PowerShell Check 기기0 통과, 원자료 분모·120초 상태합·J 산술·CPU coverage·공유CSV·동결hash·공유물만으로 그림/표 재현 확인. 그림 육안 확인. 대상HEAD84532f0+미커밋 소스는 verification.json 참조. PC 검증은 장시간 안정성/독립 모형검증이 아니다.

원자료 분석:
```powershell
python -B -m tools.d1_background_activity_result --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v6/collection_plan.json --exports C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_run_v6 --output '<새 분석 폴더>'
```
공유물만으로 표·그림 재생:
```powershell
python -B -m tools.d1_background_activity_share --previous docs/results/online_policy_study_01/background_activity_run03/summary.json --current docs/results/online_policy_study_01/background_activity_run04/summary.json --output '<새 공유 출력 폴더>'
```

다음 PC 행동 하나: **적격 네 개발 자료의 과거 시스템 활동과 잔차를 연결하여 gamma가 기존 전력/AP 항과 분리 식별되는지 검사**한다. 계수 채택·독립 확인 계획은 결과 전까지 보류한다. 같은 실측을 자동 반복하지 않는다.
