"""M8 블록 1 정정 묶음 (조민규 10/15 19:3x 답 `조민규_답_1015c_DEV블록1수신_정정6.txt` ①~⑥ + 10:0x 답 `_1015b` #3 #5 #7) — 블록 1 결과 변경 0 · 재측정 0 · 파생표만.

  py -3 -X utf8 s26/tools/mixreq/m8_b1_corrections.py --out <D1_ondevice>\\sim\\out_m8\\b1_corrections [--results results]
Writes: b1_consumption.csv (①) · b1_gate_ledger.csv (②) · registration_versions.csv + registration/*.md + plan_m8l64_supp/ + instructions_index.md (③) · session_table_m8_v2.csv (④)
        · README.md (⑤ 해석 문구 · 대표 선택 규칙 · 횟수) · perfetto_r2_evidence.json (⑥) · delegate_evidence_m8.csv (1015b #7) · gate_contract_table.json (1015b #3). 계산 · 판정 0.
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
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import m8_common as M8  # noqa: E402
import mixreq_common as C  # noqa: E402
import compiled_model_evidence as CME  # noqa: E402

REPO = M8.REPO
PLAN_ROOT = REPO / "s26" / "results" / "m8_prep"
HOST_SOURCE_BY_LAUNCH = [  # (드라이버 프로세스 시작 시각, 그때 작업 트리 = 커밋) — 원장 · git log 로 복원
    ("2026-10-15T08:34:38", "a0a804b6c"), ("2026-10-15T10:03:17", "7202008d9"), ("2026-10-15T10:10:03", "fbfdc23d2"), ("2026-10-15T10:58:23", "4bcac066c"),
    ("2026-10-15T11:25:11", "beb80b36f"), ("2026-10-15T13:28:37", "3344119f4"), ("2026-10-15T16:54:51", "3344119f4"),
]
APK_SOURCE = "90db991c6"
TT_RE = re.compile(r"^(?P<ts>\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+)\s+(?P<pid>\d+)\s+(?P<tid>\d+)\s+(?P<level>[VDIWEF])\s+(?P<tag>[^:]*?)\s*:\s?(?P<msg>.*)$")
REG = [("v1", "d1sim/docs/M8_사전등록_v1.md", "b8314f6fc", "2026-10-14 23:4x", "스모크 · 회귀 (판정 밖) · v2 로 대체"),
       ("v2", "d1sim/docs/M8_사전등록_v2.md", "90db991c6", "2026-10-15 02:37", "P0 10 · P0 보충 r2 (계약) · DEV 블록 1 전 세션 (게이트 v2 + 영훈 운영 강제 START) · 블록 2 계약 (게이트만 v4/v5)"),
       ("v3", "d1sim/docs/M8_사전등록_v3.md", "a0a804b6c", "2026-10-15 08:26", "부록 1: P0 Perfetto on 보충 r2 (L64 idx 8 · stdin config) · 운영 (낮 블록 · 고정 유휴 생략 · Tref 키 분리)"),
       ("v4", "d1sim/docs/M8_사전등록_v4.md", "06fad2c4b", "2026-10-15 12:43", "부록 2: 블록 2 · CONFIRM START 밴드 Tref_block ± 1.0 (블록 1 소급 0)"),
       ("v5", "d1sim/docs/M8_사전등록_v5.md", "3344119f4", "2026-10-15 13:16", "부록 3: 블록 2 · CONFIRM START 판정 창 120 s · 기울기 ≤ 0.2 (블록 2 첫 세션 16:54 부터 · 블록 1 소급 0)")]
INSTRUCTIONS = [("프롬프트_M8_준비묶음_1014.md", "2026-10-14 (준비 D부)"), ("프롬프트_M8_추가지시_1014.md", "2026-10-14 22:2x (영훈 · SOC 20 · 묻지 않기)"),
                ("조민규_답_1015_계약값_8항목.txt", "2026-10-15 01:5x (조민규 · 값 8개 → 등록 v2)"), ("프롬프트_M8_추가지시2_1015.md", "2026-10-15 (값 8개 지시)"),
                ("프롬프트_M8_DEV블록_1015.md", "2026-10-15 08:xx (영훈 · D-3 DEV 블록 1·2 지금)"),
                ("(채팅) 영훈 08:2x", "폰 주소 · '충전 후 온도 조건만 반영 · 무조건 시간 대기 없이' → --no-fixed-idle (원장 08:2x)"),
                ("(채팅) 영훈 10:1x", "'기준 온도 안 맞아도 중단 말고 무조건 완주' → --gate-force-start (B1-04 · 05) (원장 10:1x)"),
                ("(채팅) 영훈 10:5x", "'원래 기준대로 하되 강제 시작은 30분' → --gate-force-after-s 1800 (B1-06 ~) (원장 10:5x)"),
                ("조민규_답_1015b_P0수신_정정8.txt", "2026-10-15 10:0x (조민규 · P0 수신 정정 8) · 프롬프트_M8_추가지시3_1015.md"),
                ("(채팅) 조민규 12:4x (영훈 전달)", "게이트 변경 허용 · 별도 개정 · 기존 보존 → 등록 v4 (원장 12:4x)"),
                ("조민규_답_1015c_DEV블록1수신_정정6.txt", "2026-10-15 19:3x (조민규 · 블록 1 수신 정정 6) · 프롬프트_M8_추가지시4_1015.md → 이 묶음")]


def pick(rows: list[dict], key: str, target: float | None, method: str, tol: float) -> dict:
    """온도 파생 (정정 3판): key = 'up' (기기 CLOCK_BOOTTIME s · progress mono_ns/1e9 와 같은 시계) 또는 'epoch' (host). method 'nearest' = |t − target| 최소 (양쪽) · 'before' = target 이전 (≤) 가장 늦은 표본 (직전 실측). tol 밖/없음 = null."""
    if target is None or not rows:
        return dict(AP=None, SKIN=None, sample=None, delta_s=None, method=method, note="null (표본/시계 정렬 없음)")
    cand = [r for r in rows if r.get(key) is not None and (r[key] <= target if method == "before" else True)]
    if not cand:
        return dict(AP=None, SKIN=None, sample=None, delta_s=None, method=method, note="null (target 이전 표본 없음)")
    r = min(cand, key=lambda x: abs(x[key] - target))
    d = r[key] - target
    if abs(d) > tol:
        return dict(AP=None, SKIN=None, sample=r[key], delta_s=round(d, 3), method=method, note=f"null (|delta| {abs(d):.1f} s > {tol} s)")
    return dict(AP=r["AP"], SKIN=r["SKIN"], sample=r[key], delta_s=round(d, 3), method=method, note="")


def slope_ok(last: dict, slope_max: float):
    """0 · -0.0 은 유효한 숫자 (abs <= slope_max 통과) · None/결측 = null (조민규 10/15 정정 1 · v1 은 `or 9` 로 0 을 결측 취급했음)."""
    a, b = last.get("ap_slope_c_per_min"), last.get("skin_slope_c_per_min")
    if a is None or b is None:
        return None
    return abs(float(a)) <= slope_max and abs(float(b)) <= slope_max


def host_source_at(t: str) -> str:
    src = HOST_SOURCE_BY_LAUNCH[0][1]
    for ts, sha in HOST_SOURCE_BY_LAUNCH:
        if t and t >= ts:
            src = sha
    return src


def hal_rows(p: Path) -> list[dict]:
    out = []
    if not p or not p.is_file():
        return out
    with open(p, encoding="utf-8-sig", errors="replace", newline="") as f:
        for r in csv.DictReader(f):
            try:
                out.append(dict(epoch=float(r["host_ms"]) / 1000, up=float(r["device_uptime_s"]) if r.get("device_uptime_s") else None, AP=float(r["AP"]) if r.get("AP") else None, SKIN=float(r["SKIN"]) if r.get("SKIN") else None,
                                BAT=float(r["BAT"]) if r.get("BAT") else None, SOC=int(float(r["level"])) if r.get("level") else None))
            except (ValueError, KeyError):
                pass
    return out


def nearest(rows: list[dict], epoch: float | None, tol: float = 6.0) -> dict:
    if epoch is None or not rows:
        return {}
    r = min(rows, key=lambda x: abs(x["epoch"] - epoch))
    return r if abs(r["epoch"] - epoch) <= tol else {}


def varint(b: bytes, i: int):
    v = s = 0
    while True:
        c = b[i]; i += 1
        v |= (c & 0x7F) << s; s += 7
        if not c & 0x80:
            return v, i


def proto_fields(b: bytes):
    """top-level (field, wire, payload-or-value) iterator — TracePacket 의 필드 번호만 센다 (스키마 없이)."""
    i = 0
    while i < len(b):
        key, i = varint(b, i)
        f, w = key >> 3, key & 7
        if w == 0:
            v, i = varint(b, i); yield f, w, v
        elif w == 2:
            n, i = varint(b, i); yield f, w, b[i:i + n]; i += n
        elif w == 1:
            yield f, w, b[i:i + 8]; i += 8
        elif w == 5:
            yield f, w, b[i:i + 4]; i += 4
        else:
            return


def perfetto_evidence(trace: Path) -> dict:
    b = trace.read_bytes()
    packets = 0; ts = []; fields = {}
    try:
        for f, w, payload in proto_fields(b):
            if f == 1 and w == 2:
                packets += 1
                for ff, ww, vv in proto_fields(payload):
                    fields[ff] = fields.get(ff, 0) + 1
                    if ff == 8 and ww == 0:
                        ts.append(vv)
        parse_ok = True
    except Exception as e:  # noqa: BLE001
        parse_ok = False
    names = {38: "battery (BatteryCounters)", 40: "power_rails", 44: "trace_config", 45: "trace_stats", 33: "clock_snapshot", 35: "track_event", 39: "android_log", 43: "sys_stats", 52: "service_event"}
    return dict(file=str(trace), sha256=C.sha256_file(trace), bytes=len(b), parse_ok=parse_ok, packets=packets,
                field_counts={f"{k} {names.get(k, '')}".strip(): v for k, v in sorted(fields.items())},
                timestamp_ns_min=min(ts) if ts else None, timestamp_ns_max=max(ts) if ts else None, span_s=((max(ts) - min(ts)) / 1e9) if ts else None,
                battery_counter_packets=fields.get(38, 0), power_rails_packets=fields.get(40, 0),
                method="protobuf wire 스캔 (스키마 없음 · trace_processor 미설치 — 패킷 수 · 필드 번호 · timestamp 범위만) · '오버헤드 검증 완료' 아님",
                strings_found=[s for s in ("android.power", "battery", "linux.sys_stats") if s.encode() in b])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, default=REPO / "results")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--onedrive", type=Path, required=True)
    ap.add_argument("--rev", type=int, default=1, help="2 = 조민규 10/15 21:xx 정정 (slope 0 · B1-03 이벤트 연결 · EDD a2 대표 문구/열 · 휴식 원점) → out/v2/ (v1 파일 보존)")
    args = ap.parse_args()
    M8.activate()
    out = args.out / f"v{args.rev}" if args.rev >= 2 else args.out
    out.mkdir(parents=True, exist_ok=True)
    agg_source = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=str(REPO)).stdout.strip()
    blocks = C.read_json(PLAN_ROOT / "plan_m8/blocks.json")
    b1 = next(b for b in blocks["stages"]["dev_blocks"] if b["block_no"] == 1)
    labels = {s["label"]: s for s in b1["sessions"]}
    evs = [json.loads(l) for l in (args.results / "S26_M8_driver_events.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    runs = [e for e in evs if e.get("what") == "run_end" and e.get("run_kind") == "dev" and str(e.get("label", "")).startswith("B1-")]
    forced = [e for e in evs if e.get("what") == "gate_forced_start" and str(e.get("label", "")).startswith("B1-")]
    trefs = C.read_json(args.results / "S26_M8_tref.json")
    pre = [json.loads(l) for l in (args.results / "S26_M8_prestart_ledger.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    pre_b1 = [r for r in pre if str(r.get("label", "")).startswith("B1-") or r.get("label") == "Tref_day"]
    dev_root = args.results / "S26_M8_DEV"
    # ---------------- ① consumption
    cons = []
    for lab, s in labels.items():
        plan = C.read_json(PLAN_ROOT / s["plan_dir"] / "plan.json")
        pe = next(e for e in plan["sessions"] if e["index"] == s["index"])
        folder_name = f"S26_MIXREQ_{s['index']:02d}_{pe['policy']}"
        attempts = sorted(set((r.get("attempt") or 1) for r in runs if r["label"] == lab and r.get("rc") is not None))
        rep_done = False
        for a in attempts or [1]:
            folder = dev_root / s["plan_dir"] / f"{folder_name}_a{a}"
            rr = [r for r in runs if r["label"] == lab and r.get("attempt") == a and r.get("rc") is not None]
            r = rr[-1] if rr else {}
            v = C.read_json(folder / "validated.json") if (folder / "validated.json").is_file() else {}
            before = C.read_json(folder / "validated_before_coverage_fix_1015.json") if (folder / "validated_before_coverage_fix_1015.json").is_file() else None
            summ = C.read_json(folder / "device" / "summary.json") if (folder / "device" / "summary.json").is_file() else {}
            app_started = (folder / "host" / "session_log.json").is_file() and bool(C.read_json(folder / "host" / "session_log.json").get("start_time"))
            completed = (folder / "device" / "summary.json").is_file()
            planned = pe["requests"]
            done = (v.get("counts") or {}).get("succeeded") if v else None
            rc = r.get("rc")
            if rc == 5:
                cons.append(dict(label=lab, experiment_id=s["experiment_id"], index=s["index"], session_id=s["session_id"], attempt=a, event="rc5_folder_collision", app_start=False, completed=False,
                                 eligible=None, eligible_before_fix=None, requests_planned=planned, requests_completed=0, representative=False, device_raw="없음 (앱 시작 0)",
                                 reason="호스트 폴더 이름 (index+policy) 충돌 → 앱 START 0 · 별도 행 (사고 2 · 10:07)"))
                continue
            rep = bool(v.get("eligible")) and not rep_done
            if rep:
                rep_done = True
            hl = C.read_json(folder / "host" / "session_log.json") if (folder / "host" / "session_log.json").is_file() else {}
            mf = C.read_json(folder / "device" / "manifest.json") if (folder / "device" / "manifest.json").is_file() else (C.read_json(folder / "host" / "manifest_pushed.json") if (folder / "host" / "manifest_pushed.json").is_file() else {})
            raw_dir = args.out / "EDD_a1_device_raw" / "app_files_a1"
            is_edd_a1 = (lab == "B1-06-M128_ORDER" and a == 1)
            a1_dev_done = (sum(1 for x in raw_dir.glob("*.result.json")) if (is_edd_a1 and raw_dir.is_dir()) else "")
            cons.append(dict(label=lab, experiment_id=s["experiment_id"], index=s["index"], session_id=s["session_id"], attempt=a, event=("stall_rc4" if rc == 4 else "run"), app_start=app_started,
                             completed=completed, eligible=v.get("eligible"), eligible_before_fix=(before or {}).get("eligible") if before else "",
                             requests_planned=planned, requests_completed=done if done is not None else (len(summ.get("rows", [])) if summ else 0),
                             representative=rep, device_raw=("회수 (EDD_a1_device_raw/ · 읽기 전용 pull · 재실행 0)" if is_edd_a1 else "세션 폴더 device/"),
                             reason=(("a2 유효 = 대표 (a1 = stall · host 회수실패)" if a == 2 else "a1 유효 = 대표 (첫 유효 시도)") if rep else ("추가 시도 · 보존 · 대표 아님 (a1 이 검사기 고침 재검증으로 유효)" if v.get("eligible") else
                                     ("adb 끊김 stall · a1 소비 · host 회수실패 (당시) · 기기 완료 128 은 뒤 회수 (별도 열)" if rc == 4 else "무효"))),
                             a1_host_recovery_at_run=("실패 (adb 끊김 · observe lost · pull 0)" if is_edd_a1 else ""), a1_device_completed_recovered=a1_dev_done,
                             partner_check_note=("조민규 10/15 검산: a1 납기 30+4 = 34/128 · 대표 a2 39+7 = 46/128 (이쪽 계산 0 · 기록만)" if lab == "B1-06-M128_ORDER" else ""),
                             command_id=hl.get("command_id"), host_start=hl.get("start_time"), host_end=hl.get("end_time"), source_path=folder.relative_to(args.results).as_posix(),
                             manifest_split=mf.get("split"), analysis_split=mf.get("analysis_split"), stage=mf.get("stage"), split_note="manifest.split = confirmation (앱 경로 · 실제 세션) · analysis_split = dev (분석 역할) — 둘은 다른 뜻"))
    tot_planned = sum(labels[l]["index"] * 0 + next(e for e in C.read_json(PLAN_ROOT / labels[l]["plan_dir"] / "plan.json")["sessions"] if e["index"] == labels[l]["index"])["requests"] for l in labels)
    with open(out / "b1_consumption.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cons[0].keys())); w.writeheader(); w.writerows(cons)
    app_starts = sum(1 for c in cons if c["app_start"])
    completed_n = sum(1 for c in cons if c["completed"])
    req_completed_all = sum(c["requests_completed"] or 0 for c in cons)
    req_rep = sum(c["requests_completed"] or 0 for c in cons if c["representative"])
    # ---------------- ② gate ledger
    gl = []
    n16 = 0
    for r in pre_b1:
        res = r.get("result")
        if res in ("PRESTART_REJECT", "GATE_UNDECIDABLE"):
            n16 += 1
            d = (r.get("decisions") or [{}])[-1]
            wrong = (r.get("tref") == 28.7)
            gl.append(dict(t=r["t"], label=r["label"], kind="prestart_reject", result=res, reason=r.get("reason"), waited_s=r.get("waited_s"), tref=r.get("tref"), ap_last=d.get("ap_median"),
                           ap_slope_last=d.get("ap_slope_c_per_min"), soc=d.get("soc"), counts_in_ledger_16=True, counts_in_report_14=(not wrong),
                           note=("잘못된 Tref 28.7 (충전 열) 기준 거절 · 보고 14 에서 뺀 2건" if wrong else "")))
        elif res == "GATE_UNDECIDABLE_POLL":
            gl.append(dict(t=r["t"], label=r["label"], kind="undecidable_poll", result=res, reason=";".join(r.get("reason") or []), waited_s="", tref="", ap_last="", ap_slope_last="", soc="",
                           counts_in_ledger_16=False, counts_in_report_14=False, note="판정 불가 폴 (REJECT 아님 · 별개 열)"))
        elif res == "TREF_UNDECIDABLE":
            gl.append(dict(t=r["t"], label="Tref", kind="tref_undecidable", result=res, reason=r.get("reason"), waited_s="", tref="", ap_last="", ap_slope_last="", soc="", counts_in_ledger_16=False, counts_in_report_14=False, note=""))
    for k, v in trefs.items():
        gl.append(dict(t=v.get("t"), label="Tref", kind="tref_derivation", result=("valid" if k != "2026-10-15_day_b1" else "invalid_reference"), reason=k, waited_s=v.get("idle_before_search_s"), tref=v.get("tref_c"),
                       ap_last=v.get("ap_median"), ap_slope_last=v.get("ap_slope_c_per_min"), soc="", counts_in_ledger_16=False, counts_in_report_14=False,
                       note={"2026-10-15": "새벽 P0 (유휴 1,200 s 뒤)", "2026-10-15_day_b1": "08:28 충전 분리 13 min 뒤 (고정 유휴 생략) → 유휴 조건 아님 → B1-00 · B1-02 · 보충 r2 는 이 값으로 START · 09:58 폐기",
                             "2026-10-15_day_b1r": "10:04 유휴 37 min 뒤 재산출 → B1-03 ~ B1-18", "2026-10-15_b2": "블록 2 (유휴 1,200 s 뒤)"}.get(k, "")))
    for e in forced:
        gl.append(dict(t=e["t"], label=e["label"], kind="forced_start", result="FORCED_START", reason=e.get("reason"), waited_s=e.get("waited_s"), tref=e.get("tref"), ap_last=(e.get("last") or {}).get("ap_median"),
                       ap_slope_last=(e.get("last") or {}).get("ap_slope_c_per_min"), soc=(e.get("last") or {}).get("soc"), counts_in_ledger_16=False, counts_in_report_14=False,
                       note=("즉시 강제 (--gate-force-start · 영훈 10:1x)" if e.get("cumulative_wait_s") is None else f"누적 {e.get('cumulative_wait_s')} s ≥ 1800 강제 (--gate-force-after-s · 영훈 10:5x)")))
    gl.append(dict(t="2026-10-15T10:03:17", label="B1-03-RECENT_IDLE60_C252_GPU", kind="extra_gate_after_wrong_tref", result="regate", reason="Tref 28.7 거절 2회는 잘못된 기준값 → 재산출 뒤 재게이트 1회 (등록 밖 · 조민규 판단)",
                   waited_s="", tref=27.2, ap_last="", ap_slope_last="", soc="", counts_in_ledger_16=False, counts_in_report_14=False, note="10:07 rc 5 (폴더 충돌) → 10:10 재시작 → 10:10 START · 유효"))
    gl.append(dict(t="2026-10-15T11:19:52", label="B1-06-M128_ORDER", kind="retry_rest_short", result="a1 stall → a2", reason="adb 끊김 11:17 → a1 rc 4 (앱 시작 · 소비) → 드라이버 재시작 → a2 11:28:13",
                   waited_s=501.181, tref="", ap_last="", ap_slope_last="", soc="", counts_in_ledger_16=False, counts_in_report_14=False,
                   note="휴식 (원점별): host driver_events run_end(a1 rc4) 11:19:52.415 → run_start(a2) 11:28:13.596 = 501.181 s · driver_log RESULT 11:19:52 → RUN 11:28:13 = 501 s (초 분해능) · host session_log a1 end 11:19:31 → a2 start 11:28:17 = 526 s · 기기 a1 cleanup mono → a2 session_start mono = 482.336 s · 등록 600 s 미만 · 재시작이 잔여 휴식을 복원하지 않음 → 다음 드라이버 (CONFIRM 판)"))
    gl.append(dict(t="2026-10-15T13:28:37", label="B1-11-M128_PAIR_N", kind="restart_gate_accumulation", result="restart", reason="adb 끊김 13:26 (재시도 게이트 중 · 앱 시작 0) → 재시작 → 거절 누적 다시 0 부터 (1차 606 + 300 + 재시도 910 → 강제)",
                   waited_s="", tref=27.2, ap_last="", ap_slope_last="", soc="", counts_in_ledger_16=False, counts_in_report_14=False, note="재시작 전 13:13 REJECT(slope) 1건 + 재시작 뒤 13:39 REJECT(tref) · 14:00 강제 → 같은 자리 거절 3건"))
    gl.sort(key=lambda x: str(x["t"]))
    with open(out / "b1_gate_ledger.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(gl[0].keys())); w.writeheader(); w.writerows(gl)
    # ---------------- ④ session table v2
    orig = list(csv.DictReader(open(PLAN_ROOT / "dev/block1/tables/session_table_m8.csv", encoding="utf-8")))
    v2 = []
    for row in orig:
        if row["stage"] != "dev":
            continue
        cands = [(i, r) for i, r in enumerate(evs, 1) if r.get("what") == "run_end" and r.get("run_kind") == "dev" and r["label"] == row["label"] and str(r.get("attempt")) == row["attempt"] and r.get("rc") is not None]
        hl = C.read_json(dev_root / row["folder"].split("/", 1)[1] / "host" / "session_log.json") if "/" in row["folder"] and (dev_root / row["folder"].split("/", 1)[1] / "host" / "session_log.json").is_file() else {}
        match = [(i, r) for i, r in cands if (r.get("times") or {}).get("host_start") == hl.get("start_time")] or [(i, r) for i, r in cands if r.get("rc") == 0] or cands[-1:]
        ev_row, ev = match[-1] if match else (None, {})
        gate = ev.get("gate") or {}
        last = (gate.get("decisions") or [{}])[-1]
        H = hal_rows(Path(ev["hal_csv"])) if ev.get("hal_csv") else []
        t = ev.get("times") or {}
        app_start = nearest(H, t.get("host_start_epoch"))
        common = nearest(H, t.get("origin_host_epoch"))
        first_pre = nearest(H, (t.get("origin_host_epoch") or 0) + M8.FIRST_OFFSET_US / 1e6 - 2.5) if t.get("origin_host_epoch") else {}
        prov = {}
        if args.rev >= 3:
            folder = dev_root / row["folder"].split("/", 1)[1] if "/" in row["folder"] else None
            cb = C.read_json(folder / "device" / "common_boundary.json") if folder and (folder / "device" / "common_boundary.json").is_file() else {}
            common_ns = cb.get("start_ns")
            first_ns = min((x["scheduled_arrival_ns"] for x in cb.get("rows", []) if x.get("scheduled_arrival_ns") is not None), default=None)
            ss_ns = None
            prog = folder / "device" / "progress.jsonl" if folder else None
            if prog and prog.is_file():
                for line in prog.read_text(encoding="utf-8", errors="replace").splitlines():
                    if '"session_start"' in line:
                        ss_ns = json.loads(line).get("mono_ns"); break
            pc = pick(H, "up", common_ns / 1e9 if common_ns else None, "nearest", 6.0)
            pf = pick(H, "up", first_ns / 1e9 if first_ns else None, "before", 10.0)
            pa = pick(H, "epoch", t.get("host_start_epoch"), "nearest", 6.0)
            pd = pick(H, "up", ss_ns / 1e9 if ss_ns else None, "nearest", 6.0)
            hal_sha = C.sha256_file(Path(ev["hal_csv"])) if ev.get("hal_csv") and Path(ev["hal_csv"]).is_file() else None
            prov = dict(hal_path=(Path(ev["hal_csv"]).name if ev.get("hal_csv") else None), hal_sha256=hal_sha, clock_note="common/first/device_session_start = 기기 CLOCK_BOOTTIME (HAL device_uptime_s = progress mono_ns/1e9) · app_start = host 시계 (HAL host_ms vs session_log start_time)",
                        common_target_ns=common_ns, common_sample_up_s=pc["sample"], common_delta_s=pc["delta_s"], common_method="nearest (양쪽 · ≤ 6 s)", common_AP=pc["AP"], common_SKIN=pc["SKIN"], common_note=pc["note"],
                        first_request_target_ns=first_ns, first_request_rule="target = min(common_boundary.rows.scheduled_arrival_ns) (= common0 + 35 s) · 표본 = target 이전 (≤) 가장 늦은 HAL 표본 · ≤ 10 s · 이후 표본은 쓰지 않음 (직전 실측)",
                        first_request_pre_sample_up_s=pf["sample"], first_request_pre_delta_s=pf["delta_s"], first_request_pre_method="before (≤ target · ≤ 10 s)", first_request_pre_AP=pf["AP"], first_request_pre_SKIN=pf["SKIN"], first_request_pre_note=pf["note"],
                        app_start_target_host_epoch=t.get("host_start_epoch"), app_start_sample_host_epoch=pa["sample"], app_start_delta_s=pa["delta_s"], app_start_method="host 호출시각 (session_log start_time) 근접 HAL (nearest · ≤ 6 s) — 기기 session_start · 앱 직접 센서와 다름",
                        app_start_AP=pa["AP"], app_start_SKIN=pa["SKIN"], app_start_note=pa["note"],
                        device_session_start_target_ns=ss_ns, device_session_start_sample_up_s=pd["sample"], device_session_start_delta_s=pd["delta_s"], device_session_start_AP=pd["AP"], device_session_start_SKIN=pd["SKIN"], device_session_start_method="nearest (≤ 6 s · 기기 시계)",
                        gate_last_method="게이트 마지막 판정의 60 s 창 AP/SKIN 중앙값 (표본 1개 아님 · host 시계)")
        r2 = dict(row)
        r2.update(gate_last_t=last.get("t"), gate_last_AP=last.get("ap_median"), gate_last_SKIN=last.get("skin_median"), gate_last_SOC=last.get("soc"), gate_last_ap_slope=last.get("ap_slope_c_per_min"),
                  app_start_AP=app_start.get("AP"), app_start_SKIN=app_start.get("SKIN"), app_start_SOC=app_start.get("SOC"), common_start_AP=common.get("AP"), common_start_SKIN=common.get("SKIN"), common_start_SOC=common.get("SOC"),
                  first_request_pre_AP=first_pre.get("AP"), first_request_pre_SKIN=first_pre.get("SKIN"),
                  AP_band_ok=(abs(last["ap_median"] - gate["tref"]) <= (gate.get("band_c") or 0.5)) if (last.get("ap_median") is not None and gate.get("tref") is not None) else None,
                  slope_ok=slope_ok(last, gate.get("slope_max") or 0.1), ap_slope_raw=repr(last.get("ap_slope_c_per_min")), skin_slope_raw=repr(last.get("skin_slope_c_per_min")),
                  event_row=ev_row, event_rc=ev.get("rc"), command_id=hl.get("command_id"), session_id_key=row.get("session_id"), host_start_key=hl.get("start_time"),
                  hal_method="nearest HAL row <= 6 s (보간 아님 · 없으면 null) · start_* 는 게이트 전", app_start_method=("nearest" if app_start else "null (정렬 규약 없음)"), **({} if args.rev < 3 else dict(v2_common_start_AP_deprecated=common.get("AP"), v2_first_request_pre_AP_deprecated=first_pre.get("AP"))),
                  gate_passed=(gate.get("result") == "start"), forced=bool(gate.get("forced_start")), gate_version=gate.get("gate_version") or "v2",
                  apk_source=APK_SOURCE, host_source_at_run=host_source_at(row.get("start_time") or ev.get("t")), aggregation_source=agg_source,
                  start_AP_note="start_* = 게이트 대기 전 (HAL 시작 시) 값 · 시작 조건은 gate_last_* / app_start_* / common_start_* 열")
        if args.rev >= 3:
            for k in ("common_start_AP", "common_start_SKIN", "common_start_SOC", "first_request_pre_AP", "first_request_pre_SKIN", "app_start_AP", "app_start_SKIN"):
                r2.pop(k, None)   # v2 의 이벤트 시각 기반 값 (common 로그 발행 시각 + 오프셋) 은 폐기 → prov 열로 대체
            r2.update(prov)
        v2.append(r2)
    with open(out / "session_table_m8_v2.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(v2[0].keys())); w.writeheader(); w.writerows(v2)
    if args.rev >= 2:
        ev_rows = [dict(label=r["label"], attempt=r["attempt"], ap_slope_raw=r["ap_slope_raw"], skin_slope_raw=r["skin_slope_raw"], slope_ok=r["slope_ok"], AP_band_ok=r["AP_band_ok"], forced=r["forced"],
                        is_zero=(r["ap_slope_raw"] in ("0.0", "-0.0") or r["skin_slope_raw"] in ("0.0", "-0.0")), is_none=("None" in (r["ap_slope_raw"], r["skin_slope_raw"]))) for r in v2]
        (out / "slope_check_evidence.json").write_bytes(C.canonical_json(dict(rule="slope_ok = (ap is not None and skin is not None) and abs(ap) <= max and abs(skin) <= max · 0.0 / -0.0 = 숫자 (통과) · None = null",
            v1_bug="v1: abs(x or 9) → 0.0 이 falsy 라 9 로 바뀌어 실패 처리 (B1-05 · 08 · 09 · 12)", generator="s26/tools/mixreq/m8_b1_corrections.py (--rev 2)", aggregation_source=agg_source, rows=ev_rows)))
    # ---------------- ③ registration versions · plan supp · instructions index
    (out / "registration").mkdir(exist_ok=True)
    regrows = []
    for ver, rel, commit, sealed, scope in REG:
        p = REPO / rel
        if p.is_file():
            shutil.copy2(p, out / "registration" / p.name)
        regrows.append(dict(version=ver, file=rel, sha256=C.sha256_file(p) if p.is_file() else None, commit=commit, sealed=sealed, applied_scope=scope))
    with open(out / "registration_versions.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(regrows[0].keys())); w.writeheader(); w.writerows(regrows)
    if (PLAN_ROOT / "plan_m8l64_supp").is_dir():
        if (out / "plan_m8l64_supp").exists():
            shutil.rmtree(out / "plan_m8l64_supp")
        shutil.copytree(PLAN_ROOT / "plan_m8l64_supp", out / "plan_m8l64_supp")
        shutil.copy2(PLAN_ROOT / "plan_m8/p0_supp.json", out / "p0_supp.json")
    lines = ["# instructions_index — 원장에 인용한 지시 · 답 (파일 + 시각) · 10/15", "", "| 파일 / 채팅 | 시각 · 내용 | 있음 |", "|---|---|---|"]
    for name, when in INSTRUCTIONS:
        p = args.onedrive / name
        lines.append(f"| `{name}` | {when} | {'예 (' + C.sha256_file(p)[:12] + '…)' if p.is_file() else '채팅 (파일 없음 · 원장 인용)'} |")
    (out / "instructions_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # ---------------- 1015b #3 gate contract table
    gate_v2 = C.read_json(PLAN_ROOT / "contract_v2/gate_m8.json")
    (out / "gate_contract_table.json").write_bytes(C.canonical_json(dict(
        note="유효 계약 한 표 (1015b #3): 옛 규칙 (참고만) vs 적용값",
        legacy_reference_only=dict(soc_band="40~80 (조민규 제안 · 참고 열)", skin_rule="SKIN 29.5~31.5 (M6/M7 start band · M8 미사용 · --skin-band 0,100)", tref_v1="TREF_DAY_IDLE_MEDIAN_V1 (SKIN 120 s · 제안 · 미사용)"),
        applied=dict(block1=dict(gate_version="v2", tref="TREF_DAY_FIRST_STABLE_AP60_V2 (키 day_b1 28.7 → day_b1r 27.2)", band_c=0.5, window_s=60, slope_max=0.1, soc_min=20, soc_max=None,
                                 operation="영훈: 즉시 강제 START (B1-04·05) · 누적 1,800 s 강제 START (B1-06~) · 고정 유휴 생략"),
                     block2=dict(gate_version="v5", tref="같은 산출법 (키 b2 26.8 · 유휴 1,200 s 뒤)", band_c=1.0, window_s=120, slope_max=0.2, soc_min=20, soc_max=None, operation="누적 1,800 s 강제 START"),
                     next_driver=dict(stable_miss="TREF_UNDECIDABLE 로 남김 (대체값 Tref 사용 0) · CONFIRM 판부터", hal_path="gate_attempt_id 별 HAL csv · SHA (재시도가 label_a1 을 덮지 않음) · CONFIRM 판부터",
                                      restart="재시작 시 잔여 휴식 · 거절 한도 복원 · CONFIRM 판부터")),
        source_v2_json=dict(file="s26/results/m8_prep/contract_v2/gate_m8.json", sha256=C.sha256_file(PLAN_ROOT / "contract_v2/gate_m8.json"), keys=list(gate_v2)))))
    # ---------------- ⑥ perfetto
    tr = args.results / "S26_M8_P0" / "perfetto_PERFETTO_ON_C32_r2.perfetto-trace"
    pf = perfetto_evidence(tr) if tr.is_file() else dict(file=str(tr), missing=True)
    pf.update(original_on_session="PERFETTO_ON_C32 (L64 idx 2 · 04:01 유효 · trace 0 · 실질 OFF · 실제 bank = L64 (C32+D32)) 보존", r2="PERFETTO_ON_C32_r2 (L64 idx 8 · 08:28 ~ 08:33 유효 · 추가 장치 시도 1 · 등록 v3 부록)",
              claim="지원 확인 (정상 trace 1개) · 오버헤드 정량 아님 · 정책 비교군 (DEV · CONFIRM) 은 전부 Perfetto OFF")
    (out / "perfetto_r2_evidence.json").write_bytes(C.canonical_json(pf))
    # ---------------- 1015b #7 delegate evidence (순서 기반 연결 · TID 는 Java thread id 라 logcat tid 와 다름)
    drows = []
    pat = re.compile(r"Replacing (?P<x>\d+) out of (?P<y>\d+) node\(s\) with delegate \((?P<name>[^)]+)\)|GpuEnvironment|LiteRT GPU|NPU|Npu|ENN|dispatch|partition", re.I)
    for row in v2:
        folder = dev_root / row["folder"].split("/", 1)[1] if "/" in row["folder"] else None
        if not folder or not (folder / "host" / "logcat_threadtime.txt").is_file():
            continue
        pid = ""   # runner PID = 'Replacing … with delegate' 줄이 가장 많은 PID (앱 cleanup.json 엔 pid 없음) · 아래에서 정함
        starts = []
        prog = folder / "device" / "progress.jsonl"
        for l in (prog.read_text(encoding="utf-8", errors="replace").splitlines() if prog.is_file() else []):
            if '"runtime_return"' in l:
                e = json.loads(l); starts.append(e)
        logs = []
        for line in (folder / "host" / "logcat_threadtime.txt").read_text(encoding="utf-8", errors="replace").splitlines():
            m = TT_RE.match(line)
            if m:
                logs.append(dict(m.groupdict(), tag=m.group("tag").strip()))
        cnt = {}
        for x in logs:
            if CME.REPLACE_RE.search(x["msg"]):
                cnt[x["pid"]] = cnt.get(x["pid"], 0) + 1
        pid = max(cnt, key=cnt.get) if cnt else ""
        mine = [x for x in logs if x["pid"] == pid and (CME.REPLACE_RE.search(x["msg"]) or pat.search(x["msg"]))]
        repl = [x for x in mine if "Replacing" in x["msg"]]
        for i, x in enumerate(repl):
            rt = starts[i] if i < len(starts) else {}
            drows.append(dict(label=row["label"], attempt=row["attempt"], runner_pid=pid, logcat_tid=x["tid"], logcat_time=x["ts"], tag=x["tag"], msg=x["msg"][:200],
                              runtime_key_by_order=rt.get("key"), model_sha256=rt.get("model_sha256"), engine=rt.get("engine"), litert_version=rt.get("litert_version"),
                              join_method="runtime_return 순서 ↔ Replacing 줄 순서 (같은 PID) · TID 직접 연결 불가 (앱 thread_id = Java id)", requested_backend=(rt.get("key") or "").rsplit("_", 1)[-1],
                              npu_note=("컴파일 모델 SHA 311e4aac… (efficientnet_lite0_Samsung_E9965) · 품질 조건 = FP16 NPU (별도 Q 판정)" if (rt.get("key") or "").endswith("NPU") else "")))
        other = [x for x in mine if "Replacing" not in x["msg"]]
        drows.append(dict(label=row["label"], attempt=row["attempt"], runner_pid=pid, logcat_tid="", logcat_time="", tag="", msg=f"기타 delegate/accelerator 줄 {len(other)}건 (등록·로드 줄 = 증거 아님 · CME 규칙)",
                          runtime_key_by_order="", model_sha256="", engine="", litert_version="", join_method="", requested_backend="", npu_note=""))
    if drows:
        with open(out / "delegate_evidence_m8.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(drows[0].keys())); w.writeheader(); w.writerows(drows)
    # ---------------- README (⑤ 문구 · 대표 규칙 · 횟수)
    readme = f"""# M8 블록 1 정정 묶음 (조민규 10/15 19:3x 답 정정 6 · 10:0x 답 정정 8 중 #3 #5 #7) — 블록 1 결과 변경 0 · 재측정 0 · 집계 source `{agg_source}` · {dt.datetime.now().isoformat(timespec='seconds')}

