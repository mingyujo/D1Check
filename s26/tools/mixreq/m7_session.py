"""M7 one session = m6_session.main() unchanged, with the M7 tables activated first (m7_common.activate(): m6_common.P_ORDER = M6 + M7 rows ·
registration = M7 v2 — so validated.json / start records carry the M7 registration; index 12..51 (P) · 4..18 (K) come from the plan manifests).

  set ANDROID_SERIAL=<ip:port>
  py -3 -X utf8 s26/tools/mixreq/m7_session.py --plan <plan_m7p|plan_m7prep|plan_m7k|plan_m7s> (--index i | --smoke name) --results <root>
      --runlog <runs.jsonl> [--label ..] [--attempt 1|2] [--legacy-validate (S · S7 regression)] [--skip-precheck --skip-gate (K after B/C prep)] ...
Exit codes = m6_session (0 valid · 1 invalid · 2 gate · 3 device · 4 stall · 5 folder exists · 6 charge needed · 7 locked · 8 SOC > max).
m6_session.py · mixreq_session.py · m6_validate.py · mixreq_validate.py are not modified.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m7_common  # noqa: E402
import m6_session  # noqa: E402

if __name__ == "__main__":
    m7_common.activate()
    sys.exit(m6_session.main())
