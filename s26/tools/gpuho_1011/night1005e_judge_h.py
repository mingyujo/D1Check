# -*- coding: utf-8 -*-
"""night1005e_judge_h.py — GPU 홀드아웃 (GH 1011) 열 지표 래퍼 = `night1005e_judge.py` (SHA 접두 2db1cda5, 복사·수정 금지) + 칸 GAh · GBh.

왜: `night1005e_judge.py` 의 GBe 는 체인 `gpu_eff_work50_v1` · 구간 720 / 180 s 에 묶여 있어 (`_expect` 가 체인 · 길이가 다르면 오류)
GH 의 B 체인 `gpu_eff_work50eq_v1` (T / 900 − T s, 등록 §2-2) 런을 거부한다. 이 래퍼는 그 판정기와 그것이 import 하는
`night1005_judge.py` (ca8680c2) 의 칸 표에 GAh · GBh 를 **더한다** (기존 칸 유지 — night1005e_judge_c.py (에너지 C) 와 같은 방식).
GBh 의 구간 길이는 레포 체인 파일 `tools/chains/gpu_eff_work50eq_v1.json` 에서 읽는다 (canonical SHA 를 `d1sim/gpu_holdout_v1/common.py` 값과 대조).
열 지표는 **기술** — 블록 판정 (m5 · k) 은 `d1sim/gpu_holdout_v1/judge_gpuho.py` 가 한다. 결과 보기 전 (2026-10-11 GH 3단계, 폰 칸 0) 고정.
results\\ 는 읽기만. 같은 입력 두 번 = 같은 바이트.

  py night1005e_judge_h.py selftest
  py night1005e_judge_h.py run <run_dir> --cell GAh|GBh --block 1..8 --gate-label <정확한 label> [--watch csv] [--gate-log csv]
                              [--phone-watch csv] --out f.json
  py night1005e_judge_h.py pair --a f.json --b f.json --out f.json        (열 쌍 차이 — 기술)
  py night1005e_judge_h.py watchcheck <run_dir> --phone-watch csv --out f.json

칸: GAh = GAe 와 같은 사양 (GPU · A · gpu_eff_work100_v1 · work_d100 300 s + tail_idle 600 s · FP32)
    GBh = GPU · B · gpu_eff_work50eq_v1 · work_d50 T s (d50) + tail_idle 900 − T s (d1)
GH 가 정함 (결과 전): ① 블록 1~8 — import 한 run_judge 는 블록 ∈ (1, 2) 만 받으므로 내부 호출은 블록 1 · 출력 block 을 실제 k 로
  (block_internal = 1 을 같이 적는다 — 에너지 C 래퍼와 같음). ② pair 는 GAh · GBh 끼리만 (같은 블록 · 감시 이벤트 런 거부 · B t38 잘림 표시).
  resource · cmp 는 두지 않는다. ③ kind 문자열은 import 한 그대로 (night1005_run · night1005_pair) + judge_h (이 파일 · import SHA · 칸 표).
"""
import argparse, contextlib, hashlib, importlib.util, io, json, os, re, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
OD_SIM = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _first_existing(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(paths[0])


# --- import (복사·수정 금지) ---------------------------------------------------------------------
N5E_PREFIX = "2db1cda5"
_N5E_PATH = _first_existing(os.path.join(HERE, "night1005e_judge.py"), os.path.join(OD_SIM, "night1005e_judge.py"),
                            os.path.join(REPO, "s26", "tools", "night_1005e", "night1005e_judge.py"))
if not _sha(_N5E_PATH).startswith(N5E_PREFIX):
    raise SystemExit(f"IMPORT_ERROR: night1005e_judge.py SHA {_sha(_N5E_PATH)[:8]} ≠ {N5E_PREFIX} ({_N5E_PATH})")
_spec = importlib.util.spec_from_file_location("night1005e_judge", _N5E_PATH)
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)          # 이것이 night1005_judge (ca8680c2) 를 SHA 확인 뒤 import 한다
N5 = E.N5
JudgeError, load_run, segments_of, load_watch, dumps = E.JudgeError, E.load_run, E.segments_of, E.load_watch, E.dumps

