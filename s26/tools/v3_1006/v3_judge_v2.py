# -*- coding: utf-8 -*-
"""v3_judge_v2.py — V3 v2 판정 스크립트 = `v3_judge.py` (SHA 접두 67ad5d42, 복사·수정 금지) + v2 칸 표.

`V3_사전등록_v2.md` (등록 커밋 d0a513c, SHA c478525d…) §4 · §5 = v1 §4 · §5 그대로 → 규칙 · 지표 · 문구 · 반올림 · 열 고르기는 전부
`v3_judge.py` 의 함수 (run_v3 · pair_v3 · cond_v3) 를 그대로 부른다. 바꾼 것은 칸 표 하나뿐이다:
  A2_base → v3_A_base_v2 · A2_ours → v3_A_ours_v1 · B2_base → v3_B_base_v2 · B2_ours → v3_B_ours_v1
v3_judge 의 함수는 모듈 전역 CELLS 를 읽으므로, v2 명령은 그 전역을 v2 표로 잠시 바꿔 부르고 끝나면 v1 표로 되돌린다 (_cells).
결과 보기 전 (2026-10-07 P1h 1부, v2 칸 0) 고정. results\\ 는 읽기만. 같은 입력 두 번 = 같은 바이트.

  py v3_judge_v2.py selftest
  py v3_judge_v2.py run <run_dir> --cell A2_base|A2_ours|B2_base|B2_ours --block 1|2 --gate-label <정확한 label> [--watch csv]
                        [--gate-log csv] [--phone-watch csv] --out f.json
  py v3_judge_v2.py pair --base f.json --ours f.json --out f.json
  py v3_judge_v2.py cond --pairs p_b1.json p_b2.json --pred <d1sim/out/v3_prediction_v2.json> --out f.json
  (watchcheck = `night1005e_judge.py watchcheck` 그대로)

P1h 가 정함 (결과 전):
  ① v1 칸 이름 (A_base …) 은 이 스크립트가 받지 않는다 (argparse choices = v2 칸 4개). v1 런을 v2 칸으로 판정하면 구간 표 착오로 오류.
  ② 런 · 블록 · 조건 JSON 의 kind 는 v3_judge 그대로 (v3_run · v3_pair · v3_cond) — 그 위에 judge_v2 (이 파일 · v3_judge SHA · 칸 표) 를 덧붙인다.
  ③ 조건 키 (cond) 는 A · B 그대로 → 예측 JSON (v3_prediction_v2.json) 의 blocks["A"|"B"] 를 읽는다.
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


V3_PREFIX = "67ad5d42"
_V3_PATH = _first_existing(os.path.join(HERE, "v3_judge.py"), os.path.join(OD_SIM, "v3_judge.py"),
                           os.path.join(REPO, "s26", "tools", "v3_1006", "v3_judge.py"))
if not _sha(_V3_PATH).startswith(V3_PREFIX):
    raise SystemExit(f"IMPORT_ERROR: v3_judge.py SHA {_sha(_V3_PATH)[:8]} ≠ {V3_PREFIX} ({_V3_PATH})")
_spec = importlib.util.spec_from_file_location("v3_judge", _V3_PATH)
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)
JudgeError, load_run, load_watch, dumps = V.JudgeError, V.load_run, V.load_watch, V.dumps

CELLS_V1 = V.CELLS
CELLS_V2 = {
    "A2_base": dict(cond="A", role="base", chain="v3_A_base_v2",
                    segs=[(1, 10), (100, 310), (1, 610), (100, 310), (1, 560), (100, 310), (1, 900)]),
    "A2_ours": dict(CELLS_V1["A_ours"]),
    "B2_base": dict(cond="B", role="base", chain="v3_B_base_v2",
                    segs=[(1, 50), (100, 330), (1, 550), (100, 330), (1, 560), (100, 340), (1, 569)]),
    "B2_ours": dict(CELLS_V1["B_ours"]),
}


@contextlib.contextmanager
def _cells(table):
    old = V.CELLS
    V.CELLS = table
    try:
        yield
    finally:
        V.CELLS = old


def judge_v2_info():
    return dict(file=os.path.abspath(__file__), v3_judge=dict(path=_V3_PATH, sha256=_sha(_V3_PATH), expected_prefix=V3_PREFIX),
                cells={k: v["chain"] for k, v in CELLS_V2.items()})


def run_v2(run, cell, block, watch=None, gate_log=None, gate_label=None, phone_watch=None):
    if cell not in CELLS_V2:
        raise JudgeError(f"칸 {cell} ∉ {list(CELLS_V2)} (v2 칸만)")
    with _cells(CELLS_V2):
        out = V.run_v3(run, cell, block, watch, gate_log, gate_label, phone_watch)
    out["judge_v2"] = judge_v2_info()
    return out


def pair_v2(base, ours):
    for x in (base, ours):
        if x.get("cell") not in CELLS_V2:
            raise JudgeError(f"v2 칸 런이 아님: {x.get('cell')}")
    with _cells(CELLS_V2):
        out = V.pair_v3(base, ours)
    out["judge_v2"] = judge_v2_info()
    return out


def cond_v2(pairs, pred, pred_path=None):
    with _cells(CELLS_V2):
        out = V.cond_v3(pairs, pred, pred_path)
    out["judge_v2"] = judge_v2_info()
    return out


# ============================================================ selftest (v1 selftest 전부 + v2 칸 표)
def selftest():
    res = []

    def check(name, cond, got):
        res.append((name, bool(cond), got))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc1 = V.selftest()
    mm = re.findall(r"selftest (?:PASS|FAIL) \((\d+)/(\d+)\)", buf.getvalue())
    m = mm[-1] if mm else None                      # 마지막 줄 = v3_judge 자신 (33/33)
    check("v3_judge selftest 그대로 33/33 (v1 칸 표)", rc1 == 0 and m and m[0] == m[1] == "33", m if m else buf.getvalue()[-200:])
    check("v3_judge SHA 접두 67ad5d42", _sha(_V3_PATH).startswith(V3_PREFIX), _sha(_V3_PATH)[:8])
    check("v1 selftest 뒤 v3_judge.CELLS = v1 표 그대로", V.CELLS is CELLS_V1 and set(V.CELLS) == {"A_base", "A_ours", "B_base", "B_ours"}, list(V.CELLS))
    same = {}
    for cell, c in CELLS_V2.items():
        ch = V._load_json(os.path.join(REPO, "tools", "chains", c["chain"] + ".json"))
        same[cell] = (ch["chain_id"] == c["chain"] and [(s["duty"], s["duration_s"]) for s in ch["segments"]] == c["segs"]
                      and [s["label"] for s in ch["segments"]] == [V._label(i, d) for i, (d, _) in enumerate(c["segs"])])
    check("v2 칸 표 = tools/chains (chain_id · duty · 길이 · 라벨)", all(same.values()), same)
    check("v2 ours 칸 = v1 ours 칸 (같은 체인 · 같은 구간)", CELLS_V2["A2_ours"] == CELLS_V1["A_ours"] and CELLS_V2["B2_ours"] == CELLS_V1["B_ours"], "")
    sig = {k: sum(L for _, L in c["segs"]) for k, c in CELLS_V2.items()}
    check("Σ: A2 3010 · B2 2729 (v1 과 같음) · 기준선 구간 7", sig == {"A2_base": 3010, "A2_ours": 3010, "B2_base": 2729, "B2_ours": 2729}
          and len(CELLS_V2["A2_base"]["segs"]) == len(CELLS_V2["B2_base"]["segs"]) == 7, sig)
    tmp = tempfile.mkdtemp(prefix="v3v2_selftest_")
    try:
        with _cells(CELLS_V2):
            rdA, SA = V._mk(tmp, "a2b", "A2_base", lambda t: 10.0, lambda t: 31.0 if t < 100 else (39.0 if t < 2000 else 33.5))
            rdAo, _ = V._mk(tmp, "a2o", "A2_ours", lambda t: 10.0, lambda t: 31.0 if t < 100 else 36.0)
            rdB, _ = V._mk(tmp, "b2b", "B2_base", lambda t: 10.0, lambda t: 31.0)
        with _cells(CELLS_V1):
            rdV1, _ = V._mk(tmp, "a1b", "A_base", lambda t: 10.0, lambda t: 31.0)
        jA = run_v2(load_run(rdA), "A2_base", 1, gate_label="x")
        n_exp = sum(s["n"] for s in SA["segments"])
        check("run A2_base: n = 구간 Σ · 조임 0 · 가동 칸 31+31+31", jA["work"]["n"] == n_exp > 0 and jA["work"]["throttle_time_s"] == 0
              and jA["work"]["n_active_bins"] == 93 and jA["chain_id"] == "v3_A_base_v2", (jA["work"]["n"], jA["work"]["n_active_bins"]))
        jB = run_v2(load_run(rdB), "B2_base", 2, gate_label="x")
        check("run B2_base: 가동 칸 33+33+34", jB["work"]["n_active_bins"] == 100, jB["work"]["n_active_bins"])
        check("run 뒤 v3_judge.CELLS = v1 표로 되돌림", V.CELLS is CELLS_V1, list(V.CELLS))
        for name, fn in (("v2 기준선 런을 v1 칸 A_base 로 → 오류", lambda: run_v2(load_run(rdA), "A_base", 1, gate_label="x")),
                         ("v2 기준선 런을 A2_ours 로 → 오류", lambda: run_v2(load_run(rdA), "A2_ours", 1, gate_label="x")),
                         ("v2 기준선 런을 B2_base 로 → 오류", lambda: run_v2(load_run(rdA), "B2_base", 1, gate_label="x")),
                         ("v1 기준선 런 (v3_A_base_v1) 을 A2_base 로 → 오류", lambda: run_v2(load_run(rdV1), "A2_base", 1, gate_label="x")),
                         ("--gate-label 없음 → 오류", lambda: run_v2(load_run(rdA), "A2_base", 1))):
            try:
                fn()
                check(name, False, "no error")
            except JudgeError as e:
                check(name, True, str(e)[:60])
        check("오류 뒤에도 v3_judge.CELLS = v1 표", V.CELLS is CELLS_V1, "")
        jo = run_v2(load_run(rdAo), "A2_ours", 1, gate_label="x")
        p1 = pair_v2(jA, jo)
        check("pair A2: Δ = 39.0 − 36.0 = 3.0 · r = n_ours / n_base", p1["deltas"]["d_max_skin"] == 3.0 and p1["r"] == V._r6(jo["work"]["n"] / jA["work"]["n"]),
              (p1["deltas"]["d_max_skin"], p1["r"]))
        try:
            pair_v2(jo, jA)
            check("pair: 자리 바뀜 → 오류", False, "no error")
        except JudgeError as e:
            check("pair: 자리 바뀜 → 오류", True, str(e)[:40])
        try:
            pair_v2(dict(jA, cell="A_base"), jo)
            check("pair: v1 칸 런 → 오류", False, "no error")
        except JudgeError as e:
            check("pair: v1 칸 런 → 오류", True, str(e)[:40])
        p2 = dict(p1, block=2)
        pred = V._fpred("A", 3.0, 3.0)
        c = cond_v2([p1, p2], pred)
        c_again = cond_v2([p2, p1], pred)
        check("cond A2: 같은 입력 = 같은 바이트 · ③ 문구 = v3_judge L3 · 결론 = conclusion_row", dumps(c) == dumps(c_again) and c["j3"]["label"] in V.L3.values()
              and c["conclusion"] == V.conclusion_row("A", c["j3"], c["j4_main"]), c["j3"]["label"])
        c1 = cond_v2([p1], pred)
        check("cond 블록 1개 → 판정 안 함", c1["judged"] is False, c1["label"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(1 for _, ok, _ in res if ok)
    for name, ok, got in res:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  got={got}"))
    print(f"selftest v2 {'PASS' if n_ok == len(res) else 'FAIL'} ({n_ok}/{len(res)})")
    return 0 if n_ok == len(res) else 1


# ============================================================ CLI
def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    r = sub.add_parser("run")
    r.add_argument("run_dir"); r.add_argument("--cell", required=True, choices=list(CELLS_V2)); r.add_argument("--block", type=int, required=True)
    r.add_argument("--gate-label", required=True); r.add_argument("--watch"); r.add_argument("--gate-log"); r.add_argument("--phone-watch")
    r.add_argument("--out", required=True)
    p = sub.add_parser("pair")
    p.add_argument("--base", required=True); p.add_argument("--ours", required=True); p.add_argument("--out", required=True)
    c = sub.add_parser("cond")
    c.add_argument("--pairs", nargs="+", required=True); c.add_argument("--pred", required=True); c.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return selftest()
    try:
        if a.cmd == "run":
            out = run_v2(load_run(a.run_dir), a.cell, a.block, load_watch(a.watch), a.gate_log, a.gate_label, a.phone_watch)
        elif a.cmd == "pair":
            out = pair_v2(V._load_json(a.base), V._load_json(a.ours))
        else:
            out = cond_v2([V._load_json(x) for x in a.pairs], V._load_json(a.pred), a.pred)
    except JudgeError as e:
        print("JUDGE_ERROR:", e)
        return 2
    s = dumps(out)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(s + "\n")
    print(s[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
