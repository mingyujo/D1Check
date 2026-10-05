"""NIGHT 1005e copy of s26/tools/s26_start_gate.py (unchanged file) - ONLY change: SOC upper 90 -> 100 (prereg night1005e s1, 21:5x amendment:
"SOC 30~100"). Absolute-temperature start gate (0927). Polls every 120 s until HAL SKIN<=32, AP<=32, BAT<=30, unplugged, SOC 30..100.
Usage: py start_gate.py <serial> <label> <logcsv>. Exit 0 when passed; prints wait time. Never charges, never loads."""
import csv, datetime, os, re, subprocess, sys, time

ADB = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
SERIAL, LABEL, LOG = sys.argv[1], sys.argv[2], sys.argv[3]


def state():
    th = subprocess.run([ADB, "-s", SERIAL, "shell", "dumpsys", "thermalservice"], capture_output=True, text=True, timeout=30).stdout
    hal = th.split("Current temperatures from HAL", 1)[1]
    t = {}
    for v, n in re.findall(r"mValue=([-\d.]+), mType=\d+, mName=(\w+)", hal):
        t.setdefault(n, float(v))
    st = int(re.search(r"Thermal Status:\s*(-?\d+)", th).group(1))
    b = subprocess.run([ADB, "-s", SERIAL, "shell", "dumpsys", "battery"], capture_output=True, text=True, timeout=30).stdout
    lvl = int(re.search(r"^\s*level:\s*(\d+)", b, re.M).group(1))
    plugged = bool(re.search(r"(AC|USB|Wireless|Dock) powered:\s*true", b))
    return t, st, lvl, plugged


t0 = time.time()
new = not os.path.exists(LOG)
with open(LOG, "a", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    if new:
        w.writerow(["label", "local_time", "waited_s", "SKIN", "AP", "BAT", "thermal_status", "soc", "plugged", "pass"])
    while True:
        t, st, lvl, plugged = state()
        ok = (not plugged and 30 <= lvl <= 100 and t["SKIN"] <= 32.0 and t["AP"] <= 32.0 and t["BAT"] <= 30.0)
        waited = round(time.time() - t0)
        row = [LABEL, datetime.datetime.now().isoformat(timespec="seconds"), waited, t["SKIN"], t["AP"], t["BAT"], st, lvl, plugged, ok]
        w.writerow(row); f.flush(); print(*row, flush=True)
        if ok:
            sys.exit(0)
        if plugged or lvl < 30 or lvl > 100:
            print("GATE_BLOCKED_NONTHERMAL", flush=True); sys.exit(2)
        time.sleep(120)
