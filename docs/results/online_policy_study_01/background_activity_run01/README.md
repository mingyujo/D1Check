# 배경 활동 개발 대조 Run01 — 앱 시작 전 중단, 2026-10-03

> 최신: 새 plan_v3 수집4/4 완료·소비/종료, 시스템 trace 계약 부적격. [Run02 결과](../background_activity_run02/README.md). 아래 준비·중단 기록은 과거 사실이며 이 계획을 재실행하지 않는다.

**stopped_no_resume.** 승인된 plan_v2를 한 번 호출했다. 새 APK 설치·기기 동일성·host 환경 확인은 통과했지만 첫 C0의 trace 준비에서 `perfetto --help` exit1을 실패로 취급해 종료했다. 앱 시작/추론/공식 관측은 0이다. 새 에너지·AP 오차, 계수 식별, 독립 확인은 없다. 같은 계획을 재실행하거나 새 실행 계획을 자동 생성하지 않았다.

[작은 요약](summary.json) · [종료 화면](index.html) · [원래 준비 계약](../background_activity_pc_v1/README.md)

## 실제 경계와 원인

실행 코드 HEAD `5053451e94b60dab8d4cc6e32c5d2aaa1423cc4e`, 최초 작업 트리 clean. Check는 계획 SHA `a214b53e8aab91ed948f23343a2fbf7eb33e2839e721d16aadc94862ad78d97e`, APK SHA `9d8d55c2742b485e18f8a0812b70bf33ed66f9185c6d47b80c39f086e73fd932` 및 기존 모형과 일치했다. 현재 ADB 목록에서 A24 하나를 선택하고 모든 후속 명령은 그 transport에 고정했다. fingerprint/하드웨어·설치본·package/version·프로젝트 서명 확인, 비충전/배터리78%/BAT27.9°C/thermal0/기존 화면 조건은 관측상 통과했다. host /proc/meminfo 조회는 보존했으며 앱 내부 memory·warmup 품질/GPU 및 numeric 시작 AP 승인은 아직 도달하지 않았다.

|이벤트|UTC host wall clock|근거|
|---|---|---|
|현재 transport 목록 조회 착수|08:58:51.829 부근|별도 launch check approval/client 기록|
|원 실행 claim|08:59:23.569|host_checkpoints/0000.json|
|설치 검증·설치 단계 cleanup|09:00:09.830까지|installation_receipt.json, 명령0020–0027|
|첫 C0 입력 staging·trace 준비|09:00:11.951 이후|attempt.json, 명령0044–0076|
|perfetto --help client|09:00:20.108–20.241|명령0077 result/stdout/stderr|
|원래 예외 checkpoint|09:00:22.319|host_checkpoints/0004.json|
|실패 prefix 회수·host cleanup·종료|09:00:23.878까지|명령0078–0087, checkpoint0005|

모두 host 기록의 wall clock과 monotonic duration이며 Android 사건과 임의로 시계를 정렬하지 않았다. 앱이 시작되지 않아 앱 monotonic timeline/공식창이 없다. 실행기가 앱을 실행하지 않은 사실은 전체 명령 로그에 `am start`가 없고 launch_attempts=0이며 trace 검사 앞에서 예외가 발생했다는 코드·checkpoint 순서로 확인했다. 빈 progress만 보고 추론0으로 정한 것이 아니다.

실패 명령은 `adb -s <현재 선택 A24> shell perfetto --help`: 0.132722초에 exit1, stdout0byte, stderr3804byte. stderr는 완전한 `Usage: perfetto`이며 --detach/--attach/--is_detached/--txt를 모두 포함한다. trace query/start에 이르기 전에 ObservedDevice의 일반 nonzero 검사에서 중단됐다. 연결 소실·timeout 기록은 이번 명령에 없다. stdout0은 명령의 stdout일 뿐 전송량0이나 연결 단절을 뜻하지 않는다. 나머지 nonzero4개는 예정된 `test -e`의 파일 부재 exit1이고 실패가 아니다.

**확인된 결함은 host 도움말 exit 처리**다. 이를 근거로 A24의 Perfetto 실제 data source/config/권한/clock/손실/trace 회수가 성공한다고 확정하지 않는다. 이 사항들은 미검증이다.

## 승인 대비 실제 소비

|항목|승인 상한|실제|
|---|---:|---:|
|개발 세션|4|준비 시도1, 앱 실행0, 완료0|
|본 요청 / warmup / 총 추론|192 / 32 / 224|각0|
|runtime|16|0|
|staging|4회·28파일|1회·7파일|
|설치본 host pull|1|1|
|APK push / 데이터 보존 설치|각1|각1, 설치본 SHA 확인|
|trace 시작 / trace pull|각4|각0|
|ADB|13036|89=실행기88+선택 조회1|
|고정 관측|840초|0초|
|전체 상한|4454초|명령 선택2.116+실행기61.637=63.753초, 첫 조회~종료 wall92.049초|
|재시도 / 대체 / 추가 세션|각0|각0|

