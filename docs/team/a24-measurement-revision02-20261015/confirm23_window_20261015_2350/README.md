# 남은23회 — 23:50 전 종료로 앞당긴 C7 방문

사용자 “11시50분전까진 끝내야”를 반영한다. **기기23:45 KST 종료, 회수·저장23:50 전 완료**를 적용하고 마지막5분을 확보한다. 이전23:58 시간창의 파일을 수정하지 않고, C6를 앱 전 대기에서 안전하게 닫은 뒤 새 C7 시간창으로 결합했다. 원확인40 중 미실행23회·3,368요청만 같은 순서로 대상으로 한다.

[앞당긴 시간창](USER_WINDOW.json) · [실행 계약](EXECUTION_CONTRACT.json) · [23개 실제 authorization PC 검산](PC_VERIFICATION.json) · [관련31검사](REGRESSION_VERIFICATION.json) · [읽기전용 시작 점검](BEFORE_DEVICE_READONLY.json)

**현재 C7 실행 중:** 실제 시작 소스는 공개 커밋 `268d47bca5c7e5f98b893388f507e606bef99ede`이며 coordinator SHA는 `426f92d2a4178613a366ce806386f50419a20695f6b99682f1d4fc7260ef66e5`다. [실제 시작 문맥·결합 SHA](RUNTIME_CONTEXT.json). 시작 직후 앱 전 AP28.2℃/APP0으로 원기록이 생성됐다. 이후 완료 여부는 실제 원장으로 확인한다. 이 명령을 재실행하지 않는다.

- 실제 job은 `output/A24R02C7/job.json`, 새 원물은 `Documents/A24R02C7`, 전역 소유·예약은 `Documents/A24R02C7_GLOBAL`이다. 실제 실행 여부는 owner·APP intent·START/close·outcome·WINDOW_STOPPED와 대조한다. 시작한 명령을 다시 실행하지 않는다.
- 시작 전 확인17/40·2,352본요청, 정식58/81·23미실행, 실제APP55+별도진단1=56이다. 첫 조건 L64 PAIR_G는 원 BASE의27.1℃와 reference SHA `a09f9325ac22164fa3e1fc1b2f1c267927ea5d02702fda30796bb087e367d570`를 그대로 인계한다.
- C6는22:30:21 KST에 앱 전 냉각 중 종료했다. APP/워밍업/MAIN/START/claim/세션 소비0이며 원리적으로 냉각 불가함을 판정한 종료가 아니다. [닫힌 냉각 원기록·정정·SHA](../../../results/a24_measurement_share_20261015/preAPP_visit_06_cooling/README.md)를 따로 보존한다. 원 C6 계약·소스 기록은 변경하지 않는다.
- 새 coordinator는 **종료된 앱 전 대기의 근거가 있는 경우만** 미소비로 인계한다. APP 명령·intent·START·실제 raw·불명확한 종료가 있으면 차단하며, 이전 냉각 기록·stop·binding SHA를 검증한다. 과거 실행을 재수집하거나 실패를 삭제하는 변경이 아니다. 관련31기능·회귀 검사가 통과했다.
- frozen core179·APK·모델·입력·기한·품질·MAIN 조건·지원 병행·예산81은 그대로다. 새APP/NEW_SESSION21분·MAIN5분 여유를 이번의 더 이른 기기 종료에 적용한다. 동일 기기 재연결 대기는 최대20분과 남은 시간창 중 짧은 쪽이다.
- 준비 전 자연 냉각과 준비·워밍업 후 MAIN 조건을 구분한다. [시작온도·상승량·냉각의 한계 설명](../confirm23_window_20261015_2158/INITIAL_STATE_INTERPRETATION.md)은 계약 변경이 아니다. 사용자는 같은 장소라고 정정했고, 주변 온도·통풍은 미측정이다.
- 22:34:59 KST 읽기16명령에서 같은 등록폰·설치APK SHA 일치·SOC82%/비충전·화면81/수동/Awake·미실행 경로 충돌0·소유 프로세스0을 확인했다. 이 점검은 APP·설치·설정변경·추론·계측·세션 소비0이다. 별도 사용자 온도 질문의22:34:05 AP28.0℃ 조회6명령도 구분해 로컬에 보존한다.

J 미판정·AP는 HAL 읽기 채널·표면온도 미검증·experiment_ready=false를 유지한다. 사용자 작업·데스크톱 학습·S26/NPU는 변경하지 않는다. 원래40조건의 실패·미완료·미실행 분모를 그대로 보존한다.

~~~powershell
$env:PYTHONIOENCODING='utf-8'
python -u -B tools/d1_a24_confirm_remaining.py execute output/A24R02C7/job.json --execute-authorized
~~~

위는 이번 방문의 원명령 기록이며 실행한 뒤에는 재사용하지 않는다. 중지·이동은 현재 원물 root의 `STOP_AFTER_CURRENT.json`을 write-once로 남겨 다음APP를 차단한다. 현재 요청이 실행 중이면 close·회수까지 마친다.
