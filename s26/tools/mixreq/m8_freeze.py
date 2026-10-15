"""M8 CONFIRM 전 동결 파일 (등록 v2 §5 · 프롬프트 M8-DEV 4단계 · 2026-10-15) — DEV 2블록 결과 (driver events · validated) 를 읽어 후보 · 설정 SHA · 지표 정의 · 비교 쌍 규칙 · 분모 · 제외 규칙 ·
DEV 자료 SHA (B1 · B2 묶음) · CONFIRM 계획 (5블록 95 · seed 20261022 · 순서 미리 계산) 을 JSON 으로 쓴다. **계산 · 판정 0** (유효 수 세기만). 조민규 쪽에 없는 항목 (동결 예측 모델 · 정책별 수치 예측 ·
ATC/PPO 인계물 · 분석 기준 · 허용치) 은 "status": "missing_from_partner" 로 두고 채우지 않는다 (01:5x #8).

  py -3 -X utf8 s26/tools/mixreq/m8_freeze.py --out <json> [--results results] [--bundle <zip> ...] [--copy <path>]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m8_common as M8  # noqa: E402
import mixreq_common as C  # noqa: E402
import m8_plan as PL  # noqa: E402

REPO = M8.REPO
PLAN_ROOT = REPO / "s26" / "results" / "m8_prep"
MISSING = dict(status="missing_from_partner", note="조민규 01:5x #8: 새 M8 계약에 대응하는 동결 예측 모델 · 정책별 수치 예측 · 최종 ATC/PPO 인계물 없음 → 값 채우지 않음 · '미완료 — 인계물 없음' · 사후 비교를 '예측 검증' 이라 부르지 않음")


def sha(p: Path) -> str | None:
    return C.sha256_file(p) if p.is_file() else None


def dev_runs(results: Path) -> list[dict]:
    p = results / "S26_M8_driver_events.jsonl"
    out = []
    for l in p.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        if r.get("what") == "run_end" and r.get("run_kind") == "dev":
            out.append(r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, default=REPO / "results")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bundle", type=Path, action="append", default=[])
    ap.add_argument("--copy", type=Path, action="append", default=[])
    ap.add_argument("--source-commit", default="")
    args = ap.parse_args()
    M8.activate()
    blocks = C.read_json(PLAN_ROOT / "plan_m8" / "blocks.json")
    runs = dev_runs(args.results)
    tref = C.read_json(args.results / "S26_M8_tref.json") if (args.results / "S26_M8_tref.json").is_file() else {}
    # ---- 후보 19군: DEV 블록 1 · 2 세션의 결과 (rc · validated · prestart_reject)
    groups = []
    for gi, g in enumerate(blocks["groups_per_block"]):
        eid, arm_name = g["experiment_id"], g["arm"]
        a = next(x for x in M8.arms(eid) if x["name"] == arm_name)
        sessions = []
        for blk in blocks["stages"]["dev_blocks"]:
            s = next(x for x in blk["sessions"] if x["group_index"] == gi)
            evs = [r for r in runs if r.get("label") == s["label"]]
            attempts = [dict(attempt=r.get("attempt"), rc=r.get("rc"), validated=r.get("validated"), reasons=r.get("reasons"), prestart_reject=r.get("prestart_reject"), gate=(r.get("gate") or {}).get("result"),
                             gate_waited_s=(r.get("gate") or {}).get("waited_s"), tref=(r.get("gate") or {}).get("tref"), in_block_charge=r.get("in_block_charge"),
                             start_soc=(r.get("start_state") or {}).get("soc"), end_soc=(r.get("end_state") or {}).get("soc"), start_ap=(r.get("start_state") or {}).get("AP"),
                             start_skin=(r.get("start_state") or {}).get("SKIN"), host_start=(r.get("times") or {}).get("host_start")) for r in evs]
            valid = any(x["validated"] is True and x["rc"] == 0 for x in attempts)
            sessions.append(dict(block_no=blk["block_no"], order_pos=s["order_pos"], label=s["label"], index=s["index"], session_id=s["session_id"], manifest_sha256=s["manifest_sha256"],
                                 plan_dir=s["plan_dir"], valid=valid, rejects=sum(1 for x in attempts if x["prestart_reject"]), attempts=attempts))
        n_valid = sum(1 for s in sessions if s["valid"])
        groups.append(dict(group_index=gi, experiment_id=eid, arm=arm_name, bank=a["bank"], policy=a["policy"], policy_args=a["wait"], prep=a["prep"], block=a["block"],
                           selection=M8.SELECTION[a["policy"]], concurrency=M8.CONCURRENCY[a["policy"]],
                           config_sha256=dict(manifest_block1=sessions[0]["manifest_sha256"], manifest_block2=sessions[1]["manifest_sha256"], plan=(blocks.get("plan_sha256") or {}).get(M8.PLAN_DIR[eid])),
                           dev_valid=f"{n_valid}/2", dev_sessions=sessions,
                           confirm_status=("CONFIRM" if n_valid == 2 else "개발만 (DEV 2/2 미달 · 조민규 결정)"),
                           rule="등록 v2 §5-1(a): DEV 2/2 유효인 군만 CONFIRM · 1/2 이하 = '개발만' 표시 · 조민규 결정 · 반복 축소 0"))
    # ---- CONFIRM 계획 (seed 20261022 · 순서 미리 계산 · M8-B 에서 같은 seed 로 재생성 = 같은 값)
    rng = random.Random(M8.CONFIRM_SEED)
    confirm_blocks = []
    for b in range(1, PL.CONFIRM_BLOCKS + 1):
        order = list(range(len(PL.BLOCK_GROUPS)))
        rng.shuffle(order)
        rows = []
        for pos, gi in enumerate(order):
            eid, arm_name = PL.BLOCK_GROUPS[gi]
            rep = b - 1
            index = M8.dev_count(eid) + M8.index_of(eid, arm_name, rep)
            rows.append(dict(order_pos=pos, group_index=gi, experiment_id=eid, arm=arm_name, repetition=rep, index=index, session_id=M8.session_id(eid, index), label=f"C{b}-{pos:02d}-{arm_name}"))
        confirm_blocks.append(dict(block_no=b, order=order, sessions=rows))
    bundles = [dict(path=str(p), sha256=sha(p), bytes=p.stat().st_size if p.is_file() else None) for p in args.bundle]
    freeze = dict(
        schema="s26-m8-confirm-freeze-v1", made=dt.datetime.now().isoformat(timespec="seconds"), source_commit=args.source_commit,
        status_split=dict(prepared=True, registered=True, dev_started=True, dev_completed=all(s["valid"] for g in groups for s in g["dev_sessions"]),
                          confirm_started=False, note="준비 · 등록 · 실측 착수 · 완료 상태 분리 (조민규 #8) · CONFIRM 은 별도 프롬프트 M8-B · 이 파일 커밋 뒤"),
        registration=dict(v2=dict(file="d1sim/docs/M8_사전등록_v2.md", sha256=sha(REPO / "d1sim/docs/M8_사전등록_v2.md")), v3=dict(file="d1sim/docs/M8_사전등록_v3.md", sha256=sha(REPO / "d1sim/docs/M8_사전등록_v3.md"), note="v2 바이트 + 부록 (P0 보충 · 운영) · 블록 1·2 = v2 계약"),
                          contract_table_v2=dict(file="d1sim/docs/M8_계약표_v2.md", sha256=sha(REPO / "d1sim/docs/M8_계약표_v2.md")),
                          contract_v2={p.name: sha(p) for p in sorted((PLAN_ROOT / "contract_v2").glob("*"))},
                          blocks_json=dict(file="s26/results/m8_prep/plan_m8/blocks.json", sha256=sha(PLAN_ROOT / "plan_m8/blocks.json"), dev_seed=blocks["dev_seed"], confirm_seed=blocks["confirm_seed"]),
                          p0_supp_json=dict(file="s26/results/m8_prep/plan_m8/p0_supp.json", sha256=sha(PLAN_ROOT / "plan_m8/p0_supp.json")),
                          plan_sha256=blocks.get("plan_sha256"), apk_sha256="37960e25c5948f661f2f5b47a90a4356be1b3712706d34679e71a14842ced6ea", apk_installed="2026-10-15T02:37:52 (재설치 금지)"),
        settings=dict(policies=7, banks=dict(M8.BANK_COUNT), burst_interval_ns=M8.BURST_INTERVAL_NS, first_offset_ns=M8.FIRST_OFFSET_NS, deadlines_ms=dict(urgent=M8.URGENT_DEADLINE_MS, normal=M8.NORMAL_DEADLINE_MS),
                      wait_configs=dict(WAIT200x16=M8.WAIT200X16, WAIT200x12=M8.WAIT200X12, WAIT1000x12=M8.WAIT1000X12), phases=M8.phases(M8.BLOCK_M),
                      soc=dict(start_min=M8.SOC_MIN_START, start_max=M8.SOC_MAX_START, new_band_reference_only=list(M8.SOC_NEW_BAND), note="SOC ≥ 20 · 상한 없음 = 영훈 운영 결정 · 원래 40~80 과 다른 조건 · 기준 밖 삭제 0"),
                      tref_v2=dict(algorithm="TREF_DAY_FIRST_STABLE_AP60_V2", sensor=M8.TREF_SENSOR, idle_s=M8.TREF_IDLE_S, window_s=M8.TREF_WINDOW_S, min_samples=M8.TREF_MIN_SAMPLES, max_gap_s=M8.TREF_MAX_GAP_S,
                                   search_max_s=M8.TREF_SEARCH_MAX_S, band_c=M8.TREF_BAND_C, slope_max_c_per_min=M8.SLOPE_MAX_C_PER_MIN, gate_poll_s=M8.GATE_POLL_S, gate_max_wait_s=M8.GATE_MAX_WAIT_S,
                                   dev_values={k: dict(tref_c=v.get("tref_c"), stable_miss=v.get("stable_miss"), fixed_idle_skipped=v.get("fixed_idle_skipped"), t=v.get("t")) for k, v in tref.items()},
                                   confirm_rule="측정 구간마다 (드라이버 시작) 새로 산출 · 블록 안 재산출 0 · 거절 횟수 보고 옮기지 않음 · CONFIRM 에서 상수 변경 0"),
                      coverage=dict(app_pre_t0_min_s=M8.APP_PRE_T0_MIN_S, app_post_t0_min_s=M8.APP_POST_T0_MIN_S, app_points_s=list(M8.APP_POINTS_S), hal_ap_points_s=list(M8.HAL_AP_POINTS_S), hal_iv_points_s=list(M8.HAL_IV_POINTS_S),
                                    app_max_gap_s=M8.APP_MAX_GAP_S, hal_max_gap_s=M8.HAL_MAX_GAP_S, hal_target_period_s=M8.HAL_TARGET_PERIOD_S),
                      operation=dict(run_gap_min_s=M8.RUN_GAP_MIN_S, hal_pre_start_s=M8.HAL_PRE_START_S, hal_after_origin_s=M8.HAL_AFTER_ORIGIN_S, safety_skin_c=M8.SAFETY_SKIN_C, safety_thermal_status=M8.SAFETY_THERMAL_STATUS,
                                     charge_to_first_run_min_s=M8.CHARGE_TO_FIRST_RUN_MIN_S, dev_deviation_1015="영훈 08:xx: 충전 뒤 고정 유휴 생략 (--no-fixed-idle) · 낮 블록 · 블록 2 바로 이어서 · Tref 키 분리 — 등록 v3 부록 · CONFIRM 운영은 M8-B 프롬프트에서 정함")),
        metrics=dict(definitions=["서비스 svc70/80/90/95/100 (분모 planned)", "긴급 P95 (output_ready) · 일반 P95 (readback 성공) — 응답 경계 = priority", "전량완료 all_completed · late (urgent_late · normal_late) · undispatched · failed · unfinished",
                                  "WAIT nominal / planned / dose / overrun / cut (명목으로 실제 대체 0)", "준비 prep_calls · prep_actual_s (RECENT)", "readback_ok 성공률", "coverage app/host (post_t0 ≥ 210 · 점 0/35/120/180)",
                                  "ΔJ · AP · 잔열 = 조민규 계산 (이쪽 산출물 = 표본만 · 계산 0)"],
                     source="m8_readout.py (response_m8.json session_summary) · m8_table.py 세션 표 · coverage_check.py"),
        analysis_criteria=MISSING, tolerances=MISSING, model_predictions=MISSING, atc_ppo_handoff=MISSING,
        comparison_pairs=dict(status="이쪽 동결 (구조 규칙만 · 수치 기준 = missing_from_partner)",
                              rules=["같은 bank 안에서 정책만 다른 군을 쌍으로 (같은 블록의 같은 반복 번호끼리 1:1)",
                                     "M128: BASE↔ORDER (FIFO↔EDD) · BASE↔PAIR_G · BASE↔PAIR_N · BASE↔NPU_SERIAL · BASE↔WAIT200x16 · WAIT200x16↔WAIT200x12 · WAIT200x16↔WAIT1000x12",
                                     "SMOOTH128: BASE↔ORDER · BASE↔PAIR_G · SMOOTH128_X↔M128_X (도착 모양)", "L64: BASE↔PAIR_G",
                                     "RECENT: CPU60↔IDLE60 (백엔드 CPU/GPU/NPU 별) · P0 FN C252 1세션은 참고만 (쌍 아님)",
                                     "쌍의 한쪽이 무효/빈 자리면 그 반복의 쌍은 비교 제외 (삭제 0 · 표시)"]),
        denominators=dict(requests="planned (bank 수 · 완료만 남기지 않음)", sessions="계획 세션 수 (DEV 19×2 · CONFIRM 19×5) · PRESTART_REJECT / GATE_UNDECIDABLE = 계획 coverage 분모 (START 와 구분) · 실제 서비스율 분모 = START 한 세션",
                          consumption="실패/미완료/재시도/충전/안전정지 소비 보존 · a2 재사용 0 · 쓴 ID 재사용 0"),
        exclusion_rules=["유효 = m8_validate A0 ~ A10 (coverage A10 포함) · 무효 → a2 1회 → invalid_twice (자리 비움 · 재사용 0)", "PRESTART_REJECT 2회 = 자리 비움 (계획 밖 재시도 0)",
                         "SOC 밴드 (40~80) 밖 자료 삭제 0 · '원래 조건 준수' 표기 0 · 블록 안 충전 세션은 표시 (무효 아님)", "Perfetto 는 P0 보충 세션만 on · 블록은 off (미지원 (권한))",
                         "M7-A L-C3/L-G3 = DEV 재사용 후보 (식별표 연결 필요 · 87/38 대체 아님)"],
        candidates=groups, dev_summary=dict(groups=len(groups), confirm_eligible=sum(1 for g in groups if g["confirm_status"] == "CONFIRM"), dev_only=[g["arm"] for g in groups if g["confirm_status"] != "CONFIRM"],
                                            prestart_rejects=sum(s["rejects"] for g in groups for s in g["dev_sessions"])),
        dev_data=dict(bundles=bundles, repo_copy="s26/results/m8_prep/dev/block1 · block2 (표 · readout · prestart · tref · 정리 logcat 만)"),
        confirm_plan=dict(blocks=PL.CONFIRM_BLOCKS, sessions_per_block=len(PL.BLOCK_GROUPS), total=PL.CONFIRM_BLOCKS * len(PL.BLOCK_GROUPS), seed=M8.CONFIRM_SEED,
                          index_rule="dev_count(exp) + index_of(exp, arm, rep) · rep = 0..4 · session_id = uuid5(M8_NS, exp/index)", order_rule="random.Random(seed).shuffle(range(19)) 블록마다 (m8_plan DEV 와 같은 방식) · M8-B 에서 재생성 = 같은 값",
                          order_precomputed=confirm_blocks, termination="5블록 완주 · 못 끝내면 그 모듈 '미완료/개발만' 명시 · 반복 축소 0", start="M8-B 별도 프롬프트 · 이 파일 커밋 · push · 조민규 부족 항목 답 뒤",
                          dev_only_groups_note="'개발만' 군도 CONFIRM 계획에서 빼지 않음 (조민규 결정 전 · 축소 0)"),
        notes=["계산 · 판정 0 (유효 수 세기만)", "확인 자료로 계수 · 조건 · 제외 규칙 · 순서 · Tref 상수 · coverage 상수를 바꾸지 않는다 · 동결 전 CONFIRM 0"])
    bb = C.canonical_json(freeze)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(bb)
    for c in args.copy:
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_bytes(bb)
    print(json.dumps(dict(out=str(args.out), sha256=C.sha256_bytes(bb), bytes=len(bb), confirm_eligible=freeze["dev_summary"]["confirm_eligible"], dev_only=freeze["dev_summary"]["dev_only"]), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
