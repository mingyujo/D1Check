결과 커밋 `e7b1652d72ab55f80cd1545241a8e42afadcea63` 외부 게시 확인: 익명26파일·20,044,587B·13 ZIP+새 ON 원본 ZIP 바이트 일치 PASS. [확인 영수증](../../results/a24_followon_measurements_20261016/PUBLICATION_VERIFIED.json).

# 2026-10-16 09:33 KST — 후속 실측 종료

실패 보완5/5 정상 회수, 480/480 MAIN·출력 오류0·AP 관측창5건 적격. 원 L64 1건은 기존27.1℃ 사전 조건 미충족으로 APP0/미실행 보존이다. 계약상109/110 소비, 기존 실패를 성공으로 바꾸지 않았다. 활성 측정 worker/owner는 없다.

[후속 보고서·오프라인 화면](../../results/a24_followon_measurements_20261016/README.md) · [원자료13 ZIP와 새 ON trace](../../results/a24_measurement_share_20261016/followon_resumed_01/README.md) · [검증](../../results/a24_followon_measurements_20261016/DELIVERY_CHECK.json)

아래는 이전 시점의 진행 기록이다.

<!-- FOLLOWON_HOST_CURRENT -->
현재 후속 현황 2026-10-16 09:30:00 KST: 원 L64 재개 APP 0·정상 0; 실패 보완5 APP 5·MAIN 시작 5·정상 5/5. 완료 여부는 [기계 현황](LIVE_PROGRESS.json)의 `resumed_followon`을 따른다. 원 실패·미실행 분모를 보존한다.
<!-- FOLLOWON_HOST_END -->

# 2026-10-16 후속 재개 중

원 미실행 L64 병행 1건을 기존 계약으로 재개했고, 실패 5건은 새 ID·각1회 진단 반복으로 등록했다. 현재 완료 여부는 아래 JSON과 새 원장으로 확인한다. 이전 64등록·58정상 결과는 재개 전 스냅샷이다.

[실행 계약](failed5_followon_20261016/README.md) · [기계 현황](LIVE_PROGRESS.json)

# A24 실측 진행 현황

**마지막 갱신: 2026-10-16 06:56:40 KST**

**현재 전체 상태: 06:43 KST 실측·회수 종료 / PC 분석·공개 재현 검증 완료**

[최종 한국어 보고서·오프라인 화면](../../results/a24_final_measurements_20261016/README.md) · [전체 원자료23 ZIP](../../results/a24_final_measurements_20261016/RAW_DATA_INDEX.md) · [실패 포함 최종 집계](../../results/a24_final_measurements_20261016/FINAL_COUNTS.json)

**외부 GitHub 게시·직접 다운로드 확인 완료:** 자료 커밋`c7b71df`/실제 원격 HEAD 일치, 인증 헤더 없이37파일·원자료23 ZIP·원본 trace ZIP의 원바이트 일치. [외부 확인 영수증](../../results/a24_final_measurements_20261016/PUBLICATION_VERIFIED.json).

**최종 보고 범위:64등록·58정상·MAIN7,912/8,456·출력오류0. 실패5·미실행1은 보존했으며 원독립40은37정상이다.** 새 공통 기준6은 전량 정상이다. 공개 ZIP의 이벤트·응답·AP·출력 재계산과 PC26검사가 통과했다. 최고AP/에너지 공동 개선·센서 교정·모형 독립 정확도PASS는 아니다. 현재 추가 기기/학습 큐는 없다.


- 원래 독립 확인: **37/40 정상 완료**, 시작 전 실패·거절 2회 보존. 현재 단계 `STOPPED`. 실패·미완료는 아래 원장과 각 묶음 상태를 함께 확인한다.
- 기존85회: 84회 소비(진행·거절 포함). 별도 실패 보완12: 11회 정상 완료 / 12회 APP 시도. 이어진 방문은 같은 전역 APP 원장으로 중복 계수하지 않는다. 완료율과 예산 소비율은 다르다.
- 시작온도 대응의 별도 같은 비교군6: 6회 정상 / 6회 APP. 합산 104회 소비 / 제한적 회계 상한105회이며, 추가6은 사용자 자율처리 지시를 구체화한 범위다.
- 계측 경로 수정의 별도 OFF/ON2: 2회 정상 / 2회 APP. 기존 실패를 지우지 않고 같은 입력·공유 시작 기준으로 검증한다.
- 원확인, 관측후 개정혼합4, 과거실패 새ID 보완12는 서로 합산해 독립 성공 횟수를 늘리지 않는다.
- J 미판정 / AP는 HAL 보고값·표면온도 미검증 / experiment_ready=false. 미완료를 절감으로 해석하지 않는다.

