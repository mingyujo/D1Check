"""M8 bundle (프롬프트 C부 · D-2 · D-3 · 조민규 답 §10) — copy · sanitize · tables · README · SHA256SUMS · zip. No calculation. m6_bundle (copy_tree · PAT scan · sha256) imported unchanged.

  py -3 -X utf8 s26/tools/mixreq/m8_bundle.py --kind prep|p0|block --block 1 --onedrive <D1_ondevice> --stage <dir> --zip <path> [--results results] [--extra <file> ...]
      [--apk-sha256 ..] [--signer-sha256 ..] [--source-commit ..] [--fingerprint ..]
prep  = A부 파생표 + 계약표 + contract_questions + 앱 diff + 시험 결과 + m8_* 도구 + coverage_check 검증 + 계획 (blocks.json · plan_m8*) + schedule + provenance (측정 0 · 수행 표시 없음)
p0 / block = results (S26_M8_SMOKE · P0 · DEV · HAL · run log · events · prestart ledger · tref) + tables (m8_table) + docs + plans.
Rules: raw logcat_threadtime.txt never copied (sanitized only · m6_bundle.copy_tree) · *.apk skipped · PAT scan (IPv4:port · serial · IPv6 link-local · 폰 clat 접두 192-0-0) → refuse on hit.
"""
from __future__ import annotations

import argparse
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
import m8_common as M8  # noqa: E402

REPO = M8.REPO
PAT_M8 = re.compile(PAT.pattern + r"|192\.0\.0\.")
RESULT_ROOTS = ("S26_M8_SMOKE", "S26_M8_P0", "S26_M8_DEV", "S26_M8_HAL", "S26_M8_REGRESSION", "S26_M8_PROBE")
PLAN_DIRS = tuple(M8.PLAN_DIR.values()) + ("plan_m8",)
TOOLS = ("m8_common.py", "m8_plan.py", "m8_session.py", "m8_validate.py", "m8_gate.py", "m8_driver.py", "m8_driver.ps1", "m8_readout.py", "m8_table.py", "m8_bundle.py", "coverage_check.py",
         "m8_perfetto_battery.cfg", "m8_probe.ps1", "test_m8.py", "m7_derive_1014.py", "m7_hal_cont.ps1")


