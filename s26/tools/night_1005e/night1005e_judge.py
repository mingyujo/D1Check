# -*- coding: utf-8 -*-
"""night1005e_judge.py — 밤 1005e 판정기 (N2: EffNet 세기 A/B, 칸 NAe·NBe·GAe·GBe) = night1005_judge.py 를 import 하는 얇은 판.
`밤1005e_사전등록_v1.md` (SHA 1287acd9…) §3 · §4-2 를 글자 그대로. 판정 함수 · 문턱 · 같은 일 0.95 · 선별 기준 · 6개 판정 순서 ·
결론 문장 틀 · cmp 허용오차는 import 한 `night1005_judge.py` (SHA 접두 ca8680c2 — 다르면 오류) 그대로다. 복사·수정 금지.
결과 보기 전 (2026-10-05 23:4x, N2 측정 전) 고정. results\\ 는 읽기만. 같은 입력 두 번 = 같은 바이트.

  py night1005e_judge.py selftest
  py night1005e_judge.py run <run_dir> --cell NAe|NBe|GAe|GBe --block 1|2 --gate-label <정확한 label> [--watch csv] [--gate-log csv]
                            [--phone-watch csv] --out f.json
  py night1005e_judge.py pair --a f.json --b f.json --out f.json
  py night1005e_judge.py resource --pairs f1.json f2.json [--room-c ℃] [--spare] --out f.json
  py night1005e_judge.py cmp --pred-v21 f --pred-v2 f --pred-v1 f --runs r… --pairs p… --out f.json
  py night1005e_judge.py watchcheck <run_dir> --phone-watch csv --out f.json

더하는 것 (§4-2 ①~⑦ — 이것만):
  ① 구간 모델 SHA: run_metadata `chain_segments[*].model_sha256` (없으면 그 구간의 segment_end detail `model_sha256`) —
     10/5 G50P2 체인 런 (MobileNet GPU) 에서 두 필드를 확인했다. NPU 칸 311e4aac… · GPU 칸 6c7ab0a6… 와 **다른 SHA 가 있으면 오류**.
     어느 구간에도 SHA 가 없으면 "모델 SHA 미기록" 표시 (오류 아님 — 세션이 폰 파일 sha256sum 으로 대신 확인). 일부만 있으면 "일부 미기록".
     (GPU model_path 체인에서 러너가 SHA 를 적는지는 2-0 스모크 G 에서 확인한다.)
  ② --phone-watch (세션이 "감시 켬" 일 때만 준다): §3 규칙. 칸 창 = 구간 0 시작 − 60 s ~ 마지막 구간 끝.
     **시각 출처 = 폰 시계**: 구간 start_wall_ms / end_wall_ms 는 러너 JSONL 의 wall_ms (폰 System.currentTimeMillis) 로 m1m2_judge_1002._wall_at
     이 근사한 값이고, 감시 CSV 의 phone_ms 는 폰 `date +%s%3N` 이다 → CSV 의 phone_ms 열로 맞춘다 (pc_ms 는 쓰지 않는다).
     표본 = ok == 1 이고 phone_ms 가 있는 줄. 이벤트: 칸 창 전체에서 ① call_state 에 0 이 아닌 값 · ② audio_mode ≠ MODE_NORMAL,
     구간 0 시작 ~ 마지막 구간 끝에서만 ③ focus ≠ 그 런의 구간 0 첫 표본 (구간 0 시작 이후 첫 표본) 값 · ④ wakefulness ≠ Awake.
     공백 = 칸 창 안 연속 표본 간격 (창 시작 → 첫 표본, 마지막 표본 → 창 끝 포함) 이 그 간격 끝 표본 period_s × 3 초과 →
     "감시 공백 ○ s" (이벤트 아님). 이벤트 > 0 → "감시 이벤트 — 무효" · pair · resource · cmp 가 그 런을 받지 않는다 (오류).
  ③ watchcheck: 어느 체인이든 (N4 · "감시 기록만") 칸 창 이벤트만 본다. kind = night1005e_watchcheck.
  ④ pair 에 "B t38 잘림 가능" (B 899 s SKIN ≥ 38.0).
  ⑤ 결론 조건 괄호 = 사전 등록 §4-2 문장 (--room-c 없으면 "실내 미기록"). import 모듈 전역 COND 를 resource 할 때 바꾼다.
  ⑥ pair 는 NAe·NBe 또는 GAe·GBe 끼리만 (MobileNet 칸과 섞이면 오류).
  ⑦ resource --spare → 결론 문장 끝에 "(예비 런 포함 — 블록 순서 안 지켜짐)".
  kind 문자열은 import 한 그대로 (night1005_run · night1005_pair · night1005_resource). 출력에 import 대상 SHA (imports_e).
"""
import argparse, contextlib, csv, hashlib, importlib.util, io, json, os, re, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
OD_SIM = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _first_existing(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(paths[0])


# --- import (복사·수정 금지) ---------------------------------------------------------------------
N5_PREFIX = "ca8680c2"
_N5_PATH = _first_existing(os.path.join(HERE, "night1005_judge.py"), os.path.join(OD_SIM, "night1005_judge.py"),
                           os.path.join(REPO, "s26", "tools", "night_1005", "night1005_judge.py"))
if not _sha(_N5_PATH).startswith(N5_PREFIX):
    raise SystemExit(f"IMPORT_ERROR: night1005_judge.py SHA {_sha(_N5_PATH)[:8]} ≠ {N5_PREFIX} ({_N5_PATH})")
N5 = _load_module("night1005_judge", _N5_PATH)
JudgeError, load_run, segments_of, load_watch, dumps = N5.JudgeError, N5.load_run, N5.segments_of, N5.load_watch, N5.dumps

NPU_SHA = "311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31"
GPU_SHA = "6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0"
NEW_CELLS = {
    "NAe": dict(resource="NPU", side="A", chain="npu_eff_work100_v1", labels=["work_d100", "tail_idle"], duties=[100, 1], durs=[300, 600]),
    "NBe": dict(resource="NPU", side="B", chain="npu_eff_work50_v1", labels=["work_d50", "tail_idle"], duties=[50, 1], durs=[660, 240]),
    "GAe": dict(resource="GPU", side="A", chain="gpu_eff_work100_v1", labels=["work_d100", "tail_idle"], duties=[100, 1], durs=[300, 600]),
    "GBe": dict(resource="GPU", side="B", chain="gpu_eff_work50_v1", labels=["work_d50", "tail_idle"], duties=[50, 1], durs=[720, 180]),
}
MODEL_SHA = {"NPU": NPU_SHA, "GPU": GPU_SHA}
N5.CELLS.update(NEW_CELLS)            # 더하기 (기존 NA·NB·GA·GB 유지 — _expect · run_judge · _mk_run · _fake_run 이 호출 때 전역을 읽는다)
COND_ORIG = N5.COND
SPARE_NOTE = "(예비 런 포함 — 블록 순서 안 지켜짐)"
WATCH_PRE_S = 60
GAP_FACTOR = 3.0
T38_CUT = 38.0
EPS = 1e-9


def _fmt_room(room_c):
    if room_c is None:
        return "실내 미기록"
    r = float(room_c)
    txt = str(int(r)) if r.is_integer() else f"{r:g}"
    return f"실내 {txt} ℃ (진술)"


def cond_e(room_c=None):
    return ("— 조건: 이 설치본 · EfficientNet-Lite0 FLOAT32 (계약 분류 모델 · NPU 는 AOT 변환본) · 시작 밴드 · 비행기 모드 켬 · 방해 금지 켬 · "
            f"{_fmt_room(room_c)} · 자원당 2쌍 · 도착·기한·긴급 요청 없는 레버 시험 (정책 시험 아님)")


def import_check_e():
    out = dict(night1005_judge=dict(path=_N5_PATH, sha256=_sha(_N5_PATH), expected_prefix=N5_PREFIX, ok=_sha(_N5_PATH).startswith(N5_PREFIX)))
    out.update(N5.import_check())
    return out


def _load_json(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


# ============================================================ ① 모델 SHA
def model_sha_check(S, resource):
    exp = MODEL_SHA[resource]
    meta = S["meta"]
    cs = meta.get("chain_segments") if isinstance(meta.get("chain_segments"), list) else []
    by_idx = {c.get("index"): c.get("model_sha256") for c in cs if isinstance(c, dict)}
    found = []
    for seg in S["segments"]:
        i = seg["index"]
        sha, src = by_idx.get(i), "run_metadata.chain_segments"
        if not sha:
            sha, src = seg.get("_end_model_sha256"), "segment_end detail"
        found.append(dict(index=i, sha256=sha or None, source=src if sha else None))
    present = [f for f in found if f["sha256"]]
    bad = [f for f in present if f["sha256"] != exp]
    if bad:
        raise JudgeError(f"구간 모델 SHA 다름: {[(f['index'], f['sha256'][:8]) for f in bad]} ≠ {exp[:8]} ({resource})")
    if not present:
        label = "모델 SHA 미기록"
    elif len(present) < len(found):
        label = "모델 SHA 일부 미기록 (있는 것은 일치)"
    else:
        label = "모델 SHA 일치"
    return dict(expected=exp, label=label, segments=found)


def _segments_with_end_sha(run):
    S = segments_of(run)
    ends = [e for e in run["events"] if e.get("event") == "segment_end"]
    for e in ends:
        d = N5.J._detail(e)
        i = d.get("index")
        for seg in S["segments"]:
            if seg["index"] == i:
                seg["_end_model_sha256"] = d.get("model_sha256")
    return S


# ============================================================ ② 감시
def load_phone_watch(path):
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            try:
                ok = (r.get("ok") or "").strip() == "1"
                pm = int(r["phone_ms"]) if (r.get("phone_ms") or "").strip() else None
                per = float(r.get("period_s") or 10)
            except (ValueError, KeyError, TypeError):
                continue
            if not ok or pm is None:
                continue
            rows.append(dict(phone_ms=pm, call=(r.get("call_state") or "").strip(), audio=(r.get("audio_mode") or "").strip(),
                             focus=(r.get("focus") or "").strip(), wake=(r.get("wakefulness") or "").strip(), period_s=per))
    rows.sort(key=lambda x: x["phone_ms"])
    return rows


def watch_stats(S, rows, csv_path=None):
    segs = S["segments"]
    s0, s_end = segs[0]["start_wall_ms"], segs[-1]["end_wall_ms"]
    if s0 is None or s_end is None:
        raise JudgeError("구간 wall_ms 없음 — 감시 창을 못 맞춘다")
    w0 = s0 - WATCH_PRE_S * 1000
    inwin = [r for r in rows if w0 <= r["phone_ms"] <= s_end]
    run_part = [r for r in inwin if r["phone_ms"] >= s0]
    ref_focus = run_part[0]["focus"] if run_part else None
    events = []
    for r in inwin:
        rel = round((r["phone_ms"] - s0) / 1000.0, 3)
        calls = [c for c in r["call"].split("|") if c != ""]
        if any(c != "0" for c in calls):
            events.append(dict(t_rel_s=rel, kind="① 통화 상태", value=r["call"]))
        if r["audio"] != "MODE_NORMAL":
            events.append(dict(t_rel_s=rel, kind="② 오디오 모드", value=r["audio"]))
        if r["phone_ms"] >= s0:
            if ref_focus is not None and r["focus"] != ref_focus:
                events.append(dict(t_rel_s=rel, kind="③ 맨 앞 창", value=r["focus"]))
            if r["wake"] != "Awake":
                events.append(dict(t_rel_s=rel, kind="④ 화면", value=r["wake"]))
    # 공백 (창 시작 → 첫 표본 · 표본 사이 · 마지막 표본 → 창 끝)
    pts = [w0] + [r["phone_ms"] for r in inwin] + [s_end]
    pers = [inwin[0]["period_s"] if inwin else 10.0] + [r["period_s"] for r in inwin] + [inwin[-1]["period_s"] if inwin else 10.0]
    max_gap, flags = 0.0, []
    for i in range(1, len(pts)):
        g = (pts[i] - pts[i - 1]) / 1000.0
        max_gap = max(max_gap, g)
        if g > GAP_FACTOR * pers[i] + EPS:
            flags.append(dict(from_rel_s=round((pts[i - 1] - s0) / 1000.0, 3), gap_s=round(g, 3), limit_s=GAP_FACTOR * pers[i]))
    n_ev = len(events)
    return dict(csv=csv_path, clock="phone (CSV phone_ms ↔ 러너 wall_ms)", window_rel_s=[-WATCH_PRE_S, round((s_end - s0) / 1000.0, 3)],
                n_samples=len(inwin), reference_focus=ref_focus, n_events=n_ev, events=events,
                max_gap_s=round(max_gap, 3), gaps=flags,
                gap_label=None if not flags else "감시 공백 " + " · ".join(f"{f['gap_s']:.0f} s" for f in flags),
                verdict="감시 이벤트 — 무효 (쌍·자원·cmp 에 넣지 않음)" if n_ev else "감시 이벤트 없음")


def _events_of(j):
    pw = j.get("phone_watch")
    return 0 if not pw else int(pw.get("n_events") or 0)


# ============================================================ 명령
def run_e(run, cell, block, watch=None, gate_log=None, gate_label=None, phone_watch=None):
    if cell not in NEW_CELLS:
        raise JudgeError(f"칸 {cell} ∉ {list(NEW_CELLS)} (이 판정기는 EffNet 칸만)")
    if not gate_label:
        raise JudgeError("--gate-label 필수 (부분 문자열 매칭 금지)")
    S = _segments_with_end_sha(run)
    msc = model_sha_check(S, NEW_CELLS[cell]["resource"])
    j = N5.run_judge(run, cell, block, watch, gate_log, gate_label)
    j["model_sha_check"] = msc
    j["phone_watch"] = None if phone_watch is None else watch_stats(S, load_phone_watch(phone_watch), phone_watch)
    j["imports_e"] = import_check_e()
    return j


def pair_e(a, b):
    for x, side in ((a, "A"), (b, "B")):
        if x.get("cell") not in NEW_CELLS:
            raise JudgeError(f"{side} 칸 {x.get('cell')} 는 EffNet 칸이 아님 (MobileNet 칸과 섞지 않는다)")
        if _events_of(x):
            raise JudgeError(f"{side} ({x.get('cell')} b{x.get('block')}) 에 감시 이벤트 {_events_of(x)}건 — 무효 런")
    if {a["cell"], b["cell"]} not in ({"NAe", "NBe"}, {"GAe", "GBe"}):
        raise JudgeError(f"쌍은 NAe·NBe 또는 GAe·GBe 만: {a['cell']} + {b['cell']}")
    p = N5.pair_judge(a, b)
    s899 = ((b.get("temps") or {}).get("at_899") or {}).get("SKIN")
    cut = s899 is not None and s899 >= T38_CUT - EPS
    p["b_t38_cut"] = dict(b_skin_899=s899, flag=cut, label="B t38 잘림 가능" if cut else None, rule="B 899 s SKIN ≥ 38.0")
    p["cells"] = dict(a=a["cell"], b=b["cell"])
    p["phone_watch_events"] = dict(a=_events_of(a), b=_events_of(b))
    p["imports_e"] = import_check_e()
    return p


def resource_e(pairs, room_c=None, spare=False):
    for p in pairs:
        cells = p.get("cells") or {}
        if cells.get("a") not in NEW_CELLS or cells.get("b") not in NEW_CELLS:
            raise JudgeError("EffNet 쌍 JSON 이 아님 (night1005e pair 출력만)")
        if any((p.get("phone_watch_events") or {}).values()):
            raise JudgeError(f"쌍 b{p.get('block')} 에 감시 이벤트 런")
    N5.COND = cond_e(room_c) + ((" " + SPARE_NOTE) if spare else "")
    try:
        r = N5.resource_judge(pairs)
    finally:
        N5.COND = COND_ORIG
    r["room_c"] = room_c
    r["spare"] = bool(spare)
    r["condition"] = cond_e(room_c) + ((" " + SPARE_NOTE) if spare else "")
    r["b_t38_cut"] = [dict(block=p["block"], label=(p.get("b_t38_cut") or {}).get("label")) for p in sorted(pairs, key=lambda q: q["block"])]
    r["imports_e"] = import_check_e()
    return r


def cmp_e(preds, runs, pairs):
    for j in runs:
        if j.get("cell") not in NEW_CELLS:
            raise JudgeError(f"cmp 런 {j.get('cell')} 는 EffNet 칸이 아님")
        if _events_of(j):
            raise JudgeError(f"cmp 런 {j['cell']} b{j['block']} 에 감시 이벤트")
    for p in pairs:
        if any((p.get("phone_watch_events") or {}).values()):
            raise JudgeError(f"cmp 쌍 b{p.get('block')} 에 감시 이벤트 런")
    out = N5.cmp_all(preds, runs, pairs)
    out["imports_e"] = import_check_e()
    return out


def watchcheck(run, phone_watch):
    S = segments_of(run)
    m = S["meta"]
    return dict(kind="night1005e_watchcheck", run_id=m.get("run_id"), chain_id=(m.get("chain_spec") or {}).get("chain_id"),
                phone_watch=watch_stats(S, load_phone_watch(phone_watch), phone_watch), imports_e=import_check_e())


# ============================================================ selftest (합성 — 결과 보기 전 양방향)
def _patch_meta(rd, chain_segments):
    jp = [os.path.join(rd, "gpu", f) for f in os.listdir(os.path.join(rd, "gpu"))][0]
    with open(jp, encoding="utf-8") as fh:
        lines = fh.readlines()
    for i, ln in enumerate(lines):
        e = json.loads(ln)
        if e.get("event") == "run_metadata":
            e["chain_segments"] = chain_segments
            lines[i] = json.dumps(e, separators=(",", ":")) + "\n"
            break
    with open(jp, "w", encoding="utf-8") as fh:
        fh.writelines(lines)


def _write_watch(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("pc_ms,phone_ms,call_state,audio_mode,focus,wakefulness,cmd_ms,ok,basic_normal,period_s,err\n")
        for r in rows:
            fh.write(",".join(f'"{x}"' for x in (r["t"], r["t"], r.get("call", "0|0"), r.get("audio", "MODE_NORMAL"), r.get("focus", "runner/Act"),
                                                  r.get("wake", "Awake"), 300, 1, 1, r.get("per", 10), "")) + "\n")


def selftest():
    res = []

    def check(name, cond, got):
        res.append((name, bool(cond), got))
    # ① import 한 판정기의 selftest 그대로 (COND 를 바꾸기 전)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc5 = N5.selftest()
    m = re.search(r"\((\d+)/(\d+)\)", buf.getvalue())
    check("① night1005_judge.py selftest 그대로 49/49 (새 칸을 더한 뒤)", rc5 == 0 and m and m.group(1) == m.group(2) == "49", m.group(0) if m else buf.getvalue()[-200:])
    check("① import 대상 SHA 접두 (night1005 ca8680c2 · m1m2 ea282d4a · night1003 a5ceab41)", all(v["ok"] for v in import_check_e().values()),
          {k: v["sha256"][:8] for k, v in import_check_e().items()})
    tmp = tempfile.mkdtemp(prefix="night1005e_selftest_")
    try:
        flat = lambda t: 29.5
        st = N5._steps
        # ② 새 칸 — 문턱 · 처리율 · 누적 · GBe 720 s · 칸 착오
        for cell, base, lo, hi in (("NAe", 0.9, 1.059, 1.060), ("GAe", 3.3, 1.099, 1.100)):
            for r, expect in ((lo, None), (hi, 100)):
                rd = N5._mk_run(tmp, f"thr_{cell}_{r}", cell, st(base, [(100, r)]), flat)
                j = run_e(load_run(rd), cell, 1, gate_label="x")
                check(f"② run {cell}: 100 s 부터 ×{r} → 첫 조임 {expect} (문턱 {N5.THR[NEW_CELLS[cell]['resource']]})",
                      j["work"]["first_throttle_s"] == expect, (j["work"]["first_throttle_s"], j["work"]["throttle_time_s"]))
        rd = N5._mk_run(tmp, "rateN", "NBe", lambda t: 0.9, flat, rate=20.0)
        j = run_e(load_run(rd), "NBe", 1, gate_label="x")
        check("② run NBe: d50 20/s → n ≈ 6,600 · 처리율 ≈ 10/s · 누적 66칸 · 마지막 = n", abs(j["work"]["n"] - 6600) <= 2 and abs(j["work"]["rate_per_s"] - 10) < 0.01
              and len(j["work"]["cumulative"]) == 66 and j["work"]["cumulative"][-1]["cum"] == j["work"]["n"], (j["work"]["n"], j["work"]["rate_per_s"]))
        rd = N5._mk_run(tmp, "rateG", "GBe", lambda t: 3.3, flat, rate=20.0)
        j = run_e(load_run(rd), "GBe", 2, gate_label="x")
        check("② run GBe: work 720 s · tail 180 s · n ≈ 7,200 · 누적 72칸", abs(j["work"]["length_s"] - 720) < 0.01 and abs(j["tail"]["length_s"] - 180) < 0.01
              and abs(j["work"]["n"] - 7200) <= 2 and len(j["work"]["cumulative"]) == 72, (j["work"]["length_s"], j["tail"]["length_s"], j["work"]["n"]))
        rd = N5._mk_run(tmp, "mobilenet_as_nae", "NA", lambda t: 0.75, flat)
        try:
            run_e(load_run(rd), "NAe", 1, gate_label="x")
            check("② MobileNet 체인 (npu_work100_v1) 을 NAe 로 → 오류", False, "판정이 나왔다")
        except JudgeError as err:
            check("② MobileNet 체인 (npu_work100_v1) 을 NAe 로 → 오류", True, str(err))
        try:
            run_e(load_run(rd), "NA", 1, gate_label="x")
            check("② MobileNet 칸 NA → 오류 (이 판정기는 EffNet 칸만)", False, "판정이 나왔다")
        except JudgeError as err:
            check("② MobileNet 칸 NA → 오류 (이 판정기는 EffNet 칸만)", True, str(err))
        # ③ 모델 SHA
        rd = N5._mk_run(tmp, "sha_ok", "GAe", lambda t: 3.3, flat)
        _patch_meta(rd, [dict(index=0, model_sha256=GPU_SHA), dict(index=1, model_sha256=GPU_SHA)])
        j = run_e(load_run(rd), "GAe", 1, gate_label="x")
        check("③ 모델 SHA 일치 → '모델 SHA 일치'", j["model_sha_check"]["label"] == "모델 SHA 일치", j["model_sha_check"]["label"])
        rd = N5._mk_run(tmp, "sha_bad", "NAe", lambda t: 0.9, flat)
        _patch_meta(rd, [dict(index=0, model_sha256=NPU_SHA), dict(index=1, model_sha256="1415b2c87d01b67a" + "0" * 48)])
        try:
            run_e(load_run(rd), "NAe", 1, gate_label="x")
            check("③ 구간 1 모델 SHA 다름 → 오류", False, "판정이 나왔다")
        except JudgeError as err:
            check("③ 구간 1 모델 SHA 다름 → 오류", True, str(err))
        rd = N5._mk_run(tmp, "sha_none", "NAe", lambda t: 0.9, flat)
        j = run_e(load_run(rd), "NAe", 1, gate_label="x")
        check("③ SHA 필드 없음 → '모델 SHA 미기록' (오류 아님)", j["model_sha_check"]["label"] == "모델 SHA 미기록", j["model_sha_check"]["label"])
        # ④ 감시
        rd = N5._mk_run(tmp, "watchA", "NAe", lambda t: 0.9, flat)
        runA = load_run(rd)
        S = segments_of(runA)
        s0, s1 = S["segments"][0]["start_wall_ms"], S["segments"][-1]["end_wall_ms"]

        def grid(per=10, start=-55, gap_at=None, gap_len=None, **over):
            rows, t = [], s0 + start * 1000
            while t <= s1 + 5000:
                rows.append(dict(t=int(t), per=per))
                t += per * 1000
            if gap_at is not None:
                g0 = s0 + gap_at * 1000
                rows = [r for r in rows if not (g0 < r["t"] < g0 + gap_len * 1000)]
                rows.append(dict(t=int(g0), per=per)); rows.append(dict(t=int(g0 + gap_len * 1000), per=per))
                rows.sort(key=lambda r: r["t"])
            return rows

        def wcase(name, rows, tag):
            p = os.path.join(tmp, f"w_{tag}.csv")
            _write_watch(p, rows)
            return watch_stats(S, load_phone_watch(p), p), p

        base = grid()
        w, p_clean = wcase("clean", base, "clean")
        check("④ 정상 표본만 → 이벤트 0 · 공백 없음", w["n_events"] == 0 and w["gap_label"] is None and w["reference_focus"] == "runner/Act", (w["n_events"], w["max_gap_s"]))
        rows = [dict(r) for r in base]
        for r in rows:
            if 400_000 <= r["t"] - s0 < 410_000:
                r["focus"] = "com.kakao.talk/Main"
        w, p_focus = wcase("focus_in", rows, "focus_in")
        check("④ 구간 안 맨 앞 창 바뀜 → 이벤트 ③", w["n_events"] >= 1 and w["events"][0]["kind"] == "③ 맨 앞 창", w["events"][:1])
        jA = run_e(runA, "NAe", 1, gate_label="x", phone_watch=p_focus)
        rdB = N5._mk_run(tmp, "watchB", "NBe", lambda t: 0.9, flat, rate=40.0)
        jB = run_e(load_run(rdB), "NBe", 1, gate_label="x")
        try:
            pair_e(jA, jB)
            check("④ 감시 이벤트 런 → pair 거부", False, "판정이 나왔다")
        except JudgeError as err:
            check("④ 감시 이벤트 런 → pair 거부", True, str(err))
        rows = [dict(r) for r in base]
        for r in rows:
            if -50_000 <= r["t"] - s0 < -10_000:
                r["focus"] = "launcher/Home"
        w, _ = wcase("focus_pre", rows, "focus_pre")
        check("④ 구간 0 앞 60 s 의 맨 앞 창 바뀜 → 무시", w["n_events"] == 0, w["events"][:1])
        rows = [dict(r) for r in base]
        for r in rows:
            if -30_000 <= r["t"] - s0 < -20_000:
                r["audio"] = "MODE_IN_COMMUNICATION"
        w, _ = wcase("audio_pre", rows, "audio_pre")
        check("④ 구간 0 앞 60 s 의 오디오 ≠ normal → 이벤트 ②", w["n_events"] == 1 and w["events"][0]["kind"] == "② 오디오 모드", w["events"])
        rows = [dict(r) for r in base] + [dict(t=int(s0 - 61_000), audio="MODE_IN_CALL", call="1|0")]
        rows.sort(key=lambda r: r["t"])
        w, _ = wcase("outside", rows, "outside")
        check("④ 창 밖 (구간 0 − 61 s) 통화·오디오 → 무시", w["n_events"] == 0, w["events"][:1])
        w, _ = wcase("gap31", grid(gap_at=200, gap_len=31), "gap31")
        check("④ 10 s 박자 · 공백 31 s → '감시 공백'", w["gap_label"] is not None and any(abs(g["gap_s"] - 31) < 0.01 for g in w["gaps"]), (w["gap_label"], w["max_gap_s"]))
        w, _ = wcase("gap30", grid(gap_at=200, gap_len=30), "gap30")
        check("④ 10 s 박자 · 공백 30 s → 없음", w["gap_label"] is None, (w["gap_label"], w["max_gap_s"]))
        w, _ = wcase("gap31_30", grid(per=30, start=-55, gap_at=200, gap_len=31), "gap31_30")
        check("④ 30 s 박자 · 공백 31 s → 없음", w["gap_label"] is None, (w["gap_label"], w["max_gap_s"]))
        rows = [dict(r) for r in base]
        for r in rows:
            if 600_000 <= r["t"] - s0 < 610_000:
                r["wake"] = "Asleep"
        w, _ = wcase("wake", rows, "wake")
        check("④ 구간 안 화면 ≠ Awake → 이벤트 ④", w["n_events"] == 1 and w["events"][0]["kind"] == "④ 화면", w["events"])
        wc = watchcheck(runA, p_focus)
        check("④ watchcheck = run 과 같은 이벤트 수", wc["phone_watch"]["n_events"] == jA["phone_watch"]["n_events"] and wc["kind"] == "night1005e_watchcheck",
              wc["phone_watch"]["n_events"])
        # ⑤ B t38 잘림 경계
        A = N5._fake_run("NAe", 1, 10000, 40.0, 200, 100, 0, 200)
        for s899, exp in ((37.9, False), (38.0, True)):
            Bf = N5._fake_run("NBe", 1, 10000, 40.0, 200, 100, 0, 200)
            Bf["temps"]["at_899"] = dict(SKIN=s899)
            p = pair_e(A, Bf)
            check(f"⑤ B 899 s SKIN {s899} → 'B t38 잘림 가능' {exp}", p["b_t38_cut"]["flag"] is exp and (p["b_t38_cut"]["label"] == "B t38 잘림 가능") is exp,
                  p["b_t38_cut"])
        # ⑥ MobileNet + EffNet 섞임
        try:
            pair_e(N5._fake_run("NA", 1, 10000, 40.0, 200, 100, 0, 200), N5._fake_run("NBe", 1, 10000, 40.0, 200, 100, 0, 200))
            check("⑥ pair NA (MobileNet) + NBe → 오류", False, "판정이 나왔다")
        except JudgeError as err:
            check("⑥ pair NA (MobileNet) + NBe → 오류", True, str(err))
        try:
            pair_e(N5._fake_run("NAe", 1, 10000, 40.0, 200, 100, 0, 200), N5._fake_run("GBe", 1, 10000, 40.0, 200, 100, 0, 200))
            check("⑥ pair NAe + GBe → 오류", False, "판정이 나왔다")
        except JudgeError as err:
            check("⑥ pair NAe + GBe → 오류", True, str(err))
        # ⑦ 조건 괄호 · 예비
        def PP(block, d):
            a = N5._fake_run("NAe", block, 10000, 40.0, 200, 100, 0, 200)
            b = N5._fake_run("NBe", block, 10000, round(40.0 - d, 1), 200, 100, 0, 200)
            return pair_e(a, b)
        prs = [PP(1, 1.0), PP(2, 1.2)]
        r = resource_e(prs, room_c=23)
        check("⑦ resource --room-c 23 → 'B 낮음' · 문장 끝 '실내 23 ℃ (진술)' 조건", r["verdict"] == "B 낮음 (2쌍)" and r["sentence"].endswith(cond_e(23))
              and "실내 23 ℃ (진술)" in r["sentence"] and "EfficientNet-Lite0 FLOAT32" in r["sentence"], r["sentence"][-140:])
        r = resource_e(prs)
        check("⑦ resource (room 없음) → '실내 미기록'", "실내 미기록" in r["sentence"] and r["sentence"].endswith(cond_e(None)), r["sentence"][-80:])
        r = resource_e(prs, room_c=23, spare=True)
        check("⑦ resource --spare → 문장 끝 '(예비 런 포함 — 블록 순서 안 지켜짐)'", r["sentence"].endswith(SPARE_NOTE), r["sentence"][-60:])
        check("⑦ resource 뒤 import 모듈 COND 원복", N5.COND == COND_ORIG, N5.COND[:30])
        # ⑧ --gate-label 정확 매칭
        gl = os.path.join(tmp, "gate.csv")
        with open(gl, "w", encoding="utf-8") as fh:
            fh.write("label,local_time,waited_s,SKIN,AP,BAT,thermal_status,soc,plugged,upper_pass,lower_skin_ge_29.1,lower_bat_ge_27.5,lower_pass,lower_policy,action\n")
            fh.write("03_NAe_b1,2026-10-06T01:00:00,0,29.5,28.0,28.0,0,90,0,True,True,True,True,required,run\n")
            fh.write("04_NAe_b1_re,2026-10-06T01:40:00,0,28.5,28.0,27.0,0,85,0,True,False,False,False,mark,run_marked_lower_fail\n")
        rd = N5._mk_run(tmp, "gate", "NAe", lambda t: 0.9, flat)
        j1 = run_e(load_run(rd), "NAe", 1, gate_log=gl, gate_label="03_NAe_b1")
        j2 = run_e(load_run(rd), "NAe", 1, gate_log=gl, gate_label="04_NAe_b1_re")
        check("⑧ --gate-label 정확 매칭: NAe_b1 → 자기 줄 (하한 통과) · NAe_b1_re → 자기 줄 (하한 미달)",
              j1["start"]["gate_row"]["label"] == "03_NAe_b1" and j1["start"]["lower"]["label"] == "하한 통과"
              and j2["start"]["gate_row"]["label"] == "04_NAe_b1_re" and j2["start"]["lower"]["label"] == "하한 미달",
              (j1["start"]["gate_row"]["label"], j2["start"]["gate_row"]["label"]))
        try:
            run_e(load_run(rd), "NAe", 1, gate_log=gl, gate_label=None)
            check("⑧ --gate-label 없음 → 오류", False, "판정이 나왔다")
        except JudgeError as err:
            check("⑧ --gate-label 없음 → 오류", True, str(err))
        # ⑨ 결정성
        rd1 = N5._mk_run(tmp, "detA", "GBe", st(3.3, [(200, 1.2)]), N5._ramp(29.5, 39.0, 720.0, 900.0, 33.0))
        rd2 = N5._mk_run(tmp, "detB", "GBe", st(3.3, [(200, 1.2)]), N5._ramp(29.5, 39.0, 720.0, 900.0, 33.0))
        a1 = dumps(run_e(load_run(rd1), "GBe", 1, gate_label="x", phone_watch=p_clean)).replace(rd1.replace("\\", "\\\\"), "X").replace(rd1, "X")
        a2 = dumps(run_e(load_run(rd2), "GBe", 1, gate_label="x", phone_watch=p_clean)).replace(rd2.replace("\\", "\\\\"), "X").replace(rd2, "X")
        check("⑨ 결정성: run 같은 입력 두 번 = 같은 바이트 (경로 제외)", a1 == a2, f"{len(a1)} B")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(c for _, c, _ in res)
    print("| 시험 | 결과 | 값 |\n|---|---|---|")
    for name, c, got in res:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:170]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in res if c)}/{len(res)})")
    return 0 if ok else 1


