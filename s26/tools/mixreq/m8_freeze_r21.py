"""M8 CONFIRM 동결 R21 (2026-10-16 · 조민규 1016 정정안 SHA 1dc9f5b5… · 프롬프트 M8-B R21 2단계) — 부모 = 동결 v1 (deedfc1b… · 바이트 보존 · 변경 0). 결정적 바이트 (made 시각은 인자).

  py -3 -X utf8 s26/tools/mixreq/m8_freeze_r21.py --prep s26/results/m8_prep --applied "2026-10-16 05:12:47 +0900" --out s26/results/m8_prep/CONFIRM_FREEZE_M8_R21_v1.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import m8_plan_r21 as PR  # noqa: E402
import m8_readout_r21 as R  # noqa: E402


def build(prep: Path, applied: str) -> dict:
    v1b = (prep / PR.FREEZE_V1).read_bytes()
    assert C.sha256_bytes(v1b) == PR.FREEZE_V1_SHA
    v1 = json.loads(v1b)
    man_b = (prep / "plan_m8_r21" / "r21_manifest.json").read_bytes()
    man = json.loads(man_b)
    dev_b = (prep / "r21" / "energy_eligibility_dev.json").read_bytes()
    dev = json.loads(dev_b)
    slots = [dict(block=f"R{b['block_no']}", pos=s["order_pos"], label=s["label"], arm=s["arm"], experiment_id=s["experiment_id"], index=s["index"], session_id=s["session_id"],
                  origin_label=s["origin_slot"]["label"], manifest_sha256=s["manifest_sha256"]) for b in man["stages"]["confirm_blocks"] for s in b["sessions"]]
    v1_pairs = v1["comparison_pairs"]["rules"]
    return dict(
        schema="s26-m8-confirm-freeze-r21-v1",
        revision_id=PR.REVISION_ID,
        header=R.HEADER,
        parent=dict(file=PR.FREEZE_V1, sha256=PR.FREEZE_V1_SHA, note="동결 v1 무변경 (바이트 보존) · R21 은 v1 을 부모로 참조 · v1 의 정의 (지표 · 분모 · 제외 · gate_v5 · coverage) 는 아래에서 바꾼 것 외 그대로"),
        correction=dict(file="조민규_답_1016_21슬롯_목적정정.txt", sha256=PR.CORRECTION_SHA, applied=applied,
                        replaces_prompt=dict(file="프롬프트_M8B_CONFIRM_1016.md", sha256="c9554f9bc5f8657e2c0ceffeac9d7434706dae6dcaf6863967c634a2d3ef64eb", status="대체됨 (파일 보존 · 수정 0)"),
                        prompt=dict(file="프롬프트_M8B_CONFIRM_R21_1016.md", sha256="e43cf9178ebf7d44e9072e6ebcc0c2c978cc795513dcdbdf47da7adb0d2f1e8f")),
        # 1. 범위
        scope=dict(branch="A (CONFIRM START 0 · 0단계 원장 05:12:47)", blocks=3, groups=7, slots=21, new_sessions_added=0,
                   keep_groups=list(PR.KEEP), excluded_groups=list(PR.EXCLUDED), excluded_status="미완료 — R21 축소로 CONFIRM 안 함 (DEV 2/2 만) · 소비 0",
                   slot_table=slots, r21_manifest=dict(file="plan_m8_r21/r21_manifest.json", sha256=C.sha256_bytes(man_b)), plan_sha256=man["plan_sha256"],
                   index_rule_note=PR.INDEX_RULE_NOTE,
                   unchanged="입력 · 모델 · 기한 (긴급 800 / 일반 2,000 ms) · 응답 경계 (priority) · AVAILABLE · 비선점 · 최대 2건 · WAIT 설정 · v5 게이트 · 계측 창 · 안전 · SOC (≥ 20 · 상한 없음) · 거절 한도 · 동결 v1 exclusion_rules",
                   exclusion_rules=v1["exclusion_rules"], gate_v5=v1["settings"]["gate_v5"], no_relaxation="시간 · 충전 · gate 대기를 줄이려고 기준 완화 0"),
        # 2. 비교쌍
        comparison_pairs=dict(pairs=[dict(ref=a, arm=b, d="arm − ref") for a, b in R.PAIRS], unit="같은 R블록 안 1:1 · 한쪽 무효/빈 자리 = 그 블록 쌍 제외 · n 적음 · 대체 0 · 사후 선택 0",
                              v1_pair_rules=v1_pairs,
                              v1_pairs_not_run=["M128 BASE↔PAIR_N", "M128 WAIT200x16↔WAIT200x12", "M128 WAIT200x16↔WAIT1000x12", "SMOOTH128 BASE↔ORDER", "SMOOTH128_ORDER↔M128_ORDER (도착 모양)", "L64 BASE↔PAIR_G",
                               "RECENT CPU60↔IDLE60 (CPU/GPU/NPU)"], v1_pairs_not_run_status="R21 미실행"),
        # 3. 주결과 정의
        primary=dict(
            J0_180=dict(definition="∫ W dt · W = −current_raw(µA) × voltage(mV) / 10⁹ · 앱 power_sample · common 0 ~ 180 s · 사다리꼴 · 경계 = 양측 실제 표본 선형 (gap ≤ 2.5 s) · 창 안 gap > 2.5 s → null (보간 0)",
                        condition="에너지 적격 (4) 일 때만 값", label=R.ENERGY_LABEL),
            AP35_180_mean=dict(definition="HAL AP (온도 센서 · 표면온도 아님 · SKIN 과 구분) 35 ~ 180 s 사다리꼴 / 145 s · 경계 = 양측 표본 선형 (gap ≤ 5 s) · 안 되면 null"),
            AP35_180_peak=dict(definition="[35, 180] 안 실제 HAL 표본 최대 (보간값 아님) · 창 coverage 실패면 null"),
            AP180=dict(definition="180 s 시점 양측 HAL 표본 선형 (gap ≤ 5 s) · 없으면 null"),
            AP180_minus_AP0=dict(definition="AP180 − AP0 (각 시점 양측 표본 선형 · gap ≤ 5 s) · R21 주결과 잔열", v1_column="AP180_minus_AP35_v1 = v1 정의 'AP(180) − AP(35)' 보존 (열 이름 분리)"),
            time_zero="common_boundary.start_ns (기기 CLOCK_BOOTTIME) · 앱 progress mono_ns 와 HAL device_uptime_s 같은 시계 (정정 3판)",
            same_table=["긴급 / 일반 / 전체 완료 수", "정시율 (deadline_met / planned)", "svc70/80/90/95/100 (분모 planned)", "응답 P95 (긴급 output_ready · 일반 readback 성공)",
                        "납기 손해 (late 수 · 비율 · 넘긴 ms 합 = Σ(response − deadline) · 응답 있음만)", "failed · undispatched · unfinished", "미완료 세션 (invalid_twice · 빈 자리)"],
            secondary=["J0_120 · J35_180 (같은 규칙)", "실제 병행 dose s (execution_start ~ worker_release ≥ 2 건 겹침)", "WAIT 명목 / planned / 실제 dose / 초과량 / cut",
                       "입장 지연 (queue_entry − actual_arrival) · 배정 지연 (dispatch − queue_entry) 분포 (중앙값 · p95 · 최대)"]),
        # 4. 에너지 적격
        energy_eligibility=dict(
            hypothesis=R.UNIT_HYPOTHESIS, a24_import=0,
            rule=dict(discharge_neg_min=R.DISCHARGE_NEG_MIN, load_window_s=list(R.LOAD_WINDOW), voltage_range_mv=list(R.VOLTAGE_RANGE_MV), r_median_range=list(R.R_RANGE),
                      r_interval="앱 유효 표본 중 charge_counter 가 바뀐 첫 표본 ~ 마지막 바뀐 표본 (계단 경계 사이) · Q_int = ∫(−I) dt / 3600 µAh · ΔQ_cc = 감소 µAh · gap ≤ 2.5 s",
                      verdict_ok="단위 가설 적격", verdict_ng="미확정 — raw 보존 · 에너지 미판정 (×1000 등 임의 보정 0)",
                      per_session_confirm="DEV 적격 & 세션 r ∈ [0.8, 1.25] & plugged 0 & J 창 coverage 통과일 때만 J · 아니면 null + 사유 · AP · 응답은 따로"),
            dev_basis=dict(file="r21/energy_eligibility_dev.json", sha256=C.sha256_bytes(dev_b), scope=dev["scope"], verdict=dev["verdict"]["verdict"],
                           checks=dev["verdict"]["checks"], code="m8_readout_r21.py dev-energy (sha256 " + C.sha256_bytes((HERE / "m8_readout_r21.py").read_bytes()) + " at freeze)",
                           note="DEV 로 규칙 봉인 · 계산은 이번이 처음 · CONFIRM 자료 미열람 (CONFIRM START 0)"),
            fixed_text=R.ENERGY_NOTE),
        # 5. 창 · 경계 · 결측
        windows=dict(coverage_v1=v1["settings"]["coverage"], added="AP0 점 (HAL 양측 · gap ≤ 5 s)", pre_s=60, post_s=210,
                     provenance_columns=["common_boundary.start_ns", "계획 offset (첫 35 s) / scheduled binding (scheduled_arrival_ns = start_ns + offset_ns)",
                                         "앱 power 원파일 (device/progress.jsonl) · SHA · 시계 (CLOCK_BOOTTIME) · 첫/끝 표본 시각", "연속 HAL 원파일 · SHA · 시계 (device_uptime_s · host_ms) · 읽기 시작/끝",
                                         "센서 갱신 시각 미제공 (앱 · HAL 둘 다)"],
                     forbidden="이웃 세션 이어붙임 · 결측 보간 · tail 외삽 0"),
        # 6. 추정 · 다중 비교
        estimation=dict(unit="R블록 (n ≤ 3)", report="d_b 3개 전부 · 평균 · 중앙값 · 최소 · 최대 · 부호 (+/−/0 · n) · t (df = n − 1) 95 % 구간 = 기술용 · 양측 p",
                        multiple="Holm (FWER 0.05) · 지표마다 7쌍 묶음 · 보정 전 p 병기 · '유의' 대신 'Holm 보정 p < 0.05 (k/n)'",
                        header="3블록은 통계적 최소나 유의성 보장이 아니다 · 요청 128건을 독립 반복으로 세지 않는다"),
        # 7. 초기 상태
        initial_state=dict(columns=["gate 결과 · AP_band/slope/passed/forced", "Tref_block (키 · 값)", "시작 AP · SKIN · BAT", "120 s 기울기 (v5 판정 창)", "resident (START 직전 앱 프로세스)",
                                    "직전 세션 (label · 끝 시각)", "직전 휴식 s", "SOC 시작/끝", "충전 여부 · 블록 안 충전", "시간대 (host 시각 · 시)",
                                    "사람 개입 · 강제 gate (자동 1,800 s) · 자동 WAIT 횟수 (각각 별도 열)", "WAIT 명목 / 실제 dose / 초과량"],
                           rule="기록만 · 군별 보정 · 재정렬 · 대체 0 · 남은 초기 편차는 표에 그대로"),
        # 8. 주장 경계
        claims_boundary=dict(not_claimed=["RECENT 열 이력 메커니즘", "CPU/NPU 전체 경로", "NPU 병행 (PAIR_N)", "최적 WAIT", "resident 재생성"], status="미완료",
                             partner="조민규 쪽 REFINE26/RISK 조건부 예측은 이쪽 판정 아님 · 사전예측 없던 세션을 '사전예측 검증' 이라 부르지 않음",
                             model_predictions=v1["model_predictions"], tolerances=v1["tolerances"], atc_ppo_handoff=v1["atc_ppo_handoff"],
                             missing_from_partner="model_predictions · tolerances · atc_ppo_handoff 그대로 (채우지 않음)"),
        operation=dict(tref="블록마다 새 키 (드라이버 시작) · 유휴 ≥ 1,200 s 뒤 첫 안정 60 s AP 창 · 블록 안 재산출 0 · TREF_UNDECIDABLE 대체값 0",
                       driver="CONFIRM 판 m8_driver --stage confirm (3단계 커밋 · v5 상수 고정 · 21 슬롯 밖 거절 · 재시작 복원 · gate_attempt_id HAL · Perfetto OFF)",
                       stop_exceptions=["잠금", "adb 3회 + mdns + IPv6 실패 → 새 주소", "케이블 (SOC < 20)", "안전 SKIN ≥ 43 · thermal_status ≥ 3"],
                       human_force_start=0, auto_force_after_cumulative_s=1800),
        status=dict(confirm_started=False, note="이 파일 커밋 · push 뒤 3단계 (드라이버 · 분석 계약) → 첫 START"),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prep", type=Path, required=True)
    ap.add_argument("--applied", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.prep, args.applied)
    b = C.canonical_json(doc)
    args.out.write_bytes(b)
    print(f"{args.out.name} {C.sha256_bytes(b)} {len(b)} B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
