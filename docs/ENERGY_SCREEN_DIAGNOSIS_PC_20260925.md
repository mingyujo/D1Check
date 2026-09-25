# ENERGY-SCREEN-DIAG-PC-01 — 화면 관측 timeout PC 진단·최소 수정

## 확정 원인과 미확정 사항

시작 `eed0852`/clean, 브랜치 `feature/arrival-scheduling-20260923`. 기존 계획/registry/원자료는 stopped_no_resume 그대로다. ADB·기기 조회·설치·추론·빌드를 실행하지 않았다.

직접 중단 원인은 `energy_collection_run_v2/host_commands/1099/client/result.json`의 명시적 serial 대상 `adb shell dumpsys power` **2초 제한 소진**이다. 2026-09-25 19:18:19.812 KST 시작,19:18:21.837 종료(2.016초). 당시 첫 개발 CC_DG serial의 탐지GPU 부하 구간이었다. 마지막 화면 관측 직전 정상 조회는19:18:09경이다. 실패 출력222612bytes/오류출력0이며 부분 문자열은 Awake/interactive였다. 전체 명령 완료 증거가 없으므로 정상 gate로 승격하지 않는다.

기존 동일 조회32건 중31완료/1timeout. 완료31건 시간 최소0.297/중앙0.422/nearest-rank P95 0.656/최대0.687초. 출력546314~550740bytes, 중앙547581bytes. 이는 한 실행의 기술통계이며 미래 지연분포/신뢰구간이 아니다. 같은 조회 시작 간격은 초기 설치·세션 gate 사이51.875/18.985초, 이후 대체로10.39~11.23초였다. 즉시 중복 조회/동시 자체 ADB client는 기록상0이다. 설정조회는 시작 gate에만, 화면10초·thermal2초·목록/heartbeat는 직렬이다. 다른 앱/도구의 전체 ADB 활동은 포괄 관측하지 않았으므로 외부 경합은 미확인이다.

`d1_recorded_process.run`은 receipt/file 생성 전 monotonic 시작부터 Popen 및 wait까지2초를 계산한다. 따라서 client 생성·ADB 통신·기기 dumpsys 처리·전송·로컬 파일 쓰기를 포함한다. 앞선 server_probe(최대1초)와 실패 후 root 종료/host snapshot은 이2초 밖이되 전체 deadline 안이다. 기존 로그에는 Popen 반환 시각이 없어 생성/통신/기기 처리/출력 지연을 더 분리할 수 없다. stdout/stderr는 PIPE가 아닌 파일 직접 redirect이므로 host가 PIPE를 안 읽어 막히는 구조는 아니다. 디스크/무선/기기 처리/OS 스케줄링 지연 가능성은 남지만 어느 하나로 확정할 수 없다.

큰 덤프의 생성·약0.55MB 전송·저장과 반복 host 관측은 기기 에너지/부하에 영향을 줄 수 있다. 관측 없는 대조가 없어 영향 크기는 식별 불가다. 마지막 GPU 이벤트는 host 관측 실패의 원인을 증명하지 않는다. 화면 꺼짐·native crash·추론 자체 실패도 확정할 수 없다.

## 중단·회수 경계

1099 timeout→1100 manifest 회수→1101 진행기록 회수(19:18:26.149 반환)→1102 cleanup 조회→1103 force-stop(19:18:26.654 반환)→1104 ps/1105 thermal 순이다. 회수한10902행의 마지막은 seq10901 `load-1-67` host_inference start. snapshot은 force-stop보다 먼저이므로 그 사이 실행을0으로 간주하지 않는다.

runtime4/warmup8/적격성2 반환, 작업 최소746시작·745lane해제 확인. 실제 진단 시작748~872, 총명시추론 시작756~880의 기존 보수적 상한을 유지한다. app cleanup 조회는 종료 전 파일이 없어 `cat: ... No such file or directory`를 반환했고 기존 exec-out 경로가 exit0으로 전달해 파일명만 cleanup.json으로 저장했다. 정상 앱 정리를 의미하지 않는다. host 종료·프로세스 부재는 별도 확인됐다. 같은 원자료를 수정하지 않는다.

## 최소 변경과 검증

