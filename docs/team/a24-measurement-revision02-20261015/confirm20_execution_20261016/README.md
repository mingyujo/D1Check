# 남은 독립 확인20회 — C9 실행 등록

사용자 최신 지시 **“우리 지금부터 실측 끝까지 다 진행할거야”**에 따라 기존 독립 확인40회 중 미실행20회·2,984요청을 이어간다. 시작 전 누적은20/40회·2,736요청, 정식 예산61/81회다. 완료·실패·기소비 ID를 재실행하거나 대체하지 않는다.

- 원순서 개정 `0..16 → 18..39 → 17` 유지. 첫 조건은 원21 M128 ORDER이고, 마지막은 원17 L64 PAIR_G다.
- 이월 M12828.4℃·L6427.1℃와 원 reference SHA를 그대로 사용한다. 새 묶음의 첫 기준만 기존 사전 알고리즘으로 정한다. 시작 온도·서비스·품질 기준 완화0.
- 사용자는 이번에는 별도의 시각 대신 **잔여 실측 완료까지**를 승인했다. 실행기에 필요한 기술적 상한은 작업자 판단으로 **2026-10-16 기기12:40 / 저장12:45 KST**에 둔다. 사용자가 이 시각을 직접 지정했다고 표현하지 않는다. 그 전에20슬롯의 승인 처리가 끝나면 즉시 회수·종료한다.
- SOC10% 미만/불명, 충전, 다른 기기/설치APK, 기기·앱 오류는 기존 계약으로 차단한다. 동일 기기 단절 재연결은 최대20분이고 불확실한 APP 전송을 자동 재전송하지 않는다.
- 과거처럼 도달하지 않는 온도를50분씩 무작정 기다리지 않는다. 대기 추이를 관찰하고 막힘을 알리며, 기준 재선정·미실행 누락으로 완료를 만들지 않는다. 원래 실행중인 APP의 준비 후600초 gate는 그대로다.
- 원 core179·APK·입력·기한·완료/실제lane반환·정책·계수·NPU·데스크톱 학습은 보존한다. J는미판정/AP는HAL 채널이며 표면온도는미검증, `experiment_ready=false`다.

실제 job은 로컬 `output/A24R02C9/job.json`, 원물은 `Documents/A24R02C9`, 전역 예약은 `Documents/A24R02C9_GLOBAL`이다. 실제 실행 여부는 root의 owner·APP intent·START·outcome·`WINDOW_STOPPED.json`과 대조한다. 이 문서는 실행 완료 증거가 아니다. **같은 명령을 중복 호출하지 않는다.**

시작 전 읽기16명령으로 동일 등록폰·설치APK SHA일치, SOC76%·비충전·수동밝기81·화면켜짐·기존 소유 앱 프로세스0·미실행 경로충돌0을 확인했다. 추가 APP/추론/계측/소비는 이 점검에서0이다. 동결 APK SHA는 `6fbe5c0812e3d123259be5004d37c6a4d6e9a2b750df2ac4ae5460b01f0bfd8b`다.

## 명령

```powershell
python -B tools/d1_a24_confirm_remaining.py inspect output/A24R02C9/job.json
# 아래는 최초 실행1회만. root가 생성되었으면 재실행 금지.
python -u -B tools/d1_a24_confirm_remaining.py execute output/A24R02C9/job.json --execute-authorized
```

상태 변경·유의미한 완료·새 장애는 PROJECT_STATUS와 실측 원장에 기록하고, 닫힌 원물만 묶음 ZIP·CSV·분석으로 공유한다. 이전 [20회 결과](../../../results/a24_measurement_share_20261015/confirmation_visit_08/README.md)·[미실행 목록과 PC 준비](../confirm20_preparation_after_C8_20261015/README.md)는 보존한다.