# --- GBh 구간 길이 = 레포 체인 파일 (canonical SHA 대조) ----------------------------------------
CHAIN_B = os.path.join(REPO, "tools", "chains", "gpu_eff_work50eq_v1.json")
sys.path.insert(0, os.path.join(REPO, "tools"))
import npu_chain  # noqa: E402
_cb = npu_chain.load_chain(CHAIN_B)
GBH_CANONICAL = _cb["sha256"]
_segs = _cb["spec"]["segments"]
assert [s["label"] for s in _segs] == ["work_d50", "tail_idle"] and [s["duty"] for s in _segs] == [50, 1] and all(s["accelerator"] == "GPU" for s in _segs), _segs
T_B = int(_segs[0]["duration_s"])
assert T_B + int(_segs[1]["duration_s"]) == 900 and 10 <= T_B <= 840, (T_B, _segs)
try:
    sys.path.insert(0, REPO)
    from d1sim.gpu_holdout_v1 import common as _GC
    if _GC.CELLS["GBh"]["canonical"] != GBH_CANONICAL:
        raise SystemExit(f"IMPORT_ERROR: gpu_eff_work50eq_v1 canonical {GBH_CANONICAL[:8]} ≠ common.py {_GC.CELLS['GBh']['canonical'][:8]}")
    COMMON_CHECK = "common.py canonical 일치"
except ImportError:
    COMMON_CHECK = "common.py 없음 (대조 못 함)"

H_CELLS = {
    "GAh": dict(E.NEW_CELLS["GAe"]),
    "GBh": dict(resource="GPU", side="B", chain="gpu_eff_work50eq_v1", labels=["work_d50", "tail_idle"], duties=[50, 1], durs=[T_B, 900 - T_B]),
}
E.NEW_CELLS.update(H_CELLS)          # 더하기 (기존 NAe · NBe · GAe · GBe 유지 — run_e 가 이 전역을 본다)
N5.CELLS.update(H_CELLS)             # 더하기 (기존 NA · NB · GA · GB · …e 유지 — _expect · run_judge · _mk_run 이 이 전역을 본다)
BLOCKS = tuple(range(1, 9))
BLOCK_INTERNAL = 1


def judge_h_info():
    return dict(file=os.path.abspath(__file__), night1005e_judge=dict(path=_N5E_PATH, sha256=_sha(_N5E_PATH), expected_prefix=N5E_PREFIX),
                chain_b=dict(path=CHAIN_B, canonical_sha256=GBH_CANONICAL, T_s=T_B, common_check=COMMON_CHECK),
                cells={k: dict(chain=v["chain"], durs=v["durs"], duties=v["duties"]) for k, v in H_CELLS.items()})


