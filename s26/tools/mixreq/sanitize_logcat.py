"""Sanitized logcat copy for sharing (M5, 2026-10-12, 영훈 "모든 파일 공유"): the raw logcat (git 밖) may contain iccid / eSIM / SIM /
carrier / radio lines and device identifiers. This writes <dst>/logcat_threadtime.sanitized.txt where
  * every line matching DROP_RE (SIM · eSIM · iccid · imsi · imei · msisdn · carrier · radio · telephony · wifi ssid/bssid) is removed
    (replaced by one placeholder line with the count at the end),
  * adb serials (R3KL…, adb-…_adb-tls-connect), IPv4[:port], IPv6 (incl. fe80) and MAC addresses are masked.
Evidence lines (D1MIX / D1Q1 / D1Q20 marks, litert, tflite, Dispatch, ENN) are kept unless they match DROP_RE.

  py -3 -X utf8 s26/tools/mixreq/sanitize_logcat.py <src logcat> <dst dir>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DROP_RE = re.compile(r"iccid|esim|euicc|\bsim\b|simcard|sim_state|gsm\.|ril\.|persist\.radio|imsi|imei|meid|msisdn|phone.?number|carrier|"
                     r"telephony|subscription|subinfo|plmn|mcc|mnc|operator|radio|ssid|bssid|wpa_|wificond|wifi.*scan|location|gps|\beid\b",
                     re.IGNORECASE)
MASKS = [
    (re.compile(r"R3KL[0-9A-Z]{7}"), "<SERIAL>"),
    (re.compile(r"adb-[A-Za-z0-9_-]+\._adb-tls-connect\._tcp"), "<SERIAL>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{2,5})?\b"), "<IP>"),
    (re.compile(r"\bfe80[:][0-9a-fA-F:]*(?:%\w+)?", re.IGNORECASE), "<IPV6>"),   # not hh:mm:ss timestamps
    (re.compile(r"\b[23][0-9a-fA-F]{3}:(?:[0-9a-fA-F]{0,4}:){2,6}[0-9a-fA-F]{1,4}\b"), "<IPV6>"),
    (re.compile(r"\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b"), "<MAC>"),
]


def main() -> int:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    dropped = 0
    with open(src, encoding="utf-8", errors="replace") as fin, open(dst / "logcat_threadtime.sanitized.txt", "w", encoding="utf-8", newline="\n") as fout:
        for line in fin:
            if DROP_RE.search(line):
                dropped += 1
                continue
            for rx, rep in MASKS:
                line = rx.sub(rep, line)
            fout.write(line.rstrip("\r\n") + "\n")
        fout.write(f"### sanitized copy: {dropped} lines removed (SIM / carrier / radio / wifi / location patterns); serial · IP · MAC masked\n")
    print(dst.name, "dropped", dropped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