## 최신 원자료 ZIP·CSV·버전/SHA

- [개정혼합4: 2정상·1시작거절·1미실행 시점의 원자료](../../results/a24_measurement_share_20261016/stable_reference_extra4_01/README.md)
- [C9 시작거절 원자료·실패 포함 전체 원장](../../results/a24_measurement_share_20261016/confirmation_visit_09/README.md)
- [이전 C8 원자료·그림·원장](../../results/a24_measurement_share_20261015/confirmation_visit_08/README.md)
- [C10_R02CONFIRM03_C252 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/C10_R02CONFIRM03_C252/README.md)
- [C10_R02CONFIRM04_C252 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/C10_R02CONFIRM04_C252/README.md)
- [C10_R02CONFIRM04_L64 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/C10_R02CONFIRM04_L64/README.md)
- [C11_R02CONFIRM04_M128 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/C11_R02CONFIRM04_M128/README.md)
- [C11_R02CONFIRM05_C252 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/C11_R02CONFIRM05_C252/README.md)
- [C11_R02CONFIRM05_L64 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/C11_R02CONFIRM05_L64/README.md)
- [C11_R02CONFIRM05_M128 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/C11_R02CONFIRM05_M128/README.md)
- [REBASE6_NEW_L64_L64 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/REBASE6_NEW_L64_L64/README.md)
- [REBASE6_NEW_M128_M128 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/REBASE6_NEW_M128_M128/README.md)
- [TRACE2_TRACE_REPAIR_I_C32 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/TRACE2_TRACE_REPAIR_I_C32/README.md)
- [SUP12_C1_F_CPU_C252 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/SUP12_C1_F_CPU_C252/README.md)
- [SUP12_C1_DEV_CPU_C252 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/SUP12_C1_DEV_CPU_C252/README.md)
- [SUP12_C1_OLD_CONFIRM_PAIR_L64 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/SUP12_C1_OLD_CONFIRM_PAIR_L64/README.md)
- [SUP12_C1_OLD_CONFIRM_STOP_M128 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/SUP12_C1_OLD_CONFIRM_STOP_M128/README.md)
- [SUP12_C1_W1_CPU_C252 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/SUP12_C1_W1_CPU_C252/README.md)
- [SUP12_C1_W3_GPU_C252 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/SUP12_C1_W3_GPU_C252/README.md)
- [SUP12_C1_C9_ORDER_M128 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/SUP12_C1_C9_ORDER_M128/README.md)
- [SUP12_C1_R2_PAIR_M128 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/SUP12_C1_R2_PAIR_M128/README.md)
- [EXTRA4_ORDER_REBASE_M128_01_M128 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/EXTRA4_ORDER_REBASE_M128_01_M128/README.md)
- [SUP12_I_UNRESIDENT_IDLE 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/SUP12_I_UNRESIDENT_IDLE/README.md)
- [SUP12_I_RESIDENT_IDLE 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/SUP12_I_RESIDENT_IDLE/README.md)
- [SUP12_TRACE_I_C32 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/SUP12_TRACE_I_C32/README.md)

## 계획·재개·해석

- [실측 원장과 중지·재개 방법](MEASUREMENT_RUNBOOK.md)
- [실패 보완12의 고정 범위·새 ID·예산·검증](failed_supplement12_20261016/README.md)
- [시작온도 대응의 같은 비교군6: 별도 개발 반복](matched_rebaseline6_20261016/README.md)
- [계측 오류 보존·미실행8 계속](supplement8_after_trace_error_20261016/README.md)
- [공식 설정 경로의 새 OFF/ON2](trace_path_repair2_20261016/README.md)
- [기계 판독용 현재 상태](LIVE_PROGRESS.json)

종료한 비교 묶음은 닫힘 증거와 파일 SHA를 확인해 공개한다. 실행 중 원물은 복사하지 않는다. 외부 확인은 이 파일의 마지막 갱신 시각과 원격 커밋 시각을 함께 본다. 네트워크·인증·충돌이 발생하면 이를 우회하거나 다른 작업을 수정하지 않고 공개 업로드를 멈춘다.
