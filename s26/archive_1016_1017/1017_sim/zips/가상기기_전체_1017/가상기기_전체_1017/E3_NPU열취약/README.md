# 가상 기기 (NPU 쏠림 해소) × 우리 규칙 — 재현 묶음 (영훈 · 2026-10-17)
엔진 = 조민규 `codex/s26-simulator-handoff-20261016` s26_simulator (물리·계수 파일 무수정). 변경은 code/*.diff:
- vlegal(): 가상 기기 설정 `globalThis.__VDEV = {clsPair, maxOwners}` — 기본값이면 원래 병행 규칙과 같음 (결과 동일 확인).
- 비교군 `FIFO_BACKFILL_ANY_V1` · `EDF_BACKFILL_ANY_V1` (빈 가속기: NPU 우선, 안 되면 GPU) 추가.
- run5.cjs: job 의 `v.npuAP` 로 `AP:classification_NPU` 계수를 실행 때 바꿈 (파일 그대로).
확인 판정 = prereg/PREREG_VDEV_NPUTHERMAL_1017.md, 원자료 = results/vdev_npu_thermal_confirm_864.jsonl, 집계 = `python3 code/vcanal.py` (경로 수정 필요).
