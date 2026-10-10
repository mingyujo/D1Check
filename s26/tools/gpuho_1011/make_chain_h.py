"""GPU HOLDOUT (GH 1011, 3단계-3): build tools/chains/gpu_eff_work50eq_v1.json (prereg GPU홀드아웃_사전등록_v1.md §2-2) from gpu_eff_work50_v1.

Method = energy C make_chain_c.py / 밤1005e_체인기록.md §1: read with tools/npu_chain.load_chain (validate + canonical SHA),
serialize json.dumps(indent=2, ensure_ascii=False) + "\\n" (LF).
Step 1: re-serialize every existing tools/chains/*.json the same way and require byte identity (incl. gpu_eff_work50_v1).
Step 2: the template gpu_eff_work50_v1 must have canonical SHA 4af89784...; A chain gpu_eff_work100_v1 df0ffa2f... and
        smoke smoke_gpu_eff_v1 16c951ba... are re-checked (unchanged).
Step 3: copy the template, change only chain_id -> gpu_eff_work50eq_v1 and duration_s 720 -> T (work_d50, GPU 50) ·
        180 -> 900 - T (tail_idle, GPU 1) (Σ 900), T read from sim/out_gpuho/T_calc.json (t_calc.py). Every other field stays
        (model_path · input_spec · gpu_precision · per_segment). Refuses to overwrite an existing different chain.
  py -X utf8 make_chain_h.py <T_calc.json>
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4")
sys.path.insert(0, str(ROOT / "tools"))
import npu_chain  # noqa: E402

CH = ROOT / "tools" / "chains"
EXPECT = {"gpu_eff_work50_v1": "4af89784ae20fce30f356ca30c69d4ec54aab65f9582901e846a0b4ac54cf53c",
          "gpu_eff_work100_v1": "df0ffa2f15ddc9c1c0cab60cd09daeff48e34165296af64aaf77e58bc85eb513",
          "smoke_gpu_eff_v1": "16c951ba993423b82b2921b2e000957afeb7ea8e5b192121590a381ae29aea29"}
NEW = "gpu_eff_work50eq_v1"


def ser(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def build(template_spec, chain_id, durs):
    obj = json.loads(json.dumps(template_spec))          # deep copy, key order kept
    obj["chain_id"] = chain_id
    for s in obj["segments"]:
        duty, dur = durs[s["label"]]
        assert s["duty"] == duty, (s["label"], s["duty"], duty)
        assert s["accelerator"] == "GPU", s
        s["duration_s"] = dur
    return obj


tc = json.load(open(sys.argv[1], encoding="utf-8"))
T = int(tc["T"])
assert tc["kind"] == "gpuho_T_calc_v1" and 10 <= T <= 840 and T % 10 == 0, (tc.get("kind"), T)
DURS = {"work_d50": (50, T), "tail_idle": (1, 900 - T)}
print(f"T = {T} (from {sys.argv[1]}) -> work_d50 GPU 50·{T} / tail_idle GPU 1·{900 - T}")

existing = sorted(CH.glob("*.json"))
same = sum(1 for p in existing if ser(json.loads(p.read_bytes().decode("utf-8"))) == p.read_bytes())
print(f"step1 reserialize identical {same}/{len(existing)}")
if same != len(existing):
    sys.exit(2)
for cid, sha in EXPECT.items():
    got = npu_chain.load_chain(CH / f"{cid}.json")["sha256"]
    print(f"step2 {cid} canonical {got} {'OK' if got == sha else 'MISMATCH'}")
    if got != sha:
        sys.exit(4)
tmpl = npu_chain.load_chain(CH / "gpu_eff_work50_v1.json")
same_back = ser(build(tmpl["spec"], "gpu_eff_work50_v1", {"work_d50": (50, 720), "tail_idle": (1, 180)}))
if same_back != (CH / "gpu_eff_work50_v1.json").read_bytes():
    print("step3 regenerate gpu_eff_work50_v1: NOT byte-identical")
    sys.exit(5)
print("step3 regenerate gpu_eff_work50_v1 with the same build(): byte-identical")
obj = build(tmpl["spec"], NEW, DURS)
path = CH / f"{NEW}.json"
if path.exists():
    if path.read_bytes() == ser(obj):
        print(f"EXISTS (byte-identical, not rewritten): {path.name}")
    else:
        print(f"EXISTS and DIFFERENT, not overwritten: {path.name}")
        sys.exit(3)
else:
    path.write_bytes(ser(obj))
    print(f"wrote {path.name}")
info = npu_chain.load_chain(path)
print(f"{NEW} canonical {info['sha256']} file {info['source_file_sha256']} total {info['total_duration_s']} s segments "
      + " · ".join(f"{s['label']} {s['accelerator']} {s['duty']}·{s['duration_s']}" for s in info["spec"]["segments"]))
