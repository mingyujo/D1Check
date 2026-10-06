"""V3 1006: byte copy of s26/tools/n4_1006/run_check_1006r.py (only this line added). Called with NPU --exp-sha 311e4aac… --input lcg-rgb-127-128.
N4 1006r copy of s26/tools/night_1005e/run_check_1005e.py. ONLY change: optional --exp-sha <sha> --input <spec> override the expected model SHA /
input_spec (used for the N1 MobileNet supplementary runs: NPU 1415b2c8... / GPU d95b3c5e... , input lcg-unit). Without them = the 1005e behaviour.
NIGHT 1005e: per-run check used for the smoke pass criteria (prereg night1005e s4-0) and for the N4 model-SHA record.

usage: py -X utf8 run_check_1005e.py <results_out_dir> <NPU|GPU> [--phone-sha <sha>]
Reads (never writes inside results): experiment_manifest.json runs[0] (status, validation), the single runner JSONL in runs\\<id>\\gpu
(run_metadata chain_segments[*].model_sha256 / input_spec, segment_end detail termination_reason / inference_count / model_sha256).
Prints one JSON line. Pass criteria (smoke): orchestrator slot valid · every segment duration_complete · model SHA = expected
(no SHA in the run -> the phone file sha256sum given by --phone-sha must equal expected; a DIFFERENT SHA in the run = fail) ·
input_spec = lcg-rgb-127-128 · every segment n > 0 · no emergency.
"""
import glob, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
EXP = {"NPU": "311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31",
       "GPU": "6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0"}
INPUT = "lcg-rgb-127-128"


def detail(e):
    d = e.get("detail")
    if isinstance(d, dict):
        return d
    try:
        return json.loads(d) if isinstance(d, str) else {}
    except ValueError:
        return {}


def main():
    out_dir, res = sys.argv[1], sys.argv[2]
    phone_sha = sys.argv[sys.argv.index("--phone-sha") + 1] if "--phone-sha" in sys.argv else None
    global INPUT
    if "--exp-sha" in sys.argv:
        EXP[res] = sys.argv[sys.argv.index("--exp-sha") + 1]
    if "--input" in sys.argv:
        INPUT = sys.argv[sys.argv.index("--input") + 1]
    r = dict(out_dir=os.path.basename(out_dir), resource=res, reasons=[])
    mp = os.path.join(out_dir, "experiment_manifest.json")
    if not os.path.exists(mp):
        r.update(passed=False, reasons=["no manifest"]); print(json.dumps(r, ensure_ascii=False)); return 1
    m = json.load(open(mp, encoding="utf-8"))
    slot = (m.get("runs") or [{}])[0]
    v = slot.get("validation") or {}
    r.update(manifest_status=m.get("status"), halt_reason=m.get("halt_reason"), slot_status=slot.get("status"),
             valid=bool(v.get("valid")), failed_checks=v.get("failed_checks"))
    emerg = slot.get("status") == "emergency_aborted" or "emergency" in str(m.get("halt_reason") or "")
    r["emergency"] = emerg
    files = glob.glob(os.path.join(out_dir, "runs", "*", "gpu", "*.jsonl"))
    if len(files) != 1:
        r["reasons"].append(f"runner jsonl count {len(files)}")
    meta, ends = None, []
    if files:
        with open(files[0], encoding="utf-8") as fh:
            for line in fh:
                if '"inference"' in line and '"event":"inference"' in line.replace(" ", ""):
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("event") == "run_metadata" and meta is None:
                    meta = e
                elif e.get("event") == "segment_end":
                    ends.append(detail(e))
    segs = []
    cs = {c.get("index"): c for c in ((meta or {}).get("chain_segments") or []) if isinstance(c, dict)}
    for d in ends:
        i = d.get("index")
        c = cs.get(i, {})
        segs.append(dict(index=i, label=d.get("label"), termination_reason=d.get("termination_reason"), n=d.get("inference_count"),
                         model=d.get("model") or c.get("model"), model_sha256=c.get("model_sha256") or d.get("model_sha256"),
                         input_spec=c.get("input_spec") or d.get("input_spec")))
    r["segments"] = segs
    r["chain_id"] = (meta or {}).get("chain_id")
    r["run_id"] = (meta or {}).get("run_id")
    shas = {s["model_sha256"] for s in segs if s["model_sha256"]}
    if not r["valid"]:
        r["reasons"].append("slot not valid")
    if emerg:
        r["reasons"].append("emergency")
    if len(segs) != 2 and "smoke" in r["out_dir"]:
        r["reasons"].append(f"segments {len(segs)} != 2")
    for s in segs:
        if s["termination_reason"] != "duration_complete":
            r["reasons"].append(f"seg {s['index']} termination {s['termination_reason']}")
        if not s["n"]:
            r["reasons"].append(f"seg {s['index']} n=0")
        if s["input_spec"] != INPUT:
            r["reasons"].append(f"seg {s['index']} input_spec {s['input_spec']}")
    if shas - {EXP[res]}:
        r["reasons"].append(f"model sha differs {sorted(x[:8] for x in shas)}")
        r["sha_label"] = "다른 SHA"
    elif not shas:
        r["sha_label"] = "런에 SHA 없음 → 폰 파일 SHA 로 대신"
        if phone_sha != EXP[res]:
            r["reasons"].append(f"no sha in run and phone sha {str(phone_sha)[:8]} != expected")
    elif len(shas) == 1 and all(s["model_sha256"] for s in segs):
        r["sha_label"] = "런 메타 SHA 일치"
    else:
        r["sha_label"] = "일부 구간만 SHA (있는 것은 일치)"
    r["passed"] = not r["reasons"]
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
