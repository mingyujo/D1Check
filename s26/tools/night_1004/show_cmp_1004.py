"""Print a night1004_judge cmp output as compact tables (read-only)."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
c = json.load(open(sys.argv[1], encoding="utf-8"))
only = sys.argv[2] if len(sys.argv) > 2 else None


def f(x):
    if isinstance(x, float):
        return round(x, 3)
    if isinstance(x, list):
        return [f(v) for v in x]
    if isinstance(x, dict):
        return {k: f(v) for k, v in x.items() if k not in ("dt_s", "status")}
    return x


print("notes:", c["notes"])
print("measured:", c["measured"])
for grp in ("v2", "v1"):
    for chain, by in c[grp].items():
        if only and chain != only:
            continue
        for var, b in by.items():
            print(f"\n=== {grp} {chain} {var} col={b['column']} start={b['start_skin']} supported={b['supported']} counts={b['counts']}")
            for r in b["rows"]:
                print(f"  {r['cell']}: pred={f(r['predicted'])} | meas={f(r['measured'])} | {r['criterion']} | {r['verdict']}")
for form, byc in c["reference_forms"].items():
    for chain, by in byc.items():
        if only and chain != only:
            continue
        for var, b in by.items():
            short = [(r["cell"][:18], r["verdict"].split(" (")[0]) for r in b["rows"] if r["verdict"] != "—"]
            print(f"\n--- ref {form} {chain} {var} counts={b['counts']} :: {short}")
