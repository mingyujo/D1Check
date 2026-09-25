# ENERGY-SAMPLER-LOAD-DIAG-01 결과 — 2026-09-25

수정 sampler의 CC_DG **직렬 부하 진단 1세션을 완료**했다. 이는 정식 개발·확인 표본이나 에너지 절감 평가가 아니다. 이전 COLLECT-03의 `NoSuchElementException`은 stack이 없어 동일 원인으로 확정할 수 없으며, 이번 한 번의 성공은 반복·병행 안정성을 입증하지 않는다.

## 실행과 소비

- 실행 시작 코드: `55a143bcf96a249fdfc7581f2777e5079e6a1608`, clean. `energy_sampler_load_plan_v2/collection_plan.json` SHA-256 `2fae1bf99d59ccade283e8ff2f8022cf2a025b9b7fe8b1c23d9f925c44e7fa84`. A24 `SM-A245N` / 계획 fingerprint·hardware serial 확인, 현재 transport `192.168.219.103:39995`. 실행 전 배터리 79%, 비충전, 30.5°C, thermal 0 및 화면·메모리 gate 통과.
- 원래 설치본과 수정 APK 해시가 달라 승인된 전송 1회·설치 1회를 사용했다. 설치 후 APK SHA-256 `2874a97f93c21816fea683bd6403326443dd9c15e682919c4087788d22670931`, 계획의 package/version/signer와 일치. staging 1회·7파일.
- 세션 1/1 완료, runtime 생성 4/4, warmup 8/8, 적격성 2/2, 작업 870/870, 명시적 추론 880/880. 재시도·대체·추가 0. 실행기 claim→종료 902.5초 / 상한 2,100초. 이 시간은 설치·실행·회수·cleanup을 포함하며 요청별 처리시간으로 사용하지 않는다.
- 앱 `summary.json` completed, `cleanup.json` completed. 원시 `progress.jsonl`에 dispatch/request_start/output_ready/worker_release/lane_available가 각각 872개이고 host inference 시작·성공 단계가 각각 880개다. 이벤트 sequence 0–13,128에 중복·누락이 없다. sampler/session 실패 sidecar 없음. host 원자료 882파일 회수, host cleanup completed 및 `ps -A`를 이용한 프로세스 부재 검사 통과.

## sampler와 적용 범위

`power_sample` 794건, 새 상태 snapshot 필드가 있는 이벤트 1,678건을 회수했다. 모든 snapshot에서 `snapshot_start ≤ sensor_read_end ≤ state_snapshot ≤ event`이며 active key가 resident key 집합에 포함됐다. 4개 runtime 생성 전 표본 8건을 제외하면 4개 resident가 기록됐다. 화면 조회는 71/71 성공, 호스트 관측 지연 중앙값 0.610초·최대 0.781초다. 앱 표본의 배터리는 78–79%, 30.5–30.7°C, thermal status 0이었다. 이 성공은 새 snapshot/기록 경로가 **해당 직렬 부하 1회**에서 끝까지 작동했다는 증거다.

수집기의 `validated.json`은 `eligible_descriptive_only`를 기록했다. 480초 공통창에 작업 870건 완료, 전력 샘플 gap 0, resident 냉각 180초 중 0.746초는 에너지 적분 범위 밖이다. 전류 mA 해석은 여전히 조건부이며 절대 에너지 정확도가 인증된 것은 아니다. 이번 진단의 수치로 정식 직렬/병행 차이, 관측 비용 변화, 새 정책 우월성, 반복 안정성을 판단하지 않는다. 옛 부분 세션과 결합하지 않으며 `experiment_ready=false`를 유지한다.

## 근거와 재현

- 외부 원본·host 명령·receipt: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_sampler_load_run_v1/` (`FINAL_RECEIPT.json`, `00_806b55b0-1e94-58f3-82ec-fd95270f304f/validated.json`, `artifacts/progress.jsonl`, `artifacts/cleanup.json`, `host_cleanup.json`). 상세 보고: 같은 root의 `FINAL_REPORT.md`.
- 계획·APK identity·실행 명령: [준비 계약](ENERGY_SAMPLER_PC_20260925.md). 실행한 명령은 `RUN_AFTER_APPROVAL.ps1 -Action Check`, 이어서 현재 A24 serial을 지정한 `-Action Run -Approved`였다. 이 단일 사용 계획은 완료되어 **재실행하지 않는다**.
- 공유 가능한 작은 집계: [summary.json](results/energy_sampler_load_diag_01/summary.json). 원본·APK·모델·키는 Git에 포함하지 않는다.

다음 최소 행동은 정식 수집을 새 계획으로 재준비할 때 수정 APK·관측 경로를 개발과 확인에 동일하게 적용하고, 직렬/병행 적격성 및 전력·열 비교 기준을 다시 점검하는 것이다. **추가 실측 승인이나 실행은 이번 진단에 포함되지 않는다.**
