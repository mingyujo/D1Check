# 남은23회 — 21:58 시작 2시간 창

사용자 “2시간 있음”에 따라 **2026-10-15 21:58:13~23:58:13 KST**, 기기 종료 **23:53:13**, 마지막5분 저장으로 새 방문을 등록했다. 원계획40 중 미실행23회/3,368요청만 원순서대로 대상으로 한다. 짧은 시간창에 모두 완료한다고 전제하지 않으며 새APP21분/MAIN5분 여유가 부족하면 더 시작하지 않는다.

[시간창](USER_WINDOW.json) · [실행 계약](EXECUTION_CONTRACT.json) · [PC23 결합 증거](PC_VERIFICATION.json) · [실행 소스 문맥](RUNTIME_CONTEXT.json) · [시작 전 읽기 점검](BEFORE_DEVICE_READONLY.json)

- 실제 job: `output/A24R02C6/job.json`, 실행 로그 `output/A24R02C6/execution.log`. 이 명령은 이미 시작했으며 다시 실행하지 않는다.
- 원물: `Documents/A24R02C6`; 전역 예약/intent/owner: `Documents/A24R02C6_GLOBAL`.
- 시작 전 확인17/40·정식58/81·실제APP55+별도진단1=56. 이번 APP intent를 예산에 추가하며 모호한 전송도 소비로 보존하고 자동 재전송하지 않는다.
- 첫 조건은 블록3 L64 PAIR_G, `2f15f739-0a34-58d3-b8e9-24a739bc6d8c`. 앞 BASE의 **27.1℃**, 원 reference SHA `a09f9325ac22164fa3e1fc1b2f1c267927ea5d02702fda30796bb087e367d570`를 그대로 복사한다.
- 처음은 앱 밖 자연 냉각 대기다. 최초 관측 AP 약29.4℃였으며 낮아졌다는 이유로 기준을 새로 잡지 않는다. 준비 전 냉각과 워밍업 후 MAIN의 기존±0.5℃·60초·기울기0.1℃/분·최대600초 판정을 구분한다. 앱 밖 대기도 종료 시간창을 넘기지 않는다.
- 시작 전 폰은 동일 신원·기기APK SHA 일치·SOC84%·비충전·화면81/수동/Awake·예정 ID 경로 충돌0·소유 프로세스0이었다. 읽기16명령이며 실제 실행 수는 별도 원장으로 센다.
- 실행 소스는 공개 `31fa982f32df8d9e8e661f9240cde297e09acca6`의 coordinator SHA `bdf8811c5f5b249ce582798483ccf4dd9e549a55310a81e30003cca4b829c199`. core179/APK/계수/기한/전체40/지원 자원/MAIN·품질 판정은 변경하지 않는다.

사용자가 이동·중지를 지시하면 현재root의 `STOP_AFTER_CURRENT.json`을 write-once로 작성한다. 현재 조건은 close·회수까지 마치고 다음APP를 막는다. 이미 생성된root/종료 명령은 재사용하지 않으며, 실패·미완료·AP부적격을 성공으로 바꾸지 않는다. 에너지J null·표면온도 미검증·experiment_ready=false·원worktree/데스크톱/S26/NPU는 유지한다.

실제 상태는 현재 owner·APP intent·START/close·outcome·`WINDOW_STOPPED.json`과 대조한다. [남은23회 PC 준비](../confirm23_preparation_20261015/README.md) · [전체 실측 안내](../MEASUREMENT_RUNBOOK.md) · [기존 완료 원물](../../../results/a24_measurement_share_20261015/README.md)
