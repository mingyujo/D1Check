# COLLECT-04 온도 동등성 중단 분석과 COLLECT-05 실행 후보

상태: **PC 준비 완료, 기기 미검증, 새 수집 미승인**. 이 문서는 종료된 COLLECT-04를 재개하거나 기존 ±0.5°C 판정 기준을 바꾸지 않는다. 원본·소비 registry·기존 FAIL·부분 에너지·40개 동결값·20개 null·`experiment_ready=false`는 그대로다.

## 확인된 온도 경로

`energy_collection_run_v4`의 두 시도는 같은 `tools/d1_logger_v4.py:parse_thermalservice`의 HAL `AP` 필드(°C, 관측 표기 0.1°C)와 동일한 앱 `resident_baseline` phase 경계 안의 host monotonic 표본 중앙값으로 비교했다. host는 `/proc/uptime` 조회 전후를 기록해 중간 시각과 불확실성을 보존한다. 앱 이벤트는 `elapsedRealtimeNanos`다. 한 기기 시간축의 구간만 뺐고 PC wall clock과 섞지 않았다.

| 구간 | 확인된 길이·표본 | AP 경로 |
|---|---:|---|
| 개발 CC_DG 직렬 공식 baseline | 120.009초·45개 | 32.9→31.4°C, 중앙값 **31.5°C**; 마지막 60초 31.4~31.5°C |
| 직렬 load 870건 | 327.274초·114개 | 31.4→34.0°C, 관측 최고 34.9°C |
| 직렬 post-work wait | 152.824초·52개 | 34.0→32.4°C |
| 직렬 resident cooling | 180.004초·63개 | 32.4→32.3°C |
| 다음 병행 준비 전 | 직렬 냉각 종료→병행 session 시작 60.130초 | 냉각 마지막 32.3°C, 병행 session 전 표본 31.4°C; 그 사이 연속 온도는 없음 |
| 병행 runtime 4개·warmup 8개·적격성 2개 후 공식 baseline | 120.043초·41개 | 첫 표본 33.8°C, 마지막 32.2°C, 중앙값 **32.3°C**; 마지막 60초 32.2~32.4°C |

따라서 공식 중앙값 차이는 **+0.8°C**로 사전 gate ±0.5°C를 넘는다. host가 병행 load를 arm하기 전에 중단했다. 직렬 냉각 마지막과 다음 session 전 표본은 오히려 내려갔고, 다음 runtime/warmup/적격성 이후 공식 baseline 첫 표본은 session 전보다 2.4°C 높았다. **준비 구간 재가열은 관측되지만**, 잔열·주변 온도·프로세스/화면 등 개별 원인의 몫은 식별되지 않는다. 180초 냉각 자체가 부족했다고 단정할 수 없다. 각 baseline의 최대 내부 표본 간격은 3.295/3.880초였고 첫·마지막 경계에 약 0.5~2초 표본 공백이 있다. 주변온도는 기록되지 않았다.

첫 시도는 직렬1세션만 완료했고 두 번째 병행 시도는 공식 baseline에서 멈췄다. 개발 2시도·1완료·1중단·2미시도, 확인 4미시도, 동결 없음. 두 번째에서는 앱 cleanup 기록을 확인하지 못했으나 host 종료와 프로세스 부재는 확인했다. 연결/배터리/thermal/화면 조회 및 두 번째 적격성 probe는 통과했고 다른 관측된 중단 요인은 없다. 긴 병행 load 안정성은 여전히 미확인이다. 상세 원본 판독은 [COLLECT-04 결과](ENERGY_THERMAL_COLLECT04_RESULTS_20260925.md)와 외부 `energy_collection_run_v4/FINAL_RECEIPT.json`을 따른다.

## 새 사전 준비 절차

종료된 계획과 분리한 `ENERGY-THERMAL-COLLECT-05` / `energy_collection_plan_v9` / `energy_collection_run_v5`에만 적용한다. 기존 180초 resident cooling과 session 간 순서를 유지한다. **매 세션 동일하게** runtime 4개 생성→warmup 8개→적격성 2개 완료 후, resident 상태에서 최대 360초의 `temperature_preparation` 구간을 연다. host는 단일 AP 센서의 완료된 관측만 보고, 마지막 60초에 20개 이상·내부 간격 최대 10초·시각 불확실성 최대 2초·범위 최대 0.3°C인 경우 준비 완료로 판정한다. 병행 세션에서는 이 창의 중앙값이 해당 단계·pair 직렬 공식 baseline 중앙값의 ±0.25°C 이내여야 한다. 첫 직렬에는 anchor가 없다. 그때 **공식 120초 baseline을 정확히 한 번** 수집하고, 이전과 같은 ±0.5°C paired 중앙값 gate를 다시 적용한다. 반복 baseline 선택·기준 완화·미래 표본 사용은 없다.

60초·20개는 기존 약 2.8~3초 AP 표본 간격에서 한 표본으로 안정 판정을 피하기 위한 설계값이다. 0.3°C 창은 관측된 baseline 후반 변동폭과 0.1°C 표기 해상도를 참고했다. ±0.25°C 사전 anchor 여유는 기존 ±0.5°C 최종 gate를 대체하지 않도록 둔 예방적 값이다. 360초는 기존 120초 baseline과 별도로 bounded 대기를 허용하는 **미검증 운영 상한**이다. 어느 값도 안정성·gate 성공률을 실측으로 입증하지 않는다. 350초까지 적격 창이 없거나 센서/thermal 조회가 무효이면 공식 baseline·load를 시작하지 않고 실패 근거를 남긴다. 앱 자체 arm timeout 360초, watchdog 1560초, host poll 1580초를 넘기지 않는다. host 기록·화면 조회·전류 샘플링은 이 대기에도 계속된다.

