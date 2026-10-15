# C10 — 원미실행19회 계속

새 개정 혼합4는 WAIT/BASE2조건256건 정상회수, PAIR는27.6℃ 공통 기준을 최대600초 안에 통과하지 못해APP1/MAIN0·예정128미실시로 보존했다. 실제추가4소비3, ORDER1은미실행/예산예약으로 남긴다. PAIR의실패·cleanup DRAINED·기록닫힘·같은실행회수·빈자기프로세스정리를 확인한 뒤 C10을 시작했다. 이전PAIR를같은ID로재실행하거나성공으로승격하지않는다.

사용자 승인 전체85회 안에서, 원계획81의미실행19회·2,856요청을 **원래 승인 순서 그대로** 먼저 진행한다. 새개정ORDER는별도계획쪽에그대로보존하며원40의순서는바꾸지않았다. 원계획시작전62소비 + 추가개정3소비 =65, C10최대19를모두소비해도84이며남은개정ORDER1까지85다. 원래40의실패128과개정4의실패128은각각보고한다.

- 실제job `output/A24R02C10/job.json`, 원물 `Documents/A24R02C10`, 전역예약 `Documents/A24R02C10_GLOBAL`.
- 실제시작2026-10-16 01:48:18 KST, 최초분류CPU SID `c8e507d1-6c8a-5886-b1a1-6aa57592ca7f`.
- 실행소스f43b357, coordinator SHA `4ce2df0533a68b9d8bda549f38031bfe6d894bf0a727293fc7c23a4a590f708d`, 원179/APK/원40등록·입력·기한·MAIN판정·완료/자원반환은불변이다. 이실행의준비전조건도원v2이며개정4의예비조건보완을몰래전용하지않았다.
- 새전화읽기16과기존이력/원장/실제19authorization PC검산을결합했다. 완료·실패ID는건너뛰고미시도19만처음실행한다. 마지막L64는기존27.1℃reference를이월한다.
- 기기12:40/저장12:45 KST기술상한(사용자직접종료시각아님), SOC≥10·비충전·동일기기/화면·단절최대20분·새APP21분/MAIN5분여유를유지한다.

```powershell
python -B output/A24R02C10/PC_OBSERVE.py
# 실행명령은이미1회호출됐으므로재실행금지.
```

실제진행은OWNER/APP intent/START/outcome/WINDOW_STOPPED를대조한다. 중지지시에는C10 root의STOP_AFTER_CURRENT를기록해다음APP만막고현재조건을회수한다. J미판정/AP HAL·표면미검증/experiment_ready=false·기존원자료/사용자WIP/데스크톱/S26/NPU는유지한다.