## 횟수 · 소비 (①)
- 계획 자리 19 (19군 × 1) · 사전 게이트 시도 (prestart ledger 거절) **{n16}** (보고 14 = 잘못된 Tref 28.7 의 B1-03 2건 제외) · 판정 불가 폴 별개 열 · **앱 START {app_starts} = 완료 {completed_n} + 회수실패 1 (B1-06 EDD a1 · adb 끊김 stall)** · 폴더 충돌 rc 5 = 앱 START 0 (별도 행).
- 19군 대표 결과 = {req_rep:,} 요청 · 추가 시도 포함 완료 {req_completed_all:,} (B1-01 CPU252 a2 포함). "실패 0 / 19회만 실측" 이라 쓰지 않음.
- **대표 선택 규칙**: 군마다 **첫 유효 시도** (검사기 A0~A10 · coverage 고침 뒤 재검증 포함) = 대표. B1-01: a1 (수정 전 무효 → 수정 후 유효) = 대표 · a2 (유효) = 추가 시도 보존 (대표 아님). B1-06: a1 stall (앱 START · 회수실패 · device raw 회수) · a2 = 대표.
- B1-06 EDD a1 device raw: `EDD_a1_device_raw/` (폰 `/data/local/tmp/mixreq/sessions/<sid>/a1` 2 파일 + 앱 `files/mixreq/<sid>/a1` 265 파일 · 읽기 전용 pull · 재실행 0).