준비 대기는 출력의 `temperature_preparation` phase와 `gate_probe/temperature_preparation.json`에 별도로 기록한다. 공식 baseline과 동결 통계는 이전과 같이 하나만 사용한다. 추가 대기를 포함한 기기 전체 에너지와 시간은 별도 `including_preparation` 지표로 보존한다. 공식 baseline에서 산출하는 resident idle 기준과 전체 준비 비용은 서로 다른 수치다. 시작 온도 조건을 맞춘 실험의 **준비 비용**을 실제 배치 정책의 냉각 비용이나 절감 효과에서 숨겨서는 안 된다. 직렬 선행 순서와 주변 조건 미측정은 유지되는 한계다.

확인 단계의 병행 anchor를 개발 단계 직렬 온도에서 고를 수 있던 기존 host 조회를 같은 단계·같은 pair의 적격 직렬 세션 **정확히 하나**로 한정했다. 이는 결과에 유리한 기준을 고르는 변경이 아니라 기존 같은 단계 직렬 선행 계약을 gate에도 적용한 PC 결함 수정이다. 미실행 plan_v8은 보존하되 사용하지 않는다.

## 후보 예산과 미검증 범위

비교군·작업량·순서·입력·품질·화면/배터리/thermal/memory gate·2초 화면 조회 timeout·중단·재시도0·개발4→동결→확인4는 변경하지 않았다. 직렬1완료와 중단1은 새 표본에 넣지 않는다. 개발 자료로만 동결하고 확인 후 재조정하지 않는다.

| 항목 | COLLECT-04 | COLLECT-05 후보 |
|---|---:|---:|
| 고정 공식 관측 (baseline 120+work 480+cooling 180초) | 8×13 = **104분** | **104분**, 동일 |
| 공식 관측 전 조건부 준비 | 없음 | 최소 8×60초 = **8분**, 세션당 최대 360초 = **48분** |
| 세션 timeout 예약 합 | 8×25분 | 8×31분 |
| 설치+세션+동결 timeout 합산 예약 | 10+200+10 = **220분** 중 기존 문서의 작업별 예약 **206분40초** | 기존 작업별 예약 +48 = **254분40초**; 일반 예상시간 아님 |
| 전체 hard 상한 | **220분** | **268분** = 설치10+세션8×31+동결10; 회수·cleanup 포함 |
| 소비 상한 | 개발4+확인4, 진단6976, warmup64, 명시적 추론7040, runtime32, staging8/56 | **동일**; 전송/설치 각 최대1, 재시도·대체·추가0 |

위 `254분40초`는 기존 계약의 timeout 합산 예약 `206분40초`에 세션별 6분의 예약을 더한 수치이며 정상 소요시간 추정이 아니다. 실제 완주시간은 고정 관측104분과 최소 준비8분 외에 초기화·gate·입력 staging·회수·cleanup·동결·환경 대기가 더해져 미확정이다. hard 268분은 새 준비 최대48분만큼 기존220분에서 늘린 것이다. 첫 세션이 준비 gate를 통과할지, 배터리가 끝까지 유지될지 PC로 확인할 수 없다.

새 APK SHA-256 `c631095aed62115031adaf7346f10b4f87434713eacbe6992fcc7d338503350d`, 프로젝트 signer SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`. 새 계획 SHA-256 `3f794c9ac01066777e9e0d9553f8494bd00c5fc8b60dbdebd95f66a1cc35bfc2`. 기기 현재 설치본·환경·실제 병행 gate는 **실행 직전 확인 대상**이다. PC의 서명 일치는 설치 성공이나 병행 안정성 증거가 아니다. 새 계획은 `PREPARED_NOT_APPROVED`, 출력과 소비 registry 미생성이다.

PC 검증: `python -B -m unittest tools.test_d1_energy_collection` (26건), `:benchmark-runner:testModelProbeUnitTest --tests EnergyCollectionCoreTest`, 격리 APK 빌드·서명 검사, 아래 Check/dry-run 통과. Kotlin/host 변경의 실기기 동작은 검증되지 않았다. 자세한 명령·해시는 외부 `energy_collection_temperature_pc_v1/FINAL_REPORT.md`와 `energy_collection_plan_v9`의 manifest를 따른다.

```powershell
python -B C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_temperature_pc_v1/REPRODUCE.py
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_plan_v9/RUN_AFTER_APPROVAL.ps1' -Action Check
```

새 실행은 **이번 작업의 승인 범위가 아니다**. 승인 후에도 같은 A24 transport serial, 계획·APK·서명/현재 설치본, 비충전 배터리20% 이상·35°C 이하·thermal0·화면·memory, stage별 직렬/병행 적격성, 남은 시간·cleanup 예약을 모두 확인해야 한다. 조건 실패 또는 사전 준비 최대 대기 소진 시 부하를 시작하지 않고 원본 회수·cleanup 후 `stopped_no_resume`로 종료한다. 실행 명령은 새 승인 시에만 `RUN_AFTER_APPROVAL.ps1 -Action Run -Approved -Serial '<현재 A24 serial>'`이다.
