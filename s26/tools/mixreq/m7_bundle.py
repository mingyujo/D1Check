"""M7 development bundle (프롬프트 M7-A 3단계-4 · 6단계-1 · 등록 M7 v2 §5 · §6-1) — copy, sanitize, tables, README, SHA256SUMS, zip. No calculation
(J · 열 · 정책 비교 없음). m6_bundle.py (copy_tree · PAT scan · sha256) is imported unchanged; m7_table.py builds the tables.

  py -3 -X utf8 s26/tools/mixreq/m7_bundle.py --results results --onedrive <D1_ondevice> --stage <dir> --zip <D1_ondevice>/sim/out_m7/m7_dev_bundle_1.zip
      --bundle-no 1 [--case-stand-wind "..."] [--room 미기록] [--with-m6-rows]

Contents: docs (등록 v1 · v2 · 대조 · REQUEST · APK_COMMIT_MAP · APK_M7_AREA_DIFF · area_rules · 원장 사본) · plans (plan_m7p / prep / k / s) · results
(S26_M7_S7 · S26_M7_M6REPRO · S26_M7_SMOKE · S26_M7_K · S26_M7_PREP · S26_M7_P · S26_M7_S · S26_M7_HAL · run log · driver events · keepawake log) ·
tables (m7_table: session_table_m7.csv · apk_manifest_session_map.csv · field_map.json · fingerprint.txt · readouts) · README.md · SHA256SUMS.
Rules (= M5 / M6 share): raw logcat_threadtime.txt is NEVER copied — only the sanitized copy; *.apk and watch.stop skipped; every text file is
scanned for the commit PAT (IPv4 with port · adb serial · IPv6 link-local) and the zip is refused if any hit remains.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from m6_bundle import PAT, TEXT_EXT, copy_tree, jsonl, sha256  # noqa: E402
import m7_common as M7  # noqa: E402

REPO = HERE.parents[2]
RESULT_ROOTS = ("S26_M7_S7", "S26_M7_M6REPRO", "S26_M7_SMOKE", "S26_M7_K", "S26_M7_PREP", "S26_M7_P", "S26_M7_S", "S26_M7_HAL")
PLANS = ("plan_m7p", "plan_m7prep", "plan_m7k", "plan_m7s")
UNITS = ("전류 µA (current_raw · 방전 음수 · API 값 · 기기 스케일 미검증 — 등록 M6 v3 §3-7 가설 그대로) · charge_counter µAh · 전압 mV · 배터리 온도 deci-℃ · HAL 온도 ℃ (0.1 단위) · "
         "시각 mono_ns (기기 단조 시계) / host_ms (PC epoch ms) · 같은 gauge 라 독립 전력 기준 아님 (M6 v3 §7-2)")
MITIGATIONS = ("완화 1 (항목 1 · 등록 §1-4): 준비 P ~ K 사이 끊김 없는 관측 = 호스트 연속 HAL + dumpsys battery (hal_cont · 2.3 s) · 앱 power_sample 은 세션 밖 (cooling 끝 ~ K 준비) 없음 → power_gap = {reason: app not running between sessions (APK: power_sample only inside a session)} · 추정 채움 0",
               "완화 2 (항목 2 · 등록 §2-6): 마지막 AVAILABLE 뒤 180 s 냉각 — 온도는 호스트 HAL 을 원점 + 300 s 까지 (hal_coverage_after_last_available_s ≥ 180 실측) · 전력은 앱 cooling 60 s 까지 (power_coverage_after_last_available_s ≈ 105 s 실측)",
               "완화 3 (항목 4 · 등록 §4-3): 지속 S 냉각 600 s — 온도는 호스트 HAL 을 창 끝 + 600 s 까지 · 전력은 cooling 60 s · 준비는 블록 A/N (R4 와 같음 · 블록 M 아님)")


def usage(results: Path) -> dict:
    """실측 사용량 (등록 §5-7): 세션별 순수 실행 (run log start → end) · 대기 (세션 사이) · 재시도 (attempt 2) · 충전 (plugged 구간 — 드라이버 기록) — 기술만."""
    runs = jsonl(results / "S26_M7_runs.jsonl")
    starts = {}
    rows = []
    for r in runs:
        key = (r.get("label"), r.get("attempt"))
        if r.get("event") == "start":
            starts[key] = r
        elif r.get("event") == "end" and key in starts:
            s = starts.pop(key)
            rows.append(dict(label=r["label"], attempt=r.get("attempt"), start=s["t"], end=r["t"], run_s=round(float(r["epoch"]) - float(s["epoch"]), 1), rc=r.get("rc")))
    rows.sort(key=lambda x: x["start"])
    waits = [dict(after=a["label"], before=b["label"], wait_s=round((dt.datetime.fromisoformat(b["start"]) - dt.datetime.fromisoformat(a["end"])).total_seconds(), 1))
             for a, b in zip(rows, rows[1:])]
    events = jsonl(results / "S26_M7_driver_events.jsonl")
    charges = [e for e in events if e.get("what") in ("charge_wait", "rc6_transient")]
    return dict(sessions=rows, pure_run_s=round(sum(r["run_s"] for r in rows), 1), retry_run_s=round(sum(r["run_s"] for r in rows if r.get("attempt") == 2), 1),
                waits=waits, wait_total_s=round(sum(w["wait_s"] for w in waits), 1), charge_events=charges, first=rows[0]["start"] if rows else None, last=rows[-1]["end"] if rows else None)


def readme(args, table_index: dict, use: dict, plan_shas: dict) -> str:
    lines = [f"# M7 개발 묶음 {args.bundle_no} — S26 같은 APK 확대 반복 (M7-apk) · 측정 · readout 까지 (계산 · 판정 = 조민규 / Cowork)", "",
             f"- 만든 시각: {dt.datetime.now().isoformat(timespec='seconds')} · 등록 v2 `{M7.REGISTRATION['sha256']}` (v1 `{M7.REGISTRATION_V1['sha256'][:8]}…`) · "
             f"APK M7 `878b10b7bc05300ddddc60fac0b2fb40eb020870841e473a8775827ef92bf092` (커밋 `7ad2b18f`) · M6 12세션은 APK `6a4da1ac…` (`cycle = m6` 행만)",
             f"- 계획 SHA: " + " · ".join(f"{k} `{v}`" for k, v in plan_shas.items()),
             f"- 세션 표 행: {table_index.get('rows')} (m7 {table_index.get('m7_rows')} · m6 {table_index.get('m6_rows')}) · 유효 (m7): {json.dumps(table_index.get('valid'), ensure_ascii=False)} · kind 별: {json.dumps(table_index.get('by_kind'), ensure_ascii=False)}",
             f"- fingerprint: `{table_index.get('fingerprint')}` · 케이스/거치/바람: {table_index.get('case_stand_wind')} · 실내 온도: {table_index.get('room_c')}", "",
             "## 단위 · 부호", f"- {UNITS}", "",
             "## 완화 3개 (등록 v2 · 대조 문서)", *[f"- {m}" for m in MITIGATIONS], "",
             "## 공백 사유 (null)",
             "- `power_gap`: 세션 사이 (준비 P cooling 끝 → K 준비 · 세션 cooling 60 s 뒤) 앱 power_sample 없음 — APK 가 세션 안에서만 표본을 쓴다 (field_map.json power_gap)",
             "- `응답 시각`: 앱에 요청자 응답 이벤트 없음 (field_map.json) · `실내 온도`: 온도계 없음 → 미기록 · K 의 `power_coverage_after_last_available_s`: 요청 0 → null",
             "- 조건 B · C 의 K 는 시작 띠 · 게이트 대기를 건너뛴다 (등록 §1-2 90 s 간격 우선 · plan_m7k.k_after_prep_gate) → band_result = skipped · 시작 SKIN 등은 세션 표 start_* 열",
             "- index 자리: M6 · R4 가 쓴 자리 뒤 (P 12 ~ 51 · K 4 ~ 18 · S 16 ~ 27 · 등록 v2 머리 단락) · session_id = uuid5(실험 ID/index) 그대로", "",
             "## 실측 사용량 (run log · 기술만)",
             f"- 세션 {len(use['sessions'])} · 순수 실행 합 {use['pure_run_s']} s · 재시도 (attempt 2) 실행 {use['retry_run_s']} s · 세션 사이 대기 합 {use['wait_total_s']} s (유휴 · 안정 · 게이트 · 띠 포함) · 충전 구간 (드라이버 기록) {len(use['charge_events'])} · 첫 세션 {use['first']} · 마지막 끝 {use['last']}",
             "- 세션별 run_s 는 `usage.json`", "",
             "## 폴더", "- `docs/` 등록 v1 · v2 · 대조 · REQUEST · APK_COMMIT_MAP.md · APK_M7_AREA_DIFF.json · area_rules.json · freeze_m7.txt (원장 사본)",
             "- `plans/` plan_m7p · plan_m7prep · plan_m7k · plan_m7s (plan.json · manifests · smoke · projection.json · device_inputs.json)",
             "- `results/` S26_M7_S7 (회귀) · S26_M7_M6REPRO (M6 재현 스모크) · S26_M7_SMOKE · S26_M7_K · S26_M7_PREP · S26_M7_P · S26_M7_S · S26_M7_HAL (연속 HAL csv) · S26_M7_runs.jsonl · S26_M7_driver_events.jsonl · 드라이버 콘솔 · keepawake 로그",
             "- `tables/` session_table_m7.csv · apk_manifest_session_map.csv · field_map.json · fingerprint.txt · table_index.json · readout_<root>/ (m6_readout: 세션 JSON · inventory.csv · readout_index.json)",
             "- logcat 은 정리본 (`logcat_threadtime.sanitized.txt`) 만 · *.apk 없음 · 주소 · 시리얼 0 (PAT 검사)", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, default=REPO / "results")
    ap.add_argument("--onedrive", required=True, type=Path)
    ap.add_argument("--stage", required=True, type=Path)
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--bundle-no", default="1")
    ap.add_argument("--case-stand-wind", default="미확인")
    ap.add_argument("--room", default="미기록")
    ap.add_argument("--with-m6-rows", action="store_true", help="session table: add cycle = m6 rows from the M6-A / M6-B tables (final bundle)")
    args = ap.parse_args()
    if args.stage.exists():
        raise SystemExit(f"stage exists: {args.stage}")
    st = args.stage
    (st / "docs").mkdir(parents=True)
    for src, dst in ((args.onedrive / "sim" / "M7_확대반복_사전등록_v1.md", "M7_확대반복_사전등록_v1.md"), (args.onedrive / "sim" / "M7_확대반복_사전등록_v2.md", "M7_확대반복_사전등록_v2.md"),
                     (args.onedrive / "조민규_확대요청_대조_1013.md", "조민규_확대요청_대조_1013.md"), (REPO / "s26/results/m7_1013/REQUEST_1013.md", "REQUEST_1013.md"),
                     (REPO / "s26/results/m6_1012/APK_COMMIT_MAP.md", "APK_COMMIT_MAP.md"), (REPO / "s26/results/m7_1013/APK_M7_AREA_DIFF.json", "APK_M7_AREA_DIFF.json"),
                     (REPO / "s26/results/m6_1012/area_rules.json", "area_rules.json"), (args.onedrive / "sim" / "out_m7" / "freeze_m7.txt", "freeze_m7.txt")):
        if src.is_file():
            shutil.copy2(src, st / "docs" / dst)
    plan_shas = {}
    for d in PLANS:
        copy_tree(REPO / "s26/results/m7_1013" / d, st / "plans" / d)
        plan_shas[d] = (REPO / "s26/results/m7_1013" / d / "plan_sha256.txt").read_text(encoding="utf-8").strip()
    for root_name in RESULT_ROOTS:
        if (args.results / root_name).is_dir():
            copy_tree(args.results / root_name, st / "results" / root_name)
    (st / "results").mkdir(exist_ok=True)
    for p in sorted(args.results.glob("*")):
        if p.is_file() and (p.name in ("S26_M7_runs.jsonl", "S26_M7_driver_events.jsonl") or p.name.startswith(("driver_", "m7_")) and p.suffix in (".txt", ".ps1")):
            shutil.copy2(p, st / "results" / p.name)
    for name in ("keepawake_m7.log",):
        if (args.onedrive / "sim" / "out_m7" / name).is_file():
            shutil.copy2(args.onedrive / "sim" / "out_m7" / name, st / "results" / name)
    tables = st / "tables"
    cmd = [sys.executable, "-X", "utf8", str(HERE / "m7_table.py"), "--results", str(args.results), "--out", str(tables), "--case-stand-wind", args.case_stand_wind, "--room", args.room]
    if args.with_m6_rows:
        cmd += ["--m6-table", str(REPO / "s26/results/m6_1012/session_table.csv"), "--m6-table", str(REPO / "s26/results/m6_1012/confirm/session_table_confirm.csv")]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
    if r.returncode != 0:
        raise SystemExit(f"m7_table failed: {r.stderr[-800:]}")
    table_index = json.loads((tables / "table_index.json").read_text(encoding="utf-8"))
    use = usage(args.results)
    (st / "usage.json").write_text(json.dumps(use, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    (st / "README.md").write_text(readme(args, table_index, use, plan_shas), encoding="utf-8", newline="\n")
    hits = []
    for p in sorted(st.rglob("*")):
        if p.is_file() and p.suffix in TEXT_EXT:
            if PAT.search(p.read_text(encoding="utf-8", errors="replace")):
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
    print(json.dumps(dict(zip=str(args.zip), sha256=sha256(args.zip), bytes=args.zip.stat().st_size, files=len(files) + 1, table_rows=table_index.get("rows"), valid=table_index.get("valid")), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
