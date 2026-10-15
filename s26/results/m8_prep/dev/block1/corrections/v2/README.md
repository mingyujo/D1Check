# M8 블록 1 정정 묶음 (조민규 10/15 19:3x 답 정정 6 · 10:0x 답 정정 8 중 #3 #5 #7) — 블록 1 결과 변경 0 · 재측정 0 · 집계 source `fe14bd886` · 2026-10-15T22:26:54

## 횟수 · 소비 (①)
- 계획 자리 19 (19군 × 1) · 사전 게이트 시도 (prestart ledger 거절) **16** (보고 14 = 잘못된 Tref 28.7 의 B1-03 2건 제외) · 판정 불가 폴 별개 열 · **앱 START 21 = 완료 20 + 회수실패 1 (B1-06 EDD a1 · adb 끊김 stall)** · 폴더 충돌 rc 5 = 앱 START 0 (별도 행).
- 19군 대표 결과 = 3,048 요청 · 추가 시도 포함 완료 3,300 (B1-01 CPU252 a2 포함). "실패 0 / 19회만 실측" 이라 쓰지 않음.
- **대표 선택 규칙**: 군마다 **첫 유효 시도** (검사기 A0~A10 · coverage 고침 뒤 재검증 포함) = 대표. B1-01: a1 (수정 전 무효 → 수정 후 유효) = 대표 · a2 (유효) = 추가 시도 보존 (대표 아님). B1-06: a1 stall (앱 START · 회수실패 · device raw 회수) · a2 = 대표.
- B1-06 EDD a1 device raw: `EDD_a1_device_raw/` (폰 `/data/local/tmp/mixreq/sessions/<sid>/a1` 2 파일 + 앱 `files/mixreq/<sid>/a1` 265 파일 · 읽기 전용 pull · 재실행 0).

## 게이트 소비 (② `b1_gate_ledger.csv`)
- Tref 28.7 (충전 열 · 유휴 조건 아님) → 27.2 재산출 · 강제 START 5 (B1-04 · 05 즉시 / B1-10 · 11 · 18 누적 1,800 s) · B1-03 추가 게이트 · B1-11 재시작 뒤 거절 누적 · B1-06 a1→a2 휴식 ≈ 501 s (< 600) — 각각 별도 행.
- 통과 못 한 자리 · 강제 START 는 정상 PASS 로 바꾸지 않음 → `session_table_m8_v2.csv` 의 `AP_band_ok` · `slope_ok` · `gate_passed` · `forced` 네 열.
- 다음 드라이버 (CONFIRM 판 · 블록 2 는 3344119f4 고정): 재시작 시 잔여 휴식 · 거절 한도 복원 · gate_attempt_id 별 HAL 경로/SHA · stable_miss = TREF_UNDECIDABLE.

## 버전 (③ `registration_versions.csv` · `registration/` · `instructions_index.md`)
- 블록 1 = 등록 v2 계약 + v3 운영 (게이트 v2 + 영훈 강제 START) · 블록 2 = v2 계약 + v4/v5 게이트 (16:54 부터 · 드라이버 3344119f4) · v4 · v5 블록 1 소급 0.
- `source_commit` 세 열: 측정 APK source = `90db991c6` (P0 ZIP 그대로) · 실행 당시 host source (드라이버 시작 시각별) · 이번 집계 source = `fe14bd886`.

## 해석 문구 (⑤ · readout · 보고에 그대로)
- M128 (블록 1 · 각 1회): 직렬 BASE 긴급 13/96 · 일반 11/32 기한 내 · EDD 긴급 39/96 · 일반 7/32 · 병행 PAIR_G/PAIR_N 96/96 · 32/32 → "EDD 는 긴급 개선 대신 일반 손해 · WAIT 는 이번 조건에서 손해" 처럼 **장점과 손해를 같이** 적는다 · 우위/절감 판정 아님.
- WAIT 실제 합 3228.921486 / 2420.040116 / 12022.011016 ms (200x16 / 200x12 / 1000x12) 그대로 보존 · 명목 12 s ≠ 실제 cap ("명목 WAIT 실측").
- **L64 PAIR = 실제 겹침 0 → 병행 효과 대조로 세지 않음** (새 부하는 새 등록 · 현재 입력을 결과에 맞춰 바꾸지 않음).
- C252 RECENT/IDLE 252/252 → "납기 지표만으로 열 이력 효과 없음" 이라 쓰지 않음 · AP 는 시작 조건/이력 차이 → 기술 통계만 · 에너지/열 최종 판정 없음.
- 단일 PNG · 새 session ID/seed = 독립 세션 반복 · 새 이미지 일반화 아님.

## Perfetto r2 (⑥ `perfetto_r2_evidence.json`)
- 원 ON trace 0 보존 (실제 bank = L64) · r2 17134 B · SHA `bbd5f751e12face39ad8dd07c502376fffb2f62f3e517097594da23b6b6f523a` · 패킷 354 · battery 카운터 패킷 338 · 범위 303.985585781 s · parse = protobuf wire 스캔 (trace_processor 미설치) → "지원 확인" 까지 · "오버헤드 검증 완료" 아님 · 보충 1 시도 소비 원장.

## delegate 증거 (`delegate_evidence_m8.csv` · 1015b #7)
- logcat `Replacing N out of M node(s) with delegate (X)` 줄을 runner PID 로 고르고 runtime_return 순서로 runtime_key · model SHA 와 연결 (TID 직접 연결 불가 · 순서 기반 표시) · 등록/로드 줄은 증거 아님 (CME 규칙) · NPU = 컴파일 모델 SHA · 품질 조건 표기 · 탐지 GPU 본요청 = warmup/probe 와 구분.

계산 · 판정 0 (유효 수 · 요청 수 세기만).