- **에너지 경로만** 새 `d1_energy_screen.snapshot` 사용. 기기에서 같은 `dumpsys power`를 끝까지 실행하되 두 상태행과 producer exit marker만 필터링하여 전송한다. 원자료의 두 상태행은55bytes다. marker 포함 크기는 향후 기기에서 확인해야 한다. 단순 grep 성공으로 dumpsys 실패를 숨기지 않도록 producer exit0 marker/중복 없음/두 상태 모두를 요구한다. `$?`는 inner shell에서 평가하도록 인자를 quote한다.
- **2초 제한·10초 cadence·새 조회·미확인 즉시 중단 유지**, 재시도/캐시/오래된 상태 전용 없음. query_unavailable, state_violation, setting_violation을 구분한다. 부분 출력이 정상 문자열을 포함해도 timeout은 실패다. 기존 arrival/calibration의 전체 덤프 경로는 변경하지 않는다.
- host 명령 receipt에 spawn 시작/반환/wait 시작/정상 반환 시각을 추가했다. 기기 내부 처리시간을 만든 것이 아니다. timeout/종료 의미는 동일하다.
- JSON 회수 시 파싱에 실패하면 `.invalid.bin`에 원문을 보존하고 회수 실패로 표시한다. 앱 실패와 회수 실패를 혼동하지 않는다. 기존 잘못된 이름의 원본은 보존한다.
- 관련 Python24건 통과(신규7+energy17): 누락/중복/비정상 producer 종료·실제 상태위반·조회timeout·재시도0·설정불일치·cat 오류·부분파일·bounded client 종료. 기존31완료 덤프의 PC 필터/파서 재생도 일치했다. 재생 marker는 완료 receipt에 근거한 합성값이며 실제 Android shell 성공을 증명하지 않는다. 명령 인용/grep 지원·기기 latency·native 동작은 미검증이다. Android/APK 변경·재빌드 없음.

줄이는 것은 **전송/host저장량**이며 기기 dumpsys 생성비용은 그대로다. 시간·에너지 절감량이나 재발률을 산출하지 않는다. 변경 후 관측 부담이 달라져 기존 부분 에너지125.4J/314.2J와 새 실측을 같은 측정조건으로 조용히 합칠 수 없다. mA 가설·불완전 관측 한계와 experiment_ready=false 유지.

## 다음 최소 후보 — 미승인·미실행

별도 `ENERGY-SCREEN-OBSERVE-01` 후보: **추론 없는 화면 관측1회 시퀀스**, filtered query32회/10초 간격(관측창320초), identity/환경/readiness≤60초, client 종료·기록≤60초, 여유40초로 전체상한480초(8분). 설치/전송/runtime/warmup/AI요청 모두0, 재시도/대체/추가0. 32회는 기존 실패까지의 관측 건수 대응일 뿐 안정성 검정 표본수가 아니다. 종료 계획 재개가 아니며 새 registry는 이번에 만들지 않는다.

동일 A24·비충전/20%/≤35°C/thermal0·화면 기존값, 실행중 다른 수집 없음 조건. 32조회 모두2초 안에 두 상태+producer exit0을 새로 확보해야 ‘필터 기기 동작 확인’으로만 판정한다. 한 번이라도 timeout/불완전/상태위반이면 중단. 앱을 시작하지 않으므로 앱 force-stop도 필요 없고 자신이 시작한 client만 bounded 정리한다. 본 후보의 장치 실행 CLI는 아직 작성하지 않았으며 있다고 제시하지 않는다. 승인·후보 스크립트 고정 전에 실행 불가다.

이는 전송·shell/파서 호환성을 확인하는 최소 진단이며 **추론 부하 중 timeout 재발 위험을 검증하지 못한다**. 성공해도 전체8세션 재수집이나 병행 우월성 평가로 자동 확대하지 않는다. 실패하면 해당 관측 방식 개발을 중단하고 원문을 보존한다. 다음 부담 큰 수집을 정하기 전에 이 한 번의 확인 결과와 남은 부하 위험을 판단한다.

## 근거·재현

[조회별 CSV](results/energy_screen_diagnosis_pc_01/screen_queries.csv), [통계](results/energy_screen_diagnosis_pc_01/summary.json), [검증 대상](results/energy_screen_diagnosis_pc_01/verification.json).
외부 상세 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_screen_diagnosis_pc_v1`와 기존 run_v2. 원자료/키/모델/APK는 Git에 올리지 않는다.

```powershell
python -B -m unittest tools.test_d1_energy_screen tools.test_d1_energy_collection -v
python -B -m tools.d1_energy_screen_audit --run C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_run_v2 --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_screen_diagnosis_reproduce_NEW
```

출력은 새 경로만 허용한다. plan_v4의 source hash는 이제 현재 host와 다르며 소비된 옛 계획은 수정하지 않는다. 실행 당시 소스는 Git6b1a743/eed0852에서 재현한다. 미래 계획에는 새 host source hash가 필요하다. 기존 FAIL·부분 결과·동결값·종료 기록·S26/NPU 별도 범위를 보존한다.
