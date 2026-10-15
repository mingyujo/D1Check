"""M8 CONFIRM R21 블록 묶음 (2026-10-16 · 프롬프트 M8-B R21 5단계) — 그 R블록 세션 폴더 전부 (시도 · 사전 이동 포함) · HAL (gate_attempt_id 별) · run log · events · prestart · tref ·
드라이버 log/state/progress/console · R21 manifest · 계획 · 동결 R21 + v1 · 정정안 · 원장 사본 + R21 발췌 (소비/실패) · readout_r21 (그 블록 + 누적) · 에너지 적격 표 (DEV · CONFIRM) ·
delegate 증거 · 버전/SHA · SHA256SUMS · PAT 0 · APK 0. 계산 = m8_readout_r21 (봉인 계약) 만.

  py -3 -X utf8 s26/tools/mixreq/m8_bundle_r21.py --block 1 --onedrive <D1_ondevice> --stage <dir> --zip <path>
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from m6_bundle import PAT, TEXT_EXT, copy_tree, sha256  # noqa: E402
import compiled_model_evidence as CME  # noqa: E402

REPO = HERE.parents[2]
PREP = REPO / "s26" / "results" / "m8_prep"
PAT_M8 = re.compile(PAT.pattern + r"|192\.0\.0\.")
TT_RE = re.compile(r"^(?P<ts>\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+)\s+(?P<pid>\d+)\s+(?P<tid>\d+)\s+(?P<level>[VDIWEF])\s+(?P<tag>[^:]*?)\s*:\s?(?P<msg>.*)$")
TOOLS = ("m8_common.py", "m8_plan.py", "m8_plan_r21.py", "m8_freeze_r21.py", "m8_session.py", "m8_validate.py", "m8_gate.py", "m8_driver.py", "m8_driver.ps1", "m8_readout.py",
         "m8_readout_r21.py", "m8_bundle_r21.py", "coverage_check.py", "test_m8.py", "test_m8_r21.py", "m7_hal_cont.ps1", "m7_driver.py")


def delegate_rows(label: str, attempt: int, folder: Path) -> list[dict]:
    """DEV 정정 v1 (1015b #7) 과 같은 규칙: runner PID = 'Replacing … with delegate' 줄이 가장 많은 PID · runtime_return 순서 ↔ Replacing 줄 순서 (TID 직접 연결 불가)."""
    lc = folder / "host" / "logcat_threadtime.txt"
    if not lc.is_file():
        return [dict(label=label, attempt=attempt, msg="logcat 없음")]
    starts = [json.loads(l) for l in (folder / "device" / "progress.jsonl").read_text(encoding="utf-8", errors="replace").splitlines() if '"runtime_return"' in l] \
        if (folder / "device" / "progress.jsonl").is_file() else []
    logs = []
    for line in lc.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TT_RE.match(line)
        if m:
            logs.append(dict(m.groupdict(), tag=m.group("tag").strip()))
    cnt = {}
    for x in logs:
        if CME.REPLACE_RE.search(x["msg"]):
            cnt[x["pid"]] = cnt.get(x["pid"], 0) + 1
    pid = max(cnt, key=cnt.get) if cnt else ""
    repl = [x for x in logs if x["pid"] == pid and "Replacing" in x["msg"]]
    out = []
    for i, x in enumerate(repl):
        rt = starts[i] if i < len(starts) else {}
        out.append(dict(label=label, attempt=attempt, runner_pid=pid, logcat_tid=x["tid"], logcat_time=x["ts"], tag=x["tag"], msg=x["msg"][:200], runtime_key_by_order=rt.get("key"),
                        model_sha256=rt.get("model_sha256"), engine=rt.get("engine"), litert_version=rt.get("litert_version"), requested_backend=(rt.get("key") or "").rsplit("_", 1)[-1],
                        join_method="runtime_return 순서 ↔ Replacing 줄 순서 (같은 PID) · TID 직접 연결 불가"))
    if not out:
        out.append(dict(label=label, attempt=attempt, runner_pid=pid, msg="Replacing 줄 0 (runtime_return " + str(len(starts)) + ")"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--block", type=int, required=True)
    ap.add_argument("--results", type=Path, default=REPO / "results")
    ap.add_argument("--onedrive", required=True, type=Path)
    ap.add_argument("--stage", required=True, type=Path)
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--manifest", type=Path, default=PREP / "plan_m8_r21" / "r21_manifest_v2.json")
    args = ap.parse_args()
    if args.stage.exists():
        raise SystemExit(f"stage exists: {args.stage}")
    b = args.block
    st = args.stage
    man = json.loads(args.manifest.read_text(encoding="utf-8"))
    blk = next(x for x in man["stages"]["confirm_blocks"] if x["block_no"] == b)
    labels = [s["label"] for s in blk["sessions"]]
    # results: 그 블록 세션 폴더 (a1 · a2 · _pre*)
    croot = args.results / "S26_M8_CONFIRM"
    folders = []
    for s in blk["sessions"]:
        plan = json.loads((PREP / s["plan_dir"] / "plan.json").read_text(encoding="utf-8"))
        pol = next(e["policy"] for e in plan["sessions"] if e["index"] == s["index"])
        for p in sorted((croot / s["plan_dir"]).glob(f"S26_MIXREQ_{s['index']:02d}_{pol}_a*")) if (croot / s["plan_dir"]).is_dir() else []:
            copy_tree(p, st / "results" / "S26_M8_CONFIRM" / s["plan_dir"] / p.name)
            folders.append((s["label"], p))
        for pc in s.get("prior_consumed") or []:   # 이전 판 소비 START (v1 idx 502 등) — 보존 · 계수
            pd1 = s["plan_dir"].removesuffix("v2")
            for p in sorted((croot / pd1).glob(f"S26_MIXREQ_{pc['index']:02d}_*_a{pc['attempt']}")) if (croot / pd1).is_dir() else []:
                copy_tree(p, st / "results" / "S26_M8_CONFIRM" / pd1 / p.name)
                folders.append((s["label"], p))
    (st / "results" / "S26_M8_HAL").mkdir(parents=True, exist_ok=True)
    for p in sorted((args.results / "S26_M8_HAL").glob(f"hal_cont_R{b}-*")):
        shutil.copy2(p, st / "results" / "S26_M8_HAL" / p.name)
    for p in sorted(croot.glob("*")) if croot.is_dir() else []:
        if p.is_file() and (p.name.startswith("driver_") or p.name.startswith("console_R") and any(p.name.startswith(f"console_{l}_") for l in labels)):
            shutil.copy2(p, st / "results" / "S26_M8_CONFIRM" / p.name)
    for p in sorted(args.results.glob("*")):
        if p.is_file() and (p.name.startswith("S26_M8_") and p.suffix in (".jsonl", ".json") or p.name.startswith("driver_m8_confirm_") and p.suffix == ".txt"):
            shutil.copy2(p, st / "results" / p.name)
    # 소비 · 실패 발췌 (그 블록 · runs / events / prestart)
    ext = []
    for name in ("S26_M8_runs.jsonl", "S26_M8_driver_events.jsonl", "S26_M8_prestart_ledger.jsonl"):
        f = args.results / name
        if f.is_file():
            for l in f.read_text(encoding="utf-8").splitlines():
                if any(f'"{lab}' in l for lab in labels) or (f'"block": {b}' in l and "confirm" in l) or f"Tref_block 2026-10-16_R{b}" in l:
                    ext.append(f"{name}\t{l}")
    (st / "consumption").mkdir()
    (st / "consumption" / f"R{b}_consumption_extract.tsv").write_text("\n".join(ext) + "\n", encoding="utf-8", newline="\n")
    led = args.onedrive / "sim" / "out_m8" / "prep_ledger.txt"
    (st / "docs").mkdir()
    if led.is_file():
        shutil.copy2(led, st / "docs" / "prep_ledger.txt")
        r21 = [l for l in led.read_text(encoding="utf-8").splitlines() if "R21" in l or f"R{b}-" in l]
        (st / "consumption" / f"R{b}_ledger_extract.txt").write_text("\n".join(r21) + "\n", encoding="utf-8", newline="\n")
    for src in (PREP / "CONFIRM_FREEZE_M8_R21_v2.json", PREP / "CONFIRM_FREEZE_M8_R21_v1.json", PREP / "CONFIRM_FREEZE_M8_v1.json", croot / "R1-0_a1_v1_incident.json", args.onedrive / "조민규_답_1016_21슬롯_목적정정.txt", args.onedrive / "프롬프트_M8B_CONFIRM_R21_1016.md",
                args.onedrive / "sim" / "out_m8" / "questions_for_영훈.md"):
        if src.is_file():
            shutil.copy2(src, st / "docs" / src.name)
    for d in ("plan_m8_r21", "plan_m8m128_r21", "plan_m8s128_r21", "plan_m8m128_r21v2", "plan_m8s128_r21v2", "r21"):
        copy_tree(PREP / d, st / "plans" / d)
    (st / "tools").mkdir()
    for t in TOOLS:
        if (HERE / t).is_file():
            shutil.copy2(HERE / t, st / "tools" / t)
    # readout_r21 (그 블록 · 누적)
    for tag, blocks in ((f"R{b}", str(b)), (f"R1-R{b}", ",".join(str(i) for i in range(1, b + 1)))):
        r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "m8_readout_r21.py"), "confirm", "--results", str(args.results), "--manifest", str(args.manifest),
                            "--dev-energy", str(PREP / "r21" / "energy_eligibility_dev.json"), "--out", str(st / "readout_r21" / tag), "--blocks", blocks], capture_output=True, text=True, encoding="utf-8", cwd=str(REPO))
        if r.returncode != 0:
            raise SystemExit(f"readout_r21 failed: {r.stderr[-1200:]}")
    # 에너지 적격 표 (CONFIRM 세션별)
    rows = []
    for f in sorted((st / "readout_r21" / f"R{b}" / "sessions").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        ch = (d.get("app") or {}).get("charge") or {}
        rows.append(dict(session=f.stem, eligible_session=d.get("eligible"), energy_eligible=d.get("energy_eligible"), null_reason=d.get("energy_null_reason"), r=ch.get("r"), q_int_uah=ch.get("q_int_uah"),
                         dq_cc_uah=ch.get("dq_cc_uah"), steps=json.dumps(ch.get("step_sizes")), load_neg=(d.get("app") or {}).get("load_neg_fraction"),
                         v_min=(d.get("app") or {}).get("voltage_min_mv"), v_max=(d.get("app") or {}).get("voltage_max_mv"), plugged_any=(d.get("app") or {}).get("plugged_any")))
    if rows:
        with open(st / "readout_r21" / f"energy_eligibility_confirm_R{b}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    drows = []
    for label, p in folders:
        m = re.search(r"_a(\d)$", p.name)
        if m:
            drows += delegate_rows(label, int(m.group(1)), p)
    if drows:
        keys = []
        for r in drows:
            keys += [k for k in r if k not in keys]
        with open(st / "readout_r21" / f"delegate_evidence_R{b}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(drows)
    git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8", cwd=str(REPO)).stdout.strip()   # noqa: E731
    versions = dict(made=dt.datetime.now().isoformat(timespec="seconds"), block=f"R{b}", revision_id=man["revision_id"], host_commit=git("rev-parse", "HEAD"),
                    r21_manifest_sha256=sha256(args.manifest), r21_manifest_v1_sha256=sha256(PREP / "plan_m8_r21" / "r21_manifest.json"),
                    freeze_r21_sha256=sha256(PREP / "CONFIRM_FREEZE_M8_R21_v2.json"), freeze_r21_v1_sha256=sha256(PREP / "CONFIRM_FREEZE_M8_R21_v1.json"),
                    freeze_v1_sha256=sha256(PREP / "CONFIRM_FREEZE_M8_v1.json"), apk_sha256="37960e25c5948f661f2f5b47a90a4356be1b3712706d34679e71a14842ced6ea",
                    tools={t: sha256(HERE / t) for t in TOOLS if (HERE / t).is_file()}, sessions=[f"{l} {p.name}" for l, p in folders])
    (st / "versions_sha.json").write_text(json.dumps(versions, ensure_ascii=False, indent=1), encoding="utf-8")
    (st / "README.md").write_text("\n".join([
        f"# M8 CONFIRM R21 블록 R{b} 묶음 — {versions['made']}", "",
        "- 조민규 1016 정정안 (SHA 1dc9f5b5…) · 동결 R21 `" + (versions["freeze_r21_sha256"] or "") + "` (부모 v1 `deedfc1b…`) · R21 manifest `" + (versions["r21_manifest_sha256"] or "") + "` · host " + versions["host_commit"],
        "- 3블록은 통계적 최소나 유의성 보장이 아니다 · 요청 128건을 독립 반복으로 세지 않는다 · J = 등록 단위 가설 아래 gauge 추정 J (내부 gauge 정합 · 외부 전력계 교정 아님) · AP = HAL 온도 센서 (표면온도 아님)",
        "- `results/` 그 블록 세션 폴더 전부 (logcat 정리본) · HAL (gate_attempt_id 별) · runs / events / prestart / tref · 드라이버 log/state/progress/console",
        "- `consumption/` 그 블록 소비 · 실패 · 재시도 · 거절 발췌 + 원장 R21 발췌 · `docs/` 동결 R21 · v1 · 정정안 · 프롬프트 · 원장 사본 · 질문",
        "- `readout_r21/R" + str(b) + "/` 그 블록 · `R1-R" + str(b) + "/` 누적 (sessions_r21.csv · slots_r21.csv · pairs_r21.csv · readout_r21.json) · 에너지 적격 (DEV = plans/r21 · CONFIRM = energy_eligibility_confirm) · delegate 증거",
        "- `plans/` R21 manifest · 계획 폴더 · DEV 에너지 표 · `tools/` 코드 사본 · `versions_sha.json` · SHA256SUMS · 주소/시리얼 0 (PAT 검사) · APK 0", ""]), encoding="utf-8", newline="\n")
    hits = []
    for p in sorted(st.rglob("*")):
        if p.is_file() and p.suffix in TEXT_EXT | {".cfg", ".ps1", ".py", ".tsv"}:
            if PAT_M8.search(p.read_text(encoding="utf-8", errors="replace")):
                hits.append(str(p.relative_to(st)))
    if hits:
        raise SystemExit(f"PAT hits remain — refuse: {hits[:10]}")
    if any(p.suffix == ".apk" for p in st.rglob("*")):
        raise SystemExit("apk in bundle — refuse")
    files = sorted(p for p in st.rglob("*") if p.is_file())
    (st / "SHA256SUMS").write_text("".join(f"{sha256(p)}  {p.relative_to(st).as_posix()}\n" for p in files), encoding="utf-8", newline="\n")
    args.zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(st.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(st).as_posix())
    print(json.dumps(dict(zip=str(args.zip), sha256=sha256(args.zip), bytes=args.zip.stat().st_size, files=len(files) + 1, sessions=len(folders)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