## 게이트 소비 (② `b1_gate_ledger.csv`)
- Tref 28.7 (충전 열 · 유휴 조건 아님) → 27.2 재산출 · 강제 START 5 (B1-04 · 05 즉시 / B1-10 · 11 · 18 누적 1,800 s) · B1-03 추가 게이트 · B1-11 재시작 뒤 거절 누적 · B1-06 a1→a2 휴식 ≈ 501 s (< 600) — 각각 별도 행.
- 통과 못 한 자리 · 강제 START 는 정상 PASS 로 바꾸지 않음 → `session_table_m8_v2.csv` 의 `AP_band_ok` · `slope_ok` · `gate_passed` · `forced` 네 열.
- 다음 드라이버 (CONFIRM 판 · 블록 2 는 3344119f4 고정): 재시작 시 잔여 휴식 · 거절 한도 복원 · gate_attempt_id 별 HAL 경로/SHA · stable_miss = TREF_UNDECIDABLE.

## 버전 (③ `registration_versions.csv` · `registration/` · `instructions_index.md`)
- 블록 1 = 등록 v2 계약 + v3 운영 (게이트 v2 + 영훈 강제 START) · 블록 2 = v2 계약 + v4/v5 게이트 (16:54 부터 · 드라이버 3344119f4) · v4 · v5 블록 1 소급 0.
- `source_commit` 세 열: 측정 APK source = `{APK_SOURCE}` (P0 ZIP 그대로) · 실행 당시 host source (드라이버 시작 시각별) · 이번 집계 source = `{agg_source}`.

