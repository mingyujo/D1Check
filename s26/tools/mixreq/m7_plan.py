"""M7 plan generator (2026-10-13) — deterministic bytes, no timestamps. m6_plan.py · mixreq_plan.py · m6_common.py are NOT modified (imported;
m7_common.extended() points the m6_common tables at the M7 rows while the plans are built).

  py -3 -X utf8 s26/tools/mixreq/m7_plan.py --out-root s26/results/m7_1013
      --cls-model local_models/efficientnet_lite0.tflite --det-model local_inputs/public/efficientdet_lite0.tflite
      --aot-model npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite
      --png local_inputs/canonical_v123/00575b9132bb3746.png --anchors local_inputs/reference_pc/anchors.json
      --cls-labels local_inputs/reference_pc/labels_without_background.txt --det-labels local_inputs/reference_pc/labels.txt

Writes four plan folders under --out-root (등록 M7 v2 · M7-apk index 자리):
  plan_m7p/    P 30: S26-M6-P index 12..41 = 등록 §2-3 (D1 12..17 · D2 18..23 · D3 24..29 · K1 30..35 · K2 36..41) + smoke (S26-M6-P-SMOKE
               index 12 = L-C · 100 requests · time_scale 1) + projection.json (L · B each one SHA across all rows = M6 values, else stop)
  plan_m7prep/ 준비 P 10: S26-M6-P index 42..51 (세트 n: L-C = 42 + 2(n−1) · L-N = 43 + 2(n−1)) · role = prep · same manifest columns as P
  plan_m7k/    K 15: S26-M6-K index 4..18 (세트 s 의 p 번째 = 4 + 3(s−1) + p · 조건 = 등록 §1-5 ABC / BCA / CAB / ACB / BAC) + smoke
               (S26-M6-K-SMOKE index 4 · time_scale 10). Manifest columns = M6 plan_m6k (condition · set · prep index live in plan.json).
  plan_m7s/    S 12: S26-MIXREQ-03 index 16..27 = 등록 §4-4 (C G N N G C | G C N N C G) · block A (C · G) / N (N) · 3,000 requests ·
               720 s (R4 (S) manifest form, registration = M7 v2, mixreq v3 kept as registration_mixreq_v3) + smoke (S26-MIXREQ-03-SMOKE
               index 16 · 24 requests · time_scale 10 · block A · CPU).
Session manifests keep split "confirmation" + analysis_split dev / confirm · cycle m7 · item · role · pair 0 (dev) / 1 (confirm).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m7_common as M7  # noqa: E402
import mixreq_common as C  # noqa: E402
import mixreq_plan as P  # noqa: E402
import policy_ref  # noqa: E402
import m6_common as M  # noqa: E402
import m6_plan as MP  # noqa: E402

PLAN_SCHEMA = "s26-m7-plan-v1"
REG_L = "ad29e8196e3f96a018d0f4483b9c14a2eab1150b6e670a4ccfb685d4364f39c6"   # 등록 §2-2 투영 SHA L
REG_B = "9fc5ef9f5afc2fba46ad9c5b26a4d2c65e0b2a1c87a09a07b175e5f21e954c0b"   # 등록 §2-2 투영 SHA B
CONSTANTS = dict(idle_min_s=M7.IDLE_MIN_S, stable_window_s=M7.STABLE_WINDOW_S, stable_slope_c_per_min=M7.STABLE_SLOPE_C_PER_MIN,
                 stable_recheck_s=M7.STABLE_RECHECK_S, stable_extra_max_s=M7.STABLE_EXTRA_MAX_S, prep_to_k_gap_s=M7.PREP_TO_K_GAP_S,
                 prep_to_k_gap_max_s=M7.PREP_TO_K_GAP_MAX_S, run_gap_min_s=M7.RUN_GAP_MIN_S, hal_pre_start_bc_s=M7.HAL_PRE_START_BC_S,
                 hal_pre_start_p_s=M7.HAL_PRE_START_P_S, hal_p_after_origin_s=M7.HAL_P_AFTER_ORIGIN_S, hal_s_after_window_s=M7.HAL_S_AFTER_WINDOW_S,
                 s_gap_min_s=M7.S_GAP_MIN_S, hal_target_period_s=M7.HAL_TARGET_PERIOD_S, safety_skin_c=M7.SAFETY_SKIN_C,
                 safety_thermal_status=M7.SAFETY_THERMAL_STATUS, charge_to_first_run_min_s=M7.CHARGE_TO_FIRST_RUN_MIN_S,
                 start_skin_band=[29.5, 31.5], band_wait_s=1200, gate=dict(skin_max=32, ap_max=32, bat_max=30), soc_band=[M.SOC_MIN, M.SOC_MAX])
REGS = dict(registration=M7.REGISTRATION, registration_v1=M7.REGISTRATION_V1, m6_registration=M7.M6_REGISTRATION)
NOTES_COMMON = ["split = confirmation (app: real session) · analysis_split = 등록 개발 dev / 확인 confirm · cycle = m7",
                "index 는 M6 · R4 가 쓴 자리 뒤 (P 12.. · K 4.. · S 16..) — 등록 v2 머리 단락 · session_id = uuid5(실험 ID/index) 그대로",
                "계산 · 판정 (J · 열 · 정책 비교) 없음 — 조민규 / Cowork"]


def common_plan(experiment_id: str, device: dict, block: str, **extra) -> dict:
    return dict(schema=PLAN_SCHEMA, experiment_id=experiment_id, protocol=C.PROTOCOL, cycle=M7.CYCLE, block=block, **REGS,
                inputs={k: {kk: vv for kk, vv in v.items() if kk != "host_path"} for k, v in device.items()},
                device_input_dir=C.DEVICE_INPUT_DIR, device_session_dir=C.DEVICE_SESSION_DIR, app_package=C.APP_PACKAGE, app_output_dir=C.APP_OUTPUT_DIR,
                sample_period_ms=C.SAMPLE_PERIOD_MS, stop_rules=C.STOP_RULES, start_check=C.START_CHECK, constants=CONSTANTS, **extra)


def projection_check(sessions: list[dict], tag: str) -> dict:
    out = {}
    for load, reg in (("L", REG_L), ("B", REG_B)):
        shas = {f"{s['index']:02d}": s["projection_sha256"] for s in sessions if s["load"] == load}
        values = set(shas.values()) | {M.projection_sha256(M.load_requests(M.session_id(M.P_ID, 0), load))}
        out[load] = dict(rows=shas, equal=len(values) == 1, sha256=sorted(values)[0] if len(values) == 1 else sorted(values), registered=reg,
                         matches_registered=values == {reg}, fields=list(M.PROJECTION_FIELDS), request_rows=M.REQUEST_COUNT)
        if values != {reg}:
            raise SystemExit(f"{tag}: projection SHA for load {load} = {sorted(values)} != registered {reg} — stop (등록 §2-2)")
    return out


def p_entry(index: int, device: dict, role: str, labels: dict) -> dict:
    load, letter = M.load_of(index), M.letter_of(index)
    m = MP.manifest(M.P_ID, "confirmation", index, M.policy_of(index), device, 1,
                    dict(m6_load=load, m6_letter=letter, cycle=M7.CYCLE, role=role, **labels))
    rel = f"manifests/{index:02d}_{load}-{letter}_{m['session_id']}.json"
    return MP.entry(m, rel, load=load, letter=letter, role=role, cycle=M7.CYCLE, projection_sha256=M.projection_sha256(m["requests"]), **labels)


def build_p(device: dict) -> dict:
    sessions = []
    for index in range(M7.P_FIRST, M7.PREP_FIRST):
        blk, pos = M7.p_block_of(index)
        sessions.append(p_entry(index, device, "main", dict(analysis_split=M7.p_analysis_split(index), item=2, m7_block=blk, order_pos=pos)))
    sm = MP.manifest(M.P_SMOKE_ID, "diagnostic", M7.P_SMOKE_INDEX, M.policy_of(M7.P_SMOKE_INDEX), device, 1,
                     dict(m6_load="L", m6_letter="C", cycle=M7.CYCLE, role="smoke", smoke=True))
    smoke = [MP.entry(sm, "smoke/P_smoke_L-C.json", name="P_smoke_L-C", load="L", letter="C", role="smoke", projection_sha256=M.projection_sha256(sm["requests"]))]
    projection = projection_check(sessions + smoke, "plan_m7p")
    per_policy = {p: sum(1 for s in sessions if s["policy"] == p) for p in policy_ref.POLICIES}
    assert per_policy == {policy_ref.POLICY_CPU: 10, policy_ref.POLICY_PAR: 10, policy_ref.POLICY_PAR_NPU: 10}, per_policy
    assert M7.p_positions_ok(M7.P_BLOCKS)
    blocks = {b: [M7.p_index(b, i) for i in range(6)] for b in M7.P_BLOCK_ORDER}
    plan = common_plan(M.P_ID, device, M.BLOCK, item=2, phases={M.BLOCK: C.phases_of(M.P_ID, M.BLOCK)}, request_count=M.REQUEST_COUNT,
                       order={b: list(M7.P_BLOCKS[b]) for b in M7.P_BLOCK_ORDER}, blocks=blocks, dev_blocks=list(M7.P_DEV_BLOCKS), confirm_blocks=list(M7.P_CONFIRM_BLOCKS),
                       dev=[i for b in M7.P_DEV_BLOCKS for i in blocks[b]], confirm=[i for b in M7.P_CONFIRM_BLOCKS for i in blocks[b]],
                       loads=dict(L="i = 0..99 · 35,000 + 400·i ms · 짝 = 분류 urgent 1,500 · 홀 = 탐지 normal 6,000",
                                  B="k, j = 0..9 · i = 10k + j · 35,000 + 4,000·k + 50·j ms · j 짝 = 분류 · 홀 = 탐지"),
                       projection=projection, v2_bound_s=M.V2_BOUND_S, soc_band=[M.SOC_MIN, M.SOC_MAX],
                       execution=dict(m7a_part1=blocks["D1"], m7a_part2=blocks["D2"], m7a_part3=blocks["D3"], m7b=blocks["K1"] + blocks["K2"],
                                      note="D1 = 1부 (K 세트 1 뒤) · D2 = 2부 (K 세트 2 앞) · D3 = 3부 (K 세트 3 뒤) · K1 · K2 = M7-B (조민규 동결 SHA 뒤)"),
                       execution_order=[i for b in M7.P_DEV_BLOCKS for i in blocks[b]], smoke_experiment_id=M.P_SMOKE_ID,
                       sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in sessions],
                       smoke=[{k: v for k, v in s.items() if k != "_manifest"} for s in smoke],
                       notes=NOTES_COMMON + ["block M = classification_CPU/GPU/NPU · detection_CPU/GPU 상주 (세 규칙 같음)",
                                             "연속 HAL: 세션 앱 시작 ≥ 60 s 전 → 원점 + 300 s (등록 §2-6) · 전력은 앱 cooling 60 s 까지 (power_coverage_after_last_available_s 실측)"])
    return dict(plan=plan, sessions=sessions, smoke=smoke, device=device)


def build_prep(device: dict) -> dict:
    sessions = []
    for index in range(M7.PREP_FIRST, M7.PREP_FIRST + 10):
        set_no, cond = M7.prep_set_of(index)
        sessions.append(p_entry(index, device, "prep", dict(analysis_split="dev" if set_no in M7.K_DEV_SETS else "confirm", item=1, m7_set=set_no,
                                                           m7_cond=cond, k_index=M7.k_index(set_no, M7.K_SETS[set_no].index(cond)))))
    projection = projection_check(sessions, "plan_m7prep")
    plan = common_plan(M.P_ID, device, M.BLOCK, item=1, role="prep", phases={M.BLOCK: C.phases_of(M.P_ID, M.BLOCK)}, request_count=M.REQUEST_COUNT,
                       prep=[dict(set=s, cond=c, index=M7.prep_index(s, c), load_rule=M7.PREP_LOAD_OF_COND[c]) for s in M7.K_SETS for c in ("B", "C")],
                       projection=projection, v2_bound_s=M.V2_BOUND_S, soc_band=[M.SOC_MIN, M.SOC_MAX], smoke_experiment_id=M.P_SMOKE_ID,
                       sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in sessions], smoke=[],
                       notes=NOTES_COMMON + ["role = prep: 조건 B = L-C · C = L-N (등록 §1-2) · 유효 V1 ~ V5 그대로 · 항목 2 반복에 세지 않음",
                                             "준비 run log 끝 → 90 s → K 앱 시작 (허용 90 ~ 100 · 실제값 기록 · 넘으면 gap_over)"])
    return dict(plan=plan, sessions=sessions, smoke=[], device=device)


def build_k(device: dict) -> dict:
    sessions = []
    for index in range(M7.K_FIRST, M7.K_FIRST + 15):
        set_no, pos, cond = M7.k_set_of(index)
        split = M7.k_analysis_split(index)
        label = f"K{set_no}{cond}"
        m = MP.manifest(M.K_ID, "confirmation", index, policy_ref.POLICY_CPU, device, 1,
                        dict(analysis_split=split, m6_run=label, cycle=M7.CYCLE, item=1, role="main", m7_set=set_no, m7_cond=cond, order_pos=pos))
        prep = M7.prep_index(set_no, cond) if cond in M7.PREP_LOAD_OF_COND else None
        sessions.append(MP.entry(m, f"manifests/{index:02d}_{label}_{m['session_id']}.json", analysis_split=split, letter=label, set=set_no, pos=pos,
                                 condition=cond, prep_index=prep, prep_load_rule=M7.PREP_LOAD_OF_COND.get(cond), role="main", cycle=M7.CYCLE))
    sm = MP.manifest(M.K_SMOKE_ID, "diagnostic", M7.K_SMOKE_INDEX, policy_ref.POLICY_CPU, device, M7.K_SMOKE_TIME_SCALE,
                     dict(m6_run="K_smoke_m7", cycle=M7.CYCLE, role="smoke", smoke=True))
    smoke = [MP.entry(sm, "smoke/K_smoke_m7.json", name="K_smoke_m7", letter="K_smoke_m7", role="smoke")]
    assert M7.latin_square_ok(M7.K_SETS)
    sets = {s: [dict(pos=p, condition=M7.k_cond(s, p), index=M7.k_index(s, p), prep_index=(M7.prep_index(s, M7.k_cond(s, p)) if M7.k_cond(s, p) != "A" else None))
                for p in range(3)] for s in M7.K_SETS}
    plan = common_plan(M.K_ID, device, M.BLOCK, item=1, phases={M.BLOCK: C.phases_of(M.K_ID, M.BLOCK)}, request_count=0, common_s=780, windows_s=M.K_WINDOWS_S,
                       sets=sets, set_order={s: M7.K_SETS[s] for s in M7.K_SETS}, dev_sets=list(M7.K_DEV_SETS), confirm_sets=list(M7.K_CONFIRM_SETS),
                       dev=[M7.k_index(s, p) for s in M7.K_DEV_SETS for p in range(3)], confirm=[M7.k_index(s, p) for s in M7.K_CONFIRM_SETS for p in range(3)],
                       conditions=dict(A="유휴 ≥ 1,200 s (직전 run log 끝 → K 앱 시작) · 시작 직전 120 s AP · SKIN 기울기 |·| ≤ 0.1 ℃/min → stable / stable_miss (최대 추가 1,200 s)",
                                       B="준비 P L-C (plan_m7prep) run log 끝 → 90 s → K 앱 시작 (허용 90 ~ 100 · gap_over 표시)",
                                       C="준비 P L-N (plan_m7prep) run log 끝 → 90 s → K 앱 시작"),
                       k_after_prep_gate="B · C 의 K 는 시작 띠 · 게이트 대기를 건너뛴다 (등록 §1-2 90 s 간격이 우선 · 앱 안 안전 정지 규칙 · skin_watch 그대로 · 준비 P 가 게이트 통과) — 시작 SKIN · AP · BAT · SOC 는 K 기록에 적는다",
                       soc_band=[M.SOC_MIN, M.SOC_MAX], execution_order=[M7.k_index(s, p) for s in M7.K_DEV_SETS for p in range(3)],
                       smoke_experiment_id=M.K_SMOKE_ID, smoke_time_scale=M7.K_SMOKE_TIME_SCALE,
                       sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in sessions],
                       smoke=[{k: v for k, v in s.items() if k != "_manifest"} for s in smoke],
                       notes=NOTES_COMMON + ["요청 0 · 공통창 780 s · 매니페스트 계약 열 = M6 plan_m6k (index · session_id · 표식만 다름)",
                                             "W = [0, 180) s · S = [600, 780) s (등록 §4-2 M6 · 계산은 Cowork)", "조건 · 세트 · 준비 index 는 이 plan.json 에만 (앱은 K 매니페스트를 M6 K 와 같게 본다)"])
    return dict(plan=plan, sessions=sessions, smoke=smoke, device=device)


def s_manifest(experiment_id: str, split: str, index: int, letter: str, device: dict, count: int, time_scale: int, labels: dict) -> dict:
    block = M7.S_BLOCK_OF_LETTER[letter]
    m = P.manifest(experiment_id, split, index, block, M7.LETTER_POLICY[letter], device, count)
    m["pair"] = 1 if labels.get("analysis_split") == "confirm" else 0     # app: pair 0..3 (mixreq pair_of would exceed 3 for index 16..27)
    m["time_scale"] = time_scale
    m["registration_mixreq_v3"] = m.pop("registration")                   # the -03 row's own registration (R4 v3) kept for traceability
    m.pop("registration_v2", None)
    m.pop("registration_v1", None)
    m["registration"] = {k: v for k, v in M7.REGISTRATION.items() if k != "time"}
    m.update(labels)
    return m


def build_s(device: dict) -> dict:
    sessions = []
    for index in range(M7.S_FIRST, M7.S_FIRST + 12):
        letter, label, split = M7.s_letter_of(index), M7.s_label(index), M7.s_analysis_split(index)
        m = s_manifest(M7.S_ID, "confirmation", index, letter, device, C.request_count_of(M7.S_ID), 1,
                       dict(analysis_split=split, cycle=M7.CYCLE, item=4, role="main", m7_s=label, m6_letter=letter, m7_label=f"{label}-{letter}"))
        sessions.append(MP.entry(m, f"manifests/{index:02d}_{label}-{letter}_{m['session_id']}.json", analysis_split=split, letter=letter, label=label,
                                 role="main", cycle=M7.CYCLE, s_block=m["block"]))
    sm = s_manifest(M7.S_SMOKE_ID, "diagnostic", M7.S_SMOKE_INDEX, "C", device, M7.S_SMOKE_REQUESTS, M7.S_SMOKE_TIME_SCALE,
                    dict(cycle=M7.CYCLE, role="smoke", smoke=True, m7_label="S_smoke_m7-C"))
    smoke = [MP.entry(sm, "smoke/S_smoke_m7.json", name="S_smoke_m7", letter="C", role="smoke", time_scale=M7.S_SMOKE_TIME_SCALE)]
    plan = common_plan(M7.S_ID, device, "A/N", item=4, phases={b: C.phases_of(M7.S_ID, b) for b in ("A", "N")}, request_count=C.request_count_of(M7.S_ID),
                       common_s=C.common_s_of(M7.S_ID), step_ms=C.STEP_MS, order=list(M7.S_ORDER), dev=list(M7.S_DEV), confirm=list(M7.S_CONFIRM),
                       block_of_letter=M7.S_BLOCK_OF_LETTER, mixreq_registrations=C.registration_fields(M7.S_ID), registration_version=C.registration_version(M7.S_ID),
                       soc_band=[M.SOC_MIN, M.SOC_MAX], execution_order=list(M7.S_DEV), smoke_experiment_id=M7.S_SMOKE_ID, smoke_time_scale=M7.S_SMOKE_TIME_SCALE,
                       sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in sessions],
                       smoke=[{k: v for k, v in s.items() if k != "_manifest"} for s in smoke],
                       notes=NOTES_COMMON + ["S26-MIXREQ-03 행 그대로 (3,000 요청 · 200 ms · 공통창 720 s · 기한 1.5 / 6 s) · 준비 = 블록 A (C · G) / N (N) — R4 (S) 와 같음 · 블록 M 아님",
                                             "유효 = R4 v3 (S) 규칙 (mixreq_validate 지속 규칙 · drain 750 s 한계) · 세션 사이 ≥ 600 s · 연속 HAL 창 끝 + 600 s",
                                             "C 는 식은 시간대 (새벽 · 아침) 에 두되 순서는 바꾸지 않는다 (시작 시각 조정)"])
    return dict(plan=plan, sessions=sessions, smoke=smoke, device=device)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-root", required=True, type=Path)
    for name in ("cls-model", "det-model", "aot-model", "png", "anchors", "cls-labels", "det-labels"):
        ap.add_argument("--" + name, required=True, type=Path)
    args = ap.parse_args()
    device = MP.device_inputs(args)
    with M7.extended():   # m6_plan.manifest → m6_common.requests → P_ORDER[index] for 12..51 · registration = M7 v2
        built = dict(plan_m7p=build_p(device), plan_m7prep=build_prep(device), plan_m7k=build_k(device), plan_m7s=build_s(device))
    for name, b in built.items():
        digest = MP.write_sessions(args.out_root / name, b)
        print(f"{name} {digest} sessions {len(b['sessions'])} smoke {len(b['smoke'])}")
        for s in b["sessions"] + b["smoke"]:
            extra = f" proj {s['projection_sha256']}" if "projection_sha256" in s else ""
            print(f"  {s['manifest']} {s['manifest_sha256']}{extra}")
        if "projection" in b["plan"]:
            pj = b["plan"]["projection"]
            print(f"  projection L {pj['L']['sha256']} ok={pj['L']['matches_registered']} · B {pj['B']['sha256']} ok={pj['B']['matches_registered']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
