"""M5 session validity — mixreq_validate.validate (9 rules, unchanged and imported) with ONE rule replaced for the state-split form.

  py -3 -X utf8 s26/tools/mixreq/statesplit_validate.py <session_dir> [--selftest] [--out validated.json]

S26-STATESPLIT-01 (등록 상태분리 v2 §1): the last requests arrive at 119.8 / 119.9 s, so the R3 window rule 3 ([35 s, 120 s) for dispatch and
lane_available) cannot hold by construction. Rule 3 is re-evaluated here as dispatch · lane_available ∈ [35 s, 150 s) (common window +
drain; a drain that does not finish already fails the session in the app). Rules 0 · 1 · 2 · 4 · 5 · 6 · 7 · 8 · 9 and the NPU contract
are the mixreq_validate results as they are (rule 5 = v2/v3: CPU overlap 0 is a condition, parallel overlap recorded). The request table
itself is checked against statesplit_common.requests (rule 3b, part of rule 3). Fixed before any measurement (freeze_statesplit.txt).
S26-SUSTAIN-ABBA-01 and every other experiment: mixreq_validate.validate unchanged (window [35, 720) for ABBA = -03 rule).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import mixreq_validate as V  # noqa: E402
import statesplit_common as S  # noqa: E402

SCHEMA_TAG = "statesplit-rule3-v1"


def validate(session_dir: Path, device_dir: Path | None, logcat: Path | None, skin_watch: Path | None, phone_watch: Path | None,
             selftest: bool) -> tuple[dict, dict | None]:
    validated, contract = V.validate(session_dir, device_dir, logcat, skin_watch, phone_watch, selftest)
    data = V.load_session(session_dir, device_dir)
    if data["missing"] or data["manifest"]["experiment_id"] not in (S.STATESPLIT_ID, S.STATESPLIT_SMOKE_ID):
        return validated, contract
    m = data["manifest"]
    scale = int(m.get("time_scale", 1))
    rows = data.get("requests") or []
    origin = (data.get("common_boundary") or {}).get("start_ns")
    lo, hi = S.WINDOW_S[0] * 1e9 / scale, S.WINDOW_S[1] * 1e9 / scale
    out_of_window = []
    if origin is not None:
        for r in rows:
            for k in ("dispatch_ns", "lane_available_ns"):
                if r.get(k) is None or not (lo <= int(r[k]) - int(origin) < hi):
                    out_of_window.append((r["request_id"], k))
    try:
        sid_table_ok = m["requests"] == S.requests(m["session_id"])
    except ValueError:
        sid_table_ok = False
    original = validated["rules"].get("3_window")
    validated["rules"]["3_window"] = dict(
        passed=origin is not None and bool(rows) and not out_of_window and sid_table_ok,
        detail=dict(origin_ns=origin, bounds_s=[lo / 1e9, hi / 1e9], violations=out_of_window[:10], request_table_matches_statesplit=sid_table_ok,
                    last_lane_available_s=max((int(r["lane_available_ns"]) - int(origin)) / 1e9 for r in rows if r.get("lane_available_ns")) if origin and rows else None,
                    rule=SCHEMA_TAG + ": dispatch · lane_available in [35 s, 150 s) (common 120 + drain 30)",
                    mixreq_rule3_result=dict(passed=(original or {}).get("passed"), bounds_s=((original or {}).get("detail") or {}).get("bounds_s"))))
    reasons = [name for name, r in validated["rules"].items() if not r["passed"]]
    if selftest and m.get("split") == "confirmation":
        reasons.append("selftest cannot judge a confirmation session")
    validated.update(eligible=not reasons, reasons=reasons, statesplit=dict(rule3=SCHEMA_TAG, registration=S.REGISTRATION_SS,
                                                                           analysis_split=m.get("analysis_split"), statesplit_block=m.get("statesplit_block"),
                                                                           letter=m.get("statesplit_letter")))
    return validated, contract


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session_dir", type=Path)
    ap.add_argument("--device-dir", type=Path)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--npu-out", type=Path)
    args = ap.parse_args()
    host = args.session_dir / "host"
    logcat = host / "logcat_threadtime.txt" if (host / "logcat_threadtime.txt").is_file() else None
    skin = host / "skin_watch.csv" if (host / "skin_watch.csv").is_file() else None
    phone = host / "phone_watch.csv" if (host / "phone_watch.csv").is_file() else None
    validated, contract = validate(args.session_dir, args.device_dir, logcat, skin, phone, args.selftest)
    C.write_json(args.out or args.session_dir / "validated.json", validated)
    if contract is not None:
        C.write_json(args.npu_out or args.session_dir / "npu_contract.json", contract)
    print(json.dumps(dict(eligible=validated.get("eligible"), reasons=validated.get("reasons"),
                          npu_contract=None if contract is None else contract.get("passed")), ensure_ascii=False))
    return 0 if validated.get("eligible") else 1


if __name__ == "__main__":
    sys.exit(main())