# ============================================================ CLI
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    a = sub.add_parser("run")
    a.add_argument("run_dir")
    a.add_argument("--cell", required=True, choices=sorted(NEW_CELLS))
    a.add_argument("--block", required=True, type=int, choices=(1, 2))
    a.add_argument("--gate-label", required=True)
    a.add_argument("--watch")
    a.add_argument("--gate-log")
    a.add_argument("--phone-watch")
    a.add_argument("--out")
    a = sub.add_parser("pair")
    a.add_argument("--a", required=True)
    a.add_argument("--b", required=True)
    a.add_argument("--out")
    a = sub.add_parser("resource")
    a.add_argument("--pairs", nargs="+", required=True)
    a.add_argument("--room-c", type=float)
    a.add_argument("--spare", action="store_true")
    a.add_argument("--out")
    a = sub.add_parser("cmp")
    a.add_argument("--pred-v21")
    a.add_argument("--pred-v2")
    a.add_argument("--pred-v1")
    a.add_argument("--runs", nargs="*", default=[])
    a.add_argument("--pairs", nargs="*", default=[])
    a.add_argument("--out")
    a = sub.add_parser("watchcheck")
    a.add_argument("run_dir")
    a.add_argument("--phone-watch", required=True)
    a.add_argument("--out")
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd == "run":
            res = run_e(load_run(args.run_dir), args.cell, args.block, load_watch(args.watch), args.gate_log, args.gate_label, args.phone_watch)
        elif args.cmd == "pair":
            res = pair_e(_load_json(args.a), _load_json(args.b))
        elif args.cmd == "resource":
            res = resource_e([_load_json(f) for f in args.pairs], args.room_c, args.spare)
        elif args.cmd == "watchcheck":
            res = watchcheck(load_run(args.run_dir), args.phone_watch)
        else:
            preds = {}
            for tag in ("v21", "v2", "v1"):
                v = getattr(args, f"pred_{tag}")
                if v and not os.path.exists(v):
                    print(f"NOTE: pred-{tag} 파일 없음 → '예측 없음' ({v})", file=sys.stderr)
                preds[tag] = (v, _load_json(v) if (v and os.path.exists(v)) else None)
            res = cmp_e(preds, [_load_json(f) for f in args.runs], [_load_json(f) for f in args.pairs])
    except JudgeError as err:
        print(f"JUDGE_ERROR: {err}", file=sys.stderr)
        return 2
    text = dumps(res)
    if getattr(args, "out", None):
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
