"""M6 readout = per-session JSON from mixreq_readout.read_session (imported, unchanged) + an inventory table. NO judgment, no J / 열 /
policy comparison (등록 M6 v3 §3-7 · §4-5 · §6: computed by 조민규 / Cowork).

  py -3 -X utf8 s26/tools/mixreq/m6_readout.py --plan <plan_dir>/plan.json --results <results root> --out <readout dir>

Writes <out>/sessions/<index>_<label>_a<attempt>.json (read_session dict without the bulky manifest/rows/validated/host_log, plus the M6
labels: analysis_split · m6_load · m6_letter · m6_run · start band record · in_block_charge) · <out>/inventory.csv · <out>/readout_index.json
(slot status per planned index: valid / invalid_twice / invalid_once / not_attempted). Sessions whose experiment_id differs from the plan's
are skipped (never mixed).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import m6_common as M  # noqa: E402,F401  (registers the M6 experiment rows · block M)
import mixreq_readout as R  # noqa: E402

FIELDS = ["index", "label", "analysis_split", "load", "letter", "policy", "block", "attempt", "eligible", "reasons", "start_time", "end_time",
          "start_band_result", "start_skin_band", "soc_at_precheck", "in_block_charge", "gate_skin", "urgent_p95_ms", "normal_p95_ms", "deadline_met",
          "completed", "overlap_s", "last_lane_available_s", "npu_contract", "folder"]


def band_records(results: Path) -> list[dict]:
    p = results / "start_band.jsonl"
    if not p.is_file():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    plan = C.read_json(args.plan)
    bands = band_records(args.results)
    (args.out / "sessions").mkdir(parents=True, exist_ok=True)
    rows, skipped, by_index = [], [], {}
    for folder in sorted(p for p in args.results.iterdir() if p.is_dir()):
        s = R.read_session(folder, args.selftest)
        if s is None:
            skipped.append(f"{folder.name}: no validated.json")
            continue
        m = s["manifest"]
        if m["experiment_id"] != plan["experiment_id"]:
            skipped.append(f"{folder.name}: experiment_id {m['experiment_id']} != plan {plan['experiment_id']}")
            continue
        entry = next((e for e in plan["sessions"] if e["index"] == m["session_index"]), {})
        label = m.get("m6_run") or (f"{m.get('m6_load')}-{m.get('m6_letter')}" if m.get("m6_load") else entry.get("letter"))
        band_label = f"index{m['session_index']:02d}"
        band = next((b for b in reversed(bands) if b.get("label") == band_label and b.get("attempt") == m["attempt"]), None)
        out = {k: v for k, v in s.items() if k not in ("validated", "manifest", "rows", "host_log")}
        out.update(experiment_id=m["experiment_id"], label=label, analysis_split=m.get("analysis_split"), m6_load=m.get("m6_load"),
                   m6_letter=m.get("m6_letter"), m6_run=m.get("m6_run"), manifest_sha256=s["host_log"].get("manifest_sha256"),
                   start_band=band, in_block_charge=(band or {}).get("in_block_charge"), host_start_time=s["host_log"].get("start_time"),
                   host_end_time=s["host_log"].get("end_time"), apk_sha256=s["host_log"].get("apk_sha256"), gate=s["host_log"].get("gate"),
                   validated_rules={k: v.get("passed") for k, v in s["validated"]["rules"].items()},
                   mixreq_rules=s["validated"].get("mixreq_rules"))
        C.write_json(args.out / "sessions" / f"{m['session_index']:02d}_{label}_a{m['attempt']}.json", out)
        svc = s.get("service") or {}
        last_poll = (band or {}).get("polls", [{}])[-1] if band and band.get("polls") else {}
        row = dict(index=m["session_index"], label=label, analysis_split=m.get("analysis_split"), load=m.get("m6_load"), letter=m.get("m6_letter"),
                   policy=m["policy"], block=m["block"], attempt=m["attempt"], eligible=s["eligible"], reasons=";".join(s["reasons"]),
                   start_time=s["host_log"].get("start_time"), end_time=s["host_log"].get("end_time"),
                   start_band_result=(band or {}).get("result"), start_skin_band=(band or {}).get("start_skin"), soc_at_precheck=last_poll.get("soc"),
                   in_block_charge=(band or {}).get("in_block_charge"), gate_skin=(s["host_log"].get("gate") or {}).get("last"),
                   urgent_p95_ms=svc.get("urgent", {}).get("p95_ms"), normal_p95_ms=svc.get("normal", {}).get("p95_ms"),
                   deadline_met=svc.get("all", {}).get("deadline_met"), completed=svc.get("all", {}).get("completed"),
                   overlap_s=s.get("overlap_s"), last_lane_available_s=s.get("last_lane_available_s"),
                   npu_contract=(s.get("contract") or {}).get("passed"), folder=folder.name)
        rows.append(row)
        by_index.setdefault(m["session_index"], []).append(row)
    slots = {}
    for e in plan["sessions"]:
        att = sorted(by_index.get(e["index"], []), key=lambda r: r["attempt"])
        if any(r["eligible"] for r in att):
            status = "valid"
        elif len(att) >= 2:
            status = "invalid_twice"
        elif len(att) == 1:
            status = "invalid_once"
        else:
            status = "not_attempted"
        slots[str(e["index"])] = dict(status=status, letter=e.get("letter"), load=e.get("load"), policy=e["policy"], analysis_split=e.get("analysis_split"),
                                      attempts=[dict(attempt=r["attempt"], eligible=r["eligible"], reasons=r["reasons"]) for r in att])
    with open(args.out / "inventory.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["index"], r["attempt"])):
            w.writerow(r)
    index = dict(schema="s26-m6-readout-index-v1", plan=str(args.plan), plan_sha256=C.sha256_file(args.plan), experiment_id=plan["experiment_id"],
                 registration=plan.get("registration"), sessions=len(rows), skipped=skipped, slots=slots,
                 slot_counts={k: sum(1 for v in slots.values() if v["status"] == k) for k in ("valid", "invalid_twice", "invalid_once", "not_attempted")},
                 note="readout only — J · 열 · 정책 비교 계산 안 함 (조민규 / Cowork)")
    C.write_json(args.out / "readout_index.json", index)
    print(json.dumps(dict(sessions=len(rows), slot_counts=index["slot_counts"], skipped=len(skipped)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