## 해석 문구 (⑤ · readout · 보고에 그대로)
- M128 (블록 1 · 각 1회): 직렬 BASE 긴급 13/96 · 일반 11/32 기한 내 · EDD 긴급 39/96 · 일반 7/32 · 병행 PAIR_G/PAIR_N 96/96 · 32/32 → "EDD 는 긴급 개선 대신 일반 손해 · WAIT 는 이번 조건에서 손해" 처럼 **장점과 손해를 같이** 적는다 · 우위/절감 판정 아님.
- WAIT 실제 합 3228.921486 / 2420.040116 / 12022.011016 ms (200x16 / 200x12 / 1000x12) 그대로 보존 · 명목 12 s ≠ 실제 cap ("명목 WAIT 실측").
- **L64 PAIR = 실제 겹침 0 → 병행 효과 대조로 세지 않음** (새 부하는 새 등록 · 현재 입력을 결과에 맞춰 바꾸지 않음).
- C252 RECENT/IDLE 252/252 → "납기 지표만으로 열 이력 효과 없음" 이라 쓰지 않음 · AP 는 시작 조건/이력 차이 → 기술 통계만 · 에너지/열 최종 판정 없음.
- 단일 PNG · 새 session ID/seed = 독립 세션 반복 · 새 이미지 일반화 아님.

