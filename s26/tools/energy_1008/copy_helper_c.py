"""copy_helper_c.py - P1i (energy C 1008): copy a P1h v3b helper to energy_1008 with exact
string replacements only. Usage: py copy_helper_c.py <src> <dst> <header> [old=>new ...]
Bytes are kept (BOM, CRLF); every replacement must match at least once or it fails."""
import sys

src, dst, header = sys.argv[1], sys.argv[2], sys.argv[3]
reps = [a.split("=>", 1) for a in sys.argv[4:]]
b = open(src, "rb").read()
bom = b.startswith(b"\xef\xbb\xbf")
t = b[3:].decode("utf-8") if bom else b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
for old, new in reps:
    n = t.count(old)
    if n == 0:
        sys.exit(f"NO MATCH: {old!r}")
    t = t.replace(old, new)
    print(f"replaced {n}x: {old!r} -> {new!r}")
t = "# " + header + nl + t
out = (b"\xef\xbb\xbf" if bom else b"") + t.encode("utf-8")
open(dst, "wb").write(out)
print(f"wrote {dst} ({len(out)} B, bom={bom})")
