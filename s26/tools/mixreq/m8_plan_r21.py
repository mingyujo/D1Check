"""M8 CONFIRM R21 plan (2026-10-16 · 조민규 1016 정정안 SHA 1dc9f5b5… · 프롬프트 M8-B R21) — deterministic bytes, no timestamps. m8_plan.manifest is imported unchanged.

  py -3 -X utf8 s26/tools/mixreq/m8_plan_r21.py --out-root s26/results/m8_prep

21 슬롯 = 동결 v1 (CONFIRM_FREEZE_M8_v1.json · deedfc1b…) confirm_plan.order_precomputed 의 C1 ~ C3 에서 유지 7군만 · 상대 순서 그대로 (새 무작위 0) · R블록 = R1 ~ R3.
index · session_id = 원 C 슬롯 값 그대로 (95판 START 0 · 미소비 · 1:1 추적). 매니페스트 = m8_plan.manifest (DEV 와 같은 함수 · analysis_split confirm → pair 1).
Writes <out-root>/plan_m8m128_r21/ · plan_m8s128_r21/ (plan.json · manifests/ · device_inputs.json · plan_sha256.txt) and <out-root>/plan_m8_r21/r21_manifest.json (+ _sha256.txt).
95판 계획 · 기존 plan_m8* · 동결 v1 은 읽기만 (변경 0).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m8_common as M8  # noqa: E402
import mixreq_common as C  # noqa: E402
import m8_plan as P  # noqa: E402
import m6_plan as MP  # noqa: E402

REVISION_ID = "M8_CONFIRM_R21_v1"
SCHEMA = "s26-m8-confirm-r21-v1"
FREEZE_V1 = "CONFIRM_FREEZE_M8_v1.json"
FREEZE_V1_SHA = "deedfc1be65354a0ef05ffacb07cefe7e939e6cc0a53d560493e5632eeb4023f"
CORRECTION_SHA = "1dc9f5b58b518f145b33ed6bf8d0216aa9e40e9ba490e0af996d40c31e6ac257"
KEEP = ("M128_BASE", "M128_ORDER", "M128_PAIR_G", "M128_WAIT200x16", "M128_NPU_SERIAL", "SMOOTH128_BASE", "SMOOTH128_PAIR_G")
EXCLUDED = ("L64_BASE", "L64_PAIR_G", "RECENT_IDLE60_C252_CPU", "RECENT_IDLE60_C252_GPU", "RECENT_IDLE60_C252_NPU", "RECENT_CPU60_C252_CPU", "RECENT_CPU60_C252_GPU",
            "RECENT_CPU60_C252_NPU", "M128_PAIR_N", "M128_WAIT200x12", "M128_WAIT1000x12", "SMOOTH128_ORDER")
R_BLOCKS = 3
PLAN_DIR_R21 = {M8.M128_ID: "plan_m8m128_r21", M8.S128_ID: "plan_m8s128_r21"}
SRC_PLAN_DIR = {M8.M128_ID: "plan_m8m128", M8.S128_ID: "plan_m8s128"}
# 프롬프트 1단계 표 (검산용 · 생성은 동결 v1 에서)
EXPECTED = {
    1: ["C1-03-M128_PAIR_G", "C1-05-M128_ORDER", "C1-09-M128_WAIT200x16", "C1-14-SMOOTH128_PAIR_G", "C1-16-M128_BASE", "C1-17-M128_NPU_SERIAL", "C1-18-SMOOTH128_BASE"],
    2: ["C2-00-M128_WAIT200x16", "C2-04-SMOOTH128_PAIR_G", "C2-07-SMOOTH128_BASE", "C2-09-M128_BASE", "C2-13-M128_PAIR_G", "C2-14-M128_NPU_SERIAL", "C2-15-M128_ORDER"],
    3: ["C3-03-M128_WAIT200x16", "C3-05-M128_BASE", "C3-09-SMOOTH128_BASE", "C3-10-M128_NPU_SERIAL", "C3-11-M128_ORDER", "C3-13-SMOOTH128_PAIR_G", "C3-16-M128_PAIR_G"],
}


INDEX_RULE_NOTE = ("동결 v1 index 규칙 'dev_count + index_of(arm, rep)' 은 dev_count (M128 500 · S128 200) 가 arm 수 (8 · 3) 의 배수가 아니라 arm = index % len(arms) 와 맞지 않음 "
                   "(95 슬롯 중 85 · 예 C1-03 M128_PAIR_G idx 502 → index 로 읽으면 M128_WAIT200x12). R21 = index · session_id 는 원 슬롯 그대로 (프롬프트 1단계) · "
                   "arm · policy · wait · prep · runtimes 는 슬롯 arm 으로 명시 (m8_plan.manifest 를 그 arm 으로 호출) · 하류 (m8_validate · m8_readout · m8_table) 는 매니페스트 arm/policy 필드를 읽음 · "
                   "requests() 는 bank 만 쓰고 군 안 bank 동일 (M128 · SMOOTH128) · m8_label = '<arm>#confirm<rep>'")


def manifest_for(eid: str, index: int, arm_name: str, rep: int, device: dict, labels: dict) -> dict:
    """m8_plan.manifest 를 슬롯 arm 으로 (arm_of(index) 대신) — INDEX_RULE_NOTE."""
    a = next(x for x in M8.arms(eid) if x["name"] == arm_name)
    keep = (M8.arm_of, M8.repetition_of)
    M8.arm_of = lambda e, i: a
    M8.repetition_of = lambda e, i: f"confirm{rep}"
    try:
        return P.manifest(eid, "confirmation", index, device, 1, labels)
    finally:
        M8.arm_of, M8.repetition_of = keep


def build(out_root: Path) -> tuple[dict, dict]:
    fz_bytes = (out_root / FREEZE_V1).read_bytes()
    if C.sha256_bytes(fz_bytes) != FREEZE_V1_SHA:
        raise SystemExit("freeze v1 SHA mismatch")
    fz = C.read_json(out_root / FREEZE_V1)
    keep, excluded = set(KEEP), set(EXCLUDED)
    assert len(keep | excluded) == 19 and not keep & excluded
    per_exp: dict[str, list[dict]] = {eid: [] for eid in PLAN_DIR_R21}
    devices = {eid: C.read_json(out_root / SRC_PLAN_DIR[eid] / "device_inputs.json") for eid in PLAN_DIR_R21}
    blocks = []
    for b in range(1, R_BLOCKS + 1):
        cb = next(x for x in fz["confirm_plan"]["order_precomputed"] if x["block_no"] == b)
        slots = sorted((s for s in cb["sessions"] if s["arm"] in keep), key=lambda s: s["order_pos"])
        if [s["label"] for s in slots] != EXPECTED[b]:
            raise SystemExit(f"R{b} slot table differs from prompt: {[s['label'] for s in slots]}")
        sessions = []
        for pos, s in enumerate(slots):
            eid = s["experiment_id"]
            if M8.session_id(eid, s["index"]) != s["session_id"] or s["index"] < M8.dev_count(eid):
                raise SystemExit(f"index/session_id mismatch at {s['label']}")
            label = f"R{b}-{pos}-{s['arm']}"
            origin = dict(label=s["label"], index=s["index"], session_id=s["session_id"], block_no=b, order_pos=s["order_pos"], group_index=s["group_index"], repetition=s["repetition"])
            labels = dict(analysis_split="confirm", stage="confirm", run_label=label, block_no=b, order_pos=pos, group_index=s["group_index"], revision_id=REVISION_ID, origin_slot=origin)
            m = manifest_for(eid, s["index"], s["arm"], s["repetition"], devices[eid], labels)
            assert m["arm"] == s["arm"] and m["session_id"] == s["session_id"]
            e = P.entry(m, f"manifests/{s['index']:03d}_{m['arm']}_{m['session_id']}.json", stage="confirm", run_label=label, block_no=b, order_pos=pos,
                        group_index=s["group_index"], revision_id=REVISION_ID, origin_slot=origin)
            per_exp[eid].append(e)
            sessions.append(dict(stage="confirm", label=label, experiment_id=eid, index=s["index"], arm=s["arm"], session_id=s["session_id"], manifest_sha256=e["manifest_sha256"],
                                 plan_dir=PLAN_DIR_R21[eid], block_no=b, order_pos=pos, group_index=s["group_index"], perfetto="off", revision_id=REVISION_ID, origin_slot=origin))
        blocks.append(dict(block_no=b, label=f"R{b}", origin_block=f"C{b}", origin_order=cb["order"], sessions=sessions))
    built = {}
    for eid, rows in per_exp.items():
        rows = sorted(rows, key=lambda e: e["index"])
        src = C.read_json(out_root / SRC_PLAN_DIR[eid] / "plan.json")
        plan = {k: v for k, v in src.items() if k not in ("sessions", "smoke", "notes", "dev_count")}
        plan.update(schema=P.PLAN_SCHEMA, revision_id=REVISION_ID, sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in rows], smoke=[],
                    source_plan=dict(dir=SRC_PLAN_DIR[eid], plan_sha256=(out_root / SRC_PLAN_DIR[eid] / "plan_sha256.txt").read_text(encoding="utf-8").strip()),
                    dev_count=M8.dev_count(eid),
                    notes=[f"{REVISION_ID}: CONFIRM 대역 index (원 C1 ~ C3 슬롯 그대로) · 매니페스트 = m8_plan.manifest (DEV 와 같은 함수 · analysis_split confirm)",
                           "계산 · 판정 없음 — 측정 계획만"])
        dev = {k: dict(host_path=v["host_path"], device_path=v["device_path"], sha256=v["sha256"], bytes=v["bytes"]) for k, v in devices[eid].items()}
        built[PLAN_DIR_R21[eid]] = dict(plan=plan, sessions=rows, smoke=[], device=dev)
    manifest = dict(schema=SCHEMA, revision_id=REVISION_ID, parent_freeze=dict(file=FREEZE_V1, sha256=FREEZE_V1_SHA), correction_sha256=CORRECTION_SHA,
                    keep_groups=list(KEEP), excluded_groups=list(EXCLUDED), excluded_status="미완료 — R21 축소로 CONFIRM 안 함 (DEV 2/2 만)",
                    blocks=R_BLOCKS, sessions_per_block=len(KEEP), total=R_BLOCKS * len(KEEP),
                    rule="동결 v1 confirm_plan.order_precomputed C1 ~ C3 에서 유지 7군 · 상대 순서 그대로 · 새 무작위 0 · index/session_id = 원 C 슬롯 그대로",
                    index_rule_note=INDEX_RULE_NOTE,
                    stages=dict(confirm_blocks=blocks), registration=M8.registration(), cycle=M8.CYCLE, contract=M8.CONTRACT)
    return manifest, built


REVISION_ID_V2 = "M8_CONFIRM_R21_v2"
V2_RULE = ("v2 (2026-10-16 05:4x 사고): 앱 M8Plan.validateSession 이 arm = index % len(arms) 를 강제 → v1 idx 502 (R1-0 PAIR_G) 를 M128_WAIT200x12 로 읽고 거부 (session not started). "
           "v1 21 슬롯 index 중 앱 규칙과 맞는 것 0 → v2 index = ceil(dev_count / len(arms)) × len(arms) + arm 자리 + len(arms) × (R − 1) (M128 504 + · SMOOTH128 201 +) · "
           "슬롯 · 순서 · arm · 입력 · 정책 · WAIT · 기한 변경 0 · 매니페스트 = m8_plan.manifest 그대로 (arm 덮어쓰기 0) · v1 index 는 origin_slot.index · v1_index 로 보존")
V1_CONSUMED = {"R1-0-M128_PAIR_G": dict(revision_id=REVISION_ID, index=502, session_id="a3fb231b-28aa-5286-a6cb-ea77474f03d0", attempt=1, rc=4, start="2026-10-16T05:30:38", end="2026-10-16T05:40:59",
                                        reason="앱 manifest 검증 거부 (m8 index 502 is M128_WAIT200x12 · manifest policy FIFO_PAIR_CG_V1) · session not started · 부하 0 · rc 4 stall 600 s")}


def aligned_index(eid: str, arm_name: str, r: int) -> int:
    a = M8.arms(eid)
    base = -(-M8.dev_count(eid) // len(a)) * len(a)
    return base + next(i for i, x in enumerate(a) if x["name"] == arm_name) + len(a) * (r - 1)


def build_v2(out_root: Path) -> tuple[dict, dict]:
    v1 = C.read_json(out_root / "plan_m8_r21" / "r21_manifest.json")
    assert v1["revision_id"] == REVISION_ID
    devices = {eid: C.read_json(out_root / SRC_PLAN_DIR[eid] / "device_inputs.json") for eid in PLAN_DIR_R21}
    per_exp: dict[str, list[dict]] = {eid: [] for eid in PLAN_DIR_R21}
    blocks = []
    for blk in v1["stages"]["confirm_blocks"]:
        b = blk["block_no"]
        sessions = []
        for s in blk["sessions"]:
            eid, label, pos = s["experiment_id"], s["label"], s["order_pos"]
            idx = aligned_index(eid, s["arm"], b)
            labels = dict(analysis_split="confirm", stage="confirm", run_label=label, block_no=b, order_pos=pos, group_index=s["group_index"], revision_id=REVISION_ID_V2,
                          origin_slot=s["origin_slot"], v1_index=s["index"])
            m = P.manifest(eid, "confirmation", idx, devices[eid], 1, labels)
            assert m["arm"] == s["arm"] == M8.arm_of(eid, idx)["name"] and idx >= M8.dev_count(eid)
            e = P.entry(m, f"manifests/{idx:03d}_{m['arm']}_{m['session_id']}.json", stage="confirm", run_label=label, block_no=b, order_pos=pos,
                        group_index=s["group_index"], revision_id=REVISION_ID_V2, origin_slot=s["origin_slot"], v1_index=s["index"])
            per_exp[eid].append(e)
            row = dict(stage="confirm", label=label, experiment_id=eid, index=idx, arm=s["arm"], session_id=m["session_id"], manifest_sha256=e["manifest_sha256"],
                       plan_dir=PLAN_DIR_R21[eid] + "v2", block_no=b, order_pos=pos, group_index=s["group_index"], perfetto="off", revision_id=REVISION_ID_V2,
                       origin_slot=s["origin_slot"], v1_index=s["index"])
            if label in V1_CONSUMED:
                row.update(prior_consumed=[V1_CONSUMED[label]], start_attempt=2,
                           start_attempt_note="v1 a1 (idx 502) = 소비된 실패 START (보존 · 계수) → 슬롯 재시도 1회 규칙 (a2 · 600 s 휴식) · 성공 행으로 a1 을 덮지 않음")
            sessions.append(row)
        blocks.append(dict(blk, sessions=sessions))
    built = {}
    for eid, rows in per_exp.items():
        rows = sorted(rows, key=lambda e: e["index"])
        src = C.read_json(out_root / SRC_PLAN_DIR[eid] / "plan.json")
        plan = {k: v for k, v in src.items() if k not in ("sessions", "smoke", "notes", "dev_count")}
        plan.update(schema=P.PLAN_SCHEMA, revision_id=REVISION_ID_V2, sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in rows], smoke=[],
                    source_plan=dict(dir=SRC_PLAN_DIR[eid], plan_sha256=(out_root / SRC_PLAN_DIR[eid] / "plan_sha256.txt").read_text(encoding="utf-8").strip()),
                    dev_count=M8.dev_count(eid), notes=[V2_RULE, "계산 · 판정 없음 — 측정 계획만"])
        dev = {k: dict(host_path=v["host_path"], device_path=v["device_path"], sha256=v["sha256"], bytes=v["bytes"]) for k, v in devices[eid].items()}
        built[PLAN_DIR_R21[eid] + "v2"] = dict(plan=plan, sessions=rows, smoke=[], device=dev)
    manifest = {k: v for k, v in v1.items() if k not in ("plan_sha256", "stages", "revision_id", "index_rule_note")}
    manifest.update(revision_id=REVISION_ID_V2, index_rule_note=V2_RULE, parent_manifest=dict(file="plan_m8_r21/r21_manifest.json", revision_id=REVISION_ID,
                    sha256=C.sha256_bytes((out_root / "plan_m8_r21" / "r21_manifest.json").read_bytes())), v1_consumed=V1_CONSUMED, stages=dict(confirm_blocks=blocks))
    return manifest, built


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-root", required=True, type=Path)
    ap.add_argument("--rev", type=int, default=1, choices=(1, 2))
    args = ap.parse_args()
    M8.activate()
    if args.rev == 2:
        manifest, built = build_v2(args.out_root)
        shas = {name: MP.write_sessions(args.out_root / name, b) for name, b in built.items()}
        for name in shas:
            print(f"{name} {shas[name]} sessions {len(built[name]['sessions'])}")
        manifest["plan_sha256"] = shas
        mb = C.canonical_json(manifest)
        (args.out_root / "plan_m8_r21" / "r21_manifest_v2.json").write_bytes(mb)
        d = C.sha256_bytes(mb)
        (args.out_root / "plan_m8_r21" / "r21_manifest_v2_sha256.txt").write_text(d + "\n", encoding="utf-8", newline="\n")
        print(f"r21_manifest_v2 {d} slots {manifest['total']}")
        return 0
    manifest, built = build(args.out_root)
    shas = {}
    for name, b in built.items():
        shas[name] = MP.write_sessions(args.out_root / name, b)
        print(f"{name} {shas[name]} sessions {len(b['sessions'])}")
    manifest["plan_sha256"] = shas
    out = args.out_root / "plan_m8_r21"
    out.mkdir(parents=True, exist_ok=True)
    mb = C.canonical_json(manifest)
    (out / "r21_manifest.json").write_bytes(mb)
    d = C.sha256_bytes(mb)
    (out / "r21_manifest_sha256.txt").write_text(d + "\n", encoding="utf-8", newline="\n")
    print(f"r21_manifest {d} slots {manifest['total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
