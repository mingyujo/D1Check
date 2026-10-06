"""V3 (P1g 1-3): build the 4 V3 chains of sim/V3_사전등록_v1.md §2 (commit 036f87b) from d1sim/out/v3_1006/timelines.json.

Method = make_chains_1005e.py (밤1005e_체인기록.md §1): json.loads -> json.dumps(indent=2, ensure_ascii=False) + "\\n" (LF).
Step 1: re-serialize every existing tools/chains/*.json the same way and require byte identity.
Step 2: template = tools/chains/npu_eff_work100_v1.json segment 0 (NPU · models/efficientnet_lite0_Samsung_E9965.tflite ·
        lcg-rgb-127-128; chain model_prepare per_segment). Per new chain only chain_id and segment label/duty/duration_s change.
Encoding (§2-2): commanded duty per 10 s cell over the window [0, min(horizon, 3600)] -> run length; duty 0 (no BG) -> 1 (d_min);
        the last cell is clipped so Σ = ceil(window) whole seconds. §2-3 merging only if > 32 segments (then this script stops —
        merging needs a re-simulation first). Label = s<NN>_d<duty>.
Writes only new files; refuses to overwrite an existing chain.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4")
CH = ROOT / "tools" / "chains"
TL = ROOT / "d1sim" / "out" / "v3_1006" / "timelines.json"
TEMPLATE = "npu_eff_work100_v1"
MAX_SEG = 32
MAX_TOTAL = 3600
D_MIN = 1
PLAN = [("v3_A_base_v1", "A", "fixed-prio"), ("v3_A_ours_v1", "A", "ours(m0,o0)"),
        ("v3_B_base_v1", "B", "fixed-prio"), ("v3_B_ours_v1", "B", "ours(m0,o0)")]


def ser(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def rle(grid):
    segs = []
    for duty, L in zip(grid["duty"], grid["cell_len_s"]):
        d = D_MIN if duty == 0 else int(duty)
        if segs and segs[-1][0] == d:
            segs[-1][1] += L
        else:
            segs.append([d, L])
    return segs


def main():
    same = 0
    existing = sorted(CH.glob("*.json"))
    for p in existing:
        raw = p.read_bytes()
        if ser(json.loads(raw.decode("utf-8"))) == raw:
            same += 1
        else:
            print("NOT BYTE-IDENTICAL:", p.name)
    print(f"step1 reserialize identical {same}/{len(existing)}")
    if same != len(existing):
        return 2
    tl = json.loads(TL.read_bytes().decode("utf-8"))
    if not tl["checks"]["all_section_2_1_ok"]:
        print("timelines.json §2-1 check failed — stop")
        return 4
    t = json.loads((CH / f"{TEMPLATE}.json").read_bytes().decode("utf-8"))
    base = t["segments"][0]
    for s in t["segments"]:
        a = {k: v for k, v in s.items() if k not in ("label", "duty", "duration_s")}
        b = {k: v for k, v in base.items() if k not in ("label", "duty", "duration_s")}
        assert a == b, s
    for new, cond, key in PLAN:
        g = tl["conditions"][cond]["policies"][key]["grid"]
        segs = rle(g)
        total = sum(L for _, L in segs)
        assert total == g["sigma_s"] <= MAX_TOTAL, (new, total)
        if len(segs) > MAX_SEG:
            print(f"{new}: {len(segs)} segments > {MAX_SEG} — §2-3 merge + re-sim needed; stop")
            return 5
        obj = dict(t)
        obj["chain_id"] = new
        nsegs = []
        for i, (duty, dur) in enumerate(segs):
            s = dict(base)
            s["duty"] = duty
            s["duration_s"] = dur
            s["label"] = f"s{i:02d}_d{duty}"
            nsegs.append(s)
        obj["segments"] = nsegs
        path = CH / f"{new}.json"
        if path.exists():
            print("EXISTS, not overwritten:", path.name)
            return 3
        data = ser(obj)
        path.write_bytes(data)
        print(f"wrote {path.name} segments={len(segs)} sum={total} sha256={hashlib.sha256(data).hexdigest()}")
        print("   ", " ".join(f"d{d}x{L}" for d, L in segs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