## Perfetto r2 (⑥ `perfetto_r2_evidence.json`)
- 원 ON trace 0 보존 (실제 bank = L64) · r2 {pf.get('bytes')} B · SHA `{pf.get('sha256')}` · 패킷 {pf.get('packets')} · battery 카운터 패킷 {pf.get('battery_counter_packets')} · 범위 {pf.get('span_s')} s · parse = protobuf wire 스캔 (trace_processor 미설치) → "지원 확인" 까지 · "오버헤드 검증 완료" 아님 · 보충 1 시도 소비 원장.

## delegate 증거 (`delegate_evidence_m8.csv` · 1015b #7)
- logcat `Replacing N out of M node(s) with delegate (X)` 줄을 runner PID 로 고르고 runtime_return 순서로 runtime_key · model SHA 와 연결 (TID 직접 연결 불가 · 순서 기반 표시) · 등록/로드 줄은 증거 아님 (CME 규칙) · NPU = 컴파일 모델 SHA · 품질 조건 표기 · 탐지 GPU 본요청 = warmup/probe 와 구분.

계산 · 판정 0 (유효 수 · 요청 수 세기만).
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps(dict(out=str(out), consumption_rows=len(cons), gate_rows=len(gl), n16=n16, app_starts=app_starts, completed=completed_n, req_rep=req_rep, req_all=req_completed_all, v2_rows=len(v2), delegate_rows=len(drows)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