def _load_json(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def run_h(run, cell, block, watch=None, gate_log=None, gate_label=None, phone_watch=None):
    if cell not in H_CELLS:
        raise JudgeError(f"칸 {cell} ∉ {list(H_CELLS)} (이 래퍼는 GH 칸만)")
    if block not in BLOCKS:
        raise JudgeError(f"블록 {block} ∉ 1..8")
    if not gate_label:
        raise JudgeError("--gate-label 필수 (부분 문자열 매칭 금지)")
    j = E.run_e(run, cell, BLOCK_INTERNAL, watch, gate_log, gate_label, phone_watch)
    j["block"] = block
    j["block_internal"] = BLOCK_INTERNAL
    j["judge_h"] = judge_h_info()
    return j


def pair_h(a, b):
    for x, side in ((a, "A"), (b, "B")):
        if x.get("cell") not in H_CELLS:
            raise JudgeError(f"{side} 칸 {x.get('cell')} 는 GH 칸이 아님 (GAh · GBh 만)")
        if E._events_of(x):
            raise JudgeError(f"{side} ({x.get('cell')} b{x.get('block')}) 에 감시 이벤트 {E._events_of(x)}건 — 무효 런")
    if (a["cell"], b["cell"]) != ("GAh", "GBh"):
        raise JudgeError(f"쌍은 A = GAh · B = GBh 만: {a['cell']} + {b['cell']}")
    p = N5.pair_judge(a, b)            # 같은 블록 · 같은 자원 · A/B 자리 검사 포함
    s899 = ((b.get("temps") or {}).get("at_899") or {}).get("SKIN")
    cut = s899 is not None and s899 >= E.T38_CUT - E.EPS
    p["b_t38_cut"] = dict(b_skin_899=s899, flag=cut, label="B t38 잘림 가능" if cut else None, rule="B 899 s SKIN ≥ 38.0")
    p["cells"] = dict(a=a["cell"], b=b["cell"])
    p["phone_watch_events"] = dict(a=E._events_of(a), b=E._events_of(b))
    p["note"] = "열 쌍 지표 기술 — 블록 판정 (m5 · k) 은 d1sim/gpu_holdout_v1/judge_gpuho.py"
    p["imports_e"] = E.import_check_e()
    p["judge_h"] = judge_h_info()
    return p


def watchcheck(run, phone_watch):
    out = E.watchcheck(run, phone_watch)
    out["judge_h"] = judge_h_info()
    return out


# ============================================================ selftest (합성 — 결과 보기 전 양방향)
def selftest():
    res = []

    def check(name, cond, got):
        res.append((name, bool(cond), got))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = E.selftest()
    m = re.search(r"selftest 전체: (PASS|FAIL) \((\d+)/(\d+)\)", buf.getvalue())
    check("① night1005e_judge.py selftest 그대로 전부 PASS (GAh · GBh 를 더한 뒤)", rc == 0 and m and m.group(1) == "PASS" and m.group(2) == m.group(3),
          m.group(0) if m else buf.getvalue()[-200:])
    check("① import 대상 SHA 접두 (night1005e 2db1cda5 · night1005 ca8680c2 · m1m2 ea282d4a · night1003 a5ceab41)",
          _sha(_N5E_PATH).startswith(N5E_PREFIX) and all(v["ok"] for v in E.import_check_e().values()),
          {k: v["sha256"][:8] for k, v in E.import_check_e().items()})
    check("① 기존 칸 유지 (NA NB GA GB NAe NBe GAe GBe) + GAh GBh · GBe 720/180 그대로 · GBh = (T, 900 − T) · T 는 10 의 배수",
          all(k in N5.CELLS for k in ("NA", "NB", "GA", "GB", "NAe", "NBe", "GAe", "GBe", "GAh", "GBh")) and E.NEW_CELLS["GBe"]["durs"] == [720, 180]
          and H_CELLS["GBh"]["durs"] == [T_B, 900 - T_B] and T_B % 10 == 0 and COMMON_CHECK.startswith("common.py canonical"), (T_B, COMMON_CHECK))
    tmp = tempfile.mkdtemp(prefix="night1005e_h_selftest_")
    try:
        flat = lambda t: 29.5
        rdB = N5._mk_run(tmp, "gbh", "GBh", lambda t: 3.3, flat, rate=20.0)
        runB = load_run(rdB)
        try:
            E.run_e(runB, "GBe", 1, gate_label="x")
            check(f"② {T_B}/{900 - T_B} 런 (gpu_eff_work50eq_v1) 을 GBe 로 → 오류", False, "판정이 나왔다")
        except JudgeError as err:
            check(f"② {T_B}/{900 - T_B} 런 (gpu_eff_work50eq_v1) 을 GBe 로 → 오류", True, str(err))
        jB = run_h(runB, "GBh", 5, gate_label="x")
        check(f"② 같은 런을 GBh (블록 5) 로 → 통과 · work {T_B} s · tail {900 - T_B} s · n ≈ {T_B * 10} · 누적 {T_B // 10}칸 · block 5 · GPU 문턱 1.10",
              abs(jB["work"]["length_s"] - T_B) < 0.01 and abs(jB["tail"]["length_s"] - (900 - T_B)) < 0.01 and abs(jB["work"]["n"] - T_B * 10) <= 2
              and len(jB["work"]["cumulative"]) == T_B // 10 and jB["block"] == 5 and jB["block_internal"] == 1 and jB["threshold_ratio"] == 1.10 and jB["resource"] == "GPU",
              (jB["work"]["length_s"], jB["tail"]["length_s"], jB["work"]["n"], jB["block"], jB["threshold_ratio"]))
        rdA = N5._mk_run(tmp, "gah", "GAh", lambda t: 3.3, flat, rate=20.0)
        runA = load_run(rdA)
        jA = run_h(runA, "GAh", 5, gate_label="x")
        check("② 300/600 GPU 런 (gpu_eff_work100_v1) 을 GAh 로 → 통과 · work 300 s · tail 600 s",
              abs(jA["work"]["length_s"] - 300) < 0.01 and abs(jA["tail"]["length_s"] - 600) < 0.01 and jA["cell"] == "GAh", (jA["work"]["length_s"], jA["tail"]["length_s"]))
        jAe = E.run_e(runA, "GAe", 1, gate_label="x")
        check("② 같은 300/600 런을 GAe 로 → 기존 판정기도 그대로 통과 (칸 사양 같음)", jAe["work"]["n"] == jA["work"]["n"], (jAe["work"]["n"], jA["work"]["n"]))
        for bad_cell, run_ in (("GBh", runA), ("GAh", runB)):
            try:
                run_h(run_, bad_cell, 1, gate_label="x")
                check(f"② 다른 체인 런을 {bad_cell} 로 → 오류", False, "판정이 나왔다")
            except JudgeError as err:
                check(f"② 다른 체인 런을 {bad_cell} 로 → 오류", True, str(err))
        # GPU 문턱 경계 (×1.10) 가 GBh 에서도 그대로
        st = N5._steps
        for r, expect in ((1.099, None), (1.100, 100)):
            rd = N5._mk_run(tmp, f"thr_gbh_{r}", "GBh", st(3.3, [(100, r)]), flat)
            j = run_h(load_run(rd), "GBh", 1, gate_label="x")
            check(f"② GBh: 100 s 부터 ×{r} → 첫 조임 {expect} (GPU 문턱 1.10)", j["work"]["first_throttle_s"] == expect, (j["work"]["first_throttle_s"], j["work"]["throttle_time_s"]))
        for bad in (0, 9):
            try:
                run_h(runA, "GAh", bad, gate_label="x")
                check(f"③ 블록 {bad} → 오류", False, "판정이 나왔다")
            except JudgeError as err:
                check(f"③ 블록 {bad} → 오류", True, str(err))
        try:
            run_h(runA, "GAe", 1, gate_label="x")
            check("③ 칸 GAe → 오류 (이 래퍼는 GH 칸만)", False, "판정이 나왔다")
        except JudgeError as err:
            check("③ 칸 GAe → 오류 (이 래퍼는 GH 칸만)", True, str(err))
        try:
            run_h(runA, "GAh", 1, gate_label=None)
            check("③ --gate-label 없음 → 오류", False, "판정이 나왔다")
        except JudgeError as err:
            check("③ --gate-label 없음 → 오류", True, str(err))
        p = pair_h(jA, jB)
        check(f"④ pair GAh + GBh (같은 블록 5) → 일 비 ≈ {T_B * 10}/6,000 · block 5 · cells", p["block"] == 5
              and abs(p["work_ratio"] - jB["work"]["n"] / jA["work"]["n"]) < 1e-12 and p["cells"] == dict(a="GAh", b="GBh") and p["resource"] == "GPU", (p["block"], round(p["work_ratio"], 4), p["same_work_label"]))
        jB6 = run_h(runB, "GBh", 6, gate_label="x")
        for name, pa, pb in (("④ pair 블록 다름 (5 vs 6) → 오류", jA, jB6), ("④ pair A/B 자리 바뀜 → 오류", jB, jA), ("④ pair GAe + GBh → 오류", jAe, jB)):
            try:
                pair_h(pa, pb)
                check(name, False, "판정이 나왔다")
            except JudgeError as err:
                check(name, True, str(err))
        jbad = dict(jA)
        jbad["phone_watch"] = dict(n_events=1)
        try:
            pair_h(jbad, jB)
            check("④ 감시 이벤트 런 → pair 거부", False, "판정이 나왔다")
        except JudgeError as err:
            check("④ 감시 이벤트 런 → pair 거부", True, str(err))
        rd1 = N5._mk_run(tmp, "detA", "GBh", N5._steps(3.3, [(200, 1.2)]), N5._ramp(29.5, 38.4, float(T_B), 900.0, 34.0))
        rd2 = N5._mk_run(tmp, "detB", "GBh", N5._steps(3.3, [(200, 1.2)]), N5._ramp(29.5, 38.4, float(T_B), 900.0, 34.0))
        a1 = dumps(run_h(load_run(rd1), "GBh", 3, gate_label="x")).replace(rd1.replace("\\", "\\\\"), "X").replace(rd1, "X")
        a2 = dumps(run_h(load_run(rd2), "GBh", 3, gate_label="x")).replace(rd2.replace("\\", "\\\\"), "X").replace(rd2, "X")
        check("⑤ 결정성: run 같은 입력 두 번 = 같은 바이트 (경로 제외)", a1 == a2, f"{len(a1)} B")
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
    a.add_argument("--cell", required=True, choices=sorted(H_CELLS))
    a.add_argument("--block", required=True, type=int, choices=BLOCKS)
    a.add_argument("--gate-label", required=True)
    a.add_argument("--watch")
    a.add_argument("--gate-log")
    a.add_argument("--phone-watch")
    a.add_argument("--out")
    a = sub.add_parser("pair")
    a.add_argument("--a", required=True)
    a.add_argument("--b", required=True)
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
            res = run_h(load_run(args.run_dir), args.cell, args.block, load_watch(args.watch), args.gate_log, args.gate_label, args.phone_watch)
        elif args.cmd == "pair":
            res = pair_h(_load_json(args.a), _load_json(args.b))
        else:
            res = watchcheck(load_run(args.run_dir), args.phone_watch)
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