명령 선택과 Run 사이의 PC 준비 공백도 wall92.049초에 포함했다. 실행기600/896초 예약은 정상 소요시간이 아니며 실제는 훨씬 짧다. 첫 C0만 준비됐고 CPU96/PAR96/C0_POST는 미시도. 개발4 자료도 AP/에너지/과거입력·CPU 활동 검증도 얻지 못했다. 설치만 성공한 것으로 GPU·앱 안정성·모형 검증을 주장하지 않는다.

## 회수와 종료

앱이 아직 실행되지 않아 앱 자체 cleanup은 해당 없음이다. 설치 단계 force-stop1회와 실패 세션 정리 force-stop1회는 다른 단계의 소유된 정리이며 세션 종료 중 재시도는 없다. 종료 후 명령0086의 `ps -A`에서 대상 package 행이 없고 thermal0을 확인했다. 다른 앱·설정·ADB server·endpoint는 변경하지 않았다.

실패 prefix의7개 cat 조회는 예정된 예외 경로였으나 아직 만들어지지 않은 앱 artifact의 `No such file or directory` 출력이므로 정상 회수 자료가 아니다. progress_prefix의 invalid/partial line1은 이 오류 문자열이지 실행 이벤트가 아니다. 정상 회수·앱 실패·추론 미확인을 혼동하지 않는다. 원래 host exception과 후속 non-JSON 회수 오류는 별도로 보존했다.

Python child9672/PowerShell parent11316의 정상 receipt 및 도구 exit1을 확인했고 이후 PC 프로세스 조회에서 해당 PID는 없었다. checkpoint의 상세 host_identity는 null이었다. PID만으로 완전한 소유권이 확인됐다고 표현하지 않는다. 외부 복구나 추가 force-stop은 수행하지 않았다. trace 시작 intent 자체가 없으므로 활성 trace와 원격 trace 파일은 만들지 않았고 삭제도 하지 않았다.

## 최소 PC 수정·검증

`trace_start`의 help 조회만 `check=False`로 바꾸고, exit0/1 + recognizable `Usage: perfetto` + 필요한 네 옵션을 모두 확인해야만 다음 단계로 진행하게 했다. 다른 명령의 nonzero 검사를 완화하지 않았고 추가 조회/재시도/timeout 변경을 넣지 않았다. 새 입력·부하·APK·모형·센서 설정은 변경하지 않았다.

원본 stderr와 byte-identical인 `tools/fixtures/perfetto_help_a24_exit1.txt`를 사용해 실제 trace 시작 진입에서 help exit1 처리·한 번만 읽기·exit2 거절을 검증했다. 관련 Python8건 모두 통과. 기존 단일 recovery·실제 fake 공유 runner·소비 재실행 차단·clock/loss/null 검사도 포함된다. 수정은 PC 검증이며 이후 기기 실행은 하지 않았다. 기존 소비 plan_v2의 Check가 기기 호출 전에 거절되는 것과 원래 plan/APK/model SHA 불변도 확인했다.

재현:

```powershell
python -B -m unittest tools.test_d1_background_activity_plan
```

기존 프로젝트 서명 APK는 이미 설치됐으며 Android 변경/추가 빌드0. 모형 기본/strict/experiment_ready=false 유지. 수정된 host source hash는 과거 동결 실행기와 다르므로 **종료된 plan_v2를 변경·재개하지 않는다**. 새로운 실측은 이번 승인에 이어 자동 실행하지 않는다.

## 원본과 다음 행동

- 원 실행: `C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_run_v2/FINAL_RECEIPT.json`; 같은 root의 frozen plan, installation, host_commands/0077/client, host_checkpoints, failure prefix, registry stopped 기록.
- 현재 transport 선택 기록: 외부 `background_activity_launch_check_20261003T085851Z`.
- 원본484파일 inventory와 분리된 기술 분석: 외부 `background_activity_run_v2_pc_analysis/{raw_inventory.json,summary.json,host_exit_observation.json}`. 원본은 수정하지 않았다.
- 정확도·에너지/열 정책 우열·후보 식별은 여전히 미완료. 결과 그림을 만들지 않는다.

다음 PC 행동 하나: **수정한 도움말 판독 경로를 별도 미소비 계획의 실행기 해시에 연결한다.** 설치된 APK는 재사용하며 그 계획의 현재 설치본·data-source/config 지원 gate는 실행 전 확인해야 한다. 이번에는 새 계획·claim·추가 실행을 만들지 않았다.
