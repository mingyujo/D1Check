# A24 실측 진행 현황

**마지막 갱신: 2026-10-16 02:39:03 KST**

- 원래 독립 확인: **26/40 정상 완료**, 시작 전 실패·거절 2회 보존. 현재 단계 `PRE_APP_COOLING`. 실패·미완료는 아래 원장과 각 묶음 상태를 함께 확인한다.
- 기존85회: 72회 소비(진행·거절 포함). 별도 실패 보완12: 0회 정상 완료 / 0회 APP 시도. 합산 회계 상한97이며 완료율과 예산 소비율은 다르다.
- 원확인, 관측후 개정혼합4, 과거실패 새ID 보완12는 서로 합산해 독립 성공 횟수를 늘리지 않는다.
- J 미판정 / AP는 HAL 보고값·표면온도 미검증 / experiment_ready=false. 미완료를 절감으로 해석하지 않는다.

## 최신 원자료 ZIP·CSV·버전/SHA

- [개정혼합4: 2정상·1시작거절·1미실행 시점의 원자료](../../results/a24_measurement_share_20261016/stable_reference_extra4_01/README.md)
- [C9 시작거절 원자료·실패 포함 전체 원장](../../results/a24_measurement_share_20261016/confirmation_visit_09/README.md)
- [이전 C8 원자료·그림·원장](../../results/a24_measurement_share_20261015/confirmation_visit_08/README.md)
- [C10_R02CONFIRM03_C252 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/C10_R02CONFIRM03_C252/README.md)
- [C10_R02CONFIRM04_C252 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/C10_R02CONFIRM04_C252/README.md)
- [C10_R02CONFIRM04_L64 원자료 ZIP·CSV·소스 SHA](../../../docs/results/a24_measurement_share_20261016/automatic_checkpoints/C10_R02CONFIRM04_L64/README.md)

## 계획·재개·해석

- [실측 원장과 중지·재개 방법](MEASUREMENT_RUNBOOK.md)
- [실패 보완12의 고정 범위·새 ID·예산·검증](failed_supplement12_20261016/README.md)
- [기계 판독용 현재 상태](LIVE_PROGRESS.json)

종료한 비교 묶음은 닫힘 증거와 파일 SHA를 확인해 공개한다. 실행 중 원물은 복사하지 않는다. 외부 확인은 이 파일의 마지막 갱신 시각과 원격 커밋 시각을 함께 본다. 네트워크·인증·충돌이 발생하면 이를 우회하거나 다른 작업을 수정하지 않고 공개 업로드를 멈춘다.
