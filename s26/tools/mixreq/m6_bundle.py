"""M6-A development bundle (프롬프트 M6-A 8단계 · M5 공유본과 같은 포함 규칙) — copy, sanitize, table, SHA256SUMS, zip. No calculation.

  py -3 -X utf8 s26/tools/mixreq/m6_bundle.py --results results --repo-results s26/results/m6_1012 --onedrive <D1_ondevice> --stage <dir>
      --zip <D1_ondevice>/sim/out_m6/m6_dev_bundle.zip [--room-temp results/room_temp.jsonl]

Contents: 등록 v3 · APK_COMMIT_MAP.md (빌드 재현 포함) · M6_사전계산_1012.md + precalc/ · plan_m6p / plan_m6k / plan_m6e (manifests · configs ·
projection.json) · results/S26_M6_GAUGE (E1 ~ E3 · ET · smoke · invalid attempts) · S26_M6_K (K1 · K2 · smoke) · S26_M6_P (P dev 0 ~ 5 + invalid
attempts + smoke) · S26_M6_S6 (regression) · readouts · run log · session table (CSV) · SHA256SUMS.
Rules (= M5 share): raw logcat_threadtime.txt is NEVER copied — only <host>/logcat_threadtime.sanitized.txt (sanitize_logcat.py); every text
file is scanned for the commit PAT (IPv4 with port · adb serial · IPv6 link-local) and the zip is refused if any hit remains; binaries other than the device
outputs (*.apk) are excluded.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAT = re.compile(r"([0-9]{1,3}\.){3}[0-9]{1,3}" + ":" + r"[0-9]{2,5}|R3KL[0-9A-Z]{7}|" + "fe8" + "0:")   # split so this file never matches itself
TEXT_EXT = {".json", ".jsonl", ".txt", ".csv", ".md", ".py", ".ps1"}
ROOTS = ("S26_M6_GAUGE", "S26_M6_K", "S26_M6_P", "S26_M6_S6", "S26_M6_SMOKE_GAUGE", "S26_M6_SMOKE_K", "S26_M6_SMOKE_P")
TABLE_FIELDS = ["kind", "idx", "label", "load", "rule", "attempt", "eligible", "reasons", "start_time", "start_SKIN", "start_AP", "start_BAT", "start_SOC",
                "brightness", "brightness_mode", "band_result", "in_block_charge", "previous_run", "previous_end", "gap_s", "room_temp_c", "folder"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def copy_tree(src: Path, dst: Path) -> None:
    for p in sorted(src.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(src)
        if p.suffix == ".apk" or p.name in ("watch.stop",):
            continue
        if p.name == "logcat_threadtime.txt":
            subprocess.run([sys.executable, "-X", "utf8", str(HERE / "sanitize_logcat.py"), str(p), str((dst / rel).parent)], check=True, capture_output=True)
            continue
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst / rel)


def jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.is_file() else []


def table(results: Path, room: list[dict]) -> list[dict]:
    runs = jsonl(results / "S26_M6_runs.jsonl")
    rows = []
    for root_name, kind in zip(ROOTS, ("E", "K", "P", "S6", "smoke", "smoke", "smoke")):
        root = results / root_name
        if not root.is_dir():
            continue
        bands = jsonl(root / "start_band.jsonl")
        for folder in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.endswith("_readout")):
            v = None
            for name in ("validated.json", "gauge_validated.json"):
                if (folder / name).is_file():
                    v = json.loads((folder / name).read_text(encoding="utf-8"))
            log = {}
            for name in ("host/session_log.json", "host/gauge_log.json"):
                if (folder / name).is_file():
                    log = json.loads((folder / name).read_text(encoding="utf-8"))
            if (folder / "host" / "gauge_log.json").is_file():
                m = re.match(r"(E\d|ET|E_smoke)(_loop)?_a(\d)", folder.name)
                label, idx, attempt = (m.group(1) + (m.group(2) or "")) if m else folder.name, None, int(m.group(3)) if m else None
                band = log.get("band")
            else:
                man = json.loads((folder / "host" / "manifest_pushed.json").read_text(encoding="utf-8")) if (folder / "host" / "manifest_pushed.json").is_file() else {}
                idx, attempt = man.get("session_index"), man.get("attempt")
                label = man.get("m6_run") or (f"{man.get('m6_load')}-{man.get('m6_letter')}" if man.get("m6_load") else folder.name)
                band = next((b for b in reversed(bands) if b.get("label") == (f"index{idx:02d}" if idx is not None else None) and b.get("attempt") == attempt), None)
            start = (band or {}).get("start") or ((band or {}).get("polls") or [{}])[-1]
            prev = (band or {}).get("previous_run") or {}
            st = log.get("start_time")
            gap = None
            if st and prev.get("t"):
                import datetime as _dt
                gap = round((_dt.datetime.fromisoformat(st) - _dt.datetime.fromisoformat(prev["t"])).total_seconds())
            rt = next((r.get("start_c") for r in room if r.get("label") == label or (label == "E1" and r.get("label") == "E_block_start")), None)
            rows.append(dict(kind=kind, idx=idx, label=label, load=(label.split("-")[0] if kind == "P" else None), rule=(label.split("-")[1] if kind == "P" and "-" in label else None),
                             attempt=attempt, eligible=(v or {}).get("eligible"), reasons=";".join((v or {}).get("reasons") or []), start_time=st,
                             start_SKIN=start.get("SKIN"), start_AP=start.get("AP"), start_BAT=start.get("BAT"), start_SOC=start.get("soc"),
                             brightness=start.get("brightness"), brightness_mode=start.get("brightness_mode"), band_result=(band or {}).get("result"),
                             in_block_charge=(band or {}).get("in_block_charge"), previous_run=prev.get("label"), previous_end=prev.get("t"), gap_s=gap,
                             room_temp_c=rt, folder=f"{root_name}/{folder.name}"))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--repo-results", required=True, type=Path)
    ap.add_argument("--onedrive", required=True, type=Path)
    ap.add_argument("--stage", required=True, type=Path)
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--room-temp", type=Path)
    args = ap.parse_args()
    if args.stage.exists():
        raise SystemExit(f"stage exists: {args.stage}")
    st = args.stage
    (st / "docs").mkdir(parents=True)
    shutil.copy2(args.onedrive / "sim" / "M6_동일APK_사전등록_v3.md", st / "docs" / "M6_동일APK_사전등록_v3.md")
    for name in ("APK_COMMIT_MAP.md", "M6_사전계산_1012.md", "area_rules.json"):
        shutil.copy2(args.repo_results / name, st / "docs" / name)
    for d in ("precalc", "build_repro", "plan_m6p", "plan_m6k", "plan_m6e"):
        copy_tree(args.repo_results / d, st / d)
    for root_name in ROOTS + ("S26_M6_P_readout", "S26_M6_K_readout"):
        if (args.results / root_name).is_dir():
            copy_tree(args.results / root_name, st / "results" / root_name)
    for name in ("S26_M6_runs.jsonl", "room_temp.jsonl"):
        if (args.results / name).is_file():
            shutil.copy2(args.results / name, st / "results" / name)
    room = jsonl(args.room_temp) if args.room_temp else []
    rows = table(args.results, room)
    with open(st / "session_table.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TABLE_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    hits = []
    for p in sorted(st.rglob("*")):
        if p.is_file() and p.suffix in TEXT_EXT:
            text = p.read_text(encoding="utf-8", errors="replace")
            if PAT.search(text):
                hits.append(str(p.relative_to(st)))
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
