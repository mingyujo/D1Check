"""M8 one session = m6_session.main() unchanged, with the M8 tables activated (m8_common.activate(): experiment rows · block NONE · USED_KEYS · session cap · SOC band = 영훈 운영 결정)
and the validator replaced by m8_validate (contract M8 rules A0 ~ A10). m6_session.py · mixreq_session.py · m6_validate.py · mixreq_validate.py are not modified.

  set ANDROID_SERIAL=<ip:port>
  py -3 -X utf8 s26/tools/mixreq/m8_session.py --plan s26/results/m8_prep/plan_m8m128 (--index i | --smoke name) --results <root> --runlog <runs.jsonl>
      --label <run label> --skin-band 0,100 --band-wait-s 0 [--attempt 1|2] [--hal-cont <csv>] ...
Start-band wait is replaced by the M8 host gate (m8_gate.py · Tref) — pass --skin-band 0,100 so the M6 precheck only checks SOC (≥ 20) · plugged · lock.
Exit codes = m6_session (0 valid · 1 invalid · 2 gate · 3 device · 4 stall · 5 folder exists · 6 charge needed · 7 locked · 8 SOC > max).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m8_common  # noqa: E402
import m6_session  # noqa: E402
import m8_validate  # noqa: E402
import mixreq_validate as V  # noqa: E402


def main() -> int:
    m8_common.activate()
    hal_cont = None
    argv = sys.argv[1:]
    if "--hal-cont" in argv:
        i = argv.index("--hal-cont")
        hal_cont = Path(argv[i + 1])
        del argv[i:i + 2]
        sys.argv = [sys.argv[0]] + argv

    def validate(session_dir, device_dir, logcat, skin_watch, phone_watch, selftest):
        return m8_validate.validate(session_dir, device_dir, logcat, skin_watch, phone_watch, selftest, hal_cont)

    m6_session.MV = types.SimpleNamespace(validate=validate)   # m6_session.patch_session reads MV.validate (M6 → M8 validator)
    m6_session.V = V
    return m6_session.main()


if __name__ == "__main__":
    sys.exit(main())
