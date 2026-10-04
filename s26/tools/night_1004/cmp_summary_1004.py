"""Compact per-block verdict summary of cmp_all.json (read-only) — for the holdout document."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
c = json.load(open(sys.argv[1], encoding="utf-8"))
print("measured:", c["measured"])
print("notes:", c["notes"])


def short(b):
    return " | ".join(f"{r['cell'][:22]}={r['verdict'].split(' (')[0]}" for r in b["rows"] if r["verdict"] != "—")


for grp in ("v2", "v1"):
    for chain in ("n50p", "g50p", "gi300", "ni300"):
        for var, b in (c[grp].get(chain) or {}).items():
            k = b["counts"]
            print(f"{grp:3s} {chain:6s} {var:11s} col={b['column']:16s} sup={b['supported']} 맞음={k.get('맞음',0)} 틀림={k.get('틀림',0)} 미확인={k.get('미확인',0)} 판정불가={k.get('판정 불가',0)}")
for form, byc in c["reference_forms"].items():
    for chain in ("n50p", "g50p", "gi300", "ni300"):
        for var, b in (byc.get(chain) or {}).items():
            k = b["counts"]
            print(f"ref {form:24s} {chain:6s} {var:10s} 맞음={k.get('맞음',0)} 틀림={k.get('틀림',0)} 미확인={k.get('미확인',0)}")
# totals
for grp in ("v2", "v1"):
    tot = {}
    for chain, by in c[grp].items():
        for var, b in by.items():
            t = tot.setdefault(var, [0, 0, 0])
            t[0] += b["counts"].get("맞음", 0); t[1] += b["counts"].get("틀림", 0); t[2] += b["counts"].get("미확인", 0)
    print(grp, "TOTAL", tot)
tot = {}
for form, byc in c["reference_forms"].items():
    for chain, by in byc.items():
        for var, b in by.items():
            t = tot.setdefault(f"{form}/{var}", [0, 0, 0])
            t[0] += b["counts"].get("맞음", 0); t[1] += b["counts"].get("틀림", 0); t[2] += b["counts"].get("미확인", 0)
print("ref TOTAL", tot)
