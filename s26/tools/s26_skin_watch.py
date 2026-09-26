"""Host-side safety watcher for C1-probe: log SKIN/AP/BAT/status every 15 s; SKIN >= 45.0 -> force-stop runner."""
import csv, datetime, os, re, subprocess, sys, time

ADB = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
SERIAL, OUT, STOPFILE = sys.argv[1], sys.argv[2], sys.argv[3]
LIMIT = 45.0
PKG = "com.example.d1check.benchmarkrunner"


def sample():
    txt = subprocess.run([ADB, "-s", SERIAL, "shell", "dumpsys", "thermalservice"],
                         capture_output=True, text=True, timeout=20).stdout
    st = re.search(r"Thermal Status:\s*(-?\d+)", txt)
    sec = txt.split("Current temperatures from HAL", 1)[-1]
    sec = re.split(r"Current cooling devices", sec, 1)[0]
    vals = {}
    for v, name in re.findall(r"mValue=([-\d.]+), mType=\d+, mName=(\w+)", sec):
        vals.setdefault(name, float(v))
    bat = subprocess.run([ADB, "-s", SERIAL, "shell", "dumpsys battery | grep -E ' level:|powered:'"],
                         capture_output=True, text=True, timeout=20).stdout
    lvl = re.search(r"level:\s*(\d+)", bat)
    return (int(st.group(1)) if st else None, vals, int(lvl.group(1)) if lvl else None,
            bool(re.search(r"(AC|USB|Wireless) powered:\s*true", bat)))


new = not os.path.exists(OUT)
with open(OUT, "a", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    if new:
        w.writerow(["local_time", "thermal_status", "SKIN", "AP", "BAT", "battery_level", "any_powered", "action"])
    while not os.path.exists(STOPFILE):
        try:
            status, v, lvl, powered = sample()
            action = ""
            if v.get("SKIN") is not None and v["SKIN"] >= LIMIT:
                subprocess.run([ADB, "-s", SERIAL, "shell", "am", "force-stop", PKG], timeout=20)
                action = f"FORCE_STOP_SKIN_GE_{LIMIT}"
            w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), status, v.get("SKIN"), v.get("AP"),
                        v.get("BAT"), lvl, powered, action])
            f.flush()
        except Exception as e:  # keep watching
            w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), "", "", "", "", "", "", f"ERR {e!r}"])
            f.flush()
        time.sleep(15)
