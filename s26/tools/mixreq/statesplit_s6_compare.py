"""M5 S6 regression record: a session of the new APK on an existing manifest vs an R3 session of the same policy — contract keys and
phase columns (record only, no judgment). Prints urgent P95 (prompt M5 v3 3-3: near 74 ~ 80 ms for B2, else stop and report).

  py -3 -X utf8 s26/tools/mixreq/statesplit_s6_compare.py --new <session folder> --ref <R3 session folder> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import mixreq_readout as R  # noqa: E402


def shape(folder: Path) -> dict:
    d = folder / "device"
    rows = C.read_json(d / "requests.json")
    summary = C.read_json(d / "summary.json")
    events = [json.loads(l) for l in (d / "progress.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    result = C.read_json(next(d.glob("*.result.json")))
    phases = [e.get("phase") for e in events if e.get("kind") == "phase_start"]
    return dict(request_row_keys=sorted({k for r in rows for k in r}), summary_keys=sorted(summary), result_keys=sorted(result),
                event_kinds=sorted({e["kind"] for e in events}), phase_order=phases,
                power_sample_keys=sorted({k for e in events if e.get("kind") == "power_sample" for k in e}),
                files=sorted({p.name for p in d.iterdir() if not p.name.endswith((".event.json", ".result.json"))}))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--new", required=True, type=Path)
    ap.add_argument("--ref", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    n, r = shape(a.new), shape(a.ref)
    same = {k: n[k] == r[k] for k in n}
    diff = {k: dict(only_new=sorted(set(n[k]) - set(r[k])), only_ref=sorted(set(r[k]) - set(n[k]))) for k in n if n[k] != r[k] and k != "phase_order"}
    s = R.read_session(a.new, False)
    rs = R.read_session(a.ref, False)
    out = dict(schema="s26-m5-s6-regression-v1", new=str(a.new), ref=str(a.ref), same=same, differences=diff,
               phase_order_new=n["phase_order"], phase_order_ref=r["phase_order"],
               new_service=s.get("service"), ref_service=rs.get("service"), new_eligible=s["eligible"], new_reasons=s["reasons"],
               new_lane_service_ms=s.get("lane_service_ms"), ref_lane_service_ms=rs.get("lane_service_ms"),
               new_apk=s["host_log"].get("apk_sha256"), ref_apk=rs["host_log"].get("apk_sha256"))
    C.write_json(a.out, out)
    print(json.dumps(dict(same=same, differences=diff, new_eligible=s["eligible"], new_reasons=s["reasons"],
                          urgent_p95_new=s["service"]["urgent"]["p95_ms"], urgent_p95_ref=rs["service"]["urgent"]["p95_ms"],
                          deadline_new=s["service"]["all"]["deadline_met"]), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
