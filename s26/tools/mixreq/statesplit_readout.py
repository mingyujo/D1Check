"""M5 readout = per-session JSON from mixreq_readout.read_session (imported, unchanged) + an inventory table. NO judgment, no J / AP /
state-wise values (등록 상태분리 v2 §2 · 지속감속 확인 v1 §2 are computed by Cowork).

  py -3 -X utf8 s26/tools/mixreq/statesplit_readout.py --plan <plan_dir>/plan.json --results <results root> --out <readout dir>

Writes <out>/sessions/<index>_<letter>_a<attempt>.json (read_session dict without the bulky manifest/rows/validated/host_log, plus the M5
labels: analysis_split · statesplit_block · letter · start band record) · <out>/inventory.csv · <out>/readout_index.json (slot status per
planned index: valid / invalid_twice / invalid_once / not_attempted — the R3 slot words). Sessions whose experiment_id differs from the
plan's are skipped (never mixed). For ABBA (kind sustained) read_session adds the (S)-6 sustained block as for -03.
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
import statesplit_common as S  # noqa: E402,F401  (registers the M5 experiment rows)
import mixreq_readout as R  # noqa: E402

FIELDS = ["index", "letter", "analysis_split", "statesplit_block", "policy", "block", "attempt", "eligible", "reasons", "start_time", "end_time",
          "start_band_result", "start_skin_band", "soc_at_precheck", "gate_skin", "urgent_p95_ms", "normal_p95_ms", "deadline_met", "completed",
          "overlap_s", "last_lane_available_s", "peak_skin_c", "peak_ap_c", "npu_contract", "folder"]


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
        letter = entry.get("letter") or m.get("statesplit_letter")
        label = f"index{m['session_index']:02d}"
        band = next((b for b in reversed(bands) if b.get("label") == label and b.get("attempt") == m["attempt"]), None)
        out = {k: v for k, v in s.items() if k not in ("validated", "manifest", "rows", "host_log")}
        out.update(experiment_id=m["experiment_id"], letter=letter, analysis_split=m.get("analysis_split"), statesplit_block=m.get("statesplit_block"),
                   manifest_sha256=s["host_log"].get("manifest_sha256"),
                   start_band=band, host_start_time=s["host_log"].get("start_time"), host_end_time=s["host_log"].get("end_time"),
                   apk_sha256=s["host_log"].get("apk_sha256"), gate=s["host_log"].get("gate"), validated_rules={k: v.get("passed") for k, v in s["validated"]["rules"].items()})
        C.write_json(args.out / "sessions" / f"{m['session_index']:02d}_{letter}_a{m['attempt']}.json", out)
        svc = s.get("service") or {}
        last_poll = (band or {}).get("polls", [{}])[-1] if band and band.get("polls") else {}
        row = dict(index=m["session_index"], letter=letter, analysis_split=m.get("analysis_split"), statesplit_block=m.get("statesplit_block"),
                   policy=m["policy"], block=m["block"], attempt=m["attempt"], eligible=s["eligible"], reasons=";".join(s["reasons"]),
                   start_time=s["host_log"].get("start_time"), end_time=s["host_log"].get("end_time"),
                   start_band_result=(band or {}).get("result"), start_skin_band=(band or {}).get("start_skin"), soc_at_precheck=last_poll.get("soc"),
                   gate_skin=(s["host_log"].get("gate") or {}).get("last"),
                   urgent_p95_ms=svc.get("urgent", {}).get("p95_ms"), normal_p95_ms=svc.get("normal", {}).get("p95_ms"),
                   deadline_met=svc.get("all", {}).get("deadline_met"), completed=svc.get("all", {}).get("completed"),
                   overlap_s=s.get("overlap_s"), last_lane_available_s=s.get("last_lane_available_s"),
                   peak_skin_c=(s.get("thermal") or {}).get("peak_skin"), peak_ap_c=(s.get("thermal") or {}).get("peak_ap"),
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
        slots[str(e["index"])] = dict(status=status, letter=e.get("letter"), policy=e["policy"], analysis_split=e.get("analysis_split"),
                                      attempts=[dict(attempt=r["attempt"], eligible=r["eligible"], reasons=r["reasons"]) for r in att])
    with open(args.out / "inventory.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["index"], r["attempt"])):
            w.writerow(r)
    index = dict(schema="s26-m5-readout-index-v1", plan=str(args.plan), plan_sha256=C.sha256_file(args.plan), experiment_id=plan["experiment_id"],
                 registration=plan.get("registration"), sessions=len(rows), skipped=skipped, slots=slots,
                 slot_counts={k: sum(1 for v in slots.values() if v["status"] == k) for k in ("valid", "invalid_twice", "invalid_once", "not_attempted")},
                 note="readout only — 계산 · 판정은 Cowork (등록 §2)")
    C.write_json(args.out / "readout_index.json", index)
    print(json.dumps(dict(sessions=len(rows), slot_counts=index["slot_counts"], skipped=len(skipped)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