def readme(args, extra_lines: list[str]) -> str:
    lines = [f"# M8 묶음 ({args.kind}{' 블록 ' + str(args.block) if args.kind == 'block' else ''}) — S26 새 계약 (M8-apk) · {'준비 완료 (측정 · 설치 · 스모크 0 · 수행 표시 없음)' if args.kind == 'prep' else '측정 · readout 까지 (계산 · 판정 = 조민규 / Cowork)'}", "",
             f"- 만든 시각: {dt.datetime.now().isoformat(timespec='seconds')} · 등록 `{M8.registration()['sha256']}` ({M8.registration()['file']}) · APK `{args.apk_sha256 or '미빌드/미기록'}` · 서명 `{args.signer_sha256 or '-'}` · source `{args.source_commit or '-'}`",
             "- 계약: 정책 7 (FIFO/EDD × SERIAL/PAIR × CPU/CG/CN · WAIT 인자) · bank 4 (L64 · C252 · M128 · SMOOTH128 · µs · 기한 0.8/2) · 응답 = urgent output_ready / normal readback (priority) · baseline 60 · cooling 90 · 120 s 뒤 dispatch 0 · 준비 role (RECENT) · NO_RUNTIME",
             "- 게이트: SOC 시작 하한 20 · 상한 없음 (영훈 운영 결정 · 조민규 40~80 은 참고 열) · Tref 제안 v1 (TREF_DAY_IDLE_MEDIAN_V1 · ± 0.5 · 기울기 0.1 · 10 min → PRESTART_REJECT 원장)",
             "- 단위 · 부호: 앱 current_raw µA (방전 음수 · 기기 스케일 미검증) · charge_counter µAh · voltage mV · host HAL ℃ 0.1 · 2.3 s · 갱신 시각 미제공 · 같은 gauge = 독립 기준 아님 · 앱/host 분리 (이어붙임 0 · host J180 계산 0)",
             "- 분모: planned (완료만 남기지 않음) · PRESTART_REJECT 는 계획 coverage 분모 (START 와 구분) · 실패/미완료/재시도/충전/안전정지 소비 보존 · a2 재사용 0 · 쓴 ID 재사용 0", ""] + extra_lines + ["",
             "## 폴더", "- `docs/` 계약표 v1 · 등록 v1 · contract_questions · A부 파생표 (derived_1014) · 원장 사본 · schedule_m8 · detection_gpu_evidence · instrumentation check",
             "- `plans/` plan_m8* (plan.json · manifests · smoke · device_inputs · projection 없음 — bank 는 M8Plan 식) · plan_m8/blocks.json (DEV seed 20261014 · 순서 · CONFIRM 설계)",
             "- `tools/` m8_* · coverage_check.py · 실행 명령 = m8_driver.ps1 머리 주석 · lock = results/S26_M8_driver.lock · 종료 = 드라이버 kill → 세션 프로세스 트리 taskkill /T",
             "- `app/` git diff --stat aaa7b87f -- request-runner/ · 영역별 diff · 시험 결과 (회귀 = 기존 계약 / 새 계약 시험 구분) · 빌드 명령 · 시각 · APK SHA · 서명 (APK 바이너리 없음)",
             "- `results/` (p0/block) S26_M8_* 세션 폴더 (logcat 정리본만) · S26_M8_HAL · run log · driver events · prestart ledger · tref" if args.kind != "prep" else "- `results/` 없음 (prep = 측정 0)",
             "- `tables/` session_table_m8 · provenance_m8 · coverage_m8 · field_map_m8 · usage_m8 · readout_m8/ (서비스 70~100 · 분모 · WAIT dose · readback · 준비 · ΔJ 계산 0)" if args.kind != "prep" else "",
             "- 주소 · 시리얼 0 (PAT 검사) · *.apk 없음", ""]
    return "\n".join(l for l in lines if l is not None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", required=True, choices=("prep", "p0", "block"))
    ap.add_argument("--block", type=int, default=1)
    ap.add_argument("--results", type=Path, default=REPO / "results")
    ap.add_argument("--onedrive", required=True, type=Path)
    ap.add_argument("--stage", required=True, type=Path)
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--extra", type=Path, action="append", default=[])
    ap.add_argument("--app-dir", type=Path, help="folder with app diff · test results · build record (copied to app/)")
    ap.add_argument("--apk-sha256", default="")
    ap.add_argument("--signer-sha256", default="")
    ap.add_argument("--source-commit", default="")
    ap.add_argument("--fingerprint", default="미확인")
    ap.add_argument("--case-stand-wind", default="케이스 없음 · 책상 위 눕힘 · 바람 없음")
    ap.add_argument("--room", default="NA")
    args = ap.parse_args()
    if args.stage.exists():
        raise SystemExit(f"stage exists: {args.stage}")
    st = args.stage
    (st / "docs").mkdir(parents=True)
    docs = [REPO / "d1sim/docs/M8_계약표_v1.md", REPO / "d1sim/docs/M8_사전등록_v1.md", REPO / "s26/results/m8_prep/contract", REPO / "s26/results/m7_1013/derived_1014",
            args.onedrive / "sim/out_m8/prep_ledger.txt", REPO / "s26/results/m8_prep/schedule_m8.md", REPO / "s26/results/m8_prep/detection_gpu_evidence.md",
            REPO / "s26/results/m8_prep/m8_instrumentation_check.md", REPO / "s26/results/m8_prep/coverage_check_vs_A4.json", REPO / "s26/results/m6_1012/APK_COMMIT_MAP.md", REPO / "s26/results/m6_1012/area_rules.json"]
    for src in docs + list(args.extra):
        if src.is_dir():
            copy_tree(src, st / "docs" / src.name)
        elif src.is_file():
            shutil.copy2(src, st / "docs" / src.name)
    for d in PLAN_DIRS:
        if (REPO / "s26/results/m8_prep" / d).is_dir():
            copy_tree(REPO / "s26/results/m8_prep" / d, st / "plans" / d)
    (st / "tools").mkdir()
    for t in TOOLS:
        if (HERE / t).is_file():
            shutil.copy2(HERE / t, st / "tools" / t)
    if args.app_dir and args.app_dir.is_dir():
        copy_tree(args.app_dir, st / "app")
    extra_lines = []
    if args.kind != "prep":
        for root_name in RESULT_ROOTS:
            if (args.results / root_name).is_dir():
                copy_tree(args.results / root_name, st / "results" / root_name)
        (st / "results").mkdir(exist_ok=True)
        for p in sorted(args.results.glob("*")):
            if p.is_file() and (p.name.startswith("S26_M8_") and p.suffix in (".jsonl", ".json") or p.name.startswith("driver_m8_") and p.suffix == ".txt"):
                shutil.copy2(p, st / "results" / p.name)
        tables = st / "tables"
        cmd = [sys.executable, "-X", "utf8", str(HERE / "m8_table.py"), "--results", str(args.results), "--out", str(tables), "--case-stand-wind", args.case_stand_wind, "--room", args.room,
               "--fingerprint", args.fingerprint, "--apk-sha256", args.apk_sha256, "--signer-sha256", args.signer_sha256, "--source-commit", args.source_commit]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
        if r.returncode != 0:
            raise SystemExit(f"m8_table failed: {r.stderr[-800:]}")
        idx = json.loads((tables / "table_index.json").read_text(encoding="utf-8"))
        extra_lines += [f"- 세션 표 행: {idx.get('rows')} · 유효: {json.dumps(idx.get('valid_by_stage'), ensure_ascii=False)} · stage 별: {json.dumps(idx.get('by_stage'), ensure_ascii=False)}"]
    (st / "README.md").write_text(readme(args, extra_lines), encoding="utf-8", newline="\n")
    hits = []
    for p in sorted(st.rglob("*")):
        if p.is_file() and p.suffix in TEXT_EXT | {".cfg", ".ps1", ".py"}:
            if PAT_M8.search(p.read_text(encoding="utf-8", errors="replace")):
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
    print(json.dumps(dict(zip=str(args.zip), sha256=sha256(args.zip), bytes=args.zip.stat().st_size, files=len(files) + 1), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
