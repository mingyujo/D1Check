"""M6-B confirmation bundle (프롬프트 M6-B 4단계) — copy, sanitize, tables, SHA256SUMS, zip. No calculation (J · 열 · 정책 비교 없음).

  py -3 -X utf8 s26/tools/mixreq/m6b_confirm_bundle.py --results results --repo-results s26/results/m6_1012 --onedrive <D1_ondevice>
      --stage <dir> --zip <D1_ondevice>/sim/out_m6/m6_confirm_bundle.zip --installed-apk-sha <sha>

Contents: S6 regression (results/S26_M6B_S6) · P confirm idx 06..11 (every attempt folder incl. invalid / _pre) · K3 · K4 (plan_m6k idx 02 · 03)
· block-level logs of S26_M6_P / S26_M6_K (driver log · state · start_band · awake · screen_timeout · gate log) · confirm readouts · run log ·
keepawake log · plans (plan.json · manifests idx 06..11 / K 02 · 03 · projection) · registration v3 · CONFIRMATION_FREEZE.json · ledger copy ·
session_table_confirm.csv · apk_manifest_session_map.csv · SHA256SUMS.
Same rules as m6_bundle.py (M6-A): raw logcat_threadtime.txt never copied (sanitized only) · *.apk / watch.stop skipped · every text file scanned for
the commit PAT (IPv4 with port · adb serial · IPv6 link-local) and the zip is refused if any hit remains.
analysis_split = "confirm" (P idx 6..11 · K3 · K4) / "regression" (S6) — separate from the legacy device field split = "confirmation".
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from m6_bundle import PAT, TEXT_EXT, copy_tree, jsonl, sha256  # noqa: E402

P_IDX = (6, 7, 8, 9, 10, 11)
K_IDX = (2, 3)
FIELDS = ["kind", "idx", "label", "load", "rule", "policy", "attempt", "eligible", "reasons", "analysis_split", "start_time", "end_time",
          "start_SKIN", "start_AP", "start_BAT", "start_SOC", "band_result", "brightness", "brightness_mode", "airplane", "zen_mode", "screen_off_timeout",
          "wakefulness", "keyguard_showing", "device_locked", "focus_apps", "focus_non_session_rows", "previous_run", "previous_end", "gap_s",
          "in_block_charge", "room_temp_c", "folder"]
MAP_FIELDS = ["kind", "idx", "label", "attempt", "analysis_split", "session_id", "manifest_sha256_plan", "manifest_sha256_pushed", "installed_apk_sha256",
              "session_apk_sha256", "plan_sha256", "projection_sha256", "folder"]


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def session_folders(root: Path, idxs) -> list[Path]:
    out = []
    for i in idxs:
        out += sorted(p for p in root.glob(f"S26_MIXREQ_{i:02d}_*") if p.is_dir())
    return out


def focus_info(host: Path) -> tuple[str, int]:
    f = host / "phone_watch.csv"
    if not f.is_file():
        return "", 0
    apps, other = set(), 0
    with open(f, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            foc = (r.get("focus") or "").split("/")[0]
            if foc:
                apps.add(foc)
                if foc != "com.example.d1check.requestrunner":
                    other += 1
    return ";".join(sorted(apps)), other


def row_for(kind: str, folder: Path, root: Path, plan: dict, plan_sha: str, label_of) -> tuple[dict, dict]:
    host = folder / "host"
    log = load(host / "session_log.json")
    man = load(host / "manifest_pushed.json")
    v = load(folder / "validated.json")
    idx, attempt = man.get("session_index"), man.get("attempt")
    if idx is None:
        m = re.match(r"S26_MIXREQ_(\d+)_.*_a(\d)", folder.name)
        idx, attempt = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    sess = next((s for s in plan.get("sessions", []) if s["index"] == idx), {})
    bands = jsonl(root / "start_band.jsonl")
    band = next((b for b in reversed(bands) if b.get("label") == f"index{idx:02d}" and b.get("attempt") == attempt), {}) if idx is not None else {}
    start = band.get("start") or (band.get("polls") or [{}])[-1]
    prev = band.get("previous_run") or {}
    st = log.get("start_time")
    gap = round((dt.datetime.fromisoformat(st) - dt.datetime.fromisoformat(prev["t"])).total_seconds()) if st and prev.get("t") else None
    label = label_of(idx)
    aw = next((a for a in reversed(jsonl(root / "awake.jsonl")) if a.get("label") == label and (not st or a.get("t", "") <= st)), {})
    first = aw.get("first") or {}
    sb = log.get("settings_before") or {}
    apps, other = focus_info(host)
    split = "regression" if kind == "S6" else (sess.get("analysis_split") or "confirm")
    row = dict(kind=kind, idx=idx, label=label, load=sess.get("load"), rule=sess.get("letter"), policy=sess.get("policy") or man.get("policy"),
               attempt=attempt, eligible=v.get("eligible"), reasons=";".join(v.get("reasons") or []), analysis_split=split, start_time=st,
               end_time=log.get("end_time"), start_SKIN=start.get("SKIN"), start_AP=start.get("AP"), start_BAT=start.get("BAT"), start_SOC=start.get("soc"),
               band_result=band.get("result"), brightness=sb.get("brightness", start.get("brightness")),
               brightness_mode=sb.get("brightness_mode", start.get("brightness_mode")), airplane=sb.get("airplane"), zen_mode=sb.get("zen_mode"),
               screen_off_timeout=sb.get("screen_off_timeout"), wakefulness=first.get("wakefulness"), keyguard_showing=first.get("keyguard_showing"),
               device_locked=first.get("device_locked"), focus_apps=apps, focus_non_session_rows=other, previous_run=prev.get("label"),
               previous_end=prev.get("t"), gap_s=gap, in_block_charge=band.get("in_block_charge"), room_temp_c="미기록",
               folder=f"{root.name}/{folder.name}")
    mp = dict(kind=kind, idx=idx, label=label, attempt=attempt, analysis_split=split, session_id=sess.get("session_id") or man.get("session_id"),
              # S6 = legacy plan_v3c: its plan manifest_sha256 is not the pushed-manifest hash (different scheme) -> pushed SHA only
              manifest_sha256_plan=None if kind == "S6" else sess.get("manifest_sha256"), manifest_sha256_pushed=log.get("manifest_sha256"), installed_apk_sha256=None,
              session_apk_sha256=log.get("apk_sha256"), plan_sha256=plan_sha, projection_sha256=sess.get("projection_sha256"), folder=row["folder"])
    return row, mp


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--repo-results", required=True, type=Path)
    ap.add_argument("--onedrive", required=True, type=Path)
    ap.add_argument("--stage", required=True, type=Path)
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--installed-apk-sha", required=True)
    ap.add_argument("--s6-plan", type=Path, default=Path("s26/results/mixreq_1008/plan_v3c"))
    args = ap.parse_args()
    if args.stage.exists():
        raise SystemExit(f"stage exists: {args.stage}")
    st, res, rr = args.stage, args.results, args.repo_results
    (st / "docs").mkdir(parents=True)
    shutil.copy2(args.onedrive / "sim" / "M6_동일APK_사전등록_v3.md", st / "docs" / "M6_동일APK_사전등록_v3.md")
    shutil.copy2(args.onedrive / "sim" / "out_m6" / "CONFIRMATION_FREEZE_조민규_1013.json", st / "docs" / "CONFIRMATION_FREEZE.json")
    shutil.copy2(args.onedrive / "sim" / "out_m6" / "freeze_m6.txt", st / "docs" / "M6_LEDGER.txt")
    plans = {}
    for name, idxs in (("plan_m6p", P_IDX), ("plan_m6k", K_IDX)):
        src = rr / name
        (st / name / "manifests").mkdir(parents=True)
        for f in ("plan.json", "plan_sha256.txt", "projection.json", "device_inputs.json"):
            if (src / f).is_file():
                shutil.copy2(src / f, st / name / f)
        for i in idxs:
            for m in (src / "manifests").glob(f"{i:02d}_*.json"):
                shutil.copy2(m, st / name / "manifests" / m.name)
        plans[name] = (load(src / "plan.json"), sha256(src / "plan.json"))
    s6plan = (load(args.s6_plan / "plan.json"), sha256(args.s6_plan / "plan.json"))
    rows, maps = [], []
    groups = (("S6", res / "S26_M6B_S6", None, s6plan, lambda i: "S6_m6b"),
              ("P", res / "S26_M6_P", P_IDX, plans["plan_m6p"], lambda i: f"P{i}"),
              ("K", res / "S26_M6_K", K_IDX, plans["plan_m6k"], lambda i: f"K{i + 1}"))
    for kind, root, idxs, (plan, psha), label_of in groups:
        if not root.is_dir():
            continue
        folders = sorted(p for p in root.iterdir() if p.is_dir()) if idxs is None else session_folders(root, idxs)
        for folder in folders:
            copy_tree(folder, st / "results" / root.name / folder.name)
            if (folder / "host" / "session_log.json").is_file() or (folder / "validated.json").is_file():
                r, m = row_for(kind, folder, root, plan, psha, label_of)
                m["installed_apk_sha256"] = args.installed_apk_sha
                rows.append(r)
                maps.append(m)
        for f in sorted(p for p in root.iterdir() if p.is_file()):
            if f.name != "watch.stop":
                (st / "results" / root.name).mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, st / "results" / root.name / f.name)
    for d in ("S26_M6B_P_readout", "S26_M6B_K_readout"):
        if (res / d).is_dir():
            copy_tree(res / d, st / "results" / d)
    for name in ("S26_M6_runs.jsonl", "keepawake_log.txt", "S26_M6B_S6_stdout_i5.txt", "S26_M6B_S6_stdout.txt",
                 "driver_p_confirm_console.txt", "driver_k_confirm_console.txt"):
        if (res / name).is_file():
            shutil.copy2(res / name, st / "results" / name)
    for name, fields, data in (("session_table_confirm.csv", FIELDS, rows), ("apk_manifest_session_map.csv", MAP_FIELDS, maps)):
        with open(st / name, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in data:
                w.writerow(r)
    hits = [str(p.relative_to(st)) for p in sorted(st.rglob("*"))
            if p.is_file() and p.suffix in TEXT_EXT and PAT.search(p.read_text(encoding="utf-8", errors="replace"))]
    if hits:
        raise SystemExit(f"PAT hits remain — refuse: {hits[:10]}")
    files = sorted(p for p in st.rglob("*") if p.is_file())
    (st / "SHA256SUMS").write_text("".join(f"{sha256(p)}  {p.relative_to(st).as_posix()}\n" for p in files), encoding="utf-8", newline="\n")
    args.zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(st.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(st).as_posix())
    print(json.dumps(dict(zip=str(args.zip), sha256=sha256(args.zip), files=len(files) + 1, table_rows=len(rows)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
