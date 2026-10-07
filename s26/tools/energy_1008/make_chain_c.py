"""ENERGY C (P1i 1008, 1-4): build tools/chains/npu_eff_work50eq_v1.json (energy prereg v1 §6-2) from npu_eff_work50_v1.

Method = 밤1005e_체인기록.md §1 / make_chains_1005e.py: read with tools/npu_chain.load_chain (validate + canonical SHA),
serialize json.dumps(indent=2, ensure_ascii=False) + "\\n" (LF).
Step 1: re-serialize every existing tools/chains/*.json the same way and require byte identity (incl. npu_eff_work50_v1).
Step 2: the template npu_eff_work50_v1 must have canonical SHA 168a5b53...; A chain npu_eff_work100_v1 4433e259... and
        smoke smoke_npu_eff_v1 82ce7744... are re-checked (unchanged).
Step 3: copy the template, change only chain_id -> npu_eff_work50eq_v1 and duration_s 660 -> 620 (work_d50, NPU 50) ·
        240 -> 280 (tail_idle, NPU 1) (Σ 900). Every other field stays. Refuses to overwrite an existing chain.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4")
sys.path.insert(0, str(ROOT / "tools"))
import npu_chain  # noqa: E402

CH = ROOT / "tools" / "chains"
EXPECT = {"npu_eff_work50_v1": "168a5b53c1c73dee0d3e219832735de67642946b98d57c2899bb1db7b2eaa3f6",
          "npu_eff_work100_v1": "4433e25923aa7aacfaa5f123466135e145b10100e27c7d416874abab8337f09c",
          "smoke_npu_eff_v1": "82ce7744d47c8fa783d46f86fa105a4ed62883d84e8cc44d2a451bca2a906eeb"}
NEW = "npu_eff_work50eq_v1"
DURS = {"work_d50": (50, 620), "tail_idle": (1, 280)}


def ser(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def build(template_spec, chain_id, durs):
    obj = json.loads(json.dumps(template_spec))          # deep copy, key order kept
    obj["chain_id"] = chain_id
    for s in obj["segments"]:
        duty, dur = durs[s["label"]]
        assert s["duty"] == duty, (s["label"], s["duty"], duty)
        s["duration_s"] = dur
    return obj


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
tmpl = npu_chain.load_chain(CH / "npu_eff_work50_v1.json")
# generation method check: the same build() with the template's own values must give the template bytes
same_back = ser(build(tmpl["spec"], "npu_eff_work50_v1", {"work_d50": (50, 660), "tail_idle": (1, 240)}))
if same_back != (CH / "npu_eff_work50_v1.json").read_bytes():
    print("step3 regenerate npu_eff_work50_v1: NOT byte-identical")
    sys.exit(5)
print("step3 regenerate npu_eff_work50_v1 with the same build(): byte-identical")
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
