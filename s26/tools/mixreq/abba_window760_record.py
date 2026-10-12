"""ABBA record-only re-validation (영훈 결정 2026-10-12 11:2x, AFTER the a1 result, BEFORE the a2 result): if the slot is invalid twice,
keep the registered outcome (invalid_twice · 판정 밖) and ALSO write validated_window760.json = mixreq_validate.validate (9 rules, unchanged)
with rule 3 re-evaluated on [35 s, 760 s). Tag: "결과 뒤 · 영훈 결정 · 판정 밖 기록". Never used as a judgment input.

  py -3 -X utf8 s26/tools/mixreq/abba_window760_record.py <session folder> [<session folder> ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import statesplit_common as S  # noqa: E402,F401
import mixreq_validate as V  # noqa: E402

TAG = "결과 뒤 · 영훈 결정 · 판정 밖 기록"
HI_S = 760.0


def main() -> int:
    for folder in map(Path, sys.argv[1:]):
        host = folder / "host"
        validated, _ = V.validate(folder, None, host / "logcat_threadtime.txt", host / "skin_watch.csv", host / "phone_watch.csv", False)
        data = V.load_session(folder, None)
        origin = (data.get("common_boundary") or {}).get("start_ns")
        rows = data.get("requests") or []
        lo, hi = C.WINDOW_START_S * 1e9, HI_S * 1e9
        bad = [(r["request_id"], k) for r in rows for k in ("dispatch_ns", "lane_available_ns")
               if r.get(k) is None or not (lo <= int(r[k]) - int(origin) < hi)] if origin is not None else ["no origin"]
        registered = validated["rules"]["3_window"]
        validated["rules"]["3_window"] = dict(passed=origin is not None and bool(rows) and not bad,
                                              detail=dict(bounds_s=[C.WINDOW_START_S, HI_S], violations=bad[:10], registered_rule3=registered))
        reasons = [k for k, r in validated["rules"].items() if not r["passed"]]
        validated.update(eligible_window760=not reasons, reasons_window760=reasons, eligible=None, record_only=TAG,
                         note="registered result = validated.json (invalid); this file is a record, not a judgment input")
        C.write_json(folder / "validated_window760.json", validated)
        print(folder.name, "window760 eligible:", not reasons, reasons)
    return 0


if __name__ == "__main__":
    sys.exit(main())
