# 별도 전류 반응 진단 후 CONFIRM 복귀

2026-10-15. 별도 진단APP1회/543초/6반복을 회수·종료한 뒤 원래 확인40의 미시도31조건을 같은 순서로 등록했다. [실제 진단 결과](../../../results/a24_revision02_20261015/current_response_diag_01/README.md)는 순수 센서 지연·J 정확도 검증이 아니며 시간 보정을 적용하지 않는다. 기존CONFIRM APK와179핵심소스는 그대로다.

[시간창](USER_WINDOW.json) · [계약](EXECUTION_CONTRACT.json) · [PC31결합·9검사](FOLLOWUP_PC_VERIFICATION.json) · [등록](REGISTRATION.json) · [직전소비50 원장](../confirm40_window02_20261015/GLOBAL_CONSUMPTION_LEDGER_AFTER_PAUSE.json)

실제job은 `output/a24_confirmation40_after_diag_20261015/job.json`,원물은 `Documents/A24R02C3`,독점예약·APP intent는 `Documents/A24R02C3_GLOBAL`다. 시작 전 공식소비50/81,확인9/40·1,272요청완료,별도진단1회다. 실행 중 총소비는50+새root의APP intent이며 진단1회는 별도 포함해 공시한다. 기존종료창·root를 재실행하지 않는다. 기기20:02/작업20:07 KST,신규APP21분/MAIN5분 여유는 동일하다.

첫재개조건은 R02CONFIRM02 M128 PAIR_G다.18:49:50 KST에 실제MAIN이 시작됐다. 직전BASE가 정한**27.9℃** reference를 같은SHA로 복사해 공유하고,진단 뒤 안정·냉각·공통워밍업 후 원MAIN gate를 다시 통과했다. 기준 재선정·임계완화·완료군 재측정은0이다.

직전방문 중지 직전에 다음PAIR의PC binding만 만들어져 있었지만 APP예약/intent·START·원물·outcome은0이었다. 새coordinator는 이 상태와 보존된binding전체SHA,종료증거를 명시적으로 검사한 뒤 그 미실행ID의 최초APP만 허용한다. 이미실행한ID나모호한예약은차단한다. 기존followup소스는 덮어쓰지 않았다.31개정확manifest/authorization은PC에서전부조립했으며 가상reference는실기기증거가아니다.

새 `tools/d1_a24_confirm_after_diagnostic.py`는 진단close/기존APK보존·기존원물·전역미소비상태를 결합한다. 향후 사용자가 이동·중지를 지시하면 현재root에 `STOP_AFTER_CURRENT.json`을 새로 작성할 수 있다. 이 플래그는 다음APP를 막고 이미진행중인조건은close·회수까지 마친다. 활성소스·동결창을수정하거나실행중추론을강제종료하지않는다.

```powershell
# 조회 전용: 정확한 계약·원물·PC증거를 검사한다.
python -B tools/d1_a24_confirm_after_diagnostic.py output/a24_confirmation40_after_diag_20261015/job.json
# 아래 실행은 이미 시작했다. 새root/새방문을 등록하지 않고 다시 호출하지 않는다.
```

현재실제상태는위job의원물·APP intent·START/close·`WINDOW_STOPPED.json`과프로세스를확인한다.실행등록은31회완료를뜻하지않는다.데스크톱훈련/S26/NPU/사용자WIP는변경하지않는다.
