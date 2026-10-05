"""NIGHT 1005e (P1e 1-1): build the 8 EffNet chains of prereg 밤1005e_사전등록_v1.md s1 from the MobileNet templates.

Method = 밤1005_체인기록.md s1: json.loads -> json.dumps(indent=2, ensure_ascii=False) + "\\n" (LF).
Step 1: re-serialize every existing tools/chains/*.json the same way and require byte identity.
Step 2: per new chain, copy the template segments, change only chain_id, segment label/duty/duration_s and the
model fields (NPU: model asset; GPU: model -> model_path in the same key position; input_spec both).
Model values were read from run_metadata of results/S26_EffN420_npu_1004 (NPU) and
results/S26_EffB2_02_gpu100_1004 (GPU): npu_model_source, model_sha256, npu_input_spec.
Writes only new files; refuses to overwrite an existing chain.
"""
import json, sys, hashlib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4")
CH = ROOT / "tools" / "chains"

def ser(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

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
    sys.exit(2)

NPU_MODEL = "models/efficientnet_lite0_Samsung_E9965.tflite"
GPU_PATH = "/data/local/tmp/efficientnet_lite0.tflite"
INPUT = "lcg-rgb-127-128"

# (new file, template, [(label, duty, duration_s), ...]) — prereg s1 table
PLAN = [
    ("npu_eff_work100_v1", "npu_work100_v1", [("work_d100", 100, 300), ("tail_idle", 1, 600)]),
    ("npu_eff_work50_v1", "npu_work50_v1", [("work_d50", 50, 660), ("tail_idle", 1, 240)]),
    ("gpu_eff_work100_v1", "gpu_work100_v1", [("work_d100", 100, 300), ("tail_idle", 1, 600)]),
    ("gpu_eff_work50_v1", "gpu_work50_v1", [("work_d50", 50, 720), ("tail_idle", 1, 180)]),
    ("npu_eff_idle300_v1", "npu_idle300_v1", [("cold_ref_d10", 10, 60), ("heat_d100", 100, 300), ("rest_idle", 1, 300), ("reheat_d100", 100, 180)]),
    ("gpu_eff_idle300_v1", "gpu_idle300_v1", [("cold_ref_d10", 10, 60), ("heat_d100", 100, 600), ("rest_idle", 1, 300), ("reheat_d100", 100, 300)]),
    ("smoke_npu_eff_v1", "npu_work100_v1", [("work_d100", 100, 30), ("tail_idle", 1, 30)]),
    ("smoke_gpu_eff_v1", "gpu_work100_v1", [("work_d100", 100, 30), ("tail_idle", 1, 30)]),
]

def swap_model(seg):
    out = {}
    for k, v in seg.items():
        if k == "model":
            if seg["accelerator"] == "NPU":
                out["model"] = NPU_MODEL
            else:
                out["model_path"] = GPU_PATH
        elif k == "input_spec":
            out["input_spec"] = INPUT
        else:
            out[k] = v
    return out

for new, tmpl, segs in PLAN:
    t = json.loads((CH / f"{tmpl}.json").read_bytes().decode("utf-8"))
    base = t["segments"][0]
    # template segments must agree outside label/duty/duration_s (same assert as 밤1005_체인기록 s1)
    for s in t["segments"]:
        a = {k: v for k, v in s.items() if k not in ("label", "duty", "duration_s")}
        b = {k: v for k, v in base.items() if k not in ("label", "duty", "duration_s")}
        assert a == b, (tmpl, s)
    obj = dict(t)
    obj["chain_id"] = new
    nsegs = []
    for (lab, duty, dur) in segs:
        s = dict(base)
        s["duty"] = duty
        s["duration_s"] = dur
        s["label"] = lab
        nsegs.append(swap_model(s))
    obj["segments"] = nsegs
    path = CH / f"{new}.json"
    if path.exists():
        print("EXISTS, not overwritten:", path.name)
        sys.exit(3)
    data = ser(obj)
    path.write_bytes(data)
    print(f"wrote {path.name} sha256={hashlib.sha256(data).hexdigest()} sum={sum(x[2] for x in segs)}")
