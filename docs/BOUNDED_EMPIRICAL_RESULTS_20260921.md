# Bounded empirical calibration 결과

**SIM-01_READY**. 적용 범위는 Galaxy A24, 현재 모델과 canonical 입력, thermal status 0, resident-only descriptive 비교다. 본 simulation과 formal experiment는 실행하지 않았다.

- 정확히 30세션·480호출을 완료했다. 실패·retry·대체·추가 세션은 0개다. Solo 네 cell별 5세션과 완전한 paired 5쌍을 확보했다. 11,155개 event, 출력 동등성 480건, memory admission 550건 및 cleanup 검증이 통과했다.
- 측정 전에 fsync/atomic replace manifest와 exclusive host lock을 구축했다. 실제 context 중단 복구는 필요하지 않았다. 복구 경로는 host mock 4건과 atomic unit test 13건으로 검증했다.
- Co-run−CPU serial의 긴급 P95 차이는 평균 −2,838.11ms(bootstrap CI −2,854.72..−2,822.59), makespan은 +2,178.00ms(CI 2,127.30..2,223.81), throughput은 −0.880 req/s였다. 긴급 응답과 전체 처리 효율의 상충관계다. 엄격한 warm deadline에서는 co-run이 더 좋지 않았다. 5쌍의 descriptive 결과로 보편적 우월성이나 인과효과를 주장하지 않는다.
- 이번 sampled peak PSS는 311,353KiB이고 thermal status는 0이었다. 기존 326,254KiB 관측도 보존했다. 어느 값도 절대 최대나 안전 headroom 보장이 아니다.
- Joint 30블록과 paired 5단위, session bootstrap 2,000회, LOSO, low/central/high/cold-stress, 공통 CRN 및 복수 deadline 시나리오를 생성했다. 이는 사용자 SLA, 모집단 cold P95 또는 요청별 90% 예측 보장이 아니다.
- Simulation input SHA-256: `4eeae6f6f8e9954d153b010767ba5a84307e5b8d0a971e7a478b0255413c0fc5`. 독립 output root에서 파생 파일 전체를 동일하게 재생성했다. 원본 validator, cross-session field mixing 거절, no-op 검증이 통과했다.
- 전체 Python 436건(434 PASS, 기존 skip 2)과 별도 recovery 4건이 통과했다. Compileall과 diff-check도 통과했다. Android/APK hash 불변을 확인했고 전체 빌드는 반복하지 않았다. 기존 원자료 2,213파일과 이전 보고서 hash를 보존했다.

전체 세션 목록, 분포, paired 결과, deadline, hash, 명령과 최종 Git 상태는 외부 보고서에 기록했다.

`C:\Users\LG\Documents\D1Check_Bounded_Empirical_Run\run_20260921_atomic_v1\FINAL_REPORT.md`

같은 폴더의 `execution_manifest.json`이 실행 상태의 기준이다. 결과 재현은 `analyze_completed.py`의 host-only generation/validation을 사용한다. 완료된 기기 세션은 재실행하지 않는다.

다음 행동은 동결 입력을 사용하는 별도 승인 simulation 계획이다. 미측정 2 GPU/4 runtime, dynamic reload, 다른 thermal 상태나 overlap을 생성하지 않는다. 기존 coverage 80.38% 실패와 consumed holdout을 새 성공 결과로 바꾸지 않았다.
