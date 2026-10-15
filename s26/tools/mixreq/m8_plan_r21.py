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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-root", required=True, type=Path)
    args = ap.parse_args()
    M8.activate()
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
