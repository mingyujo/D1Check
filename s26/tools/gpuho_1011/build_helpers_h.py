"""build_helpers_h.py — GH (1011) 3단계-5: make the s26/tools/gpuho_1011 operation helpers from the energy-C (P1i) helpers with EXACT string
replacements only (copy_helper_c.py method: bytes kept — BOM, CRLF; every replacement must match at least once), and install the
session driver / restore script written by this session with UTF-8 BOM + CRLF (PowerShell 5.1 reads BOM-less .ps1 with Korean paths as cp949).
  py -X utf8 build_helpers_h.py <scratch_dir_with_session_driver_h.ps1> <GBh canonical sha256>
"""
import os
import sys

REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
SRC = os.path.join(REPO, "s26", "tools", "energy_1008")
DST = os.path.join(REPO, "s26", "tools", "gpuho_1011")
scratch, canon = sys.argv[1], sys.argv[2]
assert len(canon) == 64
os.makedirs(DST, exist_ok=True)


def copy_replace(src_name, dst_name, header, reps):
    b = open(os.path.join(SRC, src_name), "rb").read()
    bom = b.startswith(b"\xef\xbb\xbf")
    t = b[3:].decode("utf-8") if bom else b.decode("utf-8")
    nl = "\r\n" if "\r\n" in t else "\n"
    for old, new in reps:
        n = t.count(old)
        if n == 0:
            sys.exit(f"NO MATCH in {src_name}: {old!r}")
        t = t.replace(old, new)
        print(f"  {src_name}: replaced {n}x {old!r} -> {new!r}")
    t = "# " + header + nl + t
    out = (b"\xef\xbb\xbf" if bom else b"") + t.encode("utf-8")
    open(os.path.join(DST, dst_name), "wb").write(out)
    print(f"wrote {dst_name} ({len(out)} B, bom={bom})")


HDR = "GPU holdout (GH 1011) copy of s26\\tools\\energy_1008\\{} - changed only: host dir S26_host_gpuho_1011 . csv / stop / log names *_h . helper names *_h (logic unchanged)."
HOST = ("S26_host_energy_1008", "S26_host_gpuho_1011")
copy_replace("run_cell_c.ps1", "run_cell_h.ps1", HDR.format("run_cell_c.ps1"),
             [HOST, ('$T6 = "$wd\\s26\\tools\\energy_1008"', '$T6 = "$wd\\s26\\tools\\gpuho_1011"'), ("stall_watch_c.ps1", "stall_watch_h.ps1"), ("gate_log_c.csv", "gate_log_h.csv"),
              ("gate_upper_raw_c.csv", "gate_upper_raw_h.csv"), ("dryrun_c.ps1", "dryrun_h.ps1"), ("launch_cell_c.ps1", "launch_cell_h.ps1"), ("adb_state_c.csv", "adb_state_h.csv")])
copy_replace("launch_cell_c.ps1", "launch_cell_h.ps1", HDR.format("launch_cell_c.ps1"), [HOST])
copy_replace("dryrun_c.ps1", "dryrun_h.ps1", HDR.format("dryrun_c.ps1"), [HOST])
copy_replace("stall_watch_c.ps1", "stall_watch_h.ps1", HDR.format("stall_watch_c.ps1"), [("# Energy C (P1i 1008) copy of v3_1006\\stall_watch_v3b.ps1 - changed only: this header line (functions identical).", "# (functions identical to energy_1008\\stall_watch_c.ps1)")])
copy_replace("keepawake_c.ps1", "keepawake_h.ps1", HDR.format("keepawake_c.ps1"), [HOST, ("keepawake_c.stop", "keepawake_h.stop"), ("keepawake_c_log.txt", "keepawake_h_log.txt")])
copy_replace("keepawake_c_screen.ps1", "keepawake_h_screen.ps1", HDR.format("keepawake_c_screen.ps1"), [HOST, ("keepawake_c_screen.stop", "keepawake_h_screen.stop"), ("keepawake_c_screen_log.txt", "keepawake_h_screen_log.txt")])
copy_replace("start_watch_c.ps1", "start_watch_h.ps1", HDR.format("start_watch_c.ps1"), [HOST, ("skin_watch_c.csv", "skin_watch_h.csv"), ("phone_watch_c.csv", "phone_watch_h.csv"), ("host_pids_c.txt", "host_pids_h.txt")])
copy_replace("phone_read_c.ps1", "phone_read_h.ps1", HDR.format("phone_read_c.ps1"), [HOST, ("phone_settings_log_c.txt", "phone_settings_log_h.txt"), ("P1i stage 0-5", "GH stage 0 / 4-1")])
copy_replace("stall_selftest_c.ps1", "stall_selftest_h.ps1", HDR.format("stall_selftest_c.ps1"), [HOST, ("stall_watch_c.ps1", "stall_watch_h.ps1")])

# driver · restore written by this session -> BOM + CRLF, GBh canonical filled
for name in ("session_driver_h.ps1", "restore_h.ps1"):
    t = open(os.path.join(scratch, name), "rb").read().decode("utf-8")
    t = t.replace("__GBH_CANONICAL__", canon)
    assert "__GBH_CANONICAL__" not in t
    t = t.replace("\r\n", "\n").replace("\n", "\r\n")
    out = b"\xef\xbb\xbf" + t.encode("utf-8")
    open(os.path.join(DST, name), "wb").write(out)
    print(f"wrote {name} ({len(out)} B, bom=True, crlf)")
print("done")
